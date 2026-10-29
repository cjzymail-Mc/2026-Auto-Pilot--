"""Visible login-only bootstrap with current-account discovery; never opens forms."""
from __future__ import annotations

import argparse
import time
from types import SimpleNamespace

from bpm.browser_probe import Probe, HOST, PASS, BLOCKED, QR_EXPIRED_JS


class LoginProbe(Probe):
    def __init__(self, args):
        super().__init__(args)
        self._required_name = args.expect_name
        self._saw_login_gate = False
        self._last_login_state = "UNKNOWN"

    def _launch(self):
        if not self.args.force_scan:
            # Normal reuse must use the same protected profile as business runs.
            # A fresh context is reserved for an explicitly requested new scan.
            super()._launch()
            self.log_event(event="login_context_mode", mode="persistent_profile_reuse")
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._login_browser = self._pw.chromium.launch(
            headless=False, args=["--start-maximized", "--no-proxy-server"])
        self.ctx = self._login_browser.new_context(ignore_https_errors=True,
                                                  viewport={"width": 1440, "height": 900})
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(45000)
        self.page.on("dialog", lambda dialog: dialog.dismiss())
        self.log_event(event="login_context_mode", mode="fresh_scan_context")

    def login_state(self, page):
        # Discovery is confined to this login-only bootstrap; business execution
        # still requires the discovered expected identity and all existing guards.
        account = page.locator("a#user-profile-dd.profile-toggle-link > span")
        name = account.inner_text().strip() if account.count() == 1 and account.is_visible() else ""
        if name and not self._required_name:
            self.args.expect_name = name
        state, marks, evidence = super().login_state(page)
        if state == "LOGIN_REQUIRED":
            self._saw_login_gate = True
        if state == "LOGGED_IN" and (not name or name != self.args.expect_name):
            return "UNKNOWN", marks, evidence
        return state, marks, evidence

    def phase_entry(self):
        self.page.goto(HOST, wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(1500)
        state, _, _ = self.login_state(self.page)
        self._last_login_state = state
        self.log_event(event="login_state_observed", phase="entry", state=state)
        if state == "LOGGED_IN":
            self.checks["c1_entry_login"].update(status=PASS, reason="Live account verified")
            return PASS
        if state == "LOGIN_REQUIRED":
            self.checks["c1_entry_login"].update(status=BLOCKED, reason="WAIT_HUMAN_LOGIN")
            if self.args.login_wait > 0:
                self.say("QR_WINDOW_READY — 请在弹出的企业微信窗口扫码；本次仅登录，不操作单据。")
                self.log_event(event="login_window_ready", force_scan=self.args.force_scan)
            return "LOGIN_REQUIRED"
        self.checks["c1_entry_login"].update(status=BLOCKED, reason="LOGIN_STATE_UNKNOWN")
        return "UNKNOWN"

    def wait_login(self):
        deadline = time.monotonic() + self.args.login_wait
        refreshed = 0
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(1000)
            state, _, _ = self.login_state(self.page)
            self._last_login_state = state
            if state == "LOGGED_IN":
                self._fresh_scan_confirmed = bool(self.args.force_scan and self._saw_login_gate)
                self.checks["c1_entry_login"].update(status=PASS, reason="Live account verified after login gate")
                self.log_event(event="login_identity_verified", fresh_scan=self._fresh_scan_confirmed)
                return PASS
            if state == "LOGIN_REQUIRED" and refreshed < 5 and self.page.evaluate(QR_EXPIRED_JS):
                self.page.reload(wait_until="domcontentloaded", timeout=30000)
                refreshed += 1
                self.log_event(event="login_qr_refreshed", n=refreshed)
        state = self._last_login_state
        reason = "WAIT_HUMAN_LOGIN" if state == "LOGIN_REQUIRED" else "LOGIN_STATE_UNKNOWN"
        self.checks["c1_entry_login"].update(status=BLOCKED, reason=reason)
        self.log_event(event="login_wait_end", state=state, reason=reason)
        return BLOCKED if state == "LOGIN_REQUIRED" else "UNKNOWN"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-scan", action="store_true", help="fresh context; do not inject previous credentials")
    parser.add_argument("--expect-name", default=None, help="optional explicit identity constraint")
    parser.add_argument("--login-wait", type=int, default=900)
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S-login60"))
    options = parser.parse_args(argv)
    import re
    if not 1 <= options.login_wait <= 3600 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", options.run):
        parser.error("invalid login wait or run identifier")
    args = SimpleNamespace(run=options.run, doc_id=None, expect_name=options.expect_name,
                           force_scan=options.force_scan, tech_budget=1800, login_wait=options.login_wait,
                           wall_cap=options.login_wait + 300, fill_plan=None, login_only=True,
                           keep_open_minutes=0, interactive_pick=False)
    probe = LoginProbe(args)
    probe.main()
    return 0 if probe.result.get("finish_reason") == "SUCCESS_LOGIN_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
