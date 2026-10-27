"""Authorized, read-only inspection for the speedup work; never opens a form for editing."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bpm.browser_probe import Probe, HOST, LIST_PATH, PASS, assert_internal
from bpm.ui import observed_operator, DraftUIAdapter
from bpm.plan import file_hash, load_type
from bpm.template import parse_list_items

RUN = "20261023-speedup-preparation"
PLAN = ROOT / "feature01-细化报销skill/2026-10-23 真实演示后报销填写提速方案.md"

class ReadOnlyProbe(Probe):
    def _launch(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=False, args=["--no-proxy-server"])
        self.ctx = self.browser.new_context(ignore_https_errors=True, viewport={"width":1440,"height":900})
        self._inject_session_state()
        self.page = self.ctx.new_page()
        self.page.set_default_timeout(45000)

p = ReadOnlyProbe(SimpleNamespace(run=RUN, doc_id="15426093015", expect_name="陈晶",
    tech_budget=1800, login_wait=1200, wall_cap=3600, fill_plan=None, keep_open_minutes=0))
record = {"objective":"按真实演示后报销填写提速方案施工，修复核验、固化正式控件、完成真实 C0/C1 对照及严格整单回读",
    "plan_path":str(PLAN), "plan_sha256":file_hash(PLAN),
    "authorization":"用户明确要求执行本方案；第 2.1 节授权真实观察、控件测试、新建未保存测试单及必要 C0/C1 回归",
    "forbidden":["覆盖或重存已保存样张","保存新测试单","提交","发送","流转","审批","上传","直接写接口"],
    "goal_registration":"create_goal rejected: unfinished prior goal; prior goal state preserved",
    "protected_sample":{"state":"user_saved", "identity":"pending_exact_read_only_discovery"}}
p.save("requested_goal_and_authorization.json", json.dumps(record,ensure_ascii=False,indent=2))
p.acquire_lock()
reason="NEEDS_INPUT"
try:
    p._preflight()
    p._launch()
    captured=[]
    def response(r):
        u=urlsplit(r.url)
        if u.netloc=="oa.api.qiaodan.com" and u.path.startswith("/reimburse/query/") and r.status==200:
            captured.append(r)
    p.page.on("response",response)
    p.page.goto(assert_internal(HOST+LIST_PATH),wait_until="domcontentloaded")
    p.page.wait_for_timeout(5000)
    if observed_operator(p.page)!=p.args.expect_name:
        raise RuntimeError("verified login unavailable")
    safe=[]
    for r in captured:
        for item in parse_list_items(r.text()):
            safe.append({k:item.get(k) for k in ("id","bizNumber","appliedName","createdName","description","totalCost","bizStatus","createdDate")})
    p.save("recent_documents.json",json.dumps(safe,ensure_ascii=False,indent=2))
    matches={x["id"]:x for x in safe if x.get("description")=="【现场演示·不保存·关联已替换】公出油补" and x.get("createdName")=="陈晶"}
    if len(matches)!=1:
        p.shot(p.page,"saved_sample_list_lookup.png")
        raise RuntimeError("saved sample not uniquely found in recent list")
    item=next(iter(matches.values()))
    p.type_config=load_type("travel")
    children={}
    def child_response(r):
        u=urlsplit(r.url)
        if u.netloc=="oa.api.qiaodan.com" and r.status==200 and "/"+item["id"] in u.path:
            try:
                value=r.json()
                if isinstance(value,list) and any(isinstance(x,dict) and "bizDetailCost" in x for x in value):
                    children[u.path]=[{k:x.get(k) for k in ("bizTypeName","bizNo","bizDetailCost","bizDetailNum","usedCost","cost")} for x in value]
            except Exception:
                pass
    p.page.on("response",child_response)
    p.page.goto(assert_internal(HOST+"/oa/reimburse?type=view&id="+item["id"]),wait_until="domcontentloaded")
    p.page.wait_for_timeout(4000)
    snapshot=DraftUIAdapter(p).capture_snapshot()
    if snapshot["page"]["biz_number"]!=item["bizNumber"]:
        raise RuntimeError("saved sample exact identity mismatch")
    p.save("protected_saved_sample.json",json.dumps({"identity":item,"read_only":True,"snapshot":snapshot,"detail_api":children},ensure_ascii=False,indent=2))
    p.shot(p.page,"protected_saved_sample.png")
    p._save_session_state()
    reason="SUCCESS_READ_ONLY_PROTECTED_SAMPLE"
    print(json.dumps({"status":reason,"biz_number":item["bizNumber"],"uuid":item["id"],"detail_api":children,"attempt":str(p.attempt)},ensure_ascii=False))
finally:
    p.result["finish_reason"]=reason
    p.atomic_result()
    p._close_browser()
    p.release_lock()
    p.budget.close()
