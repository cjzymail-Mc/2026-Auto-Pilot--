"""单会话贯通执行入口（G1）：一个业务编排执行者持有 context、锁及自有页面。

两条输入分支（2026-10-28 BPM-FASTLANE-20261028-V2）：

- ``--task``：agent 先离线完成原件理解、事实提取和场景字段映射（facts_payload：
  FactSet 载荷 + blueprint，模板派生字段留白）；本入口单会话内完成
  取得当前身份 → 按完整单号 live 读模板（同一 probe，不再另起 ReadOnlyProbe）
  → 用本次观察补齐模板事实/蓝图 → G2 授权编译 → 生成器产出最终计划并冻结
  → 复用既有连续填写链。不得先冻结计划再覆盖其中的模板快照。
- ``--fill-plan``：已就绪计划原样执行——不无条件重读模板、不把 fill_only
  静默升级为保存；核实当前身份后直接进程内复用 StructuredProbe 连续执行链
  （不再经 stage1 子进程边界）。

G2 授权编译（compile_authorization）：三分支（既有 registry 意图只读核实 /
测试合成强制 fill_only / 按任务声明编译），固定顺序为
检查既有 run／registry 与请求意图 → 形成含授权字段的最终计划 → 完整来源及
金额校验（生成器内置）→ 计算 plan_hash/config_sha256 → 落盘最终计划与
授权绑定记录 → 执行绑定核对。授权记录是 run 内独立派生产物，含策略/请求
来源引用、编译时间与 task_id/plan_hash/config_sha256/操作人四绑定，不把含
plan_hash 的记录反向嵌入计划（无自引用）。

G3：填写完成→终局自检→有授权时保存→同 context 只读副页持久化全量核验→
result_delivered 完成事件先原子落盘再驻留（agent 用宿主后台通知立即交付，
不等驻留进程退出）。旧 CLI（fill_once/bpm_login/bpm_template/bpm.query）
行为保持兼容。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bpm.fill_cli import _run_path, allocate_run, validate_task
from bpm.paths import ROOT
from bpm.plan import PlanError, file_hash, load_plan, plan_hash
from bpm.types import TypeConfigError, check_template_type, resolve_type
from bpm.ui import StructuredProbe

RUNS = ROOT / "automation" / "runs"
REGISTRY = ROOT / "automation" / "task-registry"

# A1 日常自动保存策略登记号（SKILL.md「日常保存策略」节，2026-10-27 增补）。
A1_STANDING_POLICY = "BPM-SELFDRIVE-20261027-A1"
AUTHORIZATION_RECORD_SCHEMA = "1.0"
ONESHOT_TASK_KIND = "oneshot_task"


class OneshotPrepareBlocked(RuntimeError):
    """任务分支准备缺口：携带结构化 issues（NEEDS_INPUT 族，不猜不代填）。"""

    def __init__(self, issues):
        super().__init__("; ".join(str(i.get("message") or i.get("code")) for i in issues))
        self.issues = list(issues)


def _gap(path, code, message):
    return {"path": path, "code": code, "message": message}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _append_event(run, payload):
    with (Path(run) / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _timing_event(run, action, t0_ms, **fields):
    _append_event(run, {"event": "timing", "action": action, "t0_ms": t0_ms,
                        "dur_ms": time.time() * 1000 - t0_ms, "outcome": "ok", **fields})


def _protected(path):
    return any(p.lower() in {".pw-profile", ".local-session", ".git", "legacy-ia2"} for p in Path(path).parts)


# ------------------------------------------------------------ G2 授权编译

def _journal_state(task_id):
    """跨 run 保存意图（只读核实；不新建、不删除、不改写）。"""
    import hashlib
    journal = REGISTRY / (hashlib.sha256(task_id.encode("utf-8")).hexdigest() + ".json")
    if not journal.is_file():
        return None, journal
    try:
        return json.loads(journal.read_text(encoding="utf-8")), journal
    except (OSError, ValueError):
        return {"status": "UNREADABLE_JOURNAL", "journal": str(journal)}, journal


def compile_authorization(task, blueprint):
    """G2 三分支授权编译（纯函数：输入任务+蓝图，输出计划授权块+编译元数据）。

    分支序（G2.3 固定编译顺序的第一步「检查既有 run／registry 与请求意图」
    由调用方在启动浏览器前完成；此处只做逐任务决策）：
    1. 测试/回放/占位/合成（task.synthetic 或 blueprint.test_context）→ 强制
       fill_only（与 validate_plan 的 test_context 守卫同向；测试用真实历史
       材料仍属测试，不靠删除标记变成真实单）；
    2. 任务声明 fill_only → fill_only（用户明确只填或默认不保存）；
    3. 任务声明 save_draft 且 save_basis 合法（user_request 引用本次用户请求，
       或 standing_policy 引用 A1 日常策略）→ save_draft。
    声明 save_draft 而 basis 缺失/越界 → 结构化缺口，不编译保存（缺真实用途
    依据不能凭“没有 test_context”认定为真实可保存任务）。
    """
    declared = task["authorization"]
    synthetic = task.get("synthetic") is True or "test_context" in blueprint
    explicit_test_draft = False
    if ("test_context" in blueprint and task.get("synthetic") is not True
            and declared["mode"] == "save_draft"
            and (declared.get("save_basis") or {}).get("kind") == "user_request"):
        from bpm.test_draft_authorization import validate_test_draft_authorization
        candidate = dict(blueprint, task_id=task["task_id"], document_type=task["document_type"])
        # Full source/marker validation is repeated on the generated plan and
        # immediately before SaveController clicks its unique Save button.
        candidate["header"] = {"description": "测试、勿流转"}
        explicit_test_draft = validate_test_draft_authorization(candidate, verify_sources=False)
    if explicit_test_draft:
        mode, branch = "save_draft", "explicit_historical_test_draft"
        source = {"kind": "user_request", "reference": declared["save_basis"]["reference"]}
    elif synthetic:
        mode, branch = "fill_only", "synthetic_forced_fill_only"
        reference = "task.synthetic=true" if task.get("synthetic") is True else "blueprint.test_context"
        source = {"kind": "forced_fill_only", "reference": reference}
    elif declared["mode"] == "fill_only":
        mode, branch = "fill_only", "declared_fill_only"
        source = {"kind": "task_declaration", "reference": "task.authorization.mode=fill_only"}
    else:
        basis = declared.get("save_basis") or {}
        if basis.get("kind") == "standing_policy" and basis.get("reference") != A1_STANDING_POLICY:
            raise OneshotPrepareBlocked([_gap(
                "/authorization/save_basis", "UNKNOWN_STANDING_POLICY",
                "standing_policy 引用必须是已登记的 A1 日常策略 {0}".format(A1_STANDING_POLICY))])
        mode, branch = "save_draft", "declared_save_draft"
        source = {"kind": basis["kind"], "reference": basis["reference"]}
    block = {"mode": mode, "task_id": task["task_id"],
             "statement": declared["statement"], "allow_submit": False}
    meta = {"branch": branch, "request_source": source, "synthetic": synthetic,
            "requested_mode": declared["mode"]}
    return block, meta


def build_authorization_record(task, plan, meta, run):
    """授权绑定记录：run 内独立派生产物，四绑定（task_id/plan_hash/config_sha256/
    操作人）+ 策略/请求来源引用 + 编译时间。不嵌入计划（无自引用）。"""
    return {"schema_version": AUTHORIZATION_RECORD_SCHEMA,
            "task_id": task["task_id"],
            "plan_hash": plan_hash(plan),
            "config_sha256": resolve_type(plan["document_type"]).sha256,
            "operator": task["operator"],
            "mode": plan["authorization"]["mode"],
            "branch": meta["branch"],
            "request_source": meta["request_source"],
            "task_statement": task["authorization"]["statement"],
            "synthetic": meta["synthetic"],
            "requested_mode": meta["requested_mode"],
            "compiled_at": _now(),
            "run": Path(run).name}


def verify_record_bindings(record, plan, task):
    """执行/重试绑定核对：记录四绑定与最终计划及任务完全一致，否则停止。"""
    mismatches = []
    if record.get("task_id") != plan.get("task_id"):
        mismatches.append("task_id")
    if record.get("plan_hash") != plan_hash(plan):
        mismatches.append("plan_hash")
    if record.get("config_sha256") != resolve_type(plan["document_type"]).sha256:
        mismatches.append("config_sha256")
    if record.get("operator") != task.get("operator"):
        mismatches.append("operator")
    if mismatches:
        raise OneshotPrepareBlocked([_gap(
            "/authorization_record", "AUTHORIZATION_BINDING_CONFLICT",
            "授权记录与最终计划绑定不一致: {0}；按原状态停止，不改绑不另建".format(mismatches))])


# ------------------------------------------------------------ 模板补全（G1.2/G1.3）

def complete_from_live_snapshot(task, payload, snapshot, snapshot_path):
    """用本次 live 观察补齐模板来源事实与蓝图 header 绑定。

    模板字段值一律取自 snapshot["header"]（本次观察）；agent 不得预供模板字段
    值或预冻结快照——不能仅替换哈希使旧值通过。缺快照键、重复声明、预供值、
    预冻结 template 块均返回结构化缺口。
    """
    from bpm.facts import FactSet
    blueprint = payload["blueprint"]
    spec = blueprint.get("template_completion") or {}
    fact_specs = spec.get("facts") or []
    header_fields = spec.get("header_fields") or {}
    gaps = []

    template_block = blueprint.get("template") or {}
    if template_block.get("biz_number") != task["template_biz_number"]:
        gaps.append(_gap("/blueprint/template", "TEMPLATE_NUMBER_CONFLICT",
                         "blueprint.template.biz_number 与任务 template_biz_number 不一致"))
    if template_block.get("sha256") or template_block.get("snapshot_path"):
        gaps.append(_gap("/blueprint/template", "TEMPLATE_PRE_FROZEN",
                         "任务分支不允许预冻结模板快照（离线快照请改用 --fill-plan 分支）"))
    if task.get("template_snapshot_path"):
        gaps.append(_gap("/template_snapshot_path", "TEMPLATE_PRE_FROZEN",
                         "任务分支按完整单号 live 读模板，不携带离线快照路径"))

    if not isinstance(fact_specs, list):
        fact_specs = []
        gaps.append(_gap("/blueprint/template_completion/facts", "SPEC_INVALID", "facts 必须是数组"))
    if not isinstance(header_fields, dict):
        header_fields = {}
        gaps.append(_gap("/blueprint/template_completion/header_fields", "SPEC_INVALID",
                         "header_fields 必须是对象"))
    declared_keys = [fs.get("fact_key") for fs in fact_specs if isinstance(fs, dict)]
    if len(declared_keys) != len(set(declared_keys)) or any(not k for k in declared_keys):
        gaps.append(_gap("/blueprint/template_completion/facts", "SPEC_INVALID",
                         "fact_key 必须非空且不重复"))
    header = snapshot.get("header") or {}
    fields_by_key = {}
    for fs in fact_specs:
        if not isinstance(fs, dict):
            continue
        key, kind, fields = fs.get("fact_key"), fs.get("kind"), fs.get("fields")
        if not isinstance(fields, dict) or not fields:
            gaps.append(_gap("/blueprint/template_completion/facts/{0}".format(key),
                             "SPEC_INVALID", "fields 必须是非空对象（事实值键→快照 header 键）"))
            continue
        fields_by_key[key] = fields
        for value_key, snap_key in fields.items():
            if snap_key not in header:
                gaps.append(_gap("/blueprint/template_completion/facts/{0}".format(key),
                                 "SNAPSHOT_FIELD_MISSING",
                                 "本次 live 快照缺 header 键 {0}（事实字段 {1}）".format(snap_key, value_key)))
    for plan_field, fact_key in header_fields.items():
        if fact_key not in fields_by_key:
            gaps.append(_gap("/blueprint/template_completion/header_fields/{0}".format(plan_field),
                             "FACT_KEY_UNDECLARED", "引用了未声明的事实 {0!r}".format(fact_key)))
            continue
        if plan_field in (blueprint.get("header") or {}):
            gaps.append(_gap("/blueprint/header/{0}".format(plan_field), "TEMPLATE_VALUE_PRE_SUPPLIED",
                             "模板派生字段不得预供值/预绑定（须由本次 live 观察补齐）"))
        if plan_field not in fields_by_key[fact_key]:
            gaps.append(_gap("/blueprint/template_completion/header_fields/{0}".format(plan_field),
                             "SPEC_INVALID", "事实 {0} 的 fields 未覆盖计划字段 {1}".format(fact_key, plan_field)))
    if gaps:
        raise OneshotPrepareBlocked(gaps)

    factset = FactSet.from_payload(payload["factset"])
    snapshot_file = Path(snapshot_path)
    sha = file_hash(snapshot_file)
    locator_file = str(snapshot_file)
    fact_ids = {}
    for fs in fact_specs:
        value = {value_key: header[snap_key] for value_key, snap_key in fs["fields"].items()}
        first_snap_key = next(iter(fs["fields"].values()))
        fact_ids[fs["fact_key"]] = factset.add(
            fs["kind"], source="template", value=value,
            locator=locator_file + "#/header/" + first_snap_key,
            input_hashes={"template": sha})
    for plan_field, fact_key in header_fields.items():
        fact = factset.get(fact_ids[fact_key])
        snap_key = fields_by_key[fact_key][plan_field]
        blueprint.setdefault("header", {})[plan_field] = {
            "value": fact.value[plan_field], "fact_id": fact.fact_id,
            "locator": locator_file + "#/header/" + snap_key}
    blueprint["template"] = {"biz_number": task["template_biz_number"],
                             "captured_at": snapshot.get("captured_at"),
                             "sha256": sha, "snapshot_path": str(snapshot_file)}
    return factset, blueprint


# ------------------------------------------------------------ 任务分支探针

class TaskBranchProbe(StructuredProbe):
    """G1 任务分支：StructuredProbe 的延迟绑定形态。

    浏览器/锁/页面生命周期全部由 Probe.main() 拥有；本类只挂
    pending_task_prepare 钩子（Probe.main 在身份确认后、填写链之前调用），
    在钩子内完成 live 模板读取→事实/蓝图补全→授权编译→生成→冻结→绑定。
    """

    def __init__(self, args, preparation):
        super().__init__(args)          # args.fill_plan=None → 延迟绑定形态
        self._preparation = preparation
        self.pending_task_prepare = self._prepare_and_freeze

    def _prepare_and_freeze(self):
        from bpm.browser_probe import BLOCKED, PASS
        from bpm.plan_generate import PlanGenerationError, generate_fill_plan
        from bpm.template import _json_default, fetch_template
        prep = self._preparation
        task, payload = prep["task"], prep["payload"]

        def blocked(issues, stage):
            self.result["task_status"] = "NEEDS_INPUT"
            self.result["issues"] = issues
            self.log_event(event="oneshot_prepare_blocked", stage=stage, issues=issues)
            return BLOCKED

        try:
            if prep.get("frozen") is not None:
                # G2.5 同一请求重试：复用已冻结计划与授权记录，不重新生成。
                frozen = prep["frozen"]
                self.bind_final_plan(frozen["plan"], frozen["plan_path"])
                self.log_event(event="oneshot_prepare", branch="reuse_frozen_plan",
                               plan_hash=self.bound_plan_hash)
                return PASS

            # 1. live 模板读取：同一 probe、共享会话；不另起浏览器/锁（G1.4/G1.5）。
            with self._timing("template_live_read"):
                snapshot = fetch_template(self, task["template_biz_number"])
                check_template_type(snapshot, task["document_type"])
                snapshot_path = Path(prep["run_dir"]) / "template_snapshot.json"
                _atomic_write_json(snapshot_path, json.loads(json.dumps(
                    snapshot, ensure_ascii=False, default=_json_default)))
            # 2. 用本次观察补齐模板事实/蓝图（值只来自 live 快照）。
            with self._timing("facts_blueprint_completion"):
                factset, blueprint = complete_from_live_snapshot(
                    task, payload, snapshot, snapshot_path)
            # 3. G2 授权编译（三分支决策入 blueprint.authorization）。
            with self._timing("authorization_compile"):
                block, meta = compile_authorization(task, blueprint)
                blueprint["authorization"] = block
            # 4. 生成最终计划（生成器内置 reconcile+完整来源/金额校验）。
            with self._timing("plan_generation"):
                generated = generate_fill_plan(
                    factset, blueprint, base_dir=prep["payload_path"].parent,
                    registry_dir=blueprint.get("registry_dir"))
                plan = generated["plan"]
            # 5/6. 计算 plan_hash/config_sha256 → 落盘最终计划+授权记录 → 绑定核对。
            with self._timing("plan_freeze"):
                record = build_authorization_record(task, plan, meta, prep["run_dir"])
                verify_record_bindings(record, plan, task)
                plan_path = Path(prep["run_dir"]) / "fill_plan.json"
                _atomic_write_json(plan_path, plan)
                _atomic_write_json(Path(prep["run_dir"]) / "authorization_record.json", record)
                binding = dict(prep["binding"])
                binding["plan_sha256"] = plan_hash(plan)
                _atomic_write_json(Path(prep["run_dir"]) / "task_binding.json", binding)
                self.log_event(event="oneshot_plan_frozen", plan_hash=plan_hash(plan),
                               mode=plan["authorization"]["mode"], branch=meta["branch"],
                               task_id=task["task_id"])
            # 7. 执行绑定：phase_fill 将再次完整核验计划/哈希/绑定。
            self.bind_final_plan(plan, plan_path)
            return PASS
        except OneshotPrepareBlocked as exc:
            return blocked(exc.issues, "prepare")
        except PlanGenerationError as exc:
            issues = list(exc.issues or [])
            issues.extend({"path": d.get("path", "/fill_plan"), "code": "GENERATOR_INVALID",
                           "message": json.dumps(d, ensure_ascii=False)[:400]} for d in (exc.details or []))
            if not issues:
                issues = [_gap("/fill_plan", "GENERATOR_INVALID", str(exc))]
            return blocked(issues, "generate")
        except (ValueError, TypeError, OSError) as exc:
            return blocked([_gap("/prepare", "PREPARE_FAILED",
                                 "{0}: {1}".format(type(exc).__name__, exc))], "prepare")


# ------------------------------------------------------------ 分支执行

def _probe_args(args, run_name, *, fill_plan):
    from types import SimpleNamespace
    return SimpleNamespace(
        run=run_name, doc_id=None, expect_name=args.expect_name,
        tech_budget=args.tech_budget if args.tech_budget is not None else 1800.0,
        login_wait=args.login_wait if args.login_wait is not None else 480.0,
        wall_cap=args.wall_cap if args.wall_cap is not None else 2400.0,
        fill_plan=fill_plan, keep_open_minutes=args.keep_open_minutes,
        login_only=False, resume_attempt="latest" if args.resume_run else None,
        interactive_pick=False, pick_wait=900.0, owned_guarded_context=True)


def _run_plan_branch(args):
    """已就绪 fill-plan：保持计划/来源/授权原样，进程内复用连续执行链。"""
    plan_path = Path(args.fill_plan).resolve()
    if _protected(plan_path):
        raise ValueError("protected plan location")
    t0 = time.time() * 1000
    plan = load_plan(plan_path, expected_operator=args.expect_name)
    from bpm.types import resolve_type as _resolve
    binding = {"kind": "fill_plan", "task_id": plan["task_id"], "plan_sha256": plan_hash(plan),
               "operator": args.expect_name, "config_sha256": _resolve(plan["document_type"]).sha256}
    if args.validate_only:
        print(json.dumps({"status": "PLAN_VALIDATED", "plan_sha256": binding["plan_sha256"],
                          "browser_launched": False}, ensure_ascii=False))
        return 0
    run = allocate_run(binding, args.resume_run or args.run, resume=bool(args.resume_run))
    if not args.resume_run:
        _atomic_write_json(run / "input_plan_snapshot.json", plan)
    _timing_event(run, "oneshot_plan_readiness", t0, plan_hash=binding["plan_sha256"],
                  branch="fill_plan", note="load_plan 完整校验（真实校验函数复用）")
    probe = StructuredProbe(_probe_args(args, run.name, fill_plan=str(plan_path)))
    probe.main()
    _print_result(probe)
    return 0 if probe.result.get("finish_reason") in ("SUCCESS_FILL_ONLY", "SUCCESS_DRAFT_SAVED") else 2


def _run_revision_branch(args):
    """Explicit existing-draft operation; use the same owner lifecycle as create."""
    from bpm.revision import RevisionProbe, revision_authorization
    from bpm.save import SaveError, config_hash
    paths = [Path(value).resolve() for value in
             (args.fill_plan, args.prior_plan, args.revision_authorization)]
    if any(_protected(path) or ".local-session" in path.parts for path in paths):
        raise ValueError("protected revision input location")
    plan_path, prior_path, proof_path = paths
    plan = load_plan(plan_path, expected_operator=args.expect_name)
    prior = load_plan(prior_path, expected_operator=args.expect_name)
    proof_sha = file_hash(proof_path)
    try:
        proof = revision_authorization(plan, proof_path, proof_sha, REGISTRY)
    except SaveError as exc:
        raise ValueError(str(exc)) from None
    if (plan_hash(prior) != proof["prior_plan_hash"] or prior["task_id"] != plan["task_id"]
            or prior["document_type"] != plan["document_type"]):
        raise ValueError("prior plan does not bind the original saved draft")
    if plan["authorization"]["mode"] != "save_draft":
        raise ValueError("explicit revision requires task-bound save_draft authorization")
    binding = {"kind": "existing_draft_revision", "task_id": plan["task_id"],
               "plan_sha256": plan_hash(plan), "prior_plan_sha256": plan_hash(prior),
               "revision_authorization_sha256": proof_sha,
               "prior_journal_sha256": proof["prior_journal_sha256"],
               "operator": args.expect_name, "config_sha256": config_hash(plan["document_type"])}
    if args.validate_only:
        print(json.dumps({"status": "REVISION_VALIDATED", "plan_sha256": plan_hash(plan),
                          "browser_launched": False, "operation": "revise_existing_draft"}))
        return 0
    run = allocate_run(binding, args.resume_run or args.run, resume=bool(args.resume_run))
    if not args.resume_run:
        _atomic_write_json(run / "input_plan_snapshot.json", plan)
    probe = RevisionProbe(_probe_args(args, run.name, fill_plan=str(prior_path)),
                          plan_path=plan_path, proof_path=proof_path,
                          proof_sha=proof_sha, registry=REGISTRY)
    probe.main()
    _print_result(probe)
    return 0 if probe.result.get("finish_reason") == "SUCCESS_DRAFT_SAVED" else 2


def _run_task_branch(args):
    """本次任务及准备工件：离线校验 → 单会话 身份→live 模板→计划冻结→填写。"""
    t0 = time.time() * 1000
    task_path = Path(args.task).resolve()
    if _protected(task_path):
        raise ValueError("protected task location")
    task = json.loads(task_path.read_text(encoding="utf-8"))
    issues = validate_task(task, task_path.parent)
    if task.get("operator") != args.expect_name:
        issues.append(_gap("/operator", "IDENTITY_MISMATCH", "operator differs from expected identity"))
    if not task.get("facts_payload"):
        issues.append(_gap("/facts_payload", "NEEDS_INPUT",
                           "任务分支需要 agent 离线准备的 facts_payload（FactSet 载荷+blueprint）"))
    if issues:
        raise PlanError(issues)

    payload_path = (task_path.parent / task["facts_payload"]).resolve()
    if _protected(payload_path):
        raise ValueError("protected facts payload location")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not {"factset", "blueprint"} <= set(payload):
        raise PlanError([_gap("/facts_payload", "NEEDS_INPUT",
                              "facts_payload 须含 factset 与 blueprint")])
    blueprint = payload["blueprint"]
    manifest_ref = (blueprint.get("materials") or {}).get("manifest_path")
    manifest_file = Path(manifest_ref) if manifest_ref and Path(manifest_ref).is_absolute() \
        else (payload_path.parent / manifest_ref if manifest_ref else None)
    if manifest_file is None or not manifest_file.is_file():
        raise PlanError([_gap("/blueprint/materials/manifest_path", "NEEDS_INPUT",
                              "材料 manifest 不存在（离线材料准备未完成）")])
    try:
        type_identity = resolve_type(task["document_type"], require_executable=True)
    except TypeConfigError as exc:
        raise PlanError([_gap("/document_type", "TYPE_NOT_EXECUTABLE", str(exc))]) from None

    if args.validate_only:
        try:
            block, meta = compile_authorization(task, blueprint)
        except OneshotPrepareBlocked as exc:
            raise PlanError(exc.issues) from None
        print(json.dumps({"status": "TASK_VALIDATED", "browser_launched": False,
                          "compiled_authorization": {"mode": block["mode"], "branch": meta["branch"],
                                                     "request_source": meta["request_source"]}},
                         ensure_ascii=False))
        return 0

    # G2.3 第一步：检查既有 run／registry 与请求意图（进浏览器前完成）。
    journal_state, journal_path = _journal_state(task["task_id"])
    if args.resume_run:
        run = _run_path(args.resume_run)
        existing = json.loads((run / "task_binding.json").read_text(encoding="utf-8"))
        core = {key: existing.get(key) for key in
                ("kind", "task_id", "task_sha256", "operator", "config_sha256")}
        binding = {"kind": ONESHOT_TASK_KIND, "task_id": task["task_id"],
                   "task_sha256": plan_hash(task), "operator": task["operator"],
                   "config_sha256": type_identity.sha256}
        if core != binding:
            raise ValueError("retry binding differs; use a new run")
        frozen = None
        if (run / "fill_plan.json").is_file() and (run / "authorization_record.json").is_file():
            plan = load_plan(run / "fill_plan.json", expected_operator=args.expect_name)
            record = json.loads((run / "authorization_record.json").read_text(encoding="utf-8"))
            verify_record_bindings(record, plan, task)
            frozen = {"plan": plan, "plan_path": run / "fill_plan.json", "record": record}
        binding = dict(existing)
    else:
        if journal_state is not None and journal_state.get("status") in (
                "SAVE_INTENT", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED", "UNREADABLE_JOURNAL"):
            # 红线：已有保存意图/成功记录只读核实；禁止再保存/另建/换 task_id。
            # journal 不可读同样无法核实意图，一律阻断新开（不猜状态）。
            print(json.dumps({
                "status": "EXISTING_SAVE_INTENT", "browser_launched": False,
                "task_id": task["task_id"], "journal": str(journal_path),
                "journal_status": journal_state.get("status"),
                "message": "已有跨 run 保存意图/记录：只读核实原单，不新建任务、不改绑授权",
            }, ensure_ascii=False))
            return 2
        binding = {"kind": ONESHOT_TASK_KIND, "task_id": task["task_id"],
                   "task_sha256": plan_hash(task), "operator": task["operator"],
                   "config_sha256": type_identity.sha256}
        run = allocate_run(binding, args.run)
        frozen = None
    _timing_event(run, "oneshot_task_offline_prepare", t0, task_id=task["task_id"],
                  document_type=task["document_type"],
                  agent_offline_prepare_measured=False,
                  note="agent 离线材料理解/事实准备时长未计量（未知），此段仅含本入口离线校验")

    preparation = {"task": task, "payload": payload, "payload_path": payload_path,
                   "run_dir": run, "binding": binding, "frozen": frozen}
    probe = TaskBranchProbe(_probe_args(args, run.name, fill_plan=None), preparation)
    probe.main()
    _print_result(probe)
    return 0 if probe.result.get("finish_reason") in ("SUCCESS_FILL_ONLY", "SUCCESS_DRAFT_SAVED") else 2


def _print_result(probe):
    """驻留结束后 stdout 终局摘要；更早的交付锚点是 events 的 result_delivered。"""
    print(json.dumps({
        "status": probe.result.get("finish_reason"),
        "task_status": probe.result.get("task_status"),
        "save_status": probe.result.get("save_status"),
        "run": probe.result.get("run"), "attempt": probe.result.get("attempt"),
        "plan_hash": probe.result.get("plan_hash"),
    }, ensure_ascii=False))


# ------------------------------------------------------------ CLI

def build_parser():
    parser = argparse.ArgumentParser(description="单会话贯通执行入口（task/fill-plan 两分支）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task", help="本次任务及离线准备工件（单会话：身份→live 模板→计划冻结→填写）")
    mode.add_argument("--fill-plan", help="已就绪 v1.0 计划（原样执行，不重读模板/不升级授权）")
    parser.add_argument("--prior-plan", help="同单修订的原成功计划；必须与修订授权同时提供")
    parser.add_argument("--revision-authorization", help="明确同单修订授权；不适用于新建/task分支")
    parser.add_argument("--expect-name", required=True,
                        help="期待登录账户姓名（须来自本次真实探查或用户明确预期）")
    parser.add_argument("--run", help="新独立 run 标识")
    parser.add_argument("--resume-run", help="同绑定重试 run（计划/操作人/配置哈希须完全相同）")
    parser.add_argument("--keep-open-minutes", type=float, default=45)
    parser.add_argument("--validate-only", action="store_true")
    for flag in ("login-wait", "wall-cap", "tech-budget"):
        parser.add_argument("--" + flag, type=float)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    os.chdir(ROOT)
    try:
        if args.run and args.resume_run:
            raise ValueError("--run and --resume-run are mutually exclusive")
        if not 0 <= args.keep_open_minutes <= 1440:
            raise ValueError("keep-open-minutes must be within 0..1440")
        for option in ("login_wait", "wall_cap", "tech_budget"):
            value = getattr(args, option)
            if value is not None and not 0 < value < float("inf"):
                raise ValueError(option + " must be finite and positive")
        if args.resume_run:
            _run_path(args.resume_run)
        if args.prior_plan or args.revision_authorization:
            if not (args.prior_plan and args.revision_authorization and args.fill_plan):
                raise ValueError("revision requires --fill-plan, --prior-plan and --revision-authorization")
            return _run_revision_branch(args)
        if args.task:
            return _run_task_branch(args)
        return _run_plan_branch(args)
    except OneshotPrepareBlocked as exc:
        print(json.dumps({"status": "NEEDS_INPUT", "issues": exc.issues,
                          "browser_launched": False}, ensure_ascii=False))
        return 2
    except (PlanError, ValueError, TypeError, OSError) as exc:
        print(json.dumps({"status": "NEEDS_INPUT",
                          "issues": exc.issues if isinstance(exc, PlanError)
                          else [{"code": "INPUT_INVALID", "message": str(exc)}],
                          "browser_launched": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
