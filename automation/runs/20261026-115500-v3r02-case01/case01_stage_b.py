# -*- coding: utf-8 -*-
"""V3-R02 CASE-01 阶段 B/C/D/E：票面事实层 + 去重索引 + 交叉核对 + 期间核定。

输入=阶段 A raw/*.json（73 件行级锚点，含 sha256）；xlsx（idx01）不走 PDF 分类，
由 openpyxl 只读读取参与期间核定。全部结论带锚点（page/bbox/来源 sha256）；
无匹配字段登记 GAP，不猜值；文件名仅作 rel 标识不作业务证据。
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "automation/runs/20261026-115500-v3r02-case01"
XLSX = ROOT / "feature01-细化报销skill/12月公出-发票/12月-自驾公出公里数统计表.xlsx"

DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日|(\d{4})-(\d{1,2})-(\d{1,2})")
MONEY_RE = re.compile(r"^[¥￥]?([0-9]+(?:\.[0-9]{1,2})?)$")


def anchor(item):
    return {"page": item["page"], "bbox": item["bbox"]}


def pick(items, pred):
    return [it for it in items if pred(it)]


def nearest_right(items, label, max_dy=6.0, min_dx=5.0):
    """label 行右侧近邻值行（同 y 带、x 更大、取 dx 最小者）。"""
    best = None
    for it in items:
        if it is label:
            continue
        if abs(it["bbox"][1] - label["bbox"][1]) <= max_dy and it["bbox"][0] > label["bbox"][0] + min_dx:
            if best is None or it["bbox"][0] < best["bbox"][0]:
                best = it
    return best


def column_row_values(items, header_labels, value_pred, y_lo=2.0, y_hi=22.0, max_dx=70.0):
    """表头标签行下方近行的值按 x 最近标签归列（列表头→值映射）。"""
    out = {}
    for label_text, label_items in header_labels.items():
        for label in label_items:
            cands = [it for it in items
                     if value_pred(it) and label["bbox"][1] < it["bbox"][1] <= label["bbox"][1] + y_hi
                     and abs(it["bbox"][0] - label["bbox"][0]) <= max_dx]
            if cands:
                cands.sort(key=lambda it: (abs(it["bbox"][0] - label["bbox"][0]), it["bbox"][1]))
                out.setdefault(label_text, []).append(cands[0])
    return out


def find_lines(items, text, exact=False):
    if exact:
        return [it for it in items if it["text"].strip() == text]
    return [it for it in items if text in it["text"]]


def classify(rec):
    text_all = "\n".join(it["text"] for it in rec["items"])
    if "收费公路通行费电子票据汇总单" in text_all:
        return "summary_by_invoice" if "按票据索引" in text_all else "summary_by_trip"
    if "成品油" in text_all and "电子发票" in text_all:
        return "fuel_invoice"
    if "增值税电子普通发票" in text_all and "通行费" in text_all:
        return "toll_invoice"
    return "unclassified"


def parse_toll_invoice(rec):
    items, gaps, facts = rec["items"], [], {}
    # 表头键值（标签 x≈432 值 x≈474，y 近邻）
    for label_text, field in (("发票代码:", "invoice_code"), ("发票号码:", "invoice_number"),
                              ("开票日期:", "issue_date"), ("校验码:", "check_code")):
        labels = find_lines(items, label_text, exact=True)
        if not labels:
            gaps.append(f"toll:{field}:label_absent")
            continue
        value = nearest_right(items, labels[0])
        if value is None:
            gaps.append(f"toll:{field}:value_absent")
        else:
            facts[field] = {"value": value["text"].strip(), "anchor": anchor(value)}
    # 明细行（列表头→值）
    header_labels = {}
    for label_text in ("项目名称", "车牌号", "类型", "通行日期起", "通行日期止", "金　额", "税率", "税　额"):
        hits = find_lines(items, label_text, exact=True)
        if hits:
            header_labels[label_text] = hits
    row_map = column_row_values(
        items, header_labels,
        lambda it: bool(re.fullmatch(r"\S+", it["text"].strip())) and not it["text"].strip().endswith((":", "：")),
    )
    field_map = {"项目名称": "item_name", "车牌号": "plate", "类型": "vehicle_type",
                 "通行日期起": "travel_date_from", "通行日期止": "travel_date_to",
                 "金　额": "amount_ex_tax", "税率": "tax_rate", "税　额": "tax_amount"}
    for label_text, field in field_map.items():
        if label_text in row_map and row_map[label_text]:
            value = row_map[label_text][0]
            facts[field] = {"value": value["text"].strip(), "anchor": anchor(value)}
        else:
            gaps.append(f"toll:{field}:cell_absent")
    # 价税合计
    small = find_lines(items, "（小写）", exact=True)
    if small:
        value = nearest_right(items, small[0])
        if value and MONEY_RE.match(value["text"].strip()):
            facts["total_amount"] = {"value": MONEY_RE.match(value["text"].strip()).group(1), "anchor": anchor(value)}
        else:
            gaps.append("toll:total_amount:absent")
    else:
        gaps.append("toll:total_amount:label_absent")
    big = find_lines(items, "价税合计（大写）", exact=True)
    if big:
        value = nearest_right(items, big[0], max_dy=4.0)
        if value:
            facts["total_amount_cn"] = {"value": value["text"].strip(), "anchor": anchor(value)}
    return facts, gaps


def parse_fuel_invoice(rec):
    items, gaps, facts = rec["items"], [], {}
    for pattern, field in ((r"发票号码[：:]\s*([0-9]{8,})", "invoice_number"),
                           (r"开票日期[：:]\s*([0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日)", "issue_date")):
        hit = None
        for it in items:
            m = re.search(pattern, it["text"])
            if m:
                hit = (m.group(1), it)
                break
        if hit:
            facts[field] = {"value": hit[0], "anchor": anchor(hit[1])}
        else:
            gaps.append(f"fuel:{field}:absent")
    names = find_lines(items, "名称：")
    if len(names) >= 2:
        facts["buyer_name"] = {"value": names[0]["text"].split("名称：", 1)[1].strip(), "anchor": anchor(names[0])}
        facts["seller_name"] = {"value": names[1]["text"].split("名称：", 1)[1].strip(), "anchor": anchor(names[1])}
    else:
        gaps.append("fuel:buyer_or_seller_absent")
    small = [it for it in items if "（小写）" in it["text"] and "¥" in it["text"]]
    if small:
        m = re.search(r"（小写）[¥￥]([0-9]+(?:\.[0-9]{1,2})?)", small[0]["text"])
        if m:
            facts["total_amount"] = {"value": m.group(1), "anchor": anchor(small[0])}
    else:
        gaps.append("fuel:total_amount:absent")
    # 大写与（小写）同行（如"肆佰肆拾肆圆壹角伍分"），过滤水印字符取含中文大写数字的最近右侧
    big = find_lines(items, "价税合计（大写）", exact=True)
    if big:
        cn_chars = "壹贰叁肆伍陆柒捌玖拾佰仟万亿零圆元角分整"
        cands = [it for it in items if any(c in it["text"] for c in cn_chars)
                 and abs(it["bbox"][1] - big[0]["bbox"][1]) <= 6
                 and it["bbox"][0] > big[0]["bbox"][0]]
        cands.sort(key=lambda it: it["bbox"][0])
        if cands:
            facts["total_amount_cn"] = {"value": cands[0]["text"].strip(), "anchor": anchor(cands[0])}
        else:
            gaps.append("fuel:total_amount_cn:absent")
    header_labels = {}
    for label_text in ("数  量", "单  价", "金  额", "税率/征收率", "税  额 "):
        hits = find_lines(items, label_text.strip(), exact=False)
        if hits:
            header_labels[label_text.strip()] = hits
    row_map = column_row_values(
        items, header_labels,
        lambda it: bool(MONEY_RE.match(it["text"].strip()) or re.fullmatch(r"\d+(\.\d+)?%?", it["text"].strip())))
    for label_text, field in (("数  量", "quantity"), ("单  价", "unit_price"), ("金  额", "amount_ex_tax"),
                              ("税率/征收率", "tax_rate"), ("税  额", "tax_amount")):
        key = label_text.strip()
        if key in row_map and row_map[key]:
            value = row_map[key][0]
            facts[field] = {"value": value["text"].strip(), "anchor": anchor(value)}
        else:
            gaps.append(f"fuel:{field}:cell_absent")
    product = [it for it in items if it["text"].startswith("*")]
    if product:
        facts["product_name"] = {"value": product[0]["text"].strip(), "anchor": anchor(product[0])}
    return facts, gaps


def parse_summary(rec):
    items, gaps, facts = rec["items"], [], {}
    joined = "\n".join(it["text"] for it in rec["items"])
    for pattern, field in ((r"汇总单号[:：]\s*(\S+)", "summary_number"),
                           (r"开票申请日期[:：]\s*(\S+)", "apply_date")):
        m = re.search(pattern, joined)
        if m:
            line = find_lines(items, m.group(1))[0]
            facts[field] = {"value": m.group(1), "anchor": anchor(line)}
        else:
            gaps.append(f"summary:{field}:absent")
    # 同 y 键值对
    for label_text, field in (("车牌号码", "plate"), ("交易金额", "declared_total"),
                              ("购买方名称", "buyer_name"), ("行程数量", "trip_count"),
                              ("票据数量", "invoice_count"), ("纳税人识别号", "buyer_tax_id")):
        labels = find_lines(items, label_text, exact=True)
        if not labels:
            gaps.append(f"summary:{field}:label_absent")
            continue
        value = nearest_right(items, labels[0], max_dy=3.0)
        if value is None:
            gaps.append(f"summary:{field}:value_absent")
        else:
            facts[field] = {"value": value["text"].strip(), "anchor": anchor(value)}
    # 票据行（布局配对判别：8 位数字行与 12 位票据代码同 y±1.5 配对才是票号——
    # 票号可 20 开头，不能用 20\d{6} 排除日期；未配对的 8 位行=通行日期候选）
    codes = [it for it in items if re.fullmatch(r"\d{12}", it["text"].strip())]
    all8 = [it for it in items if re.fullmatch(r"\d{8}", it["text"].strip())]
    rows, paired = [], set()
    for num in all8:
        code = min((c for c in codes if abs(c["bbox"][1] - num["bbox"][1]) <= 1.5),
                   key=lambda c: abs(c["bbox"][0] - num["bbox"][0]), default=None)
        if code is None:
            continue
        paired.add(id(num))
        band = [it["text"].strip().lstrip("¥￥") for it in items
                if re.fullmatch(r"[¥￥]?[0-9]+(?:\.[0-9]{1,2})?", it["text"].strip())
                and abs(it["bbox"][1] - num["bbox"][1]) <= 2.5]
        rows.append({"invoice_code": code["text"].strip(),
                     "invoice_number": num["text"].strip(), "anchor": anchor(num),
                     "row_amounts": band, "y": num["bbox"][1]})
    rows.sort(key=lambda r: r["y"])
    facts["referenced_invoices"] = {"value": [r["invoice_number"] for r in rows],
                                    "anchor": "per-row anchors in summary_rows", "rows": rows}
    # 行程日期对（通行日期起止列：未与代码配对的 8 位行）
    dates = [it for it in all8 if id(it) not in paired]
    facts["trip_dates_raw"] = {"value": [it["text"].strip() for it in dates],
                               "anchors": [anchor(it) for it in dates]}
    # 出入口站（闽·…站/至；站名可任意分行续接（如"闽·福建石狮"+"北石湖站"），按 y 邻近拼接）
    stations = [it for it in items if it["text"].strip().startswith("闽·")]
    stations.sort(key=lambda it: it["bbox"][1])
    joined_stations = []
    for st in stations:
        name = st["text"].strip()
        conts = sorted(
            (it for it in items
             if not it["text"].strip().startswith("闽·")
             and it["text"].strip() not in ("至",)
             and not re.fullmatch(r"[¥￥0-9.,%\s]+", it["text"])
             and 0 < it["bbox"][1] - st["bbox"][1] <= 13
             and abs(it["bbox"][0] - st["bbox"][0]) < 40),
            key=lambda it: it["bbox"][1])
        if conts:
            name += "".join(it["text"].strip() for it in conts)
        joined_stations.append({"name": name, "anchor": anchor(st)})
    facts["stations_raw"] = {"value": [s["name"] for s in joined_stations],
                             "anchors": [s["anchor"] for s in joined_stations]}
    if len(joined_stations) >= 2:
        zhi = [it for it in items if it["text"].strip() == "至"]
        facts["station_pair"] = {
            "value": f"{joined_stations[0]['name']} 至 {joined_stations[-1]['name']}",
            "anchor": [joined_stations[0]["anchor"], joined_stations[-1]["anchor"]],
            "via_zhi_y": zhi[0]["bbox"][1] if zhi else None}
    # 价税合计（大写/小写）：汇总单（小写）的值在标签正下方（同列 y+~9），不在右侧
    small = [it for it in items if "（小写）" in it["text"]]
    if small:
        cand = sorted((it for it in items if "¥" in it["text"]
                       and 2 <= it["bbox"][1] - small[0]["bbox"][1] <= 16
                       and abs(it["bbox"][0] - small[0]["bbox"][0]) < 12),
                      key=lambda it: it["bbox"][1])
        if not cand:
            right = nearest_right(items, small[0], max_dy=12.0)
            cand = [right] if right and "¥" in right["text"] else []
        if cand:
            m = re.search(r"[¥￥]([0-9]+(?:\.[0-9]{1,2})?)", cand[0]["text"])
            if m:
                facts["total_amount"] = {"value": m.group(1), "anchor": anchor(cand[0])}
    big = find_lines(items, "价税合计（大写）", exact=True)
    if big:
        # 同行右侧最近且含中文大写数字的行（水印字符如 'U' 常夹在中间，须过滤）
        cn_chars = "壹贰叁肆伍陆柒捌玖拾佰仟万亿零元角分整"
        cands = [it for it in items if any(c in it["text"] for c in cn_chars)
                 and abs(it["bbox"][1] - big[0]["bbox"][1]) <= 6
                 and it["bbox"][0] > big[0]["bbox"][0]]
        cands.sort(key=lambda it: it["bbox"][0])
        if cands:
            facts["total_amount_cn"] = {"value": cands[0]["text"].strip(), "anchor": anchor(cands[0])}
    return facts, gaps


def read_excel_rows():
    """数据实际占 B..J（openpyxl 逐 A 起返回，index0=A 恒 None）：
    B序号 C时间(Excel serial 或日期) D出发地 E目的地 F公里数 G补贴金额 H过路费 I合计 J备注。
    round-1 报告的"A–I"字母系探针 used_range($B$1) off-by-one，以本读数为准。"""
    from datetime import date, timedelta
    from openpyxl import load_workbook
    wb = load_workbook(str(XLSX), read_only=True, data_only=True)
    ws = wb["汇总"]
    rows = []
    for row in ws.iter_rows(min_row=4, max_row=24, values_only=True):
        if row is None:
            continue
        vals = (list(row) + [None] * 11)[:11]
        seq, when, src, dst, km, subsidy, toll, total, note = vals[1:10]
        if isinstance(when, (int, float)) and 40000 < when < 60000:
            when = (date(1899, 12, 30) + timedelta(days=int(when))).isoformat()
        elif when is not None:
            when = str(when)
        rows.append({"seq": seq, "date": when, "from": src, "to": dst,
                     "km": km, "subsidy": subsidy, "toll_filled": toll,
                     "total": total, "note": note})
    wb.close()
    return rows


def main() -> int:
    stage_a = json.loads((RUN / "stage_a_index.json").read_text(encoding="utf-8"))
    facts_files = []
    for meta in stage_a["files"]:
        rec = json.loads(next(RUN.glob(f"raw/{meta['idx']:02d}_*.json")).read_text(encoding="utf-8"))
        cls = classify(rec)
        entry = {"idx": rec["idx"], "rel": rec["rel"], "sha256": rec["sha256"], "class": cls}
        if cls == "toll_invoice":
            entry["facts"], entry["gaps"] = parse_toll_invoice(rec)
        elif cls == "fuel_invoice":
            entry["facts"], entry["gaps"] = parse_fuel_invoice(rec)
        elif cls in ("summary_by_invoice", "summary_by_trip"):
            entry["facts"], entry["gaps"] = parse_summary(rec)
        elif cls == "unclassified" and rec["rel"].endswith(".xlsx"):
            entry["facts"], entry["gaps"] = {}, ["workbook:not_pdf_pipeline"]
        else:
            entry["facts"], entry["gaps"] = {}, ["unclassified"]
        facts_files.append(entry)

    # 代收通行费票面无 金额/税率/税额 列值（版式事实，非提取失败）：定性重标
    for e in facts_files:
        item_name = e["facts"].get("item_name", {}).get("value", "") if isinstance(e.get("facts"), dict) else ""
        if "代收" in item_name:
            e["gaps"] = [g.replace(":cell_absent", ":not_on_face_daishou") for g in e["gaps"]]

    # ---- 去重索引：唯一票据身份 ↔ 文件
    identities = {}
    for e in facts_files:
        if e["class"] == "toll_invoice":
            code = e["facts"].get("invoice_code", {}).get("value")
            num = e["facts"].get("invoice_number", {}).get("value")
            if code and num:
                key = f"toll:{code}-{num}"
            else:
                key = f"toll:incomplete:{e['rel']}"
        elif e["class"] == "fuel_invoice":
            num = e["facts"].get("invoice_number", {}).get("value")
            key = f"fuel:{num}" if num else f"fuel:incomplete:{e['rel']}"
        elif e["class"] in ("summary_by_invoice", "summary_by_trip"):
            sn = e["facts"].get("summary_number", {}).get("value")
            key = f"summary:{sn}" if sn else f"summary:incomplete:{e['rel']}"
        else:
            continue
        e["identity"] = key
        identities.setdefault(key, {"identity": key, "class": e["class"], "files": []})
        identities[key]["files"].append({"idx": e["idx"], "rel": e["rel"], "sha256": e["sha256"]})

    # ---- 交叉核对：汇总单 vs 独立发票文件（行金额带 vs 独立票价税合计）
    invoice_by_identity = {k: v for k, v in identities.items() if k.startswith(("toll:", "fuel:"))}
    invoice_total_by_number = {}
    for e in facts_files:
        if e["class"] == "toll_invoice":
            num = e["facts"].get("invoice_number", {}).get("value")
            total = e["facts"].get("total_amount", {}).get("value")
            if num and total:
                invoice_total_by_number[num] = total
    summary_entries = [e for e in facts_files if e["class"].startswith("summary")]
    toll_entries = [e for e in facts_files if e["class"] == "toll_invoice"]
    crosschecks = []
    for s in summary_entries:
        rows = s["facts"].get("referenced_invoices", {}).get("rows", [])
        referenced = []
        for r in rows:
            match_key = f"toll:{r['invoice_code']}-{r['invoice_number']}"
            standalone = invoice_by_identity.get(match_key)
            standalone_total = invoice_total_by_number.get(r["invoice_number"])
            referenced.append({
                "invoice_code": r["invoice_code"], "invoice_number": r["invoice_number"],
                "row_amounts": r.get("row_amounts"),
                "standalone_file": standalone["files"][0]["rel"] if standalone else None,
                "standalone_found": bool(standalone),
                "standalone_total": standalone_total,
                "amount_match": (standalone_total in r.get("row_amounts", [])) if standalone_total else None,
            })
        declared = s["facts"].get("declared_total", {}).get("value")
        declared_n = None
        if declared and "¥" in declared:
            m = re.search(r"[¥￥]([0-9]+(?:\.[0-9]{1,2})?)", declared)
            declared_n = m.group(1) if m else None
        elif declared:
            declared_n = declared
        declared_count = s["facts"].get("invoice_count", {}).get("value")
        total_amt = s["facts"].get("total_amount", {}).get("value")
        crosschecks.append({
            "rel": s["rel"], "summary_number": s["facts"].get("summary_number", {}).get("value"),
            "declared_total": declared_n, "footer_total_amount": total_amt,
            "declared_invoice_count": declared_count,
            "referenced": referenced,
            "referenced_count": len(referenced),
            "count_consistent": (declared_count == str(len(referenced))) if declared_count else None,
        })

    # ---- 期间核定：通行日期（票面）+ 开票日期 + 目录名差异
    periods = []
    for e in toll_entries + summary_entries:
        f = e["facts"]
        periods.append({
            "rel": e["rel"], "class": e["class"],
            "travel_date_from": f.get("travel_date_from", {}).get("value") if e["class"] == "toll_invoice" else None,
            "travel_date_to": f.get("travel_date_to", {}).get("value") if e["class"] == "toll_invoice" else None,
            "trip_dates_raw": f.get("trip_dates_raw", {}).get("value") if e["class"].startswith("summary") else None,
            "issue_date": f.get("issue_date", {}).get("value"),
        })

    excel_rows = read_excel_rows()

    # ---- 观测值汇总（零预设：仅按票面/单元格直接推导）
    def dec(v):
        try:
            return Decimal(str(v))
        except Exception:
            return None
    toll_unique = [k for k, v in identities.items() if k.startswith("toll:") and not k.startswith("toll:incomplete")]
    fuel_unique = [k for k, v in identities.items() if k.startswith("fuel:") and not k.startswith("fuel:incomplete")]
    identity_total = {}
    for e in toll_entries:
        t = e["facts"].get("total_amount", {}).get("value")
        if e.get("identity") and t:
            identity_total.setdefault(e["identity"], []).append(t)
    T = sum((dec(v[0]) for v in identity_total.values() if v), Decimal("0"))
    fuel_totals = {}
    for e in facts_files:
        if e["class"] == "fuel_invoice":
            t = e["facts"].get("total_amount", {}).get("value")
            if e.get("identity") and t:
                fuel_totals.setdefault(e["identity"], []).append(t)
    O = sum((dec(v[0]) for v in fuel_totals.values() if v), Decimal("0"))
    km_sum = sum((d for d in (dec(r["km"]) for r in excel_rows) if d is not None), Decimal("0"))
    subsidy_sum = sum((d for d in (dec(r["subsidy"]) for r in excel_rows) if d is not None), Decimal("0"))
    observed = {
        "note": "观测值汇总：仅从票面/单元格直接推导，范围裁定（哪些行/票纳入 R=M+T 口径）留 CASE-02/03/04，不作业务结论。",
        "unique_toll_invoices": len(toll_unique), "unique_fuel_invoices": len(fuel_unique),
        "T_toll_total": str(T), "O_fuel_total": str(O),
        "excel_km_sum_all_rows": str(km_sum), "excel_subsidy_sum_all_rows": str(subsidy_sum),
    }

    out = {
        "stage": "B/C/D/E", "run": "20261026-115500-v3r02-case01",
        "files": facts_files,
        "identities": sorted(identities.values(), key=lambda v: v["identity"]),
        "crosschecks": crosschecks,
        "periods": periods,
        "excel_rows": excel_rows,
        "observed_totals": observed,
    }
    # 摘要
    print("classes:", {c: sum(1 for e in facts_files if e['class'] == c) for c in sorted({e['class'] for e in facts_files})})
    print("identities:", len(identities), "| multi-file identities:", {k: len(v['files']) for k, v in identities.items() if len(v['files']) > 1})
    print("crosscheck count_consistent:", sum(1 for c in crosschecks if c['count_consistent']), "/", len(crosschecks))
    print("crosscheck amount_match:", sum(1 for c in crosschecks for r in c['referenced'] if r['amount_match']),
          "/", sum(1 for c in crosschecks for r in c['referenced']))
    print("crosscheck referenced standalone missing:", [(c['rel'], [r['invoice_number'] for r in c['referenced'] if not r['standalone_found']]) for c in crosschecks if not all(r['standalone_found'] for r in c['referenced'])])
    # 同尺寸簇核身（round-1 manifest bytes + 本轮身份）
    manifest = json.loads((ROOT / "automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json").read_text(encoding="utf-8"))
    by_rel = {f["rel"]: f for g in manifest["groups"].values() for f in g["files"]}
    ident_by_rel = {e["rel"]: e.get("identity") for e in facts_files}
    size_clusters = {}
    for rel, f in by_rel.items():
        size_clusters.setdefault(f["bytes"], []).append(rel)
    clusters = [{"bytes": b, "rels": rels,
                 "identities": sorted({ident_by_rel.get(r) for r in rels}),
                 "conclusion": "same_identity_pair_renderings" if len({ident_by_rel.get(r) for r in rels}) == 1
                 else "different_identities_not_duplicates"}
                for b, rels in sorted(size_clusters.items()) if len(rels) > 1]
    out["same_size_clusters"] = clusters
    print("same-size clusters:", len(clusters))
    for c in clusters:
        print("  cluster", c["bytes"], c["conclusion"], c["identities"])
    gaps_all = [(e["rel"], g) for e in facts_files for g in e["gaps"] if ":not_on_face_daishou" not in g]
    print("gaps (excl. daishou layout facts):", len(gaps_all))
    for rel, g in gaps_all[:40]:
        print("  GAP", rel, g)
    print("observed:", observed)
    (RUN / "case01-facts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
