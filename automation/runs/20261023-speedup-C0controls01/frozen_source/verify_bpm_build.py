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

ROOT = Path(__file__).resolve().parent
CODE = ["fill_once.py", "stage1_browser_probe.py", "stage1_probe_selftest.py", "bpm_plan.py",
        "bpm_materials.py", "bpm_template.py", "bpm_ui.py", "bpm_verify.py", "bpm_save.py", "bpm_perf.py",
        "verify_bpm_build.py", "automation/fill-plan.schema.json", "automation/task.schema.json",
        "automation/document-types/travel.json", "README.md", "AGENTS.md",
        ".claude/skills/bpm-fill-run/SKILL.md", ".claude/skills/bpm-fill-run/references/travel.md",
        ".claude/skills/bpm-fill-run/references/plan-contract.md"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S-draft-build"))
    args = parser.parse_args(argv)
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
        ("capability-tests", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "tests", "-p", "test_bpm_*.py", "-v"]),
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
    files = CODE + [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "tests").glob("test_bpm_*.py"))]
    manifest = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}
    (out / "source_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"status": "OFFLINE_PASS" if all(r["exit_code"] == 0 for r in results) else "OFFLINE_FAILED",
              "checks": results, "source_manifest": "source_manifest.json", "production_access": False,
              "production_writes": False, "real_fill_verified": False, "real_save_verified": False,
              "missing_real_inputs": ["exact_history_template_number", "current_material_directory", "specific_create_and_save_instruction"]}
    (out / "build_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "artifact_dir": str(out)}, ensure_ascii=False))
    return 0 if result["status"] == "OFFLINE_PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
