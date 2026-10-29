"""Hash-checked installation of this reviewed team-workflow change only."""
from pathlib import Path
import hashlib
import json
import os
import tempfile

HERE = Path(__file__).resolve().parent
TARGET = Path(r"D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.claude/skills/team-workflow").resolve()
FILES = ["scripts/prepare_new.py", "fixtures/test_prepare_new.py", "scripts/workflow.py",
         "references/relay.md", "SKILL.md"]

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    before = json.loads((HERE / "before-hashes.json").read_text(encoding="utf-8"))
    frozen = json.loads((HERE / "candidate-hashes.json").read_text(encoding="utf-8"))
    for name in FILES:
        dst = (TARGET / name).resolve()
        if not dst.is_relative_to(TARGET): raise RuntimeError("INSTALL_PATH_OUTSIDE_TARGET")
        data = (HERE / "staged/team-workflow" / name).read_bytes()
        if sha(data) != frozen[name]: raise RuntimeError("CANDIDATE_CHANGED: " + name)
        actual = sha(dst.read_bytes()) if dst.exists() else None
        if actual not in (before.get(name), frozen[name]): raise RuntimeError("INSTALLED_FILE_CHANGED: " + name)
    results = []
    for name in FILES:
        dst = TARGET / name
        data = (HERE / "staged/team-workflow" / name).read_bytes()
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dst.parent, prefix=dst.name + ".install-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            # Detect edits made after the first complete preflight as well.
            actual = sha(dst.read_bytes()) if dst.exists() else None
            if actual not in (before.get(name), frozen[name]): raise RuntimeError("INSTALL_DRIFT: " + name)
            os.replace(tmp, dst)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        if sha(dst.read_bytes()) != frozen[name]: raise RuntimeError("INSTALL_VERIFY_FAILED: " + name)
        results.append({"file": name, "sha256": frozen[name]})
    # Read through the runtime junction as well as the canonical source.
    runtime = Path(r"C:/Users/xy198/.claude-glm/skills/team-workflow")
    if any(sha((runtime/name).read_bytes()) != frozen[name] for name in FILES):
        raise RuntimeError("RUNTIME_JUNCTION_MISMATCH")
    result = {"installed": results, "runtime_junction_verified": True,
              "scope": "shared skill only; no workflow state/task/progress or OA business changed"}
    (HERE / "validation/installed.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"installed_files": len(results), "runtime_junction_verified": True}))

if __name__ == "__main__": main()
