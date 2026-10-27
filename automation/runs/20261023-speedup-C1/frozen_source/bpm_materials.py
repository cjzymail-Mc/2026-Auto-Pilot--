"""Read-only material inventory and structured extraction; never uploads files."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from bpm_plan import file_hash, money, pointer_get

IMAGE_PDF = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}


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


def validate_manifest(manifest, *, base_dir=None):
    base = Path(base_dir or ".").resolve()
    issues, seen, seen_paths = [], set(), set()
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0" or not isinstance(manifest.get("files"), list):
        return [{"code": "MATERIAL_INVALID", "message": "invalid material manifest"}]
    try:
        if not isinstance(manifest.get("root"), str) or not manifest["root"].strip():
            raise ValueError("manifest root must be a nonempty directory path")
        root_path = Path(manifest["root"])
        root = _safe_material(root_path if root_path.is_absolute() else base / root_path)
        if not root.is_dir():
            raise ValueError("manifest root must be an existing directory")
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        return [{"code": "MATERIAL_INVALID", "message": str(exc)}]

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

    for item in manifest["files"]:
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


def validate_value_proof(proof, expected, *, base_dir=None, monetary=False, material_hashes=None):
    """A corroborating statement is a located, hashed value, never an inline claim."""
    try:
        if not isinstance(proof, dict) or set(proof) - {"kind", "path", "locator", "sha256"}:
            raise ValueError("invalid corroborating proof object")
        if proof.get("kind", "user") not in ("material", "user"):
            raise ValueError("corroboration must be current material or user evidence")
        path = Path(proof["path"])
        path = _safe_material(path if path.is_absolute() else Path(base_dir or ".") / path)
        if file_hash(path) != proof.get("sha256"):
            raise ValueError("corroborating evidence hash drift")
        if path.suffix.lower() == ".json":
            contents = json.loads(path.read_text(encoding="utf-8"))
            if is_reviewed_extraction(contents) and material_hashes is not None:
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
    hashes = {item["sha256"] for item in files}
    originals = {item["sha256"] for item in files if Path(item["path"]).suffix.lower() in IMAGE_PDF}
    documents = materials.get("image_documents", [])
    if not isinstance(documents, list):
        bad("image_documents must be an array")
        return issues
    declared, identities, allocations, exempt = set(), set(), defaultdict(lambda: Decimal(0)), set()
    rules = plan.get("amount_rules") if isinstance(plan.get("amount_rules"), dict) else {}
    tables = plan.get("tables") if isinstance(plan.get("tables"), dict) else {}
    primary = "costs" if rules.get("costs") == "sum" and tables.get("costs") else "details"
    rows = tables.get(primary) if isinstance(tables.get(primary), list) else []
    allowed_pointers = {f"/tables/{primary}/{index}/fields/cost" for index, _ in enumerate(rows)}
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
                errors = validate_value_proof(document["proof"], document["reason"], base_dir=base, material_hashes=hashes)
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
                    errors = validate_value_proof(excluded["proof"], excluded["reason"], base_dir=base, material_hashes=hashes)
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
            errors = validate_value_proof(row["proof"], row["reason"], base_dir=base, material_hashes=hashes)
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
