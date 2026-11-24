"""User-authorized shipping approval through the normal UI, never write APIs.

Only /oa/express (寄件快递单) is enabled. Expense reimbursements are unrelated.
An append-only, fsynced journal prevents automatic replay after any click intent.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlsplit

ORIGIN = "https://bpm.qiaodan.com"
IDENTIFIER = re.compile(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
DISPLAY_SECONDS = 6
AUTHORIZATION = "USER-20261117-SHIPPING-ONLY-DISPLAY-6S"


class ApprovalStopped(RuntimeError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def stamp():
    return datetime.now().astimezone().isoformat()


def brief(value, limit=40):
    return " ".join(str(value or "").split())[:limit]


class ApprovalJournal:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def key(self, subject, task):
        return digest([subject, task.get("bizId"), task.get("id")])

    def exists(self, key):
        # Corrupt/incomplete/old records also block replay. Never delete to retry.
        return (self.directory / (key + ".jsonl")).exists()

    def write(self, key, state, *, first=False, **data):
        with (self.directory / (key + ".jsonl")).open("x" if first else "a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(schema_version=1, at=stamp(), state=state,
                                         authorization=AUTHORIZATION, **data), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


@dataclass(frozen=True)
class ShippingHandler:
    key: str = "shipping_express"
    label: str = "快递单"
    route: str = "/oa/express"
    component: str = "qd-express-detail"

    def wait_ready(self, page, task, expected_url):
        deadline = time.monotonic() + 20
        while True:
            if page.is_closed() or page.url != expected_url or visible_dialogs(page).count():
                raise ApprovalStopped("加载期间页面或对话框变化")
            try:
                summary = self.snapshot(page, task, expected_url)
                exact_button(page)
                return summary
            except ApprovalStopped:
                if time.monotonic() >= deadline:
                    raise
                page.wait_for_timeout(600)

    def snapshot(self, page, task, expected_url):
        if page.is_closed() or page.url != expected_url:
            raise ApprovalStopped("单据页面已关闭或地址变化")
        root = page.locator(self.component + ":visible")
        if root.count() != 1:
            raise ApprovalStopped("无法唯一确认寄件快递单页面")
        # 2026-11-24 live probe (approval-diag): the header host renders as a
        # zero-sized inline box holding only the caption "快递单"; the document
        # number is a label.print-label inside qd-dynamic-form. Custom element
        # hosts have no reliable visibility box — check rendered content instead.
        headers = root.locator("qd-dynamic-form-header")
        if headers.count() != 1:
            raise ApprovalStopped("无法核对单据编号")
        values = root.locator("qd-dynamic-form").evaluate_all(
            "es => es.flatMap(e => [e.innerText, ...Array.from(e.querySelectorAll('input,textarea,select'), x => x.value)])")
        header_values = headers.evaluate_all(
            "es => es.flatMap(e => [e.innerText, e.textContent, ...Array.from(e.querySelectorAll('input'), x => x.value)])")
        number = re.escape(task["bizNumber"])
        if not any(re.search(r"(?<![A-Za-z0-9])" + number + r"(?![A-Za-z0-9])", v or "") for v in header_values + values):
            raise ApprovalStopped("单据页面编号与待办不一致")
        # A custom element can have a zero-sized inline box even when its table
        # rows are visible. Check the rendered rows rather than the host box.
        tables = root.locator('qd-dynamic-table[tablecaption="快递明细"]').filter(
            has=page.locator("td.prop-num:visible"))
        if tables.count() != 1:
            raise ApprovalStopped("无法唯一确认快递明细")
        rows = tables.locator("tbody tr:visible").filter(has=page.locator("td.prop-num"))
        if rows.count() == 0:
            raise ApprovalStopped("快递明细为空或结构变化")
        # Read rendered values only. Never access Angular objects or write DOM.
        details = rows.evaluate_all(
            "es => es.map(e => [e.innerText, ...Array.from(e.querySelectorAll('input,textarea,select'), x => x.value)])")
        items = []
        for row in rows.all()[:3]:
            name, quantity = row.locator("td.prop-shipName"), row.locator("td.prop-num")
            if name.count() == quantity.count() == 1:
                items.append(brief(name.inner_text()) + " × " + brief(quantity.inner_text(), 12))
        return {"number": task["bizNumber"], "detail_count": len(details),
                "items": items, "fingerprint": digest([header_values, values, details])}


# Extension point: implement a handler AND explicitly add separately authorized
# types here. A new route, label, config value, or reimbursement category never
# opts a document into approval by itself.
AUTHORIZED_HANDLERS = (ShippingHandler(),)


def handler_for(task):
    return next((h for h in AUTHORIZED_HANDLERS if task.get("url") == h.route), None)


def exact_button(scope):
    button = scope.get_by_role("button", name="流转", exact=True)
    if button.count() != 1 or not button.is_visible() or not button.is_enabled():
        raise ApprovalStopped("流转按钮缺失、不唯一或不可用")
    return button


def visible_dialogs(page):
    return page.locator('[role="dialog"]:visible, .ui-dialog:visible')


def flow_dialog(page):
    dialog = page.locator(".flow-dialog:visible")
    if dialog.count() != 1 or visible_dialogs(page).count() != 1:
        raise ApprovalStopped("出现未支持的确认窗口")
    title = dialog.locator(".ui-dialog-title")
    if title.count() != 1 or title.inner_text().strip() != "流转":
        raise ApprovalStopped("不是标准流转确认窗口")
    rows = dialog.locator("tbody tr:visible").filter(has=page.locator("td.prop-userName"))
    selected = rows.locator("xpath=self::*[contains(concat(' ', normalize-space(@class), ' '), ' ui-state-highlight ') or @aria-selected='true']")
    if selected.count() == 1:
        target = selected
    elif rows.count() == 1 and selected.count() == 0:
        target = rows  # OA's fixed sole next node, without choosing another user.
    else:
        raise ApprovalStopped("下一节点不能唯一确认，需人工处理")
    if not target.locator("td.prop-userName").inner_text().strip():
        raise ApprovalStopped("下一节点执行人为空")
    if dialog.locator('.ui-message-error:visible, .ui-messages-error:visible, [aria-invalid="true"]:visible').count():
        raise ApprovalStopped("流转窗口存在校验错误")
    return dialog, digest(target.inner_text())


class AutoApprover:
    def __init__(self, journal, subject, check_identity, pending, say, log):
        self.journal, self.subject = journal, subject
        self.check_identity, self.pending = check_identity, pending
        self.say, self.log = say, log

    def validate_task(self, task, url):
        if any(not isinstance(task.get(k), str) or not IDENTIFIER.fullmatch(task[k]) for k in ("id", "bizId")):
            raise ApprovalStopped("待办标识无效")
        if (not isinstance(task.get("bizNumber"), str) or not task["bizNumber"].strip()
                or len(task["bizNumber"]) > 100 or not task["bizNumber"].isprintable()):
            raise ApprovalStopped("待办单号无效")
        if (str(task.get("toUserCode")) != self.subject or task.get("bizStatus") != 7
                or any(type(task.get(k)) is not int for k in ("bizStatus", "status", "kind"))
                or task.get("status") not in (0, 1) or task.get("kind") not in (1, 2, 3)
                or task.get("isHeld") is True):
            raise ApprovalStopped("不是当前账号可处理的待审任务")
        parsed = urlsplit(url)
        if (f"{parsed.scheme}://{parsed.netloc}" != ORIGIN or parsed.path != task["url"]
                or parse_qs(parsed.query).get("id") != [task["bizId"]]
                or len(parse_qs(parsed.query).get("task", [])) != 1):
            raise ApprovalStopped("页面与待办来源不一致")

    def report(self, state, task, summary=None, reason=None):
        labels = {"SUCCESS": "流转成功", "STOPPED": "未自动流转", "UNCERTAIN": "流转结果待核实",
                  "RECORDED": "已有处理记录，未重复流转"}
        self.log(event="approval_auto_result", state=state,
                 task_key=self.journal.key(self.subject, task), reason=reason)
        detail = f"｜明细 {summary['detail_count']} 行" if summary else ""
        if summary and summary.get("items"):
            detail += "｜" + "；".join(summary["items"])
        # Brief business record only; no recipient address/phone, bank or token.
        self.say(f"【{labels[state]}】快递单 {brief(task.get('bizNumber'), 100)}{detail}"
                 + (f"｜{reason}" if reason else ""))
        return state

    def handle(self, page, task):
        handler = handler_for(task)
        if handler is None:
            return "MANUAL"
        summary, key, intent = None, None, False
        native_dialog = []
        on_dialog = lambda dialog: native_dialog.append(dialog.type)
        page.on("dialog", on_dialog)
        try:
            expected_url = page.url
            self.validate_task(task, expected_url)
            key = self.journal.key(self.subject, task)
            if self.journal.exists(key):
                return self.report("RECORDED", task)
            self.check_identity(page)
            summary = handler.wait_ready(page, task, expected_url)
            if visible_dialogs(page).count():
                raise ApprovalStopped("页面已有对话框，保留人工处理")
            exact_button(page)
            page.bring_to_front()
            self.log(event="approval_auto_display", task_key=key, seconds=DISPLAY_SECONDS)
            self.say(f"自动审批｜快递单 {summary['number']}｜明细 {summary['detail_count']} 行｜展示 6 秒后流转")
            # A monotonic deadline guarantees a full six seconds after readiness.
            deadline = time.monotonic() + DISPLAY_SECONDS
            while time.monotonic() < deadline:
                page.wait_for_timeout(min(600, max(1, int((deadline - time.monotonic()) * 1000))))
                if (page.is_closed() or page.url != expected_url or native_dialog
                        or not page.evaluate("() => document.visibilityState === 'visible'")):
                    raise ApprovalStopped("展示期间页面或弹窗变化")
            self.check_identity(page)
            if not self.pending(task):
                raise ApprovalStopped("当前任务已处理或发生变化")
            self.check_identity(page)
            if (handler.snapshot(page, task, expected_url) != summary
                    or visible_dialogs(page).count() or native_dialog):
                raise ApprovalStopped("展示期间单据内容或窗口变化")
            button = exact_button(page)
            # Persist before the first flow click; interruption never auto-replays.
            self.journal.write(key, "FLOW_INTENT", first=True, summary=summary)
            intent = True
            button.click(timeout=5000)
            page.locator(".flow-dialog:visible").wait_for(timeout=8000)
            # OA opens the dialog before its asynchronous next-node query ends.
            page.locator(".flow-dialog:visible td.prop-userName:visible").first.wait_for(timeout=8000)
            page.wait_for_timeout(600)
            if native_dialog:
                raise ApprovalStopped("出现未支持的原生确认框")
            dialog, target = flow_dialog(page)
            if not self.pending(task):
                raise ApprovalStopped("确认前单据或待办变化")
            self.check_identity(page)
            if handler.snapshot(page, task, expected_url) != summary:
                raise ApprovalStopped("确认前单据内容变化")
            dialog2, target2 = flow_dialog(page)
            if target != target2 or native_dialog:
                raise ApprovalStopped("确认前下一节点变化")
            confirm = exact_button(dialog2)
            self.journal.write(key, "FLOW_CONFIRM_INTENT", next_node_hash=target)
            def match(response):
                parsed = urlsplit(response.url)
                return (parsed.scheme == "https" and parsed.netloc == "admin.api.qiaodan.com"
                        and re.fullmatch(r"/flow/to/[0-9a-fA-F-]{32,36}", parsed.path) is not None
                        and response.request.method == "POST")
            with page.expect_response(match, timeout=20000) as event:
                confirm.click(timeout=5000)
            response = event.value
            request = response.request.post_data_json
            result = response.json() if response.status == 200 else None
            if (not isinstance(request, dict) or request.get("isApproved") is not True
                    or not isinstance(result, dict) or str(result.get("bizId", "")).lower() != task["bizId"].lower()):
                raise ApprovalStopped("未取得匹配单据的成功响应")
            # The visible page may auto-close after normal OA success.
            if not self.pending(task):
                self.journal.write(key, "SUCCESS", summary=summary)
                return self.report("SUCCESS", task, summary)
            raise ApprovalStopped("流转后原待办仍存在")
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ApprovalStopped) else type(exc).__name__
            if intent:
                try:
                    self.journal.write(key, "UNCERTAIN", reason=reason)
                except OSError:
                    # The durable earlier intent still prevents a second click.
                    reason += "；结果记录写入失败，保留原流转意图"
            return self.report("UNCERTAIN" if intent else "STOPPED", task, summary, reason)
        finally:
            page.remove_listener("dialog", on_dialog)
