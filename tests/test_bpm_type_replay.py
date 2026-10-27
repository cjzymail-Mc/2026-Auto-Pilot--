"""Explicit test authorization and replay lineage; no live browser access."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from automation import prepare_type_replay_test as replay
from bpm.plan import file_hash, validate_plan, load_type
from test_bpm_new_types import build_type_plan


class ReplayTests(unittest.TestCase):
    def test_authorized_replay_retains_lineage_and_default_people_without_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = []
            auth = {key: True for key in ("allow_history_replay", "allow_new_unsaved_test_pages", "allow_fill")}
            auth.update(allow_save=False, allow_submit=False, operator="测试操作人", user_statement="授权历史数据未保存测试", selected_templates={})
            for kind in ("express", "rd_materials"):
                plan, path = build_type_plan(root / kind, kind)
                snapshot = Path(plan["template"]["snapshot_path"])
                view = root / (kind + "-view.json")
                data = {"header_fields": [{"name": key + "0", "value": value} for key, value in plan["header"].items()],
                        "tables": [{"title": load_type(kind)["tables"][key]["title"], "rows": copy.deepcopy(rows)} for key, rows in plan["tables"].items()]}
                view.write_text(json.dumps(data), encoding="utf-8")
                records.append({"number": plan["template"]["biz_number"], "document_type": kind,
                    "snapshot_path": str(snapshot), "snapshot_sha256": file_hash(snapshot),
                    "view_path": str(view), "view_sha256": file_hash(view)})
                auth["selected_templates"][kind] = plan["template"]["biz_number"]
            defaults = root / "defaults.json"
            defaults.write_text(json.dumps({"operator": auth["operator"], "fields_written": 0,
                "applicant": {"name": "当前默认申请人", "company": "当前默认公司", "department": "当前默认部门"},
                "header": {"budgetYears": "2026"}}), encoding="utf-8")
            authorization = root / "authorization.json"
            authorization.write_text(json.dumps(auth), encoding="utf-8")
            study = root / "study.json"
            study.write_text(json.dumps({"records": records}), encoding="utf-8")
            with mock.patch.object(replay, "ROOT", root):
                for kind in ("express", "rd_materials"):
                    path = replay.build_replay(kind, kind + "-R1", study, defaults, authorization)
                    plan = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(validate_plan(plan), [])
                    self.assertEqual(plan["authorization"]["mode"], "fill_only")
                    self.assertEqual(plan["applicant"]["name"], "当前默认申请人")
                    self.assertNotIn("identity", plan)
                    proof = json.loads(Path(next(iter(plan["sources"].values()))["path"]).read_text(encoding="utf-8"))
                    self.assertTrue(proof["test_only"])
                    self.assertTrue(proof["not_new_expenses"])
                    self.assertEqual(proof["replay_lineage"]["authorization_sha256"], file_hash(authorization))

    def test_save_permission_or_missing_replay_authorization_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "auth.json"
            for auth in ({}, {"allow_history_replay": True, "allow_new_unsaved_test_pages": True,
                              "allow_fill": True, "allow_save": True, "allow_submit": False}):
                path.write_text(json.dumps(auth), encoding="utf-8")
                with self.assertRaises(ValueError):
                    replay.read_authorization(path)
