"""Synthetic scenarios based on observed columns; never usable for real claims."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from bpm.plan import file_hash, validate_plan, ROOT
from bpm.materials import inventory_materials
from bpm.verify import verify_snapshot
from test_bpm_plan import build_valid_plan, add_invoice, refresh_manifest


def refresh_type_proofs(plan, path):
    root = Path(path).parent
    proof = root / "originals/reviewed_facts.json"
    facts = {key: copy.deepcopy(plan[key]) for key in ("applicant", "header", "tables", "table_applicability")}
    facts["no_invoice_rule"] = "离线合成场景免真实票据，不得用于生产报销"
    proof.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    pointers = [f"/{block}/{key}" for block in ("applicant", "header") for key in facts[block]]
    pointers += [f"/tables/{table}/{i}/fields/{key}" for table, rows in facts["tables"].items()
                 for i, row in enumerate(rows) for key in row["fields"]]
    pointers += [f"/table_applicability/{key}/reason" for key in facts["table_applicability"]]
    plan["sources"] = {p: {"kind": "material", "path": str(proof), "locator": p, "sha256": file_hash(proof)} for p in pointers}
    primary = "products" if plan["document_type"] == "rd_materials" else "costs" if plan["tables"]["costs"] else "details"
    amount_field = "price" if primary == "products" else "cost"
    plan["materials"]["no_invoice_rows"] = [{"plan_pointer": f"/tables/{primary}/{i}/fields/{amount_field}",
        "reason": facts["no_invoice_rule"], "proof": {"kind": "user", "path": str(proof), "locator": "/no_invoice_rule", "sha256": file_hash(proof)}}
        for i, row in enumerate(plan["tables"][primary])]
    refresh_manifest(root, plan)
    Path(path).write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")


def build_type_plan(root, kind, *, cost_count=3, empty_costs=False, product_count=3):
    plan, path = build_valid_plan(root, cost_count=cost_count, empty_costs=empty_costs or kind == "rd_materials")
    plan["document_type"] = kind
    plan["header"]["submitType"] = "快递费" if kind == "express" else "研发材料费"
    plan["table_applicability"] = {"relations": {"reason": "本合成业务明确不关联任何单据"}}
    plan["tables"]["details"][0]["fields"]["budgetOwner"] = "测试预算归属"
    if not plan["tables"]["costs"]:
        plan["table_applicability"]["costs"] = {"reason": "本合成业务费用说明不适用"}
    if kind == "rd_materials":
        plan["tables"]["products"] = [{"row_id": f"p{i}", "fields": {
            "code": f"000100{i}", "name": f"测试物品{i}", "purchaser": "测试购买人", "price": str(12 // product_count) + ".00", "description": ""}}
            for i in range(product_count)]
        plan["amount_rules"].update(products="sum", product_amount_semantics="line_total")
    snapshot = Path(plan["template"]["snapshot_path"])
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    data.update(document_type=kind, uuid="a" * 32, header={"submitType": plan["header"]["submitType"]})
    snapshot.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    plan["template"]["sha256"] = file_hash(snapshot)
    refresh_type_proofs(plan, path)
    return plan, path


class NewTypePlanTests(unittest.TestCase):
    def test_extra_budget_echo_requires_readonly_without_inventing_budget_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, path = build_type_plan(tmp, "express")
            snap = {"page": {"url": "https://bpm.qiaodan.com/oa/reimburse?type=new", "is_new": True,
                              "operator": plan["operator"], "biz_number": "", "uuid": "", "status": "编制中"},
                    "applicant": copy.deepcopy(plan["applicant"]), "header": copy.deepcopy(plan["header"]),
                    "tables": copy.deepcopy(plan["tables"]), "extra_tables": {"detailrels": []},
                    "completeness": {key: True for key in ("header", "detailrels", *plan["tables"])},
                    "observed_at": "2026-10-23T12:00:00Z"}
            row = snap["tables"]["details"][0]
            row["fields"]["subjectSurplus"] = "-1.00"
            row["field_metadata"] = {"subjectSurplus": {"readonly": True}}
            self.assertTrue(verify_snapshot(plan, snap)["ok"])
            row["field_metadata"]["subjectSurplus"]["readonly"] = False
            self.assertFalse(verify_snapshot(plan, snap)["ok"])
            row["fields"]["unmodeledQuantity"] = "2"
            self.assertIn("UNMODELED_BUSINESS_FIELD", [i["code"] for i in verify_snapshot(plan, snap)["issues"]])

    def test_valid_multiline_express_and_empty_costs_have_exact_schema_branches(self):
        import jsonschema
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            for kind, empty in (("express", False), ("express", True), ("rd_materials", True)):
                plan, path = build_type_plan(Path(tmp) / (kind + str(empty)), kind, empty_costs=empty)
                self.assertEqual(validate_plan(plan), [])
                jsonschema.validate(plan, schema)
                wrong = copy.deepcopy(plan)
                wrong["header"]["submitType"] = "差旅费"
                self.assertTrue(validate_plan(wrong))
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(wrong, schema)

    def test_product_duplicate_archive_unmodeled_quantity_and_historical_facts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, path = build_type_plan(tmp, "rd_materials")
            for change in ("duplicate", "quantity", "history", "missing_applicability"):
                wrong = copy.deepcopy(plan)
                if change == "duplicate":
                    wrong["tables"]["products"][1]["fields"]["code"] = wrong["tables"]["products"][0]["fields"]["code"]
                elif change == "quantity":
                    wrong["tables"]["products"][0]["fields"]["count"] = "2"
                elif change == "history":
                    wrong["sources"]["/tables/products/0/fields/code"]["kind"] = "template"
                else:
                    wrong["table_applicability"] = {}
                self.assertTrue(validate_plan(wrong), change)

    def test_invoice_allocations_cover_product_prices_and_detect_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, path = build_type_plan(tmp, "rd_materials", product_count=1)
            item = add_invoice(tmp, plan, amount="12.00")
            item["records"][0]["allocations"][0]["plan_pointer"] = "/tables/products/0/fields/price"
            plan["materials"]["no_invoice_rows"] = []
            self.assertEqual(validate_plan(plan), [])
            item["records"][0]["allocations"][0]["amount"] = "11.00"
            self.assertTrue(validate_plan(plan))


if __name__ == "__main__":
    unittest.main()
