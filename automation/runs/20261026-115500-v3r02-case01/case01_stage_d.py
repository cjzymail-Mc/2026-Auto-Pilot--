# -*- coding: utf-8 -*-
"""V3-R02 CASE-01 阶段 D：关键页 spot-render + 事后哈希零漂移核验（只读）。

render：fitz 原样位图（150dpi）到 evidence/，覆盖每类首件 + 4 个同尺寸簇成员 +
0906 拆分票对 + 1210"(2)"，全部只读渲染，不写原件目录。
post-hash：对 73 件重算 sha256 与 round-1 manifest 对账，非零漂移即失败退出。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[3]
CASE = ROOT / "feature01-细化报销skill/12月公出-发票"
RUN = Path(__file__).resolve().parent
MANIFEST = ROOT / "automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json"

# 每类首件 + 特证件（同尺寸簇成员/拆分票/返回票；rel 均为 facts 实测路径）
SPOT = [
    ("toll_first", "0825/0825厦门到晋江发票.pdf"),
    ("toll_daishou_0906_a", "0906/0905厦门到晋江发票1.pdf"),
    ("toll_split_0906_b", "0906/0905厦门到晋江发票2.pdf"),
    ("toll_1210_p2", "1210/1210晋江-厦门1 (2).pdf"),
    ("cluster_41802_a", "1028/1028晋江到厦门发票.pdf"),
    ("cluster_41802_b", "1112/1112厦门到晋江发票.pdf"),
    ("summary_first", "0825/0825通行费电子票据汇总单(票据).pdf"),
    ("summary_trip_0917", "0917/0917通行费电子票据汇总单(行程).pdf"),
    ("fuel_first", "油票/油票1.pdf"),
]


def main() -> int:
    ev = RUN / "evidence"
    ev.mkdir(exist_ok=True)
    renders = []
    for tag, rel in SPOT:
        path = CASE / rel
        doc = fitz.open(str(path))
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        out = ev / f"spot_{tag}.png"
        pix.save(str(out))
        renders.append({"tag": tag, "rel": rel, "page": 1, "png_sha256": hashlib.sha256(out.read_bytes()).hexdigest()})
        doc.close()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = [(gname, f) for gname, g in manifest["groups"].items() for f in g["files"]]
    drift = []
    for gname, f in files:
        digest = hashlib.sha256((CASE / f["rel"]).read_bytes()).hexdigest()
        if digest != f["sha256"]:
            drift.append(f["rel"])
    (RUN / "stage_d_render_posthash.json").write_text(
        json.dumps({"renders": renders, "post_hash_files": len(files), "post_hash_drift": drift,
                    "render_note": "fitz 150dpi 只读渲染；原图目录未写入"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"renders: {len(renders)}; post-hash: {len(files)} files, drift={'NONE' if not drift else drift}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
