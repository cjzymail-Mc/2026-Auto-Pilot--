# -*- coding: utf-8 -*-
"""stage1_offline_verify.py —— D2 观测 / D4 两处死等消除的离线 DOM 验证（round-2 合同 ctr-a10bb3f6）。

不连 OA、不载入 .pw-profile（红线②无关）：本地 file:// 夹具驱动【真实探针方法】
（object.__new__(Probe) 最小属性实例，__main__ 有守卫可安全 import）：

  五类离线观测（D2，条款1）          四类局部验证（D4/D5，条款4）
  ─────────────────────────────    ─────────────────────────────────
  S1 正常成功        = D 双击挂载    L1 点击后消失的浮层    = A + A2
  S2 缺失元素        = E1 纯文本格   L2 选中+确认的表格弹窗 = B
  S3 不可编辑元素    = C 只读回显格   L3 预算不可编辑回显   = C（同 S3）
  S4 内部捕获后继续  = E2 隐藏输入    L4 延迟挂载合法编辑器 = D（同 S1）
  S5 再次尝试        = E3 点击后显现

  A  = .ui-dropdown-panel 点行即关（panel.remove）→ row detach + 浮层关 → 选中提交
  A2 = 点行只删行、浮层仍开（this.remove）→ 未提交 → 如实按未选中收口（不默认成功）
  B  = .ui-dialog + table + footer 确定 → 行高亮 + 白名单确认 → 弹窗关闭、返回原文
  C  = td 内挂载 readonly input（预算科目只读回显）→ cell_input_skip，不 fill 死等
  D  = dblclick 才挂载可写 input（Enter 提交回 td.textContent）→ fill 成功（不误伤）
  E1 = td 无 input 无编辑器 → 两次激活后 CELL_NOT_EDITABLE（快速，无死等）
  E2 = input 一直 display:none → fill 8s 局部超时 → inner_exc×2 → 继续 → CELL_NOT_EDITABLE
  E3 = input 隐藏、第 3 次 click 才显现 → 第 1 次 fill 8s 超时留 inner_exc，第 2 次成功

断言基线：所有被测动作 timing 事件 dur_ms 均远小于 45000（证明局部守卫/短超时生效，
不再是 ≈45000ms×N 死等）；inner_exc / cell_input_skip / pick_row_detached /
pick_row_verify / 尝试序号(attempt/attempts) 在 events.jsonl 可查。
工件落 automation/offline-verify/<ts>-offline/（fixtures/ + evidence/ + events.jsonl +
offline_result.json）。运行：python -X utf8 -m tools.verification.offline_dom（仓库根）。
"""
import io
import json
import shutil
import sys
import time
import types
from pathlib import Path

from bpm.paths import ROOT as BASE
import bpm.browser_probe as probe_mod  # noqa: E402  (__main__ 有守卫，import 安全)

from playwright.sync_api import sync_playwright  # noqa: E402

OUT = BASE / "automation" / "offline-verify" / (
    time.strftime("%Y%m%d-%H%M%S") + "-offline")
FIX = OUT / "fixtures"
EV = OUT / "evidence"
OUT.mkdir(parents=True, exist_ok=False)
FIX.mkdir(exist_ok=True)
EV.mkdir(exist_ok=True)

# ---- 夹具（标记契约 = OVERLAY_DUMP_JS/DIALOG_DUMP_JS 选择器 + _vis boundingRect）----
FIXTURES = {
    # A：dropdown 点行即关（行+浮层同删）→ detach + 浮层关 = 点击即选中提交
    "a_dropdown_close.html": """<!doctype html><meta charset="utf-8"><title>A</title>
<body style="margin:0">
<div class="ui-dropdown-panel" id="panel" style="position:fixed;top:40px;left:40px;width:260px;height:140px;background:#fff;border:1px solid #999;z-index:10">
<ul style="margin:0;padding:0;list-style:none">
<li id="row-hit" style="padding:8px" onclick="document.getElementById('panel').remove()">命中行-alpha</li>
<li id="row-noise" style="padding:8px" onclick="document.getElementById('panel').remove()">干扰行-beta</li>
</ul></div></body>""",
    # A2：点行只删行、浮层仍开 → 未提交 → 按未选中失败收口
    "a2_dropdown_still_open.html": """<!doctype html><meta charset="utf-8"><title>A2</title>
<body style="margin:0">
<div class="ui-dropdown-panel" id="panel2" style="position:fixed;top:40px;left:40px;width:260px;height:140px;background:#fff;border:1px solid #999;z-index:10">
<ul style="margin:0;padding:0;list-style:none">
<li id="row-hit2" style="padding:8px" onclick="this.remove()">命中行-alpha</li>
<li id="row-noise2" style="padding:8px">干扰行-beta</li>
</ul></div></body>""",
    # B：确认式 p-dialog 弹表（行保留 + 高亮 + footer 白名单确定）
    "b_dialog_confirm.html": """<!doctype html><meta charset="utf-8"><title>B</title>
<body style="margin:0">
<div class="ui-dialog" id="dlg" style="position:fixed;top:60px;left:60px;width:380px;height:240px;background:#fff;border:1px solid #666;z-index:10">
<div class="ui-dialog-title">选择公出单</div>
<table style="width:100%"><thead><tr><th>公出单号</th></tr></thead>
<tbody><tr id="brow"><td style="padding:6px">12026075605 公出单</td></tr></tbody></table>
<div class="ui-dialog-footer" style="padding:8px;text-align:right">
<button id="bok">确定</button><button id="bcancel">取消</button></div></div>
<script>
document.getElementById('brow').addEventListener('click', function(){ this.classList.add('ui-state-highlight'); });
document.getElementById('bok').addEventListener('click', function(){ this.closest('.ui-dialog').remove(); });
</script></body>""",
    # C：预算科目式只读回显格（挂载 readonly input）
    "c_readonly_cell.html": """<!doctype html><meta charset="utf-8"><title>C</title>
<body><table><tbody><tr>
<td id="cell-ro" style="padding:6px;border:1px solid #ccc">差旅费预算<input readonly value="差旅费"></td>
</tr></tbody></table></body>""",
    # D：双击才挂载的可写编辑器（Enter 提交回 td.textContent）
    "d_dblclick_editor.html": """<!doctype html><meta charset="utf-8"><title>D</title>
<body><table><tbody><tr>
<td id="cell-edit" style="padding:6px;border:1px solid #ccc">原值</td>
</tr></tbody></table>
<script>
var td = document.getElementById('cell-edit');
td.addEventListener('dblclick', function(){
  if (td.querySelector('input')) return;
  var i = document.createElement('input');
  i.value = td.textContent.trim();
  i.addEventListener('keydown', function(ev){
    if (ev.key === 'Enter') { td.textContent = this.value; this.remove(); }
  });
  td.appendChild(i); i.focus();
});
</script></body>""",
    # E1：缺失元素——无 input、无编辑器（纯文本格）
    "e1_missing_editor.html": """<!doctype html><meta charset="utf-8"><title>E1</title>
<body><table><tbody><tr>
<td id="cell-plain" style="padding:6px;border:1px solid #ccc">纯文本格</td>
</tr></tbody></table></body>""",
    # E2：内部捕获后继续——input 一直 display:none（两次 8s 局部超时→inner_exc→continue）
    "e2_hidden_input.html": """<!doctype html><meta charset="utf-8"><title>E2</title>
<body><table><tbody><tr>
<td id="cell-hidden" style="padding:6px;border:1px solid #ccc">隐藏输入<input id="hi" style="display:none"></td>
</tr></tbody></table></body>""",
    # E3：再次尝试——第 3 次 click（dblclick 的 2 次 + 激活 click 的 1 次）才显现 input
    "e3_retry_reveal.html": """<!doctype html><meta charset="utf-8"><title>E3</title>
<body><table><tbody><tr>
<td id="cell-retry" style="padding:6px;border:1px solid #ccc">再试<input id="ri" style="display:none"></td>
</tr></tbody></table>
<script>
var n = 0;
document.getElementById('cell-retry').addEventListener('click', function(){
  n += 1;
  if (n >= 3) { document.getElementById('ri').style.display = ''; }
});
</script></body>""",
}
for name, html in FIXTURES.items():
    io.open(FIX / name, "w", encoding="utf-8", newline="\n").write(html)

# ---- 最小属性实例驱动真实探针方法（不跑 __init__，不碰 profile/lock）----
p = object.__new__(probe_mod.Probe)
p.run_dir = OUT
p.ev = EV
p.attempt = types.SimpleNamespace(name="offline-verify")
p.args = types.SimpleNamespace(run=OUT.name, doc_id="OFFLINE", expect_name="")

RESULTS = []


def check(scenario, name, cond, detail=""):
    RESULTS.append({"scenario": scenario, "assertion": name,
                    "ok": bool(cond), "detail": str(detail)[:200]})
    print(f"  {'PASS' if cond else 'FAIL'}  {name}"
          + (f"  [{detail}]" if detail and not cond else ""))


def events_since(scenario):
    """取该场景 start..end 标记之间的 events.jsonl 条目（追加式文件，全文读后切片）。"""
    lines = [json.loads(x) for x in io.open(
        OUT / "events.jsonl", encoding="utf-8").read().splitlines() if x.strip()]
    try:
        s = max(i for i, e in enumerate(lines)
                if e.get("event") == "offline_marker"
                and e.get("scenario") == scenario and e.get("phase") == "start")
        e_ = max(i for i, e in enumerate(lines)
                 if e.get("event") == "offline_marker"
                 and e.get("scenario") == scenario and e.get("phase") == "end")
        return lines[s:e_ + 1]
    except ValueError:
        return []


def timing_of(evs, action, **match):
    return [e for e in evs if e.get("event") == "timing" and e.get("action") == action
            and all(e.get(k) == v for k, v in match.items())]


def run_scenario(page, scenario, drive, shot_name):
    p.log_event(event="offline_marker", scenario=scenario, phase="start")
    t0 = time.perf_counter()
    out = drive(page)
    wall = time.perf_counter() - t0
    p.shot(page, shot_name)
    p.log_event(event="offline_marker", scenario=scenario, phase="end", wall_s=round(wall, 2))
    return out, wall


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True, args=["--no-proxy-server"])
    page = browser.new_page()
    page.set_default_timeout(20000)  # 本 harness 页级兜底；探针全局 45000 不在本脚本管辖

    # ---- A / L1a：dropdown 点行即关 → detach + 浮层关 = 选中提交（<10s，非 45s）----
    def drive_a(page):
        page.goto((FIX / "a_dropdown_close.html").as_uri())
        return p._overlay_search_pick(page, page, "命中行", "离线A-dropdown点行即关",
                                      prescan=True)
    res, wall = run_scenario(page, "A_dropdown_close_success", drive_a, "a_close.png")
    ev = events_since("A_dropdown_close_success")
    check("A", "真实链返回 True（外层成功路径）", res is True, f"res={res}")
    check("A", "pick_row_detached 事件 + overlay_open=False", any(
        e.get("event") == "pick_row_detached" and e.get("overlay_open") is False
        and e.get("chk") == "row_detached_overlay_state" for e in ev))
    t = timing_of(ev, "overlay_pick_row")
    check("A", "overlay_pick_row 完成（无 45s 死等）",
          bool(t) and t[0].get("dur_ms", 10 ** 9) < 10000,
          f"dur={t[0].get('dur_ms') if t else 'NA'}ms wall={wall:.1f}s")
    check("A", "fill_overlay_row selected=True（选中提交）", any(
        e.get("event") == "fill_overlay_row" and e.get("selected") is True for e in ev))

    # ---- A2 / L1b：点行后浮层仍开 → 未提交 → 失败收口（不默认成功）----
    def drive_a2(page):
        page.goto((FIX / "a2_dropdown_still_open.html").as_uri())
        return p._overlay_search_pick(page, page, "命中行", "离线A2-浮层仍开", prescan=True)
    res, wall = run_scenario(page, "A2_overlay_open_fail_loud", drive_a2, "a2_open_fail.png")
    ev = events_since("A2_overlay_open_fail_loud")
    check("A2", "真实链返回 False（按未选中收口）", res is False, f"res={res}")
    check("A2", "pick_row_detached overlay_open=True 留痕", any(
        e.get("event") == "pick_row_detached" and e.get("overlay_open") is True
        and e.get("chk") == "row_detached_overlay_open" for e in ev))
    check("A2", "未默认成功（早退于成功日志之前：无 fill_overlay_row 事件）+ fill_pick_miss 在场",
          not [e for e in ev if e.get("event") == "fill_overlay_row"]
          and any(e.get("event") == "fill_pick_miss" for e in ev))
    t = timing_of(ev, "overlay_pick_row")
    check("A2", "失败路径也无 45s 死等（<10s）",
          bool(t) and t[0].get("dur_ms", 10 ** 9) < 10000,
          f"dur={t[0].get('dur_ms') if t else 'NA'}ms wall={wall:.1f}s")

    # ---- B / L2：确认式 p-dialog 弹表（选中态+白名单确认原链不变）----
    def drive_b(page):
        page.goto((FIX / "b_dialog_confirm.html").as_uri())
        return p._overlay_search_pick(page, page, "12026075605", "离线B-确认式弹表",
                                      prescan=True)
    res, wall = run_scenario(page, "B_dialog_confirm_unchanged", drive_b, "b_dialog.png")
    ev = events_since("B_dialog_confirm_unchanged")
    check("B", "真实链返回 True", res is True, f"res={res}")
    tv = timing_of(ev, "pick_row_verify", attempt=1)
    check("B", "pick_row_verify（在挂行核验，即时返回）",
          bool(tv) and tv[0].get("outcome") == "ok" and tv[0].get("dur_ms", 10 ** 9) < 5000,
          f"{tv[0] if tv else 'NA'}")
    check("B", "fill_overlay_row selected=True + confirm=确定", any(
        e.get("event") == "fill_overlay_row" and e.get("selected") is True
        and "确定" in str(e.get("confirm")) for e in ev))
    check("B", "确认后弹窗已关（守卫未触发 dialog_still_open）", any(
        e.get("event") == "fill_overlay_row"
        and "dialog_still_open" not in str(e.get("confirm")) for e in ev))
    check("B", "页面对话框已移除", page.locator(".ui-dialog").count() == 0)

    # ---- C / S3 / L3：预算只读回显格 → cell_input_skip，不 fill ----
    def drive_c(page):
        page.goto((FIX / "c_readonly_cell.html").as_uri())
        cell = page.locator("#cell-ro")
        return p._fill_ng_cell(page, page, cell, "测试写入值")
    (st, rb), wall = run_scenario(page, "C_readonly_skip", drive_c, "c_ro.png")
    ev = events_since("C_readonly_skip")
    check("C", "返回 CELL_NOT_EDITABLE（既有语义不变）", st == "CELL_NOT_EDITABLE", f"st={st}")
    skips = [e for e in ev if e.get("event") == "cell_input_skip"]
    check("C", "cell_input_skip×2（attempt 1/2）带 readonly_or_disabled",
          len(skips) == 2 and {s.get("attempt") for s in skips} == {1, 2}
          and all(s.get("reason") == "readonly_or_disabled" for s in skips),
          f"skips={[(s.get('attempt'), s.get('reason')) for s in skips]}")
    check("C", "未发起任何 fill/select_option（无 cell_input_write）",
          not timing_of(ev, "cell_input_write"))
    check("C", "整格 <10s（旧路径 91.8s）", wall < 10, f"wall={wall:.1f}s")

    # ---- D / S1 / L4：双击挂载合法编辑器 → 照常 fill（不误伤）----
    def drive_d(page):
        page.goto((FIX / "d_dblclick_editor.html").as_uri())
        cell = page.locator("#cell-edit")
        return p._fill_ng_cell(page, page, cell, "新编辑值")
    (st, rb), wall = run_scenario(page, "D_dblclick_editor_ok", drive_d, "d_edit.png")
    ev = events_since("D_dblclick_editor_ok")
    check("D", "返回 OK", st == "OK", f"st={st}")
    check("D", "回读=写入值（Enter 提交回 td）", rb == "新编辑值", f"rb={rb!r}")
    ta = timing_of(ev, "cell_activate")
    check("D", "cell_activate 带尝试序号（attempt/attempts）",
          bool(timing_of(ev, "cell_activate", attempt=1, attempts=2)),
          f"activate={[ (e.get('attempt'), e.get('attempts')) for e in ta]}")
    tw = timing_of(ev, "cell_input_write", how="fill")
    check("D", "cell_input_write how=fill outcome=ok（可写编辑器未误伤）",
          bool(tw) and tw[0].get("outcome") == "ok" and tw[0].get("attempt") == 1,
          f"{tw[0] if tw else 'NA'}")
    check("D", "整格 <10s", wall < 10, f"wall={wall:.1f}s")

    # ---- E1 / S2：缺失元素（无 input/编辑器）→ 快速 CELL_NOT_EDITABLE ----
    def drive_e1(page):
        page.goto((FIX / "e1_missing_editor.html").as_uri())
        cell = page.locator("#cell-plain")
        return p._fill_ng_cell(page, page, cell, "x")
    (st, rb), wall = run_scenario(page, "E1_missing_element", drive_e1, "e1_missing.png")
    ev = events_since("E1_missing_element")
    check("E1", "返回 CELL_NOT_EDITABLE（缺失=如实报）", st == "CELL_NOT_EDITABLE", f"st={st}")
    check("E1", "cell_activate×2（attempt 1/2）", len(
        timing_of(ev, "cell_activate")) == 2)
    check("E1", "无 inner_exc / 无 skip / 无 write（纯缺失不产生异常记录）",
          not [e for e in ev if e.get("event") in ("inner_exc", "cell_input_skip")]
          and not timing_of(ev, "cell_input_write"))
    check("E1", "整格 <10s", wall < 10, f"wall={wall:.1f}s")

    # ---- E2 / S4：内部捕获后继续（隐藏 input → 8s 局部超时 → inner_exc → continue）----
    def drive_e2(page):
        page.goto((FIX / "e2_hidden_input.html").as_uri())
        cell = page.locator("#cell-hidden")
        return p._fill_ng_cell(page, page, cell, "不可见值")
    (st, rb), wall = run_scenario(page, "E2_hidden_continue", drive_e2, "e2_hidden.png")
    ev = events_since("E2_hidden_continue")
    ix = [e for e in ev if e.get("event") == "inner_exc"
          and e.get("where") == "cell_input_write"]
    check("E2", "inner_exc×2（exc=TimeoutError，吞前留痕）",
          len(ix) == 2 and all(e.get("exc") == "TimeoutError" for e in ix)
          and {e.get("attempt") for e in ix} == {1, 2}
          and all(e.get("behavior") == "continue_next_act" for e in ix),
          f"{[(e.get('attempt'), e.get('exc'), e.get('dur_ms')) for e in ix]}")
    tw = timing_of(ev, "cell_input_write")
    check("E2", "cell_input_write×2 全 outcome=timeout（异常可见非吞）",
          len(tw) == 2 and all(e.get("outcome") == "timeout" for e in tw),
          f"{[(e.get('attempt'), e.get('outcome'), e.get('dur_ms')) for e in tw]}")
    check("E2", "单次 ≈8s 局部短超时（非 45s 死等）",
          bool(tw) and all(7000 <= e.get("dur_ms", 0) < 12000 for e in tw),
          f"durs={[e.get('dur_ms') for e in tw]}")
    check("E2", "继续后仍 CELL_NOT_EDITABLE（行为语义不变）", st == "CELL_NOT_EDITABLE", f"st={st}")

    # ---- E3 / S5：再次尝试（第 1 次 8s 超时留痕，第 2 次成功）----
    def drive_e3(page):
        page.goto((FIX / "e3_retry_reveal.html").as_uri())
        cell = page.locator("#cell-retry")
        return p._fill_ng_cell(page, page, cell, "再试成功值")
    (st, rb), wall = run_scenario(page, "E3_retry_success", drive_e3, "e3_retry.png")
    ev = events_since("E3_retry_success")
    t1 = timing_of(ev, "cell_input_write", how="fill", attempt=1)
    t2 = timing_of(ev, "cell_input_write", how="fill", attempt=2)
    check("E3", "attempt=1 outcome=timeout + attempt=2 outcome=ok（逐次可见）",
          bool(t1) and t1[0].get("outcome") == "timeout"
          and bool(t2) and t2[0].get("outcome") == "ok",
          f"a1={t1[0].get('outcome') if t1 else 'NA'} a2={t2[0].get('outcome') if t2 else 'NA'}")
    ix = [e for e in ev if e.get("event") == "inner_exc"
          and e.get("where") == "cell_input_write" and e.get("attempt") == 1]
    check("E3", "inner_exc 仅 attempt=1（第 2 次成功不再有）", len(ix) == 1)
    check("E3", "重试后返回 OK（再次尝试可成功）", st == "OK", f"st={st}")

    # ---- 全局红线：离线全程无任何 ≥45s 计时段 ----
    all_lines = [json.loads(x) for x in io.open(
        OUT / "events.jsonl", encoding="utf-8").read().splitlines() if x.strip()]
    big = [e for e in all_lines if e.get("event") == "timing"
           and e.get("dur_ms", 0) >= 45000]
    check("GLOBAL", "全程无 ≥45000ms 计时段（死等消除）", not big, f"{big[:3]}")
    browser.close()

# ---- 工件落盘 ----
ok_n = sum(1 for r in RESULTS if r["ok"])
summary = {
    "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "contract": "ctr-a10bb3f6", "round": 2,
    "probe_sha256_head": __import__("hashlib").sha256(
        io.open(Path(probe_mod.__file__), "rb").read()).hexdigest()[:16],
    "total": len(RESULTS), "passed": ok_n, "failed": len(RESULTS) - ok_n,
    "scenarios": sorted({r["scenario"] for r in RESULTS}),
    "results": RESULTS,
}
io.open(OUT / "offline_result.json", "w", encoding="utf-8", newline="\n").write(
    json.dumps(summary, ensure_ascii=False, indent=1))
print()
print(f"OFFLINE VERIFY {'ALL PASS' if ok_n == len(RESULTS) else 'FAILED'}"
      f"（{ok_n}/{len(RESULTS)} 断言；工件 → {OUT.relative_to(BASE)}）")
sys.exit(0 if ok_n == len(RESULTS) else 1)
