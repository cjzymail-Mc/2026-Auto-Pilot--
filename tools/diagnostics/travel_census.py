#!/usr/bin/env python3
"""BPM 差旅费单据内容普查 v5（只读，不填不存；检查点优先）。

背景：类型盘点（list_type_query.py）显示列表维度同质（近2年 63 单全部 转账/同公司/
本部门），差异只能在单据内部 → 逐单拉明细做内容普查，为「一 skill + N 模板 vs
N skill」决策提供数据。

v5 三项纠正（用户 2026-10-23）：
  1. 凭证只留内存：xhr_tpl/authorization 值绝不落盘（redact_tpl 只记头名）。
  2. 验收收紧：主表 59 键是扁平头，行数据在 6 个子端点（details/costs/relations/
     banks/products/detailrels，前缀式 /reimburse/{ch}/{uuid}，140831 实证）——
     检查点与每单验收都要求 dict 解析 + 单号 + uuid 核对 + 子表内容非空；
     「主表-only」不再算普查成功。
  3. 首页缺口闭合：v4 曾把步骤 1 首页 harvest 采到即弃、ui_paginate 只采翻页新页
     → 恰丢 page-1 的 20 行（449/469）。v5 首页条目作种子 + 开跑前重点一次查询
     重发首页 xhr + 底册（469 行）对照 bizNumber 直查补采，逐单闭合 63 张清单。

关键情报（2026-10-23 三轮实证）：
  1. sync Playwright 事件 handler 内调 resp.text() 会阻塞再入抛异常 → handler 只存
     Response 对象，body 延后取。
  2. 列表接口是跨域纯 GET：https://oa.api.qiaodan.com/reimburse/query/{size}/{page}?for=1
     （UI 筛选后分页 GET 不带条件 → 条件在服务端会话里，同 cookie 直接 fetch 即可）
     → 探明后直接 fetch 全量，绕开 UI 翻页等待。
  3. API 的 submitType 是代码不是中文（08=差旅费），映射由 DOM 行 join 实证：
     08差旅费 11研发材料费 15快递费 02低值易耗品/办公用品 04福利费/劳保
     01其他费用 24维修费 06各项会议支出
  4. 详情 xhr 在【新标签页】里发 → response 监听必须挂到 context 所有页面
     （context.on("page")），只挂列表页必漏。
  5. fetch body 截断：469 条列表 ≈ 500KB+，旧 300KB cap 会把 JSON 截断致解析失败
     → cap 按用途传参（列表 4MB / 详情 300KB）。

v4 检查点优先（用户指令 2026-10-23）：先成功读取【一张】真实详情并核对单号+字段
结构落证据（checkpoint_detail_ok），门未过绝不批量；门过自动扩大批量采集全部目标。
采集策略：A. 7 个详情端点模式猜测（用已有 uuid）→ B. DOM 点行捕获真实详情 xhr →
C. xhr 不可用时 DOM 点行采样兜底。
红线不破：全程 GET/导航；不点任何 NO_SAVE_WORDS 按钮；原始值只落 evidence，控制台脱敏。
用法：python -X utf8 -m tools.diagnostics.travel_census [--limit 63] [--dom-sample 12] [--checkpoint-only]
工件：automation/runs/<run>/travel_census.json + attempt_001/evidence/
"""
import argparse
import io
import json
import re
import sys
import time
from urllib.parse import urlsplit

import bpm.browser_probe as pb
from bpm.browser_probe import HOST, LIST_PATH, assert_internal, mask
from tools.diagnostics.type_query import TypeQuery

CUTOFF = "2024-10-23"          # 与类型盘点同口径（近 2 年，制单日期）
SUBMITTYPE_MAP = {"08": "差旅费", "11": "研发材料费", "15": "快递费",
                  "02": "低值易耗品、办公用品采购", "04": "福利费、劳保用品",
                  "01": "其他费用", "24": "维修费", "06": "各项会议支出"}
DEFAULT_IDS_FROM = ("automation/runs/20261023-105801-travelcensus/"
                    "attempt_001/evidence/list_items_api.json")
DEFAULT_BASELINE = ("automation/runs/20261023-102118-typequery/"
                    "attempt_001/evidence/list_dept_all.json")

# v4 实证：页面内 fetch oa.api 全部 status=0 TypeError: Failed to fetch（CORS 拦截，
# 应用自身 XHR 头组合才被放行）→ 一律改走 context.request（共享 cookie jar，无 CORS）。
def uid_variants(uid):
    """uuid 形态变体：API 返回 32hex 无横线，请求路径可能是标准 dashed。"""
    u = str(uid or "")
    out = [u] if u else []
    if u and "-" not in u and len(u) == 32:
        out.append(f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:32]}")
    return out

VIEW_JS = """() => {
  const clean = s => (s||'').replace(/\\s+/g, ' ').trim().slice(0, 80);
  const tables = [];
  for (const t of document.querySelectorAll('table')) {
    const heads = [...t.querySelectorAll('thead th')].map(th => clean(th.innerText));
    const rows = [...t.querySelectorAll('tbody tr')]
      .map(tr => [...tr.children].map(td => clean(td.innerText))).filter(r => r.length);
    if (rows.length) tables.push({heads, rows: rows.slice(0, 40)});
  }
  const props = [...document.querySelectorAll('[class*="prop-"]')].slice(0, 120)
    .map(el => ({cls: (el.className || '').slice(0, 60), text: clean(el.innerText)}));
  return {url: location.href.slice(0, 140), title: document.title.slice(0, 40),
          has_paginator: !!document.querySelector('.ui-paginator'), tables, props};
}"""


class Census(TypeQuery):
    def __init__(self, args):
        super().__init__(args)
        self.caps = []          # [{resp, url, rt, ct, status, body(None 延后读)}]
        self.consumed = 0
        self.list_ep = None
        self._api_headers = None

    # ---- 网络捕获（handler 内绝不阻塞；挂到 context 所有页面，含新标签页） ----
    def _wire(self):
        def on_resp(resp):
            try:
                if resp.request.resource_type not in ("xhr", "fetch"):
                    return
                url = resp.url
                ct = (resp.headers or {}).get("content-type", "")
                if "json" not in ct and not any(q in url for q in ("/api", "reimburse", "/oa/")):
                    return
                self.caps.append({"resp": resp, "url": url, "rt": resp.request.resource_type,
                                  "ct": ct, "status": resp.status, "body": None})
            except Exception:
                pass

        def wire_page(pg):
            try:
                pg.on("response", on_resp)
            except Exception:
                pass
        for pg in self.page.context.pages:
            wire_page(pg)
        self.page.context.on("page", wire_page)

    @staticmethod
    def _items_from_body(body):
        try:
            j = json.loads(body)
        except Exception:
            return None
        arr = None
        if isinstance(j, list):
            arr = j
        elif isinstance(j, dict):
            for k in ("content", "data", "items", "rows", "list", "result", "records"):
                v = j.get(k)
                if isinstance(v, list):
                    arr = v
                    break
                if isinstance(v, dict):
                    for k2 in ("content", "items", "rows", "list", "records"):
                        if isinstance(v.get(k2), list):
                            arr = v[k2]
                            break
                    if arr:
                        break
        if not arr:
            return None
        return [o for o in arr if isinstance(o, dict) and
                any(k in o for k in ("submitType", "bizNumber", "bizStatus"))] or None

    def harvest(self):
        """消化未处理捕获（延后读 body），返回新单据对象数组；记录 list_ep。
        只认 reimburse/query URL 族——20261023-135739 实证：别的 API（流程引擎待办，
        bizType/flowXxx 形状，无 submitType）也会被 bizNumber 匹配误吸进来。"""
        out = []
        for c in self.caps[self.consumed:]:
            if "reimburse/query" not in c["url"]:
                continue
            if c["body"] is None:
                try:
                    c["body"] = c["resp"].text()[:800000]
                except Exception:
                    c["body"] = ""
            items = self._items_from_body(c["body"]) if c["body"] else None
            if items:
                out.extend(items)
                self.list_ep = c["url"]
        self.consumed = len(self.caps)
        return out

    def auth_headers(self):
        """从捕获的 reimburse/query 请求抄头（除 cookie）——context.request 只有 cookie
        会 401（20261023-135739 实证 /reimburse/{uuid} 与列表直拉均 401 空体）。
        只缓存不落日志值；事件里仅记头名。"""
        if getattr(self, "_api_headers", None) is not None:
            return self._api_headers
        for c in self.caps:
            if "reimburse/query" not in c["url"]:
                continue
            try:
                hdrs = {k: v for k, v in (c["resp"].request.headers or {}).items()
                        if k.lower() not in ("cookie", "content-length")}
            except Exception:
                hdrs = {}
            if hdrs:
                self._api_headers = hdrs
                self.p.log_event(event="api_headers_captured", names=sorted(hdrs.keys()))
                return hdrs
        return {}

    def api_get(self, url, headers=None, cap=300000):
        """GET via context.request（共享 cookie jar，无 CORS；默认带应用授权头）。"""
        hdrs = headers or self.auth_headers() or {"Accept": "application/json"}
        try:
            r = self.page.context.request.get(url, headers=hdrs, timeout=20000)
            return {"status": r.status, "ct": r.headers.get("content-type", ""),
                    "body": r.text()[:cap]}
        except Exception as e:
            return {"status": 0, "ct": "", "body": f"exc:{str(e)[:120]}"}

    def _scan_detail_xhr(self, t):
        """在未消化捕获里找详情端点：URL 含任一 id 变体/bizNumber 且 body 含单号。
        全部新捕获先落 captured_xhr 事件（诊断性）；命中返回
        {url, headers(去 cookie), token_form} 或 None。"""
        biz = str(t["bizNumber"])
        toks = uid_variants(t.get("id"))
        best = None
        for c in self.caps[self.consumed:]:
            if c["body"] is None:
                try:
                    c["body"] = c["resp"].text()[:800000]
                except Exception:
                    c["body"] = ""
            self.p.log_event(event="captured_xhr", url=c["url"][:150], status=c["status"])
            hit_tok = next((tok for tok in toks + [biz] if tok and tok in c["url"]), None)
            if hit_tok and biz in (c["body"] or ""):
                try:
                    hdrs = {k: v for k, v in (c["resp"].request.headers or {}).items()
                            if k.lower() != "cookie"}   # 红线：请求头绝不落 cookie
                except Exception:
                    hdrs = {}
                form = "dashed" if "-" in hit_tok else ("biz" if hit_tok == biz else "dashless")
                best = {"url": c["url"], "headers": hdrs, "token_form": form, "token": hit_tok}
        self.consumed = len(self.caps)
        return best

    def _tpl_of(self, url, t):
        """从 URL 反推 token 形态，构造批量模板（头用应用授权头）。"""
        hdrs = self.auth_headers() or {"Accept": "application/json"}
        biz = str(t["bizNumber"])
        for tok in uid_variants(t.get("id")):
            if tok and tok in url:
                return {"url": url, "headers": hdrs,
                        "token_form": "dashed" if "-" in tok else "dashless", "token": tok}
        if biz in url:
            return {"url": url, "headers": hdrs, "token_form": "biz", "token": biz}
        return None

    @staticmethod
    def _sub_token(tpl, t):
        """按 tpl 的 token 形态把探针单 token 替换成目标单 token。"""
        old, form = tpl.get("token") or "", tpl.get("token_form", "dashless")
        if not old:
            return tpl["url"]
        if form == "biz":
            new = str(t["bizNumber"])
        else:
            vs = uid_variants(t.get("id"))
            if not vs:
                new = str(t["bizNumber"])
            elif form == "dashed" and len(vs) > 1:
                new = vs[1]
            else:
                new = vs[0]
        return tpl["url"].replace(old, new)

    @staticmethod
    def _date(v):
        if v is None:
            return ""
        if isinstance(v, (int, float)):
            try:
                return time.strftime("%Y-%m-%d", time.localtime(v / 1000 if v > 1e11 else v))
            except Exception:
                return str(v)[:10]
        return str(v)[:10]

    @staticmethod
    def _zh(code):
        return SUBMITTYPE_MAP.get(str(code or ""), str(code or ""))

    # ---- 检查点：一张真实详情（单号核对 + 字段结构落证据） ----
    def load_probe_target(self):
        """复用已有 API 物件（含服务端 uuid）选最新一张 差旅费×近2年 作探针单。"""
        try:
            with io.open(self.args.ids_from, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception as e:
            self.p.log_event(event="probe_ids_unavailable", error=str(e)[:140],
                             path=self.args.ids_from)
            return None
        cands = [it for it in items if "差旅" in self._zh(it.get("submitType"))
                 and self._date(it.get("createdAt")) >= CUTOFF and it.get("bizNumber")]
        if not cands:
            return None
        cands.sort(key=lambda it: str(it.get("createdAt") or ""), reverse=True)
        it = cands[0]
        return {"id": str(it.get("id") or ""), "bizNumber": str(it.get("bizNumber")),
                "createdAt": self._date(it.get("createdAt")),
                "code": it.get("submitType"), "src": "ids_from"}

    def try_detail_candidates(self, t):
        """详情端点模式猜测（uuid 变体/bizNumber × 路径族；context.request 无 CORS 且
        自动带应用授权头）。成功返回 (url, rr, headers)。"""
        if not self.list_ep:
            return None
        sp = urlsplit(self.list_ep)
        root = f"{sp.scheme}://{sp.netloc}"
        base = self.list_ep.split("?")[0]
        for tok in uid_variants(t.get("id")) + ([str(t["bizNumber"])] if t.get("bizNumber") else []):
            for cand in (f"{root}/reimburse/{tok}", f"{root}/reimburse/detail/{tok}",
                         f"{root}/reimburse/get/{tok}", f"{root}/reimburse/view/{tok}",
                         f"{root}/reimburse/info/{tok}", f"{base}/{tok}",
                         f"{base}?id={tok}"):
                rr = self.api_get(cand)
                if rr.get("status") == 200 and (rr.get("body") or "")[:1] in "{[" \
                        and str(t["bizNumber"]) in rr["body"]:
                    return cand, rr, (self.auth_headers() or {"Accept": "application/json"})
                self.p.log_event(event="detail_candidate_reject", url=cand[:130],
                                 status=rr.get("status"), head=(rr.get("body") or "")[:50])
        return None

    def checkpoint_dom(self, t):
        """当前筛选列表页点行开单据（新标签页优先），提取视图 + 捕获真实详情 xhr。
        返回 (view_or_None, tpl_or_None)。"""
        p = self.p
        r = self.rows() or {"rows": []}
        row_idx = next((i for i, row in enumerate(r["rows"])
                        if row.get("bizNumber") == t["bizNumber"]), None)
        if row_idx is None:
            p.log_event(event="checkpoint_dom_skip", why="row_not_on_page1",
                        biz=mask(t["bizNumber"], 4))
            return None, None
        pages_before = len(self.page.context.pages)
        row_loc = self.page.locator("tbody tr:has(td)").nth(row_idx)
        row_loc.click(timeout=5000)
        self.page.wait_for_timeout(2000)
        if len(self.page.context.pages) == pages_before and "/oa/reimburses" in self.page.url:
            # 单击只选中未开单（20261023-135739 实证 3s 后仍是列表页）→ 双击递进
            row_loc.dblclick(timeout=5000)
            self.page.wait_for_timeout(2500)
        newp = self.page.context.pages[pages_before:]
        if newp:                            # 新标签页：列表状态未动
            vp = newp[-1]
            vp.wait_for_load_state("domcontentloaded", timeout=20000)
            vp.wait_for_timeout(1500)
            p.log_event(event="detail_route", where="new_tab", url=vp.url[:150])
            view = vp.evaluate(VIEW_JS)
            p.save("checkpoint_detail_view.html", vp.content())
            p.shot(vp, "checkpoint_detail_view.png")
            tpl = self._scan_detail_xhr(t)
            vp.close()
        else:                               # 同页跳转
            p.log_event(event="detail_route", where="same_page", url=self.page.url[:150])
            view = self.page.evaluate(VIEW_JS)
            p.save("checkpoint_detail_view.html", self.page.content())
            p.shot(self.page, "checkpoint_detail_view.png")
            tpl = self._scan_detail_xhr(t)
            try:                            # 回列表（sync API 是 go_back；失败则重导航）
                self.page.go_back(wait_until="domcontentloaded", timeout=15000)
                self.wait_table()
            except Exception:
                p.log_event(event="go_back_fallback", url=self.page.url[:100])
                self.page.goto(assert_internal(HOST + LIST_PATH),
                               wait_until="domcontentloaded", timeout=45000)
                self.wait_table()
                self.org_select("CreatedPath", self.args.dept)
                self.query_click()
                self.page.wait_for_timeout(1500)
        return view, tpl

    @staticmethod
    def summarize_body(body, biz):
        """解析详情 JSON → 结构摘要（顶层键 + 明细数组定位 + 单号核对）。"""
        out = {"bizNumber_found": str(biz) in (body or "")}

        def sh(v, d=0):
            if isinstance(v, dict):
                if d >= 4:
                    return f"dict({len(v)})"
                return {str(k): sh(x, d + 1) for k, x in list(v.items())[:60]}
            if isinstance(v, list):
                if d >= 4:
                    return f"list({len(v)})"
                return {"list_len": len(v), "row0": sh(v[0], d + 1) if v else None}
            return type(v).__name__

        def walk(v, path, acc):
            if isinstance(v, list) and v and isinstance(v[0], dict):
                acc.append({"path": path, "len": len(v),
                            "row_keys": sorted(str(k) for k in v[0].keys())[:40]})
            elif isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{path}.{k}", acc)

        try:
            j = json.loads(body)
            arrays = []
            walk(j, "$", arrays)
            out.update({"shape": sh(j), "detail_arrays": arrays[:10]})
        except Exception as e:
            out.update({"parse": f"fail:{str(e)[:60]}", "head": (body or "")[:200]})
        return out

    # ---- 全量列表直拉 ----
    def fetch_api_all(self, expect_total):
        """直接 fetch 列表全量：大 pageSize 一把拉 → 分页兜底/续拉。失败返回 []。"""
        if not self.list_ep:
            return []
        sp = urlsplit(self.list_ep)
        root = f"{sp.scheme}://{sp.netloc}"
        q = ("?" + sp.query) if sp.query else ""
        by_key = {}

        def merge(items):
            for it in items:
                k = str(it.get("id") or it.get("bizNumber") or "")
                if k:
                    by_key[k] = it

        for size in (1000, 500, 200):        # 大页优先：一次拿全
            rr = self.api_get(f"{root}/reimburse/query/{size}/1{q}", cap=4000000)
            items = self._items_from_body(rr.get("body") or "") if rr.get("status") == 200 else None
            if items:
                merge(items)
                self.p.log_event(event="api_bulk_fetch", size=size, got=len(by_key))
                if len(by_key) >= min(expect_total or 10**9, 100) or size == 200:
                    break
        if len(by_key) < (expect_total or 0) - 10:      # 空或不足 → 分页续拉
            for pg in range(1, 60):
                rr = self.api_get(f"{root}/reimburse/query/20/{pg}{q}", cap=4000000)
                items = self._items_from_body(rr.get("body") or "") if rr.get("status") == 200 else None
                if not items:
                    break
                n0 = len(by_key)
                merge(items)
                if len(by_key) == n0:
                    break
                self.page.wait_for_timeout(200)
            self.p.log_event(event="api_paged_fetch", got=len(by_key))
        return list(by_key.values())

    # ---- 子端点：详情弹窗实测 xhr 全家福（20261023-140831 前缀式，非 /reimburse/{id}/xxx）----
    CHILDREN = ("details", "costs", "relations", "banks", "products", "detailrels")

    @staticmethod
    def redact_tpl(tpl):
        """tpl 落盘版：头只留名字——authorization 值绝不进任何工件（红线 2，
        2026-10-23 用户纠正：v4 曾把整个 xhr_tpl 写进 children_probe.json）。"""
        if not tpl:
            return None
        return {"url": tpl.get("url"), "token_form": tpl.get("token_form"),
                "header_names": sorted((tpl.get("headers") or {}).keys())}

    def _children_content(self, kids):
        """子表内容行数：仅计 200 且可解析为行数组者 → {端点: 行数}。
        内容判据（用户纠正 2）：主表 59 键是扁平头，行数据全在子端点——
        行数为空 = 只采到表头，不算普查成功。"""
        out = {}
        for ch, v in (kids or {}).items():
            if not (isinstance(v, dict) and v.get("status") == 200):
                continue
            try:
                j = json.loads(v.get("body") or "")
            except Exception:
                continue
            rows = None
            if isinstance(j, list):
                rows = j
            elif isinstance(j, dict):
                for k in (ch, "content", "data", "items", "rows", "list",
                          "result", "records"):
                    if isinstance(j.get(k), list):
                        rows = j[k]
                        break
            if rows is not None:
                out[ch] = len(rows)
        return out

    def api_root(self):
        if not self.list_ep:
            return None
        sp = urlsplit(self.list_ep)
        return f"{sp.scheme}://{sp.netloc}"

    def fetch_children(self, uid):
        """采 6 子表（明细行/费用/关联单/收款行/产品/明细关联），全部 GET 只读。"""
        root = self.api_root()
        out = {}
        if not root or not uid:
            return out
        for ch in self.CHILDREN:
            rr = self.api_get(f"{root}/reimburse/{ch}/{uid}")
            out[ch] = {"status": rr.get("status"),
                       "body": rr.get("body") if rr.get("status") == 200
                       else (rr.get("body") or "")[:80]}
            self.page.wait_for_timeout(150)
        return out

    def children_probe(self, t):
        """双击开真弹窗记录 xhr（captured_xhr 事件）+ 前缀式子端点核验，结果落盘。"""
        p = self.p
        p.say("children 探测：双击开弹窗记录真实 xhr …")
        view, xhr_tpl = self.checkpoint_dom(t)
        p.log_event(event="children_view", ok=view is not None,
                    title=(view or {}).get("title", ""),
                    tables=len((view or {}).get("tables", [])))
        kids = self.fetch_children(t.get("id"))
        p.log_event(event="children_status",
                    status={k: v.get("status") for k, v in kids.items()},
                    rows=self._children_content(kids))
        p.save("children_probe.json", json.dumps(
            {"view_title": (view or {}).get("title"),
             "tables": (view or {}).get("tables"), "props": (view or {}).get("props"),
             "children_status": {k: v.get("status") for k, v in kids.items()},
             "children_rows": self._children_content(kids),
             "children": kids, "xhr_tpl": self.redact_tpl(xhr_tpl)},
            ensure_ascii=False, indent=1))
        p.say("children 探测完成：详见 children_probe.json 与 events captured_xhr")

    # ---- 主流程 ----
    def run(self):
        p = self.p
        p.acquire_lock()
        ok = False
        try:
            p._launch()
            self.page = p.page
            self._wire()
            p.log_event(event="travel_census_start", cutoff=CUTOFF, limit=self.args.limit,
                        v="4-checkpoint-first")
            st = p.phase_entry()
            if st == "LOGIN_REQUIRED":
                p.say("登录态过期——需要企微扫码（约 21s 人工）")
                st = p.wait_login()
            if st != pb.PASS:
                p.say(f"登录未成立（{st}），终止")
                return 2
            p._save_session_state()

            # 1) 列表 + 组织筛选（探明 list_ep 与服务端筛选会话；检查点 DOM 也靠它）
            self.page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded",
                           timeout=45000)
            self.wait_table()
            self.org_select("CreatedPath", self.args.dept)
            self.query_click()
            page1 = []                        # 首页条目必须留住——v4 缺口根因：此处曾
            for _ in range(8):                # 采到即弃，ui_paginate 只采翻页后新页 → 恰丢 page-1 的 20 行
                self.page.wait_for_timeout(1200)
                page1.extend(self.harvest())
                if page1:
                    break
            r = self.rows() or {}
            m = re.search(r"共\s*(\d+)\s*条", r.get("page_text") or "") or \
                re.search(r"(\d+)\s*条", r.get("page_text") or "")
            expect_total = int(m.group(1)) if m else 0
            p.log_event(event="list_ep_found", url=(self.list_ep or "")[:140],
                        expect_total=expect_total)

            if self.args.children_probe:                # 子端点发现模式（不批量）
                probe0 = self.load_probe_target()
                if not probe0:
                    p.say("children 探测失败：无探针单")
                    return 3
                self.children_probe(probe0)
                ok = True
                return 0

            # 2) ★检查点：一张真实详情成功（单号核对 + 字段结构落证据），门未过不批量
            probe = self.load_probe_target()
            if not probe:                     # 无 ids_from → 从当前页 1 挑最新 差旅 行
                row = next((x for x in (r.get("rows") or [])
                            if "差旅" in (x.get("submitType") or "")), None)
                if row:
                    probe = {"id": "", "bizNumber": str(row.get("bizNumber")),
                             "createdAt": row.get("createdAt") or "", "code": "08",
                             "src": "page1_dom"}
            if not probe:
                p.say("检查点失败：无可用探针单（ids_from 与页面均无 差旅费×近2年）→ 终止")
                return 3
            p.say(f"检查点探针单 {mask(probe['bizNumber'], 4)}（{probe['createdAt']}，"
                  f"来源 {probe['src']}）")

            mode, tpl, doc0 = "none", None, None
            hit = self.try_detail_candidates(probe)     # A. 端点模式猜测
            if hit:
                cand, rr, hdrs = hit
                tpl = self._tpl_of(cand, probe) or {"url": cand, "headers": hdrs,
                                                    "token_form": "biz", "token": ""}
                mode = "api"
                doc0 = {"bizNumber": probe["bizNumber"], "createdAt": probe["createdAt"],
                        "fetch": rr}
                p.save("checkpoint_detail.json", json.dumps(doc0, ensure_ascii=False, indent=1))
            else:                                        # B. DOM 点行捕获真实 xhr
                view, xhr_tpl = self.checkpoint_dom(probe)
                # 验收收紧：单号命中【且】真在详情页（无分页器 + title=报销单）——
                # 20261023-135739 实证列表页本身含单号会 false positive
                view_ok = (view is not None
                           and probe["bizNumber"] in json.dumps(view, ensure_ascii=False)
                           and not view.get("has_paginator")
                           and "报销单" in (view.get("title") or ""))
                if view_ok:
                    p.save("checkpoint_detail_view.json",
                           json.dumps(view, ensure_ascii=False, indent=1))
                    if xhr_tpl:                         # 捕获到真实详情端点 → 回取 JSON 核验
                        rr2 = self.api_get(xhr_tpl["url"], headers=xhr_tpl.get("headers"))
                        if rr2.get("status") == 200 and probe["bizNumber"] in (rr2.get("body") or ""):
                            mode, tpl = "domxhr", xhr_tpl
                            doc0 = {"bizNumber": probe["bizNumber"],
                                    "createdAt": probe["createdAt"], "view": view, "fetch": rr2}
                        else:
                            p.log_event(event="domxhr_refetch_fail", status=rr2.get("status"),
                                        url=xhr_tpl["url"][:120])
                            mode = "domview"
                            doc0 = {"bizNumber": probe["bizNumber"],
                                    "createdAt": probe["createdAt"], "view": view}
                    else:
                        mode = "domview"
                        doc0 = {"bizNumber": probe["bizNumber"],
                                "createdAt": probe["createdAt"], "view": view}
                    p.save("checkpoint_detail.json",
                           json.dumps(doc0, ensure_ascii=False, indent=1))
                else:
                    p.log_event(event="checkpoint_dom_fail", view_ok=view_ok,
                                title=(view or {}).get("title", ""),
                                has_paginator=(view or {}).get("has_paginator"),
                                biz=mask(probe["bizNumber"], 4))
            if doc0 is None:
                p.say("检查点失败：端点猜测与 DOM 点行均未取得可核验详情 → 终止（不批量）")
                p.log_event(event="checkpoint_detail_FAIL")
                return 3
            shape = (self.summarize_body(doc0.get("fetch", {}).get("body", ""), probe["bizNumber"])
                     if mode in ("api", "domxhr") else
                     {"view_tables": len(doc0["view"].get("tables", [])),
                      "view_props": len(doc0["view"].get("props", [])),
                      "bizNumber_found": True})
            # 检查点内容门槛（用户纠正 2）：主表 JSON 可核验还不够——
            # 主表是 59 个扁平键，行数据全在 6 个子端点；子表无内容 = 只采到表头，不批量
            children_rows = {}
            if mode in ("api", "domxhr"):
                doc0["children"] = self.fetch_children(probe.get("id"))
                children_rows = self._children_content(doc0["children"])
                p.log_event(event="checkpoint_children", rows=children_rows,
                            status={k: v.get("status") for k, v in doc0["children"].items()})
                if not children_rows:
                    p.say("检查点失败：主表可核验但 6 子表无一采到内容（仅表头）→ 不批量")
                    p.log_event(event="checkpoint_detail_FAIL", why="children_empty",
                                children_status={k: v.get("status")
                                                 for k, v in doc0["children"].items()})
                    return 3
                p.save("checkpoint_detail.json", json.dumps(doc0, ensure_ascii=False, indent=1))
            elif mode == "domview" and not doc0["view"].get("tables"):
                p.say("检查点失败：视图无表格内容 → 不批量")
                p.log_event(event="checkpoint_detail_FAIL", why="view_no_tables")
                return 3
            p.save("checkpoint_detail_shape.json", json.dumps(shape, ensure_ascii=False, indent=1))
            p.log_event(event="checkpoint_detail_ok", mode=mode,
                        biz=mask(probe["bizNumber"], 4),
                        tpl=((tpl or {}).get("url") or "")[:130],
                        arrays=len(shape.get("detail_arrays") or []),
                        biz_check=shape.get("bizNumber_found"),
                        children=children_rows)
            p.say(f"★检查点通过（{mode}）：单号核对 "
                  f"{'√' if shape.get('bizNumber_found') else '×'}；"
                  f"字段结构已落 checkpoint_detail_shape.json")
            if self.args.checkpoint_only:
                p.say("--checkpoint-only：检查点即停，未批量")
                ok = True
                return 0

            # 3) 全量列表（API 直拉优先，UI 翻页兜底——首页种子传入）
            all_items = self.fetch_api_all(expect_total)
            if expect_total and len(all_items) < expect_total - 10:
                p.say(f"API 直拉 {len(all_items)} < 预期 {expect_total} → UI 翻页兜底")
                all_items = self.ui_paginate(page1)
            p.save("list_items_api.json", json.dumps(all_items, ensure_ascii=False, indent=1))
            p.say(f"列表全量 {len(all_items)} 单（预期 {expect_total}）")

            # 4) 目标：差旅费 × 近2年（submitType 代码 → 中文映射）
            targets = []
            for it in all_items:
                if "差旅" not in self._zh(it.get("submitType")):
                    continue
                d = self._date(it.get("createdAt"))
                if d >= CUTOFF:
                    targets.append({"id": str(it.get("id") or it.get("bizNumber")),
                                    "bizNumber": it.get("bizNumber"),
                                    "createdAt": d, "code": it.get("submitType")})
            targets = targets[: self.args.limit]
            p.say(f"→ 差旅费×近2年 {len(targets)} 单（限 {self.args.limit}）")

            # 5) 批量详情（仅在检查点通过后）：主表 + 6 子表/单
            docs = [doc0]                     # 检查点单计入成果，批量时按单号去重
            got_bizs = {doc0["bizNumber"]}
            want = set()                      # 底册应采集合（差旅×近2y），5b/6 步共用
            if mode in ("api", "domxhr") and tpl and targets:
                p.log_event(event="detail_batch_start", mode=mode, n=len(targets),
                            url=tpl["url"][:120])
                for i, t in enumerate(targets, 1):
                    d = next((x for x in docs if x.get("bizNumber") == t.get("bizNumber")), None)
                    if d is None:
                        rr = self.api_get(self._sub_token(tpl, t), headers=tpl.get("headers"))
                        j = None
                        try:
                            j = json.loads(rr.get("body") or "")
                        except Exception:
                            pass
                        tid = str(t.get("id") or "")
                        # 验收（用户纠正 2）：200 + dict 解析 + 单号命中 + uuid 交叉核对
                        #（t.id 可能是 bizNumber 兜底值，此时跳过 uuid 核对）
                        id_match = (not tid or tid == str(t.get("bizNumber"))
                                    or str((j or {}).get("id") or "").replace("-", "")
                                    == tid.replace("-", ""))
                        if (rr.get("status") == 200 and isinstance(j, dict)
                                and str(t["bizNumber"]) in rr["body"] and id_match):
                            d = {**t, "fetch": rr}
                            docs.append(d)
                            got_bizs.add(t["bizNumber"])
                        else:
                            p.log_event(event="detail_fetch_rejected", id=t["id"],
                                        status=rr.get("status"),
                                        why="parse" if not isinstance(j, dict)
                                        else ("id" if not id_match else "biz"))
                    if d is not None and "children" not in d:
                        d["children"] = self.fetch_children(t["id"])
                    self.page.wait_for_timeout(200)
                    if i % 10 == 0 or i == len(targets):
                        p.say(f"API 普查 {i}/{len(targets)}（已采 {len(docs)}）")

                # 5b) 缺口补采：对照底册（469 行 DOM 盘点）找漏采的 差旅×2y，
                #     先试 /reimburse/{bizNumber} 直查（无 uuid 时的唯一 API 路）
                if self.args.baseline:
                    try:
                        with io.open(self.args.baseline, "r", encoding="utf-8") as f:
                            base_rows = json.load(f)
                        want = {str(r["bizNumber"]) for r in base_rows
                                if "差旅" in (r.get("submitType") or "")
                                and (r.get("createdAt") or "") >= CUTOFF}
                    except Exception as e:
                        want, base_rows = set(), None
                        p.log_event(event="baseline_load_fail", error=str(e)[:120])
                    missing = sorted(want - got_bizs)
                    if missing:
                        p.say(f"底册对照：缺 {len(missing)} 单 → bizNumber 直查补采")
                        root = self.api_root()
                        for biz in missing:
                            rr = self.api_get(f"{root}/reimburse/{biz}")
                            jb = None
                            try:
                                jb = json.loads(rr.get("body") or "")
                            except Exception:
                                pass
                            if (rr.get("status") == 200 and isinstance(jb, dict)
                                    and biz in rr["body"]):
                                uid = str(jb.get("id") or "").replace("-", "")
                                d = {"id": uid, "bizNumber": biz, "createdAt": "",
                                     "code": "08", "fetch": rr, "topup": "bizNumber"}
                                d["children"] = self.fetch_children(uid)
                                docs.append(d)
                                got_bizs.add(biz)
                            else:
                                p.log_event(event="topup_miss", biz=mask(biz, 4),
                                            status=rr.get("status"))
                            self.page.wait_for_timeout(200)
            elif targets:
                p.say("详情 API 不可用 → DOM 点行采样（--dom-sample 控制）")
                for i, t in enumerate(targets[: self.args.dom_sample], 1):
                    if t["bizNumber"] in got_bizs:
                        continue
                    view = self.open_doc_by_row(t)
                    if view:
                        docs.append({**t, "view": view})
                        got_bizs.add(t["bizNumber"])
                    if i % 5 == 0 or i == min(len(targets), self.args.dom_sample):
                        p.say(f"DOM 普查 {i}/{min(len(targets), self.args.dom_sample)}")

            # 6) 落盘 + 摘要（控制台脱敏；「已采」与「含子表内容」分开报——
            #    用户纠正 2：主表-only 不算内容普查完成）
            for d in docs:
                if "children" in d and "children_rows" not in d:
                    d["children_rows"] = self._children_content(d["children"])
            validated = sum(1 for d in docs if d.get("children_rows"))
            want_total = 0
            if self.args.baseline:
                want_total = len(want) if want else 0
            result = {"mode": mode, "cutoff": CUTOFF, "dept": self.args.dept,
                      "submittype_map": SUBMITTYPE_MAP,
                      "checkpoint": {"bizNumber": probe["bizNumber"], "src": probe["src"],
                                     "tpl_url": (tpl or {}).get("url"),
                                     "token_form": (tpl or {}).get("token_form"),
                                     "shape": shape,
                                     "children": children_rows},
                      "api_items": len(all_items), "expect_total": expect_total,
                      "ui_seed": len(page1),
                      "targets": len(targets), "baseline_want": want_total,
                      "docs": docs, "validated": validated, "list_ep": self.list_ep,
                      "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            io.open(p.run_dir / "travel_census.json", "w", encoding="utf-8",
                    newline="\n").write(json.dumps(result, ensure_ascii=False, indent=1))
            p.log_event(event="travel_census_end", mode=mode, docs=len(docs),
                        validated=validated, targets=len(targets),
                        baseline_want=want_total)
            p.say(f"完成：主表已采 {len(docs)} 单（底册目标 {max(want_total, len(targets))}），"
                  f"其中【含子表内容】{validated} 单（模式 {mode}）；travel_census.json 落盘；"
                  f"例单号 {mask(str(docs[0]['bizNumber']), 4) if docs else '-'}")
            ok = True
            return 0
        finally:
            p.log_event(event="travel_census_close", outcome="OK" if ok else "ERROR")
            p._close_browser()
            p.release_lock()

    # ---- 兜底 1：UI 翻页（API 直拉失败时） ----
    def ui_paginate(self, seed=None):
        """v5 修复首页缺口（用户纠正 3）：①种子合并步骤 1 采到的首页条目；
        ②开跑前重点一次「查询」重发首页 xhr——v4 实证 census_page page=1
        api_items=0、总量恰少 20 行（= 整个首页）；③连停 3 页才断（原 2 页）。"""
        by_key, page_no, stalls = {}, 1, 0
        for it in (seed or []):
            k = str(it.get("id") or it.get("bizNumber") or "")
            if k:
                by_key[k] = it
        n0 = len(by_key)
        try:
            self.query_click()               # 重发首页查询，补回被吞的 page-1
            for _ in range(10):
                self.page.wait_for_timeout(1000)
                for it in self.harvest():
                    k = str(it.get("id") or it.get("bizNumber") or "")
                    if k:
                        by_key[k] = it
                if len(by_key) > n0:
                    break
            self.p.log_event(event="ui_seed_refire", seed=len(seed or []),
                             after=len(by_key))
        except Exception as e:
            self.p.log_event(event="ui_seed_refire_fail", error=str(e)[:100])
        while True:
            self.page.wait_for_timeout(2000)
            for it in self.harvest():
                k = str(it.get("id") or it.get("bizNumber") or "")
                if k:
                    by_key[k] = it
            r = self.rows() or {}
            n0 = len(by_key)
            self.p.log_event(event="census_page", page=page_no, api_items=n0,
                             page_text=(r.get("page_text") or "")[:60])
            if r.get("next_disabled") is not False or page_no >= 60:
                break
            self.page.locator("a.ui-paginator-next").first.click()
            page_no += 1
            for _ in range(10):               # 轮询等新页响应
                self.page.wait_for_timeout(1000)
                for it in self.harvest():
                    k = str(it.get("id") or it.get("bizNumber") or "")
                    if k:
                        by_key[k] = it
                if len(by_key) > n0:
                    break
            stalls = stalls + 1 if len(by_key) == n0 else 0
            if stalls >= 3:
                self.p.say(f"连续 3 页无新数据，停止 UI 翻页（已 {len(by_key)} 单）")
                break
        return list(by_key.values())

    # ---- 兜底 2：DOM 点行打开单据视图（重导航版，批量采样用） ----
    def open_doc_by_row(self, t):
        p = self.p
        try:
            self.page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded",
                           timeout=45000)
            self.wait_table()
            self.org_select("CreatedPath", self.args.dept)
            self.query_click()
            self.page.wait_for_timeout(2500)
            r = self.rows() or {"rows": []}
            row_idx = next((i for i, row in enumerate(r["rows"])
                            if row.get("bizNumber") == t["bizNumber"]), None)
            if row_idx is None:
                p.log_event(event="dom_nav_fail", stage="row_not_found", id=t["id"])
                return None
            pages_before = len(self.page.context.pages)
            self.page.locator("tbody tr:has(td)").nth(row_idx).click(timeout=5000)
            self.page.wait_for_timeout(3000)
            newp = self.page.context.pages[pages_before:]
            if newp:                            # 新标签页：列表状态未动
                vp = newp[-1]
                vp.wait_for_load_state("domcontentloaded", timeout=20000)
                vp.wait_for_timeout(1500)
                view = vp.evaluate(VIEW_JS)
                p.save("detail_sample.html", vp.content())
                vp.close()
            else:                               # 同页跳转
                view = self.page.evaluate(VIEW_JS)
                p.save("detail_sample.html", self.page.content())
                try:
                    self.page.go_back(wait_until="domcontentloaded", timeout=15000)
                    self.wait_table()
                except Exception:
                    p.log_event(event="go_back_fallback", url=self.page.url[:100])
            return view
        except Exception as e:
            p.log_event(event="detail_dom_fail", id=t.get("id"), error=str(e)[:140])
            return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="BPM 差旅费单据内容普查（只读，检查点优先）")
    ap.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S") + "-travelcensus")
    ap.add_argument("--dept", default="运动表现研究部")
    ap.add_argument("--expect-name", default="陈晶")
    ap.add_argument("--login-wait", type=float, default=480.0)
    ap.add_argument("--limit", type=int, default=63, help="最多普查单数")
    ap.add_argument("--dom-sample", type=int, default=12, help="DOM 兜底采样单数")
    ap.add_argument("--ids-from", default=DEFAULT_IDS_FROM,
                    help="已有 API 列表物件（含服务端 uuid），检查点探针单来源")
    ap.add_argument("--baseline", default=DEFAULT_BASELINE,
                    help="469 行 DOM 底册（中文类型+制单日期）：63 张差旅清单的对照与补采依据")
    ap.add_argument("--checkpoint-only", action="store_true",
                    help="检查点（一张详情）通过即停，不批量")
    ap.add_argument("--children-probe", action="store_true",
                    help="子端点发现：双击真弹窗记录 xhr + GET 模式枚举，不批量")
    args = ap.parse_args(argv)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(Census(args).run())


if __name__ == "__main__":
    main()
