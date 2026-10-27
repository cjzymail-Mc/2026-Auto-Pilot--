# 离线诊断（v2）：读 attempt_007 fill_form.html 文本，剥 script/link/base 后 set_content，
# 静态解析『新增』按钮真实属性 + 费用说明表祖先链 + 当前 TABLE_MAP_JS 归属。只读，不触网。
import pathlib
import re
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from playwright.sync_api import sync_playwright
import bpm.browser_probe as P

HTML = pathlib.Path(r"automation/runs/20261021-131724-1c1aadbd/attempt_007/evidence/fill_form.html")

BTN_JS = """() => {
  const out = [];
  for (const b of document.querySelectorAll('button')) {
    const t = (b.textContent || '').trim();
    if (b.title === '新增' || b.getAttribute('aria-label') === '新增' || t === '新增' || (b.innerText || '').trim() === '新增')
      out.push({
        title: b.title, aria: b.getAttribute('aria-label'), text: t.slice(0, 12),
        cls: (b.className || '').slice(0, 70),
        vis: (() => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })(),
        parentCls: (b.parentElement ? (b.parentElement.className || '').toString().slice(0, 70) : ''),
        gpCls: (b.parentElement && b.parentElement.parentElement
                ? (b.parentElement.parentElement.className || '').toString().slice(0, 70) : '')
      });
  }
  return out;
}"""

ANC_JS = """() => {
  const out = [];
  const t = Array.from(document.querySelectorAll('table')).find(x => {
    const q = x.closest('qd-dynamic-table');
    if (!q) return false;
    const cap = q.querySelector('.table-caption');
    return cap && (cap.textContent || '').includes('费用说明');
  });
  if (!t) return ['费用说明表未找到'];
  let anc = t.parentElement, depth = 0;
  while (anc && anc !== document.body && depth < 12) {
    const tbls = anc.querySelectorAll('table').length;
    const btns = Array.from(anc.querySelectorAll('button')).filter(b =>
      b.title === '新增' || b.getAttribute('aria-label') === '新增' || (b.textContent || '').trim() === '新增').length;
    out.push(`depth${depth} <${anc.tagName.toLowerCase()} class="${(anc.className || '').toString().slice(0, 46)}"> tables=${tbls} addBtns=${btns}`);
    anc = anc.parentElement; depth++;
  }
  return out;
}"""

h = HTML.read_text(encoding="utf-8", errors="ignore")
h = re.sub(r"<script\b[^>]*>.*?</script>", "", h, flags=re.S | re.I)
h = re.sub(r"<script\b[^>]*/?>", "", h, flags=re.I)
h = re.sub(r"<link\b[^>]*/?>", "", h, flags=re.I)
h = re.sub(r"<base\b[^>]*/?>", "", h, flags=re.I)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.set_content(h, wait_until="domcontentloaded", timeout=20000)
    pg.wait_for_timeout(800)
    info = pg.evaluate("() => ({ready: document.readyState, tables: document.querySelectorAll('table').length,"
                       " buttons: document.querySelectorAll('button').length,"
                       " qdt: document.querySelectorAll('qd-dynamic-table').length})")
    print("=== 基础计数 ===", info)
    print("=== 匹配到的『新增』按钮 ===")
    for x in pg.evaluate(BTN_JS):
        print(" ", x)
    print("=== 费用说明表向上祖先链 ===")
    for line in pg.evaluate(ANC_JS):
        print(" ", line)
    print("=== 当前 TABLE_MAP_JS 结果 ===")
    for t in pg.evaluate(P.TABLE_MAP_JS):
        print(f"  title={t['title']!r:16} rows={t['row_count']} add_sel={'有' if t['add_sel'] else '空'}"
              f" body_sel={'同sel' if t.get('body_sel') == t.get('sel') else '独立body表'}")
    b.close()
