"""Local, fully intercepted interaction replay; no OA session/profile access."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bpm.ui import StructuredProbe
from bpm.plan import file_hash

def main():
    ap=argparse.ArgumentParser();ap.add_argument("output");args=ap.parse_args()
    output=Path(args.output).resolve()
    if not output.is_relative_to(ROOT/"automation/offline-verify") or output.exists():
        raise ValueError("new offline-verify artifact required")
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=["--no-proxy-server"])
        page=browser.new_page()
        page.route("**/*",lambda route:route.fulfill(status=200,content_type="text/html",body="<html></html>"))
        page.goto("https://fixture.invalid/")
        p=object.__new__(StructuredProbe);p.page=page;p.run_dir=Path(tmp)
        times=[];activations=[]
        for _ in range(3):
            page.set_content('''<table><tbody><tr><td id="cell"><input value=""></td></tr></tbody></table>
              <script>window.activations=0;document.querySelector('td').ondblclick=()=>{activations++};
              document.querySelector('input').onkeydown=e=>{if(e.key==='Enter'){let td=e.target.closest('td'),v=e.target.value;td.textContent=v;}};</script>''')
            t0=time.perf_counter()
            p._write_cell(page.locator('#cell'),"cost","20.00","benchmark",native_priority=True)
            if page.locator('#cell').inner_text()!="20.00":
                raise ValueError("interaction did not commit")
            times.append(time.perf_counter()-t0)
            activations.append(page.evaluate('activations'))
        browser.close()
    value={"source_sha256":{"bpm/ui.py":file_hash(ROOT/"bpm/ui.py"),"bpm/browser_probe.py":file_hash(ROOT/"bpm/browser_probe.py")},
        "purpose":"already-mounted native editor; actual fill, Enter, Tab and settle read; fully intercepted synthetic Chromium",
        "samples_seconds":times,"median_seconds":statistics.median(times),"range_seconds":[min(times),max(times)],
        "activation_counts":activations,"production_access":False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(value,ensure_ascii=False))
if __name__=="__main__":main()
