"""Round-7 travelloop：agent 自驱全链（登记→模板→提取复核→事实→对账→矩阵→计划→执行就绪）。

事实/决策内容由 agent 阅读本次材料（originals/replay_r7.json，授权历史回放 rev02，
sha256 a80c424a…）后给出；每步只调用仓库库函数并落中间工件+events.jsonl。
不预写 facts_payload/blueprint 塞入口：FactSet 全部经 add/add_expense/add_payee 构造，
计划由 bpm_plan_generate.generate_fill_plan 生成并当场过 validate_plan。
"""
import json
import shutil
import sys
import time
from decimal import Decimal
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
sys.path.insert(0, str(ROOT))

from bpm_facts import FactSet, reconcile                      # noqa: E402
from bpm_materials import prepare_dual_materials, register_derived, validate_dual_manifest  # noqa: E402
from bpm_plan import file_hash, plan_hash, validate_plan      # noqa: E402
from bpm_plan_generate import generate_fill_plan             # noqa: E402
from bpm_request import (build_reuse_matrix, entries_from_matrix, execution_ready,           # noqa: E402
                         operator_from_session_record, register_matrix, register_request,
                         resolve_template)

EVENTS = RUN / "events.jsonl"
CENSUS = ROOT / "automation/runs/20261023-142146-travelcensus/travel_census.json"
SESSION_RECORD = ROOT / "automation/.local-session/6f998b924ecf48b0b8c2b6ea16ef54ba/session_record.json"
TEMPLATE_NUMBER = "15426093015"
TASK_ID = "20261024-r7-travelloop-15426093015"
ROUND = "7"


def log(event, **fields):
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": event, **fields},
                      ensure_ascii=False)
    with EVENTS.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    print(line, flush=True)


def artifact(relative, payload):
    path = RUN / relative
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"relative_path": relative, "sha256": file_hash(path)}


def main():
    original = RUN / "originals/replay_r7.json"
    # 离线链可重建：重跑前清掉派生根与本轮计划产物（originals 只读不动，events 追加留史）。
    for stale in ("materials",):
        target = RUN / stale
        if target.exists():
            shutil.rmtree(target)
    for stale in ("template_snapshot.json", "fill_plan_r7.json",
                  "plan_validation.json", "execution_ready.json"):
        target = RUN / stale
        if target.exists():
            target.unlink()
    material_sha = file_hash(original)
    log("chain_start", run=RUN.name, material_sha256=material_sha,
        material_basis="授权历史回放 rev02（2026-10-24 用户更正三点之回放授权范围）只读复制")

    # ---- 阶段 3 前置：双根材料准备
    manifest_path = prepare_dual_materials(RUN / "originals", RUN / "materials")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues = validate_dual_manifest(manifest, base_dir=RUN)
    assert not issues, issues
    log("prepare_dual_materials", manifest=str(manifest_path),
        originals=len(manifest["files"]), derived=len(manifest["derived_files"]))

    # ---- 阶段 1 请求登记（库函数；缺要素即 NEEDS_INPUT，不落盘）
    request = register_request({
        "template_biz_number": TEMPLATE_NUMBER,
        "materials_dir": str(RUN / "originals"),
        "statement": "公出油补报销（授权历史业务回放）：三张公出单关联、餐补与通行费明细、"
                     "其它交通/伙食结算明细、收款徐亮，合计 633.84；本轮 fill_only 只填不存。",
        "declared_category": "差旅费",
        "relation_refs": ["12026101976", "12026070366", "12026037675"],
    }, manifest_path=manifest_path)
    assert request["status"] == "REGISTERED", request
    log("register_request", status="REGISTERED",
        artifact=request["artifact"]["relative_path"], sha256=request["artifact"]["sha256"])

    # ---- 阶段 2 模板决策（缓存定向读取；类别矛盾/未知即拒绝）
    resolved = resolve_template(str(CENSUS), TEMPLATE_NUMBER, declared_category="差旅费")
    assert resolved["status"] == "RESOLVED", resolved
    snapshot = resolved["snapshot"]
    snapshot_path = RUN / "template_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    template_block = {"biz_number": snapshot["biz_number"], "captured_at": snapshot["captured_at"],
                      "sha256": file_hash(snapshot_path), "snapshot_path": "template_snapshot.json"}
    log("resolve_template", status="RESOLVED", document_type=resolved["document_type"],
        uuid=snapshot["uuid"], source_kind=snapshot["source"]["kind"],
        snapshot_sha256=template_block["sha256"])

    # ---- 阶段 3 提取复核（结构化回放材料：agent 通读+机械交叉核对）
    material = json.loads(original.read_text(encoding="utf-8"))
    details, costs = material["tables"]["details"], material["tables"]["costs"]
    relations, banks = material["tables"]["relations"], material["tables"]["banks"]
    detail_sum = sum((Decimal(row["fields"]["cost"]) for row in details), Decimal("0"))
    cost_sum = sum((Decimal(row["fields"]["cost"]) for row in costs), Decimal("0"))
    bank_sum = sum((Decimal(row["fields"]["cost"]) for row in banks), Decimal("0"))
    nowcost_sum = sum((Decimal(row["fields"]["nowCost"]) for row in relations), Decimal("0"))
    total = Decimal(material["header"]["totalCost"])
    assert detail_sum == cost_sum == bank_sum == total, (detail_sum, cost_sum, bank_sum, total)
    assert material["demo_only"] is True and material["not_new_expenses"] is True
    review = {
        "schema_version": "1.0", "kind": "agent_extraction_review",
        "reviewer": "round7-B-agent", "material_sha256": material_sha,
        "material_kind": "authorized_historical_replay_json",
        "extracted": {
            "applicant": {key: "/applicant/{0}".format(key) for key in material["applicant"]},
            "header": {key: "/header/{0}".format(key) for key in material["header"]},
            "tables": {table: ["/tables/{0}/{1}/fields/{2}".format(table, index, column)
                               for index, row in enumerate(rows) for column in row["fields"]]
                       for table, rows in material["tables"].items()},
            "authorization_semantics": ["/demo_only", "/not_new_expenses",
                                        "/substitution_authorization/user_reply",
                                        "/invoice_requirement_for_demo"],
        },
        "mechanical_crosscheck": {
            "details_sum": str(detail_sum), "costs_sum": str(cost_sum), "banks_sum": str(bank_sum),
            "relations_nowCost_sum": str(nowcost_sum), "header_totalCost": str(total),
            "closure": "四表合计与 totalCost 全部闭合",
        },
        "review_notes": [
            "材料为结构化回放 JSON（非扫描件）：无 OCR 层，字段值由 JSON 指针直接定位。",
            "demo_only/not_new_expenses 语义随件携带，未删除；演示免票说明原文用于免票依据。",
            "真实发票原件缺口：本回放无票面原件，登记为 round-7 已知缺口，不虚构。",
        ],
    }
    review_ref = register_derived(manifest_path, "reviewed/replay_agent_review.json", review,
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="round7-chain/agent_extraction_review")
    # 2026-10-24 16:00 本次 run 20261024-160024-8502f91d 实页观测（blocked_readback）：
    # 新表页默认制单人 陈晶/运动表现研究部（首填因缺申请人工号被阻断，页面零写入）。
    creator_observation = {
        "schema_version": "1.0", "kind": "system_observation_extract",
        "observed_run": "20261024-160024-8502f91d",
        "source_evidence": "attempt_001/evidence/blocked_readback.json",
        "source_evidence_sha256": file_hash(
            ROOT / "automation/runs/20261024-160024-8502f91d/attempt_001/evidence/blocked_readback.json"),
        "createdName": "陈晶", "createdDeptName": "运动表现研究部",
        "page": {"is_new": True, "operator": "陈晶",
                 "url": "https://bpm.qiaodan.com/oa/reimburse?type=new"},
        "observed_at": "2026-10-24T16:00:34+08:00",
    }
    creator_ref = register_derived(manifest_path, "observed/page_creator_observation.json",
                                   creator_observation, role="run_evidence",
                                   sources=[material_sha],
                                   generated_by="round7-chain/system_observation_extract")
    log("agent_extraction_review", artifact="reviewed/replay_agent_review.json", sha256=review_ref,
        rows={"details": len(details), "costs": len(costs),
              "relations": len(relations), "banks": len(banks)},
        closure=str(total))

    # ---- 阶段 4 事实构造（全部经 FactSet API；金额 Decimal）
    hashes = {"originals/replay_r7.json": material_sha}
    locator = "originals/replay_r7.json#{0}"
    facts = FactSet(business_ref=TASK_ID, bindings={"originals/replay_r7.json": material_sha})
    f_applicant = facts.add("business_identity", source="material_extraction",
                            value=material["applicant"], locator=locator.format("/applicant"),
                            input_hashes=hashes, note="回放材料申请人身份（本次值，非模板历史）")
    f_header = facts.add("scope", source="material_extraction", value={
        key: material["header"][key] for key in
        ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType", "submitType", "description")
    }, locator=locator.format("/header"), input_hashes=hashes, note="单头显示值（转账/人民币/差旅费…）")
    f_total = facts.add("total", source="deterministic_computation",
                        value={"amount": str(total)},
                        locator="derived:total#details-cost-sum",
                        derivation="details 两行 cost 求和；与 costs/banks/relations.nowCost 及材料 totalCost 四方闭合一致")
    f_relations = [facts.add("relation_archive", source="material_extraction", value={
        "bizNumber": row["fields"]["bizNumber"], "bizTypeName": row["fields"]["bizTypeName"],
        "isLast": row["fields"]["isLast"], "nowCost": row["fields"]["nowCost"],
        "amount": row["fields"]["nowCost"],
    }, locator=locator.format("/tables/relations/{0}".format(index)), input_hashes=hashes,
        note="用户授权替换后的三张公出单（回放授权 numbers）")
        for index, row in enumerate(relations)]
    # 层语义：costs 六行为最细粒度费用台账（逐日期/类别）→ detail 层；
    # details 两行为按科目聚合（60=24+24+12，573.84=191.28×3）→ summary 层。
    f_details = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                   layer="summary", category=row["fields"]["reimItem"],
                                   value_extra={key: row["fields"][key] for key in
                                                ("reimItem", "digest", "budgetDeptName", "budgetNo",
                                                 "subjectName", "budgetItemName")},
                                   locator=locator.format("/tables/details/{0}".format(index)),
                                   input_hashes=hashes)
                 for index, row in enumerate(details)]
    f_costs = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                 layer="detail", category=row["fields"]["project"],
                                 date=row["fields"]["startDate"],
                                 value_extra={key: row["fields"][key] for key in
                                              ("project", "startDate", "endDate", "projectPlace",
                                               "count", "reason")},
                                 locator=locator.format("/tables/costs/{0}".format(index)),
                                 input_hashes=hashes)
               for index, row in enumerate(costs)]
    bank = banks[0]["fields"]
    f_payee = facts.add_payee(name=bank["payee"], account=bank["account"], branch=bank["bank"],
                              interbank=bank["bankCode"], amount=bank["cost"],
                              source="material_extraction",
                              locator=locator.format("/tables/banks/0"), input_hashes=hashes)
    # 申请人稳定工号（identity 前置证据）：模板单申请人=材料申请人=徐亮（同名同部门），
    # appliedBy=117070006 双源印证：本次模板快照 + 2026-10-23 demo attempt_002 独立回读。
    f_employee_id = facts.add("business_identity", source="template",
                              value={"applicant_employee_id": snapshot["applicant"]["appliedBy"],
                                     "appliedName": snapshot["applicant"]["appliedName"]},
                              locator="template_snapshot.json#/applicant/appliedBy",
                              input_hashes={"template_snapshot.json": template_block["sha256"]},
                              note="同人员稳定工号复用（AGENTS 允许有依据的稳定身份复用）；"
                                   "佐证：20261023-live-complex-demo attempt_002 independent_readback appliedBy 同值")
    # 制单人身份（页面默认，非计划值）：本次实页观测工件登记进派生根后作系统观察事实。
    obs_hashes = {"materials/observed/page_creator_observation.json": creator_ref.split(":", 1)[1]}
    f_creator = facts.add("business_identity", source="system_observation",
                          value={"creator_name": "陈晶", "creator_department": "运动表现研究部"},
                          locator="materials/observed/page_creator_observation.json#/createdName",
                          input_hashes=obs_hashes,
                          note="新表页默认制单人观测（20261024-160024-8502f91d blocked_readback）；"
                               "执行时由 INITIAL_CREATOR_MISMATCH 现场再核")
    waiver = material["invoice_requirement_for_demo"]
    # 免票依据挂 detail 层（costs 六行）：对账覆盖最细粒度费用，生成器映射主表行指针。
    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/invoice_requirement_for_demo"))
               for fact in f_costs]
    facts_ref = register_derived(manifest_path, "facts/factset.json", facts.to_payload(),
                                 role="run_evidence", sources=[material_sha],
                                 generated_by="round7-chain/FactSet")
    log("factset_built", artifact="facts/factset.json", sha256=facts_ref, facts=len(facts),
    kinds={kind: len(facts.by_kind(kind)) for kind in
               ("business_identity", "scope", "expense", "relation_archive", "payee_group",
                "no_invoice_basis", "total")})

    # ---- 阶段 5 对账（程序化；任何 block 即拒）
    report = reconcile(facts)
    assert not report.blocked, report.to_payload()
    report_ref = register_derived(manifest_path, "facts/reconciliation.json", report.to_payload(),
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="round7-chain/reconcile")
    log("reconcile", blocked=False,
        checks={c.name: c.status for c in report.checks}, artifact="facts/reconciliation.json",
        sha256=report_ref)

    # ---- 阶段 5b 复用矩阵（六字段组逐字段决策；值一律事实绑定）
    decisions = [
        {"group": "form_identity", "field": "document_type", "decision": "identify",
         "template_value": "差旅费(travel)", "basis": "模板快照 submitType=差旅费，与请求声明一致"},
        {"group": "form_identity", "field": "form_structure", "decision": "identify",
         "template_value": "relations/details/costs/banks 四表", "basis": "travel 封闭注册结构"},
        {"group": "current_person", "field": "name", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/name"},
        {"group": "current_person", "field": "company", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/company"},
        {"group": "current_person", "field": "department", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/department"},
        {"group": "current_business", "field": "description", "decision": "replace", "fact_id": f_header,
         "locator": "/header/description"},
        {"group": "stable_context", "field": "corpCode", "decision": "replace", "fact_id": f_header,
         "locator": "/header/corpCode"},
        {"group": "stable_context", "field": "bizOrign", "decision": "replace", "fact_id": f_header,
         "locator": "/header/bizOrign"},
        {"group": "stable_context", "field": "budgetYears", "decision": "replace", "fact_id": f_header,
         "locator": "/header/budgetYears", "basis": "本次材料 2026 年度，非模板旧值沿用"},
        {"group": "stable_context", "field": "payType", "decision": "replace", "fact_id": f_header,
         "locator": "/header/payType"},
        {"group": "stable_context", "field": "currencyType", "decision": "replace", "fact_id": f_header,
         "locator": "/header/currencyType"},
        {"group": "stable_context", "field": "submitType", "decision": "replace", "fact_id": f_header,
         "locator": "/header/submitType"},
    ]
    decisions += [{"group": "proven_references", "field": "relations[{0}].bizNumber".format(index),
                   "decision": "replace", "fact_id": f_relations[index],
                   "locator": "/tables/relations/{0}/fields/bizNumber".format(index),
                   "basis": "用户授权替换（回复：允许，仅用于本次演示）"}
                  for index in range(len(relations))]
    decisions += [
        {"group": "proven_references", "field": "banks[0].payee", "decision": "replace",
         "fact_id": f_payee, "locator": "/tables/banks/0/fields/payee",
         "basis": "回放材料收款人（材料证明属于本次回放）"},
        {"group": "empty_tables", "field": "relations", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 3 张已授权公出单，全部入表"},
        {"group": "empty_tables", "field": "details", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 2 行报销明细"},
        {"group": "empty_tables", "field": "costs", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 6 行结算明细"},
        {"group": "empty_tables", "field": "banks", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 1 行收款信息"},
    ]
    matrix = build_reuse_matrix(snapshot, facts, decisions)
    matrix_ref = register_matrix(matrix, manifest_path=manifest_path)
    log("reuse_matrix", artifact=matrix_ref["relative_path"], sha256=matrix_ref["sha256"],
        rows=len(matrix["rows"]))

    # ---- 阶段 6 计划（entries + 行绑定 blueprint → 生成器）
    fields = ("name", "company", "department", "corpCode", "bizOrign", "budgetYears",
              "payType", "currencyType", "submitType", "description")
    entries = entries_from_matrix(matrix, facts, fields)
    applicant_entries = {key: entries[key] for key in ("name", "company", "department")}
    header_entries = {key: entries[key] for key in
                      ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType",
                       "submitType", "description")}

    def row_entries(table, index, row, money_fact, money_column):
        out = {}
        for column in row["fields"]:
            entry = {"value": row["fields"][column], "fact_id": money_fact,
                     "locator": "/tables/{0}/{1}/fields/{2}".format(table, index, column)}
            out[column] = entry
        return out

    blueprint = {
        "document_type": "travel", "task_id": TASK_ID, "operator": "陈晶",
        "template": template_block,
        "materials": {"manifest_path": str(manifest_path)},
        "authorization": {
            "mode": "fill_only", "task_id": TASK_ID, "allow_submit": False,
            "statement": "本轮为授权历史业务回放的只填不存练习：材料为用户授权演示回放"
                         "（substitution_authorization.user_reply=允许，仅用于本次演示），"
                         "在新页真实填写后不保存、不提交、不产生新报销。",
        },
        "not_applicable": [],
        "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
        "applicant": applicant_entries,
        "header": header_entries,
        "tables": {
            "relations": [{"row_id": row["row_id"],
                           "fields": row_entries("relations", index, row, f_relations[index], "nowCost")}
                          for index, row in enumerate(relations)],
            "details": [{"row_id": row["row_id"],
                         "fields": row_entries("details", index, row, f_details[index], "cost")}
                        for index, row in enumerate(details)],
            "costs": [{"row_id": row["row_id"],
                       "fields": row_entries("costs", index, row, f_costs[index], "cost")}
                      for index, row in enumerate(costs)],
            "banks": [{"row_id": row["row_id"],
                       "fields": row_entries("banks", 0, row, f_payee, "cost")}
                      for row in banks],
        },
        "total": {"value": str(total), "fact_id": f_total},
        # 2026-10-24 16:00 首次实填在 _initial_applicant 被 COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED
        # 阻断（页面默认申请人陈晶≠计划申请人徐亮，选择组织需工号消歧）；identity 按观测证据补齐：
        # creator 陈晶/运动表现研究部 来自本次 run 20261024-160024-8502f91d blocked_readback 实页观测。
        "identity": {
            "applicant_employee_id": {"value": snapshot["applicant"]["appliedBy"],
                                      "fact_id": f_employee_id, "locator": "/applicant/appliedBy"},
            "creator_name": {"value": "陈晶", "fact_id": f_creator, "locator": "/createdName"},
            "creator_department": {"value": "运动表现研究部", "fact_id": f_creator,
                                   "locator": "/createdDeptName"},
        },
    }
    blueprint_ref = register_derived(manifest_path, "plan/blueprint.json", blueprint,
                                     role="run_evidence", sources=[material_sha],
                                     generated_by="round7-chain/blueprint_assembly")
    log("blueprint_assembled", artifact="plan/blueprint.json", sha256=blueprint_ref,
        identity={"applicant_employee_id": blueprint["identity"]["applicant_employee_id"]["value"],
                  "basis": "template appliedBy（双源印证）+ 本次实页 creator 观测（system_observation 工件）"},
        table_rows={table: len(rows) for table, rows in blueprint["tables"].items()})

    generated = generate_fill_plan(facts, blueprint, base_dir=RUN)
    plan = generated["plan"]
    plan["test_context"] = {"purpose": "授权历史业务回放的 travel 真实闭环（round-7，只填不存）",
                            "round": ROUND,
                            "authorization_path": "originals/replay_r7.json",
                            "authorization_sha256": material_sha}
    issues = validate_plan(plan, expected_operator="陈晶", verify_sources=True, base_dir=RUN)
    assert not issues, issues
    plan_path = RUN / "fill_plan_r7.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact("plan_validation.json", {"status": "PLAN_VALIDATED", "issues": [],
                                      "plan_sha256": file_hash(plan_path),
                                      "sources": len(plan["sources"]),
                                      "reconciliation": generated["reconciliation"]})
    log("plan_ready", plan="fill_plan_r7.json", sha256=file_hash(plan_path),
        plan_hash=plan_hash(plan), sources=len(plan["sources"]), status="PLAN_READY")

    # ---- 阶段 7 执行就绪（真实 validate-only 子进程）
    evidence = operator_from_session_record(SESSION_RECORD)
    assert evidence is not None, "会话记录无已认证 principal，操作人证据缺失"
    readiness = execution_ready(plan_path, evidence)
    artifact("execution_ready.json", readiness)
    assert readiness["status"] == "EXECUTION_READY", readiness
    log("execution_ready", status="EXECUTION_READY", operator=evidence["name"],
        source=evidence["source"], validate_only=True, browser_launched=False,
        suggested_command=readiness["suggested_command"])

    print(json.dumps({"chain": "COMPLETE", "run": RUN.name, "plan": str(plan_path),
                      "plan_sha256": file_hash(plan_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
