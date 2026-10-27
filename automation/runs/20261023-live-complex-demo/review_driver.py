"""User-authorized historical replay, visible form only; never saves.

Keeps one profile owner alive while local, explicitly enumerated review commands
are inspected between actions. Credentials are handled solely by Probe helpers.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from stage1_browser_probe import Probe, FORM_MAP_JS, TABLE_MAP_JS, HOST, NEW_FORM_PATH, PASS, assert_internal
from bpm_ui import StructuredProbe, DraftUIAdapter, observed_operator, _prop
from bpm_plan import load_plan, load_type, plan_hash
from bpm_template import fetch_template
from bpm_verify import verify_snapshot

RUN = Path(__file__).resolve().parent
p = Probe(SimpleNamespace(run=RUN.name, doc_id="15426093015", expect_name="陈晶",
                          tech_budget=7200, login_wait=1200, wall_cap=100000,
                          fill_plan=None, keep_open_minutes=1440))
new_page = None
history_page = None
q = None
creator = None
fill_started = False


def dump(name):
    fields = p.page.evaluate(FORM_MAP_JS)
    tables = p.page.evaluate(TABLE_MAP_JS)
    p.save(name + ".json", json.dumps({"url": p.page.url, "operator": observed_operator(p.page),
                                     "fields": fields, "tables": tables}, ensure_ascii=False, indent=2))
    p.shot(p.page, name + ".png")
    return {"artifact": name + ".json", "fields": len(fields), "tables": len(tables)}


def handle(c):
    global new_page, history_page, q, creator, fill_started
    op = c["op"]
    if observed_operator(p.page) != p.args.expect_name:
        raise RuntimeError("actual topbar operator changed")
    if op == "extension":
        # Task-local inspected UI helpers; ordinary no-save guard remains active.
        import importlib.util
        spec = importlib.util.spec_from_file_location("review_actions", RUN / "review_actions.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.handle(p, q, c, {"fill_started": fill_started, "creator": creator})
    if op == "read_template":
        snap = fetch_template(p, p.args.doc_id)
        p.save("template_snapshot.json", json.dumps(snap, ensure_ascii=False, indent=2))
        history_page = p.ctx.new_page()
        history_page.goto(assert_internal(HOST + "/oa/reimburse?type=view&id=" + snap["uuid"]), wait_until="domcontentloaded")
        history_page.wait_for_timeout(4000)
        p.page = history_page
        return dump("history_display")
    if op == "new_blank":
        if new_page is not None:
            raise RuntimeError("new form already exists; never create a duplicate")
        new_page = p.ctx.new_page()
        p.page = new_page
        new_page.goto(assert_internal(HOST + NEW_FORM_PATH), wait_until="domcontentloaded")
        new_page.wait_for_timeout(5000)
        creator = next((f["value"] for f in new_page.evaluate(FORM_MAP_JS) if _prop(f.get("name")) == "createdName"), None)
        p.log_event(event="demo_creator_initial_observed", creator=creator)
        return dump("initial_blank")
    if op == "observe":
        return dump(c.get("tag", "current_observation"))
    if op == "initial_identity":
        if fill_started or p.page is not new_page:
            raise RuntimeError("identity is immutable after filling starts")
        prop = c["property"]
        if prop not in ("appliedName", "createdName"):
            raise RuntimeError("only initial person selection is permitted")
        fields = p.page.evaluate(FORM_MAP_JS)
        hits = [f for f in fields if _prop(f.get("name")) == prop]
        if len(hits) != 1:
            raise RuntimeError("person field not unique")
        if str(hits[0].get("value")) == c["value"]:
            return {"unchanged": True}
        raise RuntimeError("person field selection needs observed picker; never overwrite readonly identity")
    if op == "fill":
        if fill_started or p.page is not new_page:
            raise RuntimeError("fill already started or wrong page")
        plan_path = Path(c["plan"]).resolve()
        plan = load_plan(plan_path, expected_operator=p.args.expect_name)
        if plan["authorization"]["mode"] != "fill_only":
            raise RuntimeError("demo may never save")
        q = object.__new__(StructuredProbe)
        q.__dict__ = p.__dict__
        q.fill_plan = plan
        q.fill_plan_path = plan_path
        q.plan_base = plan_path.parent
        q.type_config = load_type(plan["document_type"])
        q.bound_plan_hash = plan_hash(plan)
        q.config_hash = hashlib.sha256(json.dumps(q.type_config, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        q.native_dialogs = []
        q.adapter = DraftUIAdapter(q)
        q._check_initial_page()
        before_creator = next((f["value"] for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name")) == "createdName"), None)
        if before_creator != creator:
            raise RuntimeError("creator changed before fill")
        binding = {"task_id": plan["task_id"], "plan_sha256": q.bound_plan_hash,
                   "operator": plan["operator"], "mode": "fill_only_historical_demonstration"}
        (RUN / "task_binding.json").write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding="utf-8")
        registry = ROOT / "automation/task-registry"
        registry.mkdir(exist_ok=True)
        lifecycle = registry / (hashlib.sha256(plan["task_id"].encode()).hexdigest() + ".form.json")
        with lifecycle.open("x", encoding="utf-8") as f:
            json.dump({**binding, "state": "FORM_INTENT", "run": RUN.name, "attempt": p.attempt.name}, f, ensure_ascii=False)
        fill_started = True
        p.log_event(event="demo_fill_start", **binding, creator_locked=creator)
        q._fill_arrays()
        return final_check()
    if op == "verify":
        if q is None:
            raise RuntimeError("no plan bound")
        return final_check()
    raise RuntimeError("unsupported review command")


def final_check():
    snap = q.adapter.capture_snapshot()
    check = verify_snapshot(q.fill_plan, snap, base_dir=q.plan_base)
    after_creator = next((f["value"] for f in p.page.evaluate(FORM_MAP_JS) if _prop(f.get("name")) == "createdName"), None)
    if after_creator != creator:
        check["ok"] = False
        check["issues"].append({"code": "CREATOR_CHANGED"})
    p.save("independent_readback.json", json.dumps(snap, ensure_ascii=False, indent=2))
    p.save("independent_verification.json", json.dumps(check, ensure_ascii=False, indent=2))
    p.shot(p.page, "demo_final.png")
    p.result.update(task_status="SUCCESS_FILL_ONLY" if check["ok"] else "READBACK_MISMATCH",
                    save_status="NOT_ATTEMPTED", creator_before=creator, creator_after=after_creator,
                    plan_hash=q.bound_plan_hash, verification=check)
    p.atomic_result()
    p.log_event(event="demo_verification", ok=check["ok"], creator_unchanged=creator == after_creator,
                save_attempted=False)
    return {"status": p.result["task_status"], "check": check}


try:
    p.acquire_lock()
    p._preflight()
    p._launch()
    state = p.phase_entry()
    if state == "LOGIN_REQUIRED":
        state = p.wait_login()
    if state != PASS or observed_operator(p.page) != p.args.expect_name:
        raise RuntimeError("login not verified")
    p._save_session_state()
    p.log_event(event="demo_driver_ready", no_proxy=True)
    (RUN / "driver_ready.json").write_text(json.dumps({"ready": True, "attempt": p.attempt.name}), encoding="utf-8")
    print("READY", flush=True)
    for _ in range(24 * 60 * 60 * 2):
        cmd = RUN / "command.json"
        if cmd.exists():
            c = json.loads(cmd.read_text(encoding="utf-8"))
            cmd.unlink()
            try:
                result = handle(c)
            except Exception as exc:
                result = {"error": type(exc).__name__, "message": str(exc)}
                p.log_event(event="demo_command_error", op=c.get("op"), error=str(exc))
                p.shot(p.page, "command_error.png")
            (RUN / ("response_" + str(c["id"]) + ".json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"id": c["id"], **result}, ensure_ascii=False), flush=True)
        if p.page.is_closed():
            break
        p.page.wait_for_timeout(500)
finally:
    p.atomic_result()
    p._close_browser()
    p.release_lock()
    p.budget.close()
