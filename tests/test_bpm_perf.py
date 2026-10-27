import unittest
from tools.diagnostics.perf import report,union_ms

class PerfTests(unittest.TestCase):
    def test_nested_intervals_are_not_added_twice(self):
        self.assertEqual(union_ms([(0,10),(2,4),(8,15),(20,22)]),17)
        value=report([{"event":"UI_START","epoch_ms":1000},
            {"event":"timing","action":"section","t0_ms":1100,"dur_ms":600},
            {"event":"timing","action":"cell","t0_ms":1200,"dur_ms":200},
            {"event":"READBACK_END","epoch_ms":2000,"ok":True}])
        self.assertEqual(value["instrumented_union_seconds"],.6)
        self.assertEqual(value["uncovered_seconds"],.4)
    def test_failed_incomplete_window_is_not_comparable(self):
        self.assertFalse(report([{"event":"UI_START","epoch_ms":1000}])["comparable_complete_ui"])
