# -*- coding: utf-8 -*-
"""V3-R07 关联控件可选单据枚举探针（只读枚举，零选择零保存）。

冻结依据：team-task src-c1c5d877 / 合同 ctr-affef776 冻结范围 2；V3 §5.3。
目的：在真实新建差旅费页的关联表中打开真实 relation dialog，枚举当前可选单据
（默认首屏，不翻页），落盘 JSON+截图后关闭弹窗，不做任何选择、不点确定、
不保存；关闭后核实关联行 bizNumber 仍为空（零选择副作用）。

白名单点击：新增 / 单据类型下拉选择『公出单』（打开公出单弹窗所需）/ 选择表格数据 /
弹窗关闭（X 或 Escape）。保存/提交/发送/流转/上传/暂存/贴票/审批/确定 一律不存在于
本脚本；任何未知弹框不确认。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from stage1_browser_probe import (BASE, HOST, NEW_FORM_PATH, PASS, Probe,
                                  TABLE_MAP_JS, assert_internal)

ALLOWED_CLICKS = {"新增", "选择表格数据", "公出单"}


class EnumProbe(Probe):
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

    def _guard(self, what):
        if what not in ALLOWED_CLICKS:
            self.log_event(event="ENUM_CLICK_BLOCKED", what=what)
            raise RuntimeError("non-whitelisted click blocked: " + str(what))
        self.log_event(event="enum_click", what=what)

    def _relations_table(self, frame):
        tables = frame.evaluate(TABLE_MAP_JS) or []
        hits = [t for t in tables if t.get("title") == "关联单据"
                and any(h.get("prop") == "bizNumber" for h in t.get("headers", []))]
        if len(hits) != 1:
            self.save("enum_table_candidates.json", json.dumps(tables, ensure_ascii=False, indent=1))
            raise RuntimeError("relations table not unique: %d" % len(hits))
        return hits[0]

    def enumerate_dialog(self):
        page = self.page
        page.goto(assert_internal(HOST + NEW_FORM_PATH), wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        frame, _ = self._form_frame(page)
        table = self._relations_table(frame)
        col = {h.get("prop"): i for i, h in enumerate(table.get("headers", []))}
        root_sel = "qd-dynamic-table:has(th.prop-bizNumber)"
        if page.locator(root_sel).count() != 1:
            raise RuntimeError("relations component not unique: %d" % page.locator(root_sel).count())
        root = page.locator(root_sel)
        if root.count() != 1:
            raise RuntimeError("relations component not unique: %d" % root.count())
        self._guard("新增")
        add = root.get_by_role("button", name="新增", exact=True)
        if add.count() != 1:
            # 与 bpm_ui._ensure_row 同口径：实际工具栏按钮 title 有值但无可见文本
            add = root.locator("button[title='新增']")
        if add.count() != 1:
            raise RuntimeError("add button not unique")
        add.click(timeout=8000)
        page.wait_for_timeout(1500)
        body = root.locator(".ui-table-scrollable-body > table")
        if body.count() != 1:
            body = root.locator(" > table")
        rows = body.locator("tbody tr")
        if rows.count() < 1:
            raise RuntimeError("new relation row not created")
        row0 = rows.nth(0)
        self.shot(page, "enum_01_row_added.png")

        # —— bizTypeName 下拉：对齐 bpm_ui._pick_option 口径（ng-tns token 限定面板 + 600ms 轮询 + 精确文本）。
        # attempt_001 教训：新增行后编辑态已挂载且面板可能已展开（enum_01 截图早于任何单元格交互），
        # 此时无条件 dblclick/组件 click 都是 toggle，会把已开面板点收起 → 面板内 0 项。
        # 故先探测已挂载编辑器与已开面板，仅当面板未开时才点 trigger。
        from bpm_ui import _same
        type_cell = row0.locator("td").nth(col["bizTypeName"])
        dd = type_cell.locator(".ui-dropdown")
        if dd.count() != 1:
            type_cell.dblclick(timeout=8000)
            page.wait_for_timeout(600)
            dd = type_cell.locator(".ui-dropdown")
        if dd.count() != 1:
            self.save("enum_02a_type_cell_html.json", json.dumps(
                {"bizTypeName_cell_html": type_cell.evaluate("e=>e.outerHTML")}, ensure_ascii=False))
            raise RuntimeError("bizTypeName dropdown not mounted: %d" % dd.count())
        token = dd.evaluate("e=>Array.from(e.classList).find(c=>c.startsWith('ng-tns-'))||''")
        if not token:
            raise RuntimeError("bizTypeName dropdown token missing")
        panel = page.locator(".ui-dropdown-panel." + token)
        opts = panel.locator("li:visible")
        if not opts.count():
            trigger = dd.locator(".ui-dropdown-trigger")
            (trigger if trigger.count() == 1 else dd).click(timeout=8000)
            page.wait_for_timeout(600)
            opts = panel.locator("li:visible")
        hits = []
        type_options = []
        for _ in range(4):
            page.wait_for_timeout(600)
            type_options = [opts.nth(i).inner_text() for i in range(opts.count())]
            hits = [i for i, t in enumerate(type_options) if _same(t, "公出单")]
            if len(hits) == 1:
                break
        if len(hits) != 1:
            self.save("enum_02a_type_panel_state.json", json.dumps(
                {"token": token, "option_count": opts.count(), "options": type_options},
                ensure_ascii=False))
            page.keyboard.press("Escape")
            raise RuntimeError("bizTypeName option 公出单 not unique: %d" % len(hits))
        self.shot(page, "enum_02a_type_panel_open.png")
        self._guard("公出单")
        opts.nth(hits[0]).click(timeout=8000)
        page.wait_for_timeout(600)
        # 与 bpm_ui._write_cell 下拉分支同口径：选中后 Escape 退出单元格编辑态
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # —— bizNumber 弹窗按钮：对齐 bpm_ui._activate 语义——先探测已挂载编辑器，未挂载才 dblclick
        num_cell = row0.locator("td").nth(col["bizNumber"])
        btn = num_cell.locator(".tableselect button[aria-label='选择表格数据']")
        if not btn.count():
            num_cell.dblclick(timeout=8000)
            page.wait_for_timeout(600)
            btn = num_cell.locator(".tableselect button[aria-label='选择表格数据']")
        if btn.count() != 1:
            self.save("enum_02_cell_html.json", json.dumps(
                {"bizNumber_cell_html": num_cell.evaluate("e=>e.outerHTML")}, ensure_ascii=False))
            raise RuntimeError("relation dialog button not unique: %d" % btn.count())
        self._guard("选择表格数据")
        btn.click(timeout=8000)
        page.wait_for_timeout(2500)
        dialogs = page.locator(".ui-dialog:visible")
        if dialogs.count() != 1:
            raise RuntimeError("relation dialog not unique: %d" % dialogs.count())
        dialog = dialogs.first
        title = (dialog.locator(".ui-dialog-title").first.inner_text() or "").strip()
        headers = [h.strip() for h in dialog.locator("thead th").all_inner_texts()]
        drows = dialog.locator("tbody tr:visible")
        count = drows.count()
        data = []
        for i in range(count):
            data.append([c.strip() for c in drows.nth(i).locator(":scope > td").all_text_contents()])
        paginator = ""
        pag = dialog.locator(".ui-paginator")
        if pag.count():
            paginator = (pag.first.inner_text() or "").strip().replace("\n", " ")
        self.shot(page, "enum_03_dialog_first_page.png")
        self.save_html(page, "enum_03_dialog.html")

        # 关闭：优先标题栏 X；不存在则 Escape。绝不点击 确定/选择 类按钮。
        closer = dialog.locator(".ui-dialog-titlebar-close")
        closed_by = "titlebar_close"
        if closer.count() == 1:
            closer.first.click(timeout=8000)
        else:
            closed_by = "escape"
            page.keyboard.press("Escape")
        page.wait_for_timeout(1500)
        if page.locator(".ui-dialog:visible").count():
            raise RuntimeError("relation dialog still visible after close")
        num_after = (num_cell.evaluate(
            "td=>{const i=td.querySelector('input:not([type=hidden])');return i?i.value:(td.textContent||'').trim();}") or "")
        enumeration = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "scope": "真实 relation dialog 默认首屏（未翻页、未检索、未选择）",
            "dialog_title": title, "headers": headers, "row_count": count,
            "rows": data, "paginator_text": paginator,
            "bizTypeName_options_observed": type_options,
            "closed_by": closed_by, "selection_performed": False,
            "bizNumber_after_close": num_after,
            "notes": ["首屏即真实可选单据实际枚举值（V3 §5.3 来源=真实关联控件）",
                      "行数不强行等于真实票数/公出单数；本枚举仅供建模随机占位选择",
                      "bizTypeName_options_observed=选公出单时该下拉面板实际渲染的完整选项清单（证据）"],
        }
        self.save("relation_enumeration.json", json.dumps(enumeration, ensure_ascii=False, indent=2))
        self.shot(page, "enum_04_after_close.png")
        if num_after:
            raise RuntimeError("bizNumber non-empty after dialog close (unexpected selection)")
        return enumeration


def main():
    run = "20261026-181500-v3r07-fill"
    expect = sys.argv[1] if len(sys.argv) > 1 else "陈晶"
    p = EnumProbe(SimpleNamespace(run=run, doc_id=None, expect_name=expect,
                                  tech_budget=1800, login_wait=480, wall_cap=2400,
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
            raise ValueError("relation enumeration requires verified login")
        p._save_session_state()
        with p._timing("relation_enumeration"):
            enum = p.enumerate_dialog()
        p.log_event(event="relation_enumeration_done", rows=enum["row_count"],
                    selection_performed=False, closed_by=enum["closed_by"])
        reason = "SUCCESS_RELATION_ENUM_ONLY"
        print(json.dumps({"status": reason, "rows": enum["row_count"],
                          "run": run, "attempt": p.attempt.name}, ensure_ascii=False))
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.atomic_result()
        p.log_event(event="relation_enum_end", status=reason)
        p._close_browser()
        p.release_lock()
        p.budget.close()


if __name__ == "__main__":
    sys.exit(main())
