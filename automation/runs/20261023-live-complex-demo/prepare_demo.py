"""Explicit user-selected historical replay; not evidence of new expenses."""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from bpm_plan import file_hash, load_type, validate_plan, plan_hash
from bpm_materials import inventory_materials

out = Path(__file__).resolve().parent
evidence = out / "attempt_002/evidence"
display_path = evidence / "history_display_snapshot.json"
display = json.loads(display_path.read_text(encoding="utf-8"))
snapshot_path = evidence / "template_snapshot.json"
snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
config = load_type("travel")
task_id = "20261023-user-complex-history-demo-15426093015"
plan = {"schema_version":"1.0","config_version":"1.0","task_id":task_id,"document_type":"travel",
        "operator":"陈晶","applicant":copy.deepcopy(display["applicant"]),
        "template":{"biz_number":snapshot["biz_number"],"captured_at":snapshot["captured_at"],
                    "snapshot_path":str(snapshot_path),"sha256":file_hash(snapshot_path)},
        "header":{key:display["header"][key] for key in config["header"]},
        "tables":{},"sources":{},"unresolved":[],"not_applicable":[],
        "amount_rules":{"costs":"sum","cost_amount_semantics":"line_total"},
        "authorization":{"mode":"fill_only","task_id":task_id,"allow_submit":False,
            "statement":"用户要求挑选近期较复杂历史报销单并填好供现场检查；本任务仅复演历史内容、不代表本次新费用，只填不存，禁止提交。"}}
plan["header"]["description"] = "【现场演示·不保存】" + display["header"]["description"]
for key,spec in config["tables"].items():
    plan["tables"][key] = [{"row_id":f"demo-{key}-{i+1}","fields":{prop:r["fields"][prop] for prop in spec["columns"]}}
                             for i,r in enumerate(display["tables"][key])]
for row in plan["tables"]["costs"]:
    if not row["fields"]["reason"]:
        row["fields"]["reason"] = "历史单未填项目说明（现场演示）"
material_root = out / "demonstration_materials"
material_root.mkdir(exist_ok=True)
reason = "用户授权本次仅按历史内容演示填写，不保存、不提交，不发生新的报销；本演示不要求提供新发票，此说明不构成真实报销免票规则。"
facts = {k:copy.deepcopy(plan[k]) for k in ("applicant","header","tables")}
facts.update(demo_only=True,not_new_expenses=True,invoice_requirement_for_demo=reason,
             user_request="你挑一个近期的报销单（复杂度稍微高一些的），然后填好给我现场检查下看看；注意，制单人一开始填好好不能再改，否则所有内容都会被自动清空",
             source_history={"number":snapshot["biz_number"],"path":str(display_path),"sha256":file_hash(display_path)},
             transformations=["备注加现场演示不保存标识", "历史为空的3行项目说明加明确演示注记，未虚构行程或费用"])
proof = material_root / "user_authorized_historical_replay.json"
proof.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
digest = file_hash(proof)
pointers = [f"/{section}/{key}" for section in ("applicant","header") for key in plan[section]]
pointers += [f"/tables/{table}/{i}/fields/{prop}" for table,rows in plan["tables"].items()
             for i,row in enumerate(rows) for prop in row["fields"]]
plan["sources"] = {ptr:{"kind":"material","path":str(proof),"locator":ptr,"sha256":digest} for ptr in pointers}
manifest = out / "materials_manifest.json"
manifest.write_text(json.dumps(inventory_materials(material_root),ensure_ascii=False,indent=2),encoding="utf-8")
plan["materials"] = {"manifest_path":str(manifest),"manifest_sha256":file_hash(manifest),
    "no_invoice_rows":[{"plan_pointer":f"/tables/costs/{i}/fields/cost","reason":reason,
                        "proof":{"kind":"user","path":str(proof),"locator":"/invoice_requirement_for_demo","sha256":digest}}
                       for i,_ in enumerate(plan["tables"]["costs"])]}
issues = validate_plan(plan,expected_operator="陈晶",base_dir=out)
(out/"demo_plan_validation.json").write_text(json.dumps({"issues":issues,"mode":"historical_demo_fill_only","plan_hash":plan_hash(plan)},ensure_ascii=False,indent=2),encoding="utf-8")
if issues:
    print(json.dumps(issues,ensure_ascii=False,indent=2))
    sys.exit(2)
(out/"fill_plan.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"validation":"PASS","template":snapshot["biz_number"],"total":plan["header"]["totalCost"],
                  "counts":{k:len(v) for k,v in plan["tables"].items()},"plan_hash":plan_hash(plan)},ensure_ascii=False))
