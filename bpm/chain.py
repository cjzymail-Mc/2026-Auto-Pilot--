"""bpm_chain — 报销链产品化入口（round-10 ctr-8cb7b247 §3）。

把 round-7/8/9 各 run 手写 chain_driver 的公共链收编为单一 CLI/库入口：

    register_request → 模板绑定 → 提取复核 → FactSet → reconcile
    → 复用矩阵 → blueprint → generate_fill_plan → validate_plan → execution_ready

- 分类型家族构建：dual_layer（express/office_supplies：details=summary、costs=detail）、
  single_layer（welfare_labor：details 即最细层、costs 空表双理由）、travel_replay
  （travel：另含关联单 relation_archive、模板工号身份、制单人系统观测溯源）。
  rd_materials（products 物品档案链路）暂无家族构建器，显式拒绝（CHAIN_FAMILY_NOT_IMPLEMENTED）。
- 本入口面向离线链复跑：材料须自带 test_only/demo_only/synthetic 语义（授权回放或
  合成件）；真实用户供料仍走 fill_once/bpm_plan 正常任务流，不经本 CLI。
- events 沿用 round-9 分段标记：chain_segment_start 的 segment = 既有 events 行数 + 1
  （append-only，不回改历史段）；任一阶段失败落 plan_generation_failed 事件（含 stage/
  code/error）后以非零码退出。
- 不触碰浏览器：execution_ready 仅以真实子进程运行 `fill_once --validate-only`
  （该分支在浏览器派发之前返回）。
- P2-2 折入：合成材料（synthetic=true）的 user_instruction 事实在
  bpm_plan_generate._source_for_fact 降级 kind=material；本模块对生成计划再断言
  合成链零 kind=user（kind_user_guard 事件留证）。
- P2-3 折入：操作人优先取会话记录实测值（operator_from_session_record，
  source=system_observation）；无实测值时要求显式 --operator-fallback 并在结果与
  events 标注 operator_note（真实执行前须以 S1 实测登录值替换 --expect-name）。
- P2-4 部分折入（round-10 自主裁决①）：test_context.authorization_path 键名保留
  （bpm_plan 精确四键契约不在本轮授权面），语义澄清落 events 与 chain_result：
  该键在本链语义为“授权/材料工件路径”，非人工审批路径；完整改名待 bpm_plan 授权轮。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from decimal import Decimal
from pathlib import Path

from bpm.paths import ROOT

from bpm.facts import FactSet, reconcile                                    # noqa: E402
from bpm.materials import prepare_dual_materials, register_derived, validate_dual_manifest  # noqa: E402
from bpm.plan import file_hash, plan_hash, validate_plan                    # noqa: E402
from bpm.plan_generate import generate_fill_plan                            # noqa: E402
from bpm.request import (build_reuse_matrix, entries_from_matrix,           # noqa: E402
                         execution_ready, operator_from_session_record,
                         register_matrix, register_request)
from bpm.types import check_template_type, resolve_type                     # noqa: E402

FAMILIES = {
    "travel": "travel_replay",
    "express": "dual_layer",
    "office_supplies": "dual_layer",
    "welfare_labor": "single_layer",
}
HEADER_KEYS = ("corpCode", "bizOrign", "budgetYears", "payType",
               "currencyType", "submitType", "description")
ENTRY_FIELDS = ("name", "company", "department") + HEADER_KEYS


class ChainError(RuntimeError):
    """链执行失败（携带 stage/code，统一落 plan_generation_failed 事件）。"""

    def __init__(self, stage, code, message):
        super().__init__(message)
        self.stage = stage
        self.code = code


class ChainRun:
    """单次链执行的落盘上下文（events/工件/清理），家族构建器共用。"""

    def __init__(self, run_dir, document_type, round_label):
        self.run = run_dir
        self.document_type = document_type
        self.round = round_label
        self.events = run_dir / "events.jsonl"

    def log(self, event, **fields):
        line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                           "event": event, **fields}, ensure_ascii=False)
        with self.events.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        print(line, flush=True)

    def segment_index(self):
        """round-9 分段约定：segment = 既有 events 行数 + 1（append-only）。"""
        if not self.events.exists():
            return 1
        with self.events.open("r", encoding="utf-8") as stream:
            return sum(1 for _ in stream) + 1

    def artifact(self, relative, payload):
        path = self.run / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"relative_path": relative, "sha256": file_hash(path)}


def _type_label(document_type):
    identity = resolve_type(document_type)
    allowed = identity.config["header"]["submitType"]["allowed_values"]
    return allowed[0]


def _resolve_operator(args):
    """P2-3：实测优先（会话记录），回退须显式并留 operator_note。"""
    record = args.session_record
    if record is None:
        current = ROOT / "automation/.local-session/current.json"
        if current.is_file():
            try:
                pointer = json.loads(current.read_text(encoding="utf-8"))
                record = ROOT / "automation/.local-session" / pointer["record"]
            except (OSError, ValueError, KeyError):
                record = None
    if record is not None and Path(record).is_file():
        evidence = operator_from_session_record(record)
        if evidence is not None:
            evidence["measured"] = True
            evidence["operator_note"] = ("P2-3：--expect-name 已注入会话记录实测值"
                                         "（source=system_observation）")
            return evidence
    if not args.operator_fallback:
        raise ChainError("operator", "CHAIN_NEEDS_OPERATOR",
                         "无已认证会话记录实测操作人，且未提供 --operator-fallback；"
                         "真实执行前须以 S1 实测登录值替换")
    return {"name": args.operator_fallback, "source": "user_policy",
            "basis": "调用方显式回退值（本链未实测登录）", "measured": False,
            "operator_note": ("P2-3：回退操作人非实测值；真实执行前须以 S1 实测登录值"
                              "替换 --expect-name")}


def _money(value):
    return Decimal(str(value))


def _sum_rows(rows, column="cost"):
    return sum((_money(row["fields"][column]) for row in rows), Decimal("0"))


def _row_extra(row):
    return {key: value for key, value in row["fields"].items() if key != "cost"}


def _build_review(material, material_sha, family, reviewer, round_label):
    """提取复核：结构化材料指针 + 机械交叉核对（金额四方/多方闭合）。"""
    tables = material["tables"]
    details, costs = tables.get("details", []), tables.get("costs", [])
    banks = tables.get("banks", [])
    relations = tables.get("relations", [])
    total = _money(material["header"]["totalCost"])
    crosscheck = {
        "details_sum": str(_sum_rows(details)), "costs_sum": str(_sum_rows(costs)),
        "banks_sum": str(_sum_rows(banks)), "header_totalCost": str(total),
    }
    if family == "travel_replay":
        crosscheck["relations_nowCost_sum"] = str(_sum_rows(relations, "nowCost"))
        if _sum_rows(relations, "nowCost") != total:
            raise ChainError("agent_extraction_review", "CHAIN_AMOUNT_CLOSURE_BROKEN",
                             "relations.nowCost 合计与 totalCost 不闭合")
        semantic_keys = ["/demo_only", "/not_new_expenses",
                         "/substitution_authorization/user_reply",
                         "/invoice_requirement_for_demo"]
    else:
        semantic_keys = ["/test_only", "/not_new_expenses", "/no_invoice_rule",
                         "/table_applicability/relations/reason"]
    # 闭合口径：dual_layer 与 travel 四方（details=costs=banks=totalCost）；
    # single_layer（welfare）costs 空表 not_applicable，三方闭合（details=banks=totalCost）。
    sums = [_sum_rows(details), _sum_rows(banks)]
    if family != "single_layer":
        sums.append(_sum_rows(costs))
    if any(value != total for value in sums):
        raise ChainError("agent_extraction_review", "CHAIN_AMOUNT_CLOSURE_BROKEN",
                         "材料金额闭合失败: {0} vs totalCost={1}".format(
                             [str(value) for value in sums], total))
    for flag in ("test_only", "demo_only", "synthetic"):
        if material.get(flag) is True:
            break
    else:
        raise ChainError("agent_extraction_review", "CHAIN_MATERIAL_SEMANTICS_MISSING",
                         "材料未携带 test_only/demo_only/synthetic 语义；本入口仅复跑"
                         "授权回放或合成件，真实用户供料走 fill_once 正常任务流")
    return {
        "schema_version": "1.0", "kind": "agent_extraction_review",
        "reviewer": reviewer, "material_sha256": material_sha,
        "material_kind": ("synthetic_offline_chain_fixture" if material.get("synthetic") is True
                          else "authorized_historical_replay_json"),
        "extracted": {
            "applicant": {key: "/applicant/{0}".format(key) for key in material["applicant"]},
            "header": {key: "/header/{0}".format(key) for key in material["header"]},
            "tables": {table: ["/tables/{0}/{1}/fields/{2}".format(table, index, column)
                               for index, row in enumerate(rows) for column in row["fields"]]
                       for table, rows in material["tables"].items()},
            "authorization_semantics": semantic_keys,
        },
        "mechanical_crosscheck": crosscheck,
        "review_notes": [
            "结构化 JSON 材料（非扫描件）：无 OCR 层，字段值由 JSON 指针直接定位。",
            "test_only/demo_only/synthetic 与免票语义随件携带未删除。",
            "bpm_chain 产品化复跑（round-{0}）：值与来源全部绑定本 run 材料原件。".format(
                round_label),
        ],
    }


def _base_decisions(f_applicant, f_header, form_structure_basis):
    return [
        {"group": "form_identity", "field": "document_type", "decision": "identify",
         "template_value": form_structure_basis[0], "basis": "模板快照类别与请求声明一致"},
        {"group": "form_identity", "field": "form_structure", "decision": "identify",
         "template_value": form_structure_basis[1], "basis": "封闭注册结构+材料空表理由"},
        {"group": "current_person", "field": "name", "decision": "replace",
         "fact_id": f_applicant, "locator": "/applicant/name"},
        {"group": "current_person", "field": "company", "decision": "replace",
         "fact_id": f_applicant, "locator": "/applicant/company"},
        {"group": "current_person", "field": "department", "decision": "replace",
         "fact_id": f_applicant, "locator": "/applicant/department"},
        {"group": "current_business", "field": "description", "decision": "replace",
         "fact_id": f_header, "locator": "/header/description"},
    ] + [
        {"group": "stable_context", "field": key, "decision": "replace",
         "fact_id": f_header, "locator": "/header/{0}".format(key)} for key in HEADER_KEYS
    ]


def _empty_table_decisions(material, tables):
    reasons = material.get("table_applicability", {})
    row_labels = {"relations": "关联单", "details": "报销明细", "costs": "结算明细",
                  "banks": "收款信息"}
    decisions = []
    for table in ("relations", "details", "costs", "banks"):
        rows = tables.get(table, [])
        if rows:
            decisions.append({"group": "empty_tables", "field": table,
                              "decision": "not_applicable",
                              "reason": "非空表：本次材料提供 {0} 行{1}".format(
                                  len(rows), row_labels[table])})
        else:
            reason = (reasons.get(table) or {}).get("reason")
            if not reason:
                raise ChainError("factset", "CHAIN_EMPTY_TABLE_REASON_MISSING",
                                 "空表 {0} 缺 table_applicability 当次来源理由".format(table))
            decisions.append({"group": "empty_tables", "field": table,
                              "decision": "not_applicable", "reason": reason})
    return decisions


def _row_entries(table, index, row, fact_id):
    return {column: {"value": row["fields"][column], "fact_id": fact_id,
                     "locator": "/tables/{0}/{1}/fields/{2}".format(table, index, column)}
            for column in row["fields"]}


def _build_facts(material, document_type, family, task_id, snapshot, creator_payload,
                 material_name, material_sha, register):
    """家族差异全部落在这里：层语义/关联单/身份/免票依据。返回 (facts, by_kind 索引)。"""
    tables = material["tables"]
    details, costs = tables.get("details", []), tables.get("costs", [])
    banks = tables.get("banks", [])
    relations = tables.get("relations", [])
    hashes = {"originals/{0}".format(material_name): material_sha}
    locator = "originals/{0}#{1}".format(material_name, "{0}")
    facts = FactSet(business_ref=task_id,
                    bindings={"originals/{0}".format(material_name): material_sha})
    total = _money(material["header"]["totalCost"])

    f_applicant = facts.add("business_identity", source="material_extraction",
                            value=material["applicant"], locator=locator.format("/applicant"),
                            input_hashes=hashes, note="材料申请人（本次值，非模板历史）")
    f_header = facts.add("scope", source="material_extraction",
                         value={key: material["header"][key] for key in HEADER_KEYS},
                         locator=locator.format("/header"), input_hashes=hashes,
                         note="单头显示值（金额语义与类别码以材料为源）")
    f_total = facts.add("total", source="deterministic_computation",
                        value={"amount": str(total)}, locator="derived:total#details-cost-sum",
                        derivation="明细求和；与费用/收款各层合计及材料 totalCost 闭合")
    f_relations = [facts.add("relation_archive", source="material_extraction", value={
        "bizNumber": row["fields"]["bizNumber"], "bizTypeName": row["fields"]["bizTypeName"],
        "isLast": row["fields"]["isLast"], "nowCost": row["fields"]["nowCost"],
        "amount": row["fields"]["nowCost"],
    }, locator=locator.format("/tables/relations/{0}".format(index)), input_hashes=hashes,
        note="回放授权关联单（numbers 以材料为源）")
        for index, row in enumerate(relations)]

    detail_layer = "detail" if family == "single_layer" else "summary"
    f_details = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                   layer=detail_layer, category=row["fields"]["reimItem"],
                                   value_extra=_row_extra(row),
                                   locator=locator.format("/tables/details/{0}".format(index)),
                                   input_hashes=hashes)
                 for index, row in enumerate(details)]
    f_costs = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                 layer="detail", category=row["fields"]["project"],
                                 date=row["fields"]["startDate"], value_extra=_row_extra(row),
                                 locator=locator.format("/tables/costs/{0}".format(index)),
                                 input_hashes=hashes)
               for index, row in enumerate(costs)]
    f_payees = [facts.add_payee(name=row["fields"]["payee"], account=row["fields"]["account"],
                                branch=row["fields"]["bank"], interbank=row["fields"]["bankCode"],
                                amount=row["fields"]["cost"], source="material_extraction",
                                locator=locator.format("/tables/banks/{0}".format(index)),
                                input_hashes=hashes)
                for index, row in enumerate(banks)]
    # 空表理由事实（relations 空 / single_layer 另含 costs 空）
    f_ta = {}
    for table in ("relations", "costs"):
        if not tables.get(table, []):
            reason = material["table_applicability"][table]["reason"]
            f_ta[table] = facts.add("scope", source="user_instruction",
                                    value={"reason": reason},
                                    locator=locator.format(
                                        "/table_applicability/{0}/reason".format(table)),
                                    note="空表当次来源理由（材料原文；P2-4：语义为材料路径）")
    # 免票依据：travel 用 invoice_requirement_for_demo，其余用 no_invoice_rule；
    # 挂最细费用层（dual_layer/travel=costs；single_layer=details）。
    waiver_key = "invoice_requirement_for_demo" if family == "travel_replay" else "no_invoice_rule"
    basis_target = f_details if family == "single_layer" else f_costs
    waiver = material[waiver_key]
    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/{0}".format(waiver_key)))
               for fact in basis_target]

    identity = {}
    if family == "travel_replay":
        applicant_name = material["applicant"]["name"]
        template_applicant = snapshot.get("applicant") or {}
        if template_applicant.get("appliedName") != applicant_name:
            raise ChainError("factset", "CHAIN_IDENTITY_DUAL_SOURCE_BROKEN",
                             "模板申请人与材料申请人同名印证失败: {0!r} vs {1!r}".format(
                                 template_applicant.get("appliedName"), applicant_name))
        f_employee_id = facts.add("business_identity", source="template",
                                  value={"applicant_employee_id": template_applicant["appliedBy"],
                                         "appliedName": template_applicant["appliedName"]},
                                  locator="template_snapshot.json#/applicant/appliedBy",
                                  input_hashes={"template_snapshot.json": register["template_sha"]},
                                  note="同人员稳定工号复用（模板快照双源印证）")
        identity["applicant_employee_id"] = {
            "value": template_applicant["appliedBy"], "fact_id": f_employee_id,
            "locator": "/applicant/appliedBy"}
        if creator_payload is not None:
            creator_ref = register_derived(register["manifest_path"],
                                           "observed/page_creator_observation.json",
                                           creator_payload, role="run_evidence",
                                           sources=[material_sha],
                                           generated_by="bpm_chain/system_observation_extract")
            obs_hashes = {"materials/observed/page_creator_observation.json":
                          creator_ref.split(":", 1)[1]}
            f_creator = facts.add("business_identity", source="system_observation",
                                  value={"creator_name": creator_payload["createdName"],
                                         "creator_department": creator_payload["createdDeptName"]},
                                  locator="materials/observed/page_creator_observation.json#/createdName",
                                  input_hashes=obs_hashes,
                                  note="新表页默认制单人观测（{0}；溯源随工件）".format(
                                      creator_payload.get("observed_run", "prior-run")))
            identity["creator_name"] = {"value": creator_payload["createdName"],
                                        "fact_id": f_creator, "locator": "/createdName"}
            identity["creator_department"] = {"value": creator_payload["createdDeptName"],
                                              "fact_id": f_creator, "locator": "/createdDeptName"}
    return facts, {"applicant": f_applicant, "header": f_header, "total": f_total,
                   "details": f_details, "costs": f_costs, "payees": f_payees,
                   "relations": f_relations, "ta": f_ta, "basis": f_basis,
                   "identity": identity}


def run_chain(args):
    """公共链主体；返回 chain_result（失败抛 ChainError，由 CLI 落失败段）。"""
    document_type = args.document_type
    family = FAMILIES.get(document_type)
    if family is None:
        raise ChainError("entry", "CHAIN_FAMILY_NOT_IMPLEMENTED",
                         "{0} 暂无家族构建器（rd_materials products 链路未产品化）；"
                         "本轮支持 travel/express/office_supplies/welfare_labor".format(
                             document_type))
    label = _type_label(document_type)
    material_source = Path(args.material).resolve()
    snapshot_source = Path(args.template_snapshot).resolve()
    run_dir = (ROOT / args.run_dir).resolve() if not Path(args.run_dir).is_absolute() \
        else Path(args.run_dir).resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ChainError("entry", "CHAIN_RUN_DIR_NOT_EMPTY",
                         "run 目录已存在且非空（链不覆盖历史 run）: {0}".format(run_dir))
    run_dir.mkdir(parents=True)
    chain = ChainRun(run_dir, document_type, args.round)

    operator = _resolve_operator(args)   # P2-3：实测优先，失败即中止
    material_name = material_source.name
    originals = run_dir / "originals"
    originals.mkdir()
    shutil.copyfile(material_source, originals / material_name)
    shutil.copyfile(snapshot_source, run_dir / "template_snapshot.json")
    material_sha = file_hash(originals / material_name)
    material = json.loads((originals / material_name).read_text(encoding="utf-8"))
    snapshot = json.loads((run_dir / "template_snapshot.json").read_text(encoding="utf-8"))
    try:
        check_template_type(snapshot, document_type)
        resolve_type(document_type)
    except Exception as exc:  # TypeConfigError
        raise ChainError("template_bound", "CHAIN_TEMPLATE_TYPE_MISMATCH", str(exc))
    if snapshot.get("biz_number") != args.template_number:
        raise ChainError("template_bound", "CHAIN_TEMPLATE_NUMBER_MISMATCH",
                         "快照单号 {0!r} 与 --template-number {1!r} 不符".format(
                             snapshot.get("biz_number"), args.template_number))
    template_sha = file_hash(run_dir / "template_snapshot.json")
    lineage = material.get("replay_lineage") or {}
    if lineage.get("template_sha256") and lineage["template_sha256"] != template_sha:
        raise ChainError("template_bound", "CHAIN_TEMPLATE_LINEAGE_DRIFT",
                         "模板快照 sha 与材料 lineage 漂移")
    synthetic = material.get("synthetic") is True
    segment = chain.segment_index()
    chain.log("chain_segment_start", segment=segment, run=run_dir.name,
              chain_tool="bpm_chain", document_type=document_type, family=family,
              round=args.round, material_sha256=material_sha,
              material_basis=("合成离线链材料（synthetic=true，不入业务 manifest）" if synthetic
                              else "授权历史回放材料（test_only/demo_only 语义随件）只读复制"),
              template_basis="--template-snapshot 指定快照只读复制（lineage sha 核对通过）")
    chain.log("operator_resolved", name=operator["name"], source=operator["source"],
              measured=operator.get("measured", False), operator_note=operator["operator_note"])

    manifest_path = prepare_dual_materials(originals, run_dir / "materials")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues = validate_dual_manifest(manifest, base_dir=run_dir)
    if issues:
        raise ChainError("prepare_dual_materials", "CHAIN_MANIFEST_INVALID", str(issues)[:500])
    chain.log("prepare_dual_materials", manifest=str(manifest_path),
              originals=len(manifest["files"]), derived=len(manifest["derived_files"]))

    task_id = args.task_id or "chain-r{0}-{1}-{2}".format(
        args.round, document_type, args.template_number)
    statement = args.statement or (
        "{0}报销链复跑（bpm_chain round-{1}）：明细 {2} 行、结算 {3} 行、"
        "收款 {4} 行，合计 {5}；validate-only 只填不存。".format(
            label, args.round, len(material["tables"].get("details", [])),
            len(material["tables"].get("costs", [])), len(material["tables"].get("banks", [])),
            material["header"]["totalCost"]))
    request = register_request({
        "template_biz_number": args.template_number,
        "materials_dir": str(originals),
        "statement": statement,
        "declared_category": label,
        "relation_refs": [row["fields"]["bizNumber"]
                          for row in material["tables"].get("relations", [])],
    }, manifest_path=manifest_path)
    if request["status"] != "REGISTERED":
        raise ChainError("register_request", "CHAIN_REQUEST_NEEDS_INPUT",
                         json.dumps(request.get("gaps"), ensure_ascii=False)[:500])
    chain.log("register_request", status="REGISTERED", task_id=task_id,
              artifact=request["artifact"]["relative_path"], sha256=request["artifact"]["sha256"])

    chain.log("template_bound", status="RESOLVED", document_type=document_type,
              uuid=snapshot.get("uuid"), snapshot_sha256=template_sha,
              basis="--template-snapshot 快照绑定+check_template_type+lineage 核对")

    review = _build_review(material, material_sha, family,
                           "bpm-chain-agent/round-{0}".format(args.round), args.round)
    review_ref = register_derived(manifest_path, "reviewed/agent_review.json", review,
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="bpm_chain/agent_extraction_review")
    chain.log("agent_extraction_review", artifact="reviewed/agent_review.json",
              sha256=review_ref,
              rows={table: len(rows) for table, rows in material["tables"].items()},
              closure=str(material["header"]["totalCost"]))

    creator_payload = None
    if family == "travel_replay" and args.creator_observation:
        creator_payload = json.loads(Path(args.creator_observation).read_text(encoding="utf-8"))
    register = {"manifest_path": manifest_path, "template_sha": template_sha}
    facts, index = _build_facts(material, document_type, family, task_id, snapshot,
                                creator_payload, material_name, material_sha, register)
    facts_ref = register_derived(manifest_path, "facts/factset.json", facts.to_payload(),
                                 role="run_evidence", sources=[material_sha],
                                 generated_by="bpm_chain/FactSet")
    chain.log("factset_built", artifact="facts/factset.json", sha256=facts_ref, facts=len(facts),
              kinds={kind: len(facts.by_kind(kind)) for kind in
                     ("business_identity", "scope", "expense", "relation_archive",
                      "payee_group", "no_invoice_basis", "total")})

    report = reconcile(facts)
    if report.blocked:
        raise ChainError("reconcile", "CHAIN_RECONCILE_BLOCKED",
                         json.dumps(report.to_payload(), ensure_ascii=False)[:500])
    register_derived(manifest_path, "facts/reconciliation.json", report.to_payload(),
                     role="run_evidence", sources=[material_sha],
                     generated_by="bpm_chain/reconcile")
    chain.log("reconcile", blocked=False, checks={c.name: c.status for c in report.checks})

    structure = {
        "travel_replay": ("{0}({1})".format(label, document_type),
                          "relations/details/costs/banks 四表"),
        "dual_layer": ("{0}({1})".format(label, document_type),
                       "relations/details/costs/banks 四表（relations 空）"),
        "single_layer": ("{0}({1})".format(label, document_type),
                         "relations/details/costs/banks 四表（relations+costs 空）"),
    }[family]
    decisions = _base_decisions(index["applicant"], index["header"], structure)
    decisions += [{"group": "proven_references",
                   "field": "relations[{0}].bizNumber".format(i), "decision": "replace",
                   "fact_id": index["relations"][i],
                   "locator": "/tables/relations/{0}/fields/bizNumber".format(i),
                   "basis": "回放材料关联单（授权 numbers 以材料为源）"}
                  for i in range(len(index["relations"]))]
    decisions += [{"group": "proven_references", "field": "banks[{0}].payee".format(i),
                   "decision": "replace", "fact_id": index["payees"][i],
                   "locator": "/tables/banks/{0}/fields/payee".format(i),
                   "basis": "材料收款人（材料证明属于本次回放/合成件）"}
                  for i in range(len(index["payees"]))]
    decisions += _empty_table_decisions(material, material["tables"])
    matrix = build_reuse_matrix(snapshot, facts, decisions)
    matrix_ref = register_matrix(matrix, manifest_path=manifest_path)
    chain.log("reuse_matrix", artifact=matrix_ref["relative_path"], sha256=matrix_ref["sha256"],
              rows=len(matrix["rows"]))

    entries = entries_from_matrix(matrix, facts, ENTRY_FIELDS)
    applicant_entries = {key: entries[key] for key in ("name", "company", "department")}
    header_entries = {key: entries[key] for key in HEADER_KEYS}
    tables = material["tables"]
    if family == "single_layer":
        amount_rules = {"costs": "not_applicable",
                        "costs_reason": material["table_applicability"]["costs"]["reason"],
                        "cost_amount_semantics": "line_total"}
    else:
        amount_rules = {"costs": "sum", "cost_amount_semantics": "line_total"}
    authorization_statement = (
        "合成离线链复跑（round-{0} bpm_chain）：synthetic/test_only/not_new_expenses；"
        "仅 validate-only 子进程，不填真实页面、不保存不提交。".format(args.round)
        if synthetic else
        "授权历史回放链复跑（round-{0} bpm_chain）：test_only/demo_only/not_new_expenses 随件；"
        "仅 validate-only 子进程，不填真实页面、不保存不提交。".format(args.round))
    blueprint = {
        "document_type": document_type, "task_id": task_id, "operator": operator["name"],
        "template": {"biz_number": snapshot["biz_number"], "captured_at": snapshot["captured_at"],
                     "sha256": template_sha, "snapshot_path": "template_snapshot.json"},
        "materials": {"manifest_path": str(manifest_path)},
        "authorization": {"mode": "fill_only", "task_id": task_id, "allow_submit": False,
                          "statement": authorization_statement},
        "not_applicable": [],
        "amount_rules": amount_rules,
        "applicant": applicant_entries,
        "header": header_entries,
        "tables": {
            "relations": [{"row_id": row["row_id"],
                           "fields": _row_entries("relations", i, row, index["relations"][i])}
                          for i, row in enumerate(tables.get("relations", []))],
            "details": [{"row_id": row["row_id"],
                         "fields": _row_entries("details", i, row, index["details"][i])}
                        for i, row in enumerate(tables.get("details", []))],
            "costs": [{"row_id": row["row_id"],
                       "fields": _row_entries("costs", i, row, index["costs"][i])}
                      for i, row in enumerate(tables.get("costs", []))],
            "banks": [{"row_id": row["row_id"],
                       "fields": _row_entries("banks", i, row, index["payees"][i])}
                      for i, row in enumerate(tables.get("banks", []))],
        },
        "total": {"value": str(_money(material["header"]["totalCost"])),
                  "fact_id": index["total"]},
        "table_applicability": {
            table: {"value": material["table_applicability"][table]["reason"],
                    "fact_id": fact_id,
                    "locator": "/table_applicability/{0}/reason".format(table)}
            for table, fact_id in index["ta"].items()},
    }
    if index["identity"]:
        blueprint["identity"] = index["identity"]
    blueprint_ref = register_derived(manifest_path, "plan/blueprint.json", blueprint,
                                     role="run_evidence", sources=[material_sha],
                                     generated_by="bpm_chain/blueprint_assembly")
    chain.log("blueprint_assembled", artifact="plan/blueprint.json", sha256=blueprint_ref,
              identity={key: entry["value"] for key, entry in index["identity"].items()}
              or None,
              table_rows={table: len(rows) for table, rows in blueprint["tables"].items()})

    generated = generate_fill_plan(facts, blueprint, base_dir=run_dir)
    plan = generated["plan"]
    # P2-2：合成链零 kind=user（真实链 kind=user 严格对应用户真实供料）。
    user_sources = [pointer for pointer, source in plan.get("sources", {}).items()
                    if source.get("kind") == "user"]
    for row in plan.get("materials", {}).get("no_invoice_rows", []):
        if row.get("proof", {}).get("kind") == "user":
            user_sources.append(row["proof"].get("path", "no_invoice_row"))
    if synthetic and user_sources:
        raise ChainError("plan_generation", "CHAIN_SYNTHETIC_MASQUERADES_USER",
                         "合成链计划出现 kind=user 来源: {0}".format(user_sources[:5]))
    chain.log("kind_user_guard", synthetic=synthetic, user_kind_sources=len(user_sources))
    plan["test_context"] = {
        "purpose": "{0} {1}（round-{2}，bpm_chain 复跑；{3}）".format(
            args.template_number, label, args.round,
            "合成材料 synthetic/test_only" if synthetic else "授权历史回放材料"),
        "round": args.round,
        # P2-4（自主裁决①）：authorization_path 语义=授权/材料工件路径（非人工审批路径）。
        "authorization_path": "originals/{0}".format(material_name),
        "authorization_sha256": material_sha,
    }
    issues = validate_plan(plan, expected_operator=operator["name"],
                           verify_sources=True, base_dir=run_dir)
    if issues:
        raise ChainError("plan_generation", "CHAIN_PLAN_INVALID",
                         json.dumps(issues, ensure_ascii=False)[:500])
    plan_path = run_dir / "fill_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    chain.artifact("plan_validation.json",
                   {"status": "PLAN_VALIDATED", "issues": [],
                    "plan_sha256": file_hash(plan_path), "sources": len(plan["sources"]),
                    "reconciliation": generated["reconciliation"]})
    chain.log("plan_ready", plan="fill_plan.json", sha256=file_hash(plan_path),
              plan_hash=plan_hash(plan), sources=len(plan["sources"]), status="PLAN_READY")

    readiness = execution_ready(plan_path, {key: operator[key] for key in
                                            ("name", "source", "basis") if key in operator})
    if readiness["status"] != "EXECUTION_READY":
        raise ChainError("execution_ready", "CHAIN_VALIDATE_ONLY_FAILED",
                         json.dumps(readiness.get("gaps"), ensure_ascii=False)[:500])
    chain.artifact("execution_ready.json", readiness)
    chain.log("execution_ready", status="EXECUTION_READY", operator=operator["name"],
              source=operator["source"], measured=operator.get("measured", False),
              operator_note=operator["operator_note"],
              suggested_command=readiness["suggested_command"],
              validate_only=True, browser_launched=False)

    result = {
        "status": "CHAIN_COMPLETE", "chain_tool": "bpm_chain", "family": family,
        "document_type": document_type, "run": run_dir.name, "segment": segment,
        "round": args.round, "synthetic": synthetic,
        "plan": {"path": str(plan_path), "sha256": file_hash(plan_path),
                 "plan_hash": plan_hash(plan)},
        "operator": operator,
        "kind_user_guard": {"synthetic": synthetic, "user_kind_sources": 0 if synthetic else None},
        "test_context_semantics": ("P2-4 自主裁决①：authorization_path=授权/材料工件路径；"
                                   "完整改名待 bpm_plan 授权轮"),
        "events": "events.jsonl", "validate_only": True, "browser_launched": False,
    }
    chain.artifact("chain_result.json", result)
    chain.log("chain_result", status="CHAIN_COMPLETE", plan=str(plan_path),
              plan_hash=plan_hash(plan), browser_launched=False)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="报销链产品化复跑（离线；validate-only，不触碰浏览器）",
        prog="bpm_chain")
    parser.add_argument("--material", required=True, help="材料原件 JSON（复制进 run originals/）")
    parser.add_argument("--document-type", required=True,
                        choices=["travel", "express", "rd_materials", "office_supplies",
                                 "welfare_labor"])
    parser.add_argument("--run-dir", required=True, help="新 run 目录（须不存在或为空）")
    parser.add_argument("--template-snapshot", required=True, help="模板快照 JSON（只读复制）")
    parser.add_argument("--template-number", required=True, help="完整模板单号（数字串）")
    parser.add_argument("--round", default="10", help="轮次标记（events/计划 test_context）")
    parser.add_argument("--task-id", default=None, help="任务 id（缺省 chain-r<round>-<type>-<单号>）")
    parser.add_argument("--statement", default=None, help="业务说明（缺省按材料行数生成）")
    parser.add_argument("--session-record", default=None,
                        help="会话记录 JSON（缺省读 automation/.local-session/current.json）")
    parser.add_argument("--operator-fallback", default=None,
                        help="无实测操作人时的显式回退值（user_policy，结果留 P2-3 note）")
    parser.add_argument("--creator-observation", default=None,
                        help="travel 家族制单人观测工件 JSON（system_observation 溯源）")
    args = parser.parse_args(argv)
    if args.document_type == "rd_materials":
        print(json.dumps({"status": "CHAIN_FAILED", "code": "CHAIN_FAMILY_NOT_IMPLEMENTED",
                          "stage": "entry",
                          "error": "rd_materials 暂无家族构建器（products 链路未产品化）"},
                         ensure_ascii=False))
        return 2
    try:
        result = run_chain(args)
    except ChainError as exc:
        payload = {"status": "CHAIN_FAILED", "stage": exc.stage, "code": exc.code,
                   "error": str(exc)[:800]}
        run_dir = Path(args.run_dir)
        if run_dir.is_dir():
            with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(
                    {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "event": "plan_generation_failed", **payload}, ensure_ascii=False) + "\n")
            (run_dir / "chain_result.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False), flush=True)
        return 1
    print(json.dumps({"chain": "COMPLETE", "run": result["run"],
                      "plan": result["plan"]["path"],
                      "plan_hash": result["plan"]["plan_hash"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
