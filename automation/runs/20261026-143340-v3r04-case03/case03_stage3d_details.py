# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段三d（浏览器只读）：13 张陈晶公出单逐张详情双通道采集。

attempt_010 教训：
- 查看机制真实存在且打开的是路由页 /oa/workout?type=view&id=<uuid32>（单数 workout）；
- 逐张经列表行+查看的流程被表单回填/翻页状态拖垮（12 张 ROW_NOT_FOUND）；
- 旧 api-fallback-*.json 的 uuid 替换正则 [0-9a-fA-F-]{36} 与真实 32 位无杠 uuid 不符，
  全部落到同一错误端点 —— attempt_010 的 api-fallback 文件一律不得作为对应单据证据。

本阶段双通道（都不经过列表表单，零写入）：
A) 观测到的只读详情 GET：https://oa.api.qiaodan.com/WorkOut/<uuid32>
   （uuid 直接取 chen-docs.json 的 id，不做任何正则替换；认证头仅内存，不落盘）
B) 观测到的查看路由页：/oa/workout?type=view&id=<uuid32>（真实点击学到的路由族）
   页面自身会发同一 GET —— 与 A 通道互证 bizNumber 一致才记 captured；
   可见性判据 = URL 含期望 id 且正文含「公出明细」，不再用 .ui-dialog 或单号在正文
   （12025073893 实测正文无单号，判据改用页面结构性标题）。
视图页上的 保存/打印/返回 一律不点；全程只 goto/读 DOM/截图。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case03_probe import TripProbe, RUN, EXPECT_NAME  # noqa: E402
from stage1_browser_probe import HOST, PASS  # noqa: E402

API_ORIGIN = "https://oa.api.qiaodan.com"
VIEW_PATH = "/oa/workout?type=view&id="


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    from types import SimpleNamespace
    docs = json.loads((RUN / "chen-docs.json").read_text(encoding="utf-8"))
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {
        "stage": "3d dual-channel details (observed GET + observed view route)",
        "invalid_prior_evidence": {
            "attempt": "attempt_010",
            "files": "api-fallback-*.json",
            "cause": "uuid substitution regex [0-9a-fA-F-]{36} never matched the real "
                     "32-hex-no-dash uuid; all 12 requests hit 3f260a65f3b748308e88e353ead9e9dc",
        },
        "docs": [],
    }
    ok_count = api_only = failed = 0
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

        # 先进模块首页一次：确认菜单可达 + 产生 api 认证头（内存）
        page.goto(HOST + "/oa/workouts", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        p._drain_capture("v3d-entry")
        if not p._api_headers:
            reason = "NO_AUTH_HEADERS"
            raise ValueError("no auth headers observed; cannot use read-only GET")

        for doc in docs:
            biz, uid = doc["bizNumber"], doc["id"]
            entry = {"bizNumber": biz, "uuid": uid, "appliedAt": doc.get("appliedAt"),
                     "bizStatus": doc.get("bizStatus"), "reimed": doc.get("reimed")}
            # ---- 通道 A：观测到的只读详情 GET ----
            a_ok, a_body, a_status = False, None, None
            try:
                resp = p.ctx.request.get(API_ORIGIN + "/WorkOut/" + uid,
                                         headers=p._api_headers, timeout=20000)
                a_status = resp.status
                a_body = json.loads(resp.text())
                if a_body.get("bizNumber") == biz:
                    a_ok = True
                else:
                    p.log_event(event="v3d_api_biznumber_mismatch", bizNumber=biz,
                                api_bizNumber=str(a_body.get("bizNumber"))[:40])
            except Exception as e:
                p.log_event(event="v3d_api_failed", bizNumber=biz, error=str(e)[:160])
            if a_ok:
                name = f"api-detail-{biz}.json"
                text = json.dumps({"request_path": "/WorkOut/" + uid, "method": "GET",
                                   "http_status": a_status, "body": a_body},
                                  ensure_ascii=False, indent=1)
                p.save(name, text)
                entry["api_file"] = name
                entry["api_sha256"] = sha256_text(text)
                entry["api_trip_rows"] = len(a_body.get("workOutDetails") or
                                             a_body.get("details") or [])
            # ---- 通道 B：观测到的查看路由页（页面自身再发同一 GET） ----
            b_ok, view_note = False, ""
            try:
                page.goto(HOST + VIEW_PATH + uid, wait_until="domcontentloaded",
                          timeout=45000)
                page.wait_for_timeout(3500)
                for _ in range(6):  # 最多再等 3s 渲染
                    body_txt = page.evaluate(
                        "() => document.body ? document.body.innerText.slice(0, 80000) : ''")
                    if "公出明细" in body_txt:
                        break
                    page.wait_for_timeout(500)
                url_ok = uid in page.url
                text_ok = "公出明细" in body_txt
                b_ok = url_ok and text_ok
                view_note = f"url_ok={url_ok}, text_ok={text_ok}"
                if b_ok:
                    caps = p._drain_capture(f"v3d-{biz}")
                    ui_api_hit = any("/WorkOut/" + uid in c["path"] for c in caps)
                    entry["ui_text_evidence"] = f"detail3d-{biz}-text.txt"
                    entry["ui_screenshot"] = p.shot(page, f"detail3d-{biz}.png")
                    p.save(f"detail3d-{biz}-text.txt", body_txt)
                    entry["ui_api_paths"] = [c["path"] for c in caps][:6]
                    entry["ui_api_hit"] = ui_api_hit
                    p.log_event(event="v3d_doc_view_ok", bizNumber=biz,
                                ui_api_hit=ui_api_hit)
                else:
                    p.shot(page, f"detail3d-{biz}-FAILED.png")
                    p.log_event(event="v3d_doc_view_failed", bizNumber=biz, note=view_note)
            except Exception as e:
                view_note = str(e)[:160]
                p.log_event(event="v3d_doc_view_error", bizNumber=biz, error=view_note)

            if a_ok and b_ok:
                entry["status"] = "CAPTURED"
                ok_count += 1
            elif a_ok:
                entry["status"] = "API_ONLY"
                entry["view_note"] = view_note
                api_only += 1
            else:
                entry["status"] = "FAILED"
                entry["view_note"] = view_note
                failed += 1
            manifest["docs"].append(entry)

        manifest["summary"] = {"captured": ok_count, "api_only": api_only,
                               "failed": failed, "total": len(docs)}
        reason = "DETAILS_CAPTURED" if (ok_count + api_only) == len(docs) else \
                 ("PARTIAL" if ok_count + api_only else "ALL_FAILED")
        p.result["case03_details_3d"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_details_3d"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage3d_end", status=reason,
                    captured=ok_count, api_only=api_only, failed=failed)
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "details3d-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
