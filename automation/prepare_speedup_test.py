"""Prepare a separately authorized, unsaved historical-replay test plan."""
import argparse
import copy
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bpm.plan import file_hash, plan_hash, validate_plan

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--round",required=True)
    ap.add_argument("--purpose",required=True)
    args=ap.parse_args()
    if not args.round.replace("-","").isalnum():
        raise ValueError("simple round required")
    out=ROOT/"automation/speedup-plans"/args.round
    out.mkdir(parents=True,exist_ok=False)
    old=ROOT/"automation/runs/20261023-live-complex-demo/fill_plan_revision02.json"
    plan=json.loads(old.read_text(encoding="utf-8"))
    authorization=ROOT/"feature01-细化报销skill/2026-10-23 真实演示后报销填写提速方案.md"
    t0=time.time()*1000
    plan["task_id"]="speedup-20261023-"+args.round
    plan["authorization"]={"mode":"fill_only","task_id":plan["task_id"],"allow_submit":False,
        "statement":"本方案第 2.1 节明确授权的新建未保存测试单，复用已确认示范数据，仅用于 "+args.purpose+"；禁止保存和提交"}
    plan["test_context"]={"purpose":args.purpose,"round":args.round,
        "authorization_path":str(authorization),"authorization_sha256":file_hash(authorization)}
    plan["identity"]={"applicant_employee_id":"117070006","creator_name":"陈晶","creator_department":"运动表现研究部"}
    plan["header"]["description"]="【提速测试·不保存·"+args.round+"】公出油补"
    # The old source files remain immutable; the new explicit test facts retain
    # their exact replay lineage and cannot be mistaken for new business costs.
    facts={k:copy.deepcopy(plan[k]) for k in ("applicant","header","tables","identity")}
    old_facts=Path(next(iter(plan["sources"].values()))["path"])
    original=json.loads(old_facts.read_text(encoding="utf-8"))
    facts.update(test_only=True,not_new_expenses=True,purpose=args.purpose,
        replay_plan_path=str(old),replay_plan_sha256=file_hash(old),
        no_invoice_rule="本次仅为已授权未保存测试，复用已确认示范数据；不代表真实新费用或实际业务免票依据")
    fp=out/"test_facts.json"
    fp.write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
    pointers=[f"/{k}/{p}" for k in ("applicant","header","identity") for p in plan[k]]
    pointers += [f"/tables/{k}/{i}/fields/{p}" for k,rows in plan["tables"].items() for i,r in enumerate(rows) for p in r["fields"]]
    plan["sources"]={p:{"kind":"user","path":str(fp),"sha256":file_hash(fp),"locator":p} for p in pointers}
    for r in plan["materials"]["no_invoice_rows"]:
        r["reason"]=facts["no_invoice_rule"]
        r["proof"]={"kind":"user","path":str(fp),"sha256":file_hash(fp),"locator":"/no_invoice_rule"}
    issues=validate_plan(plan,expected_operator="陈晶",base_dir=out)
    if issues:
        raise ValueError(issues)
    path=out/"fill_plan.json"
    path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"preparation.json").write_text(json.dumps({"t0_ms":t0,"dur_ms":time.time()*1000-t0,
        "kind":"reuse_confirmed_demonstration_inputs_no_new_material_parsing",
        "purpose":args.purpose,"plan_hash":plan_hash(plan),"authorization_sha256":file_hash(authorization),
        "template_sha256":plan["template"]["sha256"],"materials_sha256":plan["materials"]["manifest_sha256"],
        "protected_saved_sample":{"biz_number":"15426104612","uuid":"8fb51b7920424c24b89cd2b058e0a226","read_only":True}},ensure_ascii=False,indent=2),encoding="utf-8")
    print(path)
if __name__=="__main__":main()
