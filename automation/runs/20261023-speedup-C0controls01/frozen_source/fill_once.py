#!/usr/bin/env python3
"""Prepare task materials or execute an explicit validated plan; no historical defaults."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from bpm_plan import PlanError, file_hash, load_plan, plan_hash
from bpm_materials import prepare_materials

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "automation/runs"


def _write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _run_path(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
        raise ValueError("run id must be a simple 1-100 character identifier")
    if not RUNS.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("runs root escapes repository")
    result = (RUNS / run_id).resolve()
    if result.parent != RUNS.resolve():
        raise ValueError("run path escapes runs root")
    return result


def allocate_run(binding, run_id=None, resume=False):
    run_id = run_id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    run = _run_path(run_id)
    RUNS.mkdir(parents=True, exist_ok=True)
    if resume:
        existing = json.loads((run / "task_binding.json").read_text(encoding="utf-8"))
        if existing != binding:
            raise ValueError("retry binding differs; use a new run")
    else:
        run.mkdir(exist_ok=False)
        _write(run / "task_binding.json", binding)
    return run


def validate_task(task, base_dir):
    required = {"schema_version", "task_id", "document_type", "operator", "template_biz_number", "materials_dir", "statement", "authorization"}
    issues = []
    def bad(path, message):
        issues.append({"path": path, "code": "TASK_INVALID", "message": message})
    if not isinstance(task, dict):
        return [{"path": "/", "code": "TASK_INVALID", "message": "task object required"}]
    for key in required - set(task):
        bad("/" + key, "required property missing")
    for key in set(task) - required - {"template_snapshot_path"}:
        bad("/" + key, "unknown task property")
    for key in required - {"authorization"}:
        if not isinstance(task.get(key), str) or not task.get(key, "").strip():
            bad("/" + key, "nonempty string required")
    if task.get("schema_version") != "1.0" or task.get("document_type") != "travel":
        bad("/", "only task schema 1.0 / travel is supported")
    if not isinstance(task.get("template_biz_number"), str) or not re.fullmatch(r"\d+", task.get("template_biz_number", "")):
        bad("/template_biz_number", "template number must remain digit string")
    auth = task.get("authorization")
    if not isinstance(auth, dict) or set(auth) != {"mode", "task_id", "statement", "allow_submit"} or auth.get("mode") not in ("fill_only", "save_draft") or auth.get("task_id") != task.get("task_id") or auth.get("allow_submit") is not False or not isinstance(auth.get("statement"), str) or not auth.get("statement", "").strip():
        bad("/authorization", "task-bound fill_only/save_draft authorization required; submission forbidden")
    if isinstance(task.get("materials_dir"), str):
        materials = (Path(base_dir) / task["materials_dir"]).resolve()
        if not materials.is_dir() or any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in materials.parts):
            bad("/materials_dir", "readable nonprotected material directory required")
    return issues


def prepare_task(task_path, expected_operator=None, run_id=None):
    task_path = Path(task_path).resolve()
    if any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in task_path.parts):
        raise ValueError("protected task location")
    task = json.loads(task_path.read_text(encoding="utf-8"))
    issues = validate_task(task, task_path.parent)
    if expected_operator is not None and task.get("operator") != expected_operator:
        issues.append({"path": "/operator", "code": "IDENTITY_MISMATCH", "message": "operator differs from expected identity"})
    if issues:
        raise PlanError(issues)
    run = allocate_run({"kind": "task", "task_id": task["task_id"], "task_sha256": plan_hash(task), "operator": task["operator"]}, run_id)
    _write(run / "task.json", task)
    manifest = prepare_materials(task_path.parent / task["materials_dir"], run / "materials")
    gaps = [{"path": "/fill_plan", "code": "NEEDS_INPUT", "message": "Review materials and generate sourced v1.0 plan; never infer costs, dates or invoice facts from history."}]
    template = {"biz_number": task["template_biz_number"]}
    if task.get("template_snapshot_path"):
        snapshot_path = (task_path.parent / task["template_snapshot_path"]).resolve()
        if any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in snapshot_path.parts):
            raise ValueError("protected snapshot path")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if snapshot.get("biz_number", snapshot.get("bizNumber")) != task["template_biz_number"]:
            raise ValueError("snapshot does not bind requested document number")
        template.update({"snapshot_path": str(snapshot_path), "sha256": file_hash(snapshot_path)})
    else:
        gaps.append({"path": "/template", "code": "NEEDS_INPUT", "message": "Targeted read-only template snapshot required via bpm_template; no history census."})
    result = {"status": "NEEDS_INPUT", "task_id": task["task_id"], "run": run.name, "template": template,
              "materials": {"manifest_path": str(manifest), "manifest_sha256": file_hash(manifest)}, "gaps": gaps, "browser_launched": False}
    _write(run / "preparation_result.json", result)
    _write(run / "stage1_result.json", result)
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": "TASK_PREPARED", "time": time.time(), "task_id": task["task_id"], "status": "NEEDS_INPUT"}, ensure_ascii=False) + "\n")
    return result


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--task", help="prepare material inventory only; no browser")
    mode.add_argument("--fill-plan", help="explicit canonical v1.0 plan JSON")
    parser.add_argument("--expect-name", help="expected operator; required for plan")
    parser.add_argument("--run", help="new independent run identifier")
    parser.add_argument("--resume-run", help="retry run with identical task/plan/operator")
    parser.add_argument("--keep-open-minutes", type=float, default=45)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--legacy-regression", action="store_true", help="explicit old-plan fill-only regression")
    for flag in ("login-wait", "wall-cap", "tech-budget"):
        parser.add_argument("--" + flag, type=float)
    return parser


def main(argv=None):
    prepare_t0 = time.time()*1000
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
        if args.task:
            if args.legacy_regression or args.resume_run:
                raise ValueError("task preparation does not accept legacy/retry mode")
            if args.validate_only:
                path = Path(args.task).resolve()
                task = json.loads(path.read_text(encoding="utf-8"))
                issues = validate_task(task, path.parent)
                if args.expect_name and task.get("operator") != args.expect_name:
                    issues.append({"path": "/operator", "code": "IDENTITY_MISMATCH", "message": "operator differs"})
                if issues:
                    raise PlanError(issues)
                print(json.dumps({"status": "TASK_VALIDATED", "browser_launched": False}))
                return 0
            print(json.dumps(prepare_task(args.task, args.expect_name, args.run), ensure_ascii=False))
            return 2
        if not args.expect_name:
            raise ValueError("--expect-name required for plan validation/execution")
        plan_path = Path(args.fill_plan).resolve()
        if any(p.lower() in {".pw-profile", ".git", "legacy-ia2"} for p in plan_path.parts):
            raise ValueError("protected plan location")
        if args.legacy_regression:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            if not isinstance(plan, dict) or plan.get("schema_version") == "1.0":
                raise ValueError("legacy regression requires old-format object")
            binding = {"kind": "legacy_regression", "plan_sha256": plan_hash(plan), "operator": args.expect_name}
        else:
            plan = load_plan(plan_path, expected_operator=args.expect_name)
            binding = {"kind": "fill_plan", "task_id": plan["task_id"], "plan_sha256": plan_hash(plan), "operator": args.expect_name,
                       "config_sha256": file_hash(ROOT / "automation/document-types/travel.json")}
        if args.validate_only:
            print(json.dumps({"status": "PLAN_VALIDATED" if not args.legacy_regression else "LEGACY_REGRESSION_ONLY", "plan_sha256": binding["plan_sha256"], "browser_launched": False}))
            return 0
        run = allocate_run(binding, args.resume_run or args.run, resume=bool(args.resume_run))
        from verify_bpm_build import CODE
        hashes={name:file_hash(ROOT/name) for name in CODE}
        manifest_path=run/("execution_source_manifest.json" if not args.resume_run else "resume_source_manifest_"+str(time.time_ns())+".json")
        _write(manifest_path,hashes)
        with (run/"events.jsonl").open("a",encoding="utf-8") as stream:
            stream.write(json.dumps({"event":"timing","action":"entry_plan_validation_binding","t0_ms":prepare_t0,
                "dur_ms":time.time()*1000-prepare_t0,"outcome":"ok","plan_hash":binding["plan_sha256"],
                "source_manifest_sha256":file_hash(manifest_path)},ensure_ascii=False)+"\n")
        if not args.resume_run:
            _write(run / "input_plan_snapshot.json", plan)
        command = [sys.executable, "-X", "utf8", str(ROOT / "stage1_browser_probe.py"), "--run", run.name,
                   "--expect-name", args.expect_name, "--fill-plan", str(plan_path), "--keep-open-minutes", str(args.keep_open_minutes)]
        if args.legacy_regression:
            command.append("--legacy-regression")
        if args.resume_run:
            command.extend(["--resume-attempt", "latest"])
        for option in ("login_wait", "wall_cap", "tech_budget"):
            if getattr(args, option) is not None:
                command.extend(["--" + option.replace("_", "-"), str(getattr(args, option))])
        return subprocess.call(command, cwd=ROOT)
    except (PlanError, ValueError, OSError) as exc:
        print(json.dumps({"status": "NEEDS_INPUT", "issues": exc.issues if isinstance(exc, PlanError) else [{"code": "INPUT_INVALID", "message": str(exc)}], "browser_launched": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
