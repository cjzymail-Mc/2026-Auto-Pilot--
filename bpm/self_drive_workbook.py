"""Bounded V3-layout mileage-copy backfill and persisted Excel recalculation.

Only the known F/G/H/I mileage layout is supported. The original stays read-only;
meal allowance remains in the separate scenario calculation, not a new column.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from zipfile import BadZipFile
from decimal import Decimal
from pathlib import Path

from bpm.materials import _safe_material
from bpm.plan import file_hash, money
from bpm.self_drive_plan import _Evidence, assess_self_drive, SelfDriveBindingError


def _cached_cents(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("missing numeric recalculation cache")
    raw = Decimal(str(value))
    if not raw.is_finite():
        raise ValueError("nonfinite Excel value")
    cents = raw.quantize(Decimal(".01"))
    if abs(raw - cents) > Decimal("0.0000001"):
        raise ValueError("Excel result is not a cent amount; not just a floating-point tail")
    return cents


def _snapshot(book):
    return {"sheets": book.sheetnames,
            "merges": {ws.title: sorted(str(r) for r in ws.merged_cells.ranges) for ws in book},
            "cells": {(ws.title, cell.coordinate): (cell.value, cell.number_format)
                      for ws in book for row in ws for cell in row if cell.value is not None}}


def _recalculate_with_excel(path, sheet, assignments):
    """Own hidden Excel instance, macros/events/link updates disabled; no active app."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    excel, book = None, None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False
        excel.AskToUpdateLinks = False
        excel.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        book = excel.Workbooks.Open(str(path), UpdateLinks=0, ReadOnly=False, AddToMru=False)
        ws = book.Worksheets(sheet)
        for row, value in assignments.items():
            ws.Cells(row, 8).Value = float(money(value))
            ws.Cells(row, 9).Formula = f"=G{row}+H{row}"
        excel.CalculateFullRebuild()
        book.Save()
        book.Close(SaveChanges=False)
        book = None
        return "excel_com"
    except Exception as exc:
        raise SelfDriveBindingError("owned Excel recalculation failed: " + str(exc)) from exc
    finally:
        cleanup_errors = []
        try:
            if book is not None:
                try:
                    book.Close(SaveChanges=False)
                except Exception as exc:
                    cleanup_errors.append(str(exc))
            if excel is not None:
                try:
                    excel.Quit()
                except Exception as exc:
                    cleanup_errors.append(str(exc))
        finally:
            pythoncom.CoUninitialize()
        if cleanup_errors:
            raise SelfDriveBindingError("owned Excel cleanup uncertain: " + "; ".join(cleanup_errors))


def prepare_workbook_copy(*, inputs_path, manifest_path, workbook_path,
                          row_map, output_dir, sheet="汇总"):
    """Assess sourced inputs, backfill a NEW copy and reopen its stored caches.

    row_map maps scenario row IDs to actual worksheet row numbers. It is routing,
    never an amount source: each packet's km proof must reference exactly F<row>
    of this original workbook. Source totals, formulas and original subsidy
    values must agree before any copy is created.
    """
    import openpyxl
    inputs_path, manifest_path, source, output = (
        _safe_material(Path(p)) for p in (inputs_path, manifest_path, workbook_path, output_dir))
    if source.suffix.lower() != ".xlsx":
        raise SelfDriveBindingError("only the observed xlsx mileage layout is supported")
    if output.exists() or any(output == p.parent or output in p.parents or p.parent in output.parents
                              for p in (source, inputs_path, manifest_path)):
        raise SelfDriveBindingError("workbook output must be a separate, new directory")
    manifest_sha, input_sha, original_sha = (file_hash(p) for p in (manifest_path, inputs_path, source))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ev = _Evidence(manifest, manifest_path.parent)
    original_paths = {str(ev.path(item["path"])) for item in manifest.get("files", [])}
    if str(source) not in original_paths or ev.files.get(str(inputs_path)) != input_sha:
        raise SelfDriveBindingError("original workbook and registered input packet required in the same manifest")
    packet = json.loads(inputs_path.read_text(encoding="utf-8"))
    result = assess_self_drive(packet, manifest, base_dir=manifest_path.parent)
    rows = {row["row_id"]: row for row in result["calculation"]["rows"]}
    if (not isinstance(row_map, dict) or set(row_map) != set(rows)
            or any(isinstance(v, bool) or not isinstance(v, int) for v in row_map.values())
            or len(set(row_map.values())) != len(row_map)):
        raise SelfDriveBindingError("unique, exhaustive scenario-row to worksheet-row mapping required")
    for item in packet["rows"]:
        proof = item["km"]
        if (ev.path(proof["path"]) != source or proof["sha256"] != original_sha
                or proof["locator"] != f"{sheet}!F{row_map[item['row_id']]}"):
            raise SelfDriveBindingError("mileage proof must bind this original workbook and exact mapped F cell")
    book = openpyxl.load_workbook(source, data_only=False)
    try:
        ws = book[sheet]
        for coordinate, prefix in [("F3", "公里"), ("G3", "补贴金额"), ("H3", "过路费"), ("I3", "合计")]:
            if not str(ws[coordinate].value or "").startswith(prefix):
                raise SelfDriveBindingError("unsupported mileage header at " + coordinate)
        sums = []
        for row in ws:
            for cell in row:
                value = cell.value
                if isinstance(value, str) and value.startswith("="):
                    if any(token in value.upper() for token in ["[", "WEBSERVICE(", "HYPERLINK(", "RTD(", "DDE("]):
                        raise SelfDriveBindingError("external/active formula is outside offline workbook scope")
                if cell.column == 9 and isinstance(value, str):
                    match = re.fullmatch(r"=SUM\(I([0-9]+):I([0-9]+)\)", value, re.I)
                    if match:
                        sums.append((cell.coordinate, int(match[1]), int(match[2]), value))
        if len(sums) != 1:
            raise SelfDriveBindingError("one existing I-column SUM total required; no guessed formulas")
        total_cell, start, end, total_formula = sums[0]
        if start != 4 or int(total_cell[1:]) != end + 1 or set(row_map.values()) != set(range(start, end + 1)):
            raise SelfDriveBindingError("mapping must cover the complete observed mileage table")
        before = _snapshot(book)
        assignments, expected, changes = {}, {}, []
        for rid, row in rows.items():
            index = row_map[rid]
            if money(str(ws[f"F{index}"].value)) != money(row["km"]):
                raise SelfDriveBindingError("workbook mileage differs from independently sourced input")
            if money(str(ws[f"G{index}"].value)) != money(row["row_subsidy"]):
                raise SelfDriveBindingError("existing subsidy conflicts with frozen rate; original G is not overwritten")
            current_h, current_i = ws[f"H{index}"].value, ws[f"I{index}"].value
            if current_h not in (None, "") and money(str(current_h)) != money(row["row_toll"]):
                raise SelfDriveBindingError("existing toll amount conflicts; no silent overwrite")
            if current_i not in (None, "", f"=G{index}+H{index}"):
                raise SelfDriveBindingError("unsupported existing row-total value/formula")
            assignments[index] = row["row_toll"]
            expected[index] = money(row["row_transport"])
            changes.append({"row_id": rid, "worksheet_row": index,
                            "H": {"old": current_h, "new": row["row_toll"]},
                            "I": {"old": current_i, "new_formula": f"=G{index}+H{index}"},
                            "toll_ids": row["toll_ids"]})
    finally:
        book.close()
    output.mkdir(parents=True, exist_ok=False)
    copy = output / "mileage-verified.xlsx"
    shutil.copyfile(source, copy)
    report = {"status": "NEEDS_INPUT", "real_fill_verified": False, "real_save_verified": False,
              "source_sha256": original_sha, "inputs_sha256": input_sha, "manifest_sha256": manifest_sha,
              "changes": changes, "rules_sha256": result["rules_sha256"]}
    try:
        report["engine"] = _recalculate_with_excel(copy, sheet, assignments)
        reopened = openpyxl.load_workbook(copy, data_only=False)
        try:
            after = _snapshot(reopened)
            allowed = {(sheet, f"{col}{index}") for index in assignments for col in ["H", "I"]}
            if before["sheets"] != after["sheets"] or before["merges"] != after["merges"]:
                raise SelfDriveBindingError("workbook structure changed")
            if any(before["cells"].get(key) != after["cells"].get(key)
                   for key in set(before["cells"]) | set(after["cells"]) if key not in allowed):
                raise SelfDriveBindingError("cells outside authorized H/I changes differ")
            for index, amount in assignments.items():
                if (_cached_cents(reopened[sheet][f"H{index}"].value) != money(amount)
                        or reopened[sheet][f"I{index}"].value != f"=G{index}+H{index}"):
                    raise SelfDriveBindingError("saved row amount/formula differs")
            if reopened[sheet][total_cell].value != total_formula:
                raise SelfDriveBindingError("original total formula changed")
        finally:
            reopened.close()
        cached = openpyxl.load_workbook(copy, data_only=True, read_only=True)
        try:
            measured = {index: _cached_cents(cached[sheet][f"I{index}"].value) for index in expected}
            transport = sum(expected.values(), Decimal(0))
            if measured != expected or _cached_cents(cached[sheet][total_cell].value) != transport:
                raise SelfDriveBindingError("persisted Excel calculation differs from independent Decimal recomputation")
        finally:
            cached.close()
        if (file_hash(source), file_hash(inputs_path), file_hash(manifest_path)) != (original_sha, input_sha, manifest_sha):
            raise SelfDriveBindingError("input drift during workbook calculation")
        # Revalidate every located input, not merely the packet's outer hash.
        fresh = assess_self_drive(packet, manifest, base_dir=manifest_path.parent)
        if fresh != result:
            raise SelfDriveBindingError("scenario evidence or rules drift during calculation")
        report.update(status="WORKBOOK_VERIFIED_OFFLINE", copy_path=str(copy), copy_sha256=file_hash(copy),
                      transport_total=str(transport), meal_separate=result["calculation"]["C_meal"],
                      reimbursement_total=result["calculation"]["R_reimburse"],
                      persisted_cache_verified=True, original_unchanged=True)
    except (OSError, ValueError, TypeError, KeyError, ImportError, BadZipFile) as exc:
        report.update(status="NEEDS_INPUT", message=str(exc), persisted_cache_verified=False)
    finally:
        (output / "workbook_result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ["inputs", "manifest", "workbook", "row-map", "output"]:
        p.add_argument("--" + flag, required=True)
    p.add_argument("--sheet", default="汇总")
    args = p.parse_args(argv)
    try:
        row_map_path = _safe_material(Path(args.row_map))
        result = prepare_workbook_copy(inputs_path=args.inputs, manifest_path=args.manifest,
                                       workbook_path=args.workbook,
                                       row_map=json.loads(row_map_path.read_text(encoding="utf-8")),
                                       output_dir=args.output, sheet=args.sheet)
        print(json.dumps({"status": result["status"], "browser_launched": False,
                          "persisted_cache_verified": result.get("persisted_cache_verified", False)}, ensure_ascii=False))
        return 0 if result["status"] == "WORKBOOK_VERIFIED_OFFLINE" else 2
    except (OSError, ValueError, TypeError, KeyError, ImportError, BadZipFile) as exc:
        print(json.dumps({"status": "NEEDS_INPUT", "message": str(exc), "browser_launched": False}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
