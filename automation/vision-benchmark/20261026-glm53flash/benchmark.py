"""Isolated pixel-only GLM benchmark. No credentials are read or recorded here.

The existing Git Bash claude-glm function provides provider/auth in its subshell.
Each request is a fresh, nonpersistent CLI process with all tools disabled.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import time
from datetime import datetime, timezone
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import fitz

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INPUTS = HERE / "inputs"
RESULTS = HERE / "results"
FACTS = ROOT / "automation/runs/20261026-115500-v3r02-case01/case01-facts.json"
ORIGINALS = ROOT / "feature01-细化报销skill/12月公出-发票"
BASH = r"C:\Program Files\Git\bin\bash.exe"
FIELDS = ["document_type", "document_number", "issue_or_apply_date", "plate",
          "travel_date_from", "travel_date_to", "origin_station", "destination_station",
          "invoice_codes", "invoice_numbers", "trip_count", "invoice_count",
          "amount_ex_tax", "tax_amount", "total_amount", "total_amount_cn",
          "buyer_name", "quantity", "unit_price"]


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def event(**kw):
    with (HERE / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now(), **kw}, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(rel, target, dpi=200):
    src = ORIGINALS / rel
    with fitz.open(src) as doc:
        assert doc.page_count == 1
        page = doc[0]
        page.get_pixmap(dpi=dpi, alpha=False).save(target)
    return {"rel": rel, "sha256": sha(src), "page": 1, "dpi": dpi}


def normalize(key, value):
    if value is None:
        return None
    if isinstance(value, list):
        return sorted(str(x).strip() for x in value)
    if key.endswith("date") or key.startswith("travel_date"):
        return re.sub(r"\D", "", str(value))
    if key in ["total_amount", "amount_ex_tax", "tax_amount", "quantity", "unit_price"]:
        try:
            return str(Decimal(re.sub(r"[¥￥,\s]", "", str(value))).normalize())
        except Exception:
            return str(value)
    if key in ["trip_count", "invoice_count", "red_circle_count", "blue_square_count"]:
        return str(value)
    return re.sub(r"\s", "", str(value))


def expected_for(entry):
    facts = entry["facts"]
    vals = {k: v.get("value") for k, v in facts.items() if isinstance(v, dict)}
    out = {}
    if entry["class"] == "summary_by_trip":
        out.update(document_type="trip_summary", document_number=vals["summary_number"],
                   issue_or_apply_date=vals["apply_date"], plate=vals["plate"],
                   travel_date_from=vals["trip_dates_raw"][0], travel_date_to=vals["trip_dates_raw"][-1],
                   origin_station=vals["stations_raw"][0], destination_station=vals["stations_raw"][-1],
                   invoice_numbers=vals["referenced_invoices"],
                   invoice_codes=[x["invoice_code"] for x in facts["referenced_invoices"]["rows"]],
                   trip_count=vals["trip_count"], invoice_count=vals["invoice_count"],
                   total_amount=vals["total_amount"], total_amount_cn=vals["total_amount_cn"],
                   buyer_name=vals["buyer_name"])
    else:
        out.update(document_type=entry["class"], document_number=vals["invoice_number"],
                   issue_or_apply_date=vals["issue_date"], invoice_numbers=[vals["invoice_number"]])
        for k in ["plate", "travel_date_from", "travel_date_to", "amount_ex_tax", "tax_amount",
                  "total_amount", "total_amount_cn", "buyer_name", "quantity", "unit_price"]:
            if k in vals:
                out[k] = vals[k]
        if "invoice_code" in vals:
            out["invoice_codes"] = [vals["invoice_code"]]
    return out


def prepare():
    INPUTS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    if (HERE / "golden.json").exists():
        print("Already prepared; existing random challenge retained.")
        return
    image = Image.new("RGB", (1200, 740), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 36)
    nonce = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(9))
    invoice = "".join(secrets.choice("0123456789") for _ in range(20))
    amount = str(Decimal(secrets.randbelow(80000) + 10000) / Decimal(100))
    texts = ["视觉识别测试样张（合成资料）", f"验证码：{nonce}", f"票号：{invoice}",
             f"金额：{amount} 元", "起点：泉州东站", "终点：厦门北站", "请数出下方红色圆形和蓝色正方形"]
    for n, line in enumerate(texts):
        draw.text((40, 25 + n * 69), line, font=font, fill="black")
    for x in [70, 220]:
        draw.ellipse((x, 550, x + 90, 640), fill="red")
    for x in [480, 650, 820]:
        draw.rectangle((x, 550, x + 90, 640), fill="blue")
    image.save(INPUTS / "S01.png")
    cases = [{"id": "S01", "kind": "synthetic", "image": "S01.png", "expected": {
        "verification_code": nonce, "invoice_number": invoice, "total_amount": amount,
        "origin_station": "泉州东站", "destination_station": "厦门北站",
        "red_circle_count": 2, "blue_square_count": 3}}]
    entries = json.loads(FACTS.read_text(encoding="utf-8"))["files"]
    samples = [
        ("R01", "0825/0825通行费电子票据汇总单(行程).pdf"),
        ("R02", "0825/0825厦门到晋江发票.pdf"),
        ("R03", "油票/油票1.pdf"),
        ("R04", "0906/0905通行费电子票据汇总单(行程).pdf"),
        ("R05", "0917/0917通行费电子票据汇总单(行程).pdf"),
    ]
    for ident, rel in samples:
        entry = next(e for e in entries if e["rel"] == rel)
        source = render(rel, INPUTS / f"{ident}.png")
        assert source["sha256"] == entry["sha256"]
        cases.append({"id": ident, "kind": "document", "image": f"{ident}.png", "source": source,
                      "expected": expected_for(entry)})
    # A deterministic low-resolution, slightly rotated derivative. The original is untouched.
    im = Image.open(INPUTS / "R01.png").convert("RGB")
    im = im.resize((900, round(im.height * 900 / im.width)), Image.Resampling.LANCZOS)
    im = im.rotate(3, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
    im = im.filter(ImageFilter.GaussianBlur(0.35))
    im.save(INPUTS / "D01.jpg", quality=72)
    cases.append({"id": "D01", "kind": "document", "image": "D01.jpg", "derived_from": "R01",
                  "transform": "width=900; rotation=3deg; gaussian_blur=0.35; JPEG quality=72",
                  "expected": dict(cases[1]["expected"])})
    # A fresh synthetic missing-field image: abstention cannot depend on prior invoice knowledge.
    im = image.copy()
    ImageDraw.Draw(im).rectangle((0, 155, 1199, 222), fill="white")
    im.save(INPUTS / "N01.png")
    expected = dict(cases[0]["expected"])
    expected["invoice_number"] = None
    cases.append({"id": "N01", "kind": "synthetic", "image": "N01.png", "expected": expected,
                  "transform": "invoice number row fully removed"})
    for case in cases:
        p = INPUTS / case["image"]
        case["image_sha256"] = sha(p)
        with Image.open(p) as im:
            case["image_size"] = list(im.size)
    dump(HERE / "golden.json", {"created_at": now(), "cases": cases,
          "ground_truth": "synthetic generator and previously independently checked PDF text facts; never sent to model",
          "normalization": "dates ignore separators; money Decimal; lists sorted; whitespace ignored; Chinese characters otherwise exact"})
    event(action="prepared", cases=len(cases))
    print(json.dumps({"prepared": len(cases), "directory": str(HERE)}, ensure_ascii=False))


def prompt_for(case):
    if case["kind"] == "synthetic":
        keys = ["verification_code", "invoice_number", "total_amount", "origin_station",
                "destination_station", "red_circle_count", "blue_square_count"]
        return ("只依据这张图片识别可见文字并数图形，返回一个JSON对象，字段为" + ", ".join(keys)
                + "。号码和金额用字符串，数量用整数。不可见、被遮挡的字段必须为null，禁止推测补全。不要调用工具，不要输出解释。")
    return ("请只依据这张单页图片提取票据内容，返回一个JSON对象。字段为：" + ", ".join(FIELDS)
            + "。document_type只能为trip_summary/toll_invoice/fuel_invoice/unknown。"
            "document_number为本单据自己的汇总单号或发票号码；issue_or_apply_date为开票日期或开票申请日期。"
            "通行起止日期不可用开票申请日期替代。站名保持原文，换行要拼接，保留省份前缀；"
            "invoice_codes和invoice_numbers为图片中引用的全部票据代码/号码数组，逐票据行对应，重复代码保留，保留前导零；"
            "trip_count和invoice_count为整数；其他字段用字符串。金额、数量、单价按印刷原值抄录，不计算替代。"
            "不适用或看不清的字段用null，不猜测。禁止调用工具、读取PDF文字层、搜索资料或参考其他文件。只输出JSON。")


def parse_answer(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def run_one(case, model):
    target = RESULTS / f"{case['id']}-{model}.json"
    if target.exists():
        print(f"SKIP existing {target.name}", flush=True)
        return
    image_path = INPUTS / case["image"]
    media = "image/jpeg" if image_path.suffix == ".jpg" else "image/png"
    prompt = prompt_for(case)
    args = ["claude-glm", "--safe-mode", "--setting-sources", "", "--strict-mcp-config",
            "--mcp-config", '{"mcpServers":{}}', "--tools", "", "--disable-slash-commands",
            "--model", model, "--no-session-persistence", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose", "--max-budget-usd", "1",
            "--system-prompt", "You extract visible facts from attached images. No tools are available. Return only the requested JSON. Never invent missing text.",
            "-p"]
    command = "source ~/.bashrc; " + shlex.join(args)
    message = {"type": "user", "message": {"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": media,
         "data": base64.b64encode(image_path.read_bytes()).decode("ascii")}},
        {"type": "text", "text": prompt}]}}
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    started = time.monotonic()
    event(action="request_started", case=case["id"], model=model, image_sha256=case["image_sha256"])
    print(f"START {case['id']} {model}", flush=True)
    result = {"case_id": case["id"], "requested_model": model, "at": now(), "prompt": prompt,
              "image_sha256": case["image_sha256"], "route": "Git Bash existing claude-glm/Zhipu; Anthropic-compatible; base64 image content block",
              "isolation": "safe-mode; no settings sources; no MCP; no tools; no persistence; fresh CLI process"}
    try:
        proc = subprocess.run([BASH, "--noprofile", "--norc", "-c", command],
             input="1\n" + json.dumps(message, ensure_ascii=False) + "\n", capture_output=True,
             text=True, encoding="utf-8", errors="replace", env=env, cwd=INPUTS, timeout=180)
        records = []
        for line in proc.stdout.splitlines():
            try:
                record = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(record, dict) and record.get("type") in ["assistant", "result", "system"]:
                # Output contains no input echo, credential data, or image base64.
                records.append(record)
        result["exit_code"] = proc.returncode
        result["records"] = records
        result["stderr_tail"] = re.sub(r"(?i)(?:bearer\s+|(?:api[_-]?key|auth[_-]?token)[=: ]+)\S+", "[REDACTED]", proc.stderr[-1600:])
        texts = []
        models = []
        tools = []
        for rec in records:
            if rec.get("type") == "assistant":
                m = rec.get("message", {})
                if m.get("model"):
                    models.append(m["model"])
                for block in m.get("content", []):
                    if block.get("type") == "text":
                        texts.append(block["text"])
                    if block.get("type") == "tool_use":
                        tools.append(block.get("name"))
            if rec.get("type") == "result":
                result["cli_result"] = rec
        result["returned_models"] = sorted(set(models))
        result["tool_calls"] = tools
        text = result.get("cli_result", {}).get("result") or "\n".join(texts)
        result["answer_text"] = text
        try:
            answer = parse_answer(text)
            result["answer"] = answer
            checks = []
            for key, expected in case["expected"].items():
                actual = answer.get(key)
                checks.append({"field": key, "expected": expected, "actual": actual,
                  "pass": key in answer and normalize(key, expected) == normalize(key, actual)})
            result["checks"] = checks
            result["score"] = {"correct": sum(c["pass"] for c in checks), "total": len(checks)}
            result["all_pass"] = all(c["pass"] for c in checks)
        except Exception as exc:
            result["parse_error"] = type(exc).__name__
    except subprocess.TimeoutExpired:
        result["transport_error"] = "CLI exceeded 180 seconds; no result inferred"
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    dump(target, result)
    event(action="request_finished", case=case["id"], model=model, elapsed_seconds=result["elapsed_seconds"],
          returned_models=result.get("returned_models"), score=result.get("score"), all_pass=result.get("all_pass"),
          transport_error=result.get("transport_error"))
    print(json.dumps({k:result.get(k) for k in ["case_id", "requested_model", "returned_models", "score", "all_pass", "elapsed_seconds", "transport_error", "parse_error"]}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "run"])
    parser.add_argument("--cases", default="S01")
    parser.add_argument("--model", default="glm-5.3-flash")
    parser.add_argument("--allow-real-materials", action="store_true",
                        help="Only use after explicit user authorization for these real images and api.z.ai")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        cases = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))["cases"]
        wanted = args.cases.split(",")
        for case in cases:
            if case["id"] in wanted:
                if case["kind"] == "document" and not case.get("synthetic_only") and not args.allow_real_materials:
                    raise SystemExit("Real material requests require explicit user authorization; synthetic cases remain available.")
                run_one(case, args.model)


if __name__ == "__main__":
    main()
