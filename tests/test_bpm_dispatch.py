import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bpm.browser_probe as P
from bpm.ui import StructuredProbe


class DispatchTests(unittest.TestCase):
    def test_legacy_regression_business_failure_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.json"
            path.write_text(json.dumps({"meta": {}}), encoding="utf-8")
            for status in ("FAILED", "BLOCKED(c1_entry_login)", "SUCCESS_FILL_ONLY"):
                obj = SimpleNamespace(result={"finish_reason": status}, main=lambda: None)
                with patch.object(P, "Probe", return_value=obj):
                    result = P.main(["--expect-name", "测试", "--fill-plan", str(path), "--legacy-regression"])
                self.assertEqual(result, 0 if status == "SUCCESS_FILL_ONLY" else 2)

    def test_v1_business_failure_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps({"schema_version": "1.0"}), encoding="utf-8")
            for status in ("NEEDS_INPUT", "READBACK_MISMATCH", "WAIT_HUMAN_LOGIN", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED"):
                obj = SimpleNamespace(result={"finish_reason": status}, main=lambda: None)
                with patch("bpm.ui.StructuredProbe", return_value=obj):
                    result = P.main(["--expect-name", "测试", "--fill-plan", str(path)])
                self.assertEqual(result, 0 if status == "SUCCESS_DRAFT_SAVED" else 2)

    def test_restored_form_is_not_the_entry_navigation_target(self):
        old = SimpleNamespace(url="https://bpm.qiaodan.com/oa/reimburse?type=new", navigated=False)
        class Page:
            url = "about:blank"
            def set_default_timeout(self, value):
                self.timeout = value
            def on(self, *args):
                pass
        fresh = Page()
        ctx = SimpleNamespace(pages=[old], new_page=lambda: fresh)
        p = object.__new__(StructuredProbe)
        p.ctx, p.page = ctx, old
        with patch.object(P.Probe, "_launch", return_value=None):
            p._launch()
        self.assertIs(p.page, fresh)
        self.assertEqual(p.restored_pages[0]["url"], old.url)
        self.assertFalse(old.navigated)

    def test_unsafe_run_and_budget_rejected(self):
        for flag, value in (("--run", "../../unsafe"), ("--wall-cap", "nan"), ("--keep-open-minutes", "inf")):
            with self.assertRaises(SystemExit):
                P.parse_args(["--expect-name", "测试", flag, value])


if __name__ == "__main__":
    unittest.main()
