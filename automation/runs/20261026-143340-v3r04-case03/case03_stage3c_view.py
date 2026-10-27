# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段三c（浏览器只读）：单号+日期精查 → 行选择 → 查看 → 详情采集。

3b 教训：制单人过滤在每次重新查询时被 Angular 回填为默认 陈晶（截图实证 11 行
createdBy=陈晶 vs 全组织 96 行），导致 createdBy≠陈晶 的单号精查 0 行。
策略：
- 只设 4 个日期格（不碰制单人，避免与回填行为搏斗）；
- 13 张单逐一：单号精查 → 行点击 → 查看 → 详情 API/DOM/截图 + sha256；
- createdBy≠陈晶 查不到的单：先从学习步观察详情 GET 端点（如 /WorkOut/<uuid>），
  属纯只读 GET（bpm_template 先例：观测到的端点+内存认证头可用），逐张补抓；
- 弹框 dismiss；关闭只用自带关闭图标，不点 返回；零业务写入。
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
API_ORIGIN = "https://oa.api.qiaodan.com"
DATE_FROM, DATE_TO = "2025-01-01", "2026-12-31"


def set_dates(page, p):
    pickers = page.locator("qd-desktop-date-picker input.ui-inputtext")
    if pickers.count() < 6:
        raise ValueError(f"date pickers missing: {pickers.count()}")
    for idx, value in ((0, DATE_FROM), (1, DATE_TO), (2, DATE_FROM), (3, DATE_TO)):
        el = pickers.nth(idx)
        el.click(); el.fill(value); el.press("Enter")
        page.wait_for_timeout(700)
        if el.input_value() != value:
            raise ValueError(f"picker {idx}={el.input_value()!r}")


def open_doc(page, p, biz):
    """单号精查 → 行选择 → 查看；返回 (ok, visible, note)。"""
    no_input = page.locator("input#BizNumber0")
    no_input.click(); no_input.fill("")
    page.wait_for_timeout(200)
    no_input.fill(biz)
    page.wait_for_timeout(400)
    btn = page.get_by_role("button", name="查询", exact=True)
    p._click_guard("查询")
    btn.click(timeout=8000)
    page.wait_for_timeout(2400)
    row = page.locator("table tbody tr", has_text=biz)
    if row.count() == 0:
        return False, False, "ROW_NOT_FOUND"
    row.first.click(timeout=8000)
    page.wait_for_timeout(900)
    view = page.get_by_role("button", name="查看", exact=True)
    if view.count() != 1:
        return False, False, f"VIEW_BUTTON_COUNT={view.count()}"
    p._click_guard("查看")
    view.click(timeout=8000)
    page.wait_for_timeout(3800)
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
            page.wait_for_timeout(1400)
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
    manifest = {"stage": "view via number+date query", "docs": [], "api_fallback": []}
    not_found = []
    detail_endpoint = None
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
        set_dates(page, p)
        p.shot(page, "v3c-list-ready.png")

        ok_all = True
        for i, doc in enumerate(docs):
            biz = doc["bizNumber"]
            ok, visible, note = open_doc(page, p, biz)
            if not ok or not visible:
                manifest["docs"].append({"bizNumber": biz, "uuid": doc["id"],
                                         "status": "OPEN_FAILED", "note": str(note)[:200]})
                p.log_event(event="v3c_doc_open_failed", bizNumber=biz, note=str(note)[:200])
                not_found.append(doc)
                close_dialog(page, p)
                continue
            caps = p._drain_capture(f"v3c-{biz}")
            paths = [c["path"] for c in caps]
            if detail_endpoint is None:
                for path in paths:
                    if "/WorkOut/" in path and "/WorkOut/query" not in path:
                        detail_endpoint = path
                        p.log_event(event="v3c_detail_endpoint_learned", path=path)
            text = page.evaluate("() => document.body ? document.body.innerText.slice(0, 80000) : ''")
            p.save(f"detail-{biz}-text.txt", text)
            shot = p.shot(page, f"detail-{biz}.png")
            manifest["docs"].append({
                "bizNumber": biz, "uuid": doc["id"], "appliedAt": doc.get("appliedAt"),
                "view_url": page.url, "text_evidence": f"detail-{biz}-text.txt",
                "screenshot": shot,
                "api": [{"path": c["path"], "file": c["file"], "sha256": c["sha256"]} for c in caps],
            })
            p.log_event(event="v3c_doc_captured", bizNumber=biz, api_paths=paths[:8])
            if not close_dialog(page, p):
                if "workouts" not in page.url:
                    page.goto(TRIP_URL, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(3500)
                    set_dates(page, p)

        # createdBy≠陈晶 的查不到单：观测到的只读详情 GET 端点补抓（认证头只在内存）
        if not_found and detail_endpoint:
            import re as _re
            base = _re.sub(r"/[0-9a-fA-F-]{36}", "/{uuid}", detail_endpoint)
            for doc in not_found:
                biz, uid = doc["bizNumber"], doc["id"]
                path = detail_endpoint
                if "{uuid}" in base:
                    import uuid as _uuid
                    path = base.replace("{uuid}", uid)
                try:
                    resp = p.ctx.request.get(API_ORIGIN + path, headers=p._api_headers, timeout=20000)
                    body = resp.text()
                    payload = {"request_path": path, "method": "GET",
                               "http_status": resp.status, "body": json.loads(body)}
                    name = f"api-fallback-{biz}.json"
                    p.save(name, json.dumps(payload, ensure_ascii=False, indent=1))
                    manifest["api_fallback"].append({
                        "bizNumber": biz, "uuid": uid, "path": path,
                        "http_status": resp.status, "file": name,
                        "sha256": __import__("hashlib").sha256(
                            json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()})
                    p.log_event(event="v3c_api_fallback", bizNumber=biz,
                                status=resp.status, path=path)
                except Exception as e:
                    p.log_event(event="v3c_api_fallback_failed", bizNumber=biz, error=str(e)[:160])
        elif not_found:
            p.log_event(event="v3c_no_detail_endpoint_for_fallback",
                        missing=[d["bizNumber"] for d in not_found])

        manifest["detail_endpoint"] = detail_endpoint
        reason = "VIEW_CAPTURED"
        p.result["case03_view"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_view"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage3c_end", status=reason,
                    docs=len(manifest.get("docs", [])), fallback=len(manifest.get("api_fallback", [])))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "view-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
