"""BPM 报销单只读查询入口：关键词找候选 / 精确单号读取（不填不存）。

一次受锁保护的只读会话内完成：真实认证（复用 ``bpm.login.LoginProbe`` 生命周期，
入口内已认证时无需先独立运行 bpm_login.py）、默认「仅当前制单人」筛选核实与清除、
关键词三分支（主表备注/明细摘要/明细备注）OR 查询合并去重、制单时间降序、
精确单号读取与可选模板快照（复用 ``bpm.template`` 既有校验）。

本模块只读：不新建/填写/保存/提交任何业务单据，不点击保存族按钮；唯一提交类
动作是筛选区的「查询」按钮（过 ``Probe._click_guard`` 守卫）。查询响应按解析后的
host/path 匹配（``oa.api.qiaodan.com/reimburse/query/<n>/<n>``，合法 query string
不参与判等），监听先于点击注册。

用法（cwd=仓库根）::

    python -X utf8 -m bpm.query --keyword "外购样品" --limit 5 --run "<run-id>"
    python -X utf8 -m bpm.query --number "15426104120" --snapshot --run "<run-id>"

产物：``automation/runs/<run>/events.jsonl``（追加）、``attempt_NNN/evidence/`` 与
run 根的 ``query_result.json``。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit

from bpm.browser_probe import HOST, LIST_PATH, PASS
from bpm.login import LoginProbe
from bpm.template import fetch_template, observe_template_view, parse_list_items

# 实证（2026-10-27 list-inspection + lookup.py）：筛选区控件 ID 与字段含义。
KEYWORD_FIELDS = (("Description15", "主表备注"), ("Digest19", "明细摘要"), ("Description20", "明细备注"))
CREATOR_INPUT = "#CreatedPath2"          # 制单人（默认带出当前登录人，即「仅当前制单人」）
CREATOR_ROW = ".form-row.CreatedPath"
NUMBER_INPUT = "#BizNumber1"             # 单据编号（BizNumber22 为关联单号，不用）
DATE_ROW = ".form-row.CreatedAt"         # 制单日期起止（两个无 id input）
LIST_API_HOST = "oa.api.qiaodan.com"
LIST_API_PATH_RE = re.compile(r"/reimburse/query/\d+/\d+")

# 定位所需摘要字段（计划：默认查询只取定位所需摘要，不搬整行）。
CANDIDATE_FIELDS = ("bizNumber", "id", "createdName", "createdAt", "submitType",
                    "totalCost", "bizStatus", "description")


def list_query_response(target):
    """列表查询响应判别（Playwright expect_response predicate 兼容形态）。

    接收 Response 对象（用其 .url/.status，实证 lookup.py 同口径）或纯 URL 字符串
    （离线测试直接传 URL）；按解析后的 scheme/host/path 判等，忽略合法 query string。
    """
    if isinstance(target, str):
        url, status = target, 200
    else:
        url = getattr(target, "url", "") or ""
        status = getattr(target, "status", 0)
    if status != 200:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == LIST_API_HOST
            and LIST_API_PATH_RE.fullmatch(parsed.path) is not None)


def validate_cli(args):
    """CLI 参数反例集：空条件、互斥、limit 范围、snapshot 归属。返回错误列表。"""
    errors = []
    if bool(args.keyword) == bool(args.number):
        errors.append("--keyword 与 --number 必须二选一且至少一个")
    if args.number is not None and not re.fullmatch(r"\d+", args.number):
        errors.append("--number 必须是完整单号数字字符串（保留前导零，不做前缀匹配）")
    if not 1 <= args.limit <= 20:
        errors.append("--limit 必须在 1—20")
    if args.snapshot and not args.number:
        errors.append("--snapshot 仅用于 --number 精确读取")
    for name in ("date_from", "date_to"):
        value = getattr(args, name)
        if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            errors.append(f"--{name.replace('_', '-')} 须为 YYYY-MM-DD")
    if args.date_from and args.date_to and args.date_from > args.date_to:
        errors.append("--date-from 不得晚于 --date-to")
    if args.keyword is not None and not args.keyword.strip():
        errors.append("--keyword 不能为空白")
    return errors


def merge_candidates(branch_items, limit):
    """三分支候选合并：单号+UUID 去重，制单时间（createdAt 字符串口径）降序，
    并列保留并列标记；每分支先取足前 limit 再合并（调用方保证）。"""
    merged = {}
    for field_id, items in branch_items:
        for item in items:
            key = (item.get("bizNumber"), item.get("id"))
            if key[0] is None:
                continue
            entry = merged.setdefault(key, {k: item.get(k) for k in CANDIDATE_FIELDS})
            entry.setdefault("matched_fields", []).append(field_id)
    ordered = sorted(merged.values(),
                     key=lambda c: (c.get("createdAt") or "", c.get("bizNumber") or ""),
                     reverse=True)
    top_time = ordered[0].get("createdAt") if ordered else None
    for candidate in ordered:
        candidate["tied_with_latest"] = bool(top_time and candidate.get("createdAt") == top_time)
    return ordered


def exact_match(items, number):
    """精确单号匹配：bizNumber 全等（保留前导零、不做前缀命中）；
    多 UUID 唯一性破坏即报错。返回 (candidate|None, error|None)。"""
    exact = [i for i in items if isinstance(i, dict) and i.get("bizNumber") == number]
    uuids = {i.get("id") for i in exact}
    if len(uuids) > 1:
        return None, f"完整单号 {number} 对应多个 UUID：{sorted(str(u) for u in uuids)}——停止，不任取"
    if not exact:
        return None, None
    candidate = {k: exact[0].get(k) for k in CANDIDATE_FIELDS}
    candidate["matched_fields"] = ["单据编号"]
    return candidate, None


def classify_keyword_outcome(branches):
    """三分支结果分类：全失败 failed / 部分失败 partial / 全成功零命中 zero / 有命中 ok。"""
    ok = [b for b in branches if b["status"] == "ok"]
    if not ok:
        return "failed"
    if len(ok) < len(branches):
        return "partial"
    return "zero_results" if not any(b["items"] for b in ok) else "ok"


class QueryCLI:
    def __init__(self, options):
        self.o = options
        self.timings = {"launch_s": None, "auth_s": None, "query_s": None,
                        "detail_s": None, "total_s": None}
        self.retries = 0
        probe_args = SimpleNamespace(
            run=options.run, doc_id=None, expect_name=options.expect_name,
            force_scan=False, tech_budget=1800.0, login_wait=options.login_wait,
            wall_cap=options.wall_cap, fill_plan=None, login_only=True,
            keep_open_minutes=0.0, interactive_pick=False)
        self.p = LoginProbe(probe_args)
        self.page = None

    # ---- 会话生命周期（G1）----
    def open_session(self):
        t0 = time.perf_counter()
        self.p._launch()
        self.timings["launch_s"] = round(time.perf_counter() - t0, 1)
        t0 = time.perf_counter()
        state = self.p.phase_entry()
        if state == "LOGIN_REQUIRED" and self.o.login_wait > 0:
            state = self.p.wait_login()      # 有界 login_wait，不无限等待扫码
        self.timings["auth_s"] = round(time.perf_counter() - t0, 1)
        if state != PASS:
            observed = getattr(self.p, "_last_login_state", "UNKNOWN")
            if observed == "LOGIN_REQUIRED":
                raise LoginUnavailable("观察到登录入口，登录尚未成立；未执行查询。",
                                       auth_state="LOGIN_REQUIRED")
            raise LoginUnavailable("登录状态未能确认，尚无凭据失效证据；未执行查询。",
                                   auth_state="UNKNOWN")
        self.p._save_session_state()          # 成功探查后的本机会话元数据更新（30 天口径不变）
        self.page = self.p.page

    def open_list(self):
        from bpm.browser_probe import assert_internal
        self.page.goto(assert_internal(HOST + LIST_PATH), wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_selector("th.prop-submitType", timeout=30000)
        self.page.wait_for_timeout(1500)

    # ---- 筛选区（清默认 + 用户显式筛选保留）----
    def read_creator_filter(self):
        loc = self.page.locator(CREATOR_INPUT)
        return loc.input_value() if loc.count() == 1 else None

    def clear_default_creator(self):
        """清除系统自动带出的「仅当前制单人」筛选并回读确认；失败即报错，
        不静默按较窄范围继续。实证：clear-icon 被输入框遮挡，须触发其 UI 事件。"""
        before = self.read_creator_filter()
        if not before:
            return {"had_default": False}
        icon = self.page.locator(f"{CREATOR_ROW} .clear-icon")
        if icon.count() == 0:
            raise ScopeFilterError("默认制单人筛选存在但清空图标未观察到；不能按较窄范围冒充查询")
        icon.first.dispatch_event("click")
        self.page.wait_for_timeout(600)
        after = self.read_creator_filter()
        if after != "":
            raise ScopeFilterError(f"默认制单人筛选清除后回读非空（{after!r}）；停止，不冒充已放宽范围")
        self.p.log_event(event="default_creator_filter_cleared", before=before)
        return {"had_default": True, "was": before}

    def apply_explicit_filters(self):
        """用户显式筛选逐项落实并回读；不给就跳过。人员/组织多候选不允许任取首项。"""
        applied = {}
        if self.o.creator:
            self._org_pick(self.page.locator(CREATOR_ROW).first,
                           self.o.creator, "制单人", person=True)
            applied["creator"] = self.o.creator
        if self.o.department:
            # 类名实证于真实筛选区 dump（20261027-common-accept-dept：dqc-container form-row
            # AppliedDeptPath 存在；标签文本「申请部门」会同时命中申请人行，不可用）
            row = self.page.locator(".form-row.AppliedDeptPath").first
            if self.page.locator(".form-row.AppliedDeptPath").count() != 1:
                names = []
                all_rows = self.page.locator(".form-row")
                for i in range(min(all_rows.count(), 20)):
                    cls = all_rows.nth(i).get_attribute("class")
                    if cls:
                        names.append(cls.strip())
                raise ScopeFilterError(
                    f"申请部门筛选行未唯一定位（筛选区行类名 {names}）")
            self._org_pick(row, self.o.department, "申请部门", person=False)
            applied["department"] = self.o.department
        if self.o.date_from or self.o.date_to:
            inputs = self.page.locator(f"{DATE_ROW} input")
            if inputs.count() < 2:
                raise ScopeFilterError("制单日期起止输入未观察到两个")
            if self.o.date_from:
                inputs.nth(0).fill(self.o.date_from)
            if self.o.date_to:
                inputs.nth(1).fill(self.o.date_to)
            applied["date_range"] = [self.o.date_from, self.o.date_to]
        return applied

    def _org_pick(self, cont, value, label, person):
        """范式复用 ui.py 申请人选择（同族「组织架构」对话框）：fill+Enter 才触发搜索、
        人名节点文本为「姓名 [工号]」、组织节点为纯名称、点击后验选中态。首版只打字不
        回车，树从未过滤（真实 run 20261027-common-accept-creator/creator2：两人名均
        0 命中）——已按实证修正。person=True 判人名（必须带工号括号，同名多工号即歧义）；
        person=False 判组织（先精确唯一，再前缀唯一，均不唯一即歧义）。"""
        cont.scroll_into_view_if_needed()
        btn = cont.locator("button[aria-label='选择组织']").first
        if btn.count() == 0:
            raise ScopeFilterError(f"{label}选择触发按钮未观察到")
        btn.click(timeout=4000)
        dlg = self.page.locator(".org-select-dialog").first
        try:
            dlg.wait_for(state="visible", timeout=6000)
        except Exception:
            raise ScopeFilterError(f"{label}组织弹窗未打开")
        self.page.wait_for_timeout(1000)
        inp = dlg.locator("input:visible").first
        if inp.count() > 0:
            inp.fill("")
            inp.fill(value)
            inp.press("Enter")
            self.page.wait_for_timeout(1500)
        loose = dlg.get_by_text(value, exact=False)
        texts = []
        for i in range(min(loose.count(), 12)):
            try:
                texts.append(loose.nth(i).inner_text(timeout=2000).strip())
            except Exception:
                continue
        if person:
            pat = re.compile(rf"^{re.escape(value)}\s*\[")
            hits = sorted({t for t in texts if pat.match(t)})
            others = sorted({t for t in texts if t and not pat.match(t)})
        else:
            exact = sorted({t for t in texts if t == value})
            prefix = sorted({t for t in texts if t.startswith(value)})
            hits = exact if len(exact) == 1 else prefix
            others = sorted({t for t in texts if t not in set(hits)})
        if len(hits) != 1:                         # 多候选/零候选都不任取
            raise ScopeFilterError(
                f"{label}「{value}」{'姓名式' if person else '组织'}候选 {len(hits)} 个、"
                f"其他含式命中 {len(others)} 个（样例 {(hits[:2] + others[:2])}）"
                f"——歧义或未找到，不任取首项")
        node = dlg.get_by_text(hits[0], exact=False).first
        self.p._click_guard(hits[0][:20])
        node.click()
        self.page.wait_for_timeout(500)
        # 选中态类落在祖先行节点（get_by_text 命中内层文本元素）→ closest 上溯判定；
        # 仅作诊断事件，绑定判据是下方确定后的筛选回读
        if not node.evaluate("e=>!!e.closest('[aria-selected=true],.ui-state-highlight')"):
            self.p.log_event(event="org_node_selection_state_unproven",
                             kind=label, value=value)
        self.page.wait_for_timeout(300)
        for name in ("确 定", "确定", "确 认", "确认", "选 择", "选择"):
            ok_btn = dlg.get_by_role("button", name=name, exact=True)
            if ok_btn.count() > 0 and ok_btn.first.is_visible():
                if not ok_btn.first.is_enabled():
                    raise ScopeFilterError(
                        f"{label}「{value}」节点点击后「{name}」仍禁用——所选节点未注册选中"
                        f"（可能为不可选父节点，请改用具体部门）；不点击禁用按钮")
                self.p._click_guard(name)
                ok_btn.first.click(timeout=8000)
                break
        self.page.wait_for_timeout(800)
        readback = cont.locator("input").first.input_value()
        if value not in readback:
            raise ScopeFilterError(f"{label}选择后回读不符：{readback!r}")
        self.p.log_event(event="explicit_filter_applied", kind=label, value=value)

    # ---- 查询（响应监听先注册，再点击）----
    def click_query(self):
        buttons = self.page.get_by_role("button", name="查询", exact=True)
        if buttons.count() != 1:
            raise QueryFlowError("「查询」按钮未唯一观察到")
        self.p._click_guard("查询")
        buttons.click(timeout=8000)

    def run_branch(self, field_id, keyword):
        """单个关键词字段分支：只填本字段、清其余两个，查询并捕获列表响应。"""
        for other, _ in KEYWORD_FIELDS:
            self.page.locator("#" + other).fill("" if other != field_id else keyword)
        branch = {"field": field_id, "status": "ok", "items": [], "reason": ""}
        try:
            with self.page.expect_response(list_query_response, timeout=30000) as received:
                self.click_query()
            self.page.wait_for_timeout(600)
            branch["items"] = parse_list_items(received.value.text())
        except Exception as exc:                     # 超时/解析失败：分支失败，不当零结果
            branch["status"] = "failed"
            branch["reason"] = f"{type(exc).__name__}: {exc}"[:200]
            self.p.log_event(event="keyword_branch_failed", field=field_id, reason=branch["reason"])
        self.p.save(f"keyword_{field_id}_response.json",
                    json.dumps(branch["items"], ensure_ascii=False, indent=1))
        return branch

    def paginate_branch(self, field_id, keyword, want, max_pages):
        """分支取足前 want 个候选（跨页）；到上限/无下一页即停。"""
        branch = self.run_branch(field_id, keyword)
        if branch["status"] != "ok":
            return branch
        pages = 1
        while (len(branch["items"]) < want and pages < max_pages):
            nxt = self.page.locator("a.ui-paginator-next").first
            if nxt.count() == 0 or "ui-state-disabled" in (nxt.get_attribute("class") or ""):
                break
            try:
                with self.page.expect_response(list_query_response, timeout=30000) as received:
                    nxt.click(timeout=5000)
                self.page.wait_for_timeout(800)
                branch["items"].extend(parse_list_items(received.value.text()))
                pages += 1
            except Exception as exc:
                branch["status"] = "partial"
                branch["reason"] = f"翻页第 {pages + 1} 页失败：{exc}"[:200]
                break
        branch["pages"] = pages
        return branch

    # ---- 主流程 ----
    def run(self):
        t_total = time.perf_counter()
        outcome = {"status": None}
        self.p.acquire_lock()
        ok = False
        try:
            self.open_session()
            self.open_list()
            scope = {"default_creator_filter": self.clear_default_creator(),
                     "explicit_filters": self.apply_explicit_filters(),
                     "account": self.p.args.expect_name,
                     "scope_note": "当前账号可访问的全部报销单（已清默认仅当前制单人筛选）"
                     if not self.o.creator else "当前账号可访问范围内按显式筛选"}
            t0 = time.perf_counter()
            if self.o.keyword:
                outcome = self.keyword_flow(scope)
            else:
                outcome = self.number_flow(scope)
            self.timings["query_s"] = round(time.perf_counter() - t0, 1)
            outcome.update(self.common_result(scope))
            ok = outcome.get("status") not in ("failed", "WAIT_HUMAN_LOGIN")
            return outcome
        except (LoginUnavailable, ScopeFilterError, QueryFlowError) as exc:
            outcome = {"status": type(exc).__name__.upper(), "reason": str(exc)}
            if isinstance(exc, LoginUnavailable):
                outcome["auth_state"] = exc.auth_state
            outcome.update(self.common_result({}))
            return outcome
        finally:
            self.timings["total_s"] = round(time.perf_counter() - t_total, 1)
            self.p.log_event(event="query_close", outcome=outcome.get("status"),
                             timings=self.timings, retries=self.retries)
            self.p._close_browser()          # 只关闭本入口创建的 context
            self.p.release_lock()            # 只释放自己持有的锁
            self.write_result(outcome)
            self.p.result["finish_reason"] = f"READ_ONLY_QUERY_{outcome.get('status', 'ERROR')}".upper()
            self.p.atomic_result()

    def keyword_flow(self, scope):
        branches = []
        merged_input = []
        for field_id, _label in KEYWORD_FIELDS:
            branch = self.paginate_branch(field_id, self.o.keyword, self.o.limit, self.o.pages)
            branches.append({"field": branch["field"], "status": branch["status"],
                             "reason": branch.get("reason", ""), "pages": branch.get("pages", 1),
                             "items": branch["items"]})
            merged_input.append((field_id, branch["items"][: self.o.limit * 3]))
        status = classify_keyword_outcome(branches)
        candidates = merge_candidates(
            [(b["field"], [i for i in b["items"]]) for b in branches if b["status"] in ("ok", "partial")],
            self.o.limit) if status in ("ok", "partial", "zero_results") else []
        return {"status": status, "keyword": self.o.keyword, "branches": branches,
                "candidates": candidates[: self.o.limit],
                "candidates_truncated": len(candidates) > self.o.limit,
                "sort_basis": "createdAt 降序（客户端合并后按响应真实值排序；同日并列保留并列标记）",
                "sufficient_evidence": status in ("ok", "zero_results"),
                "insufficient_reason": "" if status in ("ok", "zero_results") else
                "部分关键词分支失败（见 branches[].reason），未完成足够取证，不宣称「未找到」或「最新已确认」"
                if status == "partial" else "全部分支失败，查询未成立"}

    def number_flow(self, scope):
        self.page.locator(NUMBER_INPUT).fill(self.o.number)
        branch = {"field": NUMBER_INPUT, "status": "ok", "items": [], "reason": ""}
        try:
            with self.page.expect_response(list_query_response, timeout=30000) as received:
                self.click_query()
            self.page.wait_for_timeout(600)
            items = parse_list_items(received.value.text())
            self.p.save("number_response.json", json.dumps(items, ensure_ascii=False, indent=1))
        except Exception as exc:
            branch.update(status="failed", reason=f"{type(exc).__name__}: {exc}"[:200])
            return {"status": "failed", "number": self.o.number, "reason": branch["reason"]}
        candidate, err = exact_match(items, self.o.number)
        if err:
            return {"status": "AMBIGUOUS_NUMBER", "reason": err}
        if candidate is None:
            return {"status": "zero_results", "number": self.o.number,
                    "candidates": [], "sufficient_evidence": True,
                    "sort_basis": "不适用（精确单号查询）",
                    "insufficient_reason": ""}
        result = {"status": "ok", "number": self.o.number, "candidates": [candidate],
                  "sufficient_evidence": True, "sort_basis": "不适用（精确单号查询）",
                  "insufficient_reason": ""}
        if self.o.snapshot:
            t0 = time.perf_counter()
            # 本分支已捕获的精确列表响应作为 identity hint 交接：fetch_template 内部
            # 仍实时核验主表 bizNumber/UUID（历史制单人≠当前登录人时，_target_list 的
            # 默认「仅当前制单人」范围查不到该单，hint 提供定位线索，主表验证不放宽）。
            snapshot = fetch_template(self.p, self.o.number,
                                      lookup_list=str(self.p.ev / "number_response.json"))
            view = observe_template_view(self.p, snapshot)
            self.timings["detail_s"] = round(time.perf_counter() - t0, 1)
            snap_path = self.p.run_dir / "template_snapshot.json"
            snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2,
                                            default=str), encoding="utf-8", newline="\n")
            from bpm.plan import file_hash
            result["snapshot"] = {"path": str(snap_path), "sha256": file_hash(snap_path),
                                  "uuid": snapshot.get("uuid"),
                                  "view_tables": {t["title"]: t["row_count"] for t in view.get("tables", [])},
                                  "operator_observed": view.get("operator")}
        return result

    def common_result(self, scope):
        return {"input": {"keyword": self.o.keyword, "number": self.o.number,
                          "creator": self.o.creator, "department": self.o.department,
                          "date_range": [self.o.date_from, self.o.date_to],
                          "limit": self.o.limit, "snapshot": self.o.snapshot},
                "scope": scope, "timings_s": self.timings, "retries": self.retries,
                "evidence": {"events": "events.jsonl", "attempt": self.p.attempt.name},
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def write_result(self, outcome):
        import io as _io
        payload = dict(outcome)
        payload.setdefault("input", {})
        payload.setdefault("timings_s", self.timings)
        with _io.open(self.p.run_dir / "query_result.json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)


class LoginUnavailable(RuntimeError):
    def __init__(self, message, *, auth_state="UNKNOWN"):
        super().__init__(message)
        self.auth_state = auth_state


class ScopeFilterError(RuntimeError):
    pass


class QueryFlowError(RuntimeError):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="BPM 报销单只读查询（关键词/精确单号；不填不存）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--keyword", help="关键词（主表备注/明细摘要/明细备注 三分支 OR 合并）")
    mode.add_argument("--number", help="完整单号（精确字符串匹配，保留前导零）")
    parser.add_argument("--creator", help="可选：制单人（组织选择器，多候选即停）")
    parser.add_argument("--department", help="可选：申请部门（组织选择器，多候选即停）")
    parser.add_argument("--date-from", help="可选：制单日期起 YYYY-MM-DD")
    parser.add_argument("--date-to", help="可选：制单日期止 YYYY-MM-DD")
    parser.add_argument("--expect-name", default=None, help="可选：预期登录人；未指定则自动发现当前账号")
    parser.add_argument("--limit", type=int, default=5, help="候选上限，默认 5（1—20）")
    parser.add_argument("--pages", type=int, default=3, help="单分支翻页上限，默认 3 页")
    parser.add_argument("--snapshot", action="store_true", help="仅 --number：另读模板快照并核验主表")
    parser.add_argument("--login-wait", type=float, default=480.0)
    parser.add_argument("--wall-cap", type=float, default=1200.0)
    parser.add_argument("--run", default=time.strftime("%Y%m%d-%H%M%S") + "-query")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    errors = validate_cli(args)
    if errors:
        print(json.dumps({"status": "INVALID_ARGS", "errors": errors}, ensure_ascii=False))
        return 2
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", args.run):
        print(json.dumps({"status": "INVALID_RUN_ID"}, ensure_ascii=False))
        return 2
    cli = QueryCLI(args)
    outcome = cli.run()
    print(json.dumps(outcome, ensure_ascii=False, default=str))
    return 0 if outcome.get("status") in ("ok", "zero_results") else 2


if __name__ == "__main__":
    raise SystemExit(main())
