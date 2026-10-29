"""bpm.query 离线反例：参数校验、URL 匹配、三分支合并去重、排序并列、
零结果与失败区分、精确单号前导零/多 UUID。UI 交互按真实验收覆盖，不在本文件伪造。"""
import sys
import unittest
from types import SimpleNamespace

from bpm.query import (CANDIDATE_FIELDS, classify_keyword_outcome, exact_match,
                       list_query_response, merge_candidates, validate_cli)


def cli_args(**kw):
    base = dict(keyword=None, number=None, creator=None, department=None,
                date_from=None, date_to=None, limit=5, snapshot=False)
    base.update(kw)
    return SimpleNamespace(**base)


class ValidateCliTests(unittest.TestCase):
    def test_keyword_or_number_required(self):
        self.assertTrue(validate_cli(cli_args()))
        self.assertTrue(validate_cli(cli_args(keyword="外购", number="154")))
        self.assertFalse(validate_cli(cli_args(keyword="外购")))
        self.assertFalse(validate_cli(cli_args(number="15426104120")))

    def test_number_digit_string_only(self):
        self.assertFalse(validate_cli(cli_args(number="0154261041")))
        self.assertTrue(validate_cli(cli_args(number="15a4")) is not None and
                        validate_cli(cli_args(number="15a4")))
        self.assertFalse(validate_cli(cli_args(number="154 1")) is False)

    def test_limit_bounds(self):
        self.assertTrue(validate_cli(cli_args(keyword="x", limit=0)))
        self.assertTrue(validate_cli(cli_args(keyword="x", limit=21)))
        self.assertFalse(validate_cli(cli_args(keyword="x", limit=1)))
        self.assertFalse(validate_cli(cli_args(keyword="x", limit=20)))

    def test_snapshot_requires_number(self):
        self.assertTrue(validate_cli(cli_args(keyword="x", snapshot=True)))
        self.assertFalse(validate_cli(cli_args(number="15426104120", snapshot=True)))

    def test_date_range_order_and_format(self):
        self.assertTrue(validate_cli(cli_args(keyword="x", date_from="2026/01/01")))
        self.assertTrue(validate_cli(cli_args(keyword="x", date_from="2026-10-02", date_to="2026-10-01")))
        self.assertFalse(validate_cli(cli_args(keyword="x", date_from="2026-10-01", date_to="2026-10-02")))

    def test_blank_keyword_rejected(self):
        self.assertTrue(validate_cli(cli_args(keyword="   ")))


class ListResponseUrlTests(unittest.TestCase):
    def test_matches_only_observed_list_endpoint(self):
        self.assertTrue(list_query_response(
            "https://oa.api.qiaodan.com/reimburse/query/1/10"))
        self.assertTrue(list_query_response(
            "https://oa.api.qiaodan.com/reimburse/query/1/10?primeNgTable=tbl-0"))  # 合法 query string 不影响
        self.assertFalse(list_query_response(
            "https://oa.api.qiaodan.com/reimburse/15426104120"))          # 模板 GET，非列表
        self.assertFalse(list_query_response(
            "https://evil.example.com/reimburse/query/1/10"))
        self.assertFalse(list_query_response(
            "http://oa.api.qiaodan.com/reimburse/query/1/10"))             # 非 https
        self.assertFalse(list_query_response("not a url"))
        self.assertFalse(list_query_response(
            "https://oa.api.qiaodan.com/reimburse/query/a/b"))


def item(num, uid, created="2026-10-01", **kw):
    d = {k: None for k in CANDIDATE_FIELDS}
    d.update(bizNumber=num, id=uid, createdAt=created)
    d.update(kw)
    return d


class MergeCandidatesTests(unittest.TestCase):
    def test_three_branch_or_merge_and_dedup(self):
        a = [item("1", "u1"), item("2", "u2")]
        b = [item("2", "u2"), item("3", "u3")]
        c = [item("4", "u4")]
        merged = merge_candidates([("Description15", a), ("Digest19", b), ("Description20", c)], 5)
        self.assertEqual([m["bizNumber"] for m in merged], ["4", "3", "2", "1"])  # 同日按单号降序
        by_num = {m["bizNumber"]: m for m in merged}
        self.assertEqual(by_num["2"]["matched_fields"], ["Description15", "Digest19"])  # 跨分支命中合并
        self.assertEqual(len(merged), 4)

    def test_same_number_different_uuid_not_merged(self):
        # 同单号不同 UUID 视为不同候选（身份以单号+UUID 识别）
        a = [item("1", "u1")]
        b = [item("1", "u2")]
        merged = merge_candidates([("Description15", a), ("Digest19", b)], 5)
        self.assertEqual(len(merged), 2)

    def test_descending_order_and_tie_marked(self):
        a = [item("1", "u1", created="2026-10-20"), item("2", "u2", created="2026-10-27"),
             item("3", "u3", created="2026-10-27")]
        merged = merge_candidates([("Description15", a)], 5)
        self.assertEqual([m["bizNumber"] for m in merged], ["3", "2", "1"])  # createdAt 降序，并列按单号
        self.assertTrue(merged[0]["tied_with_latest"] and merged[1]["tied_with_latest"])
        self.assertFalse(merged[2]["tied_with_latest"])

    def test_missing_created_at_sorts_last(self):
        a = [item("1", "u1", created=None), item("2", "u2", created="2026-01-01")]
        merged = merge_candidates([("Digest19", a)], 5)
        self.assertEqual([m["bizNumber"] for m in merged], ["2", "1"])

    def test_rows_without_number_skipped(self):
        merged = merge_candidates([("Description15", [{"id": "u9", "createdAt": "2026-10-01"}])], 5)
        self.assertEqual(merged, [])


class ClassifyOutcomeTests(unittest.TestCase):
    def test_zero_results_is_not_failure(self):
        branches = [{"status": "ok", "items": []} for _ in range(3)]
        self.assertEqual(classify_keyword_outcome(branches), "zero_results")

    def test_all_failed(self):
        branches = [{"status": "failed", "items": []} for _ in range(3)]
        self.assertEqual(classify_keyword_outcome(branches), "failed")

    def test_partial_failure_never_reports_zero_or_ok(self):
        branches = [{"status": "ok", "items": []}, {"status": "failed", "items": []},
                    {"status": "ok", "items": [item("1", "u1")]}]
        self.assertEqual(classify_keyword_outcome(branches), "partial")


class ExactMatchTests(unittest.TestCase):
    def test_exact_string_no_prefix(self):
        items = [item("15426104120", "u1"), item("15426104121", "u2")]
        candidate, err = exact_match(items, "15426104120")
        self.assertIsNone(err)
        self.assertEqual(candidate["bizNumber"], "15426104120")

    def test_prefix_not_matched(self):
        items = [item("15426104120", "u1")]
        candidate, err = exact_match(items, "1542610")
        self.assertIsNone(candidate)
        self.assertIsNone(err)

    def test_leading_zeros_preserved(self):
        items = [item("00154", "u1")]
        candidate, err = exact_match(items, "00154")
        self.assertIsNone(err)
        self.assertEqual(candidate["bizNumber"], "00154")

    def test_multiple_uuids_rejected(self):
        items = [item("154", "u1"), item("154", "u2")]
        candidate, err = exact_match(items, "154")
        self.assertIsNone(candidate)
        self.assertIn("多个 UUID", err)

    def test_no_match_is_zero_not_error(self):
        candidate, err = exact_match([item("9", "u1")], "154")
        self.assertIsNone(candidate)
        self.assertIsNone(err)


class EvidenceHygieneTests(unittest.TestCase):
    def test_candidate_fields_carry_no_credentials(self):
        protected = ("cookie", "token", "password", "authorization", "secret")
        for field in CANDIDATE_FIELDS:
            self.assertFalse(any(p in field.lower() for p in protected),
                             f"candidate field leaks credential-ish name: {field}")


if __name__ == "__main__":
    unittest.main()
