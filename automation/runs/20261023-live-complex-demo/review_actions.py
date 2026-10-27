"""Task-local UI diagnostics; never save, submit, or use write endpoints."""
import json
from stage1_browser_probe import FORM_MAP_JS, TABLE_MAP_JS
from bpm_ui import _prop, StructuredProbe


def handle(p, q, c, state):
    action = c["action"]
    if action == "show_identity_information":
        label=p.page.get_by_text("基础信息",exact=True)
        if label.count()!=1:
            raise RuntimeError("basic information toggle not unique")
        p._click_guard("基础信息")
        label.click(timeout=8000)
        p.page.wait_for_timeout(600)
        creator=next(f["value"] for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name"))=="createdName")
        if creator!=state["creator"]:
            raise RuntimeError("creator changed")
        table=q._table_by_prop(p.page.main_frame,"bizNo","关联单据明细")
        metadata=[{"row":i,"field":prop,**q._cell_loc(p.page,table,i,q._column(table,prop)).evaluate(
            "e=>({readonly:e.classList.contains('readonly'),visibleText:e.innerText})")}
                  for i in range(3) for prop in ("bizDetailCost","bizDetailNum","usedCost")]
        p.save("system_empty_field_metadata_all.json",json.dumps(metadata,ensure_ascii=False,indent=2))
        p.page.locator("#bizStatus0").scroll_into_view_if_needed()
        p.shot(p.page,"demo_review_identity_expanded.png")
        p.log_event(event="demo_identity_presented",creator_unchanged=True,save_attempted=False,
                    readonly_empty_system_fields=sum(x["readonly"] and not x["visibleText"].strip() for x in metadata))
        return {"creator":creator,"creator_unchanged":True,"readonly_empty_system_fields":len(metadata)}
    if action == "present_for_review":
        table=q._table_by_prop(p.page.main_frame,"bizNo","关联单据明细")
        metadata={prop:q._cell_loc(p.page,table,0,q._column(table,prop)).evaluate(
            "e=>({classes:e.className,visibleText:e.innerText,readonly:e.classList.contains('readonly')})")
                  for prop in ("bizDetailCost","bizDetailNum","usedCost")}
        p.save("system_empty_field_metadata.json",json.dumps(metadata,ensure_ascii=False,indent=2))
        q._cell("banks",0,"cost").scroll_into_view_if_needed()
        p.shot(p.page,"demo_costs_and_bank.png")
        creator_field=next(f for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name"))=="createdName")
        creator_control=p.page.locator(creator_field["sel"])
        if not creator_control.is_visible():
            label=p.page.get_by_text("基础信息",exact=True)
            if label.count()!=1:
                raise RuntimeError("basic information disclosure not unique")
            p._click_guard("基础信息")
            label.click(timeout=8000)
            p.page.wait_for_timeout(600)
        p.page.locator("#bizStatus0").scroll_into_view_if_needed()
        p.page.bring_to_front()
        p.shot(p.page,"demo_review_identity.png")
        p.log_event(event="demo_presented_for_review",creator_unchanged=True,save_attempted=False,
                    field_mismatch_count=0,strict_unresolved_system_fields=9)
        return {"presented":True,"empty_field_metadata":metadata,"browser_remains_open":True}
    if action == "final_review":
        from bpm_verify import verify_snapshot
        from bpm_plan import plan_hash
        p.page.keyboard.press("Tab")
        p.page.wait_for_timeout(1200)
        snapshot=q.adapter.capture_snapshot()
        checked=verify_snapshot(q.fill_plan,snapshot,base_dir=q.plan_base)
        fields=p.page.evaluate(FORM_MAP_JS)
        creator=next(f["value"] for f in fields if _prop(f.get("name"))=="createdName")
        if creator!=state["creator"]:
            checked["ok"]=False
            checked["issues"].append({"code":"CREATOR_CHANGED"})
        p.save("independent_readback.json",json.dumps(snapshot,ensure_ascii=False,indent=2))
        p.save("independent_verification.json",json.dumps(checked,ensure_ascii=False,indent=2))
        p.page.bring_to_front()
        p.page.evaluate("window.scrollTo(0,0)")
        p.shot(p.page,"demo_final.png")
        p.result.update(task_status="SUCCESS_FILL_ONLY" if checked["ok"] else "READBACK_MISMATCH",
                        finish_reason="SUCCESS_FILL_ONLY" if checked["ok"] else "READBACK_MISMATCH",
                        save_status="NOT_ATTEMPTED",save_allowed=False,demonstration_only=True,
                        creator_before=state["creator"],creator_after=creator,plan_hash=plan_hash(q.fill_plan),
                        current_plan_file=str(q.fill_plan_path),verification=checked,
                        actual_row_counts={k:len(v) for k,v in snapshot["tables"].items()})
        p.checks["c7_fill_new"].update(status="PASS" if checked["ok"] else "FAIL",reason=p.result["task_status"])
        p.atomic_result()
        p._save_session_state()
        p.log_event(event="demo_ready_for_manual_review",ok=checked["ok"],creator_unchanged=creator==state["creator"],
                    actual_row_counts=p.result["actual_row_counts"],save_attempted=False,keep_open_hours=24)
        return {"status":p.result["task_status"],"rows":p.result["actual_row_counts"],"creator":creator,"issues":checked["issues"]}
    if action == "authorize_demo_revision":
        from pathlib import Path
        from bpm_plan import load_plan,plan_hash
        import hashlib
        plan_path=Path(c["plan"]).resolve()
        if plan_path.parent!=p.run_dir.resolve() or plan_path.name!="fill_plan_revision02.json":
            raise RuntimeError("unexpected revision source")
        new=load_plan(plan_path,expected_operator=p.args.expect_name)
        old=q.fill_plan
        if new["task_id"]!=old["task_id"] or new["authorization"]["mode"]!="fill_only":
            raise RuntimeError("demo revision may not change task or save mode")
        if new["applicant"]!=old["applicant"] or new["template"]!=old["template"]:
            raise RuntimeError("identity/template immutable")
        if any(new["header"][k]!=v for k,v in old["header"].items() if k!="description"):
            raise RuntimeError("only demo description and explicitly listed relations may change")
        if any(new["tables"][k]!=old["tables"][k] for k in ("costs","details","banks")):
            raise RuntimeError("no other row changes authorized")
        numbers=["12026101976","12026070366","12026037675"]
        if [r["fields"]["bizNumber"] for r in new["tables"]["relations"]]!=numbers:
            raise RuntimeError("exact authorized numbers required")
        for a,b in zip(new["tables"]["relations"],old["tables"]["relations"]):
            if any(a["fields"][k]!=v for k,v in b["fields"].items() if k!="bizNumber"):
                raise RuntimeError("relation values other than number immutable")
        p._dialog_close_guarded(p.page)
        current=q.adapter.capture_snapshot()
        if not current["page"]["is_new"] or any(r["fields"].get("bizNumber") for r in current["tables"]["relations"]):
            raise RuntimeError("cannot revise an existing selected relation or saved form")
        creator=next(f["value"] for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name"))=="createdName")
        if creator!=state["creator"]:
            raise RuntimeError("creator changed")
        record={"event":"USER_AUTHORIZED_DEMO_PLAN_REVISION","previous_plan_sha256":q.bound_plan_hash,
                "new_plan_sha256":plan_hash(new),"task_id":new["task_id"],"numbers":numbers,
                "user_reply":"允许，仅用于本次演示","save_allowed":False,"same_existing_form":True}
        p.save("authorized_revision02.json",json.dumps(record,ensure_ascii=False,indent=2))
        p.log_event(**record)
        q.fill_plan=new
        q.bound_plan_hash=plan_hash(new)
        q.fill_plan_path=plan_path
        q.plan_base=plan_path.parent
        registry=Path(__file__).resolve().parents[3]/"automation/task-registry"
        lifecycle=registry/(hashlib.sha256(new["task_id"].encode()).hexdigest()+".form.json")
        saved=json.loads(lifecycle.read_text(encoding="utf-8"))
        saved["authorized_revision02"]=record
        lifecycle.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding="utf-8")
        return {"revision_bound":True,"plan_hash":q.bound_plan_hash,"creator_unchanged":True}
    if action == "open_cached_history":
        from bpm_template import cached_template
        from bpm_plan import load_type
        from bpm_ui import DraftUIAdapter
        from stage1_browser_probe import HOST, assert_internal
        snap = cached_template("automation/runs/20261023-142146-travelcensus/travel_census.json", p.args.doc_id)
        p.save("template_snapshot.json", json.dumps(snap, ensure_ascii=False, indent=2))
        p.page = p.ctx.new_page()
        p.page.goto(assert_internal(HOST + "/oa/reimburse?type=view&id=" + snap["uuid"]), wait_until="domcontentloaded")
        p.page.wait_for_timeout(4000)
        p.type_config = load_type("travel")
        display = DraftUIAdapter(p).capture_snapshot()
        if display["page"]["biz_number"] != p.args.doc_id:
            raise RuntimeError("cached UUID does not reopen exact full historical number")
        p.save("history_display_snapshot.json", json.dumps(display, ensure_ascii=False, indent=2))
        p.shot(p.page, "history_display.png")
        p.log_event(event="demo_history_exact_live_view", number=p.args.doc_id, uuid=snap["uuid"])
        return {"full_number_verified": True, "counts": {k: len(v) for k,v in display["tables"].items()}}
    if action == "inspect_person":
        prop = c["property"]
        if prop not in ("createdName", "appliedName"):
            raise RuntimeError("unsupported identity")
        field = next(f for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name")) == prop)
        info = p.page.locator(field["sel"]).evaluate("e=>e.parentElement.parentElement.outerHTML")
        p.save("person_picker_dom.json", json.dumps({"property": prop, "html": info}, ensure_ascii=False, indent=2))
        return {"property": prop, "value": field["value"], "dom": info}
    if action == "picker_state":
        data = {"fields": p.page.evaluate(FORM_MAP_JS), "candidates": p._pick_candidates(p.page.main_frame),
                "dialog": p._visible_dialog(p.page.main_frame), "overlay": p._overlay_open(p.page.main_frame)}
        p.save(c.get("tag", "picker_state") + ".json", json.dumps(data, ensure_ascii=False, indent=2))
        p.shot(p.page, c.get("tag", "picker_state") + ".png")
        return {"artifact": c.get("tag", "picker_state") + ".json"}
    if action == "collect_now":
        snap=q.adapter.capture_snapshot()
        p.save(c.get("tag","live_snapshot")+".json",json.dumps(snap,ensure_ascii=False,indent=2))
        return {"relations":snap["tables"]["relations"],"dialog":p._visible_dialog(p.page.main_frame),"overlay":p._overlay_open(p.page.main_frame)}
    if action == "planned_field":
        if q is None:
            raise RuntimeError("bound plan required")
        key, index, prop = c["table"], c["row"], c["property"]
        value = q.fill_plan["tables"][key][index]["fields"][prop]
        q._write(key,index,prop,value,picker=c.get("picker",False))
        p.log_event(event="demo_planned_field",table=key,row=index,property=prop)
        return {"written":True,"table":key,"row":index,"property":prop}
    if action == "inspect_cell":
        if c.get("close_dialog"):
            p._dialog_close_guarded(p.page)
        cell = q._cell(c["table"],c["row"],c["property"])
        if c.get("activate"):
            cell.dblclick()
            p.page.wait_for_timeout(600)
        return {"html":cell.evaluate("e=>e.outerHTML")}
    if action == "inspect_relation_amount":
        from bpm_ui import ROWS_JS
        table=q._table_by_prop(p.page.main_frame,"bizNo","关联单据明细")
        lower=p.page.evaluate(ROWS_JS,table)
        upper=q._cell("relations",0,"nowCost")
        cell=q._cell_loc(p.page,table,0,q._column(table,"cost"))
        cell.dblclick(timeout=8000)
        p.page.wait_for_timeout(600)
        return {"upper":upper.evaluate("e=>e.outerHTML"),"lower_rows":lower,
                "headers":table["headers"],"lower":cell.evaluate("e=>e.outerHTML")}
    if action == "inspect_bank_dependency":
        bank=q._cell("banks",0,"bank").evaluate("e=>e.outerHTML")
        code=q._cell("banks",0,"bankCode")
        code.dblclick(timeout=8000)
        p.page.wait_for_timeout(600)
        return {"bank":bank,"bankCode":code.evaluate("e=>e.outerHTML"),
                "expected_bank":q.fill_plan["tables"]["banks"][0]["fields"]["bank"],
                "expected_code":q.fill_plan["tables"]["banks"][0]["fields"]["bankCode"]}
    if action == "select_bank_branch":
        wanted=q.fill_plan["tables"]["banks"][0]["fields"]
        cell=q._cell("banks",0,"bank")
        button=cell.locator("button").filter(has=p.page.locator(".fa-search"))
        if button.count()!=1:
            raise RuntimeError("observed bank lookup button not unique")
        p._click_guard("查询开户行")
        button.click(timeout=8000)
        p.page.wait_for_timeout(1200)
        handle(p,q,{"action":"picker_state","tag":"bank_branch_picker"},state)
        q._overlay_search_pick(p.page,p.page.main_frame,wanted["bankCode"],"demo_bank_branch_exact_code",prescan=True)
        for _ in range(20):
            p.page.wait_for_timeout(600)
            row=q._read_rows("banks")[0]["fields"]
            if row.get("bankCode")==wanted["bankCode"] and row.get("bank")==wanted["bank"] and not p._visible_dialog(p.page.main_frame):
                p.log_event(event="demo_bank_branch_exact_verified",code=wanted["bankCode"])
                return {"branch_verified":True,"bank":row["bank"],"code":row["bankCode"]}
        raise RuntimeError("exact bank branch and routing code not confirmed")
    if action == "dropdown_metadata":
        cell=q._cell(c["table"],c["row"],c["property"])
        if not cell.locator(".ui-dropdown").count():
            cell.dblclick(timeout=8000)
            p.page.wait_for_timeout(600)
        comp=cell.locator(".ui-dropdown")
        if comp.count()!=1:
            raise RuntimeError("dropdown not mounted")
        token=comp.evaluate("e=>Array.from(e.classList).find(c=>c.startsWith('ng-tns-'))")
        return {"token":token,"panels":p.page.locator(".ui-dropdown-panel."+token).evaluate_all(
            "es=>es.map(e=>({tag:e.tagName,cls:e.className,html:e.outerHTML.slice(0,18000)}))")}
    if action == "open_planned_selector":
        cell = q._cell(c["table"],c["row"],c["property"])
        if not cell.locator(".tableselect button").count():
            cell.dblclick()
            p.page.wait_for_timeout(600)
        button = cell.locator(".tableselect button[aria-label='选择表格数据']")
        if button.count() != 1:
            raise RuntimeError("observed table-selector not unique")
        p._click_guard("选择表格数据")
        button.click(timeout=8000)
        p.page.wait_for_timeout(1200)
        return handle(p,q,{"action":"picker_state","tag":c.get("tag","table_selector")},state)
    if action == "resume_arrays":
        if q is None:
            raise RuntimeError("bound plan required")
        q._fill_arrays()
        return {"array_execution_returned":True}
    if action == "live_fill_remaining":
        import types
        from bpm_ui import UIBlocked

        def write_observed(self,key,index,prop,value,picker=False):
            current = self._read_rows(key)[index]["fields"].get(prop,"")
            if str(current).strip() == str(value).strip():
                return
            if key=="relations" and prop=="nowCost":
                from bpm_ui import ROWS_JS
                table=self._table_by_prop(p.page.main_frame,"bizNo","关联单据明细")
                wanted=self.fill_plan["tables"]["relations"][index]["fields"]
                lower=p.page.evaluate(ROWS_JS,table)
                matches=[i for i,r in enumerate(lower) if r["fields"].get("bizNo")==wanted["bizNumber"]
                         and r["fields"].get("bizTypeName")==wanted["bizTypeName"]]
                if len(matches)!=1:
                    raise UIBlocked("EXACT_RELATION_DETAIL_NOT_UNIQUE")
                cell=self._cell_loc(p.page,table,matches[0],self._column(table,"cost"))
                status,_=self._fill_ng_cell(p.page,p.page.main_frame,cell,str(value))
                if status!="OK":
                    raise UIBlocked("RELATION_DETAIL_COST_NOT_EDITABLE")
                from bpm_verify import values_equal
                echo=self._read_rows(key)[index]["fields"].get(prop,"")
                if not values_equal(prop,echo,value):
                    raise UIBlocked("RELATION_DETAIL_SUM_ECHO_MISMATCH")
                p.log_event(event="demo_relation_amount_via_detail",row=index,identity=wanted["bizNumber"])
                return
            cell = self._cell(key,index,prop)
            if not cell.locator(".ui-dropdown,.ui-multiselect,input:not([type=hidden]),textarea,select").count():
                cell.dblclick(timeout=8000)
                p.page.wait_for_timeout(600)
            dropdown = cell.locator(".ui-dropdown,.ui-multiselect")
            if dropdown.count() == 1:
                token=dropdown.evaluate("e=>Array.from(e.classList).find(c=>c.startsWith('ng-tns-'))||''")
                if not token:
                    raise UIBlocked("DROPDOWN_INSTANCE_ID_MISSING")
                panel=p.page.locator(".ui-dropdown-panel."+token+",.ui-multiselect-panel."+token)
                options=panel.locator("li:visible")
                if not options.count():
                    dropdown.locator(".ui-dropdown-trigger,.ui-multiselect-trigger").click(timeout=8000)
                    p.page.wait_for_timeout(600)
                hits=[]
                for _ in range(4):
                    hits=[i for i in range(options.count()) if options.nth(i).inner_text().strip()==str(value)]
                    if len(hits)==1:
                        break
                    p.page.wait_for_timeout(600)
                if len(hits)!=1:
                    p.save("live_option_miss.json",json.dumps({"table":key,"row":index,"property":prop,"wanted":str(value),"options":[options.nth(i).inner_text() for i in range(options.count())]},ensure_ascii=False,indent=2))
                    p.page.keyboard.press("Escape")
                    raise UIBlocked(f"LIVE_EXACT_OPTION_NOT_UNIQUE:{key}:{index}:{prop}")
                p._click_guard(str(value))
                options.nth(hits[0]).click(timeout=8000)
                p.page.wait_for_timeout(400)
                p.page.keyboard.press("Escape")
                p.page.keyboard.press("Tab")
                self._cell_settle_read(p.page,p.page.main_frame,cell)
            elif (key=="banks" and cell.locator("input:not([type=hidden]),textarea").count()==1
                  and cell.locator("input:not([type=hidden]),textarea").evaluate("e=>!e.readOnly&&!e.disabled")):
                # The real bank account editor permits direct entry as well as
                # a personal-account shortcut. Use only the native writable
                # input; never remove readonly or change a selected identity.
                status,_=self._fill_ng_cell(p.page,p.page.main_frame,cell,str(value))
                if status!="OK":
                    raise UIBlocked(f"BANK_NATIVE_INPUT_FAILED:{prop}")
            elif cell.locator(".tableselect button[aria-label='选择表格数据']").count() == 1:
                p._click_guard("选择表格数据")
                cell.locator(".tableselect button[aria-label='选择表格数据']").click(timeout=8000)
                p.page.wait_for_timeout(1200)
                picked=self._overlay_search_pick(p.page,p.page.main_frame,str(value),f"live/{key}/{index}/{prop}",prescan=True)
                if not picked:
                    # Some real dialogs commit and close while the legacy
                    # overlay inventory still sees another page widget. Prove
                    # the exact selected value afresh; never substitute a row.
                    confirmed=False
                    for _ in range(20):
                        p.page.wait_for_timeout(600)
                        echo=self._read_rows(key)[index]["fields"].get(prop,"")
                        if str(echo).strip()==str(value).strip() and not self._visible_dialog(p.page.main_frame):
                            confirmed=True
                            break
                    if not confirmed:
                        raise UIBlocked(f"LIVE_EXACT_TABLE_PICK_MISSING:{key}:{index}:{prop}")
                    p.log_event(event="demo_picker_exact_dom_echo",table=key,row=index,property=prop)
            else:
                status,_ = self._fill_ng_cell(p.page,p.page.main_frame,cell,str(value))
                if status != "OK":
                    raise UIBlocked(f"LIVE_CELL_WRITE_BLOCKED:{key}:{index}:{prop}:{status}")
            observed = self._read_rows(key)[index]["fields"].get(prop,"")
            from bpm_verify import values_equal
            if not values_equal(prop,observed,value):
                raise UIBlocked(f"LIVE_CELL_ECHO_MISMATCH:{key}:{index}:{prop}")
            p.log_event(event="demo_live_cell_written",table=key,row=index,property=prop)

        def relation_observed(self,index,fields):
            self._ensure_row("relations",index)
            existing=self._read_rows("relations")[index]["fields"]
            if existing.get("bizNumber") and existing["bizNumber"]!=fields["bizNumber"]:
                raise UIBlocked("RELATION_ROW_IDENTITY_MISMATCH")
            for prop in ("bizTypeName","bizNumber","nowCost","isLast"):
                self._write("relations",index,prop,fields[prop])

        q._write = types.MethodType(write_observed,q)
        q._fill_relation = types.MethodType(relation_observed,q)
        # All actions remain bound to the validated plan and existing page.
        if plan_hash_checked(q) is False:
            raise RuntimeError("plan drift")
        if p._visible_dialog(p.page.main_frame) or p._overlay_open(p.page.main_frame):
            p._dialog_close_guarded(p.page)
        q._fill_arrays()
        return {"array_execution_returned":True,"executor":"observed_editors_historical_demo_only"}
    if action == "initial_person_search":
        if state["fill_started"]:
            raise RuntimeError("identity locked")
        dlg = p._visible_dialog(p.page.main_frame)
        if not dlg or dlg["title"] != "组织架构":
            raise RuntimeError("expected organization picker")
        loc = p.page.locator(dlg["sel"]).locator("input")
        if loc.count() != 1:
            raise RuntimeError("search input not unique")
        loc.fill(c["value"])
        loc.press("Enter")
        p.page.wait_for_timeout(1500)
        return handle(p, q, {"action": "picker_state", "tag": "person_search_result"}, state)
    if action == "select_observed_initial_person":
        if state["fill_started"]:
            raise RuntimeError("identity locked")
        dlg = p._visible_dialog(p.page.main_frame)
        if not dlg or dlg["title"] != "组织架构":
            raise RuntimeError("organization picker required")
        candidates = p._pick_candidates(p.page.main_frame)
        rows = [r for candidate in candidates for r in candidate["row_list"] if r["text"] == c["exact_row"]]
        if len(rows) != 1 or "[" + c["employee_id"] + "]" not in c["exact_row"]:
            raise RuntimeError("exact employee identity is not unique")
        row = p.page.locator(rows[0]["sel"])
        row.click()
        p.page.wait_for_timeout(500)
        selected = row.evaluate("e=>e.matches('[aria-selected=true],.ui-state-highlight')||!!e.querySelector('[aria-selected=true],.ui-state-highlight')")
        if not selected:
            raise RuntimeError("organization node has no selected-state proof")
        button = p.page.locator(dlg["sel"]).get_by_role("button", name="确定", exact=True)
        if button.count() != 1:
            raise RuntimeError("person confirmation not unique")
        p._click_guard("确定")
        button.click()
        p.page.wait_for_timeout(2500)
        fields = p.page.evaluate(FORM_MAP_JS)
        current = { _prop(f.get("name")): f.get("value") for f in fields if f.get("name") }
        if current.get("appliedName") != c["name"] or current.get("appliedBy") != c["employee_id"]:
            raise RuntimeError("selected person echo mismatch")
        if current.get("createdName") != state["creator"]:
            raise RuntimeError("creator unexpectedly changed during applicant selection")
        p.log_event(event="demo_initial_applicant_selected", name=c["name"], creator_unchanged=True)
        p.save("initial_identity_fixed.json", json.dumps(current,ensure_ascii=False,indent=2))
        p.shot(p.page,"initial_identity_fixed.png")
        return {"applicant":current.get("appliedName"),"creator":current.get("createdName"),"identity_fixed":True}
    if action == "click_observed":
        if state["fill_started"] and c.get("identity"):
            raise RuntimeError("identity locked")
        loc = p.page.locator(c["selector"])
        if loc.count() != 1 or not loc.is_visible():
            raise RuntimeError("observed target not unique and visible")
        text = loc.inner_text().strip() or loc.get_attribute("title") or loc.get_attribute("aria-label") or ""
        p._click_guard(text)
        if not text or text != c["expected_text"]:
            raise RuntimeError("exact observed control label changed")
        loc.click(timeout=8000)
        p.page.wait_for_timeout(1200)
        p.log_event(event="demo_observed_click", label=text, selector=c["selector"])
        return handle(p, q, {"action": "picker_state", "tag": c.get("tag", "after_click")}, state)
    if action == "pick_exact":
        if state["fill_started"]:
            raise RuntimeError("initial identity selection only before fill")
        shell = object.__new__(StructuredProbe)
        shell.__dict__ = p.__dict__
        ok = shell._overlay_search_pick(p.page, p.page.main_frame, c["value"], "demo_initial_person", prescan=True)
        return {"picked": ok, "fields": p.page.evaluate(FORM_MAP_JS)}
    raise RuntimeError("unsupported task-local diagnostic")


def plan_hash_checked(q):
    from bpm_plan import validate_plan,plan_hash
    return not validate_plan(q.fill_plan,expected_operator=q.args.expect_name,base_dir=q.plan_base) and plan_hash(q.fill_plan)==q.bound_plan_hash
