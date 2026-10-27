# -*- coding: utf-8 -*-
"""V3-R03 CASE-02 阶段 A：范围裁定——Excel 行 ↔ 唯一通行费票据逐票映射（只读）。

上游：case01-facts.json（round-2 CASE-01 事实层）+ 原件 xlsx（openpyxl 只读，绝不保存）。
裁定规则（合同 ctr-14bb5408）：
- 主键 = 票面 travel_date + 行方向（D=厦门总部→E=X 为去程；D=X→E=厦门总部 为返程）；
  组内两汇总单按站点方向分去/返（起点翔安=去程；终点翔安/同安=返程）。
- 每张纳入票据恰好指向行内一次分配；多票到同一行逐票列示后求和。
- 无法分配/重复分配/跨日歧义登记 gaps，不摊分、不按文件序。
- 0917 返程票面终点同安站 vs 行目的地厦门总部：按日期+方向映射成立，差异登记。
输出 case02-mapping.json：行级映射 + 票级反查 + K/M/T 推导 + gaps + 原件哈希前值。
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FACTS = ROOT / "automation/runs/20261026-115500-v3r02-case01/case01-facts.json"
XLSX = ROOT / "feature01-细化报销skill/12月公出-发票/12月-自驾公出公里数统计表.xlsx"
MANIFEST = ROOT / "automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json"

RATE_PER_KM = Decimal("1.00")  # 用户公里规则：1 元/公里（本案例冻结实测口径；表头电车 0.15 档见冲突记录）


def main() -> int:
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    byfile = {f["rel"]: f for f in facts["files"]}
    def fact(rel, k):
        v = (byfile[rel].get("facts") or {}).get(k)
        return v["value"] if isinstance(v, dict) else v

    # -- 票据池：27 张唯一通行费（identity -> 票面事实）
    tolls = {}
    for info in facts["identities"]:
        if not info["identity"].startswith("toll:"):
            continue
        rel = info["files"][0]["rel"]
        tolls[info["identity"]] = {
            "rel": rel, "sha256": info["files"][0]["sha256"],
            "invoice_number": fact(rel, "invoice_number"),
            "total": Decimal(fact(rel, "total_amount")),
            "travel_date": fact(rel, "travel_date_from"),
        }

    # -- 行程池：20 汇总单身份（方向由 station_pair 判）
    trips = []
    for info in facts["identities"]:
        if not info["identity"].startswith("summary:"):
            continue
        rel = info["files"][0]["rel"]
        pair = fact(rel, "station_pair")          # "A 至 B"
        a, b = (s.strip() for s in pair.split("至"))
        outbound = a.endswith("翔安站")            # 起点翔安=去程（厦门→晋江方向）
        trips.append({
            "identity": info["identity"], "rel": rel,
            "summary_number": fact(rel, "summary_number"),
            "total": Decimal(fact(rel, "total_amount")),
            "from_station": a, "to_station": b,
            "direction": "out" if outbound else "return",
            "dates": sorted({d for d in fact(rel, "trip_dates_raw")}),
            "invoices": [r for r in fact(rel, "referenced_invoices")],
        })

    # -- 原件行（只读）；返程行 C 列空，日期自同序号去程行承接（去返成对结构，round-1/2 已核实）
    wb = openpyxl.load_workbook(XLSX, data_only=False, read_only=False)
    ws = wb["汇总"]
    rows = []
    pending_date = None
    for r in range(4, 24):
        d, e = ws.cell(row=r, column=4).value, ws.cell(row=r, column=5).value
        if not d:
            continue
        serial = ws.cell(row=r, column=3).value
        if serial is not None:
            date = openpyxl.utils.datetime.from_excel(serial).date().isoformat()
            pending_date = date
        else:
            date = pending_date
        rows.append({
            "row": r, "from": d, "to": e,
            "direction": "out" if d == "厦门总部" else "return",
            "km": Decimal(str(ws.cell(row=r, column=6).value)),
            "subsidy": Decimal(str(ws.cell(row=r, column=7).value)),
            "date_serial": serial,
            "date": date,
        })

    # -- 逐行映射
    gaps, mapping = [], []
    used_invoices: dict[str, dict] = {}
    for row in rows:
        date_compact = row["date"].replace("-", "")
        cands = [t for t in trips if t["direction"] == row["direction"] and date_compact in t["dates"]]
        if len(cands) != 1:
            gaps.append({"row": row["row"], "date": row["date"], "direction": row["direction"],
                         "problem": f"行程候选 {len(cands)} 个（应为 1）", "candidates": [c["identity"] for c in cands]})
            continue
        trip = cands[0]
        invs, row_total = [], Decimal("0")
        for num in trip["invoices"]:
            ident = next((k for k, v in tolls.items() if v["invoice_number"] == num), None)
            if ident is None:
                gaps.append({"row": row["row"], "problem": f"汇总单引用票 {num} 无独立票文件"})
                continue
            if ident in used_invoices:
                gaps.append({"row": row["row"], "problem": f"票 {ident} 重复分配（先 {used_invoices[ident]['row']} 后 {row['row']}）"})
                continue
            used_invoices[ident] = {"row": row["row"], "summary": trip["identity"]}
            invs.append({"identity": ident, "invoice_number": num,
                         "amount": str(tolls[ident]["total"]), "rel": tolls[ident]["rel"],
                         "sha256": tolls[ident]["sha256"]})
            row_total += tolls[ident]["total"]
        note = None
        if row["direction"] == "return" and trip["to_station"].endswith("同安站"):
            note = "票面终点 同安站 vs 行目的地 厦门总部（站点↔地址两套词汇，按日期+方向映射，差异登记）"
        mapping.append({
            "row": row["row"], "date": row["date"], "direction": row["direction"],
            "km": str(row["km"]), "subsidy": str(row["subsidy"]),
            "trip": {"identity": trip["identity"], "summary_number": trip["summary_number"],
                     "station_pair": f"{trip['from_station']} 至 {trip['to_station']}",
                     "declared_total": str(trip["total"])},
            "invoices": invs, "row_toll_total": str(row_total), "note": note,
        })

    # -- 闭合核对
    unallocated = sorted(set(tolls) - set(used_invoices))
    if unallocated:
        gaps.append({"problem": "存在未分配票据", "identities": unallocated})
    K = sum((m["km"] and Decimal(m["km"]) for m in mapping), Decimal("0"))
    M = K * RATE_PER_KM
    T = sum((Decimal(m["row_toll_total"]) for m in mapping), Decimal("0"))
    declared_check = all(Decimal(m["row_toll_total"]) == Decimal(m["trip"]["declared_total"]) for m in mapping)

    # -- 原件哈希前值（74 件对 round-1 manifest）
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = [(g, f) for g in manifest["groups"].values() for f in g["files"]]
    pre_drift = [f["rel"] for _, f in files
                 if hashlib.sha256((ROOT / "feature01-细化报销skill/12月公出-发票" / f["rel"]).read_bytes()).hexdigest() != f["sha256"]]

    out = {
        "stage": "A 范围裁定（Excel 行 ↔ 唯一通行费票据）",
        "rule": "主键=票面 travel_date + 行方向；组内两汇总单按站点方向分去/返；每票恰一次行内分配",
        "rate_per_km": str(RATE_PER_KM),
        "km_rule_source": "V3 §4.1 用户公里规则 1 元/公里（本案例冻结实测口径）；表头电车 0.15 档与孰低原则=冲突记录，不改值（本表全部按 1 元/公里补贴列实测值）",
        "rows": mapping, "invoice_allocation_index": used_invoices, "gaps": gaps,
        "closure": {
            "toll_identities_total": len(tolls), "allocated": len(used_invoices),
            "unallocated": unallocated, "rows_mapped": len(mapping), "rows_total": len(rows),
            "row_totals_equal_summary_declared": declared_check,
        },
        "observed": {"K_km": str(K), "M_subsidy_expected": str(M), "T_toll": str(T),
                     "R_reimburse_expected": str(M + T)},
        "pre_hash_files": len(files), "pre_hash_drift": pre_drift,
    }
    (RUN / "case02-mapping.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rows {len(mapping)}/{len(rows)}; invoices {len(used_invoices)}/{len(tolls)}; "
          f"unallocated={unallocated or 'NONE'}; gaps={len(gaps)}; "
          f"K={K} M={M} T={T} R={M + T}; declared_check={declared_check}; pre_drift={pre_drift or 'NONE'}")
    return 0 if (not gaps and not unallocated and len(mapping) == len(rows) and declared_check and not pre_drift) else 1


if __name__ == "__main__":
    raise SystemExit(main())
