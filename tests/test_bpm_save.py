import copy
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from bpm.save import SaveController, SaveError
try:
    from tests.test_bpm_verify import build_fixture
except ModuleNotFoundError:
    from test_bpm_verify import build_fixture


class Adapter:
    def __init__(self, snapshot, attempt):
        self.snapshot = copy.deepcopy(snapshot)
        self.attempt = Path(attempt)
        self.clicks = 0
        self.captures = 0
        self.reopens = 0
        self.unknown = False
        self.timeout = False
        self.mutate = False
        self.button = {"text": "保存", "count": 1, "enabled": True, "visible": True}
        self.identity = {"uuid": "b" * 32, "biz_number": "15426000002", "status": "编制中"}
        self.saved = copy.deepcopy(snapshot)
        self.saved["page"].update(self.identity, is_new=False,
                                   url="https://bpm.qiaodan.com/oa/reimburse?type=view&id="+"b"*32)

    def capture_snapshot(self):
        self.captures += 1
        result = copy.deepcopy(self.snapshot)
        result["observed_at"] = f"2026-10-23T01:00:0{self.captures}Z"
        if self.mutate and self.captures > 1:
            result["header"]["description"] = "changed"
        return result

    def screenshot(self, name):
        (self.attempt / (name + ".png")).write_bytes(b"offline screenshot fixture")
        return name + ".png"

    def exact_save_button(self):
        return self.button

    def click_exact_save(self):
        # Durable intent must exist before this irreversible adapter call.
        journals = list((self.attempt.parent / "save_tasks").glob("*.json"))
        assert len(journals) == 1
        assert json.loads(journals[0].read_text(encoding="utf-8"))["status"] == "SAVE_INTENT"
        self.clicks += 1
        if self.timeout:
            raise TimeoutError()

    def observe_saved(self):
        return {"identity": self.identity, "unique": True, "dialogs": ["unknown"] if self.unknown else []}

    def inspect_uncertain(self):
        return self.observe_saved()

    def reopen(self, identity):
        self.reopens += 1
        return copy.deepcopy(self.saved)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.snapshot = build_fixture(self.root)
        self.attempt = self.root / "attempt_001"
        self.attempt.mkdir()
        self.adapter = Adapter(self.snapshot, self.attempt)

    def controller(self, plan=None):
        return SaveController(plan or self.plan, self.adapter, self.attempt,
                              expected_operator=self.plan["operator"])

    def test_success_requires_reopen_and_restart_does_not_click(self):
        result = self.controller().run()
        self.assertEqual(result["status"], "SUCCESS_DRAFT_SAVED")
        self.assertEqual((self.adapter.clicks, self.adapter.reopens), (1, 1))
        result = self.controller().run()
        self.assertEqual(result["status"], "SUCCESS_DRAFT_SAVED")
        self.assertEqual((self.adapter.clicks, self.adapter.reopens), (1, 2))

    def test_no_authorization_boolean_string_or_submission(self):
        for index, (key, value) in enumerate((("mode", True), ("mode", "true"), ("allow_submit", "false"), ("allow_submit", True), ("task_id", "other"), ("statement", ""))):
            with self.subTest(key=key, value=value):
                plan = copy.deepcopy(self.plan)
                plan["authorization"][key] = value
                controller = self.controller(plan)
                # These negative inputs do not create an intent and can be retried
                # under a separate isolated offline task registry.
                controller.journal = self.root / (str(index) + ".json")
                self.assertEqual(controller.run()["status"], "NEEDS_INPUT")
        self.assertEqual(self.adapter.clicks, 0)

    def test_preflight_rejects_compound_duplicate_and_dialog_buttons(self):
        original = copy.deepcopy(self.adapter.button)
        for delta in ({"text": "保存并提交"}, {"count": 2}, {"enabled": False}, {"dialogs": ["确定提交？"]}):
            self.adapter.button = {**original, **delta}
            self.assertEqual(self.controller().run()["status"], "NEEDS_INPUT")
        self.assertEqual(self.adapter.clicks, 0)

    def test_page_change_after_screenshot_no_click(self):
        self.adapter.mutate = True
        self.assertEqual(self.controller().run()["status"], "READBACK_MISMATCH")
        self.assertEqual(self.adapter.clicks, 0)

    def test_complete_but_empty_relation_details_never_click_save(self):
        self.adapter.snapshot["extra_tables"]["detailrels"] = []
        self.adapter.snapshot["completeness"]["detailrels"] = True
        self.assertEqual(self.controller().run()["status"], "READBACK_MISMATCH")
        self.assertEqual(self.adapter.clicks, 0)

    def test_incomplete_and_wrong_page_no_click(self):
        self.adapter.snapshot["completeness"]["banks"] = False
        self.assertEqual(self.controller().run()["status"], "READBACK_MISMATCH")
        self.adapter.snapshot["completeness"]["banks"] = True
        self.adapter.snapshot["page"]["is_new"] = False
        self.assertEqual(self.controller().run()["status"], "READBACK_MISMATCH")
        self.assertEqual(self.adapter.clicks, 0)

    def test_timeout_persists_uncertainty_no_second_click(self):
        self.adapter.timeout = True
        self.assertEqual(self.controller().run()["status"], "SAVE_UNCERTAIN")
        self.assertEqual(self.adapter.clicks, 1)
        self.adapter.timeout = False
        result = self.controller().run()
        self.assertEqual(result["status"], "SUCCESS_DRAFT_SAVED")
        self.assertEqual(self.adapter.clicks, 1)

    def test_unknown_dialog_never_confirmed(self):
        self.adapter.unknown = True
        self.assertEqual(self.controller().run()["status"], "SAVE_UNCERTAIN")
        self.assertEqual(self.controller().run()["status"], "SAVE_UNCERTAIN")
        self.assertEqual(self.adapter.clicks, 1)
        self.assertEqual(self.adapter.reopens, 0)

    def test_stale_plan_cannot_overwrite_pending_journal(self):
        self.adapter.timeout = True
        self.controller().run()
        changed = copy.deepcopy(self.plan)
        changed["header"]["description"] = "different plan"
        with self.assertRaises(SaveError):
            self.controller(changed).run()
        self.assertEqual(self.adapter.clicks, 1)

    def test_hash_drift_after_screenshot_blocks_click(self):
        original = self.adapter.screenshot
        def screenshot(name):
            path = original(name)
            Path(self.plan["template"]["snapshot_path"]).write_text("drift", encoding="utf-8")
            return path
        self.adapter.screenshot = screenshot
        self.assertEqual(self.controller().run()["status"], "READBACK_MISMATCH")
        self.assertEqual(self.adapter.clicks, 0)

    def test_reopened_mismatch_retains_identity_and_never_clicks_again(self):
        self.adapter.saved["tables"]["banks"][0]["fields"]["account"] = "different"
        first = self.controller().run()
        self.assertEqual(first["status"], "SAVE_UNCERTAIN")
        self.assertEqual(first["pending_identity"], self.adapter.identity)
        second = self.controller().run()
        self.assertEqual(second["status"], "SAVE_UNCERTAIN")
        self.assertEqual(self.adapter.clicks, 1)

    def test_unknown_persisted_state_never_clicks(self):
        controller = self.controller()
        controller.journal.write_text(json.dumps({"task_id": controller.task_id,
                                                  "plan_hash": controller.plan_hash,
                                                  "config_sha256": controller.config_sha256,
                                                  "status": "UNRECOGNIZED_SAVED_STATE"}), encoding="utf-8")
        with self.assertRaises(SaveError):
            controller.run()
        self.assertEqual(self.adapter.clicks, 0)

    def test_config_drift_after_screenshot_blocks_click(self):
        controller = self.controller()
        original = self.adapter.screenshot
        def screenshot(name):
            result = original(name)
            patcher = mock.patch("bpm.save.config_hash", return_value="0"*64)
            patcher.start()
            self.addCleanup(patcher.stop)
            return result
        self.adapter.screenshot = screenshot
        result = controller.run()
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertIn({"code": "CONFIG_CHANGED"}, result["issues"])
        self.assertEqual(self.adapter.clicks, 0)

    def test_config_drift_on_restart_never_reconciles_under_new_config(self):
        self.adapter.timeout = True
        controller = self.controller()
        controller.run()
        with mock.patch("bpm.save.config_hash", return_value="0"*64):
            with self.assertRaises(SaveError):
                self.controller().run()
        self.assertEqual(self.adapter.clicks, 1)
        self.assertEqual(self.adapter.reopens, 0)

    def test_save_events_append_at_run_authority(self):
        self.controller().run()
        path = self.attempt.parent / "events.jsonl"
        first = path.read_text(encoding="utf-8").splitlines()
        self.controller().run()
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:len(first)], first)
        self.assertGreater(len(lines), len(first))
        self.assertTrue(all(json.loads(line)["config_sha256"] for line in lines))
        self.assertFalse((self.attempt / "events.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
