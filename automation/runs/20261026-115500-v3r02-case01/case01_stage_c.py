# -*- coding: utf-8 -*-
"""V3-R02 CASE-01 阶段 C：大写↔小写内部一致性核验（只读，不改事实层）。

输入 case01-facts.json（阶段 B 产物）：
1. 中文大写金额 → Decimal（壹贰…拾佰仟万亿 + 圆/元角分整，支持零头/整/负零变体）；
2. 逐文件核对 total_amount_cn（大写）与 total_amount（小写）一致；
3. toll/fuel 票面内部闭合：amount_ex_tax + tax_amount == total_amount（字段齐时）；
4. 输出 case01-consistency.json，全部结论带 file/rel 定位，不通过项单独列出。
不预设业务范围裁定；仅票面内部一致性。
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

RUN = Path(__file__).resolve().parent
FACTS = RUN / "case01-facts.json"

CN_DIGITS = {"零": 0, "壹": 1, "贰": 2, "叁": 3, "肆": 4, "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9}
CN_UNITS = {"拾": 10, "佰": 100, "仟": 1000}
CN_SECTIONS = {"万": 10 ** 4, "亿": 10 ** 8}


def cn_amount_to_decimal(text: str) -> Decimal | None:
    """中文大写金额 → Decimal（精确到分）。解析失败返回 None，不猜测。"""
    s = re.sub(r"[（(]\s*小写\s*[)）].*$", "", text)
    s = re.sub(r"[（(]\s*大写\s*[)）]", "", s)
    s = s.replace("人民币", "").replace("圆", "元").strip()
    if not s or s in ("--", "—", "无", "零元整"):
        return Decimal("0") if s == "零元整" else None
    m = re.fullmatch(r"(?:[零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+元)?(零?[壹贰叁肆伍陆柒捌玖]?)角?(零?[壹贰叁肆伍陆柒捌玖]?)分?整?", s)
    frac_part = None
    if m and (m.group(1) or m.group(2) or "整" in s or "角" in s or "分" in s):
        jiao = CN_DIGITS.get(m.group(1).lstrip("零"), 0) if m.group(1) else 0
        fen = CN_DIGITS.get(m.group(2).lstrip("零"), 0) if m.group(2) else 0
        frac_part = Decimal(jiao) / 10 + Decimal(fen) / 100
    yuan_part = None
    ym = re.match(r"^([零壹贰叁肆伍陆柒捌玖拾佰仟万亿]+)元", s)
    if ym:
        yuan_part = _cn_int(ym.group(1))
        if yuan_part is None:
            return None
    if yuan_part is not None and frac_part is not None:
        return yuan_part + frac_part
    if yuan_part is not None:
        return yuan_part
    if frac_part is not None and re.search(r"[角分]", s):
        return frac_part
    return None


def _cn_int(s: str) -> Decimal | None:
    total, section, digit = Decimal(0), Decimal(0), 0
    for ch in s:
        if ch in CN_DIGITS:
            digit = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            section += Decimal(digit if digit else 1) * CN_UNITS[ch]
            digit = 0
        elif ch in CN_SECTIONS:
            section += Decimal(digit)
            total += section * CN_SECTIONS[ch]
            section, digit = Decimal(0), 0
        elif ch == "零":
            continue
        else:
            return None
    return total + section + digit


def dec(text) -> Decimal | None:
    if text is None:
        return None
    m = re.search(r"-?[0-9]+(?:\.[0-9]{1,2})?", str(text))
    return Decimal(m.group(0)) if m else None


def main() -> int:
    d = json.loads(FACTS.read_text(encoding="utf-8"))
    checks, mismatches = [], []
    for f in d["files"]:
        facts = f.get("facts") or {}
        small, big = facts.get("total_amount"), facts.get("total_amount_cn")
        if small and big:
            want = cn_amount_to_decimal(big["value"])
            got = dec(small["value"])
            ok = want is not None and got is not None and want == got
            checks.append({"rel": f["rel"], "class": f["class"], "small": small["value"],
                           "big": big["value"], "big_as_decimal": str(want), "match": bool(ok)})
            if not ok:
                mismatches.append(checks[-1])
        # toll/fuel 内部价税闭合（字段齐才算）
        if f["class"] in ("toll_invoice", "fuel_invoice"):
            ex, tax, tot = (dec((facts.get(k) or {}).get("value")) for k in
                            ("amount_ex_tax", "tax_amount", "total_amount"))
            if None not in (ex, tax, tot):
                ok = ex + tax == tot
                checks.append({"rel": f["rel"], "class": f["class"], "kind": "ex_tax_close",
                               "ex": str(ex), "tax": str(tax), "total": str(tot), "match": bool(ok)})
                if not ok:
                    mismatches.append(checks[-1])
    both = [c for c in checks if c.get("kind") != "ex_tax_close"]
    close = [c for c in checks if c.get("kind") == "ex_tax_close"]
    out = {
        "stage": "C 大写↔小写一致性核验（票面内部，不含范围裁定）",
        "cn_small_checks": len(both), "cn_small_matches": sum(1 for c in both if c["match"]),
        "ex_tax_close_checks": len(close), "ex_tax_close_matches": sum(1 for c in close if c["match"]),
        "mismatches": mismatches, "checks": checks,
    }
    (RUN / "case01-consistency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"大写↔小写: {out['cn_small_matches']}/{out['cn_small_checks']}; 价税闭合: "
          f"{out['ex_tax_close_matches']}/{out['ex_tax_close_checks']}; mismatches={len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
