# -*- coding: utf-8 -*-
"""oa_test_relations 占位意图块（V3 §5.3；V3-R07 ctr-affef776 冻结范围 2）。

受限随机测试占位关联：仅 travel + fill_only；行值必须已物化为真实 relations 行；
本块只声明 test_placeholder 语义/随机方法与种子/枚举绑定/分离声明，不引入免核值。
"""
import copy
import json
import unittest
from pathlib import Path

from bpm.plan import ROOT, validate_plan


def _base_plan():
    plan = json.loads((ROOT / "automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json").read_text(encoding="utf-8"))
    plan = copy.deepcopy(plan)
    plan["task_id"] = "oa-test-relations-fixture"
    plan["authorization"]["task_id"] = plan["task_id"]
    return plan


def _add_placeholder(plan, *, row_ids=("case07-relations-1",), chosen_index=0, candidates=5, seed="seed-fixture"):
    plan["tables"]["relations"] = [{"row_id": "case07-relations-1", "fields": {
        "bizTypeName": "公出单", "bizNumber": "12026096668", "nowCost": "1924.93", "isLast": "是"}}]
    plan["oa_test_relations"] = {
        "test_placeholder": True,
        "purpose": "测试占位关联（fixture）",
        "separation": "与 actual_trip_matches 严格分离（fixture）",
        "row_ids": list(row_ids),
        "selection": {"method": "random.Random(seed).randrange", "seed": seed,
                      "enumeration_path": "fixture/enumeration.json",
                      "enumeration_sha256": "a" * 64, "candidates_count": candidates,
                      "chosen_index": chosen_index}}
    return plan


class OaTestRelationsTests(unittest.TestCase):
    def test_accepts_travel_fill_only_placeholder_block(self):
        plan = _add_placeholder(_base_plan())
        issues = [i for i in validate_plan(plan, "陈晶", verify_sources=False)
                  if "oa_test_relations" in i.get("path", "/")]
        self.assertEqual(issues, [])

    def test_rejects_non_travel_document_type(self):
        plan = _add_placeholder(_base_plan())
        plan["document_type"] = "express"
        issues = validate_plan(plan, "陈晶", verify_sources=False)
        self.assertTrue(any("placeholder test relations are modeled for travel only" in i["message"] for i in issues))

    def test_rejects_save_draft_authorization(self):
        plan = _add_placeholder(_base_plan())
        plan["authorization"]["mode"] = "save_draft"
        issues = validate_plan(plan, "陈晶", verify_sources=False)
        self.assertTrue(any("placeholder test relations require fill_only" in i["message"] for i in issues))

    def test_rejects_row_ids_without_materialized_relations(self):
        plan = _add_placeholder(_base_plan())
        plan["tables"]["relations"] = []
        issues = validate_plan(plan, "陈晶", verify_sources=False)
        self.assertTrue(any("placeholder intent requires materialized relations rows" in i["message"] for i in issues))

    def test_rejects_unknown_row_id_and_duplicate_references(self):
        for row_ids in (["missing-row"], ["case07-relations-1", "case07-relations-1"]):
            plan = _add_placeholder(_base_plan(), row_ids=row_ids)
            issues = validate_plan(plan, "陈晶", verify_sources=False)
            self.assertTrue(any("row ids must reference existing relation rows" in i["message"] for i in issues), row_ids)

    def test_rejects_false_test_placeholder_and_open_keys(self):
        plan = _add_placeholder(_base_plan())
        plan["oa_test_relations"]["test_placeholder"] = False
        self.assertTrue(any("must be marked test_placeholder=true" in i["message"]
                            for i in validate_plan(plan, "陈晶", verify_sources=False)))
        plan = _add_placeholder(_base_plan())
        plan["oa_test_relations"]["extra"] = 1
        self.assertTrue(any("exact placeholder intent keys required" in i["message"]
                            for i in validate_plan(plan, "陈晶", verify_sources=False)))

    def test_rejects_chosen_index_outside_candidates(self):
        plan = _add_placeholder(_base_plan(), chosen_index=5, candidates=5)
        issues = validate_plan(plan, "陈晶", verify_sources=False)
        self.assertTrue(any("chosen index outside enumerated candidates" in i["message"] for i in issues))

    def test_schema_conformance(self):
        import jsonschema
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        plan = _add_placeholder(_base_plan())
        jsonschema.validate(plan, schema)  # 接受
        broken = copy.deepcopy(plan)
        broken["oa_test_relations"]["selection"]["chosen_index"] = -1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(broken, schema)


if __name__ == "__main__":
    unittest.main()
