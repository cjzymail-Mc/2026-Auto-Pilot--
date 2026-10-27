"""W05 生成器与阶段衔接单测（全部合成材料；R3-P2 两小修同册）。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bpm.facts import FactSet, _dec, reconcile
from bpm.extraction import run_pdf_extraction
from bpm.materials import prepare_dual_materials
from bpm.plan import file_hash, load_plan, validate_plan
from bpm.plan_generate import PlanGenerationError, generate_fill_plan

from test_bpm_extraction import ensure_fixtures as ensure_w03_fixtures

FIXTURES = Path(__file__).resolve().parent / "fixtures"
W05 = FIXTURES / "w05"
STAMP = W05 / "w05-v3"


def ensure_w05_fixtures():
    """幂等：travel_ledger.xlsx 三 sheet 原件语义件 + user_instructions.json。"""
    if W05.is_dir() and not STAMP.is_file():
        shutil.rmtree(W05)
    if STAMP.is_file():
        return W05
    W05.mkdir(parents=True, exist_ok=True)
    import openpyxl
    book = openpyxl.Workbook()
    detail = book.active
    detail.title = "明细"
    detail.append(["摘要", "金额", "项目", "预算部门", "预算编号", "科目", "预算项目"])
    detail.append(["住宿费测试", 128.70, "差旅住宿", "测试预算部", "000123", "测试科目", "测试预算项目"])
    costs = book.create_sheet("费用区间")
    costs.append(["项目", "开始", "结束", "地点", "数量", "金额", "事由"])
    costs.append(["住宿", "2026-10-23", "2026-10-23", "测试地点", "1", 128.70, "测试事由"])
    banks = book.create_sheet("收款")
    banks.append(["收款人", "账号", "开户行", "联行号", "金额"])
    banks.append(["测试收款人", "0000000001", "测试银行", "001234", 128.70])
    book.save(str(W05 / "travel_ledger.xlsx"))
    (W05 / "user_instructions.json").write_text(json.dumps({
        "applicant": {"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
        "budgetYears": "2026", "description": "测试材料说明",
        "no_invoice_rule": "离线合成数据免票理由：测试费用明确无需发票（仅机制验证）",
        "relation_rule": "快递任务无关联单据",
        "costs_rule": "快递任务按明细行报销，无费用区间明细"
    }, ensure_ascii=False), encoding="utf-8")
    STAMP.write_text("synthetic fixtures only; regenerate by deleting this stamp", encoding="utf-8")
    return W05


def check_by_name(report, name):
    return next(c for c in report.checks if c.name == name)


class W05TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w05 = ensure_w05_fixtures()
        cls.w03 = ensure_w03_fixtures()

    def prepared_task_root(self, *, with_invoice=True):
        """合成任务根：originals/（发票+xlsx+user json）+ work/ 双根 + 模板快照。"""
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        originals = root / "originals"
        originals.mkdir()
        shutil.copy(self.w03 / "invoice.pdf", originals / "invoice.pdf")
        shutil.copy(self.w05 / "travel_ledger.xlsx", originals / "travel_ledger.xlsx")
        shutil.copy(self.w05 / "user_instructions.json", originals / "user_instructions.json")
        manifest_path = prepare_dual_materials(originals, root / "work")
        extraction = None
        if with_invoice:
            result = run_pdf_extraction(manifest_path, "invoice.pdf")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            extraction = next(Path(item["path"]) for item in manifest["derived_files"]
                              if item["role"] == "reviewed_extraction")
        snapshot = root / "template_snapshot.json"
        snapshot.write_text(json.dumps({
            "biz_number": "000123456", "captured_at": "2026-10-24T10:00:00+08:00",
            "rendered_options": {"bizOrign": "测试流程", "payType": "转账",
                                 "currencyType": "人民币", "submitType": "差旅费"}
        }, ensure_ascii=False), encoding="utf-8")
        return root, manifest_path, extraction, snapshot


def travel_factset(root, *, ledger_rel="originals/travel_ledger.xlsx"):
    """travel 合成事实集：身份(user)/票据(extraction)/费用(xlsx)/收款/总额。"""
    manifest = json.loads((root / "work" / "manifest.json").read_text(encoding="utf-8"))
    originals = {Path(item["path"]).name: item["sha256"] for item in manifest["files"]}
    ledger_sha = originals["travel_ledger.xlsx"]
    fs = FactSet(bindings={"ledger": ledger_sha})
    identity = fs.add("business_identity", source="user_instruction",
                      value={"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
                      locator="originals/user_instructions.json#/applicant/name")
    invoice_sha = originals["invoice.pdf"]
    invoice_id, _ = fs.add_invoice("00301234", "128.70",
                                   locator="work/reviewed/invoice#page:1",
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
    rendered = fs.add("scope", source="template",
                      value={"bizOrign": "测试流程", "payType": "转账",
                             "currencyType": "人民币", "submitType": "差旅费"},
                      locator="template_snapshot.json#/rendered_options/bizOrign",
                      input_hashes={"template": file_hash(root / "template_snapshot.json")})
    return fs, {"identity": identity, "invoice": invoice_id, "expense": expense,
                "payee": payee, "budget": budget, "description": description,
                "total": total, "rendered": rendered}


def travel_blueprint(root, facts, ids, extraction, snapshot):
    ledger = "originals/travel_ledger.xlsx"
    entry = lambda value, fact_id, locator=None: ({"value": value, "fact_id": fact_id, "locator": locator}
                                                  if locator else {"value": value, "fact_id": fact_id})
    blueprint = {
        "document_type": "travel", "task_id": "synthetic-w05",
        "operator": "测试操作人",
        "applicant": {key: entry(value, ids["identity"], "originals/user_instructions.json#/applicant/" + key)
                      for key, value in facts.get(ids["identity"]).value.items()},
        "template": {"biz_number": "000123456", "captured_at": "2026-10-24T10:00:00+08:00",
                     "sha256": file_hash(snapshot), "snapshot_path": str(snapshot)},
        "materials": {"manifest_path": str(root / "work" / "manifest.json")},
        "header": {
            "corpCode": entry("测试公司", ids["identity"], "originals/user_instructions.json#/applicant/company"),
            "bizOrign": entry("测试流程", ids["rendered"], "template_snapshot.json#/rendered_options/bizOrign"),
            "budgetYears": entry("2026", ids["budget"], "originals/user_instructions.json#/budgetYears"),
            "payType": entry("转账", ids["rendered"], "template_snapshot.json#/rendered_options/payType"),
            "currencyType": entry("人民币", ids["rendered"], "template_snapshot.json#/rendered_options/currencyType"),
            "submitType": entry("差旅费", ids["rendered"], "template_snapshot.json#/rendered_options/submitType"),
            "description": entry("测试材料说明", ids["description"], "originals/user_instructions.json#/description"),
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
        "authorization": {"mode": "fill_only", "task_id": "synthetic-w05",
                          "statement": "仅填写本合成测试任务", "allow_submit": False},
        "invoice_extractions": [{"invoice_fact_id": ids["invoice"],
                                 "extraction_path": str(extraction)}],
    }
    return blueprint


# ------------------------------------------------------------ R3-P2 两小修

class R3P2FixTests(W05TestCase):
    def test_dec_rejects_over_two_decimals(self):
        # R4-P2d：正例断言真实量化结果，不用同义反复
        for good, expect in (("128.70", "128.70"), ("100", "100.00"), ("0.5", "0.50"),
                             (128.7, "128.70"), ("112.00", "112.00"), (7, "7.00")):
            self.assertEqual(str(_dec(good)), expect)
        for bad in ("100.004", "0.005", 1.234, "1.2345"):
            with self.assertRaises(ValueError):
                _dec(bad)

    def test_same_account_different_names_blocked(self):
        fs = FactSet()
        inv, _ = fs.add_invoice("00301234", "100.00", locator="inv.pdf")
        exp = fs.add_expense("100.00", locator="ledger.xlsx#明细!C2")
        fs.add_allocation(inv, exp, "100.00", locator="分配")
        fs.add_payee(name="甲公司", account="622200001", branch="X支行", interbank="102",
                     amount="100.00", locator="结算单#L1")
        fs.add_payee(name="乙公司", account="622200001", branch="X支行", interbank="102",
                     amount="100.00", locator="银行回单#L1")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("payee_identity", report.block_names())
        joined = json.dumps(check_by_name(report, "payee_identity").details, ensure_ascii=False)
        self.assertIn("同账号不同户名", joined)

    def test_factset_payload_roundtrip(self):
        fs, _ = travel_factset(self.prepared_task_root()[0])
        restored = FactSet.from_payload(fs.to_payload())
        self.assertEqual(len(restored), len(fs))
        self.assertEqual([f.fact_id for f in restored], [f.fact_id for f in fs])
        self.assertEqual(restored.get("F-0001").value, fs.get("F-0001").value)


# ------------------------------------------------------------ 生成器 e2e（travel）

class GeneratorE2ETests(W05TestCase):
    def test_travel_end_to_end_validated_plan(self):
        root, manifest_path, extraction, snapshot = self.prepared_task_root()
        fs, ids = travel_factset(root)
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot)
        generated = generate_fill_plan(fs, blueprint, base_dir=root)
        plan = generated["plan"]
        self.assertEqual(validate_plan(plan, verify_sources=True, base_dir=root), [])
        # 关键工件哈希绑定
        bindings = generated["fact_bindings"]
        self.assertEqual(bindings["/tables/details/0/fields/cost"]["fact_id"], ids["expense"])
        self.assertTrue(bindings["/tables/details/0/fields/cost"]["artifact_sha256"])
        self.assertEqual(plan["materials"]["image_documents"][0]["records"][0]["allocations"],
                         [{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "128.70"}])
        # 写盘过 load_plan 正式入口回读
        path = root / "fill_plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(load_plan(path, "测试操作人")["header"]["totalCost"], "128.70")
        # 全链工件哈希在案
        for artifact in (manifest_path, extraction, snapshot):
            self.assertTrue(Path(artifact).is_file())

    def test_invoice_binding_hash_crosscheck(self):
        """票据事实必须绑定 reviewed 提取的原件哈希（同 xlsx 对账链）。"""
        root, _, extraction, snapshot = self.prepared_task_root()
        fs, ids = travel_factset(root)
        payload = json.loads(Path(extraction).read_text(encoding="utf-8"))
        fs.get(ids["invoice"]).input_hashes.clear()   # 破坏原件哈希绑定
        fs.get(ids["invoice"]).input_hashes["extraction:x"] = "0" * 64
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot)
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("原件哈希", str(caught.exception))


# ------------------------------------------------------------ 生成器前置门与反例

class GeneratorGateTests(W05TestCase):
    def complete(self):
        root, manifest_path, extraction, snapshot = self.prepared_task_root()
        fs, ids = travel_factset(root)
        return root, fs, ids, travel_blueprint(root, fs, ids, extraction, snapshot)

    def test_reconcile_blocked_refuses(self):
        root, fs, ids, blueprint = self.complete()
        fs.add_expense("999.00", locator="originals/travel_ledger.xlsx#明细!B9")  # 未覆盖费用行
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("对账未通过", str(caught.exception))

    def test_binding_drift_refuses(self):
        root, fs, ids, blueprint = self.complete()
        blueprint["current_bindings"] = {"ledger": "0" * 64}
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("漂移", str(caught.exception))

    def test_artifact_drift_refuses(self):
        root, fs, ids, blueprint = self.complete()
        target = root / "originals" / "travel_ledger.xlsx"
        target.write_bytes(target.read_bytes() + b"\0")   # 工件被改，哈希与事实绑定不符
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("哈希与绑定不符", str(caught.exception))

    def test_value_fact_mismatch_refuses(self):
        root, fs, ids, blueprint = self.complete()
        blueprint["tables"]["details"][0]["fields"]["cost"]["value"] = "64.00"  # ≠事实 128.70
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("事实金额不一致", str(caught.exception))

    def test_validation_failure_is_generator_error(self):
        root, fs, ids, blueprint = self.complete()
        blueprint["tables"]["details"][0]["fields"]["digest"]["value"] = "票面没有的摘要"
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertTrue(caught.exception.issues)

    def test_unsourced_value_refuses(self):
        root, fs, ids, blueprint = self.complete()
        observed = fs.add("scope", source="system_observation",
                          value={"payType": "对公转账"},
                          locator="oa-顶栏#观察")   # 无登记观察工件 → 拒绝（W06+ 语义）
        blueprint["header"]["payType"]["fact_id"] = observed
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        # 文件不存在/覆盖定位不一致/不在派生根均拒绝；system_observation 必须给可哈希观察证明
        message = str(caught.exception)
        self.assertTrue(any(key in message for key in
                            ("事实工件不存在", "观察工件", "覆盖定位与事实工件不一致")), message)

    def test_money_fact_without_amount_key_refuses(self):
        """R4-P2b：金额字段绑到无 amount 键的事实时显式失败，不得自比恒真。"""
        root, fs, ids, blueprint = self.complete()
        text_fact = fs.add("scope", source="user_instruction",
                           value={"text": "不是金额的事实"},
                           locator="originals/user_instructions.json#/description")
        blueprint["tables"]["details"][0]["fields"]["cost"]["fact_id"] = text_fact
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("缺 amount 键", str(caught.exception))

    def test_unhashed_bound_fact_refuses(self):
        """R4-P2c：被绑定 material_extraction 事实清空 input_hashes → 生成器拒绝。"""
        root, fs, ids, blueprint = self.complete()
        fs.get(ids["expense"]).input_hashes.clear()
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("缺版本绑定", str(caught.exception))

    def test_unhashed_template_fact_refuses(self):
        """R4-P2c：模板事实无快照哈希绑定同样拒绝（不自动补绑定）。"""
        root, fs, ids, blueprint = self.complete()
        fs.get(ids["rendered"]).input_hashes.clear()
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("缺版本绑定", str(caught.exception))


# ------------------------------------------------------------ express 免票+空表场景

class ExpressNoInvoiceTests(W05TestCase):
    def test_express_no_invoice_and_empty_tables(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        originals = root / "originals"
        originals.mkdir()
        shutil.copy(self.w05 / "travel_ledger.xlsx", originals / "travel_ledger.xlsx")
        shutil.copy(self.w05 / "user_instructions.json", originals / "user_instructions.json")
        manifest_path = prepare_dual_materials(originals, root / "work")
        snapshot = root / "template_snapshot.json"
        snapshot.write_text(json.dumps({
            "biz_number": "000999999", "captured_at": "2026-10-24T10:00:00+08:00",
            "document_type": "express", "uuid": "12345678123456781234567812345678",
            "header": {"submitType": "快递费"},
            "rendered_options": {"bizOrign": "测试流程", "payType": "转账",
                                 "currencyType": "人民币", "submitType": "快递费"}},
            ensure_ascii=False), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ledger_sha = next(item["sha256"] for item in manifest["files"]
                          if item["path"].endswith("travel_ledger.xlsx"))
        fs = FactSet(bindings={"ledger": ledger_sha})
        identity = fs.add("business_identity", source="user_instruction",
                          value={"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
                          locator="originals/user_instructions.json#/applicant/name")
        expense = fs.add_expense("128.70", locator="originals/travel_ledger.xlsx#明细!B2",
                                 input_hashes={"ledger": ledger_sha}, value_extra={"digest": "住宿费测试"})
        fs.add_no_invoice_basis(expense, reason="离线合成数据免票理由：测试费用明确无需发票（仅机制验证）",
                                source="user_instruction",
                                locator="originals/user_instructions.json#/no_invoice_rule")
        payee = fs.add_payee(name="测试收款人", account="0000000001", branch="测试银行",
                             interbank="001234", amount="128.70",
                             locator="originals/travel_ledger.xlsx#收款!A2",
                             input_hashes={"ledger": ledger_sha})
        budget = fs.add("budget", source="user_instruction", value={"year": "2026"},
                        locator="originals/user_instructions.json#/budgetYears")
        description = fs.add("scope", source="user_instruction", value={"text": "测试材料说明"},
                             locator="originals/user_instructions.json#/description")
        relation_rule = fs.add("scope", source="user_instruction",
                               value={"text": "快递任务无关联单据"},
                               locator="originals/user_instructions.json#/relation_rule")
        costs_rule = fs.add("scope", source="user_instruction",
                            value={"text": "快递任务按明细行报销，无费用区间明细"},
                            locator="originals/user_instructions.json#/costs_rule")
        total = fs.add("total", source="deterministic_computation", derivation="明细合计",
                       value={"amount": "128.70"}, locator="derived:total#sum")
        rendered = fs.add("scope", source="template",
                          value={"bizOrign": "测试流程", "payType": "转账",
                                 "currencyType": "人民币", "submitType": "快递费"},
                          locator="template_snapshot.json#/rendered_options/bizOrign",
                          input_hashes={"template": file_hash(snapshot)})
        entry = lambda value, fact_id, locator=None: ({"value": value, "fact_id": fact_id, "locator": locator}
                                                      if locator else {"value": value, "fact_id": fact_id})
        ledger = "originals/travel_ledger.xlsx"
        blueprint = {
            "document_type": "express", "task_id": "synthetic-w05-express", "operator": "测试操作人",
            "applicant": {key: entry(value, identity, "originals/user_instructions.json#/applicant/" + key)
                          for key, value in fs.get(identity).value.items()},
            "template": {"biz_number": "000999999", "captured_at": "2026-10-24T10:00:00+08:00",
                         "sha256": file_hash(snapshot), "snapshot_path": str(snapshot)},
            "materials": {"manifest_path": str(manifest_path)},
            "header": {
                "corpCode": entry("测试公司", identity, "originals/user_instructions.json#/applicant/company"),
                "bizOrign": entry("测试流程", rendered, "template_snapshot.json#/rendered_options/bizOrign"),
                "budgetYears": entry("2026", budget, "originals/user_instructions.json#/budgetYears"),
                "payType": entry("转账", rendered, "template_snapshot.json#/rendered_options/payType"),
                "currencyType": entry("人民币", rendered, "template_snapshot.json#/rendered_options/currencyType"),
                "submitType": entry("快递费", rendered, "template_snapshot.json#/rendered_options/submitType"),
                "description": entry("测试材料说明", description, "originals/user_instructions.json#/description"),
            },
            "tables": {
                "relations": [],
                "details": [{"row_id": "d0", "fields": {
                    "reimItem": entry("差旅住宿", expense, ledger + "#明细!C2"),
                    "digest": entry("住宿费测试", expense, ledger + "#明细!A2"),
                    "budgetDeptName": entry("测试预算部", expense, ledger + "#明细!D2"),
                    "budgetNo": entry("000123", expense, ledger + "#明细!E2"),
                    "subjectName": entry("测试科目", expense, ledger + "#明细!F2"),
                    "budgetItemName": entry("测试预算项目", expense, ledger + "#明细!G2"),
                    "cost": entry("128.70", expense, ledger + "#明细!B2"),
                    "budgetOwner": entry("测试预算部", expense, ledger + "#明细!D2"),
                }}],
                "costs": [],
                "banks": [{"row_id": "b0", "fields": {
                    "payee": entry("测试收款人", payee, ledger + "#收款!A2"),
                    "account": entry("0000000001", payee, ledger + "#收款!B2"),
                    "bank": entry("测试银行", payee, ledger + "#收款!C2"),
                    "bankCode": entry("001234", payee, ledger + "#收款!D2"),
                    "cost": entry("128.70", payee, ledger + "#收款!E2"),
                }}],
            },
            "total": {"value": "128.70", "fact_id": total},
            "table_applicability": {
                "relations": entry("快递任务无关联单据", relation_rule,
                                   "originals/user_instructions.json#/relation_rule"),
                "costs": entry("快递任务按明细行报销，无费用区间明细", costs_rule,
                               "originals/user_instructions.json#/costs_rule"),
            },
            "amount_rules": {"costs": "not_applicable", "costs_reason": "本任务材料明确费用区间不适用",
                             "cost_amount_semantics": "line_total"},
            "not_applicable": ["费用区间"],
            "authorization": {"mode": "fill_only", "task_id": "synthetic-w05-express",
                              "statement": "仅填写本合成测试任务", "allow_submit": False},
        }
        generated = generate_fill_plan(fs, blueprint, base_dir=root)
        plan = generated["plan"]
        self.assertEqual(validate_plan(plan, verify_sources=True, base_dir=root), [])
        self.assertEqual(plan["materials"]["no_invoice_rows"][0]["plan_pointer"],
                         "/tables/details/0/fields/cost")
        self.assertEqual(plan["table_applicability"]["relations"]["reason"], "快递任务无关联单据")


# ------------------------------------------------------------ R7 identity 有源绑定

class R7IdentityTests(W05TestCase):
    """identity（申请人工号+制单人）与 system_observation 来源（2026-10-24 W06+）。"""

    def prepared_with_identity(self):
        root, manifest_path, extraction, snapshot = self.prepared_task_root()
        # 模板快照补申请人（appliedBy 工号）——travel_factset 会现场重算快照哈希
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["applicant"] = {"appliedName": "测试申请人", "appliedBy": "117000001"}
        snapshot.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        fs, ids = travel_factset(root)
        # 制单人观测工件登记进派生根（role=run_evidence → kind=agent_reviewed）
        from bpm.materials import register_derived
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_sha = manifest["files"][0]["sha256"]
        creator_ref = register_derived(manifest_path, "observed/creator.json",
                                       {"createdName": "测试操作人", "createdDeptName": "测试制单部门"},
                                       role="run_evidence", sources=[original_sha],
                                       generated_by="test-system-observation")
        creator_sha = creator_ref.split(":", 1)[1]
        f_employee = fs.add("business_identity", source="template",
                            value={"applicant_employee_id": "117000001"},
                            locator="template_snapshot.json#/applicant/appliedBy",
                            input_hashes={"template": file_hash(snapshot)})
        f_creator = fs.add("business_identity", source="system_observation",
                           value={"creator_name": "测试操作人", "creator_department": "测试制单部门"},
                           locator="work/observed/creator.json#/createdName",
                           input_hashes={"observation": creator_sha})
        ids.update(employee=f_employee, creator=f_creator)
        return root, extraction, snapshot, fs, ids

    def test_identity_binds_template_employee_id_and_observed_creator(self):
        root, extraction, snapshot, fs, ids = self.prepared_with_identity()
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot)
        blueprint["identity"] = {
            "applicant_employee_id": {"value": "117000001", "fact_id": ids["employee"],
                                      "locator": "/applicant/appliedBy"},
            "creator_name": {"value": "测试操作人", "fact_id": ids["creator"],
                             "locator": "/createdName"},
            "creator_department": {"value": "测试制单部门", "fact_id": ids["creator"],
                                   "locator": "/createdDeptName"},
        }
        plan = generate_fill_plan(fs, blueprint, base_dir=root)["plan"]
        self.assertEqual(plan["identity"]["applicant_employee_id"], "117000001")
        self.assertEqual(plan["sources"]["/identity/applicant_employee_id"]["kind"], "template")
        self.assertEqual(plan["sources"]["/identity/creator_name"]["kind"], "agent_reviewed")
        self.assertEqual(plan["sources"]["/identity/creator_department"]["locator"], "/createdDeptName")
        self.assertEqual(validate_plan(plan, verify_sources=True, base_dir=root), [])

    def test_system_observation_requires_derived_artifact(self):
        root, extraction, snapshot, fs, ids = self.prepared_with_identity()
        # 观测事实指向原件（未登记派生根）→ 拒绝，不给无观察证明的值放行
        manifest = json.loads((root / "work" / "manifest.json").read_text(encoding="utf-8"))
        ledger_sha = next(item["sha256"] for item in manifest["files"]
                          if item["path"].endswith("travel_ledger.xlsx"))
        rogue = fs.add("business_identity", source="system_observation",
                       value={"creator_name": "未留证观测"},
                       locator="originals/travel_ledger.xlsx#/收款!A2",
                       input_hashes={"ledger": ledger_sha})
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot)
        blueprint["identity"] = {
            "applicant_employee_id": {"value": "117000001", "fact_id": ids["employee"],
                                      "locator": "/applicant/appliedBy"},
            "creator_name": {"value": "未留证观测", "fact_id": rogue},
            "creator_department": {"value": "测试制单部门", "fact_id": ids["creator"],
                                   "locator": "/createdDeptName"},
        }
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("观察工件", str(caught.exception))

    def test_bound_identity_template_fact_needs_input_hashes(self):
        root, extraction, snapshot, fs, ids = self.prepared_with_identity()
        fs.get(ids["employee"]).input_hashes.clear()   # R4-P2c：被绑定 template 事实必须有版本哈希
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot)
        blueprint["identity"] = {
            "applicant_employee_id": {"value": "117000001", "fact_id": ids["employee"],
                                      "locator": "/applicant/appliedBy"},
            "creator_name": {"value": "测试操作人", "fact_id": ids["creator"],
                             "locator": "/createdName"},
            "creator_department": {"value": "测试制单部门", "fact_id": ids["creator"],
                                   "locator": "/createdDeptName"},
        }
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("input_hashes", str(caught.exception))


# ------------------------------------------------------------ D3 多 record 载荷布线

class MultiRecordExtractionTests(W05TestCase):
    """一文件多票（上游分件后多 record reviewed 载荷）：逐 record 匹配/漏票/重复消费。

    场景：一张 128.70 的费用行由两张票覆盖（100.00 + 28.70）——双布线消费同一载荷。
    """

    def prepared_multi(self, records):
        root, manifest_path, extraction, snapshot = self.prepared_task_root()
        fs, ids = travel_factset(root)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        invoice_sha = next(item["sha256"] for item in manifest["files"]
                           if item["path"].endswith("invoice.pdf"))
        payload = {"schema_version": "1.0", "reviewed": True,
                   "reviewed_by": "bpm-collect.multi-test",
                   "original_path": str((root / "originals" / "invoice.pdf").resolve()),
                   "original_sha256": invoice_sha,
                   "records": records, "review_evidence": {"note": "合成多票布线"},
                   "gaps": []}
        from bpm.materials import register_derived
        register_derived(manifest_path, "reviewed/multi.json", payload,
                         role="reviewed_extraction", sources=[invoice_sha],
                         generated_by="test-multi-record")
        multi = root / "work" / "reviewed" / "multi.json"
        # 票 1：改面值 100.00、分配 100.00；票 2：新建 00301999 面值 28.70 分配 28.70
        fs.get(ids["invoice"]).value["face_total"] = "100.00"
        for allocation in fs.by_kind("invoice_allocation"):
            if allocation.value["invoice_ref"] == ids["invoice"]:
                allocation.value["amount"] = "100.00"
        inv2, _ = fs.add_invoice("00301999", "28.70", locator="work/reviewed/multi.json#invoice-2",
                                 input_hashes={"extraction:" + invoice_sha: invoice_sha})
        fs.add_allocation(inv2, ids["expense"], "28.70", locator="分配#票2")
        ids["invoice2"] = inv2
        return root, fs, ids, snapshot, multi

    @staticmethod
    def record(record_id, number, amount):
        return {"record_id": record_id,
                "fields": {"invoice_number": {"value": number, "locator": "page:" + record_id[-1]},
                           "total_amount": {"value": amount, "locator": "page:" + record_id[-1]}}}

    def blueprint_with(self, root, fs, ids, snapshot, wirings):
        blueprint = travel_blueprint(root, fs, ids, None, snapshot)
        blueprint["invoice_extractions"] = wirings
        return blueprint

    def test_multi_record_all_consumed_builds_plan(self):
        records = [self.record("invoice-1", "00301234", "100.00"),
                   self.record("invoice-2", "00301999", "28.70")]
        root, fs, ids, snapshot, multi = self.prepared_multi(records)
        blueprint = self.blueprint_with(root, fs, ids, snapshot, [
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},
            {"invoice_fact_id": ids["invoice2"], "extraction_path": str(multi)},
        ])
        plan = generate_fill_plan(fs, blueprint, base_dir=root)["plan"]
        documents = plan["materials"]["image_documents"]
        # 一份原件一条文档：两布线并入同一文档，records 覆盖载荷全部 record
        self.assertEqual(len(documents), 1)
        by_record = {item["record_id"]: item for item in documents[0]["records"]}
        self.assertEqual(set(by_record), {"invoice-1", "invoice-2"})
        self.assertEqual(by_record["invoice-1"]["allocations"],
                         [{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "100.00"}])
        self.assertEqual(by_record["invoice-2"]["allocations"][0]["amount"], "28.70")
        self.assertEqual(validate_plan(plan, verify_sources=True, base_dir=root), [])

    def test_leftover_record_refuses(self):
        """载荷第 3 个 record 未被任何布线消费 → 漏票拒绝，不静默丢弃。"""
        records = [self.record("invoice-1", "00301234", "100.00"),
                   self.record("invoice-2", "00301999", "28.70"),
                   self.record("invoice-3", "00301777", "5.00")]
        root, fs, ids, snapshot, multi = self.prepared_multi(records)
        blueprint = self.blueprint_with(root, fs, ids, snapshot, [
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},
            {"invoice_fact_id": ids["invoice2"], "extraction_path": str(multi)},
        ])
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("漏票", str(caught.exception))
        self.assertIn("invoice-3", str(caught.exception))

    def test_duplicate_consumption_refuses(self):
        records = [self.record("invoice-1", "00301234", "100.00"),
                   self.record("invoice-2", "00301999", "28.70")]
        root, fs, ids, snapshot, multi = self.prepared_multi(records)
        blueprint = self.blueprint_with(root, fs, ids, snapshot, [
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},   # 同 record 二次消费
        ])
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("重复消费", str(caught.exception))

    def test_ambiguous_duplicate_number_refuses(self):
        records = [self.record("invoice-1", "00301234", "100.00"),
                   self.record("invoice-2", "00301234", "28.70")]   # 同票号双 record
        root, fs, ids, snapshot, multi = self.prepared_multi(records)
        blueprint = self.blueprint_with(root, fs, ids, snapshot, [
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},
        ])
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("无法唯一匹配", str(caught.exception))

    def test_missing_number_refuses(self):
        records = [self.record("invoice-1", "00301001", "100.00")]
        root, fs, ids, snapshot, multi = self.prepared_multi(records)
        blueprint = self.blueprint_with(root, fs, ids, snapshot, [
            {"invoice_fact_id": ids["invoice"], "extraction_path": str(multi)},
        ])
        with self.assertRaises(PlanGenerationError) as caught:
            generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertIn("不含该票据事实的票号", str(caught.exception))


# ------------------------------------------------------------ fill_once 阶段衔接

class StageLinkageTests(W05TestCase):
    def setUp(self):
        self.source_root, _, self.extraction, self.snapshot = self.prepared_task_root()

    def build_task(self, *, with_payload=True, sabotage=False):
        # payload/blueprint 与绝对路径工件（manifest derived_root、快照）同根生成：
        # 双根 manifest 的 derived_root 是绝对路径，目录搬迁会使提取工件脱离 derived root
        # （bpm_materials 显式拒绝），v1 契约内不做搬迁，故直接在本次测试的独立根内落件。
        task_root = self.source_root
        extraction, snapshot = self.extraction, self.snapshot
        fs, ids = travel_factset(task_root)
        blueprint = travel_blueprint(task_root, fs, ids, extraction, snapshot)
        if sabotage:
            blueprint["tables"]["details"][0]["fields"]["cost"]["value"] = "64.00"
        task = {"schema_version": "1.0", "task_id": "synthetic-w05", "document_type": "travel",
                "operator": "测试操作人", "template_biz_number": "000123456",
                "materials_dir": "originals", "statement": "本次测试材料",
                "template_snapshot_path": "template_snapshot.json",
                "authorization": {"mode": "fill_only", "task_id": "synthetic-w05",
                                  "statement": "仅填写本测试任务", "allow_submit": False}}
        if with_payload:
            payload = {"schema_version": "1.0", "factset": fs.to_payload(), "blueprint": blueprint}
            (task_root / "facts_payload.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            task["facts_payload"] = "facts_payload.json"
        task_path = task_root / "task.json"
        task_path.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
        return task_path

    def run_prepare(self, task_path, run_id):
        import bpm.fill_cli as fill_once
        base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        with mock.patch.object(fill_once, "ROOT", base), \
                mock.patch.object(fill_once, "RUNS", base / "runs"):
            return fill_once.prepare_task(task_path, "测试操作人", run_id), base / "runs" / run_id

    def test_payload_ready_advances_to_plan_ready(self):
        task_path = self.build_task()
        result, run = self.run_prepare(task_path, "w05ready")
        self.assertEqual(result["status"], "PLAN_READY")
        self.assertEqual(result["stage"], "PLAN_READY")
        plan_path = Path(result["fill_plan_path"])
        self.assertTrue(plan_path.is_file())
        self.assertTrue(plan_path.resolve().is_relative_to(run.resolve()))
        self.assertEqual(validate_plan(json.loads(plan_path.read_text(encoding="utf-8")),
                                       verify_sources=True,
                                       base_dir=task_path.parent), [])
        self.assertFalse(result["browser_launched"])
        self.assertEqual(result["gaps"], [])

    def test_blocked_reconciliation_reports_needs_input_with_structured_gaps(self):
        task_path = self.build_task()
        payload = json.loads((task_path.parent / "facts_payload.json").read_text(encoding="utf-8"))
        payload["factset"]["facts"].append({
            "fact_id": "F-9999", "kind": "expense", "source": "material_extraction",
            "value": {"amount": "77.00", "layer": "detail"},
            "locator": "originals/travel_ledger.xlsx#明细!B9",
            "derivation": None, "input_hashes": {}, "note": None,
            "created_at": "2026-10-24T12:00:00+00:00"})
        (task_path.parent / "facts_payload.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result, _ = self.run_prepare(task_path, "w05blocked")
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["stage"], "FACTS_BUILT")
        self.assertTrue(any(gap["code"] == "RECONCILIATION_BLOCKED" for gap in result["gaps"]))
        structured = result["structured_gaps"]
        self.assertTrue(structured)
        self.assertEqual(set(structured[0]),
                         {"file", "locator", "region", "candidates", "reason", "affected_rows"})

    def test_generator_failure_reports_needs_input(self):
        task_path = self.build_task(sabotage=True)
        result, _ = self.run_prepare(task_path, "w05sabotage")
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["stage"], "RECONCILED")
        self.assertTrue(any(gap["code"] == "GENERATOR_INVALID" for gap in result["gaps"]))

    def test_no_payload_keeps_legacy_needs_input(self):
        task_path = self.build_task(with_payload=False)
        result, run = self.run_prepare(task_path, "w05legacy")
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["stage"], "MATERIALS_READY")
        self.assertTrue(any(gap["path"] == "/fill_plan" for gap in result["gaps"]))
        self.assertFalse(result["browser_launched"])
        self.assertTrue((run / "events.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
