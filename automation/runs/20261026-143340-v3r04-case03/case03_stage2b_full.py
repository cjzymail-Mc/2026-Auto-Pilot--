# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段二b（浏览器只读）：全量宽窗查询（无制单人过滤）+ 全分页捕获。

背景（attempt_006 证据）：制单人 clear-icon 点击后自动查询曾发出 CreatedPath='/'（全组织
2025 年 total=52），但随后的 查询 点击又带回 CreatedPath=陈晶（9 行）——表单模型回填。
本轮策略：
- 日期窗放宽 申请日期+制单日期 = 2025-01-01..2026-12-31（覆盖 2026 年初补申请的 2025 年末行程）；
- 制单人清空用真实 Playwright click(force) 触发 Angular 处理器；
- 查询后从捕获的 post_data 里核实最终过滤器（不得含 CreatedPath 具体人）才继续分页；
- 全分页捕获 + 每页 DOM/截图；全程零业务写入。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case03_probe import TripProbe, RUN, EXPECT_NAME  # noqa: E402
from stage1_browser_probe import HOST, PASS  # noqa: E402

TRIP_URL = HOST + "/oa/workouts"
DATE_FROM, DATE_TO = "2025-01-01", "2026-12-31"
MAX_PAGES = 30


def query_filters(caps, p):
    """从捕获里取最后一个 WorkOut/query 的过滤器摘要。"""
    last = None
    for c in caps:
        if re.search(r"/WorkOut/query/\d+/\d+$", c["path"]):
            payload = json.loads((p.ev / c["file"]).read_text(encoding="utf-8"))
            pd = payload.get("post_data") or ""
            try:
                args = json.loads(pd).get("args", [])
            except Exception:
                args = []
            last = {a.get("propertyName"): str(a.get("text", ""))[:70]
                    for a in args if isinstance(a, dict)}
    return last


def main() -> int:
    from types import SimpleNamespace
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "wide-window full capture", "date_from": DATE_FROM,
                "date_to": DATE_TO, "pages": [], "rows_total": None,
                "final_filters": None}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("wide query requires verified login")
        p._save_session_state()
        p._arm_capture()
        page = p.page

        page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        # 日期四格：[0]/[1]=申请日期起/止，[2]/[3]=制单日期起/止（映射验证同 stage2）
        pickers = page.locator("qd-desktop-date-picker input.ui-inputtext")
        n = pickers.count()
        if n < 6:
            reason = "DATE_PICKERS_NOT_FOUND"
            raise ValueError(f"expected 6 date pickers, got {n}")
        defaults = [pickers.nth(i).input_value() for i in range(n)]
        p.log_event(event="date_picker_defaults", values=defaults)
        if defaults[2] != "2026-10-01":
            reason = "DATE_PICKER_MAPPING_UNEXPECTED"
            raise ValueError(f"picker[2] expected 2026-10-01, got {defaults[2]!r}")
        for idx, value in ((0, DATE_FROM), (1, DATE_TO), (2, DATE_FROM), (3, DATE_TO)):
            el = pickers.nth(idx)
            el.click()
            el.fill(value)
            el.press("Enter")
            page.wait_for_timeout(700)
            got = el.input_value()
            p.log_event(event="date_set", index=idx, want=value, got=got)
            if got != value:
                reason = "DATE_SET_FAILED"
                raise ValueError(f"date picker {idx} did not accept {value}: {got!r}")

        # 制单人清空：真实 click（force 绕开输入遮挡）触发 Angular 处理器
        creator = page.locator("input#CreatedPath2")
        if creator.count() == 1 and creator.input_value().strip():
            icon = page.locator(".form-row.CreatedPath .clear-icon")
            creator.hover()
            page.wait_for_timeout(300)
            icon.first.click(timeout=8000, force=True)
            page.wait_for_timeout(800)
            p.log_event(event="creator_filter_cleared", after=creator.input_value())

        p.shot(page, "wide-query-before.png")
        btn = page.get_by_role("button", name="查询", exact=True)
        if btn.count() != 1:
            reason = "QUERY_BUTTON_NOT_UNIQUE"
            raise ValueError(f"查询 button count={btn.count()}")
        p._click_guard("查询")
        btn.click(timeout=8000)
        page.wait_for_timeout(2500)

        # 核实最终查询过滤器：不得包含具体人 CreatedPath（'/' 全组织可接受）
        caps = p._drain_capture("wide-q0")
        final = query_filters(caps, p)
        manifest["final_filters"] = final
        p.log_event(event="wide_query_filters", filters=final)
        if final and final.get("CreatedPath") not in (None, "/", ""):
            reason = "CREATOR_FILTER_LEAKED"
            raise ValueError(f"final query still filters creator: {final.get('CreatedPath')}")
        # 已捕获的 wide-q0 里可能已含首页响应——由分页循环统一重查（重新查询一次保证顺序简单）
        p._click_guard("查询")
        btn.click(timeout=8000)
        page.wait_for_timeout(2500)

        page_no = 0
        while page_no < MAX_PAGES:
            page_no += 1
            for _ in range(20):
                if p._captured:
                    break
                page.wait_for_timeout(500)
            caps = p._drain_capture(f"wide-page{page_no:02d}")
            body = None
            for c in caps:
                m = re.search(r"/WorkOut/query/(\d+)/(\d+)$", c["path"])
                if m and int(m.group(2)) == page_no:
                    payload = json.loads((p.ev / c["file"]).read_text(encoding="utf-8"))
                    body = payload["body"]
                    manifest["pages"].append({
                        "page": page_no, "size": int(m.group(1)), "evidence": c["file"],
                        "sha256": c["sha256"], "rows": len(body.get("data") or []),
                        "filters": {a.get("propertyName"): str(a.get("text", ""))[:70]
                                    for a in (json.loads(payload.get("post_data") or '{"args":[]}').get("args", []))
                                    if isinstance(a, dict)}})
            if body is None:
                p.log_event(event="page_no_query_response", page=page_no)
                break
            rows = page.evaluate("""() => [...document.querySelectorAll('table tbody tr')]
                .map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText || '').trim()))""")
            p.save(f"wide-rows-page{page_no:02d}.json", json.dumps(rows, ensure_ascii=False, indent=1))
            p.shot(page, f"wide-list-page{page_no:02d}.png")
            has_next = bool(body.get("hasNextPage"))
            p.log_event(event="wide_page_captured", page=page_no,
                        api_rows=len(body.get("data") or []), dom_rows=len(rows),
                        totalCount=body.get("totalCount"), hasNextPage=has_next)
            manifest["rows_total"] = body.get("totalCount")
            if not has_next:
                break
            nxt = page.locator("p-paginator .ui-paginator-next:not(.ui-state-disabled), "
                               ".ui-paginator .ui-paginator-next:not(.ui-state-disabled)")
            if nxt.count() == 0:
                p.log_event(event="next_button_missing", page=page_no)
                break
            p._click_guard("下一页")
            nxt.first.click(timeout=8000)
            page.wait_for_timeout(2200)

        manifest["pages_captured"] = page_no
        reason = "WIDE_CAPTURED"
        p.result["case03_wide"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_wide"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage2b_end", status=reason,
                    pages=len(manifest.get("pages", [])), rows_total=manifest.get("rows_total"))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "wide-query-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
