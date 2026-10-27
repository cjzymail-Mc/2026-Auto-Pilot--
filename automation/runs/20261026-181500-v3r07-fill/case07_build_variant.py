# -*- coding: utf-8 -*-
"""V3-R07 CASE-07 执行变体 v1.1 生成器（确定性，可复跑）。

冻结依据：team-task src-c1c5d877 / 合同 ctr-affef776 冻结范围 2；V3 §5.3。
输入（全部只读）：
  - round-6 fill-plan v1.0（automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json）
  - 真实关联控件枚举（本 run attempt_002/evidence/relation_enumeration.json，零选择零保存）
规则：
  1. 种子先验（pre-committed）：seed = sha256("<team_run>-case07")[:16]，在查看枚举结果前即由
     round-7 team_run 派生，不可挑选候选。
  2. 候选 = 枚举默认首屏 20 行（未翻页未检索，探针 scope 声明口径）；排除项 = 已用真实公出单
     12026096668（命中则先移除再 randrange；本次核验不在列，无移除）。
  3. chosen_index = random.Random(seed).randrange(len(candidates))；除 tables.relations/
     oa_test_relations/sources(+4)/materials/not_applicable[0]/task_id/authorization/
     test_context 外，任何值与 v1.0 零偏离（本脚本逐路径断言）。
输出（落 run 根）：case07-task-material.json、materials-manifest.json、fill-plan-v11.json、
  variant-diff.json、variant-validate.json；校验 = jsonschema + bpm_plan.validate_plan
  （verify_sources=True）+ coverage F>R 复验（时序入 events.jsonl）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

RUN = ROOT / "automation/runs/20261026-181500-v3r07-fill"
V10 = ROOT / "automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json"
ENUM = RUN / "attempt_002/evidence/relation_enumeration.json"
TEAM_RUN = "20261026-180546-c1c5d877"
EXCLUDE = "12026096668"  # 已被模板旧单使用的真实公出单，不得重新占用（V3 §5.3）
TASK_ID = "v3r07-case07-fill-20261026"


def sha256f(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def append_event(**kw):
    kw["ts"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")
    with (RUN / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


def flat(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flat(v, f"{prefix}/{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flat(v, f"{prefix}/{i}"))
    else:
        out[prefix] = obj
    return out


def main() -> int:
    from bpm_plan import validate_plan

    plan10 = json.loads(V10.read_text(encoding="utf-8"))
    enum = json.loads(ENUM.read_text(encoding="utf-8"))
    enum_sha = sha256f(ENUM)

    # 1. 候选与排除核验
    assert enum["selection_performed"] is False and enum["bizNumber_after_close"] == "", "枚举不洁净"
    headers = enum["headers"]
    i_num, i_status, i_date, i_person, i_reason = (headers.index("单据编号"), headers.index("单据状态"),
                                                   headers.index("申请日期"), headers.index("申请人"),
                                                   headers.index("公出事由"))
    rows = enum["rows"]
    exclusion_hits = [r for r in rows if r[i_num] == EXCLUDE]
    candidates = [r for r in rows if r[i_num] != EXCLUDE]

    # 2. 种子先验 + RNG
    seed = hashlib.sha256((TEAM_RUN + "-case07").encode("utf-8")).hexdigest()[:16]
    chosen_index = random.Random(seed).randrange(len(candidates))
    chosen = candidates[chosen_index]
    assert chosen[i_person] == "陈晶", "占位候选申请人异常: %s" % chosen[i_person]

    # 3. 任务材料 v1.1（material 源目标；占位关联全部依据入此文件）
    material = {
        "schema_version": "v3r07-case07-task-material-1.0",
        "generated_at": now_iso(),
        "case": "CASE-07 随机测试占位关联（fill_only）",
        "basis": "team-task src-c1c5d877 / 合同 ctr-affef776 冻结范围 2；V3 §5.3",
        "placeholder_relation": {
            "bizTypeName": "公出单",
            "bizNumber": chosen[i_num],
            "nowCost": plan10["header"]["totalCost"],
            "isLast": "是",
            "chosen_row": {"status": chosen[i_status], "applied_date": chosen[i_date],
                           "bizNumber": chosen[i_num], "applicant": chosen[i_person],
                           "reason": chosen[i_reason]},
            "selection": {
                "method": "random.Random(seed).randrange",
                "seed": seed,
                "seed_derivation": "sha256('%s-case07')[:16]（team_run 派生，先验提交，先于枚举查看）" % TEAM_RUN,
                "enumeration_path": str(ENUM),
                "enumeration_sha256": enum_sha,
                "enumeration_scope": enum["scope"],
                "total_available": 76, "candidates_count": len(candidates),
                "exclusion": {"excluded_number": EXCLUDE, "hits_in_candidates": len(exclusion_hits),
                              "policy": "命中则先移除再 randrange；本次不在列，无移除"},
                "chosen_index": chosen_index,
            },
            "nowCost_semantics": "关联行 nowCost 合计 == 应报总额 totalCost（单行=1924.93；旧单与 demo 同口径闭合）",
        },
        "separation": "与 actual_trip_matches（automation/runs/20261026-143340-v3r04-case03/，12 MATCHED/15 NO_MATCH）"
                      "两套数据分开建模、核验、报告；占位选中对象仅为本案例 fill_only 测试占位，不冒充真实逐票对照结论，"
                      "不改动模板旧单关联，不重新占用已用真实公出单 %s；绑定本案例及 fill_only。" % EXCLUDE,
    }
    mat_path = RUN / "case07-task-material.json"
    mat_path.write_text(json.dumps(material, ensure_ascii=False, indent=2), encoding="utf-8")
    mat_sha = sha256f(mat_path)

    # 4. manifest v1.1 = round-6 上游 5 件 + 本轮任务材料 + 枚举 JSON
    man10 = json.loads((ROOT / "automation/runs/20261026-172300-v3r06-template-plan/materials-manifest.json")
                       .read_text(encoding="utf-8"))
    files = [dict(f) for f in man10["files"]]

    def _entry(p: Path, sha: str) -> dict:
        return {"material_id": "sha256:" + sha, "path": str(p),
                "relative_path": str(p.relative_to(ROOT / "automation/runs")).replace("\\", "/"),
                "sha256": sha, "size_bytes": p.stat().st_size, "duplicate_paths": []}

    files += [_entry(mat_path, mat_sha), _entry(ENUM, enum_sha)]
    manifest = {"schema_version": man10["schema_version"], "root": man10["root"], "files": files}
    man_path = RUN / "materials-manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. v1.1 = v1.0 深拷贝 + 声明范围内的唯四改动簇
    plan = copy.deepcopy(plan10)
    plan["task_id"] = TASK_ID
    plan["authorization"] = dict(plan10["authorization"])
    plan["authorization"]["task_id"] = TASK_ID
    plan["authorization"]["statement"] = (
        "V3 round 7（合同 ctr-affef776 冻结范围 1–5）：以 round-6 fill-plan v1.0 为基线生成执行变体 v1.1；"
        "正式入口真实填写全部表与业务行（header+details 2+costs 20+banks 1+测试占位关联 1 行）；"
        "fill_only 不保存不提交；占位选择若产生即时持久占用立即停止并如实报告（V3 §5.3 停止条款）。")
    plan["test_context"] = dict(plan10["test_context"])
    plan["test_context"]["purpose"] = ("V3-R07 CASE-07 正式入口真实填写（fill_only）+ 受限随机测试占位关联；"
                                       "覆盖门槛 F>R 已复验（见本 run events）")
    plan["test_context"]["round"] = "7"
    plan["not_applicable"] = list(plan10["not_applicable"])
    plan["not_applicable"][0] = (
        "relations：本轮 CASE-07 在真实 OA 关联表中建立 1 条受限随机测试占位行（oa_test_relations 声明，"
        "test_placeholder=true；来源=真实关联控件默认首屏枚举，方法 random.Random(seed).randrange、种子先验记录在案）；"
        "原对应公出单 %s 已被模板旧单使用，不复用不重新占用；真实逐票对照结论独立见 actual_trip_matches，"
        "占位对象零冒充。" % EXCLUDE)
    plan["tables"] = dict(plan10["tables"])
    plan["tables"]["relations"] = [{"row_id": "case07-relations-1", "fields": {
        "bizTypeName": "公出单", "bizNumber": chosen[i_num],
        "nowCost": plan10["header"]["totalCost"], "isLast": "是"}}]
    plan["sources"] = dict(plan10["sources"])
    for prop, locator in (("bizTypeName", "/placeholder_relation/bizTypeName"),
                          ("bizNumber", "/placeholder_relation/bizNumber"),
                          ("nowCost", "/placeholder_relation/nowCost"),
                          ("isLast", "/placeholder_relation/isLast")):
        plan["sources"]["/tables/relations/0/fields/" + prop] = {
            "kind": "material", "path": str(mat_path), "locator": locator, "sha256": mat_sha}
    plan["oa_test_relations"] = {
        "test_placeholder": True,
        "purpose": "CASE-07 随机测试占位关联：原对应公出单 %s 已被模板旧单使用，本案例 fill_only 允许占位"
                   "（V3 §5.3；合同 ctr-affef776 冻结范围 2）" % EXCLUDE,
        "selection": {"method": "random.Random(seed).randrange", "seed": seed,
                      "enumeration_path": str(ENUM), "enumeration_sha256": enum_sha,
                      "candidates_count": len(candidates), "chosen_index": chosen_index},
        "separation": material["separation"],
        "row_ids": ["case07-relations-1"]}
    plan["materials"] = dict(plan10["materials"])
    plan["materials"]["manifest_path"] = str(man_path)
    plan["materials"]["manifest_sha256"] = sha256f(man_path)

    # 6. 零偏离断言：除声明改动簇外逐路径一致
    ALLOWED_PREFIXES = ("/task_id", "/authorization", "/test_context", "/not_applicable/0",
                        "/tables/relations", "/oa_test_relations", "/sources//tables/relations/",
                        "/materials/manifest_path", "/materials/manifest_sha256")
    f10, f11 = flat(plan10), flat(plan)
    drift = {k for k in set(f10) ^ set(f11) | {k for k in f10 if k in f11 and f10[k] != f11[k]}
             if not any(k == a or k.startswith(a) for a in ALLOWED_PREFIXES)}
    if drift:
        raise SystemExit("v1.1 偏离 v1.0 声明范围: %s" % sorted(drift))

    v11_path = RUN / "fill-plan-v11.json"
    v11_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # 7. 校验：jsonschema + validate_plan(verify_sources=True) + coverage F>R 复验
    import jsonschema
    schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(plan, schema)
    issues = validate_plan(plan, "陈晶", verify_sources=True)
    cov = plan["coverage"]
    F, R = Decimal(cov["F_coverage_total"]), Decimal(cov["R_reimburse"])
    costs_sum = sum((Decimal(r["fields"]["cost"]) for r in plan["tables"]["costs"]), Decimal(0))
    coverage_ok = F > R and costs_sum == Decimal(plan["header"]["totalCost"]) == R
    validate_summary = {"schema": "PASS", "validate_plan_issues": issues,
                        "coverage_recheck": {"F": str(F), "R": str(R), "F_gt_R": F > R,
                                             "costs_sum": str(costs_sum),
                                             "totalCost": plan["header"]["totalCost"],
                                             "pass": coverage_ok},
                        "v11_sha256": sha256f(v11_path),
                        "plan_sha256_v10": sha256f(V10)}
    (RUN / "variant-validate.json").write_text(json.dumps(validate_summary, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    if issues or not coverage_ok:
        raise SystemExit("validate failed: issues=%s coverage_ok=%s" % (issues, coverage_ok))

    diff = {
        "variant": "v1.1", "baseline": str(V10), "baseline_sha256": sha256f(V10),
        "generated_at": now_iso(), "allowed_change_clusters": list(ALLOWED_PREFIXES),
        "zero_drift_outside_clusters": True,
        "relations_placeholder": {"row": plan["tables"]["relations"][0],
                                  "chosen_index": chosen_index, "seed": seed,
                                  "candidates_count": len(candidates),
                                  "exclusion_hits": len(exclusion_hits)},
        "task_material": {"path": str(mat_path), "sha256": mat_sha},
        "manifest": {"path": str(man_path), "sha256": sha256f(man_path), "files": len(files)},
        "v11_path": str(v11_path), "v11_sha256": sha256f(v11_path),
    }
    (RUN / "variant-diff.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    append_event(event="variant_v11_built", baseline_sha256=diff["baseline_sha256"],
                 v11_sha256=diff["v11_sha256"], task_material_sha256=mat_sha,
                 manifest_sha256=diff["manifest"]["sha256"], seed=seed,
                 candidates=len(candidates), chosen_index=chosen_index,
                 chosen_biz_number=chosen[i_num], exclusion_hits=len(exclusion_hits),
                 validate_issues=0, coverage_recheck_pass=coverage_ok)
    print(json.dumps({"status": "VARIANT_V11_OK", "chosen": chosen[i_num], "seed": seed,
                      "chosen_index": chosen_index, "candidates": len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
