"""W01 用户请求与模板决策：请求登记 → 缓存定向模板核对+类别识别 → 未知类别只读识别 → 复用/替换矩阵。

链路定位（全部离线，零网络）：
- 请求登记（W01a）：结构化请求记录经 `register_derived` 以 role=user_request 落双根
  manifest 派生根（版本化、哈希入 manifest、sources=本次原件哈希）；记录显式携带
  user_instruction 语义标注。缺必要素（模板单号/材料定位/业务说明）返回 NEEDS_INPUT
  附 GAP_FIELDS 形状结构化缺口，不猜、不落盘。
- 模板核对（W01b）：只用 `bpm_template.cached_template` 按完整单号定向读取缓存 census
  corpus（唯一命中、fetch/children 全 200 强制在彼处）；类别识别走封闭注册
  code/label 映射；请求声明类别与模板类别矛盾 → 集中冲突报告拒绝继续，不悄悄换类。
- 未知类别（D13）：类别不在封闭注册 → 只读识别报告（观察值/注册对照/不支持部分/
  结构证据/登记开发子任务建议，writable=False）；不映射任何已注册类别绕过。live OA
  读模板属 W06 浏览器轮，本模块不新增任何网络访问。
- 复用矩阵（W01c）：逐字段决策 adopt/replace/identify/not_applicable，值一律来自
  FactSet 事实绑定（fact_id），模板值只作识别对照。构造期反例：current_business
  （日期/期间/说明/费用/金额/发票）与 proven_references（关联/档案/收款）禁止 adopt
  模板来源；旧年度预算、模板历史申请人 adopt 须用户政策显式确认。
- 执行串联（W06 D10）：`execution_ready` 把 PLAN_READY 计划经真实
  `fill_once --validate-only` 子进程校验全绿后产出"执行就绪"结论（计划路径+sha256、
  操作人证据、建议执行命令）；操作人来源封闭枚举（本次 user_policy/系统观察），
  模板历史人员不可推导，缺来源判 NEEDS_INPUT 不猜姓名。仅上层编排，
  不改 fill_once 参数语义、不启动浏览器。
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bpm.facts import FactSet
from bpm.materials import dual_hash_sets, register_derived
from bpm.template import CHILDREN, cached_template
from bpm.types import _REGISTRY, TypeConfigError, type_from_category

REQUEST_SCHEMA = "1.0"
MATRIX_SCHEMA = "1.0"

REQUEST_KEYS = {"template_biz_number", "materials_dir", "statement", "declared_category",
                "applicant", "payee_hint", "budget", "relation_refs", "user_policy"}

FIELD_GROUPS = {
    "form_identity": "表单类别/结构/字段和历史填写形态（识别用，不直接抄值）",
    "stable_context": "公司/流程归属/币种/预算及稳定收款资料（本次适用且有依据才复用）",
    "current_person": "当前默认申请人/制单人（按本次用户政策，不被模板历史人员覆盖）",
    "current_business": "日期/期间/业务说明/费用行/金额/发票身份（仅本次材料/系统观察/明确计算）",
    "proven_references": "关联编号/物品档案/收款对象（必须证明属于本次，系统唯一命中）",
    "empty_tables": "空表与不适用字段（本次业务材料和已确认规则解释）",
}
DECISIONS = ("adopt", "replace", "identify", "not_applicable")

# current_business / proven_references 字段值只能来自本次（材料/用户/明确计算）——
# 模板旧日期、旧金额、旧收款、旧关联编号冒充本次值在构造期即拒绝（HISTORICAL_FACT_REUSE
# 在 bpm_plan.validate_plan 还有计划层兜底，此处是矩阵层前置）。
_NO_TEMPLATE_ADOPT_GROUPS = ("current_business", "proven_references")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _gap(reason, *, file=None, locator=None, candidates=None, affected_rows=None):
    """GAP_FIELDS 形状结构化缺口（与 bpm_extraction/fill_once._structured 同形）。"""
    return {"file": file, "locator": locator, "region": None,
            "candidates": list(candidates or []), "reason": reason,
            "affected_rows": list(affected_rows or [])}


def _file_hash(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------ W01a 请求登记

def validate_request(fields):
    """结构校验：返回 (normalized, gaps)；缺必要素时 gaps 非空且不落盘。"""
    if not isinstance(fields, dict):
        return None, [_gap("用户请求必须是结构化对象")]
    gaps = []
    if not isinstance(fields.get("template_biz_number"), str) \
            or not re.fullmatch(r"\d+", fields.get("template_biz_number") or ""):
        gaps.append(_gap("缺完整模板单号（数字串；无单号不得猜测或代选）",
                         file="request", locator="/template_biz_number"))
    if not isinstance(fields.get("materials_dir"), str) or not fields.get("materials_dir", "").strip():
        gaps.append(_gap("缺材料目录定位（本次原始资料所在目录）",
                         file="request", locator="/materials_dir"))
    if not isinstance(fields.get("statement"), str) or not fields.get("statement", "").strip():
        gaps.append(_gap("缺业务说明/应报范围", file="request", locator="/statement"))
    unknown = sorted(set(fields) - REQUEST_KEYS)
    if unknown:
        gaps.append(_gap("请求携带未知字段（封闭键集）: {0}".format(unknown),
                         file="request", locator="/"))
    normalized = {key: fields[key] for key in REQUEST_KEYS if key in fields}
    return normalized, gaps


def register_request(fields, *, manifest_path):
    """齐备请求 → 版本化工件落派生根（role=user_request）；缺要素 → NEEDS_INPUT+缺口。"""
    manifest_path = Path(manifest_path)
    normalized, gaps = validate_request(fields)
    if gaps:
        return {"status": "NEEDS_INPUT", "gaps": gaps}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_hashes, _ = dual_hash_sets(manifest)
    if not original_hashes:
        return {"status": "NEEDS_INPUT",
                "gaps": [_gap("材料清单无任何原件，请求登记缺乏可绑定来源",
                              file=str(manifest_path), locator="/files")]}
    payload = dict(normalized)
    payload.update({"schema_version": REQUEST_SCHEMA, "source_semantics": "user_instruction",
                    "registered_at": _now()})
    relative_name = "request-{0}.json".format(uuid.uuid4().hex[:12])
    derived_id = register_derived(manifest_path, relative_name, payload,
                                  role="user_request", sources=sorted(original_hashes),
                                  generated_by="bpm.request.register_request")
    return {"status": "REGISTERED", "record": payload,
            "artifact": {"derived_id": derived_id, "relative_path": relative_name,
                         "role": "user_request", "sha256": derived_id.split(":", 1)[1]}}


# ------------------------------------------------------------ W01b 模板核对

def resolve_template(census_path, biz_number, *, declared_category=None):
    """缓存定向读取+类别识别；矛盾集中报告，未知类别转只读识别。

    normalize_template 的校验顺序先 uuid/结构后类别，未登记类别可能以其它
    ValueError 形态先抛——凡根因是类别未登记的，一律转只读识别报告。
    """
    try:
        snapshot = cached_template(census_path, biz_number)
    except TypeConfigError as exc:
        if exc.code == "UNSUPPORTED_TYPE":
            return {"status": "UNSUPPORTED", "report": identify_unknown(census_path, biz_number)}
        raise
    except ValueError:
        _, _, main = _load_doc(census_path, biz_number)
        try:
            type_from_category(main.get("submitType"))
        except TypeConfigError:
            return {"status": "UNSUPPORTED", "report": identify_unknown(census_path, biz_number)}
        raise
    document_type = snapshot["document_type"]
    observed = snapshot.get("header", {}).get("submitType")
    conflicts = []
    if declared_category is not None:
        try:
            declared_type = type_from_category(declared_category)
        except TypeConfigError:
            conflicts.append({"kind": "declared_category_unregistered",
                              "declared": declared_category, "declared_type": None,
                              "observed_category": observed, "template_type": document_type,
                              "message": "请求声明类别本身不在封闭注册内"})
        else:
            if declared_type != document_type:
                conflicts.append({"kind": "category_mismatch",
                                  "declared": declared_category, "declared_type": declared_type,
                                  "observed_category": observed, "template_type": document_type,
                                  "message": "请求声明类别与模板实际类别矛盾；不悄悄换类/换模板，请用户澄清"})
    if conflicts:
        return {"status": "CONFLICT", "conflicts": conflicts, "snapshot": snapshot}
    return {"status": "RESOLVED", "document_type": document_type, "snapshot": snapshot}


# ------------------------------------------------------------ 未知类别只读识别

def _load_doc(census_path, number):
    # R5-P2 取舍说明：本函数与 bpm_template.cached_template 各自解析 census corpus 的
    # bizNumber 命中与 fetch/children 结构（约 15 行重复）。不复用其内部实现，是因为
    # cached_template 的唯一命中/状态校验与 normalize 耦合在快照产出路径上，identify_unknown
    # 需要的是"类别识别失败后仍能读原始 doc 留结构证据"的前置形态——抽公共层会把两条
    # 校验语义（产快照 vs 只读取证）搅在一起，重复成本低于耦合成本；corpus 格式变更时
    # 两处同步修改（cached_template 在前，本函数在后跟改）。
    path = Path(census_path).resolve()
    if any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in path.parts):
        raise ValueError("protected source")
    corpus = json.loads(path.read_text(encoding="utf-8"))
    docs = corpus.get("docs") if isinstance(corpus, dict) else None
    if not isinstance(docs, list):
        raise ValueError("not a captured census artifact")
    hits = [doc for doc in docs if doc.get("bizNumber") == number]
    if len(hits) != 1:
        raise ValueError("full template number must identify exactly one cached document")
    doc = hits[0]
    if doc.get("fetch", {}).get("status") != 200:
        raise ValueError("template main read incomplete")
    main = json.loads(doc["fetch"]["body"], parse_float=Decimal)
    return path, doc, main


def identify_unknown(census_path, biz_number):
    """类别不在封闭注册 → 只读识别报告；不产生可写快照，不映射已注册类别绕过。"""
    path, doc, main = _load_doc(census_path, biz_number)
    observed = main.get("submitType")
    try:
        document_type = type_from_category(observed)
    except TypeConfigError:
        document_type = None
    if document_type is not None:
        return {"status": "KNOWN", "document_type": document_type,
                "message": "该类别已在封闭注册内，请走 resolve_template 正常路径"}
    safe_fields = sorted(key for key in main
                         if not re.search(r"token|cookie|auth|secret|password", key, re.I))
    children_state = {key: {"status": doc.get("children", {}).get(key, {}).get("status"),
                            "rows": len(json.loads(doc["children"][key]["body"]))
                            if doc.get("children", {}).get(key, {}).get("status") == 200 else None}
                      for key in CHILDREN}
    registry_view = {dt: {"label": label, "code": code}
                     for dt, (_, label, code, _) in _REGISTRY.items()}
    return {
        "status": "UNSUPPORTED", "biz_number": biz_number,
        "observed_category": observed, "registry": registry_view,
        "unsupported_parts": [
            "封闭类型注册（bpm_types）无此类别：无可执行 config、无字段/列定义、无编辑器映射",
            "不得映射为任何已注册类别绕过（含『其他费用』语义）；本报告只读，writable=false",
        ],
        "evidence": {"main_fields": safe_fields, "children_state": children_state,
                     "corpus": {"path": str(path), "sha256": _file_hash(path)}},
        "suggested_subtask": ("登记开发子任务：将该类别纳入 bpm_types 封闭注册"
                              "（快照字段盘点→config 设计→编辑器映射→执行验证），"
                              "完成前拒绝该类别任何写入"),
        "writable": False,
    }


# ------------------------------------------------------------ W01c 复用/替换矩阵

def _row_error(row, message):
    return ValueError("复用矩阵行非法 [{0}/{1}]: {2}".format(
        row.get("group"), row.get("field"), message))


def build_reuse_matrix(snapshot, factset, decisions, *, user_policy=None):
    """逐字段决策矩阵：值来源一律 fact_id 事实绑定，模板值仅识别对照。

    decisions: [{group, field, decision, fact_id?, basis?, reason?, template_value?}]
    构造期拒绝：current_business/proven_references 组 adopt 模板来源（旧值冒充本次）；
    旧年度预算 adopt 无用户确认；模板历史申请人 adopt 无用户政策确认；adopt/replace
    无 fact_id；empty_tables 非 not_applicable；form_identity 非 identify/not_applicable。
    """
    if not isinstance(snapshot, dict) or not snapshot.get("document_type"):
        raise ValueError("矩阵需要已解析模板快照（resolve_template 产物）")
    if not isinstance(factset, FactSet):
        raise ValueError("矩阵需要 FactSet（值来源事实绑定）")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("矩阵决策行必须是非空数组")
    user_policy = user_policy or {}
    covered = set()
    rows = []
    for row in decisions:
        if not isinstance(row, dict) or not {"group", "field", "decision"} <= set(row):
            raise _row_error(row, "缺 group/field/decision")
        group, field, decision = row["group"], row["field"], row["decision"]
        if group not in FIELD_GROUPS:
            raise _row_error(row, "未知字段组（封闭六组）")
        if decision not in DECISIONS:
            raise _row_error(row, "未知决策（封闭四值）")
        # R5-P2：同一 (group,field) 出现多行会让 entries_from_matrix 后行覆盖前行，
        # 取值歧义在构造期显式拒绝（不同组同名字段不受影响）。
        if (group, str(field)) in covered:
            raise _row_error(row, "重复 (group,field) 决策行（一字段一决策）")
        covered.add((group, str(field)))
        entry = {"group": group, "field": field, "decision": decision,
                 "template_value": row.get("template_value")}
        if row.get("fact_field"):
            entry["fact_field"] = row["fact_field"]   # 事实值键≠计划字段名时的显式映射（如 corpCode←company）
        fact = None
        if row.get("fact_id"):
            fact = factset.get(row["fact_id"])
            entry["fact_id"] = fact.fact_id
            entry["fact_source"] = fact.source
        if decision in ("adopt", "replace"):
            if fact is None:
                raise _row_error(row, "adopt/replace 行必须绑定 fact_id（值来源事实）")
            if decision == "adopt":
                if group in _NO_TEMPLATE_ADOPT_GROUPS and fact.source == "template":
                    raise _row_error(row, "模板旧值不得冒充本次值（历史复用反例）")
                if group == "stable_context" and field == "budgetYears":
                    budget_policy = user_policy.get("budget") if isinstance(user_policy.get("budget"), dict) else {}
                    if budget_policy.get("reuse") != "confirmed":
                        raise _row_error(row, "旧年度预算沿用必须用户显式确认（user_policy.budget.reuse=confirmed）")
                if group == "stable_context" and fact.source == "template" and not str(row.get("basis") or "").strip():
                    raise _row_error(row, "稳定资料复用必须给依据（basis）")
                if group == "current_person" and fact.source == "template":
                    if user_policy.get("identity_reuse") != "confirmed":
                        raise _row_error(row, "模板历史申请人不得覆盖本次用户政策（须 user_policy.identity_reuse=confirmed）")
            else:   # replace：本次值不得来自模板
                if fact.source == "template":
                    raise _row_error(row, "replace 行来源不得是模板事实")
        elif decision == "identify":
            if group != "form_identity":
                raise _row_error(row, "identify 仅用于表单形态识别（不直接抄值）")
        elif decision == "not_applicable":
            if not str(row.get("reason") or "").strip():
                raise _row_error(row, "not_applicable 必须给有源理由")
            if group == "empty_tables" and fact is not None:
                raise _row_error(row, "空表解释行不需要值来源事实（理由即证据）")
        if group == "form_identity" and decision not in ("identify", "not_applicable"):
            raise _row_error(row, "表单形态行仅识别用（identify/not_applicable），不产计划值")
        if group == "empty_tables" and decision != "not_applicable":
            raise _row_error(row, "空表组只能 not_applicable（本次业务材料和已确认规则解释）")
        if row.get("basis"):
            entry["basis"] = row["basis"]
        if row.get("reason"):
            entry["reason"] = row["reason"]
        if row.get("locator"):
            entry["locator"] = row["locator"]   # 多字段共用一事实时的字段级定位覆盖
        rows.append(entry)
    missing_groups = sorted(set(FIELD_GROUPS) - {row["group"] for row in rows})
    if missing_groups:
        raise ValueError("矩阵未覆盖全部字段组: {0}".format(missing_groups))
    return {"schema_version": MATRIX_SCHEMA, "document_type": snapshot["document_type"],
            "snapshot": {"biz_number": snapshot.get("biz_number"), "uuid": snapshot.get("uuid"),
                         "source": snapshot.get("source")},
            "user_policy": user_policy, "rows": rows, "generated_at": _now()}


def register_matrix(matrix, *, manifest_path):
    """矩阵工件落派生根（role=decision_matrix），sources=本次原件哈希。"""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_hashes, _ = dual_hash_sets(manifest)
    if not original_hashes:
        raise ValueError("矩阵登记需要非空原件来源")
    relative_name = "decision-matrix-{0}.json".format(uuid.uuid4().hex[:12])
    derived_id = register_derived(manifest_path, relative_name, matrix,
                                  role="decision_matrix", sources=sorted(original_hashes),
                                  generated_by="bpm.request.build_reuse_matrix")
    return {"derived_id": derived_id, "relative_path": relative_name,
            "role": "decision_matrix", "sha256": derived_id.split(":", 1)[1]}


def _fact_scalar(fact, field, fact_field=None):
    key = fact_field or field
    if key in fact.value:
        return fact.value[key]
    if "text" in fact.value and len(fact.value) == 1:
        return fact.value["text"]
    raise ValueError("事实 {0} 无字段 {1} 可作计划值（value={2!r}）".format(
        fact.fact_id, key, fact.value))


def entries_from_matrix(matrix, factset, fields):
    """矩阵 adopt/replace 行 → blueprint 绑定项建议 {field: {value, fact_id}}。

    值一律从事实取（fact.value[field]，模板值只识别对照）；不在 fields 内的行跳过
    （表行/票据等由 W05 生成器的 tables/invoice 路径绑定，不经此函数）。
    """
    if not isinstance(fields, (list, tuple, set)) or not fields:
        raise ValueError("fields 必须是非空字段名集合")
    entries = {}
    for row in matrix["rows"]:
        if row["decision"] not in ("adopt", "replace") or row["field"] not in set(fields):
            continue
        fact = factset.get(row["fact_id"])
        entry = {"value": _fact_scalar(fact, row["field"], row.get("fact_field")),
                 "fact_id": fact.fact_id}
        if row.get("locator"):
            entry["locator"] = row["locator"]
        entries[row["field"]] = entry
    missing = sorted(set(fields) - set(entries))
    if missing:
        raise ValueError("矩阵未覆盖请求字段: {0}".format(missing))
    return entries


# ------------------------------------------------------------ W06 D10 执行串联

# 操作人合法来源封闭枚举：本次用户政策 或 本次系统观察（登录身份探查）。
# 模板历史人员（applicant/历史操作人）永远不是来源——同名也不得据此推导。
OPERATOR_SOURCES = ("user_policy", "system_observation")

from bpm.paths import ROOT as _ROOT


def validate_operator_evidence(evidence):
    """操作人证据封闭校验：{name, source∈OPERATOR_SOURCES, basis?}。

    来源越界（如 template/template_history）直接 ValueError——这是合规防线，
    不是缺输入；缺证据（None/空 name）由 execution_ready 判 NEEDS_INPUT。
    """
    if not isinstance(evidence, dict) or not isinstance(evidence.get("name"), str) \
            or not evidence["name"].strip():
        raise ValueError("操作人证据必须是 {name, source, basis?} 且 name 非空")
    if evidence.get("source") not in OPERATOR_SOURCES:
        raise ValueError("操作人来源只能是 {0}（模板历史人员不可推导本次操作人）: {1!r}".format(
            list(OPERATOR_SOURCES), evidence.get("source")))
    operator = {"name": evidence["name"].strip(), "source": evidence["source"]}
    if evidence.get("basis"):
        if not isinstance(evidence["basis"], str):
            raise ValueError("basis 必须是字符串")
        operator["basis"] = evidence["basis"]
    return operator


def operator_from_session_record(session_record_path):
    """系统观察来源：Git 排除的 .local-session 会话记录 → 操作人证据（只读）。

    auth_status 非 authenticated 或缺 name → None（缺输入，不猜）。只取
    principal.name 与核验层次拼 basis；不复制任何凭证引用或其余元数据原值。
    """
    record = json.loads(Path(session_record_path).read_text(encoding="utf-8"))
    principal = record.get("principal") if isinstance(record, dict) else None
    name = principal.get("name") if isinstance(principal, dict) else None
    if record.get("auth_status") != "authenticated" \
            or not isinstance(name, str) or not name.strip():
        return None
    basis = "automation/.local-session 会话记录 principal（auth_status=authenticated）"
    level = record.get("identity_verification_level")
    if isinstance(level, str) and level.strip():
        basis += " level={0}".format(level.strip())
    return {"name": name.strip(), "source": "system_observation", "basis": basis}


def execution_ready(plan_path, operator_evidence, *, timeout=600):
    """PLAN_READY 计划 → fill_once --validate-only 全绿 → 执行就绪结论。

    只做上层编排：实际校验经真实 CLI 子进程 `python -X utf8 fill_once.py
    --fill-plan <计划> --expect-name <身份> --validate-only`（exit 0 +
    PLAN_VALIDATED 才算全绿），不改变 fill_once 任何参数语义，绝不启动浏览器
    （validate-only 分支本身在浏览器派发之前返回）。缺操作人证据 → NEEDS_INPUT
    + GAP_FIELDS 缺口，不猜姓名、不调 CLI；计划校验失败 → NEEDS_INPUT 透传
    fill_once issues。
    """
    if not isinstance(plan_path, (str, Path)) or not str(plan_path).strip():
        return {"status": "NEEDS_INPUT",
                "gaps": [_gap("缺 PLAN_READY 填报计划文件定位", file="execution",
                              locator="/plan_path")], "browser_launched": False}
    plan_path = Path(plan_path).resolve()
    if not plan_path.is_file():
        return {"status": "NEEDS_INPUT",
                "gaps": [_gap("计划文件不存在: {0}".format(plan_path),
                              file=str(plan_path), locator="/")], "browser_launched": False}
    try:
        operator = validate_operator_evidence(operator_evidence)
    except ValueError as exc:
        if operator_evidence is None:
            return {"status": "NEEDS_INPUT",
                    "gaps": [_gap("缺本次操作人来源证据（user_policy/系统观察；"
                                  "模板历史人员不可推导，不猜姓名）",
                                  file="execution", locator="/operator")],
                    "browser_launched": False}
        raise
    import subprocess
    import sys
    command = [sys.executable, "-X", "utf8", str(_ROOT / "fill_once.py"),
               "--fill-plan", str(plan_path), "--expect-name", operator["name"],
               "--validate-only"]
    try:
        completed = subprocess.run(command, cwd=str(_ROOT), capture_output=True,
                                   text=True, encoding="utf-8", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "NEEDS_INPUT",
                "gaps": [_gap("validate-only 子进程未完成: {0}".format(exc),
                              file="execution", locator="/fill_once")],
                "operator": operator, "browser_launched": False}
    lines = [line for line in (completed.stdout or "").splitlines() if line.strip()]
    payload = None
    if lines:
        try:
            payload = json.loads(lines[-1])
        except ValueError:
            payload = None
    if completed.returncode != 0 or not isinstance(payload, dict) \
            or payload.get("status") != "PLAN_VALIDATED":
        issues = payload.get("issues") if isinstance(payload, dict) else None
        return {"status": "NEEDS_INPUT",
                "gaps": [_gap("计划未通过 fill_once --validate-only（exit={0}）".format(
                                  completed.returncode),
                              file=str(plan_path), locator="/")],
                "issues": issues or [{"code": "VALIDATE_ONLY_FAILED",
                                      "message": (completed.stdout or "")[-2000:]}],
                "operator": operator, "browser_launched": False}
    suggested = ('python -X utf8 fill_once.py --fill-plan "{0}" '
                 '--expect-name "{1}" --keep-open-minutes 45').format(plan_path, operator["name"])
    # P2 字段名歧义修正（双字段留兼容）：fill_once validate-only 返回的 plan_sha256
    # 实为 plan_hash(plan) 规范哈希（非计划文件字节 sha256）。新字段 plan_hash 为准，
    # 旧字段 sha256 原值保留，既有消费方不受影响。
    return {"status": "EXECUTION_READY",
            "plan": {"path": str(plan_path),
                     "plan_hash": payload.get("plan_sha256"),
                     "sha256": payload.get("plan_sha256")},
            "operator": operator,
            "validate_only": {"status": payload.get("status"),
                              "browser_launched": payload.get("browser_launched", False)},
            "suggested_command": suggested,
            "browser_launched": False}
