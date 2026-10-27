"""Reproducible offline acceptance. Never launches the production probe main.

Chromium tests intercept every request and use synthetic data; no login profile
is read by them. The existing probe selftest remains a separate required check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from bpm.paths import ROOT
CODE = ["fill_once.py", "bpm_login.py", "bpm_template.py", "bpm_chain.py",
        "stage1_browser_probe.py", "stage1_probe_selftest.py", "verify_bpm_build.py",
        "tools/__init__.py", "requirements-dev.txt", "automation/prepare_type_replay_test.py", "automation/fill-plan.schema.json", "automation/task.schema.json",
        "automation/document-types/express.json", "automation/document-types/rd_materials.json",
        # Round-10（ctr-8cb7b247 §1）：document-types 清单随封闭注册同步五类型——
        # 02/04 config 与 notes 进 manifest 冻结，config sha 进构建产物。
        "automation/document-types/office_supplies.json", "automation/document-types/welfare_labor.json",
        "automation/document-types/office_supplies.notes.md", "automation/document-types/welfare_labor.notes.md",
        ".claude/skills/bpm-fill-run/references/express.md",
        ".claude/skills/bpm-fill-run/references/rd-materials.md",
        "automation/document-types/travel.json", "README.md", "AGENTS.md",
        ".claude/skills/bpm-fill-run/SKILL.md", ".claude/skills/bpm-fill-run/references/travel.md",
        ".claude/skills/bpm-fill-run/references/plan-contract.md",
        ".claude/skills/bpm-fill-run/references/full-chain.md",
        # BPM-SELFDRIVE-20261027-V1 R1（ctr-640d0763）：自驾规则版本化配置进 manifest
        # 冻结（bpm_self_drive.py / tests 由下方 glob 自动纳入）。
        "automation/business-scenarios/self_drive.json", "docs/repository-layout.md"]
# Freeze the actual implementation as well as compatibility entry points.
# Directory moves must never silently remove business code or skill references
# from execution_source_manifest/source_manifest. Legacy one-shot scripts and
# maintenance before-images are intentionally outside the production source set.
CODE = sorted(set(CODE) | {
    p.relative_to(ROOT).as_posix()
    for directory in ("bpm", "tools/verification", "tools/diagnostics")
    for p in (ROOT / directory).rglob("*.py")
} | {
    p.relative_to(ROOT).as_posix()
    for p in (ROOT / ".claude/skills/bpm-fill-run").rglob("*.md")
})


def real_input_layers(materials_dir, save_instruction_required):
    """真实输入三层语义（D22 / V3 §12.1）：missing=真缺、supplied=已供料、
    waived=非本轮要求。fill_only 缺省下 specific_create_and_save_instruction 不再
    作为无条件 missing 项；real_save_verified=false 维持"未测"语义不变。"""
    missing = ["exact_history_template_number"]
    supplied, waived = [], []
    if materials_dir:
        supplied.append({"item": "current_material_directory", "path": materials_dir,
                         "status": "supplied"})
    else:
        missing.append("current_material_directory")
    if save_instruction_required:
        missing.append("specific_create_and_save_instruction")
    else:
        waived.append({"item": "specific_create_and_save_instruction",
                       "reason": "fill_only mainline: save/submit out of scope for this build; "
                                 "real_save_verified=false means untested, not a pending requirement"})
    return {"missing": missing, "supplied": supplied, "waived": waived}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S-draft-build"))
    parser.add_argument("--materials-dir", default=None,
                        help="真实案例材料目录（相对仓库根）；传入即声明 current_material_directory 已供料")
    parser.add_argument("--save-instruction-required", action="store_true",
                        help="声明本轮要求具体保存指令（默认缺省=fill_only 主线不要求）")
    args = parser.parse_args(argv)
    if args.materials_dir and not (ROOT / args.materials_dir).is_dir():
        parser.error("--materials-dir must be an existing directory relative to repo root")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", args.run):
        parser.error("simple run id required")
    out = (ROOT / "automation/offline-verify" / args.run).resolve()
    if out.parent != (ROOT / "automation/offline-verify").resolve():
        parser.error("acceptance output escapes offline-verify")
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONUTF8="1", BPM_TEST_EVIDENCE_DIR=str(out / "dom-evidence"))
    results = []
    for name, command in [
        ("probe-selftest", [sys.executable, "-X", "utf8", "stage1_probe_selftest.py"]),
        # V3-R05：pattern 由 test_bpm_*.py 放宽为 test_*.py —— 与全量 discover 等价
        # （原 299≠308 差 test_skill_docs.py 的 9 项；progress.json observations 痛点闭环）
        ("capability-tests", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]),
    ]:
        before = time.perf_counter()
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        log = completed.stdout + completed.stderr
        (out / (name + ".log")).write_text(log, encoding="utf-8")
        match = re.search(r"Ran (\d+) tests?", log)
        item = {"name": name, "command": command[1:], "exit_code": completed.returncode,
                "seconds": round(time.perf_counter() - before, 3), "log": name + ".log"}
        if match:
            item["test_count"] = int(match[1])
        results.append(item)
        with (out / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "OFFLINE_CHECK", **item}, ensure_ascii=False) + "\n")
        print(json.dumps(item, ensure_ascii=False), flush=True)
    files = CODE + [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "tests").glob("test_*.py"))]
    manifest = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}
    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"status": "OFFLINE_PASS" if all(r["exit_code"] == 0 for r in results) else "OFFLINE_FAILED",
              "checks": results, "source_manifest": "source_manifest.json", "production_access": False,
              "production_writes": False, "real_fill_verified": False, "real_save_verified": False,
              "missing_real_inputs": real_input_layers(args.materials_dir, args.save_instruction_required)["missing"],
              "real_input_semantics": real_input_layers(args.materials_dir, args.save_instruction_required),
              "real_input_args": {"materials_dir": args.materials_dir,
                                  "save_instruction_required": bool(args.save_instruction_required)}}
    (out / "build_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "artifact_dir": str(out)}, ensure_ascii=False))
    return 0 if result["status"] == "OFFLINE_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
