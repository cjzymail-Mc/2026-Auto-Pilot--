#!/usr/bin/env python3
"""BPM 报销单列表类型盘点（只读查询，不填不存）。

用途：按 制单人=运动表现研究部（org 选择器，回落 申请部门）查询报销单列表，
枚举 报销类别（prop-submitType）实际出现过的类型清单，为后续分类型 fill skill 提供底册。

复用 stage1_browser_probe 的：profile 锁 / 浏览器启动（--no-proxy-server）/ 登录态注入
（10h TTL）/ 扫码登录门 / 事件流落盘。本脚本不 import 任何填写逻辑，不点击任何
NO_SAVE_WORDS 按钮（查询/翻页除外，均过守卫）。

用法（cwd=仓库根）：python -X utf8 -m tools.diagnostics.type_query [--dept 运动表现研究部] [--login-wait 480]
工件：automation/runs/<run>/（events.jsonl / attempt_001/evidence/ / types_result.json）
"""
import argparse
import io
import json
import re
import sys
import time
from types import SimpleNamespace

import bpm.browser_probe as pb
from bpm.browser_probe import (HOST, LIST_PATH, NO_SAVE_WORDS, Probe,
                                  assert_internal, mask)

# 数据表行读取：按 thead th 的 prop-* 类映射列名（form-schema v0.2 结论：列头带 prop-*）。
# PrimeNG 滚动表拆表陷阱（2026-10-23 两轮实证）：表头表有 prop-* thead 但 tbody 空；
# 表体表带全部行却【无 thead】→ 不能用同一条件筛表。改为两步：先从任一含 submitType
# 的 thead 取列序 props，再对【所有】表的 tbody tr 按列下标映射。
ROWS_PROP_JS = """
() => {
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  let props = null, heads = [];
  for (const t of document.querySelectorAll('table')) {
    const ths = [...t.querySelectorAll('thead th')];
    const p = ths.map(th => ((th.className || '').match(/prop-([\\w]+)/) || [])[1] || null);
    if (p.includes('submitType')) { props = p; heads = ths.map(th => clean(th.innerText)); break; }
  }
  if (!props) return null;
  const rows = [];
  for (const t of document.querySelectorAll('table')) {
    for (const tr of t.querySelectorAll('tbody tr')) {
      const tds = [...tr.children];
      if (tds.length < 3) continue;
      const o = {};
      tds.forEach((td, i) => { if (props[i]) o[props[i]] = clean(td.innerText); });
      if (Object.values(o).some(v => v)) rows.push(o);
    }
  }
  const pg = document.querySelector('.ui-paginator');
  const next = document.querySelector('.ui-paginator-next');
  return {heads, rows, page_text: pg ? (pg.innerText || '').replace(/\\s+/g, ' ').trim() : '',
          next_disabled: next ? next.className.includes('ui-state-disabled') : null};
}
"""

def guard_click(p, what):
    """与主探针 _click_guard 同口径：禁点词一律拒。"""
    w = re.sub(r"\s+", "", (what or ""))
    if not w or any(bad in w or w in bad for bad in NO_SAVE_WORDS if bad):
        raise RuntimeError(f"NO_SAVE_GUARD: 拒绝点击「{what}」")
    return True


class TypeQuery:
    def __init__(self, args):
        self.args = args
        probe_args = SimpleNamespace(
            run=args.run, doc_id=None, expect_name=args.expect_name,
            tech_budget=1800.0, login_wait=args.login_wait, wall_cap=2400.0,
            interactive_pick=False, pick_wait=0.0, keep_open_minutes=0.0,
            fill_plan=None)
        self.p = Probe(probe_args)          # 复用锁/启动/登录门/落盘，不跑其 main 流程
        self.page = None

    # ---- 基础 ----
    def rows(self):
        return self.page.evaluate(ROWS_PROP_JS)

    def wait_table(self, timeout_s=30.0):
        """等数据表挂载（th.prop-submitType 出现）+ 渲染沉降。Angular 异步绑定，
        goto 后 3s 定睡不稳（2026-10-23 两轮实证 0 行）。"""
        try:
            self.page.wait_for_selector("th.prop-submitType", timeout=int(timeout_s * 1000))
        except Exception:
            self.p.log_event(event="table_wait_timeout", url=self.page.url[:80])
        self.page.wait_for_timeout(1500)

    def query_click(self):
        """点击筛选区的 查询/搜索 按钮（唯一允许的提交类动作，非保存族）。"""
        for name in ("查询", "搜索", "检索"):
            loc = self.page.get_by_role("button", name=name, exact=True)
            if loc.count() > 0:
                guard_click(self.p, name)
                loc.first.click()
                return name
        # 兜底：全文枚举可见按钮文本
        texts = self.page.evaluate(
            "() => [...document.querySelectorAll('button')].filter(b => b.offsetParent)"
            ".map(b => (b.innerText||'').trim()).filter(Boolean).slice(0, 40)")
        self.p.say(f"未找到 查询/搜索/检索 按钮；可见按钮={texts}")
        raise RuntimeError("QUERY_BUTTON_NOT_FOUND")

    def read_all_pages(self, tag):
        """当前筛选下翻页采集全部行（翻页点击 a.ui-paginator-next，只读导航族）。
        按 单据编号+整行签名 去重，防冻结列/克隆表重复行。"""
        got, seen_keys, page_no, seen_total, empty_first = [], set(), 1, "?", True
        while True:
            self.page.wait_for_timeout(1800)
            r = self.rows()
            if not r:
                if empty_first and page_no == 1:
                    self.wait_table()          # 首页表慢挂载 → 再等一轮
                    r = self.rows()
                if not r:
                    self.p.say(f"[{tag}] 第 {page_no} 页未读到数据表")
                    break
            empty_first = False
            new_n = 0
            for row in r["rows"]:
                key = row.get("bizNumber") or "|".join(row.values())
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                got.append(row)
                new_n += 1
            page_txt = r.get("page_text") or ""
            m = re.search(r"(\d+)\s*条", page_txt) or re.search(r"of\s+(\d+)", page_txt) \
                or re.search(r"共\s*(\d+)", page_txt)
            if m:
                seen_total = m.group(1)
            self.p.log_event(event="list_page_read", tag=tag, page=page_no,
                             rows_new=new_n, total_seen=len(got), page_text=page_txt[:80])
            if new_n == 0 and page_no > 1:
                self.p.log_event(event="list_page_stalled", tag=tag, page=page_no)
            if r.get("next_disabled") is not False:   # None=无分页器 或 True=到底
                break
            if page_no >= 200:
                self.p.say("翻页上限 200 页保护触发")
                break
            self.page.locator("a.ui-paginator-next").first.click()
            page_no += 1
        return got, seen_total, page_no

    # ---- org 选择器（制单人/申请部门 共用交互） ----
    def org_select(self, row_cls, value):
        """打开 .form-row.<row_cls> 的组织选择弹窗（button[aria-label=选择组织] →
        p-dialog「组织架构」appendTo body），搜索并选中 value 节点。失败抛异常。
        DOM 依据：attempt_009 list.html——input readonly 不可直接输入，触发器是
        fa-sitemap 图标按钮；弹窗 styleclass=org-select-dialog。"""
        cont = self.page.locator(f"div.form-row.{row_cls}").first
        cont.scroll_into_view_if_needed()
        cont.screenshot(path=str(self.p.ev / f"org_{row_cls}_closed.png"))
        # 打开：点「选择组织」图标按钮（aria-label），等 org-select-dialog 可见
        btn = self.page.locator(f"div.form-row.{row_cls} button[aria-label='选择组织']").first
        if btn.count() == 0:
            raise RuntimeError(f"ORG_TRIGGER_NOT_FOUND:{row_cls}")
        btn.click(timeout=4000)
        dlg = self.page.locator(".org-select-dialog").first
        try:
            dlg.wait_for(state="visible", timeout=6000)
        except Exception:
            self.p.shot(self.page, f"org_{row_cls}_dialog_miss.png")
            raise RuntimeError(f"ORG_DIALOG_NOT_OPENED:{row_cls}")
        self.page.wait_for_timeout(1200)
        self.p.log_event(event="org_picker_opened", row=row_cls)
        self.p.save(f"org_{row_cls}_dialog.html", self.page.content())
        # 弹窗内搜索框（组织架构树通常带过滤输入）
        inp = dlg.locator("input:visible").first
        if inp.count() > 0:
            inp.fill("")
            inp.press_sequentially(value, delay=50)
            self.page.wait_for_timeout(1500)
        else:
            self.p.say("组织弹窗无可见搜索框——直接在树里找目标")
        # 选中节点：精确文本优先，包含次之
        node = dlg.get_by_text(value, exact=True).first
        if node.count() == 0:
            node = dlg.get_by_text(value, exact=False).first
        if node.count() == 0:
            self.p.shot(self.page, f"org_{row_cls}_node_miss.png")
            raise RuntimeError(f"ORG_NODE_NOT_FOUND:{row_cls}:{value}")
        txt = node.inner_text(timeout=3000).replace("\n", " ")[:40]
        guard_click(self.p, txt)
        node.click()
        self.p.log_event(event="org_node_clicked", row=row_cls, picked=txt)
        self.page.wait_for_timeout(1000)
        # 弹窗若有确认钮（确定/确认/选择）则点掉；无则节点点击即选中
        for name in ("确 定", "确定", "确 认", "确认", "选 择", "选择"):
            ok_btn = dlg.get_by_role("button", name=name, exact=True)
            if ok_btn.count() > 0 and ok_btn.first.is_visible():
                guard_click(self.p, name)
                ok_btn.first.click()
                self.p.log_event(event="org_dialog_confirmed", row=row_cls, btn=name)
                break
        self.page.wait_for_timeout(800)
        self.p.shot(self.page, f"org_{row_cls}_picked.png")

    # ---- 主流程 ----
    def run(self):
        p = self.p
        p.acquire_lock()
        ok = False
        try:
            p._launch()
            self.page = p.page
            p.log_event(event="type_query_start", dept=self.args.dept, mode="readonly")
            st = p.phase_entry()
            if st == "LOGIN_REQUIRED":
                p.say("登录态过期——需要企微扫码（约 21s 人工）")
                st = p.wait_login()
            if st != pb.PASS:
                p.say(f"登录未成立（{st}），终止")
                return 2
            p._save_session_state()          # 续 10h TTL

            # 1) 列表页 + 默认范围基线
            self.page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded", timeout=45000)
            self.wait_table()
            base = self.rows()
            base_rows = base["rows"] if base else []
            p.save("list_default.json", json.dumps(base, ensure_ascii=False, indent=1))
            p.shot(self.page, "list_default.png")
            p.say(f"默认列表 {len(base_rows)} 行（登录人本人单据）；分页信息={(base or {}).get('page_text', '')}")

            # 2) 组织条件查询：制单人=部门 → 回落 申请部门=部门
            got, total, pages, how = [], "?", 1, None
            for row_cls, label in (("CreatedPath", "制单人"), ("AppliedDeptPath", "申请部门")):
                try:
                    p.say(f"尝试筛选 {label}={self.args.dept} …")
                    self.org_select(row_cls, self.args.dept)
                    btn = self.query_click()
                    how = f"{label}={self.args.dept}（按钮「{btn}」）"
                    break
                except Exception as e:
                    p.say(f"{label} 筛选失败：{e!r} → 尝试下一策略")
                    p.log_event(event="org_filter_fail", row=row_cls, error=str(e)[:160])
                    try:
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(800)
                    except Exception:
                        pass
            if how:
                got, total, pages = self.read_all_pages("dept")
                p.save("list_dept_all.json", json.dumps(got, ensure_ascii=False, indent=1))
                p.shot(self.page, "list_dept_final.png")
            else:
                p.say("两种组织筛选均失败——按默认范围（登录人本人单据）盘点并如实标注")

            # 3) 汇总：主口径=近 2 年（制单日期 cutoff），附全量对照
            scope_rows = got if got else base_rows
            scope_note = how or "默认列表（登录人本人单据；组织筛选未成功）"
            today = time.localtime()
            try:
                cutoff = time.strftime("%Y-%m-%d", (today.tm_year - 2, today.tm_mon, today.tm_mday,
                                                    0, 0, 0, 0, 0, -1))
            except Exception:
                cutoff = f"{today.tm_year - 2}-01-01"
            rows_2y = [r for r in scope_rows if (r.get("createdAt") or "") >= cutoff]

            def aggregate(rows):
                types = {}
                for r in rows:
                    t = (r.get("submitType") or "(空)").strip() or "(空)"
                    d = types.setdefault(t, {"count": 0, "docs": [], "creators": set(),
                                             "depts": set(), "dates": []})
                    d["count"] += 1
                    if r.get("bizNumber") and len(d["docs"]) < 3:
                        d["docs"].append(r["bizNumber"])
                    if r.get("createdName"):
                        d["creators"].add(r["createdName"])
                    if r.get("appliedDeptName"):
                        d["depts"].add(r["appliedDeptName"])
                    if r.get("createdAt"):
                        d["dates"].append(r["createdAt"])
                for d in types.values():
                    d["creators"] = sorted(d["creators"])
                    d["depts"] = sorted(d["depts"])
                    d["date_range"] = [min(d["dates"]), max(d["dates"])] if d["dates"] else []
                    d.pop("dates", None)
                return {t: d for t, d in sorted(types.items(), key=lambda kv: -kv[1]["count"])}

            types_2y, types_all = aggregate(rows_2y), aggregate(scope_rows)

            # 4) 尽力枚举 报销类别 下拉选项（系统全量；失败不阻塞，放最后防拖慢主链路）
            submit_opts = self.try_submittype_options()

            result = {
                "mode": "readonly_type_query", "dept_arg": self.args.dept,
                "filter_applied": how, "scope_note": scope_note,
                "cutoff_2y": cutoff,
                "rows_total": len(scope_rows), "rows_2y": len(rows_2y),
                "pages": pages, "page_text_total": total,
                "submittype_filter_options": submit_opts,
                "types_2y": types_2y,
                "types_all": types_all,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            io.open(p.run_dir / "types_result.json", "w", encoding="utf-8", newline="\n").write(
                json.dumps(result, ensure_ascii=False, indent=1))
            p.log_event(event="type_query_end", rows=len(scope_rows), rows_2y=len(rows_2y),
                        types_2y=len(types_2y), filter=how)
            p.say(f"完成：全量 {len(scope_rows)} 行 / 近2年 {len(rows_2y)} 行 → "
                  f"{len(types_2y)} 种报销类别（cutoff={cutoff}）；types_result.json 已落盘")
            for t, d in types_2y.items():
                p.say(f"  [近2年] {t}: {d['count']} 单  {d['date_range']}  "
                      f"例:{[mask(x, 4) for x in d['docs']]}")
            for t, d in types_all.items():
                if t not in types_2y:
                    p.say(f"  [仅历史] {t}: {d['count']} 单  {d['date_range']}")
            if submit_opts:
                p.say(f"报销类别下拉选项（系统全量 {len(submit_opts)} 项）: {submit_opts}")
            ok = True
            return 0
        finally:
            p.log_event(event="type_query_close", outcome="OK" if ok else "ERROR")
            p._close_browser()
            p.release_lock()

    def try_submittype_options(self):
        """尽力打开 报销类别 筛选下拉，枚举全量选项；任何失败返回 []（不阻塞主流程）。"""
        try:
            cont = self.page.locator("div.form-row.SubmitType").first
            if cont.count() == 0:
                return []
            cont.scroll_into_view_if_needed()
            for sel in ("div.form-row.SubmitType .ui-dropdown-trigger",
                        "div.form-row.SubmitType .ui-dropdown",
                        "div.form-row.SubmitType input",
                        "div.form-row.SubmitType"):
                loc = self.page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.click(timeout=3000)
                self.page.wait_for_timeout(1200)
                opts = self.page.evaluate(
                    "() => [...document.querySelectorAll('.ui-dropdown-items li, .ui-multiselect-items li, .ui-overlay li, .ui-autocomplete-items li')]"
                    ".map(li => (li.innerText||'').trim()).filter(Boolean).slice(0, 80)")
                opts = [o for o in dict.fromkeys(opts) if o not in ("查询", "重置", "确定", "取消")]
                if opts:
                    self.p.save("submittype_options.json", json.dumps(opts, ensure_ascii=False, indent=1))
                    self.p.shot(self.page, "submittype_options.png")
                    try:
                        self.page.keyboard.press("Escape")
                    except Exception:
                        pass
                    return opts
            return []
        except Exception as e:
            self.p.log_event(event="submittype_enum_fail", error=str(e)[:160])
            return []


def main(argv=None):
    ap = argparse.ArgumentParser(description="BPM 报销单类型盘点（只读）")
    ap.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S") + "-typequery")
    ap.add_argument("--dept", default="运动表现研究部", help="组织筛选值（制单人→回落申请部门）")
    ap.add_argument("--expect-name", default="陈晶")
    ap.add_argument("--login-wait", type=float, default=480.0)
    args = ap.parse_args(argv)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rc = TypeQuery(args).run()
    sys.exit(rc)


if __name__ == "__main__":
    main()
