"""Read-only material inventory and structured extraction; never uploads files."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from bpm.plan import file_hash, money, pointer_get

IMAGE_PDF = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}

DUAL_MANIFEST_VERSION = "2.0"
# user_request/decision_matrix（W01）：用户请求登记记录与模板复用决策矩阵——版本化
# agent 决策工件，落派生根但不冒充原件；枚举保持封闭，仅显式扩充。
DERIVED_ROLES = ("parsed_extraction", "reviewed_extraction", "ocr_result", "render", "run_evidence",
                 "user_request", "decision_matrix")
DUAL_PROOF_KINDS = ("material", "user", "agent_reviewed")


def is_reviewed_extraction(data):
    if not isinstance(data, dict):
        return False
    if any(key in data for key in ("reviewed", "reviewed_by", "original_path", "original_sha256")):
        return True
    records = data.get("records")
    return isinstance(records, list) and any(
        isinstance(record, dict) and isinstance(record.get("fields"), dict)
        and any(isinstance(field, dict) and "locator" in field for field in record["fields"].values())
        for record in records)


def _safe_material(path):
    lexical = Path(path)
    resolved = lexical.resolve()
    if any(part.lower() in {".pw-profile", ".git", "legacy-ia2"} for part in lexical.parts + resolved.parts):
        raise ValueError("protected path cannot be material")
    return resolved


def inventory_materials(directory):
    """Content-based dedup; equal names alone are never treated as equal materials."""
    root = _safe_material(directory)
    if not root.is_dir():
        raise ValueError("materials directory does not exist")
    files, hashes = [], {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        resolved = _safe_material(path)
        if not resolved.is_relative_to(root):
            raise ValueError("material symlink escapes inventory root")
        digest = file_hash(resolved)
        relative = path.relative_to(root).as_posix()
        if digest in hashes:
            hashes[digest]["duplicate_paths"].append(relative)
            continue
        item = {"material_id": "sha256:" + digest, "path": str(path.absolute()),
                "relative_path": relative, "sha256": digest,
                "size_bytes": resolved.stat().st_size, "duplicate_paths": []}
        files.append(item)
        hashes[digest] = item
    return {"schema_version": "1.0", "root": str(root), "files": files}


def _validated_root(value, base):
    """Parse a manifest root reference into an existing non-protected directory."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("manifest root must be a nonempty directory path")
    path = Path(value)
    root = _safe_material(path if path.is_absolute() else base / path)
    if not root.is_dir():
        raise ValueError("manifest root must be an existing directory")
    return root


def _check_files_in_root(files, root, base):
    """Shared single-root per-file checks (v1.0 semantics, unchanged)."""
    issues, seen, seen_paths = [], set(), set()

    def relative_file(relative):
        if (not isinstance(relative, str) or not relative or "\\" in relative
                or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise ValueError("material relative path must be canonical without traversal")
        candidate = Path(relative)
        if candidate.is_absolute() or candidate.drive or candidate.as_posix() != relative:
            raise ValueError("material relative path must be canonical and relative")
        lexical = root / candidate
        resolved = _safe_material(lexical)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError("material path escapes root or is not a file")
        if relative in seen_paths:
            raise ValueError("material path appears more than once")
        seen_paths.add(relative)
        return lexical, resolved

    for item in files:
        try:
            digest = item["sha256"]
            if digest in seen:
                raise ValueError("duplicate content must be represented as duplicate_paths")
            seen.add(digest)
            if not isinstance(item.get("path"), str) or not item["path"].strip():
                raise ValueError("material primary path required")
            declared = Path(item["path"])
            if ".." in declared.parts:
                raise ValueError("material primary path contains traversal")
            declared = declared if declared.is_absolute() else base / declared
            lexical, path = relative_file(item["relative_path"])
            if (not declared.is_relative_to(root)
                    or declared.relative_to(root).as_posix() != item["relative_path"]
                    or declared != lexical or _safe_material(declared) != path):
                raise ValueError("material primary path and relative_path must match within manifest root")
            if file_hash(path) != digest or item.get("material_id") != "sha256:" + digest or path.stat().st_size != item.get("size_bytes"):
                raise ValueError("material hash, size or identifier drift")
            duplicates = item.get("duplicate_paths", [])
            if not isinstance(duplicates, list) or len(set(duplicates)) != len(duplicates):
                raise ValueError("invalid duplicate paths")
            for relative in duplicates:
                _, duplicate = relative_file(relative)
                if file_hash(duplicate) != digest:
                    raise ValueError("duplicate path content drift or escape")
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, AttributeError) as exc:
            issues.append({"code": "MATERIAL_INVALID", "message": str(exc)})
    return issues


def validate_manifest(manifest, *, base_dir=None):
    base = Path(base_dir or ".").resolve()
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("files"), list):
        return [{"code": "MATERIAL_INVALID", "message": "invalid material manifest"}]
    try:
        root = _validated_root(manifest.get("root"), base)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return [{"code": "MATERIAL_INVALID", "message": str(exc)}]
    return _check_files_in_root(manifest["files"], root, base)


def _dual_roots(manifest, base):
    originals = _validated_root(manifest.get("originals_root"), base)
    derived = _validated_root(manifest.get("derived_root"), base)
    if originals == derived or originals.is_relative_to(derived) or derived.is_relative_to(originals):
        raise ValueError("originals root and derived root must be disjoint non-nested directories")
    return originals, derived


def dual_hash_sets(manifest):
    """(original_hashes, derived_hashes) for a structurally-shaped dual manifest."""
    originals = {item["sha256"] for item in manifest.get("files", [])
                 if isinstance(item, dict) and isinstance(item.get("sha256"), str)}
    derived = {item["sha256"] for item in manifest.get("derived_files", [])
               if isinstance(item, dict) and isinstance(item.get("sha256"), str)}
    return originals, derived


def validate_dual_manifest(manifest, *, base_dir=None):
    """v2.0: read-only originals plus a separate derived root for agent outputs.

    Derived artifacts never masquerade as originals: roots are disjoint, roles and
    source bindings are declared, and every hash is recomputed from disk.
    """
    base = Path(base_dir or ".").resolve()
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != DUAL_MANIFEST_VERSION
            or not isinstance(manifest.get("files"), list) or not isinstance(manifest.get("derived_files"), list)):
        return [{"code": "MATERIAL_INVALID", "message": "invalid dual-root material manifest"}]
    try:
        originals, derived = _dual_roots(manifest, base)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return [{"code": "MATERIAL_INVALID", "message": str(exc)}]
    issues = _check_files_in_root(manifest["files"], originals, base)
    original_hashes, _ = dual_hash_sets(manifest)
    seen = set()
    for item in manifest["derived_files"]:
        try:
            digest = item["sha256"]
            if digest in seen:
                raise ValueError("duplicate derived content must reuse one entry")
            seen.add(digest)
            if digest in original_hashes:
                raise ValueError("derived artifact duplicates an original; copy-back is not a derivation")
            if item.get("role") not in DERIVED_ROLES:
                raise ValueError("derived role must be one of " + ", ".join(DERIVED_ROLES))
            if item.get("derived_id") != "sha256:" + digest:
                raise ValueError("derived identifier drift")
            relative = item.get("relative_path")
            if (not isinstance(relative, str) or not relative or "\\" in relative
                    or any(part in ("", ".", "..") for part in relative.split("/"))):
                raise ValueError("derived relative path must be canonical without traversal")
            candidate = Path(relative)
            if candidate.is_absolute() or candidate.drive or candidate.as_posix() != relative:
                raise ValueError("derived relative path must be canonical and relative")
            declared = Path(item["path"])
            if not isinstance(item.get("path"), str) or not item["path"].strip() or ".." in declared.parts:
                raise ValueError("derived primary path required without traversal")
            declared = declared if declared.is_absolute() else base / declared
            lexical = derived / candidate
            resolved = _safe_material(lexical)
            if not resolved.is_relative_to(derived) or not resolved.is_file():
                raise ValueError("derived path escapes derived root or is not a file")
            if (not declared.is_relative_to(derived)
                    or declared.relative_to(derived).as_posix() != relative
                    or declared != lexical or _safe_material(declared) != resolved):
                raise ValueError("derived primary path and relative_path must match within derived root")
            if file_hash(resolved) != digest or resolved.stat().st_size != item.get("size_bytes"):
                raise ValueError("derived hash or size drift")
            sources = item.get("sources")
            if (not isinstance(sources, list) or not sources
                    or any(not isinstance(source, str) or source not in original_hashes for source in sources)):
                raise ValueError("derived sources must be nonempty original material hashes")
            if not isinstance(item.get("generated_by"), str) or not item["generated_by"].strip():
                raise ValueError("derived generator identity required")
            if not isinstance(item.get("generated_at"), str) or not item["generated_at"].strip():
                raise ValueError("derived generation timestamp required")
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, AttributeError) as exc:
            issues.append({"code": "MATERIAL_INVALID", "message": str(exc)})
    return issues


def _canonical_relative(name):
    if (not isinstance(name, str) or not name or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError("derived relative name must be canonical without traversal")
    candidate = Path(name)
    if candidate.is_absolute() or candidate.drive or candidate.as_posix() != name:
        raise ValueError("derived relative name must be canonical and relative")
    return candidate


def register_derived(manifest_path, relative_name, payload, *, role, sources, generated_by):
    """Append one agent-generated artifact under the derived root and rebind the manifest."""
    from datetime import datetime, timezone
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DUAL_MANIFEST_VERSION:
        raise ValueError("register_derived requires a dual-root manifest")
    issues = validate_dual_manifest(manifest, base_dir=manifest_path.parent)
    if issues:
        raise ValueError("cannot extend drifted manifest: " + issues[0]["message"])
    if role not in DERIVED_ROLES:
        raise ValueError("derived role must be one of " + ", ".join(DERIVED_ROLES))
    candidate = _canonical_relative(relative_name)
    original_hashes, existing_derived = dual_hash_sets(manifest)
    if (not isinstance(sources, list) or not sources
            or any(not isinstance(source, str) or source not in original_hashes for source in sources)):
        raise ValueError("derived sources must be nonempty original material hashes")
    if not isinstance(generated_by, str) or not generated_by.strip():
        raise ValueError("derived generator identity required")
    declared_root = Path(manifest["derived_root"])
    derived_root = _safe_material(declared_root if declared_root.is_absolute() else manifest_path.parent / declared_root)
    target = _safe_material(derived_root / candidate)
    if not target.is_relative_to(derived_root) or target.exists():
        raise ValueError("derived target must stay inside derived root and be new")
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (bytes, bytearray)):
        target.write_bytes(payload)
    elif isinstance(payload, str):
        target.write_text(payload, encoding="utf-8")
    else:
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    digest = file_hash(target)
    if digest in original_hashes or digest in existing_derived:
        target.unlink()
        raise ValueError("derived content must not duplicate originals or existing derived entries")
    manifest["derived_files"].append({"derived_id": "sha256:" + digest, "role": role, "path": str(target),
                                      "relative_path": relative_name, "sha256": digest,
                                      "size_bytes": target.stat().st_size, "sources": list(sources),
                                      "generated_by": generated_by,
                                      "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return "sha256:" + digest


def _excel_value(cell):
    value = cell.value
    if value is None:
        return "", None
    if cell.data_type == "f":
        return None, "formula requires reviewed calculated value"
    if isinstance(value, bool):
        return "true" if value else "false", None
    if isinstance(value, (int, float)):
        # Numeric identifiers with a zero mask can be rendered without losing leading zeroes.
        if re.fullmatch(r"0+", cell.number_format or "") and isinstance(value, int):
            return str(value).zfill(len(cell.number_format)), None
        if isinstance(value, int) and abs(value) >= 10 ** 15:
            return None, "long numeric identifier may already have lost precision; text/review required"
        return str(value), "numeric cell: identifier interpretation requires review"
    if hasattr(value, "isoformat"):
        return value.isoformat(), None
    return str(value), None


def extract_structured(path):
    """Return located strings, never interpret raw files as reimbursement rows."""
    path = _safe_material(path)
    result = {"schema_version": "1.0", "source_path": str(path), "source_sha256": file_hash(path),
              "status": "PARSED", "cells": [], "issues": []}
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row_index, row in enumerate(csv.reader(stream), 1):
                for column, value in enumerate(row, 1):
                    result["cells"].append({"locator": f"row:{row_index}/column:{column}", "value": value})
    elif suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("openpyxl is required to read XLSX materials") from exc
        book = openpyxl.load_workbook(path, read_only=True, data_only=False)
        try:
            for sheet in book:
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is None:
                            continue
                        value, issue = _excel_value(cell)
                        locator = f"{sheet.title}!{cell.coordinate}"
                        result["cells"].append({"locator": locator, "value": value,
                                                "original_type": cell.data_type})
                        if issue:
                            result["issues"].append({"locator": locator, "message": issue})
        finally:
            book.close()
    elif suffix == ".json":
        # Reviewed extraction JSON is accepted as a separate auditable input.
        data = json.loads(path.read_text(encoding="utf-8"))
        if is_reviewed_extraction(data):
            result["issues"].extend(validate_reviewed_extraction(data, base_dir=path.parent))
        result["status"] = "STRUCTURED_JSON"
    else:
        result["status"] = "NEEDS_INPUT"
        result["issues"].append({"message": "PDF/image extraction requires reviewed structured JSON with original hash and page/region locators" if suffix in IMAGE_PDF else "unsupported material format"})
    if result["issues"]:
        result["status"] = "NEEDS_REVIEW" if result["cells"] else "NEEDS_INPUT"
    return result


def read_locator(path, locator, *, allow_numeric=False):
    """Resolve only precise machine-verifiable locators; ambiguous OCR text is rejected."""
    path = _safe_material(path)
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if is_reviewed_extraction(data):
            issues = validate_reviewed_extraction(data, base_dir=path.parent)
            if issues:
                raise ValueError(issues[0]["message"])
        return pointer_get(data, locator)
    if suffix == ".csv":
        match = re.fullmatch(r"row:([1-9]\d*)/column:([1-9]\d*)", locator)
        if not match:
            raise ValueError("CSV locator must be row:N/column:N (1-based)")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        return rows[int(match[1])-1][int(match[2])-1]
    if suffix == ".xlsx":
        import openpyxl
        if "!" not in locator:
            raise ValueError("XLSX locator must be Sheet!A1")
        sheet, coordinate = locator.rsplit("!", 1)
        if not re.fullmatch(r"[A-Z]+[1-9]\d*", coordinate):
            raise ValueError("single XLSX cell required")
        book = openpyxl.load_workbook(path, read_only=True, data_only=False)
        try:
            value, issue = _excel_value(book[sheet][coordinate])
            if issue and not (allow_numeric and issue.startswith("numeric cell:")):
                raise ValueError(issue + "; use reviewed structured extraction instead")
            return value
        finally:
            book.close()
    raise ValueError("use reviewed structured extraction JSON for PDF/image source locators")


def validate_reviewed_extraction(data, *, base_dir=None):
    """Bind reviewed OCR facts to original page/region; identities stay strings."""
    base = Path(base_dir or ".").resolve()
    issues = []
    if not isinstance(data, dict) or data.get("schema_version") != "1.0" or data.get("reviewed") is not True or not isinstance(data.get("reviewed_by"), str) or not data.get("reviewed_by", "").strip():
        return [{"code": "EXTRACTION_INVALID", "message": "reviewed extraction identity and schema required"}]
    try:
        source = Path(data["original_path"])
        source = _safe_material(source if source.is_absolute() else base / source)
        if file_hash(source) != data.get("original_sha256"):
            raise ValueError("reviewed extraction original hash drift")
        records = data["records"]
        if not isinstance(records, list) or not records:
            raise ValueError("reviewed extraction records required")
        seen = set()
        for record in records:
            if not isinstance(record.get("record_id"), str) or not record["record_id"].strip() or record["record_id"] in seen:
                raise ValueError("unique string record_id required")
            seen.add(record["record_id"])
            if not isinstance(record.get("fields"), dict) or not record["fields"]:
                raise ValueError("record fields required")
            for field in record["fields"].values():
                if not isinstance(field, dict) or not isinstance(field.get("value"), str) or not isinstance(field.get("locator"), str) or not field["locator"].strip():
                    raise ValueError("reviewed values must be strings with original page/region locators")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issues.append({"code": "EXTRACTION_INVALID", "message": str(exc)})
    return issues


def validate_value_proof(proof, expected, *, base_dir=None, monetary=False, material_hashes=None,
                         original_hashes=None, derived_hashes=None):
    """A corroborating statement is a located, hashed value, never an inline claim.

    Dual-root manifests (original_hashes + derived_hashes) require an explicit proof
    kind, and agent-generated derived artifacts can only corroborate as agent_reviewed.
    """
    dual = derived_hashes is not None
    try:
        if not isinstance(proof, dict) or set(proof) - {"kind", "path", "locator", "sha256"}:
            raise ValueError("invalid corroborating proof object")
        kind = proof.get("kind")
        if dual:
            if kind not in DUAL_PROOF_KINDS:
                raise ValueError("dual-root corroboration requires explicit kind " + "|".join(DUAL_PROOF_KINDS))
            if kind == "material" and original_hashes is not None and proof.get("sha256") not in original_hashes:
                raise ValueError("material corroboration must hash-match an original material")
            if kind == "user" and proof.get("sha256") in derived_hashes:
                raise ValueError("agent-generated derived artifacts cannot corroborate as user evidence")
            if kind == "agent_reviewed" and proof.get("sha256") not in derived_hashes:
                raise ValueError("agent_reviewed corroboration must hash-match a derived artifact")
        elif proof.get("kind", "user") not in ("material", "user"):
            raise ValueError("corroboration must be current material or user evidence")
        path = Path(proof["path"])
        path = _safe_material(path if path.is_absolute() else Path(base_dir or ".") / path)
        if file_hash(path) != proof.get("sha256"):
            raise ValueError("corroborating evidence hash drift")
        if path.suffix.lower() == ".json":
            contents = json.loads(path.read_text(encoding="utf-8"))
            if is_reviewed_extraction(contents):
                if dual:
                    if (contents.get("original_sha256") not in (original_hashes or set())
                            or proof.get("sha256") not in derived_hashes):
                        raise ValueError("reviewed proof must be a derived artifact binding an original of this manifest")
                elif material_hashes is not None:
                    if contents.get("original_sha256") not in material_hashes or proof.get("sha256") not in material_hashes:
                        raise ValueError("reviewed proof and its original must belong to same material manifest")
        if not isinstance(proof.get("locator"), str) or not proof["locator"].strip():
            raise ValueError("corroborating locator required")
        actual = read_locator(path, proof["locator"], allow_numeric=monetary)
        if (money(actual) != money(expected)) if monetary else (str(actual) != str(expected)):
            raise ValueError("corroborating value conflicts with planned value")
        return []
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        return [{"code": "SOURCE_CONFLICT", "message": str(exc)}]


def validate_image_documents(materials, manifest, plan, *, base_dir=None):
    """Explicit invoice identity, original binding and primary-row reconciliation.

    All PDFs/images are possible invoices until source-backed classification.
    This does not perform OCR, infer allowance rules or accept partial receipts.
    """
    from collections import defaultdict
    from decimal import Decimal
    base = Path(base_dir or ".").resolve()
    issues = []
    def bad(message, code="INVOICE_RECONCILIATION_INVALID"):
        issues.append({"code": code, "message": message})
    files = manifest.get("files", [])
    dual = isinstance(manifest, dict) and manifest.get("schema_version") == DUAL_MANIFEST_VERSION
    if dual:
        preflight = validate_dual_manifest(manifest, base_dir=base)
        if preflight:
            bad("dual manifest invalid: " + preflight[0]["message"], "MATERIAL_INVALID")
            return issues
    original_hashes, derived_hashes = dual_hash_sets(manifest) if dual else ({item["sha256"] for item in files}, set())
    derived_entries = {item["sha256"]: item for item in manifest.get("derived_files", [])} if dual else {}
    hashes = original_hashes | derived_hashes if dual else {item["sha256"] for item in files}
    originals = {item["sha256"] for item in files if Path(item["path"]).suffix.lower() in IMAGE_PDF}

    def proof_issues(proof, expected):
        if dual:
            return validate_value_proof(proof, expected, base_dir=base,
                                         original_hashes=original_hashes, derived_hashes=derived_hashes)
        return validate_value_proof(proof, expected, base_dir=base, material_hashes=hashes)
    documents = materials.get("image_documents", [])
    if not isinstance(documents, list):
        bad("image_documents must be an array")
        return issues
    declared, identities, allocations, exempt = set(), set(), defaultdict(lambda: Decimal(0)), set()
    rules = plan.get("amount_rules") if isinstance(plan.get("amount_rules"), dict) else {}
    tables = plan.get("tables") if isinstance(plan.get("tables"), dict) else {}
    from bpm.plan import load_type
    config = load_type(plan.get("document_type"))
    primary = config.get("primary_expense_table") or ("costs" if rules.get("costs") == "sum" and tables.get("costs") else "details")
    amount_field = config.get("tables", {}).get(primary, {}).get("amount_field", "cost")
    rows = tables.get(primary) if isinstance(tables.get(primary), list) else []
    allowed_pointers = {f"/tables/{primary}/{index}/fields/{amount_field}" for index, _ in enumerate(rows)}
    if documents and primary == "costs" and rules.get("cost_amount_semantics") != "line_total":
        bad("invoice reconciliation currently supports line_total costs only", "UNSUPPORTED_INVOICE_SEMANTICS")
    for document in documents:
        try:
            if not isinstance(document, dict):
                raise ValueError("image document object required")
            original_hash = document.get("original_sha256")
            if original_hash not in originals or original_hash in declared:
                raise ValueError("each PDF/image original must be classified exactly once by manifest hash")
            declared.add(original_hash)
            if document.get("kind") == "not_invoice":
                if set(document) != {"original_sha256", "kind", "reason", "proof"} or not isinstance(document.get("reason"), str) or not document["reason"].strip():
                    raise ValueError("not_invoice classification requires source-backed reason")
                errors = proof_issues(document["proof"], document["reason"])
                if errors:
                    raise ValueError(errors[0]["message"])
                continue
            if document.get("kind") != "invoice" or set(document) != {"original_sha256", "kind", "extraction_path", "extraction_sha256", "records"}:
                raise ValueError("invoice requires reviewed extraction and record reconciliations")
            path = Path(document["extraction_path"])
            path = _safe_material(path if path.is_absolute() else base / path)
            digest = file_hash(path)
            if digest != document.get("extraction_sha256") or digest not in hashes:
                raise ValueError("reviewed extraction hash must match same material manifest")
            if dual:
                entry = derived_entries.get(digest)
                if entry is None or entry.get("role") != "reviewed_extraction":
                    raise ValueError("dual-root invoices require a derived reviewed_extraction artifact")
                declared_root = Path(manifest["derived_root"])
                derived_root = _safe_material(declared_root if declared_root.is_absolute() else base / declared_root)
                if not path.is_relative_to(derived_root):
                    raise ValueError("dual-root extraction must live under the derived root")
            extraction = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_reviewed_extraction(extraction, base_dir=path.parent)
            if errors:
                raise ValueError(errors[0]["message"])
            if extraction.get("original_sha256") != original_hash:
                raise ValueError("reviewed extraction must bind this exact PDF/image original")
            records = {record["record_id"]: record for record in extraction["records"]}
            reconciliation = document["records"]
            if not isinstance(reconciliation, list) or any(not isinstance(item, dict) for item in reconciliation):
                raise ValueError("invoice record reconciliation array required")
            ids = [item.get("record_id") for item in reconciliation]
            if any(not isinstance(item, str) for item in ids) or len(set(ids)) != len(ids) or set(ids) != set(records):
                raise ValueError("every reviewed invoice record requires exactly one reconciliation")
            for item in reconciliation:
                fields = records[item["record_id"]]["fields"]
                invoice_number = fields.get("invoice_number", {}).get("value")
                invoice_code = fields.get("invoice_code", {}).get("value", "")
                if not isinstance(invoice_number, str) or not invoice_number.strip() or not isinstance(invoice_code, str):
                    raise ValueError("invoice_number must be an exact reviewed string")
                identity = (invoice_code, invoice_number)
                if identity in identities:
                    raise ValueError("duplicate invoice identity across scans or records")
                identities.add(identity)
                amount_fields = [fields[key]["value"] for key in ("amount", "total_amount") if key in fields]
                if not amount_fields or any(money(amount) != money(amount_fields[0]) for amount in amount_fields):
                    raise ValueError("one consistent reviewed invoice amount/total_amount required")
                amount = money(amount_fields[0])
                if "not_applicable" in item:
                    if set(item) != {"record_id", "not_applicable"}:
                        raise ValueError("invoice exclusion cannot also allocate")
                    excluded = item["not_applicable"]
                    if not isinstance(excluded, dict) or set(excluded) != {"reason", "proof"} or not isinstance(excluded.get("reason"), str) or not excluded["reason"].strip():
                        raise ValueError("invoice not_applicable requires source-backed reason")
                    errors = proof_issues(excluded["proof"], excluded["reason"])
                    if errors:
                        raise ValueError(errors[0]["message"])
                    continue
                assigned = item.get("allocations")
                if set(item) != {"record_id", "allocations"} or not isinstance(assigned, list) or not assigned:
                    raise ValueError("invoice needs primary-row allocations or explicit exclusion")
                subtotal, seen = Decimal(0), set()
                for allocation in assigned:
                    if not isinstance(allocation, dict) or set(allocation) != {"plan_pointer", "amount"}:
                        raise ValueError("allocation requires exact plan_pointer and amount")
                    pointer = allocation["plan_pointer"]
                    if not isinstance(pointer, str) or pointer not in allowed_pointers or pointer in seen:
                        raise ValueError("allocation must uniquely target current primary expense amount pointers")
                    seen.add(pointer)
                    allocated = money(allocation["amount"])
                    if allocated <= 0:
                        raise ValueError("positive invoice allocation required")
                    subtotal += allocated
                    allocations[pointer] += allocated
                if subtotal != amount:
                    raise ValueError("invoice allocations differ from reviewed total; partial reimbursement unsupported")
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            bad(str(exc))
    if declared != originals:
        bad("every PDF/image original needs reviewed invoice reconciliation or source-backed not_invoice classification", "NEEDS_INPUT")
    no_invoice_rows = materials.get("no_invoice_rows", [])
    if not isinstance(no_invoice_rows, list):
        bad("no_invoice_rows must be an array")
        no_invoice_rows = []
    for row in no_invoice_rows:
        try:
            if not isinstance(row, dict) or set(row) != {"plan_pointer", "reason", "proof"}:
                raise ValueError("no_invoice_rows require pointer, reason and proof")
            pointer = row["plan_pointer"]
            if not isinstance(pointer, str) or pointer not in allowed_pointers or pointer in exempt or pointer in allocations:
                raise ValueError("no-invoice reason must target unique, unallocated primary expense row")
            if not isinstance(row.get("reason"), str) or not row["reason"].strip():
                raise ValueError("source-backed no-invoice row reason required")
            errors = proof_issues(row["proof"], row["reason"])
            if errors:
                raise ValueError(errors[0]["message"])
            exempt.add(pointer)
        except (ValueError, TypeError, KeyError) as exc:
            bad(str(exc))
    for pointer, amount in allocations.items():
        try:
            if amount != money(pointer_get(plan, pointer)):
                bad("Excel/plan amount conflicts with reconciled invoice total at " + pointer, "INVOICE_AMOUNT_CONFLICT")
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            bad(str(exc))
    if set(allocations) | exempt != allowed_pointers:
        bad("all primary expense rows require invoice reconciliation or source-backed no_invoice_rows reason", "NEEDS_INPUT")
    return issues


def prepare_materials(directory, output_dir):
    output = Path(output_dir).resolve()
    root = Path(directory).resolve()
    if output.is_relative_to(root):
        raise ValueError("parsed output must be separate from original materials")
    manifest = inventory_materials(root)
    output.mkdir(parents=True, exist_ok=False)
    parsed = output / "parsed"
    parsed.mkdir()
    for item in manifest["files"]:
        result = extract_structured(item["path"])
        (parsed / (item["sha256"] + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def prepare_dual_materials(directory, output_dir):
    """v2.0 preparation: originals stay read-only; parsed extractions land in the derived root.

    Old single-root tasks are not migrated; callers opt in per task.
    """
    from datetime import datetime, timezone
    output = Path(output_dir).resolve()
    root = Path(directory).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output) or output == root:
        raise ValueError("derived output root must be disjoint from original materials")
    files = inventory_materials(root)["files"]
    output.mkdir(parents=True, exist_ok=False)
    (output / "parsed").mkdir()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    derived_files = []
    for item in files:
        result = extract_structured(item["path"])
        relative = "parsed/" + item["sha256"] + ".json"
        target = output / "parsed" / (item["sha256"] + ".json")
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        digest = file_hash(target)
        derived_files.append({"derived_id": "sha256:" + digest, "role": "parsed_extraction", "path": str(target),
                              "relative_path": relative, "sha256": digest, "size_bytes": target.stat().st_size,
                              "sources": [item["sha256"]], "generated_by": "bpm.materials.prepare_dual_materials",
                              "generated_at": stamp})
    manifest = {"schema_version": DUAL_MANIFEST_VERSION, "originals_root": str(root), "derived_root": str(output),
                "files": files, "derived_files": derived_files}
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path
