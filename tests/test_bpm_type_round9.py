"""Round-9（ctr-15712bcb §1）02/04 首件单元测试：注册/配置校验/离线计划链。

对应 code-adaptation-prep A 表 level 1（config→注册）与 level 2（离线链计划验证）。
不做真实页面控件测试、不注册业务填写路径（合同本轮零浏览器动作）。
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bpm.plan import file_hash, validate_plan
from bpm.types import TypeConfigError, check_template_type, resolve_type, type_from_category
from test_bpm_new_types import build_type_plan, refresh_type_proofs

ROUND9 = {"office_supplies": ("低值易耗品、办公用品采购", "02"),
          "welfare_labor": ("福利费、劳保用品", "04")}


def build_round9_plan(root, kind):
    """复用 express 夹具骨架改写为 02/04 计划（列集与 express 完全一致，实测）。"""
    label = ROUND9[kind][0]
    plan, path = build_type_plan(Path(root) / kind, "express", empty_costs=(kind == "welfare_labor"))
    plan["document_type"] = kind
    plan["header"]["submitType"] = label
    if kind == "welfare_labor":
        plan["amount_rules"].update(costs="not_applicable",
                                    costs_reason="本类历史单 costs 全空（研究样本实测），合成业务沿用")
    snapshot = Path(plan["template"]["snapshot_path"])
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    data.update(document_type=kind, uuid="b" * 32, header={"submitType": label})
    snapshot.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    plan["template"]["sha256"] = file_hash(snapshot)
    refresh_type_proofs(plan, path)
    return plan, path


class Round9TypeCommon(unittest.TestCase):
    kind = None  # 子类注入

    def setUp(self):
        if self.kind is None:  # pragma: no cover - 基类不直接跑
            self.skipTest("common base")
        self.label, self.code = ROUND9[self.kind]
        self.config_path = Path(resolve_type(self.kind).path)

    def test_registration_identity_and_template_binding(self):
        identity = resolve_type(self.kind)
        self.assertTrue(identity.executable)
        self.assertEqual(identity.document_type, self.kind)
        self.assertEqual(type_from_category(self.label), self.kind)
        self.assertEqual(type_from_category(self.code), self.kind)
        # 新类型摘要绑定注册表+配置+解析器（非裸配置哈希），且跨调用稳定
        self.assertNotEqual(identity.sha256, file_hash(self.config_path))
        self.assertEqual(resolve_type(self.kind).sha256, identity.sha256)
        for category in (self.label, self.code):
            check_template_type({"document_type": self.kind, "uuid": "c" * 32,
                                 "header": {"submitType": category}}, self.kind)
        for snapshot, code in (
                ({"document_type": "travel", "uuid": "c" * 32, "header": {"submitType": self.label}}, "TYPE_MISMATCH"),
                ({"document_type": self.kind, "uuid": "c" * 32, "header": {"submitType": "差旅费"}}, "TYPE_MISMATCH"),
                ({"document_type": self.kind, "header": {"submitType": self.label}}, "NEEDS_INPUT"),
                ({"document_type": self.kind, "uuid": "zz", "header": {"submitType": self.label}}, "NEEDS_INPUT")):
            with self.subTest(snapshot=snapshot), self.assertRaises(TypeConfigError) as caught:
                check_template_type(snapshot, self.kind)
            self.assertEqual(caught.exception.code, code)

    def test_negative_config_mutations_are_rejected(self):
        identity = resolve_type(self.kind)
        mutations = [("category", {"label": self.label, "api_code": "99"}),
                     ("execution_state", "ready"),
                     ("header", dict(identity.config["header"],
                                     submitType={"label": "报销类别", "type": "text", "editor": "dropdown",
                                                 "allowed_values": ["差旅费"]})),
                     ("invoice_policy", {"mode": "document_level", "required": False}),
                     ("invoice_policy", {"mode": "document_level", "required": False,
                                         "evidence": "x", "note": "多余键"}),
                     ("invoice_policy", {"mode": "either_level", "required": False, "evidence": "x"}),
                     ("invoice_policy", {"mode": "document_level", "required": "no", "evidence": "x"})]
        for key, value in mutations:
            data = copy.deepcopy(identity.config)
            data[key] = value
            with self.subTest(key=key), mock.patch("bpm.types.Path.read_bytes",
                                                   return_value=json.dumps(data).encode()):
                with self.assertRaises(TypeConfigError) as caught:
                    resolve_type(self.kind)
            self.assertEqual(caught.exception.code, "TYPE_CONFIG_INVALID")

    def test_offline_chain_plan_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build_round9_plan(tmp, self.kind)
            self.assertEqual(validate_plan(plan), [])

    def test_plan_level_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build_round9_plan(tmp, self.kind)
            relation = {"row_id": "r0", "fields": {"bizTypeName": "申请书", "bizNumber": "10125122466",
                                                   "nowCost": "1.00", "isLast": "是"}}
            wrong = copy.deepcopy(plan)
            wrong["tables"]["relations"] = [relation]
            self.assertIn("UNSUPPORTED_RELATION", [i.get("code") for i in validate_plan(wrong)])
            wrong = copy.deepcopy(plan)
            wrong["header"]["submitType"] = "差旅费"
            self.assertTrue(validate_plan(wrong))


class OfficeSuppliesRound9Tests(Round9TypeCommon):
    kind = "office_supplies"

    def test_primary_table_is_costs_when_amount_rules_sum(self):
        # 02 配置 costs 可用：primary=costs，免票行落在 costs（与离线链首件一致）
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build_round9_plan(tmp, self.kind)
            self.assertEqual(plan["amount_rules"]["costs"], "sum")
            pointers = {row["plan_pointer"] for row in plan["materials"]["no_invoice_rows"]}
            self.assertEqual(pointers, {f"/tables/costs/{i}/fields/cost"
                                        for i in range(len(plan["tables"]["costs"]))})


class WelfareLaborRound9Tests(Round9TypeCommon):
    kind = "welfare_labor"

    def test_empty_costs_requires_reason_and_applicability(self):
        # 04 costs 不适用：缺 costs_reason 或缺 table_applicability.costs 理由都必须被拒
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build_round9_plan(tmp, self.kind)
            self.assertEqual(plan["tables"]["costs"], [])
            wrong = copy.deepcopy(plan)
            del wrong["amount_rules"]["costs_reason"]
            self.assertTrue(any(i["path"] == "/amount_rules" for i in validate_plan(wrong)))
            wrong = copy.deepcopy(plan)
            del wrong["table_applicability"]["costs"]
            self.assertTrue(any(i["path"] == "/table_applicability" for i in validate_plan(wrong)))
            pointers = {row["plan_pointer"] for row in plan["materials"]["no_invoice_rows"]}
            self.assertEqual(pointers, {f"/tables/details/{i}/fields/cost"
                                        for i in range(len(plan["tables"]["details"]))})


if __name__ == "__main__":
    unittest.main()
