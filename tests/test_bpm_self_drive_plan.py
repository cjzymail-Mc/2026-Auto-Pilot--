"""Synthetic scenarios: provenance drift, same-row matching and plan wiring."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_bpm_plan as plan_fixture
from bpm.materials import inventory_materials
from bpm.plan import file_hash, load_plan, validate_plan
from bpm.self_drive import load_self_drive_rules
from bpm.self_drive_plan import assess_self_drive, validate_self_drive_binding


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def fixture(root):
    plan, path = plan_fixture.build_valid_plan(root, cost_count=3, total=150)
    plan["identity"] = {"creator_name": plan["applicant"]["name"], "creator_department": "测试部门", "applicant_employee_id": "00123"}
    plan["tables"]["relations"] = [{"row_id": "relation", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000001", "nowCost": "150.00", "isLast": "是"}}]
    for row, amount in zip(plan["tables"]["costs"], ["100.00", "20.00", "30.00"]):
        row["fields"]["cost"] = amount
    source = root / "originals/scenario_facts.json"
    data = {"synthetic": True, "creator": {"name": plan["applicant"]["name"], "employee_id": "00123", "department": "测试部门"},
            "scope_dates": ["2026-10-23"], "rows": [{"date": "2026-10-23", "km": "100.00", "route": "合成路线"}],
            "trips": [{"biz_number": "12026000001", "date": "2026-10-23", "route": "合成路线", "participants": [{"name": plan["applicant"]["name"], "employee_id": "00123"}]}],
            "fuel_reason": "合成油票仅覆盖，不作费用分配"}
    dump(source, data)
    def proof(p, locator):
        return {"path": str(p), "locator": locator, "sha256": file_hash(p)}
    invoices, docs = [], []
    for iid, kind, amount, number in [("t1", "toll", "20.00", "000001"), ("f1", "fuel", "200.00", "000002")]:
        pdf = root / ("originals/" + iid + ".pdf")
        pdf.write_bytes(("synthetic invoice " + iid).encode())
        ep = root / ("originals/" + iid + ".json")
        fields = {key: {"value": value, "locator": "page:1/region:" + key} for key, value in
                  {"invoice_number": number, "amount": amount, "kind": kind, "date": "2026-10-23"}.items()}
        dump(ep, {"schema_version": "1.0", "reviewed": True, "reviewed_by": "synthetic-reviewer", "original_path": str(pdf), "original_sha256": file_hash(pdf), "records": [{"record_id": "r0", "fields": fields}]})
        record = {"record_id": "r0"}
        if kind == "toll":
            record["allocations"] = [{"plan_pointer": "/tables/costs/1/fields/cost", "amount": amount}]
        else:
            record["not_applicable"] = {"reason": data["fuel_reason"], "proof": dict(proof(source, "/fuel_reason"), kind="material")}
        docs.append({"original_sha256": file_hash(pdf), "kind": "invoice", "extraction_path": str(ep), "extraction_sha256": file_hash(ep), "records": [record]})
        invoices.append(dict({"invoice_id": iid}, **{key: proof(ep, "/records/0/fields/" + field + "/value") for key, field in [("kind", "kind"), ("number", "invoice_number"), ("amount", "amount"), ("date", "date")]}))
    packet = {"schema_version": "1.0", "creator": proof(source, "/creator"), "scope_dates": proof(source, "/scope_dates"),
              "rows": [dict({"row_id": "row1", "toll_ids": ["t1"]}, **{k: proof(source, "/rows/0/" + k) for k in ["date", "km", "route"]})],
              "invoices": invoices, "trips": [proof(source, "/trips/0")], "meal_assignments": [{"date": "2026-10-23", "trip_number": "12026000001"}]}
    packet_path = root / "originals/scenario_inputs.json"
    dump(packet_path, packet)
    # Keep all ordinary scalar provenance and invoice checks active.
    original = root / "originals/reviewed_facts.json"
    facts = json.loads(original.read_text(encoding="utf-8"))
    facts.update(identity=copy.deepcopy(plan["identity"]), tables=copy.deepcopy(plan["tables"]))
    dump(original, facts)
    pointers = ["/applicant/" + k for k in plan["applicant"]] + ["/header/" + k for k in plan["header"]] + ["/identity/" + k for k in plan["identity"]]
    for table, rows in plan["tables"].items():
        for i, row in enumerate(rows):
            pointers.extend(f"/tables/{table}/{i}/fields/{k}" for k in row["fields"])
    plan["sources"] = {p: dict(proof(original, p), kind="material") for p in pointers}
    plan["materials"]["image_documents"] = docs
    plan["materials"]["no_invoice_rows"] = [{"plan_pointer": f"/tables/costs/{i}/fields/cost", "reason": facts["no_invoice_rule"], "proof": dict(proof(original, "/no_invoice_rule"), kind="material")} for i in [0, 2]]
    rules = load_self_drive_rules()
    plan["self_drive_coverage"] = {"schema_version": "1.0", "rules_version": rules.version, "rules_sha256": rules.config_sha256,
                                   "inputs": {"path": str(packet_path), "sha256": file_hash(packet_path)},
                                   "cost_bindings": {"km:row1": "/tables/costs/0/fields/cost", "toll:row1": "/tables/costs/1/fields/cost", "meal:2026-10-23": "/tables/costs/2/fields/cost"}}
    plan_fixture.refresh_manifest(root, plan)
    dump(path, plan)
    return plan, path, packet


class SelfDrivePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, self.path, self.packet = fixture(self.root)

    def manifest(self):
        return json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def assess(self, packet=None):
        return assess_self_drive(packet or self.packet, self.manifest(), base_dir=self.root)

    def scenario_issues(self):
        return [i for i in validate_plan(self.plan, base_dir=self.root) if i["path"] == "/self_drive_coverage"]

    def test_real_validator_positive_and_independent_components(self):
        self.assertEqual(validate_plan(self.plan, base_dir=self.root), [])
        self.assertEqual(load_plan(self.path), self.plan)
        result = self.assess()
        self.assertEqual(result["calculation"]["R_reimburse"], "150.00")
        self.assertEqual(result["relation_totals"], {"12026000001": "150.00"})
        self.assertFalse(result["real_save_verified"])

    def test_source_drift_before_any_execution(self):
        (self.root / "originals/scenario_facts.json").write_text("{}", encoding="utf-8")
        self.assertTrue(self.scenario_issues())

    def test_forged_packet_reference_outside_manifest(self):
        q = self.root / "unregistered.json"
        dump(q, self.packet)
        self.plan["self_drive_coverage"]["inputs"] = {"path": str(q), "sha256": file_hash(q)}
        self.assertTrue(self.scenario_issues())

    def test_malformed_and_unknown_binding_fail_closed(self):
        for value in [None, [], {}, dict(self.plan["self_drive_coverage"], unknown=True)]:
            with self.subTest(value=value):
                plan = copy.deepcopy(self.plan)
                plan["self_drive_coverage"] = value
                self.assertTrue(validate_plan(plan, base_dir=self.root))

    def test_compensating_cost_changes_rejected_even_when_total_closes(self):
        self.plan["tables"]["costs"][0]["fields"]["cost"] = "99.00"
        self.plan["tables"]["costs"][2]["fields"]["cost"] = "31.00"
        self.assertTrue(self.scenario_issues())

    def test_creator_identity_and_same_name_employee_id(self):
        self.plan["identity"]["applicant_employee_id"] = "00999"
        self.assertTrue(self.scenario_issues())
        packet = copy.deepcopy(self.packet)
        packet["creator"]["locator"] = "/trips/0/participants/0"
        with self.assertRaises(ValueError):
            self.assess(packet)

    def test_same_row_participation_prevents_cross_row_join(self):
        data_path = self.root / "originals/scenario_facts.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        data["trips"][0]["participants"][0]["employee_id"] = "00999"
        data["trips"].append(dict(data["trips"][0], date="2026-10-24", participants=[{"name": "测试申请人", "employee_id": "00123"}]))
        dump(data_path, data)
        packet = copy.deepcopy(self.packet)
        for proof in [packet["creator"], packet["scope_dates"], *[packet["rows"][0][k] for k in ["date", "km", "route"]], packet["trips"][0]]:
            proof["sha256"] = file_hash(data_path)
        packet["trips"].append(dict(packet["trips"][0], locator="/trips/1"))
        plan_fixture.refresh_manifest(self.root, self.plan)
        with self.assertRaisesRegex(ValueError, "participation"):
            self.assess(packet)

    def test_meal_days_missing_duplicate_out_of_scope(self):
        for assignments in [[], self.packet["meal_assignments"] * 2, [{"date": "2026-10-24", "trip_number": "12026000001"}]]:
            packet = copy.deepcopy(self.packet)
            packet["meal_assignments"] = assignments
            with self.subTest(assignments=assignments), self.assertRaises(ValueError):
                self.assess(packet)

    def test_toll_duplicate_fuel_assignment_and_missing_allocation(self):
        for ids in [["t1", "t1"], ["f1"], []]:
            packet = copy.deepcopy(self.packet)
            packet["rows"][0]["toll_ids"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.assess(packet)

    def test_strict_coverage_equal_or_shortage_is_blocked_from_sources(self):
        p = self.root / "originals/f1.json"
        for amount in ["130.00", "129.99"]:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["records"][0]["fields"]["amount"]["value"] = amount
            dump(p, data)
            packet = copy.deepcopy(self.packet)
            for key in ["kind", "number", "amount", "date"]:
                packet["invoices"][1][key]["sha256"] = file_hash(p)
            plan_fixture.refresh_manifest(self.root, self.plan)
            with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, "F > R"):
                self.assess(packet)

    def test_same_day_multiple_trips_count_meal_once_and_ambiguity_blocks(self):
        p = self.root / "originals/scenario_facts.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["trips"].append(dict(data["trips"][0], biz_number="12026000002", route="另一合成路线"))
        dump(p, data)
        packet = copy.deepcopy(self.packet)
        for proof in [packet["creator"], packet["scope_dates"], *[packet["rows"][0][k] for k in ["date", "km", "route"]], packet["trips"][0]]:
            proof["sha256"] = file_hash(p)
        packet["trips"].append(dict(packet["trips"][0], locator="/trips/1"))
        plan_fixture.refresh_manifest(self.root, self.plan)
        self.assertEqual(self.assess(packet)["calculation"]["C_meal"], "30.00")
        data["trips"][1]["route"] = "合成路线"
        dump(p, data)
        for proof in [packet["creator"], packet["scope_dates"], *[packet["rows"][0][k] for k in ["date", "km", "route"]], *packet["trips"]]:
            proof["sha256"] = file_hash(p)
        plan_fixture.refresh_manifest(self.root, self.plan)
        with self.assertRaisesRegex(ValueError, "one exact"):
            self.assess(packet)

    def test_rules_binding_and_legacy_model_separation(self):
        self.plan["self_drive_coverage"]["rules_sha256"] = "0" * 64
        self.assertTrue(self.scenario_issues())
        self.plan["self_drive_coverage"]["rules_sha256"] = load_self_drive_rules().config_sha256
        self.plan["coverage"] = {}
        self.assertTrue(self.scenario_issues())

    def test_no_mixed_component_no_invoice_bypass(self):
        self.plan["self_drive_coverage"]["cost_bindings"]["toll:row1"] = "/tables/costs/0/fields/cost"
        self.assertTrue(self.scenario_issues())

    def test_fuel_never_allocated_and_toll_must_use_reviewed_record(self):
        self.plan["materials"]["image_documents"][1]["records"][0] = {"record_id": "r0", "allocations": [{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "200.00"}]}
        self.assertTrue(self.scenario_issues())

    def test_actual_relation_amount_and_synthetic_save_rejected(self):
        self.plan["tables"]["relations"][0]["fields"]["nowCost"] = "149.00"
        self.assertTrue(self.scenario_issues())
        self.plan["tables"]["relations"][0]["fields"]["nowCost"] = "150.00"
        self.plan["authorization"]["mode"] = "save_draft"
        self.assertTrue(self.scenario_issues())

    def test_per_trip_compensating_differences_do_not_pass(self):
        p = self.root / "originals/scenario_facts.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["rows"][0]["km"] = "50.00"
        data["rows"].append(dict(data["rows"][0], route="另一路线"))
        data["trips"].append(dict(data["trips"][0], biz_number="12026000002", route="另一路线"))
        dump(p, data)
        packet = copy.deepcopy(self.packet)
        for proof in [packet["creator"], packet["scope_dates"], *[packet["rows"][0][k] for k in ["date", "km", "route"]], packet["trips"][0]]:
            proof["sha256"] = file_hash(p)
        packet["rows"].append({"row_id": "row2", "toll_ids": [], **{k: dict(packet["rows"][0][k], locator="/rows/1/" + k) for k in ["date", "km", "route"]}})
        packet["trips"].append(dict(packet["trips"][0], locator="/trips/1"))
        pp = self.root / "originals/scenario_inputs.json"
        dump(pp, packet)
        self.plan["self_drive_coverage"]["inputs"]["sha256"] = file_hash(pp)
        self.plan["tables"]["costs"][0]["fields"]["cost"] = "50.00"
        extra = copy.deepcopy(self.plan["tables"]["costs"][0])
        extra["row_id"] = "c3"
        self.plan["tables"]["costs"].append(extra)
        self.plan["self_drive_coverage"]["cost_bindings"]["km:row2"] = "/tables/costs/3/fields/cost"
        self.plan["tables"]["relations"][0]["fields"]["nowCost"] = "100.00"
        self.plan["tables"]["relations"].append({"row_id": "relation2", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000002", "nowCost": "50.00", "isLast": "是"}})
        plan_fixture.refresh_manifest(self.root, self.plan)
        self.assertEqual(validate_self_drive_binding(self.plan, base_dir=self.root, manifest=self.manifest()), [])
        self.plan["tables"]["relations"][0]["fields"]["nowCost"] = "104.00"
        self.plan["tables"]["relations"][1]["fields"]["nowCost"] = "46.00"
        self.assertTrue(validate_self_drive_binding(self.plan, base_dir=self.root, manifest=self.manifest()))

    def test_protected_source_and_skipped_source_verification_fail_closed(self):
        packet = copy.deepcopy(self.packet)
        packet["creator"]["path"] = str(self.root / ".local-session/session_record.json")
        with self.assertRaises(ValueError):
            self.assess(packet)
        self.assertTrue(validate_plan(self.plan, verify_sources=False, base_dir=self.root))

    def test_generator_preserves_and_validates_scenario(self):
        from bpm.facts import FactSet
        from bpm.plan_generate import generate_fill_plan, PlanGenerationError
        fs = FactSet()
        blueprint = {k: copy.deepcopy(self.plan[k]) for k in ["document_type", "task_id", "operator", "template", "authorization", "amount_rules", "self_drive_coverage"]}
        blueprint["materials"] = {"manifest_path": str(self.root / "manifest.json")}
        for section in ["applicant", "header", "identity"]:
            blueprint[section] = {}
            for k, value in self.plan[section].items():
                if k == "totalCost":
                    continue
                pointer = "/" + section + "/" + k
                proof = self.plan["sources"][pointer]
                fid = fs.add("scope", source="material_extraction", value={"value": value}, locator=proof["path"] + "#" + pointer, input_hashes={"source": proof["sha256"]})
                blueprint[section][k] = {"value": value, "fact_id": fid}
        blueprint["tables"] = {}
        cost_ids = []
        for table, rows in self.plan["tables"].items():
            blueprint["tables"][table] = []
            for i, row in enumerate(rows):
                fields = {}
                for k, value in row["fields"].items():
                    pointer = f"/tables/{table}/{i}/fields/{k}"
                    proof = self.plan["sources"][pointer]
                    opts = {"source": "material_extraction", "locator": proof["path"] + "#" + pointer, "input_hashes": {"source": proof["sha256"]}}
                    if table == "costs" and k == "cost":
                        fid = fs.add_expense(value, **opts)
                        cost_ids.append(fid)
                    else:
                        fid = fs.add("scope", value={"amount": value}, **opts)
                    fields[k] = {"value": value, "fact_id": fid}
                blueprint["tables"][table].append({"row_id": row["row_id"], "fields": fields})
        total = fs.add("total", source="deterministic_computation", value={"amount": "150.00"}, derivation="sum costs", locator="calculation#total")
        blueprint["total"] = {"value": "150.00", "fact_id": total}
        toll = self.plan["materials"]["image_documents"][0]
        invoice, _ = fs.add_invoice("000001", "20.00", locator=toll["extraction_path"] + "#/records/0/fields/amount/value", input_hashes={"source": toll["extraction_sha256"], "original": toll["original_sha256"]})
        fs.add_allocation(invoice, cost_ids[1], "20.00", locator="assignment#t1")
        for index in [0, 2]:
            proof = self.plan["materials"]["no_invoice_rows"][0]["proof"]
            fs.add("no_invoice_basis", source="material_extraction", value={"expense_ref": cost_ids[index], "reason": self.plan["materials"]["no_invoice_rows"][0]["reason"]}, locator=proof["path"] + "#" + proof["locator"], input_hashes={"source": proof["sha256"]})
        blueprint["invoice_extractions"] = [{"invoice_fact_id": invoice, "extraction_path": toll["extraction_path"]}]
        blueprint["self_drive_image_documents"] = [copy.deepcopy(self.plan["materials"]["image_documents"][1])]
        result = generate_fill_plan(fs, blueprint, base_dir=self.root)
        self.assertEqual(result["plan"]["self_drive_coverage"], self.plan["self_drive_coverage"])
        self.assertEqual(validate_plan(result["plan"], base_dir=self.root), [])
        blueprint["self_drive_coverage"]["rules_sha256"] = "0" * 64
        with self.assertRaises(PlanGenerationError):
            generate_fill_plan(fs, blueprint, base_dir=self.root)

    def test_schema_allows_bound_plan(self):
        import jsonschema
        schema = json.loads((Path(__file__).parents[1] / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(self.plan)

    def test_offline_cli_and_no_existing_output_overwrite(self):
        out = self.root.parent / (self.root.name + "-assessment")
        self.addCleanup(lambda: __import__('shutil').rmtree(out, ignore_errors=True))
        cmd = [sys.executable, "-X", "utf8", "-m", "bpm.self_drive_plan", "--inputs", str(self.root / "originals/scenario_inputs.json"), "--manifest", str(self.root / "manifest.json"), "--output", str(out)]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["browser_launched"])
        self.assertEqual(subprocess.run(cmd, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
