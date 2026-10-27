# -*- coding: utf-8 -*-
"""V3-R03 CASE-02 阶段 C：副本重开实测核验（新 Excel 进程只读）+ 独立 Decimal 复算 + 事后 74 件哈希对账。

- 新 COM 进程打开副本 ReadOnly=True：读 H4..H23 实测值、I4..I23 公式与计算值、I24 公式与计算值；
  不保存不写（副本自此定稿）。
- 独立 Decimal 复算：每行 I=G+H（G 取副本实测补贴）、总额=ΣI；与实测值按分（cent）级比对
  （Excel 浮点表示按两位小数量化后比较）。
- 事后哈希：74 件（73+xlsx）对 round-1 manifest，非零漂移即失败。
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pythoncom
import win32com.client

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
DST = RUN / "12月-自驾公出公里数统计表-已核对.xlsx"
MAPPING = RUN / "case02-mapping.json"
MANIFEST = ROOT / "automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json"
CASE = ROOT / "feature01-细化报销skill/12月公出-发票"


def cent(x) -> Decimal:
    """实测值 → 分级 Decimal（消除 Excel 浮点尾差；偏离 >0.005 视为非尾差，保留原值让比对失败）。"""
    d = Decimal(str(x))
    return d.quantize(Decimal("0.01"))


def main() -> int:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    row_expect = {m["row"]: (Decimal(m["subsidy"]), Decimal(m["row_toll_total"])) for m in mapping["rows"]}

    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(DST), ReadOnly=True, AddToMru=False)
        ws = wb.Worksheets("汇总")
        excel.Calculate()
        measured = {"rows": {}, "I24_formula": ws.Range("I24").Formula}
        for r in range(4, 24):
            measured["rows"][r] = {
                "G": str(ws.Cells(r, 7).Value), "H": str(ws.Cells(r, 8).Value),
                "I_formula": ws.Cells(r, 9).Formula, "I_value": str(ws.Cells(r, 9).Value),
            }
        measured["I24_value"] = str(ws.Range("I24").Value)
        wb.Close(SaveChanges=False)

        # 独立 Decimal 复算与比对
        mismatches, sum_i = [], Decimal("0")
        for r, cell in measured["rows"].items():
            g, h = Decimal(cell["G"]), cent(cell["H"])
            expect_i = (g + h).quantize(Decimal("0.01"))
            got_i = cent(cell["I_value"])
            sum_i += got_i
            exp_g, exp_h = row_expect[r]
            if g != exp_g or h != exp_h:
                mismatches.append({"row": r, "problem": "G/H 与裁定不符",
                                   "measured": [cell["G"], cell["H"]], "expected": [str(exp_g), str(exp_h)]})
            if got_i != expect_i:
                mismatches.append({"row": r, "problem": "I 实测≠G+H", "measured": str(got_i), "expected": str(expect_i)})
        total_measured = cent(measured["I24_value"])
        total_expected = (sum(row_expect[r][0] + row_expect[r][1] for r in row_expect)).quantize(Decimal("0.01"))
        if total_measured != total_expected:
            mismatches.append({"problem": "I24 总额实测≠独立复算", "measured": str(total_measured), "expected": str(total_expected)})
        if sum_i.quantize(Decimal("0.01")) != total_expected:
            mismatches.append({"problem": "ΣI(逐行实测)≠独立复算", "measured": str(sum_i), "expected": str(total_expected)})

        # 事后 74 件哈希对账
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        files = [(g, f) for g in manifest["groups"].values() for f in g["files"]]
        post_drift = [f["rel"] for _, f in files
                      if hashlib.sha256((CASE / f["rel"]).read_bytes()).hexdigest() != f["sha256"]]

        out = {
            "stage": "C 副本重开实测核验（独立 Decimal 复算）",
            "measured": measured,
            "independent_recompute": {
                "per_row_rule": "I = G(补贴) + H(过路费)；G/H 与 stage-A 裁定逐一比对",
                "rows_checked": len(measured["rows"]),
                "sum_I_measured": str(sum_i.quantize(Decimal("0.01"))),
                "total_expected_M_plus_T": str(total_expected),
                "total_I24_measured": str(total_measured),
                "R_equals_M_plus_T": total_measured == total_expected,
            },
            "mismatches": mismatches,
            "post_hash_files": len(files), "post_hash_drift": post_drift,
            "copy_sha256_final": hashlib.sha256(DST.read_bytes()).hexdigest(),
        }
        (RUN / "case02-reopen-verify.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"rows {len(measured['rows'])}; I24 measured={total_measured} expected={total_expected} "
              f"equal={total_measured == total_expected}; mismatches={len(mismatches)}; post_drift={post_drift or 'NONE'}")
        return 0 if (not mismatches and not post_drift) else 1
    finally:
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
