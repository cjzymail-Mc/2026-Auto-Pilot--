"""从已存只读观察证据本地重算无残留归因（零浏览器动作）。

attempt_001：观察已完成并全部落盘，仅收尾 p.close() AttributeError（Probe 无该方法）；
attempt_002：修正收尾后干净重跑（同只读范围零点击，两轮 17 行完全一致）。
归因规则（修正）：round-8 残留 = 回放关键词命中 ∨ (编制中 ∧ 创建于 2026-10-24)。
2026-10-23 的存量编制中草稿先于全部 round-7/round-8 填写，单独列为存量事实。
"""
import json
import time
from hashlib import sha256
from pathlib import Path

RUN = Path(__file__).resolve().parent
EV = RUN / "attempt_002/evidence"
data = json.loads((EV / "list_default_readonly.json").read_text(encoding="utf-8"))
rows = data.get("rows") or []
keywords = ("历史回放测试", "样品寄送", "外购样品")
joined = lambda row: " ".join(str(v) for v in row.values())
suspects = [row for row in rows if any(k in joined(row) for k in keywords)]
drafts = [row for row in rows if "编制中" in joined(row)]
today_drafts = [row for row in drafts if "2026-10-24" in joined(row)]
created_today = [row for row in rows if "2026-10-24" in joined(row)]

verdict = {
    "schema_version": "1.0",
    "observation": "server_no_residue_after_unsaved_close",
    "observed_at": "2026-10-24T18:06:14+08:00",
    "operator_scope": "登录人（陈晶）默认列表（本人单据，零筛选零业务点击）",
    "evidence": "attempt_002/evidence/list_default_readonly.json + list_default_readonly.png",
    "rows_read": len(rows),
    "page_text": data.get("page_text", ""),
    "fills_covered": {
        "express": "20261024-173807-72170651 SUCCESS_FILL_ONLY save=NOT_ATTEMPTED",
        "rd_materials": "20261024-174803-cd2e04e4 SUCCESS_FILL_ONLY save=NOT_ATTEMPTED",
    },
    "round8_residue": {
        "replay_keyword_hits": suspects,
        "draft_created_2026_10_24": today_drafts,
        "any_row_created_2026_10_24": created_today,
        "none": not suspects and not today_drafts and not created_today,
    },
    "preexisting_draft_observation": {
        "rows": drafts,
        "attribution": "15426104612 创建于 2026-10-23，早于 round-7（10-24）与 round-8（10-24）"
                       "全部真实填写；描述/金额/申请人与 round-7 回放材料同源——为 2026-10-23 "
                       "live-complex-demo 现场演示时期的服务端存量草稿，非本轮填写残留。",
        "disposition": "只读登记，不删除不提交不修改（红线：不得为清场触碰他人/历史草稿）",
    },
    "conclusion": "round-8 两笔 fill_only 未保存关页在服务端无残留（今日创建 0 行、回放关键词 0 命中）；"
                  "存量 10-23 草稿单列登记。",
    "execution_disclosure": "观察执行两遍：attempt_001 观察完成但收尾 AttributeError（Probe 无 close 方法），"
                            "attempt_002 修正 _close_browser+release_lock 后干净重跑；两轮同只读范围零点击，"
                            "17 行读数完全一致。合同④'观察一次'按诚实失败-重试纪律留痕（两遍均零写）。",
}
out = RUN / "no_residue_verdict_final.json"
out.write_text(json.dumps(verdict, ensure_ascii=False, indent=2), encoding="utf-8")
line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": "no_residue_verdict_recomputed",
                   "artifact": "no_residue_verdict_final.json",
                   "sha256": sha256(out.read_bytes()).hexdigest(),
                   "round8_no_residue": verdict["round8_residue"]["none"],
                   "preexisting_draft": "15426104612 (2026-10-23, live-complex-demo 存量)",
                   "attempts": "attempt_001 收尾异常已披露 / attempt_002 干净"}, ensure_ascii=False)
with (RUN / "events.jsonl").open("a", encoding="utf-8") as s:
    s.write(line + "\n")
print(line)
