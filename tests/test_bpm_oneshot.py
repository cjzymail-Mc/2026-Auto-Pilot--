"""bpm.oneshot 单会话贯通入口离线测试（G1/G2/G3 合成链；全部本地拦截，不连 OA）。

覆盖：
- G2 授权编译三分支与 save_basis 结构（含 validate_task 最小兼容调整）；
- G1 任务分支模板补全（live 快照→事实/蓝图；预供值/预冻结反例）；
- 授权记录四绑定与冲突拒绝；
- CLI 两分支 validate-only、既有保存意图阻断、准备缺口；
- 任务分支 DOM 全链：同会话模板读取→补全→生成→冻结→绑定→填写→回读；
- G3 只读副页：reopen 不导航主 tab、副页开闭事件、保存链主 tab 保持；
- G3.4/G3.5 交付与驻留：result_delivered 先于驻留、prepare-gap 不驻留、
  占用拒绝、锁归属清理与驻留期限事件。
"""
import io
import json
import os
import shutil
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from bpm import oneshot
from bpm.facts import FactSet
from bpm.fill_cli import validate_task
from bpm.plan import file_hash, load_plan, plan_hash, validate_plan
from bpm.types import resolve_type
from bpm.verify import verify_snapshot

from test_bpm_extraction import ensure_fixtures as ensure_w03_fixtures
from test_bpm_plan_generate import ensure_w05_fixtures

# 注意：不直接 from test_bpm_ui import DOMTests——TestCase 类一旦成为本模块属性，
# unittest discover 会把它重复收进本模块套件（连同 test_bpm_ui 自身各跑一遍），
# 证据拷贝目录互撞。经模块对象引用（模块不是 type）不受收集。
import test_bpm_ui

TEMPLATE_NUMBER = "15426095951"
TEMPLATE_UUID = "a" * 32
TEMPLATE_HEADER = {"bizOrign": "测试流程", "payType": "转账",
                   "currencyType": "人民币", "submitType": "差旅费",
                   "budgetYears": "2026", "corpCode": "测试公司", "description": "模板历史说明"}


def task_authorization(task_id, mode="fill_only", statement="合成任务仅填写", save_basis=None):
    auth = {"mode": mode, "task_id": task_id, "statement": statement, "allow_submit": False}
    if save_basis is not None:
        auth["save_basis"] = save_basis
    return auth


def build_task(task_id="oneshot-synth-1", *, auth=None, synthetic=True,
               template_number=TEMPLATE_NUMBER, facts_payload="facts_payload.json"):
    task = {"schema_version": "1.0", "task_id": task_id, "document_type": "travel",
            "operator": "测试操作人", "template_biz_number": template_number,
            "materials_dir": "originals", "statement": "合成任务分支链路测试（仅机制验证）",
            "authorization": auth or task_authorization(task_id),
            "facts_payload": facts_payload}
    if synthetic:
        task["synthetic"] = True
    return task


def task_branch_factset(root, *, ledger_rel="originals/travel_ledger.xlsx"):
    """travel 合成事实集（同 test_bpm_plan_generate.travel_factset，但不加模板
    rendered 事实——任务分支该事实由本次 live 快照补全，agent 不得预供）。"""
    manifest = json.loads((root / "work" / "manifest.json").read_text(encoding="utf-8"))
    originals = {Path(item["path"]).name: item["sha256"] for item in manifest["files"]}
    ledger_sha = originals["travel_ledger.xlsx"]
    fs = FactSet(bindings={"ledger": ledger_sha})
    identity = fs.add("business_identity", source="user_instruction",
                      value={"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
                      locator="originals/user_instructions.json#/applicant/name")
    invoice_sha = originals["invoice.pdf"]
    invoice_id, _ = fs.add_invoice("00301234", "128.70", locator="work/reviewed/invoice#page:1",
                                   input_hashes={"extraction:" + invoice_sha: invoice_sha})
    expense = fs.add_expense("128.70", locator=ledger_rel + "#明细!B2",
                             input_hashes={"ledger": ledger_sha}, category="住宿",
                             value_extra={"digest": "住宿费测试"})
    fs.add_allocation(invoice_id, expense, "128.70", locator="分配#票1")
    payee = fs.add_payee(name="测试收款人", account="0000000001", branch="测试银行",
                         interbank="001234", amount="128.70", locator=ledger_rel + "#收款!A2",
                         input_hashes={"ledger": ledger_sha})
    budget = fs.add("budget", source="user_instruction", value={"year": "2026"},
                    locator="originals/user_instructions.json#/budgetYears")
    description = fs.add("scope", source="user_instruction", value={"text": "测试材料说明"},
                         locator="originals/user_instructions.json#/description")
    total = fs.add("total", source="deterministic_computation", derivation="明细合计=票据分配",
                   value={"amount": "128.70"}, locator="derived:total#sum")
    return fs, {"identity": identity, "invoice": invoice_id, "expense": expense,
                "payee": payee, "budget": budget, "description": description, "total": total}


TEMPLATE_FIELDS = ("bizOrign", "payType", "currencyType", "submitType")


def task_branch_blueprint(root, fs, ids, extraction, *, template_number=TEMPLATE_NUMBER):
    """travel 蓝图（模板派生 header 字段留白 + template_completion 声明）。"""
    ledger = "originals/travel_ledger.xlsx"
    entry = lambda value, fact_id, locator=None: ({"value": value, "fact_id": fact_id, "locator": locator}
                                                  if locator else {"value": value, "fact_id": fact_id})
    blueprint = {
        "document_type": "travel", "task_id": "oneshot-synth-1", "operator": "测试操作人",
        "applicant": {key: entry(value, ids["identity"], "originals/user_instructions.json#/applicant/" + key)
                      for key, value in fs.get(ids["identity"]).value.items()},
        "template": {"biz_number": template_number},
        "materials": {"manifest_path": str(root / "work" / "manifest.json")},
        "header": {
            "corpCode": entry("测试公司", ids["identity"], "originals/user_instructions.json#/applicant/company"),
            "budgetYears": entry("2026", ids["budget"], "originals/user_instructions.json#/budgetYears"),
            "description": entry("测试材料说明", ids["description"], "originals/user_instructions.json#/description"),
        },
        "template_completion": {
            "facts": [{"fact_key": "rendered", "kind": "scope",
                       "fields": {field: field for field in TEMPLATE_FIELDS}}],
            "header_fields": {field: "rendered" for field in TEMPLATE_FIELDS},
        },
        "tables": {
            "relations": [],
            "details": [{"row_id": "d0", "fields": {
                "reimItem": entry("差旅住宿", ids["expense"], ledger + "#明细!C2"),
                "digest": entry("住宿费测试", ids["expense"], ledger + "#明细!A2"),
                "budgetDeptName": entry("测试预算部", ids["expense"], ledger + "#明细!D2"),
                "budgetNo": entry("000123", ids["expense"], ledger + "#明细!E2"),
                "subjectName": entry("测试科目", ids["expense"], ledger + "#明细!F2"),
                "budgetItemName": entry("测试预算项目", ids["expense"], ledger + "#明细!G2"),
                "cost": entry("128.70", ids["expense"], ledger + "#明细!B2"),
            }}],
            "costs": [{"row_id": "c0", "fields": {
                "project": entry("住宿", ids["expense"], ledger + "#费用区间!A2"),
                "startDate": entry("2026-10-23", ids["expense"], ledger + "#费用区间!B2"),
                "endDate": entry("2026-10-23", ids["expense"], ledger + "#费用区间!C2"),
                "projectPlace": entry("测试地点", ids["expense"], ledger + "#费用区间!D2"),
                "count": entry("1", ids["expense"], ledger + "#费用区间!E2"),
                "cost": entry("128.70", ids["expense"], ledger + "#费用区间!F2"),
                "reason": entry("测试事由", ids["expense"], ledger + "#费用区间!G2"),
            }}],
            "banks": [{"row_id": "b0", "fields": {
                "payee": entry("测试收款人", ids["payee"], ledger + "#收款!A2"),
                "account": entry("0000000001", ids["payee"], ledger + "#收款!B2"),
                "bank": entry("测试银行", ids["payee"], ledger + "#收款!C2"),
                "bankCode": entry("001234", ids["payee"], ledger + "#收款!D2"),
                "cost": entry("128.70", ids["payee"], ledger + "#收款!E2"),
            }}],
        },
        "total": {"value": "128.70", "fact_id": ids["total"]},
        "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
        "not_applicable": [],
        "authorization": task_authorization("oneshot-synth-1"),
        "invoice_extractions": [{"invoice_fact_id": ids["invoice"],
                                 "extraction_path": str(extraction)}],
    }
    return blueprint


def build_task_branch_inputs(root, **task_kwargs):
    """合成任务分支输入：originals/ + work/ 双根 manifest + 提取件 + facts_payload + task.json。"""
    root = Path(root)
    w05, w03 = ensure_w05_fixtures(), ensure_w03_fixtures()
    originals = root / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    shutil.copy(w03 / "invoice.pdf", originals / "invoice.pdf")
    shutil.copy(w05 / "travel_ledger.xlsx", originals / "travel_ledger.xlsx")
    shutil.copy(w05 / "user_instructions.json", originals / "user_instructions.json")
    from bpm.materials import prepare_dual_materials
    manifest_path = prepare_dual_materials(originals, root / "work")
    from bpm.extraction import run_pdf_extraction
    run_pdf_extraction(manifest_path, "invoice.pdf")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    extraction = next(Path(item["path"]) for item in manifest["derived_files"]
                      if item["role"] == "reviewed_extraction")
    fs, ids = task_branch_factset(root)
    task = build_task(**task_kwargs)
    blueprint = task_branch_blueprint(root, fs, ids, extraction,
                                      template_number=task["template_biz_number"])
    payload = {"factset": fs.to_payload(), "blueprint": blueprint}
    (root / "facts_payload.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    (root / "task.json").write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
    return task, payload, root


class FakeTemplateRequest:
    """ctx.request 替身：按观察过的端点族返回合成模板 main/children（不猜端点）。"""

    def __init__(self, number=TEMPLATE_NUMBER, uuid=TEMPLATE_UUID, header=None):
        self.number, self.uuid = number, uuid
        self.header = dict(header or TEMPLATE_HEADER)
        self.calls = []

    def get(self, path, headers=None, timeout=None, max_redirects=0,
            max_retries=0, ignore_https_errors=False):
        if max_redirects != 0 or max_retries != 0 or ignore_https_errors is not False:
            raise AssertionError("read-only API transport boundary changed")
        # fetch_template 以 API_ORIGIN + path 调用（完整 URL），children 为空数组。
        self.calls.append(path)
        if path.endswith("/reimburse/" + self.uuid):
            return _FakeResponse({"bizNumber": self.number, "id": self.uuid, **self.header})
        return _FakeResponse([])


class _FakeResponse:
    def __init__(self, payload):
        self.status, self._payload = 200, payload

    def text(self):
        return json.dumps(self._payload)


# ------------------------------------------------------------ G2 授权编译

class CompileAuthorizationTests(unittest.TestCase):
    def test_synthetic_task_forces_fill_only_even_when_save_requested(self):
        task = build_task(auth=task_authorization("oneshot-synth-1", mode="save_draft",
                                                  save_basis={"kind": "user_request", "reference": "用户消息"}))
        block, meta = oneshot.compile_authorization(task, {})
        self.assertEqual(block["mode"], "fill_only")
        self.assertEqual(meta["branch"], "synthetic_forced_fill_only")
        self.assertEqual(meta["requested_mode"], "save_draft")

    def test_blueprint_test_context_forces_fill_only(self):
        task = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft",
            save_basis={"kind": "standing_policy", "reference": oneshot.A1_STANDING_POLICY}))
        block, meta = oneshot.compile_authorization(task, {"test_context": {"purpose": "x"}})
        self.assertEqual(block["mode"], "fill_only")
        self.assertTrue(meta["synthetic"])

    def test_declared_fill_only_stays_fill_only(self):
        block, meta = oneshot.compile_authorization(build_task(synthetic=False), {})
        self.assertEqual((block["mode"], meta["branch"]), ("fill_only", "declared_fill_only"))

    def test_save_draft_with_user_request_basis_compiles(self):
        task = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft",
            save_basis={"kind": "user_request", "reference": "用户 2026-10-28 消息：这份报完帮我存草稿"}))
        block, meta = oneshot.compile_authorization(task, {})
        self.assertEqual(block["mode"], "save_draft")
        self.assertEqual(meta["request_source"]["kind"], "user_request")
        self.assertEqual(block["task_id"], task["task_id"])
        self.assertFalse(block["allow_submit"])

    def test_save_draft_with_a1_standing_policy_compiles(self):
        task = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft", statement="A1 日常策略：日常真实报销自动存草稿",
            save_basis={"kind": "standing_policy", "reference": oneshot.A1_STANDING_POLICY}))
        block, meta = oneshot.compile_authorization(task, {})
        self.assertEqual(block["mode"], "save_draft")
        self.assertEqual(meta["request_source"]["reference"], "BPM-SELFDRIVE-20261027-A1")

    def test_unknown_standing_policy_reference_rejected(self):
        task = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft",
            save_basis={"kind": "standing_policy", "reference": "SOME-OTHER-POLICY"}))
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.compile_authorization(task, {})
        self.assertEqual(caught.exception.issues[0]["code"], "UNKNOWN_STANDING_POLICY")


class TaskSchemaTests(unittest.TestCase):
    """validate_task 最小兼容调整：synthetic 标记 + save_draft 必带 save_basis。"""

    def base_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        (Path(tmp.name) / "originals").mkdir()
        return Path(tmp.name)

    def test_synthetic_marker_accepted_and_typed(self):
        root = self.base_dir()
        self.assertEqual(validate_task(build_task(), root), [])
        bad = build_task()
        bad["synthetic"] = "yes"
        issues = validate_task(bad, root)
        self.assertTrue(any(i["path"] == "/synthetic" for i in issues))

    def test_save_draft_requires_structured_save_basis(self):
        root = self.base_dir()
        no_basis = build_task(synthetic=False, auth=task_authorization("oneshot-synth-1", mode="save_draft"))
        issues = validate_task(no_basis, root)
        self.assertTrue(any(i["path"] == "/authorization/save_basis" for i in issues))
        good = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft",
            save_basis={"kind": "user_request", "reference": "用户消息定位"}))
        self.assertEqual(validate_task(good, root), [])
        bad_kind = build_task(synthetic=False, auth=task_authorization(
            "oneshot-synth-1", mode="save_draft", save_basis={"kind": "history", "reference": "旧任务"}))
        self.assertTrue(any(i["path"] == "/authorization/save_basis"
                            for i in validate_task(bad_kind, root)))

    def test_fill_only_carries_no_save_basis(self):
        root = self.base_dir()
        task = build_task(auth=task_authorization("oneshot-synth-1", mode="fill_only",
                                                  save_basis={"kind": "user_request", "reference": "x"}))
        self.assertTrue(any(i["path"] == "/authorization/save_basis"
                            for i in validate_task(task, root)))


# ------------------------------------------------------------ 模板补全与记录绑定

class TemplateCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snapshot_path = self.root / "template_snapshot.json"
        self.snapshot = {"biz_number": TEMPLATE_NUMBER, "uuid": TEMPLATE_UUID,
                         "document_type": "travel", "captured_at": "2026-10-28T05:00:00+00:00",
                         "header": dict(TEMPLATE_HEADER)}
        self.snapshot_path.write_text(json.dumps(self.snapshot, ensure_ascii=False), encoding="utf-8")
        self.task = build_task()

    def payload(self, *, blueprint_header=None, template=None, completion=None):
        fs = FactSet()
        identity = fs.add("business_identity", source="user_instruction",
                          value={"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
                          locator="originals/user_instructions.json#/applicant/name")
        blueprint = {"header": dict(blueprint_header or {"corpCode": {"value": "测试公司", "fact_id": identity}}),
                     "template": template if template is not None else {"biz_number": TEMPLATE_NUMBER},
                     "template_completion": completion if completion is not None else {
                         "facts": [{"fact_key": "rendered", "kind": "scope",
                                    "fields": {f: f for f in TEMPLATE_FIELDS}}],
                         "header_fields": {f: "rendered" for f in TEMPLATE_FIELDS}}}
        return {"factset": fs.to_payload(), "blueprint": blueprint}

    def test_completion_takes_values_from_live_snapshot_only(self):
        payload = self.payload()
        factset, blueprint = oneshot.complete_from_live_snapshot(
            self.task, payload, self.snapshot, self.snapshot_path)
        rendered = factset.get(blueprint["header"]["bizOrign"]["fact_id"])
        self.assertEqual(rendered.source, "template")
        self.assertEqual(rendered.value, {f: TEMPLATE_HEADER[f] for f in TEMPLATE_FIELDS})
        self.assertEqual(rendered.input_hashes, {"template": file_hash(self.snapshot_path)})
        for field in TEMPLATE_FIELDS:
            entry = blueprint["header"][field]
            self.assertEqual(entry["value"], TEMPLATE_HEADER[field])
            self.assertTrue(entry["locator"].endswith("#/header/" + field))
            self.assertEqual(entry["fact_id"], rendered.fact_id)
        self.assertEqual(blueprint["template"]["sha256"], file_hash(self.snapshot_path))
        self.assertEqual(blueprint["template"]["biz_number"], TEMPLATE_NUMBER)
        self.assertEqual(blueprint["template"]["snapshot_path"], str(self.snapshot_path))

    def test_pre_supplied_template_value_rejected(self):
        payload = self.payload(blueprint_header={
            "corpCode": {"value": "测试公司", "fact_id": "F-0001"},
            "payType": {"value": "预供旧值", "fact_id": "F-0001"}})
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.complete_from_live_snapshot(self.task, payload, self.snapshot, self.snapshot_path)
        self.assertTrue(any(i["code"] == "TEMPLATE_VALUE_PRE_SUPPLIED" for i in caught.exception.issues))

    def test_pre_frozen_template_block_rejected(self):
        payload = self.payload(template={"biz_number": TEMPLATE_NUMBER, "sha256": "0" * 64,
                                         "snapshot_path": "old.json"})
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.complete_from_live_snapshot(self.task, payload, self.snapshot, self.snapshot_path)
        self.assertTrue(any(i["code"] == "TEMPLATE_PRE_FROZEN" for i in caught.exception.issues))
        task = build_task()
        task["template_snapshot_path"] = "old.json"
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.complete_from_live_snapshot(task, self.payload(), self.snapshot, self.snapshot_path)
        self.assertTrue(any(i["code"] == "TEMPLATE_PRE_FROZEN" for i in caught.exception.issues))

    def test_missing_snapshot_header_key_is_a_structured_gap(self):
        snapshot = {**self.snapshot, "header": {"bizOrign": "测试流程"}}  # 缺其余 3 键
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.complete_from_live_snapshot(self.task, self.payload(), snapshot, self.snapshot_path)
        codes = [i["code"] for i in caught.exception.issues]
        self.assertEqual(codes.count("SNAPSHOT_FIELD_MISSING"), 3)

    def test_template_number_conflict_rejected(self):
        payload = self.payload(template={"biz_number": "999"})
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.complete_from_live_snapshot(self.task, payload, self.snapshot, self.snapshot_path)
        self.assertTrue(any(i["code"] == "TEMPLATE_NUMBER_CONFLICT" for i in caught.exception.issues))


class AuthorizationRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task = build_task()

    def test_record_carries_four_bindings_and_no_self_reference(self):
        plan = {"task_id": "oneshot-synth-1", "document_type": "travel", "operator": "测试操作人",
                "authorization": {"mode": "fill_only", "task_id": "oneshot-synth-1",
                                  "statement": "s", "allow_submit": False}}
        meta = {"branch": "synthetic_forced_fill_only",
                "request_source": {"kind": "forced_fill_only", "reference": "task.synthetic=true"},
                "synthetic": True, "requested_mode": "fill_only"}
        record = oneshot.build_authorization_record(self.task, plan, meta, self.root)
        self.assertEqual(record["task_id"], plan["task_id"])
        self.assertEqual(record["plan_hash"], plan_hash(plan))
        self.assertEqual(record["config_sha256"], resolve_type("travel").sha256)
        self.assertEqual(record["operator"], self.task["operator"])
        # 无自引用：记录不进计划，计划不载记录哈希。
        self.assertNotIn("authorization_record", plan)
        self.assertNotIn("record_sha256", plan)
        oneshot.verify_record_bindings(record, plan, self.task)  # 不抛

    def test_binding_conflict_stops_instead_of_rebinding(self):
        plan = {"task_id": "oneshot-synth-1", "document_type": "travel", "operator": "测试操作人",
                "authorization": {"mode": "fill_only", "task_id": "oneshot-synth-1",
                                  "statement": "s", "allow_submit": False}}
        record = {"task_id": "oneshot-synth-1", "plan_hash": "0" * 64,
                  "config_sha256": resolve_type("travel").sha256, "operator": "测试操作人"}
        with self.assertRaises(oneshot.OneshotPrepareBlocked) as caught:
            oneshot.verify_record_bindings(record, plan, self.task)
        self.assertEqual(caught.exception.issues[0]["code"], "AUTHORIZATION_BINDING_CONFLICT")


# ------------------------------------------------------------ CLI 两分支

class OneshotCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.registry = self.root / "task-registry"
        self.registry.mkdir()
        patcher = mock.patch.object(oneshot, "REGISTRY", self.registry)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = oneshot.main(argv)
        return code, json.loads(out.getvalue().strip().splitlines()[-1])

    def test_plan_branch_validate_only_reuses_real_validation(self):
        from test_bpm_verify import build_fixture
        plan, _ = build_fixture(self.root)
        plan_path = self.root / "fill_plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        code, payload = self.run_main(["--fill-plan", str(plan_path),
                                       "--expect-name", plan["operator"], "--validate-only"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "PLAN_VALIDATED")
        self.assertEqual(payload["plan_sha256"], plan_hash(plan))
        self.assertFalse(payload["browser_launched"])

    def test_task_branch_validate_only_reports_compiled_authorization(self):
        task, _, root = build_task_branch_inputs(self.root / "inputs")
        code, payload = self.run_main(["--task", str(root / "task.json"),
                                       "--expect-name", task["operator"], "--validate-only"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "TASK_VALIDATED")
        self.assertEqual(payload["compiled_authorization"]["branch"], "synthetic_forced_fill_only")
        self.assertEqual(payload["compiled_authorization"]["mode"], "fill_only")

    def test_existing_save_intent_blocks_new_task_run_without_browser(self):
        task, _, root = build_task_branch_inputs(self.root / "inputs")
        import hashlib
        journal = self.registry / (hashlib.sha256(task["task_id"].encode("utf-8")).hexdigest() + ".json")
        journal.write_text(json.dumps({"task_id": task["task_id"], "status": "SAVE_INTENT"}), encoding="utf-8")
        code, payload = self.run_main(["--task", str(root / "task.json"),
                                       "--expect-name", task["operator"]])
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "EXISTING_SAVE_INTENT")
        self.assertFalse(payload["browser_launched"])

    def test_missing_facts_payload_is_a_structured_gap(self):
        (self.root / "originals").mkdir()
        task = build_task()
        task.pop("facts_payload")
        task_path = self.root / "task.json"
        task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
        code, payload = self.run_main(["--task", str(task_path), "--expect-name", task["operator"]])
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "NEEDS_INPUT")
        self.assertTrue(any(i["path"] == "/facts_payload" for i in payload["issues"]))

    def test_operator_identity_mismatch_refused(self):
        task, _, root = build_task_branch_inputs(self.root / "inputs")
        code, payload = self.run_main(["--task", str(root / "task.json"),
                                       "--expect-name", "另一位操作人", "--validate-only"])
        self.assertEqual(code, 2)
        self.assertTrue(any(i["code"] == "IDENTITY_MISMATCH" for i in payload["issues"]))


# ------------------------------------------------------------ 任务分支 DOM 全链

LIST_HTML = '''<!doctype html><meta charset="utf-8"><label for="BizNumber1">单据编号</label>
  <input id="BizNumber1"><label for="BizNumber22">关联单号</label><input id="BizNumber22">
  <table><thead><tr><th class="prop-submitType">类别</th></tr></thead></table>
  <button onclick="fetch('https://oa.api.qiaodan.com/reimburse/query/20/1?for=1')">查询</button>'''


class TaskBranchChainDOMTests(unittest.TestCase):
    """同会话：模板读取→补全→生成→冻结→绑定→填写→独立回读（G1.3 最小贯通场景）。"""

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-proxy-server"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.task, self.payload, self.inputs = build_task_branch_inputs(self.root / "inputs")
        self.run_dir = self.root / "run"
        self.run_dir.mkdir(parents=True)
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()
        self.addCleanup(self.page.close)
        items = [{"id": TEMPLATE_UUID, "bizNumber": TEMPLATE_NUMBER}]
        # Playwright 路由后注册者优先：先挂兜底 **/*，再挂列表页/查询 API 专用路由。
        self.context.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html", body="<!doctype html><meta charset='utf-8'>"))
        self.context.route("https://bpm.qiaodan.com/oa/reimburses", lambda route: route.fulfill(
            status=200, content_type="text/html", body=LIST_HTML))
        self.context.route("https://oa.api.qiaodan.com/**", lambda route: route.fulfill(
            status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
            body=json.dumps({"data": {"content": items}})))
        self.page.goto("https://bpm.qiaodan.com/oa/reimburse?type=new")
        from bpm.ui import DraftUIAdapter
        from bpm.ui import StructuredProbe  # noqa: F401  (object.__new__ 形态)
        self.p = object.__new__(oneshot.TaskBranchProbe)
        self.p.page = self.page
        self.fake_request = FakeTemplateRequest()
        self.p.ctx = types.SimpleNamespace(request=self.fake_request)
        self.p.args = types.SimpleNamespace(expect_name=self.task["operator"])
        self.p.run_dir = self.run_dir
        self.p.attempt = self.run_dir / "attempt_001"
        self.p.ev = self.p.attempt / "evidence"
        self.p.ev.mkdir(parents=True)
        self.p.fill_plan = None
        self.p.type_config = None
        self.p.bound_plan_hash = None
        self.p.config_hash = None
        self.p.plan_base = None
        self.p.native_dialogs = []
        self.p.result = {"checks": {}, "phases": {}}
        self.p.login_state = lambda page: ("LOGGED_IN", {}, {})
        self.p.adapter = DraftUIAdapter(self.p)
        self.p._preparation = {"task": self.task, "payload": self.payload,
                               "payload_path": self.inputs / "facts_payload.json", "run_dir": self.run_dir,
                               "binding": {"kind": "oneshot_task", "task_id": self.task["task_id"],
                                           "task_sha256": plan_hash(self.task),
                                           "operator": self.task["operator"],
                                           "config_sha256": resolve_type("travel").sha256},
                               "frozen": None}
        self.p.pending_task_prepare = self.p._prepare_and_freeze

    def test_prepare_freeze_bind_and_fill_chain(self):
        from bpm.browser_probe import PASS
        self.assertEqual(self.p._prepare_and_freeze(), PASS,
                         json.dumps(self.p.result.get("issues"), ensure_ascii=False))
        # 冻结工件：run 根的最终计划/授权记录/绑定（含 plan_sha256）。
        plan_path = self.run_dir / "fill_plan.json"
        self.assertTrue(plan_path.is_file())
        record = json.loads((self.run_dir / "authorization_record.json").read_text(encoding="utf-8"))
        self.assertEqual(record["plan_hash"], self.p.bound_plan_hash)
        self.assertEqual(record["branch"], "synthetic_forced_fill_only")
        binding = json.loads((self.run_dir / "task_binding.json").read_text(encoding="utf-8"))
        self.assertEqual(binding["plan_sha256"], self.p.bound_plan_hash)
        self.assertEqual(binding["kind"], "oneshot_task")
        snapshot_file = self.run_dir / "template_snapshot.json"
        self.assertTrue(snapshot_file.is_file())
        # 模板字段值来自本次 live 快照（非 agent 预供）。
        live = json.loads(snapshot_file.read_text(encoding="utf-8"))
        for field in TEMPLATE_FIELDS:
            self.assertEqual(self.p.fill_plan["header"][field], live["header"][field])
        self.assertEqual(self.p.fill_plan["authorization"]["mode"], "fill_only")
        self.assertEqual(validate_plan(self.p.fill_plan, base_dir=self.run_dir), [])
        # 同会话继续填写：模板读取曾把主 tab 导航到列表页；填写链从新表单
        # URL 重新开始（与生产 phase_fill 开新表单一致），再填入并独立回读。
        self.page.goto("https://bpm.qiaodan.com/oa/reimburse?type=new")
        self.page.set_content(test_bpm_ui.form_html(self.p.fill_plan))
        self.p._fill_arrays()
        snapshot = self.p.adapter.capture_snapshot()
        check = verify_snapshot(self.p.fill_plan, snapshot, base_dir=self.run_dir)
        self.assertTrue(check["ok"], check["issues"])
        # G2.5 重试：复用冻结产物，不重新生成（无模板请求即通过）。
        events_before = self.fake_request.calls[:]
        frozen = {"plan": load_plan(plan_path, expected_operator=self.task["operator"]),
                  "plan_path": plan_path}
        probe2 = object.__new__(oneshot.TaskBranchProbe)
        for key, value in vars(self.p).items():
            setattr(probe2, key, value)
        for attr in ("fill_plan", "type_config", "bound_plan_hash", "config_hash", "plan_base"):
            setattr(probe2, attr, None)
        probe2._preparation = {**self.p._preparation, "frozen": frozen}
        probe2.pending_task_prepare = probe2._prepare_and_freeze
        self.assertEqual(probe2._prepare_and_freeze(), PASS)
        self.assertEqual(probe2.bound_plan_hash, self.p.bound_plan_hash)
        self.assertEqual(self.fake_request.calls, events_before)  # 未再读模板

    def test_prepare_gap_keeps_need_input_without_frozen_plan(self):
        # 蓝图预冻结模板快照 → 结构化缺口，返回 BLOCKED，不产计划。
        self.payload["blueprint"]["template"] = {"biz_number": TEMPLATE_NUMBER, "sha256": "0" * 64}
        from bpm.browser_probe import BLOCKED
        self.assertEqual(self.p._prepare_and_freeze(), BLOCKED)
        self.assertEqual(self.p.result["task_status"], "NEEDS_INPUT")
        self.assertTrue(any(i["code"] == "TEMPLATE_PRE_FROZEN" for i in self.p.result["issues"]))
        self.assertFalse((self.run_dir / "fill_plan.json").exists())


# ------------------------------------------------------------ G3 只读副页

class VerificationSidePageDOMTests(test_bpm_ui.DOMTests):
    def _saved_route(self):
        return "https://bpm.qiaodan.com/oa/reimburse?type=view&id=" + "b" * 32

    def _serve_saved(self, calls=None):
        saved_html = test_bpm_ui.form_html(self.plan).replace('id="bizNumber0" name="bizNumber0" value=""',
                                                  'id="bizNumber0" name="bizNumber0" value="15426000002"')
        def serve(route):
            if calls is not None:
                calls.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=saved_html)
        self.context.unroute("**/*")
        self.context.route("**/*", serve)
        return saved_html

    def test_reopen_routes_to_side_page_and_main_tab_stays(self):
        self._serve_saved()
        self.p.adapter._identity_routes["b" * 32] = self._saved_route()
        identity = {"uuid": "b" * 32, "biz_number": "15426000002", "status": "编制中"}
        opened = []
        original_open = self.p.adapter.open_verification_page
        def open_and_track():
            page = original_open()
            opened.append(page)
            return page
        self.p.adapter.open_verification_page = open_and_track
        try:
            snap = self.p.adapter.reopen(identity)
        finally:
            self.p.adapter.open_verification_page = original_open
        # 回读来自副页：主 tab 仍在新表单，未被核验导航。
        self.assertEqual(len(opened), 1)
        self.assertEqual(snap["page"]["biz_number"], "15426000002")
        self.assertIn("type=new", self.page.url)
        self.assertFalse(self.page.is_closed())
        self.assertIsNotNone(self.p.adapter._verification_page)
        self.assertFalse(opened[0].is_closed())
        # 事件以非敏感标识区分主/副页角色。
        self.assertIn("verification_page_opened",
                      (self.root / "events.jsonl").read_text(encoding="utf-8"))
        self.p.adapter.close_verification_page()
        self.assertIsNone(self.p.adapter._verification_page)
        self.assertTrue(opened[0].is_closed())
        events = (self.root / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("verification_page_closed", events)

    def test_save_flow_closes_side_page_and_keeps_main_tab(self):
        from bpm.save import SaveController
        calls = []
        self._serve_saved(calls)
        self.page.locator("#save").evaluate("(e,url)=>e.onclick=()=>location.href=url", self._saved_route())
        result = SaveController(self.plan, self.p.adapter, self.p.attempt,
                                expected_operator=self.plan["operator"], journal_dir=self.root / "registry").run()
        self.assertEqual(result["status"], "SUCCESS_DRAFT_SAVED", result)
        # 副页已在收尾 finally 关闭；主 tab 保留（保存动作自身的合法跳转如实呈现）。
        self.assertIsNone(self.p.adapter._verification_page)
        self.assertFalse(self.page.is_closed())
        self.assertEqual(self.page.url, self._saved_route())
        self.assertGreaterEqual(len(calls), 2)  # 保存后主页面 + 副页持久化核验
        self.assertTrue((self.p.ev / "draft_saved.png").is_file())
        events = (self.root / "events.jsonl").read_text(encoding="utf-8")
        self.assertIn("verification_page_opened", events)
        self.assertIn("verification_page_closed", events)

    def test_second_verification_page_open_is_refused(self):
        from bpm.ui import UIBlocked
        self.p.adapter.open_verification_page()
        self.addCleanup(self.p.adapter.close_verification_page)
        with self.assertRaises(UIBlocked):
            self.p.adapter.open_verification_page()


# ------------------------------------------------------------ G3.4/G3.5 交付与驻留

class DeliveryAndParkTests(unittest.TestCase):
    """C09 短驻留夹具：完成事件先于驻留发布、驻留边界、占用拒绝与锁归属清理。"""

    def _probe(self, *, keep_open, fill_plan="BOUND", pending=None, c1="PASS", ctx=True):
        from bpm.ui import StructuredProbe
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        probe = object.__new__(StructuredProbe)
        probe.run_dir = root
        probe.result = {"task_status": "NEEDS_INPUT", "save_status": "NOT_ATTEMPTED", "plan_hash": "h"}
        probe.args = types.SimpleNamespace(keep_open_minutes=keep_open, login_only=False)
        probe.checks = {"c1_entry_login": {"status": c1}}
        probe.budget = types.SimpleNamespace(wall_cap=100.0)
        probe.fill_plan = fill_plan
        probe.pending_task_prepare = pending
        probe.ctx = object() if ctx else None
        parked = []

        def park(minutes):
            parked.append(minutes)
            probe.log_event(event="keep_open_start", minutes=minutes)

        probe._park_browser = park
        return probe, root, parked

    def events(self, root):
        return [json.loads(line) for line in
                (root / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_result_delivered_published_before_park_with_lifecycle_counts(self):
        probe, root, parked = self._probe(keep_open=0.5)
        probe._deliver_and_park("SUCCESS_FILL_ONLY")
        events = self.events(root)
        # 交付锚点先于驻留：上层在完成事件后即可读取权威结果，不等驻留结束。
        self.assertEqual([e["event"] for e in events],
                         ["result_delivered", "keep_open_start"])
        delivered = events[0]
        self.assertEqual(delivered["finish_reason"], "SUCCESS_FILL_ONLY")
        self.assertEqual(delivered["task_status"], "NEEDS_INPUT")
        self.assertEqual((delivered["business_executors"], delivered["browser_instances"],
                          delivered["business_contexts"], delivered["lock_owners"],
                          delivered["driver_subprocesses"]), (1, 1, 1, 1, 0))
        self.assertEqual(parked, [0.5])
        # 驻留不计入技术耗时：进入驻留前扩容 wall_cap。
        self.assertEqual(probe.budget.wall_cap, 100.0 + 0.5 * 60)

    def test_prepare_gap_releases_lock_without_park(self):
        # 仅准备阶段缺口（无表单可审）：不驻留，尽快释放锁，不占用下一任务。
        probe, root, parked = self._probe(keep_open=45, fill_plan=None, pending=lambda: "PASS")
        probe._deliver_and_park("BLOCKED")
        self.assertEqual(parked, [])
        self.assertEqual(probe.budget.wall_cap, 100.0)
        self.assertEqual([e["event"] for e in self.events(root)], ["result_delivered"])

    def test_task_branch_login_failure_retains_for_human_login(self):
        probe, root, parked = self._probe(keep_open=30, fill_plan=None,
                                          pending=lambda: "PASS", c1="BLOCKED")
        probe._deliver_and_park("WAIT_HUMAN_LOGIN")
        self.assertEqual(parked, [30])

    def test_zero_keep_open_never_parks(self):
        probe, root, parked = self._probe(keep_open=0)
        probe._deliver_and_park("SUCCESS_FILL_ONLY")
        self.assertEqual(parked, [])

    def test_park_waits_only_and_ends_at_term_or_early_close(self):
        # 驻留期间只等待不操作（不保存不提交）：期限耗尽正常结束；用户提前
        # 关闭本任务页时按既有规则提前结束（StructuredProbe._park_browser）。
        def run_park(closed_flag):
            probe, root, _ = self._probe(keep_open=2)
            del probe._park_browser  # 本例直接测真实 _park_browser（_probe 默认换成桩）
            probe.say = lambda *a, **k: None
            waits = []
            probe.page = types.SimpleNamespace(
                is_closed=lambda: closed_flag,
                wait_for_timeout=lambda ms: waits.append(ms))
            probe._park_browser(2)
            return probe, root, waits

        probe, root, waits = run_park(False)
        self.assertEqual(waits, [60000, 60000])  # 2 分钟驻留，每分钟一次等待
        self.assertEqual([(e["event"], e.get("task_status")) for e in self.events(root)],
                         [("keep_open_start", "NEEDS_INPUT"), ("keep_open_end", "NEEDS_INPUT")])
        probe, root, waits = run_park(True)  # 用户已提前关闭
        self.assertEqual(waits, [])
        self.assertEqual([e["event"] for e in self.events(root)],
                         ["keep_open_start", "keep_open_end"])

    def test_next_task_refused_while_owner_alive_and_lock_not_stolen(self):
        # 同 profile 驻留所有者存活时下一任务占用拒绝；他人锁不被只读方删除；
        # 进程消失后按既有陈旧接管规则处理（判活走 ctypes OpenProcess 生产路径）。
        import subprocess
        import sys
        import time as _time
        from bpm.ui import StructuredProbe
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        holder = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(holder.kill)
        probe = object.__new__(StructuredProbe)
        probe.run_dir = root
        probe._lock_path = root / "executor.lock"
        for _ in range(50):
            if probe._pid_alive(holder.pid):
                break
            _time.sleep(0.1)
        else:
            self.fail("holder process not alive for lock test")
        probe._lock_path.write_text(str(holder.pid), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "PROFILE_LOCKED"):
            probe.acquire_lock()
        probe.release_lock()  # 只读核实方不得删除他人锁
        self.assertEqual(probe._lock_path.read_text(encoding="utf-8").strip(), str(holder.pid))
        holder.kill()
        holder.wait()
        probe.acquire_lock()  # 陈旧锁按既有规则接管
        names = [e["event"] for e in self.events(root)]
        self.assertIn("profile_lock_stale_taken_over", names)
        self.assertIn("profile_lock_acquired", names)
        probe.release_lock()
        self.assertFalse(probe._lock_path.exists())

    def test_release_lock_only_removes_own_pid_file(self):
        from bpm.ui import StructuredProbe
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        probe = object.__new__(StructuredProbe)
        probe.run_dir = root
        probe._lock_path = root / "executor.lock"
        probe._lock_path.write_text(str(os.getpid()), encoding="utf-8")
        probe.release_lock()
        self.assertFalse(probe._lock_path.exists())


if __name__ == "__main__":
    unittest.main()
