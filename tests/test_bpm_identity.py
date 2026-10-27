# -*- coding: utf-8 -*-
"""bpm_identity 身份关系测试（BPM-SELFDRIVE-20261027-V1 R2 D5，用户 2026-10-27 指示）。

覆盖：结构校验/未知缺口、不换人凑对照值、不默认零餐补、schema 联动。
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bpm.identity import (creator_identity_established, expected_mismatch_gap,
                          meal_basis_gap, validate_identity_relations)

ROOT = Path(__file__).resolve().parent.parent

VALID = {
    "login_operator": {"name": "操作人甲", "source": "oa_profile",
                       "source_locator": "oa-顶栏#只读核实"},
    "form_creator": {"name": "制单人乙", "source": "template_page",
                     "source_locator": "真实新页#系统默认制单人"},
    "expense_owner": {"name": "所属人丙", "source": "workout_detail",
                      "source_locator": "公出单事实行#人员"},
}


class ValidationTests(unittest.TestCase):
    def test_full_valid_relations_pass(self):
        self.assertEqual(validate_identity_relations(VALID), [])
        self.assertTrue(creator_identity_established(VALID))
        self.assertIsNone(meal_basis_gap(VALID))   # 餐补前提成立

    def test_missing_entirely_is_needs_input(self):
        for empty in (None, {}, "x", []):
            gaps = validate_identity_relations(empty)
            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0]["code"], "IDENTITY_RELATIONS_MISSING")

    def test_unknown_role_reports_gap_without_guessing(self):
        gaps = validate_identity_relations({"login_operator": VALID["login_operator"]})
        codes = [gap["code"] for gap in gaps]
        self.assertEqual(codes.count("IDENTITY_ROLE_UNKNOWN"), 2)   # 制单人/所属人未知
        self.assertIn("form_creator", [gap["role"] for gap in gaps])
        self.assertIn("expense_owner", [gap["role"] for gap in gaps])

    def test_unsourced_role_reports_gap(self):
        partial = dict(VALID, form_creator={"name": "制单人乙"})
        gaps = validate_identity_relations(partial)
        self.assertTrue(any(gap["code"] == "IDENTITY_ROLE_UNSOURCED" and gap["role"] == "form_creator"
                            for gap in gaps))
        bad_source = dict(VALID, form_creator={"name": "制单人乙", "source": "guess",
                                               "source_locator": "猜的"})
        self.assertTrue(any(gap["code"] == "IDENTITY_ROLE_UNSOURCED"
                            for gap in validate_identity_relations(bad_source)))

    def test_unknown_role_field_rejected(self):
        extra = dict(VALID, approver={"name": "丁", "source": "oa_profile",
                                      "source_locator": "x"})
        self.assertTrue(any(gap["code"] == "IDENTITY_ROLE_INVALID"
                            for gap in validate_identity_relations(extra)))


class MealBasisTests(unittest.TestCase):
    def test_creator_unestablished_yields_gap_not_zero_meal(self):
        """不默认零餐补：身份不成立 → 缺口（NEEDS_INPUT），不是 C=0。"""
        for relations in (None, {}, VALID,
                          {"form_creator": {"name": "乙", "source": "user_statement",
                                            "source_locator": "仅声明"}}):
            gap = meal_basis_gap(relations)
            if relations is VALID:
                self.assertIsNone(gap)
                continue
            self.assertIsNotNone(gap)
            self.assertEqual(gap["code"], "MEAL_BASIS_CREATOR_UNKNOWN")
            self.assertIn("不默认零餐补", gap["detail"])

    def test_statement_only_source_does_not_establish_creator(self):
        """user_statement 只是声明：单独不构成制单人身份合法成立。"""
        relations = dict(VALID, form_creator={"name": "乙", "source": "user_statement",
                                              "source_locator": "用户口头说明"})
        self.assertFalse(creator_identity_established(relations))

    def test_no_swapping_people_to_match_reference(self):
        """不换人凑对照值：预期与实测不一致 → 真实缺口，不改预期也不换人。"""
        gaps = expected_mismatch_gap(VALID, "另一个名字")
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["code"], "IDENTITY_EXPECTATION_MISMATCH")
        self.assertIn("不换人凑对照值", gaps[0]["detail"])
        # 一致或无预期 → 无缺口
        self.assertEqual(expected_mismatch_gap(VALID, "制单人乙"), [])
        self.assertEqual(expected_mismatch_gap(VALID, None), [])


class SchemaLinkageTests(unittest.TestCase):
    def test_task_schema_accepts_identity_relations(self):
        import jsonschema
        schema = json.loads((ROOT / "automation" / "task.schema.json").read_text(encoding="utf-8"))
        task = {
            "schema_version": "1.0", "task_id": "d5-schema-check",
            "document_type": "travel", "operator": "操作人甲",
            "template_biz_number": "000123456", "materials_dir": "originals",
            "statement": "合成 schema 联动测试",
            "authorization": {"mode": "fill_only", "task_id": "d5-schema-check",
                              "statement": "仅测试", "allow_submit": False},
            "identity_relations": VALID,
        }
        jsonschema.validate(task, schema)   # 合法：通过
        self.assertEqual(validate_identity_relations(task["identity_relations"]), [])

    def test_task_schema_rejects_unsourced_role(self):
        import jsonschema
        schema = json.loads((ROOT / "automation" / "task.schema.json").read_text(encoding="utf-8"))
        task = {
            "schema_version": "1.0", "task_id": "d5-schema-check",
            "document_type": "travel", "operator": "操作人甲",
            "template_biz_number": "000123456", "materials_dir": "originals",
            "statement": "合成 schema 联动测试",
            "authorization": {"mode": "fill_only", "task_id": "d5-schema-check",
                              "statement": "仅测试", "allow_submit": False},
            "identity_relations": dict(VALID, expense_owner={"name": "丙", "source": "guess",
                                                             "source_locator": "猜的"}),
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(task, schema)


if __name__ == "__main__":
    unittest.main()
