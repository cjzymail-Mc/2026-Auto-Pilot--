"""Synthetic-only authentication regression; never reads the real profile."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bpm import browser_probe
from bpm.browser_probe import BLOCKED, HOST, PASS, Probe
from bpm.login import LoginProbe
from bpm.query import LoginUnavailable, QueryCLI


def login_probe(state="UNKNOWN", *, wait=0, force=False):
    p = object.__new__(LoginProbe)
    p.args = SimpleNamespace(login_wait=wait, force_scan=force)
    p.page = MagicMock()
    p.checks = {"c1_entry_login": {"status": "NOT_RUN"}}
    p._last_login_state = state
    p._saw_login_gate = state == "LOGIN_REQUIRED"
    p.login_state = MagicMock(return_value=(state, {}, {}))
    p.log_event = MagicMock()
    p.say = MagicMock()
    return p


class LoginClassificationTests(unittest.TestCase):
    def test_unknown_is_blocked_without_scan_prompt(self):
        p = login_probe()
        self.assertEqual(p.phase_entry(), "UNKNOWN")
        self.assertEqual(p.checks["c1_entry_login"]["status"], BLOCKED)
        self.assertEqual(p.checks["c1_entry_login"]["reason"], "LOGIN_STATE_UNKNOWN")
        p.say.assert_not_called()
        self.assertFalse(any(c.kwargs.get("event") == "login_window_ready"
                             for c in p.log_event.call_args_list))

    def test_only_observed_login_gate_can_prompt(self):
        p = login_probe("LOGIN_REQUIRED", wait=5)
        self.assertEqual(p.phase_entry(), "LOGIN_REQUIRED")
        p.say.assert_called_once()
        self.assertEqual(p._last_login_state, "LOGIN_REQUIRED")

    def test_zero_wait_observes_gate_without_asking_to_scan(self):
        p = login_probe("LOGIN_REQUIRED")
        self.assertEqual(p.phase_entry(), "LOGIN_REQUIRED")
        p.say.assert_not_called()
        self.assertEqual(p.checks["c1_entry_login"]["status"], BLOCKED)

    def test_live_identity_is_required_for_success(self):
        p = login_probe("LOGGED_IN")
        self.assertEqual(p.phase_entry(), PASS)
        self.assertEqual(p.checks["c1_entry_login"]["status"], PASS)
        p.say.assert_not_called()

    def test_gate_then_unknown_never_becomes_expired_or_refreshes_qr(self):
        p = login_probe("LOGIN_REQUIRED", wait=1)
        p.login_state.return_value = ("UNKNOWN", {}, {})
        with patch("bpm.login.time.monotonic", side_effect=[0, .1, 1.1]):
            self.assertEqual(p.wait_login(), "UNKNOWN")
        self.assertEqual(p.checks["c1_entry_login"]["reason"], "LOGIN_STATE_UNKNOWN")
        p.page.evaluate.assert_not_called()
        p.page.reload.assert_not_called()

    def test_observed_gate_timeout_stays_blocked(self):
        p = login_probe("LOGIN_REQUIRED")
        self.assertEqual(p.wait_login(), BLOCKED)
        self.assertEqual(p.checks["c1_entry_login"]["reason"], "WAIT_HUMAN_LOGIN")

    def test_verified_scan_success_keeps_existing_fresh_scan_guard(self):
        p = login_probe("LOGIN_REQUIRED", wait=1, force=True)
        p.login_state.return_value = ("LOGGED_IN", {}, {})
        with patch("bpm.login.time.monotonic", side_effect=[0, .1]):
            self.assertEqual(p.wait_login(), PASS)
        self.assertTrue(p._fresh_scan_confirmed)

    def test_normal_login_uses_original_persistent_launch(self):
        p = login_probe()
        with patch.object(Probe, "_launch", autospec=True) as launch:
            p._launch()
        launch.assert_called_once_with(p)
        self.assertEqual(p.log_event.call_args.kwargs["mode"], "persistent_profile_reuse")

    def test_forced_scan_still_uses_clean_context_without_injection(self):
        p = login_probe(force=True)
        p._inject_session_state = MagicMock()
        pw = MagicMock()
        with patch("playwright.sync_api.sync_playwright", return_value=pw), \
                patch.object(Probe, "_launch") as persistent:
            p._launch()
        persistent.assert_not_called()
        p._inject_session_state.assert_not_called()
        pw.start.return_value.chromium.launch_persistent_context.assert_not_called()
        pw.start.return_value.chromium.launch.assert_called_once()
        self.assertEqual(p.log_event.call_args.kwargs["mode"], "fresh_scan_context")


class QueryLoginGateTests(unittest.TestCase):
    def query(self, state, *, wait=0):
        q = object.__new__(QueryCLI)
        q.o = SimpleNamespace(login_wait=wait)
        q.timings = {}
        q.p = MagicMock()
        q.p.phase_entry.return_value = state
        q.p._last_login_state = state
        return q

    def test_unknown_does_not_wait_or_persist(self):
        q = self.query("UNKNOWN", wait=900)
        with self.assertRaises(LoginUnavailable) as cm:
            q.open_session()
        self.assertEqual(cm.exception.auth_state, "UNKNOWN")
        self.assertNotIn("扫码", str(cm.exception))
        q.p.wait_login.assert_not_called()
        q.p._save_session_state.assert_not_called()

    def test_zero_wait_gate_does_not_wait_or_persist(self):
        q = self.query("LOGIN_REQUIRED")
        with self.assertRaises(LoginUnavailable) as cm:
            q.open_session()
        self.assertEqual(cm.exception.auth_state, "LOGIN_REQUIRED")
        q.p.wait_login.assert_not_called()
        q.p._save_session_state.assert_not_called()

    def test_gate_becoming_unknown_keeps_unknown_reason(self):
        q = self.query("LOGIN_REQUIRED", wait=1)
        q.p.wait_login.return_value = "UNKNOWN"
        q.p._last_login_state = "UNKNOWN"
        with self.assertRaises(LoginUnavailable) as cm:
            q.open_session()
        self.assertEqual(cm.exception.auth_state, "UNKNOWN")
        q.p._save_session_state.assert_not_called()

    def test_verified_reuse_keeps_existing_persistence_path(self):
        q = self.query(PASS)
        q.open_session()
        q.p.wait_login.assert_not_called()
        q.p._save_session_state.assert_called_once()
        self.assertIs(q.page, q.p.page)


class SyntheticStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-proxy-server"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "synthetic-state.json"
        self.ctx = self.browser.new_context()
        self.addCleanup(self.ctx.close)
        # Every request is fulfilled locally, including the production-like origin.
        self.ctx.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html", body="<title>SYNTHETIC ONLY</title>"))
        self.p = object.__new__(Probe)
        self.p.ctx = self.ctx
        self.p.log_event = MagicMock()
        self.payload = {
            "cookies": [{"name": "synthetic_cookie", "value": "old-fixture",
                         "domain": "bpm.qiaodan.com", "path": "/"}],
            "origins": [{"origin": HOST, "localStorage": [
                {"name": "synthetic_local", "value": "old-fixture"}]}],
            "_page_storage": {HOST: {"synthetic_session": "old-fixture"}}}

    def inject(self, *, usable=True):
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")
        with patch.object(browser_probe, "SESSION_STATE", self.path), \
                patch.object(browser_probe, "_session_state_usable", return_value=usable):
            self.p._inject_session_state()

    def page(self, host=HOST):
        page = self.ctx.new_page()
        page.goto(host + "/synthetic-auth-fixture")
        return page

    @staticmethod
    def values(page):
        return page.evaluate("() => [localStorage.getItem('synthetic_local'),"
                             "sessionStorage.getItem('synthetic_session')]")

    def test_missing_values_restored_but_refresh_survives_reload_and_navigation(self):
        self.inject()
        page = self.page()
        self.assertEqual(self.values(page), ["old-fixture", "old-fixture"])
        page.evaluate("() => {localStorage.setItem('synthetic_local','site-refreshed');"
                      "sessionStorage.setItem('synthetic_session','site-refreshed')}")
        page.reload()
        page.goto(HOST + "/second-synthetic-document")
        self.assertEqual(self.values(page), ["site-refreshed", "site-refreshed"])

    def test_empty_existing_values_are_not_treated_as_missing(self):
        self.inject()
        page = self.page()
        page.evaluate("() => {localStorage.setItem('synthetic_local','');"
                      "sessionStorage.setItem('synthetic_session','')}")
        page.reload()
        self.assertEqual(self.values(page), ["", ""])

    def test_existing_profile_cookie_is_not_overwritten(self):
        fresh = dict(self.payload["cookies"][0], value="site-refreshed")
        self.ctx.add_cookies([fresh])
        self.inject()
        cookies = [c for c in self.ctx.cookies() if c["name"] == fresh["name"]]
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["value"], "site-refreshed")

    def test_storage_is_confined_to_original_origin(self):
        self.inject()
        page = self.page("https://unrelated.invalid")
        self.assertEqual(self.values(page), [None, None])
        self.assertEqual(self.ctx.cookies("https://unrelated.invalid"), [])

    def test_missing_or_expired_state_is_skipped_without_installing_script(self):
        self.inject(usable=False)
        page = self.page()
        self.assertEqual(self.values(page), [None, None])
        self.assertEqual(self.ctx.cookies(), [])
        self.assertEqual(self.p.log_event.call_args.kwargs["event"], "session_state_skip")

    def test_real_missing_file_and_expired_legacy_file_fail_closed(self):
        with patch.object(browser_probe, "SESSION_STATE", self.path):
            self.p._inject_session_state()
        self.path.write_text(json.dumps(self.payload), encoding="utf-8")
        os.utime(self.path, (1, 1))
        with patch.object(browser_probe, "SESSION_STATE", self.path):
            self.p._inject_session_state()
        self.assertTrue(all(c.kwargs["event"] == "session_state_skip"
                            for c in self.p.log_event.call_args_list))
        self.assertEqual(self.values(self.page()), [None, None])

    def test_malformed_state_error_exports_only_exception_type(self):
        self.path.write_text("synthetic-private-text", encoding="utf-8")
        with patch.object(browser_probe, "SESSION_STATE", self.path), \
                patch.object(browser_probe, "_session_state_usable", return_value=True):
            self.p._inject_session_state()
        event = self.p.log_event.call_args.kwargs
        self.assertEqual(event, {"event": "session_state_inject_error",
                                 "error_type": "JSONDecodeError"})
        self.assertNotIn("synthetic-private-text", repr(event))


if __name__ == "__main__":
    unittest.main()
