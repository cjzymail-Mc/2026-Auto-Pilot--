"""Exact, read-only template snapshots from captured history or observed GETs.

No credentials or arbitrary response bodies are exported. Cached snapshots are
explicitly marked cached; neither this module nor task preparation creates forms.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bpm_plan import file_hash, load_type
from stage1_browser_probe import HOST, LIST_PATH, assert_internal

CHILDREN = ("details", "costs", "relations", "banks", "products", "detailrels")
API_ORIGIN = "https://oa.api.qiaodan.com"
UUID_RE = re.compile(r"(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})\Z")


def _uuid(value):
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise ValueError("exact server UUID required")
    return value.replace("-", "").lower()


def _read_json(body):
    return json.loads(body, parse_float=Decimal)


def _scalars(obj, allowed):
    out = {}
    for key in allowed:
        value = obj.get(key)
        if value is not None and isinstance(value, (str, int, bool, Decimal)):
            # API numbers retain exact decimal representation. Identifiers must
            # already be strings; never reconstruct leading zeros from numbers.
            out[key] = str(value) if isinstance(value, Decimal) else value
    return out


def normalize_template(number, main, children, source):
    if not isinstance(number, str) or not re.fullmatch(r"\d+", number):
        raise ValueError("full template number must be a digit string")
    if not isinstance(main, dict) or main.get("bizNumber") != number:
        raise ValueError("template full number mismatch")
    uid = _uuid(main.get("id"))
    config = load_type("travel")
    tables = {}
    extra = {
        "detailrels": ("bizTypeName", "bizNo", "bizDetailCost", "bizDetailNum", "usedCost", "cost"),
        "products": ("productName", "num", "price", "cost", "description"),
    }
    for key in CHILDREN:
        rows = children.get(key)
        if not isinstance(rows, list):
            raise ValueError("missing or incomplete template subtable: " + key)
        allowed = config["tables"][key]["columns"] if key in config["tables"] else extra[key]
        safe_rows = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or _uuid(row.get("reimburseId")) != uid:
                raise ValueError("child row does not belong to exact template: " + key)
            safe_rows.append({"row_id": f"template-{key}-{index + 1}", "fields": _scalars(row, allowed)})
        tables[key] = safe_rows
    return {
        "schema_version": "1.0", "biz_number": number, "uuid": uid,
        "captured_at": datetime.now(timezone.utc).isoformat(), "source": source,
        "representation": "observed_api_values_codes_require_current_display_resolution",
        "applicant": _scalars(main, ("appliedName", "appliedDeptName", "corpCode", "appliedBy")),
        "header": _scalars(main, tuple(config["header"]) + ("bizStatus", "createdName", "createdBy")),
        "tables": tables,
    }


def cached_template(census_path, number):
    path = Path(census_path).resolve()
    if any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in path.parts):
        raise ValueError("protected source")
    corpus = json.loads(path.read_text(encoding="utf-8"))
    docs = corpus.get("docs") if isinstance(corpus, dict) else None
    if not isinstance(docs, list):
        raise ValueError("not a captured census artifact")
    hits = [doc for doc in docs if doc.get("bizNumber") == number]
    if len(hits) != 1:
        raise ValueError("full template number must identify exactly one cached document")
    doc = hits[0]
    if doc.get("fetch", {}).get("status") != 200:
        raise ValueError("template main read incomplete")
    children = {}
    for key in CHILDREN:
        captured = doc.get("children", {}).get(key, {})
        if captured.get("status") != 200:
            raise ValueError("template child read incomplete: " + key)
        children[key] = _read_json(captured["body"])
    return normalize_template(number, _read_json(doc["fetch"]["body"]), children,
                              {"kind": "cached", "path": str(path), "sha256": file_hash(path)})


def _find_list_filter(page):
    # The list uses a different filter form: BizNumber1 is 单据编号,
    # BizNumber22 is 关联单号. The associated label is observed in list.html.
    loc = page.get_by_label("单据编号", exact=True)
    if loc.count() != 1:
        raise ValueError("exact full-number list filter not observed uniquely")
    return loc


def parse_list_items(body):
    """Observed JSON list wrappers only; reject ambiguous or malformed payloads.

    Kept here so live discovery and cached replay use the same frozen parser,
    without importing the broader historical census/query executors.
    """
    value = json.loads(body)
    wrappers = ("content", "data", "items", "rows", "list", "result", "records")
    for _ in range(3):
        if isinstance(value, list):
            if any(not isinstance(item, dict) for item in value):
                raise ValueError("list response contains malformed rows")
            return value
        if not isinstance(value, dict):
            break
        candidates = [value[key] for key in wrappers if isinstance(value.get(key), (dict, list))]
        if len(candidates) != 1:
            raise ValueError("list response wrapper not unique")
        value = candidates[0]
    raise ValueError("observed list response wrapper missing")


def exact_list_item(items, number):
    if not isinstance(number, str) or not re.fullmatch(r"\d+", number):
        raise ValueError("full document number must remain a digit string")
    matches = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("malformed list row")
        if item.get("bizNumber") == number:
            matches[_uuid(item.get("id"))] = item
    if len(matches) != 1:
        raise ValueError("full document number does not identify exactly one UUID")
    return next(iter(matches.values()))


def _target_list(probe, number):
    """Apply an exact full-number query and retain only its matching list item.

    The application may use POST for read-only query forms. This function only
    clicks the already observed 查询 UI; it never issues a write request itself.
    Response auth headers stay in this local function's memory.
    """
    if not isinstance(number, str) or not re.fullmatch(r"\d+", number):
        raise ValueError("full document number required")
    captured = []
    page = probe.page
    def on_response(response):
        parsed = urlsplit(response.url)
        if (parsed.scheme == "https" and parsed.netloc == "oa.api.qiaodan.com"
                and re.fullmatch(r"/reimburse/query/\d+/\d+", parsed.path)
                and response.status == 200):
            captured.append(response)
    page.on("response", on_response)
    try:
        page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("th.prop-submitType", timeout=30000)
        _find_list_filter(page).fill(number)
        buttons = page.get_by_role("button", name="查询", exact=True)
        if buttons.count() != 1:
            raise ValueError("exact 查询 button not unique")
        probe._click_guard("查询")
        captured.clear()
        buttons.click(timeout=8000)
        page.wait_for_timeout(1500)
        for _ in range(10):
            if captured:
                break
            page.wait_for_timeout(600)
        matches, headers = [], None
        for response in captured:
            for item in parse_list_items(response.text()):
                if item.get("bizNumber") == number:
                    matches.append(item)
                    headers = {k: v for k, v in response.request.headers.items()
                               if k.lower() not in ("cookie", "content-length", "host")}
        item = exact_list_item(matches, number)
        if not headers:
            raise ValueError("exact template list lookup not unique or not complete")
        return item, headers
    finally:
        page.remove_listener("response", on_response)


def fetch_template(probe, number):
    item, headers = _target_list(probe, number)
    uid = _uuid(item["id"])
    def get(path):
        # Endpoints witnessed by children_probe; no guesses using business number.
        response = probe.ctx.request.get(API_ORIGIN + path, headers=headers, timeout=20000)
        if response.status != 200:
            raise ValueError("read-only template fetch incomplete")
        return _read_json(response.text())
    main = get("/reimburse/" + uid)
    children = {key: get(f"/reimburse/{key}/{uid}") for key in CHILDREN}
    probe.log_event(event="exact_template_read", child_counts={k: len(v) for k, v in children.items()},
                    source="observed_get", header_names=sorted(headers))
    return normalize_template(number, main, children, {"kind": "live", "endpoint_family": "observed_reimburse_uuid_get"})


def open_exact_document(probe, number, expected_uuid=None):
    item, _ = _target_list(probe, number)
    uid = _uuid(item["id"])
    if expected_uuid is not None and uid != _uuid(expected_uuid):
        raise ValueError("saved number and UUID do not identify the same record")
    # This exact read route was observed in children_probe, not inferred from a
    # write endpoint. The form collector still verifies identity after navigation.
    return assert_internal(HOST + "/oa/reimburse?type=view&id=" + uid)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read an exact BPM history template; never creates a form")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--census", help="read an existing captured history artifact")
    mode.add_argument("--live", action="store_true", help="targeted read-only UI/GET lookup (same profile lock)")
    parser.add_argument("--template-number", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expect-name", help="required for live identity verification")
    parser.add_argument("--login-wait", type=float, default=480)
    args = parser.parse_args(argv)
    out = Path(args.output).resolve()
    root = Path(__file__).resolve().parent / "automation" / "runs"
    if not out.is_relative_to(root) or out.exists():
        parser.error("output must be a new file beneath automation/runs")
    try:
        if args.live:
            if not args.expect_name or not 0 <= args.login_wait < float("inf"):
                parser.error("live read requires --expect-name and finite nonnegative login wait")
            if out.parent.parent != root or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", out.parent.name):
                parser.error("live output must be automation/runs/<simple-run-id>/<new-file>.json")
            snapshot = live_template(args.template_number, args.expect_name, out.parent.name, args.login_wait)
        else:
            snapshot = cached_template(args.census, args.template_number)
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "NEEDS_INPUT", "phase": "template_read", "reason": str(exc)}, ensure_ascii=False))
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "TEMPLATE_SNAPSHOT_READY", "path": str(out), "sha256": file_hash(out)}, ensure_ascii=False))
    return 0


def live_template(number, expected_operator, run, login_wait=480):
    """Dedicated read-only context; never navigates or closes restored forms.

    The same executor lock protects the shared credential file. Browser storage
    injection is in memory; credentials are never exported to task artifacts.
    """
    from types import SimpleNamespace
    from stage1_browser_probe import Probe, PASS
    class ReadOnlyProbe(Probe):
        def login_state(self, page):
            from bpm_ui import observed_operator
            state, marks, evidence = super().login_state(page)
            if state == "LOGGED_IN" and observed_operator(page) != self.args.expect_name:
                return "UNKNOWN", marks, evidence
            return state, marks, evidence

        def _launch(self):
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            browser = self._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
            self.ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
            self._inject_session_state()
            self.page = self.ctx.new_page()
            self.page.set_default_timeout(45000)
    p = ReadOnlyProbe(SimpleNamespace(run=run, doc_id=number, expect_name=expected_operator,
                                     tech_budget=1800, login_wait=login_wait, wall_cap=2400,
                                     fill_plan=None, keep_open_minutes=0))
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("exact template read requires verified login")
        p._save_session_state()
        snapshot = fetch_template(p, number)
        p.save("template_snapshot.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
        reason = "SUCCESS_TEMPLATE_READ_ONLY"
        return snapshot
    finally:
        p.result["finish_reason"] = reason
        p.atomic_result()
        p.log_event(event="template_read_end", status=reason)
        p._close_browser()
        p.release_lock()
        p.budget.close()


if __name__ == "__main__":
    sys.exit(main())
