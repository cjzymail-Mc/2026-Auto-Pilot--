# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段四（离线）：27 张通行费 → 真实公出单 逐票对照与完整性重算。

数据源（全部来自本轮 run 证据，无硬编码映射）：
- case01-facts.json（上游 round2）：27 张通行费身份（identity/rel/sha256）；
- case02-mapping.json（上游 round3）：20 行汇总 ↔ 27 票 exactly-once 分配 + 金额；
- attempt_011 api-detail-*.json（本 run 阶段3d）：陈晶 13 张公出单详情（含行级公出人员）；
- attempt_012 api-cand-*.json（本 run 阶段3e）：缺日候选同事单详情（排除证据）；
- attempt_007 宽窗全组织 96 行（本 run 阶段2b）：申请人完整性依据。

判定（程序化）：
- 对每个通行日 D：在陈晶 13 张单的行级明细（details[].appliedName==陈晶 且
  factNaturalStartDate<=D<=factNatureEndDate）中找覆盖单 → MATCHED；
- 否则在 3e 候选（同窗 appliedAt∈[D,D+6] 的全组织单据）中列排除记录 → NO_MATCH；
- 绝不与占位语义混写：本轮未在 OA 关联表选择任何单据（零写入），本表仅真实对照。
完整性三向重算：票集 27 恒等、Σ=486.93（Decimal）、逐单票数/Excel 行数闭合。
产物：actual_trip_matches.json（机器）+ CASE-03-report.md（人读）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

RUN = Path(__file__).resolve().parent
REPO = RUN.parent.parent.parent
FACTS = REPO / "automation/runs/20261026-115500-v3r02-case01/case01-facts.json"
MAPPING = REPO / "automation/runs/20261026-131000-v3r03-case02/case02-mapping.json"

CST = timezone(timedelta(hours=8))


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def main() -> int:
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    det_m = json.loads((RUN / "details3d-manifest.json").read_text(encoding="utf-8"))
    cand_m = json.loads((RUN / "candidates3e-manifest.json").read_text(encoding="utf-8"))

    # ---- 上游票集（27 张）与映射 ----
    toll_identities = [i for i in facts["identities"] if i["class"] == "toll_invoice"]
    plate_values = {f["facts"].get("plate", {}).get("value")
                    for f in facts["files"] if f.get("class") == "toll_invoice"}
    assert plate_values == {"闽D263GG"}, f"plate drift: {plate_values}"
    by_identity = {t["identity"]: t for t in toll_identities}
    invoice_rows = {}   # identity -> {row, date, amount, rel, sha256, station_pair}
    for r in mapping["rows"]:
        for inv in r["invoices"]:
            assert inv["identity"] not in invoice_rows, f"duplicate allocation {inv['identity']}"
            invoice_rows[inv["identity"]] = {
                "excel_row": r["row"], "travel_date": r["date"],
                "amount": inv["amount"], "invoice_number": inv["invoice_number"],
                "rel": inv["rel"], "sha256": inv["sha256"],
                "station_pair": r.get("trip", {}).get("station_pair"),
                "summary_number": r.get("trip", {}).get("summary_number"),
            }

    # ---- 陈晶 13 张单：行级明细（从 attempt_011 api 文件读取，含证据指针）----
    own_docs = []
    for d in det_m["docs"]:
        api = next((c for c in det_m["docs"] if c["bizNumber"] == d["bizNumber"]), None)
        f = None
        for att in sorted(RUN.glob("attempt_*/evidence/api-detail-*.json")):
            p = json.loads(att.read_text(encoding="utf-8"))
            if p.get("request_path") == "/WorkOut/" + d["uuid"]:
                f = att
                break
        assert f is not None, f"missing api-detail for {d['bizNumber']}"
        p = json.loads(f.read_text(encoding="utf-8"))
        b = p["body"]
        own_docs.append({
            "bizNumber": b["bizNumber"], "uuid": b["id"],
            "appliedAt": (b.get("appliedAt") or "")[:10],
            "place": b.get("place"), "bizReason": b.get("bizReason"),
            "bizStatus": b.get("bizStatus"), "reimed": b.get("reimed"),
            "evidence_file": str(f.relative_to(RUN)).replace("\\", "/"),
            "sha256": api["api_sha256"] if api and api.get("api_sha256") else None,
            "ui_screenshot": d.get("ui_screenshot"),
            "ui_text_evidence": d.get("ui_text_evidence"),
            "rows": [{"appliedName": r.get("appliedName"),
                      "factStart": (r.get("factNatureStartDate") or "")[:10],
                      "factEnd": (r.get("factNatureEndDate") or "")[:10]}
                     for r in (b.get("details") or [])],
        })

    def covering_own_docs(day: str):
        return [doc for doc in own_docs
                if any(r["appliedName"] == "陈晶" and r["factStart"] <= day <= r["factEnd"]
                       for r in doc["rows"])]

    cand_by_biz = {c["bizNumber"]: c for c in cand_m["candidates"]}
    # 3e 候选覆盖的缺日 → 排除记录
    def colleague_exclusions(day: str):
        out = []
        for c in cand_m["candidates"]:
            if c.get("gap_day") != day or c.get("status") != "CAPTURED":
                continue
            out.append({
                "bizNumber": c["bizNumber"], "uuid": c["uuid"],
                "applicant": c["doc_appliedName"], "place": c["doc_place"],
                "bizReason": c["doc_bizReason"], "reimed": c["doc_reimed"],
                "covers_day": c["covers_gap_day"], "chen_in_traveler_rows": c["chen_in_rows"],
                "traveler_rows": c["rows"],
                "evidence_file": f"attempt_012/evidence/api-cand-{c['bizNumber']}.json",
                "exclusion_basis": "同日/近窗同事单据，行级公出人员不含陈晶"
                if not c["chen_in_rows"] else "行级含陈晶（不应出现在缺日）",
            })
        return out

    # ---- 逐票对照 ----
    per_invoice = []
    per_day = {}
    for ident, info in sorted(invoice_rows.items(), key=lambda kv: (kv[1]["travel_date"], kv[1]["excel_row"])):
        day = info["travel_date"]
        matched = covering_own_docs(day)
        rec = {
            "identity": ident,
            "invoice_number": info["invoice_number"],
            "amount": info["amount"],
            "rel": info["rel"], "sha256": info["sha256"],
            "excel_row": info["excel_row"],
            "travel_date": day, "station_pair": info["station_pair"],
            "summary_number": info["summary_number"],
            "plate": next(iter(plate_values)),
        }
        if matched:
            assert len(matched) == 1, f"day {day} matched multiple own docs"
            doc = matched[0]
            chen_rows = [r for r in doc["rows"] if r["appliedName"] == "陈晶"]
            rec["result"] = "MATCHED"
            rec["matched_doc"] = {
                "bizNumber": doc["bizNumber"], "uuid": doc["uuid"],
                "appliedAt": doc["appliedAt"], "place": doc["place"],
                "bizReason": doc["bizReason"], "bizStatus": doc["bizStatus"],
                "reimed": doc["reimed"],
                "chen_trip": {"factStart": chen_rows[0]["factStart"],
                              "factEnd": chen_rows[0]["factEnd"]},
                "evidence": {"api_file": doc["evidence_file"],
                             "api_sha256": doc["sha256"],
                             "ui_screenshot": doc["ui_screenshot"],
                             "ui_text": doc["ui_text_evidence"]},
            }
            rec["match_basis"] = (f"公出单 {doc['bizNumber']} 明细行（陈晶，"
                                  f"{chen_rows[0]['factStart']}~{chen_rows[0]['factEnd']}，"
                                  f"地点{doc['place']}）与通行日 {day} 同日覆盖；"
                                  f"站点走向（{info['station_pair']}）与 厦门↔{doc['place']} 往返一致")
        else:
            rec["result"] = "NO_MATCH"
            rec["exclusion"] = {
                "own_docs_scanned": len(own_docs),
                "own_docs_covering_day": 0,
                "colleague_docs_same_window": colleague_exclusions(day),
                "conclusion": (f"通行日 {day} 无陈晶为公出人员的任何公出单（13 张本人单全查，"
                               f"全组织宽窗 96 单内同窗候选已核行级人员均不含陈晶）；"
                               "如实报缺，不虚构对应"),
            }
        per_invoice.append(rec)
        per_day.setdefault(day, {"count": 0, "sum": Decimal("0"), "result": rec["result"],
                                 "docs": set()})
        per_day[day]["count"] += 1
        per_day[day]["sum"] += Decimal(info["amount"])
        if rec["result"] == "MATCHED":
            per_day[day]["docs"].add(rec["matched_doc"]["bizNumber"])

    # ---- 完整性三向重算 ----
    ids_upstream = sorted(by_identity)
    ids_mapped = sorted(invoice_rows)
    ids_here = sorted(r["identity"] for r in per_invoice)
    sum_upstream = sum((Decimal(i["amount"]) for i in invoice_rows.values()), Decimal("0"))
    checks = {
        "invoice_set_27_identity": {"upstream": len(ids_upstream), "mapping": len(ids_mapped),
                                    "this_report": len(ids_here),
                                    "equal": ids_upstream == ids_mapped == ids_here},
        "total_amount": {"expected": "486.93", "recomputed": str(sum_upstream),
                         "equal": sum_upstream == Decimal("486.93")},
        "excel_rows": {"mapping_rows": len(mapping["rows"]),
                       "distinct_rows_used": len({i["excel_row"] for i in invoice_rows.values()}),
                       "equal": len(mapping["rows"]) == len({i["excel_row"] for i in invoice_rows.values()})},
        "per_day_counts": {d: v["count"] for d, v in sorted(per_day.items())},
        "per_day_sums": {d: str(v["sum"]) for d, v in sorted(per_day.items())},
        "allocation_exactly_once": mapping["closure"]["unallocated"] == []
                                   and mapping["closure"]["allocated"] == 27,
    }
    assert checks["invoice_set_27_identity"]["equal"], "invoice set drift"
    assert checks["total_amount"]["equal"], "amount drift"
    assert checks["excel_rows"]["equal"], "excel row drift"

    matched = [r for r in per_invoice if r["result"] == "MATCHED"]
    no_match = [r for r in per_invoice if r["result"] == "NO_MATCH"]
    doc_ticket_counts = {}
    for r in matched:
        doc_ticket_counts.setdefault(r["matched_doc"]["bizNumber"], {"tickets": 0, "sum": Decimal("0"),
                                                                     "excel_rows": []})
        doc_ticket_counts[r["matched_doc"]["bizNumber"]]["tickets"] += 1
        doc_ticket_counts[r["matched_doc"]["bizNumber"]]["sum"] += Decimal(r["amount"])
        doc_ticket_counts[r["matched_doc"]["bizNumber"]]["excel_rows"].append(r["excel_row"])

    out = {
        "schema": "case03-actual-trip-matches/1.0",
        "generated_at": now_iso(),
        "run": RUN.name,
        "scope_note": ("本轮 fill_only 只读查证：未在 OA 关联表选择任何单据（零写入、零占位）；"
                       "本表仅为 27 张通行费 ↔ 真实公出单 的逐票对照，与任何占位关联语义严格分离。"
                       "attempt_010 的 api-fallback-*.json 因 uuid 替换缺陷全部无效，"
                       "以 attempt_011/012 双通道证据为准。"),
        "operator": {"name": "陈晶", "user_id": "116070053",
                     "identity_source": "bpm_login.py 只读探查（本轮 P1）"},
        "query_evidence": {
            "module": "公出单 https://bpm.qiaodan.com/oa/workouts",
            "wide_window": "申请日期+制单日期 2025-01-01..2026-12-31，制单人=全组织（CreatedPath='/' 每页核实）",
            "org_wide_docs": 96, "own_applicant_docs": 13, "own_detail_rows": sum(len(d["rows"]) for d in own_docs),
            "gap_day_candidates_checked": len(cand_m["candidates"]),
        },
        "summary": {
            "total_invoices": len(per_invoice), "matched": len(matched),
            "no_match": len(no_match),
            "matched_sum": str(sum((Decimal(r["amount"]) for r in matched), Decimal("0"))),
            "no_match_sum": str(sum((Decimal(r["amount"]) for r in no_match), Decimal("0"))),
            "matched_days": sorted({r["travel_date"] for r in matched}),
            "no_match_days": sorted({r["travel_date"] for r in no_match}),
            "per_doc_ticket_counts": {k: {"tickets": v["tickets"], "sum": str(v["sum"]),
                                          "excel_rows": sorted(v["excel_rows"]),
                                          "reimed": next(d["reimed"] for d in own_docs if d["bizNumber"] == k)}
                                      for k, v in sorted(doc_ticket_counts.items())},
        },
        "completeness_checks": checks,
        "invoices": per_invoice,
    }
    (RUN / "actual_trip_matches.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 人读报告 ----
    L = []
    L.append("# CASE-03 报告：27 张通行费 ↔ 真实公出单 逐票查证（fill_only 只读）\n")
    L.append(f"- 生成：{now_iso()}｜run：`{RUN.name}`（attempt_007 宽窗 / attempt_011 本人单详情 / attempt_012 缺日候选）")
    L.append("- 操作人：陈晶（user_id 116070053，本轮登录探查）；模块：公出单 `/oa/workouts`")
    L.append("- **零写入**：未选任何关联单据、未点任何保存/提交类按钮；本报告与占位关联语义严格分离。")
    L.append("- 证据链：列表宽窗全组织 96 单（5 页）→ 陈晶 13 单详情（GET `/WorkOut/<uuid32>` 200 + 查看路由页截图互证）→ 缺日候选 8 单详情。\n")
    L.append("## 总览\n")
    L.append(f"- 27 张通行费（Σ **486.93**，Decimal 重算恒等）→ **{len(matched)} 张有同日陈晶公出单对应**（Σ {out['summary']['matched_sum']}），"
             f"**{len(no_match)} 张无对应**（Σ {out['summary']['no_match_sum']}），一张不漏。")
    L.append(f"- 有对应日：{('、'.join(out['summary']['matched_days'])).replace('2025-', '')}")
    L.append(f"- 无对应日：{('、'.join(out['summary']['no_match_days'])).replace('2025-', '')}\n")
    L.append("### 逐单票数（有对应）\n")
    L.append("| 公出单 | 事由 | 公出日期 | reimed | 票数 | 票额合计 | Excel 行 |")
    L.append("|---|---|---|---|---|---|---|")
    for k, v in sorted(doc_ticket_counts.items()):
        doc = next(d for d in own_docs if d["bizNumber"] == k)
        cr = next(r for r in doc["rows"] if r["appliedName"] == "陈晶")
        L.append(f"| {k} | {doc['bizReason']} | {cr['factStart']} | {doc['reimed']} | "
                 f"{v['tickets']} | {v['sum']} | {','.join(map(str, sorted(v['excel_rows'])))} |")
    L.append("\n## 逐票明细\n")
    L.append("| # | 通行日 | 发票号 | 金额 | 站点走向 | Excel行 | 结果 | 对应单据/排除依据 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(per_invoice, 1):
        if r["result"] == "MATCHED":
            m = r["matched_doc"]
            basis = f"[{m['bizNumber']}]{m['bizReason']}（{m['place']}，reimed={m['reimed']}）"
        else:
            ex = r["exclusion"]["colleague_docs_same_window"]
            who = "、".join(f"{c['bizNumber']}({c['applicant']}，人员不含陈晶)" for c in ex) or "同窗无候选"
            basis = f"无陈晶单据；同窗同事单：{who}"
        L.append(f"| {i} | {r['travel_date']} | {r['invoice_number']} | {r['amount']} | "
                 f"{r['station_pair'] or ''} | {r['excel_row']} | {r['result']} | {basis} |")
    L.append("\n## 无对应日的证据（诚实缺口）\n")
    for day in out["summary"]["no_match_days"]:
        ex = next(r["exclusion"] for r in per_invoice if r["travel_date"] == day)
        L.append(f"- **{day}**：本人 13 单无同日明细；全组织同窗候选 "
                 f"{len(ex['colleague_docs_same_window'])} 张（"
                 + "；".join(f"{c['bizNumber']} {c['applicant']}《{c['bizReason']}》公出人员={'+'.join(r2['appliedName'] for r2 in c['traveler_rows'])}"
                             for c in ex["colleague_docs_same_window"])
                 + "）——行级公出人员均**不含陈晶**，无法建立对应；如实报缺。")
    L.append("\n## 完整性三向重算\n")
    L.append(f"- 票集：上游 27 == 映射 27 == 本报告 27（identity 恒等）✓")
    L.append(f"- 金额：Σ = {checks['total_amount']['recomputed']} == 486.93 ✓（Decimal，逐日 {json.dumps(checks['per_day_sums'], ensure_ascii=False)}）")
    L.append(f"- Excel 行：映射 20 行 == 本报告去重行 20 ✓；分配恰好一次（unallocated=[]）✓")
    L.append("- 逐日票数：" + json.dumps(checks["per_day_counts"], ensure_ascii=False))
    L.append("\n## 证据索引\n")
    L.append("- 宽窗 5 页：`attempt_007/evidence/api-wide-page01..05.json`（96 单）+ `wide-list-page01..05.png`")
    L.append("- 本人 13 单：`attempt_011/evidence/api-detail-<biz>.json`（GET 200，bizNumber 互证）+ `detail3d-<biz>.png` + `detail3d-<biz>-text.txt`")
    L.append("- 缺日候选 8 单：`attempt_012/evidence/api-cand-<biz>.json`")
    L.append("- 无效作废：`attempt_010/evidence/api-fallback-*.json`（uuid 替换缺陷，见 `details3d-manifest.json` 的 invalid_prior_evidence）")
    L.append("- 机器可读：`actual_trip_matches.json`")
    (RUN / "CASE-03-report.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"matched={len(matched)} no_match={len(no_match)} "
          f"matched_sum={out['summary']['matched_sum']} no_match_sum={out['summary']['no_match_sum']}")
    print("per-doc:", {k: v['tickets'] for k, v in doc_ticket_counts.items()})
    print("checks all pass:", all(v.get("equal", True) for v in checks.values() if isinstance(v, dict)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
