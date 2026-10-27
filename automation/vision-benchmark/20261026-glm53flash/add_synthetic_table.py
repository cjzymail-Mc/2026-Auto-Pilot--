"""Generate fictional table challenges from scratch; no original PDF is used."""
import json
import secrets
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent
path = HERE / "golden.json"
data = json.loads(path.read_text(encoding="utf-8"))
if any(c["id"] == "T01" for c in data["cases"]):
    raise SystemExit("Synthetic tables already exist")

font_path = r"C:\Windows\Fonts\msyh.ttc"
font = ImageFont.truetype(font_path, 28)
small = ImageFont.truetype(font_path, 24)
title = ImageFont.truetype(font_path, 42)
image = Image.new("RGB", (1800, 1000), "white")
d = ImageDraw.Draw(image)

def text(x, y, value, f=font):
    d.text((x, y), str(value), font=f, fill="black")

digits = lambda n: "".join(secrets.choice("0123456789") for _ in range(n))
summary = "9900" + digits(12)
code = "0" + digits(11)
numbers = ["0" + digits(7), "2" + digits(7)]
text(380, 25, "收费公路通行费电子票据汇总单", title)
text(700, 85, "（按行程索引）")
text(40, 140, "合成测试样张：以下单位、号码、行程均为虚构", small)
text(40, 190, f"汇总单号: {summary}")
text(1130, 190, "开票申请日期: 2026-09-06")
text(40, 245, "车牌号码: 测试A12345")
text(620, 245, "交易金额: ¥21.37")
text(1110, 245, "购买方名称: 合成测试有限公司")
text(40, 300, "行程数量: 1")
text(620, 300, "票据数量: 2")

xs = [40, 110, 330, 640, 800, 1090, 1310, 1540, 1750]
for x in xs:
    d.line((x, 365, x, 660), fill="black", width=2)
for y in [365, 445, 660]:
    d.line((40, y, 1750, y), fill="black", width=2)
d.line((800, 550, 1750, 550), fill="black", width=2)
headers = ["序号", "通行日期\n起止", "出入口信息", "交易金额", "票据代码", "票据号码", "金额(含税)", "税额"]
for x, h in zip(xs[:-1], headers):
    text(x + 10, 380, h, small)
text(60, 525, "1")
text(125, 480, "20260905")
text(125, 585, "20260905")
text(365, 450, "浙·杭州南")
text(425, 488, "站")
text(425, 528, "至")
text(365, 568, "浙·宁波东")
text(425, 605, "站")
text(665, 525, "21.37")
for y, num, amount, tax in [(485, numbers[0], "10.21", "0.30"), (590, numbers[1], "11.16", "0.33")]:
    text(815, y, code)
    text(1110, y, num)
    text(1340, y, amount)
    text(1570, y, tax)
text(40, 705, "共1段行程    共2张票据    交易金额 ¥21.37")
text(40, 775, "价税合计（大写）: 贰拾壹元叁角柒分")
text(1100, 775, "（小写）: ¥21.37")
text(40, 870, "仅用于视觉识别测试，不可作为真实业务凭据。", small)

expected = {"document_type": "trip_summary", "document_number": summary,
            "issue_or_apply_date": "2026-09-06", "plate": "测试A12345",
            "travel_date_from": "20260905", "travel_date_to": "20260905",
            "origin_station": "浙·杭州南站", "destination_station": "浙·宁波东站",
            "invoice_codes": [code, code], "invoice_numbers": numbers,
            "trip_count": 1, "invoice_count": 2, "total_amount": "21.37",
            "total_amount_cn": "贰拾壹元叁角柒分", "buyer_name": "合成测试有限公司"}
import hashlib
for ident, degraded in [("T01", False), ("T02", True)]:
    im = image.copy()
    suffix = ".png"
    if degraded:
        im = im.resize((900, 500), Image.Resampling.LANCZOS)
        im = im.rotate(3, expand=True, fillcolor="white", resample=Image.Resampling.BICUBIC)
        im = im.filter(ImageFilter.GaussianBlur(0.35))
        suffix = ".jpg"
    target = HERE / "inputs" / (ident + suffix)
    im.save(target, **({"quality": 72} if degraded else {}))
    data["cases"].append({"id": ident, "kind": "document", "synthetic_only": True,
                         "image": target.name, "image_size": list(im.size),
                         "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                         "expected": dict(expected),
                         "provenance": "Pillow drawing from fictional literals and secrets-generated digits; no original PDF accessed",
                         "transform": "900px, 3deg, blur=0.35, JPEG72" if degraded else "none"})
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Prepared T01/T02: synthetic only; no real invoice content.")
