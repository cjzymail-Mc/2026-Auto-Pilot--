"""Fail-closed, offline validation for versioned BPM plans (no browser I/O)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PlanError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("; ".join(f"{i['path']}: {i['message']}" for i in issues))


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def money(value):
    """Exact nonnegative cents. Floats, exponents and silently rounded values fail."""
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError("amount must be a decimal string or integer, never float")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", str(value)):
        raise ValueError("amount must be nonnegative plain decimal with at most two decimals")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("nonfinite amount")
    return result


def pointer_get(obj, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("locator must be a JSON pointer")
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def load_type(document_type):
    if document_type != "travel":
        raise PlanError([{"path": "/document_type", "code": "UNSUPPORTED_TYPE", "message": "unsupported document type"}])
    return json.loads((ROOT / "automation/document-types/travel.json").read_text(encoding="utf-8"))


def _proof_path(value, base_dir):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing evidence path")
    p = Path(value)
    p = (base_dir / p).resolve() if not p.is_absolute() else p.resolve()
    if any(part.lower() in {".pw-profile", ".git", "legacy-ia2"} for part in p.parts):
        raise ValueError("protected evidence location")
    if not p.is_file():
        raise ValueError("evidence file does not exist")
    return p


def validate_plan(plan, expected_operator=None, verify_sources=True, *, base_dir=None):
    issues = []
    base_dir = Path(base_dir or ROOT).resolve()

    def bad(path, message, code="INVALID_PLAN"):
        issues.append({"path": path, "code": code, "message": message})

    def text(value, path):
        if not isinstance(value, str) or not value.strip():
            bad(path, "nonempty string required")
            return False
        return True

    if not isinstance(plan, dict):
        bad("/", "plan must be an object")
        return issues
    allowed = {"schema_version", "task_id", "document_type", "config_version", "operator", "applicant", "template", "materials", "header", "tables", "sources", "authorization", "unresolved", "not_applicable", "amount_rules"}
    optional = {"identity", "test_context"}
    for key in sorted(set(plan) - allowed - optional):
        bad("/" + key, "unknown top-level property")
    for key in sorted(allowed - set(plan)):
        bad("/" + key, "required property missing")
    for key, expected in (("schema_version", "1.0"), ("config_version", "1.0"), ("document_type", "travel")):
        if plan.get(key) != expected:
            bad("/" + key, f"supported value is {expected}", "UNSUPPORTED_VERSION" if key != "document_type" else "UNSUPPORTED_TYPE")
    for key in ("task_id", "operator"):
        text(plan.get(key), "/" + key)
    if expected_operator is not None and plan.get("operator") != expected_operator:
        bad("/operator", "operator differs from expected identity", "IDENTITY_MISMATCH")
    applicant = plan.get("applicant", {})
    if not isinstance(applicant, dict):
        bad("/applicant", "object required")
        applicant = {}
    if set(applicant) != {"name", "company", "department"}:
        bad("/applicant", "exact name, company and department identity required")
    values, value_types = {}, {}
    identity = plan.get("identity")
    if "identity" in plan:
        if not isinstance(identity, dict) or set(identity) != {"applicant_employee_id", "creator_name", "creator_department"}:
            bad("/identity", "exact applicant employee id and creator identity required")
        else:
            for key, value in identity.items():
                if text(value, "/identity/" + key):
                    values["/identity/" + key] = value
            if not re.fullmatch(r"\d+", str(identity["applicant_employee_id"])):
                bad("/identity/applicant_employee_id", "exact employee identifier required")
    for key in ("name", "company", "department"):
        if text(applicant.get(key), "/applicant/" + key):
            values["/applicant/" + key] = applicant[key]
    for key in ("unresolved", "not_applicable"):
        if not isinstance(plan.get(key), list):
            bad("/" + key, "array required")
    if isinstance(plan.get("not_applicable"), list) and any(not isinstance(item, str) or not item.strip() for item in plan["not_applicable"]):
        bad("/not_applicable", "nonempty strings required")
    if plan.get("unresolved"):
        bad("/unresolved", "resolve all gaps before browser launch", "NEEDS_INPUT")
    authorization = plan.get("authorization", {})
    if not isinstance(authorization, dict):
        authorization = {}
    if set(authorization) != {"mode", "task_id", "statement", "allow_submit"}:
        bad("/authorization", "exact authorization keys required")
    if authorization.get("mode") not in ("fill_only", "save_draft"):
        bad("/authorization/mode", "fill_only or save_draft required")
    if authorization.get("task_id") != plan.get("task_id"):
        bad("/authorization/task_id", "authorization must bind this task")
    if authorization.get("allow_submit") is not False:
        bad("/authorization/allow_submit", "submission is forbidden")
    text(authorization.get("statement"), "/authorization/statement")
    context = plan.get("test_context")
    if "test_context" in plan:
        if not isinstance(context, dict) or set(context) != {"purpose", "round", "authorization_path", "authorization_sha256"}:
            bad("/test_context", "explicit test purpose, round and authorization evidence required")
        else:
            for key in ("purpose","round","authorization_path"):
                text(context[key],"/test_context/"+key)
            if not isinstance(context["authorization_sha256"],str) or not SHA256.fullmatch(context["authorization_sha256"]):
                bad("/test_context/authorization_sha256","SHA256 required")
            if verify_sources:
                try:
                    path = _proof_path(context["authorization_path"], base_dir)
                    if file_hash(path) != context["authorization_sha256"]:
                        raise ValueError("test authorization hash mismatch")
                except (OSError, ValueError, TypeError) as exc:
                    bad("/test_context", str(exc))
        if authorization.get("mode") != "fill_only":
            bad("/authorization/mode", "test context permits unsaved fill_only only")
    config = load_type("travel")
    header = plan.get("header", {})
    if not isinstance(header, dict):
        bad("/header", "object required")
        header = {}
    if set(header) != set(config["header"]):
        bad("/header", "all configured header properties required; unknown properties forbidden")
    if header.get("corpCode") != applicant.get("company"):
        bad("/header/corpCode", "rendered company must match applicant.company", "IDENTITY_MISMATCH")
    tables = plan.get("tables", {})
    if not isinstance(tables, dict):
        bad("/tables", "object required")
        tables = {}
    if set(tables) != set(config["tables"]):
        bad("/tables", "exactly relations, details, costs, banks required")

    def check_field(value, spec, path):
        kind = spec["type"]
        try:
            if kind == "money":
                money(value)
            elif kind == "count":
                if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"\d+(?:\.\d+)?", str(value)) or Decimal(str(value)) <= 0:
                    raise ValueError("positive plain decimal count required")
            elif kind == "date":
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError("ISO YYYY-MM-DD required")
            elif kind == "identifier":
                if not isinstance(value, str) or not re.fullmatch(r"\d+", value):
                    raise ValueError("digit identifier must remain a string")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError("nonempty exact string required")
            if "allowed_values" in spec and value not in spec["allowed_values"]:
                raise ValueError("value is outside supported exact rendered options")
        except (ValueError, TypeError, InvalidOperation) as exc:
            bad(path, str(exc))
        values[path] = value
        value_types[path] = kind

    for key, value in header.items():
        if key in config["header"]:
            check_field(value, config["header"][key], "/header/" + key)
    for table, spec in config["tables"].items():
        rows = tables.get(table)
        if not isinstance(rows, list):
            bad("/tables/" + table, "row array required")
            continue
        if table in {"details", "banks"} and not rows:
            bad("/tables/" + table, "at least one row required")
        seen, business = set(), set()
        for index, row in enumerate(rows):
            at = f"/tables/{table}/{index}"
            if not isinstance(row, dict) or set(row) != {"row_id", "fields"}:
                bad(at, "exact row_id and fields object required")
                continue
            row_id = row.get("row_id")
            if not text(row_id, at + "/row_id"):
                continue
            if row_id in seen:
                bad(at + "/row_id", "duplicate stable row identifier")
            seen.add(row_id)
            fields = row.get("fields")
            if not isinstance(fields, dict):
                bad(at + "/fields", "fields must be object")
                continue
            if set(fields) != set(spec["columns"]):
                bad(at + "/fields", "exact configured columns required")
            business_key = str(fields.get("bizNumber")) if table == "relations" else json.dumps(fields, sort_keys=True, ensure_ascii=False)
            if business_key in business:
                bad(at, "duplicate business row")
            business.add(business_key)
            for key, value in fields.items():
                if key in spec["columns"]:
                    check_field(value, spec["columns"][key], at + "/fields/" + key)
            if table == "costs" and isinstance(fields.get("startDate"), str) and isinstance(fields.get("endDate"), str) and fields["startDate"] > fields["endDate"]:
                bad(at, "startDate follows endDate")
    rules = plan.get("amount_rules", {})
    if not isinstance(rules, dict):
        rules = {}
    if set(rules) - {"costs", "costs_reason", "cost_amount_semantics"}:
        bad("/amount_rules", "unknown amount rule (loan offsets unsupported)")
    if rules.get("cost_amount_semantics") not in ("line_total", "unit_price_times_count"):
        bad("/amount_rules/cost_amount_semantics", "explicit cost amount semantics required")
    costs = tables.get("costs")
    if isinstance(costs, list) and costs:
        if rules.get("costs") != "sum":
            bad("/amount_rules/costs", "nonempty cost table requires sum")
    elif rules.get("costs") != "not_applicable" or not isinstance(rules.get("costs_reason"), str) or not rules.get("costs_reason", "").strip():
        bad("/amount_rules", "empty costs require explicit not_applicable and reason")
    try:
        total = money(header["totalCost"])
        if total <= 0:
            bad("/header/totalCost", "positive reimbursement total required")
        for table in ("details", "banks", "costs"):
            rows = tables[table]
            if table == "costs" and not rows:
                continue
            amount = sum((money(r["fields"]["cost"]) * (Decimal(str(r["fields"]["count"])) if table == "costs" and rules.get("cost_amount_semantics") == "unit_price_times_count" else 1) for r in rows), Decimal(0))
            if amount != total:
                bad("/tables/" + table, "amount sum differs from totalCost", "AMOUNT_MISMATCH")
    except (ValueError, KeyError, TypeError, InvalidOperation):
        pass  # Shape/type issues were collected above.

    # Every executable scalar is independently traceable. Historical expenses cannot be recycled.
    sources = plan.get("sources", {})
    if not isinstance(sources, dict):
        bad("/sources", "source map required")
        sources = {}
    for pointer in sources:
        if pointer not in values:
            bad("/sources/" + str(pointer), "source does not identify a planned scalar")
    manifest = None
    for section, path_key, hash_key in (("template", "snapshot_path", "sha256"), ("materials", "manifest_path", "manifest_sha256")):
        evidence = plan.get(section, {})
        if not isinstance(evidence, dict):
            bad("/" + section, "object required")
            continue
        expected_keys = {"biz_number", "captured_at", "sha256", "snapshot_path"} if section == "template" else {"manifest_path", "manifest_sha256"}
        optional_keys = set() if section == "template" else {"image_documents", "no_invoice_rows"}
        if expected_keys - set(evidence) or set(evidence) - expected_keys - optional_keys:
            bad("/" + section, "exact configured evidence keys required")
        if not isinstance(evidence.get(hash_key), str) or not SHA256.fullmatch(evidence.get(hash_key, "")):
            bad("/" + section + "/" + hash_key, "SHA256 required")
        text(evidence.get(path_key), "/" + section + "/" + path_key)
        if section == "template":
            if not isinstance(evidence.get("biz_number"), str) or not re.fullmatch(r"\d+", evidence.get("biz_number", "")):
                bad("/template/biz_number", "template number must be digit string")
            try:
                captured = datetime.fromisoformat(evidence["captured_at"].replace("Z", "+00:00"))
                if captured.tzinfo is None:
                    raise ValueError("capture timestamp must include timezone")
            except (KeyError, ValueError, TypeError, AttributeError):
                bad("/template/captured_at", "ISO capture timestamp required")
        if verify_sources:
            try:
                evidence_path = _proof_path(evidence.get(path_key), base_dir)
                if file_hash(evidence_path) != evidence.get(hash_key):
                    raise ValueError("evidence content hash drift")
                if section == "materials":
                    from bpm_materials import validate_manifest
                    manifest = json.loads(evidence_path.read_text(encoding="utf-8"))
                    material_issues = validate_manifest(manifest, base_dir=evidence_path.parent)
                    for issue in material_issues:
                        bad("/materials", issue["message"], issue["code"])
                    if material_issues:
                        manifest = None
                    else:
                        from bpm_materials import validate_image_documents
                        for issue in validate_image_documents(evidence, manifest, plan, base_dir=base_dir):
                            bad("/materials", issue["message"], issue["code"])
                else:
                    snapshot = json.loads(evidence_path.read_text(encoding="utf-8"))
                    if not isinstance(snapshot, dict) or snapshot.get("biz_number", snapshot.get("bizNumber")) != evidence.get("biz_number"):
                        raise ValueError("template snapshot document number differs")
                    if snapshot.get("captured_at") != evidence.get("captured_at"):
                        raise ValueError("template capture time differs from snapshot")
            except (OSError, ValueError) as exc:
                bad("/" + section, str(exc), "SOURCE_INVALID")
    for pointer, value in values.items():
        source = sources.get(pointer)
        if not isinstance(source, dict):
            bad(pointer, "source proof missing", "SOURCE_MISSING")
            continue
        kind = source.get("kind")
        if kind not in ("material", "template", "user", "derived"):
            bad(pointer, "unsupported source kind", "SOURCE_INVALID")
            continue
        if set(source) - {"kind", "path", "locator", "sha256", "operation", "inputs", "corroborates"}:
            bad(pointer, "unknown source proof properties", "SOURCE_INVALID")
        corroborates = source.get("corroborates", [])
        if not isinstance(corroborates, list) or any(not isinstance(proof, dict) for proof in corroborates):
            bad(pointer, "corroborates must be an array of located hash proofs", "SOURCE_INVALID")
        elif verify_sources:
            from bpm_materials import validate_value_proof
            for proof in corroborates:
                for issue in validate_value_proof(proof, value, base_dir=base_dir, monetary=value_types.get(pointer) == "money",
                                                  material_hashes={item["sha256"] for item in manifest.get("files", [])} if manifest is not None else set()):
                    bad(pointer, issue["message"], issue["code"])
        if kind == "template" and (pointer.startswith("/tables/costs/") or pointer.startswith("/tables/relations/") or pointer.endswith("/cost") or pointer in {"/header/totalCost", "/header/budgetYears", "/header/description"} or "invoice" in pointer.lower()):
            bad(pointer, "current task facts cannot derive from historical template", "HISTORICAL_FACT_REUSE")
        if pointer.startswith("/tables/details/") and pointer.endswith("/fields/digest") and kind not in ("material", "user"):
            bad(pointer, "current expense digest requires primary material or user evidence", "HISTORICAL_FACT_REUSE")
        if kind == "derived":
            inputs = source.get("inputs")
            if source.get("operation") != "sum" or not isinstance(inputs, list) or not inputs or any(not isinstance(p, str) or p not in values or p == pointer for p in inputs):
                bad(pointer, "only explicit sum of other planned amount pointers supported", "SOURCE_INVALID")
            else:
                try:
                    if len(set(inputs)) != len(inputs) or money(value) != sum((money(values[p]) for p in inputs), Decimal(0)):
                        raise ValueError("derived sum mismatch or duplicate inputs")
                    if any(sources.get(p, {}).get("kind") == "derived" for p in inputs):
                        raise ValueError("derived chains unsupported")
                except (ValueError, TypeError):
                    bad(pointer, "derived sum must close exactly", "SOURCE_INVALID")
            continue
        if not text(source.get("locator"), pointer + "/source/locator"):
            continue
        if not isinstance(source.get("sha256"), str) or not SHA256.fullmatch(source.get("sha256", "")):
            bad(pointer, "source SHA256 required", "SOURCE_INVALID")
        if not verify_sources:
            continue
        try:
            path = _proof_path(source.get("path"), base_dir)
            if file_hash(path) != source.get("sha256"):
                raise ValueError("source content hash drift")
            template_proof = plan.get("template") if isinstance(plan.get("template"), dict) else {}
            if kind == "template" and source.get("sha256") != template_proof.get("sha256"):
                raise ValueError("template source must bind template snapshot")
            if kind == "material" and manifest is not None and source.get("sha256") not in {f["sha256"] for f in manifest.get("files", [])}:
                raise ValueError("material source absent from manifest")
            from bpm_materials import read_locator
            if path.suffix.lower() == ".json":
                contents = json.loads(path.read_text(encoding="utf-8"))
                from bpm_materials import is_reviewed_extraction
                if is_reviewed_extraction(contents):
                    from bpm_materials import validate_reviewed_extraction
                    errors = validate_reviewed_extraction(contents, base_dir=path.parent)
                    if errors:
                        raise ValueError(errors[0]["message"])
                    material_hashes = {item["sha256"] for item in manifest.get("files", [])} if manifest is not None else set()
                    if contents.get("original_sha256") not in material_hashes or source.get("sha256") not in material_hashes:
                        raise ValueError("reviewed extraction and original must belong to same material manifest")
            located = read_locator(path, source["locator"], allow_numeric=value_types.get(pointer) in {"money", "count"})
            # No normalization of identifiers, names or selected option labels.
            if str(located) != str(value):
                try:
                    numeric = pointer.endswith("/cost") or pointer == "/header/totalCost" or pointer.endswith("/nowCost")
                    if not numeric or money(located) != money(value):
                        raise ValueError("located value differs from planned value")
                except (ValueError, TypeError):
                    raise ValueError("located value differs from planned value")
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            bad(pointer, str(exc), "SOURCE_INVALID")
    return issues


def load_plan(path, expected_operator=None, verify_sources=True):
    path = Path(path).resolve()
    try:
        if any(part.lower() in {".pw-profile", ".git", "legacy-ia2"} for part in path.parts):
            raise ValueError("protected plan location")
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError([{"path": "/", "code": "PLAN_UNREADABLE", "message": str(exc)}]) from exc
    issues = validate_plan(plan, expected_operator, verify_sources, base_dir=path.parent)
    if issues:
        raise PlanError(issues)
    return plan
