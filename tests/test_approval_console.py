"""Console pause regressions; no OA connection or credential access."""
import ctypes
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("console_watch", ROOT / "feature03-自动审批快递单/approval_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class ConsoleModeTests(unittest.TestCase):
    def api(self, before=503, after=None):
        kernel = MagicMock()
        kernel.GetStdHandle.return_value = 0x123456789
        values = iter([before, (before | 0x80) & ~0x40 if after is None else after])
        def read(_handle, output):
            ctypes.cast(output, ctypes.POINTER(watch.wintypes.DWORD)).contents.value = next(values)
            return True
        kernel.GetConsoleMode.side_effect = read
        kernel.SetConsoleMode.return_value = True
        return kernel

    def configure(self, kernel):
        with patch.object(watch.sys, "platform", "win32"), \
                patch.object(watch.ctypes, "WinDLL", return_value=kernel, create=True), \
                patch.object(watch.ctypes, "get_last_error", return_value=5, create=True):
            return watch.disable_console_quick_edit()

    def test_mouse_selection_disabled_with_ctrl_c_and_other_flags_preserved(self):
        kernel = self.api()
        result = self.configure(kernel)
        self.assertEqual(result, {"status": "configured", "before": 503, "after": 439})
        self.assertTrue(result["after"] & 1)  # ENABLE_PROCESSED_INPUT / Ctrl+C
        self.assertEqual(result["before"] ^ result["after"], 0x40)

    def test_required_extended_flag_set_when_original_console_lacks_it(self):
        kernel = self.api(before=0x47)
        self.assertEqual(self.configure(kernel)["after"], 0x87)

    def test_already_disabled_remains_disabled(self):
        self.assertEqual(self.configure(self.api(before=439))["after"], 439)

    def test_redirected_input_or_no_console_does_not_try_to_change_mode(self):
        kernel = self.api()
        kernel.GetConsoleMode.side_effect = lambda *args: False
        self.assertEqual(self.configure(kernel), {"status": "unavailable", "error_code": 5})
        kernel.SetConsoleMode.assert_not_called()

    def test_access_denied_is_reported_without_claiming_success(self):
        kernel = self.api()
        kernel.SetConsoleMode.return_value = False
        self.assertEqual(self.configure(kernel), {"status": "failed", "error_code": 5})

    def test_readback_mismatch_is_reported(self):
        self.assertEqual(self.configure(self.api(after=503))["status"], "verify_failed")

    def test_non_windows_is_noop(self):
        with patch.object(watch.sys, "platform", "linux"):
            self.assertEqual(watch.disable_console_quick_edit(), {"status": "not_windows"})

    def test_double_click_entry_configures_console_before_any_output(self):
        order = []
        with patch.object(watch, "disable_console_quick_edit", side_effect=lambda: order.append("console")), \
                patch.object(watch, "load_config", side_effect=lambda *a: (
                    order.append("config") or (ROOT, watch.CONFIG_DEFAULTS))), \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(watch.main(["--check-config"]), 0)
        self.assertEqual(order, ["console", "config"])


class DiscoveryEvidenceTests(unittest.TestCase):
    def test_detection_record_precedes_visible_window_and_console_status(self):
        probe, window, inbox = MagicMock(), MagicMock(), MagicMock()
        probe.budget = SimpleNamespace(wall_cap=1200)
        probe.page.is_closed.side_effect = [False, True]
        account = ("synthetic-user", "测试")
        inbox.query.return_value = [{"id": "synthetic-task", "toUserCode": account[0],
                                     "bizStatus": 7, "status": 0, "kind": 1}]
        order = []
        probe.log_event.side_effect = lambda **kw: order.append(kw["event"])
        probe.say.side_effect = lambda *a: order.append("console")
        window.open.side_effect = lambda *a: order.append("open") or MagicMock()
        with patch.object(watch, "Inbox", return_value=inbox), \
                patch.object(watch, "ready_inbox"), \
                patch("bpm.session.state_usable", return_value=True), \
                patch.object(watch, "detail_url", return_value="synthetic:url"), \
                patch.object(watch, "flash_browser", return_value=True):
            watch.monitor(probe, window, account, 10)
        self.assertLess(order.index("approval_pending_detected"), order.index("open"))
        self.assertLess(order.index("approval_monitor_cycle"), len(order) - 1)
        self.assertEqual(order[-1], "console")
        window.close.assert_not_called()


@unittest.skipUnless(sys.platform == "win32", "Windows console integration")
class RealConsoleTests(unittest.TestCase):
    def test_native_selection_pauses_output_and_startup_disables_quick_edit(self):
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0  # Test console stays hidden.
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.json"
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(ROOT / "tests/fixtures/approval_console_selection.py"), str(output)],
                creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup,
                capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(report["before_selection_flags"] & 1, report)
        self.assertTrue(report["before_output_blocked"], report)
        self.assertEqual(report["configuration"]["status"], "configured", report)
        self.assertEqual(report["after_attempts"], [
            {"selection_flags": 0, "output_blocked": False}] * 3, report)


if __name__ == "__main__":
    unittest.main()
