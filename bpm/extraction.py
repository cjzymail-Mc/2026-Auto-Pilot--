"""W03 原件理解：本地 PDF/图片/表格提取与复核管线（离线，不上传任何原件）。

分层契约——所有派生产物经 ``bpm_materials.register_derived`` 写入派生根并绑定原件哈希：
  role=ocr_result          引擎/嵌入文本的原始输出层，永不携带 reviewed 标记；
  role=reviewed_extraction 实际执行过复核的事实层，复核方式/时间/执行者逐字段留证。

硬边界：
  - 文件名（含扩展名以外的名字部分）不作为类别或票据身份证据，扩展名只路由解析器；
  - 本模块不存在「每个非空行生成一条费用」的机械转换路径，行事实只作对账输入；
  - 公式单元格只取缓存值或本地可重算的简单 SUM，公式文本永不当金额；
  - 前导零/丢精度不修复，只登记结构化缺口；
  - OCR 引擎为本机可插拔封闭注册，禁止网络/云端调用；
  - 真实识别路径（2026-10-24 起）：文本 PDF 走嵌入文本层（extract_pdf_text/facts，
    多页行级锚点）；扫描件/图片经 render_pages 全页渲染后由 agent 视觉复核
    （review_pass verify=agent-visual，逐字段页/区域锚点+复核者留证+机械比对
    缺位如实记录）。barstub 为纯测试引擎（自制条带图解码），仅驱动管线测试，
    不作为真实原件识别路径。
"""

import csv
import io
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bpm.materials import register_derived, validate_reviewed_extraction
from bpm.plan import file_hash

ID_COLUMN_MARKERS = ("票号", "发票号", "账号", "运单号", "单号", "卡号", "工号", "订单号")
SUMMARY_MARKERS = ("合计", "小计", "汇总", "总计")
SEMANTIC_CATEGORIES = ("invoice", "summary_statement", "duplicate_copy", "explanation", "other_pending")
GAP_FIELDS = ("file", "locator", "region", "candidates", "reason", "affected_rows")


# ---------------------------------------------------------------- 缺口登记


def gap(file, locator, reason, *, region=None, candidates=None, affected_rows=None):
    """结构化缺口：文件/页或单元格定位/候选或原因/受影响行，字段封闭。"""
    return {"file": str(file), "locator": str(locator), "region": region,
            "candidates": list(candidates or []), "reason": str(reason),
            "affected_rows": list(affected_rows or [])}


class GapLog:
    """清晰件继续处理：缺口只登记，不中断整批。"""

    def __init__(self):
        self._items = []

    def add(self, *args, **kwargs):
        entry = gap(*args, **kwargs)
        self._items.append(entry)
        return entry

    def extend(self, entries):
        for entry in entries:
            if set(entry) != set(GAP_FIELDS):
                raise ValueError("gap entry must carry exactly " + ", ".join(GAP_FIELDS))
            self._items.append(entry)

    def to_list(self):
        return [dict(entry) for entry in self._items]


# ------------------------------------------------------- OCR 引擎封闭注册

_OCR_ENGINES = {}


def register_ocr_engine(name, engine):
    if not isinstance(name, str) or not name.strip() or not callable(engine):
        raise ValueError("ocr engine requires a name and a callable")
    _OCR_ENGINES[name] = engine


def available_ocr_engines():
    return sorted(_OCR_ENGINES)


def run_ocr(image_bytes, *, engine):
    """原始输出层：只做识别，绝不标注 reviewed。引擎只在本机运行。"""
    if engine not in _OCR_ENGINES:
        raise ValueError("unknown local ocr engine; registered: " + ", ".join(available_ocr_engines()))
    items = _OCR_ENGINES[engine](image_bytes)
    if not isinstance(items, list) or any(not isinstance(item, dict) or "text" not in item for item in items):
        raise ValueError("ocr engine must return text items")
    return {"schema_version": "1.0", "engine": engine, "generated_at": _now(),
            "items": [dict(item) for item in items]}


BAR_CELL = 10
BAR_HEIGHT = 16
BAR_GAP_CELLS = 2


def draw_bars(text, *, cell=BAR_CELL, height=BAR_HEIGHT):
    """确定性条码绘制：数字 d 画 d+1 个连续黑格，位间空 BAR_GAP_CELLS 格。

    与 ``barstub`` 解码器共用参数，用于测试与演示；不含任何业务数据。
    """
    from PIL import Image, ImageDraw
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("bar encoding supports digits only")
    widths = [int(d) + 1 for d in text]
    total_cells = sum(widths) + BAR_GAP_CELLS * (len(widths) - 1)
    image = Image.new("L", (total_cells * cell, height + 24), 255)
    draw = ImageDraw.Draw(image)
    cursor = 0
    for width in widths:
        draw.rectangle([cursor * cell, 12, (cursor + width) * cell - 1, 12 + height - 1], fill=0)
        cursor += width + BAR_GAP_CELLS
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _barstub_engine(image_bytes):
    """本机像素解码器（barstub）：读条带行黑格游程→数字，输出带 bbox 的文本项。

    这是确定性测试/演示引擎，证明「渲染→识别→两层落盘」管线真实可跑；
    它不访问网络，同一图像永远同一输出。
    """
    from PIL import Image
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    width, height = image.size
    pixels = image.load()
    dark_rows = [y for y in range(height) if any(pixels[x, y] < 128 for x in range(width))]
    if not dark_rows:
        return []
    top, bottom = min(dark_rows), max(dark_rows)
    ymid = (top + bottom) // 2
    runs, x = [], 0
    while x < width:
        if pixels[x, ymid] < 128:
            start = x
            while x < width and pixels[x, ymid] < 128:
                x += 1
            runs.append((start, x))
        else:
            x += 1
    digits = []
    if runs:
        first_x, last_x = runs[0][0], runs[-1][1]
        for start, end in runs:
            cells = round((end - start) / BAR_CELL)
            if not 1 <= cells <= 10:
                raise ValueError("bar run length does not decode to a digit")
            digits.append(str(cells - 1))
    else:
        first_x = last_x = 0
    return [{"text": "".join(digits), "page": 1, "bbox": [first_x, top, last_x, bottom + 1]}]


register_ocr_engine("barstub", _barstub_engine)


# ------------------------------------------------------------ PDF 文本链

INVOICE_FIELD_PATTERNS = (
    ("invoice_number", re.compile(r"发票号码[：:]\s*([0-9A-Za-z\-]{6,})")),
    ("invoice_code", re.compile(r"发票代码[：:]\s*([0-9]{8,})")),
    ("issue_date", re.compile(r"开票日期[：:]\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日|[0-9]{4}-[0-9]{1,2}-[0-9]{1,2})")),
    ("issuer_name", re.compile(r"(?:开票主体|销售方名称)[：:]\s*([^\s：][^：]*?)\s*$")),
    ("subtotal_amount", re.compile(r"合计（不含税）[^0-9]*([0-9]+(?:\.[0-9]{1,2})?)")),
    ("tax_amount", re.compile(r"税额[（(]?[^0-9]*?([0-9]+(?:\.[0-9]{1,2})?)")),
    ("total_amount", re.compile(r"价税合计[^0-9]*([0-9]+(?:\.[0-9]{1,2})?)")),
)
INVOICE_FIELD_PATTERN_BY_FIELD = dict(INVOICE_FIELD_PATTERNS)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _region_for(y0, y1, height):
    """版面区域锚点：页高 25%/75% 分 header/body/footer。"""
    middle = (y0 + y1) / 2 / height if height else 0
    if middle < 0.25:
        return "header"
    if middle > 0.75:
        return "footer"
    return "body"


def extract_pdf_text(path):
    """嵌入文本层：fitz 逐页取行级 bbox，输出带页码/区域/坐标的原始行。"""
    import fitz

    document = fitz.open(path)
    try:
        items = []
        for page_number, page in enumerate(document, start=1):
            height = page.rect.height
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"])
                    if not text.strip():
                        continue
                    x0, y0, x1, y1 = line["bbox"]
                    items.append({"text": text, "page": page_number,
                                  "bbox": [round(v, 1) for v in line["bbox"]],
                                  "region": _region_for(y0, y1, height)})
        return {"schema_version": "1.0", "source": "pdf-embedded-text", "pages": document.page_count,
                "items": items}
    finally:
        document.close()


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def extract_pdf_facts(path):
    """标签驱动的票据事实抽取：每值带页/区域/bbox 锚点，金额做 Decimal 闭合复核。

    Round-10（ctr-8cb7b247 §1）一票一件契约显式拒绝：同一文件检出 ≥2 个互异
    发票号码或发票代码即登记 GAP（不拆分、不并票——拆分策略未授权），该文件
    不得作为单票证据进入发票链；事实层维持首匹配（不虚构合并票）。
    """
    lines = extract_pdf_text(path)
    facts, log = {}, GapLog()
    for field, pattern in INVOICE_FIELD_PATTERNS:
        for item in lines["items"]:
            match = pattern.search(item["text"])
            if match:
                facts[field] = {"value": match.group(1),
                                "anchor": {"page": item["page"], "region": item["region"], "bbox": item["bbox"]}}
                break
    # 多票身份检测：全量匹配身份字段（不限首页/首个）
    identity_hits = {}
    for item in lines["items"]:
        for field in ("invoice_number", "invoice_code"):
            match = INVOICE_FIELD_PATTERN_BY_FIELD[field].search(item["text"])
            if match:
                identity_hits.setdefault(field, []).append((match.group(1), item))
    for field, observed in identity_hits.items():
        distinct = []
        for value, _ in observed:
            if value not in distinct:
                distinct.append(value)
        if len(distinct) > 1:
            first_item = observed[0][1]
            log.add(path, "page:{0}".format(first_item["page"]),
                    "同一文件检出多张发票身份（{0}：{1} 个互异值；一票一件契约，不拆分不并票，"
                    "拒绝作为单票证据，请人工拆分原件后分件提交）".format(field, len(distinct)),
                    region=first_item["region"], candidates=distinct,
                    affected_rows=["invoice-1"])
    closure = {"checked": False, "closed": None}
    if all(field in facts for field in ("subtotal_amount", "tax_amount", "total_amount")):
        closure["checked"] = True
        subtotal = _money(facts["subtotal_amount"]["value"])
        tax = _money(facts["tax_amount"]["value"])
        total = _money(facts["total_amount"]["value"])
        closure["closed"] = subtotal + tax == total
        closure["subtotal"], closure["tax"], closure["total"] = str(subtotal), str(tax), str(total)
        if not closure["closed"]:
            log.add(path, "page:{0}".format(facts["total_amount"]["anchor"]["page"]),
                    "价税合计与（不含税合计+税额）不闭合",
                    region=facts["total_amount"]["anchor"]["region"],
                    candidates=[facts["total_amount"]["value"]],
                    affected_rows=["invoice-1"])
    return {"facts": facts, "closure": closure, "gaps": log.to_list(), "lines": lines["items"]}


def _manifest_file(manifest, original_relpath):
    for item in manifest.get("files", []):
        if item.get("relative_path") == original_relpath:
            return item
    raise ValueError("original not in manifest: " + original_relpath)


def _resolve_original(manifest_path, item):
    """原件路径与 R2-P1 同口径：相对路径挂 manifest 所在目录，CWD 无关。"""
    original = Path(item["path"])
    return original if original.is_absolute() else Path(manifest_path).parent / original


def _load_manifest(manifest_path):
    manifest_path = Path(manifest_path)
    return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8"))


def run_pdf_extraction(manifest_path, original_relpath, *, reviewer="bpm-extraction.run_pdf_extraction"):
    """文本 PDF 端到端：嵌入文本层(ocr_result) + 逐字段锚点复核(reviewed_extraction)。

    复核过程=每个事实回锚到原始行（页/bbox 重合）+ 金额 Decimal 闭合，
    复核证据逐字段写入 review_evidence；OCR/嵌入文本裸输出永不标 reviewed。
    """
    manifest_path, manifest = _load_manifest(manifest_path)
    item = _manifest_file(manifest, original_relpath)
    original = _resolve_original(manifest_path, item)
    raw = extract_pdf_text(original)
    facts = extract_pdf_facts(original)
    ocr_id = register_derived(manifest_path, "ocr/{0}.json".format(item["sha256"][:16]), raw,
                              role="ocr_result", sources=[item["sha256"]], generated_by="bpm_extraction:pdf-embedded-text")
    evidence, record_fields = {}, {}
    for field, fact in facts["facts"].items():
        anchor = fact["anchor"]
        locator = "page:{0}/region:{1}/bbox:{2}".format(anchor["page"], anchor["region"], anchor["bbox"])
        record_fields[field] = {"value": fact["value"], "locator": locator}
        hit = next((index for index, line in enumerate(raw["items"])
                    if line["page"] == anchor["page"] and line["bbox"] == anchor["bbox"]), None)
        if hit is None:
            raise ValueError("fact anchor not present in raw layer: " + field)
        evidence[field] = {"verified_via": "raw-line-anchor-match", "raw_item_index": hit}
    evidence["decimal_closure"] = facts["closure"]
    payload = {"schema_version": "1.0", "reviewed": True, "reviewed_by": reviewer, "reviewed_at": _now(),
               "method": "embedded-text-line-anchors+decimal-closure", "original_path": str(original),
               "original_sha256": item["sha256"], "records": [{"record_id": "invoice-1", "fields": record_fields}],
               "review_evidence": evidence, "gaps": facts["gaps"]}
    errors = validate_reviewed_extraction(payload, base_dir=Path(item["path"]).parent)
    if errors:
        raise ValueError("reviewed payload invalid: " + errors[0]["message"])
    reviewed_id = register_derived(manifest_path, "reviewed/{0}.json".format(item["sha256"][:16]), payload,
                                   role="reviewed_extraction", sources=[item["sha256"]], generated_by=reviewer)
    return {"ocr_derived_id": ocr_id, "reviewed_derived_id": reviewed_id,
            "payload": payload, "closure": facts["closure"], "gaps": facts["gaps"]}


# ------------------------------------------------------------ 图片两层链

def render_pages(path, *, dpi=150):
    """本地渲染全页：PDF 每页→PNG（页级定位的页码来源）；图片原样（page=1）。不访问网络。"""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import fitz

        document = fitz.open(path)
        try:
            return [{"page": number, "png": document[number - 1].get_pixmap(dpi=dpi).tobytes("png")}
                    for number in range(1, document.page_count + 1)]
        finally:
            document.close()
    return [{"page": 1, "png": path.read_bytes()}]


def render_original(path, *, dpi=150):
    """兼容单图入口：仅返回首页 PNG 字节；全页路径（页级锚点/视觉复核）用 render_pages。"""
    return render_pages(path, dpi=dpi)[0]["png"]


def render_to_files(path, out_dir, *, dpi=150):
    """全页渲染落盘，供 agent 视觉复核逐页查看：返回 [{page, path, sha256}]。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    renders = []
    for page in render_pages(path, dpi=dpi):
        target = out_dir / "page-{0:03d}.png".format(page["page"])
        target.write_bytes(page["png"])
        renders.append({"page": page["page"], "path": str(target), "sha256": file_hash(target)})
    return renders


def ocr_pass(manifest_path, original_relpath, *, engine, relative_name=None):
    """全页渲染→本地引擎逐页→role=ocr_result；原始输出层，无 reviewed 语义。

    引擎输出的 page 一律盖上真实渲染页码（页级定位贯通：barstub 这类引擎
    自带 page:1 只对单页图片成立，多页 PDF 由渲染循环重写）。
    """
    manifest_path, manifest = _load_manifest(manifest_path)
    item = _manifest_file(manifest, original_relpath)
    pages = render_pages(_resolve_original(manifest_path, item))
    items = []
    for page in pages:
        for entry in run_ocr(page["png"], engine=engine)["items"]:
            entry["page"] = page["page"]
            items.append(entry)
    raw = {"schema_version": "1.0", "engine": engine, "pages": len(pages),
           "generated_at": _now(), "items": items}
    name = relative_name or "ocr/{0}.json".format(item["sha256"][:16])
    derived_id = register_derived(manifest_path, name, raw, role="ocr_result",
                                  sources=[item["sha256"]], generated_by="bpm_extraction:ocr:" + engine)
    return {"derived_id": derived_id, "relative_name": name, "raw": raw,
            "pages": len(pages), "original_sha256": item["sha256"]}


def review_pass(manifest_path, original_relpath, fields, *, reviewer, method,
                ocr_relative_name=None, verify="raw-cross-check"):
    """复核层：fields 每字段引用 raw item 或区域锚点，复核动作真实执行并留证。

    verify="raw-cross-check"：逐字段与 ocr_result 原始项文本比对（引擎输出层复核）；
    verify="agent-visual"：agent 已对照原页区域，锚点+执行者留证，机械比对缺位如实记录。
    """
    manifest_path, manifest = _load_manifest(manifest_path)
    item = _manifest_file(manifest, original_relpath)
    original = _resolve_original(manifest_path, item)
    raw_items, evidence = [], {}
    if verify == "raw-cross-check":
        if not ocr_relative_name:
            raise ValueError("raw-cross-check requires the ocr_result relative name")
        raw_entry = next(entry for entry in manifest["derived_files"] if entry["relative_path"] == ocr_relative_name)
        raw_payload = json.loads(Path(raw_entry["path"]).read_text(encoding="utf-8"))
        raw_items = raw_payload["items"]
    elif verify != "agent-visual":
        raise ValueError("unknown review verification mode: " + verify)
    record_fields = {}
    for field, spec in fields.items():
        value, page, region, bbox = spec["value"], spec.get("page", 1), spec.get("region"), spec.get("bbox")
        locator = "page:{0}/region:{1}/bbox:{2}".format(page, region, bbox)
        record_fields[field] = {"value": str(value), "locator": locator}
        if verify == "raw-cross-check":
            index = spec.get("raw_item")
            if index is None or not 0 <= index < len(raw_items):
                raise ValueError("field must reference a raw item: " + field)
            if str(value) != raw_items[index]["text"]:
                raise ValueError("reviewed value disagrees with raw ocr item: " + field)
            evidence[field] = {"verified_via": "raw-item-cross-check", "raw_item_index": index}
        else:
            evidence[field] = {"verified_via": "agent-visual-region-recheck",
                               "mechanical_crosscheck": "unavailable-no-engine-output"}
    record_id = next(iter(fields.values())).get("record_id", "visual-1")
    payload = {"schema_version": "1.0", "reviewed": True, "reviewed_by": reviewer, "reviewed_at": _now(),
               "method": method, "original_path": str(original), "original_sha256": item["sha256"],
               "records": [{"record_id": record_id, "fields": record_fields}],
               "review_evidence": evidence, "gaps": []}
    errors = validate_reviewed_extraction(payload, base_dir=original.parent)
    if errors:
        raise ValueError("reviewed payload invalid: " + errors[0]["message"])
    derived_id = register_derived(manifest_path, "reviewed/{0}.json".format(item["sha256"][:16]), payload,
                                  role="reviewed_extraction", sources=[item["sha256"]], generated_by=reviewer)
    return {"derived_id": derived_id, "payload": payload}


def run_image_extraction(manifest_path, original_relpath, *, engine, reviewer="bpm-extraction.run_image_extraction"):
    """图片端到端：渲染→ocr_result 层→逐字段 raw 交叉复核→reviewed_extraction 层。"""
    ocr = ocr_pass(manifest_path, original_relpath, engine=engine)
    items = ocr["raw"]["items"]
    fields = {}
    for index, item in enumerate(items):
        fields["code_{0}".format(index + 1)] = {"value": item["text"], "raw_item": index,
                                                "page": item.get("page", 1),
                                                "region": "body", "bbox": item.get("bbox"),
                                                "record_id": "visual-1"}
    review = review_pass(manifest_path, original_relpath, fields, reviewer=reviewer,
                         method="local-engine-raw-cross-check", ocr_relative_name=ocr["relative_name"],
                         verify="raw-cross-check")
    return {"ocr": ocr, "review": review}


# --------------------------------------------------------- Excel/CSV 语义链

_SCIENTIFIC = re.compile(r"^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$")
_TRAILING_ZERO = re.compile(r"^\d+\.\d*0$")


def _column_index(ref):
    letters = re.match(r"([A-Z]+)", ref).group(1)
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - 64)
    return index - 1


def _column_letters(index):
    letters = ""
    value = index + 1
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _split_ref(ref):
    match = re.fullmatch(r"(?:(.+)!)?\$?([A-Z]+)\$?(\d+)", ref or "")
    if not match:
        return None, None, None
    return match.group(1), match.group(2) + match.group(3), int(match.group(3))


def _recompute_simple_sum(formula, sheets, default_sheet):
    """本地重算仅限 ``=SUM([Sheet!]A1:A9)`` 形式且区间内全为字面数字；否则返回 None。"""
    match = re.fullmatch(r"=SUM\((?:(?:'([^']+)'|([\w一-鿿]+))!)?\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)\)",
                         (formula or "").replace(" ", ""))
    if not match:
        return None
    quoted, plain, col_a, row_a, col_b, row_b = match.groups()
    sheet_name = quoted or plain or default_sheet
    sheet = sheets.get(sheet_name)
    if sheet is None:
        return None
    total = Decimal(0)
    for row in range(int(row_a), int(row_b) + 1):
        for column in range(_column_index(col_a), _column_index(col_b) + 1):
            cell = sheet["cells"].get("{0}{1}".format(_column_letters(column), row))
            if cell is None or cell.get("kind") != "number":
                return None
            total += Decimal(str(cell["value"]))
    return total.quantize(Decimal("0.01"))


def extract_workbook(path):
    """xlsx 语义盘点：sheet 可见性/隐藏行/筛选/表头/合计行/公式缓存或重算/前导零/跨表提示。

    只产出结构与事实，不做任何「行→费用」转换；数量相同金额相同仅提示待对账。
    """
    from openpyxl import load_workbook

    log = GapLog()
    formulas_view = load_workbook(path, data_only=False)
    cached_view = load_workbook(path, data_only=True)
    sheets = {}
    for sheet in formulas_view.worksheets:
        cached_sheet = cached_view[sheet.title]
        cells = {}
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                entry = {"value": cell.value if not isinstance(cell.value, str) else cell.value,
                         "kind": {None: "empty", "s": "text", "n": "number", "f": "formula", "b": "bool"}.get(cell.data_type, "other"),
                         "number_format": cell.number_format}
                if cell.data_type == "f":
                    entry["formula"] = cell.value
                    entry["cached"] = cached_sheet.cell(cell.row, cell.column).value
                cells[cell.coordinate] = entry
        sheets[sheet.title] = {"state": sheet.sheet_state, "cells": cells,
                               "hidden_rows": sorted(row for row, dimension in sheet.row_dimensions.items()
                                                     if dimension.hidden),
                               "autofilter": {"ref": sheet.auto_filter.ref,
                                              "columns": len(sheet.auto_filter.filterColumn)} if sheet.auto_filter and sheet.auto_filter.ref else None}
    for name, sheet in sheets.items():
        headers = {}
        header_row = None
        for row in range(1, 40):
            values = [(ref, entry["value"]) for ref, entry in sheet["cells"].items()
                      if entry.get("kind") in ("text", "number") and _split_ref(ref)[2] == row]
            if len(values) >= 2:
                header_row = row
                for ref, value in sorted(values, key=lambda pair: _column_index(re.match(r"[A-Z]+", pair[0]).group(0))):
                    headers[str(value)] = _column_index(re.match(r"[A-Z]+", ref).group(0))
                break
        sheet["header_row"] = header_row
        sheet["headers"] = headers
        id_columns = {marker: index for marker, index in headers.items()
                      if any(key in str(marker) for key in ID_COLUMN_MARKERS)}
        for ref, entry in sheet["cells"].items():
            if id_columns and entry["kind"] == "number":
                column = _column_index(re.match(r"[A-Z]+", ref).group(0))
                if column in id_columns.values() and isinstance(entry["value"], (int, float)):
                    log.add(path, "{0}!{1}".format(name, ref),
                            "编号列为数值单元格：前导零/丢精度不可恢复，不补零修复",
                            candidates=[str(entry["value"])],
                            affected_rows=["{0}!{1}".format(name, _split_ref(ref)[1])])
        summary_rows = []
        for row in range(1, 200):
            row_cells = [(ref, entry) for ref, entry in sheet["cells"].items() if _split_ref(ref)[2] == row]
            if not row_cells:
                continue
            first = min(row_cells, key=lambda pair: _column_index(re.match(r"[A-Z]+", pair[0]).group(0)))
            if first[1]["kind"] == "text" and any(marker in str(first[1]["value"]) for marker in SUMMARY_MARKERS):
                amount = None
                for ref, entry in row_cells:
                    if entry["kind"] == "number":
                        amount = entry["value"]
                        break
                    if entry["kind"] == "formula":
                        cached = entry.get("cached")
                        if cached is not None:
                            amount = cached
                        else:
                            recomputed = _recompute_simple_sum(entry["formula"], sheets, name)
                            if recomputed is not None:
                                amount = str(recomputed)
                        break
                summary_rows.append({"row": row, "label": str(first[1]["value"]), "amount": amount})
        sheet["summary_rows"] = summary_rows
        formula_cells = []
        for ref, entry in sheet["cells"].items():
            if entry["kind"] != "formula":
                continue
            cached = entry.get("cached")
            resolution, resolved = ("cached", cached) if cached is not None else (None, None)
            if cached is None:
                recomputed = _recompute_simple_sum(entry["formula"], sheets, name)
                if recomputed is not None:
                    resolution, resolved = "recomputed", str(recomputed)
                else:
                    resolution = "gap"
                    log.add(path, "{0}!{1}".format(name, ref),
                            "公式无缓存值且非简单 SUM，本地不可重算；公式文本不当金额",
                            candidates=[str(entry["formula"])],
                            affected_rows=["{0}!{1}".format(name, _split_ref(ref)[1])])
            formula_cells.append({"ref": "{0}!{1}".format(name, ref), "formula": entry["formula"],
                                  "cached": cached, "resolution": resolution, "resolved": resolved})
        sheet["formula_cells"] = formula_cells
    summary_of = []
    for name, sheet in sheets.items():
        for summary in sheet["summary_rows"]:
            for other_name, other in sheets.items():
                if other_name == name:
                    continue
                detail_amounts = [entry["value"] for ref, entry in other["cells"].items()
                                  if entry["kind"] == "number" and _split_ref(ref)[2] not in
                                  {srow["row"] for srow in other["summary_rows"]}
                                  and (other["header_row"] is None or _split_ref(ref)[2] != other["header_row"])]
                if detail_amounts:
                    try:
                        detail_total = sum((_money(value) for value in detail_amounts), Decimal(0))
                        summary_total = _money(summary["amount"]) if summary["amount"] is not None else None
                        if summary_total is not None:
                            summary_of.append({"summary": "{0}!row{1}".format(name, summary["row"]),
                                               "candidate_detail_sheet": other_name,
                                               "amount_match": detail_total == summary_total,
                                               "note": "汇总=明细仅为候选关系，是否同一费用待对账"})
                    except (InvalidOperation, TypeError):
                        pass
    seen_tuples, hints = {}, []
    for name, sheet in sheets.items():
        for row in range(1, 200):
            row_cells = {entry["kind"]: (ref, entry) for ref, entry in sheet["cells"].items() if _split_ref(ref)[2] == row}
            if "number" not in row_cells:
                continue
            ref, entry = row_cells["number"]
            key = "{0}|{1}|{2}".format(row_cells.get("text", (None, {"value": ""}))[1]["value"],
                                       entry["value"], name)
            normalized = "{0}|{1}".format(row_cells.get("text", (None, {"value": ""}))[1]["value"], entry["value"])
            seen_tuples.setdefault(normalized, []).append("{0}!{1}".format(name, _split_ref(ref)[1]))
    for normalized, locations in seen_tuples.items():
        if len(locations) > 1:
            hints.append({"tuple": normalized, "locations": locations,
                          "note": "数量相同金额相同≠重复业务，仅提示待对账"})
    return {"schema_version": "1.0", "kind": "workbook", "sheets": sheets,
            "summary_candidates": summary_of, "reconciliation_hints": hints, "gaps": log.to_list()}


def extract_csv_table(path):
    """CSV 行列定位：全字符串原值（前导零天然保留）；科学计数/尾零丢精度只登记。"""
    log = GapLog()
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    headers = {str(value): index for index, value in enumerate(rows[0])} if rows else {}
    id_columns = {header for header in headers if any(key in header for key in ID_COLUMN_MARKERS)}
    table = []
    for row_number, row in enumerate(rows, start=1):
        cells = {}
        for column_number, value in enumerate(row):
            ref = "R{0}C{1}".format(row_number, column_number + 1)
            cells[ref] = {"value": value}
            if id_columns and column_number in {headers[header] for header in id_columns}:
                if _SCIENTIFIC.match(value) or _TRAILING_ZERO.match(value):
                    log.add(path, ref, "CSV 编号列出现科学计数法/尾零，已丢精度，不补零修复",
                            candidates=[value], affected_rows=[ref])
        table.append({"row": row_number, "cells": cells})
    return {"schema_version": "1.0", "kind": "csv", "header": rows[0] if rows else [],
            "rows": table, "gaps": log.to_list()}


# ----------------------------------------------------------- 语义类别盘点

INVOICE_REQUIRED_FACTS = ("invoice_number", "total_amount")


def classify_materials(manifest):
    """按内容哈希做语义分类；文件名（扩展名只路由解析器）绝不作类别证据。

    判别依据必须落在 basis 字段（版面特征/关键词/表结构/内容哈希）；
    不确定即 other_pending 并给 pending_reason，不硬猜。
    """
    by_hash = {}
    for item in manifest.get("files", []):
        entry = by_hash.setdefault(item["sha256"], {"relative_paths": [], "category": None,
                                                    "basis": None, "pending_reason": None})
        entry["relative_paths"].append(item["relative_path"])
        # inventory 把同内容件收进 duplicate_paths（内容哈希判等），一并计入路径集合
        entry["relative_paths"].extend(path for path in item.get("duplicate_paths", []) if isinstance(path, str))
    for digest, entry in by_hash.items():
        if len(entry["relative_paths"]) > 1:
            entry["category"] = "duplicate_copy"
            entry["basis"] = "identical content sha256 across paths"
    for item in manifest.get("files", []):
        entry = by_hash[item["sha256"]]
        if entry["category"] is not None:
            continue
        path = Path(item["path"])
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            facts = extract_pdf_facts(path)["facts"]
            if all(field in facts for field in INVOICE_REQUIRED_FACTS):
                entry["category"] = "invoice"
                entry["basis"] = "content keywords 发票号码+价税合计 with page/region anchors"
            else:
                entry["category"] = "other_pending"
                entry["basis"] = "embedded text lacks invoice keywords"
                entry["pending_reason"] = "PDF 缺发票关键要素，需人工/视觉复核后定类"
        elif suffix in (".xlsx", ".xls"):
            workbook = extract_workbook(path)
            if any(sheet["summary_rows"] or sheet["formula_cells"] for sheet in workbook["sheets"].values()):
                entry["category"] = "summary_statement"
                entry["basis"] = "table structure with 合计/小计/汇总 rows or formula totals"
            else:
                entry["category"] = "other_pending"
                entry["basis"] = "table without 合计/汇总 structure markers"
                entry["pending_reason"] = "无合计/汇总结构标记，明细或统计角色待对账判定"
        elif suffix in (".txt", ".md"):
            text = path.read_text(encoding="utf-8")
            invoice_like = any(pattern.search(text) for _, pattern in INVOICE_FIELD_PATTERNS)
            table_like = "\t" in text or text.count("|") >= 4
            if not invoice_like and not table_like and any(key in text for key in ("说明", "事由", "情况")):
                entry["category"] = "explanation"
                entry["basis"] = "prose text without invoice keywords or table structure"
            elif invoice_like:
                entry["category"] = "other_pending"
                entry["basis"] = "invoice keywords in plain text without layout anchors"
                entry["pending_reason"] = "文本含票据关键词但无版面锚点，需 PDF/图片原件定类"
            else:
                entry["category"] = "other_pending"
                entry["basis"] = "text lacks classification markers"
                entry["pending_reason"] = "文本内容不足以判定类别"
        elif suffix in (".png", ".jpg", ".jpeg"):
            entry["category"] = "other_pending"
            entry["basis"] = "raster image; local engine output pending"
            entry["pending_reason"] = "图片需本地视觉复核后定类；文件名不作证据"
        else:
            entry["category"] = "other_pending"
            entry["basis"] = "unmodeled content shape"
            entry["pending_reason"] = "未建模的内容形态，不硬猜"
    return {"by_hash": {digest: entry for digest, entry in by_hash.items()},
            "categories": sorted(entry["category"] for entry in by_hash.values())}
