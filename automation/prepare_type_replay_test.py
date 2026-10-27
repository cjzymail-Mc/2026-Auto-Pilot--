"""Prepare explicit, authorized historical-replay UI tests. Never saves a form."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bpm.plan import file_hash, validate_plan, plan_hash, load_type
from bpm.materials import inventory_materials


def read_authorization(path):
    path = Path(path).resolve()
    if any(x.lower() in {".pw-profile", ".git", "legacy-ia2"} for x in path.parts):
        raise ValueError("protected authorization path")
    auth = json.loads(path.read_text(encoding="utf-8"))
    if not all(auth.get(k) is True for k in ("allow_history_replay", "allow_new_unsaved_test_pages", "allow_fill")):
        raise ValueError("explicit historical replay/new unsaved test authorization required")
    if auth.get("allow_save") is not False or auth.get("allow_submit") is not False:
        raise ValueError("this test utility forbids save and submit")
    return path, auth


def capture_defaults(auth_path, run, *, inspect_category=None, inspect_product_add=False):
    from bpm.browser_probe import Probe, HOST, NEW_FORM_PATH, PASS, FORM_MAP_JS, TABLE_MAP_JS, assert_internal
    from bpm.ui import observed_operator, _prop, ROWS_JS
    _, auth = read_authorization(auth_path)
    class DefaultProbe(Probe):
        def _launch(self):
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self.browser = self._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
            self.ctx = self.browser.new_context(ignore_https_errors=True, viewport={"width": 1440, "height": 900})
            self._inject_session_state()
            self.page = self.ctx.new_page()
        def login_state(self, page):
            state, marks, evidence = super().login_state(page)
            if state == "LOGGED_IN" and observed_operator(page) != self.args.expect_name:
                return "UNKNOWN", marks, evidence
            return state, marks, evidence
    p = DefaultProbe(SimpleNamespace(run=run, doc_id="", expect_name=auth["operator"],
        tech_budget=600, login_wait=60, wall_cap=900, fill_plan=None, keep_open_minutes=0))
    p.acquire_lock()
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            raise ValueError("verified login required")
        p._save_session_state()
        p.page.goto(assert_internal(HOST + NEW_FORM_PATH), wait_until="domcontentloaded", timeout=45000)
        for _ in range(50):
            fields = p.page.evaluate(FORM_MAP_JS)
            header = {_prop(f.get("name")): f.get("value", "") for f in fields if _prop(f.get("name"))}
            mapped = p.page.evaluate(TABLE_MAP_JS)
            if header.get("appliedName") and any(t.get("title") == "报销明细" for t in mapped):
                break
            p.page.wait_for_timeout(600)
        else:
            raise ValueError("default new-form identity not loaded")
        if observed_operator(p.page) != auth["operator"] or header.get("bizNumber"):
            raise ValueError("not this operator's blank unsaved new form")
        if inspect_category:
            from bpm.ui import StructuredProbe
            p._pick_option = StructuredProbe._pick_option.__get__(p, type(p))
            candidates = [f for f in fields if _prop(f.get("name")) == "submitType"]
            if len(candidates) != 1:
                raise ValueError("category control is not unique")
            label = load_type(inspect_category)["header"]["submitType"]["allowed_values"][0]
            status, _, _ = p._ng_write(p.page, p.page.main_frame, candidates[0], label)
            if status != "OK": raise ValueError("category selection failed")
            p.page.wait_for_timeout(1200)
            fields = p.page.evaluate(FORM_MAP_JS)
            header = {_prop(f.get("name")): f.get("value", "") for f in fields if _prop(f.get("name"))}
            if header.get("submitType") != label: raise ValueError("category echo differs")
            mapped = p.page.evaluate(TABLE_MAP_JS)
            if inspect_product_add:
                inspect_product_controls(p)
                fields = p.page.evaluate(FORM_MAP_JS)
                mapped = p.page.evaluate(TABLE_MAP_JS)
        observation = {"kind": "authorized_blank_test_default_observation", "operator": auth["operator"],
            "applicant": {"name": header["appliedName"], "company": header["corpCode"], "department": header["appliedDeptName"]},
            "header": header, "header_fields": fields,
            "tables": [{"title": t["title"], "headers": t["headers"], "rows": p.page.evaluate(ROWS_JS, t)}
                       for t in mapped if t.get("title") not in ("确认人", "审批记录")],
            "observed_at": datetime.now(timezone.utc).isoformat(), "fields_written": int(bool(inspect_category)),
            "product_rows_added": int(bool(inspect_product_add)), "save_clicks": 0}
        if inspect_category:
            observation["kind"] = "authorized_category_controls_observation"
            observation["toolbar_controls"] = p.page.locator("qd-dynamic-table").evaluate_all(r"""tables=>tables.map(t=>({
              title:(t.querySelector('.table-caption')?.textContent||'').trim(),
              buttons:Array.from(t.querySelectorAll('button')).map(b=>({text:(b.textContent||'').trim(),
                title:b.title,aria:b.getAttribute('aria-label'),disabled:b.disabled,
                visible:b.getBoundingClientRect().width>0,classes:b.className,
                icons:Array.from(b.querySelectorAll('i,span')).map(e=>e.className)}))}))""")
        filename = "category_controls.json" if inspect_category else "default_personnel.json"
        p.save(filename, json.dumps(observation, ensure_ascii=False, indent=2))
        p.shot(p.page, "default_personnel.png")
        p.log_event(event="authorized_blank_test_observed", fields_written=observation["fields_written"],
                    product_rows_added=observation["product_rows_added"], save_clicks=0)
        p.result["finish_reason"] = "SUCCESS_CONTROLS_OBSERVED" if inspect_category else "SUCCESS_DEFAULTS_OBSERVED"
        return p.ev / filename
    finally:
        p.atomic_result()
        p._close_browser()
        p.release_lock()
        p.budget.close()


def inspect_product_controls(probe):
    from bpm.ui import TABLE_MAP_JS
    page = probe.page
    component = page.locator("qd-dynamic-table:has(th.prop-code)")
    button = component.locator("button[title='新增']")
    if component.count() != 1 or button.count() != 1 or not button.is_enabled():
        raise ValueError("product add control not unique after category selection")
    probe._click_guard("新增")
    button.click(timeout=8000)
    page.wait_for_timeout(1200)
    table = next((t for t in page.evaluate(TABLE_MAP_JS) if t.get("title") == "物品档案"), None)
    if not table or not table["row_count"]:
        dialogs = page.locator(".ui-dialog:visible").evaluate_all("ds=>ds.map(d=>({text:d.innerText.slice(0,1500),buttons:Array.from(d.querySelectorAll('button')).map(b=>({title:b.title,text:b.textContent}))}))")
        probe.save("product_add_dialog.json", json.dumps(dialogs, ensure_ascii=False, indent=2))
        probe.shot(page, "product_add_dialog.png")
        raise ValueError("product add did not create a table row; see dialog evidence")
    controls = []
    for index, column in enumerate(table["headers"]):
        if not column.get("prop"): continue
        cell = page.locator(table.get("body_sel") or table["sel"]).locator("tbody tr").first.locator("td").nth(index)
        if not cell.evaluate("e=>e.classList.contains('readonly')"):
            cell.dblclick(timeout=8000)
            page.wait_for_timeout(600)
        controls.append({"prop": column["prop"], "cell": cell.evaluate("e=>({text:e.textContent,classes:e.className,inputs:Array.from(e.querySelectorAll('input,textarea,select')).map(x=>({tag:x.tagName,type:x.type,readonly:x.readOnly,disabled:x.disabled,value:x.value})),buttons:Array.from(e.querySelectorAll('button')).map(x=>({title:x.title,aria:x.getAttribute('aria-label'),icons:Array.from(x.querySelectorAll('i,span')).map(y=>y.className)}))})")})
        page.keyboard.press("Tab")
    probe.save("product_add_controls.json", json.dumps(controls, ensure_ascii=False, indent=2))
    return controls


def build_replay(kind, round_name, study_path, defaults_path, auth_path):
    auth_path, auth = read_authorization(auth_path)
    if kind not in ("express", "rd_materials") or not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", round_name):
        raise ValueError("explicit supported type and simple test round required")
    records = json.loads(Path(study_path).read_text(encoding="utf-8"))["records"]
    hits = [r for r in records if r["number"] == auth["selected_templates"][kind] and r["document_type"] == kind]
    if len(hits) != 1:
        raise ValueError("authorized exact template study record missing")
    record = hits[0]
    template_path, view_path = ROOT / record["snapshot_path"], ROOT / record["view_path"]
    if file_hash(template_path) != record["snapshot_sha256"] or file_hash(view_path) != record["view_sha256"]:
        raise ValueError("historical replay source drift")
    template = json.loads(template_path.read_text(encoding="utf-8"))
    view = json.loads(view_path.read_text(encoding="utf-8"))
    defaults_path = Path(defaults_path).resolve()
    defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
    if defaults["operator"] != auth["operator"] or defaults.get("fields_written") != 0:
        raise ValueError("untouched current default personnel observation required")
    config = load_type(kind)
    out = ROOT / "automation/type-replay-plans" / round_name
    out.mkdir(parents=True, exist_ok=False)
    material_dir = out / "test-inputs"
    material_dir.mkdir()
    header = {k: str(view_value(view, k)) for k in config["header"]}
    header["corpCode"] = defaults["applicant"]["company"]
    header["budgetYears"] = str(defaults["header"].get("budgetYears") or template["header"]["budgetYears"])
    header["description"] = "【历史回放测试·不保存·" + round_name + "】" + str(view_value(view, "description"))
    for key, spec in config["header"].items():
        if spec["type"] == "money": header[key] = normalize_money(header[key])
    tables = {}
    for key, spec in config["tables"].items():
        tables_in_view = [t for t in view["tables"] if t["title"] == spec["title"]]
        if len(tables_in_view) != 1:
            raise ValueError("exact observed table missing: " + key)
        rows = []
        for index, observed in enumerate(tables_in_view[0]["rows"]):
            values = {prop: observed["fields"][prop] for prop in spec["columns"]}
            for prop, column in spec["columns"].items():
                if column["type"] == "money": values[prop] = normalize_money(values[prop])
            rows.append({"row_id": f"replay-{key}-{index+1}", "fields": values})
        tables[key] = rows
    rules = {"costs": "sum" if tables["costs"] else "not_applicable", "cost_amount_semantics": "line_total"}
    if not tables["costs"]: rules["costs_reason"] = "已授权未保存历史回放：原模板费用说明为空；不代表新费用不适用规则"
    if "products" in tables: rules.update(products="sum", product_amount_semantics="line_total")
    task_id = "type-replay-20261023-" + round_name
    plan = {"schema_version": "1.0", "config_version": "1.0", "document_type": kind, "task_id": task_id,
        "operator": auth["operator"], "applicant": copy.deepcopy(defaults["applicant"]), "header": header, "tables": tables,
        "template": {"biz_number": template["biz_number"], "captured_at": template["captured_at"],
                     "snapshot_path": str(template_path.resolve()), "sha256": file_hash(template_path)},
        "test_context": {"purpose": "已授权复杂历史数据回放，验证真实控件和整单；不申报新费用、不保存",
            "round": round_name, "authorization_path": str(auth_path), "authorization_sha256": file_hash(auth_path)},
        "authorization": {"mode": "fill_only", "task_id": task_id, "statement": auth["user_statement"] + "；本轮只填不存，不提交", "allow_submit": False},
        "unresolved": [], "not_applicable": [config["tables"][k]["title"] for k, rows in tables.items() if not rows],
        "table_applicability": {k: {"reason": "已授权未保存历史回放：原模板本表为空，仅用于测试"} for k, rows in tables.items() if not rows},
        "amount_rules": rules}
    facts = {key: copy.deepcopy(plan[key]) for key in ("applicant", "header", "tables", "table_applicability")}
    facts.update(test_only=True, not_new_expenses=True,
        replay_lineage={"template_path": str(template_path), "template_sha256": file_hash(template_path),
            "view_path": str(view_path), "view_sha256": file_hash(view_path),
            "defaults_path": str(defaults_path), "defaults_sha256": file_hash(defaults_path),
            "authorization_path": str(auth_path), "authorization_sha256": file_hash(auth_path)},
        no_invoice_rule="仅为用户明确授权的历史数据未保存测试，不申报新费用、不代表业务免票依据")
    proof = material_dir / "authorized_replay_facts.json"
    proof.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(inventory_materials(material_dir), ensure_ascii=False, indent=2), encoding="utf-8")
    primary = "products" if kind == "rd_materials" else "costs" if tables["costs"] else "details"
    amount_field = "price" if primary == "products" else "cost"
    plan["materials"] = {"manifest_path": str(manifest_path), "manifest_sha256": file_hash(manifest_path),
        "no_invoice_rows": [{"plan_pointer": f"/tables/{primary}/{i}/fields/{amount_field}", "reason": facts["no_invoice_rule"],
            "proof": {"kind": "user", "path": str(proof), "sha256": file_hash(proof), "locator": "/no_invoice_rule"}}
            for i, _ in enumerate(tables[primary])]}
    pointers = [f"/{key}/{prop}" for key in ("applicant", "header") for prop in plan[key]]
    pointers += [f"/tables/{key}/{i}/fields/{prop}" for key, rows in tables.items() for i, row in enumerate(rows) for prop in row["fields"]]
    pointers += [f"/table_applicability/{key}/reason" for key in plan["table_applicability"]]
    plan["sources"] = {p: {"kind": "user", "path": str(proof), "sha256": file_hash(proof), "locator": p} for p in pointers}
    issues = validate_plan(plan, expected_operator=auth["operator"], base_dir=out)
    if issues: raise ValueError(issues)
    path = out / "fill_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "preparation.json").write_text(json.dumps({"kind": "authorized_historical_replay_not_new_expenses",
        "plan_hash": plan_hash(plan), "rows": {k: len(v) for k, v in tables.items()},
        "lineage": facts["replay_lineage"], "save_permitted": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def view_value(view, prop):
    from bpm.ui import _prop
    matches = [f["value"] for f in view["header_fields"] if _prop(f.get("name")) == prop]
    if len(matches) != 1: raise ValueError("exact observed header missing: " + prop)
    return matches[0]


def normalize_money(value):
    from bpm.verify import decimal
    result = decimal(value)
    if result < 0 or result != result.quantize(Decimal("0.01")):
        raise ValueError("invalid replay line amount")
    return format(result, ".2f")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--authorization", required=True)
    ap.add_argument("--capture-defaults", action="store_true")
    ap.add_argument("--inspect-category", choices=("express", "rd_materials"))
    ap.add_argument("--inspect-product-add", action="store_true")
    ap.add_argument("--run")
    ap.add_argument("--document-type", choices=("express", "rd_materials"))
    ap.add_argument("--round")
    ap.add_argument("--study", default=str(ROOT / "automation/type-extension/historical-field-study.json"))
    ap.add_argument("--defaults")
    args = ap.parse_args()
    if args.capture_defaults:
        if not args.run: ap.error("--run required to capture defaults")
        if args.inspect_product_add and args.inspect_category != "rd_materials": ap.error("product controls require rd_materials")
        print(capture_defaults(args.authorization, args.run, inspect_category=args.inspect_category,
                               inspect_product_add=args.inspect_product_add))
    else:
        if args.inspect_category: ap.error("--inspect-category requires --capture-defaults")
        if not args.defaults or not args.round or not args.document_type:
            ap.error("explicit --defaults, --round and --document-type required")
        print(build_replay(args.document_type, args.round, args.study, args.defaults, args.authorization))


if __name__ == "__main__": main()
