"""Synthetic fixtures only: no real personnel or account information."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bpm.plan import PlanError, file_hash, load_plan, money, plan_hash, validate_plan
from bpm.materials import inventory_materials


def build_valid_plan(directory, *, detail_count=1, cost_count=1, bank_count=1, empty_costs=False, total=12):
    """Return (plan, plan_path); all independent provenance is inside directory."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    material_dir = root / "originals"
    material_dir.mkdir(exist_ok=True)
    plan = {"schema_version": "1.0", "task_id": "synthetic-task", "document_type": "travel", "config_version": "1.0",
            "operator": "测试操作人", "applicant": {"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
            "template": {}, "materials": {},
            "header": {"corpCode": "测试公司", "bizOrign": "测试流程", "budgetYears": "2026", "payType": "转账", "currencyType": "人民币", "submitType": "差旅费", "description": "测试材料说明", "totalCost": f"{total}.00"},
            "tables": {"relations": [], "details": [], "costs": [], "banks": []}, "sources": {},
            "authorization": {"mode": "fill_only", "task_id": "synthetic-task", "statement": "仅填写本测试任务", "allow_submit": False},
            "unresolved": [], "not_applicable": [], "amount_rules": {"costs": "not_applicable" if empty_costs else "sum", "cost_amount_semantics": "line_total"}}
    for i in range(detail_count):
        plan["tables"]["details"].append({"row_id": f"d{i}", "fields": {"reimItem": "测试项目", "digest": f"测试摘要{i}", "budgetDeptName": "测试预算部", "budgetNo": "000123", "subjectName": "测试科目", "budgetItemName": "测试预算项目", "cost": f"{total // detail_count}.00"}})
    if empty_costs:
        plan["amount_rules"]["costs_reason"] = "本任务材料明确费用说明不适用"
        plan["not_applicable"] = ["费用说明"]
    else:
        for i in range(cost_count):
            plan["tables"]["costs"].append({"row_id": f"c{i}", "fields": {"project": "其它交通", "startDate": "2026-10-23", "endDate": "2026-10-23", "projectPlace": f"测试地点{i}", "count": "1", "cost": f"{total // cost_count}.00", "reason": f"测试事由{i}"}})
    for i in range(bank_count):
        plan["tables"]["banks"].append({"row_id": f"b{i}", "fields": {"payee": "测试收款人", "account": f"00000000000{i}", "bank": "测试银行", "bankCode": "001234", "cost": f"{total // bank_count}.00"}})
    # User-request provenance has explicit located scalar values, separate from executable plan.
    facts = {"applicant": copy.deepcopy(plan["applicant"]), "header": copy.deepcopy(plan["header"]), "tables": copy.deepcopy(plan["tables"]),
             "no_invoice_rule": "本夹具是离线合成数据，全部测试费用明确无需真实发票；不可用于生产报销"}
    proof = material_dir / "reviewed_facts.json"
    proof.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
    digest = file_hash(proof)
    pointers = ["/applicant/" + key for key in facts["applicant"]] + ["/header/" + key for key in facts["header"]]
    for table, rows in facts["tables"].items():
        for i, row in enumerate(rows):
            pointers.extend(f"/tables/{table}/{i}/fields/{key}" for key in row["fields"])
    plan["sources"] = {p: {"kind": "material", "path": str(proof), "locator": p, "sha256": digest} for p in pointers}
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(inventory_materials(material_dir)), encoding="utf-8")
    primary = "details" if empty_costs else "costs"
    plan["materials"] = {"manifest_path": str(manifest), "manifest_sha256": file_hash(manifest),
                         "no_invoice_rows": [{"plan_pointer": f"/tables/{primary}/{index}/fields/cost", "reason": facts["no_invoice_rule"],
                                              "proof": {"kind": "user", "path": str(proof), "locator": "/no_invoice_rule", "sha256": digest}}
                                             for index, _ in enumerate(plan["tables"][primary])]}
    snapshot = root / "template.json"
    snapshot.write_text(json.dumps({"biz_number": "000123456", "captured_at": "2026-10-23T10:00:00+08:00"}), encoding="utf-8")
    plan["template"] = {"biz_number": "000123456", "captured_at": "2026-10-23T10:00:00+08:00", "sha256": file_hash(snapshot), "snapshot_path": str(snapshot)}
    path = root / "fill_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    return plan, path


def refresh_manifest(root, plan):
    path = Path(root) / "manifest.json"
    path.write_text(json.dumps(inventory_materials(Path(root) / "originals")), encoding="utf-8")
    plan["materials"]["manifest_sha256"] = file_hash(path)


def add_invoice(root, plan, *, suffix="a", number="000001", amount="12.00", allocations=None):
    root = Path(root)
    original = root / f"originals/invoice-{suffix}.pdf"
    original.write_bytes(("synthetic scan " + suffix).encode())
    extraction = root / f"originals/ocr-{suffix}.json"
    data = {"schema_version": "1.0", "reviewed": True, "reviewed_by": "test-reviewer", "original_path": str(original), "original_sha256": file_hash(original),
            "records": [{"record_id": "0001", "fields": {"invoice_number": {"value": number, "locator": "page:1/region:number"}, "amount": {"value": amount, "locator": "page:1/region:total"}}}]}
    extraction.write_text(json.dumps(data), encoding="utf-8")
    primary = "details" if plan["amount_rules"]["costs"] == "not_applicable" else "costs"
    item = {"original_sha256": file_hash(original), "kind": "invoice", "extraction_path": str(extraction), "extraction_sha256": file_hash(extraction),
            "records": [{"record_id": "0001", "allocations": allocations or [{"plan_pointer": f"/tables/{primary}/0/fields/cost", "amount": amount}]}]}
    allocated = {entry["plan_pointer"] for entry in item["records"][0]["allocations"]}
    plan["materials"]["no_invoice_rows"] = [row for row in plan["materials"].get("no_invoice_rows", []) if row["plan_pointer"] not in allocated]
    plan["materials"].setdefault("image_documents", []).append(item)
    refresh_manifest(root, plan)
    return item


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.path = build_valid_plan(self.root)

    def codes(self, plan=None, verify=True):
        return [i["code"] for i in validate_plan(plan or self.plan, verify_sources=verify)]

    def test_valid_and_hash(self):
        self.assertEqual(load_plan(self.path, "测试操作人"), self.plan)
        self.assertEqual(plan_hash(self.plan), plan_hash(dict(reversed(list(self.plan.items())))))

    def test_multi_rows_more_than_two_costs(self):
        plan, _ = build_valid_plan(self.root / "multi", detail_count=2, cost_count=3, bank_count=2)
        self.assertEqual(validate_plan(plan), [])

    def test_identity(self):
        self.assertIn("IDENTITY_MISMATCH", [i["code"] for i in validate_plan(self.plan, "another")])
        self.plan["header"]["corpCode"] = "another company"
        self.assertIn("IDENTITY_MISMATCH", self.codes())

    def test_current_expenses_not_from_history(self):
        self.plan["sources"]["/tables/costs/0/fields/cost"]["kind"] = "template"
        self.assertIn("HISTORICAL_FACT_REUSE", self.codes())

    def test_current_digest_requires_primary_current_evidence(self):
        pointer = "/tables/details/0/fields/digest"
        current_proof = copy.deepcopy(self.plan["sources"][pointer])
        snapshot = Path(self.plan["template"]["snapshot_path"])
        data = json.loads(snapshot.read_text(encoding="utf-8"))
        data["tables"] = {"details": [{"fields": {"digest": self.plan["tables"]["details"][0]["fields"]["digest"]}}]}
        snapshot.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.plan["template"]["sha256"] = file_hash(snapshot)
        self.plan["sources"][pointer] = {"kind": "template", "path": str(snapshot), "sha256": file_hash(snapshot), "locator": pointer,
                                          "corroborates": [current_proof]}
        self.assertTrue(any(issue["path"] == pointer and issue["code"] == "HISTORICAL_FACT_REUSE" for issue in validate_plan(self.plan)))
        self.plan["sources"][pointer] = current_proof
        self.assertEqual(validate_plan(self.plan), [])

    def test_zero_images_still_require_explicit_no_invoice_evidence(self):
        self.assertEqual(validate_plan(self.plan), [])
        rows = self.plan["materials"].pop("no_invoice_rows")
        self.assertIn("NEEDS_INPUT", self.codes())
        self.plan["materials"]["no_invoice_rows"] = copy.deepcopy(rows)
        del self.plan["materials"]["no_invoice_rows"][0]["proof"]
        self.assertTrue(validate_plan(self.plan))
        self.plan["materials"]["no_invoice_rows"] = rows
        self.assertEqual(validate_plan(self.plan), [])

    def test_source_drift(self):
        (self.root / "originals/reviewed_facts.json").write_text("{}", encoding="utf-8")
        self.assertIn("SOURCE_INVALID", self.codes())

    def test_source_locator_mismatch(self):
        self.plan["header"]["description"] = "changed"
        self.assertIn("SOURCE_INVALID", self.codes())

    def test_total_and_bank_amount_mismatch(self):
        self.plan["tables"]["details"][0]["fields"]["cost"] = "11.00"
        self.assertIn("AMOUNT_MISMATCH", self.codes())

    def test_empty_costs_requires_reason(self):
        plan, _ = build_valid_plan(self.root / "empty", empty_costs=True)
        self.assertEqual(validate_plan(plan), [])
        del plan["amount_rules"]["costs_reason"]
        self.assertTrue(validate_plan(plan))

    def test_identifier_numeric_and_leading_zero(self):
        self.assertEqual(self.plan["tables"]["banks"][0]["fields"]["account"], "000000000000")
        self.plan["tables"]["banks"][0]["fields"]["account"] = 123456
        self.assertTrue(self.codes())

    def test_money_rejects_float_exponent_and_rounding(self):
        for value in (1.1, "1e2", "NaN", "-1", "1.005", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                money(value)

    def test_old_plan_and_unknown_type_rejected(self):
        self.assertTrue(validate_plan({"header": {"事由": {"value": "旧计划"}}}))
        self.plan["document_type"] = "unknown_type"
        self.assertIn("UNSUPPORTED_TYPE", self.codes())

    def test_save_task_binding_and_submit_forbidden(self):
        self.plan["authorization"]["task_id"] = "different"
        self.plan["authorization"]["allow_submit"] = True
        self.assertTrue(self.codes())

    def test_duplicate_row_business_value(self):
        row = copy.deepcopy(self.plan["tables"]["banks"][0])
        row["row_id"] = "different-id"
        self.plan["tables"]["banks"].append(row)
        self.assertTrue(any("duplicate business" in i["message"] for i in validate_plan(self.plan)))

    def test_no_default_plan_cli_and_traversal(self):
        import bpm.fill_cli as fill_once
        with self.assertRaises(SystemExit):
            fill_once.build_parser().parse_args([])
        for value in ("../escape", "a/b", "C:\\escape", "."):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fill_once._run_path(value)

    def test_resume_bound_to_hash(self):
        import bpm.fill_cli as fill_once
        with patch.object(fill_once, "ROOT", self.root), patch.object(fill_once, "RUNS", self.root / "runs"):
            run = fill_once.allocate_run({"plan_sha256": "a"}, "safe")
            self.assertEqual(fill_once.allocate_run({"plan_sha256": "a"}, "safe", True), run)
            with self.assertRaises(ValueError):
                fill_once.allocate_run({"plan_sha256": "b"}, "safe", True)
            with self.assertRaises(FileExistsError):
                fill_once.allocate_run({"plan_sha256": "a"}, "safe")

    def test_unit_price_times_count_and_explicit_derived_sum(self):
        self.plan["amount_rules"]["cost_amount_semantics"] = "unit_price_times_count"
        self.plan["tables"]["costs"][0]["fields"]["cost"] = "6.00"
        self.plan["tables"]["costs"][0]["fields"]["count"] = "2"
        self.plan["sources"]["/header/totalCost"] = {"kind": "derived", "operation": "sum", "inputs": ["/tables/details/0/fields/cost"]}
        self.assertEqual(validate_plan(self.plan, verify_sources=False), [])
        self.plan["sources"]["/header/totalCost"]["inputs"].append("/tables/details/0/fields/cost")
        self.assertTrue(validate_plan(self.plan, verify_sources=False))

    def test_malformed_top_level_and_proofs_fail_closed(self):
        for key in self.plan:
            for value in (None, [], {}, True, 4, ""):
                if value == self.plan[key] and type(value) is type(self.plan[key]):
                    continue
                with self.subTest(key=key, value=value):
                    malformed = copy.deepcopy(self.plan)
                    malformed[key] = value
                    self.assertTrue(validate_plan(malformed))
        self.plan["sources"]["/header/totalCost"] = {"kind": "derived", "operation": "sum", "inputs": [{}]}
        self.assertTrue(validate_plan(self.plan))

    def test_task_preparation_never_launches_browser(self):
        import bpm.fill_cli as fill_once
        task = {"schema_version": "1.0", "task_id": "synthetic-task", "document_type": "travel", "operator": "测试操作人", "template_biz_number": "000123456", "materials_dir": str(self.root / "originals"), "statement": "本次测试材料", "authorization": self.plan["authorization"]}
        path = self.root / "task.json"
        path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
        with patch.object(fill_once, "ROOT", self.root), patch.object(fill_once, "RUNS", self.root / "runs"), patch.object(fill_once.subprocess, "call") as launch:
            result = fill_once.prepare_task(path, "测试操作人", "prepared")
            self.assertEqual(result["status"], "NEEDS_INPUT")
            self.assertFalse(result["browser_launched"])
            self.assertTrue((self.root / "runs/prepared/events.jsonl").is_file())
            launch.assert_not_called()

    def test_invalid_plan_cli_refuses_before_subprocess(self):
        import bpm.fill_cli as fill_once
        self.plan["header"]["totalCost"] = "11.00"
        self.path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")
        with patch.object(fill_once.subprocess, "call") as launch:
            self.assertEqual(fill_once.main(["--fill-plan", str(self.path), "--expect-name", "测试操作人"]), 2)
            launch.assert_not_called()

    def test_reviewed_original_drift_rejected_through_plan(self):
        original = self.root / "originals/invoice.pdf"
        original.write_bytes(b"synthetic-original-v1")
        reviewed = self.root / "originals/ocr.json"
        data = {"schema_version": "1.0", "reviewed": True, "reviewed_by": "test-reviewer",
                "original_path": str(original), "original_sha256": file_hash(original),
                "records": [{"record_id": "0001", "fields": {"description": {"value": self.plan["header"]["description"], "locator": "page:1/region:header"}, "classification": {"value": "本原件为说明材料且本测试费用无需发票", "locator": "page:1/region:rule"}}}]}
        reviewed.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.plan["sources"]["/header/description"] = {"kind": "material", "path": str(reviewed), "sha256": file_hash(reviewed), "locator": "/records/0/fields/description/value"}
        proof = {"path": str(reviewed), "sha256": file_hash(reviewed), "locator": "/records/0/fields/classification/value"}
        reason = data["records"][0]["fields"]["classification"]["value"]
        self.plan["materials"]["image_documents"] = [{"original_sha256": file_hash(original), "kind": "not_invoice", "reason": reason, "proof": proof}]
        self.plan["materials"]["no_invoice_rows"] = [{"plan_pointer": "/tables/costs/0/fields/cost", "reason": reason, "proof": proof}]
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(inventory_materials(original.parent)), encoding="utf-8")
        self.plan["materials"]["manifest_sha256"] = file_hash(manifest)
        self.assertEqual(validate_plan(self.plan), [])
        original.write_bytes(b"synthetic-original-v2")
        # Even if the current material inventory is refreshed, stale OCR cannot pass.
        manifest.write_text(json.dumps(inventory_materials(original.parent)), encoding="utf-8")
        self.plan["materials"]["manifest_sha256"] = file_hash(manifest)
        self.assertTrue(any(issue["path"] == "/header/description" and issue["code"] == "SOURCE_INVALID" for issue in validate_plan(self.plan)))

    def test_valid_invoice_and_excel_invoice_conflict(self):
        plan, _ = build_valid_plan(self.root / "invoice-valid", total=20)
        add_invoice(self.root / "invoice-valid", plan, amount="20.00")
        self.assertEqual(validate_plan(plan), [])
        conflict, _ = build_valid_plan(self.root / "invoice-conflict", total=20)
        add_invoice(self.root / "invoice-conflict", conflict, amount="21.00")
        self.assertIn("INVOICE_AMOUNT_CONFLICT", self.codes(conflict))

    def test_different_scan_same_invoice_identity_rejected(self):
        add_invoice(self.root, self.plan, suffix="a")
        add_invoice(self.root, self.plan, suffix="b")
        self.assertTrue(any("duplicate invoice identity" in issue["message"] for issue in validate_plan(self.plan)))

    def test_missing_invoice_classification_or_reconciliation(self):
        item = add_invoice(self.root, self.plan)
        del self.plan["materials"]["image_documents"]
        self.assertIn("NEEDS_INPUT", self.codes())
        self.plan["materials"]["image_documents"] = [item]
        item["records"] = []
        self.assertTrue(any("every reviewed invoice" in issue["message"] for issue in validate_plan(self.plan)))
        item["records"] = [{"record_id": "0001", "allocations": [{"plan_pointer": "/tables/details/0/fields/cost", "amount": "12.00"}]}]
        self.assertTrue(any("primary expense" in issue["message"] for issue in validate_plan(self.plan)))
        item["extraction_path"] = str(self.root / "originals/missing-ocr.json")
        self.assertTrue(validate_plan(self.plan))

    def test_invoice_targets_details_only_when_costs_not_applicable(self):
        plan, _ = build_valid_plan(self.root / "no-costs", empty_costs=True)
        add_invoice(self.root / "no-costs", plan)
        self.assertEqual(validate_plan(plan), [])

    def test_allowance_no_invoice_source_and_corroboration(self):
        plan, _ = build_valid_plan(self.root / "allowance", cost_count=3)
        add_invoice(self.root / "allowance", plan, amount="8.00", allocations=[{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "4.00"}, {"plan_pointer": "/tables/costs/1/fields/cost", "amount": "4.00"}])
        path = self.root / "allowance/originals/user-rule.json"
        path.write_text(json.dumps({"reason": "本次第三行系经确认无需票据的补助", "amount": "4.00"}), encoding="utf-8")
        proof = {"path": str(path), "sha256": file_hash(path), "locator": "/reason"}
        plan["materials"]["no_invoice_rows"] = [{"plan_pointer": "/tables/costs/2/fields/cost", "reason": "本次第三行系经确认无需票据的补助", "proof": proof}]
        plan["sources"]["/tables/costs/2/fields/cost"]["corroborates"] = [{"path": str(path), "sha256": file_hash(path), "locator": "/amount"}]
        refresh_manifest(self.root / "allowance", plan)
        self.assertEqual(validate_plan(plan), [])
        plan["materials"]["no_invoice_rows"][0]["reason"] = "unsupported claim"
        self.assertTrue(validate_plan(plan))
        plan["materials"]["no_invoice_rows"][0]["reason"] = "本次第三行系经确认无需票据的补助"
        path.write_text(json.dumps({"reason": "本次第三行系经确认无需票据的补助", "amount": "5.00"}), encoding="utf-8")
        proof["sha256"] = file_hash(path)
        plan["sources"]["/tables/costs/2/fields/cost"]["corroborates"][0]["sha256"] = file_hash(path)
        refresh_manifest(self.root / "allowance", plan)
        self.assertIn("SOURCE_CONFLICT", self.codes(plan))


if __name__ == "__main__":
    unittest.main()
