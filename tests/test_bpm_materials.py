import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from bpm.materials import (extract_structured, inventory_materials, prepare_materials,
                           read_locator, validate_manifest, validate_reviewed_extraction)
from bpm.plan import file_hash


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "originals"
        self.source.mkdir()

    def test_dedup_by_content(self):
        (self.source / "a.csv").write_text("编号,金额\n00123,12.00\n", encoding="utf-8")
        (self.source / "b.csv").write_bytes((self.source / "a.csv").read_bytes())
        manifest = inventory_materials(self.source)
        self.assertEqual(len(manifest["files"]), 1)
        self.assertEqual(manifest["files"][0]["duplicate_paths"], ["b.csv"])
        self.assertEqual(validate_manifest(manifest), [])
        manifest["files"].append(dict(manifest["files"][0]))
        self.assertTrue(validate_manifest(manifest))

    def test_csv_identifiers_preserved(self):
        path = self.source / "a.csv"
        path.write_text("编号,账号\n000123,001234567890123456\n", encoding="utf-8")
        self.assertEqual(read_locator(path, "row:2/column:1"), "000123")
        parsed = extract_structured(path)
        self.assertEqual(parsed["cells"][-1]["value"], "001234567890123456")

    def test_xlsx_strings_zero_masks_formulas(self):
        import openpyxl
        path = self.source / "a.xlsx"
        book = openpyxl.Workbook()
        sheet = book.active
        sheet["A1"] = "000123456789012345"
        sheet["B1"] = 123
        sheet["B1"].number_format = "000000"
        sheet["C1"] = "=1+1"
        sheet["D1"] = 12.30
        book.save(path)
        book.close()
        self.assertEqual(read_locator(path, "Sheet!A1"), "000123456789012345")
        self.assertEqual(read_locator(path, "Sheet!B1"), "000123")
        with self.assertRaises(ValueError):
            read_locator(path, "Sheet!C1")
        self.assertEqual(read_locator(path, "Sheet!D1", allow_numeric=True), "12.3")
        with self.assertRaises(ValueError):
            read_locator(path, "Sheet!D1")
        self.assertEqual(extract_structured(path)["status"], "NEEDS_REVIEW")

    def test_pdf_requires_reviewed_extraction(self):
        path = self.source / "invoice.pdf"
        path.write_bytes(b"synthetic pdf stand-in; no business values")
        self.assertEqual(extract_structured(path)["status"], "NEEDS_INPUT")
        data = {"schema_version": "1.0", "reviewed": True, "reviewed_by": "test-reviewer", "original_path": str(path), "original_sha256": file_hash(path), "records": [{"record_id": "001", "fields": {"invoice_number": {"value": "00001234", "locator": "page:1/region:top-right"}}}]}
        self.assertEqual(validate_reviewed_extraction(data), [])
        data["records"][0]["fields"]["invoice_number"]["value"] = 1234
        self.assertTrue(validate_reviewed_extraction(data))

    def test_separate_parsed_outputs(self):
        (self.source / "a.csv").write_text("value\n001\n", encoding="utf-8")
        manifest = prepare_materials(self.source, self.root / "output")
        self.assertTrue(manifest.is_file())
        self.assertEqual(len(list((self.root / "output/parsed").glob("*.json"))), 1)
        with self.assertRaises(ValueError):
            prepare_materials(self.source, self.source / "parsed")

    def test_protected_input_rejected(self):
        protected = self.source / ".pw-profile"
        protected.mkdir()
        (protected / "session_state.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            inventory_materials(self.source)

    def test_manifest_root_must_be_existing_nonprotected_directory(self):
        manifest = {"schema_version": "1.0", "root": str(self.source), "files": []}
        self.assertEqual(validate_manifest(manifest), [])
        file = self.source / "a.csv"
        file.write_text("value", encoding="utf-8")
        protected = self.root / ".pw-profile"
        protected.mkdir()
        for root in ("", str(self.root / "missing"), str(file), str(protected)):
            with self.subTest(root=root):
                invalid = copy.deepcopy(manifest)
                invalid["root"] = root
                self.assertTrue(validate_manifest(invalid))

    def test_manifest_primary_path_and_relative_must_match_root(self):
        first = self.source / "a.csv"
        first.write_text("value", encoding="utf-8")
        manifest = inventory_materials(self.source)
        outside = self.root / "outside.csv"
        outside.write_bytes(first.read_bytes())
        invalid = copy.deepcopy(manifest)
        invalid["files"][0]["path"] = str(outside)
        self.assertTrue(validate_manifest(invalid))
        second = self.source / "b.csv"
        second.write_bytes(first.read_bytes())
        invalid = copy.deepcopy(manifest)
        invalid["files"][0]["relative_path"] = "b.csv"
        self.assertTrue(validate_manifest(invalid))
        relative = copy.deepcopy(manifest)
        relative["root"] = "originals"
        relative["files"][0]["path"] = "originals/a.csv"
        self.assertEqual(validate_manifest(relative, base_dir=self.root), [])

    def test_manifest_duplicate_paths_cannot_escape_or_alias_primary(self):
        (self.source / "a.csv").write_text("value", encoding="utf-8")
        (self.source / "b.csv").write_text("value", encoding="utf-8")
        (self.root / "outside.csv").write_text("value", encoding="utf-8")
        manifest = inventory_materials(self.source)
        self.assertEqual(validate_manifest(manifest), [])
        for relative in ("../outside.csv", str(self.source / "b.csv"), "sub/../b.csv", "a.csv", "./b.csv", "sub//b.csv"):
            with self.subTest(relative=relative):
                invalid = copy.deepcopy(manifest)
                invalid["files"][0]["duplicate_paths"] = [relative]
                self.assertTrue(validate_manifest(invalid))

    def test_manifest_symbolic_link_cannot_escape_material_root(self):
        outside = self.root / "outside.csv"
        outside.write_text("value", encoding="utf-8")
        link = self.source / "escape.csv"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            if os.name != "nt":
                self.skipTest("file symlink unavailable: " + str(exc))
            # NTFS junctions exercise real reparse-point containment without the
            # administrator privilege required for Windows file symlinks.
            outside_dir = self.root / "outside-directory"
            outside_dir.mkdir()
            outside = outside_dir / "outside.csv"
            outside.write_text("value", encoding="utf-8")
            junction = self.source / "escape-directory"
            if junction.parent.resolve() != self.source.resolve() or outside_dir.parent.resolve() != self.root.resolve():
                self.fail("test junction paths escaped temporary workspace")
            result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside_dir)], capture_output=True)
            if result.returncode:
                self.skipTest("NTFS junction unavailable")
            link = junction / "outside.csv"
        relative = link.relative_to(self.source).as_posix()
        manifest = {"schema_version": "1.0", "root": str(self.source), "files": [{"material_id": "sha256:" + file_hash(outside), "path": str(link), "relative_path": relative, "sha256": file_hash(outside), "size_bytes": outside.stat().st_size, "duplicate_paths": []}]}
        self.assertTrue(validate_manifest(manifest))
        regular = self.source / "regular.csv"
        regular.write_bytes(outside.read_bytes())
        duplicate_manifest = copy.deepcopy(manifest)
        duplicate_manifest["files"][0].update(path=str(regular), relative_path="regular.csv", duplicate_paths=[relative])
        self.assertTrue(validate_manifest(duplicate_manifest))
        try:
            inventory = inventory_materials(self.source)
        except ValueError:
            pass
        else:
            self.assertTrue(all(Path(item["path"]).resolve().is_relative_to(self.source.resolve()) for item in inventory["files"]))


if __name__ == "__main__":
    unittest.main()
