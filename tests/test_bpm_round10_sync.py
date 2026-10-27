"""Round-10（ctr-8cb7b247 §1）附属同步测试：manifest 五类型/schema enum。

注：「一页多票拒绝」承重断言不在本文件，在
tests/test_bpm_extraction.py::D18MatrixTests::test_d18_pdf_one_page_two_invoices_pins_single_record_contract
（D18 §3-1；progress.json errata[0] 订正，docstring 随 V3-R05 同步）。
"""
import json
from pathlib import Path
import unittest

from bpm.plan import ROOT


class ManifestSyncTests(unittest.TestCase):
    def test_source_manifest_freezes_five_type_configs_and_notes(self):
        import tools.verification.build as verify_bpm_build
        manifest_files = verify_bpm_build.CODE
        expected = ["automation/document-types/{0}".format(name) for name in
                    ("travel.json", "express.json", "rd_materials.json",
                     "office_supplies.json", "welfare_labor.json",
                     "office_supplies.notes.md", "welfare_labor.notes.md")]
        for relative in expected:
            self.assertIn(relative, manifest_files, relative)
            self.assertTrue((ROOT / relative).is_file(), relative)
        # manifest 清单同步后主交付参考（full-chain.md）也入冻结面
        self.assertIn(".claude/skills/bpm-fill-run/references/full-chain.md", manifest_files)


class SchemaEnumSyncTests(unittest.TestCase):
    def test_schema_covers_five_document_types_and_new_plans_validate(self):
        import jsonschema
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["document_type"]["enum"],
                         ["travel", "express", "rd_materials", "office_supplies", "welfare_labor"])
        self.assertEqual(schema["properties"]["header"]["properties"]["submitType"]["enum"],
                         ["差旅费", "快递费", "研发材料费", "低值易耗品、办公用品采购", "福利费、劳保用品"])
        branches = {branch["if"]["properties"]["document_type"]["const"] for branch in schema["allOf"]}
        self.assertEqual(branches, {"travel", "express", "rd_materials", "office_supplies", "welfare_labor"})
        for document_type, run in (("office_supplies", "20261024-193500-officeloop"),
                                   ("welfare_labor", "20261024-194500-welfareloop")):
            with self.subTest(document_type=document_type):
                plan = json.loads((ROOT / "automation/runs" / run / "fill_plan_r9.json").read_text(encoding="utf-8"))
                jsonschema.validate(plan, schema)
                self.assertEqual(plan["document_type"], document_type)

    def test_schema_rejects_unregistered_type_and_wrong_label_pairing(self):
        import jsonschema
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        plan = json.loads((ROOT / "automation/runs/20261024-193500-officeloop/fill_plan_r9.json").read_text(encoding="utf-8"))
        jsonschema.validate(plan, schema)
        wrong = json.loads(json.dumps(plan))
        wrong["document_type"] = "meeting_expense"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(wrong, schema)
        mismatched = json.loads(json.dumps(plan))
        mismatched["header"]["submitType"] = "福利费、劳保用品"  # 02 单配 04 标签
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(mismatched, schema)


if __name__ == "__main__":
    unittest.main()
