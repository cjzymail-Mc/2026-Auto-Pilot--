# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段二（浏览器只读）：公出单 2025 年定向查询 + 分页逐页捕获。

- 申请人筛选默认=陈晶（页面默认值，不改动）；日期区间 2025-01-01 → 2025-12-31；
  单据状态不过滤（已用单可能在任何状态）。
- 只点 查询 与分页箭头；逐页捕获 /WorkOut/query/*/* 响应 JSON + 页面快照；
  全程零业务写入（新增/修改/删除/流程/导出/跨月申请/返回 一律不碰）。
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
DATE_FROM, DATE_TO = "2025-01-01", "2025-12-31"
MAX_PAGES = 30


def main() -> int:
    from types import SimpleNamespace
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "targeted query 2025", "pages": [], "rows_total": None}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("query requires verified login")
        p._save_session_state()
        p._arm_capture()
        page = p.page

        page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        # 日期区间：6 个 qd-desktop-date-picker（HTML 锚文本映射实测：
        # [0]/[1]=申请日期起/止，[2]/[3]=制单日期起/止（默认起=当月1号，即漏 2025 的元凶），
        # [4]/[5]=公出时间起/止）。验证映射：默认带值的必须是 [2]。
        pickers = page.locator("qd-desktop-date-picker input.ui-inputtext")
        n = pickers.count()
        p.log_event(event="date_pickers_found", count=n)
        if n < 6:
            reason = "DATE_PICKERS_NOT_FOUND"
            raise ValueError(f"expected 6 date pickers, got {n}")
        defaults = [pickers.nth(i).input_value() for i in range(n)]
        p.log_event(event="date_picker_defaults", values=defaults)
        if defaults[2] != "2026-10-01":
            reason = "DATE_PICKER_MAPPING_UNEXPECTED"
            raise ValueError(f"picker[2] expected default 2026-10-01, got {defaults[2]!r}")
        for idx, value in ((0, DATE_FROM), (1, DATE_TO), (2, DATE_FROM), (3, DATE_TO)):
            el = pickers.nth(idx)
            el.click()
            el.fill(value)
            el.press("Enter")
            page.wait_for_timeout(600)
            got = el.input_value()
            p.log_event(event="date_set", index=idx, want=value, got=got)
            if got != value:
                reason = "DATE_SET_FAILED"
                raise ValueError(f"date picker {idx} did not accept {value}: {got!r}")

        # 制单人默认=陈晶会漏掉他人代制的单：点输入组内的 × clear-icon 清空（只读查询表单）
        creator = page.locator("input#CreatedPath2")
        if creator.count() == 1 and creator.input_value().strip():
            clear_icon = page.locator(".form-row.CreatedPath .clear-icon")
            if clear_icon.count() >= 1:
                creator.hover()
                page.wait_for_timeout(300)
                clear_icon.first.evaluate("el => el.click()")
                page.wait_for_timeout(500)
                p.log_event(event="creator_filter_cleared", before="陈晶",
                            after=creator.input_value())
            else:
                p.log_event(event="creator_filter_clear_icon_missing",
                            note="保留默认陈晶过滤；若出行日覆盖不全再二遍查询")

        # 申请人筛选保持页面默认（陈晶）；只读不动。查询前留证。
        p.shot(page, "query-before.png")

        btn = page.get_by_role("button", name="查询", exact=True)
        if btn.count() != 1:
            reason = "QUERY_BUTTON_NOT_UNIQUE"
            raise ValueError(f"查询 button count={btn.count()}")
        p._click_guard("查询")
        btn.click(timeout=8000)
        page.wait_for_timeout(2500)

        # 逐页捕获：解析响应拿 totalPages/hasNextPage，点下一页箭头翻页
        page_no = 0
        while page_no < MAX_PAGES:
            page_no += 1
            for _ in range(20):
                if p._captured:
                    break
                page.wait_for_timeout(500)
            caps = p._drain_capture(f"page{page_no:02d}")
            body = None
            for c in caps:
                m = re.search(r"/WorkOut/query/(\d+)/(\d+)$", c["path"])
                if m:
                    body = json.loads((p.ev / c["file"]).read_text(encoding="utf-8"))["body"]
                    manifest["pages"].append({"page": int(m.group(2)), "size": int(m.group(1)),
                                              "evidence": c["file"], "sha256": c["sha256"],
                                              "rows": len(body.get("data", []))})
            if body is None:
                p.log_event(event="page_no_query_response", page=page_no)
            rows = page.evaluate("""() => [...document.querySelectorAll('table tbody tr')]
                .map(tr => [...tr.querySelectorAll('td')].map(td => (td.innerText || '').trim()))""")
            p.save(f"rows-page{page_no:02d}.json", json.dumps(rows, ensure_ascii=False, indent=1))
            p.shot(page, f"list-page{page_no:02d}.png")
            total = body.get("totalCount") if body else None
            has_next = bool(body.get("hasNextPage")) if body else False
            p.log_event(event="page_captured", page=page_no, rows=len(rows),
                        api_rows=len(body.get("data", [])) if body else None,
                        totalCount=total, hasNextPage=has_next)
            if not has_next:
                manifest["rows_total"] = total
                break
            nxt = page.locator("p-paginator .ui-paginator-next:not(.ui-state-disabled), "
                               ".ui-paginator .ui-paginator-next:not(.ui-state-disabled)")
            if nxt.count() == 0:
                p.log_event(event="next_button_missing", page=page_no)
                manifest["rows_total"] = total
                break
            p._click_guard("下一页")
            nxt.first.click(timeout=8000)
            page.wait_for_timeout(2000)

        manifest["pages_captured"] = page_no
        reason = "QUERY_CAPTURED"
        p.result["case03_query"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_query"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage2_end", status=reason,
                    pages=len(manifest.get("pages", [])), rows_total=manifest.get("rows_total"))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "query-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
