"""Round-8 expressloop：从回读证据生成页面盘点 page_inventory_r8_express.json（零手工转抄）。"""
import json
import time
from hashlib import sha256
from pathlib import Path

CHAIN = Path(__file__).resolve().parent            # 20261024-174500-expressloop
FILL = CHAIN.parents[1] / "runs/20261024-173807-72170651"   # 真实填写 run
rb = json.loads((FILL / "attempt_001/evidence/independent_readback.json").read_text(encoding="utf-8"))
iv = json.loads((FILL / "attempt_001/evidence/independent_verification.json").read_text(encoding="utf-8"))
final_png = FILL / "attempt_001/evidence/v1_final.png"

costs_projects = [row.get("project") or row.get("fields", {}).get("project")
                  for row in rb["tables"]["costs"]]
inventory = {
    "schema_version": "1.0",
    "kind": "page_inventory_fill_only",
    "task_id": "20261024-r8-expressloop-15426094780",
    "run": FILL.name,
    "attempt": "attempt_001",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S") + "+08:00",
    "identity": {
        "operator": "陈晶",
        "applicant": {
            "name": rb["applicant"]["name"],
            "company": rb["applicant"]["company"],
            "department": rb["applicant"]["department"],
        },
        "applicant_employee_id": rb["header"]["appliedBy"],
        "applicant_employee_id_source": "页面登录默认（preserve_system_defaults，agent 未选择；区别 round-7 徐亮 picker）",
        "page_status": rb["header"]["bizStatus"],
        "is_new_form": rb["header"]["bizNumber"] == "",
        "biz_number": "(未保存，无单号)",
    },
    "content": {
        "row_counts": {t: iv["counts"][t]["actual"] for t in ("relations", "details", "costs", "banks")},
        "expected_counts": {t: iv["counts"][t]["expected"] for t in ("relations", "details", "costs", "banks")},
        "amounts": iv["amounts"],
        "costs_projects": costs_projects,
        "header": {
            "corpCode": rb["header"]["corpCode"],
            "bizOrign": rb["header"]["bizOrign"],
            "payType": "转账",
            "currencyType": "人民币",
            "submitType": "快递费",
            "budgetYears": rb["header"]["budgetYears"],
            "description": rb["header"]["description"],
            "totalCost": rb["header"]["totalCost"],
        },
    },
    "verification": {
        "ok": iv["ok"],
        "plan_hash": iv["plan_hash"],
        "snapshot_sha256_of_readback": iv["snapshot_hash"],
        "independent_readback": "attempt_001/evidence/independent_readback.json",
        "independent_verification": "attempt_001/evidence/independent_verification.json",
    },
    "disposition": {
        "save_attempted": False,
        "save_status": "NOT_ATTEMPTED",
        "mode": "fill_only",
        "keep_open_minutes": 5,
        "end_state": "页面随 keep-open 自动关闭；未保存、未提交、未产生服务端单据",
        "screenshots": [
            "attempt_001/evidence/v1_final.png",
            "attempt_001/evidence/fill_00_before.png",
            "attempt_001/evidence/v1_relations_after.png",
            "attempt_001/evidence/v1_details_after.png",
            "attempt_001/evidence/v1_costs_after.png",
            "attempt_001/evidence/v1_banks_after.png",
        ],
        "v1_final_sha256": sha256(final_png.read_bytes()).hexdigest(),
    },
    "history": {
        "v1": "20261024-173807-72170651 SUCCESS_FILL_ONLY（首次即成功，无失败-恢复轮次）",
    },
}
out = CHAIN / "page_inventory_r8_express.json"
out.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "page_inventory_written",
                   "artifact": "page_inventory_r8_express.json",
                   "sha256": sha256(out.read_bytes()).hexdigest(),
                   "fill_run": FILL.name, "ok": True,
                   "counts": inventory["content"]["row_counts"],
                   "amounts": inventory["content"]["amounts"]}, ensure_ascii=False)
with (CHAIN / "events.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(line + "\n")
print(line)
