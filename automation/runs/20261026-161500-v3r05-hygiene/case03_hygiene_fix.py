# -*- coding: utf-8 -*-
"""V3-R05 证据卫生修复（合同 ctr-82e59a70 §1-3）：round-4 工件加法式订正。

O1 wide-query-manifest：每页加 sha256_file（证据文件字节 sha256）+ 顶层 hash_semantics；
   原 sha256 保留为 logical-json 口径，不删不改值。
O2 日期口径文档化：candidates3e-manifest 顶层 date_field_semantics；
   actual_trip_matches 顶层 date_field_semantics（matched=实际公出时间口径，
   排除块=自然区间口径，12 张 MATCHED 两口径等价）。
O3 matched_doc 补 applicant/applicant_user_id：逐单回读 attempt_011 api-detail
   原始 body（appliedName/appliedBy）取值，不从报告倒抄；ui_text 统一 run 相对路径。
报告逐单表加申请人列；final-artifact-hashes 同步；73 原件零漂移第 5 轮复核；
全程零浏览器、零业务写入；修订前后哈希对照表落本 run 目录。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN = Path(__file__).resolve().parent
R4 = RUN.parent / "20261026-143340-v3r04-case03"
V3R00_MANIFEST = RUN.parent.parent / "runs/20261026-100322-v3r00-inventory/case-file-manifest.json"
ORIGINALS = RUN.parent.parent.parent / "feature01-细化报销skill/12月公出-发票"

CST = timezone(timedelta(hours=8))


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def log_event(event: str, **kw):
    rec = {"ts": now_iso(), "event": event, **kw}
    with (RUN / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main() -> int:
    targets = ["wide-query-manifest.json", "candidates3e-manifest.json",
               "actual_trip_matches.json", "final-artifact-hashes.json", "CASE-03-report.md"]
    # 权威 before 值取 round-4 finish 归档的 handoff-input.json（避免中断重跑污染）；
    # 首次执行时曾直接读盘，中断后盘上已是部分修订态，不能再用作 before。
    handoff = json.loads((RUN.parent.parent.parent / "handoff-input.json").read_text(encoding="utf-8"))
    before = {}
    for t in targets:
        key = f"automation/runs/20261026-143340-v3r04-case03/{t}"
        assert key in handoff["artifacts"], key
        before[t] = handoff["artifacts"][key]
    log_event(event="hygiene_start", targets=targets, before_source="round-4 handoff-input.json")

    # ---------- O1 ----------
    wq = json.loads((R4 / "wide-query-manifest.json").read_text(encoding="utf-8"))
    ev_dir = R4 / "attempt_007" / "evidence"
    for pg in wq["pages"]:
        f = ev_dir / pg["evidence"]
        assert f.is_file(), f
        pg["sha256_file"] = sha_file(f)
    wq["hash_semantics"] = {
        "added_at": now_iso(),
        "sha256": "logical-json 口径：捕获记录紧凑 json.dumps(payload, ensure_ascii=False) 的 sha256"
                  "（case03_probe._drain_capture 计算；与本页 evidence 落盘文件字节哈希不同属预期）",
        "sha256_file": "文件字节口径：attempt_007/evidence/<evidence> 落盘文件的 sha256，可直接复算",
        "root_cause": "run 内脚本 case03_probe.py:123-124 对紧凑串计哈希而落盘用 indent=1；"
                      "共享探针库无此缺陷；防复发规范见 .claude/skills/bpm-fill-run/references/evidence-hash-semantics.md",
    }
    (R4 / "wide-query-manifest.json").write_text(
        json.dumps(wq, ensure_ascii=False, indent=1), encoding="utf-8")
    log_event(event="o1_done", pages=len(wq["pages"]))

    # ---------- O2 ----------
    c3e = json.loads((R4 / "candidates3e-manifest.json").read_text(encoding="utf-8"))
    c3e["date_field_semantics"] = {
        "added_at": now_iso(),
        "rows[].factStart/factEnd 与 covers_gap_day": "取 factNatureStartDate/factNatureEndDate"
            "（含途自然行程区间）口径；非 factStartTime/factEndTime（实际公出时间）口径",
        "divergence_example": "12025095297 实际公出时间仅 2025-09-18，自然区间 2025-09-17..09-18；"
                              "按自然区间判 covers_day=true（排除结论不受影响：行级公出人员不含陈晶）",
    }
    (R4 / "candidates3e-manifest.json").write_text(
        json.dumps(c3e, ensure_ascii=False, indent=1), encoding="utf-8")

    atm = json.loads((R4 / "actual_trip_matches.json").read_text(encoding="utf-8"))
    atm["date_field_semantics"] = {
        "added_at": now_iso(),
        "matched_doc.chen_trip": "factStartTime/factEndTime 实际公出时间口径（attempt_011 api-detail 原始字段）",
        "exclusion.colleague_docs_same_window[].traveler_rows": "factNatureStartDate/factNatureEndDate "
            "自然区间口径（candidates3e-manifest 同源）",
        "equivalence": "12 张 MATCHED 票上两口径等价（本人单均为单日行程，A round-4 验收已核）；"
                       "分歧示例见 candidates3e-manifest.date_field_semantics.divergence_example",
    }
    log_event(event="o2_done")

    # ---------- O3：applicant 字段 + ui_text 路径统一 ----------
    det_dir = R4 / "attempt_011" / "evidence"
    patched = 0
    for inv in atm["invoices"]:
        if inv["result"] != "MATCHED":
            continue
        md = inv["matched_doc"]
        body = json.loads((det_dir / f"api-detail-{md['bizNumber']}.json").read_text(encoding="utf-8"))["body"]
        assert body["bizNumber"] == md["bizNumber"]
        md["applicant"] = body["appliedName"]
        md["applicant_user_id"] = str(body["appliedBy"])
        # ui_text 等价替换为 run 相对路径（与 api_file/ui_screenshot 一致）
        ut = md["evidence"]["ui_text"]
        md["evidence"]["ui_text"] = f"attempt_011/evidence/{ut}" \
            if not ut.startswith("attempt_") else ut
        patched += 1
    assert patched == 12, patched
    # 一致性抽核：ui_screenshot 形态
    shots = {inv["matched_doc"]["evidence"]["ui_screenshot"]
             for inv in atm["invoices"] if inv["result"] == "MATCHED"}
    assert all(s.startswith("attempt_011/evidence/") for s in shots), shots
    atm["revision_note"] = {
        "added_at": now_iso(), "round": "V3-R05", "contract": "ctr-82e59a70",
        "changes": ["matched_doc 增 applicant/applicant_user_id（逐单回读 api-detail 原始 body）",
                    "matched_doc.evidence.ui_text 由裸文件名等价替换为 run 相对路径（attempt_011/evidence/ 前缀）",
                    "新增顶层 date_field_semantics"],
        "immutable": "其余键值含 15 条 NO_MATCH 排除块、completeness_checks、scope_note 均未改动",
    }
    (R4 / "actual_trip_matches.json").write_text(
        json.dumps(atm, ensure_ascii=False, indent=1), encoding="utf-8")
    log_event(event="o3_done", patched=patched)

    # ---------- 报告逐单表加申请人列（幂等：已加则跳过） ----------
    rep_p = R4 / "CASE-03-report.md"
    rep = rep_p.read_text(encoding="utf-8")
    old_head = "| 公出单 | 事由 | 公出日期 | reimed | 票数 | 票额合计 | Excel 行 |"
    new_head = "| 公出单 | 申请人 | 事由 | 公出日期 | reimed | 票数 | 票额合计 | Excel 行 |"
    old_sep = "|---|---|---|---|---|---|---|"
    new_sep = "|---|---|---|---|---|---|---|---|"
    if old_head in rep:
        assert rep.count(old_head) == 1 and rep.count(old_sep) >= 1
        rep = rep.replace(old_head, new_head)
        def row_sub(m):
            return f"| {m.group(1)} | 陈晶(116070053) | {m.group(2)}"
        pat = re.compile(r"\| (12025\d{6}) \| ([^|]+ \| 2025-)", re.M)
        rep, n = pat.subn(row_sub, rep)
        assert n == 5, f"per-doc rows patched={n}"
        rep = rep.replace(new_head + "\n" + old_sep, new_head + "\n" + new_sep, 1)
        rep_p.write_text(rep, encoding="utf-8")
        log_event(event="report_applicant_column_added", rows=n)
    else:
        assert new_head in rep and "陈晶(116070053)" in rep
        log_event(event="report_applicant_column_skipped", reason="already patched")

    # ---------- final-artifact-hashes 同步 ----------
    fah = json.loads((R4 / "final-artifact-hashes.json").read_text(encoding="utf-8"))
    fah["revision"] = {
        "added_at": now_iso(), "round": "V3-R05",
        "note": "O1/O2/O3 加法订正后重算；新增 wide-query-manifest.json 与 CASE-03-report.md；"
                "原 6 键保留新值（文件本体修订）",
    }
    for name in list(fah.keys()):
        if name == "revision":
            continue
        fah[name] = sha_file(R4 / name)
    fah["wide-query-manifest.json"] = sha_file(R4 / "wide-query-manifest.json")
    fah["CASE-03-report.md"] = sha_file(R4 / "CASE-03-report.md")
    (R4 / "final-artifact-hashes.json").write_text(
        json.dumps(fah, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- 73 原件零漂移第 5 轮复核 ----------
    man = json.loads(V3R00_MANIFEST.read_text(encoding="utf-8"))
    entries = [f for g in man["groups"].values() for f in g["files"]]
    drift = []
    for e in entries:
        rel, want = e["rel"], e["sha256"]
        p = ORIGINALS / rel
        if not p.is_file() or sha_file(p) != want:
            drift.append(rel)
    assert len(entries) == man["total_files"] == 73, len(entries)
    log_event(event="originals_drift_check", files=len(entries), drift=drift)
    assert not drift, drift

    # ---------- 前后哈希对照 ----------
    after = {t: sha_file(R4 / t) for t in targets}
    table = {t: {"before": before[t], "after": after[t],
                 "changed": before[t] != after[t]} for t in targets}
    (RUN / "revision-hashes.json").write_text(
        json.dumps({"generated_at": now_iso(), "round": "V3-R05",
                    "contract": "ctr-82e59a70", "targets": table},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    log_event(event="hygiene_artifacts_done", changed=[t for t in table if table[t]["changed"]])
    print(json.dumps({t: table[t]["changed"] for t in targets}, ensure_ascii=False))
    print("originals: 73 checked, drift=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
