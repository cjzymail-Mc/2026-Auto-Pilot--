# -*- coding: utf-8 -*-
"""徐亮候选公出单详情只读核实（用户授权统计任务的证据补采）。

目标 3 张单（wide 列表 + travelcensus relation 条目佐证，详情 fact 行未采）：
- 12025085486（徐亮0825）/ 12025112775（徐亮1114，与行程日 1112 有张力）/ 12025121233（徐亮1204）
通道同 V3-R04 3e：观测到的只读 GET /WorkOut/<uuid32>（认证头仅内存）+ bizNumber 互证；
临时 context、profile 锁、--no-proxy-server 直连；零业务写入，不点任何业务按钮。
uuid 来源：automation/runs/20261023-142146-travelcensus/travel_census.json 的 relation bizId。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "automation/runs/20261026-143340-v3r04-case03"))

from case03_probe import TripProbe  # noqa: E402
from stage1_browser_probe import HOST, PASS  # noqa: E402

API_ORIGIN = "https://oa.api.qiaodan.com"
RUN = Path(__file__).resolve().parent
EXPECT_NAME = "陈晶"

TARGETS = [
    {"bizNumber": "12025085486", "uuid": "2105b4d8415f4667ba07750d0428f333",
     "trip_date": "2025-08-25", "census_desc": "徐亮0825"},
    {"bizNumber": "12025112775", "uuid": "6a636d318de64efaa9026dbee8b85440",
     "trip_date": "2025-11-12", "census_desc": "徐亮1114"},
    {"bizNumber": "12025121233", "uuid": "be228bd423fa4c7db8f5cfe3d7da676b",
     "trip_date": "2025-12-04", "census_desc": "徐亮1204"},
]


def main() -> int:
    from types import SimpleNamespace
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"stage": "xuliang candidate details", "targets": []}
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
        page.goto(HOST + "/oa/workouts", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        p._drain_capture("xl-entry")
        if not p._api_headers:
            reason = "NO_AUTH_HEADERS"
            raise ValueError("no auth headers observed")

        for t in TARGETS:
            biz, uid = t["bizNumber"], t["uuid"]
            entry = dict(t)
            try:
                resp = p.ctx.request.get(API_ORIGIN + "/WorkOut/" + uid,
                                         headers=p._api_headers, timeout=20000)
                body = json.loads(resp.text())
                if body.get("bizNumber") != biz:
                    entry["status"] = "BIZNUMBER_MISMATCH"
                    entry["api_bizNumber"] = str(body.get("bizNumber"))[:40]
                    manifest["targets"].append(entry)
                    continue
                text = json.dumps({"request_path": "/WorkOut/" + uid, "method": "GET",
                                   "http_status": resp.status, "body": body},
                                  ensure_ascii=False, indent=1)
                name = f"api-xuliang-{biz}.json"
                p.save(name, text)
                dets = body.get("details") or []
                entry.update({
                    "status": "CAPTURED", "http_status": resp.status,
                    "api_file": name,
                    "api_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "doc_appliedName": body.get("appliedName"),
                    "doc_createdName": body.get("createdName"),
                    "doc_bizReason": body.get("bizReason"),
                    "doc_place": body.get("place"),
                    "doc_reimed": body.get("reimed"),
                    "rows": [{"appliedName": d.get("appliedName"),
                              "factStart": (d.get("factStartTime") or "")[:16],
                              "factEnd": (d.get("factEndTime") or "")[:16],
                              "natureStart": (d.get("factNatureStartDate") or "")[:10],
                              "natureEnd": (d.get("factNatureEndDate") or "")[:10]}
                             for d in dets],
                })
                entry["xuliang_in_rows"] = any(d.get("appliedName") == "徐亮" for d in dets)
                entry["covers_trip_date"] = any(
                    (d.get("factNatureStartDate") or "")[:10] <= t["trip_date"] <=
                    (d.get("factNatureEndDate") or "")[:10] for d in dets)
                p.log_event(event="xl_captured", bizNumber=biz,
                            xuliang_in_rows=entry["xuliang_in_rows"],
                            covers_trip_date=entry["covers_trip_date"])
            except Exception as e:
                entry["status"] = "FAILED"
                entry["error"] = str(e)[:200]
                p.log_event(event="xl_failed", bizNumber=biz, error=str(e)[:200])
            manifest["targets"].append(entry)

        n_ok = sum(1 for t in manifest["targets"] if t.get("status") == "CAPTURED")
        reason = "DETAILS_CAPTURED" if n_ok == len(TARGETS) else "PARTIAL"
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["xuliang_details"] = manifest
        p.atomic_result()
        p.log_event(event="xuliang_detail_end", status=reason)
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "xuliang-details-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
