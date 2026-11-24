"""只读诊断：待审寄件快递单详情页的表头/表单 DOM 真实状态。

目的：2026-11-24 自动审批首单报「无法核对单据编号」，离线合成用例无法复现，
需在真实页面上核实 qd-dynamic-form-header 的数量、尺寸与可见性根因。

边界：复用 approval_watch 的登录、任务中心查询与可见窗口打开路径；只读 DOM，
不点击流转/保存/确认，不写任何业务接口。用法：
    python -X utf8 tools/diagnostics/express_header_probe.py [单号]
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "feature03-自动审批快递单"))

import approval_watch as aw  # noqa: E402
from bpm.login import LoginProbe  # noqa: E402

NUMBER = sys.argv[1] if len(sys.argv) > 1 else "13926110314"

DOM_PROBE = """() => {
  const vis = el => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const tag = t => Array.from(document.querySelectorAll(t));
  const describe = h => {
    const r = h.getBoundingClientRect();
    return {rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
            display: getComputedStyle(h).display,
            innerText: (h.innerText || '').replace(/\\s+/g, ' ').slice(0, 160),
            textContent: (h.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 160),
            inputs: Array.from(h.querySelectorAll('input')).map(i => i.value).slice(0, 12)};
  };
  return {url: location.pathname + location.search,
          express_detail: {all: tag('qd-express-detail').length,
                           visible: tag('qd-express-detail').filter(vis).length},
          header: {all: tag('qd-dynamic-form-header').length,
                   visible: tag('qd-dynamic-form-header').filter(vis).length,
                   items: tag('qd-dynamic-form-header').map(describe)},
          form: {all: tag('qd-dynamic-form').length,
                 visible: tag('qd-dynamic-form').filter(vis).length},
          table: {all: tag('qd-dynamic-table').length},
          form_text: tag('qd-dynamic-form').map(f => (f.innerText || '').replace(/\\s+/g, ' ').slice(0, 400)),
          number_holders: (() => {
            const hits = [];
            document.querySelectorAll('*').forEach(el => {
              const own = Array.from(el.childNodes)
                .filter(n => n.nodeType === 3).map(n => n.nodeValue).join('');
              if (own.includes(NUMBER_ARG)) {
                hits.push({tag: el.tagName, cls: String(el.className).slice(0, 80),
                           text: own.replace(/\\s+/g, ' ').trim().slice(0, 120)});
              }
            });
            return hits;
          })(),
          flow_button: Array.from(document.querySelectorAll('button'))
                      .filter(b => b.textContent.trim() === '流转').length};
}""".replace("NUMBER_ARG", json.dumps(NUMBER))


def main():
    probe = LoginProbe(SimpleNamespace(
        run=f"approval-diag-{uuid4().hex[:12]}", doc_id=None, expect_name=None,
        force_scan=False, tech_budget=900, login_wait=480, wall_cap=1200,
        fill_plan=None, login_only=True,
    ))
    probe.acquire_lock()
    window = None
    try:
        account = aw.startup_login(probe, False)
        inbox = aw.Inbox(probe.page, account)
        aw.ready_inbox(probe, inbox)
        rows = inbox.query(NUMBER)
        exact = [row for row in rows if row.get("bizNumber") == NUMBER]
        if not exact:
            pending = [row.get("bizNumber") for row in aw.approval_tasks(rows, account[0])]
            print(json.dumps({"error": "待办中未找到该单号", "number": NUMBER,
                              "pending_numbers": pending}, ensure_ascii=False))
            return 1
        url = aw.detail_url(probe.page, account, exact[0])
        window = aw.ApprovalWindow(probe)
        page = window.open(account, url)  # 与自动审批同款打开路径
        page.wait_for_timeout(2500)
        snapshots = [page.evaluate(DOM_PROBE)]
        page.wait_for_timeout(2500)
        snapshots.append(page.evaluate(DOM_PROBE))
        from bpm.approval import ShippingHandler
        try:
            summary = ShippingHandler().snapshot(page, exact[0], url)
            snapshot_result = {"snapshot_ok": True, "summary": summary}
        except Exception as exc:
            snapshot_result = {"snapshot_ok": False, "error": str(exc)}
        print(json.dumps({"number": NUMBER, "account": account[1],
                          "dom": snapshots, "verify": snapshot_result},
                         ensure_ascii=False, indent=2))
        return 0 if snapshot_result["snapshot_ok"] else 2
    finally:
        if window is not None:
            window.close()
        probe._close_browser()
        probe.release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
