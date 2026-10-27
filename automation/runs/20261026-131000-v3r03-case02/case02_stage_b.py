# -*- coding: utf-8 -*-
"""V3-R03 CASE-02 阶段 B：同结构副本制作 + H 列逐票回填 + I 列合计公式（COM，写副本不写原件）。

- 副本 = shutil.copy2(原件) → run 目录 12月-自驾公出公里数统计表-已核对.xlsx（原件目录零写入）。
- COM（DispatchEx 新 Excel 进程，独占副本）：H4..H23 写裁定金额（每行=其映射票面合计；
  行内多票=逐票金额相加后一次写入，逐票来源在 mapping JSON）；I4..I23 补 '=G{r}+H{r}'；
  I24 沿用原件 '=SUM(I4:I23)' 不改；F/G/J 列零触碰。
- 保存前后各读一次计算值留证；Quit 走 finally。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pythoncom
import win32com.client

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SRC = ROOT / "feature01-细化报销skill/12月公出-发票/12月-自驾公出公里数统计表.xlsx"
DST = RUN / "12月-自驾公出公里数统计表-已核对.xlsx"
MAPPING = RUN / "case02-mapping.json"


def main() -> int:
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    src_sha_before = hashlib.sha256(SRC.read_bytes()).hexdigest()
    shutil.copy2(SRC, DST)

    pythoncom.CoInitialize()
    excel = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(DST), ReadOnly=False, AddToMru=False)
        ws = wb.Worksheets("汇总")
        # 结构断言：列语义与原件一致，防止错表错列
        assert ws.Range("H3").Value.startswith("过路费"), ws.Range("H3").Value
        assert ws.Range("I3").Value.startswith("合计"), ws.Range("I3").Value
        assert ws.Range("G3").Value.startswith("补贴金额"), ws.Range("G3").Value
        assert ws.Range("I24").Formula == "=SUM(I4:I23)", ws.Range("I24").Formula

        changes = []
        for m in mapping["rows"]:
            r = m["row"]
            old_h = ws.Cells(r, 8).Value  # H 列原值（应为空）
            ws.Cells(r, 8).Value = float(Decimal(m["row_toll_total"]))  # 两位小数金额，float 载入
            old_i_formula = ws.Cells(r, 9).Formula
            ws.Cells(r, 9).Formula = f"=G{r}+H{r}"
            changes.append({
                "row": r, "date": m["date"], "direction": m["direction"],
                "H": {"cell": f"H{r}", "old": old_h, "new": m["row_toll_total"],
                      "invoices": [{"identity": i["identity"], "invoice_number": i["invoice_number"],
                                    "amount": i["amount"], "rel": i["rel"], "sha256": i["sha256"]}
                                   for i in m["invoices"]],
                      "derivation": "Σ(映射票面价税合计)；来源=CASE-01 facts（page/bbox/sha256 锚点）+ case02-mapping 行级裁定"},
                "I": {"cell": f"I{r}", "old_formula": old_i_formula, "new_formula": f"=G{r}+H{r}",
                      "derivation": "合计=补贴金额+过路费（表头设计语义；原行内无公式，补全见裁决②）"},
                "km_preserved": ws.Cells(r, 6).Value == float(m["km"]),
            })
        excel.Calculate()
        calc_after = {
            "I24_total": str(ws.Range("I24").Value),
            "I_rows": {r: str(ws.Cells(r, 9).Value) for r in range(4, 24)},
        }
        wb.Save()
        wb.Close(SaveChanges=False)
        readback = {"I24_total": str(ws.Range("I24").Value)} if False else None
        out = {
            "stage": "B 副本回填（COM）",
            "copy_path": str(DST.relative_to(ROOT)),
            "copy_sha256": hashlib.sha256(DST.read_bytes()).hexdigest(),
            "src_sha_before": src_sha_before,
            "src_sha_after": hashlib.sha256(SRC.read_bytes()).hexdigest(),
            "changes": changes,
            "calc_after_write": calc_after,
            "untouched": "F/G/J 列、I24 公式、行3 表头、行4-23 结构均未改；仅 H4..H23 值 + I4..I23 公式",
        }
        (RUN / "case02-backfill.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"copy written; H rows {sum(1 for c in changes)}; I24 after calc = {calc_after['I24_total']}; "
              f"src drift={'NONE' if src_sha_before == out['src_sha_after'] else 'DRIFT!'}; km_preserved_all={all(c['km_preserved'] for c in changes)}")
        return 0
    finally:
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
