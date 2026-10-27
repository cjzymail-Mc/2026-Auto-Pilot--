# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段三（浏览器只读）：陈晶 13 张公出单逐张详情证据采集。

- 先在列表页点击首行 单据编号 学习查看路由/详情 API（真实点击，不猜 URL）；
- 之后逐张进入查看页，捕获详情 API 响应 JSON + DOM 文本 + 截图 + sha256；
- 只读：不点 修改/删除/流程/导出/跨月申请/返回/保存类；弹框一律 dismiss；
  对话框关闭只用其自带关闭图标（pi-times/close），不用 返回。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case03_probe import TripProbe, RUN, EXPECT_NAME  # noqa: E402
from stage1_browser_probe import HOST, PASS  # noqa: E402

TRIP_URL = HOST + "/oa/workouts"
DATE_FROM, DATE_TO = "2025-01-01", "2026-12-31"


def setup_filters(page, p):
    pickers = page.locator("qd-desktop-date-picker input.ui-inputtext")
    if pickers.count() < 6:
        raise ValueError("date pickers missing")
    for idx, value in ((0, DATE_FROM), (1, DATE_TO), (2, DATE_FROM), (3, DATE_TO)):
        el = pickers.nth(idx)
        el.click(); el.fill(value); el.press("Enter")
        page.wait_for_timeout(700)
    creator = page.locator("input#CreatedPath2")
    if creator.count() == 1 and creator.input_value().strip():
        creator.hover(); page.wait_for_timeout(300)
        page.locator(".form-row.CreatedPath .clear-icon").first.click(timeout=8000, force=True)
        page.wait_for_timeout(800)


def main() -> int:
    from types import SimpleNamespace
    docs = json.loads((RUN / "chen-docs.json").read_text(encoding="utf-8"))
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "detail views", "docs": []}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("detail capture requires verified login")
        p._save_session_state()
        p._arm_capture()
        page = p.page

        # 列表 + 过滤后点击首行编号学习查看路由
        page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        setup_filters(page, p)
        btn = page.get_by_role("button", name="查询", exact=True)
        p._click_guard("查询")
        btn.click(timeout=8000)
        page.wait_for_timeout(2500)
        p._drain_capture("detail-setup")

        first_no = page.locator("table tbody tr td:nth-child(4)")  # 单据编号列
        if first_no.count() == 0:
            reason = "NO_ROWS_TO_LEARN_VIEW"
            raise ValueError("no rows after query; cannot learn view route")
        p._click_guard(first_no.first.inner_text().strip())
        first_no.first.click(timeout=8000)
        page.wait_for_timeout(3500)
        view_url = page.url
        p.shot(page, "detail-learn.png")
        p.save("detail-learn.html", page.content())
        p.save("detail-learn-text.txt", page.evaluate("() => document.body ? document.body.innerText.slice(0, 60000) : ''"))
        learn_caps = p._drain_capture("detail-learn")
        p.log_event(event="view_route_learned", url=view_url, api_count=len(learn_caps))
        manifest["learned_view_url"] = view_url
        manifest["learned_api"] = [c["path"] for c in learn_caps]

        # 学习到的路由若为 view 页则直接构造其余单据的 URL；若是 dialog（URL 未变）则改为逐张回到列表点击
        route_view = "type=view" in view_url or "id=" in view_url
        manifest["route_view"] = route_view

        for i, doc in enumerate(docs):
            biz = doc["bizNumber"]
            p.log_event(event="detail_doc_start", bizNumber=biz)
            if i == 0 and route_view:
                # 已在学习步打开首张：直接采集（上面已 drain，重新抓本张详情 API）
                pass
            if route_view:
                sep = "&" if "?" in view_url else "?"
                url = view_url  # 学习页就是首张
                if i > 0:
                    import re as _re
                    url = _re.sub(r"id=[^&]+", "id=" + doc["id"], view_url)
                    if "id=" not in url:
                        url = view_url + sep + "id=" + doc["id"]
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
            else:
                # dialog 模式：回到列表（过滤已丢失需重设）→ 点对应编号
                page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3500)
                setup_filters(page, p)
                p._click_guard("查询"); btn.click(timeout=8000)
                page.wait_for_timeout(2500)
                cell = page.locator(f"table tbody tr td:nth-child(4)", has_text=biz)
                if cell.count() == 0:
                    p.log_event(event="detail_row_not_found", bizNumber=biz)
                    manifest["docs"].append({"bizNumber": biz, "status": "ROW_NOT_FOUND"})
                    continue
                p._click_guard(biz)
                cell.first.click(timeout=8000)
                page.wait_for_timeout(3000)
            caps = p._drain_capture(f"detail-{biz}")
            text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 60000) : ''")
            p.save(f"detail-{biz}-text.txt", text)
            shot = p.shot(page, f"detail-{biz}.png")
            manifest["docs"].append({
                "bizNumber": biz, "uuid": doc["id"], "appliedAt": doc.get("appliedAt"),
                "view_url": page.url if route_view else "(dialog)",
                "text_evidence": f"detail-{biz}-text.txt",
                "screenshot": shot,
                "api": [{"path": c["path"], "file": c["file"], "sha256": c["sha256"]} for c in caps],
            })
            p.log_event(event="detail_doc_captured", bizNumber=biz, api_paths=[c["path"] for c in caps])
            # dialog 模式下关闭弹窗（关闭图标，不是 返回）
            if not route_view:
                close = page.locator(".ui-dialog-titlebar-icon[aria-label='close'], "
                                     "button[aria-label='Close'], .ui-dialog-titlebar-close")
                if close.count() > 0:
                    close.first.click(timeout=8000)
                    page.wait_for_timeout(1200)

        reason = "DETAILS_CAPTURED"
        p.result["case03_details"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_details"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage3_end", status=reason, docs=len(manifest.get("docs", [])))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "details-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
