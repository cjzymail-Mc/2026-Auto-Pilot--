# -*- coding: utf-8 -*-
"""stage1_browser_probe v2 —— 受控浏览器只读验证探针（temp.md P1/P2）

相对 v1（2026-10-21 上午 run，错误结论见 corrections.md）的修复，逐条对应 temp.md §3 表格：
 1. run 目录写死旧值 → --run 参数/自动生成；每次尝试独立 attempt_NNN/ 子目录；结果文件原子写（tmp+os.replace）
 2. phase() 捕获异常后继续 → 阶段显式状态机（PASS/BLOCKED/FAIL/NOT_AUTHORIZED/NOT_RUN），
    依赖阶段失败后续跳过；整体成功由业务断言计算，不由"没抛异常"计算
 3. classify() 用导航关键词数量认定登录 → 域名+登录退出态+账户/组织标识三证；身份未确认=UNKNOWN
 4. locate() 不确认目标 → --doc-id 显式目标；候选 0/多 → 停止，绝不进入另一张单据
 5. structure() 的 type=new 自动回退 → 已删除；只检查已确认的现有目标（corrections.md #9 同步处置 WRITE_BTN：删除）
 6. recover() 只 reload → 刷新前后比对 单据ID/账户/状态/关键值；另做浏览器重启后登录态验证
 7. WALL_CAP/budget 只打印 → 单调时钟预算强制 + 墙钟看护线程（超时强停并落盘）；结束前确认浏览器已退出
 8. 结构扫描只数控件 → 枚举全部 frame，按区块读表格行/列/编辑器与代表性字段的实际显示值

持续约束（temp.md §3 末）：
- 只读：仅导航（goto 同源 a[href] / 点击已定位行的单据链接）；无 fill/type/press/set_input_files；
  对话框一律 dismiss（绝不 accept——accept 可能确认写入）
- 填写任务（--fill-plan）单独授权，只作用于 新建报销单 页：按 fill_plan 值写入并逐格回读；
  保存/发送/流转/提交/上传/暂存/贴票/终止/返回/审批 一律不点击（NO_SAVE_WORDS + _click_guard 守卫）
- 登录态持久化：新扫码后的本地复用上限 30 天（旧 60 天记录收紧到 min(原窗口, 扫码+30 天)），
  已知 refresh token 更早到期时取更早期限；
  旧无扫码元数据状态仍限 24h。登录确认后导出 storage_state 至 profile 受限目录，
  cookie 值只落该文件，日志/证据只记条数；本地窗口从扫码时间固定计时；
  服务端会话过期不受探针控制——注入后仍被要求登录时回落扫码等待，不静默伪造登录态
- 表面自适应：SpreadJS（GC 存在）走单元格 API 路径；否则按 Angular PrimeNG DOM 处理
  （p-table 列头 prop-* / p-dropdown / p-multiselect 浮层点击选择；attempt_006 实证本表单属此类）
- 同一 profile 同时只允许一个执行者（profile 目录锁文件）
- --no-proxy-server 保留；不改系统代理
- cookie/storage 只记名不记值；URL 中 token/ticket/code 类参数脱敏后再落盘
- 登录等待 / 技术执行 / 任务墙钟三钟分开计时；登录等待不计技术预算
- 二维码会过期：等待循环内检测过期标志并刷新登录页（独立浏览器内，与企微客户端页签无关）

用法:
  python -X utf8 stage1_browser_probe.py --run <run_id> --expect-name <操作账号姓名> [--doc-id <单据编号>]
  python -X utf8 stage1_browser_probe.py --run <run_id> --expect-name <姓名> --fill-plan <fill_plan.json>
      （授权填写任务：新建报销单按模板值填写并逐格回读；只填不存，保存/发送等留给用户；不走只读链）
  python -X utf8 stage1_browser_probe.py --run <run_id> --expect-name <操作账号姓名> --interactive-pick
      （无目标编号时：先盘点列表 → 人机接力拍板 → 同会话续跑，避免重复扫码）
  python -X utf8 stage1_browser_probe.py --run <run_id>            # 无目标：只做入口+列表范围盘点后停在 TARGET_UNSPECIFIED
离线自测（不起浏览器）: python -X utf8 stage1_probe_selftest.py
"""
import argparse
import contextlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from bpm.paths import ROOT as BASE
HOST = "https://bpm.qiaodan.com"
LIST_PATH = "/oa/reimburses"          # 复数，IA2 document 一手证实（corrections.md #11）
# 仅 --fill-plan 授权路径（phase_fill）使用的页面；字面量全文件只此一处（selftest T7 静态守卫）
NEW_FORM_PATH = "/oa/reimburse?type=new"
# 填写任务禁点词：任何文本类点击前经 _click_guard 校验；只填不存，落库/离开/审批动作全归用户
NO_SAVE_WORDS = ("保存", "发送", "流转", "提交", "上传", "暂存", "贴票", "终止", "返回",
                 "审批", "同意", "驳回", "导入", "商旅", "发票识别")
PROFILE = BASE / "automation" / ".pw-profile"
# 登录态仅落 profile；新扫码后最多复用 30 天，起点不随文件写回续期。
# 旧 60 天记录生效窗口收紧到 min(原窗口, 扫码+30 天)，不整体作废、不延长。
# 已知 refresh token 更早到期时取更早期限；旧无元数据文件仍限 24h。
# 服务端失效仍回落扫码门，本地窗口不能延长服务端会话。
SESSION_STATE = PROFILE / "session_state.json"
SESSION_TTL = 30 * 24 * 3600.0


def _session_state_usable(path, now=None, ttl=SESSION_TTL):
    """Scan-anchored reuse bound plus refresh expiry; legacy files retain 24h."""
    from bpm.session import state_usable
    return state_usable(path, now=now, ttl=ttl)

# ---- 检查项状态机（temp.md：没有执行的检查不得缺省成通过） ----
NOT_RUN, PASS, BLOCKED, FAIL, NOT_AUTHORIZED = "NOT_RUN", "PASS", "BLOCKED", "FAIL", "NOT_AUTHORIZED"
CHECKS_INIT = {
    "c1_entry_login": {"status": NOT_RUN, "reason": "", "evidence": []},
    "c2_locate_target": {"status": NOT_RUN, "reason": "", "evidence": []},
    "c3_structure": {"status": NOT_RUN, "reason": "", "evidence": []},
    "c4_normal_field_write": {"status": NOT_AUTHORIZED, "reason": "只读探针不写入；写入验证须显式授权（temp.md P4）", "evidence": []},
    "c5_hard_field_write": {"status": NOT_AUTHORIZED, "reason": "同上", "evidence": []},
    "c6_recover": {"status": NOT_RUN, "reason": "", "evidence": []},
    "c7_fill_new": {"status": NOT_RUN, "reason": "未启用 --fill-plan（只读任务不新建/不填写）", "evidence": []},
}

SENSITIVE_QS = re.compile(r"(token|ticket|code|key|sid|sign|auth|pwd|password|state|session)", re.I)


def sanitize_url(u):
    """URL 中疑似临时认证参数只留参数名，值脱敏。"""
    if not u or not isinstance(u, str):
        return u
    def _m(m):
        q, eq, v = m.group(0).partition("=")
        return q + eq + ("<masked>" if v else "")
    return re.sub(r"[?&][^?&\s]+", lambda m: _m(re.match(r"[?&]([^=?&]+)(=[^&]*)?", m.group(0))) and
                  m.group(0)[0] + re.sub(r"=.*", "=<masked>", m.group(0)[1:]) if SENSITIVE_QS.search(m.group(0)) else m.group(0), u)


def mask(v, keep=2):
    """控制台/摘要用脱敏：保留前 keep 字符。证据文件保留原值（受限本地记录）。"""
    s = str(v)
    return s if len(s) <= keep else s[:keep] + "***"


def _norm_cell(s):
    """单元格/标签文本归一：去首尾空白与尾部单位括注（金额(元)→金额），供定位与回读比对。"""
    if s is None:
        return ""
    return re.sub(r"[\s,，￥¥元（）()：:]+$", "", str(s).strip())


# 同词异写/尾缀归一词表（填写匹配与回读比对共用一源）：
# 其它↔其他：attempt_013 费用类型 miss；差旅费↔差旅：attempt_023 预算科目唯一 mismatch（模板词 vs OA 选项尾缀）
_ALIAS_ROWS = (("其它", "其他"), ("差旅费", "差旅"))


def _word_norm(s):
    return str(s).replace("其它", "其他").replace("差旅费", "差旅")


def fill_match(readback, target):
    """填写回读比对：归一后字符串相等，或数值等价（191.4 == 191.40）。大写金额不与数字互认。"""
    a, b = _word_norm(_norm_cell(readback)), _word_norm(_norm_cell(target))
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 0.005
    except (TypeError, ValueError):
        return False


# ---- PrimeNG 表面解析纯逻辑（attempt_006 实证：本表单 gc=false/spreads=0，Angular PrimeNG DOM） ----
# 计划键 → 表单标签/列头 别名（模板 OCR 措辞 vs OA 列头措辞，避免跨措辞失配）
PLAN_ALIASES = {
    "费用说明": ("费用说明", "项目说明"),           # 费用明细列头为 项目说明
    "天数/次数": ("天数/次数", "次数/天", "次数"),
    "费用类型": ("费用类型", "费用项目"),
    "银行账号": ("银行账号", "账号"),
    "转账金额": ("转账金额", "金额"),
    "年度": ("年度", "预算年度"),
    "关联公出单": ("关联公出单", "关联单据", "单据号"),
    "是否为一次性": ("是否为一次性", "是否为最后一次"),
    # attempt_012 实证：本表单无「事由」字段；流程归属(bizOrign)是组织下拉（乔丹科技/中乔发展…），
    # 与事由语义无关绝不误写——事由语义落点为 备注(description)，映射在回读记录中留痕
    "事由": ("事由", "备注"),
    "支付方式": ("支付方式", "报销方式"),
}
# label 解析不到时的 name 提示（Angular 语义控件名）
NAME_HINTS = {"事由": ("description",),
              "支付方式": ("paytype",),
              "年度": ("budgetyears", "year"),
              "是否为一次性": ("islast",),
              "关联公出单": ("biznumber", "docno", "billno")}


def _alias_set(key):
    """键 → 归一别名序列：分隔符拆分 + 原键 + PLAN_ALIASES。"""
    alts = []
    for x in list(re.split(r"[/、]", str(key))) + [str(key)] + list(PLAN_ALIASES.get(str(key), ())):
        n = _norm_cell(x)
        if n and n not in alts:
            alts.append(n)
    return alts


def _resolve_ng_field(fields, label):
    """label → 字段条目：label 精确 > label 互含 > name 提示（须可写）。只选可见项；找不到→None。"""
    alts = _alias_set(label)
    cand = [f for f in fields if f.get("visible") and f.get("type") != "password"]
    for f in cand:
        lb = _norm_cell(f.get("label"))
        if lb and lb in alts:
            return f
    for f in cand:
        lb = _norm_cell(f.get("label"))
        if lb and any(a in lb or lb in a for a in alts):
            return f
    for hint in NAME_HINTS.get(str(label), ()):
        for f in cand:
            if hint in (f.get("name") or "").lower() and not f.get("readonly"):
                return f
    return None


def _table_col(headers, key):
    """列头文本 → 列序号：精确/互含（含别名）。找不到→None。"""
    alts = _alias_set(key)
    for i, h in enumerate(headers):
        t = _norm_cell(h.get("text"))
        if t and t in alts:
            return i
    for i, h in enumerate(headers):
        t = _norm_cell(h.get("text"))
        if t and any(a in t or t in a for a in alts):
            return i
    return None


# ===================== 纯逻辑（离线可测） =====================

def classify(m, expect_name=None):
    """登录态三证分类：域名 / 登录组件 / 账户标识。
    返回 (status, evidence)。身份未确认一律 UNKNOWN——绝不因 URL 看似内页+导航多就判 LOGGED_IN。
    （v1 缺陷：仅 url+oaNav>=3 即判 LOGGED_IN，temp.md 已离线复现为错。）"""
    if not isinstance(m, dict) or m.get("eval_error"):
        return "UNKNOWN", {"eval_error": m.get("eval_error") if isinstance(m, dict) else repr(m)}
    u = (m.get("url") or "").lower()
    ev = {"url": sanitize_url(u), "title": m.get("title")}
    login_domain = any(k in u for k in ("login", "passport", "sso", "auth", "oauth", "wwlogin"))
    login_widget = bool(m.get("hasPassword")) or (
        (m.get("qrHints", 0) or 0) > 0 and bool(m.get("loginText")))
    if login_domain or login_widget:
        return "LOGIN_REQUIRED", ev
    # 账户证据：期待姓名命中（核心身份证据）+ 导航，且不在登录域。
    # 退出入口仅记录不强求——2026-10-21 活体实证：真实 OA 首页顶栏无显式退出按钮（logout_hits=0），
    # 强求三证齐会把已登录页误判 UNKNOWN（attempt_001 教训）。身份不符（name_hits=0）仍一律 UNKNOWN。
    name_hits = m.get("name_hits", 0) or 0
    logout_hits = m.get("logout_hits", 0) or 0
    oa_nav = m.get("oaNav", 0) or 0
    ev.update({"name_hits": name_hits, "logout_hits": logout_hits, "oaNav": oa_nav})
    if name_hits >= 1 and oa_nav >= 3:
        return "LOGGED_IN", ev
    return "UNKNOWN", ev


ACCOUNT_PROBE_JS_TMPL = """
(expectName) => {
  let name_hits = 0, logout_hits = 0, hit_texts = [];
  const walk = (doc) => {
    for (const e of doc.querySelectorAll('a,span,div,li,button')) {
      const t = (e.childElementCount === 0 ? (e.textContent || '').trim() : '');
      if (t) {
        if (expectName && t === expectName) { name_hits++; hit_texts.push('name'); }
        if (/退出登录|注销|登出/.test(t)) { logout_hits++; hit_texts.push('logout'); }
      }
    }
  };
  walk(document);
  for (const f of document.querySelectorAll('iframe')) {
    try { if (f.contentDocument) walk(f.contentDocument); } catch (e) {}
  }
  return { name_hits, logout_hits };
}
"""

# 登录等待超时时的诊断辅助：顶栏疑似账户姓名候选（身份不符/判据失效时给活体线索，不参与判定）
TOPBAR_CANDIDATES_JS = """
() => {
  const out = [];
  for (const e of document.querySelectorAll('a,span,div,li,button')) {
    const t = e.childElementCount === 0 ? (e.textContent || '').trim() : '';
    if (!t || t.length < 2 || t.length > 4) continue;
    const cls = ((e.className || '') + ' ' + (e.parentElement ? e.parentElement.className : '')).toString().toLowerCase();
    const id = ((e.id || '') + ' ' + (e.closest('[id]') ? e.closest('[id]').id : '')).toString().toLowerCase();
    if (/user|top|header|nav|account|info|avatar/.test(cls + ' ' + id) && !out.includes(t)) out.push(t);
  }
  return out.slice(0, 10);
}
"""


def pick_target(rows, doc_id):
    """rows: [{cells:[...], href}]；doc_id: 期待单据编号。
    返回 (status, payload)。0 命中=NOT_FOUND；多命中=AMBIGUOUS；无 doc_id=TARGET_UNSPECIFIED。
    任何情况都不返回"替身"行。"""
    if not doc_id:
        return "TARGET_UNSPECIFIED", {"rows_seen": len(rows)}
    hits = [r for r in rows if any(doc_id == (c or "").strip() or doc_id in (c or "") for c in r.get("cells", []))]
    if len(hits) == 0:
        return "NOT_FOUND", {"rows_seen": len(rows), "doc_id": doc_id}
    if len(hits) > 1:
        return "AMBIGUOUS", {"matches": len(hits), "doc_id": doc_id}
    return "OK", {"row": hits[0], "doc_id": doc_id}


def compare_identity(before, after):
    """恢复校验：比对 单据ID/账户/关键值。返回 (ok, diffs)。"""
    keys = ("doc_identity", "account_name", "status_text", "key_values")
    diffs = []
    for k in keys:
        b, a = before.get(k), after.get(k)
        if b != a:
            diffs.append({"field": k, "before": b, "after": a})
    ok_loc = (after.get("url") or "").startswith(HOST) and "login" not in (after.get("url") or "").lower()
    if not ok_loc:
        diffs.append({"field": "url", "before": before.get("url"), "after": after.get("url")})
    return (len(diffs) == 0), diffs


class PhaseRunner:
    """阶段状态机：依赖阶段非 PASS 则本阶段置 NOT_RUN(skipped)。
    整体成功只认业务断言（checks 全表），不认异常与否。"""
    def __init__(self, checks, log):
        self.checks = checks
        self.log = log
        self.phase_status = {}

    def run(self, name, fn, depends=()):
        for d in depends:
            if self.phase_status.get(d) != PASS:
                self.phase_status[name] = "SKIPPED"
                self.log(f"phase {name} SKIPPED (dependency {d} != PASS)")
                return "SKIPPED"
        try:
            st = fn()
            self.phase_status[name] = st or FAIL
            self.log(f"phase {name} -> {st}")
            return st
        except Exception as e:
            self.phase_status[name] = FAIL
            self.log(f"phase {name} FAILED: {e!r}")
            traceback.print_exc()
            return FAIL


class Budget:
    """三钟：tech（技术执行，登录等待挂起）/ login_wait（人工登录等待）/ wall（总墙钟）。
    全部 time.monotonic()；wait(slice) 把单次等待切片到剩余量；wall 看护线程超时强停。"""
    def __init__(self, tech=1800.0, login=480.0, wall=2400.0, on_wall_fire=None):
        self.tech_cap, self.login_cap, self.wall_cap = tech, login, wall
        self._m0 = time.monotonic()
        self._tech_t0 = None
        self.tech_used = 0.0
        self.login_wait_used = 0.0
        self._dead = False
        self._on_wall_fire = on_wall_fire
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def _watch(self):
        while not self._dead:
            if self.monotonic_wall() >= self.wall_cap:
                self._dead = True
                if self._on_wall_fire:
                    try:
                        self._on_wall_fire()
                    except Exception:
                        pass
                os._exit(83)          # 墙钟熔断：保证旧执行必退出（结果已由回调尽力落盘）
            time.sleep(1.0)

    def monotonic_wall(self):
        return time.monotonic() - self._m0

    def tech_resume(self):
        self._tech_t0 = time.monotonic()

    def tech_pause(self):
        if self._tech_t0 is not None:
            self.tech_used += time.monotonic() - self._tech_t0
            self._tech_t0 = None

    def tech_left(self):
        cur = self.tech_used + (time.monotonic() - self._tech_t0 if self._tech_t0 is not None else 0)
        return self.tech_cap - cur

    def ensure_tech(self, need=1.0):
        left = self.tech_left()
        if left <= 0:
            raise RuntimeError("BUDGET_EXHAUSTED")
        return left

    def wait_slice(self, want, clock="tech"):
        """把期望等待切到该钟剩余量；任一钟耗尽都返回 0（等待循环安全收尾）。
        抛错职责在阶段入口 ensure_tech——等待助手不抛。"""
        if clock == "tech":
            try:
                return max(0.0, min(want, self.ensure_tech()))
            except RuntimeError:
                return 0.0
        return max(0.0, min(want, self.login_cap - self.login_wait_used))

    def login_tick(self, dt):
        self.login_wait_used += dt

    def close(self):
        self._dead = True


# ===================== 浏览器编排 =====================

GRID_ROWS_JS = """
() => {
  const out = [];
  const grab = (doc) => {
    for (const t of doc.querySelectorAll('table')) {
      const rows = [...t.querySelectorAll('tbody tr')];
      for (const tr of rows) {
        const cells = [...tr.children].map(td => (td.innerText || '').trim().slice(0, 40));
        if (cells.length >= 3 && cells.some(c => c)) {
          const a = tr.querySelector('a[href]');
          out.push({ cells, href: a ? a.href : null });
        }
      }
    }
  };
  grab(document);
  return out;
}
"""

PAGE_MARKS_JS = """
() => {
  const m = {};
  m.url = location.href;
  m.title = document.title;
  m.hasPassword = !!document.querySelector('input[type=password]');
  m.qrHints = [...document.querySelectorAll('canvas,img,div,span')].slice(0, 400)
      .filter(e => /扫码|二维码|企业微信|微信扫码|QR/.test((e.textContent||'') + (e.alt||'') + (e.title||'')))
      .length;
  m.loginText = /登录|login/i.test(document.body ? document.body.innerText.slice(0, 3000) : '');
  m.oaNav = [...document.querySelectorAll('a,span,div')].slice(0, 800)
      .filter(e => /报销|单据|审批|首页|工作台/.test(e.textContent || '')).length;
  m.forms = document.forms.length;
  return m;
}
"""

QR_EXPIRED_JS = """
() => /已过期|过期|expired|refresh/i.test(document.body ? document.body.innerText.slice(0, 4000) : '')
"""

BLOCKS_READ_JS = r"""
() => {
  const names = ['关联单据明细','报销明细','费用说明','银行信息'];
  const out = [];
  for (const nm of names) {
    let el = null;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      if ((n.textContent || '').trim() === nm) { el = n.parentElement; break; }
    }
    if (!el) { out.push({block: nm, found: false}); continue; }
    let box = el;
    for (let i = 0; i < 8 && box.parentElement; i++) {
      box = box.parentElement;
      if (box.querySelector('table, input, .editor, [contenteditable]')) break;
    }
    const q = s => box.querySelectorAll(s).length;
    const grid = [...box.querySelectorAll('table')].map(t => ({
      headers: [...t.querySelectorAll('th')].map(h => (h.innerText||'').trim().slice(0,20)),
      rows: [...t.querySelectorAll('tbody tr')].slice(0, 20).map(tr =>
        [...tr.children].map(td => (td.innerText||'').replace(/\s+/g,' ').trim().slice(0, 60)))
    }));
    out.push({
      block: nm, found: true,
      container: box.tagName + '.' + (box.className||'').toString().slice(0, 100),
      tables: q('table'), inputs: q('input'), textareas: q('textarea'), selects: q('select'),
      contenteditable: q('[contenteditable=true], [contenteditable=""]'),
      iframes: q('iframe'), canvases: q('canvas'),
      editor_widgets: [...box.querySelectorAll('[class]')].map(e => e.className.toString())
          .filter(c => /grid|editor|kendo|dhtmlx|ext-|ant-|el-|layui|jeecg|jqgrid/i.test(c)).slice(0, 8),
      grid
    });
  }
  return {blocks: out, frames: window.frames.length};
}
"""


def assert_internal(url):
    if not url or not url.startswith(HOST):
        raise RuntimeError(f"REFUSED_EXTERNAL_NAV: {sanitize_url(url)}")
    return url


# ===================== 填写任务专用（--fill-plan 授权路径） =====================
# 与 DOM_FIELD_CSS 保持同一选择器（selftest 静态校验二者一致）
DOM_FIELD_CSS = ("input:not([type=hidden]):not([type=button]):not([type=submit]):not([type=checkbox]),"
                 "select, textarea")

FORM_READY_JS = r"""
() => {
  const dom = document.querySelectorAll('%CSS%').length;
  let spreads = 0;
  try {
    if (typeof GC !== 'undefined' && GC.Spread && GC.Spread.Sheets) {
      const seen = new Set();
      for (const d of document.querySelectorAll('div')) {
        let wb = null;
        try { wb = GC.Spread.Sheets.findControl(d); } catch (e) {}
        if (wb && !seen.has(wb)) { seen.add(wb); spreads++; }
      }
    }
  } catch (e) {}
  return {dom_fields: dom, spreads};
}
""".replace("%CSS%", DOM_FIELD_CSS)

DOM_FIELDS_JS = r"""
() => {
  const els = [...document.querySelectorAll('%CSS%')];
  return els.map((el, i) => {
    let prev = '';
    let p = el;
    for (let k = 0; k < 6 && p; k++) {
      p = p.previousElementSibling || (p.parentElement && p.parentElement.previousElementSibling);
      if (p && p.innerText && p.innerText.trim()) { prev = p.innerText.trim().slice(0, 30); break; }
    }
    const row = el.closest('tr');
    return {i, tag: el.tagName, type: el.type || '',
            name: el.name || el.id || el.placeholder || el.title || el.getAttribute('aria-label') || '',
            prev_text: prev,
            row_text: row ? row.innerText.trim().slice(0, 80) : '',
            value: el.type === 'password' ? '<masked>' : (el.value || '').slice(0, 40)};
  });
}
""".replace("%CSS%", DOM_FIELD_CSS)

SPREAD_ENUM_JS = r"""
() => {
  const out = [];
  try {
    if (typeof GC === 'undefined' || !GC.Spread || !GC.Spread.Sheets) return {gc: false, spreads: []};
    const seen = new Set();
    for (const d of document.querySelectorAll('div')) {
      let wb = null;
      try { wb = GC.Spread.Sheets.findControl(d); } catch (e) {}
      if (wb && !seen.has(wb)) {
        seen.add(wb);
        const sheets = [];
        const n = wb.getSheetCount ? wb.getSheetCount() : 0;
        for (let i = 0; i < n; i++) {
          try {
            const s = wb.getSheet(i);
            const rows = s.getRowCount(), cols = s.getColumnCount();
            const texts = [];
            for (let r = 0; r < Math.min(rows, 60); r++) {
              const row = [];
              for (let c = 0; c < Math.min(cols, 24); c++) row.push(s.getText(r, c));
              texts.push(row);
            }
            sheets.push({name: s.name(), rows, cols, texts});
          } catch (e) { sheets.push({error: String(e)}); }
        }
        out.push({sheets});
      }
    }
    return {gc: true, spreads: out};
  } catch (e) { return {gc: 'error', error: String(e), spreads: out}; }
}
"""

SPREAD_CELL_OP_JS = r"""
(arg) => {
  // arg: {op: 'get'|'grow'|'set'|'startEdit', wb, sheet, r, c, value}
  if (typeof GC === 'undefined' || !GC.Spread) return {ok: false, error: 'no GC'};
  const wbs = [];
  const seen = new Set();
  for (const d of document.querySelectorAll('div')) {
    let w = null;
    try { w = GC.Spread.Sheets.findControl(d); } catch (e) {}
    if (w && !seen.has(w)) { seen.add(w); wbs.push(w); }
  }
  const wb = wbs[arg.wb];
  if (!wb) return {ok: false, error: 'no workbook ' + arg.wb};
  const s = wb.getSheet(arg.sheet);
  if (!s) return {ok: false, error: 'no sheet ' + arg.sheet};
  if (arg.op === 'get')
    return {ok: true, text: s.getText(arg.r, arg.c), value: s.getValue(arg.r, arg.c)};
  if (arg.op === 'grow') {
    if (arg.r >= s.getRowCount()) { s.addRows(s.getRowCount(), arg.r - s.getRowCount() + 1); }
    return {ok: true, rows: s.getRowCount()};
  }
  if (arg.op === 'set') {
    try { s.setValue(arg.r, arg.c, arg.value); } catch (e) { return {ok: false, error: String(e)}; }
    return {ok: true, text: s.getText(arg.r, arg.c)};
  }
  if (arg.op === 'startEdit') {
    try { s.setActiveCell(arg.r, arg.c); s.startEdit(false); } catch (e) { return {ok: false, error: String(e)}; }
    return {ok: true};
  }
  return {ok: false, error: 'bad op ' + arg.op};
}
"""

EDITOR_STATE_JS = r"""
() => {
  const el = document.activeElement;
  if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.select) {
    el.select();
    return el.value || '';
  }
  return null;   // 编辑器未聚焦：调用方不得盲打键盘
}
"""

# ---- PrimeNG 表面 JS（attempt_006 实证：Angular PrimeNG DOM，label[for=name] 绑定、p-table 列头带 prop-* 类） ----
_NG_HELPERS = r"""
const _vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
const _path = el => {
  if (el.id) return '#' + CSS.escape(el.id);
  const parts = [];
  while (el && el.nodeType === 1 && parts.length < 24) {
    let s = el.tagName.toLowerCase();
    if (el.className && typeof el.className === 'string') {
      const c = el.className.trim().split(/\s+/).filter(x => x && !/^\d+$/.test(x)).slice(0, 2)
        .map(x => '.' + CSS.escape(x)).join('');
      s += c;
    }
    const p = el.parentElement;
    if (p) {
      let idx = 1;
      for (const sib of p.children) { if (sib === el) break; if (sib.tagName === el.tagName) idx++; }
      if (p.children.length > 1) s += ':nth-of-type(' + idx + ')';
    }
    parts.unshift(s);
    el = p;
    if (el && (el.tagName === 'FORM' || (el.id && parts[0].startsWith('#')))) break;
  }
  return parts.join('>');
};
"""

# 表单字段清单：可见 input/textarea/select + p-dropdown/p-multiselect 组件（多选无可见输入框，须单独枚举）
FORM_MAP_JS = _NG_HELPERS + r"""
(scope) => {
  const out = [];
  const root = scope || document;
  const labelFor = {};
  root.querySelectorAll('label[for]').forEach(l => {
    const t = (l.textContent || '').trim();
    if (t) labelFor[l.getAttribute('for')] = t;
  });
  for (const el of root.querySelectorAll('input, textarea, select')) {
    if (el.type === 'hidden' || el.type === 'checkbox' || el.type === 'radio') continue;
    if (!_vis(el)) continue;
    let name = el.getAttribute('name') || el.id || '';
    let label = labelFor[name] || labelFor[el.id] || '';
    // attempt_011 实证：qd-dynamic-form-control 把字段名放 dfc-container 的 prop-* 类、
    // 标签放 label.display-label——input 无 name/label 时向上爬容器取
    if (!name || !label) {
      const dfc = el.closest('.dfc-container, [class*="prop-"]');
      if (dfc) {
        const m = (dfc.className || '').match(/prop-([\w-]+)/);
        if (m && !name) name = m[1];
        if (!label) {
          const dl = dfc.querySelector('label.display-label') || dfc.querySelector('label');
          if (dl) label = (dl.textContent || '').replace(/\s+/g, ' ').trim();
        }
      }
    }
    if (!label) {
      const wrap = el.closest('.ui-dropdown, .ui-multiselect, .ui-calendar, .p-float-label, .form-group, .ui-grid-row');
      if (wrap) {
        const lb = wrap.querySelector('label');
        if (lb) label = (lb.textContent || '').trim();
      }
    }
    if (!label) {
      const prev = el.parentElement ? el.parentElement.previousElementSibling : null;
      if (prev) label = (prev.textContent || '').trim().slice(0, 30);
    }
    out.push({
      name, label,
      type: el.tagName.toLowerCase() === 'input' ? (el.type || 'text') : el.tagName.toLowerCase(),
      value: (el.type === 'password') ? '' : (el.value || ''),
      readonly: el.readOnly || el.disabled,
      visible: true, sel: _path(el),
      comp: (() => { const d = el.closest('.ui-dropdown'); return d ? _path(d) : ''; })(),
    });
  }
  for (const d of root.querySelectorAll('.ui-dropdown, .ui-multiselect')) {
    const has = out.some(f => f.comp === _path(d));
    if (has) continue;
    if (!_vis(d)) continue;
    const lb = d.querySelector('.ui-dropdown-label, .ui-multiselect-label');
    // attempt_011 实证：可写 p-dropdown/p-multiselect 无可见命名 input，name 只在
    // dfc-container 的 prop-* 类、label 只在 label.display-label——从组件向上爬容器取
    let name = '', label = '';
    const dfc = d.closest('.dfc-container, [class*="prop-"]');
    if (dfc) {
      const m = (dfc.className || '').match(/prop-([\w-]+)/);
      if (m) name = m[1];
      const dl = dfc.querySelector('label.display-label') || dfc.querySelector('label');
      if (dl) label = (dl.textContent || '').replace(/\s+/g, ' ').trim();
    }
    if (!label) {
      const wrap = d.parentElement;
      if (wrap) {
        const l2 = wrap.querySelector('label');
        if (l2) label = (l2.textContent || '').trim();
      }
    }
    if (!name) {
      const inner = d.querySelector('input[name]');
      if (inner) name = inner.getAttribute('name') || '';
    }
    out.push({
      name, label,
      type: d.classList.contains('ui-multiselect') ? 'multiselect' : 'dropdown',
      value: lb ? (lb.value !== undefined && lb.value ? lb.value : (lb.textContent || '').trim()) : '',
      readonly: d.classList.contains('ui-state-disabled'),
      visible: true, sel: _path(d), comp: _path(d),
    });
  }
  return out;
}
"""

# p-table 清单：列头 th.field-col-header.prop-* → prop/text；新增按钮按「最近独占祖先」归属；行数
TABLE_MAP_JS = _NG_HELPERS + r"""
() => {
  const tables = [];
  // attempt_011 实证：新增按钮是 ui-button-icon-only，『新增』span 被 CSS 隐藏 → innerText 为空；
  // 须以 title/aria-label/textContent 识别（textContent 含被隐藏的文字 span）
  const addBtn = b => (b.title === '新增' || b.getAttribute('aria-label') === '新增'
                       || (b.textContent || '').trim() === '新增') && !b.disabled && _vis(b);
  // attempt_014 实证：选择入口实为 edit-bar『插入』钮（icon=fa fa-sign-in，title/aria=插入，
  // 无文本 span；图标 span 类是 Angular 异步渲染，map 时未必在场 → 以静态属性 title/aria 为准）
  const pickBtn = b => !b.disabled && _vis(b) && (
      b.title === '选入' || b.title === '插入'
      || b.getAttribute('aria-label') === '选入' || b.getAttribute('aria-label') === '插入'
      || (b.textContent || '').trim() === '选入'
      || !!b.querySelector('i.fa-sign-in, .fa-sign-in'));
  for (const t of document.querySelectorAll('table')) {
    if (!_vis(t)) continue;
    const ths = [];
    for (const th of t.querySelectorAll('thead th')) {
      const cls = th.className || '';
      const m = cls.match(/prop-([\w-]+)/);
      ths.push({ text: (th.textContent || '').trim(), prop: m ? m[1] : '' });
    }
    if (!ths.length) continue;
    // 表题：qd-dynamic-table 的 span.table-caption（attempt_007 HTML 实证），优先于面板标题启发
    let title = '';
    const qdt = t.closest('qd-dynamic-table');
    if (qdt) {
      const cap = qdt.querySelector('.table-caption');
      if (cap) title = (cap.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30);
    }
    // 新增按钮归属（attempt_012 复盘 + 离线诊断实证）：PrimeNG scrollable 表把 thead/tbody 拆成
    // 同组件内 3 个 table，『祖先内恰 1 个 table』判据永假；正确边界是 qd-dynamic-table 组件——
    // caption 与 edit-bar 同在其中，组件内恰含 1 个新增按钮（attempt_010 的跨面板误用同时根治）。
    let addSel = '';
    if (qdt) {
      const bs = Array.from(qdt.querySelectorAll('button')).filter(addBtn);
      if (bs.length === 1) addSel = _path(bs[0]);   // 0=只读表（审批记录等）；>1=归属不明——均如实留空
    }
    // 『选入』按钮归属同 add_sel：qd-dynamic-table 组件内恰 1 个才认（>1=含行内图标，走行内兜底）
    let pickSel = '';
    if (qdt) {
      const pbs = Array.from(qdt.querySelectorAll('button')).filter(pickBtn);
      if (pbs.length === 1) pickSel = _path(pbs[0]);
    }
    if (!addSel) {
      // 兜底：无 qd-dynamic-table 包裹的普通表（弹窗内等）沿用「最近独占祖先」
      let anc = t.parentElement;
      while (anc && anc !== document.body) {
        const tbls = anc.querySelectorAll('table').length;
        const btn = Array.from(anc.querySelectorAll('button')).find(addBtn);
        if (btn && tbls === 1) {
          addSel = _path(btn);
          if (!title) {
            const hd = anc.querySelector('.ui-panel-title, .ui-panel-titlebar, [class*="title"], h1, h2, h3, h4');
            if (hd) title = (hd.textContent || '').trim().slice(0, 30);
          }
          break;
        }
        if (btn && tbls > 1) break;   // 到了多表共享的外层：本表无专属新增，如实置空
        anc = anc.parentElement;
      }
    }
    // 数据行在 .ui-table-scrollable-body 的另一个 table 里（thead 所在表的 tbody 恒空）；
    // 空表无占位行（离线实证 <tr 数=0），row_count 数 body 表即准
    const bodyTbl = (qdt && qdt.querySelector('.ui-table-scrollable-body table')) || t;
    tables.push({
      sel: _path(t), body_sel: _path(bodyTbl), title, add_sel: addSel, pick_sel: pickSel,
      headers: ths, row_count: bodyTbl.querySelectorAll('tbody tr').length,
    });
  }
  const seen = new Set();
  return tables.filter(t => { const k = t.sel; if (seen.has(k)) return false; seen.add(k); return true; });
}
"""

# 可见对话框清单（行编辑弹窗）：标题 + 按钮文本/选择器/禁用
DIALOG_DUMP_JS = _NG_HELPERS + r"""
() => {
  const dl = [];
  // .cdk-overlay-container/.ui-overlay：Angular Material/PrimeNG 浮层弹窗不一定是 .ui-dialog
  const sels = '.ui-dialog, p-dialog, [role="dialog"], .cdk-overlay-container .ui-dialog, .ui-overlay-modal, .p-dialog';
  const seen = new Set();
  for (const d of document.querySelectorAll(sels)) {
    if (seen.has(d) || !_vis(d)) continue;
    seen.add(d);
    const t = d.querySelector('.ui-dialog-title, .ui-dialog-titlebar, [class*="title"]');
    const btns = [];
    for (const b of d.querySelectorAll('button')) {
      if (!_vis(b)) continue;
      btns.push({ text: (b.textContent || b.innerText || '').trim(), sel: _path(b), disabled: !!b.disabled || b.classList.contains('ui-state-disabled') });
    }
    // tables>0 ≈ 选择器弹窗（列表挑行）；0 ≈ 行编辑表单弹窗——选入流程的适用性判据
    dl.push({ sel: _path(d), title: t ? (t.textContent || '').trim() : '', buttons: btns,
              tables: d.querySelectorAll('table').length });
  }
  return dl;
}
"""

# 浮层画像（attempt_016）：格内『…』/button-behind 按钮开的白色搜索浮层不是 .ui-dialog——
# 按位置浮起 + 尺寸过滤泛化枚举，带出输入框/候选行/按钮清单，供搜索点选流程与审计事件用
OVERLAY_DUMP_JS = _NG_HELPERS + r"""
() => {
  const out = [];
  const sels = ['.ui-dialog', 'p-dialog', '[role="dialog"]', '.ui-overlay-panel', '.ui-overlay',
                '.ui-autocomplete-panel', '.ui-dropdown-panel', '.ui-multiselect-panel',
                '.ui-datepicker', '[class*="search-panel"]:not(.menu-search-panel)'];
  const seen = new Set();
  const push = d => {
    if (!d || seen.has(d) || !_vis(d)) return;
    const st = getComputedStyle(d);
    if (st.position !== 'fixed' && st.position !== 'absolute') return;
    const r = d.getBoundingClientRect();
    if (r.width < 80 || r.height < 30) return;
    seen.add(d);
    const t = d.querySelector('.ui-dialog-title, [class*="title"]');
    const inputs = [];
    for (const i of d.querySelectorAll('input:not([type="hidden"]), textarea')) {
      if (_vis(i)) inputs.push(i);
    }
    const rows = [];
    for (const x of d.querySelectorAll('li, tr')) {
      const txt = (x.textContent || '').replace(/\s+/g, ' ').trim();
      if (!txt || txt.length > 200 || !_vis(x)) continue;
      if (rows.length < 12) rows.push({ text: txt.slice(0, 100), sel: _path(x) });
    }
    // 带文本钮优先（022 教训同 DIALOG_SCOPE_DUMP_JS：空文本 button-behind 挤满配额）
    const allB = [];
    for (const b of d.querySelectorAll('button')) {
      if (!_vis(b)) continue;
      allB.push({ text: (b.textContent || '').trim().slice(0, 20), sel: _path(b), disabled: !!b.disabled });
    }
    const btns = allB.filter(b => b.text).slice(0, 10);
    for (const b of allB) {
      if (btns.length >= 10) break;
      if (!b.text) btns.push(b);
    }
    out.push({ sel: _path(d), cls: (d.className || '').toString().slice(0, 100),
               title: t ? (t.textContent || '').trim().slice(0, 60) : '',
               inputs: inputs.length, input_sel: inputs[0] ? _path(inputs[0]) : '',
               rows: rows.length, row_list: rows, buttons: btns,
               tables: d.querySelectorAll('table').length });
  };
  sels.forEach(s => document.querySelectorAll(s).forEach(push));
  for (const el of document.querySelectorAll('.cdk-overlay-container *')) {
    if (!Array.from(seen).some(x => x.contains(el))) push(el);
  }
  return out;
}
"""

# 弹窗容器内补扫（attempt_018）：『选择表格数据』开的是 p-dialog 弹表（带遮罩/搜索框/
# 分页表格/确定取消），被 OVERLAY_DUMP_JS 的 position+尺寸过滤漏掉（fill_overlay_dump
# 空手而归而 panel_open=true）。DIALOG_DUMP_JS 抓得到容器——按容器补扫输入框/行/按钮，
# 产出与 OVERLAY_DUMP_JS 条目同构，无 position 门槛，喂同一条两段式选行流。
DIALOG_SCOPE_DUMP_JS = _NG_HELPERS + r"""
(d) => {
  if (!d) return null;
  const t = d.querySelector('.ui-dialog-title, .ui-dialog-titlebar, [class*="title"]');
  const inputs = [];
  for (const i of d.querySelectorAll('input:not([type="hidden"]), textarea')) {
    if (_vis(i)) inputs.push(i);
  }
  const rows = [];
  for (const x of d.querySelectorAll('li, tr')) {
    const txt = (x.textContent || '').replace(/\s+/g, ' ').trim();
    if (!txt || txt.length > 200 || !_vis(x)) continue;
    if (rows.length < 12) rows.push({ text: txt.slice(0, 100), sel: _path(x) });
  }
  // 按钮≤10：带文本的优先（022 实证：初始态 11 行的空文本 button-behind 会把配额
  // 挤满，footer 的 确定/取消/全选 全被挤掉 → 点了行却找不到确认钮，弹窗残留遮罩
  // 挡死后续新增）——两段收集：先文本钮，余量再补空文本钮。
  const all = [];
  for (const b of d.querySelectorAll('button')) {
    if (!_vis(b)) continue;
    all.push({ text: (b.textContent || '').trim().slice(0, 20), sel: _path(b), disabled: !!b.disabled });
  }
  const btns = all.filter(b => b.text).slice(0, 10);
  for (const b of all) {
    if (btns.length >= 10) break;
    if (!b.text) btns.push(b);
  }
  return { sel: _path(d), cls: (d.className || '').toString().slice(0, 100),
           title: t ? (t.textContent || '').trim().slice(0, 60) : '',
           inputs: inputs.length, input_sel: inputs[0] ? _path(inputs[0]) : '',
           rows: rows.length, row_list: rows, buttons: btns,
           tables: d.querySelectorAll('table').length };
}
"""

# 页面 toast（p-toast top-center）：链式门槛/校验拦截以 toast 呈现而非浮层
# （attempt_017 预算截图实证：『✖ 请先选择一个预算单』）——点了没开面板时必读
TOAST_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('.ui-toast-item-container, .ui-toast-message').forEach(m => {
    const r = m.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    const t = (m.textContent || '').replace(/\s+/g, ' ').trim();
    if (t) out.push(t.slice(0, 120));
  });
  return out;
}
"""

# 单元格信息：文本 + 编辑器类型（dropdown/multiselect/calendar/input/textarea/select/readonly）
CELL_INFO_JS = r"""
(td) => {
  if (!td) return null;
  const txt = (td.textContent || '').trim();
  const dd = td.querySelector('.ui-dropdown');
  if (dd) return { text: txt, kind: 'dropdown', sel: dd.getAttribute('data-id') || '' , comp_path: ''};
  const ms = td.querySelector('.ui-multiselect');
  if (ms) return { text: txt, kind: 'multiselect', sel: '', comp_path: '' };
  const cal = td.querySelector('input[type="date"], .ui-calendar input');
  if (cal) return { text: txt, kind: 'calendar', sel: cal.getAttribute('name') || '' , comp_path: ''};
  const inp = td.querySelector('input:not([type="hidden"]), textarea, select');
  if (inp) return { text: txt, kind: inp.tagName.toLowerCase() === 'input' ? (inp.type || 'text') : inp.tagName.toLowerCase(), sel: inp.getAttribute('name') || '', comp_path: '' };
  return { text: txt, kind: txt ? 'readonly' : 'empty', sel: '', comp_path: '' };
}
"""

# 读取组件当前显示值：input.value 或下拉/多选 label
NG_VALUE_JS = r"""
(compSel) => {
  const el = document.querySelector(compSel);
  if (!el) return null;
  const inp = el.matches('input, textarea') ? el : el.querySelector('input');
  if (inp && !el.classList.contains('ui-dropdown') && !el.classList.contains('ui-multiselect') && inp.type !== 'hidden') return inp.value || '';
  const lb = el.querySelector('.ui-dropdown-label, .ui-multiselect-label, .ui-label');
  if (lb) return (lb.value !== undefined && lb.value ? lb.value : (lb.textContent || '')).trim();
  return null;
}
"""


class Probe:
    def __init__(self, args):
        self.args = args
        self.run_dir = BASE / "automation" / "runs" / args.run
        self.run_dir.mkdir(parents=True, exist_ok=True)
        n = 1
        while (self.run_dir / f"attempt_{n:03d}").exists():
            n += 1
        self.attempt = self.run_dir / f"attempt_{n:03d}"
        self.ev = self.attempt / "evidence"
        self.ev.mkdir(parents=True, exist_ok=False)
        self.checks = json.loads(json.dumps(CHECKS_INIT))
        self.result = {
            "probe_version": "v2", "run": args.run, "attempt": self.attempt.name,
            "doc_id": args.doc_id, "expect_name": args.expect_name,
            "checks": self.checks, "phases": {},
            "events_jsonl_note": "events.jsonl 在 run 级持续追加（可变文件，不参与终局哈希）",
            "screenshots_note": "证据均在 attempt 目录，旧 run/attempt 文件一律不覆盖",
        }
        self.budget = Budget(tech=args.tech_budget, login=args.login_wait, wall=args.wall_cap,
                             on_wall_fire=self._wall_dump)
        self.ctx = None
        self._lock_path = PROFILE / "executor.lock"
        # 填写任务（--fill-plan）：授权开关。未启用时探针保持纯只读，c7 恒 NOT_RUN
        fp = getattr(args, "fill_plan", None)
        self.fill_plan_path = Path(fp) if fp else None
        self.fill_plan = None
        if self.fill_plan_path:
            self.fill_plan = json.loads(io.open(self.fill_plan_path, encoding="utf-8").read())
            self.checks["c7_fill_new"]["reason"] = (
                "已授权填写任务（--fill-plan）：新建报销单只填不存；"
                "保存/发送/流转/提交/上传/暂存/贴票 一律不点击")
            self.result["fill_plan_file"] = str(self.fill_plan_path)

    # ---- 落盘 ----
    def log_event(self, **kw):
        kw["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        with io.open(self.run_dir / "events.jsonl", "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")

    # ---- 动作级计时（2026-10-23 效率证据链：只加观测不改行为）----
    def _timing(self, action, **fields):
        """计时段上下文：进入记 t0（perf_counter + epoch ms），退出追加 timing 事件
        （event=timing / action / t0_ms / dur_ms / outcome=ok|timeout|error / exc 异常
        类型名）。Timeout 类异常单独标 outcome=timeout——『捕获异常后继续』的默认
        45s 烧穿由此显形；fields 携带 where/section/field 等定位计数。仅观测：
        不含任何等待/重试逻辑，被包行为逐字节不变。"""
        t0 = time.perf_counter()
        t0_ms = int(time.time() * 1000)
        holder = {}

        @contextlib.contextmanager
        def _cm():
            try:
                yield holder
            except BaseException as e:
                holder["outcome"] = "timeout" if "Timeout" in type(e).__name__ else "error"
                holder["exc"] = type(e).__name__
                raise
            finally:
                dur_ms = round((time.perf_counter() - t0) * 1000)
                try:
                    self.log_event(event="timing", action=action, t0_ms=t0_ms,
                                   dur_ms=dur_ms, outcome=holder.get("outcome", "ok"),
                                   exc=holder.get("exc", ""), **fields)
                except Exception:
                    pass
        return _cm()

    def say(self, *a):
        print(time.strftime("[%H:%M:%S]"), *a, flush=True)

    def save(self, name, text):
        p = self.ev / name
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        return f"{self.attempt.name}/evidence/{name}"

    def _dump_rows_evidence(self, tag, cands, note=""):
        """弹表原始行文落盘（attempt_020 教训）：events.jsonl 全程 mask + 截图分辨率
        不足 OCR，020 到底点中了哪一行（『单据***』含公出却无单号）无法复盘。原始值
        只进 attempt 证据目录 fill_dialog_rows.jsonl（契约：证据文件保原始值，控制台/
        事件仍 mask），追加不覆盖，异常绝不影响主流程。"""
        try:
            rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "where": tag,
                   "cands": [{k: c.get(k) for k in ("sel", "cls", "title", "input_sel",
                                                    "buttons", "row_list")}
                             for c in (cands or []) if isinstance(c, dict)]}
            if note:
                rec["note"] = note
            with io.open(self.ev / "fill_dialog_rows.jsonl", "a",
                         encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def shot(self, page, name):
        try:
            with self._timing("screenshot", name=str(name)):
                page.screenshot(path=str(self.ev / name), full_page=False)
            return f"{self.attempt.name}/evidence/{name}"
        except Exception as e:
            return f"screenshot_failed:{e!r}"

    def save_html(self, page, name):
        try:
            return self.save(name, page.content())
        except Exception as e:
            return f"html_failed:{e!r}"

    def atomic_result(self):
        """结果原子写（tmp + os.replace），只写本 attempt 目录。"""
        self.budget.tech_pause()
        self.result["tech_used_s"] = round(self.budget.tech_used, 1)
        self.result["login_wait_s"] = round(self.budget.login_wait_used, 1)
        self.result["wall_s"] = round(self.budget.monotonic_wall(), 1)
        self.result["budget_respected"] = self.budget.tech_used <= self.args.tech_budget + 5
        tmp = self.attempt / ".stage1_result.json.tmp"
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(self.result, ensure_ascii=False, indent=1))
        os.replace(tmp, self.attempt / "stage1_result.json")

    def _wall_dump(self):
        try:
            self.result["finish_reason"] = "WALL_CAP_FIRED"
            self.atomic_result()
        except Exception:
            pass

    # ---- profile 锁：同一 profile 同时只由一个执行者 ----
    @staticmethod
    def _pid_alive(pid):
        """Windows 进程存活探针（无副作用）。attempt_016 事故实证：os.kill(pid, 0)
        在 Windows 上 sig=0 即 CTRL_C_EVENT——同控制台会把占用进程直接打断（停靠中
        的 016 就这样被打死），异控制台抛 WinError 87/CPython SystemError。改用
        ctypes OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) 只查不动。"""
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, int(pid))   # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                k32.GetExitCodeProcess(h, ctypes.byref(code))
                return code.value == 259                    # STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        except Exception:
            return True      # 探针失败时保守视为存活（宁可拒绝启动也不误杀/误抢）

    def acquire_lock(self):
        if self._lock_path.exists():
            try:
                pid = int(self._lock_path.read_text().strip())
            except ValueError:
                pid = None
            if pid is not None and pid != os.getpid() and self._pid_alive(pid):
                raise RuntimeError(f"PROFILE_LOCKED by pid={pid}（同 profile 已有执行者）")
            self.log_event(event="profile_lock_stale_taken_over", old_pid=pid)
        PROFILE.mkdir(parents=True, exist_ok=True)
        self._lock_path.write_text(str(os.getpid()))
        self.log_event(event="profile_lock_acquired", pid=os.getpid())

    def release_lock(self):
        try:
            if self._lock_path.exists() and self._lock_path.read_text().strip() == str(os.getpid()):
                self._lock_path.unlink()
        except Exception:
            pass

    # ---- 页面读取 ----
    def marks(self, page):
        try:
            m = page.evaluate(PAGE_MARKS_JS)
        except Exception as e:
            return {"eval_error": repr(e), "url": page.url}
        try:
            acc = page.evaluate(ACCOUNT_PROBE_JS_TMPL, self.args.expect_name) or {}
            m.update(acc)
        except Exception as e:
            m["account_probe_error"] = repr(e)
        return m

    def login_state(self, page):
        m = self.marks(page)
        st, ev = classify(m, self.args.expect_name)
        return st, m, ev

    def cookie_names(self):
        return sorted({c["name"] for c in self.ctx.cookies()})

    # ---- 阶段实现 ----
    def phase_entry(self):
        self.budget.tech_resume()
        page = self.page
        t0, nav_err = time.time(), None
        try:
            assert_internal(HOST + "/")
            page.goto(HOST + "/", wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            nav_err = repr(e)
        page.wait_for_timeout(2000)
        st, m, ev = self.login_state(page)
        self.result["entry"] = {
            "nav_error": nav_err, "nav_ms": round((time.time() - t0) * 1000),
            "classify": st, "markers": {k: v for k, v in m.items() if k != "title"},
            "cookies_names": self.cookie_names(),
            "screenshot": self.shot(page, "entry.png"), "html": self.save_html(page, "entry.html"),
        }
        self.say(f"entry classify={st} url={sanitize_url(m.get('url'))} name_hits={m.get('name_hits')} logout_hits={m.get('logout_hits')}")
        if nav_err:
            self.checks["c1_entry_login"].update(status=BLOCKED, reason=f"入口导航失败: {nav_err[:200]}",
                                                 evidence=[self.result["entry"]["screenshot"]])
            return BLOCKED
        if st == "LOGGED_IN":
            reason = ("域名内页+账户名命中+导航成立"
                      + (f"（+退出入口 x{m.get('logout_hits', 0)}）" if m.get("logout_hits")
                         else "（顶栏无显式退出钮，按放宽判据放行）"))
            self.checks["c1_entry_login"].update(status=PASS, reason=reason,
                                                 evidence=[self.result["entry"]["screenshot"]])
            return PASS
        if st == "LOGIN_REQUIRED":
            return "LOGIN_REQUIRED"          # 交给登录等待循环
        self.checks["c1_entry_login"].update(status=BLOCKED, reason=f"身份未确认({st})：无账户证据不判登录成功",
                                             evidence=[self.result["entry"]["screenshot"]])
        return BLOCKED

    def wait_login(self):
        page = self.page
        self.budget.tech_pause()
        self.say(f"LOGIN GATE — 等待扫码，上限 {self.args.login_wait:.0f}s（单独计时；二维码过期将自动刷新登录页）")
        self.log_event(event="login_wait_start", login_wait_cap=self.args.login_wait)
        qr_refreshes = 0
        slices = 0
        while True:
            slice_s = self.budget.wait_slice(5.0, clock="login")
            if slice_s <= 0:
                break
            t0 = time.monotonic()
            try:
                page.wait_for_timeout(int(slice_s * 1000))
            except Exception as we:
                # 等待期浏览器被关闭/崩溃：如实 BLOCKED，不裸抛（attempt_008 教训：关窗裸栈 FAILED）
                self.checks["c1_entry_login"].update(
                    status=BLOCKED, reason=f"登录等待期浏览器被关闭: {str(we)[:120]}")
                self.log_event(event="login_wait_aborted", error=str(we)[:160])
                return BLOCKED
            self.budget.login_tick(time.monotonic() - t0)
            slices += 1
            try:
                if page.evaluate(QR_EXPIRED_JS) and qr_refreshes < 5:
                    qr_refreshes += 1
                    self.say(f"二维码已过期 → 刷新登录页（第 {qr_refreshes} 次）")
                    self.log_event(event="login_qr_refreshed", n=qr_refreshes)
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    continue
            except Exception:
                pass
            st, m, _ = self.login_state(page)
            if slices % 6 == 0:  # 每 30s 心跳：等待期可诊断（attempt_001 教训：8 分钟静默）
                cands = None
                if st == "UNKNOWN":  # 内页但姓名未命中 → 附顶栏候选，当场区分「名字写错」vs「真没登录」
                    try:
                        cands = page.evaluate(TOPBAR_CANDIDATES_JS) or []
                    except Exception:
                        cands = []
                self.say(f"…等待中 {self.budget.login_wait_used:.0f}s/{self.args.login_wait:.0f}s "
                         f"classify={st} url={sanitize_url(m.get('url'))} "
                         f"name_hits={m.get('name_hits')} logout_hits={m.get('logout_hits')}"
                         + (f" 顶栏候选={cands[:5]}" if cands is not None else ""))
            if st == "LOGGED_IN":
                self.log_event(event="login_wait_end", outcome="LOGGED_IN",
                               waited_s=round(self.budget.login_wait_used, 1))
                reason = ("扫码后账户姓名命中+内页导航成立"
                          + (f"（+退出入口 x{m.get('logout_hits', 0)}）" if m.get("logout_hits") else "（顶栏无显式退出钮）")
                          + (f"；二维码刷新 {qr_refreshes} 次" if qr_refreshes else ""))
                self.checks["c1_entry_login"].update(
                    status=PASS, reason=reason,
                    evidence=[self.shot(page, "after_login.png")])
                self.budget.tech_resume()
                return PASS
        self.log_event(event="login_wait_end", outcome="STILL_BLOCKED",
                       waited_s=round(self.budget.login_wait_used, 1))
        # 诊断辅助：超时时刻顶栏疑似账户姓名候选（不参与判定，只给活体线索）
        try:
            cands = page.evaluate(TOPBAR_CANDIDATES_JS) or []
        except Exception:
            cands = []
        self.log_event(event="login_wait_timeout_candidates", candidates=cands)
        # DOM 正文快照：姓名判定的最终真相源（截图视觉识读已被 attempt_002 证伪一次）
        try:
            self.save("timeout_body_innertext.txt",
                      page.evaluate("() => document.body ? document.body.innerText.slice(0, 30000) : ''") or "")
        except Exception:
            pass
        reason = "登录等待窗口内未观测到账户证据"
        if cands:
            reason += f"；顶栏疑似姓名候选={cands}（若其中是操作账号本人，检查 --expect-name 是否写对）"
        self.checks["c1_entry_login"].update(status=BLOCKED, reason=reason,
                                             evidence=[self.shot(page, "login_gate_timeout.png")])
        return BLOCKED

    def _pick_relay(self, rows):
        """列表盘点后的人机接力（--interactive-pick）：写 pick_request.json，轮询 pick_reply.txt
        （单行：单据编号 或 NONE）。同一浏览器会话内续跑——重启进程会丢会话级 SSO cookie，
        每轮重扫码的成本由这里省掉（2026-10-21 attempt_002/003 实证 cookie 会话级）。"""
        req = self.attempt / "pick_request.json"
        reply = self.attempt / "pick_reply.txt"
        io.open(req, "w", encoding="utf-8").write(json.dumps({
            "ask": "请指定目标单据编号；回复写入 pick_reply.txt（单行：编号 或 NONE）",
            "rows": rows, "reply_file": str(reply),
            "pick_wait_s": getattr(self.args, "pick_wait", 0)}, ensure_ascii=False, indent=1))
        self.say(f"PICK 等待人机接力 → {req.name}（回复 pick_reply.txt；上限 {getattr(self.args, 'pick_wait', 0):.0f}s）")
        self.log_event(event="pick_wait_start", pick_wait_cap=getattr(self.args, "pick_wait", 0))
        self.budget.tech_pause()
        t0 = time.monotonic()
        chosen = None
        try:
            while time.monotonic() - t0 < getattr(self.args, "pick_wait", 0):
                time.sleep(2.0)
                try:
                    if reply.exists():
                        txt = io.open(reply, encoding="utf-8").read().strip()
                        if txt:
                            chosen = None if txt.upper() == "NONE" else txt.split()[0]
                            break
                except Exception:
                    pass
        finally:
            self.budget.tech_resume()
        self.log_event(event="pick_wait_end", waited_s=round(time.monotonic() - t0, 1), chosen=chosen)
        self.say(f"PICK 结果: {chosen or '无选择→按 TARGET_UNSPECIFIED 收尾'}")
        return chosen

    def phase_locate(self):
        self.budget.ensure_tech(10)
        page = self.page
        page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        rows = page.evaluate(GRID_ROWS_JS)
        scope = {
            "url": sanitize_url(page.url),
            "rows_on_first_page": len(rows),
            "filters_visible": page.evaluate(
                "() => [...document.querySelectorAll('input,select')].slice(0,40)"
                ".map(i => (i.name||i.id||'') + '=' + ((i.type==='password')?'<masked>':(i.value||'')).slice(0,30))"
                ".filter(s => s && s !== '=')"),
            "note": "查询范围=默认列表首屏；未翻页、未改筛选。『未发现』仅指该范围。",
        }
        self.result["list_scope"] = scope
        self.say(f"locate rows={len(rows)} (默认首屏)")
        self.save("list_rows.json", json.dumps(rows, ensure_ascii=False, indent=1))
        self.shot(page, "list.png"); self.save_html(page, "list.html")
        if self.args.doc_id is None and getattr(self.args, "interactive_pick", False):
            chosen = self._pick_relay(rows)
            if chosen:
                self.args.doc_id = chosen          # 用户拍板后原地续跑；后续阶段/检查项均用该编号
                self.result["locate_picked_interactively"] = chosen
                self.log_event(event="pick_applied", doc_id=chosen)
        st, payload = pick_target(rows, self.args.doc_id)
        self.result["locate"] = {"status": st, **{k: v for k, v in payload.items() if k != "row"}}
        if st != "OK":
            reason = {
                "TARGET_UNSPECIFIED": "未提供 --doc-id：按约不自动选择替身单据，停在列表盘点",
                "NOT_FOUND": f"该查询范围内未发现单据 {self.args.doc_id}（默认首屏 {len(rows)} 行）",
                "AMBIGUOUS": f"单据 {self.args.doc_id} 命中 {payload.get('matches')} 行，歧义停止",
            }[st]
            self.checks["c2_locate_target"].update(
                status=(BLOCKED if st == "TARGET_UNSPECIFIED" else FAIL), reason=reason,
                evidence=[f"{self.attempt.name}/evidence/list_rows.json"])
            return BLOCKED if st == "TARGET_UNSPECIFIED" else FAIL
        row = payload["row"]
        self.result["locate"]["row_cells"] = row["cells"]
        self.checks["c2_locate_target"].update(status=PASS, reason=f"唯一命中单据 {self.args.doc_id}",
                                               evidence=[f"{self.attempt.name}/evidence/list_rows.json"])
        self.target_row = row
        return PASS

    def phase_structure(self):
        self.budget.ensure_tech(10)
        page = self.page
        row = getattr(self, "target_row", None)
        if not row:
            return FAIL
        if row.get("href"):
            assert_internal(row["href"])
            page.goto(row["href"], wait_until="domcontentloaded", timeout=45000)
        else:
            # 行内单据编号链接无 href 时点该行首个链接（纯导航；单据为已结束态=查看模式）
            with page.expect_navigation(timeout=45000):
                page.locator("a").filter(has_text=self.args.doc_id).first.click()
        page.wait_for_timeout(3500)
        st, m, _ = self.login_state(page)
        if st != "LOGGED_IN":
            self.checks["c3_structure"].update(status=FAIL, reason=f"进入单据页后身份丢失({st})",
                                               evidence=[self.shot(page, "target_view_lost.png")])
            return FAIL
        frames_report = []
        for fr in page.frames:
            try:
                blocks = fr.evaluate(BLOCKS_READ_JS) if fr is not page.main_frame else page.evaluate(BLOCKS_READ_JS)
            except Exception:
                continue
            found = [b for b in blocks.get("blocks", []) if b.get("found")]
            if found:
                frames_report.append({"frame": fr.url and sanitize_url(fr.url), "blocks": blocks})
        if not frames_report:
            self.checks["c3_structure"].update(
                status=FAIL, reason="目标页未读到任何已知区块（不做 type=new 回退）",
                evidence=[self.shot(page, "target_view.png"), self.save_html(page, "target_view.html")])
            return FAIL
        self.result["structure"] = frames_report
        self.save("target_blocks.json", json.dumps(frames_report, ensure_ascii=False, indent=1))
        # 代表性字段实读（显示值）：合计与银行行（控制台脱敏）
        flat = json.dumps(frames_report, ensure_ascii=False)
        self.result["structure_reads_ok"] = bool(re.search(r"(报销|合计|收款人|账号|银行)", flat))
        self.shot(page, "target_view.png"); self.save_html(page, "target_view.html")
        self.checks["c3_structure"].update(
            status=PASS, reason=f"{len(frames_report)} 个 frame 读到区块与行/列/编辑器实值",
            evidence=[f"{self.attempt.name}/evidence/target_blocks.json", f"{self.attempt.name}/evidence/target_view.png"])
        return PASS

    # ---- 填写任务（--fill-plan 授权：新建报销单，只填不存） ----
    def _click_guard(self, what):
        """文本类点击守卫：目标名命中禁点词一律拒绝（防误触 保存/发送/流转/返回 等）。
        空白先抹平再比对，防「上 传」内嵌空格绕过包含判断。"""
        w = re.sub(r"\s+", "", _norm_cell(what))
        if not w or any(bad in w or w in bad for bad in NO_SAVE_WORDS if bad):
            raise RuntimeError(f"NO_SAVE_GUARD: 拒绝点击「{what}」")
        return True

    def _safe_eval_frame(self, frame, js, arg=None):
        try:
            return frame.evaluate(js, arg) if arg is not None else frame.evaluate(js)
        except Exception as e:
            return {"eval_error": repr(e)}

    def _form_frame(self, page):
        """承载表单的 frame：主 frame 优先，否则遍历子 frame（structure 阶段实证内容可能在 iframe）。"""
        frames = [page.main_frame] + [f for f in page.frames if f is not page.main_frame]
        for fr in frames:
            m = self._safe_eval_frame(fr, FORM_READY_JS)
            if isinstance(m, dict) and (m.get("spreads") or m.get("dom_fields")):
                return fr, m
        return page.main_frame, None

    def _locate_cell(self, spreads, key, base=None):
        """在 SpreadJS 文本快照中定位 key 所在格 → (wb, sheet, row, col)。
        key 支持『a/b』多别名；精确匹配优先于包含；base=(wb,sheet,hr) 时同表同表头行的候选优先。"""
        alts = []
        for x in list(re.split(r"[/、]", str(key))) + [str(key)]:
            n = _norm_cell(x)
            if n and n not in alts:
                alts.append(n)

        def match_rank(text):
            t = _norm_cell(text)
            if not t:
                return 0
            if t in alts:
                return 2
            return 1 if any(a in t or t in a for a in alts) else 0

        cands = []
        for wi, w in enumerate(spreads):
            for si, sh in enumerate(w.get("sheets", [])):
                for ri, row in enumerate(sh.get("texts", [])):
                    for ci, t in enumerate(row):
                        m = match_rank(t)
                        if m:
                            same = bool(base) and wi == base[0] and si == base[1] and ri == base[2]
                            cands.append((same, m, -ri, wi, si, ri, ci))
        if not cands:
            return None
        cands.sort(reverse=True)   # 同表头带 → 精确匹配 → 行号靠上
        return tuple(cands[0][3:])

    def _spread_get(self, frame, wb, sheet, r, c):
        got = self._safe_eval_frame(frame, SPREAD_CELL_OP_JS,
                                    {"op": "get", "wb": wb, "sheet": sheet, "r": r, "c": c, "value": None})
        if not (isinstance(got, dict) and got.get("ok")):
            return ""
        if got.get("text") not in (None, ""):
            return str(got["text"])
        v = got.get("value")
        return "" if v in (None, "") else str(v)

    def _spread_write(self, page, frame, wb, sheet, r, c, value):
        """单元格写入：确保行存在 → API setValue → 回读校验；不一致再 激活编辑器+真实键盘
        （insertText 中文可靠）→ Enter → 回读。返回 {method, readback, match}。"""
        try:
            frame.evaluate(SPREAD_CELL_OP_JS, {"op": "grow", "wb": wb, "sheet": sheet,
                                               "r": r, "c": c, "value": None})
            frame.evaluate(SPREAD_CELL_OP_JS, {"op": "set", "wb": wb, "sheet": sheet,
                                               "r": r, "c": c, "value": value})
        except Exception as e:
            return {"method": "api_error", "readback": "", "match": False, "error": repr(e)[:160]}
        got = self._spread_get(frame, wb, sheet, r, c)
        if fill_match(got, value):
            return {"method": "api_setValue", "readback": got, "match": True}
        # 交互回退：startEdit → 编辑器全选 → insertText → Enter（任何一步不成立即停，绝不盲打）
        try:
            st = self._safe_eval_frame(frame, SPREAD_CELL_OP_JS,
                                       {"op": "startEdit", "wb": wb, "sheet": sheet,
                                        "r": r, "c": c, "value": None})
            if not (isinstance(st, dict) and st.get("ok")):
                return {"method": "api_setValue_mismatch", "readback": got, "match": False}
            if frame.evaluate(EDITOR_STATE_JS) is None:
                return {"method": "api_setValue_mismatch", "readback": got, "match": False}
            page.keyboard.insert_text(str(value))
            page.wait_for_timeout(250)
            page.keyboard.press("Enter")
            page.wait_for_timeout(350)
        except Exception as e:
            return {"method": "keyboard_error", "readback": got, "match": False, "error": repr(e)[:160]}
        got2 = self._spread_get(frame, wb, sheet, r, c)
        return {"method": "keyboard_edit", "readback": got2, "match": fill_match(got2, value)}

    def _spread_clear(self, frame, wb, sheet, r, c):
        """只清自己误写入的格（标签邻格试探失败后回收），不做其它删除。"""
        try:
            frame.evaluate(SPREAD_CELL_OP_JS, {"op": "set", "wb": wb, "sheet": sheet,
                                               "r": r, "c": c, "value": None})
        except Exception:
            pass

    def _find_dom_field(self, dom_fields, label):
        """DOM 输入定位：name/前置文本/所在行文本 与 label 归一互含。返回序号或 None。"""
        ln = _norm_cell(label)
        for f in dom_fields:
            for probe in (f.get("name"), f.get("prev_text"), f.get("row_text")):
                pn = _norm_cell(probe)
                if pn and (ln == pn or ln in pn or pn in ln):
                    return f["i"]
        return None

    def _fill_one(self, page, frame, dom_fields, spreads, section, label, value, mode="beside"):
        """单字段填写：SpreadJS 优先（label 邻格 beside / 列头向下 below），DOM 输入兜底；
        已是目标值则跳过（already）。逐字段产出回读记录。"""
        rec = {"section": section, "field": label, "target": value}
        if spreads:
            loc = self._locate_cell(spreads, label)
            if loc:
                wb, sh, r, c = loc
                tr, tc = (r + 1, c) if mode == "below" else (r, c + 1)
                cur = self._spread_get(frame, wb, sh, tr, tc)
                if fill_match(cur, value):
                    return {**rec, "surface": "spreadjs", "cell": [tr, tc],
                            "method": "already", "readback": cur, "match": True}
                res = self._spread_write(page, frame, wb, sh, tr, tc, value)
                if res.get("match"):
                    return {**rec, "surface": "spreadjs", "cell": [tr, tc], **res}
                if mode != "below":   # beside 不中：清掉试探值，换 label 下方格再试（布局可能纵排）
                    self._spread_clear(frame, wb, sh, tr, tc)
                    res2 = self._spread_write(page, frame, wb, sh, r + 1, c, value)
                    if res2.get("match"):
                        return {**rec, "surface": "spreadjs", "cell": [r + 1, c], **res2}
                return {**rec, "surface": "spreadjs", "cell": [tr, tc], **res}
        di = self._find_dom_field(dom_fields, label)
        if di is not None:
            try:
                loc_el = frame.locator(DOM_FIELD_CSS).nth(di)
                cur = loc_el.evaluate("el => el.value || ''")
                if fill_match(cur, value):
                    return {**rec, "surface": "dom", "method": "already", "readback": cur, "match": True}
                if (dom_fields[di] or {}).get("tag") == "SELECT":
                    loc_el.select_option(label=value)
                else:
                    loc_el.fill(value)
                got = loc_el.evaluate("el => el.value || ''")
                return {**rec, "surface": "dom", "method": "fill", "readback": got,
                        "match": fill_match(got, value)}
            except Exception as e:
                rec["dom_error"] = repr(e)[:160]
        rec.setdefault("status", "NOT_LOCATED")
        rec["match"] = False
        return rec

    def _fill_grid_row(self, page, frame, spreads, section, rowno, fields):
        """表格行填写：首列定位表头带（base 约束后续列同表同行），值写列头下第 1+rowno 行。"""
        out, base = [], None
        for k, v in fields.items():
            if str(k).startswith("_") or v is None:
                continue
            loc = self._locate_cell(spreads, k, base)
            if not loc:
                out.append({"section": section, "row": rowno, "field": k, "target": str(v),
                            "status": "NOT_LOCATED", "match": False})
                continue
            wb, sh, hr, c = loc
            base = (wb, sh, hr)
            tr, tc = hr + 1 + rowno, c
            cur = self._spread_get(frame, wb, sh, tr, tc)
            if fill_match(cur, str(v)):
                out.append({"section": section, "row": rowno, "field": k, "cell": [tr, tc],
                            "target": str(v), "surface": "spreadjs", "method": "already",
                            "readback": cur, "match": True})
                continue
            res = self._spread_write(page, frame, wb, sh, tr, tc, str(v))
            out.append({"section": section, "row": rowno, "field": k, "cell": [tr, tc],
                        "target": str(v), "surface": "spreadjs", **res})
        return out

    def _fill_bank_name(self, frame, spreads):
        """开户行：只接受系统按账号自动回显且含『中国银行』（联行号 104=中行 交叉印证）的值；
        否则留空给用户——支行全称 OCR 噪声、联行号不可见，按约不猜。"""
        rec = {"section": "bank", "field": "开户行", "target": "中国银行支行全称（用户终审）"}
        loc = self._locate_cell(spreads, "开户行")
        if not loc:
            return {**rec, "status": "NOT_LOCATED", "match": False}
        wb, sh, r, c = loc
        got = self._spread_get(frame, wb, sh, r + 1, c)
        if "中国银行" in _norm_cell(got):
            return {**rec, "surface": "spreadjs", "method": "auto_display", "readback": got,
                    "match": True, "note": "系统按账号自动回显，含中国银行（联行号104=中行 交叉印证）"}
        return {**rec, "surface": "spreadjs", "method": "LEFT_FOR_USER", "readback": got,
                "match": False, "status": "DEFERRED_TO_USER",
                "note": "未自动回显；支行全称无法唯一确定，按约不猜，留人工选择"}

    # ---- PrimeNG DOM 表面填写（attempt_006/007 实证：gc=false/spreads=0，Angular PrimeNG） ----
    def _ng_value(self, frame, comp_sel):
        """读组件当前显示值（input.value 或下拉/多选 label）。"""
        try:
            return frame.evaluate(NG_VALUE_JS, comp_sel)
        except Exception:
            return None

    # 下拉浮层选项选择器（attempt_014 拓宽）：PrimeNG 7/8 以 li 为主，兼 role=option / panel 内任意 li
    _OPT_SEL = ("li.ui-dropdown-item:visible, .ui-dropdown-items li:visible, "
                ".ui-multiselect-item:visible, .ui-multiselect-items li:visible, "
                ".ui-dropdown-panel li:visible, li[role='option']:visible")

    @staticmethod
    def _opt_norm(s):
        # 措辞归一：同词异写走 _word_norm（其它↔其他 / 差旅费↔差旅）；括号全半角
        return _word_norm(s).replace("（", "(").replace("）", ")").strip()

    def _pick_option(self, page, frame, comp_loc, value, kind):
        """p-dropdown / p-multiselect 浮层选择：点开 → 轮询等浮层出项（600ms×4，重开一次）→
        归一化精确/包含匹配（选项文本过守卫）→ 按索引点击。multiselect 选完 Escape 收起；
        找不到 → 记录可见选项 + 浮层诊断（面板文本/开合状态，脱敏）后 Escape 关闭返回 None。"""
        comp_loc.scroll_into_view_if_needed()

        def options():
            # 返回 [(idx, text)]；idx 供命中后原位点击（has_text 子串匹配会误中更长选项）
            cands = page.locator(self._OPT_SEL)
            n = cands.count()
            if n == 0:
                return []
            out = []
            for i in range(min(n, 60)):
                try:
                    out.append((i, (cands.nth(i).inner_text() or "").strip().replace("\n", " ")))
                except Exception:
                    continue
            return out

        def panel_diag():
            try:
                cnt = page.locator(".ui-dropdown-panel:visible, .ui-multiselect-panel:visible").count()
                txt = ""
                if cnt:
                    p_loc = page.locator(".ui-dropdown-panel:visible, .ui-multiselect-panel:visible").first
                    txt = (p_loc.inner_text() or "").strip().replace("\n", " | ")[:300]
                return cnt, txt
            except Exception:
                return -1, ""

        opts = []
        attempt_i = 0
        for attempt_i in range(2):          # attempt_013 实证首点可能未开出浮层：重开一次
            comp_loc.click()
            for _ in range(4):              # 浮层渲染异步：attempt_013 的 600ms 一次读为空
                page.wait_for_timeout(600)
                opts = options()
                if opts:
                    break
            if opts:
                break
        v = self._opt_norm(value)
        hit_idx = None
        opt_txt = None
        for mode in ("exact", "contains"):
            for i, t in opts:
                tn = self._opt_norm(t)
                if mode == "exact":
                    hit = tn == v
                else:                       # 包含：任一方向包含（≥2字防单字误配）
                    hit = v in tn or (len(tn) >= 2 and tn in v)
                if hit:
                    hit_idx, opt_txt = i, t
                    break
            if hit_idx is not None:
                break
        if hit_idx is None:
            # 未命中如实记录当时可见选项 + 浮层开合/面板文本（脱敏）——面板文本即真实词表，
            # 供审核判断是措辞差异还是真无此选项，也供下一轮取词
            pcnt, ptxt = panel_diag()
            self.log_event(event="fill_pick_miss", target=mask(str(value)),
                           options=[mask(t)[:40] for _, t in opts[:15]],
                           panel_open=pcnt, panel_text=mask(ptxt)[:300], reopened=attempt_i)
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
            return None
        self._click_guard(opt_txt)
        page.locator(self._OPT_SEL).nth(hit_idx).click()
        page.wait_for_timeout(400)
        if kind == "multiselect":
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            except Exception:
                pass
        return opt_txt

    def _ng_write(self, page, frame, field, value):
        """按 FORM_MAP 条目写入 → (status, readback, method)。dropdown/multiselect 浮层选择；
        calendar fill+回车；其余 fill/select_option。"""
        ftype = field.get("type")
        try:
            if ftype in ("dropdown", "multiselect") and field.get("comp"):
                with self._timing("pick_option", kind=str(ftype)):
                    picked = self._pick_option(page, frame, page.locator(field["comp"]).first, value, ftype)
                if picked is None:
                    return "OPTION_NOT_FOUND", None, "overlay_pick"
                return "OK", self._ng_value(frame, field["comp"]), "overlay_pick"
            loc = page.locator(field["sel"]).first
            if ftype == "select":
                loc.select_option(str(value))
                return "OK", loc.input_value(), "select_option"
            loc.scroll_into_view_if_needed()
            loc.click()
            loc.fill(str(value))
            page.keyboard.press("Enter")     # calendar 弹层收起；普通 input 无副作用
            page.wait_for_timeout(300)
            return "OK", loc.input_value(), "fill"
        except Exception as e:
            return f"WRITE_ERROR:{str(e)[:80]}", None, ftype or "?"

    def _fill_ng_labeled(self, page, frame, fields, section, label, value):
        """label（含别名）解析 FORM_MAP 字段并写入；只读自动带出格只读回读比对。"""
        rec = {"section": section, "field": label, "target": value, "surface": "primeNg"}
        f = _resolve_ng_field(fields, label)
        if f is None:
            return {**rec, "status": "NOT_LOCATED", "match": False}
        rec.update(name=f.get("name"), label_matched=f.get("label"))
        if f.get("readonly"):
            cur = self._ng_value(frame, f.get("comp") or f.get("sel"))
            return {**rec, "status": "READONLY_AUTO", "readback": cur,
                    "match": bool(fill_match(cur, value)), "note": "只读自动带出，未写入"}
        st, rb, method = self._ng_write(page, frame, f, value)
        rec.update(method=method)
        if st != "OK":
            return {**rec, "status": st, "match": False}
        rec.update(readback=rb, match=fill_match(rb, value))
        if not rec["match"]:
            rec["status"] = "MISMATCH"
        return rec

    def _ng_eval_tables(self, frame):
        try:
            r = frame.evaluate(TABLE_MAP_JS)
            return r or []
        except Exception:
            return []

    def _table_by_prop(self, frame, prop, title_hint=None):
        """prop-* 列头定位表格；title_hint 面板标题兜底。"""
        tables = self._ng_eval_tables(frame)
        for t in tables:
            if any(h.get("prop") == prop for h in t.get("headers", [])):
                return t
        if title_hint:
            hn = _norm_cell(title_hint)
            for t in tables:
                if hn and hn in _norm_cell(t.get("title")):
                    return t
        return None

    def _row_add(self, page, frame, prop, title_hint=None):
        """点面板标题栏『新增』（过守卫）扩一行/开行编辑弹窗；返回最新表格映射。
        022 教训：残留弹窗的 ui-dialog-mask 会拦截 新增 点击直到 45s 超时崩局——
        点前防御性清场（同 _cell_table_pick）。"""
        with self._timing("row_add", prop=str(prop)):
            t = self._table_by_prop(frame, prop, title_hint)
            if t is None or not t.get("add_sel"):
                return t
            if self._visible_dialog(frame) is not None or self._overlay_open(frame):
                self._dialog_close_guarded(page)
                page.wait_for_timeout(400)
            self._click_guard("新增")
            page.locator(t["add_sel"]).first.click()
            page.wait_for_timeout(1200)
            return self._table_by_prop(frame, prop, title_hint)

    def _cell_loc(self, page, t, rowno, ci):
        # 数据行在 body 表（scrollable 结构 thead/tbody 分表），列序与 header 表 colgroup 一一对应
        return page.locator(t.get("body_sel") or t["sel"]).first \
            .locator("tbody tr").nth(rowno).locator("td").nth(ci)

    def _cell_info(self, frame, cell):
        # 先 count()（瞬时、不等待）——行/格不存在时 element_handle() 会烧满 45s 默认超时
        try:
            if cell.count() == 0:
                return {}
            return frame.evaluate(CELL_INFO_JS, cell.element_handle()) or {}
        except Exception:
            return {}

    def _cell_settle_read(self, page, frame, cell):
        """读格文本；空则 Tab 触发 blur 提交再读（attempt_013 实证：日历格 fill+回车后
        截图已见 2026-09-22 而即时回读为空——回显滞后）。共读 3 次，每次间隔 500ms。"""
        txt = (self._cell_info(frame, cell)).get("text")
        for _ in range(2):
            if txt:
                return txt
            try:
                page.keyboard.press("Tab")
            except Exception:
                pass
            page.wait_for_timeout(500)
            txt = (self._cell_info(frame, cell)).get("text")
        return txt

    def _fill_ng_cell(self, page, frame, cell, value):
        """单格写入 → (status, readback)。dropdown/multiselect 组件浮层选择；
        其余 dblclick/click 激活编辑器后 fill+回车；激活不出编辑器 → CELL_NOT_EDITABLE 如实报。"""
        info = self._cell_info(frame, cell)
        kind = info.get("kind")
        try:
            if kind in ("dropdown", "multiselect"):
                comp = cell.locator(".ui-dropdown, .ui-multiselect").first
                if comp.count() == 0:
                    return "CELL_NOT_EDITABLE", info.get("text")
                with self._timing("pick_option", kind=str(kind)):
                    picked = self._pick_option(page, frame, comp, value, kind)
                if picked is None:
                    return "OPTION_NOT_FOUND", info.get("text")
                page.wait_for_timeout(300)
                return "OK", self._cell_settle_read(page, frame, cell)
            for ai, act in enumerate(("dblclick", "click"), 1):
                t_act = time.perf_counter()
                try:
                    with self._timing("cell_activate", act=str(act),
                                      attempt=ai, attempts=2):
                        getattr(cell, act)()
                    page.wait_for_timeout(500)
                except Exception as e:
                    # D2（2026-10-23）吞掉前留痕：异常类型+该次耗时+继续行为（语义
                    # 不变仍 continue）；timing 子事件另带 outcome=timeout|error——
                    # 内层捕获自此在事件层可见，外层 cell_fill 仍可 outcome=ok
                    self.log_event(event="inner_exc", where="cell_activate",
                                   act=str(act), attempt=ai, attempts=2,
                                   exc=type(e).__name__,
                                   dur_ms=round((time.perf_counter() - t_act) * 1000),
                                   behavior="continue_next_act")
                    continue
                # attempt_018：『是否为最后一次』类格——p-dropdown 组件 dblclick 进编辑态
                # （ui-editing-cell）才挂载（017 终局 DOM 实证），入口的静态探测看不到
                # → 激活后再探一次组件，避免误报 CELL_NOT_EDITABLE
                for kind_c, comp_sel in (("dropdown", ".ui-dropdown"),
                                         ("multiselect", ".ui-multiselect")):
                    comp = cell.locator(comp_sel).first
                    if comp.count():
                        with self._timing("pick_option", kind=str(kind_c)):
                            picked = self._pick_option(page, frame, comp, value, kind_c)
                        if picked is None:
                            return "OPTION_NOT_FOUND", info.get("text")
                        page.wait_for_timeout(300)
                        return "OK", self._cell_settle_read(page, frame, cell)
                inp = cell.locator("input:not([type='hidden']), textarea, select").first
                try:
                    if inp.count():
                        st = inp.evaluate(
                            "el => ({tag: el.tagName, ro: !!(el.readOnly || el.disabled)})")
                        # D4-b（2026-10-23）actionability 预判：readonly/disabled 的挂载
                        # input（预算科目等只读回显列）fill/select_option 会等满默认
                        # 45s 才超时（round-1 L466 cell_fill 91803ms=45s×2 定论）。
                        # evaluate 对在挂元素即时返回；仅凭「当前没有 input」不判只读，
                        # 必须见到 readOnly/disabled 阳性证据才跳过该次写入——值由
                        # 预算联动带出+回读核验（budget_respected 不变）；双击后才挂载
                        # 的可写编辑器 ro=False，照常 fill 不误伤。
                        if st.get("ro"):
                            self.log_event(event="cell_input_skip", act=str(act),
                                           attempt=ai, attempts=2,
                                           reason="readonly_or_disabled",
                                           note="挂载输入框只读/禁用：跳过 fill 死等路径")
                            continue
                        if st.get("tag") == "SELECT":
                            # 显式 8s 局部短超时（先例：行点击 timeout=8000），不再
                            # 等满全局默认 45s
                            with self._timing("cell_input_write", how="select_option",
                                              attempt=ai, attempts=2):
                                inp.select_option(str(value), timeout=8000)
                        else:
                            with self._timing("cell_input_write", how="fill",
                                              attempt=ai, attempts=2):
                                inp.fill(str(value), timeout=8000)
                            page.keyboard.press("Enter")
                        page.wait_for_timeout(400)
                        return "OK", self._cell_settle_read(page, frame, cell)
                except Exception as e:
                    # D2（2026-10-23）吞掉前留痕：timing 子事件 cell_input_write 含
                    # outcome=timeout|error/exc/dur_ms（被吞的内层异常自此可见）
                    self.log_event(event="inner_exc", where="cell_input_write",
                                   act=str(act), attempt=ai, attempts=2,
                                   exc=type(e).__name__,
                                   behavior="continue_next_act")
                    continue
            return "CELL_NOT_EDITABLE", info.get("text")
        except Exception as e:
            return f"CELL_ERROR:{str(e)[:80]}", info.get("text")

    def _visible_dialog(self, frame):
        try:
            dl = frame.evaluate(DIALOG_DUMP_JS) or []
        except Exception:
            return None
        return dl[0] if dl else None

    def _overlay_dump(self, frame):
        try:
            with self._timing("overlay_dump"):
                return frame.evaluate(OVERLAY_DUMP_JS) or []
        except Exception as e:
            return [{"err": str(e)[:120]}]

    def _overlay_open(self, frame):
        """当前有内容（输入框或行）的浮层清单——区分『无浮层』与『有浮层没命中』。"""
        return [c for c in self._overlay_dump(frame)
                if isinstance(c, dict) and not c.get("err")
                and (c.get("input_sel") or (c.get("rows") or 0) > 0)]

    def _pick_candidates(self, frame):
        """选点候选合并（attempt_018）：OVERLAY_DUMP_JS 的 position+尺寸过滤会漏掉
        p-dialog 弹表（panel_open=true 而 fill_overlay_dump 空）——DIALOG_DUMP_JS 抓
        得到的容器逐个做容器内补扫（DIALOG_SCOPE_DUMP_JS），与浮层清单去重合并后
        喂同一条两段式选行流。任何一源失败不影响另一源。"""
        with self._timing("pick_candidates"):
            cands = [c for c in self._overlay_dump(frame)
                     if isinstance(c, dict) and not c.get("err")]
            seen = {c.get("sel") for c in cands}
            try:
                dl = frame.evaluate(DIALOG_DUMP_JS) or []
            except Exception:
                dl = []
            for d in dl:
                if not isinstance(d, dict) or not d.get("sel") or d.get("sel") in seen:
                    continue
                try:
                    # H1 计时候选（45s 间隙）：element_handle() 无显式超时，行不存在时烧满默认 45s
                    with self._timing("dialog_element_handle", dsel=str(d.get("sel"))[:60]):
                        eh = frame.locator(d["sel"]).first.element_handle()
                    extra = frame.evaluate(DIALOG_SCOPE_DUMP_JS, eh)
                except Exception:
                    continue
                if extra and isinstance(extra, dict):
                    cands.append(extra)
                    seen.add(extra.get("sel"))
            return cands

    def _cell_button_open(self, page, frame, td, tag, shot=None):
        """格内 button-behind 开浮层（attempt_017）：按钮常 hover 才显、甚至 DOM 在而
        computed 隐藏（016 实证 button:visible 计 0 而截图按钮可见）→ 取 button/a 不筛
        可见性；常规 click(timeout=4000) 失败 → JS-click 兜底（绕过可见性/遮挡判定）；
        无按钮则试格点击本身。返回『是否真的开出了浮层/对话框』，方法与计数逐次留痕。"""
        method = ""
        try:
            with self._timing("cell_button_hover", where=str(tag)):
                td.hover(timeout=8000)
        except Exception as e:
            self.log_event(event="fill_cell_button", where=tag, stage="hover",
                           error=str(e)[:100])
        page.wait_for_timeout(400)
        btns = td.locator("button, a")
        n = btns.count()
        clicked = False
        if n:
            btn = btns.last
            try:
                btn.click(timeout=4000)
                method, clicked = "click", True
            except Exception as e1:
                try:
                    frame.evaluate("el => el.click()", btn.element_handle())
                    method, clicked = "js_click", True
                    self.log_event(event="fill_cell_button", where=tag,
                                   note=f"常规click失败已JS-click兜底：{str(e1)[:60]}")
                except Exception as e2:
                    self.log_event(event="fill_cell_button", where=tag, stage="click",
                                   error=f"{str(e1)[:60]}|js:{str(e2)[:60]}")
        if not clicked:
            try:
                td.click(timeout=4000)
                method = "cell_click"
                clicked = True
            except Exception as e:
                self.log_event(event="fill_cell_button", where=tag, stage="cell_click",
                               error=str(e)[:100])
        if not clicked:
            return False
        page.wait_for_timeout(1200)
        if shot:
            self.shot(page, shot)
        has = bool(self._overlay_open(frame)) or self._visible_dialog(frame) is not None
        self.log_event(event="fill_cell_button", where=tag, btn_count=n,
                       method=method, overlay_open=has)
        return has

    def _toast_read(self, frame):
        """读页面可见 toast（p-toast top-center）。"""
        try:
            return frame.evaluate(TOAST_JS) or None
        except Exception:
            return None

    def _cell_table_pick(self, page, frame, td, keyword, tag, shot=None, prescan=False,
                         first_data_row=False):
        """『选择表格数据』弹表选点流（attempt_018；017 DOM 实证定案）：p-celleditor
        可编辑格 dblclick 进编辑态（ui-editing-cell）→ 编辑模板现形 .tableselect
        inputgroup + button[aria-label=选择表格数据]；output 态可见的 external-link
        按钮是『选完跳原单』入口，值空时点了无操作——017 单号/预算单三次空点击的
        根因。点开弹表后先读 toast（链式门槛如『请先选择一个预算单』以 toast 拦截
        而非浮层），面板开着才走两段式选行。返回 (是否选中, 说明)。"""
        # 防御性清场（018 教训）：残留弹窗的模态遮罩会让 dblclick 永远超时
        if self._visible_dialog(frame) is not None or self._overlay_open(frame):
            self._dialog_close_guarded(page)
            page.wait_for_timeout(400)
        try:
            with self._timing("table_pick_dblclick", where=str(tag)):
                td.dblclick(timeout=4000)
        except Exception as e:
            self.log_event(event="fill_table_pick", where=tag, stage="dblclick",
                           error=str(e)[:100])
            return False, "dblclick失败"
        page.wait_for_timeout(600)
        editing = False
        with self._timing("table_pick_editing_poll", where=str(tag)):
            for _ in range(3):
                try:
                    cls = td.get_attribute("class") or ""
                except Exception:
                    cls = ""
                if "ui-editing-cell" in cls:
                    editing = True
                    break
                page.wait_for_timeout(400)
        btn = td.locator("button[aria-label='选择表格数据'], .tableselect button").first
        if btn.count() == 0:
            self.log_event(event="fill_table_pick", where=tag, editing=editing,
                           note="编辑态未现『选择表格数据』按钮")
            return False, "编辑态未现选择按钮"
        method = ""
        try:
            with self._timing("table_pick_btn", where=str(tag)):
                btn.click(timeout=4000)
                method = "click"
        except Exception as e1:
            try:
                with self._timing("table_pick_btn_js", where=str(tag)):
                    frame.evaluate("el => el.click()", btn.element_handle())
                    method = "js_click"
            except Exception as e2:
                self.log_event(event="fill_table_pick", where=tag, stage="pick_btn",
                               error=f"{str(e1)[:60]}|js:{str(e2)[:60]}")
                return False, "选择按钮点击失败"
        page.wait_for_timeout(1200)
        toast = self._toast_read(frame)
        has = bool(self._overlay_open(frame)) or self._visible_dialog(frame) is not None
        if shot:
            self.shot(page, shot)
        self.log_event(event="fill_table_pick", where=tag, editing=editing, method=method,
                       panel_open=has, toast=toast)
        if toast:
            return False, "gated:" + ";".join(toast)[:80]
        if not has:
            return False, "选择面板未开"
        if self._overlay_search_pick(page, frame, keyword, tag, prescan=prescan,
                                     first_data_row=first_data_row):
            return True, "OK"
        return False, "弹表无命中"

    def _overlay_search_pick(self, page, frame, keyword, tag, prescan=False,
                             first_data_row=False):
        """搜索浮层通用选点流（attempt_017/019）：候选=浮层清单+弹窗容器补扫合并
        （_pick_candidates——p-dialog 弹表 position 过滤漏检的根治）。两段式：A) 有
        输入框的候选→填关键词+回车，再补点弹窗内显式『查询/搜索/检索』按钮（弹表
        带独立查询钮，回车未必触发服务端检索）；B) 全部候选（填词刷新后的 + 原始
        面板）行扫归一化命中→点行（021 起表头行一律跳过）。prescan=True 时先扫原始
        行（attempt_019 教训：小弹表搜索词会滤空数据行）。first_data_row=True 为
        授权替代专用（2026-10-22）：弹表已按单据类型过滤，初始数据行即目标集——
        不搜索直选首个含 8 位单号的数据行（021 实证：搜索框只匹配单据编号，词搜
        『公出』把表滤空、只剩含『公出事由』字样的表头，曾因此点中表头空提交）。
        命中行才点；候选内有白名单确认按钮才确认。无候选/无命中 → 守卫式关闭（含
        Escape 兜底）并如实返回 False，可见选项必留痕（fill_pick_miss）——绝不盲选。
        018 教训：早退路径也必须守卫关闭，否则残留弹窗的遮罩挡住后续单元格 dblclick。
        命中行原文存 self._last_pick_row（回读选中单号用；日志仍走 mask）。"""
        def _dump():
            return self._pick_candidates(frame)

        def _pick_row(c, r):
            """点行→选中态核验→白名单确认；返回命中行原文（事件脱敏、原文走
            fill_dialog_rows.jsonl）。021 实证：真数据行点击后 ui-state-highlight=True
            + footer 确定 → 回显成功；表头行点了无选中态、确定=空提交。"""
            row_loc = frame.locator(r["sel"]).first
            row_loc.click(timeout=8000)
            page.wait_for_timeout(600)
            # 选中态核验：行高亮/aria-selected；未选中→行内勾选框兜底
            highlighted, chk_method = False, ""
            # D4-a（2026-10-23）场景判据——点行后行是否仍挂在 DOM（count() 瞬时返回
            # 不等待，同型先例 _cell_info 守卫）：
            #  · 行已消失 =「点行即关」型 dropdown 浮层（单据类型）：行 detach 后
            #    get_attribute 会对失效定位器等满默认 45s（round-1 L365
            #    overlay_pick_row 45822ms 定论）。选中提交与否改由浮层状态核验：
            #    浮层已关 = 点击即选中提交（PrimeNG dropdown 语义）→ 走外层成功
            #    路径；浮层仍开 = 未提交 → 如实按未选中失败收口，不默认成功。
            #  · 行仍在 = 选中+确认式 p-dialog 弹表（单号弹表/预算联动）：沿用原
            #    选中态核验+白名单确认，行为不变（get_attribute 对在挂元素即时返回）。
            if row_loc.count() == 0:
                ov_open = bool(self._overlay_open(frame))
                highlighted = not ov_open
                chk_method = ("row_detached_overlay_open" if ov_open
                              else "row_detached_overlay_state")
                self.log_event(event="pick_row_detached", where=tag,
                               overlay_open=ov_open, chk=chk_method)
                if ov_open:
                    self._dump_rows_evidence(
                        tag, [],
                        note=f"DETACHED-UNCOMMITTED row={r.get('text')!r} "
                             f"overlay_open=True → 按未选中收口（不默认成功）")
                    return ""
            else:
                t_ver = time.perf_counter()
                try:
                    with self._timing("pick_row_verify", attempt=1, attempts=2):
                        cls = row_loc.get_attribute("class") or ""
                        aria = row_loc.get_attribute("aria-selected")
                    highlighted = ("ui-state-highlight" in cls) or (aria == "true")
                except Exception as e:
                    # D2（2026-10-23）吞掉前留痕：timing 子事件含 outcome/dur_ms，
                    # 原语义不变——仍落入勾选框兜底
                    self.log_event(event="inner_exc", where="pick_row_verify",
                                   attempt=1, attempts=2, exc=type(e).__name__,
                                   dur_ms=round((time.perf_counter() - t_ver) * 1000),
                                   behavior="pass_to_checkbox_fallback")
            if not highlighted:
                chk = row_loc.locator(
                    "input[type='checkbox'], input[type='radio'], "
                    ".ui-chkbox-box, .ui-radiobutton-box, p-tablecheckbox").first
                try:
                    if chk.count() > 0:
                        chk.click(timeout=4000)
                        chk_method, highlighted = "checkbox_fallback", True
                        page.wait_for_timeout(500)
                except Exception as e:
                    chk_method = f"chk_fail:{str(e)[:60]}"
            confirm_btn = ""
            for b in (c.get("buttons") or []):
                if b.get("text") in self._DIALOG_CONFIRM and not b.get("disabled"):
                    self._click_guard(b["text"])
                    frame.locator(b["sel"]).first.click(timeout=8000)
                    page.wait_for_timeout(800)
                    confirm_btn = b["text"]
                    break
            if not confirm_btn and c.get("sel"):
                # 022 实证兜底：抓取清单里没有确认钮（配额被空文本钮挤占/渲染晚）
                # → live 查弹窗 footer 按钮再确认
                try:
                    foot = frame.locator(c["sel"]).first.locator(
                        ".ui-dialog-footer button, .ui-dialog-footer a")
                    for i in range(foot.count()):
                        b = foot.nth(i)
                        txt = (b.inner_text(timeout=1000) or "").strip()
                        if txt in self._DIALOG_CONFIRM:
                            self._click_guard(txt)
                            b.click(timeout=8000)
                            page.wait_for_timeout(800)
                            confirm_btn = txt + "(footer_live)"
                            break
                except Exception:
                    pass
            picked_failed = False
            if confirm_btn and (self._visible_dialog(frame) is not None
                                or self._overlay_open(frame)):
                # 确认点了但弹窗仍在（未提交/业务拦截）→ 守卫关闭防遮罩泄漏挡死后续
                # 填写（022 的 ui-dialog-mask 拦截 新增 45s 超时根因），如实按未选中
                self._dialog_close_guarded(page)
                confirm_btn += "|dialog_still_open_guard_closed"
                picked_failed = True
            self.log_event(event="fill_overlay_row", where=tag,
                           row=mask(r.get("text") or "")[:80],
                           selected=highlighted, chk=chk_method or "-",
                           confirm=confirm_btn or "NONE_IN_CAPTURED")
            self._dump_rows_evidence(
                tag, [], note=f"PICKED row={r.get('text')!r} sel={r.get('sel')!r} "
                              f"highlighted={highlighted} chk={chk_method!r} "
                              f"confirm={confirm_btn!r} cand_btns="
                              f"{[b.get('text') for b in (c.get('buttons') or [])]}")
            return "" if picked_failed else (r.get("text") or "")

        def _is_thead(r):
            """021 实证：搜索词滤空数据行后，含关键词的表头（『公出事由』列名）会被
            当数据行点中——表头行绝不可选。"""
            return "thead" in (r.get("sel") or "")

        def _scan_pick(cands):
            """B) 行扫归一化命中（跳过表头）→点行→白名单确认；返回命中行原文或 None。"""
            for c in cands:
                for r in (c.get("row_list") or []):
                    if _is_thead(r):
                        continue
                    rn = self._opt_norm(r.get("text") or "")
                    if rn and (kn in rn or rn in kn):
                        with self._timing("overlay_pick_row", where=str(tag)):
                            return _pick_row(c, r) or None
            return None

        with self._timing("overlay_dump_candidates", where=str(tag)):
            cands = _dump()
        self.log_event(event="fill_overlay_dump", where=tag,
                       overlays=[{k: c.get(k) for k in ("cls", "title", "inputs", "rows", "tables")}
                                 for c in cands[:4]])
        self._dump_rows_evidence(tag, cands)
        if not cands:
            self._dialog_close_guarded(page)
            return False
        kn = self._opt_norm(str(keyword))
        if first_data_row:
            # 授权替代专用：首个非表头且含 8 位以上单号的数据行直选（含选中态核验
            # + 白名单确认），不进搜索两段式。_pick_row 失败路径已守卫关闭弹窗——
            # 直接按 miss 处理，绝不再点下一行（弹窗已不在）。
            for c in cands:
                for r in (c.get("row_list") or []):
                    if _is_thead(r):
                        continue
                    if re.search(r"\d{8,}", r.get("text") or ""):
                        with self._timing("overlay_pick_row_first", where=str(tag)):
                            hit_text = _pick_row(c, r)
                        if hit_text:
                            self._last_pick_row = hit_text
                            return True
                        break
                else:
                    continue
                break
            self._dump_rows_evidence(tag, cands, note="first_data_row_miss")
            self._dialog_close_guarded(page)
            return False
        try:
            # prescan：先扫原始行，命中即选（小弹表不过搜索）
            if prescan:
                with self._timing("overlay_prescan", where=str(tag)):
                    hit_text = _scan_pick(cands)
                if hit_text:
                    self._last_pick_row = hit_text
                    return True
            # A) 有输入框的候选：填词+回车（结果可能换容器挂载）+ 显式查询钮兜底
            inp = next((c for c in cands if c.get("input_sel")), None)
            if inp is not None:
                try:
                    with self._timing("overlay_search_fill", where=str(tag)):
                        frame.locator(inp["input_sel"]).first.fill(str(keyword), timeout=4000)
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(1500)
                except Exception as e:
                    self.log_event(event="fill_pick_click_error", where=tag,
                                   error=f"search_fill:{str(e)[:100]}")
                for b in (inp.get("buttons") or []):
                    if b.get("text") in ("查询", "搜索", "检索") and not b.get("disabled"):
                        try:
                            self._click_guard(b["text"])
                            with self._timing("overlay_search_btn", where=str(tag)):
                                frame.locator(b["sel"]).first.click(timeout=8000)
                                page.wait_for_timeout(1500)
                            self.log_event(event="fill_pick_search_btn", where=tag,
                                           btn=b["text"])
                        except Exception as e:
                            self.log_event(event="fill_pick_click_error", where=tag,
                                           error=f"search_btn:{str(e)[:100]}")
                        break
            # B) 全量候选行扫命中（016 修复：不再要求浮层带输入框）
            with self._timing("overlay_post_scan", where=str(tag)):
                post = _dump()
                hit_text = _scan_pick(post)
            if hit_text:
                self._last_pick_row = hit_text
                return True
            # 搜索后原始行文落盘（020 教训：miss 时也要知道搜索到底留下了什么）
            self._dump_rows_evidence(tag, post, note="post_search_miss")
            self.log_event(event="fill_pick_miss", where=tag, target=str(keyword)[:40],
                           options=[mask(r.get("text") or "")[:40]
                                    for c2 in _dump() for r in (c2.get("row_list") or [])][:12])
        except Exception as e:
            self.log_event(event="fill_pick_click_error", where=tag, error=str(e)[:160])
        self._dialog_close_guarded(page)
        return False

    def _dialog_close_guarded(self, page):
        """守卫式关闭弹窗：取消/关闭按钮（过守卫）→ Escape 兜底。"""
        for txt in ("取消", "关闭"):
            try:
                self._click_guard(txt)
                b = page.locator(".ui-dialog button", has_text=txt).last
                if b.count() and b.is_visible():
                    with self._timing("dialog_close_click", btn=str(txt)):
                        b.click()
                    page.wait_for_timeout(500)
                    return True
            except RuntimeError:
                continue
            except Exception:
                continue
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
        except Exception:
            pass
        return False

    _DIALOG_CONFIRM = ("确定", "确认", "选择", "选入", "插入", "完成")

    def _dialog_confirm(self, page, dlg):
        """弹窗确认按钮：文本在白名单且过守卫才点；否则 False（调用方守卫式关闭）。"""
        for b in (dlg.get("buttons") or []):
            if b.get("text") in self._DIALOG_CONFIRM and not b.get("disabled"):
                try:
                    self._click_guard(b["text"])
                    page.locator(b["sel"]).first.click()
                    page.wait_for_timeout(900)
                    return True
                except RuntimeError:
                    continue
                except Exception:
                    continue
        return False

    def _dialog_fill(self, page, frame, dlg, row, section):
        """行编辑弹窗：先验适用性（≥半数标签可解析才认为是本表的行编辑弹窗——attempt_010 教训：
        新增误开的是别表的选择弹窗，白名单确认会把值填错地方）；不适用→守卫式关闭记 DIALOG_WRONG；
        适用→scope=dialog 枚举填写 → 白名单确认；确认不可用则守卫式关闭并如实记。"""
        try:
            fields = frame.evaluate(FORM_MAP_JS, page.locator(dlg["sel"]).first.element_handle()) or []
        except Exception as e:
            self._dialog_close_guarded(page)
            return [{"section": section, "field": "_dialog",
                     "status": f"DIALOG_EVAL_ERROR:{str(e)[:80]}", "match": False}]
        labels = [str(k) for k in row.keys()
                  if not str(k).startswith("_") and row[k] is not None]
        resolved = sum(1 for k in labels if _resolve_ng_field(fields, k))
        if labels and resolved < max(1, len(labels) // 2):
            self._dialog_close_guarded(page)
            return [{"section": section, "field": "_dialog", "status": "DIALOG_WRONG",
                     "match": False,
                     "note": f"弹窗内可解析 {resolved}/{len(labels)} 标签，疑为别表选择弹窗，已守卫式关闭"}]
        recs = []
        for label, value in row.items():
            if str(label).startswith("_") or value is None:
                continue
            recs.append(self._fill_ng_labeled(page, frame, fields, section, label, str(value)))
        if self._dialog_confirm(page, dlg):
            return recs
        self._dialog_close_guarded(page)
        for r in recs:
            r.update(status="DIALOG_CONFIRM_GUARDED", match=False,
                     note="确认按钮未过守卫白名单或不可用，已关闭弹窗；行内值未落表")
        return recs

    def _fill_ng_table_row(self, page, frame, section, rowno, row, prop, title_hint=None):
        """p-table 行填写：行不足先『新增』（可能弹行编辑弹窗→_dialog_fill）；
        行始终不出现→ROW_NOT_CREATED + 诊断截图，绝不逐列空转 45s；逐列别名定位写入。"""
        recs = []
        base = {"section": section, "row": rowno, "surface": "primeNg"}
        t = self._table_by_prop(frame, prop, title_hint)
        if t is None:
            return [{**base, "field": str(prop), "status": "TABLE_NOT_FOUND", "match": False}]
        guard_n = 0
        dlg_tried = False
        with self._timing("row_add_loop", section=str(section), row=rowno):
            while (t.get("row_count") or 0) <= rowno and guard_n < 3:
                guard_n += 1
                t = self._row_add(page, frame, prop, title_hint) or t
                dlg = self._visible_dialog(frame)
                if dlg and not dlg_tried:
                    dlg_tried = True
                    drecs = self._dialog_fill(page, frame, dlg, row, section)
                    recs += drecs
                    if not any(r.get("status") == "DIALOG_WRONG" for r in drecs):
                        return recs
                    continue          # 错弹窗已守卫关闭：回到行数检查再试
                if (t.get("row_count") or 0) <= rowno:
                    page.wait_for_timeout(800)
        # 行仍未出现：整行如实记 + 诊断截图，不让 element_handle 烧 45s/列
        if (t.get("row_count") or 0) <= rowno:
            self.shot(page, f"fill_diag_{section}_r{rowno}.png")
            return recs + [{**base, "field": "*", "status": "ROW_NOT_CREATED",
                            "match": False,
                            "note": f"新增点击后行数仍为 {t.get('row_count')}；诊断截图已存"}]
        headers = t.get("headers", [])
        for label, value in row.items():
            if str(label).startswith("_") or value is None:
                continue
            rec = {**base, "field": label, "target": str(value)}
            ci = _table_col(headers, label)
            if ci is None:
                recs.append({**rec, "status": "COL_NOT_FOUND", "match": False})
                continue
            cell = self._cell_loc(page, t, rowno, ci)
            if cell.count() == 0:
                recs.append({**rec, "status": "CELL_MISSING", "match": False})
                continue
            cur = self._cell_info(frame, cell)
            if fill_match(cur.get("text"), str(value)):
                recs.append({**rec, "status": "ALREADY", "method": "prefilled",
                             "readback": cur.get("text"), "match": True})
                continue
            with self._timing("cell_fill", section=str(section), row=rowno, field=str(label)):
                st, rb = self._fill_ng_cell(page, frame, cell, str(value))
            recs.append({**rec, "status": st if st != "OK" else ("OK" if fill_match(rb, str(value)) else "MISMATCH"),
                         "readback": rb, "match": st == "OK" and fill_match(rb, str(value))})
        # 联动/滞后复核：预算部门/科目/项目等只读回显列可能在前序列（摘要/金额）填完后才被系统
        # 自动带出（attempt_013 CELL_NOT_EDITABLE×3 疑此）；空回读的失败记录静置后重读一次，
        # 命中如实改记 settle_reread——重读改判留痕，不做无据默认
        with self._timing("settle_reread", section=str(section), row=rowno):
            page.wait_for_timeout(800)
            t = self._table_by_prop(frame, prop, title_hint) or t
            headers = t.get("headers", headers)
            for r0 in recs:
                if r0.get("status") in ("CELL_NOT_EDITABLE", "MISMATCH") and not r0.get("readback") \
                        and r0.get("target") is not None:
                    ci2 = _table_col(headers, r0.get("field"))
                    if ci2 is None:
                        continue
                    cur2 = self._cell_info(frame, self._cell_loc(page, t, rowno, ci2))
                    if fill_match(cur2.get("text"), str(r0.get("target"))):
                        r0.update(status="OK", method="settle_reread",
                                  readback=cur2.get("text"), match=True,
                                  note="首读为空，静置后系统已带出/回显落定")
                    else:
                        r0.update(readback=cur2.get("text"))
        return recs

    def _fill_related_doc(self, page, frame, value):
        """关联公出单（attempt_018 定案流程；016/017 截图+DOM 实证）：空行『单据号』格
        button-behind 先开『单据类型』12 项下拉 → 选含模板词『公出』的行 → 单号选择
        走编辑态『选择表格数据』弹表（dblclick 进格现形真按钮）→ 选含单号的行 →
        白名单确认（若有）。精确单号 miss（原单已被一次性关联消耗，019 实证）→
        经用户 2026-10-22 授权改搜『公出』选首个公出行，选中单号以回读为准并明记
        替代。任一步无命中 → 守卫式关闭 + 如实记；终读以表体出现单号为准；绝不
        盲选。末列兜底已撤（016 实证其开的是『备注』弹窗）。"""
        rec = {"section": "header", "field": "关联公出单", "target": str(value), "surface": "primeNg"}
        t = self._table_by_prop(frame, "bizNumber", "关联单据")
        if t is None:
            return {**rec, "status": "TABLE_NOT_FOUND", "match": False}
        try:
            body = page.locator(t.get("body_sel") or t["sel"]).first.locator("tbody").inner_text() or ""
        except Exception:
            body = ""
        if str(value) in body:
            return {**rec, "status": "ALREADY", "method": "prefilled", "readback": str(value), "match": True}
        t = self._row_add(page, frame, "bizNumber", "关联单据") or t
        # attempt_015 实证：工具栏『插入』=插行不是选单入口；真入口是『单据号』格按钮
        picked = False
        ci_doc = _table_col(t.get("headers", []), "单据号")
        td = self._cell_loc(page, t, 0, ci_doc) if ci_doc is not None else None
        try:
            if td is not None and td.count():
                if self._cell_button_open(page, frame, td, "关联公出单",
                                          shot="fill_related_cell_pick.png"):
                    # 第 1 步：单据类型（关键词取模板词『公出』）
                    with self._timing("overlay_pick", where="关联单据/单据类型"):
                        ok_type = self._overlay_search_pick(page, frame, "公出", "关联单据/单据类型")
                    if ok_type:
                        page.wait_for_timeout(1200)
                        self.shot(page, "fill_related_type_picked.png")
                        # 第 2 步：单号——类型选定后若选择面未自动开出，走『选择表格数据』
                        # 弹表流（attempt_018；017 DOM 实证：单据号格 output 态只有
                        # external-link 跳转按钮，空单号点了无操作；真选择器在编辑态
                        # 模板 .tableselect 里，dblclick 进编辑态才现形）
                        if self._overlay_open(frame):
                            with self._timing("overlay_pick", where="关联单据/单号"):
                                picked = self._overlay_search_pick(page, frame, str(value),
                                                                   "关联单据/单号")
                        else:
                            with self._timing("table_pick", where="关联单据/单号"):
                                picked, _note = self._cell_table_pick(
                                    page, frame, td, str(value), "关联单据/单号",
                                    shot="fill_related_doc_pick.png")
                        # 授权替代（2026-10-22 用户）：原单据号已被一次性关联消耗，
                        # 选单列表不再出现（018/019 实证）——精确单号 miss 后改搜
                        # 模板词『公出』选首个公出行；选中单号取自命中行原文，终读
                        # 以它为准，事件/记录明记授权替代，绝不静默换值
                        if not picked:
                            with self._timing("table_pick", where="关联单据/单号-授权替代"):
                                picked, _note = self._cell_table_pick(
                                    page, frame, td, "公出", "关联单据/单号-授权替代",
                                    shot="fill_related_sub_pick.png",
                                    prescan=True, first_data_row=True)
                            if picked:
                                sub_row = getattr(self, "_last_pick_row", "") or ""
                                # 022 实证：行文日期与单号连排（…2026-07-2412026075605…），
                                # \d{8,} 会贪到拼接串——单号恒为 120 前缀 11 位（12026/25/
                                # 24/23 五例实证），优先 120\d{8}，退化才用 \d{8,}
                                sub_no = (re.search(r"120\d{8}", sub_row)
                                          or re.search(r"\d{8,}", sub_row))
                                if sub_no:
                                    value = sub_no.group(0)
                                    sub_note = "选中单号取自行文，终读以它为准"
                                else:
                                    sub_note = "命中行文无8位以上单号可提取——疑似非数据行（树节点/表头），保持原值"
                                rec["note"] = ("原单据号已被一次性关联消耗，经用户2026-10-22"
                                               "授权改选其他公出单；" + sub_note)
                                self.log_event(event="fill_related_substitute",
                                               where="关联单据/单号",
                                               row=mask(sub_row)[:80],
                                               doc_no=mask(str(value)))
        except Exception as e:
            self.log_event(event="fill_pick_click_error", where="关联公出单", error=str(e)[:160])
        if not picked:
            self._dialog_close_guarded(page)
            # 兜底：直填『单据号』格（历史 inline 兜底从未生效，保留但以终读为准）
            if ci_doc is not None:
                with self._timing("cell_fill", section="related_inline", row=0, field="单据号"):
                    st, rb = self._fill_ng_cell(page, frame, self._cell_loc(page, t, 0, ci_doc), str(value))
                rec.update(method="inline_cell", status=st if st != "OK" else
                           ("OK" if fill_match(rb, str(value)) else "MISMATCH"),
                           readback=rb, match=st == "OK" and fill_match(rb, str(value)))
        else:
            rec.update(method="type_then_doc_overlay")
        # 终读：表体是否含单号（弹表确定后回显有延迟，轮询 3×800ms）
        body2 = ""
        with self._timing("related_final_read"):
            for _ in range(3):
                t2 = self._table_by_prop(frame, "bizNumber", "关联单据")
                try:
                    body2 = page.locator(t2.get("body_sel") or t2["sel"]).first.locator("tbody").inner_text() or "" if t2 else ""
                except Exception:
                    body2 = ""
                if str(value) in body2:
                    break
                page.wait_for_timeout(800)
        if str(value) in body2:
            rec.update(readback=str(value), match=True)
            rec.pop("status", None) if rec.get("match") else None
        elif not rec.get("match"):
            rec.setdefault("status", "RELATED_DOC_NOT_CONFIRMED")
            rec["match"] = False
        return rec

    def _fill_bank_name_ng(self, page, frame):
        """开户行（PrimeNG 表面）：只认系统按账号自动回显含『中国银行』或联行号 104 前缀；
        否则尝试下拉选『中国银行』并以 104 复核；再不行 DEFERRED_TO_USER——支行全称按约不猜。"""
        rec = {"section": "bank", "field": "开户行", "target": "中国银行支行全称（用户终审）", "surface": "primeNg"}
        t = self._table_by_prop(frame, "payee", "银行")
        if t is None:
            return {**rec, "status": "TABLE_NOT_FOUND", "match": False}
        headers = t.get("headers", [])
        ci_bank = _table_col(headers, "开户行")
        ci_code = _table_col(headers, "联行号")

        def txt(ci):
            if ci is None:
                return None
            try:
                return (self._cell_info(frame, self._cell_loc(page, t, 0, ci))).get("text")
            except Exception:
                return None

        bank_txt, code_txt = txt(ci_bank), txt(ci_code)
        bn = _norm_cell(bank_txt or "")
        if "中国银行" in bn or bn == "中行" or str(code_txt or "").startswith("104"):
            note = "系统按账号自动回显，含中国银行/联行号104=中行 交叉印证"
            if bn == "中行" and not str(code_txt or "").startswith("104"):
                # attempt_013 截图实证：系统对该账号的回显形态就是简称『中行』——系统回显，非猜测
                note = "系统按账号自动回显『中行』（中国银行简称，非人工猜测）；联行号未显示"
            return {**rec, "status": "OK", "method": "auto_display",
                    "readback": f"{bank_txt} | 联行号 {code_txt}", "match": True, "note": note}
        if ci_bank is not None:
            with self._timing("cell_fill", section="bank", row=0, field="开户行下拉"):
                self._fill_ng_cell(page, frame, self._cell_loc(page, t, 0, ci_bank), "中国银行")
            page.wait_for_timeout(1000)
            bank_txt, code_txt = txt(ci_bank), txt(ci_code)
            if "中国银行" in _norm_cell(bank_txt or "") and str(code_txt or "").startswith("104"):
                return {**rec, "status": "OK", "method": "picker+104",
                        "readback": f"{bank_txt} | 联行号 {code_txt}", "match": True}
        return {**rec, "status": "DEFERRED_TO_USER",
                "readback": f"{bank_txt} | 联行号 {code_txt}", "match": False,
                "note": "支行全称无法唯一确定，按约不猜，留人工选择"}

    def _try_budget_pick(self, page, frame):
        """预算联动（attempt_018 重写；017 DOM+toast 实证定案）：预算列分两类——
        预算部门/预算归属/预算项目/科目总额/科目余额 是 readonly 回显格（td class
        含 readonly，无编辑器，选中预算单后系统带出）；可编辑的 预算单/预算科目 是
        p-celleditor 格，真入口是编辑态模板里的 button[aria-label=选择表格数据]
        （output 态的 external-link 按钮是选完跳原单用的，017 三次空点击根因）。
        链式门槛：预算科目被『✖ 请先选择一个预算单』toast 拦截 → 先预算单后科目。
        只搜模板原词（年度预算项目/科技中心/差旅），命中行才点，绝不盲选；
        每步回读预算列回显复核。"""
        def rec(st, **kw):
            return [{"section": "detail_summary", "field": "_budget_pick",
                     "status": st, "match": False, **kw}]
        ECHO_COLS = ("预算部门", "预算单", "预算科目", "预算项目")

        def echo_read():
            t2 = self._table_by_prop(frame, "reimItem", "报销明细")
            got = {}
            if t2:
                for c2 in ECHO_COLS:
                    ci2 = _table_col(t2.get("headers", []), c2)
                    if ci2 is not None:
                        got[c2] = _norm_cell((self._cell_info(
                            frame, self._cell_loc(page, t2, 0, ci2))).get("text") or "")
            return got

        t = self._table_by_prop(frame, "reimItem", "报销明细")
        if t is None:
            return rec("TABLE_NOT_FOUND", note="汇总表未找到")
        try:
            if page.locator(t.get("body_sel") or t["sel"]).first.locator("tbody tr").count() == 0:
                return rec("NO_ROW", note="汇总表无数据行")
            stages = []
            # 021 实证（fill_dialog_rows.jsonl）：预算单弹表候选 15625120077=2025年
            # 科技中心项目预算 / 76=2026年资产性预算 / 75=2026年日常费用预算（均科技
            # 中心）；77 的科目表只有 合作研发费/外购模具费/咨询服务费——不含模板词
            # 『差旅』。差旅费属日常费用类 → 按候选迭代：选预算单 → 开科目弹表
            # prescan『差旅』，命中才确认；全部候选无差旅 → 科目如实留空留审。
            # 科目确认恒为模板原词白名单；预算单选择词取自弹表实测主题词（日常
            # 费用优先），绝不选非差旅科目顶替。重复回显同一单号=候选已穷尽即停。
            BUDGET_KWS = ("日常费用", "差旅", "资产性", "项目预算", "科技中心")
            got = {}
            subject_ok = False
            ci_subj = _table_col(t.get("headers", []), "预算科目")
            picked_nos = []
            for bkw in BUDGET_KWS:
                ci = _table_col(t.get("headers", []), "预算单")
                if ci is None:
                    stages.append({"col": "预算单", "kw": bkw, "note": "列未找到"})
                    break
                stage = {"col": "预算单", "kw": bkw}
                stages.append(stage)
                td = self._cell_loc(page, t, 0, ci)
                with self._timing("table_pick", where="预算联动/预算单"):
                    ok, note = self._cell_table_pick(
                        page, frame, td, bkw, "预算联动/预算单",
                        shot="fill_budget_no_pick.png", prescan=True)
                stage.update(picked=ok, result=note)
                if not ok:
                    self.log_event(event="fill_budget_stage", **stage)
                    continue
                page.wait_for_timeout(1200)
                got = echo_read()
                stage["echo"] = " / ".join(f"{k}={v}" for k, v in got.items())
                self.log_event(event="fill_budget_stage", **stage)
                bno = re.search(r"\d{8,}", got.get("预算单") or "")
                if bno and bno.group(0) in picked_nos:
                    stage["note"] = "重复候选回显，候选已穷尽"
                    break
                if bno:
                    picked_nos.append(bno.group(0))
                # 科目：模板原词差旅（prescan 先扫初始行，019 教训）
                if ci_subj is None:
                    stages.append({"col": "预算科目", "kw": "差旅", "note": "列未找到"})
                    break
                td2 = self._cell_loc(page, t, 0, ci_subj)
                with self._timing("table_pick", where="预算联动/预算科目"):
                    ok2, note2 = self._cell_table_pick(
                        page, frame, td2, "差旅", "预算联动/预算科目",
                        shot="fill_budget_subject_pick.png", prescan=True)
                st2 = {"col": "预算科目", "kw": "差旅", "picked": ok2, "result": note2}
                stages.append(st2)
                self.log_event(event="fill_budget_stage", **st2)
                if ok2:
                    page.wait_for_timeout(1200)
                    got = echo_read()
                    if "差旅" in (got.get("预算科目") or ""):
                        subject_ok = True
                        break
                    st2["note"] = "选了差旅科目但回显未见差旅，换下一候选"
                # 未命中差旅 → 换下一张候选预算单（miss 路径已守卫关闭弹表）
            # 预算单选中后系统可能直接带出科目（含模板词 差旅）→ 补记 auto_echo
            if not subject_ok:
                got = got or echo_read()
                if "差旅" in (got.get("预算科目") or ""):
                    subject_ok = True
                    stages.append({"col": "预算科目", "note": "回显含模板词差旅",
                                   "picked": True, "result": "auto_echo"})
            if subject_ok:
                return [{"section": "detail_summary", "field": "_budget_pick",
                         "status": "OK", "match": True, "method": "cell_table_pick",
                         "target": "预算单→预算科目（科目=模板词差旅白名单）",
                         "readback": " / ".join(f"{k}={mask(v)}" for k, v in got.items()),
                         "stages": stages,
                         "note": "编辑态『选择表格数据』弹表；预算单按候选迭代，科目恒以"
                                 "模板词差旅确认，绝不选非差旅科目顶替"}]
            budget_picked = any(s.get("col") == "预算单" and s.get("picked") for s in stages)
            if budget_picked:
                return rec("SUBJECT_MISS_NOTED", method="cell_table_pick",
                           readback=" / ".join(f"{k}={mask(v)}"
                                               for k, v in (got or echo_read()).items()),
                           stages=stages,
                           note="所有候选预算单的科目表均无模板词『差旅』，科目留空留审；"
                                "各单科目见 fill_dialog_rows.jsonl，绝不选非差旅科目顶替")
            return rec("NO_OVERLAY", target="差旅（科目）", stages=stages,
                       note="预算单弹表未完成选择（fill_budget_stage 事件与"
                            " fill_budget_no_pick.png 可审）")
        except Exception as e:
            return rec(f"PICK_ERROR:{str(e)[:60]}")

    def _phase_fill_ng(self, page, frame, plan):
        """PrimeNG DOM 表面主流程：表头 label[for=name] 解析；p-table 按 prop-* 列头定位；
        表体空表先『新增』。只填不存；verdict 与 SpreadJS 路径同形。"""
        self.say("FILL 走 PrimeNG DOM 表面（p-table/p-dropdown/p-multiselect）")
        # Angular 异步绑定 name/label：goto 后立即枚举时可写字段常无名（attempt_010 教训）→
        # 轮询至「可写且带 name」字段出现，最多 ~15s
        fields = []
        with self._timing("ng_map_wait"):
            for attempt_i in range(6):
                try:
                    fields = frame.evaluate(FORM_MAP_JS) or []
                except Exception as e:
                    self.log_event(event="fill_ng_map_error", error=str(e)[:160])
                    break
                if any(f.get("name") and not f.get("readonly") for f in fields):
                    break
                self.log_event(event="fill_ng_field_wait", round=attempt_i,
                               named_writable=sum(1 for f in fields
                                                  if f.get("name") and not f.get("readonly")))
                page.wait_for_timeout(2500)
        # 表头区填写前再刷一次（表单初始化耗时不定，晚到的 name 绑定在此收敛）
        try:
            fields = frame.evaluate(FORM_MAP_JS) or fields
        except Exception:
            pass
        self.save("form_ng_map.json", json.dumps(
            {"fields": fields, "tables": self._ng_eval_tables(frame)}, ensure_ascii=False, indent=1))
        rb = []
        # 1) 表头区 + 项目说明（label 解析；关联公出单走专属路径）
        for section in ("header", "project_note"):
            with self._timing("section_fill", section=str(section)):
                for label, spec in (plan.get(section) or {}).items():
                    value = spec.get("value") if isinstance(spec, dict) else spec
                    if value is None or (section == "header" and label == "关联公出单"):
                        continue
                    rb.append(self._fill_ng_labeled(page, frame, fields, section, label, str(value)))
                    self.say(f"FILL {section}/{label} →", mask(str(value)))
                self.shot(page, f"fill_1{'0' if section == 'header' else '1'}_{section}.png")
        # 表头级字段核正（attempt_014 DOM 实证）：『项目说明』在表单中仅作费用明细列头（prop-reason），
        # 『行程说明』全 DOM 0 命中——模板这两项本就由费用明细行承载，如实标注 NOT_IN_FORM 而非计失败
        for r in rb:
            if r.get("section") == "project_note" and r.get("status") == "NOT_LOCATED":
                r.update(status="NOT_IN_FORM", match=None,
                         note="表单无此表头字段（DOM 实证）；模板值已落费用明细『项目说明』列，见 expense_detail 行记录")
        # 表单存在而模板未含的字段（attempt_017 核账）：报销类别 submitType 下拉在表单
        # header 存在且现值为空；模板切块解析（cropA-J/R1-R17/S1-S6 全量）从未出现该字段
        # 值 → 按『不猜』原则不选，如实记 FORM_FIELD_NOT_IN_TEMPLATE 留用户终审
        st_f = next((f for f in fields if f.get("name") == "submitType"), None)
        if st_f is not None and not str(st_f.get("value") or "").strip():
            rb.append({"section": "header", "field": "报销类别(submitType)",
                       "target": None, "status": "FORM_FIELD_NOT_IN_TEMPLATE", "match": None,
                       "note": "表单字段但模板未含值；不猜不选，留空待用户审核时定夺"})
        # 2) 关联公出单（选择器/弹窗）+ 是否为一次性兜底（关联单据表『是否为最后一次』列）
        rel = (plan.get("header") or {}).get("关联公出单")
        if rel is not None:
            rv = rel.get("value") if isinstance(rel, dict) else rel
            if rv is not None:
                with self._timing("section_fill", section="related_doc"):
                    rb.append(self._fill_related_doc(page, frame, rv))
                    self.say("FILL header/关联公出单 →", mask(str(rv)))
        once = [r for r in rb if r.get("field") == "是否为一次性" and not r.get("match")]
        if once:
            t = self._table_by_prop(frame, "bizNumber", "关联单据")
            if t:
                ci = _table_col(t.get("headers", []), "是否为一次性")   # 别名含 是否为最后一次
                if ci is not None:
                    with self._timing("cell_fill", section="related_once", row=0, field="是否为一次性"):
                        st, rbv = self._fill_ng_cell(page, frame, self._cell_loc(page, t, 0, ci), "是")
                    for r in once:
                        r.update(method="related_table_col",
                                 status=st if st != "OK" else ("OK" if fill_match(rbv, "是") else "MISMATCH"),
                                 readback=rbv, match=st == "OK" and fill_match(rbv, "是"))
        # 3) 费用明细 row1/row2（费用类型列 prop-project；表 caption=费用说明——attempt_012 实证
        #     『报销明细』caption 的表其实是汇总表，费用行表 caption 是『费用说明』）
        for rowno, key in enumerate(("row1", "row2")):
            row = (plan.get("expense_detail_table") or {}).get(key)
            if row:
                with self._timing("table_row_fill", section="expense_detail", row=rowno):
                    rb += self._fill_ng_table_row(page, frame, "expense_detail", rowno, row, "project", "费用说明")
        self.shot(page, "fill_20_detail.png")
        # 4) 汇总行（报销项目列 prop-reimItem；表 caption=报销明细）
        row = (plan.get("detail_summary_table") or {}).get("row1")
        if row:
            with self._timing("table_row_fill", section="detail_summary", row=0):
                rb += self._fill_ng_table_row(page, frame, "detail_summary", 0, row, "reimItem", "报销明细")
        self.shot(page, "fill_30_summary.png")
        # 4b) 预算联动尝试（模板三预算列为只读回显，模板值 科技中心/差旅/年度预算项目）：
        #     只搜模板原词、命中行才白名单确认，否则守卫式关闭——绝无盲选
        with self._timing("section_fill", section="budget_pick"):
            rb += self._try_budget_pick(page, frame)
        # 5) 银行信息（收款人列 prop-payee；开户行专属校验）
        brow = {label: str(spec.get("value") if isinstance(spec, dict) else spec)
                for label, spec in (plan.get("bank_info") or {}).items()
                if label != "开户行" and (spec.get("value") if isinstance(spec, dict) else spec) is not None}
        if brow:
            with self._timing("table_row_fill", section="bank", row=0):
                rb += self._fill_ng_table_row(page, frame, "bank", 0, brow, "payee", "银行")
        with self._timing("section_fill", section="bank_name"):
            rb.append(self._fill_bank_name_ng(page, frame))
        self.shot(page, "fill_40_bank.png")
        # 5b) 终读复核：插入/选入/联动之后，空回读的 CELL_NOT_EDITABLE 记录再读一次
        # （预算列/是否为最后一次 等 只读回显格可能此刻才被系统带出；改判一律留痕 method）
        with self._timing("section_fill", section="final_reread"):
            page.wait_for_timeout(800)
            _SEC_PROP = {"expense_detail": ("project", "费用说明"),
                         "detail_summary": ("reimItem", "报销明细"),
                         "bank": ("payee", "银行"),
                         "header": ("bizNumber", "关联单据")}
            for r0 in rb:
                if r0.get("status") == "CELL_NOT_EDITABLE" and not r0.get("readback") \
                        and r0.get("target") is not None:
                    prop = _SEC_PROP.get(r0.get("section"))
                    if not prop:
                        continue
                    tt = self._table_by_prop(frame, prop[0], prop[1])
                    if not tt:
                        continue
                    ci2 = _table_col(tt.get("headers", []), r0.get("field"))
                    if ci2 is None:
                        continue
                    cur2 = self._cell_info(frame, self._cell_loc(page, tt, r0.get("row", 0), ci2))
                    if fill_match(cur2.get("text"), str(r0.get("target"))):
                        r0.update(status="OK", method="final_reread", readback=cur2.get("text"),
                                  match=True, note="选择/联动后系统带出，终读确认")
                    else:
                        r0.update(readback=cur2.get("text"))
                        # 预算链白名单改判（attempt_023 记账时序教训）：模板词是正式项简称
                        # （差旅→差旅费），_budget_pick 已按模板词白名单确认整链；字段级
                        # 终读与联动同口径（包含关系）改判，其余字段恒走严格 fill_match
                        if (r0.get("field") in ("预算部门", "预算单", "预算科目", "预算项目")
                                and any(x.get("field") == "_budget_pick" and x.get("match")
                                        for x in rb)):
                            tv = _norm_cell(str(r0.get("target")))
                            if tv and tv in _norm_cell(cur2.get("text") or ""):
                                r0.update(status="OK", method="final_reread_whitelist",
                                          match=True,
                                          note="模板词为正式值简称（差旅→差旅费）；"
                                               "_budget_pick 联动链已按模板词白名单确认")
        # 6) verdict（与 SpreadJS 路径同形：matched/deferred+not_in_form/mismatch → c7）
        matched = [r for r in rb if r.get("match")]
        deferred = [r for r in rb if r.get("status") == "DEFERRED_TO_USER"]
        not_in_form = [r for r in rb if r.get("status") == "NOT_IN_FORM"]
        form_nf = [r for r in rb if r.get("status") == "FORM_FIELD_NOT_IN_TEMPLATE"]
        mismatch = [r for r in rb if not r.get("match")
                    and r.get("status") not in
                    ("DEFERRED_TO_USER", "NOT_IN_FORM", "FORM_FIELD_NOT_IN_TEMPLATE")]
        self.result["fill_summary"] = {
            "total": len(rb), "matched": len(matched), "surface": "primeNg",
            "deferred_to_user": [f"{r.get('section')}/{r.get('field')}" for r in deferred],
            "not_in_form": [f"{r.get('section')}/{r.get('field')}" for r in not_in_form],
            "form_not_in_template": [f"{r.get('section')}/{r.get('field')}" for r in form_nf],
            "mismatch": [f"{r.get('section')}/{r.get('row', '')}{r.get('field')} 回读『{r.get('readback')}』"
                         for r in mismatch],
            "no_save_guard": "未点击 保存/发送/流转/提交/上传/暂存/贴票/终止/返回 等任何按钮",
        }
        self.save("fill_readback.json", json.dumps(rb, ensure_ascii=False, indent=1))
        self.save("fill_final_grid.json", json.dumps(
            {"fields": self._safe_eval_frame(frame, FORM_MAP_JS),
             "tables": self._ng_eval_tables(frame)}, ensure_ascii=False, indent=1))
        self.shot(page, "fill_99_after.png")
        self.save_html(page, "fill_form.html")
        ev = [f"{self.attempt.name}/evidence/fill_readback.json",
              f"{self.attempt.name}/evidence/fill_final_grid.json",
              f"{self.attempt.name}/evidence/fill_99_after.png"]
        # D2（2026-10-23）字段级失败返回值进业务结果事件：rb 逐条（含
        # CELL_NOT_EDITABLE/OPTION_NOT_FOUND 等状态与改判 method）落 events.jsonl，
        # 不再只有 fill_end 聚合计数；回读原文留在 fill_readback.json（事件层不携带
        # 值，维持脱敏惯例）
        for r in rb:
            self.log_event(event="fill_field_result",
                           section=str(r.get("section")), field=str(r.get("field")),
                           row=r.get("row"), status=str(r.get("status")),
                           match=bool(r.get("match")),
                           method=str(r.get("method") or "-"))
        self.log_event(event="fill_end", total=len(rb), matched=len(matched),
                       deferred=len(deferred), mismatch=len(mismatch), surface="primeNg",
                       not_in_form=len(not_in_form), form_not_in_template=len(form_nf))
        if rb and not mismatch:
            extra = (f"；留人工 {len(deferred)} 项（"
                     + ", ".join(self.result["fill_summary"]["deferred_to_user"]) + "）") if deferred else ""
            extra += (f"；表单无此字段 {len(not_in_form)} 项（"
                      + ", ".join(self.result["fill_summary"]["not_in_form"]) + "）") if not_in_form else ""
            self.checks["c7_fill_new"].update(
                status=PASS,
                reason=f"{len(matched)}/{len(rb)} 字段填写且回读一致{extra}；未点击任何保存类按钮，待用户审核",
                evidence=ev)
            return PASS
        self.checks["c7_fill_new"].update(
            status=FAIL,
            reason=f"回读不一致 {len(mismatch)}/{len(rb)}："
                   + "；".join(self.result["fill_summary"]["mismatch"][:8]),
            evidence=ev)
        return FAIL

    def phase_fill(self):
        """按 fill_plan.json 在 新建报销单 页面填写全部字段并逐格回读；绝不点击保存类按钮。
        产出：form_dom_map.json（可写表面盘点，兼 P3' 表单 schema v0.2）/ fill_readback.json
        （逐字段目标值-回读-方法）/ fill_final_grid.json（整表终读，供用户审单）。"""
        self.budget.ensure_tech(60)
        page = self.page
        plan = self.fill_plan
        self.say("FILL 新建报销单（只填不存；保存/发送/流转等绝不点击）")
        self.log_event(event="fill_start", plan=str(self.fill_plan_path),
                       goal=(plan.get("meta") or {}).get("goal"))
        with self._timing("goto_new_form"):
            page.goto(assert_internal(HOST + NEW_FORM_PATH), wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        frame, surf = self._form_frame(page)
        dom_fields = frame.evaluate(DOM_FIELDS_JS) or []
        spread_map = frame.evaluate(SPREAD_ENUM_JS) or {}
        spreads = spread_map.get("spreads", []) if isinstance(spread_map, dict) else []
        self.save("form_dom_map.json", json.dumps({
            "ready": {"url": sanitize_url(page.url), "frame": sanitize_url(frame.url),
                      "dom_fields": len(dom_fields),
                      "gc": spread_map.get("gc") if isinstance(spread_map, dict) else None,
                      "spreads": len(spreads)},
            "dom_fields": dom_fields, "spread": spread_map,
        }, ensure_ascii=False, indent=1))
        self.shot(page, "fill_00_before.png")
        if not spreads and not dom_fields:
            self.checks["c7_fill_new"].update(
                status=FAIL,
                reason=f"新建页未发现可写表面（dom_fields={len(dom_fields)}, spreads=0）——form_dom_map.json 供诊断",
                evidence=[f"{self.attempt.name}/evidence/form_dom_map.json",
                          f"{self.attempt.name}/evidence/fill_00_before.png"])
            return FAIL
        if spreads:
            return self._phase_fill_spreadjs(page, frame, dom_fields, spreads, plan)
        return self._phase_fill_ng(page, frame, plan)

    def _phase_fill_spreadjs(self, page, frame, dom_fields, spreads, plan):
        """SpreadJS 表面（GC 存在）原路径：label 邻格 + 单元格 API 读写。"""
        rb = []
        # 表头区 + 项目说明（label 邻格模式；DOM 兜底）
        for section in ("header", "project_note"):
            for label, spec in (plan.get(section) or {}).items():
                value = spec.get("value") if isinstance(spec, dict) else spec
                if value is None:
                    continue
                rb.append(self._fill_one(page, frame, dom_fields, spreads, section, label, str(value)))
                self.say(f"FILL {section}/{label} →", mask(value))
            self.shot(page, f"fill_1{'0' if section == 'header' else '1'}_{section}.png")
        # 费用明细（列头向下；row2 需扩行）
        for rowno, key in enumerate(("row1", "row2")):
            row = (plan.get("expense_detail_table") or {}).get(key)
            if row:
                rb += self._fill_grid_row(page, frame, spreads, "expense_detail", rowno, row)
        self.shot(page, "fill_20_detail.png")
        # 汇总行
        row = (plan.get("detail_summary_table") or {}).get("row1")
        if row:
            rb += self._fill_grid_row(page, frame, spreads, "detail_summary", 0, row)
        self.shot(page, "fill_30_summary.png")
        # 银行信息（列头向下；开户行只认系统自动回显）
        for label, spec in (plan.get("bank_info") or {}).items():
            value = spec.get("value") if isinstance(spec, dict) else spec
            if label == "开户行":
                rb.append(self._fill_bank_name(frame, spreads))
                continue
            if value is None:
                continue
            rb.append(self._fill_one(page, frame, dom_fields, spreads, "bank", label,
                                     str(value), mode="below"))
            self.say(f"FILL bank/{label} →", mask(value))
        self.shot(page, "fill_40_bank.png")
        # 汇总校验与终局证据
        matched = [r for r in rb if r.get("match")]
        deferred = [r for r in rb if r.get("status") == "DEFERRED_TO_USER"]
        mismatch = [r for r in rb if not r.get("match") and r.get("status") != "DEFERRED_TO_USER"]
        self.result["fill_summary"] = {
            "total": len(rb), "matched": len(matched),
            "deferred_to_user": [f"{r.get('section')}/{r.get('field')}" for r in deferred],
            "mismatch": [f"{r.get('section')}/{r.get('row', '')}{r.get('field')} "
                         f"回读『{r.get('readback')}』" for r in mismatch],
            "no_save_guard": "未点击 保存/发送/流转/提交/上传/暂存/贴票/终止/返回 等任何按钮",
        }
        self.save("fill_readback.json", json.dumps(rb, ensure_ascii=False, indent=1))
        final = self._safe_eval_frame(frame, SPREAD_ENUM_JS)
        self.save("fill_final_grid.json",
                  json.dumps(final.get("spreads", []) if isinstance(final, dict) else [],
                             ensure_ascii=False, indent=1))
        self.shot(page, "fill_99_after.png")
        self.save_html(page, "fill_form.html")
        ev = [f"{self.attempt.name}/evidence/fill_readback.json",
              f"{self.attempt.name}/evidence/fill_final_grid.json",
              f"{self.attempt.name}/evidence/fill_99_after.png"]
        self.log_event(event="fill_end", total=len(rb), matched=len(matched),
                       deferred=len(deferred), mismatch=len(mismatch))
        if rb and not mismatch:
            extra = (f"；留人工 {len(deferred)} 项（"
                     + ", ".join(self.result["fill_summary"]["deferred_to_user"]) + "）") if deferred else ""
            self.checks["c7_fill_new"].update(
                status=PASS,
                reason=f"{len(matched)}/{len(rb)} 字段填写且回读一致{extra}；未点击任何保存类按钮，待用户审核",
                evidence=ev)
            return PASS
        self.checks["c7_fill_new"].update(
            status=FAIL,
            reason=f"回读不一致 {len(mismatch)}/{len(rb)}："
                   + "；".join(self.result["fill_summary"]["mismatch"][:8]),
            evidence=ev)
        return FAIL

    def _identity_snapshot(self, tag):
        page = self.page
        m = self.marks(page)
        # 单据编号必须从页面正文实证在场——不许拿 args 自比自（刷新被踢去别页要能暴露）
        doc_line = None
        try:
            body = page.evaluate("() => document.body ? document.body.innerText.slice(0, 30000) : ''") or ""
        except Exception:
            body = ""
        if self.args.doc_id and self.args.doc_id in body:
            doc_line = next((ln.strip()[:120] for ln in body.splitlines() if self.args.doc_id in ln), "")
        key_values = page.evaluate(GRID_ROWS_JS) if "reimburse" in (page.url or "") else []
        snap = {
            "url": sanitize_url(page.url),
            "doc_identity": self.args.doc_id if doc_line is not None else None,
            "doc_identity_evidence": doc_line or "doc_id_not_found_in_page_text",
            "account_name": self.args.expect_name if m.get("name_hits") else None,
            "status_text": next((r["cells"][1] for r in key_values
                                 if r.get("cells") and any(self.args.doc_id == (c or "").strip() for c in r["cells"])), None),
            "key_values": [r["cells"] for r in key_values
                           if any(self.args.doc_id == (c or "").strip() for c in r.get("cells", []))][:1],
        }
        self.save(f"identity_{tag}.json", json.dumps(snap, ensure_ascii=False, indent=1))
        return snap

    def phase_recover(self):
        self.budget.ensure_tech(10)
        page = self.page
        before = self._identity_snapshot("before_reload")
        page.reload(wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        after = self._identity_snapshot("after_reload")
        ok, diffs = compare_identity(before, after)
        ev = [f"{self.attempt.name}/evidence/identity_before_reload.json",
              f"{self.attempt.name}/evidence/identity_after_reload.json",
              self.shot(page, "after_reload.png")]
        if not ok:
            self.checks["c6_recover"].update(status=FAIL, reason=f"刷新后身份不一致: {diffs}", evidence=ev)
            return FAIL
        # 浏览器重启 → 登录态 + 目标可恢复
        self.say("recover: 关闭浏览器，同 profile 重启验证登录态与目标可达")
        self.ctx.close()
        self._launch(headless_exit_ok=True)
        page = self.page
        page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000)
        st, m, _ = self.login_state(page)
        if st != "LOGGED_IN":
            self.checks["c6_recover"].update(
                status=FAIL, reason=f"浏览器重启后登录态丢失({st})——profile 未保住会话", evidence=ev)
            return FAIL
        rows = page.evaluate(GRID_ROWS_JS)
        hit = pick_target(rows, self.args.doc_id)
        if hit[0] != "OK":
            self.checks["c6_recover"].update(status=FAIL, reason=f"重启后目标不可再定位({hit[0]})", evidence=ev)
            return FAIL
        self.checks["c6_recover"].update(
            status=PASS, reason="刷新前后身份一致 + 重启后登录态保持且目标可再定位（比较的是同一对象）",
            evidence=ev + [self.shot(page, "after_restart.png")])
        return PASS

    # ---- 浏览器生命周期 ----
    def _launch_isolated_guarded_context(self):
        """Existing historical-test isolation, with guards before its first page.

        Credentials are still read from the original protected SESSION_STATE by
        the caller. No persistent/restored profile pages are opened here.
        """
        from playwright.sync_api import sync_playwright
        from bpm.network_guard import ContextGuard
        self._pw = sync_playwright().start()
        self._guarded_browser = self._pw.chromium.launch(
            headless=False, args=["--no-proxy-server"])
        self.ctx = self._guarded_browser.new_context(
            ignore_https_errors=False, service_workers="block",
            viewport={"width": 1440, "height": 900})
        self._request_guard = ContextGuard(self.log_event).install(self.ctx)

    def _launch(self, headless_exit_ok=False):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            str(PROFILE), headless=False, ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
            args=["--start-maximized", "--no-proxy-server"],   # WinINET=Clash，内网必须绕过（corrections 沿用）
        )
        self._inject_session_state()
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.set_default_timeout(45000)
        self.page.on("dialog", lambda d: (d.dismiss(), self.log_event(event="dialog_dismissed", kind=d.type)))
        self.failed_reqs = []
        self.page.on("requestfailed", lambda r: self.failed_reqs.append(f"{r.failure} {r.url[:120]}"))

    def _inject_session_state(self):
        """TTL 内从原受保护状态补齐缺失的 cookie/localStorage/sessionStorage。
        2026-10-21 attempt_007 实证：BPM 本域 0 cookie、localStorage 无 token——登录态在
        sessionStorage（storage_state 不采集），故额外采集 _page_storage；导航只补缺失键，
        不覆盖站点已刷新值（空字符串也视为已有值）。仍须实时核验，不能保证免扫码。
        失败不致命：注入后仍被要求登录则回落扫码门（wait_login），绝不伪造登录态。
        cookie/storage 值只进浏览器内存，日志只记条数与键名。"""
        if not _session_state_usable(SESSION_STATE):
            self.log_event(event="session_state_skip", reason="missing_or_expired",
                           ttl_hours=SESSION_TTL / 3600.0)
            return
        try:
            state = json.loads(SESSION_STATE.read_text(encoding="utf-8"))
            cookies = state.get("cookies", [])
            if cookies:
                existing = {(c.get("name"), c.get("domain"), c.get("path"))
                            for c in self.ctx.cookies()}
                missing = [c for c in cookies
                           if (c.get("name"), c.get("domain"), c.get("path")) not in existing]
                if missing:
                    self.ctx.add_cookies(missing)
            origins = state.get("origins") or []
            page_storage = state.get("_page_storage") or {}
            if origins or page_storage:
                payload = json.dumps({"origins": origins, "page_storage": page_storage},
                                     ensure_ascii=False)
                self.ctx.add_init_script(
                    "try{var _st=" + payload + ";"
                    "for(var i=0;i<(_st.origins||[]).length;i++){var o=_st.origins[i];"
                    "if(location.origin===o.origin){var ls=o.localStorage||[];"
                    "for(var j=0;j<ls.length;j++){try{if(localStorage.getItem(ls[j].name)===null)"
                    "{localStorage.setItem(ls[j].name,ls[j].value)}}catch(e){}}}}"
                    "var ps=(_st.page_storage||{})[location.origin];"
                    "if(ps){for(var k in ps){try{if(sessionStorage.getItem(k)===null)"
                    "{sessionStorage.setItem(k,ps[k])}}catch(e){}}}}catch(e){}"
                )
            self.log_event(event="session_state_injected", cookies=len(cookies),
                           origins=len(origins), page_storage_origins=len(page_storage),
                           mtime_age_s=round(time.time() - SESSION_STATE.stat().st_mtime))
        except Exception as e:
            self.log_event(event="session_state_inject_error", error_type=type(e).__name__)

    def _save_session_state(self):
        """登录确认后导出到受保护 profile，保留真实扫码起点及期限。
        storage_state（cookie+localStorage）之外，另从活页采集 sessionStorage（BPM token 所在，
        attempt_007 实证）。cookie/storage 值只落该文件（不进日志/证据），日志只记条数与键名。"""
        try:
            state = self.ctx.storage_state()
            page_storage = {}
            for pg in [self.page] + [p for p in self.ctx.pages if p is not self.page]:
                try:
                    ps = pg.evaluate(
                        "() => ({origin: location.origin,"
                        " ss: (() => { try { const o = {};"
                        " for (let i = 0; i < sessionStorage.length; i++)"
                        " { const k = sessionStorage.key(i); o[k] = sessionStorage.getItem(k); }"
                        " return o; } catch (e) { return {}; } })()})")
                    if ps and ps.get("origin") and ps.get("ss"):
                        page_storage.setdefault(ps["origin"], ps["ss"])
                except Exception:
                    pass
            state["_page_storage"] = page_storage
            from bpm.session import (read_state, attach_metadata, observed_identity,
                                     persist_state, write_record)
            principal = observed_identity(self.page, state)
            if principal["name"] != self.args.expect_name:
                raise ValueError("Actual login identity differs from expected account")
            previous = read_state(SESSION_STATE)
            attach_metadata(state, previous,
                            fresh_scan=getattr(self, "_fresh_scan_confirmed", False))
            # 写回经 persist_state：无可信扫码 meta 的旧文件保留原 mtime（24h 锚点
            # 不因普通探查滚动续期）；凭证值照常刷新，不补扫码、不授新窗口。
            persist_state(SESSION_STATE, state, previous)
            record_path = write_record(state, principal)
            self._saved_session_record = record_path
            self.log_event(event="session_state_saved",
                           cookies=len(state.get("cookies", [])),
                           origins=len(state.get("origins") or []),
                           page_storage_origins=list(page_storage.keys()),
                           page_storage_key_counts={o: len(v) for o, v in page_storage.items()},
                           ttl_hours=SESSION_TTL / 3600.0)
        except Exception as e:
            self.log_event(event="session_state_save_error", error_type=type(e).__name__)
            if getattr(self.args, "login_only", False):
                raise RuntimeError("Login verified but session persistence failed") from None

    def _close_browser(self):
        """结束前确认浏览器进程退出。"""
        try:
            self.ctx.close()
        except Exception:
            pass
        try:
            self._pw.stop()
        except Exception:
            pass

    def _park_browser(self, minutes):
        """--keep-open-minutes>0：填写或仅登录成功后保留浏览器在场。
        期间只心跳不操作（不保存不提交）；分钟耗尽或进程被终止才结束。"""
        if getattr(self.args, "login_only", False):
            self.say(f"LOGIN_DONE 浏览器保留在场约 {minutes:.0f} 分钟；本地复用上限 30 天（旧 60 天记录已收紧），实际受服务端期限限制")
        else:
            self.say(f"FILL_DONE 浏览器保留在场约 {minutes:.0f} 分钟，等待用户人工审核（不保存不提交）")
        self.log_event(event="keep_open_start", minutes=minutes)
        for _ in range(max(1, int(minutes))):
            time.sleep(60)
        self.log_event(event="keep_open_end")

    def _deliver_and_park(self, reason):
        """G3.4/G3.5 交付与驻留决策（自 main() finally 原样抽出，行为不变）。

        终局结果已由调用方原子落盘并记 probe_end；此处先发布完成事件——
        agent 用宿主后台通知/事件监听在完成事件后读取权威结果并立即回复，
        不等驻留进程退出；G4 生命周期计数按本进程实际角色如实记录。
        驻留边界：填写链已绑定计划→按填写语义驻留；登录未确认→按
        WAIT_HUMAN_LOGIN 保留页面；仅准备阶段缺口（无表单可审）不驻留，
        尽快释放锁，避免占用下一任务。"""
        self.log_event(event="result_delivered", finish_reason=reason,
                       task_status=self.result.get("task_status"),
                       save_status=self.result.get("save_status"),
                       plan_hash=self.result.get("plan_hash"),
                       fresh_scan=bool(getattr(self, "_fresh_scan_confirmed", False)),
                       business_executors=1, browser_instances=1, business_contexts=1,
                       lock_owners=1, driver_subprocesses=0)
        task_branch_retain = (getattr(self, "pending_task_prepare", None) is not None
                              and getattr(self, "ctx", None) is not None
                              and (self.fill_plan is not None
                                   or self.checks["c1_entry_login"]["status"] != PASS))
        if self.args.keep_open_minutes > 0 and (self.fill_plan is not None or (
                getattr(self.args, "login_only", False)
                and self.checks["c1_entry_login"]["status"] == PASS) or task_branch_retain):
            # 驻留审单期不占墙钟：wall_cap 熔断线程不区分「执行中/驻留中」，会在驻留中途
            # os._exit(83) 硬杀（attempt_024 实证：驻留 45min 第 36 分钟被腰斩，keep_open_end
            # 缺失、锁残留）。驻留属填写后人工审单，不计入执行墙钟，进入前扩容熔断上限。
            self.budget.wall_cap += self.args.keep_open_minutes * 60
            self._park_browser(self.args.keep_open_minutes)

    # ---- 主流程 ----
    def main(self):
        self.acquire_lock()
        self.log_event(event="probe_start", run=self.args.run, attempt=self.attempt.name,
                       doc_id=self.args.doc_id, tech_budget=self.args.tech_budget,
                       login_wait_cap=self.args.login_wait, wall_cap=self.args.wall_cap)
        reason = "UNKNOWN"
        try:
            self._preflight()
            self._launch()
            runner = PhaseRunner(self.checks, self.say)
            self.result["phases"]["entry"] = runner.run("entry", self.phase_entry)
            if self.result["phases"]["entry"] == "LOGIN_REQUIRED":
                self.result["phases"]["login_wait"] = runner.run("login_wait", self.wait_login)
            entry_ok = self.checks["c1_entry_login"]["status"] == PASS
            if entry_ok:
                # 登录确认即存登录态（先于后续任何阶段，确保填写失败也不浪费本次扫码）
                self._save_session_state()
            # 注意依赖口径：c1 由 entry 或 login_wait 任一成立即 PASS（phase 字符串 LOGIN_REQUIRED ≠ 失败），
            # 故 locate 的门禁用检查项状态而非 phase 状态（attempt_003 教训：把 locate 依赖绑在 entry 的
            # phase 返回值上，login_wait 成功后整链被误判依赖不满足而 SKIPPED）
            if getattr(self.args, "login_only", False):
                self.log_event(event="login_only_complete", authenticated=entry_ok,
                               ttl_hours=SESSION_TTL / 3600.0, proxy_mode="direct")
            elif getattr(self, "pending_task_prepare", None) is not None or self.fill_plan is not None:
                # 填写任务（--fill-plan 授权或 oneshot 任务分支）：新建报销单只填不存；
                # 不做历史单据只读链。任务分支（G1）在身份确认后先经 prepare 挂钩
                # 完成同会话模板读取→最终计划与授权冻结，再进入既有填写链。
                prepare = getattr(self, "pending_task_prepare", None)
                prepared = True
                if prepare is not None:
                    if entry_ok:
                        self.result["phases"]["prepare"] = runner.run("prepare", prepare)
                        prepared = self.result["phases"]["prepare"] == PASS
                        if not prepared:
                            self.checks["c7_fill_new"].update(status=BLOCKED,
                                                              reason="任务准备阶段未通过（模板/计划/授权），未进入填写")
                    else:
                        prepared = False
                        self.checks["c7_fill_new"].update(status=NOT_RUN, reason="入口登录未通过，任务准备未执行")
                if prepared and entry_ok:
                    self.result["phases"]["fill"] = runner.run("fill", self.phase_fill)
                elif prepare is None and not entry_ok:
                    self.checks["c7_fill_new"].update(status=NOT_RUN, reason="入口登录未通过，填写未执行")
            else:
                self.result["phases"]["locate"] = runner.run("locate", self.phase_locate) \
                    if entry_ok else "SKIPPED"
                # structure/recover 依赖 locate PASS（PhaseRunner 依赖表 + 显式守卫双保险）
                self.result["phases"]["structure"] = runner.run("structure", self.phase_structure, depends=("locate",))
                self.result["phases"]["recover"] = runner.run("recover", self.phase_recover, depends=("structure",))
            reason = self._overall()
        except RuntimeError as e:
            if "BUDGET_EXHAUSTED" in repr(e):
                reason = "BUDGET_EXHAUSTED"
                for k, c in self.checks.items():
                    if c["status"] == NOT_RUN and k in ("c2_locate_target", "c3_structure", "c6_recover", "c7_fill_new"):
                        c.update(reason="技术预算耗尽，未执行")
            else:
                reason = f"ABORTED:{e!r}"
                self.log_event(event="probe_abort", error=repr(e))
        except Exception as e:
            reason = f"FATAL:{e!r}"
            traceback.print_exc()
            self.log_event(event="probe_fatal", error=repr(e))
        finally:
            # 终局证据先落盘，再按需驻留浏览器（驻留期间监控/用户都能读到 result.json）
            self.result["finish_reason"] = reason
            self.atomic_result()
            self.log_event(event="probe_end", reason=reason,
                           tech_used_s=self.result.get("tech_used_s"),
                           login_wait_s=self.result.get("login_wait_s"),
                           budget_respected=self.result.get("budget_respected"))
            self.say(f"FINISH {reason} tech={self.result.get('tech_used_s')}s "
                     f"login_wait={self.result.get('login_wait_s')}s attempt={self.attempt.name}")
            # G3.4/G3.5 立即交付锚点与驻留边界（完成事件→驻留决策，详见方法契约）。
            self._deliver_and_park(reason)
            self._close_browser()
            self.release_lock()
            self.budget.close()

    def _preflight(self):
        try:
            reg = subprocess.run(
                ["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"],
                capture_output=True, text=True, timeout=10)
            keys = [l.strip() for l in (reg.stdout or "").splitlines()
                    if any(k in l for k in ("ProxyEnable", "ProxyServer", "AutoConfigURL"))]
        except Exception as e:
            keys = [f"reg_query_failed:{e!r}"]
        try:
            s = socket.create_connection(("192.168.34.10", 443), timeout=5)
            s.close()
            sock_ok = True
        except Exception as e:
            sock_ok = f"failed:{e!r}"
        self.log_event(event="preflight", wininet_proxy=keys, direct_socket_443=str(sock_ok))
        self.say("preflight wininet:", keys, "| socket443:", sock_ok)

    def _overall(self):
        """整体成功=业务断言。只读任务：c1/c2/c3/c6 全 PASS；填写任务：c1+c7 全 PASS
        （c7 允许含 DEFERRED_TO_USER 项，但零回读不一致）；c4/c5 按设计 NOT_AUTHORIZED。"""
        if getattr(self.args, "login_only", False):
            return ("SUCCESS_LOGIN_ONLY" if self.checks["c1_entry_login"]["status"] == PASS
                    else "BLOCKED(c1_entry_login)")
        if self.fill_plan is not None:
            if (self.checks["c1_entry_login"]["status"] == PASS
                    and self.checks["c7_fill_new"]["status"] == PASS):
                return "SUCCESS_FILL_ONLY"
            if self.checks["c1_entry_login"]["status"] == BLOCKED:
                return "BLOCKED(c1_entry_login)"
            return "FAILED"
        core = ("c1_entry_login", "c2_locate_target", "c3_structure", "c6_recover")
        if all(self.checks[k]["status"] == PASS for k in core):
            return "SUCCESS_READ_ONLY"
        blocked = [k for k in core if self.checks[k]["status"] == BLOCKED]
        return f"BLOCKED({'+'.join(blocked)})" if blocked else "FAILED"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="stage1 browser probe v2 (read-only)")
    ap.add_argument("--run", default=time.strftime("probe-%Y%m%d-%H%M%S"),
                    help="run id（automation/runs/ 下目录；复用已有 run 则 attempt 递增）")
    ap.add_argument("--doc-id", default=None, help="目标单据编号（无则停在 TARGET_UNSPECIFIED，不选替身）")
    ap.add_argument("--legacy-regression", action="store_true",
                    help="显式运行旧样例回归（只填不存；不代表金额校验或保存验收）")
    ap.add_argument("--resume-attempt", default=None,
                    help="恢复本任务：先只读盘点，不自动重复新建或重试保存")
    ap.add_argument("--expect-name", required=True,
                    help="期待登录账户姓名（必填：身份判定的核心证据。缺省默认值会把错误身份放行/把本人误判 UNKNOWN"
                         "——2026-10-21 attempt_001 实证：操作账号≠事故单收款人。证据文件留原值，控制台脱敏）")
    ap.add_argument("--tech-budget", type=float, default=1800.0)
    ap.add_argument("--login-wait", type=float, default=480.0)
    ap.add_argument("--wall-cap", type=float, default=2400.0)
    ap.add_argument("--interactive-pick", action="store_true",
                    help="无 --doc-id 时：列表盘点后写 pick_request.json 并等待 pick_reply.txt"
                         "（单行：编号 或 NONE），同一会话内续跑 structure/recover——省一次重扫码")
    ap.add_argument("--pick-wait", type=float, default=900.0,
                    help="人机接力等待上限（秒，计入墙钟不计技术预算）")
    ap.add_argument("--keep-open-minutes", type=float, default=0.0,
                    help=">0：填写或仅登录成功后保留浏览器在场指定分钟（只心跳不操作）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--login-only", action="store_true",
                      help="仅打开 OA、等待扫码并持久化登录态；不执行单据操作")
    mode.add_argument("--fill-plan", default=None,
                    help="填写任务授权：fill_plan.json 路径。启用后新建报销单并按模板值填写"
                         "（只填不存，保存/发送等留给用户）；不启用则维持只读任务（locate/structure/recover）")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", args.run):
        ap.error("run id 必须为仓库 runs 下的简单名称（1–100 个字母、数字、下划线或连字符）")
    for name in ("tech_budget", "login_wait", "wall_cap", "pick_wait", "keep_open_minutes"):
        value = getattr(args, name)
        if not 0 <= value < float("inf") or (name in ("tech_budget", "wall_cap") and value == 0):
            ap.error(name + " 必须是有限的非负数（执行预算/墙钟须大于零）")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.fill_plan:
        plan_path = Path(args.fill_plan).resolve()
        if any(part.lower() in {".pw-profile", ".git", "legacy-ia2"} for part in plan_path.parts):
            raise SystemExit("受保护目录不得作为填写计划来源")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        if plan.get("schema_version") == "1.0":
            from bpm.ui import StructuredProbe
            probe = StructuredProbe(args)
            probe.main()
            return 0 if probe.result.get("finish_reason") in ("SUCCESS_FILL_ONLY", "SUCCESS_DRAFT_SAVED") else 2
        elif args.legacy_regression:
            probe = Probe(args)
            probe.main()
            return 0 if probe.result.get("finish_reason") == "SUCCESS_FILL_ONLY" else 2
        else:
            raise SystemExit("旧计划只允许显式 --legacy-regression；新任务必须使用 v1 本单计划")
    else:
        Probe(args).main()


if __name__ == "__main__":
    sys.exit(main())
