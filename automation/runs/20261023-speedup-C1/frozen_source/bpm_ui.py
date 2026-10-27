"""Array-driven BPM UI execution. Legacy interactions remain in the probe.

This module only writes form controls. Saving is exclusively mediated by
bpm_save.SaveController; requests made here for discovery/reopening are GET.
"""
from __future__ import annotations

import json
import hashlib
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from stage1_browser_probe import (
    Probe, FORM_MAP_JS, TABLE_MAP_JS, _NG_HELPERS, HOST, LIST_PATH,
    PASS, FAIL, BLOCKED, assert_internal, sanitize_url,
)

TABLES = ("relations", "details", "costs", "banks")
IDENTITY_FIELDS = {"name": "appliedName", "company": "corpCode", "department": "appliedDeptName"}


class UIBlocked(RuntimeError):
    pass


def _prop(name):
    # Angular gives ordinary inputs numbered names (appliedName2), whereas
    # dropdown components use the actual property name without a suffix.
    return re.sub(r"\d+$", "", str(name or ""))


def _same(a, b):
    return str(a).strip() == str(b).strip()


def observed_operator(page):
    """Actual account entry, witnessed in login/list/form history artifacts."""
    account = page.locator("a#user-profile-dd.profile-toggle-link > span")
    if account.count() != 1 or not account.is_visible():
        return ""
    return account.inner_text().strip()


ROWS_JS = _NG_HELPERS + r"""
(t) => {
  const roots = document.querySelectorAll(t.body_sel || t.sel);
  if (roots.length !== 1) throw new Error('AMBIGUOUS_TABLE_BODY');
  return Array.from(roots[0].querySelectorAll('tbody > tr')).map(tr => {
    const cells = Array.from(tr.children).filter(c => c.tagName === 'TD');
    if (!cells.length || tr.classList.contains('ui-table-emptymessage'))
      throw new Error('UNRECOGNIZED_DATA_ROW');
    if (cells.length !== t.headers.length) throw new Error('COLUMN_COUNT_MISMATCH');
    const fields = {};
    cells.forEach((td, i) => {
      const key = t.headers[i].prop;
      if (!key) return;
      if (Object.prototype.hasOwnProperty.call(fields, key)) throw new Error('DUPLICATE_COLUMN');
      // Read live editors as well as committed output; never reuse a write record.
      const inp = td.querySelector('input:not([type=hidden]),textarea,select');
      const lb = td.querySelector('.ui-dropdown-label,.ui-multiselect-label');
      fields[key] = lb ? (lb.value || lb.textContent || '').trim()
        : inp ? inp.value : (td.textContent || '').trim();
    });
    const field_metadata = {};
    cells.forEach((td, i) => {
      const key = t.headers[i].prop;
      if(key) field_metadata[key] = {readonly:td.classList.contains('readonly')};
    });
    return {fields,field_metadata};
  });
}
"""

PICK_ROWS_JS = _NG_HELPERS + r"""
() => {
  const panels = Array.from(document.querySelectorAll(
    '.ui-dialog,.ui-dropdown-panel,.ui-multiselect-panel,[role=dialog]')).filter(_vis);
  const seen = new Set(), out = [];
  for (const panel of panels) {
    for (const r of panel.querySelectorAll('tbody tr,li')) {
      if (!_vis(r) || r.closest('thead') || r.querySelector('th') || seen.has(r)) continue;
      seen.add(r);
      const isOption = r.tagName === 'LI';
      const cells = isOption ? [(r.textContent || '').trim()]
        : Array.from(r.querySelectorAll(':scope > td')).map(c => (c.textContent || '').trim());
      if (!cells.length) continue;
      out.push({sel:_path(r),panel:_path(panel),cells,isOption});
    }
  }
  return out;
}
"""


class StructuredProbe(Probe):
    """The v1 plan route, intentionally isolated from legacy sample assumptions."""

    def __init__(self, args):
        from bpm_plan import load_plan, plan_hash, load_type
        self.plan_base = Path(args.fill_plan).resolve().parent
        plan = load_plan(args.fill_plan, expected_operator=args.expect_name)
        self.type_config = load_type(plan["document_type"])
        self.bound_plan_hash = plan_hash(plan)
        self.config_hash = hashlib.sha256(json.dumps(self.type_config, ensure_ascii=False,
                                                     sort_keys=True).encode("utf-8")).hexdigest()
        super().__init__(args)
        self.fill_plan = plan
        self.result.update(plan_hash=self.bound_plan_hash, task_id=plan["task_id"],
                           validation_scope="v1_independent", save_status="NOT_ATTEMPTED")
        self.adapter = DraftUIAdapter(self)

    def login_state(self, page):
        state, marks, evidence = super().login_state(page)
        if state == "LOGGED_IN" and observed_operator(page) != self.args.expect_name:
            marks["operator_mismatch"] = True
            return "UNKNOWN", marks, evidence
        return state, marks, evidence

    def _launch(self, *args, **kwargs):
        with self._timing("browser_session_start"):
            if "test_context" in (getattr(self,"fill_plan",None) or {}):
                # A fresh context reuses only the existing protected session
                # helper. It cannot restore or close another user's form tabs.
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                self.test_browser = self._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
                self.ctx = self.test_browser.new_context(ignore_https_errors=True,
                    viewport={"width":1440,"height":900})
                self._inject_session_state()
            else:
                super()._launch(*args, **kwargs)
        self.native_dialogs = []
        # A persistent context can restore somebody's unsubmitted form. Never
        # let the ordinary entry navigation overwrite that first tab.
        self.restored_pages = [{"url": sanitize_url(pg.url)} for pg in self.ctx.pages]
        self.protected_restored_forms = [pg for pg in self.ctx.pages
                                         if urlsplit(pg.url).path == "/oa/reimburse"]
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(45000)
        def reject_dialog(dialog):
            self.native_dialogs.append({"kind": dialog.type})
            self.log_event(event="unknown_native_dialog_rejected", kind=dialog.type)
            dialog.dismiss()
        self.page.on("dialog", reject_dialog)
        self.page.on("framenavigated",lambda f:self.log_event(event="page_navigation",epoch_ms=int(time.time()*1000)) if f==self.page.main_frame else None)
        self.network_counts={"requests":0,"failed":0}
        def request(_):
            self.network_counts["requests"]+=1
        self.page.on("request",request)
        self.page.on("requestfailed",lambda _:self.network_counts.__setitem__("failed",self.network_counts["failed"]+1))

    def _close_browser(self):
        if "test_context" in (getattr(self,"fill_plan",None) or {}) and getattr(self,"ctx",None):
            try:
                snapshot=self.adapter.capture_snapshot()
                self.save("test_page_close_inventory.json",json.dumps({"page":snapshot["page"],
                    "test_context":self.fill_plan["test_context"],"save_status":self.result.get("save_status"),
                    "closing_own_test_context_only":True},ensure_ascii=False,indent=2))
                self.log_event(event="own_test_page_close",unsaved=snapshot["page"]["is_new"],
                    save_attempted=self.result.get("save_status")!="NOT_ATTEMPTED")
            except Exception as exc:
                self.log_event(event="test_close_inventory_unavailable",exc=type(exc).__name__)
        # A new task does not authorize closing somebody's restored form. If one
        # exists, leave its window available until its owner closes it; the wall
        # watchdog must not indirectly kill it during this human waiting period.
        protected = getattr(self, "protected_restored_forms", [])
        if any(not pg.is_closed() for pg in protected):
            self.log_event(event="restored_forms_retained", count=len(protected))
        while any(not pg.is_closed() for pg in protected):
            self.budget.wall_cap = max(self.budget.wall_cap, self.budget.monotonic_wall() + 3600)
            pg = next(pg for pg in protected if not pg.is_closed())
            try:
                pg.wait_for_timeout(1000)
            except Exception:
                break
        if any(not pg.is_closed() for pg in protected):
            # A failed connection must not be treated as permission to close it.
            self.log_event(event="restored_form_connection_unresolved")
            return
        super()._close_browser()

    def _park_browser(self, minutes):
        status = self.result.get("task_status", "NEEDS_INPUT")
        self.say(f"{status} 浏览器驻留 {minutes:.0f} 分钟，等待用户审核；不执行额外业务动作")
        self.log_event(event="keep_open_start", minutes=minutes, task_status=status)
        # Use Playwright's wait to service window events without making requests.
        # The legacy mechanism and all form settle waits remain unchanged.
        for _ in range(max(1, int(minutes))):
            if self.page.is_closed():
                break
            self.page.wait_for_timeout(60000)
        self.log_event(event="keep_open_end", task_status=status)

    def _table_by_prop(self, frame, prop, title_hint=None):
        cache=getattr(self,"_table_schema_cache",{})
        key=(prop,title_hint)
        cached=cache.get(key)
        if cached:
            state=frame.evaluate(r"""t=>{
              const roots=document.querySelectorAll(t.component_sel), bodies=document.querySelectorAll(t.body_sel);
              if(roots.length!==1||bodies.length!==1)return null;
              const cap=roots[0].querySelector('.table-caption');
              const title=cap?(cap.textContent||'').replace(/\s+/g,' ').trim().slice(0,30):'';
              const props=Array.from(roots[0].querySelectorAll('thead th')).map(e=>(e.className.match(/prop-([\w-]+)/)||[])[1]||'');
              if(title!==t.title||JSON.stringify(props)!==JSON.stringify(t.headers.map(h=>h.prop||'')))return null;
              return {row_count:bodies[0].querySelectorAll('tbody tr').length};
            }""",cached)
            if state:
                return {**cached,**state}
            cache.pop(key,None)
        with self._timing("table_schema_scan",prop=prop):
            tables = frame.evaluate(TABLE_MAP_JS) or []
        hits = [t for t in tables if any(h.get("prop") == prop for h in t.get("headers", []))
                and (title_hint is None or t.get("title") == title_hint)]
        if len(hits) != 1:
            return None
        table = hits[0]
        # Anchor to the component and its complete property signature. Body
        # classes and nth-of-type ancestor paths change when a dialog closes.
        props = [h["prop"] for h in table["headers"] if h.get("prop")]
        if not props or any(not re.fullmatch(r"[\w-]+", p) for p in props):
            raise UIBlocked("INVALID_TABLE_SIGNATURE")
        root = "qd-dynamic-table" + "".join(":has(th.prop-" + p + ")" for p in props)
        if frame.locator(root).count() != 1:
            raise UIBlocked("TABLE_COMPONENT_NOT_UNIQUE")
        body = root + " .ui-table-scrollable-body > table"
        if frame.locator(body).count() != 1:
            body = root + " > table"
        if frame.locator(body).count() != 1:
            raise UIBlocked("TABLE_BODY_NOT_UNIQUE")
        table.update(component_sel=root, body_sel=body)
        cache[key]=dict(table)
        self._table_schema_cache=cache
        return table

    def _invalidate_tables(self):
        self._table_schema_cache={}

    def _pick_option(self, page, frame, comp_loc, value, kind):
        token = comp_loc.evaluate("e=>Array.from(e.classList).find(c=>c.startsWith('ng-tns-'))||''")
        if not token or not re.fullmatch(r"ng-tns-[\w-]+", token):
            raise UIBlocked("CURRENT_DROPDOWN_INSTANCE_MISSING")
        panel = page.locator(".ui-dropdown-panel."+token+",.ui-multiselect-panel."+token)
        opts = panel.locator("li:visible")
        if not opts.count():
            trigger = comp_loc.locator(".ui-dropdown-trigger,.ui-multiselect-trigger")
            (trigger if trigger.count() == 1 else comp_loc).click(timeout=8000)
        hits=[]
        for _ in range(4):
            page.wait_for_timeout(600)
            hits = [i for i in range(opts.count()) if _same(opts.nth(i).inner_text(), value)]
            if len(hits)==1:
                break
        if len(hits) != 1:
            page.keyboard.press("Escape")
            self.log_event(event="exact_option_blocked", candidate_count=len(hits))
            return None
        item = opts.nth(hits[0])
        self._click_guard(item.inner_text())
        if kind == "multiselect" and item.get_attribute("aria-selected") == "true":
            page.keyboard.press("Escape")
            return str(value)
        item.click()
        page.wait_for_timeout(400)
        if kind == "multiselect":
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        return str(value)

    def _overlay_search_pick(self, page, frame, keyword, tag, prescan=False, first_data_row=False):
        if first_data_row:
            raise UIBlocked("FIRST_CANDIDATE_SUBSTITUTION_FORBIDDEN")
        # Only the current visible table dialog participates. Dropdown panels
        # from other components are deliberately outside this scope.
        dialogs = page.locator(".ui-dialog:visible")
        if dialogs.count() != 1:
            self.log_event(event="exact_picker_blocked", where=tag, reason="dialog_not_unique")
            return False
        dialog = dialogs
        rows = dialog.locator("tbody tr:visible")
        def hits():
            return [i for i in range(rows.count()) if str(keyword) in
                    [x.strip() for x in rows.nth(i).locator(":scope > td").all_text_contents()]]
        matches = hits()
        if not matches:
            # Search only the one current dialog, using its observed writable
            # search box. No first-row or partial-number substitution.
            inputs = dialog.locator("input:not([readonly]):not([disabled]):not([type=checkbox]):not([type=radio]):visible")
            if inputs.count() != 1:
                self.log_event(event="exact_picker_blocked", where=tag, reason="search_not_unique", count=inputs.count())
                return False
            with self._timing("picker_query", where=tag):
                inputs.fill(str(keyword), timeout=8000)
                inputs.press("Enter")
                page.wait_for_timeout(1500)
                query = dialog.get_by_role("button", name="查询", exact=True)
                if query.count()==1 and query.is_enabled():
                    self._click_guard("查询")
                    query.click(timeout=8000)
                    page.wait_for_timeout(1500)
            matches=hits()
        if len(matches)!=1:
            self.log_event(event="exact_picker_blocked", where=tag, candidate_count=len(matches))
            return False
        with self._timing("picker_select_confirm", where=tag):
            row=rows.nth(matches[0])
            row.click(timeout=8000)
            page.wait_for_timeout(600)
            # An auto-committing picker can close here. The caller must still
            # verify the exact full selected identity from the live form.
            if not dialog.count() or not dialog.is_visible():
                self._invalidate_tables()
                return True
            selected=row.evaluate("e=>e.matches('[aria-selected=true],.ui-state-highlight')||!!e.querySelector('[aria-checked=true],.ui-chkbox-box.ui-state-active,input:checked')")
            if not selected:
                self.log_event(event="exact_picker_blocked", where=tag, reason="selection_unproven")
                return False
            buttons=dialog.locator(".ui-dialog-footer button,.ui-dialog-footer a")
            good=[i for i in range(buttons.count()) if buttons.nth(i).inner_text().strip() in ("确定","确认","选择") and buttons.nth(i).is_enabled()]
            if len(good)!=1:
                return False
            self._click_guard(buttons.nth(good[0]).inner_text())
            buttons.nth(good[0]).click(timeout=8000)
            for _ in range(20):
                page.wait_for_timeout(600)
                if not dialog.count() or not dialog.is_visible():
                    self._invalidate_tables()
                    return True
        return False

    def _column(self, table, prop):
        indices = [i for i, h in enumerate(table["headers"]) if h.get("prop") == prop]
        if len(indices) != 1:
            raise UIBlocked(f"COLUMN_NOT_UNIQUE:{prop}")
        return indices[0]

    def _table(self, key):
        config = self.type_config["tables"][key]
        prop, title = next(iter(config["columns"])), config["title"]
        table = self._table_by_prop(self.page.main_frame, prop, title)
        if not table:
            raise UIBlocked(f"TABLE_NOT_UNIQUE:{key}")
        return table

    def _read_rows(self, key):
        return self.page.evaluate(ROWS_JS, self._table(key))

    def _read_field(self,key,row,field):
        # Freshly resolve the live cell; cache only table/column structure.
        return self._cell(key,row,field).evaluate(r"""td=>{
          const inp=td.querySelector('input:not([type=hidden]),textarea,select');
          const lb=td.querySelector('.ui-dropdown-label,.ui-multiselect-label');
          return lb?(lb.value||lb.textContent||'').trim():inp?inp.value:(td.textContent||'').trim();
        }""")

    def _cell(self, key, row, field):
        table = self._table(key)
        if row >= table["row_count"]:
            raise UIBlocked(f"ROW_MISSING:{key}:{row}")
        return self._cell_loc(self.page, table, row, self._column(table, field))

    def _assert_identities_locked(self):
        expected=getattr(self,"locked_identity",None)
        if expected is None:
            return
        fields={_prop(f.get("name")):f.get("value","") for f in self.page.evaluate(FORM_MAP_JS) if f.get("name")}
        if observed_operator(self.page)!=self.fill_plan["operator"] or any(fields.get(k)!=v for k,v in expected.items()):
            raise UIBlocked("LOCKED_PERSON_IDENTITY_CHANGED")

    def _activate(self, cell, where):
        mounted=cell.locator(".ui-dropdown,.ui-multiselect,input:not([type=hidden]),textarea,select,.tableselect button")
        if not mounted.count():
            with self._timing("cell_activate", where=where, act="dblclick", attempt=1):
                cell.dblclick(timeout=8000)
                self.page.wait_for_timeout(600)
        # No fallback click without evidence that the first activation changed
        # state; unknown editors stop once, before another row is attempted.
        if not mounted.count():
            raise UIBlocked("EDITOR_NOT_MOUNTED:"+where)

    def _write_cell(self, cell, field, value, where, native_priority=False):
        self._activate(cell,where)
        dropdown=cell.locator(".ui-dropdown,.ui-multiselect")
        if dropdown.count()==1:
            kind="multiselect" if "ui-multiselect" in (dropdown.get_attribute("class") or "") else "dropdown"
            with self._timing("pick_option",where=where):
                if self._pick_option(self.page,self.page.main_frame,dropdown,str(value),kind) is None:
                    raise UIBlocked("EXACT_OPTION_MISSING:"+where)
            self.page.keyboard.press("Escape")
        else:
            inp=cell.locator("input:not([type=hidden]),textarea,select")
            writable=inp.count()==1 and inp.evaluate("e=>!e.readOnly&&!e.disabled")
            button=cell.locator(".tableselect button[aria-label='选择表格数据']")
            if writable and (native_priority or not button.count()):
                # Editor discovery already activated this cell. Use its native
                # control directly, retaining the legacy commit and settle waits.
                with self._timing("cell_input_write",where=where,how="mounted_native"):
                    if inp.evaluate("e=>e.tagName")=="SELECT":
                        inp.select_option(str(value),timeout=8000)
                    else:
                        inp.fill(str(value),timeout=8000)
                        self.page.keyboard.press("Enter")
                self.page.wait_for_timeout(400)
                self._cell_settle_read(self.page,self.page.main_frame,cell)
            elif button.count()==1:
                self._click_guard("选择表格数据")
                with self._timing("picker_open",where=where):
                    button.click(timeout=8000)
                    self.page.wait_for_timeout(1200)
                if not self._overlay_search_pick(self.page,self.page.main_frame,str(value),where,prescan=True):
                    raise UIBlocked("EXACT_PICK_MISSING:"+where)
            else:
                raise UIBlocked("UNSUPPORTED_EDITOR:"+where)
        with self._timing("cell_blur_readback",where=where):
            self.page.keyboard.press("Tab")
            self._cell_settle_read(self.page,self.page.main_frame,cell)

    def _expect_cell(self,key,row,field,value):
        from bpm_verify import values_equal
        for _ in range(3):
            actual=self._read_field(key,row,field)
            if values_equal(field,value,actual):
                return
            self.page.wait_for_timeout(600)
        raise UIBlocked(f"CELL_ECHO_MISMATCH:{key}:{row}:{field}")

    def _write(self,key,row,field,value,picker=False):
        from bpm_verify import values_equal
        current=self._read_field(key,row,field)
        if values_equal(field,value,current):
            self.log_event(event="cell_already_equal",table=key,row=row,field=field)
            return
        where=f"{key}/{row}/{field}"
        with self._timing("structured_cell",where=where):
            self._write_cell(self._cell(key,row,field),field,value,where,native_priority=key=="banks" and field in ("payee","account"))
            self._expect_cell(key,row,field,value)

    def _ensure_row(self,key,index,fields=None):
        t=self._table(key)
        if t["row_count"]>index:
            return
        if t["row_count"]!=index:
            raise UIBlocked("ROW_COUNT_DRIFT:"+key)
        if self.page.locator(".ui-dialog:visible").count():
            raise UIBlocked("UNEXPECTED_DIALOG_BEFORE_ADD:"+key)
        self._click_guard("新增")
        button=self.page.locator(t["component_sel"]).get_by_role("button",name="新增",exact=True)
        if button.count()!=1:
            # Actual toolbar buttons use a title with no visible text.
            button=self.page.locator(t["component_sel"]).locator("button[title='新增']")
        if button.count()!=1:
            raise UIBlocked("ADD_BUTTON_NOT_UNIQUE:"+key)
        with self._timing("row_add",section=key):
            button.click(timeout=8000)
            self.page.wait_for_timeout(1200)
        self._invalidate_tables()
        if self._table(key)["row_count"]!=index+1:
            raise UIBlocked("ROW_NOT_CREATED:"+key)

    def _fill_relation(self,index,fields):
        if fields["bizTypeName"] not in self.type_config["extra_table_projections"]["detailrels"]["supported_relation_types"]:
            raise UIBlocked("UNSUPPORTED_RELATION_DETAIL_BRANCH")
        self._ensure_row("relations",index)
        existing=self._read_rows("relations")[index]["fields"]
        if existing.get("bizNumber") and existing["bizNumber"]!=fields["bizNumber"]:
            raise UIBlocked("RELATION_ROW_IDENTITY_MISMATCH")
        for prop in ("bizTypeName","bizNumber"):
            self._write("relations",index,prop,fields[prop])
        table=self._table_by_prop(self.page.main_frame,"bizNo","关联单据明细")
        if not table:
            raise UIBlocked("RELATION_DETAIL_TABLE_MISSING")
        lower=self.page.evaluate(ROWS_JS,table)
        hits=[i for i,r in enumerate(lower) if r["fields"].get("bizNo")==fields["bizNumber"] and r["fields"].get("bizTypeName")==fields["bizTypeName"]]
        if len(hits)!=1:
            raise UIBlocked("UNSUPPORTED_RELATION_DETAIL_CARDINALITY")
        cell=self._cell_loc(self.page,table,hits[0],self._column(table,"cost"))
        from bpm_verify import values_equal
        if not values_equal("cost",fields["nowCost"],lower[hits[0]]["fields"].get("cost")):
            self._write_cell(cell,"cost",fields["nowCost"],f"detailrels/{hits[0]}/cost",native_priority=True)
        self._expect_cell("relations",index,"nowCost",fields["nowCost"])
        self._write("relations",index,"isLast",fields["isLast"])

    def _fill_bank_branch(self,index,fields):
        current=self._read_rows("banks")[index]["fields"]
        if current.get("bank")==fields["bank"] and current.get("bankCode")==fields["bankCode"]:
            return
        cell=self._cell("banks",index,"bank")
        button=cell.locator("button").filter(has=self.page.locator(".fa-search"))
        if button.count()!=1:
            raise UIBlocked("BANK_BRANCH_LOOKUP_NOT_UNIQUE")
        self._click_guard("查询开户行")
        with self._timing("picker_open",where=f"banks/{index}/branch"):
            button.click(timeout=8000)
            self.page.wait_for_timeout(1200)
        if not self._overlay_search_pick(self.page,self.page.main_frame,fields["bankCode"],f"banks/{index}/branch",prescan=True):
            raise UIBlocked("BANK_BRANCH_EXACT_CODE_MISSING")
        for prop in ("bank","bankCode"):
            self._expect_cell("banks",index,prop,fields[prop])

    def _write_header(self):
        from bpm_verify import values_equal
        for prop, value in self.fill_plan["header"].items():
            fields = self.page.evaluate(FORM_MAP_JS)
            hits = [f for f in fields if _prop(f.get("name")) == prop]
            if len(hits) != 1:
                raise UIBlocked(f"HEADER_NOT_UNIQUE:{prop}")
            f = hits[0]
            if f.get("readonly"):
                # Computed totals settle after rows are entered; all readonly
                # values are checked by the final independent collector.
                continue
            if values_equal(prop, f.get("value"), value):
                continue
            status, _, _ = self._ng_write(self.page, self.page.main_frame, f, value)
            if status != "OK":
                raise UIBlocked(f"HEADER_WRITE_BLOCKED:{prop}")

    def _fill_arrays(self):
        self._write_header()
        for key in ("relations", "costs", "details", "banks"):
            self._invalidate_tables()
            self._assert_identities_locked()
            if getattr(self,"fill_plan_path",None):
                from bpm_plan import load_plan,plan_hash,load_type
                live=load_plan(self.fill_plan_path,expected_operator=self.args.expect_name)
                current_config=hashlib.sha256(json.dumps(load_type(live["document_type"]),ensure_ascii=False,sort_keys=True).encode("utf-8")).hexdigest()
                if plan_hash(live)!=self.bound_plan_hash or current_config!=self.config_hash:
                    raise UIBlocked("PHASE_SOURCE_OR_PLAN_OR_CONFIG_CHANGED")
            with self._timing("section_fill", section=key):
                for index, row in enumerate(self.fill_plan["tables"][key]):
                    with self._timing("table_row_fill", section=key, row=index):
                        if key == "relations":
                            self._fill_relation(index, row["fields"])
                            continue
                        fields = row["fields"]
                        self._ensure_row(key, index, fields)
                        # Dependencies: exact budget document before subject;
                        # the department/project are system echoes, never guessed.
                        order = ({"details": ["reimItem", "digest", "budgetNo", "subjectName"],
                                  "banks": ["payee", "account", "bankCode", "bank"]}.get(key, []))
                        ordered = order + [p for p in fields if p not in order]
                        for prop in ordered:
                            if prop not in fields:
                                continue
                            picker = (key == "details" and prop in ("reimItem", "budgetNo", "subjectName")
                                      or key == "costs" and prop == "project")
                            if key == "details" and prop in ("budgetDeptName", "budgetItemName", "budgetOwner"):
                                continue
                            if key == "banks" and prop in ("bank", "bankCode"):
                                if prop == "bankCode":
                                    self._fill_bank_branch(index,fields)
                                continue
                            self._write(key, index, prop, fields[prop], picker=picker)
                        self.log_event(event="structured_row_written", table=key, row=index,
                                       row_id=row["row_id"])
                self._assert_identities_locked()
                self.say(f"PROGRESS {key}: {len(self.fill_plan['tables'][key])} rows complete")
                self.shot(self.page, f"v1_{key}_after.png")
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(800)

    def phase_fill(self):
        from bpm_plan import validate_plan, plan_hash
        from bpm_verify import verify_snapshot
        from bpm_save import SaveController
        issues = validate_plan(self.fill_plan, expected_operator=self.args.expect_name, base_dir=self.plan_base)
        if issues or plan_hash(self.fill_plan) != self.bound_plan_hash:
            self.result["task_status"] = "NEEDS_INPUT"
            self.result["issues"] = issues or [{"code": "PLAN_CHANGED"}]
            self.checks["c7_fill_new"].update(status=BLOCKED, reason="计划前置核验未通过")
            return BLOCKED
        # Any existing intent journal means read-only reconciliation, never a
        # second new form, even if the previous attempt crashed before replying.
        registry = Path(__file__).resolve().parent / "automation" / "task-registry"
        journal = registry / (hashlib.sha256(self.fill_plan["task_id"].encode("utf-8")).hexdigest() + ".json")
        if journal.exists():
            state = json.loads(journal.read_text(encoding="utf-8"))
            if state.get("status") in ("SAVE_INTENT", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED"):
                return self._reconcile()
        # Run binding prevents changing plans in-place under an existing task.
        binding = self.run_dir / "task_binding.json"
        if binding.exists():
            prior = json.loads(binding.read_text(encoding="utf-8"))
            from bpm_plan import file_hash
            if (prior.get("plan_sha256") != self.bound_plan_hash
                    or prior.get("operator") != self.fill_plan["operator"]
                    or prior.get("task_id") != self.fill_plan["task_id"]
                    or prior.get("config_sha256") != file_hash(Path(__file__).resolve().parent / "automation/document-types/travel.json")):
                raise UIBlocked("RUN_BOUND_TO_DIFFERENT_PLAN")
        else:
            from bpm_plan import file_hash
            binding.write_text(json.dumps({"kind": "fill_plan", "task_id": self.fill_plan["task_id"],
                                           "plan_sha256": self.bound_plan_hash, "operator": self.fill_plan["operator"],
                                           "config_sha256": file_hash(Path(__file__).resolve().parent / "automation/document-types/travel.json")},
                                          ensure_ascii=False), encoding="utf-8")
        registry.mkdir(parents=True, exist_ok=True)
        lifecycle = registry / (hashlib.sha256(self.fill_plan["task_id"].encode("utf-8")).hexdigest() + ".form.json")
        if lifecycle.exists() or getattr(self.args, "resume_attempt", None):
            # Inspect all available form tabs before declaring recovery blocked.
            # Never navigate to a new form just to reconstruct an interrupted one.
            inventory = []
            for pg in self.ctx.pages:
                inventory.append({"url": sanitize_url(pg.url), "is_active": pg == self.page})
            self.save("resume_page_inventory.json", json.dumps(inventory, ensure_ascii=False, indent=2))
            self.result["task_status"] = "NEEDS_INPUT"
            self.checks["c7_fill_new"].update(status=BLOCKED, reason="任务已有填写意图；已盘点页面，需原未保存页明确恢复，不自动再建单")
            return BLOCKED
        # Exclusive creation is conservative if interrupted even before goto.
        with lifecycle.open("x", encoding="utf-8") as f:
            json.dump({"task_id": self.fill_plan["task_id"], "plan_hash": self.bound_plan_hash,
                       "run": self.run_dir.name, "attempt": self.attempt.name,
                       "state": "FORM_INTENT"}, f, ensure_ascii=False)
        self.log_event(event="structured_fill_start", plan_hash=self.bound_plan_hash)
        try:
            # Reuse the only authorized NEW_FORM_PATH navigation in Probe.phase_fill;
            # its legacy surface dispatcher is replaced here by a dedicated hook.
            self.log_event(event="UI_START", epoch_ms=int(time.time()*1000),
                           round=self.fill_plan.get("test_context",{}).get("round"),
                           rows={k:len(v) for k,v in self.fill_plan["tables"].items()},
                           network="chromium --no-proxy-server; fresh test context" if "test_context" in self.fill_plan else "chromium --no-proxy-server", cache="cold context; session reused")
            net0=dict(getattr(self,"network_counts",{}))
            with self._timing("ui_execution"):
                super().phase_fill()
                with self._timing("independent_readback_verify"):
                    self._assert_identities_locked()
                    snapshot = self.adapter.capture_snapshot()
                    check = verify_snapshot(self.fill_plan, snapshot, base_dir=self.plan_base)
                self.log_event(event="READBACK_END", epoch_ms=int(time.time()*1000), ok=check["ok"])
                self.log_event(event="ui_execution_metrics",network={k:v-net0.get(k,0) for k,v in getattr(self,"network_counts",{}).items()},
                    model_control_interventions=0,external_cell_commands=0,
                    definitions="continuous executor; model calls and external read-only diagnostic shell commands are not automatically measured")
            self.save("independent_readback.json", json.dumps(snapshot, ensure_ascii=False, indent=2))
            self.save("independent_verification.json", json.dumps(check, ensure_ascii=False, indent=2))
            self.shot(self.page, "v1_final.png")
            if not check["ok"]:
                self.result["task_status"] = "READBACK_MISMATCH"
                self.result["issues"] = check["issues"]
                self.checks["c7_fill_new"].update(status=FAIL, reason="完整独立回读不一致")
                return FAIL
            if self.fill_plan["authorization"]["mode"] == "save_draft":
                result = SaveController(self.fill_plan, self.adapter, self.attempt,
                                        expected_operator=self.args.expect_name, base_dir=self.plan_base,
                                        journal_dir=registry).run()
                self.result["draft_save"] = result
                self.result["task_status"] = result.get("status", "SAVE_UNCERTAIN")
                self.result["save_status"] = self.result["task_status"]
                ok = self.result["task_status"] == "SUCCESS_DRAFT_SAVED"
            else:
                self.result["task_status"] = "SUCCESS_FILL_ONLY"
                ok = True
            self.checks["c7_fill_new"].update(status=PASS if ok else BLOCKED,
                                             reason=self.result["task_status"])
            return PASS if ok else BLOCKED
        except UIBlocked as exc:
            self.result["task_status"] = "NEEDS_INPUT"
            self.result["issues"] = [{"code": str(exc)}]
            self.shot(self.page, "v1_blocked.png")
            self.checks["c7_fill_new"].update(status=BLOCKED, reason=str(exc))
            return BLOCKED
        except Exception as exc:
            self.save("unexpected_control_failure.json",json.dumps({"exception":type(exc).__name__,
                "url":sanitize_url(self.page.url),"plan_hash":self.bound_plan_hash},ensure_ascii=False,indent=2))
            self.shot(self.page,"v1_unexpected_failure.png")
            raise

    def _phase_fill_ng(self, page, frame, plan):
        self._initial_applicant()
        self._check_initial_page()
        self._fill_arrays()
        return PASS  # Independent verification, not this return, decides success.

    def _initial_applicant(self):
        """Select once, on this task's blank page, before any business inputs."""
        snapshot=self.adapter.capture_snapshot()
        if not snapshot["page"]["is_new"] or snapshot["page"]["operator"]!=self.fill_plan["operator"]:
            raise UIBlocked("INITIAL_PAGE_NOT_OWNED_NEW_FORM")
        identity=self.fill_plan.get("identity")
        header=snapshot["header"]
        creator={k:header.get(k) for k in ("createdName","createdDeptName")}
        if identity and creator!={"createdName":identity["creator_name"],"createdDeptName":identity["creator_department"]}:
            raise UIBlocked("INITIAL_CREATOR_MISMATCH")
        expected=self.fill_plan["applicant"]
        different=snapshot["applicant"]!=expected or identity and header.get("appliedBy")!=identity["applicant_employee_id"]
        if different:
            if not identity:
                raise UIBlocked("COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED")
            if any(snapshot["tables"][k] for k in ("relations","details","costs")):
                raise UIBlocked("APPLICANT_SELECTION_AFTER_DATA_FORBIDDEN")
            button=self.page.locator(".dfc-container.prop-appliedName").get_by_role("button",name="选择组织",exact=True)
            if button.count()!=1:
                # ID is a form property, not a cached dynamic component instance.
                button=self.page.locator(".orgselect:has(input[id^='appliedName']) button[aria-label='选择组织']")
            if button.count()!=1:
                raise UIBlocked("APPLICANT_PICKER_NOT_UNIQUE")
            self._click_guard("选择组织")
            with self._timing("initial_applicant_select"):
                button.click(timeout=8000)
                self.page.wait_for_timeout(1200)
                dialog=self.page.locator(".ui-dialog:visible")
                if dialog.count()!=1 or "组织架构" not in dialog.inner_text():
                    raise UIBlocked("APPLICANT_ORG_DIALOG_MISSING")
                search=dialog.locator("input:visible")
                if search.count()!=1:
                    raise UIBlocked("APPLICANT_SEARCH_NOT_UNIQUE")
                search.fill(expected["name"],timeout=8000)
                search.press("Enter")
                self.page.wait_for_timeout(1500)
                candidates=self._pick_candidates(self.page.main_frame)
                exact=re.escape(expected["name"])+r"\s+\["+re.escape(identity["applicant_employee_id"])+r"\].*"
                hits=[r for c in candidates for r in c.get("row_list",[]) if re.fullmatch(exact,r.get("text",""))]
                if len(hits)!=1:
                    raise UIBlocked("APPLICANT_FULL_ID_NOT_UNIQUE")
                node=self.page.locator(hits[0]["sel"])
                node.click(timeout=8000)
                self.page.wait_for_timeout(500)
                if not node.evaluate("e=>e.matches('[aria-selected=true],.ui-state-highlight')||!!e.querySelector('[aria-selected=true],.ui-state-highlight')"):
                    raise UIBlocked("APPLICANT_SELECTION_UNPROVEN")
                confirm=dialog.get_by_role("button",name="确定",exact=True)
                if confirm.count()!=1:
                    raise UIBlocked("APPLICANT_CONFIRM_NOT_UNIQUE")
                self._click_guard("确定")
                confirm.click(timeout=8000)
                self.page.wait_for_timeout(2500)
            snapshot=self.adapter.capture_snapshot()
            header=snapshot["header"]
        if snapshot["applicant"]!=expected or identity and header.get("appliedBy")!=identity["applicant_employee_id"]:
            raise UIBlocked("INITIAL_APPLICANT_IDENTITY_MISMATCH")
        if any(header.get(k)!=v for k,v in creator.items()):
            raise UIBlocked("CREATOR_CHANGED_DURING_APPLICANT_SELECTION")
        self.locked_identity={**creator, **{p:header.get(p) for p in ("appliedName","appliedBy","appliedDeptName","corpCode")}}
        self.log_event(event="person_identities_locked",applicant_employee_verified=bool(identity),creator_unchanged=True)

    def _phase_fill_spreadjs(self, *args):
        raise UIBlocked("UNSUPPORTED_SPREADJS_V1")

    def _check_initial_page(self):
        supported=self.type_config["extra_table_projections"]["detailrels"]["supported_relation_types"]
        if any(r["fields"]["bizTypeName"] not in supported for r in self.fill_plan["tables"]["relations"]):
            raise UIBlocked("UNSUPPORTED_RELATION_DETAIL_BRANCH")
        snap = self.adapter.capture_snapshot()
        if not snap["page"]["is_new"] or snap["applicant"] != self.fill_plan["applicant"]:
            raise UIBlocked("NEW_PAGE_IDENTITY_MISMATCH")
        if not all(snap["completeness"].values()):
            raise UIBlocked("INITIAL_PAGE_INCOMPLETE")
        for key in TABLES:
            rows = snap["tables"][key]
            if len(rows) > len(self.fill_plan["tables"][key]):
                raise UIBlocked(f"EXTRA_INITIAL_ROWS:{key}")
            # The only accepted initialized row is an exact bank identity echo.
            for row in rows:
                fields = row["fields"]
                if key == "banks":
                    expected = self.fill_plan["tables"][key][0]["fields"]
                    if any(fields.get(k) and not _same(fields[k], expected.get(k))
                           for k in ("payee", "account", "bank", "bankCode")):
                        raise UIBlocked("INITIAL_BANK_IDENTITY_MISMATCH")
                elif any(str(v).strip() not in ("", "0", "0.00", "否") for v in fields.values()):
                    raise UIBlocked(f"EXISTING_ROW_REQUIRES_RECONCILIATION:{key}")

    def _reconcile(self):
        from bpm_save import SaveController
        result = SaveController(self.fill_plan, self.adapter, self.attempt,
                                expected_operator=self.args.expect_name, base_dir=self.plan_base,
                                journal_dir=Path(__file__).resolve().parent / "automation/task-registry").run()
        self.result["draft_save"] = result
        self.result["task_status"] = result.get("status", "SAVE_UNCERTAIN")
        self.checks["c7_fill_new"].update(status=PASS if result.get("status") == "SUCCESS_DRAFT_SAVED"
                                         else BLOCKED, reason=self.result["task_status"])
        return self.checks["c7_fill_new"]["status"]

    def _overall(self):
        if self.checks["c1_entry_login"]["status"] != PASS:
            return "WAIT_HUMAN_LOGIN"
        return self.result.get("task_status", "NEEDS_INPUT")


class DraftUIAdapter:
    """Concrete UI adapter. It has no method for a write HTTP request."""

    def __init__(self, probe):
        self.p = probe
        self._identity_routes = {}

    def capture_snapshot(self):
        page = self.p.page
        fields = page.evaluate(FORM_MAP_JS)
        header, duplicates = {}, []
        for field in fields:
            key = _prop(field.get("name"))
            if not key:
                continue
            if key in header:
                duplicates.append(key)
            header[key] = field.get("value", "")
        tables, complete = {}, {"header": not duplicates and bool(header)}
        mapped = page.evaluate(TABLE_MAP_JS)
        used = set()
        for key in TABLES:
            config = self.p.type_config["tables"][key]
            prop, title = next(iter(config["columns"])), config["title"]
            hits = [t for t in mapped if t.get("title") == title
                    and any(h.get("prop") == prop for h in t.get("headers", []))]
            complete[key] = len(hits) == 1
            tables[key] = []
            if len(hits) == 1:
                used.add(hits[0]["sel"])
                try:
                    tables[key] = page.evaluate(ROWS_JS, hits[0])
                    complete[key] = len(tables[key]) == hits[0]["row_count"]
                except Exception:
                    complete[key] = False
        extras = {}
        # Relation detail rows need explicit planning support. Approval/history
        # and attachment tables are observations, not planned fee rows.
        counts = {}
        for t in mapped:
            if t["sel"] in used:
                continue
            title = t.get("title", "")
            if title in ("确认人", "审批记录"):
                continue  # Read-only workflow history, not expense rows.
            key = {"关联单据明细": "detailrels", "产品明细": "products"}.get(title, "unmodeled:" + title)
            counts[key] = counts.get(key, 0) + 1
            try:
                observed_rows = page.evaluate(ROWS_JS, t)
            except Exception:
                observed_rows = []
                complete["header"] = False
            if key in extras:
                # Preserve every row rather than allowing a second empty table
                # to overwrite the first table's unplanned business content.
                complete["header"] = False
                extras[key].extend(observed_rows)
            else:
                extras[key] = observed_rows
        complete["detailrels"] = counts.get("detailrels") == 1
        validation = page.evaluate(r"""() => {
          const vis = e => e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0;
          const controls = Array.from(document.querySelectorAll('.dfc-container input,.dfc-container textarea,.dfc-container select,qd-dynamic-table input'));
          const invalid = controls.filter(e=>vis(e) && !e.disabled && !e.checkValidity()).map(e=>({
            property:e.name || e.id || '', reason:'native_constraint'}));
          for (const e of document.querySelectorAll('.dfc-container.ng-invalid')) {
            if(vis(e)) invalid.push({property:(e.className.match(/prop-([\w-]+)/)||[])[1]||'',reason:'angular_invalid'});
          }
          return {invalid_fields:invalid,pending:Array.from(document.querySelectorAll('.dfc-container.ng-pending')).some(vis)};
        }""")
        auth, _, _ = self.p.login_state(page)
        uuid = self._uuid_from_url(page.url)
        number = str(header.get("bizNumber") or "")
        is_new = (urlsplit(page.url).path == "/oa/reimburse"
                  and parse_qs(urlsplit(page.url).query).get("type") == ["new"] and not number)
        return {"page": {"url": sanitize_url(page.url), "is_new": is_new,
                          "operator": observed_operator(page) if auth == "LOGGED_IN" else "",
                          "biz_number": number, "uuid": uuid,
                          "status": header.get("bizStatus", "")},
                "applicant": {k: str(header.get(prop) or "") for k, prop in IDENTITY_FIELDS.items()},
                "header": header, "tables": tables, "completeness": complete,
                "extra_tables": extras, "validation": validation,
                "observed_at": datetime.now(timezone.utc).isoformat()}

    @staticmethod
    def _uuid_from_url(url):
        query = parse_qs(urlsplit(url).query)
        # id is observed in history view navigation; never use a generated id.
        value = (query.get("id") or [""])[0]
        if re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value):
            return value
        return ""

    def screenshot(self, name):
        result = self.p.shot(self.p.page, name if str(name).endswith(".png") else str(name) + ".png")
        if result.startswith("screenshot_failed"):
            raise UIBlocked("SCREENSHOT_FAILED")
        if name == "before_save":
            from bpm_save import SaveController
            # Content binding, not a caller-supplied verified boolean. The
            # adapter will independently collect and validate it again at click.
            self._pre_save_content_hash = SaveController._content(self.capture_snapshot())
        return "evidence/" + (str(name) if str(name).endswith(".png") else str(name) + ".png")

    def _save_buttons(self):
        return self.p.page.get_by_role("button", name="保存", exact=True)

    def exact_save_button(self):
        loc = self._save_buttons()
        count = loc.count()
        return {"text": loc.first.inner_text().strip() if count == 1 else "",
                "count": count, "enabled": count == 1 and loc.first.is_enabled(),
                "visible": count == 1 and loc.first.is_visible(), "kind": "button",
                "dialogs": self._dialogs()}

    def click_exact_save(self):
        from bpm_save import SaveController
        from bpm_verify import verify_snapshot
        from bpm_plan import plan_hash, load_type
        plan = self.p.fill_plan
        authorization = plan.get("authorization", {})
        snapshot = self.capture_snapshot()
        bound = getattr(self, "_pre_save_content_hash", None)
        current_config = hashlib.sha256(json.dumps(load_type(plan["document_type"]), ensure_ascii=False,
                                                   sort_keys=True).encode("utf-8")).hexdigest()
        if (authorization.get("mode") != "save_draft" or authorization.get("allow_submit") is not False
                or authorization.get("task_id") != plan["task_id"]
                or plan_hash(plan) != getattr(self.p, "bound_plan_hash", None)
                or current_config != getattr(self.p, "config_hash", None)
                or bound is None or SaveController._content(snapshot) != bound
                or not verify_snapshot(plan, snapshot, base_dir=self.p.plan_base)["ok"]):
            raise UIBlocked("SAVE_STATE_CHANGED_OR_UNAUTHORIZED")
        meta = self.exact_save_button()
        if meta != {"text": "保存", "count": 1, "enabled": True, "visible": True, "kind": "button", "dialogs": []}:
            raise UIBlocked("SAVE_BUTTON_CHANGED")
        # Deliberately NOT routed through the ordinary click helper. This is the
        # single exact UI save capability; SaveController owns its invocation.
        self._save_buttons().click(timeout=8000)
        self._pre_save_content_hash = None  # This adapter can never reuse its screenshot to click twice.

    def _dialogs(self):
        return list(getattr(self.p, "native_dialogs", [])) + [d.get("title", "") for d in self.p.page.evaluate(
            "() => Array.from(document.querySelectorAll('.ui-dialog,[role=dialog]'))"
            ".filter(e=>e.getBoundingClientRect().width>0).map(e=>({title:(e.innerText||'').slice(0,100)}))")]

    def observe_saved(self):
        # Observe only. Do not confirm unknown modals or infer success from toast.
        for _ in range(10):
            self.p.page.wait_for_timeout(600)
            dialogs = self._dialogs()
            if dialogs:
                return {"dialogs": dialogs}
            snap = self.capture_snapshot()
            if snap["page"]["biz_number"]:
                return self._observe_identity(snap)
        return {"dialogs": [], "identity": {}}

    def _observe_identity(self, snap):
        page = snap["page"]
        identity = {k: page.get(k, "") for k in ("uuid", "biz_number", "status")}
        if identity["uuid"] and identity["biz_number"]:
            # Reopening is tied to a URL actually observed after save, never
            # assembled from an assumed status code or toast.
            if (urlsplit(page["url"]).path == "/oa/reimburse"
                    and parse_qs(urlsplit(page["url"]).query).get("type") == ["view"]):
                self._identity_routes[identity["uuid"]] = page["url"]
        unique = bool(identity["uuid"] and identity["biz_number"])
        # A freshly observed UUID and number on the same unique form prove its
        # page identity. Persisted content is still proven separately by reopen.
        return {"identity": identity, "snapshot": snap, "dialogs": [], "unique": unique}

    def reopen(self, identity):
        route = self._identity_routes.get(identity["uuid"])
        if not route:
            route = self._discover_saved_route(identity)
        if not route:
            raise UIBlocked("SAVED_READ_ROUTE_UNOBSERVED")
        self.p.page.goto(assert_internal(route), wait_until="domcontentloaded", timeout=45000)
        self.p.page.wait_for_timeout(2500)
        return self.capture_snapshot()

    def _discover_saved_route(self, identity):
        from bpm_template import open_exact_document
        # Exact list lookup observes the real view URL through normal UI.
        return open_exact_document(self.p, identity["biz_number"], expected_uuid=identity["uuid"])

    def inspect_uncertain(self):
        # No identity guesses by amount/date. If no exact identity survived, a
        # human must supply the newly created number for read-only reconciliation.
        dialogs = self._dialogs()
        if dialogs:
            return {"dialogs": dialogs}
        return self._observe_identity(self.capture_snapshot())
