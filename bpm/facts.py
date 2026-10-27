"""W04 版本化业务事实层 + 程序化对账（先于任何业务写入）。

事实层：每条业务事实有稳定 ID、封闭来源枚举（原件提取/复核工件、准确模板、
用户明确指令、当前系统观察、确定性计算）、来源定位（文件/页/单元格）与可选推导；
发票分配/费用行引用事实 ID 而非复制值。版本化：事实记录所基工件哈希，材料换版本
后由 check_version_drift 识别受影响事实并标记需重新规划，不改写既有事实掩盖漂移。

对账：reconcile() 对事实集做去重分层、票据 Decimal 闭合、跨源一致、分层金额闭合、
收款身份组、边界拒绝与跨任务发票提示；阻断项带定位，不得任选一份当真。
agent 推断一律不得标注 user_instruction（沿用 agent_reviewed 语义，不伪装用户）。

上游消费 bpm_extraction / bpm_materials 产物，不改动其语义。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION_SCHEMA = "1.0"

# 来源封闭枚举（任务书五类；label 用于报告呈现）
FACT_SOURCES = (
    "material_extraction",       # 原件（提取/复核工件）
    "template",                  # 准确模板
    "user_instruction",          # 用户明确指令（仅真实用户输入，agent 推断禁用）
    "system_observation",        # 当前系统观察
    "deterministic_computation", # 确定性计算（必须给 derivation）
)
SOURCE_LABELS = {
    "material_extraction": "原件（提取/复核工件）",
    "template": "准确模板",
    "user_instruction": "用户明确指令",
    "system_observation": "当前系统观察",
    "deterministic_computation": "确定性计算",
}

FACT_KINDS = (
    "business_identity", "scope", "expense", "invoice", "invoice_allocation",
    "no_invoice_basis", "payee_group", "budget", "relation_archive",
    "applicability", "open_question", "total", "coverage_evaluation",
)  # coverage_evaluation: V3-R03 覆盖模型结果事实（deterministic_computation，见 bpm_coverage.py）

EXPENSE_LAYERS = ("detail", "summary")
RECON_STATUS = ("pass", "info", "block")

# 边界：未建模的业务形态在事实构造期即拒绝，不得改名绕过进入后续保存路径
_FORBIDDEN_EXPENSE_FIELDS = ("quantity", "unit_price")      # 未建模数量乘单价
_FORBIDDEN_VALUE_KEYS = ("loan_deduction", "借款抵扣")       # 未建模借款抵扣

_MONEY = Decimal("0.01")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dec(value):
    """金额一律 Decimal 且两位小数；非法值 ValueError 不静默。

    R3-P2a：超 2 位小数的输入显式 raise——静默 quantize（banker's rounding）
    会抹平真差额，金额语义歧义必须暴露而非取整。
    """
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("非法金额: {0!r}".format(value)) from exc
    if -number.as_tuple().exponent > 2:
        raise ValueError("金额超两位小数，语义歧义需显式处理: {0!r}".format(value))
    return number.quantize(_MONEY)


def _reject_forbidden_fields(value):
    if not isinstance(value, dict):
        return
    for key in _FORBIDDEN_VALUE_KEYS:
        if key in value:
            raise ValueError("未建模业务形态拒绝入库: {0}（明确报错，不改名绕过）".format(key))
    if all(name in value for name in _FORBIDDEN_EXPENSE_FIELDS):
        raise ValueError("未建模数量×单价计价拒绝入库（quantity×unit_price）")


def _validate_fact_invariants(kind, source, value, locator, derivation, input_hashes):
    """add() 与 from_payload() 共用的全套构造不变量（R4-P2b）：
    反序列化路径不得比构造路径宽松——手写 facts_payload 夹带的违例事实同样拒绝。"""
    if kind not in FACT_KINDS:
        raise ValueError("未知事实类别: {0}（封闭注册 {1}）".format(kind, FACT_KINDS))
    if source not in FACT_SOURCES:
        raise ValueError("未知来源: {0}（封闭枚举 {1}）".format(source, FACT_SOURCES))
    if not locator or not str(locator).strip():
        raise ValueError("事实必须带来源定位 locator（{0}）".format(kind))
    if source == "deterministic_computation" and not derivation:
        raise ValueError("确定性计算事实必须给 derivation（{0}）".format(kind))
    if source == "user_instruction" and input_hashes:
        raise ValueError("绑定派生工件的事实不得标 user_instruction（agent 推断禁伪装用户）")
    _reject_forbidden_fields(value)


@dataclass(frozen=True)
class Fact:
    """不可变事实记录：drift 检查只能标记，不能改写。"""
    fact_id: str
    kind: str
    source: str
    value: dict
    locator: str
    derivation: str = None
    input_hashes: dict = field(default_factory=dict)
    note: str = None
    created_at: str = None


class FactSet:
    """稳定 ID 事实集。ID 按构造顺序 F-0001 递增；引用 ID 而非复制值。"""

    def __init__(self, *, bindings=None, business_ref=None):
        self.bindings = dict(bindings or {})   # {binding_key: sha256} 所基工件版本
        self.business_ref = business_ref       # 本次业务标识（如任务/单号引用）
        self._facts = []
        self._index = {}

    # ------------------------------------------------------------ 构造
    def add(self, kind, *, source, value, locator, derivation=None,
            input_hashes=None, note=None):
        _validate_fact_invariants(kind, source, value, locator, derivation, input_hashes or {})
        fact_id = "F-{0:04d}".format(len(self._facts) + 1)
        fact = Fact(fact_id=fact_id, kind=kind, source=source,
                    value=dict(value or {}), locator=str(locator),
                    derivation=derivation, input_hashes=dict(input_hashes or {}),
                    note=note, created_at=_now())
        self._facts.append(fact)
        self._index[fact_id] = fact
        return fact_id

    # ------------------------------------------------------------ 读取
    def __iter__(self):
        return iter(self._facts)

    def __len__(self):
        return len(self._facts)

    def get(self, fact_id):
        fact = self._index.get(fact_id)
        if fact is None:
            raise KeyError("事实不存在: {0}".format(fact_id))
        return fact

    def by_kind(self, kind):
        return [f for f in self._facts if f.kind == kind]

    def to_payload(self):
        return {"schema_version": VERSION_SCHEMA, "business_ref": self.business_ref,
                "bindings": dict(self.bindings), "generated_at": _now(),
                "facts": [{"fact_id": f.fact_id, "kind": f.kind, "source": f.source,
                           "source_label": SOURCE_LABELS[f.source], "value": f.value,
                           "locator": f.locator, "derivation": f.derivation,
                           "input_hashes": dict(f.input_hashes), "note": f.note,
                           "created_at": f.created_at} for f in self._facts]}

    @classmethod
    def from_payload(cls, payload):
        """to_payload 对偶：反序列化保持 fact_id/created_at 原值（阶段衔接用）。

        仅接受本模块产出的载荷；字段集合不符即拒绝，不做宽容补全。
        R4-P2b：逐事实复跑 _validate_fact_invariants——反序列化与 add() 同一套
        构造不变量，手写 facts_payload 夹带的违例事实（未知类别/来源、空 locator、
        缺 derivation、user_instruction 携派生绑定、_FORBIDDEN 字段）同样拒绝。
        """
        if not isinstance(payload, dict) or payload.get("schema_version") != VERSION_SCHEMA \
                or not isinstance(payload.get("facts"), list):
            raise ValueError("非法 FactSet 载荷")
        factset = cls(bindings=payload.get("bindings"), business_ref=payload.get("business_ref"))
        expected = {"fact_id", "kind", "source", "value", "locator",
                    "derivation", "input_hashes", "note", "created_at"}
        for item in payload["facts"]:
            if not isinstance(item, dict) or expected - set(item):
                raise ValueError("事实载荷字段不全: {0!r}".format(item))
            _validate_fact_invariants(item["kind"], item["source"], item["value"],
                                      item["locator"], item.get("derivation"),
                                      item.get("input_hashes") or {})
            fact = Fact(fact_id=item["fact_id"], kind=item["kind"], source=item["source"],
                        value=dict(item["value"]), locator=str(item["locator"]),
                        derivation=item.get("derivation"),
                        input_hashes=dict(item.get("input_hashes") or {}),
                        note=item.get("note"), created_at=item.get("created_at"))
            if fact.fact_id in factset._index:
                raise ValueError("事实载荷 ID 重复: {0}".format(fact.fact_id))
            factset._facts.append(fact)
            factset._index[fact.fact_id] = fact
        factset._facts.sort(key=lambda f: f.fact_id)
        return factset

    # ------------------------------------------------------------ 业务构造器
    def add_invoice(self, number, face_total, *, source="material_extraction",
                    locator, input_hashes=None):
        """同票多扫按号码归并：第二次 add 同号不建新事实，合并扫描定位；
        票面不一致留给 reconcile 阻断（不在此静默取一）。"""
        for fact in self.by_kind("invoice"):
            if fact.value.get("number") == number:
                scans = fact.value.setdefault("scans", [{"locator": fact.locator,
                                                          "face_total": fact.value["face_total"]}])
                scans.append({"locator": str(locator), "face_total": str(_dec(face_total))})
                return fact.fact_id, False
        fact_id = self.add("invoice", source=source, locator=str(locator), input_hashes=input_hashes,
                           value={"number": number, "face_total": str(_dec(face_total)),
                                  "scans": [{"locator": str(locator),
                                             "face_total": str(_dec(face_total))}]})
        return fact_id, True

    def add_invoice_from_extraction(self, payload, *, locator_prefix):
        """从 W03 reviewed_extraction 载荷建票据事实（引用其 original_sha256 作版本绑定）。

        多 record 载荷（上游分件后一文件多票）逐 record 建票并按序返回
        [(fact_id, created), ...]——不再只读 records[0]，漏票由调用方按返回数量对账。
        """
        sha = payload.get("original_sha256")
        results = []
        for index, record in enumerate(payload["records"]):
            fields = record["fields"]
            missing = [name for name in ("invoice_number", "total_amount") if name not in fields]
            if missing:
                raise ValueError("提取载荷 record {0} 缺票据要素: {1}".format(
                    record.get("record_id", index), missing))
            fact_id, created = self.add_invoice(
                fields["invoice_number"]["value"], fields["total_amount"]["value"],
                source="material_extraction",
                locator="{0}#{1}".format(locator_prefix, fields["total_amount"]["locator"]),
                input_hashes={"extraction:" + (sha or "unknown"): sha or "unknown"})
            results.append((fact_id, created))
        return results

    def add_expense(self, amount, *, source="material_extraction", locator,
                    category=None, date=None, layer="detail",
                    input_hashes=None, note=None, value_extra=None):
        if layer not in EXPENSE_LAYERS:
            raise ValueError("未知费用层: {0}（{1}）".format(layer, EXPENSE_LAYERS))
        value = {"amount": str(_dec(amount)), "layer": layer}
        if category is not None:
            value["category"] = category
        if date is not None:
            value["date"] = str(date)
        if value_extra:
            value.update(value_extra)
        return self.add("expense", source=source, value=value, locator=str(locator),
                        input_hashes=input_hashes, note=note)

    def add_allocation(self, invoice_id, expense_id, amount, *, locator,
                       source="material_extraction", input_hashes=None, derivation=None):
        """分配引用事实 ID（invoice_ref/expense_ref），不复制票号/金额。"""
        invoice, expense = self.get(invoice_id), self.get(expense_id)
        if invoice.kind != "invoice":
            raise ValueError("invoice_ref 不是票据事实: {0}({1})".format(invoice_id, invoice.kind))
        if expense.kind != "expense":
            raise ValueError("expense_ref 不是费用事实: {0}({1})".format(expense_id, expense.kind))
        return self.add("invoice_allocation", source=source, locator=str(locator),
                        input_hashes=input_hashes, derivation=derivation,
                        value={"invoice_ref": invoice_id, "expense_ref": expense_id,
                               "amount": str(_dec(amount))})

    def add_no_invoice_basis(self, expense_id, *, reason, source, locator, input_hashes=None):
        if not reason or not str(reason).strip():
            raise ValueError("免票依据必须给非空理由（免票无理由阻断）")
        self.get(expense_id)
        return self.add("no_invoice_basis", source=source, locator=str(locator),
                        input_hashes=input_hashes,
                        value={"expense_ref": expense_id, "reason": str(reason)})

    def add_payee(self, *, name, account, branch, interbank, amount=None,
                  source="material_extraction", locator, input_hashes=None):
        """收款身份按完整组登记；残缺字段记入 missing，由 reconcile 阻断而非补猜。"""
        group = {"name": name, "account": account, "branch": branch, "interbank": interbank}
        missing = [key for key, val in group.items() if val in (None, "")]
        if missing:
            group["missing"] = missing
        if amount is not None:
            group["amount"] = str(_dec(amount))
        return self.add("payee_group", source=source, value=group,
                        locator=str(locator), input_hashes=input_hashes)


# ------------------------------------------------------------ 版本漂移
def check_version_drift(factset, current_bindings):
    """比对事实绑定哈希与当前工件哈希；只标记需重新规划，不改写既有事实。

    binding key 缺失（工件消失）同样视为受影响。
    """
    current = dict(current_bindings or {})
    affected = []
    for fact in factset:
        changed = [key for key in fact.input_hashes
                   if key not in current or current[key] != fact.input_hashes[key]]
        if changed:
            affected.append({"fact_id": fact.fact_id, "kind": fact.kind,
                             "changed_keys": sorted(changed),
                             "recorded": {k: fact.input_hashes[k] for k in changed},
                             "current": {k: current.get(k) for k in changed}})
    return {"schema_version": VERSION_SCHEMA, "needs_replan": bool(affected),
            "affected": affected, "checked_at": _now()}


# ------------------------------------------------------------ 对账
@dataclass
class Check:
    name: str
    status: str
    details: list = field(default_factory=list)

    def to_payload(self):
        return {"name": self.name, "status": self.status, "details": self.details}


class ReconciliationReport:
    def __init__(self):
        self.checks = []
        self.hints = []
        self.notes = []

    def add(self, name, status, details=None):
        if status not in RECON_STATUS:
            raise ValueError("未知对账状态: {0}".format(status))
        self.checks.append(Check(name, status, list(details or [])))
        return self.checks[-1]

    @property
    def blocked(self):
        return any(c.status == "block" for c in self.checks)

    def block_names(self):
        return [c.name for c in self.checks if c.status == "block"]

    def to_payload(self):
        return {"schema_version": VERSION_SCHEMA, "blocked": self.blocked,
                "checks": [c.to_payload() for c in self.checks],
                "hints": self.hints, "notes": self.notes, "generated_at": _now()}


def scan_task_registry(registry_dir, invoice_numbers):
    """只读扫描 task-registry *.form.json：发票号命中 authorized_revision*.numbers
    或全文 → 提示项（不阻断、不写 registry）。目录缺失/不可读降级为无提示。"""
    hints, notes = [], []
    numbers = set(invoice_numbers or [])
    if not numbers:
        return hints, notes
    if not registry_dir:
        notes.append("registry_dir 未提供，跨任务发票提示未执行")
        return hints, notes
    root = Path(registry_dir)
    if not root.is_dir():
        notes.append("registry 目录不存在，跨任务发票提示降级为空: {0}".format(root))
        return hints, notes
    for path in sorted(root.glob("*.form.json")):
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError) as exc:
            notes.append("registry 文件不可读，跳过: {0}({1})".format(path.name, exc))
            continue
        for number in sorted(numbers):
            hit = None
            for revision in data.values() if isinstance(data, dict) else []:
                if not isinstance(revision, dict):
                    continue
                listed = revision.get("numbers")
                if isinstance(listed, list) and number in [str(v) for v in listed]:
                    hit = "authorized_revision*.numbers"
                    break
            if hit is None and number in text:
                hit = "text"
            if hit:
                hints.append({"invoice_number": number, "task_id": data.get("task_id"),
                              "registry_file": path.name, "evidence": hit})
    return hints, notes


def reconcile(factset, *, pending_materials=None, registry_dir=None):
    """程序化对账（先于任何业务写入）。阻断项带定位；任一 block 即整体阻断。"""
    report = ReconciliationReport()
    expenses = [f for f in factset.by_kind("expense")]
    detail = [f for f in expenses if f.value["layer"] == "detail"]
    summary = [f for f in expenses if f.value["layer"] == "summary"]
    invoices = factset.by_kind("invoice")
    allocations = factset.by_kind("invoice_allocation")
    bases = factset.by_kind("no_invoice_basis")
    payees = factset.by_kind("payee_group")
    totals = factset.by_kind("total")

    # 1. 同票多扫票面一致（不一致=跨源冲突，不得任选一份当真）
    details = []
    for inv in invoices:
        faces = {scan["face_total"] for scan in inv.value.get("scans", [])}
        if len(faces) > 1:
            details.append({"fact_id": inv.fact_id, "number": inv.value["number"],
                            "faces": sorted(faces),
                            "locators": [s["locator"] for s in inv.value.get("scans", [])],
                            "problem": "同一发票不同扫描件票面金额不一致"})
    report.add("invoice_face_consistency",
               "block" if details else "pass",
               details if details else [{"invoices": len(invoices)}])

    # 2. 票据闭合：每票分配和==票面（Decimal）；残额即部分票面，未建模拒绝
    details = []
    for inv in invoices:
        allocs = [a for a in allocations if a.value["invoice_ref"] == inv.fact_id]
        allocated = sum((Decimal(a.value["amount"]) for a in allocs), Decimal("0"))
        face = Decimal(inv.value["face_total"])
        if allocated != face:
            details.append({"fact_id": inv.fact_id, "number": inv.value["number"],
                            "face": inv.value["face_total"], "allocated": str(allocated),
                            "locators": [inv.locator] + [a.locator for a in allocs],
                            "problem": "部分票面/超分配（票面≠分配，未建模拒绝）"})
    report.add("invoice_allocation_closure",
               "block" if details else "pass",
               details if details else [{"invoices": len(invoices),
                                         "allocations": len(allocations)}])

    # 3. 费用行覆盖：主要费用行完整分配或有免票依据；超分配阻断
    details = []
    base_by_expense = {b.value["expense_ref"] for b in bases}
    for exp in detail:
        allocs = [a for a in allocations if a.value["expense_ref"] == exp.fact_id]
        covered = sum((Decimal(a.value["amount"]) for a in allocs), Decimal("0"))
        amount = Decimal(exp.value["amount"])
        if not allocs and exp.fact_id not in base_by_expense:
            details.append({"fact_id": exp.fact_id, "amount": exp.value["amount"],
                            "locator": exp.locator,
                            "problem": "费用行无分配且无免票依据（未覆盖）"})
        elif allocs and covered != amount:
            details.append({"fact_id": exp.fact_id, "amount": exp.value["amount"],
                            "covered": str(covered), "locator": exp.locator,
                            "locators": [a.locator for a in allocs],
                            "problem": "分配与费用行金额不闭合（Excel vs 票面冲突/超分配）"})
    for basis in bases:
        if not str(basis.value.get("reason", "")).strip():
            details.append({"fact_id": basis.fact_id, "locator": basis.locator,
                            "problem": "免票依据缺理由"})
    report.add("expense_allocation_coverage",
               "block" if details else "pass",
               details if details else [{"detail_expenses": len(detail),
                                         "no_invoice_bases": len(bases)}])

    # 4. 汇总层与明细层一致（结算明细 vs 合计；重复计入在此拦截，不层层相加）
    detail_sum = sum((Decimal(e.value["amount"]) for e in detail), Decimal("0"))
    summary_sum = sum((Decimal(e.value["amount"]) for e in summary), Decimal("0"))
    if summary:
        if summary_sum != detail_sum:
            report.add("summary_detail_consistency", "block", [
                {"detail_sum": str(detail_sum), "summary_sum": str(summary_sum),
                 "detail_locators": [e.locator for e in detail],
                 "summary_locators": [e.locator for e in summary],
                 "problem": "汇总层与明细层不闭合（不得任选一份当真）"}])
        else:
            report.add("summary_detail_consistency", "pass",
                       [{"detail_sum": str(detail_sum), "summary_sum": str(summary_sum)}])
    else:
        report.add("summary_detail_consistency", "pass", [{"summary_layer": "absent"}])

    # 5. 总额分层闭合：总额==明细合计==收款合计；跨层相加（明细+汇总）不接受
    bank_sum = sum((Decimal(p.value["amount"]) for p in payees if "amount" in p.value),
                   Decimal("0"))
    problems = []
    for total in totals:
        if "amount" not in total.value:
            problems.append({"fact_id": total.fact_id, "locator": total.locator,
                             "problem": "总额事实缺 amount"})
            continue
        declared = Decimal(total.value["amount"])
        expected = [detail_sum] + ([bank_sum] if bank_sum else [])
        if any(declared != value for value in expected):
            problems.append({"fact_id": total.fact_id, "declared": str(declared),
                             "detail_sum": str(detail_sum), "bank_sum": str(bank_sum),
                             "locator": total.locator,
                             "problem": "总额与明细/收款层不闭合（跨层相加重复计费不接受）"})
    if not totals:
        problems.append({"problem": "缺报销总额事实（total）"})
    report.add("total_closure", "block" if problems else "pass",
               problems if problems else [{"total": str(detail_sum),
                                           "bank_sum": str(bank_sum)}])

    # 6. 适用费用说明/档案金额：按类别分组对明细闭合
    applicability = factset.by_kind("applicability")
    details6 = []
    by_category = {}
    for exp in detail:
        category = exp.value.get("category")
        by_category[category] = by_category.get(category, Decimal("0")) + Decimal(exp.value["amount"])
    for app in applicability:
        category = app.value.get("category")
        if "amount" not in app.value:
            details6.append({"fact_id": app.fact_id, "locator": app.locator,
                             "problem": "适用说明事实缺 amount"})
            continue
        declared = Decimal(app.value["amount"])
        actual = by_category.get(category, Decimal("0"))
        if declared != actual:
            details6.append({"fact_id": app.fact_id, "category": category,
                             "declared": str(declared), "actual": str(actual),
                             "locator": app.locator,
                             "problem": "适用说明金额与该类别明细合计不闭合"})
    report.add("applicability_closure", "block" if details6 else "pass",
               details6 if details6 else [{"applicability_facts": len(applicability),
                                           "categories": {k: str(v) for k, v in by_category.items()}}])

    # 7. 费用说明 vs 报销范围：费用类别须落在范围内
    scopes = factset.by_kind("scope")
    details7 = []
    for scope in scopes:
        allowed = scope.value.get("categories")
        if not isinstance(allowed, list):
            continue
        for exp in detail:
            if exp.value.get("category") not in allowed:
                details7.append({"fact_id": exp.fact_id,
                                 "category": exp.value.get("category"),
                                 "scope_fact": scope.fact_id, "scope_locator": scope.locator,
                                 "expense_locator": exp.locator,
                                 "problem": "费用类别超出报销范围"})
    report.add("scope_consistency", "block" if details7 else "pass",
               details7 if details7 else [{"scope_facts": len(scopes)}])

    # 8. 收款身份组：字段残缺或来源冲突阻断（同名不同账号=冲突）
    details8 = []
    for payee in payees:
        if payee.value.get("missing"):
            details8.append({"fact_id": payee.fact_id, "missing": payee.value["missing"],
                             "locator": payee.locator, "problem": "收款身份组字段残缺"})
    seen = {}
    by_account = {}
    for payee in payees:
        name = payee.value.get("name")
        if not name:
            continue
        if name in seen:
            for key in ("account", "branch", "interbank"):
                if payee.value.get(key) != seen[name].value.get(key):
                    details8.append({"payees": [seen[name].fact_id, payee.fact_id],
                                     "locators": [seen[name].locator, payee.locator],
                                     "field": key,
                                     "problem": "同名收款人身份组跨源冲突"})
        else:
            seen[name] = payee
        # R3-P2b：第三种身份组冲突——同账号不同户名
        account = payee.value.get("account")
        if account:
            if account in by_account and by_account[account].value.get("name") != name:
                details8.append({"payees": [by_account[account].fact_id, payee.fact_id],
                                 "locators": [by_account[account].locator, payee.locator],
                                 "field": "name",
                                 "problem": "同账号不同户名，收款身份组冲突"})
            elif account not in by_account:
                by_account[account] = payee
    if not payees:
        report.add("payee_identity", "pass", [{"payees": 0,
                                               "note": "收款身份组缺位（候选未建或未提供），不视为冲突"}])
    else:
        report.add("payee_identity", "block" if details8 else "pass",
                   details8 if details8 else [{"payees": len(payees)}])

    # 9. 边界：未知业务表/未处置材料不得进入后续保存路径
    pending = list(pending_materials or [])
    report.add("boundary_unknown_materials",
               "block" if pending else "pass",
               [{"item": item, "problem": "未知业务表/待定材料未处置（明确报错，不改名绕过）"}
                for item in pending] or [{"pending_materials": 0}])

    # 10. 同金额不禁报：同额费用合法存在（显式 pass，防误加禁报）
    amounts = [e.value["amount"] for e in detail]
    dup = sorted({a for a in amounts if amounts.count(a) > 1})
    report.add("same_amount_not_forbidden", "pass",
               [{"duplicated_amounts": dup, "note": "同金额本身不禁报，闭合与依据另行核对"}])

    # 11. 跨任务发票提示（只读 registry；提示级，永不阻断）
    numbers = [inv.value["number"] for inv in invoices]
    hints, notes = scan_task_registry(registry_dir, numbers)
    report.hints.extend(hints)
    report.notes.extend(notes)
    report.add("cross_task_invoice_hints", "info",
               [{"hint": h} for h in hints] or [{"hints": 0}])

    return report
