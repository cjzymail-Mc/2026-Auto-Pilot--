import copy
import json
import tempfile
import unittest
from pathlib import Path

from bpm.plan import file_hash, validate_plan
from bpm.verify import verify_snapshot


def build_fixture(root):
    root = Path(root)
    plan = {
        "schema_version": "1.0", "task_id": "test-task", "document_type": "travel",
        "config_version": "1.0", "operator": "测试操作人",
        "applicant": {"name": "测试人员", "company": "测试公司", "department": "测试部门"},
        "header": {"corpCode": "测试公司", "bizOrign": "测试流程", "budgetYears": "2026",
                   "payType": "转账", "currencyType": "人民币", "submitType": "差旅费",
                   "description": "测试说明", "totalCost": "20.00"},
        "tables": {
            "relations": [{"row_id": "r1", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000001", "nowCost": "20.00", "isLast": "是"}}],
            "details": [{"row_id": "d1", "fields": {"reimItem": "通行费", "digest": "测试通行费", "budgetDeptName": "测试部门", "budgetNo": "15626000001", "subjectName": "差旅费", "budgetItemName": "年度预算项目", "cost": "20.00"}}],
            "costs": [{"row_id": "c1", "fields": {"project": "其它交通", "startDate": "2026-10-22", "endDate": "2026-10-22", "projectPlace": "厦门", "count": "2", "cost": "20.00", "reason": "测试行程"}}],
            "banks": [{"row_id": "b1", "fields": {"payee": "测试人员", "account": "001234567890", "bank": "测试银行", "bankCode": "001234", "cost": "20.00"}}],
        },
        "authorization": {"mode": "save_draft", "task_id": "test-task", "statement": "测试明确授权保存本任务草稿，禁止提交", "allow_submit": False},
        "unresolved": [], "not_applicable": [],
        "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
    }
    def write(name, obj):
        path = root / name
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return path
    template = write("template.json", {"biz_number": "15426000001", "uuid": "a" * 32, "captured_at": "2026-10-23T01:00:00Z"})
    manifest = write("manifest.json", {"schema_version": "1.0", "root": str(root), "files": []})
    proof = write("facts.json", {**{key: plan[key] for key in ("applicant", "header", "tables")},
                                 "no_invoice_rule": "本夹具仅为合成离线测试，测试费用明确无需真实票据；不适用于生产报销"})
    plan["template"] = {"biz_number": "15426000001", "captured_at": "2026-10-23T01:00:00Z", "snapshot_path": str(template), "sha256": file_hash(template)}
    plan["materials"] = {"manifest_path": str(manifest), "manifest_sha256": file_hash(manifest),
                         "no_invoice_rows": [{"plan_pointer": f"/tables/costs/{index}/fields/cost",
                                              "reason": "本夹具仅为合成离线测试，测试费用明确无需真实票据；不适用于生产报销",
                                              "proof": {"kind": "user", "path": str(proof), "locator": "/no_invoice_rule", "sha256": file_hash(proof)}}
                                             for index, _ in enumerate(plan["tables"]["costs"])]}
    sources = {}
    for block in ("applicant", "header"):
        for key in plan[block]:
            sources[f"/{block}/{key}"] = {"kind": "user", "path": str(proof), "sha256": file_hash(proof), "locator": f"/{block}/{key}"}
    for table, rows in plan["tables"].items():
        for index, row in enumerate(rows):
            for key in row["fields"]:
                pointer = f"/tables/{table}/{index}/fields/{key}"
                sources[pointer] = {"kind": "user", "path": str(proof), "sha256": file_hash(proof), "locator": pointer}
    plan["sources"] = sources
    snapshot = {"page": {"url": "https://bpm.qiaodan.com/oa/reimburse?type=new", "is_new": True, "operator": plan["operator"], "biz_number": "", "uuid": "", "status": ""},
                "applicant": copy.deepcopy(plan["applicant"]), "header": copy.deepcopy(plan["header"]),
                "tables": {key: [{"fields": copy.deepcopy(row["fields"])} for row in rows] for key, rows in plan["tables"].items()},
                "observed_at": "2026-10-23T01:00:01Z", "completeness": {key: True for key in ("header", "relations", "details", "costs", "banks", "detailrels")},
                "extra_tables": {"detailrels": [{"bizNo": "12026000001", "bizTypeName": "公出单", "cost": "20.00", "bizDetailCost": "0", "bizDetailNum": "0", "usedCost": "0"}]},
                "validation": {"invalid_fields": [], "pending": False}}
    return plan, snapshot


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plan, self.snapshot = build_fixture(self.temp.name)
        self.assertEqual(validate_plan(self.plan), [])

    def verify(self):
        return verify_snapshot(self.plan, self.snapshot)

    def test_full_fresh_snapshot_passes(self):
        self.assertTrue(self.verify()["ok"])

    def test_numeric_display_equivalence_is_field_scoped(self):
        self.snapshot["tables"]["banks"][0]["fields"]["cost"] = "20.0"
        self.assertTrue(self.verify()["ok"])
        self.snapshot["tables"]["banks"][0]["fields"]["account"] = "1234567890"
        self.assertFalse(self.verify()["ok"])

    def test_missing_extra_duplicate_and_wrong_association_rejected(self):
        original = copy.deepcopy(self.snapshot)
        for mutate in (
            lambda: self.snapshot["tables"]["banks"].clear(),
            lambda: self.snapshot["tables"]["banks"].append(copy.deepcopy(self.snapshot["tables"]["banks"][0])),
            lambda: self.snapshot["tables"]["relations"][0]["fields"].update(bizNumber="12026000002"),
            lambda: self.snapshot["tables"]["details"][0]["fields"].pop("budgetNo"),
        ):
            self.snapshot = copy.deepcopy(original)
            mutate()
            self.assertFalse(self.verify()["ok"])

    def test_incomplete_readback_empty_category_amount_and_loan_fail(self):
        original = copy.deepcopy(self.snapshot)
        mutations = (
            lambda: self.snapshot["completeness"].update(costs=False),
            lambda: self.snapshot["header"].update(submitType=""),
            lambda: self.snapshot["tables"]["details"][0]["fields"].update(cost="19.99"),
            lambda: self.snapshot["header"].update(loanCost="1"),
            lambda: self.snapshot["extra_tables"].update(products=[{"cost": "0"}]),
            lambda: self.snapshot["page"].update(url="https://other.invalid/oa/reimburse/new"),
            lambda: self.snapshot["page"].update(is_new=False),
        )
        for mutate in mutations:
            self.snapshot = copy.deepcopy(original)
            mutate()
            self.assertFalse(self.verify()["ok"])

    def test_source_hash_drift_rejected_independently(self):
        Path(self.plan["template"]["snapshot_path"]).write_text("changed", encoding="utf-8")
        self.assertFalse(self.verify()["ok"])

    def test_generated_detail_projection_requires_exact_relation_and_zero_allocations(self):
        row = {"bizNo": "12026000001", "bizTypeName": "公出单", "cost": "20.00",
               "bizDetailCost": "0.00", "bizDetailNum": "0", "usedCost": "0.00"}
        self.snapshot["extra_tables"]["detailrels"] = [row]
        self.assertTrue(self.verify()["ok"])
        for key, value in (("bizNo", "12026000002"), ("cost", "19.00"), ("usedCost", "1.00")):
            changed = copy.deepcopy(row)
            changed[key] = value
            self.snapshot["extra_tables"]["detailrels"] = [changed]
            self.assertFalse(self.verify()["ok"])
        self.snapshot["extra_tables"]["detailrels"] = [row, copy.deepcopy(row)]
        self.assertFalse(self.verify()["ok"])

    def test_missing_nonobject_observations_fail_closed(self):
        for key in ("page", "applicant", "header", "tables", "completeness", "extra_tables"):
            changed = copy.deepcopy(self.snapshot)
            changed[key] = []
            self.assertFalse(verify_snapshot(self.plan, changed)["ok"])

    def test_related_detail_readback_cannot_be_omitted(self):
        self.snapshot["extra_tables"] = {}
        self.assertFalse(self.verify()["ok"])

    def test_complete_but_empty_or_malformed_projection_is_rejected(self):
        for rows in ([], None, {}, "", [None], [{"fields": None}]):
            with self.subTest(rows=rows):
                self.snapshot["extra_tables"]["detailrels"] = rows
                self.snapshot["completeness"]["detailrels"] = True
                self.assertFalse(self.verify()["ok"])

    def test_system_empty_is_scoped_to_confirmed_readonly_zero_display(self):
        row=self.snapshot["extra_tables"]["detailrels"][0]
        row["fields"]={k:v for k,v in row.items()}
        row["field_metadata"]={p:{"readonly":True} for p in ("bizDetailCost","bizDetailNum","usedCost")}
        for p in row["field_metadata"]:
            row["fields"][p]=""
        self.assertTrue(self.verify()["ok"])
        original=copy.deepcopy(row)
        for prop,value in (("usedCost","1"),("usedCost","bad"),("bizTypeName","未知类型")):
            row.clear();row.update(copy.deepcopy(original));row["fields"][prop]=value
            self.assertFalse(self.verify()["ok"])
        row.clear();row.update(copy.deepcopy(original));row["fields"].pop("usedCost")
        self.assertFalse(self.verify()["ok"])
        row.clear();row.update(copy.deepcopy(original));row["field_metadata"]["usedCost"]["readonly"]=False
        self.assertFalse(self.verify()["ok"])
        self.snapshot["extra_tables"] = {"detailrels": []}
        self.snapshot["completeness"].pop("detailrels")
        self.assertFalse(self.verify()["ok"])

    def test_visible_required_and_angular_validity_fail_closed(self):
        for validity in ({"invalid_fields": [{"property": "unknownRequired", "reason": "required"}], "pending": False},
                         {"invalid_fields": [], "pending": True},
                         {"invalid_fields": [], "pending": "false"}, {}, []):
            changed = copy.deepcopy(self.snapshot)
            changed["validation"] = validity
            self.assertFalse(verify_snapshot(self.plan, changed)["ok"])

    def test_after_save_requires_new_identity_and_known_draft_status(self):
        self.snapshot["page"].update(url="https://bpm.qiaodan.com/oa/reimburse?type=view&id="+"b"*32, is_new=False, uuid="b"*32, biz_number="15426000002", status="编制中")
        self.assertTrue(verify_snapshot(self.plan, self.snapshot, phase="after_save")["ok"])
        for key, value in (("biz_number", self.plan["template"]["biz_number"]), ("status", "已提交"), ("uuid", "bad")):
            changed = copy.deepcopy(self.snapshot)
            changed["page"][key] = value
            self.assertFalse(verify_snapshot(self.plan, changed, phase="after_save")["ok"])
        changed = copy.deepcopy(self.snapshot)
        changed["page"].update(uuid="a"*32, url="https://bpm.qiaodan.com/oa/reimburse?type=view&id="+"a"*32)
        self.assertFalse(verify_snapshot(self.plan, changed, phase="after_save")["ok"])


if __name__ == "__main__":
    unittest.main()
