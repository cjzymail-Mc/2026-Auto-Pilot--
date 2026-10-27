# -*- coding: utf-8 -*-
"""V3-R03 CASE-02/04 阶段 D：真实案例覆盖计算与双报告（bpm_coverage 独立核验入口）。

输入=case02-mapping.json（行级裁定）+ case01-facts.json（票面）；
用生产模块 bpm_coverage.evaluate_coverage 重算 K/M/T/R/O/F/margin/门槛（独立于 stage A 的内联算术），
登记事实层 coverage_evaluation，过 validate_coverage_block，写 JSON+MD 双报告。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bpm_coverage import CoverageInputs, CoverageRow, evaluate_coverage, register_coverage_fact, validate_coverage_block  # noqa: E402
from bpm_facts import FactSet  # noqa: E402

RUN = Path(__file__).resolve().parent
MAPPING = RUN / "case02-mapping.json"
FACTS = ROOT / "automation/runs/20261026-115500-v3r02-case01/case01-facts.json"


def main() -> int:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    facts = json.loads(FACTS.read_text(encoding="utf-8"))
    byfile = {f["rel"]: f for f in facts["files"]}

    def face(rel):
        v = (byfile[rel].get("facts") or {}).get("total_amount")
        return v["value"]

    # 票面全量：27 通行费 + 5 油票（identity -> 票面价税合计）
    invoice_faces, toll_scope, fuel_pool = {}, [], []
    for info in facts["identities"]:
        rel = info["files"][0]["rel"]
        invoice_faces[info["identity"]] = face(rel)
        if info["identity"].startswith("toll:"):
            toll_scope.append(info["identity"])
        elif info["identity"].startswith("fuel:"):
            fuel_pool.append(info["identity"])

    # 行：row_id=汇总!H{r}，toll ids 从映射行反解（经汇总单引用票号→identity）
    num_to_ident = {info["identity"].split("-", 1)[1]: info["identity"]
                    for info in facts["identities"] if info["identity"].startswith("toll:")}
    rows = []
    for m in mapping["rows"]:
        inv_ids = tuple(num_to_ident[i["invoice_number"]] for i in m["invoices"])
        rows.append(CoverageRow("汇总!H{0}".format(m["row"]), m["km"], inv_ids))

    inputs = CoverageInputs(
        rate_per_km="1.00", rows=tuple(rows),
        invoice_face_totals=invoice_faces,
        toll_scope_ids=tuple(toll_scope), fuel_pool_ids=tuple(fuel_pool),
        rule_source="V3 §4.1 用户公里规则：1 元/公里（本案例冻结实测口径；表头电车 0.15 档登记冲突不改值）",
    )
    result = evaluate_coverage(inputs)

    # 事实层登记（真实案例演示链路；FactSet 仅本脚本内存态+落 run 报告，不写共享 registry）
    fs = FactSet(business_ref="V3-R03-CASE-04")
    fid = register_coverage_fact(
        fs, result, locator="case02-mapping.json#observed",
        input_hashes={"case01-facts.json": hashlib.sha256(FACTS.read_bytes()).hexdigest(),
                      "case02-mapping.json": hashlib.sha256(MAPPING.read_bytes()).hexdigest()})

    # 计划侧声明块校验（同一数值走 validate_coverage_block）
    block = {k: result[k] for k in ("model", "strict_gate", "rule_source", "rate_per_km", "K_km",
                                    "M_subsidy", "T_toll", "R_reimburse", "O_fuel_pool",
                                    "F_coverage_total", "coverage_margin")}
    issues = validate_coverage_block(block)

    json_out = {
        "stage": "D 真实案例覆盖计算（fuel_pool_strict_surplus）",
        "result": result, "fact_id": fid,
        "validate_coverage_block_issues": issues,
        "sources": {
            "K_km": "12月-自驾公出公里数统计表.xlsx 汇总!F4:F23 实测公里数合计（20 数据行全纳入）",
            "rate_per_km": "V3 §4.1 用户公里规则 1.00 元/公里",
            "M_subsidy": "K×rate（=G 列既有补贴值合计 1438 观测一致）",
            "T_toll": "27 张唯一通行费票面价税合计（CASE-01 facts，逐行分配见 case02-mapping）",
            "O_fuel_pool": "5 张油票票面价税合计（2025-12-12 中国石化 95#，覆盖池不入行）",
            "gate": "F>R 严格大于才允许 OA 填写；F≤R 阻断（V3 §13.1）",
        },
    }
    (RUN / "case02-coverage.json").write_text(json.dumps(json_out, ensure_ascii=False, indent=1), encoding="utf-8")

    md = ["# CASE-02/04 覆盖计算报告（V3-R03 / ctr-14bb5408）", "",
          "模型 `fuel_pool_strict_surplus`（bpm_coverage.evaluate_coverage 独立重算，与 stage-A 内联算术互证）：", "",
          "| 量 | 值 | 来源 |", "|---|---|---|",
          f"| K（公里） | {result['K_km']} | 汇总!F4:F23 实测合计（20 行全纳入） |",
          f"| 单价 | {result['rate_per_km']} 元/公里 | V3 §4.1 用户公里规则（表头电车 0.15 档登记冲突不改值） |",
          f"| M（公里补贴） | {result['M_subsidy']} | K×单价（=G 列 1438 观测一致） |",
          f"| T（通行费） | {result['T_toll']} | 27 张唯一通行费票面（CASE-01 facts 逐票锚点） |",
          f"| **R（待报销=M+T）** | **{result['R_reimburse']}** | M+T |",
          f"| O（油票池） | {result['O_fuel_pool']} | 5 张油票票面（2025-12-12，覆盖池不入行） |",
          f"| **F（覆盖凭据=O+T）** | **{result['F_coverage_total']}** | O+T |",
          f"| coverage_margin=F−R | {result['coverage_margin']} | F−R |",
          f"| 严格门槛 F>R | **{'通过' if result['gate_passed'] else '未达（阻断 OA 写入）'}** | V3 §4.4/§13.1 |", "",
          f"事实层登记：`{fid}`（coverage_evaluation / deterministic_computation / derivation 内含算术链）。",
          f"计划侧声明块校验 issues：{issues or '无（一致）'}。", "",
          "油票为覆盖凭据不入行分配：O 增大只抬 F/margin，永不增加 R；汇总单仅交叉核对不重复计费。",
          ""]
    (RUN / "CASE-02-04-report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"K={result['K_km']} M={result['M_subsidy']} T={result['T_toll']} R={result['R_reimburse']} "
          f"O={result['O_fuel_pool']} F={result['F_coverage_total']} margin={result['coverage_margin']} "
          f"gate={'PASS' if result['gate_passed'] else 'BLOCKED'}; block_issues={len(issues)}; fact={fid}")
    return 0 if result["gate_passed"] and not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
