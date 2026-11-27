from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from bpm.leave_save import (
    CONNECTION_WARNING, FLOW_GENERATE_URL, SAVE_DIALOG_SELECTOR, SAVE_URL,
    LeaveSaveAdapter,
)


class LeaveSaveTests(unittest.TestCase):
    def setUp(self):
        self.probe = Mock()
        self.frame = self.probe.page.main_frame
        self.plan = {"operator": "Applicant", "facts": {"reason": "Appointment"}}
        self.adapter = LeaveSaveAdapter(self.probe, Mock(), self.plan, None)
        self.request = SimpleNamespace(
            method="POST", url=SAVE_URL, frame=self.frame,
            post_data='{"bizReason":"Appointment","appliedName":"Applicant"}',
        )
        self.body = {"id": "a" * 32, "bizNumber": "12427000001", "bizStatus": 0}
        self.probe.header_value.return_value = self.body["bizNumber"]
        self.dialogs = self.probe.page.locator.return_value
        self.dialogs.count.return_value = 1
        self.dialogs.get_by_text.return_value.count.return_value = 1

    def admit_save(self):
        self.adapter.allowed = True
        self.assertTrue(self.adapter.allow_request(self.request))
        self.adapter.allowed = False
        self.adapter.reply = Mock(ok=True, status=200)
        self.adapter.reply.json.return_value = self.body

    def block_flow(self):
        flow = SimpleNamespace(method="POST", url=FLOW_GENERATE_URL, frame=self.frame)
        self.assertFalse(self.adapter.allow_request(flow))

    def test_save_admits_only_the_exact_armed_request_once(self):
        self.assertFalse(self.adapter.allow_request(self.request))
        self.block_flow()
        self.assertFalse(self.adapter.flow_generate_blocked)
        self.adapter.allowed = True
        for url in (SAVE_URL + "/other", SAVE_URL + "?other=1", FLOW_GENERATE_URL):
            request = SimpleNamespace(**{**vars(self.request), "url": url})
            self.assertFalse(self.adapter.allow_request(request))
        self.assertTrue(self.adapter.allow_request(self.request))
        self.assertFalse(self.adapter.allow_request(self.request))
        self.assertTrue(self.adapter.is_save_response(
            SimpleNamespace(url=SAVE_URL, request=self.request)))
        self.assertFalse(self.adapter.is_save_response(
            SimpleNamespace(url=SAVE_URL, request=object())))

    def test_blocked_workflow_warning_allows_read_only_reopen(self):
        self.admit_save()
        self.block_flow()
        observation = self.adapter.observe_saved()
        self.assertEqual(observation["identity"]["biz_number"], self.body["bizNumber"])
        self.assertTrue(observation["unique"])
        self.assertEqual(observation["dialogs"], 0)
        self.assertEqual(observation["visible_dialogs"], 1)
        self.assertEqual(observation["blocked_workflow_warning"], CONNECTION_WARNING)
        self.probe.page.locator.assert_called_once_with(SAVE_DIALOG_SELECTOR)
        self.dialogs.get_by_text.assert_called_once_with(CONNECTION_WARNING, exact=True)

    def test_without_correlated_flow_block_the_warning_remains_unresolved(self):
        self.admit_save()
        flow = SimpleNamespace(method="POST", url=FLOW_GENERATE_URL, frame=object())
        self.assertFalse(self.adapter.allow_request(flow))
        self.assertEqual(self.adapter.observe_saved()["dialogs"], 1)

    def test_unknown_dialog_and_non_draft_receipt_remain_unresolved(self):
        self.admit_save()
        self.block_flow()
        self.dialogs.get_by_text.return_value.count.return_value = 0
        self.assertEqual(self.adapter.observe_saved()["dialogs"], 1)
        self.dialogs.get_by_text.return_value.count.return_value = 1
        self.dialogs.count.return_value = 2
        self.assertEqual(self.adapter.observe_saved()["dialogs"], 2)
        self.dialogs.count.return_value = 1
        for status in (False, 1, None):
            with self.subTest(status=status):
                self.body["bizStatus"] = status
                self.assertEqual(self.adapter.observe_saved()["dialogs"], 1)
        self.probe.header_value.return_value = "other-number"
        self.assertIsNone(self.adapter.observe_saved())


if __name__ == "__main__":
    unittest.main()
