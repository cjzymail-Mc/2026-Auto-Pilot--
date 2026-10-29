"""Synthetic fixed-layout workbook contract; production Excel smoke is separate."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
import xml.etree.ElementTree as ET

import openpyxl
import test_bpm_self_drive_plan as scenario_fixture
import test_bpm_plan as plan_fixture
from bpm.plan import file_hash
from bpm.self_drive_workbook import prepare_workbook_copy


def workbook_fixture(root):
    plan, _, packet = scenario_fixture.fixture(root)
    source = root / "originals/mileage.xlsx"
    book = openpyxl.Workbook()
    ws = book.active
    ws.title = "汇总"
    ws.merge_cells("A1:D1")
    ws["A1"] = "合成工作簿；不是业务材料"
    for coordinate, value in {"F3": "公里数", "G3": "补贴金额", "H3": "过路费", "I3": "合计", "F4": 100, "G4": 100, "B4": "不得改写", "I5": "=SUM(I4:I4)"}.items():
        ws[coordinate] = value
    book.save(source)
    book.close()
    packet["rows"][0]["km"] = {"path": str(source), "locator": "汇总!F4", "sha256": file_hash(source)}
    scenario_fixture.dump(root / "originals/scenario_inputs.json", packet)
    plan_fixture.refresh_manifest(root, plan)
    return plan, packet, source


def fixture_engine(path, sheet, assignments, *, wrong_cache=False, outside_change=False, no_cache=False):
    """Test-only cached XML fixture, explicitly reported as a simulated engine."""
    book = openpyxl.load_workbook(path)
    ws = book[sheet]
    totals = {}
    for row, amount in assignments.items():
        ws[f"H{row}"] = float(amount)
        ws[f"I{row}"] = f"=G{row}+H{row}"
        totals[f"I{row}"] = float(ws[f"G{row}"].value) + float(amount)
    totals[f"I{max(assignments)+1}"] = sum(totals.values())
    if outside_change:
        ws["B4"] = "unexpected change"
    book.save(path)
    book.close()
    if not no_cache:
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        temp = path.with_name("fixture-engine.xlsx")
        with zipfile.ZipFile(path) as old, zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as new:
            for info in old.infolist():
                data = old.read(info.filename)
                if info.filename == "xl/worksheets/sheet1.xml":
                    tree = ET.fromstring(data)
                    for cell in tree.iter(ns + "c"):
                        if cell.attrib.get("r") in totals:
                            v = cell.find(ns + "v")
                            if v is None:
                                v = ET.SubElement(cell, ns + "v")
                            v.text = str(totals[cell.attrib["r"]] + (1 if wrong_cache else 0))
                    data = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
                new.writestr(info, data)
        os.replace(temp, path)
    return "synthetic_formula_fixture"


class SelfDriveWorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "case"
        self.plan, self.packet, self.source = workbook_fixture(self.root)

    def run_copy(self, **overrides):
        kwargs = dict(inputs_path=self.root / "originals/scenario_inputs.json", manifest_path=self.root / "manifest.json",
                      workbook_path=self.source, row_map={"row1": 4}, output_dir=self.base / "result")
        kwargs.update(overrides)
        return prepare_workbook_copy(**kwargs)

    def rebind_workbook(self):
        self.packet["rows"][0]["km"]["sha256"] = file_hash(self.source)
        scenario_fixture.dump(self.root / "originals/scenario_inputs.json", self.packet)
        plan_fixture.refresh_manifest(self.root, self.plan)

    @mock.patch("bpm.self_drive_workbook._recalculate_with_excel", side_effect=fixture_engine)
    def test_copy_only_reopen_caches_transport_and_meal_separate(self, engine):
        before = file_hash(self.source)
        result = self.run_copy()
        self.assertEqual(result["status"], "WORKBOOK_VERIFIED_OFFLINE")
        self.assertEqual(result["engine"], "synthetic_formula_fixture")
        self.assertEqual((result["transport_total"], result["meal_separate"], result["reimbursement_total"]), ("120.00", "30.00", "150.00"))
        self.assertEqual(file_hash(self.source), before)
        self.assertTrue(result["persisted_cache_verified"])
        self.assertFalse(result["real_fill_verified"])
        self.assertTrue((self.base / "result/workbook_result.json").is_file())

    def test_missing_or_incorrect_persisted_cache_is_not_a_pass(self):
        for mode in ["no_cache", "wrong_cache"]:
            with self.subTest(mode=mode), mock.patch("bpm.self_drive_workbook._recalculate_with_excel", side_effect=lambda p, s, a: fixture_engine(p, s, a, **{mode: True})):
                result = self.run_copy(output_dir=self.base / mode)
                self.assertEqual(result["status"], "NEEDS_INPUT")
                self.assertFalse(result["persisted_cache_verified"])

    @mock.patch("bpm.self_drive_workbook._recalculate_with_excel", side_effect=lambda p, s, a: fixture_engine(p, s, a, outside_change=True))
    def test_unauthorized_cell_change_is_detected(self, engine):
        self.assertEqual(self.run_copy()["status"], "NEEDS_INPUT")

    def test_row_mapping_and_original_cell_provenance(self):
        for mapping in [{}, {"row1": 5}, {"row1": 4, "unrelated": 6}, {"row1": True}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                self.run_copy(row_map=mapping)
        self.assertFalse((self.base / "result").exists())

    def test_conflicting_subsidy_toll_or_unknown_formula_never_overwritten(self):
        for cell, value in [("G4", 99), ("H4", 1), ("I4", "=F4*2")]:
            book = openpyxl.load_workbook(self.source)
            book["汇总"][cell] = value
            book.save(self.source)
            book.close()
            self.rebind_workbook()
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                self.run_copy()
            # Restore only the synthetic fixture; source production files never enter tests.
            book = openpyxl.load_workbook(self.source)
            book["汇总"][cell] = 100 if cell == "G4" else None
            book.save(self.source)
            book.close()
            self.rebind_workbook()

    def test_external_formulas_are_not_recalculated(self):
        book = openpyxl.load_workbook(self.source)
        book["汇总"]["K4"] = '=WEBSERVICE("https://invalid.example")'
        book.save(self.source)
        book.close()
        self.rebind_workbook()
        with self.assertRaisesRegex(ValueError, "external"):
            self.run_copy()

    def test_existing_or_nested_output_is_rejected(self):
        for output in [self.root, self.root / "originals/derived", self.root / "originals"]:
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.run_copy(output_dir=output)

    def test_missing_engine_or_engine_failure_reports_gap_with_copy_preserved(self):
        with mock.patch("bpm.self_drive_workbook._recalculate_with_excel", side_effect=ImportError("engine unavailable")):
            result = self.run_copy()
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertTrue((self.base / "result/mileage-verified.xlsx").is_file())
        self.assertFalse(result["persisted_cache_verified"])

    def test_source_drift_during_calculation_is_detected(self):
        def engine(path, sheet, assignments):
            marker = fixture_engine(path, sheet, assignments)
            self.source.write_bytes(b"synthetic drift")
            return marker
        with mock.patch("bpm.self_drive_workbook._recalculate_with_excel", side_effect=engine):
            result = self.run_copy()
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertIn("drift", result["message"])


if __name__ == "__main__":
    unittest.main()
