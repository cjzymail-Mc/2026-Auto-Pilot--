# -*- coding: utf-8 -*-
"""识票归集（BPM-SELFDRIVE-20261027-V1 D04）：原件只读识别 → 分类 → 唯一身份 →
规范命名整理副本 → 可逆映射。归集不产生任何费用结论——计费/餐补/覆盖由事实层与
bpm_self_drive 按规则另行计算，汇总单只作交叉核对。

纪律（合同 §4.2/D04）：
- 原件零写入：只读抽取嵌入文本层（bpm_extraction.extract_pdf_text）；整理副本只落
  独立输出目录，绝不写回材料目录；
- 机读优先：无文本层页登记 GAP（needs_visual_review），不猜值、不本地兜底 OCR、
  不上传第三方；
- 唯一票据身份 = 发票号码（辅以发票代码）；同票不同扫描合并为一身份多扫描；
  同金额不同票号绝不合并（金额不是身份）；
- 多票容器按页分组拆 record（每 record 唯一 record_id + 原件页/区域定位）；
  同页多身份仍 GAP——区域级拆分未授权，沿用一票一件契约的拒绝保护；
- 汇总单区分 票据/行程 双版式，仅交叉核对（票号在场 + 交易金额 vs 独立发票面值
  合计），不重复计费；
- 开票日期（票面）、行程日期（汇总单）、目录日期（材料目录名）分开记录不混用；
- 幂等：同一输入重跑产物逐字节一致（无时间戳、排序确定、record_id/副本名由
  身份哈希决定）；防覆盖：目标副本已存在且哈希不同即报错。

命名规则（缺字段按明确规则，不猜值）：`日期_票种_方向或路线_票号_短哈希.pdf`
- 日期=票面开票日期 YYYYMMDD；缺失用 `无日期` 并登记 GAP。
- 票种∈{通行费发票, 油票, 汇总单票据, 汇总单行程}。
- 方向或路线：仅取自原文件名中的 `X到Y`/`X-Y` 段（用户目录结构语义）；缺失省略该段。
- 票号=发票号码（汇总单用汇总单号）；缺失用 `无票号` 并登记 GAP。
- 短哈希=sha256(身份键)[:8]。重复扫描不产生第二副本（同身份同副本名，多原件映射到它）。
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from bpm.extraction import INVOICE_FIELD_PATTERN_BY_FIELD, extract_pdf_text

CLASS_TOLL_INVOICE = "toll_invoice"
CLASS_FUEL_INVOICE = "fuel_invoice"
CLASS_SUMMARY_BY_TICKET = "summary_by_ticket"
CLASS_SUMMARY_BY_TRIP = "summary_by_trip"
CLASS_UNKNOWN = "unknown"

KIND_LABELS = {CLASS_TOLL_INVOICE: "通行费发票", CLASS_FUEL_INVOICE: "油票",
               CLASS_SUMMARY_BY_TICKET: "汇总单票据", CLASS_SUMMARY_BY_TRIP: "汇总单行程"}
INVOICE_CLASSES = (CLASS_TOLL_INVOICE, CLASS_FUEL_INVOICE)
_ROUTE_RE = re.compile(r"([一-龥]{2,8})(?:到|-)([一-龥]{2,8})")
_ROUTE_TAIL_RE = re.compile(r"(发票|油票|票据|汇总单|票)$")
_DATE_CN_RE = re.compile(r"([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日")
_DATE_ISO_RE = re.compile(r"([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})")
_SUMMARY_NUMBER_RE = re.compile(r"汇总单号[：:]\s*([0-9]+)")
_SUMMARY_TOTAL_RE = re.compile(r"交易金额[^0-9]*([0-9]+(?:\.[0-9]{1,2})?)")


class CollectionError(ValueError):
    """归集结构性违规（防覆盖冲突/不可读原件/身份冲突）。"""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page_text(items, page: int) -> str:
    return "\n".join(item["text"] for item in items if item["page"] == page)


def classify_page_text(text: str) -> str:
    """按页文本分类：汇总单（票据/行程）→ 油票 → 通行费发票 → unknown。"""
    if "收费公路通行费电子票据汇总单" in text:
        if "按行程索引" in text:
            return CLASS_SUMMARY_BY_TRIP
        return CLASS_SUMMARY_BY_TICKET
    if "成品油" in text and "发票号码" in text:
        return CLASS_FUEL_INVOICE
    if "发票号码" in text and ("增值税电子普通发票" in text or "通行日期" in text):
        return CLASS_TOLL_INVOICE
    return CLASS_UNKNOWN


def _identity_hits(items, page: int):
    """页内全部发票身份命中（与 extract_pdf_facts 同一拒绝保护口径）。
    真实票据文本层多为列式（标签/值分 span），同 span 正则之外补充同视觉行绑定。"""
    hits = {}
    for field in ("invoice_number", "invoice_code"):
        for value, _ in _field_candidates(items, page, field):
            hits.setdefault(field, []).append((value, None))
    return hits


# 列式文本层绑定：标签项与值项分行分 span（如 发票号码: | 16304714 各自独立）。
# 绑定规则：值与标签同一视觉行（纵向中心差 < 行高×0.7+2.5）且在标签右侧，取水平最近。
_COLUMNAR_SPECS = {
    "invoice_number": (re.compile(r"^发票号码\s*[：:]\s*$"), re.compile(r"^[0-9A-Za-z\-]{6,}$")),
    "invoice_code": (re.compile(r"^发票代码\s*[：:]\s*$"), re.compile(r"^[0-9]{8,}$")),
    "issue_date": (re.compile(r"^开票日期\s*[：:]\s*$"),
                   re.compile(r"^[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日$|^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}$")),
    "total_amount": (re.compile(r"^（小写）$"), re.compile(r"^[¥￥]\s*[0-9]+(?:\.[0-9]{1,2})?$")),
}
# 同 span 内 “（小写）¥444.15” 形态（油票：小写与金额同一 span）
_AMOUNT_INLINE_RE = re.compile(r"（小写）\s*[¥￥]?\s*([0-9]+(?:\.[0-9]{1,2})?)")


def _y_center(bbox) -> float:
    return (bbox[1] + bbox[3]) / 2.0


def _bind_columnar_value(items, page: int, field: str):
    label_re, value_re = _COLUMNAR_SPECS[field]
    best = None
    for label in items:
        if label["page"] != page or not label_re.fullmatch(label["text"].strip()):
            continue
        for value in items:
            if value["page"] != page or value is label:
                continue
            text = value["text"].strip()
            if not value_re.fullmatch(text):
                continue
            row_gap = abs(_y_center(value["bbox"]) - _y_center(label["bbox"]))
            height = max(label["bbox"][3] - label["bbox"][1],
                         value["bbox"][3] - value["bbox"][1])
            if row_gap > height * 0.7 + 2.5 or value["bbox"][0] < label["bbox"][2] - 3:
                continue
            rank = (value["bbox"][0] - label["bbox"][2], row_gap, text)
            if best is None or rank < best[0]:
                best = (rank, value, label)
    if best is None:
        return None
    _, value, label = best
    return {"value": value["text"].strip(), "anchor": {"page": page, "region": value["region"],
                                                        "bbox": value["bbox"]}}


def _field_candidates(items, page: int, field: str):
    """页内某字段全部取值候选：同 span 正则命中 + 列式行绑定（合计去重，保序）。"""
    found = []
    for item in items:
        if item["page"] != page:
            continue
        if field == "total_amount":
            match = _AMOUNT_INLINE_RE.search(item["text"])
        else:
            match = INVOICE_FIELD_PATTERN_BY_FIELD[field].search(item["text"])
        if match:
            value = match.group(1)
            if value not in [v for v, _ in found]:
                found.append((value, item))
    bound = _bind_columnar_value(items, page, field)
    if bound:
        value = bound["value"]
        if field == "total_amount":
            value = re.sub(r"^[¥￥]\s*", "", value)
        if value not in [v for v, _ in found]:
            found.append((value, None))
    return found


def _field_on_page(items, page: int, field: str):
    candidates = _field_candidates(items, page, field)
    if not candidates:
        return None
    value, _ = candidates[0]
    return {"value": value, "anchor": {"page": page, "region": "body"}}


def _normalize_date(raw: str) -> str:
    match = _DATE_CN_RE.fullmatch(raw.strip()) or _DATE_ISO_RE.fullmatch(raw.strip())
    if not match:
        return ""
    return "{0:04d}-{1:02d}-{2:02d}".format(*(int(part) for part in match.groups()))


def _route_from_stem(stem: str) -> str:
    match = _ROUTE_RE.search(stem)
    if not match:
        return ""
    dest = _ROUTE_TAIL_RE.sub("", match.group(2))   # 剥离误入方向段的票类后缀词
    if not dest or dest == match.group(1):
        return match.group(1)
    return "{0}到{1}".format(match.group(1), dest)


def _safe_segment(value: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]', "", value)


def analyze_pdf(path: Path) -> dict:
    """单原件只读分析：页分类、逐页身份、票面字段锚点、GAP。不改任何文件。"""
    lines = extract_pdf_text(path)
    items = lines["items"]
    pages = []
    gaps = []
    for page in range(1, lines["pages"] + 1):
        text = _page_text(items, page)
        page_class = classify_page_text(text)
        page_entry = {"page": page, "class": page_class}
        if not text.strip():
            gaps.append({"gap": "needs_visual_review", "file": str(path),
                         "locator": "page:{0}".format(page),
                         "detail": "无嵌入文本层；按仓库视觉路由复核，不猜值"})
            pages.append(page_entry)
            continue
        if page_class in INVOICE_CLASSES:
            hits = _identity_hits(items, page)
            numbers = []
            for value, _ in hits.get("invoice_number", []):
                if value not in numbers:
                    numbers.append(value)
            if len(numbers) > 1:
                gaps.append({"gap": "multi_identity_single_page", "file": str(path),
                             "locator": "page:{0}".format(page),
                             "detail": "同页多发票身份（{0} 个）；区域级拆分未授权，登记 GAP".format(len(numbers)),
                             "candidates": numbers})
            elif numbers:
                page_entry["invoice_number"] = numbers[0]
                codes = []
                for value, _ in hits.get("invoice_code", []):
                    if value not in codes:
                        codes.append(value)
                if codes:
                    page_entry["invoice_code"] = codes[0]
        elif page_class == CLASS_UNKNOWN:
            gaps.append({"gap": "unclassified_page", "file": str(path),
                         "locator": "page:{0}".format(page),
                         "detail": "无法按已知票类分类（非汇总单/通行费/油票）"})
        pages.append(page_entry)
    return {"pages": pages, "gaps": gaps, "text_items": items,
            "text": "\n".join(item["text"] for item in items)}


def collect_materials(materials_dir, out_dir, *, write_copies=True) -> dict:
    """全量归集：只读分析原件 → 身份去重 → （可选）规范命名副本 → 可逆映射 manifest。

    返回的 manifest 为纯确定性数据（无时间戳）：同输入重跑逐字节一致。
    write_copies=False 只产映射不落副本（盘点/测试用）。
    """
    root = Path(materials_dir)
    if not root.is_dir():
        raise CollectionError("材料目录不存在: {0}".format(root))
    out = Path(out_dir)
    copies_dir = out / "collected"
    if write_copies:
        copies_dir.mkdir(parents=True, exist_ok=True)

    files, identities, summaries, gaps = [], {}, [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        sha = _sha256_file(path)
        entry = {"rel": rel, "sha256": sha, "bytes": path.stat().st_size}
        if path.suffix.lower() != ".pdf":
            entry["kind"] = "non_pdf_material"   # 公里表等：入映射，不产票据副本
            entry["copy"] = None
            files.append(entry)
            continue
        analysis = analyze_pdf(path)
        classes = {page["class"] for page in analysis["pages"]}
        entry["pages"] = [{k: v for k, v in page.items()} for page in analysis["pages"]]
        gaps.extend(gap.update({"file": rel}) or gap for gap in analysis["gaps"])
        if CLASS_SUMMARY_BY_TICKET in classes or CLASS_SUMMARY_BY_TRIP in classes:
            variant = CLASS_SUMMARY_BY_TRIP if CLASS_SUMMARY_BY_TRIP in classes else CLASS_SUMMARY_BY_TICKET
            number_match = _SUMMARY_NUMBER_RE.search(analysis["text"])
            total_match = _SUMMARY_TOTAL_RE.search(analysis["text"])
            summary = {"file": rel, "variant": variant, "dir": rel.split("/")[0],
                       "summary_number": number_match.group(1) if number_match else "",
                       "transaction_total": total_match.group(1) if total_match else "",
                       "sha256": sha}
            if not summary["summary_number"]:
                gaps.append({"gap": "summary_number_missing", "file": rel,
                             "locator": "page:1", "detail": "汇总单号未机读到，不猜值"})
            summary["copy"] = None
            summaries.append(summary)
            entry["kind"] = variant
            entry["summary_number"] = summary["summary_number"]
            entry["copy"] = None
            files.append(entry)
            continue
        # 发票页：按页归并身份（多页多票 → 一身份多页组；同页多票已 GAP）
        entry_identities = []
        for page in analysis["pages"]:
            if page["class"] not in INVOICE_CLASSES or "invoice_number" not in page:
                continue
            number = page["invoice_number"]
            locator = "page:{0}".format(page["page"])
            date_field = _field_on_page(analysis["text_items"], page["page"], "issue_date")
            total_field = _field_on_page(analysis["text_items"], page["page"], "total_amount")
            record = identities.get(number)
            created = record is None
            if created:
                record = {"record_id": "inv-" + hashlib.sha256(number.encode("utf-8")).hexdigest()[:8],
                          "number": number, "class": page["class"],
                          "code": page.get("invoice_code", ""),
                          "issue_date": _normalize_date(date_field["value"]) if date_field else "",
                          "face_total": total_field["value"] if total_field else "",
                          "scans": []}
                identities[number] = record
            else:
                if record["class"] != page["class"]:
                    gaps.append({"gap": "identity_class_conflict", "file": rel, "locator": locator,
                                 "detail": "票号 {0} 在不同文件被分类为 {1}/{2}".format(
                                     number, record["class"], page["class"])})
                if total_field and record["face_total"] and total_field["value"] != record["face_total"]:
                    gaps.append({"gap": "identity_face_conflict", "file": rel, "locator": locator,
                                 "detail": "票号 {0} 两次扫描面值不一致: {1}/{2}".format(
                                     number, record["face_total"], total_field["value"])})
            record["scans"].append({"file": rel, "locator": locator,
                                    "source_sha256": sha})
            if not record["issue_date"] and date_field:
                record["issue_date"] = _normalize_date(date_field["value"])
            if not record["face_total"] and total_field:
                record["face_total"] = total_field["value"]
            entry_identities.append(number)
        entry["kind"] = "invoice_file" if entry_identities else "pdf_other"
        entry["identities"] = entry_identities
        entry["copy"] = None
        files.append(entry)

    # 副本命名与写入（身份顺序确定 → 文件名确定 → 幂等）
    for number in sorted(identities):
        record = identities[number]
        if not record["issue_date"]:
            gaps.append({"gap": "issue_date_missing", "file": record["scans"][0]["file"],
                         "locator": record["scans"][0]["locator"],
                         "detail": "票号 {0} 未机读到开票日期，副本名用 无日期 占位".format(number)})
        if not record["face_total"]:
            gaps.append({"gap": "face_total_missing", "file": record["scans"][0]["file"],
                         "locator": record["scans"][0]["locator"],
                         "detail": "票号 {0} 未机读到价税合计".format(number)})
        first_scan = record["scans"][0]
        stem = Path(first_scan["file"]).stem
        date_segment = record["issue_date"].replace("-", "") or "无日期"
        route = _route_from_stem(stem)
        segments = [date_segment, KIND_LABELS[record["class"]]]
        if route:
            segments.append(route)
        segments.extend([number, record["record_id"].split("-")[1]])
        copy_name = _safe_segment("_".join(segments)) + ".pdf"
        source = root / first_scan["file"]
        record["copy_name"] = copy_name
        record["copy_sha256"] = None
        if write_copies:
            target = copies_dir / copy_name
            content_sha = _sha256_file(source)
            if target.exists():
                if _sha256_file(target) != content_sha:
                    raise CollectionError("防覆盖冲突: {0} 已存在且内容不同".format(target))
            else:
                target.write_bytes(source.read_bytes())
            record["copy_sha256"] = content_sha
    for summary in summaries:
        if not write_copies:
            continue
        source = root / summary["file"]
        # 日期槽规则：汇总单版面日期为“开票申请日期”，非票据开票日期语义，不冒用——占位 无日期
        segments = ["无日期", KIND_LABELS[summary["variant"]],
                    summary["summary_number"] or "无单号",
                    hashlib.sha256(summary["sha256"].encode("utf-8")).hexdigest()[:8]]
        copy_name = _safe_segment("_".join(segments)) + ".pdf"
        target = copies_dir / copy_name
        if target.exists():
            if _sha256_file(target) != summary["sha256"]:
                raise CollectionError("防覆盖冲突: {0} 已存在且内容不同".format(target))
        else:
            target.write_bytes(source.read_bytes())
        summary["copy"] = copy_name

    # 可逆映射落盘（确定性）：文件 → 身份/副本、身份 → 扫描/副本
    for entry in files:
        for number in entry.get("identities", []) or []:
            entry["copy"] = identities[number]["copy_name"]
        if entry.get("kind") in (CLASS_SUMMARY_BY_TICKET, CLASS_SUMMARY_BY_TRIP):
            for summary in summaries:
                if summary["file"] == entry["rel"]:
                    entry["copy"] = summary["copy"]

    manifest = {
        "schema_version": "1.0",
        "materials_root": str(root),
        "rules": {"identity": "invoice_number（辅 invoice_code）；同票不同扫描合并；金额不作身份",
                  "naming": "日期_票种_方向或路线_票号_短哈希.pdf；方向仅取原文件名 X到Y/X-Y 段，缺失省略；日期/票号缺失用 无日期/无票号 占位并登记 GAP",
                  "copies": "仅整理副本写入输出目录，原件零改动；重复扫描不产生第二副本",
                  "summary_sheets": "汇总单仅交叉核对不计费；开票日期/行程日期/目录日期分开"},
        "files": sorted(files, key=lambda item: item["rel"]),
        "identities": [identities[number] for number in sorted(identities)],
        "summaries": sorted(summaries, key=lambda item: item["file"]),
        "gaps": sorted(gaps, key=lambda gap: (gap.get("file", ""), str(gap.get("locator", "")), gap["gap"])),
    }
    return manifest


def _dedup_summaries(summaries):
    """同 汇总单号 的 票据/行程 双版式是同一份汇总单的两种渲染——按单号去重，
    交易金额取票据版（缺则行程版）；两版式金额不一致如实标记，不静默取舍。"""
    groups = {}
    for summary in summaries:
        groups.setdefault(summary["summary_number"] or summary["file"], []).append(summary)
    result = []
    for key in sorted(groups):
        members = groups[key]
        by_ticket = [m for m in members if m["variant"] == CLASS_SUMMARY_BY_TICKET]
        chosen = by_ticket[0] if by_ticket else members[0]
        totals = {m["transaction_total"] for m in members}
        result.append({"summary_number": key, "transaction_total": chosen["transaction_total"],
                       "variant_totals_consistent": len(totals) <= 1,
                       "members": sorted(m["file"] for m in members)})
    return result


def cross_check_summaries(manifest, *, root=None) -> list:
    """汇总单互证（只读、不改 manifest）：票号在场 + 每目录 交易金额合计 vs 独立发票面值合计。

    返回 per-dir 结果列表；差异如实列 report 项（不抛错、不篡改识别结果）。
    """
    root = Path(root or manifest["materials_root"])
    by_dir_invoices, by_dir_summaries = {}, {}
    for record in manifest["identities"]:
        if record["class"] != CLASS_TOLL_INVOICE:
            continue
        for scan in record["scans"]:
            directory = scan["file"].split("/")[0]
            seen = by_dir_invoices.setdefault(directory, [])
            if record["number"] not in [item["number"] for item in seen]:
                seen.append(record)   # 同目录重复扫描只计一次身份，面值不重复累计
    for summary in manifest["summaries"]:
        by_dir_summaries.setdefault(summary["dir"], []).append(summary)
    results = []
    all_dirs = sorted(set(by_dir_invoices) | set(by_dir_summaries))
    from decimal import Decimal
    for directory in all_dirs:
        records = by_dir_invoices.get(directory, [])
        summary_files = by_dir_summaries.get(directory, [])
        deduped = _dedup_summaries(summary_files)
        summary_total = sum((Decimal(g["transaction_total"] or "0") for g in deduped), Decimal("0"))
        face_total = sum((Decimal(r["face_total"] or "0") for r in records), Decimal("0"))
        numbers_missing = []
        summary_text = ""
        for summary in summary_files:
            analysis = analyze_pdf(root / summary["file"])
            summary_text += analysis["text"] + "\n"
        for record in records:
            if record["number"] not in summary_text:
                numbers_missing.append(record["number"])
        results.append({
            "dir": directory, "toll_identity_count": len(records),
            "summary_file_count": len(summary_files),
            "summary_number_count": len(deduped),
            "summary_transaction_total": str(summary_total.quantize(Decimal("0.01"))),
            "invoice_face_total": str(face_total.quantize(Decimal("0.01"))),
            "totals_match": summary_total == face_total,
            "variant_totals_inconsistent": [g["summary_number"] for g in deduped
                                            if not g["variant_totals_consistent"]],
            "numbers_missing_from_summary": numbers_missing,
        })
    return results
