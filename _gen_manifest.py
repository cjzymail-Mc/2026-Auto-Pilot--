# -*- coding: utf-8 -*-
"""定稿 manifest 生成（run 20261021-131724-1c1aadbd）。"""
import hashlib
import io
import os

RUN = r"D:\Technique Support\Claude Code Learning\Hot-Fix\【feature01-企业微信自动化办公】\automation\runs\20261021-131724-1c1aadbd"
SKIP = {"executor.lock", "manifest-sha256.txt"}
lines = []
for root, dirs, files in os.walk(RUN):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for fn in sorted(files):
        if fn in SKIP:
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, RUN).replace(os.sep, "/")
        h = hashlib.sha256(io.open(full, "rb").read()).hexdigest()
        lines.append(f"{h}  {rel}")
hdr = [
    "# manifest-sha256（run 20261021-131724-1c1aadbd，2026-10-22 定稿）",
    "# 可变性声明：events.jsonl 将在浏览器驻留结束（约17:21）追加最后一行 keep_open_end；",
    "# executor.lock（已排除）将被驻留进程删除。除此之外所有文件哈希应稳定；",
    "# 后续修正一律走新版本+corrections.md 关联，不改写本清单所列文件。",
    "",
]
io.open(os.path.join(RUN, "manifest-sha256.txt"), "w", encoding="utf-8", newline="\n").write(
    "\n".join(hdr + lines) + "\n")
print("files hashed:", len(lines))
