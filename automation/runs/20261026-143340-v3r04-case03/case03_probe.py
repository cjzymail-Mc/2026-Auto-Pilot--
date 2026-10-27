# -*- coding: utf-8 -*-
"""V3-R04 CASE-03 阶段一（浏览器只读）：公出单模块发现、定向查询、逐单详情证据采集。

设计（bpm_template.live_template 同款受控只读模式）：
- 临时 context（chromium.launch + new_context + 内存注入 session_state），不触碰/不关闭
  其他执行者页面；profile 执行者锁；Chromium --no-proxy-server 直连。
- 全程零业务写入：不点保存/发送/流转/提交/上传/暂存/贴票/审批/返回（_click_guard 把关），
  本轮零关联选择、零占位语义；只做导航、查询、分页、查看详情。
- 证据：菜单结构、列表查询响应 JSON、分页逐页、每张单详情 URL/DOM/截图 + sha256；
  响应认证头只在内存使用，绝不落盘；凭证原值不入任何工件。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from stage1_browser_probe import Probe, HOST, PASS  # noqa: E402

RUN = Path(__file__).resolve().parent
EXPECT_NAME = "陈晶"
API_HOST = "oa.api.qiaodan.com"

MENU_JS = """() => {
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const t = (a.innerText || '').trim().replace(/\\s+/g, ' ');
    const href = a.getAttribute('href') || '';
    if (!t || !href || href.startsWith('javascript')) continue;
    const key = t + '|' + href;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({text: t, href: href});
  }
  return out.slice(0, 400);
}"""

LIST_ROWS_JS = """() => {
  const tables = [...document.querySelectorAll('table')];
  return tables.map(tb => ({
    headers: [...tb.querySelectorAll('thead th')].map(th => (th.innerText || '').trim()),
    rows: [...tb.querySelectorAll('tbody tr')].map(tr =>
      [...tr.querySelectorAll('td')].map(td => (td.innerText || '').trim()))
  }));
}"""

PAGINATOR_JS = """() => {
  const out = [];
  for (const p of document.querySelectorAll('p-paginator, .ui-paginator')) {
    out.push({
      text: (p.innerText || '').replace(/\\s+/g, ' ').trim(),
      buttons: [...p.querySelectorAll('button, a')].map(b => ({
        text: (b.innerText || '').trim(), cls: b.className,
        disabled: b.disabled || b.getAttribute('disabled') !== null}))
    });
  }
  return out;
}"""

BODY_TEXT_JS = "() => document.body ? document.body.innerText.slice(0, 60000) : ''"


class TripProbe(Probe):
    def _launch(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        browser = self._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
        self.ctx = browser.new_context(ignore_https_errors=True,
                                       viewport={"width": 1440, "height": 900})
        self._inject_session_state()
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(45000)
        self.page.on("dialog", lambda d: (d.dismiss(), self.log_event(event="dialog_dismissed", kind=d.type)))
        self._api_headers = {}
        self._detail_url_pattern = None

    def login_state(self, page):
        from bpm_ui import observed_operator
        state, marks, evidence = super().login_state(page)
        if state == "LOGGED_IN" and observed_operator(page) != self.args.expect_name:
            return "UNKNOWN", marks, evidence
        return state, marks, evidence

    # ---- 响应捕获（认证头只留内存）----
    def _arm_capture(self):
        self._captured = []
        def on_response(response):
            try:
                parsed = urlsplit(response.url)
                if parsed.scheme == "https" and parsed.netloc == API_HOST and response.status == 200:
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype:
                        body = response.text()
                        self._api_headers = {k: v for k, v in response.request.headers.items()
                                             if k.lower() not in ("cookie", "content-length", "host")}
                        self._captured.append({"url": response.url, "path": parsed.path,
                                               "method": response.request.method,
                                               "post_data": (response.request.post_data or "")[:2000],
                                               "body": body})
            except Exception:
                pass
        self.page.on("response", on_response)

    def _drain_capture(self, tag):
        out = []
        for cap in getattr(self, "_captured", []):
            name = f"api-{tag}-{len(out):03d}-{re.sub(r'[^A-Za-z0-9]', '-', cap['path'])[-60:]}.json"
            payload = {"request_path": cap["path"], "method": cap["method"],
                       "post_data": cap["post_data"], "body": json.loads(cap["body"])}
            self.save(name, json.dumps(payload, ensure_ascii=False, indent=1))
            out.append({"file": name, "path": cap["path"], "sha256": hashlib.sha256(
                json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()})
        self._captured = []
        return out

    def _hash_file(self, name):
        return hashlib.sha256((self.ev / name).read_bytes()).hexdigest()


def main() -> int:
    args = SimpleNamespace(run=RUN.name, doc_id=None, expect_name=EXPECT_NAME,
                           tech_budget=1800, login_wait=480, wall_cap=2400,
                           fill_plan=None, keep_open_minutes=0)
    p = TripProbe(args)
    p.acquire_lock()
    reason = "NEEDS_INPUT"
    manifest = {"run": RUN.name, "stage": "browser read-only", "evidence": []}
    try:
        p._preflight()
        p._launch()
        state = p.phase_entry()
        if state == "LOGIN_REQUIRED":
            state = p.wait_login()
        if state != PASS:
            reason = "WAIT_HUMAN_LOGIN"
            raise ValueError("trip module read requires verified login")
        p._save_session_state()
        p._arm_capture()

        # ---- A 菜单发现：找 公出单 入口 ----
        page = p.page
        menu = page.evaluate(MENU_JS)
        p.save("home-menu-links.json", json.dumps(menu, ensure_ascii=False, indent=1))
        p.shot(page, "home.png")
        trip_links = [m for m in menu if m["text"].replace(" ", "") == "公出单"]
        p.log_event(event="menu_scan", links=len(menu), trip_hits=len(trip_links),
                    trip_hrefs=[t["href"] for t in trip_links])
        if not trip_links:
            reason = "TRIP_MODULE_NOT_FOUND"
            raise ValueError("home menu has no 公出单 link; see home-menu-links.json")
        href = trip_links[0]["href"]
        trip_url = href if href.startswith("http") else HOST + (href if href.startswith("/") else "/" + href)
        manifest["trip_module_url"] = trip_url

        # ---- B 进入公出单模块列表 ----
        page.goto(trip_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        p.shot(page, "trip-list-entry.png")
        p.save("trip-list-entry.html", page.content())
        p.save("trip-list-entry-text.txt", page.evaluate(BODY_TEXT_JS))
        manifest["evidence"] += p._drain_capture("list-entry")

        # 列表结构盘点（表头/行/分页器/筛选控件）
        structure = {
            "url": page.url,
            "tables": page.evaluate(LIST_ROWS_JS),
            "paginators": page.evaluate(PAGINATOR_JS),
            "inputs": page.evaluate("""() => [...document.querySelectorAll('input, select, textarea')]
                .map(el => ({tag: el.tagName, type: el.type || '', placeholder: el.placeholder || '',
                             value: (el.value || '').slice(0, 60), name: el.name || '',
                             id: el.id || '', cls: (el.className || '').toString().slice(0, 80)}))
                .slice(0, 120)"""),
            "buttons": page.evaluate("""() => [...document.querySelectorAll('button')]
                .map(b => (b.innerText || '').trim()).filter(Boolean).slice(0, 60)"""),
        }
        p.save("trip-list-structure.json", json.dumps(structure, ensure_ascii=False, indent=1))
        p.log_event(event="trip_list_structure",
                    headers=[t.get("headers") for t in structure["tables"]],
                    rows_total=sum(len(t.get("rows", [])) for t in structure["tables"]),
                    buttons=structure["buttons"][:20])
        reason = "STRUCTURE_CAPTURED"
        p.result["case03_browser"] = manifest
        return 0
    finally:
        p.result["finish_reason"] = reason
        p.result["case03_browser"] = manifest
        p.atomic_result()
        p.log_event(event="case03_probe_end", status=reason,
                    evidence_count=len(manifest.get("evidence", [])))
        p._close_browser()
        p.release_lock()
        p.budget.close()
        (RUN / "browser-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
