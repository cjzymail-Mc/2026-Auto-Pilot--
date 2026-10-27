"""Type admission/binding tests; synthetic evidence only, no production profile."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bpm.plan import ROOT, file_hash, validate_plan, load_type
from bpm.save import SaveController, SaveError, config_hash
from bpm.template import normalize_template, CHILDREN
from bpm.types import resolve_type, type_from_category, check_template_type, TypeConfigError
import bpm.fill_cli as fill_once
from test_bpm_plan import build_valid_plan


class TypeTests(unittest.TestCase):
    def test_closed_registry_and_observed_category_mapping(self):
        for kind, label, code in (("travel", "差旅费", "08"), ("express", "快递费", "15"),
                                  ("rd_materials", "研发材料费", "11")):
            self.assertEqual(type_from_category(label), kind)
            self.assertEqual(type_from_category(code), kind)
            self.assertEqual(resolve_type(kind, require_executable=False).document_type, kind)
        for bad in ("../travel", "travel.json", "unknown_type", "", None, [], "快递费 "):
            with self.subTest(bad=bad), self.assertRaises(TypeConfigError):
                resolve_type(bad)
        for category in (None, 15, "015", "快递", "研发材料费 "):
            with self.subTest(category=category), self.assertRaises(TypeConfigError):
                type_from_category(category)

    def test_travel_hash_preserves_existing_run_and_journal_bindings(self):
        expected = file_hash(ROOT / "automation/document-types/travel.json")
        self.assertEqual(resolve_type("travel").sha256, expected)
        self.assertEqual(config_hash("travel"), expected)

    def test_self_contained_type_binding_does_not_depend_on_travel_configuration(self):
        original = Path.read_bytes
        def changed_projection(path):
            raw = original(path)
            if path.name == "travel.json":
                return raw + b"\n"
            return raw
        before = {kind: resolve_type(kind, require_executable=False).sha256
                  for kind in ("express", "rd_materials")}
        with mock.patch.object(Path, "read_bytes", changed_projection):
            for kind, digest in before.items():
                self.assertEqual(resolve_type(kind).sha256, digest)

    def test_unmodeled_new_type_plans_cannot_launch_or_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan, path = build_valid_plan(Path(tmp))
            for kind in ("express", "rd_materials"):
                with self.subTest(kind=kind):
                    plan["document_type"] = kind
                    plan["header"]["submitType"] = "快递费" if kind == "express" else "研发材料费"
                    self.assertTrue(validate_plan(plan))
                    path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
                    with mock.patch("bpm.fill_cli.subprocess.run") as launch:
                        self.assertEqual(fill_once.main(["--fill-plan", str(path), "--expect-name", plan["operator"]]), 2)
                        launch.assert_not_called()
                    controller = SaveController(plan, object(), Path(tmp) / kind / "attempt")
                    self.assertEqual(controller.run()["status"], "NEEDS_INPUT")

    def test_prepare_both_types_reports_specific_gaps_without_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            originals = root / "originals"
            originals.mkdir()
            (originals / "facts.csv").write_text("number,amount\n000001,12.00\n", encoding="utf-8")
            for kind in ("express", "rd_materials"):
                task = {"schema_version": "1.0", "task_id": "synthetic-" + kind,
                        "document_type": kind, "operator": "测试操作人", "template_biz_number": "000123456",
                        "materials_dir": str(originals), "statement": "仅离线合成材料准备",
                        "authorization": {"mode": "fill_only", "task_id": "synthetic-" + kind,
                                          "statement": "离线准备不填写不保存", "allow_submit": False}}
                task_path = root / (kind + ".json")
                task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
                self.assertEqual(fill_once.validate_task(task, root), [])
                with mock.patch.object(fill_once, "RUNS", root / "runs"), mock.patch.object(fill_once, "ROOT", root), \
                     mock.patch("bpm.fill_cli.subprocess.run") as launch:
                    result = fill_once.prepare_task(task_path, task["operator"])
                    launch.assert_not_called()
                self.assertEqual(result["status"], "NEEDS_INPUT")
                self.assertFalse(result["browser_launched"])
                self.assertEqual(result["document_type"], kind)
                self.assertTrue(any(i["path"] == "/document_type" for i in result["gaps"]))
                self.assertEqual(result["config_sha256"], resolve_type(kind, require_executable=False).sha256)

    def test_template_category_mismatch_and_missing_identity_are_rejected(self):
        for kind in ("travel", "express", "rd_materials"):
            others = set(("travel", "express", "rd_materials")) - {kind}
            for other in others:
                with self.assertRaises(TypeConfigError):
                    check_template_type({"document_type": other}, kind)
            if kind != "travel":
                with self.assertRaises(TypeConfigError):
                    check_template_type({}, kind)
        with tempfile.TemporaryDirectory() as tmp:
            plan, _ = build_valid_plan(Path(tmp))
            snapshot_path = Path(plan["template"]["snapshot_path"])
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["header"] = {"submitType": "15"}
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            plan["template"]["sha256"] = file_hash(snapshot_path)
            self.assertTrue(any(i["path"] == "/template" for i in validate_plan(plan)))

    def test_pending_research_projection_declares_unmodeled_business_fields(self):
        uid, number = "a" * 32, "000123456"
        for category, kind in (("15", "express"), ("11", "rd_materials")):
            main = {"id": uid, "bizNumber": number, "submitType": category}
            kids = {key: [] for key in CHILDREN}
            kids["products"] = [{"reimburseId": uid, "materialSpecification": "SYNTHETIC",
                                 "name": "测试材料", "price": "12.00", "access_token": "NEVER_EXPORT"}]
            snapshot = normalize_template(number, main, kids, {"kind": "synthetic"})
            self.assertEqual(snapshot["document_type"], kind)
            self.assertTrue(snapshot["model_observation"]["execution_enabled"])
            self.assertIn("materialSpecification", snapshot["model_observation"]["unmodeled_child_fields"][0]["unmodeled_fields"])
            self.assertNotIn("NEVER_EXPORT", json.dumps(snapshot))
            self.assertEqual(snapshot["tables"]["products"][0]["fields"]["price"], "12.00")
        with self.assertRaises(TypeConfigError):
            normalize_template(number, {"id": uid, "bizNumber": number}, {k: [] for k in CHILDREN}, {})

    def test_configuration_cannot_switch_type_or_enable_pending_execution(self):
        identity = resolve_type("express", require_executable=False)
        for key, value in (("document_type", "travel"), ("category", {"label": "差旅费", "api_code": "08"}),
                           ("execution_state", "ready")):
            data = copy.deepcopy(identity.config)
            data[key] = value
            with mock.patch("bpm.types.Path.read_bytes", return_value=json.dumps(data).encode()):
                with self.assertRaises(TypeConfigError):
                    resolve_type("express", require_executable=False)


if __name__ == "__main__":
    unittest.main()
