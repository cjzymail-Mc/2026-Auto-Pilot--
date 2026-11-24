# -*- coding: utf-8 -*-
"""Dedicated BPM 请假单 entry: guarded fill, and draft save only via the
authorized controller (2026-11-20 daily authorization). 提交/流转/推送 are
never performed in any mode.

Default fill mode parks the window for on-site review with the endpoint
route dropped, so the user's own 保存 click can reach the API. With
--draft-request the fill is followed by one exact SaveController save of
the same form plus persisted reopen verification.

--observe performs read-only structure discovery (list route, form
component, field controls) without touching any field.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from bpm.browser_probe import HOST, PASS, SESSION_STATE
from bpm.evection import inventory, read_value
from bpm.login import LoginProbe
from bpm.session import observed_identity, read_state, state_usable

# Direct-route guesses follow the platform convention (evections/reimburses);
# the menu fallback discovers the real path when these miss.
CANDIDATE_LIST_PATHS = ("/oa/leaves", "/oa/leave")
SAFE_POSTS = {("oa.api.qiaodan.com", path) for path in (
    "/kindlytips/query", "/affiche/homequerybyoption", "/leave/query/20/1",
)}
# Duration reckoning is a calculation read; enabled only while filling times.
CALC_POSTS = {("ams.api.qiaodan.com", "/shiftapi/getleavereckon")}
NEW_FORM_MARK = re.compile(r"(添加新项|新增)")


class LeaveError(RuntimeError):
    pass


def unique(locator, label):
    if locator.count() != 1 or not locator.is_visible():
        raise LeaveError(f"无法唯一定位可见的{label}")
    return locator


def save_json(probe, name, value):
    return probe.save(name, json.dumps(value, ensure_ascii=False, indent=2))


def load_facts(path):
    """Facts come only from this request's explicit user instruction."""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    required = {"leave_type", "start", "end", "reason"}
    if not required <= set(payload) or set(payload) - required - {"statement"}:
        raise LeaveError("请假事实字段不符（leave_type/start/end/reason）")
    for key in ("leave_type", "reason"):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise LeaveError(f"{key}不能为空")
    parsed = {}
    for key in ("start", "end"):
        try:
            moment = datetime.fromisoformat(payload[key])
        except ValueError:
            raise LeaveError(f"{key}不是 YYYY-MM-DDTHH:MM 格式") from None
        if payload[key] != moment.strftime("%Y-%m-%dT%H:%M"):
            raise LeaveError(f"{key}须为 YYYY-MM-DDTHH:MM 格式")
        parsed[key] = moment
    if parsed["end"] <= parsed["start"]:
        raise LeaveError("结束时间须晚于开始时间")
    return payload


class LeaveProbe(LoginProbe):
    def _launch(self):
        self._launch_isolated_guarded_context(headless=False)
        self._inject_session_state()
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(15000)

    def authenticate(self):
        result = self.phase_entry()
        deadline = time.monotonic() + 25
        while result != PASS and time.monotonic() < deadline:
            self.page.wait_for_timeout(600)
            if self.login_state(self.page)[0] == "LOGGED_IN":
                result = PASS
        if result != PASS:
            raise LeaveError("WAIT_HUMAN_LOGIN")
        self._save_session_state()
        self.ctx.route("**/*", self.read_only_route)
        return self.verify_identity()

    def read_only_route(self, route):
        request = route.request
        url = urlsplit(request.url)
        key = (url.hostname, url.path.lower())
        additional_reads = getattr(self, "calculation_posts", ())
        save_adapter = getattr(self, "save_adapter", None)
        if request.method in {"GET", "HEAD", "OPTIONS"} or (
                request.method == "POST" and (key in SAFE_POSTS or key in additional_reads)) or (
                save_adapter is not None and save_adapter.allow_request(request)):
            route.fallback()
        else:
            self.log_event(event="leave_request_refused", method=request.method,
                           host=url.hostname, path=url.path)
            route.abort("blockedbyclient")

    def refused_posts(self):
        posts = []
        path = self.run_dir / "events.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if (event.get("event") == "leave_request_refused"
                    and event.get("method") == "POST"):
                posts.append(f'{event.get("host")}{event.get("path")}')
        return sorted(set(posts))

    def verify_identity(self, expected=None, *, page=None):
        page = page or self.page
        if not state_usable(SESSION_STATE) or self.login_state(page)[0] != "LOGGED_IN":
            raise LeaveError("WAIT_HUMAN_LOGIN")
        principal = observed_identity(page, read_state(SESSION_STATE))
        if not principal["user_id"] and not principal["employee_id"]:
            raise LeaveError("当前 OA 账号缺少可唯一核对的标识")
        if expected is not None and principal != expected:
            raise LeaveError("OA 操作人发生变化")
        return principal

    def click_button(self, scope, label):
        self._click_guard(label)
        target = scope.get_by_role("button", name=label, exact=True)
        if target.count() == 0:
            target = scope.locator(f'button[title="{label}"]')
        target = unique(target, label)
        if not target.is_enabled():
            raise LeaveError(f"{label}不可操作")
        self.log_event(event="leave_click", label=label)
        target.click()

    def dismiss_page_dialogs(self):
        """In-DOM PrimeNG dialogs block clicks; dismiss only (never accept).

        Escape first; a visible 取消/关闭-type button is the only clickable
        fallback — 确定/是/确认 stay untouched per AGENTS red lines."""
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            mask = self.page.locator(".ui-dialog-mask:visible")
            dialog = self.page.locator(".ui-dialog:visible")
            if mask.count() == 0 and dialog.count() == 0:
                return
            texts = [d.inner_text().strip()[:400] for d in dialog.all() if d.is_visible()]
            if texts:
                self.log_event(event="leave_page_dialog", text=texts)
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(800)
            if self.page.locator(".ui-dialog-mask:visible").count() == 0:
                continue
            for label in ("取消", "关 闭", "关闭", "否"):
                fallback = self.page.locator(f'.ui-dialog:visible button[title="{label}"],'
                                             f'.ui-dialog:visible .ui-button:has-text("{label}")')
                if fallback.count() == 1:
                    self._click_guard(label)
                    fallback.first.click()
                    self.page.wait_for_timeout(800)
                    break
        if self.page.locator(".ui-dialog-mask:visible").count():
            raise LeaveError("页面对话框无法安全关闭")

    # ---- observe: discover the leave list route and the new-form layout ----
    def discover_list(self):
        for path in CANDIDATE_LIST_PATHS:
            self.page.goto(HOST + path, wait_until="domcontentloaded", timeout=45000)
            try:
                self.page.locator("p-table").first.wait_for(timeout=30000)
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
            current = urlsplit(self.page.url)
            table = self.page.locator("p-table:visible")
            self.log_event(event="leave_route_try", tried=path, landed=current.path,
                           query=current.query, tables=table.count())
            self.shot(self.page, "route_try_" + path.strip("/").replace("/", "_") + ".png")
            if (f"{current.scheme}://{current.netloc}" == HOST
                    and current.path == path and table.count() >= 1):
                self.log_event(event="leave_list_route", source="direct", path=path)
                return path
        self.page.goto(HOST + "/", wait_until="domcontentloaded", timeout=45000)
        self.page.wait_for_timeout(2500)
        self.save("home.html", self.page.content())
        save_json(self, "home_text_map.json", self.page.evaluate("""() => {
          const shown = e => !!e.getClientRects().length;
          const seen = new Set(), out = [];
          for (const e of document.querySelectorAll('a,button,li,span,div[role]')) {
            if (!shown(e)) continue;
            const text = e.innerText.trim();
            if (!text || text.length > 30 || seen.has(text)) continue;
            seen.add(text);
            out.push({tag: e.tagName.toLowerCase(), cls: String(e.className).slice(0, 80), text});
          }
          return out.slice(0, 400);
        }"""))
        candidates = self.page.get_by_text("请假单")
        matches = [node for node in candidates.all() if node.is_visible()]
        save_json(self, "menu_matches.json", [
            {"html": node.evaluate("e => e.outerHTML.slice(0, 1200)")} for node in matches])
        if not matches:
            raise LeaveError("OA 菜单未找到可见的请假单入口")
        self._click_guard("请假单")
        matches[0].click()
        self.page.wait_for_timeout(2500)
        current = urlsplit(self.page.url)
        if f"{current.scheme}://{current.netloc}" != HOST or not current.path.startswith("/oa/"):
            raise LeaveError(f"菜单点击后未停留在 OA 路由（{current.path}）")
        self.log_event(event="leave_list_route", source="menu", path=current.path)
        return current.path

    def scan_api_paths(self):
        """Read-only static discovery: fetch the SPA bundles and list the
        /Leave/* API endpoints they reference, so save controllers bind a
        real path instead of guessing."""
        srcs = self.page.evaluate("[...document.scripts].map(s => s.src).filter(Boolean)")
        hits = {}
        patterns = (r'["\'](/[Ll]eave[A-Za-z0-9_/.-]*)["\']', r'["\']Leave/([A-Za-z0-9_/.-]+)["\']')
        for src in srcs[:80]:
            try:
                reply = self.page.request.get(src, timeout=20000)
                text = reply.text()
            except Exception:
                continue
            for pattern in patterns:
                for path in set(re.findall(pattern, text)):
                    if len(path) < 30 and not path.endswith((".js", ".css", ".html", ".ico", ".png")):
                        hits.setdefault("/" + path.lstrip("/"), []).append(src.rsplit("/", 1)[-1])
        save_json(self, "leave_api_paths.json", hits)
        self.log_event(event="leave_api_scan", scripts=len(srcs), paths=len(hits))
        return hits

    def open_list(self):
        path = self.discover_list()
        root_tag = self.page.evaluate("""() => {
          const shown = e => !!e.getClientRects().length;
          const table = [...document.querySelectorAll('p-table')].filter(shown)[0];
          if (!table) return '';
          let node = table, outermost = null;
          while (node) {
            if (node.tagName && node.tagName.startsWith('QD-')) outermost = node;
            node = node.parentElement;
          }
          return outermost ? outermost.tagName.toLowerCase() : '';
        }""")
        if not root_tag:
            raise LeaveError("请假单列表缺少 qd-* 根组件")
        listing = unique(self.page.locator(f"{root_tag}:visible"), "请假单列表")
        listing.wait_for(timeout=40000)
        self.page.wait_for_timeout(600)
        self.dismiss_page_dialogs()
        if getattr(self.args, "api_scan", False):
            self.scan_api_paths()
        layout = inventory(listing)
        save_json(self, "list_layout.json",
                  {"path": path, "root_tag": root_tag, "layout": layout})
        self.shot(self.page, "list.png")
        buttons = [label for item in layout["buttons"]
                   for label in item["label"] if NEW_FORM_MARK.search(label)]
        if not buttons:
            raise LeaveError("请假单列表未找到新增入口按钮")
        return listing, buttons[0]

    def open_form(self, listing, button_label):
        self.click_button(listing, button_label)
        deadline = time.monotonic() + 40
        root_tag = ""
        chain = []
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(1000)
            chain = self.page.evaluate("""() => {
              const shown = e => !!e.getClientRects().length;
              const field = [...document.querySelectorAll('qd-dynamic-form-control')]
                .filter(shown)[0];
              if (!field) return [];
              const tags = [];
              for (let node = field; node; node = node.parentElement)
                if (node.tagName && node.tagName.startsWith('QD-')) tags.push(node.tagName.toLowerCase());
              return tags;
            }""")
            if chain:
                break
        if not chain:
            raise LeaveError("新增后未见可见的 qd-* 表单组件")
        root_tag = chain[0] if len(chain) == 1 else (
            chain[-2] if chain[-1] == "qd-root" else chain[-1])
        save_json(self, "form_components.json",
                  {"url": self.page.url, "chain": chain, "root_tag": root_tag})
        form = unique(self.page.locator(f"{root_tag}:visible"), "请假单表单")
        self.assert_new(form)
        return form

    def assert_new(self, form):
        url = urlsplit(self.page.url)
        query = parse_qs(url.query, keep_blank_values=True)
        if (f"{url.scheme}://{url.netloc}" != HOST or any(query.get("id", [""]))
                or self.header_value(form, "单据编号")):
            raise LeaveError("未能核实为无单号的新请假单")

    def header_field(self, form, label, *, page=None):
        return unique(form.locator("qd-dynamic-form-control:visible").filter(
            has=(page or self.page).get_by_text(label, exact=True)), label)

    def header_value(self, form, label, *, page=None):
        return read_value(self.header_field(form, label, page=page))

    def form_details(self, form):
        """Per-control DOM so the fill mapping uses real selectors."""
        return form.evaluate("""root => {
          const shown = e => !!e.getClientRects().length;
          return [...root.querySelectorAll('qd-dynamic-form-control')].filter(shown).map(e => ({
            text: e.innerText.trim().slice(0, 500), cls: e.className,
            html: e.outerHTML.slice(0, 2500)
          }));
        }""")

    # ---- fill: type dropdown, reason text, one detail row; never save ----
    def detail_table(self, form, *, page=None):
        return unique(form.locator("p-table:visible").filter(
            has=(page or self.page).locator("th.prop-startTime")), "请假明细表")

    def detail_rows(self, form, *, page=None):
        return (self.detail_table(form, page=page).locator("tbody > tr:visible")
                .filter(has=(page or self.page).locator("td.prop-startTime")))

    def snapshot(self, form, operator, *, is_new, page=None):
        """Full independent readback used for pre/post-save verification."""
        page = page or self.page
        row = unique(self.detail_rows(form, page=page), "请假明细行")
        detail = {prop: read_value(unique(row.locator(f"td.prop-{prop}"), prop)) for prop in (
            "startTime", "endTime", "applyDuration", "workDuration",
            "factStartTime", "factEndTime", "description")}
        identity_ok = (self.header_value(form, "申请人", page=page) == operator
                       and self.header_value(form, "制单人", page=page) == operator)
        return {"page": {"is_new": is_new,
                         "biz_number": self.header_value(form, "单据编号", page=page),
                         "status": self.header_value(form, "单据状态", page=page)},
                "leave_type": self.leave_type_value(form, page=page),
                "reason": self.header_value(form, "事由", page=page),
                "detail": detail,
                "operator": operator if identity_ok else None,
                "extras_empty": (not self.header_value(form, "工作交接", page=page)
                                 and not self.header_value(form, "备注", page=page))}

    def leave_type_value(self, form, *, page=None):
        """p-dropdown shows the selection on its input or a label span."""
        field = self.header_field(form, "请假类型", page=page)
        return field.evaluate("""e => {
          const root = e.querySelector('p-dropdown') || e;
          const inp = root.querySelector('input:not([type=hidden])');
          const label = root.querySelector('.ui-dropdown-label');
          const fromInput = inp && inp.value ? inp.value.trim() : '';
          const fromLabel = label ? label.textContent.trim() : '';
          return fromInput || fromLabel;
        }""")

    def expect_leave_type(self, form, value):
        for _ in range(8):
            self.page.wait_for_timeout(600)
            current = self.leave_type_value(form)
            if current == value:
                return
        self.save("leave_type_field_dump.html", self.header_field(
            form, "请假类型").evaluate("e => e.outerHTML.slice(0, 2000)"))
        raise LeaveError(f"请假类型回读不一致（读到 {current!r}）")

    def select_leave_type(self, form, value):
        field = self.header_field(form, "请假类型")
        dropdown = unique(field.locator("p-dropdown:visible"), "请假类型下拉")
        self._click_guard(value)
        dropdown.click()
        panel = unique(self.page.locator(".ui-dropdown-panel:visible"), "请假类型选项面板")
        self.page.wait_for_timeout(600)
        options = [item.strip() for item in panel.locator(
            "li.ui-dropdown-item").all_inner_texts()]
        save_json(self, "leave_type_options.json", {"options": options})
        if value not in options:
            raise LeaveError(f"请假类型无「{value}」选项：{options}")
        option = unique(panel.locator("li.ui-dropdown-item").filter(
            has=self.page.get_by_text(value, exact=True)), f"选项{value}")
        option.click()
        self.expect_leave_type(form, value)
        self.dismiss_page_dialogs()

    def fill_reason(self, form, reason):
        field = self.header_field(form, "事由")
        inp = unique(field.locator("input[type=text]:visible"), "事由输入框")
        if not inp.is_editable() or inp.input_value():
            raise LeaveError("事由不是空白可编辑字段")
        inp.fill(reason)
        inp.press("Tab")
        self.page.wait_for_timeout(600)
        if self.header_value(form, "事由") != reason:
            raise LeaveError("事由回读不一致")

    def fill_detail(self, form, facts):
        from bpm.evection_save import local_minute
        self.calculation_posts = CALC_POSTS
        table = self.detail_table(form)
        self.dismiss_page_dialogs()
        self.click_button(table, "新增")
        self.page.wait_for_timeout(600)
        rows = table.locator("tbody > tr:visible").filter(
            has=self.page.locator("td.prop-startTime"))
        if rows.count() != 1:
            raise LeaveError("请假明细行数不为 1")
        row = rows.first
        for field, key in (("startTime", "start"), ("endTime", "end")):
            cell = unique(row.locator(f"td.prop-{field}"), key)
            if read_value(cell):
                raise LeaveError("请假明细原值非空")
            cell.dblclick(timeout=8000)
            self.page.wait_for_timeout(600)
            inp = unique(cell.locator("qd-date-picker input[type=text]:visible,"
                                      " input[type=text]:visible"), key)
            inp.fill(facts[key].replace("T", " "))
            inp.press("Enter")
            self.page.keyboard.press("Tab")
            for _ in range(8):
                self.page.wait_for_timeout(600)
                try:
                    if local_minute(read_value(cell)) == facts[key]:
                        break
                except ValueError:
                    pass
            else:
                raise LeaveError(f"请假明细{key}未回读到确认时分")
            self.dismiss_page_dialogs()

    def fill_form(self, form, facts, principal):
        self.verify_identity(principal)
        identity = {label: self.header_value(form, label)
                    for label in ("申请人", "申请部门", "公司", "制单人")}
        if (identity["申请人"] != principal["name"] or identity["制单人"] != principal["name"]
                or not all(identity.values())):
            raise LeaveError("新页身份默认值未核实")
        if self.header_value(form, "单据状态") != "编制中":
            raise LeaveError("新页单据状态不是编制中")
        self.select_leave_type(form, facts["leave_type"])
        self.fill_reason(form, facts["reason"])
        self.fill_detail(form, facts)
        snapshot = self.readback(form, facts, identity)
        save_json(self, "final_layout.json", inventory(form))
        self.verify_identity(principal)
        return snapshot

    def readback(self, form, facts, identity):
        from bpm.evection_save import local_minute
        if self.detail_rows(form).count() != 1:
            raise LeaveError("终局回读行数不为 1")
        base = self.snapshot(form, identity["申请人"], is_new=True)
        save_button = form.locator('button[title="保存"]')
        snapshot = {
            "identity": identity,
            "leave_type": base["leave_type"],
            "reason": base["reason"],
            "detail": base["detail"],
            "status": base["page"]["status"],
            "handover": "" if base["extras_empty"] else "非空",
            "remark": "" if base["extras_empty"] else "非空",
            "save_button_disabled": save_button.count() == 1 and save_button.first.is_disabled(),
        }
        save_json(self, "leave_readback.json", snapshot)
        if (snapshot["leave_type"] != facts["leave_type"]
                or snapshot["reason"] != facts["reason"]
                or local_minute(base["detail"]["startTime"]) != facts["start"]
                or local_minute(base["detail"]["endTime"]) != facts["end"]
                or snapshot["identity"] != identity):
            raise LeaveError("请假单终局回读存在差异")
        return snapshot

    def enable_manual_review(self):
        """Drop the endpoint-level read-only route before on-site review.

        The user's own 保存 click must reach the API (2026-11-20: a manual
        save during park was aborted by this route and surfaced as
        服务器连接失败). The domain-level ContextGuard stays installed;
        agent-side clicks keep passing _click_guard."""
        self.ctx.unroute("**/*", self.read_only_route)
        self.log_event(event="leave_manual_review_network", routes="domain_guard_only")

    def park(self):
        review_seconds = self.args.keep_open_minutes * 60
        self.budget.wall_cap = self.budget.monotonic_wall() + review_seconds + 30
        end = time.monotonic() + review_seconds
        self.log_event(event="keep_open_start", minutes=self.args.keep_open_minutes)
        while time.monotonic() < end and not self.page.is_closed():
            try:
                self.page.wait_for_timeout(1000)
            except Exception:
                if self.page.is_closed():
                    break
                raise
        self.log_event(event="keep_open_end")

    def deliver(self, status, reason=None, save_status="NOT_AUTHORIZED"):
        self.result.update(finish_reason=status, task_status=status,
                           save_status=save_status, reason=reason)
        self.atomic_result()
        self.log_event(event="result_delivered", task_status=status, reason=reason)
        self.say(status, reason or "")


def observe(options):
    args = SimpleNamespace(**vars(options), doc_id=None, tech_budget=300,
                           login_wait=0, wall_cap=780, fill_plan=None, login_only=True)
    probe = LeaveProbe(args)
    try:
        probe.acquire_lock()
        if not state_usable(SESSION_STATE):
            raise LeaveError("WAIT_HUMAN_LOGIN")
        probe._launch()
        principal = probe.authenticate()
        listing, button_label = probe.open_list()
        form = probe.open_form(listing, button_label)
        save_json(probe, "new_form_layout.json", {"path": urlsplit(probe.page.url).path,
                                                  "query": urlsplit(probe.page.url).query,
                                                  "layout": inventory(form)})
        save_json(probe, "new_form_details.json", probe.form_details(form))
        probe.shot(probe.page, "new_form.png")
        probe.verify_identity(principal)
        probe.result.update(operator=principal["name"], list_button=button_label,
                            refused_posts=probe.refused_posts())
        probe.deliver("SUCCESS_READ_ONLY_OBSERVATION")
        return 0
    except Exception as exc:
        if probe.ctx and getattr(probe, "page", None) and not probe.page.is_closed():
            probe.shot(probe.page, "blocked.png")
            probe.save("probe_error.txt", str(exc)[:4000])
        probe.deliver("NEEDS_INPUT",
                      str(exc).splitlines()[0][:220] if isinstance(exc, LeaveError)
                      else type(exc).__name__)
        return 2
    finally:
        probe._close_browser()
        probe.release_lock()
        probe.budget.close()


def fill(options):
    facts = load_facts(options.facts)
    if not options.expect_name:
        raise LeaveError("fill 需要本次核实的操作人 --expect-name")
    draft = None
    if options.draft_request:
        from bpm.leave_save import LeaveSaveController, load_request
        from bpm.paths import ROOT
        from bpm.plan import file_hash
        auth = load_request(options.draft_request, options.run, facts,
                            file_hash(options.facts), ROOT / "automation/runs" / options.run)
        draft = {"task_id": options.run, "document_type": "leave",
                 "operator": options.expect_name, "facts": facts, "authorization": auth,
                 "sources": {key: {"path": str(path.resolve()), "sha256": file_hash(path)}
                             for key, path in (("facts", options.facts),
                                               ("request", options.draft_request))}}
    if options.validate_only:
        label = "LEAVE_SAVE_VALIDATED" if draft else "LEAVE_FACTS_VALIDATED"
        print(f"{label} ({facts['leave_type']} {facts['start']}~{facts['end']})")
        return 0
    args = SimpleNamespace(**vars(options), doc_id=None, tech_budget=300,
                           login_wait=0, wall_cap=780, fill_plan=None, login_only=True)
    probe = LeaveProbe(args)
    form = None
    controller = None
    try:
        if draft:
            from bpm.leave_save import LeaveSaveController
            from bpm.paths import ROOT
            controller = LeaveSaveController(draft, None, probe.attempt, options.expect_name,
                                             journal_dir=ROOT / "automation/task-registry")
            if controller.journal.exists():
                prior = json.loads(controller.journal.read_text(encoding="utf-8"))
                if (prior.get("status") not in {"NEEDS_INPUT", "READBACK_MISMATCH"}
                        or prior.get("plan_hash") != controller.plan_hash):
                    raise LeaveError("已有保存意图或绑定不符，需只读核实")
            save_json(probe, "draft_plan.json", draft)
        probe.acquire_lock()
        if not state_usable(SESSION_STATE):
            raise LeaveError("WAIT_HUMAN_LOGIN")
        probe._launch()
        principal = probe.authenticate()
        if principal["name"] != options.expect_name:
            raise LeaveError("本次操作人与预期不符")
        listing, button_label = probe.open_list()
        form = probe.open_form(listing, button_label)
        save_json(probe, "leave_facts.json", facts)
        snapshot = probe.fill_form(form, facts, principal)
        if controller:
            from bpm.leave_save import LeaveSaveAdapter
            probe.save_adapter = controller.adapter = LeaveSaveAdapter(
                probe, form, draft, principal)
            saved = controller.run()
            probe.result.update(readback=snapshot,
                                save_identity=saved.get("identity") or saved.get("pending_identity"),
                                saved_api_path=getattr(controller.adapter, "saved_path", None))
            probe.deliver(saved["status"], saved.get("reason"), saved["status"])
            probe.park()
            return 0 if saved["status"] == "SUCCESS_DRAFT_SAVED" else 2
        probe.result.update(readback=snapshot,
                            review_screenshot=probe.shot(probe.page, "review.png"))
        probe.deliver("SUCCESS_FILL_ONLY_REVIEW")
        probe.enable_manual_review()
        probe.park()
        return 0
    except Exception as exc:
        if probe.ctx and getattr(probe, "page", None) and not probe.page.is_closed():
            probe.shot(probe.page, "blocked.png")
            probe.save("probe_error.txt", str(exc)[:4000])
        probe.deliver("NEEDS_INPUT",
                      str(exc).splitlines()[0][:220] if isinstance(exc, LeaveError)
                      else type(exc).__name__)
        if form is not None and not probe.page.is_closed():
            probe.park()
        return 2
    finally:
        probe._close_browser()
        probe.release_lock()
        probe.budget.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--api-scan", action="store_true",
                        help="observe mode: also scan bundles for /Leave/* API paths")
    parser.add_argument("--facts", type=Path)
    parser.add_argument("--draft-request", type=Path)
    parser.add_argument("--expect-name")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--keep-open-minutes", type=int, default=20)
    options = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", options.run):
        parser.error("invalid run id")
    if not 1 <= options.keep_open_minutes <= 120:
        parser.error("invalid review duration")
    if not options.observe and not options.facts:
        parser.error("fill mode requires --facts")
    if options.observe and (options.facts or options.draft_request):
        parser.error("observe mode takes no facts or draft request")
    if options.draft_request and options.validate_only and not options.facts:
        parser.error("--draft-request validation requires --facts")
    if options.observe:
        return observe(options)
    return fill(options)


if __name__ == "__main__":
    raise SystemExit(main())
