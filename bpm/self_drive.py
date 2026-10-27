# -*- coding: utf-8 -*-
"""自驾公出报销规则模型 v1（BPM-SELFDRIVE-20261027-V1 §4.4；与旧覆盖模型分离并存）。

模型 self_drive_strict_surplus_v1（规则配置 automation/business-scenarios/self_drive.json）：
  每行交通 = 原始公里数 × rate_per_km + 该行唯一通行票金额之和
  M = Σ 行公里补贴                 （用户公里数，值不来自票据）
  T = Σ 范围内唯一通行费票面        （逐行回填；汇总单仅交叉核对，不重复计费）
  C = 有效公出日去重数 × meal_per_valid_day
                                  （仅本次报销单制单人；有效日=本次范围∩已核实参与日；
                                    同日多事实/多单只计一次；不乘同行人数、不按票数计）
  R = M + T + C                    （新规则最终应报额）
  O = Σ 覆盖池油票票面              （覆盖凭据；不进入任何费用行）
  F = O + T                        （覆盖凭据总额，不是费用额）
  coverage_margin = F − R          （严格门槛：F > R 才允许 OA 填写；F ≤ R 写入前阻断，无浮点容差）

分离原则（合同 §4.4）：
- 油票是覆盖依据不是报销行——O 增大只影响 F/margin，永不增加 R；
- 新 30.00/日餐补与旧单历史餐补（12/18/24/36/48）分开建模：本模型只接受规则配置声明的
  meal_per_valid_day，旧值传入即拒绝，不折算、不沿用；
- 旧 fuel_pool_strict_surplus（R=M+T，bpm_coverage.py）按 V3 冻结口径并存，零改动；
  旧任务不静默升级，新场景绑定本配置版本与哈希；
- 全部 Decimal 精确到分；金额输入必须是两位小数可解析字符串，拒绝浮点容差放行。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bpm.paths import ROOT
DEFAULT_CONFIG = ROOT / "automation" / "business-scenarios" / "self_drive.json"

MODEL_NAME = "self_drive_strict_surplus_v1"
SCENARIO_ID = "self_drive"
STRICT_GATE = "greater"  # F > R 严格大于；F == R / F < R 均阻断
CENT = Decimal("0.01")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SelfDriveError(ValueError):
    """自驾规则结构性违规（配置/重复分配/未分配/油票入行/票面缺失/规则值不一致/日期非法）。"""


def _dec(value, what: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise SelfDriveError("{0} 不接受浮点输入（用字符串金额）: {1}".format(what, value))
    text = str(value).strip()
    if not text:
        raise SelfDriveError("{0} 不能为空".format(what))
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise SelfDriveError("{0} 不可解析为 Decimal: {1!r}".format(what, value)) from exc


# ---------------------------------------------------------------- 规则配置加载

@dataclass(frozen=True)
class SelfDriveRules:
    """从 self_drive.json 加载并校验的规则快照（版本+单价+模型+门槛）。"""
    scenario_id: str
    version: str
    model: str
    rate_per_km: Decimal
    meal_per_valid_day: Decimal
    strict_gate: str
    config_path: str
    config_sha256: str
    rule_source: str

    def rate_str(self) -> str:
        return str(self.rate_per_km)

    def meal_str(self) -> str:
        return str(self.meal_per_valid_day)


def rules_sha256(config_path=DEFAULT_CONFIG) -> str:
    p = Path(config_path)
    if not p.is_file():
        raise SelfDriveError("规则配置不存在: {0}".format(p))
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_self_drive_rules(config_path=DEFAULT_CONFIG) -> SelfDriveRules:
    """加载并封闭校验规则配置；任何结构/数值偏差抛 SelfDriveError（不返回部分结果）。"""
    p = Path(config_path)
    if not p.is_file():
        raise SelfDriveError("规则配置不存在: {0}".format(p))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SelfDriveError("规则配置不是合法 JSON: {0}".format(exc)) from exc

    for key in ("schema_version", "scenario_id", "version", "rules", "rule_source"):
        if key not in data:
            raise SelfDriveError("规则配置缺键: {0}".format(key))
    if data["schema_version"] != "1.0":
        raise SelfDriveError("schema_version 仅支持 1.0: {0}".format(data["schema_version"]))
    if data["scenario_id"] != SCENARIO_ID:
        raise SelfDriveError("scenario_id 不匹配: {0}".format(data["scenario_id"]))

    rules = data["rules"]
    if rules.get("model") != MODEL_NAME:
        raise SelfDriveError("model 仅支持 {0}: {1}".format(MODEL_NAME, rules.get("model")))
    if rules.get("strict_gate") != STRICT_GATE:
        raise SelfDriveError("strict_gate 仅支持 {0}: {1}".format(STRICT_GATE, rules.get("strict_gate")))
    rate = _dec(rules.get("rate_per_km"), "rate_per_km")
    meal = _dec(rules.get("meal_per_valid_day"), "meal_per_valid_day")
    if rate <= 0 or meal <= 0:
        raise SelfDriveError("单价必须为正: rate={0} meal={1}".format(rate, meal))
    src = data["rule_source"]
    if not str(src.get("contract", "")).strip() or not str(src.get("user_rule_statement", "")).strip():
        raise SelfDriveError("rule_source 缺 contract/user_rule_statement（规则须有来源）")
    sep = rules.get("separation") or {}
    if not isinstance(sep.get("historical_meal_values_not_reused"), list):
        raise SelfDriveError("separation.historical_meal_values_not_reused 必须是列表")
    return SelfDriveRules(
        scenario_id=data["scenario_id"], version=str(data["version"]), model=rules["model"],
        rate_per_km=rate.quantize(CENT), meal_per_valid_day=meal.quantize(CENT),
        strict_gate=rules["strict_gate"], config_path=str(p),
        config_sha256=rules_sha256(p), rule_source=src["user_rule_statement"])


# ---------------------------------------------------------------- 金额模型输入

@dataclass(frozen=True)
class SelfDriveRow:
    """纳入范围的一行：row_id 定位（如 '汇总!H4'），用户公里数与该行分到的唯一通行票。"""
    row_id: str
    km: str
    toll_invoice_ids: tuple = ()


@dataclass(frozen=True)
class MealDay:
    """一个有效公出日：date 为 ISO 日期；basis 为该制单人参与事实的来源引用
    （如 '<公出单号>/行2' 或事实层 id）。调用方负责交集与去重依据，本层拒绝重复日期。"""
    date: str
    basis: str = ""


@dataclass(frozen=True)
class SelfDriveInputs:
    """模型输入：值必须来自事实层/原件观测（locator 由调用方在事实层登记）。

    rate_per_km / meal_per_valid_day 必须与规则配置一致（新旧行为分离：历史餐补值传入即拒绝）。"""
    rate_per_km: str
    meal_per_valid_day: str
    rows: tuple                    # (SelfDriveRow, ...)
    meal_days: tuple               # (MealDay, ...) 有效公出日（已交集、已去重）
    invoice_face_totals: dict      # {invoice_id: 票面价税合计(字符串)} —— 通行费 + 油票全量
    toll_scope_ids: tuple          # 纳入范围的通行费 invoice_id 集
    fuel_pool_ids: tuple           # 覆盖池油票 invoice_id 集（不进任何行）
    rule_source: str
    rule_version: str = "1.0.0"


def evaluate_self_drive(inputs: SelfDriveInputs, rules: SelfDriveRules | None = None) -> dict:
    """独立核验入口：纯函数，从原始输入重算 K/M/T/C/R/O/F/margin 与严格门槛。

    任何结构性违规抛 SelfDriveError，不返回部分结果——调用方不得在异常时放行。
    rules 传入时校验输入与配置一致（模型/单价/版本）；不传则按输入自身口径计算。
    """
    if rules is not None:
        if inputs.rate_per_km != rules.rate_str() or inputs.meal_per_valid_day != rules.meal_str():
            raise SelfDriveError(
                "输入单价与规则配置不一致（新旧行为分离）: 输入 rate={0} meal={1}；配置 rate={2} meal={3}"
                "；历史餐补值（12/18/24/36/48）不能作为新规则输入".format(
                    inputs.rate_per_km, inputs.meal_per_valid_day, rules.rate_str(), rules.meal_str()))
        if inputs.rule_version != rules.version:
            raise SelfDriveError("规则版本不一致: 输入 {0} 配置 {1}".format(inputs.rule_version, rules.version))

    rows = list(inputs.rows)
    toll_scope = list(inputs.toll_scope_ids)
    fuel_pool = list(inputs.fuel_pool_ids)
    overlap = sorted(set(toll_scope) & set(fuel_pool))
    if overlap:
        raise SelfDriveError("同一票据不得同时是通行范围与油票池: {0}".format(overlap))
    for inv in toll_scope + fuel_pool:
        if inv not in inputs.invoice_face_totals:
            raise SelfDriveError("票面缺失: {0}".format(inv))

    # 每张纳入通行费恰指向一行一次（与旧模型同一结构纪律）
    seen: dict[str, str] = {}
    for row in rows:
        for inv in row.toll_invoice_ids:
            if inv not in toll_scope:
                raise SelfDriveError("行 {0} 分到非范围票: {1}".format(row.row_id, inv))
            if inv in seen:
                raise SelfDriveError("票 {0} 重复分配: 行 {1} 与行 {2}".format(inv, seen[inv], row.row_id))
            if inv in fuel_pool:
                raise SelfDriveError("油票不得进入行分配: {0}".format(inv))
            seen[inv] = row.row_id
    unallocated = sorted(set(toll_scope) - set(seen))
    if unallocated:
        raise SelfDriveError("范围票未分配到任何行: {0}".format(unallocated))

    # 有效公出日：ISO 合法、按日去重（同日多事实/多单只计一次）
    day_seen: dict[str, str] = {}
    for day in inputs.meal_days:
        if not _DATE_RE.fullmatch(day.date):
            raise SelfDriveError("有效公出日必须为 ISO YYYY-MM-DD: {0!r}".format(day.date))
        if day.date in day_seen:
            raise SelfDriveError("有效公出日重复（同日多事实只计一次）: {0} 依据 {1} 与 {2}".format(
                day.date, day_seen[day.date] or "(无)", day.basis or "(无)"))
        day_seen[day.date] = day.basis

    K = sum((_dec(r.km, "行公里数 " + r.row_id) for r in rows), Decimal("0"))
    rate = _dec(inputs.rate_per_km, "rate_per_km")
    meal = _dec(inputs.meal_per_valid_day, "meal_per_valid_day")
    M = (K * rate).quantize(CENT)
    per_row_detail = []
    T = Decimal("0")
    for row in rows:
        row_toll = sum((_dec(inputs.invoice_face_totals[i], "票面 " + i) for i in row.toll_invoice_ids), Decimal("0"))
        T += row_toll
        per_row_detail.append({
            "row_id": row.row_id, "km": str(_dec(row.km, "行公里数 " + row.row_id)),
            "row_subsidy": str((_dec(row.km, "行公里数 " + row.row_id) * rate).quantize(CENT)),
            "toll_ids": list(row.toll_invoice_ids), "row_toll": str(row_toll.quantize(CENT)),
            "row_transport": str((_dec(row.km, "行公里数 " + row.row_id) * rate + row_toll).quantize(CENT))})
    T = T.quantize(CENT)
    C = (Decimal(len(day_seen)) * meal).quantize(CENT)
    R = (M + T + C).quantize(CENT)
    O = sum((_dec(inputs.invoice_face_totals[i], "票面 " + i) for i in fuel_pool), Decimal("0")).quantize(CENT)
    F = (O + T).quantize(CENT)
    margin = (F - R).quantize(CENT)
    strict_pass = F > R  # 严格大于；等于/小于均 False；Decimal 精确比较，无浮点容差
    return {
        "model": MODEL_NAME, "strict_gate": STRICT_GATE, "rule_source": inputs.rule_source,
        "rule_version": inputs.rule_version,
        "K_km": str(K), "rate_per_km": str(rate), "M_subsidy": str(M),
        "T_toll": str(T),
        "meal_days": sorted(day_seen), "meal_day_count": len(day_seen),
        "meal_per_valid_day": str(meal), "C_meal": str(C),
        "R_reimburse": str(R),
        "O_fuel_pool": str(O), "F_coverage_total": str(F),
        "coverage_margin": str(margin),
        "gate_passed": bool(strict_pass),
        "rows": per_row_detail,
        "invoice_allocation": seen,
        "notes": ["油票为覆盖凭据不入行分配：O 变化只影响 F/margin，不改变 R",
                  "C 仅计本次报销单制单人在本次范围内的已核实参与日，按日去重",
                  "汇总单仅作逐票交叉核对，不参与计费",
                  "历史餐补值（12/18/24/36/48）属旧单定位口径，不得进入本模型输入"],
    }


# ---------------------------------------------------------------- 对账 helpers（§6.1 反例）

def compare_by_key(expected: dict, declared: dict, what: str) -> list:
    """逐键对账（金额 Decimal）：返回逐项差异 [(key, expected, declared, diff)]。

    刻意不做『合计相等即通过』：两条金额差恰好正负抵消时合计差为 0，但本函数返回非空
    差异列表——抵消不放行；调用方以 len(diffs) > 0 判失败并逐项定位。
    只比较给出的键：不把其他行的错误派生值转嫁为未列出键的失败（正向对照保护——
    本身正确的关联不得因别处错误被误判）。
    """
    diffs = []
    for key in sorted(set(expected) | set(declared), key=str):
        if key not in expected:
            diffs.append((key, None, str(declared[key]), "+declared-only"))
            continue
        if key not in declared:
            diffs.append((key, str(expected[key]), None, "-missing"))
            continue
        exp, got = _dec(expected[key], "{0}[{1}] expected".format(what, key)), _dec(declared[key], "{0}[{1}] declared".format(what, key))
        if exp != got:
            diffs.append((key, str(exp), str(got), str((got - exp).quantize(CENT))))
    return diffs


def reconcile_date_labels(verified_days: tuple, declared_days: tuple) -> dict:
    """日期标签对账：已核实事实日 vs 单据/费用里声明的日期标签。

    返回 {'matched': [...], 'wrong_labels': [(declared, nearest_verified_or_None, note)],
          'unaccounted_verified': [...]}。错标形态（如同月日位笔误、结束日月位笔误）必须
    识别为 wrong_label（合同 §6.1 日期反例类），不能按错误标签生成费用/餐补日。
    declared 中的每个日期必须能在 verified 中找到同日事实；仅月份或日错位即 wrong_label。
    """
    verified = set()
    for day in verified_days:
        if not _DATE_RE.fullmatch(str(day)):
            raise SelfDriveError("verified 日期必须 ISO: {0!r}".format(day))
        verified.add(str(day))
    matched, wrong, declared_set = [], [], set()
    for day in declared_days:
        d = str(day)
        if not _DATE_RE.fullmatch(d):
            raise SelfDriveError("declared 日期必须 ISO: {0!r}".format(d))
        if d in declared_set:
            raise SelfDriveError("declared 日期重复: {0}".format(d))
        declared_set.add(d)
        if d in verified:
            matched.append(d)
        else:
            candidates = sorted(v for v in verified if v[5:7] == d[5:7] or v[8:] == d[8:])
            wrong.append((d, candidates[0] if len(candidates) == 1 else None,
                          "声明日期无同日已核实事实" + ("；疑似 {0} 误标".format(candidates[0]) if len(candidates) == 1 else "")))
    return {"matched": sorted(matched), "wrong_labels": wrong,
            "unaccounted_verified": sorted(verified - declared_set)}
