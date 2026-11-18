"""Synthetic login timing and identity regressions; no real profile access."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bpm.browser_probe import BLOCKED, PASS, Budget


spec = importlib.util.spec_from_file_location(
    "approval_watch", Path(__file__).resolve().parents[1]
    / "feature03-自动审批快递单/approval_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def probe():
    p = MagicMock()
    p.args = SimpleNamespace(login_wait=480, force_scan=False, expect_name=None)
    p.checks = {"c1_entry_login": {}}
    p._fresh_scan_confirmed = False
    p._watch_account = None
    p.ctx._bpm_guard = None
    return p


class BackgroundEntryTests(unittest.TestCase):
    def test_login_gate_then_unknown_then_authenticated(self):
        p = probe()
        p.phase_entry.side_effect = lambda: (
            "LOGIN_REQUIRED" if p.args.login_wait == 0 else self.fail("Hidden QR prompt enabled"))
        p.login_state.side_effect = [("UNKNOWN", {}, {}), ("LOGGED_IN", {}, {})]
        self.assertEqual(watch.background_entry(p), PASS)
        self.assertEqual(p.page.wait_for_timeout.call_count, 2)
        p.page.wait_for_timeout.assert_called_with(600)
        self.assertEqual(p.checks["c1_entry_login"]["status"], PASS)
        self.assertEqual(p.args.login_wait, 480)
        self.assertFalse(p._fresh_scan_confirmed)
        p.wait_login.assert_not_called()

    def test_persistent_gate_and_unknown_stop_at_deadline(self):
        for state in ("LOGIN_REQUIRED", "UNKNOWN"):
            with self.subTest(state=state):
                p = probe()
                p.phase_entry.return_value = state
                p.login_state.return_value = (state, {}, {})
                with patch.object(watch.time, "monotonic", side_effect=[0, 0, 31, 31]):
                    self.assertEqual(watch.background_entry(p), state)
                p.page.wait_for_timeout.assert_called_once_with(600)
                self.assertEqual(p.checks["c1_entry_login"]["status"], BLOCKED)
                self.assertEqual(p.args.login_wait, 480)

    def test_exception_restores_login_wait(self):
        p = probe()
        p.phase_entry.side_effect = RuntimeError("synthetic network failure")
        with self.assertRaises(RuntimeError):
            watch.background_entry(p)
        self.assertEqual(p.args.login_wait, 480)


class WatchLoginTests(unittest.TestCase):
    def test_restored_session_does_not_open_scan_window(self):
        p = probe()
        with patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "background_entry", return_value=PASS), \
                patch.object(watch, "current_account", return_value=("synthetic-a", "测试甲")):
            self.assertEqual(watch.login(p, False), ("synthetic-a", "测试甲"))
        p._launch_isolated_guarded_context.assert_called_once_with(headless=True)
        p.wait_login.assert_not_called()
        p._save_session_state.assert_called_once()
        self.assertFalse(p._fresh_scan_confirmed)

    def test_unknown_restore_does_not_force_scan_or_save(self):
        p = probe()
        with patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "background_entry", return_value="UNKNOWN"):
            with self.assertRaises(watch.LoginLost):
                watch.login(p, False)
        p.wait_login.assert_not_called()
        p._save_session_state.assert_not_called()

    def scanned_login(self, *, changed=False, force=False):
        p = probe()
        p.phase_entry.return_value = "LOGIN_REQUIRED"
        def scan():
            self.assertTrue(p.args.force_scan)
            p._fresh_scan_confirmed = True
            return PASS
        p.wait_login.side_effect = scan
        saved_flags = []
        p._save_session_state.side_effect = lambda: saved_flags.append(p._fresh_scan_confirmed)
        # Restoring a fresh scan must not reset its scan anchor a second time.
        def restored(_p):
            self.assertFalse(_p._fresh_scan_confirmed)
            return PASS
        accounts = [("synthetic-a", "测试甲"),
                    ("synthetic-b", "测试乙") if changed else ("synthetic-a", "测试甲")]
        with patch("bpm.session.state_usable", return_value=False), \
                patch.object(watch, "background_entry", side_effect=restored), \
                patch.object(watch, "current_account", side_effect=accounts):
            if changed:
                with self.assertRaises(watch.LoginLost):
                    watch.login(p, force)
            else:
                self.assertEqual(watch.login(p, force), accounts[0])
        self.assertEqual(saved_flags, [True] if changed else [True, False])
        self.assertEqual(p._required_name, "测试甲")

    def test_scan_then_delayed_background_restore(self):
        self.scanned_login()

    def test_forced_scan_then_background_restore(self):
        self.scanned_login(force=True)

    def test_account_switch_during_handoff_is_rejected(self):
        self.scanned_login(changed=True)


class MonitorLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.p = probe()
        self.p.budget = SimpleNamespace(wall_cap=1200)
        self.p.page.is_closed.side_effect = [False, False, True]
        self.inbox = MagicMock()
        self.inbox.query.return_value = []
        self.account = ("synthetic-a", "测试甲")

    def run_monitor(self):
        with patch.object(watch, "Inbox", return_value=self.inbox), \
                patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "ready_inbox", side_effect=lambda p, inbox: inbox.open()):
            watch.monitor(self.p, MagicMock(), self.account, 10)

    def test_startup_cap_remains_until_inbox_ready_then_watch_survives_twenty_minutes(self):
        self.inbox.open.side_effect = lambda: self.assertEqual(self.p.budget.wall_cap, 1200)
        self.run_monitor()
        self.assertEqual(self.p.budget.wall_cap, float("inf"))
        self.assertEqual(self.inbox.query.call_count, 2)
        self.p.page.wait_for_timeout.assert_called_with(10000)
        # Exercise the real watchdog with a simulated two-hour runtime. If the
        # cap is still finite, its original os._exit(83) path must fail this test.
        budget = object.__new__(Budget)
        budget.wall_cap = self.p.budget.wall_cap
        budget._dead = False
        budget._on_wall_fire = MagicMock()
        budget.monotonic_wall = lambda: 7200
        with patch("bpm.browser_probe.os._exit") as exit_process, \
                patch("bpm.browser_probe.time.sleep", side_effect=lambda _: setattr(budget, "_dead", True)):
            budget._watch()
        exit_process.assert_not_called()
        budget._on_wall_fire.assert_not_called()

    def test_transient_query_error_is_logged_and_next_cycle_continues(self):
        self.inbox.query.side_effect = [watch.WatchError("synthetic retry"), []]
        self.run_monitor()
        events = [call.kwargs["event"] for call in self.p.log_event.call_args_list]
        self.assertEqual(events, ["approval_monitor_started", "approval_monitor_retry",
                                  "approval_monitor_cycle"])
        self.assertEqual(self.inbox.query.call_count, 2)

    def test_expired_local_authentication_still_stops_monitor(self):
        with patch.object(watch, "Inbox", return_value=self.inbox), \
                patch("bpm.session.state_usable", return_value=False):
            with self.assertRaises(watch.LoginLost):
                watch.monitor(self.p, MagicMock(), self.account, 10)
        self.inbox.query.assert_not_called()

    def test_account_change_still_stops_monitor(self):
        self.inbox.query.side_effect = watch.LoginLost("synthetic account switch")
        with self.assertRaises(watch.LoginLost):
            self.run_monitor()

    def test_new_arrival_opens_while_prior_approval_tab_stays_open(self):
        self.p.page.is_closed.side_effect = [False, False, False, True]
        first = {"id": "synthetic-first", "toUserCode": self.account[0],
                 "bizStatus": 7, "status": 0, "kind": 1}
        second = dict(first, id="synthetic-second")
        self.inbox.query.side_effect = [[first], [first, second], [first, second]]
        window = MagicMock()
        prior_tab = MagicMock()
        new_tab = MagicMock()
        window.pages = [prior_tab]
        window.open.side_effect = [prior_tab, new_tab]
        with patch.object(watch, "Inbox", return_value=self.inbox), \
                patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "ready_inbox", side_effect=lambda p, inbox: inbox.open()), \
                patch.object(watch, "detail_url", side_effect=["synthetic:first", "synthetic:second"]), \
                patch.object(watch, "flash_browser", return_value=True):
            watch.monitor(self.p, window, self.account, 10)
        self.assertEqual(self.inbox.query.call_count, 3)
        self.assertEqual(window.open.call_count, 2)  # Already-open tasks are not duplicated.
        self.assertEqual(window.open.call_args_list[1].args, (self.account, "synthetic:second"))
        prior_tab.close.assert_not_called()
        window.close.assert_not_called()
        self.assertEqual(self.p.page.wait_for_timeout.call_count, 3)


class MainExitTests(unittest.TestCase):
    def run_main(self, error):
        p = probe()
        window = MagicMock()
        window.pages = []
        with patch.object(watch, "load_config", return_value=(Path.cwd(), watch.CONFIG_DEFAULTS)), \
                patch.object(watch, "disable_console_quick_edit", return_value={"status": "configured"}), \
                patch.object(watch.sys, "platform", "win32"), \
                patch("bpm.login.LoginProbe", return_value=p), \
                patch.object(watch, "ApprovalWindow", return_value=window), \
                patch.object(watch, "startup_login", return_value=("synthetic-a", "测试甲")), \
                patch("bpm.approval.ApprovalJournal"), \
                patch.object(watch, "monitor", side_effect=error) as monitored:
            result = watch.main([])
        from bpm.approval import AutoApprover
        self.assertEqual(len(monitored.call_args.args), 5)
        self.assertIsInstance(monitored.call_args.args[-1], AutoApprover)
        window.close.assert_called_once()
        p._close_browser.assert_called_once()
        p.release_lock.assert_called_once()
        return result, [call.kwargs for call in p.log_event.call_args_list]

    def test_manual_stop_is_recorded_and_resources_released(self):
        result, events = self.run_main(KeyboardInterrupt())
        self.assertEqual(result, 0)
        self.assertEqual(events[-1], {"event": "approval_monitor_stopped", "reason": "interrupted"})

    def test_unexpected_failure_records_type_without_raw_exception(self):
        result, events = self.run_main(ValueError("synthetic private payload"))
        self.assertEqual(result, 2)
        self.assertEqual(events[0], {"event": "approval_console_input", "status": "configured"})
        self.assertEqual(events[1], {"event": "approval_monitor_failed", "reason": "error",
                                     "error_type": "ValueError"})
        self.assertNotIn("synthetic private payload", repr(events))


class VisibleWindowContextTests(unittest.TestCase):
    """2026-11-16：全量 route.fetch 中转把首开详情页放大 4 分钟并阻塞主循环；
    可见提醒窗口改用普通 context，业务探测 context 的守卫不受影响。"""

    def test_visible_context_is_plain_without_request_guard(self):
        p = probe()
        window = watch.ApprovalWindow(p)
        window.browser = MagicMock()
        source = MagicMock()
        context = window._new_visible_context(source)
        window.browser.new_context.assert_called_once_with(
            ignore_https_errors=False, service_workers="block",
            viewport={"width": 1440, "height": 900},
            storage_state=source.context.storage_state())
        self.assertIs(context, window.browser.new_context.return_value)
        p._new_guarded_context.assert_not_called()
        kwargs = p.log_event.call_args.kwargs
        self.assertEqual(kwargs.get("event"), "approval_window_context")
        self.assertEqual(kwargs.get("request_guard"), "none")

    def test_open_builds_visible_context_through_helper(self):
        p = probe()
        window = watch.ApprovalWindow(p)
        window.browser = MagicMock()
        window.browser.is_connected.return_value = True
        page = MagicMock()
        url = "https://bpm.qiaodan.com/oa/express?type=view&id=synthetic&task=1"
        page.url = url
        context = MagicMock()
        context.new_page.return_value = page
        p.page.evaluate.return_value = {"qd_access_token": None, "qd_refresh_token": None}
        with patch.object(watch, "current_account", return_value=("synthetic-a", "测试甲")), \
                patch.object(window, "_new_visible_context", return_value=context) as helper:
            opened = window.open(("synthetic-a", "测试甲"), url)
        helper.assert_called_once_with(p.page)
        p._new_guarded_context.assert_not_called()
        self.assertIs(opened, page)
        p._pw.chromium.launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
