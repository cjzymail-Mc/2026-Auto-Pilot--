# -*- coding: utf-8 -*-
"""recalc_timeline.py —— events.jsonl 统一复算脚本（round-2 D3②，合同 ctr-a10bb3f6）。

从原始 events.jsonl 重算单次 attempt 的：fill 跨度 / 顶层段合计（互不嵌套）/ 缝隙 /
热点 Top / 内层观测计数（inner_exc / cell_input_skip / pick_row_detached /
fill_field_result）/ ≥45s 死等扫描。A 验收可直接重跑，与报告数字同口径：

  python -X utf8 docs/路线与评估/recalc_timeline.py \
      --events automation/runs/20261021-131724-1c1aadbd/events.jsonl --attempt attempt_025
  python -X utf8 docs/路线与评估/recalc_timeline.py \
      --events automation/runs/20261021-131724-1c1aadbd/events.jsonl --attempt attempt_026

口径（与 2026-10-23 计时报告 §3 一致）：
- 窗口 = 该 attempt 自己的 fill_start → fill_end（fill 阶段切片，不含登录/测绘）；
  跨度取窗口内全部 timing 事件的 first_t0 → last_end（t0_ms epoch + dur_ms 同毫秒域近似）。
- 顶层段 = 不被任何其他 timing 事件区间包含的事件（epsilon 60ms 吸收 perf_counter/epoch
  混用与 int 截断）；顶层合计 = Σ dur(顶层)；缝隙 = 跨度 − 顶层合计。
- 三口径并报（D3① 修订依据）：顶层合计（全部互不嵌套）≈ A 复算口径；业务段名项合计
  （action=section_fill/table_row_fill/table_pick/overlay_pick 等业务名）≈ 报告 §3.1
  段表口径；两者之差 = 已埋点未单列项（cell_fill(独立段)/screenshot 等），单独列出。
"""
import argparse
import io
import json
import sys


def load_events(path):
    return [json.loads(x) for x in io.open(path, encoding="utf-8").read().splitlines()
            if x.strip()]


def attempt_window(events, attempt):
    """该 attempt 自己的 fill_start → fill_end 切片（fill 阶段口径，与报告 §3 一致）。"""
    idx = [i for i, e in enumerate(events)
           if e.get("event") == "probe_start" and e.get("attempt") == attempt]
    if not idx:
        sys.exit(f"[recalc] 找不到 probe_start attempt={attempt}")
    s = idx[-1]
    fs = [i for i in range(s, len(events)) if events[i].get("event") == "fill_start"]
    if not fs:
        sys.exit(f"[recalc] {attempt} 窗口内无 fill_start")
    a = fs[0]
    fe = [i for i in range(a, len(events)) if events[i].get("event") == "fill_end"]
    return events[a:fe[0] + 1] if fe else events[a:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--attempt", required=True)
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    ev = attempt_window(load_events(a.events), a.attempt)
    tm = [e for e in ev if e.get("event") == "timing" and isinstance(e.get("dur_ms"), (int, float))]
    if not tm:
        sys.exit(f"[recalc] {a.attempt} 窗口内无 timing 事件")

    iv = [(e["t0_ms"], e["t0_ms"] + e["dur_ms"], e) for e in tm]
    span = (max(b for _, b, _ in iv)) - (min(x for x, _, _ in iv))

    # 顶层 = 区间不被其他区间包含（epsilon 60ms；同区间互含时留 dur 较大者）
    EPS = 60
    top = []
    for x0, x1, e in iv:
        nested = False
        for y0, y1, f in iv:
            if f is e or f["dur_ms"] <= e["dur_ms"]:
                continue
            if y0 - EPS <= x0 and x1 <= y1 + EPS:
                nested = True
                break
        if not nested:
            top.append(e)
    top_sum = sum(e["dur_ms"] for e in top)
    glue = span - top_sum

    print(f"== {a.attempt}（fill_start→fill_end 切片）==")
    print(f"timing 事件: {len(tm)}  | fill 跨度: {span/1000:.1f}s  | "
          f"顶层段合计(全部互不嵌套): {top_sum/1000:.1f}s（{len(top)} 条）  | "
          f"缝隙: {glue/1000:.1f}s")

    named_sections = {"section_fill", "table_row_fill", "fill_ng_map",
                      "related_doc_fill", "table_pick", "overlay_pick"}
    seg = [e for e in top if e.get("action") in named_sections]
    seg_sum = sum(e["dur_ms"] for e in seg)
    buried = [e for e in top if e.get("action") not in named_sections]
    buried_sum = sum(e["dur_ms"] for e in buried)
    print(f"三口径：业务段名项合计 {seg_sum/1000:.1f}s（报告 §3.1 段表口径）｜"
          f"已埋点未单列项 {buried_sum/1000:.1f}s（{len(buried)} 条，D3① 应单列）｜"
          f"顶层合计 {top_sum/1000:.1f}s（A 复算口径）")
    buried_big = sorted((e for e in buried if e["dur_ms"] >= 300),
                        key=lambda e: -e["dur_ms"])
    print(f"-- 已埋点未单列项明细（≥300ms） --")
    for e in buried_big[:10]:
        print(f"  {e['dur_ms']:>7.0f}ms  {e.get('action')}  "
              f"where={e.get('where') or e.get('section') or '-'} "
              f"field={e.get('field') or '-'}")

    print(f"-- 热点 Top{a.top}（全部 timing，含嵌套） --")
    for e in sorted(tm, key=lambda e: -e["dur_ms"])[:a.top]:
        print(f"  {e['dur_ms']:>7.0f}ms  {e.get('action'):<22} outcome={e.get('outcome')} "
              f"where={e.get('where') or '-'} field={e.get('field') or '-'} "
              f"L{e.get('_ln', '?')}")

    obs = {k: sum(1 for e in ev if e.get("event") == k)
           for k in ("inner_exc", "cell_input_skip", "pick_row_detached",
                     "pick_row_detached_open", "fill_field_result")}
    obs["pick_row_verify_ok"] = sum(
        1 for e in tm if e.get("action") == "pick_row_verify" and e.get("outcome") == "ok")
    obs["attempt_numbered_activate"] = sum(
        1 for e in tm if e.get("action") == "cell_activate" and e.get("attempts") == 2)
    print(f"-- 内层观测（D2） --  {obs}")

    big = [e for e in tm if e["dur_ms"] >= 45000]
    print(f"-- ≥45000ms 死等扫描: {len(big)} 条"
          + (f" → {[e.get('action') for e in big]}" if big else "（无）"))

    pe = [e for e in ev if e.get("event") == "probe_end"]
    if pe:
        print(f"probe_end: {pe[-1].get('reason')} tech={pe[-1].get('tech_used_s')}s "
              f"budget_respected={pe[-1].get('budget_respected')}")


if __name__ == "__main__":
    main()
