"""W05a 事实→计划生成器：对账通过的事实自动生成 v1.0 fill-plan。

前置门（先于任何计划产出）：
1. reconcile(factset) blocked → 拒绝（阻断项即业务缺口，不是生成器输入）；
2. 材料漂移：blueprint.current_bindings 交 check_version_drift，且每个用到的
   事实工件现场重算 sha256 与 input_hashes 交叉核验，漂移即拒绝（needs_replan）。

来源绑定：每个计划标量的 source 由事实推导——locator 统一 ``file#inner`` 坐标
（xlsx ``Sheet!A1`` / JSON 指针 / CSV ``row:N/column:N``），artifact 实测哈希；
fact.source → 计划 source kind 映射（material_extraction 按工件在 originals/derived
分为 material/agent_reviewed；template→template；user_instruction→user；
deterministic_computation→derived sum；system_observation v1 显式拒绝）。
无源值、值≠事实金额、工件不在 manifest 等一律拒绝——生成器不产无源计划。

产出计划当场过 bpm_plan.validate_plan(verify_sources=True)；校验失败即生成器
缺陷（PlanGenerationError 携带 issues），不放宽、不绕过。
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from bpm.facts import check_version_drift, reconcile
from bpm.plan import load_type, money, validate_plan

GENERATOR_SCHEMA = "1.0"

PREPARATION_STAGES = ("MATERIALS_READY", "FACTS_BUILT", "RECONCILED", "PLAN_READY", "NEEDS_INPUT")


class PlanGenerationError(ValueError):
    """生成器缺陷或前置门阻断；issues/details 字段携带结构化原因。"""

    def __init__(self, message, *, issues=None, details=None):
        super().__init__(message)
        self.issues = list(issues or [])
        self.details = list(details or [])


def _file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _split_locator(locator):
    """`file#inner` → (file, inner)；无 # 视为整文件（inner="" 仅 json 指针根）。"""
    text = str(locator)
    if "#" not in text:
        raise PlanGenerationError("事实 locator 缺少 file#inner 坐标: {0!r}".format(locator))
    name, inner = text.split("#", 1)
    if not name.strip() or not inner.strip():
        raise PlanGenerationError("事实 locator 坐标不完整: {0!r}".format(locator))
    return name, inner


class _Artifacts:
    """manifest 原件+派生工件的 sha→(path, role) 索引（路径按 base_dir 解析）。"""

    def __init__(self, manifest, base_dir):
        self.base = Path(base_dir)
        self.manifest = manifest or {}
        self.originals, self.derived = {}, {}
        for item in self.manifest.get("files", []):
            self.originals[item["sha256"]] = self._resolve(item["path"])
        for item in self.manifest.get("derived_files", []):
            self.derived[item["sha256"]] = (self._resolve(item["path"]), item.get("role"))

    def _resolve(self, path):
        target = Path(path)
        return target if target.is_absolute() else (self.base / target).resolve()

    def role_of(self, path):
        sha = _file_hash(path)
        if sha in self.originals:
            return "material", sha
        if sha in self.derived:
            return "agent_reviewed", sha
        return None, sha


def _primary_table(plan, config):
    """与 validate_image_documents 同口径：显式 primary_expense_table，否则 costs 求和时为 costs。"""
    if config.get("primary_expense_table"):
        return config["primary_expense_table"]
    rules = plan.get("amount_rules", {})
    if rules.get("costs") == "sum" and plan.get("tables", {}).get("costs"):
        return "costs"
    return "details"


def _field_spec(config, table, column):
    return config["tables"][table]["columns"].get(column, {})


def _source_for_fact(fact, artifacts, template, *, override_inner=None, base_dir=None):
    """由事实构造计划 source（kind/path/locator/sha256)；无源或不符即拒绝。"""
    name, inner = _split_locator(fact.locator)
    if override_inner:
        override = str(override_inner)
        if "#" in override:   # 允许全坐标：拆出 inner 并拒绝跨文件偷换
            override_name, override = override.split("#", 1)
            if Path(override_name).name != Path(name).name:
                raise PlanGenerationError(
                    "覆盖定位与事实工件不一致: {0} vs {1}".format(override_name, name))
        if not override.strip():
            raise PlanGenerationError("覆盖定位为空: {0}".format(fact.fact_id))
        inner = override
    path = (Path(base_dir) / name)
    if not path.is_file():
        raise PlanGenerationError("事实工件不存在: {0} (事实 {1})".format(name, fact.fact_id))
    sha = _file_hash(path)
    if fact.input_hashes and sha not in fact.input_hashes.values():
        raise PlanGenerationError(
            "事实工件哈希与绑定不符（材料漂移，需重新规划）: {0} 事实 {1}".format(name, fact.fact_id))
    kind = None
    if fact.source == "material_extraction":
        role, _ = artifacts.role_of(path)
        if role is None:
            raise PlanGenerationError(
                "material_extraction 工件不在材料 manifest（originals/derived 均无）: {0}".format(name))
        kind = role
    elif fact.source == "template":
        if sha != template.get("sha256"):
            raise PlanGenerationError("template 事实工件与计划模板快照哈希不一致: {0}".format(name))
        kind = "template"
    elif fact.source == "user_instruction":
        if sha in artifacts.derived:
            raise PlanGenerationError("user_instruction 事实不得绑定派生工件: {0}".format(fact.fact_id))
        kind = "user"
        # P2-2（round-10 ctr-8cb7b247 §3 折入）：kind=user 严格对应用户真实供料。
        # 绑定工件自带 synthetic=true（离线合成材料）时降级 kind=material——合成链的
        # 免票依据/空表理由不得在计划 source 里冒充用户供料；授权回放件（test_only/
        # demo_only+lineage，用户真实供料）不含 synthetic，维持原语义。
        try:
            bound = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            bound = None
        if isinstance(bound, dict) and bound.get("synthetic") is True:
            kind = "material"
    elif fact.source == "deterministic_computation":
        kind = "derived"   # operation/inputs 由调用处补充
    elif fact.source == "system_observation":
        # W06+（2026-10-24）：系统观察事实必须指向本 manifest 派生根内 agent 登记的
        # 观察工件（role=run_evidence 等真实页面观测留证，含原观测 run 溯源），映射
        # kind=agent_reviewed；原件或未登记工件一律拒绝——不给无观察证明的值放行。
        if sha not in artifacts.derived:
            raise PlanGenerationError(
                "system_observation 事实必须绑定派生根内 agent 登记的观察工件（真实系统观察证明）: {0}".format(fact.fact_id))
        kind = "agent_reviewed"
    return {"kind": kind, "path": str(path), "locator": inner, "sha256": sha}, sha


def generate_fill_plan(factset, blueprint, *, base_dir, registry_dir=None):
    """从对账通过的事实生成 v1.0 fill-plan；返回 plan+fact_bindings+对账报告。"""
    if not isinstance(blueprint, dict):
        raise PlanGenerationError("blueprint 必须是对象")
    base = Path(base_dir)

    # ---- 前置门 1：对账通过
    report = reconcile(factset, pending_materials=blueprint.get("pending_materials"),
                       registry_dir=registry_dir or blueprint.get("registry_dir"))
    if report.blocked:
        raise PlanGenerationError(
            "对账未通过，禁止生成计划: " + ",".join(report.block_names()),
            details=[detail for check in report.checks if check.status == "block" for detail in check.details])

    # ---- 前置门 2：无材料漂移
    current = blueprint.get("current_bindings")
    if current is not None:
        drift = check_version_drift(factset, current)
        if drift["needs_replan"]:
            raise PlanGenerationError("材料版本漂移，需重新规划", details=drift["affected"])

    # ---- 前置门 3（R4-P2c）：被绑定事实必须有版本绑定哈希。
    # material_extraction/template 事实 input_hashes 为空时，逐工件哈希核验无从进行
    # （current_bindings 缺失也拦不住）——按最高风险拒绝，不静默放行，也不由生成器
    # 代事实补绑定（补绑定=生成器替事实主张来源）。
    bound_fact_ids = set()
    for section in ("applicant", "header", "identity"):
        for entry in blueprint.get(section, {}).values():
            bound_fact_ids.add(entry["fact_id"])
    for rows in blueprint.get("tables", {}).values():
        for row in rows:
            for entry in row["fields"].values():
                bound_fact_ids.add(entry["fact_id"])
    if blueprint.get("total"):
        bound_fact_ids.add(blueprint["total"]["fact_id"])
    for entry in blueprint.get("table_applicability", {}).values():
        bound_fact_ids.add(entry["fact_id"])
    for fact_id in sorted(bound_fact_ids):
        fact = factset.get(fact_id)
        if fact.source in ("material_extraction", "template") and not fact.input_hashes:
            raise PlanGenerationError(
                "被绑定 {0} 事实缺版本绑定 input_hashes（漂移门无法核验，按最高风险拒绝）: {1}".format(
                    fact.source, fact.fact_id))

    document_type = blueprint["document_type"]
    config = load_type(document_type)
    template = blueprint["template"]
    materials_path = Path(blueprint["materials"]["manifest_path"])
    if not materials_path.is_absolute():
        materials_path = (base / materials_path).resolve()
    manifest = json.loads(materials_path.read_text(encoding="utf-8"))
    artifacts = _Artifacts(manifest, base)

    plan = {"schema_version": "1.0", "task_id": blueprint["task_id"],
            "document_type": document_type, "config_version": config["config_version"],
            "operator": blueprint["operator"], "applicant": {}, "template": dict(template),
            "materials": {"manifest_path": str(materials_path),
                          "manifest_sha256": _file_hash(materials_path)},
            "header": {}, "tables": {}, "sources": {},
            "authorization": dict(blueprint["authorization"]),
            "unresolved": [], "not_applicable": list(blueprint.get("not_applicable", [])),
            "amount_rules": dict(blueprint["amount_rules"])}
    if "identity" in blueprint:
        plan["identity"] = dict(blueprint["identity"])
    fact_bindings = {}

    def bind(pointer, entry, *, expect_money=False, derived_inputs=None):
        """把 {value, fact_id, locator?, inputs?} 绑定成计划值+来源。"""
        fact = factset.get(entry["fact_id"])
        value = entry["value"]
        if expect_money:
            # R4-P2b：金额事实必须有 amount 键才可比对——缺键时 .get(amount, value)
            # 会退化成自比恒真，等于没有金额门。
            if "amount" not in fact.value:
                raise PlanGenerationError(
                    "金额字段绑定的事实缺 amount 键，无法核对计划金额: {0} ({1})".format(
                        pointer, fact.fact_id))
            if money(value) != money(fact.value["amount"]):
                raise PlanGenerationError(
                    "计划金额与事实金额不一致: {0} {1} vs 事实 {2} ({3})".format(
                        pointer, value, fact.value["amount"], fact.fact_id))
        if fact.source == "deterministic_computation":
            inputs = derived_inputs or entry.get("inputs")
            if not inputs:
                raise PlanGenerationError("derived 事实缺 inputs 指针: {0}".format(pointer))
            total = sum((money(pointer_get_value(plan, item)) for item in inputs), Decimal("0"))
            if money(value) != total:
                raise PlanGenerationError(
                    "derived 合计不闭合: {0} {1} vs {2}".format(pointer, value, total))
            plan["sources"][pointer] = {"kind": "derived", "operation": "sum", "inputs": list(inputs)}
            fact_bindings[pointer] = {"fact_id": fact.fact_id, "fact_source": fact.source}
            return value
        source, sha = _source_for_fact(fact, artifacts, template,
                                       override_inner=entry.get("locator"), base_dir=base)
        plan["sources"][pointer] = source
        fact_bindings[pointer] = {"fact_id": fact.fact_id, "fact_source": fact.source,
                                  "artifact_sha256": sha}
        return value

    def pointer_get_value(current_plan, pointer):
        node = current_plan
        for part in pointer.strip("/").split("/"):
            node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    # ---- identity（可选：申请人工号+制单人身份；与 applicant 同样必须有源绑定）
    if blueprint.get("identity"):
        plan["identity"] = {}
        for key, entry in blueprint["identity"].items():
            plan["identity"][key] = bind("/identity/" + key, entry)

    # ---- applicant（身份三字段必须有源）
    for key, entry in blueprint["applicant"].items():
        plan["applicant"][key] = bind("/applicant/" + key, entry)

    # ---- header（totalCost 由 derived 合计绑定）
    for key, entry in blueprint["header"].items():
        plan["header"][key] = bind("/header/" + key, entry)

    # ---- tables
    expense_pointer_by_fact = {}
    for table, rows in blueprint["tables"].items():
        plan["tables"][table] = []
        columns = config["tables"][table]["columns"]
        for index, row in enumerate(rows):
            fields = {}
            for column, entry in row["fields"].items():
                spec = _field_spec(config, table, column)
                is_money = spec.get("type") == "money"
                pointer = "/tables/{0}/{1}/fields/{2}".format(table, index, column)
                fields[column] = bind(pointer, entry, expect_money=is_money,
                                      derived_inputs=entry.get("inputs"))
                if is_money and factset.get(entry["fact_id"]).kind == "expense":
                    fact_id = entry["fact_id"]
                    expense_pointer_by_fact.setdefault(fact_id, []).append(pointer)
            plan["tables"][table].append({"row_id": row["row_id"], "fields": fields})

    # ---- totalCost：derived sum（明细行金额指针）
    total_entry = blueprint["total"]
    total_fact = factset.get(total_entry["fact_id"])
    detail_inputs = ["/tables/details/{0}/fields/cost".format(i)
                     for i in range(len(plan["tables"]["details"]))]
    plan["header"]["totalCost"] = bind("/header/totalCost",
                                       {"value": total_entry["value"],
                                        "fact_id": total_entry["fact_id"]},
                                       derived_inputs=detail_inputs)
    if money(plan["header"]["totalCost"]) != money(total_fact.value["amount"]):
        raise PlanGenerationError("totalCost 与总额事实不一致")

    # ---- table_applicability（非 travel 空表的有源理由）
    if document_type != "travel":
        applicability = {}
        for table, entry in blueprint.get("table_applicability", {}).items():
            pointer = "/table_applicability/{0}/reason".format(table)
            applicability[table] = {"reason": bind(pointer, entry)}
        if applicability:
            plan["table_applicability"] = applicability

    # ---- 发票→image_documents（票面事实+分配→record 闭合）
    allocations_by_invoice = {}
    for allocation in factset.by_kind("invoice_allocation"):
        allocations_by_invoice.setdefault(allocation.value["invoice_ref"], []).append(allocation)
    documents_by_path = {}  # extraction_path -> image_document（一份原件一条，多 record 并入）
    payload_cache = {}     # extraction_path -> payload（多 record 漏票检测复用）
    consumed_records = {}  # extraction_path -> {record_id: invoice_number}
    for wiring in blueprint.get("invoice_extractions", []):
        invoice = factset.get(wiring["invoice_fact_id"])
        if invoice.kind != "invoice":
            raise PlanGenerationError("invoice_extractions 绑定的不是票据事实: {0}".format(invoice.fact_id))
        extraction_path = Path(wiring["extraction_path"])
        if not extraction_path.is_absolute():
            extraction_path = (base / extraction_path).resolve()
        payload = payload_cache.get(str(extraction_path))
        if payload is None:
            payload = json.loads(extraction_path.read_text(encoding="utf-8"))
            payload_cache[str(extraction_path)] = payload
        number, face = invoice.value["number"], money(invoice.value["face_total"])
        # 多 record 载荷逐 record 匹配票号（唯一命中），不再只读第一票
        matched = [r for r in payload["records"]
                   if r["fields"].get("invoice_number", {}).get("value") == number]
        if not matched:
            raise PlanGenerationError("reviewed 提取不含该票据事实的票号: {0}".format(number))
        if len(matched) > 1:
            raise PlanGenerationError("reviewed 提取票号重复出现，无法唯一匹配: {0}".format(number))
        record = matched[0]
        used = consumed_records.setdefault(str(extraction_path), {})
        if record["record_id"] in used:
            raise PlanGenerationError(
                "reviewed 提取 record 被重复消费: {0}#{1}（已绑 {2}）".format(
                    extraction_path.name, record["record_id"], used[record["record_id"]]))
        used[record["record_id"]] = number
        fields = record["fields"]
        if fields.get("invoice_number", {}).get("value") != number:
            raise PlanGenerationError("reviewed 提取票号与票据事实不一致: {0}".format(number))
        amount_values = [fields[key]["value"] for key in ("amount", "total_amount") if key in fields]
        if not amount_values or any(money(v) != face for v in amount_values):
            raise PlanGenerationError("reviewed 提取金额与票面事实不一致: {0}".format(number))
        if payload.get("original_sha256") not in invoice.input_hashes.values():
            raise PlanGenerationError("reviewed 提取未绑定该票据事实的原件哈希: {0}".format(number))
        primary = _primary_table(plan, config)
        allocations = []
        for allocation in allocations_by_invoice.get(invoice.fact_id, []):
            pointers = [item for item in expense_pointer_by_fact.get(allocation.value["expense_ref"], [])
                        if item.startswith("/tables/{0}/".format(primary))]
            if not pointers:
                raise PlanGenerationError(
                    "分配指向的费用事实未映射到主表 {0} 行: {1}".format(primary, allocation.value["expense_ref"]))
            allocations.append({"plan_pointer": pointers[0],
                                "amount": allocation.value["amount"]})
        if not allocations:
            raise PlanGenerationError("票据事实缺分配: {0}".format(number))
        assigned = sum((money(item["amount"]) for item in allocations), Decimal("0"))
        if assigned != face:
            raise PlanGenerationError("生成器分配合计与票面不闭合: {0}".format(number))
        # 计划契约：同一原件（载荷）只分类一次——多条布线并入同一文档的 records
        doc = documents_by_path.get(str(extraction_path))
        if doc is None:
            doc = {"original_sha256": payload["original_sha256"], "kind": "invoice",
                   "extraction_path": str(extraction_path),
                   "extraction_sha256": _file_hash(extraction_path), "records": []}
            documents_by_path[str(extraction_path)] = doc
        doc["records"].append({"record_id": record["record_id"], "allocations": allocations})
    # 漏票检测：多 record 载荷中每个 record 都须被某条布线消费——
    # 上游分件成功后下游不得静默丢弃未在首位的票据。
    for path_str, used in consumed_records.items():
        leftovers = [r["record_id"] for r in payload_cache[path_str]["records"]
                     if r["record_id"] not in used]
        if leftovers:
            raise PlanGenerationError(
                "invoice_extractions 漏票: {0} 中 record {1} 未绑定任何票据事实".format(
                    Path(path_str).name, leftovers))
    documents = list(documents_by_path.values())
    if documents:
        plan["materials"]["image_documents"] = documents

    # ---- 免票依据→no_invoice_rows（有源理由；指向主表未分配行）
    primary = _primary_table(plan, config)
    no_invoice_rows = []
    for basis in factset.by_kind("no_invoice_basis"):
        candidates = [item for item in expense_pointer_by_fact.get(basis.value["expense_ref"], [])
                      if item.startswith("/tables/{0}/".format(primary))]
        expense_pointer = candidates[0] if candidates else None
        if not expense_pointer:
            raise PlanGenerationError("免票依据指向的费用事实未映射到计划行: {0}".format(basis.fact_id))
        source, sha = _source_for_fact(basis, artifacts, template, base_dir=base)
        no_invoice_rows.append({"plan_pointer": expense_pointer,
                                "reason": basis.value["reason"],
                                "proof": {"kind": source["kind"], "path": source["path"],
                                          "locator": source["locator"], "sha256": source["sha256"]}})
    if no_invoice_rows:
        plan["materials"]["no_invoice_rows"] = no_invoice_rows

    # ---- 正式校验（不通过即生成器缺陷）
    issues = validate_plan(plan, verify_sources=True, base_dir=base)
    if issues:
        raise PlanGenerationError("生成计划未过 bpm_plan 正式校验", issues=issues)

    return {"plan": plan, "fact_bindings": fact_bindings,
            "reconciliation": report.to_payload(), "generator_schema": GENERATOR_SCHEMA}
