"""Shipping-only approval, six-second display and at-most-once UI regressions."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from bpm import approval as a


def task():
    return dict(id="1" * 32, bizId="2" * 32, bizNumber="SHIP-TEST-001", url="/oa/express",
                toUserCode="synthetic-user", bizStatus=7, status=0, kind=1, isHeld=False)


class AutoApprovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = a.ApprovalJournal(self.temp.name)
        self.task = task()
        self.page = MagicMock()
        self.page.url = a.ORIGIN + "/oa/express?type=view&id=" + self.task["bizId"] + "&task=1"
        self.page.is_closed.return_value = False
        self.identity = MagicMock()
        self.pending = MagicMock(side_effect=[True, True, False])
        self.say, self.log = MagicMock(), MagicMock()
        self.controller = a.AutoApprover(self.journal, "synthetic-user", self.identity,
                                         self.pending, self.say, self.log)
        self.summary = {"number": self.task["bizNumber"], "detail_count": 2, "fingerprint": "synthetic-hash"}
        self.clock = 0
        self.page.wait_for_timeout.side_effect = self.tick
        self.opener, self.confirm, self.dialog = MagicMock(), MagicMock(), MagicMock()
        self.response = SimpleNamespace(status=200, request=SimpleNamespace(post_data_json={"isApproved": True}),
                                        json=lambda: {"bizId": self.task["bizId"]})
        self.page.expect_response.return_value.__enter__.return_value = SimpleNamespace(value=self.response)
        self.patches = [patch.object(a.ShippingHandler, "snapshot", return_value=self.summary),
                        patch.object(a, "visible_dialogs", return_value=SimpleNamespace(count=lambda: 0)),
                        patch.object(a, "exact_button", side_effect=lambda scope: self.confirm if scope is self.dialog else self.opener),
                        patch.object(a, "flow_dialog", return_value=(self.dialog, "default-next-node")),
                        patch.object(a.time, "monotonic", side_effect=lambda: self.clock)]
        self.snapshot = self.patches[0].start()
        for p in self.patches[1:]:
            p.start()
        for p in self.patches:
            self.addCleanup(p.stop)

    def tick(self, milliseconds):
        self.clock += milliseconds / 1000

    def records(self):
        p = Path(self.temp.name) / (self.journal.key("synthetic-user", self.task) + ".jsonl")
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def test_six_full_seconds_then_two_normal_ui_clicks_and_verified_record(self):
        def opening(**kw):
            self.assertGreaterEqual(self.clock, 6)
            self.assertEqual(self.records()[-1]["state"], "FLOW_INTENT")
        def confirming(**kw):
            self.assertEqual(self.records()[-1]["state"], "FLOW_CONFIRM_INTENT")
        self.opener.click.side_effect = opening
        self.confirm.click.side_effect = confirming
        self.assertEqual(self.controller.handle(self.page, self.task), "SUCCESS")
        self.page.bring_to_front.assert_called_once()
        self.assertEqual([r["state"] for r in self.records()], ["FLOW_INTENT", "FLOW_CONFIRM_INTENT", "SUCCESS"])
        self.assertEqual(self.opener.click.call_count, 1)
        self.assertEqual(self.confirm.click.call_count, 1)
        self.assertIn("流转成功", self.say.call_args.args[0])

    def test_other_documents_including_express_reimbursement_remain_manual(self):
        for route in ("/oa/reimbursement", "/oa/expresses", "/oa/travel", "/oa/express-extra"):
            with self.subTest(route=route):
                self.assertEqual(self.controller.handle(self.page, dict(self.task, url=route, description="快递单")), "MANUAL")
        self.opener.click.assert_not_called()
        self.identity.assert_not_called()

    def test_identity_change_during_display_never_clicks(self):
        self.identity.side_effect = [None, RuntimeError("synthetic identity conflict")]
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()
        self.assertEqual(self.records(), [])

    def test_document_changes_during_display_never_click(self):
        self.snapshot.side_effect = [self.summary, dict(self.summary, fingerprint="changed")]
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_user_closes_page_during_display_never_clicks(self):
        self.page.is_closed.return_value = True
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_task_already_handled_during_display_never_clicks(self):
        self.pending.side_effect = None
        self.pending.return_value = False
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_failure_after_click_is_uncertain_and_restart_cannot_replay(self):
        self.confirm.click.side_effect = TimeoutError("synthetic")
        self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
        restarted = a.AutoApprover(a.ApprovalJournal(self.temp.name), "synthetic-user", self.identity,
                                   self.pending, self.say, self.log)
        self.assertEqual(restarted.handle(self.page, self.task), "RECORDED")
        self.assertEqual(self.confirm.click.call_count, 1)
        self.assertEqual(self.opener.click.call_count, 1)

    def test_successful_record_never_replays(self):
        self.assertEqual(self.controller.handle(self.page, self.task), "SUCCESS")
        self.assertEqual(self.controller.handle(self.page, self.task), "RECORDED")
        self.assertEqual(self.confirm.click.call_count, 1)

    def test_different_tasks_on_same_document_do_not_share_journal_key(self):
        self.assertNotEqual(self.journal.key("synthetic-user", self.task),
                            self.journal.key("synthetic-user", dict(self.task, id="3" * 32)))

    def test_corrupt_existing_journal_blocks_approval(self):
        p = Path(self.temp.name) / (self.journal.key("synthetic-user", self.task) + ".jsonl")
        p.write_text("incomplete", encoding="utf-8")
        self.assertEqual(self.controller.handle(self.page, self.task), "RECORDED")
        self.opener.click.assert_not_called()

    def test_unknown_dialog_does_not_get_confirmed(self):
        with patch.object(a, "flow_dialog", side_effect=a.ApprovalStopped("unknown dialog")):
            self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
        self.confirm.click.assert_not_called()

    def test_changed_default_next_node_does_not_get_confirmed(self):
        with patch.object(a, "flow_dialog", side_effect=[(self.dialog, "a"), (self.dialog, "b")]):
            self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
        self.confirm.click.assert_not_called()

    def test_pending_task_remaining_after_response_is_not_success(self):
        self.pending.side_effect = None
        self.pending.return_value = True
        self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
        self.assertNotIn("SUCCESS", [r["state"] for r in self.records()])

    def test_invalid_or_other_account_tasks_never_click(self):
        for values in ({"id": ""}, {"toUserCode": "other"}, {"bizStatus": 5}, {"isHeld": True}):
            with self.subTest(values=values):
                self.assertEqual(self.controller.handle(self.page, dict(self.task, **values)), "STOPPED")
        self.opener.click.assert_not_called()

    def test_journal_failure_prevents_first_click(self):
        with patch.object(self.journal, "write", side_effect=OSError("synthetic disk failure")):
            self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_hidden_page_during_display_never_clicks(self):
        self.page.evaluate.return_value = False
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_native_dialog_during_display_never_confirmed(self):
        def tick(milliseconds):
            self.tick(milliseconds)
            self.page.on.call_args.args[1](SimpleNamespace(type="confirm"))
        self.page.wait_for_timeout.side_effect = tick
        self.assertEqual(self.controller.handle(self.page, self.task), "STOPPED")
        self.opener.click.assert_not_called()

    def test_wrong_business_response_never_reports_success(self):
        self.response.json = lambda: {"bizId": "4" * 32}
        self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
        self.assertNotIn("SUCCESS", [r["state"] for r in self.records()])

    def test_backward_response_never_reports_success(self):
        self.response.request.post_data_json = {"isApproved": False}
        self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")

    def test_success_record_disk_failure_does_not_trigger_retry(self):
        write = self.journal.write
        def fail_after_intent(key, state, **kwargs):
            if state in ("SUCCESS", "UNCERTAIN"):
                raise OSError("synthetic disk full")
            return write(key, state, **kwargs)
        with patch.object(self.journal, "write", side_effect=fail_after_intent):
            self.assertEqual(self.controller.handle(self.page, self.task), "UNCERTAIN")
            self.assertEqual(self.controller.handle(self.page, self.task), "RECORDED")
        self.confirm.click.assert_called_once()

    def test_journal_exclusive_create_prevents_racing_intents(self):
        key = self.journal.key("synthetic-user", self.task)
        self.journal.write(key, "FLOW_INTENT", first=True)
        with self.assertRaises(FileExistsError):
            self.journal.write(key, "FLOW_INTENT", first=True)
        self.assertEqual(len(self.records()), 1)


if __name__ == "__main__":
    unittest.main()
