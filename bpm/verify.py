"""Independent, fail-closed comparison of a plan with a fresh form snapshot.

Snapshots must be collected from the page again, never assembled from write results.
This module has no browser or OA write capability.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse
from bpm.paths import ROOT

TABLES = ("relations", "details", "costs", "banks")
MONEY = {"cost", "price", "totalCost", "nowCost", "bizCost", "loanCost", "payCost",
         "quitCost", "taxCost", "realCost", "detCost", "reimedCost",
         "totalReimedCost", "currencyTotalCost", "budgetUseCost"}
NUMBERS = MONEY | {"count", "exchangeRate"}
DATES = {"startDate", "endDate"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def decimal(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("not a decimal")
    displayed = str(value)
    if "," in displayed:
        # DOM numeric controls may render thousands separators. Accept only
        # complete three-digit groups, never strip punctuation from arbitrary
        # text. Identity/account properties never call this numeric helper.
        if not re.fullmatch(r"[+-]?[1-9][0-9]{0,2}(?:,[0-9]{3})+(?:\.[0-9]+)?", displayed):
            raise ValueError("invalid grouped decimal")
        displayed = displayed.replace(",", "")
    try:
        result = Decimal(displayed)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("not a decimal") from None
    if not result.is_finite():
        raise ValueError("not a finite decimal")
    return result


def _equal(prop, wanted, actual):
    """Only field-scoped display normalizations; no substring/fuzzy matching."""
    if prop in NUMBERS:
        try:
            return decimal(wanted) == decimal(actual)
        except ValueError:
            return False
    if prop in DATES:
        # Only midnight date displays can be represented by an ISO calendar day.
        def day(value):
            if not isinstance(value, str):
                return None
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                try:
                    return datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return None
            try:
                date = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if date.hour == date.minute == date.second == date.microsecond == 0:
                    return date.date()
            except ValueError:
                pass
            return None
        return day(wanted) is not None and day(wanted) == day(actual)
    return type(wanted) is type(actual) and wanted == actual


values_equal = _equal


def verify_snapshot(plan, snapshot, phase="before_save", base_dir=None, existing_identity=None):
    """Return evidence of all fields, row associations/counts and amount closure.

    Plan rows and freshly observed rows are compared in their visible order. A
    moved row is rejected rather than rematched across rows, which could hide a
    wrong bank/amount or related-document association.
    """
    from bpm.plan import plan_hash, validate_plan, load_type
    issues = []
    checks = {"counts": {}, "amounts": {}}
    try:
        bound_hash = plan_hash(plan)
    except (TypeError, ValueError):
        bound_hash = None
        issues.append({"code": "PLAN_HASH_INVALID", "path": "/"})
    try:
        issues.extend(validate_plan(plan, verify_sources=True, base_dir=base_dir))
    except (ValueError, TypeError, OSError) as exc:
        issues.append({"code": "PLAN_INVALID", "message": str(exc)})
    if issues:
        try:
            snapshot_hash = digest(snapshot)
        except (ValueError, TypeError):
            snapshot_hash = None
        return {"ok": False, "issues": issues, "plan_hash": bound_hash,
                "snapshot_hash": snapshot_hash, **checks}
    config = load_type(plan["document_type"])
    business_tables = tuple(config["tables"])
    def issue(code, path):
        issues.append({"code": code, "path": path})
    if phase not in ("before_save", "after_save", "before_revision"):
        issue("INVALID_PHASE", "/phase")
    if not isinstance(snapshot, dict):
        snapshot = {}
        issue("SNAPSHOT_INVALID", "/")
    page = snapshot.get("page", {})
    if not isinstance(page, dict):
        page = {}
    parsed = urlparse(str(page.get("url", "")))
    query = parse_qs(parsed.query)
    if (parsed.scheme != "https" or parsed.hostname != "bpm.qiaodan.com"
            or parsed.path != "/oa/reimburse"
            or query.get("type") != [{"before_save": "new", "before_revision": "edit"}.get(phase, "view")]):
        issue("WRONG_PAGE", "/page/url")
    if page.get("operator") != plan.get("operator"):
        issue("OPERATOR_MISMATCH", "/page/operator")
    template = plan.get("template", {})
    if phase == "before_revision":
        expected = existing_identity if isinstance(existing_identity, dict) else {}
        if (set(expected) != {"uuid", "biz_number", "status"}
                or expected.get("status") != "编制中"
                or any(page.get(key) != expected.get(key) for key in ("uuid", "biz_number", "status"))):
            issue("EXISTING_DRAFT_IDENTITY_MISMATCH", "/page")
    if phase == "before_save":
        if (page.get("is_new") is not True or page.get("biz_number") not in ("", None)
                or query.get("id")):
            issue("NOT_NEW_UNSAVED_PAGE", "/page")
    else:
        if page.get("is_new") is not False:
            issue("NOT_PERSISTED_PAGE", "/page/is_new")
        number = page.get("biz_number")
        uid = page.get("uuid")
        if not isinstance(number, str) or not re.fullmatch(r"\d{8,}", number) or number == template.get("biz_number"):
            issue("NEW_NUMBER_UNPROVEN", "/page/biz_number")
        if not isinstance(uid, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", uid):
            issue("NEW_UUID_UNPROVEN", "/page/uuid")
        if query.get("id") != [uid]:
            issue("REOPEN_URL_IDENTITY_MISMATCH", "/page/url")
        try:
            from pathlib import Path
            path = Path(template.get("snapshot_path", ""))
            path = path if path.is_absolute() else Path(base_dir or ROOT) / path
            historical = json.loads(path.read_text(encoding="utf-8"))
            historical_page = historical.get("page", historical.get("header", historical))
            historical_uuid = historical.get("uuid", historical.get("id")) or historical_page.get("uuid", historical_page.get("id"))
            if not isinstance(historical_uuid, str) or not re.fullmatch(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", historical_uuid):
                issue("TEMPLATE_UUID_UNPROVEN", "/template/snapshot_path")
            elif uid.replace("-", "").lower() == historical_uuid.replace("-", "").lower():
                issue("TEMPLATE_UUID_REUSED", "/page/uuid")
        except (OSError, TypeError, ValueError, AttributeError):
            issue("TEMPLATE_IDENTITY_UNREADABLE", "/template/snapshot_path")
        if page.get("status") != "编制中":
            issue("UNSUBMITTED_STATUS_UNPROVEN", "/page/status")
    observed = snapshot.get("observed_at")
    if not isinstance(observed, str) or not observed:
        issue("OBSERVATION_TIME_MISSING", "/observed_at")
    if "validation" in snapshot:
        validity = snapshot["validation"]
        if (not isinstance(validity, dict)
                or not isinstance(validity.get("invalid_fields"), list)
                or type(validity.get("pending")) is not bool):
            issue("VALIDATION_READBACK_INVALID", "/validation")
        else:
            if validity["invalid_fields"]:
                issue("FORM_REQUIRED_OR_INVALID_FIELDS", "/validation/invalid_fields")
            if validity["pending"]:
                issue("FORM_VALIDATION_PENDING", "/validation/pending")
    complete = snapshot.get("completeness", {})
    if not isinstance(complete, dict):
        complete = {}
    for section in ("header",) + business_tables:
        if complete.get(section) is not True:
            issue("INCOMPLETE_READBACK", "/completeness/" + section)
    applicant = snapshot.get("applicant", {})
    if not isinstance(applicant, dict):
        applicant = {}
    for prop in ("name", "company", "department"):
        if not _equal(prop, plan.get("applicant", {}).get(prop), applicant.get(prop)):
            issue("APPLICANT_MISMATCH", "/applicant/" + prop)
    header = snapshot.get("header", {})
    if not isinstance(header, dict):
        header = {}
        issue("HEADER_INVALID", "/header")
    if not header.get("submitType"):
        issue("EMPTY_SUBMIT_TYPE", "/header/submitType")
    for planned_key, observed_key in (("applicant_employee_id", "appliedBy"),
                                       ("creator_name", "createdName"),
                                       ("creator_department", "createdDeptName")):
        if "identity" in plan and header.get(observed_key) != plan["identity"][planned_key]:
            issue("PERSON_IDENTITY_MISMATCH", "/header/" + observed_key)
    for prop, value in plan.get("header", {}).items():
        if prop not in header or not _equal(prop, value, header[prop]):
            issue("VALUE_MISMATCH", "/header/" + prop)
    actual_tables = snapshot.get("tables", {})
    if not isinstance(actual_tables, dict):
        actual_tables = {}
    for table in business_tables:
        wanted_rows = plan.get("tables", {}).get(table, [])
        actual_rows = actual_tables.get(table)
        if not isinstance(actual_rows, list):
            issue("TABLE_MISSING", "/tables/" + table)
            actual_rows = []
        checks["counts"][table] = {"expected": len(wanted_rows), "actual": len(actual_rows)}
        if len(actual_rows) != len(wanted_rows):
            issue("ROW_COUNT_MISMATCH", "/tables/" + table)
        seen = set()
        for index, row in enumerate(actual_rows):
            fields = row.get("fields") if isinstance(row, dict) else None
            if not isinstance(fields, dict):
                issue("ROW_INVALID", f"/tables/{table}/{index}")
                continue
            if plan["document_type"] != "travel":
                table_config = config["tables"][table]
                extra_rules = table_config.get("readback_extra_fields", {})
                metadata = row.get("field_metadata", {})
                for prop in set(fields) - set(table_config["columns"]):
                    rule = extra_rules.get(prop)
                    if rule == "empty" and fields[prop] == "":
                        continue
                    if rule == "readonly_money":
                        try:
                            if not isinstance(metadata, dict) or metadata.get(prop, {}).get("readonly") is not True:
                                raise ValueError("unproven system echo")
                            decimal(fields[prop])  # Budget balances are system observations, not expense amounts.
                            continue
                        except (ValueError, TypeError, AttributeError):
                            pass
                    issue("UNMODELED_BUSINESS_FIELD", f"/tables/{table}/{index}/fields/{prop}")
            # Identical visible business rows cannot establish unique association.
            fingerprint = digest(fields)
            if fingerprint in seen:
                issue("DUPLICATE_ROW", f"/tables/{table}/{index}")
            seen.add(fingerprint)
            if index < len(wanted_rows):
                for prop, value in wanted_rows[index].get("fields", {}).items():
                    if prop not in fields or not _equal(prop, value, fields[prop]):
                        issue("VALUE_MISMATCH", f"/tables/{table}/{index}/fields/{prop}")
    # Non-projected business tables (products, loan lines, detail allocations)
    # must be empty, even when the writer never touched them.
    extra = snapshot.get("extra_tables", {})
    projections = load_type(plan.get("document_type")).get("extra_table_projections", {})
    if plan.get("tables", {}).get("relations") and "detailrels" in projections:
        if not isinstance(extra, dict) or "detailrels" not in extra or complete.get("detailrels") is not True:
            issue("INCOMPLETE_RELATION_DETAIL_READBACK", "/extra_tables/detailrels")
    if not isinstance(extra, dict):
        issue("EXTRA_TABLES_INVALID", "/extra_tables")
    else:
        # Declared projections are mandatory observations, including empty
        # observations. Completeness alone never proves the expected rows exist.
        for key, projection in projections.items():
            projected = plan.get("tables", {}).get(projection["from_table"], [])
            rows = extra.get(key)
            if not isinstance(rows, list):
                issue("PROJECTION_TABLE_MISSING_OR_INVALID", "/extra_tables/" + key)
            elif len(rows) != len(projected):
                issue("PROJECTION_ROW_COUNT_MISMATCH", "/extra_tables/" + key)
        for key, rows in extra.items():
            projection = projections.get(key)
            if not projection or not isinstance(rows, list):
                if rows or not isinstance(rows, list):
                    issue("UNMODELED_BUSINESS_ROWS", "/extra_tables/" + key)
                continue
            projected = plan.get("tables", {}).get(projection["from_table"], [])
            if len(rows) != len(projected):
                continue
            for index, row in enumerate(rows):
                fields = row.get("fields", row) if isinstance(row, dict) else {}
                if not isinstance(fields, dict):
                    issue("PROJECTION_ROW_INVALID", f"/extra_tables/{key}/{index}")
                    continue
                if fields.get("bizTypeName") not in projection.get("supported_relation_types", ["公出单", "出差单"]):
                    issue("UNSUPPORTED_RELATION_DETAIL_BRANCH", f"/extra_tables/{key}/{index}")
                for observed_prop, planned_prop in projection["fields"].items():
                    if observed_prop not in fields or not _equal(planned_prop, projected[index]["fields"].get(planned_prop), fields[observed_prop]):
                        issue("PROJECTION_VALUE_MISMATCH", f"/extra_tables/{key}/{index}/{observed_prop}")
                for prop in projection.get("zero_fields", []):
                    try:
                        rule = projection.get("system_field_rules", {}).get(prop, {})
                        metadata = row.get("field_metadata", {}) if isinstance(row, dict) else {}
                        metadata = metadata if isinstance(metadata,dict) else {}
                        field_meta = metadata.get(prop,{})
                        field_meta = field_meta if isinstance(field_meta,dict) else {}
                        if (prop in fields and fields[prop] == ""
                                and rule.get("empty_display") == "readonly_zero"
                                and fields.get("bizTypeName") in rule.get("relation_types", [])
                                and field_meta.get("readonly") is True):
                            # A scoped display rule, not numeric coercion. Raw
                            # observations remain empty in the snapshot/hash.
                            continue
                        if decimal(fields[prop]) != 0:
                            raise ValueError("nonzero")
                    except (ValueError, KeyError):
                        issue("UNSUPPORTED_DETAIL_ALLOCATION", f"/extra_tables/{key}/{index}/{prop}")
    for key in set(actual_tables) - set(business_tables):
        if actual_tables[key]:
            issue("UNMODELED_BUSINESS_ROWS", "/tables/" + key)
    for key, value in header.items():
        if "loan" in key.lower() or "借款" in key:
            try:
                if decimal(value) != 0:
                    issue("UNSUPPORTED_LOAN", "/header/" + key)
            except ValueError:
                issue("LOAN_AMOUNT_UNREADABLE", "/header/" + key)
    try:
        total = decimal(header["totalCost"])
        def summation(table, multiply=False):
            result = Decimal(0)
            for row in actual_tables[table]:
                fields = row["fields"]
                amount = decimal(fields["cost"])
                if multiply:
                    amount *= decimal(fields["count"])
                result += amount
            return result
        for table in ("details", "banks"):
            amount = summation(table)
            checks["amounts"][table] = str(amount)
            if amount != total:
                issue("AMOUNT_NOT_CLOSED", "/tables/" + table)
        if "products" in business_tables:
            amount = sum((decimal(r["fields"]["price"]) for r in actual_tables["products"]), Decimal(0))
            checks["amounts"]["products"] = str(amount)
            if amount != total:
                issue("AMOUNT_NOT_CLOSED", "/tables/products")
        rules = plan.get("amount_rules", {})
        if rules.get("costs") == "sum":
            amount = summation("costs", rules.get("cost_amount_semantics") == "unit_price_times_count")
            checks["amounts"]["costs"] = str(amount)
            if amount != total:
                issue("AMOUNT_NOT_CLOSED", "/tables/costs")
        elif rules.get("costs") == "not_applicable":
            if actual_tables.get("costs"):
                issue("NOT_APPLICABLE_HAS_ROWS", "/tables/costs")
        else:
            issue("COST_RULE_MISSING", "/amount_rules/costs")
        checks["amounts"]["total"] = str(total)
    except (ValueError, KeyError, TypeError):
        issue("AMOUNT_UNREADABLE", "/tables")
    return {"ok": not issues, "issues": issues, "plan_hash": bound_hash,
            "snapshot_hash": digest(snapshot), **checks}
