import copy
from types import SimpleNamespace
import unittest

from bpm.evection_save import EvectionSaveAdapter, draft_payload_matches


class EvectionDraftTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"operator": "Applicant", "purpose": "Conference",
                     "authorization": {"start": "2027-01-10T08:30", "end": "2027-01-11T17:30"},
                     "trips": [["A", "B", "2027-01-10", "2027-01-11", "2", "Conference"]]}
        self.cities = {"A": "10001", "B": "10002"}
        self.body = {"evection": {"id": None, "appliedName": "Applicant", "createdName": "Applicant",
                                  "bizReason": "Conference"}, "costs": [{}],
                     "details": [{"appliedName": "Applicant", "startTime": "2027-01-10T00:30:00.000Z",
                                  "endTime": "2027-01-11T09:30:00.000Z"}],
                     "trips": [{"startPlace": "A", "place": "B", "startPlaceCode": "10001",
                                "placeCode": "10002", "startTime": "2027-01-09T16:00:00.000Z",
                                "endTime": "2027-01-10T16:00:00.000Z", "days": 2,
                                "workItems": "Conference"}]}

    def test_request_body_fails_closed_on_drift(self):
        self.assertTrue(draft_payload_matches(self.body, self.plan, self.cities))
        for group, key, changed in (("evection", "totalAmount", "10"), ("evection", "tripMode", "plane"),
                                    ("evection", "id", "already-saved"), ("details", "endTime", "2027-01-11T10:30:00Z"),
                                    ("trips", "placeCode", "33333"), ("costs", "amount", "1")):
            with self.subTest(group=group, key=key):
                value = copy.deepcopy(self.body)
                branch = value[group] if group == "evection" else value[group][0]
                branch[key] = changed
                self.assertFalse(draft_payload_matches(value, self.plan, self.cities))

    def test_only_one_matching_browser_post_after_arm(self):
        frame = object()
        probe = SimpleNamespace(page=SimpleNamespace(main_frame=frame), city_codes=self.cities)
        adapter = EvectionSaveAdapter(probe, None, self.plan, None, None)
        request = SimpleNamespace(method="POST", url="https://oa.api.qiaodan.com/Evection/Detail",
                                  frame=frame, post_data_json=self.body)
        self.assertFalse(adapter.allow_request(request))
        adapter.allowed = True
        self.assertFalse(adapter.allow_request(SimpleNamespace(**{**vars(request), "url": request.url + "?other=1"})))
        self.assertFalse(adapter.allow_request(SimpleNamespace(**{**vars(request), "frame": object()})))
        self.assertTrue(adapter.allow_request(request))
        self.assertFalse(adapter.allow_request(request))


if __name__ == "__main__":
    unittest.main()
