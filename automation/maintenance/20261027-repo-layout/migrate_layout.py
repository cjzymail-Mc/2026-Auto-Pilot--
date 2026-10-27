"""One-shot, source-only repository layout migration authorized on 2026-10-27.

Before-images contain only the explicit source/test/document allowlist below.
Workflow inputs, business evidence, original materials and authentication state
are outside this script's read/write scope. Do not rerun against a migrated tree.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
MOVES = {
    **{f"bpm_{name}.py": f"bpm/{name}.py" for name in (
        "chain", "collect", "coverage", "extraction", "facts", "identity",
        "login", "materials", "plan", "plan_generate", "request", "save",
        "self_drive", "session", "template", "types", "ui", "verify",
    )},
    "fill_once.py": "bpm/fill_cli.py",
    "stage1_browser_probe.py": "bpm/browser_probe.py",
    "bpm_perf.py": "tools/diagnostics/perf.py",
    "list_type_query.py": "tools/diagnostics/type_query.py",
    "travel_census.py": "tools/diagnostics/travel_census.py",
    "verify_bpm_build.py": "tools/verification/build.py",
    "stage1_probe_selftest.py": "tools/verification/probe_selftest.py",
    "stage1_offline_verify.py": "tools/verification/offline_dom.py",
    "_gen_manifest.py": "tools/legacy/_gen_manifest.py",
    "_schema_v02.py": "tools/legacy/_schema_v02.py",
    "_chk_orphan2.ps1": "tools/legacy/_chk_orphan2.ps1",
}
MODULES = {
    Path(old).stem: new.removesuffix(".py").replace("/", ".")
    for old, new in MOVES.items()
    if old.endswith(".py") and not new.startswith("tools/legacy/")
}
ENTRY_POINTS = {
    name: MODULES[Path(name).stem]
    for name in (
        "fill_once.py", "bpm_login.py", "bpm_template.py", "bpm_chain.py",
        "stage1_browser_probe.py", "stage1_probe_selftest.py", "verify_bpm_build.py",
    )
}


def checked(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"path outside the repository: {relative}")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(event: str, **values) -> None:
    with (HERE / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                 "event": event, **values}, ensure_ascii=False) + "\n")


def imports(source: str) -> str:
    """Rewrite import syntax while preserving the original local binding names."""
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    edits = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        original = source[start:end]
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in MODULES:
            replacement = re.sub(r"^from\s+" + re.escape(node.module) + r"(?=\s+import)",
                                 "from " + MODULES[node.module], original, count=1)
        elif isinstance(node, ast.Import) and any(item.name in MODULES for item in node.names):
            names = []
            for item in node.names:
                if item.name in MODULES:
                    names.append(MODULES[item.name] + " as " + (item.asname or item.name))
                else:
                    names.append(item.name + (" as " + item.asname if item.asname else ""))
            replacement = "import " + ", ".join(names)
        else:
            continue
        edits.append((start, end, replacement))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    # patch("old_module.attribute") must patch the same canonical module after
    # the move. Source filenames such as "bpm_plan.py" are handled separately.
    for old, new in MODULES.items():
        source = re.sub(r"([\"'])" + re.escape(old) + r"\.(?!py\b)",
                        lambda match: match.group(1) + new + ".", source)
    return source


def change(source: str, before: str, after: str, *, count: int | None = None) -> str:
    actual = source.count(before)
    if not actual or count is not None and actual != count:
        raise ValueError(f"unexpected source shape: {before!r}: {actual}")
    return source.replace(before, after)


def relocate_paths(relative: str, source: str) -> str:
    root_modules = {
        "bpm/chain.py", "bpm/fill_cli.py", "bpm/plan.py", "bpm/self_drive.py",
        "bpm/session.py", "bpm/types.py", "tools/verification/build.py",
    }
    if relative in root_modules:
        source = change(source, "ROOT = Path(__file__).resolve().parent",
                        "from bpm.paths import ROOT", count=1)
    if relative == "bpm/browser_probe.py":
        source = change(source, "BASE = Path(__file__).resolve().parent",
                        "from bpm.paths import ROOT as BASE", count=1)
    if relative == "bpm/request.py":
        source = change(source, "_ROOT = Path(__file__).resolve().parent",
                        "from bpm.paths import ROOT as _ROOT", count=1)
    if relative == "bpm/template.py":
        source = change(source, "from pathlib import Path",
                        "from pathlib import Path\nfrom bpm.paths import ROOT", count=1)
        source = change(source, 'Path(__file__).resolve().parent / "automation" / "runs"',
                        'ROOT / "automation" / "runs"', count=1)
    if relative == "bpm/ui.py":
        source = change(source, "from pathlib import Path",
                        "from pathlib import Path\nfrom bpm.paths import ROOT", count=1)
        source = change(source, 'Path(__file__).resolve().parent / "automation"',
                        'ROOT / "automation"', count=1)
        source = change(source, 'Path(__file__).resolve().parent / "automation/task-registry"',
                        'ROOT / "automation/task-registry"', count=1)
    if relative == "bpm/verify.py":
        source = change(source, "from urllib.parse import parse_qs, urlparse",
                        "from urllib.parse import parse_qs, urlparse\nfrom bpm.paths import ROOT", count=1)
        source = change(source, "Path(base_dir or Path(__file__).parent)",
                        "Path(base_dir or ROOT)", count=1)
    if relative == "tools/verification/probe_selftest.py":
        source = change(source, "sys.path.insert(0, str(Path(__file__).resolve().parent))\n", "", count=1)
        source = change(source, 'P.BASE / "stage1_browser_probe.py"', "Path(P.__file__)")
    if relative == "tools/verification/offline_dom.py":
        source = change(source, "BASE = Path(__file__).resolve().parent\nsys.path.insert(0, str(BASE))",
                        "from bpm.paths import ROOT as BASE", count=1)
        source = change(source, 'BASE / "stage1_browser_probe.py"', "Path(probe_mod.__file__)", count=1)
    return source


def wrapper(module: str, selftest: bool = False) -> str:
    if selftest:
        launch = f'    import runpy\n    runpy.run_module("{module}", run_name="__main__")\n'
    else:
        launch = f'    raise SystemExit(import_module("{module}").main())\n'
    return (f'"""Compatibility entry point; implementation: {module}."""\n'
            "from importlib import import_module\nimport sys\n\n"
            'if __name__ == "__main__":\n' + launch + "else:\n"
            f'    sys.modules[__name__] = import_module("{module}")\n')


def main() -> None:
    if (HERE / "before-manifest.json").exists():
        raise SystemExit("migration already started; use its recorded checkpoint instead of rerunning")
    for old, new in MOVES.items():
        if not checked(old).is_file() or checked(new).exists():
            raise SystemExit(f"unexpected source/destination: {old} -> {new}")
    snapshot = {checked(name) for name in MOVES}
    snapshot.update(ROOT.glob("tests/*.py"))
    snapshot.update(ROOT.glob("automation/*.py"))
    snapshot.update((ROOT / ".claude/skills/bpm-fill-run").rglob("*.md"))
    snapshot.update(checked(name) for name in ("AGENTS.md", "README.md", "STATE.md", ".gitignore"))
    before = {}
    for source in sorted(snapshot):
        relative = source.relative_to(ROOT).as_posix()
        target = HERE / "before" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        before[relative] = sha(source)
    (HERE / "before-manifest.json").write_text(
        json.dumps({"schema_version": "1.0", "source_only": True, "files": before,
                    "moves": MOVES, "entry_points": ENTRY_POINTS}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    log("SOURCE_BASELINE_CAPTURED", file_count=len(before), root_file_count=len(list(ROOT.glob("*"))))
    for old, new in MOVES.items():
        destination = checked(new)
        destination.parent.mkdir(parents=True, exist_ok=True)
        checked(old).rename(destination)
        log("SOURCE_MOVED", old=old, new=new, before_sha256=before[old])
    rewrite = [new for new in MOVES.values() if new.endswith(".py") and not new.startswith("tools/legacy/")]
    rewrite.extend(path.relative_to(ROOT).as_posix() for path in ROOT.glob("tests/*.py"))
    rewrite.extend(path.relative_to(ROOT).as_posix() for path in ROOT.glob("automation/*.py"))
    for relative in rewrite:
        path = checked(relative)
        source = path.read_text(encoding="utf-8-sig")
        updated = relocate_paths(relative, imports(source))
        ast.parse(updated, filename=relative)
        if updated != source:
            path.write_text(updated, encoding="utf-8", newline="\n")
    for name, module in ENTRY_POINTS.items():
        checked(name).write_text(wrapper(module, name == "stage1_probe_selftest.py"),
                                 encoding="utf-8", newline="\n")
    log("LAYOUT_MIGRATED", moved_file_count=len(MOVES), compatibility_entry_count=len(ENTRY_POINTS))
    print(json.dumps({"moved_files": len(MOVES), "compatibility_entries": len(ENTRY_POINTS),
                      "before_images": len(before)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
