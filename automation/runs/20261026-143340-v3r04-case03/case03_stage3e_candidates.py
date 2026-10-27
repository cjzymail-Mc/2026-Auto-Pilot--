# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段三e（浏览器只读）：缺日候选单详情补查（排除/命中证据）。

5 个通行日（09-04/09-17/09-28/11-24/12-10）在陈晶自己的 13 张单里无同日明细。
attempt_007 全组织宽窗（96 行）里 appliedAt ∈ [D, D+6] 的候选共 9 张，其中 2 张
（12025092237/12025115547）已采集；本阶段补采其余 8 张的详情，核对：
- 每行明细的实际公出日期（factNatureStartDate/EndDate）是否覆盖缺日；
- 行级公出人员（details[].appliedName）是否含 陈晶 —— 部门同事单据若载陈晶同行，
  即为该日通行费的真实对应单据。
通道同 3d：观测到的只读 GET /WorkOut/<uuid32>（认证头仅内存）+ bizNumber 互证。
零写入：不点任何业务按钮。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from case03_probe import TripProbe, RUN, EXPECT_NAME  # noqa: E402
from stage1_browser_probe import HOST, PASS  # noqa: E402

API_ORIGIN = "https://oa.api.qiaodan.com"

CANDIDATES = [
    {"bizNumber": "12025091498", "uuid": "673e1743f72b4e4b8a6def58ca3e5955",
     "appliedAt": "2025-09-05", "applicant": "阮果清", "place": "晋江工厂", "gap_day": "2025-09-04"},
    {"bizNumber": "12025092018", "uuid": "94f8f9da76dc4046940a6294864c6739",
     "appliedAt": "2025-09-08", "applicant": "徐亮", "place": "晋江", "gap_day": "2025-09-04"},
    {"bizNumber": "12025094906", "uuid": "d9186d5d1f8147209db9902e262be113",
     "appliedAt": "2025-09-17", "applicant": "张宇昂", "place": "泉州石狮", "gap_day": "2025-09-17"},
    {"bizNumber": "12025095297", "uuid": "6e46825db34d41768aa57284d1b3f190",
     "appliedAt": "2025-09-18", "applicant": "张宇昂", "place": "晋江", "gap_day": "2025-09-17"},
    {"bizNumber": "12025098708", "uuid": "fbf995fe72db4b14a46a00735852bd36",
     "appliedAt": "2025-09-28", "applicant": "张宇昂", "place": "泉州", "gap_day": "2025-09-28"},
    {"bizNumber": "12025115994", "uuid": "9de4366410e14b26be9790b2b5c8b88b",
     "appliedAt": "2025-11-27", "applicant": "徐亮", "place": "晋江", "gap_day": "2025-11-24"},
    {"bizNumber": "12025122974", "uuid": "522cecce78ea4f2dbbee656c7cf99772",
     "appliedAt": "2025-12-10", "applicant": "阮果清", "place": "晋江工厂", "gap_day": "2025-12-10"},
    {"bizNumber": "12025123375", "uuid": "429045c57c744a16913a93304f658f41",
     "appliedAt": "2025-12-12", "applicant": "徐亮", "place": "晋江", "gap_day": "2025-12-10"},
]


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main() -> int:
    from types import SimpleNamespace
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "3e gap-day candidate details", "candidates": []}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("candidate capture requires verified login")
        p._save_session_state()
        p._arm_capture()
        page = p.page
        page.goto(HOST + "/oa/workouts", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        p._drain_capture("v3e-entry")
        if not p._api_headers:
            reason = "NO_AUTH_HEADERS"
            raise ValueError("no auth headers observed")

        for c in CANDIDATES:
            biz, uid = c["bizNumber"], c["uuid"]
            entry = dict(c)
            try:
                resp = p.ctx.request.get(API_ORIGIN + "/WorkOut/" + uid,
                                         headers=p._api_headers, timeout=20000)
                body = json.loads(resp.text())
                if body.get("bizNumber") != biz:
                    entry["status"] = "BIZNUMBER_MISMATCH"
                    entry["api_bizNumber"] = str(body.get("bizNumber"))[:40]
                    p.log_event(event="v3e_biznumber_mismatch", bizNumber=biz)
                    manifest["candidates"].append(entry)
                    continue
                text = json.dumps({"request_path": "/WorkOut/" + uid, "method": "GET",
                                   "http_status": resp.status, "body": body},
                                  ensure_ascii=False, indent=1)
                name = f"api-cand-{biz}.json"
                p.save(name, text)
                dets = body.get("details") or []
                entry.update({
                    "status": "CAPTURED", "http_status": resp.status,
                    "api_file": name, "api_sha256": sha256_text(text),
                    "doc_appliedName": body.get("appliedName"),
                    "doc_place": body.get("place"),
                    "doc_bizReason": body.get("bizReason"),
                    "doc_bizStatus": body.get("bizStatus"), "doc_reimed": body.get("reimed"),
                    "rows": [{"appliedName": d.get("appliedName"),
                              "factStart": (d.get("factNatureStartDate") or "")[:16],
                              "factEnd": (d.get("factNatureEndDate") or "")[:16]}
                             for d in dets],
                })
                entry["chen_in_rows"] = any(d.get("appliedName") == "陈晶" for d in dets)
                entry["covers_gap_day"] = any(
                    (d.get("factNatureStartDate") or "")[:10] <= c["gap_day"] <=
                    (d.get("factNatureEndDate") or "")[:10] for d in dets)
                p.log_event(event="v3e_candidate_captured", bizNumber=biz,
                            chen_in_rows=entry["chen_in_rows"],
                            covers_gap_day=entry["covers_gap_day"])
            except Exception as e:
                entry["status"] = "FAILED"
                entry["error"] = str(e)[:160]
                p.log_event(event="v3e_candidate_failed", bizNumber=biz, error=str(e)[:160])
            manifest["candidates"].append(entry)

        n_ok = sum(1 for c in manifest["candidates"] if c.get("status") == "CAPTURED")
        reason = "CANDIDATES_CAPTURED" if n_ok == len(CANDIDATES) else "PARTIAL"
        p.result["case03_candidates_3e"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_candidates_3e"] = manifest
        p.atomic_result()
        p.log_event(event="case03_stage3e_end", status=reason,
                    captured=sum(1 for c in manifest.get("candidates", [])
                                 if c.get("status") == "CAPTURED"))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "candidates3e-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
