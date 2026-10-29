"""Offline self-drive provenance, calculation and plan binding; no browser I/O.

The legacy V3 coverage model is deliberately untouched. Inputs contain located
proofs, not copied amounts. Every validation rereads those proofs and the frozen
rules. This verifies consistency; it does not certify a live login or a real save.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from bpm.materials import _safe_material, read_locator, validate_dual_manifest, validate_manifest
from bpm.plan import file_hash, money, pointer_get
from bpm.self_drive import (MealDay, SelfDriveInputs, SelfDriveRow,
                            evaluate_self_drive, load_self_drive_rules)


class SelfDriveBindingError(ValueError):
    pass


def _exact(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise SelfDriveBindingError(label + ": exact keys required: " + ", ".join(keys))


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise SelfDriveBindingError("exact ISO calendar date required")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise SelfDriveBindingError(label + ": nonempty string required")
    return value


class _Evidence:
    def __init__(self, manifest, base_dir):
        self.base = Path(base_dir).resolve()
        self.manifest = manifest
        self.synthetic = False
        check = validate_dual_manifest if manifest.get("schema_version") == "2.0" else validate_manifest
        issues = check(manifest, base_dir=self.base)
        if issues:
            raise SelfDriveBindingError("material manifest invalid: " + issues[0]["message"])
        self.files = {}
        for item in manifest.get("files", []) + manifest.get("derived_files", []):
            p = self.path(item["path"])
            self.files[str(p)] = item["sha256"]

    def path(self, value):
        p = Path(value)
        return _safe_material(p if p.is_absolute() else self.base / p)

    def read(self, proof):
        _exact(proof, ("path", "locator", "sha256"), "source proof")
        p = self.path(proof["path"])
        if (self.files.get(str(p)) != proof["sha256"]
                or file_hash(p) != proof["sha256"]):
            raise SelfDriveBindingError("source absent from this manifest or hash drift")
        if p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("synthetic") is True:
                self.synthetic = True
        return read_locator(p, _text(proof["locator"], "locator"), allow_numeric=True)


def assess_self_drive(packet, manifest, *, base_dir):
    """Recompute a sourced scenario packet, including same-row trip participation.

    Trip proof locators select ONE JSON object with biz_number/date/route/
    participants. Each participant has name and employee_id. Ambiguous trips,
    unsupported source formats or a missing creator identifier are gaps, never
    guessed. Scope dates come from a separate located user/material statement.
    """
    _exact(packet, ("schema_version", "creator", "scope_dates", "rows", "invoices",
                    "trips", "meal_assignments"), "self-drive input packet")
    if packet["schema_version"] != "1.0":
        raise SelfDriveBindingError("unsupported self-drive input schema")
    evidence = _Evidence(manifest, base_dir)
    creator = evidence.read(packet["creator"])
    _exact(creator, ("name", "employee_id", "department"), "creator")
    for key in creator:
        _text(creator[key], "creator." + key)
    if not creator["employee_id"].isdigit():
        raise SelfDriveBindingError("exact creator employee identifier required")
    scope = evidence.read(packet["scope_dates"])
    if not isinstance(scope, list) or not scope or len(set(scope)) != len(scope):
        raise SelfDriveBindingError("unique sourced scope dates required")
    scope = {_day(d) for d in scope}
    trips = []
    trip_ids = set()
    for proof in packet["trips"]:
        trip = evidence.read(proof)
        _exact(trip, ("biz_number", "date", "route", "participants"), "trip fact row")
        number = _text(trip["biz_number"], "trip number")
        if not number.isdigit():
            raise SelfDriveBindingError("complete numeric trip number required")
        key = (number, _day(trip["date"]), _text(trip["route"], "trip route"))
        if key in trip_ids:
            raise SelfDriveBindingError("duplicate trip fact row")
        trip_ids.add(key)
        if not isinstance(trip["participants"], list) or not trip["participants"]:
            raise SelfDriveBindingError("same-row participants required")
        participant_keys = set()
        for participant in trip["participants"]:
            _exact(participant, ("name", "employee_id"), "trip participant")
            pk = (_text(participant["name"], "participant name"),
                  _text(participant["employee_id"], "participant employee id"))
            if not pk[1].isdigit() or any(prior[1] == pk[1] for prior in participant_keys):
                raise SelfDriveBindingError("unique exact participant employee identifiers required")
            participant_keys.add(pk)
        if (creator["name"], creator["employee_id"]) in participant_keys:
            trips.append(trip)
    valid_days = scope & {trip["date"] for trip in trips}
    # An empty intersection is a gap: zero meal allowance cannot be assumed.
    if not valid_days:
        raise SelfDriveBindingError("no sourced creator participation within this scope")
    assignments = {}
    for entry in packet["meal_assignments"]:
        _exact(entry, ("date", "trip_number"), "meal assignment")
        day = _day(entry["date"])
        if day in assignments or not any(t["date"] == day and t["biz_number"] == entry["trip_number"] for t in trips):
            raise SelfDriveBindingError("meal day duplicated or not assigned to a same-row participating trip")
        assignments[day] = entry["trip_number"]
    if set(assignments) != valid_days:
        raise SelfDriveBindingError("meal assignments must cover exactly scope intersection, once per day")
    invoices, invoice_evidence, faces, numbers = {}, {}, {}, set()
    for item in packet["invoices"]:
        _exact(item, ("invoice_id", "kind", "number", "amount", "date"), "invoice")
        iid = _text(item["invoice_id"], "invoice id")
        if iid in invoices:
            raise SelfDriveBindingError("duplicate invoice id")
        kind, number, amount, day = (evidence.read(item[k]) for k in ("kind", "number", "amount", "date"))
        if kind not in ("toll", "fuel") or _text(number, "invoice number") in numbers:
            raise SelfDriveBindingError("unique toll/fuel invoice identities required")
        # Number, kind, amount and date must come from the same reviewed record.
        origins = {(str(evidence.path(item[k]["path"])), item[k]["sha256"],
                    item[k]["locator"].split("/fields/", 1)[0] if "/fields/" in item[k]["locator"]
                    else item[k]["locator"].rsplit("/", 1)[0]) for k in ("kind", "number", "amount", "date")}
        if len(origins) != 1:
            raise SelfDriveBindingError("invoice fields must come from the same source record")
        value = money(amount)
        if value <= 0:
            raise SelfDriveBindingError("positive invoice face amount required")
        invoices[iid] = {"kind": kind, "date": _day(day)}
        origin = next(iter(origins))
        invoice_evidence[iid] = {"number": number, "kind": kind, "amount": str(value),
                                 "path": origin[0], "record_locator": origin[2]}
        faces[iid] = str(value)
        numbers.add(number)
    rows, row_meta, row_ids = [], {}, set()
    for item in packet["rows"]:
        _exact(item, ("row_id", "date", "km", "route", "toll_ids"), "mileage row")
        rid = _text(item["row_id"], "row id")
        if rid in row_ids:
            raise SelfDriveBindingError("duplicate mileage row id")
        row_ids.add(rid)
        day, route = _day(evidence.read(item["date"])), _text(evidence.read(item["route"]), "row route")
        km = money(evidence.read(item["km"]))
        candidates = {t["biz_number"] for t in trips if t["date"] == day and t["route"] == route}
        if day not in scope or len(candidates) != 1:
            raise SelfDriveBindingError("mileage row needs one exact date/route/creator trip match")
        ids = item["toll_ids"]
        if not isinstance(ids, list) or any(i not in invoices or invoices[i] != {"kind": "toll", "date": day} for i in ids):
            raise SelfDriveBindingError("row tolls must be current-date toll invoices, never fuel")
        rows.append(SelfDriveRow(rid, str(km), tuple(ids)))
        row_meta[rid] = {"date": day, "trip_number": next(iter(candidates)), "route": route}
    if not rows:
        raise SelfDriveBindingError("sourced mileage rows required")
    rules = load_self_drive_rules()
    inputs = SelfDriveInputs(rules.rate_str(), rules.meal_str(), tuple(rows),
                            tuple(MealDay(day, assignments[day]) for day in sorted(valid_days)),
                            faces, tuple(i for i, v in invoices.items() if v["kind"] == "toll"),
                            tuple(i for i, v in invoices.items() if v["kind"] == "fuel"),
                            rules.rule_source, rules.version)
    result = evaluate_self_drive(inputs, rules=rules)
    if not result["gate_passed"]:
        raise SelfDriveBindingError("strict coverage gate requires F > R")
    components, relation_totals = {}, defaultdict(lambda: Decimal(0))
    for row in result["rows"]:
        meta = row_meta[row["row_id"]]
        for prefix, field in (("km", "row_subsidy"), ("toll", "row_toll")):
            if money(row[field]) > 0:
                components[prefix + ":" + row["row_id"]] = {"amount": row[field], "date": meta["date"]}
        relation_totals[meta["trip_number"]] += money(row["row_transport"])
    for day in sorted(valid_days):
        components["meal:" + day] = {"amount": rules.meal_str(), "date": day}
        relation_totals[assignments[day]] += rules.meal_per_valid_day
    return {"status": "SCENARIO_PREPARED_OFFLINE", "creator": creator,
            "rules_version": rules.version, "rules_sha256": rules.config_sha256,
            "calculation": result, "components": components,
            "invoice_evidence": invoice_evidence,
            "relation_totals": {k: str(v.quantize(Decimal('.01'))) for k, v in relation_totals.items()},
            "synthetic_inputs": evidence.synthetic,
            "real_fill_verified": False, "real_save_verified": False}


def validate_self_drive_binding(plan, *, base_dir, manifest=None):
    """Used by the ordinary plan validator before execution and save rechecks."""
    issues = []
    try:
        block = plan["self_drive_coverage"]
        _exact(block, ("schema_version", "rules_version", "rules_sha256", "inputs", "cost_bindings"), "self-drive binding")
        if block["schema_version"] != "1.0" or plan.get("document_type") != "travel" or "coverage" in plan:
            raise SelfDriveBindingError("new self-drive binding is travel-only and cannot mix legacy coverage")
        if manifest is None:
            raise SelfDriveBindingError("self-drive binding requires verified source material manifest")
        proof = dict(block["inputs"])
        _exact(proof, ("path", "sha256"), "input packet reference")
        manifest_path = Path(plan["materials"]["manifest_path"])
        if not manifest_path.is_absolute():
            manifest_path = Path(base_dir) / manifest_path
        evidence_base = manifest_path.resolve().parent
        ev = _Evidence(manifest, evidence_base)
        packet_path = Path(proof["path"])
        p = _safe_material(packet_path if packet_path.is_absolute() else Path(base_dir) / packet_path)
        if ev.files.get(str(p)) != proof["sha256"] or file_hash(p) != proof["sha256"]:
            raise SelfDriveBindingError("input packet not bound to this manifest or hash drift")
        packet = json.loads(p.read_text(encoding="utf-8"))
        result = assess_self_drive(packet, manifest, base_dir=evidence_base)
        if result["synthetic_inputs"] and plan.get("authorization", {}).get("mode") != "fill_only":
            raise SelfDriveBindingError("synthetic scenario inputs require fill_only")
        if (block["rules_version"], block["rules_sha256"]) != (result["rules_version"], result["rules_sha256"]):
            raise SelfDriveBindingError("self-drive rules version/hash drift")
        identity = plan.get("identity", {})
        creator = result["creator"]
        if (identity.get("creator_name"), identity.get("creator_department"), identity.get("applicant_employee_id"),
                plan.get("applicant", {}).get("name")) != (creator["name"], creator["department"], creator["employee_id"], creator["name"]):
            raise SelfDriveBindingError("creator identity/employee id not bound; delegated applicant scenario needs separate modeling")
        bindings = block["cost_bindings"]
        if not isinstance(bindings, dict) or set(bindings) != set(result["components"]):
            raise SelfDriveBindingError("cost bindings must cover each mileage/toll/meal component exactly once")
        expected_pointers = {f"/tables/costs/{i}/fields/cost" for i, _ in enumerate(plan["tables"]["costs"])}
        if (len(set(bindings.values())) != len(bindings) or set(bindings.values()) != expected_pointers
                or plan.get("amount_rules", {}).get("costs") != "sum"
                or plan.get("amount_rules", {}).get("cost_amount_semantics") != "line_total"):
            raise SelfDriveBindingError("separate, exhaustive line-total component rows required; mixed rows cannot be exempted")
        for key, pointer in bindings.items():
            expected = result["components"][key]
            fields = pointer_get(plan, pointer.rsplit("/", 1)[0])
            if (money(fields["cost"]) != money(expected["amount"]) or fields["startDate"] != expected["date"]
                    or fields["endDate"] != expected["date"] or str(fields["count"]) != "1"):
                raise SelfDriveBindingError("component amount/date/count differs from independent inputs: " + key)
        # Every toll/fuel amount must bind a reviewed invoice record already
        # classified by the ordinary material validator. Fuel is coverage-only;
        # only toll components receive actual invoice allocations.
        observed_invoices = {}
        for document in plan["materials"].get("image_documents", []):
            if document.get("kind") != "invoice":
                continue
            ep = Path(document["extraction_path"])
            ep = _safe_material(ep if ep.is_absolute() else Path(base_dir) / ep)
            extraction = json.loads(ep.read_text(encoding="utf-8"))
            reconciliations = {r["record_id"]: r for r in document["records"]}
            for index, record in enumerate(extraction["records"]):
                number = record["fields"].get("invoice_number", {}).get("value")
                if number in observed_invoices:
                    raise SelfDriveBindingError("duplicate invoice identity in plan")
                observed_invoices[number] = (str(ep), "/records/" + str(index), reconciliations[record["record_id"]])
        for iid, invoice in result["invoice_evidence"].items():
            actual = observed_invoices.get(invoice["number"])
            if actual is None or actual[:2] != (invoice["path"], invoice["record_locator"]):
                raise SelfDriveBindingError("scenario invoice must bind the classified reviewed record: " + iid)
            record = actual[2]
            if invoice["kind"] == "fuel":
                if "not_applicable" not in record or "allocations" in record:
                    raise SelfDriveBindingError("fuel is coverage-only, never an expense allocation")
            else:
                row_id = result["calculation"]["invoice_allocation"][iid]
                assigned = record.get("allocations", [])
                if (len(assigned) != 1 or assigned[0].get("plan_pointer") != bindings["toll:" + row_id]
                        or money(assigned[0].get("amount")) != money(invoice["amount"])):
                    raise SelfDriveBindingError("toll invoice must allocate exactly to its own toll component")
        R = money(result["calculation"]["R_reimburse"])
        for table in ("details", "costs", "banks"):
            if sum((money(r["fields"]["cost"]) for r in plan["tables"][table]), Decimal(0)) != R:
                raise SelfDriveBindingError(table + " differs from independently recomputed self-drive total")
        if money(plan["header"]["totalCost"]) != R:
            raise SelfDriveBindingError("plan total differs from independently recomputed self-drive total")
        relations = plan["tables"]["relations"]
        if "oa_test_relations" in plan:
            if plan.get("authorization", {}).get("mode") != "fill_only" or sum((money(r["fields"]["nowCost"]) for r in relations), Decimal(0)) != R:
                raise SelfDriveBindingError("placeholder association remains fill-only and must close separately")
        else:
            observed = {}
            for row in relations:
                fields = row["fields"]
                if fields["bizTypeName"] != "公出单" or fields["bizNumber"] in observed:
                    raise SelfDriveBindingError("unique actual trip associations required")
                observed[fields["bizNumber"]] = money(fields["nowCost"])
            if observed != {k: money(v) for k, v in result["relation_totals"].items()}:
                raise SelfDriveBindingError("per-trip allocations differ, including compensating differences")
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        issues.append({"path": "/self_drive_coverage", "code": "SELF_DRIVE_BINDING_INVALID", "message": str(exc)})
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description="Source-backed self-drive offline preparation; no OA access")
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True, help="new directory; never an existing location")
    args = parser.parse_args(argv)
    try:
        inputs, mp, output = (_safe_material(Path(v)) for v in (args.inputs, args.manifest, args.output))
        if output.exists() or any(output == p.parent or output in p.parents or p.parent in output.parents for p in (inputs, mp)):
            raise SelfDriveBindingError("output must be a separate new directory, outside input trees")
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        ev = _Evidence(manifest, mp.parent)
        if ev.files.get(str(inputs)) != file_hash(inputs):
            raise SelfDriveBindingError("input packet must already be registered in this manifest")
        result = assess_self_drive(json.loads(inputs.read_text(encoding="utf-8")), manifest, base_dir=mp.parent)
        output.mkdir(parents=True, exist_ok=False)
        (output / "self_drive_assessment.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": result["status"], "browser_launched": False, "output": str(output)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        print(json.dumps({"status": "NEEDS_INPUT", "code": "SELF_DRIVE_BINDING_INVALID", "message": str(exc), "browser_launched": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
