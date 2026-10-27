"""One authorized R02 retest: distinguish printed facts from inferred counts."""
import argparse
import copy
import json
import fitz
import benchmark as b

parser = argparse.ArgumentParser()
parser.add_argument("--allow-real-materials", action="store_true", required=True)
parser.parse_args()
data = json.loads((b.HERE / "golden.json").read_text(encoding="utf-8"))
case = copy.deepcopy(next(c for c in data["cases"] if c["id"] == "R02"))
case["id"] = "R02N"
with fitz.open(b.ORIGINALS / case["source"]["rel"]) as doc:
    original_text = "\n".join(p.get_text() for p in doc)
assert "行程数量" not in original_text and "票据数量" not in original_text
case["expected"].update(trip_count=None, invoice_count=None)
case["followup_reason"] = "Original R02 supplied counts=1 despite no printed count labels; added explicit absence policy after observing the original output. This is a prompted retest, not another independent sample."
if not any(c["id"] == "R02N" for c in data["cases"]):
    data["cases"].append(case)
    b.dump(b.HERE / "golden.json", data)
base_prompt = b.prompt_for
suffix = ("\n附加的严格事实规则：trip_count只可抄录票面明确标注‘行程数量’的值；"
          "invoice_count只可抄录票面明确标注‘票据数量’或‘共X张票据’的值。"
          "没有这些标注时必须为null。即使画面看起来是一张发票或包含一次通行，也不得推断数量为1。")
b.prompt_for = lambda c: base_prompt(c) + suffix
b.event(action="absence_retest_started", case="R02N", source_case="R02", authorization="same explicitly authorized R02 image to api.z.ai")
b.run_one(case, "glm-5.3-flash")
