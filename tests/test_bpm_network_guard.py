"""No real profile or OA requests: synthetic responses from a loopback fixture."""
import faulthandler
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bpm.browser_probe import Probe
from bpm.network_guard import (APPROVED_HOSTS, ContextGuard, NetworkBlocked,
                               authority, guarded_get)


class ExactPolicyTests(unittest.TestCase):
    def test_company_suffix_and_exact_external_scope(self):
        self.assertEqual(APPROVED_HOSTS, frozenset({
            "login.work.weixin.qq.com", "wwcdn.weixin.qq.com", "res.wx.qq.com"}))
        for host in APPROVED_HOSTS | {'qiaodan.com','bpm.qiaodan.com',
                'admin.api.qiaodan.com','oa.api.qiaodan.com','new.deep.qiaodan.com'}:
            self.assertTrue(authority("https://" + host)[2])

    def test_company_authority_normalization_and_parser_confusion(self):
        for url in ['HTTPS://QIAODAN.COM:443/', 'https://ADMIN.API.QIAODAN.COM/']:
            self.assertTrue(authority(url)[2])
        for host in ['qiaodan.com.example.org', 'evilqiaodan.com', 'qiaodan-com',
                     'qiaodan.com.', 'api..qiaodan.com', '-api.qiaodan.com',
                     'api-.qiaodan.com', 'api.%71iaodan.com', 'qiaodan。com',
                     'open.work.weixin.qq.com', 'new.wx.qq.com', 'aegis.qq.com']:
            with self.subTest(host=host):
                self.assertFalse(authority('https://' + host)[2])
        for url in ['https://user:pw@qiaodan.com/', 'https://qiaodan.com:444/',
                    'https://qiaodan.com:invalid/', 'https://evil.invalid\\@qiaodan.com/',
                    'https://qiaodan.com @evil.invalid/', 'https://qiaodan.com\t/',
                    'http://qiaodan.com/', 'wss://qiaodan.com/']:
            with self.subTest(url=url):
                self.assertFalse(authority(url)[2])

    def test_all_unapproved_authorities_fail_closed(self):
        for url in ["https://bpm.qiaodan.com.evil.invalid", "https://bpm.qiaodan.com.",
                    "https://user@bpm.qiaodan.com", "https://bpm.qiaodan.com@evil.invalid",
                    "https://192.168.34.10", "https://[::1]", "https://bpm.qiaodan.com:0",
                    "https://bpm.qiaodan.com:8443", "https://bpm.qiaodan.com:invalid",
                    "http://bpm.qiaodan.com", "wss://bpm.qiaodan.com", "file:///tmp/x"]:
            with self.subTest(url=url):
                self.assertFalse(authority(url)[2])

    def test_install_rejects_restored_pages_or_missing_websocket_support(self):
        context = MagicMock(pages=[object()])
        with self.assertRaises(NetworkBlocked):
            ContextGuard().install(context)
        context.pages = []
        context.route_web_socket = None
        with self.assertRaises(NetworkBlocked):
            ContextGuard().install(context)
        context.route.assert_not_called()

    def test_route_fetch_disables_redirects_and_retries(self):
        route = MagicMock()
        ContextGuard._fetch(route)
        route.fetch.assert_called_once_with(max_redirects=0, max_retries=0, timeout=30000)

    def test_api_rejects_before_transport_and_hides_sensitive_url_parts(self):
        p = SimpleNamespace(ctx=MagicMock(), log_event=MagicMock())
        with self.assertRaises(NetworkBlocked):
            guarded_get(p, "https://unknown.invalid/private?token=SYNTHETIC-PRIVATE")
        p.ctx.request.get.assert_not_called()
        text = str(p.log_event.call_args)
        self.assertIn("unknown.invalid", text)
        self.assertNotIn("SYNTHETIC-PRIVATE", text)
        self.assertNotIn("/private", text)

    def test_api_valid_get_keeps_strict_tls_and_never_auto_redirects(self):
        response = MagicMock(status=200)
        p = SimpleNamespace(ctx=MagicMock(), log_event=MagicMock())
        p.ctx.request.get.return_value = response
        self.assertIs(guarded_get(p, "https://oa.api.qiaodan.com/read", timeout=100), response)
        self.assertEqual(p.ctx.request.get.call_args.kwargs,
                         {"timeout": 100, "max_redirects": 0, "max_retries": 0,
                          "ignore_https_errors": False})

    def test_api_any_http_redirect_is_not_followed(self):
        for status in [301, 302, 303, 307, 308]:
            response = MagicMock(status=status, headers={"location": "https://unknown.invalid/"})
            p = SimpleNamespace(ctx=MagicMock(), log_event=MagicMock())
            p.ctx.request.get.return_value = response
            with self.assertRaises(NetworkBlocked):
                guarded_get(p, "https://oa.api.qiaodan.com/read")
            p.ctx.request.get.assert_called_once()
            response.dispose.assert_called_once()

    def test_api_cannot_override_tls_or_redirect_boundary(self):
        p = SimpleNamespace(ctx=MagicMock())
        for kwargs in [{"max_redirects": 1}, {"ignore_https_errors": True}]:
            with self.assertRaises(NetworkBlocked):
                guarded_get(p, "https://oa.api.qiaodan.com/read", **kwargs)
        p.ctx.request.get.assert_not_called()

    def test_owned_context_launch_retains_no_proxy_and_installs_before_page(self):
        p = object.__new__(Probe)
        p.log_event = MagicMock()
        pw = MagicMock()
        context = pw.start.return_value.chromium.launch.return_value.new_context.return_value
        context.pages = []
        with patch("playwright.sync_api.sync_playwright", return_value=pw):
            p._launch_isolated_guarded_context()
        self.assertEqual(pw.start.return_value.chromium.launch.call_args.kwargs["args"],
                         ["--no-proxy-server"])
        options = pw.start.return_value.chromium.launch.return_value.new_context.call_args.kwargs
        self.assertIs(options["ignore_https_errors"], False)
        self.assertEqual(options["service_workers"], "block")
        context.new_page.assert_not_called()
        context.route.assert_called_once()
        context.route_web_socket.assert_called_once()


class BrowserBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        # Last-resort whole-class watchdog; normal operations below have 5s caps.
        faulthandler.dump_traceback_later(45, exit=True)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-proxy-server"])
        class Fixture(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "https://unknown.invalid/private?token=SYNTHETIC")
                    body = b""
                else:
                    self.send_response(200)
                    body = b'<!doctype html><title>SYNTHETIC</title><link rel="icon" href="data:,"><body>fixture</body>'
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = cls.pw.request.new_context()

    @classmethod
    def tearDownClass(cls):
        cls.client.dispose()
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        faulthandler.cancel_dump_traceback_later()

    def setUp(self):
        self.ctx = self.browser.new_context(ignore_https_errors=False, service_workers="block")
        self.addCleanup(self.ctx.close)
        self.events = []
        self.guard = ContextGuard(lambda **e: self.events.append(e))
        port = self.server.server_address[1]
        self.responses = [self.client.get(f"http://127.0.0.1:{port}/", max_redirects=0)
                          for _ in range(3)]
        self.guard._fetch = MagicMock(side_effect=lambda route: self.responses.pop())
        self.guard.install(self.ctx)
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(5000)
        self.page.set_default_navigation_timeout(5000)

    def test_normal_approved_page_is_fulfilled(self):
        self.page.goto("https://bpm.qiaodan.com/synthetic")
        self.assertEqual(self.page.title(), "SYNTHETIC")
        self.guard._fetch.assert_called_once()

    def test_unknown_navigation_is_blocked_before_fetch(self):
        with self.assertRaises(Exception):
            self.page.goto("https://unknown.invalid/private?token=SYNTHETIC")
        self.guard._fetch.assert_not_called()
        self.assertEqual(self.events[-1]["host"], "unknown.invalid")

    def test_redirect_response_is_aborted_before_unknown_hop(self):
        port = self.server.server_address[1]
        response = self.client.get(f"http://127.0.0.1:{port}/redirect", max_redirects=0)
        self.guard._fetch.side_effect = None
        self.guard._fetch.return_value = response
        with self.assertRaises(Exception):
            self.page.goto("https://bpm.qiaodan.com/redirect")
        self.guard._fetch.assert_called_once()
        event = self.events[-1]
        self.assertEqual(event["reason"], "HTTP_REDIRECT_NOT_FOLLOWED")
        self.assertEqual(event["host"], "unknown.invalid")
        self.assertNotIn("SYNTHETIC", json.dumps(event))

    def test_fetch_is_bounded_and_blocked(self):
        self.page.goto("https://bpm.qiaodan.com/synthetic")
        value = self.page.evaluate("""() => Promise.race([
          fetch('https://unknown.invalid/').then(()=>false,()=>true),
          new Promise(r=>setTimeout(()=>r('timeout'),2000))])""")
        self.assertIs(value, True)
        self.assertEqual(self.guard._fetch.call_count, 1)

    def test_websocket_is_bounded_and_blocked_without_server_connection(self):
        self.page.goto("https://bpm.qiaodan.com/synthetic")
        value = self.page.evaluate("""() => new Promise(resolve => {
          const socket=new WebSocket('wss://socket-unknown.invalid/');
          socket.onopen=()=>socket.send('SYNTHETIC-POLICY-PROBE'); socket.onerror=()=>resolve(true);
          socket.onclose=()=>resolve(true); setTimeout(()=>resolve('timeout'),2000);
        })""")
        self.assertIs(value, True)
        self.assertTrue(any(e.get("channel") == "websocket" for e in self.events))
        self.assertEqual(self.guard._fetch.call_count, 1)

    def test_service_worker_registration_cannot_create_worker(self):
        self.page.goto("https://bpm.qiaodan.com/synthetic")
        value = self.page.evaluate("""() => Promise.race([
          navigator.serviceWorker.register('/worker.js').then(value=>value===undefined,()=>true),
          new Promise(r=>setTimeout(()=>r('registration_not_started'),200))])""")
        self.assertIn(value, [True, "registration_not_started"])
        self.assertEqual(self.ctx.service_workers, [])
        self.assertEqual(self.guard._fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
