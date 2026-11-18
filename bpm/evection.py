"""Dedicated BPM 出差单 entry. Only opens new, unsaved forms for review."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from bpm.browser_probe import HOST, PASS, SESSION_STATE
from bpm.login import LoginProbe
from bpm.session import observed_identity, read_state, state_usable


LIST = "qd-evection"
FORM = "qd-evection-detail"
LIST_PATH = "/oa/evections"
FORM_PATH = "/oa/evection"
TRIP_COLUMNS = ("出发城市", "目的城市", "开始日期", "结束日期", "天数", "工作事项")
TRIP_FIELDS = ("startPlace", "place", "startTime", "endTime", "days", "workItems")
SAFE_POSTS = {("oa.api.qiaodan.com", path) for path in (
    "/evection/query/20/1", "/kindlytips/query", "/affiche/homequerybyoption", "/airport/query",
)}


class EvectionError(RuntimeError):
    pass


def itinerary(source, plan):
    """Read a reviewed transcription bound to the source image bytes."""
    with plan.open(encoding="utf-8-sig") as stream:
        payload = json.load(stream)
    if set(payload) != {"image_sha256", "trips"}:
        raise EvectionError("出差行程计划字段不符")
    if hashlib.sha256(source.read_bytes()).hexdigest() != payload["image_sha256"]:
        raise EvectionError("行程图片与核对版本不一致")
    rows = payload["trips"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
        raise EvectionError("行程行数无效")
    for i, row in enumerate(rows):
        if (not isinstance(row, list) or len(row) != len(TRIP_COLUMNS)
                or any(not isinstance(value, str) or not value.strip() for value in row)):
            raise EvectionError(f"第 {i + 1} 段行程有缺项")
        start, end = date.fromisoformat(row[2]), date.fromisoformat(row[3])
        if (row[2] != start.isoformat() or row[3] != end.isoformat()
                or end < start or row[4] != str((end - start).days + 1)):
            raise EvectionError(f"第 {i + 1} 段日期或天数不闭合")
        if row[0] == row[1] or (i and rows[i - 1][1] != row[0]):
            raise EvectionError(f"第 {i + 1} 段出发与到达城市不闭合")
    return payload


def unique(locator, label):
    if locator.count() != 1 or not locator.is_visible():
        raise EvectionError(f"无法唯一定位可见的{label}")
    return locator


def save_json(probe, name, value):
    return probe.save(name, json.dumps(value, ensure_ascii=False, indent=2))


def read_value(locator):
    return locator.evaluate("""e => (e.querySelector('input:not([type=hidden]),textarea')?.value
                                     ?? e.innerText).trim()""")


def read_trip_table(table):
    """Independent read of rendered cells in order, after all editors close."""
    return table.evaluate("""(el, fields) => [...el.querySelectorAll('tbody > tr')]
      .filter(row => row.getClientRects().length && row.querySelector('td.prop-startPlace'))
      .map(row => fields.map(field => {
        const cells = row.querySelectorAll('td.prop-' + field);
        return cells.length === 1 && !cells[0].querySelector('input,textarea,select')
          ? cells[0].innerText.trim() : null;
      }))""", TRIP_FIELDS)


def unique_city_code(records):
    """Exact name matches only. Prefer the sole airport city over homonyms."""
    if len(records) > 1:
        records = [row for row in records if re.fullmatch(r"[A-Z]{3}", row[1])]
    if len(records) == 1 and records[0][0]:
        return records[0][0]
    return None


def inventory(scope):
    return scope.evaluate(r"""root => {
      const shown = e => !!e.getClientRects().length;
      const text = e => e.innerText.trim();
      const label = e => [e.getAttribute('title'), e.getAttribute('aria-label'),
                          e.textContent.trim()].filter(Boolean);
      return {
        buttons: [...root.querySelectorAll('button')].filter(shown).map(e => ({
          label: label(e), cls: e.className, disabled: e.disabled})),
        filters: [...root.querySelectorAll('qd-dynamic-query-control input')].filter(shown)
          .map(e => ({id: e.id, value: e.value, row: e.closest('.form-row')?.className})),
        headers: [...root.querySelectorAll('qd-dynamic-form-control')].filter(shown).map(e => ({
          text: text(e), controls: [...e.querySelectorAll('input,textarea,select')].filter(shown)
            .map(x => ({type: x.type, value: x.value, readOnly: x.readOnly, disabled: x.disabled})),
          cls: e.className
        })),
        tables: [...root.querySelectorAll('p-table')].filter(shown).map(e => ({
          caption: e.querySelector('.ui-table-caption')?.innerText.trim(),
          columns: [...e.querySelectorAll('thead th')].filter(shown).map(x => ({
            label: text(x), cls: x.className})),
          rows: [...e.querySelectorAll('tbody > tr')].filter(shown).slice(0, 12).map(r =>
            [...r.cells].filter(shown).map(x => ({text: text(x), cls: x.className,
              values: [...x.querySelectorAll('input,textarea,select')].filter(shown).map(y => y.value)})))
        }))
      };
    }""")


class EvectionProbe(LoginProbe):
    def _launch(self):
        self._launch_isolated_guarded_context(headless=False)
        if not self.args.force_scan:
            self._inject_session_state()
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(15000)

    def authenticate(self):
        result = self.phase_entry()
        deadline = time.monotonic() + 25
        while result != PASS and not self.args.force_scan and time.monotonic() < deadline:
            self.page.wait_for_timeout(600)
            if self.login_state(self.page)[0] == "LOGGED_IN":
                result = PASS
        if result != PASS and self.args.force_scan and result == "LOGIN_REQUIRED":
            result = self.wait_login()
        if result != PASS:
            raise EvectionError("WAIT_HUMAN_LOGIN")
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
            self.log_event(event="evection_request_refused", method=request.method,
                           host=url.hostname, path=url.path)
            route.abort("blockedbyclient")

    def verify_identity(self, expected=None, *, page=None):
        page = page or self.page
        if not state_usable(SESSION_STATE) or self.login_state(page)[0] != "LOGGED_IN":
            raise EvectionError("WAIT_HUMAN_LOGIN")
        principal = observed_identity(page, read_state(SESSION_STATE))
        if not principal["user_id"] and not principal["employee_id"]:
            raise EvectionError("当前 OA 账号缺少可唯一核对的标识")
        if expected is not None and principal != expected:
            raise EvectionError("OA 操作人发生变化")
        return principal

    def click_button(self, scope, label):
        self._click_guard(label)
        target = scope.get_by_role("button", name=label, exact=True)
        if target.count() == 0:
            target = scope.locator(f'button[title="{label}"]')
        target = unique(target, label)
        if not target.is_enabled():
            raise EvectionError(f"{label}不可操作")
        self.log_event(event="evection_click", label=label)
        target.click()

    def open_list(self):
        with self.page.expect_response(lambda r: urlsplit(r.url).path.lower() == "/evection/query/20/1"
                                       and r.request.method == "POST", timeout=30000) as loaded:
            self.page.goto(HOST + LIST_PATH, wait_until="domcontentloaded", timeout=45000)
        if not loaded.value.ok:
            raise EvectionError(f"出差单列表读取失败（HTTP {loaded.value.status}）")
        self.page.locator(f"{LIST} p-table").wait_for(timeout=40000)
        self.page.wait_for_timeout(600)
        return unique(self.page.locator(f"{LIST}:visible"), "出差单列表")

    def read_history(self, listing, principal):
        """Look at the first page of this creator's list, one exact read-only reference."""
        creator = listing.locator(".form-row.CreatedPath input:visible")
        if creator.count() != 1 or creator.input_value().strip() != principal["name"]:
            return {"status": "creator_filter_unverified"}
        rows = listing.locator("tbody > tr:visible").filter(has=self.page.locator("td.prop-bizNumber"))
        if not rows.count():
            clear = listing.locator("button.qd-date-picker-clear:visible")
            if clear.count() != 1:
                return {"status": "date_filter_unverified"}
            self._click_guard("清除日期")
            # Same date control renders its clear button beneath the input.
            # Dispatch the normal UI event and independently verify the filter.
            date_input = clear.locator("xpath=..").locator(":scope > input")
            if date_input.count() != 1 or not date_input.input_value():
                return {"status": "date_filter_unverified"}
            clear.dispatch_event("click")
            self.page.wait_for_timeout(600)
            if listing.locator("button.qd-date-picker-clear:visible").count():
                return {"status": "date_filter_clear_unverified"}
            with self.page.expect_response(lambda r: urlsplit(r.url).path.lower() == "/evection/query/20/1"
                                           and r.request.method == "POST", timeout=30000) as response:
                self.click_button(listing, "查询")
            if not response.value.ok:
                return {"status": "query_failed"}
            self.page.wait_for_timeout(600)
        for row in rows.all():
            names = [read_value(row.locator(f"td.prop-{field}"))
                     for field in ("appliedName", "createdName")]
            if names != [principal["name"]] * 2:
                continue
            number = read_value(row.locator("td.prop-bizNumber"))
            if not number:
                continue
            row.click()
            self.click_button(listing, "查看")
            form = self.page.locator(f"{FORM}:visible")
            form.get_by_text("行程安排", exact=True).wait_for(timeout=40000)
            mode = parse_qs(urlsplit(self.page.url).query).get("type")
            if mode != ["view"] or self.header_value(form, "单据编号") != number:
                raise EvectionError("历史出差单只读身份未核实")
            reference = {"status": "viewed", "number": number,
                         "company": self.header_value(form, "公司"),
                         "department": self.header_value(form, "申请部门"),
                         "cost_center": self.header_value(form, "成本中心"),
                         "purpose": self.header_value(form, "出差事由")}
            self.page.goto(HOST + LIST_PATH, wait_until="domcontentloaded", timeout=45000)
            listing.wait_for(timeout=40000)
            return reference
        return {"status": "no_own_reference_on_first_page"}

    def header_field(self, form, label, *, page=None):
        return unique(form.locator("qd-dynamic-form-control:visible").filter(
            has=(page or self.page).get_by_text(label, exact=True)), label)

    def header_value(self, form, label, *, page=None):
        return read_value(self.header_field(form, label, page=page))

    def open_form(self, listing):
        self.click_button(listing, "添加新项")
        form = self.page.locator(f"{FORM}:visible")
        form.get_by_text("行程安排", exact=True).wait_for(timeout=40000)
        self.page.wait_for_timeout(600)
        self.assert_new(form)
        return form

    def assert_new(self, form):
        url = urlsplit(self.page.url)
        query = parse_qs(url.query, keep_blank_values=True)
        if (f"{url.scheme}://{url.netloc}" != HOST or url.path != FORM_PATH
                or query.get("type") != ["new"] or any(query.get("id", [""]))
                or self.header_value(form, "单据编号")):
            raise EvectionError("未能核实为无单号的新出差单")

    def default_fields(self, form, *, page=None):
        return {label: self.header_value(form, label, page=page) for label in (
            "申请人", "申请部门", "公司", "成本中心", "制单人", "制单部门",
        )}

    def trip_table(self, form, *, page=None):
        table = unique(form.locator("p-table:visible").filter(
            has=(page or self.page).locator("th.prop-startPlace")), "行程安排表")
        for field, label in zip(TRIP_FIELDS, TRIP_COLUMNS):
            column = unique(table.locator(f"th.prop-{field}:visible"), label)
            if column.inner_text().strip() != label:
                raise EvectionError(f"行程安排列名变化（{label}）")
        return table

    def trip_rows(self, table):
        return table.locator("tbody > tr:visible").filter(has=self.page.locator("td.prop-startPlace"))

    def expect_cell(self, cell, value, field):
        for _ in range(4):
            self.page.wait_for_timeout(600)
            if read_value(cell) == value:
                return
        raise EvectionError(f"{field}的页面回读与计划不一致")

    def fill_trip_cell(self, cell, field, value):
        if read_value(cell) == value:
            return
        cell.dblclick(timeout=8000)
        self.page.wait_for_timeout(600)
        if field in ("startPlace", "place"):
            dialog = self.open_city_picker(cell)
            self.pick_city(dialog, value, self.city_codes[value])
        else:
            inp = unique(cell.locator("input:not([type=hidden]):visible, textarea:visible"), field)
            if not inp.is_editable():
                raise EvectionError(f"{field}不是可编辑控件")
            inp.fill(value)
            inp.press("Enter")
        self.page.keyboard.press("Tab")
        self.expect_cell(cell, value, field)

    def open_city_picker(self, cell):
        trigger = unique(cell.locator('button[aria-label="选择表格数据"]:visible'), "城市选择器")
        self._click_guard("选择表格数据")
        trigger.click()
        dialog = self.page.locator(".table-select-dialog:visible")
        dialog.wait_for(timeout=10000)
        self.page.wait_for_timeout(600)
        if self.page.locator(".ui-dialog:visible").count() != 1:
            raise EvectionError("城市选择时出现额外弹窗")
        return dialog

    def city_candidates(self, dialog, value):
        search = unique(dialog.locator("input[type=text]:not([readonly]):visible"), "城市查询输入框")
        search.fill(value)
        search.press("Enter")
        candidate = dialog.locator("tbody > tr:visible").filter(has=self.page.locator(
            "td.prop-cityName").filter(has_text=re.compile(r"^\s*" + re.escape(value) + r"\s*$")))
        self.page.wait_for_timeout(600)
        return candidate

    def preflight_cities(self, table, plan):
        cell = unique(self.trip_rows(table).locator("td.prop-startPlace"), "首段出发城市")
        cell.dblclick(timeout=8000)
        self.page.wait_for_timeout(600)
        dialog = self.open_city_picker(cell)
        cities = dict.fromkeys(city for row in plan["trips"] for city in row[:2])
        try:
            for value in cities:
                candidates = self.city_candidates(dialog, value)
                records = [[read_value(unique(row.locator(f"td.prop-{prop}"), prop))
                            for prop in ("cityCode", "cityThreeCode")] for row in candidates.all()]
                code = unique_city_code(records)
                if not code:
                    raise EvectionError(f"城市档案不能唯一确定（{value}，精确匹配 {len(records)} 条）")
                cities[value] = code
                self.log_event(event="evection_city_preflight", city=value, city_code=code)
        finally:
            if dialog.is_visible() and self.page.locator(".ui-dialog:visible").count() == 1:
                self.click_button(dialog, "取消")
                dialog.wait_for(state="hidden", timeout=10000)
        self.page.keyboard.press("Tab")
        self.city_codes = cities

    def pick_city(self, dialog, value, city_code):
        candidates = self.city_candidates(dialog, value)
        candidate = unique(candidates.filter(has=self.page.locator("td.prop-cityCode").filter(
            has_text=re.compile(r"^\s*" + re.escape(city_code) + r"\s*$"))), f"城市{value}档案{city_code}")
        if not city_code:
            raise EvectionError(f"城市缺少档案编码（{value}）")
        self._click_guard(value)
        candidate.click()
        self.page.wait_for_timeout(600)
        if dialog.is_visible():
            if not candidate.evaluate("e => e.matches('.ui-state-highlight,[aria-selected=true]')"):
                raise EvectionError(f"城市选中状态未确认（{value}）")
            self.click_button(dialog, "确定")
            dialog.wait_for(state="hidden", timeout=10000)
        self.log_event(event="evection_city_selected", city=value, city_code=city_code)

    def fill_form(self, form, plan, principal):
        self.verify_identity(principal)
        defaults = self.default_fields(form)
        if (defaults["申请人"] != principal["name"] or defaults["制单人"] != principal["name"]
                or not all(defaults.values())):
            raise EvectionError("新页身份和默认组织字段未核实")
        table = self.trip_table(form)
        rows = self.trip_rows(table)
        if read_trip_table(table) != [[""] * len(TRIP_FIELDS)]:
            raise EvectionError("新页行程表不为空白单行")
        self.preflight_cities(table, plan)
        for i, expected in enumerate(plan["trips"]):
            self.assert_new(form)
            if rows.count() == i:
                self.click_button(table, "新增")
                self.page.wait_for_timeout(600)
            if rows.count() != i + 1:
                raise EvectionError("行程行数与本次填写进度不一致")
            row = rows.nth(i)
            for field, value in zip(TRIP_FIELDS, expected):
                self.log_event(event="evection_fill_cell", row=i + 1, field=field)
                cell = unique(row.locator(f"td.prop-{field}:visible"), field)
                if field == "days" or (field == "startPlace" and i):
                    self.expect_cell(cell, value, field)
                else:
                    self.fill_trip_cell(cell, field, value)

        purpose = "参加TRE展会及市场调研" if {"参加TRE展会", "市调"} <= {
            row[-1] for row in plan["trips"]} else "；".join(dict.fromkeys(row[-1] for row in plan["trips"]))
        purpose_field = self.header_field(form, "出差事由")
        purpose_input = unique(purpose_field.locator("input[type=text]:visible"), "出差事由输入框")
        if not purpose_input.is_editable() or purpose_input.input_value():
            raise EvectionError("出差事由不是空白可编辑字段")
        purpose_input.fill(purpose)
        purpose_input.press("Tab")
        self.page.wait_for_timeout(600)

        self.assert_new(form)
        self.verify_identity(principal)
        actual = read_trip_table(self.trip_table(form))
        save_json(self, "trip_readback.json", {"trips": actual, "purpose": self.header_value(form, "出差事由")})
        if (actual != plan["trips"] or self.default_fields(form) != defaults
                or self.header_value(form, "出差事由") != purpose):
            raise EvectionError("出差单终局回读存在差异")
        return ["出差明细起止时刻", "工作交接", "费用说明（未提供费用）"]

    def detail_rows(self, form, *, page=None):
        page = page or self.page
        table = unique(form.locator("p-table:visible").filter(has=page.locator(
            "th.prop-applyDuration")), "出差明细表")
        return table.locator("tbody > tr:visible").filter(has=page.locator("td.prop-appliedName"))

    def fill_detail_times(self, form, auth):
        from bpm.evection_save import CALC_POSTS, local_minute
        self.calculation_posts = CALC_POSTS
        row = unique(self.detail_rows(form), "出差明细行")
        for field, key in (("startTime", "start"), ("endTime", "end")):
            cell = unique(row.locator(f"td.prop-{field}"), key)
            if read_value(cell):
                raise EvectionError("出差明细原值非空")
            cell.dblclick(timeout=8000)
            self.page.wait_for_timeout(600)
            inp = unique(cell.locator("qd-date-picker input[type=text]:visible"), key)
            inp.fill(auth[key].replace("T", " "))
            if key == "end":
                def is_reckon(response):
                    u = urlsplit(response.url)
                    return (response.request.method == "POST" and u.scheme == "https"
                            and u.netloc == "ams.api.qiaodan.com" and u.path.lower() == "/shiftapi/getleavereckon")
                with self.page.expect_response(is_reckon, timeout=25000) as outcome:
                    inp.press("Enter")
                    self.page.keyboard.press("Tab")
                if not outcome.value.ok or outcome.value.json().get("code") != "OK":
                    raise EvectionError("OA 未成功计算这段出差明细，停止保存")
            else:
                inp.press("Enter")
                self.page.keyboard.press("Tab")
            for _ in range(8):
                self.page.wait_for_timeout(600)
                try:
                    if local_minute(read_value(cell)) == auth[key]:
                        break
                except ValueError:
                    pass
            else:
                raise EvectionError(f"出差明细{key}未回读到确认时分")

    def draft_snapshot(self, form, defaults, operator, *, is_new, page=None):
        from bpm.evection_save import local_minute, zero
        page = page or self.page
        rows = self.detail_rows(form, page=page)
        count = rows.count()
        row = unique(rows, "出差明细行")
        detail_name = read_value(unique(row.locator("td.prop-appliedName"), "明细申请人"))
        value = lambda label: self.header_value(form, label, page=page)
        identity_ok = operator == detail_name and self.default_fields(form, page=page) == defaults
        costs = unique(form.locator("p-table:visible").filter(has=page.locator("th.prop-itemType")), "费用说明")
        empty_costs = costs.evaluate("""root => [...root.querySelectorAll('tbody tr:has(td.prop-itemType)')]
            .every(row => [...row.querySelectorAll('td.field-col')]
              .every(cell => !cell.innerText.trim() || (cell.matches('.prop-amount,.prop-itemNumber')
                     && /^0(?:\\.0+)?$/.test(cell.innerText.trim()))))""")
        extras_empty = (empty_costs and zero(value("出差费用")) and not value("工作交接")
                        and not value("备注") and not form.locator("tbody td.prop-fileName:visible").count())
        return {"page": {"is_new": is_new, "biz_number": value("单据编号"), "status": value("单据状态")},
                "trips": read_trip_table(self.trip_table(form, page=page)), "purpose": value("出差事由"),
                "times": [local_minute(read_value(unique(row.locator(f"td.prop-{prop}"), prop)))
                          for prop in ("startTime", "endTime")],
                "operator": operator if identity_ok else None, "details_count": count,
                "extras_empty": extras_empty}

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

    def observe_editors(self, form):
        table = self.trip_table(form)
        row = unique(self.trip_rows(table), "新行程行")
        for field in ("startTime", "workItems", "startPlace"):
            cell = unique(row.locator(f"td.prop-{field}:visible"), field)
            cell.dblclick(timeout=8000)
            self.page.wait_for_timeout(600)
            self.save(f"editor_{field}.html", cell.evaluate("e => e.outerHTML"))
            trigger = cell.locator('button[aria-label="选择表格数据"]:visible')
            if field == "startPlace" and trigger.count() == 1:
                self._click_guard("选择表格数据")
                trigger.click()
                dialog = self.page.locator(".ui-dialog:visible")
                dialog.wait_for(timeout=10000)
                self.page.wait_for_timeout(1200)
                save_json(self, "city_picker_layout.json", inventory(dialog))
            self.page.keyboard.press("Escape")
            self.page.keyboard.press("Tab")

    def deliver(self, status, reason=None, save_status="NOT_AUTHORIZED"):
        self.result.update(finish_reason=status, task_status=status,
                           save_status=save_status, reason=reason)
        self.atomic_result()
        self.log_event(event="result_delivered", task_status=status, reason=reason)
        self.say(status, reason or "")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--itinerary", required=True, type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--expect-name")
    parser.add_argument("--force-scan", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--draft-request", type=Path)
    parser.add_argument("--keep-open-minutes", type=int, default=45)
    options = parser.parse_args(argv)
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", options.run):
        parser.error("invalid run id")
    if not 1 <= options.keep_open_minutes <= 120:
        parser.error("invalid review duration")
    plan = itinerary(options.image, options.itinerary)
    draft = None
    if options.draft_request:
        from bpm.evection_save import load_request
        from bpm.plan import file_hash
        from bpm.paths import ROOT
        if options.observe or not options.expect_name:
            parser.error("saving requires this task's verified expected operator")
        auth, purpose = load_request(options.draft_request, options.run, plan["trips"],
                                     plan["image_sha256"], ROOT / "automation/runs" / options.run)
        draft = {"task_id": options.run, "document_type": "evection", "operator": options.expect_name,
                 "trips": plan["trips"], "purpose": purpose, "authorization": auth,
                 "sources": {key: {"path": str(path.resolve()), "sha256": file_hash(path)}
                             for key, path in (("image", options.image), ("itinerary", options.itinerary),
                                               ("request", options.draft_request))}}
    if options.validate_only:
        print(f"ITINERARY_VALIDATED ({len(plan['trips'])} rows)")
        return 0
    args = SimpleNamespace(**vars(options), doc_id=None, tech_budget=240,
                           login_wait=480 if options.force_scan else 0, wall_cap=780,
                           fill_plan=None, login_only=True)
    probe = EvectionProbe(args)
    form = None
    controller = None
    try:
        if draft:
            from bpm.evection_save import EvectionSaveController
            from bpm.paths import ROOT
            controller = EvectionSaveController(draft, None, probe.attempt, options.expect_name,
                                               journal_dir=ROOT / "automation/task-registry")
            if controller.journal.exists():
                prior = json.loads(controller.journal.read_text(encoding="utf-8"))
                if (prior.get("status") not in {"NEEDS_INPUT", "READBACK_MISMATCH"}
                        or prior.get("plan_hash") != controller.plan_hash):
                    raise EvectionError("已有保存意图或绑定不符，需只读核实")
            save_json(probe, "draft_plan.json", draft)
        probe.acquire_lock()
        if not options.force_scan and not state_usable(SESSION_STATE):
            raise EvectionError("WAIT_HUMAN_LOGIN")
        probe._launch()
        principal = probe.authenticate()
        listing = probe.open_list()
        save_json(probe, "list_layout.json", inventory(listing))
        probe.shot(probe.page, "list.png")
        save_json(probe, "itinerary_plan.json", plan)
        save_json(probe, "history_reference.json", probe.read_history(listing, principal))
        form = probe.open_form(listing)
        if options.observe:
            save_json(probe, "new_form_layout.json", {"path": urlsplit(probe.page.url).path,
                                                      "layout": inventory(form)})
            probe.observe_editors(form)
            probe.verify_identity(principal)
            probe.deliver("SUCCESS_READ_ONLY_OBSERVATION")
        else:
            gaps = probe.fill_form(form, plan, principal)
            if controller:
                from bpm.evection_save import EvectionSaveAdapter
                defaults = probe.default_fields(form)
                probe.fill_detail_times(form, draft["authorization"])
                probe.save_adapter = controller.adapter = EvectionSaveAdapter(probe, form, draft, principal, defaults)
                saved = controller.run()
                probe.result.update(save_identity=saved.get("identity") or saved.get("pending_identity"))
                probe.deliver(saved["status"], saved.get("reason"), saved["status"])
                probe.park()
                return 0 if saved["status"] == "SUCCESS_DRAFT_SAVED" else 2
            probe.result.update(remaining_unverified=gaps, rows_verified=len(plan["trips"]),
                                review_screenshot=probe.shot(probe.page, "review.png"))
            probe.deliver("SUCCESS_FILL_ONLY_REVIEW")
            probe.park()
        return 0
    except Exception as exc:
        if probe.ctx and getattr(probe, "page", None) and not probe.page.is_closed():
            probe.shot(probe.page, "blocked.png")
            probe.save("probe_error.txt", str(exc)[:4000])
        probe.deliver("NEEDS_INPUT", str(exc).splitlines()[0][:220] if isinstance(exc, EvectionError)
                      else type(exc).__name__)
        if form is not None and not options.observe and not probe.page.is_closed():
            probe.park()
        return 2
    finally:
        probe._close_browser()
        probe.release_lock()
        probe.budget.close()


if __name__ == "__main__":
    raise SystemExit(main())
