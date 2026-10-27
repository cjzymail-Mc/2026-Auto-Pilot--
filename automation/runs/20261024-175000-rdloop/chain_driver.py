"""Round-8 rdloop：agent 自驱全链（登记→模板缓存定向→提取复核→事实→对账→矩阵→计划→执行就绪）。

材料为用户授权历史回放 rd_materials（authorized_replay_facts.json 只读复制，
lineage 授权 automation/type-extension/live-test-authorization.json sha 绑定一致；
test_only/not_new_expenses/no_invoice_rule 原文随件）。事实/决策由 agent 阅读材料后
经 FactSet/build_reuse_matrix API 构造；计划由 generate_fill_plan 生成并当场过
validate_plan(verify_sources=True)。不预写 facts_payload/blueprint 塞入口。
模板源取缓存快照（type-view-15426094780，lineage template_sha256 MATCH）——
census 语料仅含 travel，缓存快照直接绑定（合同 ctr-633d23ae §1，自主裁决①）。
events 字段格式与 fill run 统一（event 键）。
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
                         operator_from_session_record, register_matrix, register_request)

EVENTS = RUN / "events.jsonl"
SESSION_RECORD = ROOT / "automation/.local-session/6f998b924ecf48b0b8c2b6ea16ef54ba/session_record.json"
TEMPLATE_NUMBER = "15426104120"
TASK_ID = "20261024-r8-rdloop-15426104120"
ROUND = "8"


def log(event, **fields):
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields},
                      ensure_ascii=False)
    with EVENTS.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    print(line, flush=True)


def artifact(relative, payload):
    path = RUN / relative
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"relative_path": relative, "sha256": file_hash(path)}


def main():
    original = RUN / "originals/replay_rd_r8.json"
    for stale in ("materials",):
        target = RUN / stale
        if target.exists():
            shutil.rmtree(target)
    for name in ("fill_plan_r8.json", "plan_validation.json", "execution_ready.json"):
        target = RUN / name
        if target.exists():
            target.unlink()
    material_sha = file_hash(original)
    material = json.loads(original.read_text(encoding="utf-8"))
    snapshot_path = RUN / "template_snapshot.json"
    template_block = {"biz_number": TEMPLATE_NUMBER,
                      "captured_at": json.loads(snapshot_path.read_text(encoding="utf-8"))["captured_at"],
                      "sha256": file_hash(snapshot_path), "snapshot_path": "template_snapshot.json"}
    assert template_block["sha256"] == material["replay_lineage"]["template_sha256"], "模板快照与材料 lineage 漂移"
    log("chain_start", run=RUN.name, material_sha256=material_sha,
        material_basis="授权历史回放 rd_materials（live-test-authorization user_statement 授权）只读复制",
        template_basis="缓存快照 type-view-15426104120（lineage sha MATCH）")

    manifest_path = prepare_dual_materials(RUN / "originals", RUN / "materials")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues = validate_dual_manifest(manifest, base_dir=RUN)
    assert not issues, issues
    log("prepare_dual_materials", manifest=str(manifest_path),
        originals=len(manifest["files"]), derived=len(manifest["derived_files"]))

    request = register_request({
        "template_biz_number": TEMPLATE_NUMBER,
        "materials_dir": str(RUN / "originals"),
        "statement": "研发材料费报销（授权历史回放）：外购样品 18 项物品档案行、4 行预算明细、"
                     "四名收款人分摊，合计 9935.16；本轮 fill_only 只填不存。",
        "declared_category": "研发材料费",
        "relation_refs": [],
    }, manifest_path=manifest_path)
    assert request["status"] == "REGISTERED", request
    log("register_request", status="REGISTERED",
        artifact=request["artifact"]["relative_path"], sha256=request["artifact"]["sha256"])

    # 模板缓存定向绑定（census 语料仅 travel；快照 sha 与材料 lineage 双向核对已过）
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["document_type"] == "rd_materials" and snapshot["biz_number"] == TEMPLATE_NUMBER
    assert snapshot["header"]["submitType"] == "11", snapshot["header"]["submitType"]  # 研发材料费类别码（实测）
    log("template_cached_snapshot_bound", status="RESOLVED", document_type="rd_materials",
        uuid=snapshot["uuid"], snapshot_sha256=template_block["sha256"],
        basis="type-view 缓存快照+lineage sha MATCH（合同§1 自主裁决①）")

    details, products = material["tables"]["details"], material["tables"]["products"]
    banks = material["tables"]["banks"]
    detail_sum = sum((Decimal(row["fields"]["cost"]) for row in details), Decimal("0"))
    product_sum = sum((Decimal(row["fields"]["price"]) for row in products), Decimal("0"))
    bank_sum = sum((Decimal(row["fields"]["cost"]) for row in banks), Decimal("0"))
    total = Decimal(material["header"]["totalCost"])
    assert detail_sum == product_sum == bank_sum == total, (detail_sum, product_sum, bank_sum, total)
    assert material["test_only"] is True and material["not_new_expenses"] is True
    review = {
        "schema_version": "1.0", "kind": "agent_extraction_review",
        "reviewer": "round8-B-agent", "material_sha256": material_sha,
        "material_kind": "authorized_historical_replay_json",
        "extracted": {
            "applicant": {key: "/applicant/{0}".format(key) for key in material["applicant"]},
            "header": {key: "/header/{0}".format(key) for key in material["header"]},
            "tables": {table: ["/tables/{0}/{1}/fields/{2}".format(table, index, column)
                               for index, row in enumerate(rows) for column in row["fields"]]
                       for table, rows in material["tables"].items()},
            "authorization_semantics": ["/test_only", "/not_new_expenses", "/no_invoice_rule",
                                        "/replay_lineage/authorization_sha256",
                                        "/table_applicability/relations/reason",
                                        "/table_applicability/costs/reason"],
        },
        "mechanical_crosscheck": {
            "details_sum": str(detail_sum), "products_sum": str(product_sum), "banks_sum": str(bank_sum),
            "header_totalCost": str(total), "closure": "四向闭合（details=products=banks=totalCost）",
        },
        "review_notes": [
            "结构化回放 JSON（非扫描件）：无 OCR 层，字段值由 JSON 指针直接定位。",
            "test_only/not_new_expenses/no_invoice_rule 语义随件携带未删除；授权链 live-test-"
            "authorization.json sha 经 lineage 绑定一致（allow_save=false）。",
            "模板缓存快照 sha 与 lineage MATCH；applicant=登录默认陈晶（preserve_system_defaults），"
            "无需 identity 选择器（区别 round-7）。",
        ],
    }
    review_ref = register_derived(manifest_path, "reviewed/replay_agent_review.json", review,
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="round8-rdloop/agent_extraction_review")
    log("agent_extraction_review", artifact="reviewed/replay_agent_review.json", sha256=review_ref,
        rows={"details": len(details), "products": len(products), "banks": len(banks)},
        closure=str(total))

    hashes = {"originals/replay_rd_r8.json": material_sha}
    locator = "originals/replay_rd_r8.json#{0}"
    facts = FactSet(business_ref=TASK_ID, bindings={"originals/replay_rd_r8.json": material_sha})
    f_applicant = facts.add("business_identity", source="material_extraction",
                            value=material["applicant"], locator=locator.format("/applicant"),
                            input_hashes=hashes, note="回放材料申请人=登录默认（preserve_system_defaults）")
    f_header = facts.add("scope", source="material_extraction", value={
        key: material["header"][key] for key in
        ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType", "submitType", "description")
    }, locator=locator.format("/header"), input_hashes=hashes, note="单头显示值（转账/人民币/研发材料费…）")
    f_total = facts.add("total", source="deterministic_computation",
                        value={"amount": str(total)},
                        locator="derived:total#details-cost-sum",
                        derivation="details 4 行 cost 求和；与 products 18 行 price/banks 4 行及材料 totalCost 四方闭合")
    f_details = [facts.add_expense(row["fields"]["cost"], source="material_extraction",
                                   layer="summary", category=row["fields"]["reimItem"],
                                   value_extra={key: row["fields"][key] for key in
                                                ("reimItem", "digest", "budgetDeptName", "budgetNo",
                                                 "subjectName", "budgetItemName")},
                                   locator=locator.format("/tables/details/{0}".format(index)),
                                   input_hashes=hashes)
                 for index, row in enumerate(details)]
    f_products = [facts.add_expense(row["fields"]["price"], source="material_extraction",
                                     layer="detail", category=row["fields"]["code"],
                                     value_extra={key: row["fields"][key] for key in
                                                  ("code", "name", "purchaser", "description")},
                                     locator=locator.format("/tables/products/{0}".format(index)),
                                     input_hashes=hashes)
                  for index, row in enumerate(products)]
    f_payees = [facts.add_payee(name=row["fields"]["payee"], account=row["fields"]["account"],
                                branch=row["fields"]["bank"], interbank=row["fields"]["bankCode"],
                                amount=row["fields"]["cost"], source="material_extraction",
                                locator=locator.format("/tables/banks/{0}".format(index)),
                                input_hashes=hashes)
                for index, row in enumerate(banks)]
    f_ta_relations = facts.add("scope", source="user_instruction",
                               value={"reason": material["table_applicability"]["relations"]["reason"]},
                               locator=locator.format("/table_applicability/relations/reason"),
                               note="空关联表当次来源理由（材料原文）")
    f_ta_costs = facts.add("scope", source="user_instruction",
                           value={"reason": material["table_applicability"]["costs"]["reason"]},
                           locator=locator.format("/table_applicability/costs/reason"),
                           note="空费用说明表当次来源理由（材料原文；rd 范围=费用说明为空）")
    waiver = material["no_invoice_rule"]
    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/no_invoice_rule"))
               for fact in f_products]  # 主表=products（config primary_expense_table）
    facts_ref = register_derived(manifest_path, "facts/factset.json", facts.to_payload(),
                                 role="run_evidence", sources=[material_sha],
                                 generated_by="round8-rdloop/FactSet")
    log("factset_built", artifact="facts/factset.json", sha256=facts_ref, facts=len(facts),
        kinds={kind: len(facts.by_kind(kind)) for kind in
               ("business_identity", "scope", "expense", "payee_group", "no_invoice_basis", "total")})

    report = reconcile(facts)
    assert not report.blocked, report.to_payload()
    report_ref = register_derived(manifest_path, "facts/reconciliation.json", report.to_payload(),
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="round8-rdloop/reconcile")
    log("reconcile", blocked=False, checks={c.name: c.status for c in report.checks},
        artifact="facts/reconciliation.json", sha256=report_ref)

    decisions = [
        {"group": "form_identity", "field": "document_type", "decision": "identify",
         "template_value": "研发材料费(rd_materials)", "basis": "缓存快照 submitType=研发材料费(11)，与请求声明一致"},
        {"group": "form_identity", "field": "form_structure", "decision": "identify",
         "template_value": "relations/details/costs/banks/products 五表（relations+costs 空）", "basis": "rd 注册结构+材料空表理由"},
        {"group": "current_person", "field": "name", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/name"},
        {"group": "current_person", "field": "company", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/company"},
        {"group": "current_person", "field": "department", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/department", "basis": "登录默认=材料申请人，无需选择器"},
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
    decisions += [{"group": "proven_references", "field": "banks[{0}].payee".format(index),
                   "decision": "replace", "fact_id": f_payees[index],
                   "locator": "/tables/banks/{0}/fields/payee".format(index),
                   "basis": "回放材料收款人（四名收款人分摊）"}
                  for index in range(len(banks))]
    decisions += [
        {"group": "empty_tables", "field": "relations", "decision": "not_applicable",
         "reason": material["table_applicability"]["relations"]["reason"]},
        {"group": "empty_tables", "field": "details", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 4 行预算明细"},
        {"group": "empty_tables", "field": "costs", "decision": "not_applicable",
         "reason": material["table_applicability"]["costs"]["reason"]},
        {"group": "empty_tables", "field": "banks", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 4 行收款信息"},
        {"group": "empty_tables", "field": "products", "decision": "not_applicable",
         "reason": "非空表：本次材料提供 18 行现有档案物品（按完整编号选入，不新造档案）"},
    ]
    matrix = build_reuse_matrix(snapshot, facts, decisions)
    matrix_ref = register_matrix(matrix, manifest_path=manifest_path)
    log("reuse_matrix", artifact=matrix_ref["relative_path"], sha256=matrix_ref["sha256"],
        rows=len(matrix["rows"]))

    fields = ("name", "company", "department", "corpCode", "bizOrign", "budgetYears",
              "payType", "currencyType", "submitType", "description")
    entries = entries_from_matrix(matrix, facts, fields)
    applicant_entries = {key: entries[key] for key in ("name", "company", "department")}
    header_entries = {key: entries[key] for key in
                      ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType",
                       "submitType", "description")}

    def row_entries(table, index, row, fact_id):
        return {column: {"value": row["fields"][column], "fact_id": fact_id,
                         "locator": "/tables/{0}/{1}/fields/{2}".format(table, index, column)}
                for column in row["fields"]}

    blueprint = {
        "document_type": "rd_materials", "task_id": TASK_ID, "operator": "陈晶",
        "template": template_block,
        "materials": {"manifest_path": str(manifest_path)},
        "authorization": {
            "mode": "fill_only", "task_id": TASK_ID, "allow_submit": False,
            "statement": "授权历史业务回放只填不存练习：live-test-authorization（用户原话"
                         "“你从历史表单中挑选一些复杂度高的单据作为模板，进行真实填写测试，"
                         "我给你授权，继续”，allow_save=false），test_only/not_new_expenses 随件；"
                         "新页真实填写后不保存、不提交、不产生新报销。",
        },
        "not_applicable": [],
        "amount_rules": {"costs": "not_applicable",
                       "costs_reason": material["table_applicability"]["costs"]["reason"],
                       "cost_amount_semantics": "line_total",
                       "products": "sum", "product_amount_semantics": "line_total"},
        "applicant": applicant_entries,
        "header": header_entries,
        "tables": {
            "relations": [],
            "details": [{"row_id": row["row_id"],
                         "fields": row_entries("details", index, row, f_details[index])}
                        for index, row in enumerate(details)],
            "costs": [],
            "banks": [{"row_id": row["row_id"],
                       "fields": row_entries("banks", index, row, f_payees[index])}
                      for index, row in enumerate(banks)],
            "products": [{"row_id": row["row_id"],
                          "fields": row_entries("products", index, row, f_products[index])}
                         for index, row in enumerate(products)],
        },
        "total": {"value": str(total), "fact_id": f_total},
        "table_applicability": {
            "relations": {"value": material["table_applicability"]["relations"]["reason"],
                          "fact_id": f_ta_relations,
                          "locator": "/table_applicability/relations/reason"},
            "costs": {"value": material["table_applicability"]["costs"]["reason"],
                      "fact_id": f_ta_costs,
                      "locator": "/table_applicability/costs/reason"},
        },
    }
    blueprint_ref = register_derived(manifest_path, "plan/blueprint.json", blueprint,
                                     role="run_evidence", sources=[material_sha],
                                     generated_by="round8-rdloop/blueprint_assembly")
    log("blueprint_assembled", artifact="plan/blueprint.json", sha256=blueprint_ref,
        identity=None, table_rows={table: len(rows) for table, rows in blueprint["tables"].items()})

    generated = generate_fill_plan(facts, blueprint, base_dir=RUN)
    plan = generated["plan"]
    plan["test_context"] = {"purpose": "授权历史业务回放的 rd_materials 真实闭环（round-8，只填不存）",
                            "round": ROUND,
                            "authorization_path": "originals/replay_rd_r8.json",
                            "authorization_sha256": material_sha}
    issues = validate_plan(plan, expected_operator="陈晶", verify_sources=True, base_dir=RUN)
    assert not issues, issues
    plan_path = RUN / "fill_plan_r8.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact("plan_validation.json", {"status": "PLAN_VALIDATED", "issues": [],
                                      "plan_sha256": file_hash(plan_path),
                                      "sources": len(plan["sources"]),
                                      "reconciliation": generated["reconciliation"]})
    log("plan_ready", plan="fill_plan_r8.json", sha256=file_hash(plan_path),
        plan_hash=plan_hash(plan), sources=len(plan["sources"]), status="PLAN_READY")

    evidence = operator_from_session_record(SESSION_RECORD)
    assert evidence is not None, "会话记录无已认证 principal，操作人证据缺失"
    readiness = execution_ready(plan_path, evidence)
    artifact("execution_ready.json", readiness)
    assert readiness["status"] == "EXECUTION_READY", readiness
    log("execution_ready", status="EXECUTION_READY", operator=evidence["name"],
        source=evidence["source"], validate_only=True, browser_launched=False)

    print(json.dumps({"chain": "COMPLETE", "run": RUN.name, "plan": str(plan_path),
                      "plan_sha256": file_hash(plan_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
