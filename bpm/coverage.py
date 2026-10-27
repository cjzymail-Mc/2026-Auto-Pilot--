# -*- coding: utf-8 -*-
"""燃料覆盖式通行费报销的严格覆盖模型（V3 §4.1/§4.4；与通用票面=分配约束分离建模）。

模型 fuel_pool_strict_surplus（本案例口径，按 coverage_policy 显式声明启用）：
  K = Σ 纳入行公里数                 （用户里程表，值不来自票据）
  rate = rate_per_km                 （用户公里规则；本案例 1.00 元/公里）
  M = K × rate                       （公里补贴，油车档；电车档等非本案例口径不在本模型）
  T = Σ 纳入范围唯一通行费票面        （逐行回填；汇总单仅交叉核对，不重复计费）
  R = M + T                          （待报销总额）
  O = Σ 覆盖池油票票面               （覆盖凭据；不进入任何费用行）
  F = O + T                          （覆盖凭据总额）
  coverage_margin = F − R            （严格门槛：F > R 才允许 OA 填写；F ≤ R 写入前阻断）

分离原则（V3 §4.4）：
- 油票是覆盖依据不是报销行——O 增大只影响 F/margin，永不增加 R（覆盖富余不加报）；
- 通用 reconcile() 的"每票票面==分配"约束对本模型不适用的部分（油票零分配）不删不改，
  本模型只在显式声明处并行存在；travel/express/rd_materials 既有金额路径零改动；
- 全部 Decimal 精确到分；边界 0.01 元由 Decimal 精确判定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

MODEL_NAME = "fuel_pool_strict_surplus"
STRICT_GATE = "greater"  # F > R 严格大于；F == R / F < R 均阻断

CENT = Decimal("0.01")


def _dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("覆盖模型金额不能为空")
    return Decimal(text)


@dataclass(frozen=True)
class CoverageRow:
    """纳入范围的一行：row_id 定位（如 '汇总!H4'），公里数与该行分到的通行费票。"""
    row_id: str
    km: str
    toll_invoice_ids: tuple = ()  # (invoice_id, ...) 该行分配的唯一通行费


@dataclass(frozen=True)
class CoverageInputs:
    """覆盖模型输入：值必须来自事实层/原件观测（locator 由调用方在事实层登记）。"""
    rate_per_km: str
    rows: tuple                    # (CoverageRow, ...)
    invoice_face_totals: dict      # {invoice_id: 票面价税合计(字符串)} —— 通行费 + 油票全量
    toll_scope_ids: tuple          # 纳入范围的通行费 invoice_id 集
    fuel_pool_ids: tuple           # 覆盖池油票 invoice_id 集（不进任何行）
    rule_source: str               # 规则来源（如 "V3 §4.1 用户公里规则"）


def evaluate_coverage(inputs: CoverageInputs) -> dict:
    """独立核验入口：纯函数，从原始输入重算 K/M/T/R/O/F/margin 与严格门槛。

    任何结构性违规（重复分配/未分配/油票入行/票面缺失）抛 CoverageError，
    不返回部分结果——调用方不得在异常时放行。
    """
    rows = list(inputs.rows)
    toll_scope = list(inputs.toll_scope_ids)
    fuel_pool = list(inputs.fuel_pool_ids)
    overlap = sorted(set(toll_scope) & set(fuel_pool))
    if overlap:
        raise CoverageError("同一票据不得同时是通行范围与油票池: {0}".format(overlap))
    for inv in toll_scope + fuel_pool:
        if inv not in inputs.invoice_face_totals:
            raise CoverageError("票面缺失: {0}".format(inv))

    # 每张纳入通行费恰指向一行一次
    seen: dict[str, str] = {}
    per_row, breakdown = [], []
    for row in rows:
        for inv in row.toll_invoice_ids:
            if inv not in toll_scope:
                raise CoverageError("行 {0} 分到非范围票: {1}".format(row.row_id, inv))
            if inv in seen:
                raise CoverageError("票 {0} 重复分配: 行 {1} 与行 {2}".format(inv, seen[inv], row.row_id))
            if inv in fuel_pool:
                raise CoverageError("油票不得进入行分配: {0}".format(inv))
            seen[inv] = row.row_id
    unallocated = sorted(set(toll_scope) - set(seen))
    if unallocated:
        raise CoverageError("范围票未分配到任何行: {0}".format(unallocated))

    K = sum((_dec(r.km) for r in rows), Decimal("0"))
    rate = _dec(inputs.rate_per_km)
    M = (K * rate).quantize(CENT)
    per_row_detail = []
    T = Decimal("0")
    for row in rows:
        row_toll = sum((_dec(inputs.invoice_face_totals[i]) for i in row.toll_invoice_ids), Decimal("0"))
        T += row_toll
        per_row_detail.append({"row_id": row.row_id, "km": str(_dec(row.km)),
                               "toll_ids": list(row.toll_invoice_ids), "row_toll": str(row_toll.quantize(CENT))})
    T = T.quantize(CENT)
    R = (M + T).quantize(CENT)
    O = sum((_dec(inputs.invoice_face_totals[i]) for i in fuel_pool), Decimal("0")).quantize(CENT)
    F = (O + T).quantize(CENT)
    margin = (F - R).quantize(CENT)
    strict_pass = F > R  # 严格大于；等于/小于均 False
    return {
        "model": MODEL_NAME, "strict_gate": STRICT_GATE, "rule_source": inputs.rule_source,
        "K_km": str(K), "rate_per_km": str(rate), "M_subsidy": str(M),
        "T_toll": str(T), "R_reimburse": str(R),
        "O_fuel_pool": str(O), "F_coverage_total": str(F),
        "coverage_margin": str(margin),
        "gate_passed": bool(strict_pass),
        "rows": per_row_detail,
        "invoice_allocation": seen,
        "notes": ["油票为覆盖凭据不入行分配：O 变化只影响 F/margin，不改变 R",
                  "汇总单仅作逐票交叉核对，不参与计费"],
    }


class CoverageError(ValueError):
    """覆盖模型结构性违规（重复/未分配/油票入行/票面缺失/算术不符）。"""


def register_coverage_fact(factset, result: dict, *, locator: str, input_hashes=None) -> str:
    """把 evaluate_coverage 结果登记为事实层 coverage_evaluation 事实（确定性计算，必带 derivation）。"""
    derivation = ("fuel_pool_strict_surplus: K={K}×rate={rate}=M; T=Σ范围票面; R=M+T; "
                  "O=Σ油票池票面; F=O+T; margin=F-R; 严格门槛 F>R={passed}").format(
        K=result["K_km"], rate=result["rate_per_km"], passed=result["gate_passed"])
    return factset.add(
        "coverage_evaluation", source="deterministic_computation",
        value={k: result[k] for k in ("model", "strict_gate", "rule_source", "K_km", "rate_per_km",
                                      "M_subsidy", "T_toll", "R_reimburse", "O_fuel_pool",
                                      "F_coverage_total", "coverage_margin", "gate_passed")},
        locator=locator, derivation=derivation, input_hashes=input_hashes or {})


def validate_coverage_block(block) -> list:
    """计划侧声明校验（validate_plan 可选 coverage 键）：结构封闭 + 算术复算 + 严格门槛。

    只校验声明块自身一致性（K×rate=M、M+T=R、O+T=F、F-R=margin、F>R）；
    与事实层的绑定一致性由 sources/事实 id 在生成器侧保证，本函数不复算事实。
    返回 issues 列表（空=通过）；F ≤ R 一律拒绝（写入前阻断，V3 §13.1）。
    """
    issues = []

    def bad(message, code="COVERAGE_INVALID"):
        issues.append({"code": code, "message": message})

    if not isinstance(block, dict):
        return [{"code": "COVERAGE_INVALID", "message": "coverage 必须是对象"}]
    allowed = {"model", "strict_gate", "rule_source", "rate_per_km",
               "K_km", "M_subsidy", "T_toll", "R_reimburse",
               "O_fuel_pool", "F_coverage_total", "coverage_margin"}
    for key in sorted(set(block) - allowed):
        bad("未知 coverage 键: {0}".format(key))
    for key in sorted(allowed - set(block)):
        bad("coverage 缺键: {0}".format(key))
    if issues:
        return issues
    if block["model"] != MODEL_NAME:
        bad("仅支持模型 {0}".format(MODEL_NAME))
    if block["strict_gate"] != STRICT_GATE:
        bad("strict_gate 仅支持 {0}".format(STRICT_GATE))
    if not str(block.get("rule_source", "")).strip():
        bad("rule_source 必填（规则来源）")
    try:
        K, rate = _dec(block["K_km"]), _dec(block["rate_per_km"])
        M, T = _dec(block["M_subsidy"]), _dec(block["T_toll"])
        R, O = _dec(block["R_reimburse"]), _dec(block["O_fuel_pool"])
        F, margin = _dec(block["F_coverage_total"]), _dec(block["coverage_margin"])
    except Exception as exc:  # noqa: BLE001 —— 非法数值统一转 issue
        return issues + [{"code": "COVERAGE_INVALID", "message": "coverage 数值不可解析: {0}".format(exc)}]
    for name, got, want in (
        ("M=K×rate", M, (K * rate).quantize(CENT)),
        ("R=M+T", R, (M + T).quantize(CENT)),
        ("F=O+T", F, (O + T).quantize(CENT)),
        ("coverage_margin=F-R", margin, (F - R).quantize(CENT)),
    ):
        if got != want:
            bad("{0} 不闭合: 声明 {1} 复算 {2}".format(name, got, want))
    if not issues and not F > R:
        issues.append({"code": "COVERAGE_GATE_BLOCKED",
                       "message": "覆盖门槛未达（须 F>R 严格大于）: F={0} R={1} margin={2}——阻断 OA 写入".format(F, R, margin)})
    return issues
