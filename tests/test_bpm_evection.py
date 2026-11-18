import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from bpm.evection import EvectionError, EvectionProbe, itinerary, unique_city_code


class EvectionPlanTests(unittest.TestCase):
    def test_airport_hint_resolves_homonyms_only_when_unique(self):
        self.assertEqual(unique_city_code([["10001", ""], ["10002", "ABC"]]), "10002")
        self.assertEqual(unique_city_code([["10001", ""]]), "10001")
        self.assertIsNone(unique_city_code([["10001", "ABC"], ["10002", "XYZ"]]))
        self.assertIsNone(unique_city_code([["10001", ""], ["10002", ""]]))
        self.assertIsNone(unique_city_code([]))

    def test_rejects_source_drift_and_inconsistent_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp, "source.jpg")
            image.write_bytes(b"plan source")
            plan = Path(tmp, "itinerary.json")
            data = {"image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(), "trips": [
                ["City A", "City B", "2027-01-10", "2027-01-11", "2", "Task A"],
                ["City B", "City C", "2027-01-11", "2027-01-11", "1", "Task B"],
            ]}

            def load():
                plan.write_text(json.dumps(data), encoding="utf-8")
                return itinerary(image, plan)

            self.assertEqual(load(), data)
            data["trips"][0][4] = "1"
            with self.assertRaises(EvectionError):
                load()
            data["trips"][0][4] = "2"
            data["trips"][1][0] = "City D"
            with self.assertRaises(EvectionError):
                load()
            data["trips"][1][0] = "City B"
            image.write_bytes(b"changed")
            with self.assertRaises(EvectionError):
                load()

    def test_write_methods_do_not_reach_browser_transport(self):
        probe = SimpleNamespace(log_event=Mock())
        for method, path in (("POST", "/Evection/ModelDetails"), ("DELETE", "/Evection/123"),
                             ("POST", "/Flow/Forward"), ("POST", "/Evection/query/20/1/extra")):
            with self.subTest(method=method, path=path):
                route = Mock(request=SimpleNamespace(method=method, url="https://oa.api.qiaodan.com" + path))
                EvectionProbe.read_only_route(probe, route)
                route.abort.assert_called_once_with("blockedbyclient")
                route.fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
