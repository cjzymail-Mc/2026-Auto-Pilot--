"""Round-10（ctr-8cb7b247 §2）02/04 真实新表单只读控件观察（零业务行写入、零保存）。

观察面（对应两 config required_observations 前两项 + 跨部门预算范围）：
  1) 新表单 header 编辑器形态（required/readonly/editor 类型，类别选择前后对比）；
  2) submitType 类别选择器在册选项（live）→ 选定 02/04 后的表结构重建（TABLE_MAP）；
  3) reimItem 联动枚举（02xxx / 04xxx 前缀核对）；
  4) budgetNo / subjectName 预算选择器选项与数据范围（是否含非申请人部门预算主体）；
  5) relations 行 bizTypeName 关联类型枚举（申请书34 / 福利申请单74 在册核对）与
     关联单据明细（detailrels）表形态。

纪律：仅控件级交互——类别选择、新增空行（仅为暴露行内选择器）、打开下拉浮层枚举、
Escape 收起。零字段值键入、零保存/发送/流转/提交（NO_SAVE_WORDS 全程守卫）、
页尾盘点后不保存弃页。所有点击过 guard_click；事件 mask，原始枚举进 attempt 证据。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import stage1_browser_probe as pb                                     # noqa: E402
from stage1_browser_probe import (DIALOG_DUMP_JS, FORM_MAP_JS, HOST, NEW_FORM_PATH,   # noqa: E402
                                  NO_SAVE_WORDS, Probe, TABLE_MAP_JS,
                                  assert_internal, mask)

TARGETS = [
    # (document_type, 码, 类别选项词, reimItem 期望前缀, 关联类型期望词)
    ("office_supplies", "02", "低值易耗品、办公用品采购", "02", "申请书"),
    ("welfare_labor", "04", "福利费、劳保用品", "04", "福利申请单"),
]


def guard_click(what):
    word = re.sub(r"\s+", "", (what or ""))
    if not word or any(bad in word or word in bad for bad in NO_SAVE_WORDS if bad):
        raise RuntimeError("NO_SAVE_GUARD: 拒绝点击「{0}」".format(what))
    return True


class Observe0204:
    def __init__(self, args):
        self.args = args
        probe_args = SimpleNamespace(
            run=args.run, doc_id=None, expect_name=args.expect_name,
            tech_budget=1500.0, login_wait=args.login_wait, wall_cap=2100.0,
            interactive_pick=False, pick_wait=0.0, keep_open_minutes=0.0,
            fill_plan=None)
        self.p = Probe(probe_args)     # 复用锁/启动/登录门/落盘，不跑其 main 流程
        self.page = None

    # ---- 只读枚举原语 ----
    def open_options(self, comp, tag):
        """打开 p-dropdown 浮层 → 枚举可见选项 → Escape 收起（不点任何选项）。
        comp 可为选择器字符串或 Locator。"""
        page = self.p.page
        loc = page.locator(comp).first if isinstance(comp, str) else comp
        opts = []
        for _ in range(2):                       # 首点可能未开出浮层：重开一次
            try:
                loc.scroll_into_view_if_needed()
                loc.click()
            except Exception as exc:
                self.p.log_event(event="observe_picker_open_failed", where=tag,
                                 error=repr(exc)[:120])
                break
            for _ in range(4):
                page.wait_for_timeout(600)
                cands = page.locator(pb.Probe._OPT_SEL)
                n = cands.count()
                if n:
                    for i in range(min(n, 80)):
                        try:
                            opts.append((cands.nth(i).inner_text() or "").strip().replace("\n", " "))
                        except Exception:
                            continue
                    break
            if opts:
                break
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        self.p.log_event(event="observe_picker_enum", where=tag,
                         options_masked=[mask(text)[:48] for text in opts[:15]],
                         option_count=len(opts))
        return opts

    def cell_picker_enum(self, tables, prop, code):
        """行内格选择器枚举：dblclick 激活格 → dropdown 浮层 或『选择表格数据』搜索弹窗。
        返回 {mode, options|dialog}——弹窗模式记录表头/前 30 行/分页文本（跨部门范围证据）。"""
        page = self.p.page
        table = self.table_by_prop(tables, "reimItem")
        if table is None:
            return {"status": "TABLE_MISSING"}
        live = page.evaluate(TABLE_MAP_JS)
        # _path 路径随 DOM 增删漂移（bpm_ui 实证）：改按列 prop 签名匹配同一张表
        wanted = [h.get("prop") for h in table.get("headers", [])]
        live_table = next((t for t in live
                           if [h.get("prop") for h in t.get("headers", [])] == wanted), None)
        if live_table is None:
            return {"status": "LIVE_TABLE_MISSING"}
        if live_table.get("row_count", 0) < 1:
            return {"status": "ROW_MISSING"}
        headers = live_table.get("headers", [])
        indices = [i for i, h in enumerate(headers) if h.get("prop") == prop]
        if len(indices) != 1:
            return {"status": "COLUMN_NOT_UNIQUE"}
        cell = page.locator(live_table["body_sel"] or live_table["sel"]).first \
            .locator("tbody tr").first.locator("td").nth(indices[0])
        try:
            cell.scroll_into_view_if_needed()
            info = page.evaluate(pb.CELL_INFO_JS, cell.element_handle()) if hasattr(pb, "CELL_INFO_JS") else {}
            self.p.log_event(event="observe_cell_before_activate",
                             where="{0}/details/{1}".format(code, prop),
                             text=mask((info or {}).get("text", ""))[:30],
                             editors=(info or {}).get("editors") if isinstance(info, dict) else None)
            cell.dblclick(timeout=8000)          # 激活编辑器（沿用 fill 路径已验证机制）
            page.wait_for_timeout(800)
        except Exception as exc:
            return {"status": "ACTIVATE_FAILED", "error": repr(exc)[:120]}
        dropdown = cell.locator(".ui-dropdown,.ui-multiselect")
        if dropdown.count() == 1:
            options = self.open_options(dropdown.first, "{0}/details/{1}".format(code, prop))
            page.keyboard.press("Escape")
            return {"mode": "dropdown", "option_count": len(options), "options": options[:60]}
        button = cell.locator(".tableselect button[aria-label='选择表格数据']")
        self.p.log_event(event="observe_cell_editor_state",
                         where="{0}/details/{1}".format(code, prop),
                         dropdown_count=dropdown.count(),
                         button_count=button.count(),
                         button_visible=(button.count() == 1 and button.first.is_visible()),
                         cell_html_len=len(cell.evaluate("e=>e.outerHTML") or ""))
        if button.count() == 1:
            guard_click("选择表格数据")
            button.click(timeout=8000)
            page.wait_for_timeout(1500)
            # 『选择表格数据』开 p-dialog 弹表（mask/搜索框/分页表格/确定取消）——
            # 以 DIALOG_DUMP_JS 泛化枚举（.ui-dialog/p-dialog/[role=dialog]）
            dumped = page.evaluate(DIALOG_DUMP_JS) or []
            inventory = [{"title": mask(d.get("title") or "")[:40],
                          "tables": d.get("tables"), "sel": d.get("sel")}
                         for d in dumped]
            chosen = next((d for d in dumped if d.get("tables")), None)
            if chosen is None:
                self.p.log_event(event="observe_budget_dialog_blocked",
                                 where="{0}/{1}".format(code, prop),
                                 dialogs=inventory)
                page.keyboard.press("Escape")
                return {"mode": "table_dialog", "status": "NO_TABLE_DIALOG",
                        "dialogs": inventory}
            dialog = page.locator(chosen["sel"]).first
            title = (dialog.locator(".ui-dialog-title, .ui-dialog-titlebar").first
                     .inner_text() or "").strip()
            header_cells = [h.strip() for h in dialog.locator("thead th").all_text_contents()]
            rows_loc = dialog.locator("tbody tr:visible")
            rows = []
            for i in range(min(rows_loc.count(), 30)):
                rows.append([mask(c)[:36] for c in
                             rows_loc.nth(i).locator(":scope > td").all_text_contents()])
            paginator = (dialog.locator(".ui-paginator").first.inner_text() or
                         "").replace("\n", " ").strip()
            shot = self.p.shot(page, "budget_dialog_{0}_{1}.png".format(code, prop))
            raw = {"title": title, "headers": header_cells, "row_count": rows_loc.count(),
                   "rows": [r for r in rows], "paginator": paginator,
                   "dialog_inventory": inventory}
            self.p.save("budget_dialog_{0}_{1}.json".format(code, prop),
                        json.dumps(raw, ensure_ascii=False, indent=1))
            # 只读收起：优先页脚 关闭/取消/×（均非守卫词），否则 Escape
            closed = False
            footer = dialog.locator(".ui-dialog-footer button, .ui-dialog-footer a, "
                                    "[class*='footer'] button")
            for i in range(footer.count()):
                text = (footer.nth(i).inner_text() or "").strip()
                if text in ("关闭", "取消") and footer.nth(i).is_enabled():
                    guard_click(text)
                    try:
                        footer.nth(i).click(timeout=8000)
                    except Exception:
                        pass
                    closed = True
                    break
            if not closed:
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.keyboard.press("Escape")
            page.wait_for_timeout(600)
            self.p.log_event(event="observe_budget_dialog", where="{0}/{1}".format(code, prop),
                             title=mask(title)[:40], row_count=rows_loc.count(),
                             headers=header_cells[:12], paginator=mask(paginator)[:60],
                             screenshot=shot)
            return {"mode": "table_dialog", **raw, "screenshot": shot}
        return {"mode": "unknown_editor", "cell_text": mask((cell.inner_text() or "").strip())[:40]}

    def form_map(self, scope=None):
        return self.page.evaluate(FORM_MAP_JS, scope)

    def wait_form(self, timeout_s=30.0):
        """等新表单挂载：submitType 字段在 FORM_MAP 出现 + 沉降。"""
        for _ in range(int(timeout_s)):
            fields = self.form_map()
            if fields and any(f.get("name") == "submitType" for f in fields):
                self.page.wait_for_timeout(1200)
                return self.form_map()
            self.page.wait_for_timeout(1000)
        raise RuntimeError("NEW_FORM_MOUNT_TIMEOUT")

    def wait_tables_stable(self):
        """类别重建后等表结构稳定（连续两次签名一致；600ms×20，沿用已验证节奏）。"""
        previous = None
        for _ in range(20):
            self.page.wait_for_timeout(600)
            tables = self.page.evaluate(TABLE_MAP_JS)
            signature = [(t.get("title"), [h.get("prop") for h in t.get("headers", [])])
                         for t in tables]
            if signature and signature == previous:
                return tables
            previous = signature
        return self.page.evaluate(TABLE_MAP_JS)

    @staticmethod
    def unique_field(fields, name):
        hits = [f for f in fields if f.get("name") == name]
        return hits[0] if len(hits) == 1 else None

    def table_by_prop(self, tables, prop):
        for table in tables:
            if any(h.get("prop") == prop for h in table.get("headers", [])):
                return table
        return None

    def component_sel(self, table):
        """bpm_ui 同源锚定：qd-dynamic-table + 全列 prop 签名 :has() 链（唯一命中）。"""
        props = [h.get("prop") for h in table.get("headers", []) if h.get("prop")]
        if not props or any(not re.fullmatch(r"[\w-]+", p) for p in props):
            return None
        root = "qd-dynamic-table" + "".join(":has(th.prop-{0})".format(p) for p in props)
        return root if self.page.locator(root).count() == 1 else None

    def insert_row(self, table, tag):
        """新增空行（仅为暴露行内选择器；零字段写入）。"""
        root = self.component_sel(table) if table else None
        if not root:
            self.p.log_event(event="observe_table_component_not_unique", where=tag)
            return False
        button = self.page.locator(root).get_by_role("button", name="新增", exact=True)
        if button.count() != 1:
            button = self.page.locator(root).locator("button[title='新增']")
        if button.count() != 1:
            self.p.log_event(event="observe_add_button_not_unique", where=tag,
                             count=button.count())
            return False
        guard_click("新增")
        button.first.click(timeout=8000)
        self.page.wait_for_timeout(1200)
        return root

    # ---- 单类型观察 ----
    def observe_one(self, document_type, code, label, expect_prefix, relation_word):
        p = self.p
        page = self.page
        rec = {"document_type": document_type, "category_label": label}
        page.goto(assert_internal(HOST + NEW_FORM_PATH), wait_until="domcontentloaded",
                  timeout=45000)
        fields_before = self.wait_form()
        p.save("form_before_{0}.json".format(code), json.dumps(fields_before,
                                                               ensure_ascii=False, indent=1))
        rec["header_editors_before"] = [{"name": f.get("name"), "type": f.get("type"),
                                         "readonly": f.get("readonly"),
                                         "value": mask(f.get("value"))[:30]}
                                        for f in fields_before]
        shot1 = p.shot(page, "form_before_{0}.png".format(code))

        submit = self.unique_field(fields_before, "submitType")
        if submit is None or not submit.get("comp"):
            rec["error"] = "SUBMIT_TYPE_FIELD_NOT_UNIQUE"
            return rec
        # ① 类别选择器在册选项（live）
        rec["submit_type_options"] = self.open_options(submit["comp"],
                                                       "{0}/submitType".format(code))
        # ② 选定类别（控件级观察动作；页保持不保存）
        guard_click(label)
        picked = p._pick_option(page, page.main_frame,
                                page.locator(submit["comp"]).first, label, "dropdown")
        rec["category_picked"] = picked
        tables = self.wait_tables_stable()
        fields_after = self.form_map()
        p.save("form_after_{0}.json".format(code), json.dumps(fields_after,
                                                              ensure_ascii=False, indent=1))
        p.save("tables_{0}.json".format(code), json.dumps(tables, ensure_ascii=False, indent=1))
        rec["tables_after_category"] = [{"title": t.get("title"),
                                         "props": [h.get("prop") for h in t.get("headers", [])],
                                         "rows": t.get("row_count"),
                                         "has_add": bool(t.get("add_sel")),
                                         "has_pick": bool(t.get("pick_sel"))}
                                        for t in tables]
        shot2 = p.shot(page, "category_set_{0}.png".format(code))

        # ③ details 空行 → reimItem / budgetNo / subjectName 枚举
        details = self.table_by_prop(tables, "reimItem")
        row_editors = []
        details_root = self.insert_row(details, "{0}/details".format(code)) if details else False
        if details_root:
            row_editors = self.form_map(page.locator(details_root).first.element_handle())
            p.save("row_editors_{0}.json".format(code), json.dumps(row_editors,
                                                                   ensure_ascii=False, indent=1))
            # ③-1 reimItem 枚举（未选状态：渐进披露——其余列编辑器尚未挂载）
            for name in ("reimItem",):
                field = self.unique_field(row_editors, name)
                if field is None or not field.get("comp"):
                    rec["picker_{0}".format(name)] = {"status": "NOT_PRESENT"}
                else:
                    options = self.open_options(field["comp"],
                                                "{0}/details/{1}".format(code, name))
                    rec["picker_{0}".format(name)] = {
                        "option_count": len(options), "options": options[:60],
                        "prefix_hits": [text for text in options
                                        if re.search(r"\b{0}\d{{3,}}".format(expect_prefix),
                                                     text) or text.startswith(expect_prefix)]}
            # ③-2 自主裁决⑤（events/notes/handoff 披露）：reimItem 选一项=类别联动观察的
            # 必要控件动作（渐进披露：不选则 budgetNo/subjectName 编辑器不挂载），
            # 非业务数据写入——行内零金额/事由/收款/日期，页弃置不保存。
            reim_field = self.unique_field(row_editors, "reimItem")
            options = rec.get("picker_reimItem", {}).get("options") or []
            non_blank = [text for text in options if text.strip()]
            if reim_field and reim_field.get("comp") and non_blank:
                guard_click(non_blank[0])
                rec["reim_item_picked"] = p._pick_option(
                    page, page.main_frame, page.locator(reim_field["comp"]).first,
                    non_blank[0], "dropdown")
                page.wait_for_timeout(1500)
                row_editors = self.form_map(page.locator(details_root).first.element_handle())
                p.save("row_editors_after_reim_{0}.json".format(code),
                       json.dumps(row_editors, ensure_ascii=False, indent=1))
            # ③-3 预算选择器枚举 + 跨部门范围证据（行内格激活：dropdown 浮层或搜索弹窗）
            for name in ("budgetNo", "subjectName"):
                entry = self.cell_picker_enum(tables, name, code)
                if entry.get("mode") == "dropdown":
                    entry["non_applicant_dept_markers"] = [
                        text for text in entry.get("options", [])
                        if "部" in text and "运动表现研究部" not in text][:20]
                elif entry.get("mode") == "table_dialog" and entry.get("rows"):
                    entry["non_applicant_dept_markers"] = [
                        " | ".join(r for r in row if r) for row in entry["rows"]
                        if any("部" in cell and "运动表现研究部" not in cell for cell in row)][:12]
                rec["picker_{0}".format(name)] = entry
            shot3 = p.shot(page, "details_row_{0}.png".format(code))
            rec["details_row_screenshot"] = shot3
            # 行值盘点（零业务写入核对：除联动分类器外应全空）
            rec["details_row_values"] = [{"name": f.get("name"),
                                          "value": mask(f.get("value"))[:40]}
                                         for f in row_editors]

        # ④ relations 空行 → bizTypeName 关联类型枚举 + 关联单据明细表形态
        relations = next((t for t in tables
                          if any(h.get("prop") == "bizNumber" for h in t.get("headers", []))
                          and "关联" in (t.get("title") or "")), None)
        if relations is None:
            relations = self.table_by_prop(tables, "bizNumber")
        relations_root = self.insert_row(relations, "{0}/relations".format(code)) if relations else False
        if relations_root:
            rel_editors = self.form_map(page.locator(relations_root).first.element_handle())
            field = self.unique_field(rel_editors, "bizTypeName")
            if field and field.get("comp"):
                options = self.open_options(field["comp"], "{0}/relations/bizTypeName".format(code))
                rec["relation_type_options"] = options
                rec["relation_expected_word_present"] = any(
                    relation_word in text for text in options)
            p.shot(page, "relations_row_{0}.png".format(code))
        tables_now = self.page.evaluate(TABLE_MAP_JS)
        detail_rels = [t for t in tables_now
                       if "关联单据明细" in (t.get("title") or "")
                       or any(h.get("prop") == "bizNo" for h in t.get("headers", []))]
        rec["detailrels_table"] = [{"title": t.get("title"),
                                    "props": [h.get("prop") for h in t.get("headers", [])],
                                    "rows": t.get("row_count")}
                                   for t in detail_rels]
        rec["screenshots"] = [shot1, shot2]
        rec["page_url"] = mask(page.url)[:90]
        return rec

    # ---- 主流程 ----
    def run(self):
        p = self.p
        p.acquire_lock()
        rc = 0
        try:
            p._launch()
            self.page = p.page
            # 对话框（beforeunload 等）由 Probe._launch 统一 dismiss 处置，不在此重复注册
            p.log_event(event="observe_0204_start", run=self.args.run,
                        discipline="只读控件观察：零业务行写入/零保存/零提交，页弃置不保存")
            st = p.phase_entry()
            if st == "LOGIN_REQUIRED":
                if self.args.login_wait <= 0:
                    result = {"status": "LOGIN_GAP",
                              "gaps": ["登录态失效：本轮不扫码不等待（合同 §2），02/04 控件观察登记缺口，"
                                       "其余项继续；required_observations 不回填前两项"]}
                    p.save("observe_result.json", json.dumps(result, ensure_ascii=False, indent=1))
                    p.log_event(event="observe_login_gap", status="LOGIN_GAP")
                    return 3
                st = p.wait_login()
            if st != pb.PASS:
                p.say("登录未成立（{0}），终止观察".format(st))
                p.log_event(event="observe_aborted", reason=str(st))
                return 2
            p._save_session_state()

            results = []
            for document_type, code, label, prefix, relation_word in TARGETS:
                p.log_event(event="observe_target_start", document_type=document_type)
                try:
                    rec = self.observe_one(document_type, code, label, prefix, relation_word)
                except Exception as exc:
                    rec = {"document_type": document_type, "error": repr(exc)[:300]}
                    p.shot(self.page, "error_{0}.png".format(code))
                p.log_event(event="observe_target_done", document_type=document_type,
                            error=rec.get("error"),
                            tables=len(rec.get("tables_after_category") or []),
                            reimItem_count=(rec.get("picker_reimItem") or {}).get("option_count"),
                            relation_types=len(rec.get("relation_type_options") or []))
                results.append(rec)
                p.log_event(event="observe_page_abandoned", document_type=document_type,
                            saved=False, note="未保存弃页（零保存纪律）")
            payload = {"status": "OBSERVED", "run": self.args.run,
                       "operator": self.args.expect_name, "targets": results,
                       "discipline": "只读控件观察；零业务行写入；零保存；页弃置"}
            p.save("observe_result.json", json.dumps(payload, ensure_ascii=False, indent=1))
            p.log_event(event="observe_0204_done", status="OBSERVED",
                        targets=[r.get("document_type") for r in results])
        finally:
            for teardown in (lambda: p.ctx.close(), lambda: p._pw.stop()):
                try:
                    teardown()
                except Exception:
                    pass
        return rc


def main(argv=None):
    parser = argparse.ArgumentParser(description="02/04 真实新表单只读控件观察（round-10 §2）")
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S") + "-type0204-observe")
    parser.add_argument("--expect-name", default="陈晶")
    parser.add_argument("--login-wait", type=float, default=0.0,
                        help="默认 0：登录失效不扫码不等待（登记缺口后继续其余项）")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rc = Observe0204(args).run()
    print(json.dumps({"observe_run": args.run, "rc": rc}))
    sys.exit(rc)


if __name__ == "__main__":
    main()
