"""Round-8 P2 ④：未保存关页服务端无残留——只读列表观察一次（零业务点击）。

依据：round-8 两笔 fill_only 闭环（express 20261024-173807 / rd 20261024-174803）
save_status=NOT_ATTEMPTED、页面随 keep-open 关闭。本脚本只读核验：登录人（陈晶）
默认列表（本人单据）中不存在可归因于这两次填写的服务端单据（编制中/2026-10-24
创建/回放描述关键词）。复用 stage1_browser_probe 锁+启动+登录门与 list_type_query
的只读行读取；零导航零表单写入零保存族点击。cwd 必须仓库根。
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

RUN_DIR = Path(__file__).resolve().parent
ROOT = RUN_DIR.parents[2]
sys.path.insert(0, str(ROOT))

import stage1_browser_probe as pb                              # noqa: E402
from stage1_browser_probe import HOST, LIST_PATH, Probe, assert_internal  # noqa: E402
from list_type_query import ROWS_PROP_JS                       # noqa: E402


def main():
    args = SimpleNamespace(run=RUN_DIR.name, doc_id=None, expect_name="陈晶",
                           tech_budget=300.0, login_wait=0.0, wall_cap=420.0,
                           interactive_pick=False, pick_wait=0.0,
                           keep_open_minutes=0.0, fill_plan=None)
    p = Probe(args)
    p.acquire_lock()
    try:
        p._launch()
        p.log_event(event="no_residue_observation_start", mode="readonly_zero_click")
        st = p.phase_entry()
        if st != pb.PASS:
            p.say("登录未成立（{0}），终止（--login-wait 0 不等待扫码）".format(st))
            return 2
        p._save_session_state()
        p.page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded",
                    timeout=45000)
        try:
            p.page.wait_for_selector("th.prop-submitType", timeout=30000)
        except Exception:
            p.log_event(event="table_wait_timeout", url=p.page.url[:80])
        p.page.wait_for_timeout(1500)
        data = p.page.evaluate(ROWS_PROP_JS)
        rows = (data or {}).get("rows") or []
        p.save("list_default_readonly.json",
               json.dumps(data, ensure_ascii=False, indent=1))
        p.shot(p.page, "list_default_readonly.png")

        keywords = ("历史回放测试", "样品寄送", "外购样品")
        suspects = [row for row in rows if any(k in " ".join(str(v) for v in row.values())
                                               for k in keywords)]
        drafts = [row for row in rows if "编制" in " ".join(str(v) for v in row.values())]
        today = [row for row in rows if "2026-10-24" in " ".join(str(v) for v in row.values())]
        verdict = {"observation": "server_no_residue_after_unsaved_close",
                   "operator_scope": "登录人默认列表（本人单据，零筛选零点击）",
                   "rows_read": len(rows),
                   "page_text": (data or {}).get("page_text", ""),
                   "replay_keyword_hits": suspects,
                   "draft_status_rows": drafts,
                   "created_today_rows": today,
                   "fill_runs_covered": ["20261024-173807-72170651", "20261024-174803-cd2e04e4"],
                   "no_residue": not suspects and not drafts,
                   "note": "无回放关键词命中且无编制中行 → 两次未保存关页在服务端无残留单据"}
        p.save("no_residue_verdict.json", json.dumps(verdict, ensure_ascii=False, indent=2))
        p.log_event(event="no_residue_observation_done", rows=len(rows),
                    keyword_hits=len(suspects), draft_rows=len(drafts),
                    no_residue=verdict["no_residue"])
        print(json.dumps(verdict, ensure_ascii=False))
        return 0
    finally:
        p._close_browser()
        p.release_lock()


if __name__ == "__main__":
    sys.exit(main())
