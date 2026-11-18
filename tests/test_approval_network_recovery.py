"""Network/state counterexamples. All endpoints, clocks and credentials are synthetic."""
import json
import socket
import ssl
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bpm import direct_network as dn
from bpm.network_guard import ContextGuard, NetworkBlocked
from bpm.browser_probe import PASS
from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout
from test_approval_watch_login import probe, watch


class GuardStateTests(unittest.TestCase):
    def setUp(self):
        self.p = probe()
        self.guard = ContextGuard()
        self.p.ctx.pages = []
        self.guard.install(self.p.ctx)
        self.handler = self.p.ctx.route.call_args.args[1]

    def request(self, host="bpm.qiaodan.com", kind="document", status=200, error=None):
        route = MagicMock()
        route.request.url = "https://" + host + "/synthetic"
        route.request.resource_type = kind
        response = MagicMock(status=status)
        with patch.object(self.guard, "_fetch", side_effect=error, return_value=response):
            self.handler(route)
        return response

    def test_optional_failure_does_not_veto_scan(self):
        self.request("rybbit.dev.qiaodan.com", "fetch", error=OSError("synthetic"))
        self.assertEqual(self.guard.critical_failures(), [])
        self.p.phase_entry.return_value = "LOGIN_REQUIRED"
        self.assertEqual(watch.background_entry(self.p, timeout=0), "LOGIN_REQUIRED")

    def test_critical_failure_is_current_attempt_and_success_clears_it(self):
        self.request(error=OSError("ECONNRESET"))
        self.assertEqual(self.guard.critical_failures(), ["CONNECTION"])
        self.request()
        self.assertEqual(self.guard.critical_failures(), [])
        self.request(error=OSError("synthetic timeout"))
        self.guard.begin_attempt()
        self.assertEqual(self.guard.critical_failures(), [])

    def test_current_critical_failure_does_not_become_scan(self):
        def entry():
            self.request(error=OSError("ECONNRESET"))
            return "LOGIN_REQUIRED"
        self.p.phase_entry.side_effect = entry
        with self.assertRaises(watch.NetworkUnavailable):
            watch.background_entry(self.p, timeout=0)
        self.p.wait_login.assert_not_called()

    def test_policy_auth_tls_stop_instead_of_retry(self):
        for reason, exception in (("POLICY", NetworkBlocked), ("AUTH", watch.LoginLost),
                                  ("TLS", watch.WatchError)):
            self.guard.failures = {"synthetic": reason}
            with self.assertRaises(exception):
                watch.retryable_browser_error(self.p, BrowserTimeout("synthetic"))

    def test_visible_guard_does_not_replace_background_ownership(self):
        visible = ContextGuard()
        visible.failures["synthetic"] = "POLICY"
        self.p._request_guard = visible
        watch.check_transport(self.p)

    def test_expected_close_and_dispose_error_do_not_poison_auth(self):
        self.request(error=BrowserError("Target closed"))
        self.assertEqual(self.guard.critical_failures(), [])
        response = MagicMock(status=200)
        response.dispose.side_effect = RuntimeError("synthetic dispose")
        route = MagicMock()
        route.request.url = "https://bpm.qiaodan.com/synthetic"
        route.request.resource_type = "document"
        with patch.object(self.guard, "_fetch", return_value=response):
            self.handler(route)
        self.assertEqual(self.guard.critical_failures(), [])


class RecoveryTests(unittest.TestCase):
    def test_completed_force_scan_is_consumed_once_after_handoff_failure(self):
        p = probe()
        p.phase_entry.return_value = "LOGIN_REQUIRED"
        def scan():
            p._fresh_scan_confirmed = True
            return PASS
        p.wait_login.side_effect = scan
        flags = []
        p._save_session_state.side_effect = lambda: flags.append(p._fresh_scan_confirmed)
        with patch("bpm.direct_network.proxy_environment", return_value={}), \
                patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "background_entry", side_effect=[watch.NetworkUnavailable("synthetic"), PASS]), \
                patch.object(watch, "current_account", return_value=("synthetic-a", "测试甲")), \
                patch.object(watch.time, "sleep"):
            watch.startup_login(p, True)
        self.assertEqual(p.wait_login.call_count, 1)
        self.assertEqual(flags, [True, False])
        self.assertEqual(p._required_name, "测试甲")

    def test_bound_scan_cannot_switch_identity_or_extend_expired_state(self):
        for usable in (True, False):
            p = probe()
            p._watch_account = ("synthetic-a", "测试甲")
            with patch("bpm.session.state_usable", return_value=usable), \
                    patch.object(watch, "background_entry", return_value=PASS), \
                    patch.object(watch, "current_account", return_value=("synthetic-b", "测试乙")):
                with self.assertRaises(watch.LoginLost):
                    watch.login(p, True)
            p.wait_login.assert_not_called()
            p._save_session_state.assert_not_called()

    def test_initial_inbox_timeout_retries_until_first_authenticated_query(self):
        p, inbox = probe(), MagicMock()
        inbox.open.side_effect = [BrowserTimeout("synthetic"), None]
        with patch("bpm.session.state_usable", return_value=True):
            watch.ready_inbox(p, inbox)
        self.assertEqual(inbox.open.call_count, 2)
        inbox.query.assert_called_once()
        p.page.wait_for_timeout.assert_called_once_with(600)

    def test_unknown_browser_error_is_not_network_retry(self):
        p, inbox = probe(), MagicMock()
        inbox.open.side_effect = BrowserError("synthetic unknown failure")
        with patch("bpm.session.state_usable", return_value=True):
            with self.assertRaises(BrowserError):
                watch.ready_inbox(p, inbox)
        self.assertEqual(inbox.open.call_count, 1)

    def test_network_recovery_preserves_old_tab_and_deduplication(self):
        p, inbox, window = probe(), MagicMock(), MagicMock()
        p.budget = SimpleNamespace(wall_cap=1200)
        p.page.is_closed.side_effect = [False, False, False, True]
        account = ("synthetic-a", "测试甲")
        a = {"id": "synthetic-a", "toUserCode": account[0], "bizStatus": 7, "status": 0, "kind": 1}
        b = dict(a, id="synthetic-b")
        inbox.query.side_effect = [[], [a], BrowserTimeout("synthetic"), [], [a, b]]
        with patch.object(watch, "Inbox", return_value=inbox), \
                patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "detail_url", side_effect=["synthetic:a", "synthetic:b"]), \
                patch.object(watch, "flash_browser", return_value=True):
            watch.monitor(p, window, account, 10)
        self.assertEqual(window.open.call_count, 2)
        self.assertEqual(inbox.open.call_count, 2)
        window.close.assert_not_called()

    def test_domain_drift_is_not_recovered_by_navigation(self):
        p, inbox = probe(), MagicMock()
        p.page.is_closed.return_value = False
        p.budget = SimpleNamespace(wall_cap=1200)
        inbox.query.side_effect = [[], watch.IntegrityError("synthetic drift")]
        with patch.object(watch, "Inbox", return_value=inbox), \
                patch("bpm.session.state_usable", return_value=True):
            with self.assertRaises(watch.IntegrityError):
                watch.monitor(p, MagicMock(), ("synthetic-a", "测试甲"), 10)
        self.assertEqual(inbox.open.call_count, 1)


class CleanupTests(unittest.TestCase):
    def test_context_failure_still_closes_browser_and_is_idempotent(self):
        window = watch.ApprovalWindow(probe())
        browser = window.browser = MagicMock()
        window.context = MagicMock()
        original = RuntimeError("synthetic first cleanup")
        browser.close.side_effect = ValueError("synthetic second cleanup")
        with patch.object(ContextGuard, "close", side_effect=original):
            with self.assertRaises(RuntimeError) as caught:
                window.close()
        self.assertIs(caught.exception, original)
        browser.close.assert_called_once()
        self.assertIsNone(window.context)
        self.assertIsNone(window.browser)
        window.close()

    def test_unguarded_context_keeps_original_public_close(self):
        context = MagicMock()
        context._bpm_guard = None
        ContextGuard.close(context)
        context.close.assert_called_once()
        context.set_offline.assert_not_called()


class DirectDiagnosticTests(unittest.TestCase):
    def test_connects_checked_ipv6_and_ipv4_with_original_sni(self):
        addresses = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2001:db8::1", 443, 0, 0)),
                     (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))]
        first, second = MagicMock(), MagicMock()
        first.__enter__.return_value = first
        second.__enter__.return_value = second
        first.connect.side_effect = OSError("synthetic unreachable")
        with patch.object(dn.socket, "getaddrinfo", return_value=addresses) as resolve, \
                patch.object(dn.socket, "socket", side_effect=[first, second]), \
                patch.object(dn.ssl, "create_default_context") as tls:
            self.assertEqual(dn._tls_probe("bpm.qiaodan.com")["status"], "PASS")
        self.assertEqual(resolve.call_count, 1)
        first.connect.assert_called_once_with(addresses[0][4])
        second.connect.assert_called_once_with(addresses[1][4])
        tls.return_value.wrap_socket.assert_called_once_with(second, server_hostname="bpm.qiaodan.com")

    def test_real_worker_hard_deadline_cancels_blocked_dns_equivalent(self):
        real_run = subprocess.run
        def blocked(*args, **kwargs):
            return real_run([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        with patch.object(dn.subprocess, "run", side_effect=blocked):
            result = dn.direct_tls_check("bpm.qiaodan.com", timeout=.1)
        self.assertEqual(result["reason"], "DIAGNOSTIC_DEADLINE")

    def test_proxy_credentials_are_not_exported(self):
        with patch.object(dn.sys, "platform", "linux"), \
                patch.dict(dn.os.environ, {"HTTPS_PROXY": "https://user:PRIVATE@localhost:1"}, clear=True):
            result = dn.proxy_environment()
        self.assertTrue(result["proxy_environment_present"])
        self.assertIsNone(result["route_verified"])
        self.assertNotIn("PRIVATE", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
