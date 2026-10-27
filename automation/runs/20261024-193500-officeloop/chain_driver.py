"""Round-9 officeloop：02 office_supplies 离线链首件（config→注册→合成材料→validate-only）。

零真实页面（合同 ctr-15712bcb §1：本轮零浏览器动作）。合成材料明示 synthetic、
不入业务 manifest；值取研究证据（reimItem 02001 等，见 value_evidence）。
events 分段标记（mc-expert 观察①落地）：chain_segment_start 由既有 events 行数推导段序号。
"""
import json
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
                         register_matrix, register_request)
from bpm_types import check_template_type, resolve_type       # noqa: E402

EVENTS = RUN / "events.jsonl"
TEMPLATE_NUMBER = "15426101596"
TASK_ID = "20261024-r9-officeloop-15426101596"
ROUND = "9"


def log(event, **fields):
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields},
                      ensure_ascii=False)
    with EVENTS.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    print(line, flush=True)


def segment_index():
    """分段标记：由既有 events 行数推导（append-only，不回改历史段）。"""
    if not EVENTS.exists():
        return 1
    with EVENTS.open("r", encoding="utf-8") as stream:
        return sum(1 for _ in stream) + 1


def main():
    import shutil
    for stale in ("materials",):
        target = RUN / stale
        if target.exists():
            shutil.rmtree(target)
    for name in ("fill_plan_r9.json", "execution_ready.json"):
        target = RUN / name
        if target.exists():
            target.unlink()
    original = RUN / "originals/synthetic_office_r9.json"
    material_sha = file_hash(original)
    material = json.loads(original.read_text(encoding="utf-8"))
    snapshot_path = RUN / "template_snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    template_block = {"biz_number": TEMPLATE_NUMBER,
                      "captured_at": snapshot["captured_at"],
                      "sha256": file_hash(snapshot_path), "snapshot_path": "template_snapshot.json"}
    check_template_type(snapshot, "office_supplies")
    resolve_type("office_supplies")  # 注册绑定（含 invoice_policy 形状校验）
    log("chain_segment_start", segment=segment_index(), material_sha256=material_sha,
        material_basis="合成离线链材料（synthetic=true，不入业务 manifest；值取研究证据）",
        template_basis="研究 raw 只读派生快照 raw_15426101596（uuid/biz_number 原值）")

    manifest_path = prepare_dual_materials(RUN / "originals", RUN / "materials")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    issues = validate_dual_manifest(manifest, base_dir=RUN)
    assert not issues, issues
    log("prepare_dual_materials", manifest=str(manifest_path),
        originals=len(manifest["files"]), derived=len(manifest["derived_files"]))

    request = register_request({
        "template_biz_number": TEMPLATE_NUMBER,
        "materials_dir": str(RUN / "originals"),
        "statement": "低值易耗品、办公用品采购报销（合成离线链验证）：1 行明细+1 行费用说明+"
                     "三名收款人分摊，合计 1234.56；synthetic/test_only，不填真实页面。",
        "declared_category": "低值易耗品、办公用品采购",
        "relation_refs": [],
    }, manifest_path=manifest_path)
    assert request["status"] == "REGISTERED", request
    log("register_request", status="REGISTERED",
        artifact=request["artifact"]["relative_path"], sha256=request["artifact"]["sha256"])

    details, costs, banks = (material["tables"][k] for k in ("details", "costs", "banks"))
    detail_sum = sum((Decimal(r["fields"]["cost"]) for r in details), Decimal("0"))
    cost_sum = sum((Decimal(r["fields"]["cost"]) for r in costs), Decimal("0"))
    bank_sum = sum((Decimal(r["fields"]["cost"]) for r in banks), Decimal("0"))
    total = Decimal(material["header"]["totalCost"])
    assert detail_sum == cost_sum == bank_sum == total, (detail_sum, cost_sum, bank_sum, total)
    assert material["synthetic"] is True and material["test_only"] is True
    review = {
        "schema_version": "1.0", "kind": "agent_extraction_review",
        "reviewer": "round9-B-agent", "material_sha256": material_sha,
        "material_kind": "synthetic_offline_chain_fixture",
        "synthetic_disclosure": "合成材料明示测试用；值证据在材料 value_evidence；不入业务 manifest",
        "extracted": {
            "applicant": {k: "/applicant/{0}".format(k) for k in material["applicant"]},
            "header": {k: "/header/{0}".format(k) for k in material["header"]},
            "tables": {t: ["/tables/{0}/{1}/fields/{2}".format(t, i, c)
                           for i, row in enumerate(rows) for c in row["fields"]]
                       for t, rows in material["tables"].items()},
            "table_applicability": ["/table_applicability/relations/reason"],
        },
        "mechanical_crosscheck": {
            "details_sum": str(detail_sum), "costs_sum": str(cost_sum), "banks_sum": str(bank_sum),
            "header_totalCost": str(total), "closure": "四向闭合（details=costs=banks=totalCost）",
        },
        "review_notes": [
            "模板快照为研究 raw 派生（uuid/biz_number/fetched_at 原值，header.submitType 保留实测码 02）。",
            "plan 级 relations 保持空（裁决①：bpm_plan 非 travel 非空 relations 拒绝维持）。",
            "文档级 invoice：config invoice_policy=document_level（声明级通道，裁决②）；"
            "生成器现行免票机制仍为行级 no_invoice 基础事实。",
        ],
    }
    review_ref = register_derived(manifest_path, "reviewed/synthetic_agent_review.json", review,
                                  role="run_evidence", sources=[material_sha],
                                  generated_by="round9-officeloop/agent_extraction_review")
    log("agent_extraction_review", artifact="reviewed/synthetic_agent_review.json", sha256=review_ref,
        rows={"details": len(details), "costs": len(costs), "banks": len(banks)})

    hashes = {"originals/synthetic_office_r9.json": material_sha}
    locator = "originals/synthetic_office_r9.json#{0}"
    facts = FactSet(business_ref=TASK_ID,
                    bindings={"originals/synthetic_office_r9.json": material_sha})
    f_applicant = facts.add("business_identity", source="material_extraction",
                            value=material["applicant"], locator=locator.format("/applicant"),
                            input_hashes=hashes, note="合成材料申请人=登录默认形态")
    f_header = facts.add("scope", source="material_extraction", value={
        k: material["header"][k] for k in
        ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType", "submitType", "description")
    }, locator=locator.format("/header"), input_hashes=hashes, note="单头显示值（转账/人民币/低值易耗品、办公用品采购）")
    f_total = facts.add("total", source="deterministic_computation",
                        value={"amount": str(total)}, locator="derived:total#details-cost-sum",
                        derivation="details 1 行 cost 求和；与 costs 1 行/banks 3 行及合成 totalCost 四方闭合")
    f_details = [facts.add_expense(r["fields"]["cost"], source="material_extraction",
                                   layer="summary", category=r["fields"]["reimItem"],
                                   value_extra={k: r["fields"][k] for k in
                                                ("reimItem", "digest", "budgetDeptName", "budgetNo",
                                                 "subjectName", "budgetItemName", "budgetOwner")},
                                   locator=locator.format("/tables/details/{0}".format(i)),
                                   input_hashes=hashes)
                 for i, r in enumerate(details)]
    f_costs = [facts.add_expense(r["fields"]["cost"], source="material_extraction",
                                 layer="detail", category=r["fields"]["project"],
                                 date=r["fields"]["startDate"],
                                 value_extra={k: r["fields"][k] for k in
                                              ("project", "startDate", "endDate", "projectPlace",
                                               "count", "reason")},
                                 locator=locator.format("/tables/costs/{0}".format(i)),
                                 input_hashes=hashes)
               for i, r in enumerate(costs)]
    f_payees = [facts.add_payee(name=r["fields"]["payee"], account=r["fields"]["account"],
                                branch=r["fields"]["bank"], interbank=r["fields"]["bankCode"],
                                amount=r["fields"]["cost"], source="material_extraction",
                                locator=locator.format("/tables/banks/{0}".format(i)),
                                input_hashes=hashes)
                for i, r in enumerate(banks)]
    f_ta_relations = facts.add("scope", source="user_instruction",
                               value={"reason": material["table_applicability"]["relations"]["reason"]},
                               locator=locator.format("/table_applicability/relations/reason"),
                               note="空关联表当次来源理由（合成材料原文；裁决①）")
    waiver = material["no_invoice_rule"]
    f_basis = [facts.add_no_invoice_basis(fact, reason=waiver, source="user_instruction",
                                          locator=locator.format("/no_invoice_rule"))
               for fact in f_costs]
    facts_ref = register_derived(manifest_path, "facts/factset.json", facts.to_payload(),
                                 role="run_evidence", sources=[material_sha],
                                 generated_by="round9-officeloop/FactSet")
    log("factset_built", artifact="facts/factset.json", sha256=facts_ref, facts=len(facts),
        kinds={k: len(facts.by_kind(k)) for k in
               ("business_identity", "scope", "expense", "payee_group", "no_invoice_basis", "total")})

    report = reconcile(facts)
    assert not report.blocked, report.to_payload()
    register_derived(manifest_path, "facts/reconciliation.json", report.to_payload(),
                     role="run_evidence", sources=[material_sha],
                     generated_by="round9-officeloop/reconcile")
    log("reconcile", blocked=False, checks={c.name: c.status for c in report.checks})

    decisions = [
        {"group": "form_identity", "field": "document_type", "decision": "identify",
         "template_value": "低值易耗品、办公用品采购(office_supplies)", "basis": "注册表+census 码 02（实测）"},
        {"group": "form_identity", "field": "form_structure", "decision": "identify",
         "template_value": "relations/details/costs/banks 四表（relations 空）",
         "basis": "office_supplies 注册结构+合成材料空表理由"},
        {"group": "current_person", "field": "name", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/name"},
        {"group": "current_person", "field": "company", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/company"},
        {"group": "current_person", "field": "department", "decision": "replace", "fact_id": f_applicant,
         "locator": "/applicant/department"},
        {"group": "current_business", "field": "description", "decision": "replace", "fact_id": f_header,
         "locator": "/header/description"},
    ] + [
        {"group": "stable_context", "field": k, "decision": "replace", "fact_id": f_header,
         "locator": "/header/{0}".format(k)} for k in
        ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType", "submitType")
    ] + [
        {"group": "proven_references", "field": "banks[{0}].payee".format(i),
         "decision": "replace", "fact_id": f_payees[i],
         "locator": "/tables/banks/{0}/fields/payee".format(i),
         "basis": "合成材料收款人（三名收款人分摊）"} for i in range(len(banks))
    ] + [
        {"group": "empty_tables", "field": "relations", "decision": "not_applicable",
         "reason": material["table_applicability"]["relations"]["reason"]},
        {"group": "empty_tables", "field": "details", "decision": "not_applicable",
         "reason": "非空表：合成材料提供 1 行报销明细"},
        {"group": "empty_tables", "field": "costs", "decision": "not_applicable",
         "reason": "非空表：合成材料提供 1 行费用说明"},
        {"group": "empty_tables", "field": "banks", "decision": "not_applicable",
         "reason": "非空表：合成材料提供 3 行收款信息"},
    ]
    matrix = build_reuse_matrix(snapshot, facts, decisions)
    matrix_ref = register_matrix(matrix, manifest_path=manifest_path)
    log("reuse_matrix", artifact=matrix_ref["relative_path"], sha256=matrix_ref["sha256"],
        rows=len(matrix["rows"]))

    fields = ("name", "company", "department", "corpCode", "bizOrign", "budgetYears",
              "payType", "currencyType", "submitType", "description")
    entries = entries_from_matrix(matrix, facts, fields)
    applicant_entries = {k: entries[k] for k in ("name", "company", "department")}
    header_entries = {k: entries[k] for k in
                      ("corpCode", "bizOrign", "budgetYears", "payType", "currencyType",
                       "submitType", "description")}

    def row_entries(table, index, row, fact_id):
        return {c: {"value": row["fields"][c], "fact_id": fact_id,
                    "locator": "/tables/{0}/{1}/fields/{2}".format(table, index, c)}
                for c in row["fields"]}

    blueprint = {
        "document_type": "office_supplies", "task_id": TASK_ID, "operator": "陈晶",
        "template": template_block,
        "materials": {"manifest_path": str(manifest_path)},
        "authorization": {
            "mode": "fill_only", "task_id": TASK_ID, "allow_submit": False,
            "statement": "合成离线链验证（round-9，零真实页面）：synthetic/test_only/not_new_expenses；"
                         "仅 validate-only 子进程，不填真实页面、不保存不提交。",
        },
        "not_applicable": [],
        "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
        "applicant": applicant_entries,
        "header": header_entries,
        "tables": {
            "relations": [],
            "details": [{"row_id": r["row_id"],
                         "fields": row_entries("details", i, r, f_details[i])}
                        for i, r in enumerate(details)],
            "costs": [{"row_id": r["row_id"],
                       "fields": row_entries("costs", i, r, f_costs[i])}
                      for i, r in enumerate(costs)],
            "banks": [{"row_id": r["row_id"],
                       "fields": row_entries("banks", i, r, f_payees[i])}
                      for i, r in enumerate(banks)],
        },
        "total": {"value": str(total), "fact_id": f_total},
        "table_applicability": {
            "relations": {"value": material["table_applicability"]["relations"]["reason"],
                          "fact_id": f_ta_relations,
                          "locator": "/table_applicability/relations/reason"},
        },
    }
    blueprint_ref = register_derived(manifest_path, "plan/blueprint.json", blueprint,
                                     role="run_evidence", sources=[material_sha],
                                     generated_by="round9-officeloop/blueprint_assembly")
    log("blueprint_assembled", artifact="plan/blueprint.json", sha256=blueprint_ref,
        table_rows={t: len(rows) for t, rows in blueprint["tables"].items()})

    try:
        generated = generate_fill_plan(facts, blueprint, base_dir=RUN)
    except Exception as exc:
        log("plan_generation_failed", issues=getattr(exc, "issues", None) or str(exc)[:800])
        raise
    plan = generated["plan"]
    plan["test_context"] = {"purpose": "02 office_supplies 离线链首件（round-9，零真实页面；合成材料 synthetic/test_only）",
                            "round": ROUND,
                            "authorization_path": "originals/synthetic_office_r9.json",
                            "authorization_sha256": material_sha}
    issues = validate_plan(plan, expected_operator="陈晶", verify_sources=True, base_dir=RUN)
    assert not issues, issues
    plan_path = RUN / "fill_plan_r9.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    log("plan_ready", plan="fill_plan_r9.json", sha256=file_hash(plan_path),
        plan_hash=plan_hash(plan), sources=len(plan["sources"]), status="PLAN_READY")

    evidence = {"name": "陈晶", "source": "user_policy",
                "basis": "合成离线链（零浏览器）：操作人取登录默认形态用户策略值"}
    readiness = execution_ready(plan_path, evidence)
    assert readiness["status"] == "EXECUTION_READY", readiness
    (RUN / "execution_ready.json").write_text(json.dumps(readiness, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    log("execution_ready", status="EXECUTION_READY", operator=evidence["name"],
        validate_only=True, browser_launched=False,
        plan_hash=readiness["plan"]["plan_hash"])

    print(json.dumps({"chain": "COMPLETE", "run": RUN.name, "plan": str(plan_path),
                      "plan_sha256": file_hash(plan_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
