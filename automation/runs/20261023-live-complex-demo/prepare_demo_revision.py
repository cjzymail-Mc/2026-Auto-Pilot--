"""Preserve original evidence; apply the user's explicit demo-only substitution."""
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from bpm_plan import file_hash,validate_plan,plan_hash
from bpm_materials import inventory_materials

run=Path(__file__).resolve().parent
old=json.loads((run/"fill_plan.json").read_text(encoding="utf-8"))
plan=copy.deepcopy(old)
numbers=["12026101976","12026070366","12026037675"]
for row,number in zip(plan["tables"]["relations"],numbers):
    row["fields"]["bizNumber"]=number
plan["header"]["description"]="【现场演示·不保存·关联已替换】公出油补"
plan["authorization"]["statement"] += " 用户另行明确同意：允许，仅用于本次演示；精确改用12026101976、12026070366、12026037675，仍禁止保存和提交。"
material=run/"demonstration_materials_revision02"
material.mkdir(exist_ok=False)
original=json.loads((run/"demonstration_materials/user_authorized_historical_replay.json").read_text(encoding="utf-8"))
facts={k:copy.deepcopy(plan[k]) for k in ("applicant","header","tables")}
facts.update(demo_only=True,not_new_expenses=True,source_history=original["source_history"],
             user_request=original["user_request"],invoice_requirement_for_demo=original["invoice_requirement_for_demo"],
             substitution_authorization={"question":"原三张公出单不可选，仅本次演示是否允许替换为12026101976、12026070366、12026037675并标注演示关联？",
                                         "user_reply":"允许，仅用于本次演示","numbers":numbers},
             previous_plan_sha256=plan_hash(old),
             transformations=original["transformations"]+["原关联不可选，用户明确授权本次演示替换三个完整号，金额分布沿用，不代表真实费用归属"])
proof=material/"authorized_demo_revision02.json"
proof.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
sha=file_hash(proof)
for ptr in plan["sources"]:
    plan["sources"][ptr]={"kind":"material","path":str(proof),"locator":ptr,"sha256":sha}
manifest=run/"materials_manifest_revision02.json"
manifest.write_text(json.dumps(inventory_materials(material),ensure_ascii=False,indent=2),encoding="utf-8")
plan["materials"]={"manifest_path":str(manifest),"manifest_sha256":file_hash(manifest),
                    "no_invoice_rows":[{"plan_pointer":f"/tables/costs/{i}/fields/cost","reason":facts["invoice_requirement_for_demo"],
                                        "proof":{"kind":"user","path":str(proof),"locator":"/invoice_requirement_for_demo","sha256":sha}}
                                       for i,_ in enumerate(plan["tables"]["costs"])]}
issues=validate_plan(plan,expected_operator="陈晶",base_dir=run)
assert not issues,issues
(run/"fill_plan_revision02.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"validation":"PASS","previous_plan_hash":plan_hash(old),"new_plan_hash":plan_hash(plan),"mode":"fill_only","substitutions":numbers},ensure_ascii=False))
