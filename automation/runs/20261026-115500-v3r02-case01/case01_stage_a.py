# -*- coding: utf-8 -*-
"""V3-R02 CASE-01 阶段 A：73 件原件全量原始层 dump（只读）。

复用 bpm_extraction.extract_pdf_text（fitz 行级 bbox+页/区域锚点）与 file_hash；
输出 raw/<idx>_<relname>.json，附每件 sha256（对 round-1 manifest 即时对账）。
不写原件目录；不预设任何业务结论。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bpm_extraction import extract_pdf_text  # noqa: E402

CASE = ROOT / "feature01-细化报销skill/12月公出-发票"
RUN = ROOT / "automation/runs/20261026-115500-v3r02-case01"
MANIFEST = ROOT / "automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = [(g, f) for gname, g in manifest["groups"].items() for f in g["files"]]
    (RUN / "raw").mkdir(parents=True, exist_ok=True)
    index, drift = [], []
    for i, (group, f) in enumerate(files, start=1):
        path = CASE / f["rel"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != f["sha256"]:
            drift.append(f["rel"])
        extracted = extract_pdf_text(str(path))
        record = {
            "idx": i,
            "group": group if isinstance(group, str) else group.get("name"),
            "rel": f["rel"],
            "sha256": digest,
            "pages": extracted["pages"],
            "items": extracted["items"],
        }
        safe = f["rel"].replace("/", "__").replace(" ", "_").replace("(", "(").replace(")", ")")
        (RUN / "raw" / f"{i:02d}_{safe}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({"idx": i, "rel": f["rel"], "sha256": digest, "pages": extracted["pages"],
                      "lines": len(extracted["items"])})
    (RUN / "stage_a_index.json").write_text(
        json.dumps({"files": index, "drift": drift, "count": len(index)}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(f"stage A done: {len(index)} files, drift={drift if drift else 'NONE'}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
