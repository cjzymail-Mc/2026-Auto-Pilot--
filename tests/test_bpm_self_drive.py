# -*- coding: utf-8 -*-
"""BPM-SELFDRIVE-20261027-V1 R1 自驾规则模型测试（ctr-640d0763 D2/D3）。

self_drive_strict_surplus_v1（规则配置 automation/business-scenarios/self_drive.json）：
- 配置加载封闭校验 + 哈希绑定；
- 确定性金额模型 M/T/C/R/O/F、严格门槛 F>R（F=R/F<R/±0.01 边界无浮点容差）；
- 合同 §6.1 经典反例：09-05 +2.00 与 09-28 −2.00 抵消不放行、12025098708 +4.00 与
  12025123375 −10.00 逐单定位、正向对照 12025092018 437.18 不被错误派生值误判、
  日期反例 11-12→11-14 / 11-24→12-24 识别；
- 新 30.00/日餐补与历史 12/18/24/36/48 分离；有效公出日按日去重；
- 与旧 fuel_pool_strict_surplus（R=M+T，无餐补）分离并存零回归。

夹具脱敏：票号/人员标识全部合成；案例对照值（1438 km / 486.93 / 300.00 / 2224.93 /
1924.93 / 185.90 / 195.86 / 437.18 等）仅按合同 §5/§6.1 作离线测试对照，不进生产
路由逻辑，不含账号/手机号/会话元数据/凭证。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bpm.self_drive import (  # noqa: E402
    DEFAULT_CONFIG, MODEL_NAME, SCENARIO_ID, SelfDriveError, SelfDriveInputs,
    SelfDriveRow, MealDay, compare_by_key, evaluate_self_drive,
    load_self_drive_rules, reconcile_date_labels, rules_sha256,
)
import bpm.coverage as bpm_coverage  # noqa: E402

RULE_SOURCE = "合同 BPM-SELFDRIVE-20261027-V1 §4.4（合成测试口径）"
HISTORICAL_MEAL_VALUES = ("12.00", "18.00", "24.00", "36.00", "48.00")


def case_reference_inputs(fuel_total: str = "1900.00") -> SelfDriveInputs:
    """合同 §5/§6.1 离线对照夹具：09-05/09-28 原件复算行 + 合成凑总行（凑足 K=1438、
    T=486.93）+ 10 个合成有效日 + 合成油票池。凑总行/日期/油票不是案例事实。"""
    rows = (
        SelfDriveRow("09-05", "146", ("toll-0905",)),   # 146×1.00+39.90=185.90
        SelfDriveRow("09-28", "132", ("toll-0928",)),   # 132×1.00+63.86=195.86
        SelfDriveRow("合成凑总1", "580", ("toll-f1",)),  # +191.59
        SelfDriveRow("合成凑总2", "580", ("toll-f2",)),  # +191.58
    )
    days = tuple(MealDay("2025-12-{0:02d}".format(n), "合成公出单SYN-{0:03d}/参与行".format(n))
                 for n in range(1, 11))  # 10 个合成有效日
    return SelfDriveInputs(
        rate_per_km="1.00", meal_per_valid_day="30.00", rows=rows, meal_days=days,
        invoice_face_totals={"toll-0905": "39.90", "toll-0928": "63.86",
                             "toll-f1": "191.59", "toll-f2": "191.58",
                             "fuel-pool": fuel_total},
        toll_scope_ids=("toll-0905", "toll-0928", "toll-f1", "toll-f2"),
        fuel_pool_ids=("fuel-pool",), rule_source=RULE_SOURCE,
    )


def synth_inputs(fuel_total: str = "200.00", meal_days=None,
                 meal: str = "30.00", rate: str = "1.00") -> SelfDriveInputs:
    rows = (SelfDriveRow("合成!H4", "60", ("toll-a",)),
            SelfDriveRow("合成!H5", "40", ("toll-b", "toll-c")))
    days = meal_days if meal_days is not None else ("2025-12-01", "2025-12-02", "2025-12-03")
    return SelfDriveInputs(
        rate_per_km=rate, meal_per_valid_day=meal, rows=rows,
        meal_days=tuple(d if isinstance(d, MealDay) else MealDay(d, "合成公出单SYN-001/参与行")
                        for d in days),
        invoice_face_totals={"toll-a": "10.00", "toll-b": "20.00", "toll-c": "10.00",
                             "fuel-x": fuel_total},
        toll_scope_ids=("toll-a", "toll-b", "toll-c"),
        fuel_pool_ids=("fuel-x",), rule_source=RULE_SOURCE,
    )


class ConfigTests(unittest.TestCase):
    def test_load_default_config(self):
        rules = load_self_drive_rules()
        self.assertEqual(rules.scenario_id, SCENARIO_ID)
        self.assertEqual(rules.model, MODEL_NAME)
        self.assertEqual(rules.version, "1.0.0")
        self.assertEqual(rules.rate_str(), "1.00")
        self.assertEqual(rules.meal_str(), "30.00")
        self.assertEqual(rules.strict_gate, "greater")
        self.assertEqual(rules.config_path, str(DEFAULT_CONFIG))
        self.assertEqual(rules.config_sha256, rules_sha256())
        self.assertEqual(len(rules.config_sha256), 64)
        self.assertIn("30", rules.rule_source)

    def test_sha256_stable_and_tamper_sensitive(self):
        first = rules_sha256()
        self.assertEqual(first, rules_sha256())  # 稳定
        with tempfile.TemporaryDirectory() as tmp:
            copy_path = Path(tmp) / "self_drive.json"
            data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
            data["rules"]["rate_per_km"] = "0.90"  # 篡改单价
            copy_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertNotEqual(rules_sha256(copy_path), first)

    def test_reject_invalid_configs(self):
        cases = {
            "model": lambda d: d["rules"].update(model="some_other_model"),
            "scenario": lambda d: d.update(scenario_id="not_self_drive"),
            "schema": lambda d: d.update(schema_version="2.0"),
            "missing_rules": lambda d: d.pop("rules"),
            "missing_source": lambda d: d.pop("rule_source"),
            "gate": lambda d: d["rules"].update(strict_gate="gte"),
            "rate_zero": lambda d: d["rules"].update(rate_per_km="0.00"),
            "meal_negative": lambda d: d["rules"].update(meal_per_valid_day="-30.00"),
            "source_blank": lambda d: d["rule_source"].update(user_rule_statement=" "),
            "separation_missing": lambda d: d["rules"].pop("separation"),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                data = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
                mutate(data)
                path = Path(tmp) / "self_drive.json"
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                with self.assertRaises(SelfDriveError):
                    load_self_drive_rules(path)

    def test_reject_missing_or_broken_file(self):
        with self.assertRaises(SelfDriveError):
            rules_sha256(Path("no/such/file.json"))
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            with self.assertRaises(SelfDriveError):
                load_self_drive_rules(broken)


class EvaluateTests(unittest.TestCase):
    def test_synth_happy_path_amounts(self):
        # K=100×1.00=M=100.00；T=40.00；C=3日×30.00=90.00；R=230.00；
        # O=200.00；F=240.00；margin=10.00 → 严格通过
        r = evaluate_self_drive(synth_inputs("200.00"))
        self.assertEqual((r["K_km"], r["M_subsidy"], r["T_toll"], r["C_meal"],
                          r["R_reimburse"], r["O_fuel_pool"], r["F_coverage_total"],
                          r["coverage_margin"]),
                         ("100", "100.00", "40.00", "90.00", "230.00", "200.00",
                          "240.00", "10.00"))
        self.assertTrue(r["gate_passed"])
        self.assertEqual(r["meal_day_count"], 3)

    def test_fuel_only_raises_coverage_not_reimburse(self):
        base = evaluate_self_drive(synth_inputs("200.00"))
        rich = evaluate_self_drive(synth_inputs("999.00"))
        self.assertEqual(rich["R_reimburse"], base["R_reimburse"])  # O 不入 R
        self.assertEqual(rich["F_coverage_total"], "1039.00")
        self.assertEqual(rich["coverage_margin"], "809.00")

    def test_f_equals_r_blocked(self):
        r = evaluate_self_drive(synth_inputs("190.00"))  # F=230.00 == R=230.00
        self.assertEqual(r["coverage_margin"], "0.00")
        self.assertFalse(r["gate_passed"])

    def test_f_less_than_r_blocked(self):
        r = evaluate_self_drive(synth_inputs("100.00"))  # F=140.00 < R=230.00
        self.assertEqual(r["coverage_margin"], "-90.00")
        self.assertFalse(r["gate_passed"])

    def test_one_cent_surplus_passes_no_float_tolerance(self):
        r = evaluate_self_drive(synth_inputs("190.01"))  # margin 恰 +0.01
        self.assertEqual(r["coverage_margin"], "0.01")
        self.assertTrue(r["gate_passed"])

    def test_float_money_rejected(self):
        with self.assertRaises(SelfDriveError):
            evaluate_self_drive(synth_inputs(meal=30.0))  # type: ignore[arg-type]
        with self.assertRaises(SelfDriveError):
            evaluate_self_drive(synth_inputs(rate=1.0))  # type: ignore[arg-type]

    def test_structural_violations_rejected(self):
        base = synth_inputs()
        cases = {
            "overlap": lambda i: SelfDriveInputs(**{**i.__dict__, "fuel_pool_ids": ("toll-a",)}),
            "duplicate_alloc": lambda i: SelfDriveInputs(**{**i.__dict__, "rows": (
                SelfDriveRow("合成!H4", "60", ("toll-a",)),
                SelfDriveRow("合成!H5", "40", ("toll-a", "toll-b", "toll-c")))}),
            "unallocated": lambda i: SelfDriveInputs(**{**i.__dict__, "rows": (
                SelfDriveRow("合成!H4", "100", ("toll-a",)),)}),
            "fuel_in_row": lambda i: SelfDriveInputs(**{**i.__dict__, "rows": (
                SelfDriveRow("合成!H4", "60", ("toll-a",)),
                SelfDriveRow("合成!H5", "40", ("toll-b", "fuel-x")))}),
            "face_missing": lambda i: SelfDriveInputs(**{**i.__dict__, "invoice_face_totals": {
                "toll-a": "10.00", "fuel-x": "200.00"}}),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(SelfDriveError):
                    evaluate_self_drive(mutate(base))

    def test_meal_day_duplicate_rejected(self):
        days = (MealDay("2025-12-01", "合成单SYN-A"), MealDay("2025-12-01", "合成单SYN-B"))
        with self.assertRaises(SelfDriveError):  # 同日多事实/多单只计一次——重复即拒绝
            evaluate_self_drive(synth_inputs(meal_days=days))

    def test_meal_day_iso_format_enforced(self):
        for bad in ("2025/12/01", "12-01", "2025-12-1", ""):
            with self.subTest(bad=bad):
                with self.assertRaises(SelfDriveError):
                    evaluate_self_drive(synth_inputs(meal_days=(MealDay(bad, "合成"),)))

    def test_ten_days_meal_three_hundred(self):
        days = tuple("2025-12-{0:02d}".format(n) for n in range(1, 11))  # 10 个合成日
        r = evaluate_self_drive(synth_inputs("200.00", meal_days=days))
        self.assertEqual(r["meal_day_count"], 10)
        self.assertEqual(r["C_meal"], "300.00")


class RulesBindingTests(unittest.TestCase):
    """输入与版本化规则配置绑定：历史餐补值（12/18/24/36/48）传入即拒绝（§4.4 分离）。"""

    def test_historical_meal_values_rejected(self):
        rules = load_self_drive_rules()
        for meal in HISTORICAL_MEAL_VALUES:
            with self.subTest(meal=meal):
                with self.assertRaises(SelfDriveError):
                    evaluate_self_drive(synth_inputs(meal=meal), rules=rules)

    def test_rate_mismatch_rejected(self):
        rules = load_self_drive_rules()
        with self.assertRaises(SelfDriveError):
            evaluate_self_drive(synth_inputs(rate="1.10"), rules=rules)

    def test_version_mismatch_rejected(self):
        rules = load_self_drive_rules()
        inputs = SelfDriveInputs(**{**synth_inputs().__dict__, "rule_version": "0.9.9"})
        with self.assertRaises(SelfDriveError):
            evaluate_self_drive(inputs, rules=rules)

    def test_bound_pass_through(self):
        rules = load_self_drive_rules()
        r = evaluate_self_drive(synth_inputs(), rules=rules)  # 1.00 / 30.00 与配置一致
        self.assertEqual((r["rate_per_km"], r["meal_per_valid_day"]), ("1.00", "30.00"))
        self.assertEqual(r["rule_version"], rules.version)


class CaseReferenceTests(unittest.TestCase):
    """合同 §5 离线对照（仅测试参照）：10 日 / 交通 1924.93 / 餐补 300.00 / 合计 2224.93。

    行构成为两行原件复算行（09-05 / 09-28，§6.1）+ 两行合成凑总行（凑足 K=1438、
    T=486.93）；凑总行不是案例事实，仅为把对照总额拆成可复算输入。
    """

    def case_inputs(self, fuel_total: str = "1900.00") -> SelfDriveInputs:
        return case_reference_inputs(fuel_total)

    def test_case_offline_reference_totals(self):
        r = evaluate_self_drive(self.case_inputs())
        self.assertEqual(r["K_km"], "1438")
        self.assertEqual(r["M_subsidy"], "1438.00")
        self.assertEqual(r["T_toll"], "486.93")
        self.assertEqual(r["C_meal"], "300.00")
        self.assertEqual(r["R_reimburse"], "2224.93")
        self.assertEqual((Decimal(r["M_subsidy"]) + Decimal(r["T_toll"])).quantize(Decimal("0.01")),
                         Decimal("1924.93"))  # 交通总额对照
        self.assertTrue(r["gate_passed"])  # F=2386.93 > R=2224.93（合成油票池）

    def test_case_rows_match_section_6_1_recomputation(self):
        r = evaluate_self_drive(self.case_inputs())
        by_row = {row["row_id"]: row for row in r["rows"]}
        self.assertEqual(by_row["09-05"]["row_transport"], "185.90")
        self.assertEqual(by_row["09-28"]["row_transport"], "195.86")


class ClassicCounterexampleTests(unittest.TestCase):
    """合同 §6.1：合计相等也必须失败；抵消不放行；正向对照不误判。"""

    def test_transport_errors_cancel_not_passed(self):
        expected = {"09-05 交通": "185.90", "09-28 交通": "195.86"}   # 原件复算
        declared = {"09-05 交通": "187.90", "09-28 交通": "193.86"}   # 历史单值
        # 两条错误恰好抵消：合计相等（381.76）——只断言总额会漏检
        self.assertEqual(sum(Decimal(v) for v in expected.values()),
                         sum(Decimal(v) for v in declared.values()))
        diffs = compare_by_key(expected, declared, "交通对账")
        self.assertEqual(len(diffs), 2)  # 抵消不放行：逐行差异仍在
        by_key = {d[0]: d for d in diffs}
        self.assertEqual(by_key["09-05 交通"][3], "2.00")    # 历史值−复算 = +2.00
        self.assertEqual(by_key["09-28 交通"][3], "-2.00")   # 历史值−复算 = −2.00

    def test_per_form_diffs_located_and_cumulative(self):
        # 其余 7 张按原件及历史餐补核对一致——两张一致的合成键代表它们
        expected = {"12025098708": "231.86", "12025123375": "206.59",
                    "12025092018": "437.18", "其它一致单SYN-A": "100.00"}
        declared = {"12025098708": "235.86", "12025123375": "196.59",
                    "12025092018": "437.18", "其它一致单SYN-A": "100.00"}
        diffs = compare_by_key(expected, declared, "逐单对账")
        by_key = {d[0]: d for d in diffs}
        self.assertEqual(set(by_key), {"12025098708", "12025123375"})  # 一致单零差异
        self.assertEqual(by_key["12025098708"][3], "4.00")     # +4.00 逐单定位
        self.assertEqual(by_key["12025123375"][3], "-10.00")   # −10.00 逐单定位
        cumulative = sum(Decimal(d[3]) for d in diffs)
        self.assertEqual(cumulative, Decimal("-6.00"))         # 两条关联差异累计 −6.00

    def test_positive_control_43718_not_misjudged(self):
        # 正确路径：期望值从原件复算（09-05 行交通由模型算出 185.90，不是抄历史 187.90）
        rows = evaluate_self_drive(case_reference_inputs())["rows"]
        row_0905 = {row["row_id"]: row for row in rows}["09-05"]
        self.assertEqual(row_0905["row_transport"], "185.90")
        recomputed = Decimal("191.28") + Decimal(row_0905["row_transport"]) \
            + Decimal("30.00") + Decimal("30.00")
        self.assertEqual(recomputed, Decimal("437.18"))
        # 原件复算期望 == 历史声明 → 该关联本身正确，不得误判
        self.assertEqual(compare_by_key({"12025092018": "437.18"},
                                        {"12025092018": "437.18"}, "正向对照"), [])
        # 反模式：用错误派生值（187.90）拼出的 439.18 当期望会指责这张正确的单——
        # 差异落在期望侧污染，修正方法是回原件复算，不是判该单错误
        polluted = Decimal("191.28") + Decimal("187.90") + Decimal("30.00") + Decimal("30.00")
        self.assertEqual(polluted, Decimal("439.18"))
        self.assertNotEqual(polluted, Decimal("437.18"))
        # 其他行的错误不外溢：单独对照该键仍零差异
        self.assertEqual(compare_by_key({"12025092018": "437.18"},
                                        {"12025092018": "437.18"}, "隔离对照"), [])

    def test_date_label_counterexamples_identified(self):
        verified = ("2025-11-12", "2025-11-24")          # 已核实事实日
        declared = ("2025-11-14", "2025-12-24")          # 被误写的标签
        r = reconcile_date_labels(verified, declared)
        self.assertEqual(r["matched"], [])
        self.assertEqual([w[0] for w in r["wrong_labels"]], ["2025-11-14", "2025-12-24"])
        by_declared = {w[0]: w for w in r["wrong_labels"]}
        self.assertEqual(by_declared["2025-12-24"][1], "2025-11-24")  # 唯一同日候选→疑似 11-24
        self.assertIn("2025-11-24", by_declared["2025-12-24"][2])
        # 11-14 与两个 11 月事实日同月，无唯一候选（提示尽力而为，识别本身不依赖提示）
        self.assertIsNone(by_declared["2025-11-14"][1])
        self.assertEqual(r["unaccounted_verified"], ["2025-11-12", "2025-11-24"])

    def test_date_labels_correct_pass_and_structure(self):
        verified = ("2025-11-12", "2025-11-24", "2025-12-10")
        r = reconcile_date_labels(verified, verified)
        self.assertEqual(r["matched"], list(verified))
        self.assertEqual(r["wrong_labels"], [])
        self.assertEqual(r["unaccounted_verified"], [])
        with self.assertRaises(SelfDriveError):  # 声明日期重复
            reconcile_date_labels(verified, ("2025-11-12", "2025-11-12"))
        with self.assertRaises(SelfDriveError):  # 非 ISO
            reconcile_date_labels(verified, ("2025/11/12",))
        with self.assertRaises(SelfDriveError):
            reconcile_date_labels(("11-12",), ("2025-11-12",))


class BindingDisciplineTests(unittest.TestCase):
    """P2-2（MC-R1，ctr-2433e4a3 D4）：生产路径调用 evaluate_self_drive 必须显式绑定 rules=。

    bpm_self_drive.evaluate_self_drive 的 rules=None 仅为测试的原始计算器口径；生产模块
    （bpm/ 中的实现与根目录兼容入口）任何调用点都必须在调用处绑定 rules=load_self_drive_rules()
    ——历史餐补分离是机制而非约定。本测试扫描生产源码：出现未绑定调用即失败。
    """

    def test_production_call_sites_bind_rules(self):
        import re
        root = Path(__file__).resolve().parents[1]
        targets = sorted((root / "bpm").rglob("*.py")) + sorted(root.glob("*.py"))
        offenders = []
        for path in targets:
            if path == root / "bpm/self_drive.py":
                continue  # 定义与测试口径模块自身不在生产调用面
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"evaluate_self_drive\s*\(", text):
                window = text[match.start():match.start() + 400]
                line_no = text[:match.start()].count("\n") + 1
                if "rules=" not in window:
                    offenders.append("{0}:{1}".format(path.name, line_no))
        self.assertEqual(
            offenders, [],
            "生产调用未绑定 rules=load_self_drive_rules()（P2-2 纪律）: {0}".format(offenders))


class SeparationTests(unittest.TestCase):
    """新模型与旧 fuel_pool_strict_surplus 分离并存：旧行为零改动、新行为不静默升级。"""

    def test_models_distinct(self):
        self.assertEqual(bpm_coverage.MODEL_NAME, "fuel_pool_strict_surplus")
        self.assertEqual(MODEL_NAME, "self_drive_strict_surplus_v1")
        self.assertNotEqual(MODEL_NAME, bpm_coverage.MODEL_NAME)

    def test_old_model_still_r_equals_m_plus_t_without_meal(self):
        cov = bpm_coverage.evaluate_coverage(bpm_coverage.CoverageInputs(
            rate_per_km="1.00",
            rows=(bpm_coverage.CoverageRow("合成!H4", "146", ("toll-a",)),),
            invoice_face_totals={"toll-a": "39.90", "fuel-x": "200.00"},
            toll_scope_ids=("toll-a",), fuel_pool_ids=("fuel-x",),
            rule_source="V3 §4.1（分离回归）"))
        self.assertEqual(cov["R_reimburse"], "185.90")  # R=M+T，无餐补项
        self.assertNotIn("C_meal", cov)
        self.assertNotIn("meal_days", cov)
        self.assertNotIn("meal_day_count", cov)

    def test_old_model_inputs_have_no_meal_fields(self):
        fields = bpm_coverage.CoverageInputs.__dataclass_fields__
        self.assertFalse(any("meal" in name for name in fields))

    def test_historical_meal_not_interpreted_as_new_rule(self):
        # 不绑配置时模型可按输入口径算（原始计算器语义），但生产路径必须绑定规则配置，
        # 绑定后历史值全部拒绝——不存在“把 36.00 静默当新规则”的通路
        raw = evaluate_self_drive(synth_inputs(meal="36.00"))
        self.assertEqual(raw["C_meal"], "108.00")  # 3×36，仅原始计算
        rules = load_self_drive_rules()
        with self.assertRaises(SelfDriveError):
            evaluate_self_drive(synth_inputs(meal="36.00"), rules=rules)


if __name__ == "__main__":
    unittest.main()
