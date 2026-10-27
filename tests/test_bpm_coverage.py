# -*- coding: utf-8 -*-
"""V3-R03 CASE-04 覆盖模型测试（ctr-14bb5408）。

fuel_pool_strict_surplus 严格覆盖分支 + 有效反例：
- F>R / F=R / F<R / ±0.01 元边界——仅严格大于通过；
- 覆盖富余：O 增大不改 R（不按油票加报）；
- 结构性违规（重复分配/未分配/油票入行）拒绝；
- 通用"票面=分配"闭合零放宽（回归）；
- validate_plan 可选 coverage 键 + schema 可选块（既有计划无 coverage 不受影响）。

夹具全部合成（金额/票号均为测试专用值，真实案例数值不作代码默认）。
"""
from __future__ import annotations

import copy
import json
import unittest
from decimal import Decimal
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bpm.coverage import (  # noqa: E402
    CoverageError, CoverageInputs, CoverageRow, evaluate_coverage,
    register_coverage_fact, validate_coverage_block,
)
from bpm.facts import FactSet, reconcile  # noqa: E402
from bpm.plan import validate_plan  # noqa: E402

RULE_SOURCE = "V3 §4.1 用户公里规则（合成测试口径）"


def synth_inputs(fuel_total: str = "200.00") -> CoverageInputs:
    rows = (
        CoverageRow("合成!H4", "60", ("toll-a",)),
        CoverageRow("合成!H5", "40", ("toll-b", "toll-c")),
    )
    return CoverageInputs(
        rate_per_km="1.00", rows=rows,
        invoice_face_totals={"toll-a": "10.00", "toll-b": "20.00", "toll-c": "10.00",
                             "fuel-x": fuel_total},
        toll_scope_ids=("toll-a", "toll-b", "toll-c"),
        fuel_pool_ids=("fuel-x",), rule_source=RULE_SOURCE,
    )


class EvaluateCoverageTests(unittest.TestCase):
    def test_f_greater_than_r_passes(self):
        r = evaluate_coverage(synth_inputs("200.00"))
        # K=100 rate=1.00 → M=100.00；T=40.00；R=140.00；O=200.00；F=240.00；margin=100.00
        self.assertEqual((r["M_subsidy"], r["T_toll"], r["R_reimburse"],
                          r["O_fuel_pool"], r["F_coverage_total"], r["coverage_margin"]),
                         ("100.00", "40.00", "140.00", "200.00", "240.00", "100.00"))
        self.assertTrue(r["gate_passed"])

    def test_f_equals_r_blocked(self):
        r = evaluate_coverage(synth_inputs("100.00"))  # F=140.00 == R=140.00
        self.assertFalse(r["gate_passed"])

    def test_f_less_than_r_blocked(self):
        r = evaluate_coverage(synth_inputs("50.00"))  # F=90.00 < R=140.00
        self.assertFalse(r["gate_passed"])

    def test_boundary_one_cent(self):
        # R=140.00：O=100.01 → margin +0.01 通过；O=100.00 → 0.00 拒；O=99.99 → −0.01 拒
        self.assertTrue(evaluate_coverage(synth_inputs("100.01"))["gate_passed"])
        self.assertFalse(evaluate_coverage(synth_inputs("100.00"))["gate_passed"])
        self.assertFalse(evaluate_coverage(synth_inputs("99.99"))["gate_passed"])

    def test_fuel_surplus_never_raises_r(self):
        base = evaluate_coverage(synth_inputs("200.00"))
        fat = evaluate_coverage(synth_inputs("5000.00"))
        for key in ("K_km", "M_subsidy", "T_toll", "R_reimburse"):
            self.assertEqual(base[key], fat[key], key)  # R 侧与油票池无关
        self.assertEqual(fat["coverage_margin"], "4900.00")  # F=5040.00−R=140.00，只抬 F/margin
        self.assertEqual(base["rate_per_km"], fat["rate_per_km"])

    def test_duplicate_allocation_rejected(self):
        bad = CoverageInputs(
            rate_per_km="1.00",
            rows=(CoverageRow("r1", "10", ("toll-a",)), CoverageRow("r2", "10", ("toll-a",))),
            invoice_face_totals={"toll-a": "10.00"}, toll_scope_ids=("toll-a",),
            fuel_pool_ids=(), rule_source=RULE_SOURCE)
        with self.assertRaises(CoverageError):
            evaluate_coverage(bad)

    def test_unallocated_toll_rejected(self):
        bad = CoverageInputs(
            rate_per_km="1.00", rows=(CoverageRow("r1", "10", ("toll-a",)),),
            invoice_face_totals={"toll-a": "10.00", "toll-b": "5.00"},
            toll_scope_ids=("toll-a", "toll-b"), fuel_pool_ids=(), rule_source=RULE_SOURCE)
        with self.assertRaises(CoverageError):
            evaluate_coverage(bad)

    def test_fuel_in_row_rejected(self):
        bad = CoverageInputs(
            rate_per_km="1.00",
            rows=(CoverageRow("r1", "10", ("toll-a", "fuel-x")),),
            invoice_face_totals={"toll-a": "10.00", "fuel-x": "99.00"},
            toll_scope_ids=("toll-a",), fuel_pool_ids=("fuel-x",), rule_source=RULE_SOURCE)
        with self.assertRaises(CoverageError):
            evaluate_coverage(bad)

    def test_scope_pool_overlap_rejected(self):
        bad = CoverageInputs(
            rate_per_km="1.00", rows=(CoverageRow("r1", "10", ("toll-a",)),),
            invoice_face_totals={"toll-a": "10.00"},
            toll_scope_ids=("toll-a",), fuel_pool_ids=("toll-a",), rule_source=RULE_SOURCE)
        with self.assertRaises(CoverageError):
            evaluate_coverage(bad)


class FactLayerTests(unittest.TestCase):
    def test_register_coverage_fact_and_reconcile_untouched(self):
        result = evaluate_coverage(synth_inputs("200.00"))
        fs = FactSet()
        fid = register_coverage_fact(fs, result, locator="合成:coverage",
                                     input_hashes={"case01-facts": "deadbeef"})
        self.assertEqual(fs.get(fid).kind, "coverage_evaluation")
        self.assertEqual(fs.get(fid).source, "deterministic_computation")
        self.assertTrue(fs.get(fid).derivation)
        # 通用 reconcile 语义零改动：仅一条覆盖事实、无费用/总额事实 → 仍按原规则阻断
        self.assertTrue(reconcile(fs).blocked)

    def test_generic_allocation_closure_not_relaxed(self):
        # 回归：无 coverage 声明的普通 FactSet，部分票面分配仍被通用闭合阻断
        fs = FactSet()
        inv, _ = fs.add_invoice("SYN-0001", "30.00", locator="合成票.pdf")
        exp = fs.add_expense("30.00", layer="detail", locator="合成行")
        fs.add_allocation(inv, exp, "20.00", locator="合成分配")
        self.assertTrue(reconcile(fs).blocked)


class CoverageBlockTests(unittest.TestCase):
    @staticmethod
    def block(**overrides):
        base = {"model": "fuel_pool_strict_surplus", "strict_gate": "greater",
                "rule_source": RULE_SOURCE, "rate_per_km": "1.00",
                "K_km": "100", "M_subsidy": "100.00", "T_toll": "40.00",
                "R_reimburse": "140.00", "O_fuel_pool": "200.00",
                "F_coverage_total": "240.00", "coverage_margin": "100.00"}
        base.update(overrides)
        return base

    def test_valid_block_passes(self):
        self.assertEqual(validate_coverage_block(self.block()), [])

    def test_gate_blocked_variants(self):
        # F=R（margin 0.00）与 F<R（margin −10.00）均阻断；F=R+0.01 通过
        issues = validate_coverage_block(self.block(O_fuel_pool="100.00", F_coverage_total="140.00",
                                                    coverage_margin="0.00"))
        self.assertTrue(any(i["code"] == "COVERAGE_GATE_BLOCKED" for i in issues))
        issues = validate_coverage_block(self.block(O_fuel_pool="90.00", F_coverage_total="130.00",
                                                    coverage_margin="-10.00"))
        self.assertTrue(any(i["code"] == "COVERAGE_GATE_BLOCKED" for i in issues))
        self.assertEqual(validate_coverage_block(self.block(O_fuel_pool="100.01", F_coverage_total="140.01",
                                                            coverage_margin="0.01")), [])

    def test_arithmetic_mismatch_rejected(self):
        issues = validate_coverage_block(self.block(M_subsidy="99.00"))  # K×rate 复算 100.00
        self.assertTrue(issues and all(i["code"] == "COVERAGE_INVALID" for i in issues))

    def test_unknown_and_missing_keys_rejected(self):
        bad = self.block(); bad["extra"] = "x"
        self.assertTrue(validate_coverage_block(bad))
        bad2 = {k: v for k, v in self.block().items() if k != "T_toll"}
        self.assertTrue(validate_coverage_block(bad2))

    def test_wrong_model_rejected(self):
        issues = validate_coverage_block(self.block(model="loose_pool"))
        self.assertTrue(issues)


class PlanAndSchemaTests(unittest.TestCase):
    PLAN = json.loads((ROOT / "automation/runs/20261024-155625-travelloop/fill_plan_r7.json").read_text(encoding="utf-8"))

    def test_validate_plan_accepts_valid_coverage(self):
        plan = copy.deepcopy(self.PLAN)
        plan["coverage"] = {"model": "fuel_pool_strict_surplus", "strict_gate": "greater",
                            "rule_source": RULE_SOURCE, "rate_per_km": "1.00", "K_km": "100",
                            "M_subsidy": "100.00", "T_toll": "40.00", "R_reimburse": "140.00",
                            "O_fuel_pool": "200.00", "F_coverage_total": "240.00",
                            "coverage_margin": "100.00"}
        issues = [i for i in validate_plan(plan) if i["path"] == "/coverage"]
        self.assertEqual(issues, [])

    def test_validate_plan_blocks_f_le_r(self):
        plan = copy.deepcopy(self.PLAN)
        plan["coverage"] = {"model": "fuel_pool_strict_surplus", "strict_gate": "greater",
                            "rule_source": RULE_SOURCE, "rate_per_km": "1.00", "K_km": "100",
                            "M_subsidy": "100.00", "T_toll": "40.00", "R_reimburse": "140.00",
                            "O_fuel_pool": "100.00", "F_coverage_total": "140.00",
                            "coverage_margin": "0.00"}
        issues = [i for i in validate_plan(plan) if i["path"] == "/coverage"]
        self.assertTrue(any(i["code"] == "COVERAGE_GATE_BLOCKED" for i in issues))

    def test_validate_plan_rejects_unknown_coverage_keys(self):
        plan = copy.deepcopy(self.PLAN)
        plan["coverage"] = {"bogus": True}
        issues = [i for i in validate_plan(plan) if i["path"] == "/coverage"]
        self.assertTrue(issues)

    def test_plan_without_coverage_unchanged(self):
        base = validate_plan(self.PLAN)
        self.assertFalse([i for i in base if i["path"] == "/coverage"])

    def test_schema_optional_and_strict(self):
        import jsonschema
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(self.PLAN, schema)  # 既有计划（无 coverage）仍通过
        with_cov = copy.deepcopy(self.PLAN)
        with_cov["coverage"] = {"model": "fuel_pool_strict_surplus", "strict_gate": "greater",
                                "rule_source": RULE_SOURCE, "rate_per_km": "1.00", "K_km": "100",
                                "M_subsidy": "100.00", "T_toll": "40.00", "R_reimburse": "140.00",
                                "O_fuel_pool": "200.00", "F_coverage_total": "240.00",
                                "coverage_margin": "100.00"}
        jsonschema.validate(with_cov, schema)
        bad = copy.deepcopy(with_cov)
        bad["coverage"]["nope"] = 1
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


if __name__ == "__main__":
    unittest.main()
