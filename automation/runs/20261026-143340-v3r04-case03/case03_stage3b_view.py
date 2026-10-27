# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段三b（浏览器只读）：单号精查 + 行选择 + 查看 打开详情并采集。

stage3 教训：td:nth-child(4) 编号点击无效（无导航无 API）。本阶段按 bpm_template 精查
先例：每张单用 公出单号(BizNumber0) 精确过滤 → 查询 → 行点击选中 → 工具栏 查看 打开
详情；捕获详情 API + DOM 文本 + 截图 + sha256。学习步先在首张上确认 查看 打开机制，
失败即停（不瞎试写路径）。弹框 dismiss；关闭只用自带关闭图标，不点 返回。
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


def wide_filters(page, p):
    pickers = page.locator("qd-desktop-date-picker input.ui-inputtext")
    for idx, value in ((0, DATE_FROM), (1, DATE_TO), (2, DATE_FROM), (3, DATE_TO)):
        el = pickers.nth(idx)
        el.click(); el.fill(value); el.press("Enter")
        page.wait_for_timeout(700)
    creator = page.locator("input#CreatedPath2")
    if creator.count() == 1 and creator.input_value().strip():
        creator.hover(); page.wait_for_timeout(300)
        page.locator(".form-row.CreatedPath .clear-icon").first.click(timeout=8000, force=True)
        page.wait_for_timeout(800)


def open_doc(page, p, biz, learn=False):
    """单号精查 → 行选择 → 查看。返回 (ok, detail_visible)。"""
    no_input = page.locator("input#BizNumber0")
    no_input.click(); no_input.fill(biz)
    page.wait_for_timeout(400)
    btn = page.get_by_role("button", name="查询", exact=True)
    p._click_guard("查询")
    btn.click(timeout=8000)
    page.wait_for_timeout(2200)
    row = page.locator("table tbody tr", has_text=biz)
    if row.count() == 0:
        return False, False, "ROW_NOT_FOUND"
    row.first.click(timeout=8000)          # 行选择（只读 UI 态，不改数据）
    page.wait_for_timeout(800)
    view = page.get_by_role("button", name="查看", exact=True)
    if view.count() != 1:
        return False, False, f"VIEW_BUTTON_COUNT={view.count()}"
    p._click_guard("查看")
    view.click(timeout=8000)
    page.wait_for_timeout(3500)
    # 详情可见性：URL 变化或弹出 dialog
    dialog = page.locator("p-dialog .ui-dialog, .ui-dialog")
    visible = ("id=" in page.url and "workouts" not in page.url) or (
        dialog.count() > 0 and dialog.first.is_visible())
    return True, visible, page.url


def close_dialog(page, p):
    close = page.locator(".ui-dialog-titlebar-icon[aria-label='close'], "
                         "button[aria-label='Close'], button[aria-label='close'], "
                         ".ui-dialog-titlebar-close")
    if close.count() > 0:
        try:
            close.first.click(timeout=6000)
            page.wait_for_timeout(1200)
            return True
        except Exception as e:
            p.log_event(event="dialog_close_failed", error=str(e)[:120])
    return False


def main() -> int:
    from types import SimpleNamespace
    docs = json.loads((RUN / "chen-docs.json").read_text(encoding="utf-8"))
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "view via number query + row select + 查看", "docs": []}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("view capture requires verified login")
        p._save_session_state()
        p._arm_capture()
        page = p.page

        page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        wide_filters(page, p)          # 宽窗过滤（精查单号叠加其上，防默认制单日期干扰）
        p.shot(page, "v3b-list-ready.png")

        # 学习步：首张
        first = docs[0]
        ok, visible, url = open_doc(page, p, first["bizNumber"], learn=True)
        p.shot(page, f"v3b-learn-{first['bizNumber']}.png")
        p.save(f"v3b-learn-text.txt", page.evaluate("() => document.body ? document.body.innerText.slice(0, 60000) : ''"))
        learn_caps = p._drain_capture("v3b-learn")
        p.log_event(event="v3b_learn", bizNumber=first["bizNumber"], ok=ok,
                    visible=visible, url=url, api_paths=[c["path"] for c in learn_caps])
        manifest["learn"] = {"bizNumber": first["bizNumber"], "ok": ok, "visible": visible,
                             "url": url, "api": [c["path"] for c in learn_caps]}
        if not visible:
            reason = "VIEW_MECHANISM_FAILED"
            raise ValueError(f"查看 did not open a detail for {first['bizNumber']}; see v3b-learn artifacts")

        for i, doc in enumerate(docs):
            biz = doc["bizNumber"]
            if i > 0 or True:  # 首张也重新按标准流程开一次，保证采集一致
                # 回列表（若此前是路由跳转）；dialog 模式已在原页
                if "workouts" not in page.url:
                    page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3500)
                    wide_filters(page, p)
                ok, visible, url = open_doc(page, p, biz)
                if not ok or not visible:
                    manifest["docs"].append({"bizNumber": biz, "uuid": doc["id"],
                                             "status": "OPEN_FAILED", "note": url})
                    p.log_event(event="v3b_doc_open_failed", bizNumber=biz, note=str(url)[:200])
                    close_dialog(page, p)
                    continue
            caps = p._drain_capture(f"v3b-{biz}")
            text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 80000) : ''")
            p.save(f"detail-{biz}-text.txt", text)
            shot = p.shot(page, f"detail-{biz}.png")
            manifest["docs"].append({
                "bizNumber": biz, "uuid": doc["id"], "appliedAt": doc.get("appliedAt"),
                "view_url": page.url, "text_evidence": f"detail-{biz}-text.txt",
                "screenshot": shot,
                "api": [{"path": c["path"], "file": c["file"], "sha256": c["sha256"]} for c in caps],
            })
            p.log_event(event="v3b_doc_captured", bizNumber=biz,
                        api_paths=[c["path"] for c in caps][:8])
            # 关闭详情：dialog 用关闭图标；路由页则回列表
            if not close_dialog(page, p):
                if "workouts" not in page.url:
                    page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3000)
                    wide_filters(page, p)

        reason = "VIEW_CAPTURED"
        p.result["case03_view"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_view"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage3b_end", status=reason, docs=len(manifest.get("docs", [])))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "view-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
