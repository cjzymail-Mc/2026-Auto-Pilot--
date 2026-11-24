"""Isolated Chromium fixtures only; no OA connection, credentials or live approval."""
import json
from pathlib import Path
import tempfile
import time
import unittest

from playwright.sync_api import sync_playwright

from bpm.approval import (ApprovalJournal, ApprovalStopped, AutoApprover,
                          ORIGIN, ShippingHandler, exact_button, flow_dialog)


TASK = dict(id="1" * 32, bizId="2" * 32, bizNumber="SHIP-SYNTHETIC-001", url="/oa/express",
            toUserCode="synthetic-user", bizStatus=7, status=0, kind=1, isHeld=False)
URL = ORIGIN + "/oa/express?type=view&id=" + TASK["bizId"] + "&task=1"
FLOW = "https://admin.api.qiaodan.com/flow/to/" + "3" * 32
FORM = """
<qd-express-detail>
 <button id="open">流转</button>
 <qd-dynamic-form-header>单号 SHIP-SYNTHETIC-001</qd-dynamic-form-header>
 <qd-dynamic-form>寄件测试<input value="合成值"></qd-dynamic-form>
 <qd-dynamic-table tableCaption="快递明细">
  <table><tbody><tr><td class="prop-shipName">测试样品</td><td class="prop-num">2</td></tr></tbody></table>
 </qd-dynamic-table>
</qd-express-detail>
"""
DIALOG = """
<div class="ui-dialog flow-dialog" role="dialog">
 <span class="ui-dialog-title">流转</span>
 <table><tbody><tr class="ui-state-highlight"><td class="prop-userName">合成下一节点</td></tr></tbody></table>
 <button id="confirm">流转</button><button>取消</button>
</div>
"""
HTML = """<!doctype html><html><meta charset="utf-8"><body><script>
window.openCount = 0;
setTimeout(() => {
 document.body.insertAdjacentHTML('beforeend', FORM);
 document.querySelector('#open').onclick = () => {
  window.openCount++;
  window.openedAt = performance.now();
  document.body.insertAdjacentHTML('beforeend', DIALOG);
  const row = document.querySelector('.flow-dialog tbody tr');
  row.remove();
  setTimeout(() => document.querySelector('.flow-dialog tbody').append(row), 300);
  document.querySelector('#confirm').onclick = async () => {
   await fetch(FLOW, {method:'POST', body:JSON.stringify({isApproved:true})});
   document.querySelector('.flow-dialog').remove();
  };
 };
}, 150);
</script></body></html>""".replace("FORM", json.dumps(FORM)).replace("DIALOG", json.dumps(DIALOG)).replace("FLOW", json.dumps(FLOW))


class ApprovalDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-proxy-server"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(service_workers="block")
        self.addCleanup(self.context.close)
        self.completed, self.requests = False, []

        def route_handler(route):
            # Every request is intercepted, and unexpected hosts are aborted.
            if route.request.url == URL:
                route.fulfill(status=200, content_type="text/html", body=HTML)
            elif route.request.url == FLOW and route.request.method == "POST":
                self.requests.append(route.request.post_data_json)
                self.completed = True
                route.fulfill(status=200, content_type="application/json",
                              headers={"access-control-allow-origin": ORIGIN},
                              body=json.dumps({"bizId": TASK["bizId"]}))
            else:
                route.abort()

        self.context.route("**/*", route_handler)
        self.page = self.context.new_page()
        self.page.goto(URL, wait_until="domcontentloaded")

    def ready(self):
        self.page.locator("td.prop-num").wait_for()

    def test_real_dom_late_loading_full_six_seconds_two_clicks_and_no_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            messages, timings = [], {}
            def log(**data):
                if data["event"] == "approval_auto_display":
                    timings["display"] = self.page.evaluate("performance.now()")
            approver = AutoApprover(ApprovalJournal(folder), "synthetic-user", lambda p: None,
                                    lambda task: not self.completed, messages.append, log)
            start = time.monotonic()
            self.assertEqual(approver.handle(self.page, TASK), "SUCCESS", messages)
            self.assertGreaterEqual(time.monotonic() - start, 6)
            self.assertGreaterEqual(self.page.evaluate("window.openedAt") - timings["display"], 6000)
            self.assertEqual(self.requests, [{"isApproved": True}])
            self.assertIn("测试样品 × 2", messages[-1])
            approver2 = AutoApprover(ApprovalJournal(folder), "synthetic-user", lambda p: None,
                                     lambda task: False, messages.append, log)
            self.assertEqual(approver2.handle(self.page, TASK), "RECORDED")
            self.assertEqual(self.page.evaluate("window.openCount"), 1)
            records = [json.loads(x) for x in next(Path(folder).glob("*.jsonl")).read_text(encoding="utf-8").splitlines()]
            self.assertEqual([x["state"] for x in records], ["FLOW_INTENT", "FLOW_CONFIRM_INTENT", "SUCCESS"])

    def test_same_route_with_wrong_component_or_number_is_rejected(self):
        self.ready()
        for html in (FORM.replace("qd-express-detail", "qd-reimbursement-detail"),
                     FORM.replace("SHIP-SYNTHETIC-001", "OTHER-SYNTHETIC"),
                     FORM.replace("SHIP-SYNTHETIC-001", "SHIP-SYNTHETIC-0010")):
            with self.subTest(html=html[:45]):
                self.page.set_content(html)
                with self.assertRaises(ApprovalStopped):
                    ShippingHandler().snapshot(self.page, TASK, URL)
        self.assertEqual(self.requests, [])

    def test_snapshot_includes_rendered_form_and_detail_values(self):
        self.ready()
        original = ShippingHandler().snapshot(self.page, TASK, URL)
        self.page.locator("input").fill("人工修改")
        changed = ShippingHandler().snapshot(self.page, TASK, URL)
        self.assertNotEqual(original["fingerprint"], changed["fingerprint"])

    def test_hidden_detail_table_never_counts_as_loaded(self):
        self.ready()
        self.page.set_content(FORM.replace('<qd-dynamic-table ', '<qd-dynamic-table style="display:none" '))
        with self.assertRaises(ApprovalStopped):
            ShippingHandler().snapshot(self.page, TASK, URL)

    def test_zero_sized_custom_table_host_with_visible_rows_is_readable(self):
        self.ready()
        self.page.set_content(FORM.replace('<qd-dynamic-table ',
                              '<qd-dynamic-table style="display:block;width:0;height:0;overflow:visible" '))
        size = self.page.locator("qd-dynamic-table").evaluate(
            "e => {const r=e.getBoundingClientRect(); return [r.width, r.height];}")
        self.assertEqual(size, [0, 0])
        self.assertTrue(self.page.locator("td.prop-num").is_visible())
        summary = ShippingHandler().snapshot(self.page, TASK, URL)
        self.assertEqual(summary["detail_count"], 1)
        self.assertEqual(summary["items"], ["测试样品 × 2"])

    def test_zero_sized_header_host_with_number_in_form_label_is_verified(self):
        # 2026-11-24 真实页面（approval-diag 探查 13926110314）：header host 为
        # 零尺寸 inline box、文本只有「快递单」，单号渲染为 qd-dynamic-form 内
        # 的 label.print-label。编号核对看渲染内容，不依赖 host 可见性。
        self.ready()
        html = (FORM
                .replace('<qd-dynamic-form-header>单号 SHIP-SYNTHETIC-001</qd-dynamic-form-header>',
                         '<qd-dynamic-form-header style="display:block;width:0;height:0;overflow:hidden">快递单</qd-dynamic-form-header>')
                .replace('<qd-dynamic-form>寄件测试',
                         '<qd-dynamic-form><label class="print-label">SHIP-SYNTHETIC-001</label>寄件测试'))
        self.page.set_content(html)
        self.assertFalse(self.page.locator("qd-dynamic-form-header").is_visible())
        summary = ShippingHandler().snapshot(self.page, TASK, URL)
        self.assertEqual(summary["number"], TASK["bizNumber"])
        self.assertEqual(summary["detail_count"], 1)
        self.assertEqual(summary["items"], ["测试样品 × 2"])

    def test_missing_header_component_is_rejected(self):
        self.ready()
        self.page.set_content(FORM.replace(
            '<qd-dynamic-form-header>单号 SHIP-SYNTHETIC-001</qd-dynamic-form-header>', ''))
        with self.assertRaises(ApprovalStopped):
            ShippingHandler().snapshot(self.page, TASK, URL)

    def test_only_unique_default_node_and_standard_dialog_accepted(self):
        self.ready()
        for dialog in (DIALOG.replace("ui-state-highlight", ""), DIALOG):
            self.page.set_content(FORM + dialog)
            self.assertTrue(flow_dialog(self.page)[1])
        row = '<tr><td class="prop-userName">另一个合成人员</td></tr>'
        for dialog in (DIALOG.replace("流转</span>", "回退</span>"),
                       DIALOG + '<div role="dialog">额外确认</div>',
                       DIALOG.replace("ui-state-highlight", "").replace("</tbody>", row + "</tbody>"),
                       DIALOG.replace("合成下一节点", ""),
                       DIALOG.replace("</table>", '</table><input aria-invalid="true">')):
            with self.subTest(dialog=dialog[:60]):
                self.page.set_content(FORM + dialog)
                with self.assertRaises(ApprovalStopped):
                    flow_dialog(self.page)
        self.assertEqual(self.requests, [])

    def test_similarly_named_duplicate_or_disabled_button_never_selected(self):
        for buttons in ('<button>保存并流转</button>', '<button disabled>流转</button>',
                        '<button>流转</button><button>流转</button>'):
            self.page.set_content(buttons)
            with self.assertRaises(ApprovalStopped):
                exact_button(self.page)


if __name__ == "__main__":
    unittest.main()
