"""诊断探查（进程内）：直接调用 bpm.browser_probe.main 复用 fill 计划 b
走到 products 档案选择器；对「名称」弹窗抓取网络响应（含弹窗首次目录加载）
并做交互变体（清空点放大镜=不过滤总量、输名称点放大镜），定位 2026-10-27
编号/名称关键字双 0 候选的数据源或交互原因。
不保存不提交；阻断行为与正式填写一致，仅增加只读诊断与守卫内查询点击。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import bpm.ui as ui_mod
from bpm.ui import UIBlocked

_WRITE_CELL = ui_mod.StructuredProbe._write_cell


def _snapshot_dialog(page):
    state = {}
    try:
        dialogs = page.locator(".ui-dialog:visible")
        state["dialog_count"] = dialogs.count()
        if dialogs.count() != 1:
            return state
        d = dialogs
        inp = d.locator("input:not([readonly]):not([disabled]):not([type=checkbox]):not([type=radio]):visible")
        state["input_count"] = inp.count()
        if inp.count():
            state["placeholder"] = inp.first.get_attribute("placeholder")
            state["input_value"] = inp.first.input_value()
        rows = d.locator("tbody tr:visible")
        state["rows_visible"] = rows.count()
        pages = [t.strip() for t in d.locator("[class*=paginator]").all_inner_texts() if t and t.strip()]
        state["pagination_text"] = " | ".join(pages)[:300]
        if rows.count():
            state["first_row_cells"] = [c.strip() for c in rows.first.locator(":scope > td").all_text_contents()]
    except Exception as exc:
        state["dump_error"] = repr(exc)
    return state


def _write_cell_instrumented(self, cell, field, value, where, native_priority=False, fallback_keywords=None):
    if "archive" not in str(where):
        return _WRITE_CELL(self, cell, field, value, where, native_priority, fallback_keywords)
    captured = []

    def on_response(resp):
        try:
            ct = resp.headers.get("content-type", "")
            url = resp.url
            if "json" in ct and "qiaodan.com" in url:
                body = ""
                try:
                    body = resp.text()[:2000]
                except Exception:
                    body = "<body-unavailable>"
                captured.append({"url": url.split("?")[0], "status": resp.status, "body": body})
        except Exception:
            pass

    self.page.on("response", on_response)
    try:
        return _WRITE_CELL(self, cell, field, value, where, native_priority, fallback_keywords)
    except UIBlocked as exc:
        if "EXACT_PICK_MISSING" not in str(exc):
            raise
        diag = {"where": str(where),
                "keywords_tried": [str(value)] + [str(k) for k in (fallback_keywords or [])],
                "dialog_at_block": _snapshot_dialog(self.page),
                "responses_picker_phase": captured[-16:],
                "interaction_variants": {}}
        try:
            page = self.page
            d = page.locator(".ui-dialog:visible")
            if d.count() == 1:
                inp = d.locator("input:not([readonly]):not([disabled]):not([type=checkbox]):not([type=radio]):visible")
                icon = d.locator("button:has(.fa-search), button:has(.pi-search), .ui-button:has(.fa-search), i.fa-search, i.pi-search, span.fa-search")
                diag["icon_candidate_count"] = icon.count()
                if inp.count() == 1 and icon.count() >= 1:
                    inp.fill("", timeout=4000)
                    self._click_guard("档案查询图标")
                    icon.first.click(timeout=4000)
                    page.wait_for_timeout(1800)
                    diag["interaction_variants"]["icon_click_empty"] = {
                        "state": _snapshot_dialog(page), "responses": captured[-4:]}
                    inp.fill(str((fallback_keywords or [value])[-1]), timeout=4000)
                    self._click_guard("档案查询图标")
                    icon.first.click(timeout=4000)
                    page.wait_for_timeout(1800)
                    diag["interaction_variants"]["icon_click_name"] = {
                        "state": _snapshot_dialog(page), "responses": captured[-4:]}
        except Exception as exc2:
            diag["variant_error"] = repr(exc2)
        self.save("picker_probe_diag.json", json.dumps(diag, ensure_ascii=False, indent=1))
        self.log_event(event="picker_probe_diag", where=str(where),
                       rows=diag["dialog_at_block"].get("rows_visible"),
                       placeholder=diag["dialog_at_block"].get("placeholder"),
                       icon_candidates=diag.get("icon_candidate_count"),
                       responses=len(captured))
        raise
    finally:
        try:
            self.page.remove_listener("response", on_response)
        except Exception:
            pass


ui_mod.StructuredProbe._write_cell = _write_cell_instrumented

from bpm import browser_probe  # noqa: E402

raise SystemExit(browser_probe.main([
    "--run", "tpl-copy-picker-probe-20261027",
    "--expect-name", "陈晶",
    "--fill-plan", "automation/type-replay-plans/tpl-copy-review-20261027/fill_plan_b.json",
    "--keep-open-minutes", "0",
]))
