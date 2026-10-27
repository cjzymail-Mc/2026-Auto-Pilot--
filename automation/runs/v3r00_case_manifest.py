# v3r00 案例原件逐件哈希清单（只读原件；产物落 automation/runs/<ts>-v3r00-inventory/）
import hashlib
import json
import os
import time

ROOT = "feature01-细化报销skill/12月公出-发票"
ts = time.strftime("%Y%m%d-%H%M%S")
run = f"automation/runs/{ts}-v3r00-inventory"
os.makedirs(run, exist_ok=True)

files = []
for dp, dn, fn in os.walk(ROOT):
    for f in sorted(fn):
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        files.append({"rel": rel, "bytes": os.path.getsize(p), "sha256": h.hexdigest()})

groups = {}
for f in files:
    top = f["rel"].split("/")[0] if "/" in f["rel"] else "(root)"
    groups.setdefault(top, []).append(f)

out = {
    "case_root": ROOT,
    "inventory_run": run,
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
    "total_files": len(files),
    "total_bytes": sum(f["bytes"] for f in files),
    "groups": {k: {"count": len(v), "files": v} for k, v in sorted(groups.items())},
}
with open(f"{run}/case-file-manifest.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print(json.dumps({"run": run, "total_files": out["total_files"],
                  "total_bytes": out["total_bytes"],
                  "groups": {k: v["count"] for k, v in sorted(out["groups"].items())}},
                 ensure_ascii=False, indent=1))
