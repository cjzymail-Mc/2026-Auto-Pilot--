"""Dual-root (v2.0) material contract tests; synthetic fixtures only, no real business data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from bpm.materials import (DUAL_MANIFEST_VERSION, dual_hash_sets, inventory_materials, prepare_dual_materials,
                           prepare_materials, register_derived, validate_dual_manifest, validate_image_documents,
                           validate_manifest, validate_value_proof)
from bpm.plan import file_hash


def build_reviewed_extraction(original, *, number="00001234", amount="12.00"):
    return {"schema_version": "1.0", "reviewed": True, "reviewed_by": "test-agent+review-pipeline",
            "original_path": str(original), "original_sha256": file_hash(original),
            "records": [{"record_id": "0001", "fields": {"invoice_number": {"value": number, "locator": "page:1/region:number"},
                                                         "amount": {"value": amount, "locator": "page:1/region:total"}}}]}


class DualRootContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.originals = self.root / "originals"
        self.originals.mkdir()
        (self.originals / "fees.csv").write_text("项目,金额\n交通,12.00\n", encoding="utf-8")
        self.invoice = self.originals / "invoice-a.pdf"
        self.invoice.write_bytes(b"synthetic scan stand-in; no business values")

    def prepared(self, name="work"):
        manifest_path = prepare_dual_materials(self.originals, self.root / name)
        return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_valid_dual_root_passes(self):
        manifest_path, manifest = self.prepared()
        self.assertEqual(manifest["schema_version"], DUAL_MANIFEST_VERSION)
        self.assertEqual([item["role"] for item in manifest["derived_files"]], ["parsed_extraction"] * 2)
        self.assertEqual([item["sources"] for item in manifest["derived_files"]],
                         [[file_hash(self.originals / "fees.csv")], [file_hash(self.invoice)]])
        self.assertEqual(validate_dual_manifest(manifest), [])
        derived_id = register_derived(manifest_path, "reviewed/invoice-a.json", build_reviewed_extraction(self.invoice),
                                      role="reviewed_extraction", sources=[file_hash(self.invoice)], generated_by="test-agent")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(derived_id, "sha256:" + file_hash(self.root / "work/reviewed/invoice-a.json"))
        self.assertIn("reviewed/invoice-a.json", [item["relative_path"] for item in manifest["derived_files"]])
        self.assertEqual(validate_dual_manifest(manifest), [])

    def test_register_derived_rejects_bad_role_sources_and_duplicates(self):
        manifest_path, _ = self.prepared()
        payload = build_reviewed_extraction(self.invoice)
        source = file_hash(self.invoice)
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "reviewed/x.json", payload, role="invoice", sources=[source], generated_by="t")
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "reviewed/x.json", payload, role="run_evidence", sources=["0" * 64], generated_by="t")
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "reviewed/x.json", payload, role="run_evidence", sources=[], generated_by="t")
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "../escape.json", payload, role="run_evidence", sources=[source], generated_by="t")
        register_derived(manifest_path, "reviewed/a.json", payload, role="reviewed_extraction", sources=[source], generated_by="t")
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "reviewed/b.json", payload, role="reviewed_extraction", sources=[source], generated_by="t")
        self.assertFalse((self.root / "work/reviewed/b.json").exists())

    def test_out_of_root_paths_rejected(self):
        _, manifest = self.prepared()
        escaping = copy.deepcopy(manifest)
        escaping["derived_files"][0]["relative_path"] = "../escape.json"
        self.assertTrue(validate_dual_manifest(escaping))
        outside = copy.deepcopy(manifest)
        outside["derived_files"][0]["path"] = str(self.root / "fees-copy.json")
        self.assertTrue(validate_dual_manifest(outside))
        nested = self.root / "originals/work-nested"
        nested.mkdir()
        with self.assertRaises(ValueError):
            prepare_dual_materials(self.originals, nested)
        nested_manifest = copy.deepcopy(manifest)
        nested_manifest["derived_root"] = str(nested)
        self.assertTrue(validate_dual_manifest(nested_manifest))

    def test_original_and_derived_hash_drift_rejected(self):
        manifest_path, _ = self.prepared()
        (self.originals / "fees.csv").write_text("项目,金额\n交通,99.00\n", encoding="utf-8")
        drifted = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(validate_dual_manifest(drifted))
        with self.assertRaises(ValueError):
            register_derived(manifest_path, "reviewed/a.json", build_reviewed_extraction(self.invoice),
                             role="reviewed_extraction", sources=[file_hash(self.invoice)], generated_by="t")
        (self.originals / "fees.csv").write_text("项目,金额\n交通,12.00\n", encoding="utf-8")
        _, second = self.prepared("work2")
        Path(second["derived_files"][0]["path"]).write_text("tampered", encoding="utf-8")
        self.assertTrue(validate_dual_manifest(second))

    def test_v1_contract_still_readable(self):
        single = inventory_materials(self.originals)
        self.assertEqual(single["schema_version"], "1.0")
        self.assertEqual(validate_manifest(single), [])
        self.assertTrue(prepare_materials(self.originals, self.root / "v1out").is_file())
        self.assertTrue(validate_dual_manifest(single))
        extraction = self.originals / "ocr.json"
        extraction.write_text(json.dumps(build_reviewed_extraction(self.invoice)), encoding="utf-8")
        single = inventory_materials(self.originals)
        self.assertEqual(validate_manifest(single), [])
        hashes = {item["sha256"] for item in single["files"]}
        proof = {"kind": "material", "path": str(extraction),
                 "locator": "/records/0/fields/invoice_number/value", "sha256": file_hash(extraction)}
        self.assertEqual(validate_value_proof(proof, "00001234", material_hashes=hashes), [])
        legacy_default = dict(proof)
        legacy_default.pop("kind")
        self.assertEqual(validate_value_proof(legacy_default, "00001234", material_hashes=hashes), [])

    def test_agent_inference_cannot_pass_as_user(self):
        manifest_path, manifest = self.prepared()
        register_derived(manifest_path, "reviewed/invoice-a.json", build_reviewed_extraction(self.invoice),
                         role="reviewed_extraction", sources=[file_hash(self.invoice)], generated_by="test-agent")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_hashes, derived_hashes = dual_hash_sets(manifest)
        extraction_path = self.root / "work/reviewed/invoice-a.json"
        digest = file_hash(extraction_path)

        def proof(kind=None):
            entry = {"path": str(extraction_path), "locator": "/records/0/fields/invoice_number/value", "sha256": digest}
            if kind is not None:
                entry["kind"] = kind
            return entry

        context = {"original_hashes": original_hashes, "derived_hashes": derived_hashes}
        self.assertTrue(validate_value_proof(proof(), "00001234", **context))
        self.assertTrue(validate_value_proof(proof("user"), "00001234", **context))
        self.assertTrue(validate_value_proof(proof("material"), "00001234", **context))
        self.assertEqual(validate_value_proof(proof("agent_reviewed"), "00001234", **context), [])
        material_proof = {"kind": "material", "path": str(self.originals / "fees.csv"),
                          "locator": "row:2/column:2", "sha256": file_hash(self.originals / "fees.csv")}
        self.assertEqual(validate_value_proof(material_proof, "12.00", monetary=True, **context), [])


class DualInvoiceFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.originals = self.root / "originals"
        self.originals.mkdir()
        self.invoice = self.originals / "invoice-a.pdf"
        self.invoice.write_bytes(b"synthetic scan stand-in; no business values")
        self.plan = {"document_type": "travel",
                     "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
                     "tables": {"costs": [{"row_id": "c0", "fields": {"cost": "12.00"}}]}}

    def test_dual_invoice_flow_closes(self):
        manifest_path = prepare_dual_materials(self.originals, self.root / "work")
        register_derived(manifest_path, "reviewed/invoice-a.json", build_reviewed_extraction(self.invoice),
                         role="reviewed_extraction", sources=[file_hash(self.invoice)], generated_by="test-agent")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        extraction_path = self.root / "work/reviewed/invoice-a.json"
        materials = {"image_documents": [{"original_sha256": file_hash(self.invoice), "kind": "invoice",
                                          "extraction_path": str(extraction_path), "extraction_sha256": file_hash(extraction_path),
                                          "records": [{"record_id": "0001", "allocations": [{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "12.00"}]}]}]}
        self.assertEqual(validate_image_documents(materials, manifest, self.plan), [])
        unregistered = self.root / "work/reviewed/unregistered.json"
        unregistered.write_text(json.dumps(build_reviewed_extraction(self.invoice, number="00009999")), encoding="utf-8")
        stray = copy.deepcopy(materials)
        stray["image_documents"][0].update(extraction_path=str(unregistered), extraction_sha256=file_hash(unregistered))
        self.assertTrue(validate_image_documents(stray, manifest, self.plan))
        wrong_role_path = prepare_dual_materials(self.originals, self.root / "work-role")
        register_derived(wrong_role_path, "evidence/invoice-a.json", build_reviewed_extraction(self.invoice),
                         role="run_evidence", sources=[file_hash(self.invoice)], generated_by="test-agent")
        wrong_role_manifest = json.loads(wrong_role_path.read_text(encoding="utf-8"))
        evidence_path = self.root / "work-role/evidence/invoice-a.json"
        misroled = copy.deepcopy(materials)
        misroled["image_documents"][0].update(extraction_path=str(evidence_path), extraction_sha256=file_hash(evidence_path))
        self.assertTrue(validate_image_documents(misroled, wrong_role_manifest, self.plan))


if __name__ == "__main__":
    unittest.main()
