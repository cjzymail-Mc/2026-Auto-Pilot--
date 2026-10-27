"""W01 请求登记/模板核对/未知类别识别/复用矩阵 单测（全合成；R4-P2 三修同库联动）。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bpm.facts import FactSet
from bpm.materials import prepare_dual_materials, validate_dual_manifest
from bpm.plan import file_hash, plan_hash, validate_plan
from bpm.plan_generate import generate_fill_plan
from bpm.request import (build_reuse_matrix, entries_from_matrix, execution_ready,
                         identify_unknown, operator_from_session_record,
                         register_matrix, register_request, resolve_template,
                         validate_operator_evidence)
from bpm.types import TypeConfigError, resolve_type

from test_bpm_extraction import ensure_fixtures as ensure_w03_fixtures
from test_bpm_plan_generate import W05TestCase, ensure_w05_fixtures, travel_blueprint

FIXTURES = Path(__file__).resolve().parent / "fixtures"
W01 = FIXTURES / "w01"
STAMP = W01 / "w01-v1"

TRAVEL_NUMBER = "2000123456"
UNKNOWN_NUMBER = "3000999777"
TRAVEL_UUID = "a1b2c3d4e5f64778899aabbccddddeeff"[:32]
UNKNOWN_UUID = "b2c3d4e5f64778899aabbccdeeff00000"[:32]


def ensure_w01_fixtures():
    """幂等：合成 census corpus（travel 正例 + 未登记类别 doc），格式同真实 census 工件。"""
    if W01.is_dir() and not STAMP.is_file():
        shutil.rmtree(W01)
    if STAMP.is_file():
        return W01
    W01.mkdir(parents=True, exist_ok=True)
    main = {
        "bizNumber": TRAVEL_NUMBER, "id": TRAVEL_UUID, "submitType": "差旅费",
        "appliedName": "陈晶", "appliedDeptName": "运动表现研究部",
        "corpCode": "1003", "appliedBy": "116070053",
        "bizOrign": "测试流程", "payType": "转账", "currencyType": "人民币",
        "budgetYears": "2024", "totalCost": "888.80", "description": "旧模板说明",
        "bizStatus": "已提交", "createdName": "陈晶", "createdBy": "116070053",
    }
    def child(rows):
        return {"status": 200, "body": json.dumps(rows, ensure_ascii=False)}
    children = {
        "details": child([{"reimburseId": TRAVEL_UUID, "cost": "888.80", "digest": "旧模板住宿"}]),
        "costs": child([{"reimburseId": TRAVEL_UUID, "cost": "888.80",
                         "startDate": "2024-01-02", "endDate": "2024-01-03"}]),
        "banks": child([{"reimburseId": TRAVEL_UUID, "payee": "旧收款人", "account": "9999"}]),
        "relations": child([{"reimburseId": TRAVEL_UUID, "bizNo": "OLD-REL-1"}]),
        "products": child([]),
        "detailrels": child([]),
    }
    travel_doc = {"bizNumber": TRAVEL_NUMBER,
                  "fetch": {"status": 200, "body": json.dumps(main, ensure_ascii=False)},
                  "children": children}
    unknown_main = {"bizNumber": UNKNOWN_NUMBER, "id": UNKNOWN_UUID,
                    "submitType": "低值易耗品办公用品", "appliedName": "陈晶",
                    "bizOrign": "测试流程", "totalCost": "66.60"}
    unknown_doc = {"bizNumber": UNKNOWN_NUMBER,
                   "fetch": {"status": 200, "body": json.dumps(unknown_main, ensure_ascii=False)},
                   "children": {key: child([]) for key in children}}
    corpus = {"schema_hint": "captured census artifact (synthetic)", "ts": "2026-10-24",
              "docs": [travel_doc, unknown_doc]}
    (W01 / "census.json").write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    STAMP.write_text("synthetic fixtures only; regenerate by deleting this stamp", encoding="utf-8")
    return W01


GAP_KEYS = {"file", "locator", "region", "candidates", "reason", "affected_rows"}


class W01TestCase(W05TestCase):
    """复用 W05 合成任务根（发票+xlsx+user json+双根 manifest+提取）。"""

    @classmethod
    def setUpClass(cls):
        cls.w01 = ensure_w01_fixtures()
        super().setUpClass()

    def census(self):
        return self.w01 / "census.json"


# ------------------------------------------------------------ W01a 请求登记

class RequestRegistrationTests(W01TestCase):
    def prepared(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        originals = root / "originals"
        originals.mkdir()
        shutil.copy(self.w05 / "travel_ledger.xlsx", originals / "travel_ledger.xlsx")
        shutil.copy(self.w05 / "user_instructions.json", originals / "user_instructions.json")
        return root, prepare_dual_materials(originals, root / "work")

    def test_complete_request_registers_derived_artifact(self):
        root, manifest_path = self.prepared()
        result = register_request(
            {"template_biz_number": TRAVEL_NUMBER, "materials_dir": "originals",
             "statement": "本次差旅测试报销", "declared_category": "差旅费",
             "applicant": {"name": "测试申请人"}},
            manifest_path=manifest_path)
        self.assertEqual(result["status"], "REGISTERED")
        record = result["record"]
        self.assertEqual(record["source_semantics"], "user_instruction")
        self.assertEqual(record["template_biz_number"], TRAVEL_NUMBER)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(item for item in manifest["derived_files"]
                     if item["role"] == "user_request")
        self.assertTrue(entry["path"].endswith(".json"))
        self.assertEqual(entry["derived_id"], "sha256:" + entry["sha256"])
        self.assertEqual(validate_dual_manifest(manifest, base_dir=manifest_path.parent), [])

    def test_missing_essentials_needs_input_without_writing(self):
        root, manifest_path = self.prepared()
        before = file_hash(manifest_path)
        result = register_request({"statement": "只有说明"}, manifest_path=manifest_path)
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertTrue(result["gaps"])
        for gap in result["gaps"]:
            self.assertEqual(set(gap), GAP_KEYS)
        joined = json.dumps(result["gaps"], ensure_ascii=False)
        for keyword in ("模板单号", "材料目录"):
            self.assertIn(keyword, joined)
        self.assertEqual(file_hash(manifest_path), before)   # 缺要素不落盘

    def test_unknown_request_key_rejected(self):
        root, manifest_path = self.prepared()
        result = register_request(
            {"template_biz_number": TRAVEL_NUMBER, "materials_dir": "originals",
             "statement": "x", "hack": True},
            manifest_path=manifest_path)
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertTrue(any("未知字段" in gap["reason"] for gap in result["gaps"]))


# ------------------------------------------------------------ W01b 模板核对

class TemplateResolutionTests(W01TestCase):
    def test_resolve_travel_from_cache(self):
        resolved = resolve_template(self.census(), TRAVEL_NUMBER)
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["document_type"], "travel")
        snapshot = resolved["snapshot"]
        self.assertEqual(snapshot["uuid"], TRAVEL_UUID)
        self.assertEqual(snapshot["applicant"]["appliedName"], "陈晶")   # 历史人员在案=识别素材
        self.assertEqual(snapshot["source"]["kind"], "cached")
        self.assertEqual(snapshot["source"]["sha256"], file_hash(self.census()))

    def test_declared_conflict_concentrated_report(self):
        result = resolve_template(self.census(), TRAVEL_NUMBER, declared_category="快递费")
        self.assertEqual(result["status"], "CONFLICT")
        conflict = result["conflicts"][0]
        self.assertEqual(conflict["kind"], "category_mismatch")
        self.assertEqual(conflict["declared_type"], "express")
        self.assertEqual(conflict["template_type"], "travel")
        self.assertEqual(result["snapshot"]["document_type"], "travel")   # 不悄悄换类

    def test_declared_unregistered_category_conflicts(self):
        result = resolve_template(self.census(), TRAVEL_NUMBER, declared_category="其他费用")
        self.assertEqual(result["status"], "CONFLICT")
        self.assertEqual(result["conflicts"][0]["kind"], "declared_category_unregistered")

    def test_duplicate_number_refuses(self):
        corpus = json.loads(self.census().read_text(encoding="utf-8"))
        corpus["docs"].append(dict(corpus["docs"][0]))
        twin = self.w01.parent / "w01" / "census-dup.json"
        twin.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(twin.unlink)
        with self.assertRaises(ValueError):
            resolve_template(twin, TRAVEL_NUMBER)


# ------------------------------------------------------------ 未知类别只读识别

class UnknownCategoryTests(W01TestCase):
    def test_identify_unknown_reports_without_write(self):
        report = identify_unknown(self.census(), UNKNOWN_NUMBER)
        self.assertEqual(report["status"], "UNSUPPORTED")
        self.assertEqual(report["observed_category"], "低值易耗品办公用品")
        # Round-9（ctr-15712bcb）：封闭注册扩展 02/04（offline_modeled_live_pending）。
        # census 夹具类别“低值易耗品办公用品”≠注册标签“低值易耗品、办公用品采购”，仍判 UNSUPPORTED。
        self.assertEqual(set(report["registry"]),
                         {"travel", "express", "rd_materials", "office_supplies", "welfare_labor"})
        self.assertFalse(report["writable"])
        self.assertIn("登记开发子任务", report["suggested_subtask"])
        self.assertEqual(report["evidence"]["corpus"]["sha256"], file_hash(self.census()))
        self.assertTrue(report["unsupported_parts"])

    def test_resolve_delegates_unknown_to_identification(self):
        result = resolve_template(self.census(), UNKNOWN_NUMBER)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertFalse(result["report"]["writable"])

    def test_unknown_write_paths_refused(self):
        # 类别名不是已注册 document_type：resolve_type 拒绝；矩阵要求已解析快照同样拒绝。
        with self.assertRaises(TypeConfigError):
            resolve_type("低值易耗品办公用品")
        with self.assertRaises(ValueError):
            build_reuse_matrix({"document_type": None}, FactSet(), [])
        with self.assertRaises(ValueError):
            build_reuse_matrix({}, FactSet(), [])

    def test_known_category_via_identify_reports_known(self):
        report = identify_unknown(self.census(), TRAVEL_NUMBER)
        self.assertEqual(report["status"], "KNOWN")
        self.assertEqual(report["document_type"], "travel")


# ------------------------------------------------------------ W01c 复用矩阵

def w01_factset(root, snapshot_sha):
    """贯通用事实集：值键与计划字段同名（矩阵取值 fact.value[field]）。"""
    manifest = json.loads((root / "work" / "manifest.json").read_text(encoding="utf-8"))
    originals = {Path(item["path"]).name: item["sha256"] for item in manifest["files"]}
    ledger_sha = originals["travel_ledger.xlsx"]
    fs = FactSet(bindings={"ledger": ledger_sha, "template": snapshot_sha})
    identity = fs.add("business_identity", source="user_instruction",
                      value={"name": "测试申请人", "company": "测试公司", "department": "测试部门"},
                      locator="originals/user_instructions.json#/applicant/name")
    budget = fs.add("budget", source="user_instruction", value={"budgetYears": "2026"},
                    locator="originals/user_instructions.json#/budgetYears")
    description = fs.add("scope", source="user_instruction", value={"text": "测试材料说明"},
                         locator="originals/user_instructions.json#/description")
    invoice_sha = originals["invoice.pdf"]
    invoice, _ = fs.add_invoice("00301234", "128.70", locator="work/reviewed/invoice#page:1",
                                input_hashes={"extraction:" + invoice_sha: invoice_sha})
    expense = fs.add_expense("128.70", locator="originals/travel_ledger.xlsx#明细!B2",
                             input_hashes={"ledger": ledger_sha}, category="住宿",
                             value_extra={"digest": "住宿费测试"})
    fs.add_allocation(invoice, expense, "128.70", locator="分配#票1")
    payee = fs.add_payee(name="测试收款人", account="0000000001", branch="测试银行",
                         interbank="001234", amount="128.70",
                         locator="originals/travel_ledger.xlsx#收款!A2",
                         input_hashes={"ledger": ledger_sha})
    total = fs.add("total", source="deterministic_computation", derivation="明细合计=票据分配",
                   value={"amount": "128.70"}, locator="derived:total#sum")
    rendered = fs.add("scope", source="template",
                      value={"bizOrign": "测试流程", "payType": "转账",
                             "currencyType": "人民币", "submitType": "差旅费"},
                      locator="template_snapshot.json#/header/bizOrign",
                      input_hashes={"template": snapshot_sha})
    return fs, {"identity": identity, "budget": budget, "description": description,
                "invoice": invoice, "expense": expense, "payee": payee,
                "total": total, "rendered": rendered}


def w01_decisions(ids):
    return [
        {"group": "form_identity", "field": "form_structure", "decision": "identify",
         "template_value": "差旅四表+关联/收款结构（识别用，不抄值）"},
        {"group": "stable_context", "field": "bizOrign", "decision": "adopt",
         "fact_id": ids["rendered"], "basis": "模板渲染流程与本次一致（快照哈希绑定）",
         "locator": "template_snapshot.json#/header/bizOrign"},
        {"group": "stable_context", "field": "payType", "decision": "adopt",
         "fact_id": ids["rendered"], "basis": "渲染选项，快照哈希绑定",
         "locator": "template_snapshot.json#/header/payType"},
        {"group": "stable_context", "field": "currencyType", "decision": "adopt",
         "fact_id": ids["rendered"], "basis": "渲染选项，快照哈希绑定",
         "locator": "template_snapshot.json#/header/currencyType"},
        {"group": "stable_context", "field": "submitType", "decision": "adopt",
         "fact_id": ids["rendered"], "basis": "类别=差旅费，与请求一致",
         "locator": "template_snapshot.json#/header/submitType"},
        {"group": "stable_context", "field": "corpCode", "decision": "replace",
         "fact_id": ids["identity"], "fact_field": "company",
         "locator": "originals/user_instructions.json#/applicant/company"},
        {"group": "stable_context", "field": "budgetYears", "decision": "replace",
         "fact_id": ids["budget"]},
        {"group": "current_person", "field": "name", "decision": "replace",
         "fact_id": ids["identity"],
         "locator": "originals/user_instructions.json#/applicant/name"},
        {"group": "current_person", "field": "company", "decision": "replace",
         "fact_id": ids["identity"],
         "locator": "originals/user_instructions.json#/applicant/company"},
        {"group": "current_person", "field": "department", "decision": "replace",
         "fact_id": ids["identity"],
         "locator": "originals/user_instructions.json#/applicant/department"},
        {"group": "current_business", "field": "description", "decision": "replace",
         "fact_id": ids["description"]},
        {"group": "current_business", "field": "cost", "decision": "replace",
         "fact_id": ids["expense"]},
        {"group": "current_business", "field": "invoice_number", "decision": "replace",
         "fact_id": ids["invoice"]},
        {"group": "proven_references", "field": "relations", "decision": "not_applicable",
         "reason": "本次材料无关联单据（user_instructions relation_rule）"},
        {"group": "empty_tables", "field": "products", "decision": "not_applicable",
         "reason": "差旅无物品档案表"},
    ]


class ReuseMatrixTests(W01TestCase):
    def scenario(self):
        resolved = resolve_template(self.census(), TRAVEL_NUMBER)
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        originals = root / "originals"
        originals.mkdir()
        shutil.copy(self.w05 / "travel_ledger.xlsx", originals / "travel_ledger.xlsx")
        shutil.copy(self.w03 / "invoice.pdf", originals / "invoice.pdf")
        manifest_path = prepare_dual_materials(originals, root / "work")
        snapshot_path = root / "template_snapshot.json"
        snapshot_path.write_text(json.dumps(resolved["snapshot"], ensure_ascii=False),
                                 encoding="utf-8")
        fs, ids = w01_factset(root, file_hash(snapshot_path))
        return root, resolved["snapshot"], fs, ids, manifest_path

    def test_full_matrix_builds_and_registers(self):
        root, snapshot, fs, ids, manifest_path = self.scenario()
        matrix = build_reuse_matrix(snapshot, fs, w01_decisions(ids), user_policy={})
        self.assertEqual(matrix["document_type"], "travel")
        self.assertEqual({row["group"] for row in matrix["rows"]}, set(
            ["form_identity", "stable_context", "current_person",
             "current_business", "proven_references", "empty_tables"]))
        artifact = register_matrix(matrix, manifest_path=manifest_path)
        self.assertEqual(artifact["role"], "decision_matrix")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertTrue(any(item["role"] == "decision_matrix" for item in manifest["derived_files"]))
        self.assertEqual(validate_dual_manifest(manifest, base_dir=manifest_path.parent), [])

    def test_template_old_value_pretending_current_rejected(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        decisions = w01_decisions(ids)
        decisions.append({"group": "current_business", "field": "totalCost",
                          "decision": "adopt", "fact_id": ids["rendered"]})   # 模板旧金额冒充
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)
        self.assertIn("冒充本次值", str(caught.exception))

    def test_template_old_date_pretending_current_rejected(self):
        # R5-P2 反例实例化：模板旧日期冒充本次日期（current_business/bizDate）
        root, snapshot, fs, ids, _manifest = self.scenario()
        old_date = fs.add("scope", source="template", value={"bizDate": "2024-03-08"},
                          locator="template_snapshot.json#/header/bizDate",
                          input_hashes={"template": fs.bindings["template"]})
        decisions = w01_decisions(ids)
        decisions.append({"group": "current_business", "field": "bizDate",
                          "decision": "adopt", "fact_id": old_date})
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)
        self.assertIn("冒充本次值", str(caught.exception))

    def test_template_old_payee_pretending_current_rejected(self):
        # R5-P2 反例实例化：模板旧收款对象冒充本次收款（proven_references/payeeName）
        root, snapshot, fs, ids, _manifest = self.scenario()
        old_payee = fs.add("payee_group", source="template",
                           value={"payeeName": "模板历史收款人"},
                           locator="template_snapshot.json#/banks/0/payeeName",
                           input_hashes={"template": fs.bindings["template"]})
        decisions = w01_decisions(ids)
        decisions.append({"group": "proven_references", "field": "payeeName",
                          "decision": "adopt", "fact_id": old_payee})
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)
        self.assertIn("冒充本次值", str(caught.exception))

    def test_duplicate_group_field_row_rejected(self):
        # R5-P2：同一 (group,field) 多行 → 后行覆盖前行的取值歧义在构造期拒绝
        root, snapshot, fs, ids, _manifest = self.scenario()
        decisions = w01_decisions(ids)
        decisions.append({"group": "current_person", "field": "name",
                          "decision": "identify"})   # 与既有 (current_person,name) 重复
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)
        self.assertIn("重复 (group,field)", str(caught.exception))

    def test_replace_from_template_rejected(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        decisions = w01_decisions(ids)
        decisions.append({"group": "current_business", "field": "digest",
                          "decision": "replace", "fact_id": ids["rendered"]})
        with self.assertRaises(ValueError):
            build_reuse_matrix(snapshot, fs, decisions)

    def test_old_budget_reuse_requires_confirmation(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        budget = fs.add("budget", source="template", value={"budgetYears": "2024"},
                        locator="template_snapshot.json#/header/budgetYears",
                        input_hashes={"template": fs.bindings["template"]})
        decisions = [
            {"group": "form_identity", "field": "f", "decision": "identify"},
            {"group": "stable_context", "field": "budgetYears", "decision": "adopt",
             "fact_id": budget, "basis": "沿用模板年度"},
            {"group": "current_person", "field": "name", "decision": "replace",
             "fact_id": ids["identity"]},
            {"group": "current_business", "field": "cost", "decision": "replace",
             "fact_id": ids["expense"]},
            {"group": "proven_references", "field": "relations", "decision": "not_applicable",
             "reason": "无"},
            {"group": "empty_tables", "field": "products", "decision": "not_applicable",
             "reason": "无"},
        ]
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)   # 无确认 → 旧年度沿用拒绝
        self.assertIn("旧年度预算", str(caught.exception))
        matrix = build_reuse_matrix(snapshot, fs, decisions,
                                    user_policy={"budget": {"reuse": "confirmed"}})
        self.assertEqual(matrix["rows"][1]["decision"], "adopt")

    def test_template_applicant_override_requires_policy(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        applicant = fs.add("business_identity", source="template",
                           value={"name": "陈晶", "company": "1003", "department": "运动表现研究部"},
                           locator="template_snapshot.json#/applicant/appliedName",
                           input_hashes={"template": fs.bindings["template"]})
        decisions = [
            {"group": "form_identity", "field": "f", "decision": "identify"},
            {"group": "stable_context", "field": "bizOrign", "decision": "adopt",
             "fact_id": ids["rendered"], "basis": "渲染选项"},
            {"group": "current_person", "field": "name", "decision": "adopt",
             "fact_id": applicant},
            {"group": "current_business", "field": "cost", "decision": "replace",
             "fact_id": ids["expense"]},
            {"group": "proven_references", "field": "relations", "decision": "not_applicable",
             "reason": "无"},
            {"group": "empty_tables", "field": "products", "decision": "not_applicable",
             "reason": "无"},
        ]
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)   # 模板历史申请人默认拒绝
        self.assertIn("模板历史申请人", str(caught.exception))
        matrix = build_reuse_matrix(snapshot, fs, decisions,
                                    user_policy={"identity_reuse": "confirmed"})
        self.assertEqual(matrix["rows"][2]["decision"], "adopt")

    def test_incomplete_groups_or_empty_reason_rejected(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        decisions = [row for row in w01_decisions(ids) if row["group"] != "empty_tables"]
        with self.assertRaises(ValueError) as caught:
            build_reuse_matrix(snapshot, fs, decisions)
        self.assertIn("未覆盖全部字段组", str(caught.exception))
        bad = [dict(row) for row in w01_decisions(ids)]
        bad[-1] = {"group": "empty_tables", "field": "products", "decision": "not_applicable"}
        with self.assertRaises(ValueError):
            build_reuse_matrix(snapshot, fs, bad)

    def test_form_identity_cannot_adopt_and_adopt_needs_fact(self):
        root, snapshot, fs, ids, _manifest = self.scenario()
        decisions = [dict(row) for row in w01_decisions(ids)]
        decisions[0] = {"group": "form_identity", "field": "form_structure",
                        "decision": "adopt", "fact_id": ids["rendered"]}
        with self.assertRaises(ValueError):
            build_reuse_matrix(snapshot, fs, decisions)
        decisions2 = [dict(row) for row in w01_decisions(ids)]
        decisions2[1] = {"group": "stable_context", "field": "bizOrign", "decision": "adopt"}
        with self.assertRaises(ValueError):
            build_reuse_matrix(snapshot, fs, decisions2)


# ------------------------------------------------------------ 矩阵→生成器贯通

class GeneratorIntegrationTests(W01TestCase):
    def test_matrix_blueprint_to_validated_plan(self):
        root, manifest_path, extraction, _ = self.prepared_task_root()
        # W01 路径产出的真实形状快照覆盖任务根快照，事实绑定其哈希
        resolved = resolve_template(self.census(), TRAVEL_NUMBER, declared_category="差旅费")
        self.assertEqual(resolved["status"], "RESOLVED")
        snapshot_path = root / "template_snapshot.json"
        snapshot_path.write_text(json.dumps(resolved["snapshot"], ensure_ascii=False),
                                 encoding="utf-8")
        fs, ids = w01_factset(root, file_hash(snapshot_path))
        matrix = build_reuse_matrix(resolved["snapshot"], fs, w01_decisions(ids), user_policy={})
        fields = ("name", "company", "department", "corpCode", "bizOrign", "budgetYears",
                  "payType", "currencyType", "submitType", "description")
        entries = entries_from_matrix(matrix, fs, fields)
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot_path)
        blueprint["template"]["biz_number"] = resolved["snapshot"]["biz_number"]
        blueprint["template"]["captured_at"] = resolved["snapshot"]["captured_at"]
        blueprint["applicant"] = {key: dict(entries[key]) for key in ("name", "company", "department")}
        blueprint["header"] = {key: dict(entries[key]) for key in
                               ("corpCode", "bizOrign", "budgetYears", "payType",
                                "currencyType", "submitType", "description")}
        generated = generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertEqual(validate_plan(generated["plan"], verify_sources=True, base_dir=root), [])
        bindings = generated["fact_bindings"]
        self.assertEqual(bindings["/header/payType"]["fact_id"], ids["rendered"])
        self.assertEqual(bindings["/header/budgetYears"]["fact_id"], ids["budget"])
        self.assertEqual(bindings["/applicant/name"]["fact_id"], ids["identity"])


class ExecutionReadinessTests(W01TestCase):
    """W06 D10 执行串联两态：齐备→执行就绪输出；缺身份→准确缺口（真实 CLI 子进程，全离线）。"""

    def plan_file(self):
        """请求→模板决策→矩阵→计划 全链产物落盘，返回 (plan_path, plan)。"""
        root, manifest_path, extraction, _ = self.prepared_task_root()
        resolved = resolve_template(self.census(), TRAVEL_NUMBER, declared_category="差旅费")
        snapshot_path = root / "template_snapshot.json"
        snapshot_path.write_text(json.dumps(resolved["snapshot"], ensure_ascii=False),
                                 encoding="utf-8")
        fs, ids = w01_factset(root, file_hash(snapshot_path))
        matrix = build_reuse_matrix(resolved["snapshot"], fs, w01_decisions(ids), user_policy={})
        fields = ("name", "company", "department", "corpCode", "bizOrign", "budgetYears",
                  "payType", "currencyType", "submitType", "description")
        entries = entries_from_matrix(matrix, fs, fields)
        blueprint = travel_blueprint(root, fs, ids, extraction, snapshot_path)
        blueprint["template"]["biz_number"] = resolved["snapshot"]["biz_number"]
        blueprint["template"]["captured_at"] = resolved["snapshot"]["captured_at"]
        blueprint["applicant"] = {key: dict(entries[key]) for key in ("name", "company", "department")}
        blueprint["header"] = {key: dict(entries[key]) for key in
                               ("corpCode", "bizOrign", "budgetYears", "payType",
                                "currencyType", "submitType", "description")}
        generated = generate_fill_plan(fs, blueprint, base_dir=root)
        self.assertEqual(validate_plan(generated["plan"], verify_sources=True, base_dir=root), [])
        plan_path = root / "fill_plan.json"
        plan_path.write_text(json.dumps(generated["plan"], ensure_ascii=False), encoding="utf-8")
        return plan_path, generated["plan"]

    def test_ready_state_outputs_execution_ready(self):
        plan_path, plan = self.plan_file()
        result = execution_ready(plan_path, {"name": plan["operator"], "source": "user_policy",
                                             "basis": "合成请求登记 user_policy.operator"})
        self.assertEqual(result["status"], "EXECUTION_READY")
        self.assertEqual(result["validate_only"]["status"], "PLAN_VALIDATED")
        self.assertFalse(result["browser_launched"])
        self.assertFalse(result["validate_only"]["browser_launched"])
        self.assertEqual(result["plan"]["path"], str(Path(plan_path).resolve()))
        # P2 双字段：plan_hash 为准；sha256 为兼容旧名，值同为 plan_hash(plan)（非文件字节哈希）
        self.assertEqual(result["plan"]["plan_hash"], plan_hash(plan))
        self.assertEqual(result["plan"]["sha256"], result["plan"]["plan_hash"])
        self.assertNotEqual(result["plan"]["plan_hash"], file_hash(Path(plan_path)))
        self.assertEqual(result["operator"]["name"], plan["operator"])
        self.assertEqual(result["operator"]["source"], "user_policy")
        cmd = result["suggested_command"]
        self.assertIn("--keep-open-minutes 45", cmd)
        self.assertIn('fill_once.py --fill-plan "{0}"'.format(Path(plan_path).resolve()), cmd)
        self.assertIn('--expect-name "{0}"'.format(plan["operator"]), cmd)
        self.assertNotIn("--validate-only", cmd)   # 建议的是执行命令，不是校验命令

    def test_missing_identity_needs_input_without_guessing(self):
        plan_path, _plan = self.plan_file()
        result = execution_ready(plan_path, None)
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertTrue(result["gaps"])
        self.assertIn("操作人", result["gaps"][0]["reason"])
        self.assertNotIn("operator", result)      # 不猜姓名：无 operator 键
        self.assertNotIn("suggested_command", result)
        self.assertFalse(result["browser_launched"])

    def test_template_history_source_refused(self):
        plan_path, _plan = self.plan_file()
        with self.assertRaises(ValueError) as caught:
            execution_ready(plan_path, {"name": "陈晶", "source": "template_history"})
        self.assertIn("模板历史人员", str(caught.exception))
        with self.assertRaises(ValueError):
            validate_operator_evidence({"name": "任意", "source": "template"})

    def test_invalid_plan_needs_input_with_issues(self):
        plan_path, plan = self.plan_file()
        tampered = dict(plan)
        tampered["operator"] = "另一个人"
        plan_path.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
        result = execution_ready(plan_path, {"name": plan["operator"],
                                             "source": "system_observation",
                                             "basis": "合成会话探查"})
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertTrue(result["issues"])
        self.assertFalse(result["browser_launched"])

    def test_missing_plan_file_needs_input(self):
        result = execution_ready(Path(tempfile.gettempdir()) / "no-such-plan.json",
                                 {"name": "测试操作人", "source": "user_policy"})
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertIn("不存在", result["gaps"][0]["reason"])

    def test_operator_from_session_record(self):
        record = {"auth_status": "authenticated",
                  "principal": {"name": "陈晶", "user_id": "116070053"},
                  "identity_verification_level": "header_and_subject"}
        path = Path(tempfile.mkdtemp()) / "session_record.json"
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        evidence = operator_from_session_record(path)
        self.assertEqual(evidence["name"], "陈晶")
        self.assertEqual(evidence["source"], "system_observation")
        self.assertIn("authenticated", evidence["basis"])
        self.assertIn("header_and_subject", evidence["basis"])
        record["auth_status"] = "expired"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.assertIsNone(operator_from_session_record(path))
        record["auth_status"] = "authenticated"
        record["principal"]["name"] = None
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        self.assertIsNone(operator_from_session_record(path))


if __name__ == "__main__":
    unittest.main()
