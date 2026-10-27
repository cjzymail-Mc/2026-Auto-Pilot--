"""W04 事实层 + 对账单测（全部合成材料；反例逐条对应任务书清单）。"""
import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import bpm.facts as bpm_facts
from bpm.facts import (FactSet, ReconciliationReport, check_version_drift,
                       reconcile, scan_task_registry)

from bpm.extraction import classify_materials, extract_workbook, run_pdf_extraction
from bpm.materials import prepare_dual_materials
from test_bpm_extraction import ensure_fixtures as ensure_w03_fixtures

FIXTURES = Path(__file__).resolve().parent / "fixtures"
W04 = FIXTURES / "w04"
STAMP = W04 / "w04-v2"


def ensure_w04_fixtures():
    """幂等：scan-2=同内容副本（duplicate_copy 组）；scan-3=同号不同票面；registry 模拟。"""
    if W04.is_dir() and not STAMP.is_file():
        shutil.rmtree(W04)   # 旧 stamp 整体重建，避免半新半旧
    if STAMP.is_file():
        return W04
    W04.mkdir(parents=True, exist_ok=True)
    w03 = ensure_w03_fixtures()
    shutil.copy(w03 / "invoice.pdf", W04 / "scan-2.pdf")
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "发票号码：00301234", fontname="china-s")
    page.insert_text((72, 100), "（小写）￥999.99", fontname="china-s")
    page.insert_text((72, 130), "价税合计 999.99", fontname="china-s")
    doc.save(str(W04 / "scan-3.pdf"))
    doc.close()
    registry = W04 / "task-registry-sim"
    registry.mkdir(exist_ok=True)
    (registry / "TSK-9001.form.json").write_text(json.dumps({
        "task_id": "TSK-9001", "state": "FORM_INTENT",
        "authorized_revision02": {"event": "user authorized",
                                  "numbers": ["00301234"], "save_allowed": False}
    }, ensure_ascii=False), encoding="utf-8")
    STAMP.write_text("synthetic fixtures only; regenerate by deleting this stamp", encoding="utf-8")
    return W04


def check_by_name(report, name):
    return next(c for c in report.checks if c.name == name)


class W04TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w04 = ensure_w04_fixtures()
        cls.w03 = ensure_w03_fixtures()

    def prepared(self, names):
        """合成原件→双根工作区；w04 优先、缺则回落 w03（invoice.pdf 等公共件在 w03）。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        for name in names:
            source = self.w04 / name if (self.w04 / name).is_file() else self.w03 / name
            shutil.copy(source, originals / name)
        manifest_path = prepare_dual_materials(originals, Path(temporary.name) / "work")
        return manifest_path, json.loads(manifest_path.read_text(encoding="utf-8")), originals


# ------------------------------------------------------------ 来源与稳定 ID

class SourceRuleTests(W04TestCase):
    def test_user_instruction_rejects_derived_binding(self):
        """agent 推断禁标 user：绑定派生工件的事实不得标 user_instruction。"""
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add("scope", source="user_instruction", value={"categories": ["交通"]},
                   locator="derived/x.json", input_hashes={"extraction:abc": "h1"})
        # 无工件绑定的真实用户指令可用
        fact_id = fs.add("scope", source="user_instruction",
                         value={"categories": ["交通"]}, locator="user-message:2026-10-24")
        self.assertEqual(fs.get(fact_id).source, "user_instruction")

    def test_deterministic_requires_derivation(self):
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add("total", source="deterministic_computation", value={"amount": "1.00"},
                   locator="derived")
        fs.add("total", source="deterministic_computation", value={"amount": "1.00"},
               locator="derived", derivation="明细合计")

    def test_unknown_source_and_kind_closed(self):
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add("scope", source="agent_guess", value={}, locator="x")
        with self.assertRaises(ValueError):
            fs.add("mystery_kind", source="material_extraction", value={}, locator="x")
        with self.assertRaises(ValueError):
            fs.add("scope", source="material_extraction", value={}, locator="  ")


class StableReferenceTests(W04TestCase):
    def test_ids_sequential_and_allocation_references_ids_not_copies(self):
        fs = FactSet()
        invoice_id, _ = fs.add_invoice("00301234", "128.70", locator="inv.pdf#page:1")
        expense_id = fs.add_expense("128.70", locator="ledger.xlsx#明细!C2")
        alloc_id = fs.add_allocation(invoice_id, expense_id, "128.70", locator="alloc-note")
        self.assertEqual([f.fact_id for f in fs][:2], ["F-0001", "F-0002"])
        allocation = fs.get(alloc_id)
        self.assertEqual(set(allocation.value), {"invoice_ref", "expense_ref", "amount"})
        self.assertEqual(allocation.value["invoice_ref"], invoice_id)
        self.assertEqual(allocation.value["expense_ref"], expense_id)
        self.assertNotIn("number", allocation.value)  # 票号不被复制进分配

    def test_allocation_referential_integrity(self):
        fs = FactSet()
        invoice_id, _ = fs.add_invoice("00301234", "128.70", locator="inv.pdf")
        with self.assertRaises(KeyError):
            fs.add_allocation(invoice_id, "F-9999", "1.00", locator="x")
        other, _ = fs.add_invoice("00301235", "1.00", locator="inv2.pdf")
        with self.assertRaises(ValueError):
            fs.add_allocation(other, invoice_id, "1.00", locator="x")  # invoice_ref 指向票但 expense_ref 传错位


# ------------------------------------------------------------ 版本漂移

class VersionDriftTests(W04TestCase):
    def test_drift_flags_affected_without_mutation(self):
        fs = FactSet(bindings={"extraction:invoice": "h1"})
        invoice_id, _ = fs.add_invoice("00301234", "128.70", locator="inv.pdf",
                                       input_hashes={"extraction:invoice": "h1"})
        user_scope = fs.add("scope", source="user_instruction", value={"categories": ["交通"]},
                            locator="user-message:2026-10-24")
        report = check_version_drift(fs, {"extraction:invoice": "h2"})
        self.assertTrue(report["needs_replan"])
        affected = {item["fact_id"] for item in report["affected"]}
        self.assertEqual(affected, {invoice_id})          # 用户指令事实不受材料漂移影响
        self.assertIn(user_scope, {f.fact_id for f in fs})
        self.assertEqual(fs.get(invoice_id).input_hashes, {"extraction:invoice": "h1"})  # 既有事实未被改写
        item = report["affected"][0]
        self.assertEqual(item["recorded"], {"extraction:invoice": "h1"})
        self.assertEqual(item["current"], {"extraction:invoice": "h2"})

    def test_no_drift_when_unchanged_and_artifact_gone_flags(self):
        fs = FactSet()
        fid, _ = fs.add_invoice("00301234", "1.00", locator="x",
                                input_hashes={"k": "same"})
        self.assertFalse(check_version_drift(fs, {"k": "same"})["needs_replan"])
        report = check_version_drift(fs, {})               # 工件消失同样受影响
        self.assertTrue(report["needs_replan"])
        self.assertEqual(report["affected"][0]["changed_keys"], ["k"])


# ------------------------------------------------------------ 对账：正向

class ReconcileHappyPathTests(W04TestCase):
    def test_full_coherent_set_passes_with_same_amount_expenses(self):
        """同金额≠禁报：两笔同额费用各自由不同票据完整分配，全部闭合。"""
        fs = FactSet()
        inv1, _ = fs.add_invoice("00301234", "64.35", locator="inv1.pdf#page:1")
        inv2, _ = fs.add_invoice("00301235", "64.35", locator="inv2.pdf#page:1")
        exp1 = fs.add_expense("64.35", locator="ledger.xlsx#明细!C2", category="交通")
        exp2 = fs.add_expense("64.35", locator="ledger.xlsx#明细!C3", category="交通")
        fs.add_allocation(inv1, exp1, "64.35", locator="分配:票1→行1")
        fs.add_allocation(inv2, exp2, "64.35", locator="分配:票2→行2")
        fs.add_expense("128.70", locator="ledger.xlsx#汇总!B1", layer="summary", category="交通")
        fs.add("applicability", source="material_extraction",
               value={"category": "交通", "amount": "128.70"}, locator="费用说明.txt#L1")
        fs.add("scope", source="user_instruction", value={"categories": ["交通"]},
               locator="user-message:2026-10-24")
        fs.add_payee(name="收款公司", account="1234567890", branch="某支行", interbank="102100099996",
                     amount="128.70", locator="结算单#收款行")
        fs.add("total", source="deterministic_computation", derivation="明细合计=两票分配和",
               value={"amount": "128.70"}, locator="derived:total")
        report = reconcile(fs)
        self.assertFalse(report.blocked, report.to_payload())
        same_amount = check_by_name(report, "same_amount_not_forbidden")
        self.assertEqual(same_amount.status, "pass")
        self.assertEqual(same_amount.details[0]["duplicated_amounts"], ["64.35"])

    def test_no_invoice_basis_covers_expense(self):
        fs = FactSet()
        exp = fs.add_expense("20.00", locator="ledger.xlsx#明细!C4", category="交通")
        fs.add_no_invoice_basis(exp, reason="出租车定额票免票行（本次材料说明）",
                                source="material_extraction", locator="费用说明.txt#L2")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "20.00"}, locator="derived:total")
        report = reconcile(fs)
        self.assertFalse(report.blocked, report.to_payload())


# ------------------------------------------------------------ 对账：W03 产物集成

class ExtractionIntegrationTests(W04TestCase):
    def test_invoice_from_real_extraction_closes(self):
        manifest_path, _, _ = self.prepared(["invoice.pdf"])
        result = run_pdf_extraction(manifest_path, "invoice.pdf")
        fs = FactSet()
        [(invoice_id, created)] = fs.add_invoice_from_extraction(result["payload"], locator_prefix="invoice.pdf")
        self.assertTrue(created)
        self.assertEqual(fs.get(invoice_id).value["face_total"], "128.70")
        self.assertTrue(fs.get(invoice_id).input_hashes)   # 版本绑定到 original_sha256
        exp = fs.add_expense("128.70", locator="invoice.pdf#费用行", category="交通")
        fs.add_allocation(invoice_id, exp, "128.70", locator="整票对应")
        fs.add("total", source="deterministic_computation", derivation="票面全额",
               value={"amount": "128.70"}, locator="derived:total")
        report = reconcile(fs)
        self.assertFalse(report.blocked, report.to_payload())

    def test_excel_vs_invoice_conflict_blocks_with_locators(self):
        """结算明细（xlsx 明细 4 行合计 112.00）vs 票面 128.70：阻断并双向定位。"""
        manifest_path, _, _ = self.prepared(["invoice.pdf", "ledger.xlsx"])
        result = run_pdf_extraction(manifest_path, "invoice.pdf")
        workbook = extract_workbook(self.w03 / "ledger.xlsx")
        fs = FactSet()
        [(invoice_id, _)] = fs.add_invoice_from_extraction(result["payload"], locator_prefix="invoice.pdf")
        for row in (2, 3, 4, 5):
            cell = workbook["sheets"]["明细"]["cells"]["C{0}".format(row)]
            expense_id = fs.add_expense(Decimal(str(cell["value"])),
                                        locator="ledger.xlsx#明细!C{0}".format(row))
            # 按明细行金额逐行分配 → 合计 112.00 ≠ 票面 128.70
            fs.add_allocation(invoice_id, expense_id, Decimal(str(cell["value"])),
                              locator="ledger.xlsx#明细!C{0}".format(row))
        report = reconcile(fs)
        self.assertTrue(report.blocked)
        self.assertIn("invoice_allocation_closure", report.block_names())
        closure = check_by_name(report, "invoice_allocation_closure")
        detail = closure.details[0]
        self.assertEqual(detail["face"], "128.70")
        self.assertEqual(detail["allocated"], "112.00")
        joined = json.dumps(closure.details, ensure_ascii=False)
        self.assertIn("明细!C2", joined)      # Excel 侧定位
        self.assertIn("invoice.pdf", joined)  # 票面侧定位

    def test_same_invoice_two_scans_single_count(self):
        manifest_path, _, _ = self.prepared(["invoice.pdf", "scan-2.pdf"])
        first = run_pdf_extraction(manifest_path, "invoice.pdf")
        fs = FactSet()
        [(id1, _)] = fs.add_invoice_from_extraction(first["payload"], locator_prefix="invoice.pdf")
        # 第二次扫描（同名同面）不建第二张票：归并进同一事实
        id2, created2 = fs.add_invoice("00301234", "128.70", locator="scan-2.pdf#page:1")
        self.assertEqual(id1, id2)
        self.assertFalse(created2)
        self.assertEqual(len(fs.by_kind("invoice")), 1)
        exp = fs.add_expense("128.70", locator="ledger.xlsx#明细!C2")
        fs.add_allocation(id1, exp, "128.70", locator="分配")
        fs.add("total", source="deterministic_computation", derivation="票面全额",
               value={"amount": "128.70"}, locator="derived:total")
        report = reconcile(fs)
        self.assertFalse(report.blocked, report.to_payload())   # 去重后单计
        faces = fs.get(id1).value["scans"]
        self.assertEqual(len(faces), 2)

    def test_duplicate_copy_group_consumed_once(self):
        """R2-P6 组语义：同内容副本按组去重，组内副本不逐文件误报/重复计票。"""
        manifest_path, manifest, _ = self.prepared(["invoice.pdf", "scan-2.pdf"])
        classification = classify_materials(manifest)
        groups = [entry for entry in classification["by_hash"].values()
                  if entry["category"] == "duplicate_copy"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["relative_paths"]), 2)   # 组内两副本
        # 组消费一次：仅从组代表件建一张票
        result = run_pdf_extraction(manifest_path, "invoice.pdf")
        fs = FactSet()
        fs.add_invoice_from_extraction(result["payload"], locator_prefix="invoice.pdf")
        self.assertEqual(len(fs.by_kind("invoice")), 1)          # 不因两份文件出现两张票

    def test_multi_record_payload_creates_all_invoices(self):
        """D3：多 record 载荷（上游分件后一文件多票）逐 record 建票并按序返回。"""
        payload = {
            "schema_version": "1.0", "reviewed": True, "reviewed_by": "test",
            "original_path": "multi.pdf", "original_sha256": "a" * 64,
            "records": [
                {"record_id": "invoice-1",
                 "fields": {"invoice_number": {"value": "00301001", "locator": "page:1"},
                            "total_amount": {"value": "22.64", "locator": "page:1"}}},
                {"record_id": "invoice-2",
                 "fields": {"invoice_number": {"value": "00301002", "locator": "page:2"},
                            "total_amount": {"value": "39.90", "locator": "page:2"}}},
            ],
            "review_evidence": {"note": "合成多票"}, "gaps": [],
        }
        fs = FactSet()
        results = fs.add_invoice_from_extraction(payload, locator_prefix="multi.pdf")
        self.assertEqual([created for _, created in results], [True, True])
        self.assertEqual(len(fs.by_kind("invoice")), 2)
        faces = {fs.get(fact_id).value["face_total"]: fact_id for fact_id, _ in results}
        self.assertEqual(set(faces), {"22.64", "39.90"})   # 两 record 各自面值，不并票

    def test_multi_record_missing_required_field_raises(self):
        """多 record 载荷里任一 record 缺票号/面值 → 整体拒绝（不静默漏票）。"""
        payload = {"schema_version": "1.0", "reviewed": True,
                   "original_sha256": "a" * 64,
                   "records": [
                       {"record_id": "invoice-1",
                        "fields": {"invoice_number": {"value": "00301001", "locator": "page:1"},
                                   "total_amount": {"value": "22.64", "locator": "page:1"}}},
                       {"record_id": "invoice-2",
                        "fields": {"invoice_number": {"value": "00301002", "locator": "page:2"}}},
                   ]}
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add_invoice_from_extraction(payload, locator_prefix="multi.pdf")

    def test_same_number_conflicting_face_blocks(self):
        manifest_path, _, _ = self.prepared(["invoice.pdf", "scan-3.pdf"])
        first = run_pdf_extraction(manifest_path, "invoice.pdf")
        second = run_pdf_extraction(manifest_path, "scan-3.pdf")
        fs = FactSet()
        [(id1, _)] = fs.add_invoice_from_extraction(first["payload"], locator_prefix="invoice.pdf")
        [(id2, created2)] = fs.add_invoice_from_extraction(second["payload"], locator_prefix="scan-3.pdf")
        self.assertEqual(id1, id2)
        self.assertFalse(created2)
        report = reconcile(fs)
        self.assertTrue(report.blocked)
        face = check_by_name(report, "invoice_face_consistency")
        self.assertEqual(face.status, "block")
        detail = json.dumps(face.details, ensure_ascii=False)
        self.assertIn("128.70", detail)
        self.assertIn("999.99", detail)
        self.assertIn("scan-3.pdf", detail)


# ------------------------------------------------------------ 边界拒绝

class BoundaryTests(W04TestCase):
    def test_qty_unit_price_rejected(self):
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add_expense("6.00", locator="ledger.xlsx#明细!C2",
                           value_extra={"quantity": 2, "unit_price": 3.00})

    def test_loan_deduction_rejected(self):
        fs = FactSet()
        with self.assertRaises(ValueError):
            fs.add_expense("100.00", locator="ledger.xlsx#明细!C2",
                           value_extra={"loan_deduction": "100.00"})

    def test_unknown_material_blocks(self):
        fs = FactSet()
        report = reconcile(fs, pending_materials=[
            {"relative_path": "mystery.xlsx", "category": "other_pending",
             "pending_reason": "未建模表结构"}])
        self.assertIn("boundary_unknown_materials", report.block_names())

    def test_partial_face_blocks(self):
        fs = FactSet()
        invoice_id, _ = fs.add_invoice("00301234", "128.70", locator="inv.pdf")
        exp = fs.add_expense("100.00", locator="ledger.xlsx#明细!C2")
        fs.add_allocation(invoice_id, exp, "100.00", locator="分配")
        report = reconcile(fs)
        self.assertIn("invoice_allocation_closure", report.block_names())
        detail = check_by_name(report, "invoice_allocation_closure").details[0]
        self.assertEqual(detail["face"], "128.70")
        self.assertEqual(detail["allocated"], "100.00")

    def test_uncovered_expense_blocks_and_basis_requires_reason(self):
        fs = FactSet()
        exp = fs.add_expense("50.00", locator="ledger.xlsx#明细!C2")
        with self.assertRaises(ValueError):
            fs.add_no_invoice_basis(exp, reason="", source="material_extraction",
                                    locator="费用说明.txt")
        report = reconcile(fs)
        self.assertIn("expense_allocation_coverage", report.block_names())


# ------------------------------------------------------------ 收款身份与分层闭合

class PayeeAndLayerTests(W04TestCase):
    def base_set(self):
        fs = FactSet()
        inv, _ = fs.add_invoice("00301234", "100.00", locator="inv.pdf")
        exp = fs.add_expense("100.00", locator="ledger.xlsx#明细!C2")
        fs.add_allocation(inv, exp, "100.00", locator="分配")
        return fs

    def test_incomplete_payee_blocks(self):
        fs = self.base_set()
        fs.add_payee(name="某公司", account="123", branch="", interbank="102",
                     amount="100.00", locator="结算单#收款行")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("payee_identity", report.block_names())
        detail = check_by_name(report, "payee_identity").details[0]
        self.assertIn("branch", detail["missing"])

    def test_conflicting_payee_identity_blocks(self):
        fs = self.base_set()
        fs.add_payee(name="某公司", account="111", branch="甲支行", interbank="102",
                     amount="100.00", locator="结算单#收款行")
        fs.add_payee(name="某公司", account="222", branch="甲支行", interbank="102",
                     amount="100.00", locator="银行回单#收款行")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("payee_identity", report.block_names())
        joined = json.dumps(check_by_name(report, "payee_identity").details, ensure_ascii=False)
        self.assertIn("account", joined)

    def test_absent_payees_not_treated_as_conflict(self):
        fs = self.base_set()
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertFalse(report.blocked, report.to_payload())
        self.assertEqual(check_by_name(report, "payee_identity").status, "pass")

    def test_summary_detail_mismatch_blocks(self):
        fs = self.base_set()
        fs.add_expense("120.00", locator="ledger.xlsx#汇总!B1", layer="summary")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("summary_detail_consistency", report.block_names())

    def test_total_double_count_across_layers_rejected(self):
        """跨层相加重复计费：总额=明细+汇总 不被接受。"""
        fs = self.base_set()
        fs.add_expense("100.00", locator="ledger.xlsx#汇总!B1", layer="summary")
        fs.add("total", source="deterministic_computation", derivation="错误地把汇总层也加上",
               value={"amount": "200.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("total_closure", report.block_names())

    def test_scope_violation_blocks(self):
        fs = self.base_set()
        exp2 = fs.add_expense("30.00", locator="ledger.xlsx#明细!C3", category="招待")
        inv2, _ = fs.add_invoice("00301235", "30.00", locator="inv2.pdf")
        fs.add_allocation(inv2, exp2, "30.00", locator="分配")
        fs.add("scope", source="user_instruction", value={"categories": ["交通"]},
               locator="user-message:2026-10-24")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "130.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("scope_consistency", report.block_names())

    def test_applicability_mismatch_blocks(self):
        fs = self.base_set()
        fs.add("applicability", source="material_extraction",
               value={"category": None, "amount": "90.00"}, locator="费用说明.txt#L1")
        fs.add("total", source="deterministic_computation", derivation="明细合计",
               value={"amount": "100.00"}, locator="derived")
        report = reconcile(fs)
        self.assertIn("applicability_closure", report.block_names())


# ------------------------------------------------------------ 跨任务发票提示

class RegistryHintTests(W04TestCase):
    def test_hint_from_numbers_array(self):
        fs = FactSet()
        inv, _ = fs.add_invoice("00301234", "128.70", locator="inv.pdf")
        exp = fs.add_expense("128.70", locator="ledger.xlsx#明细!C2")
        fs.add_allocation(inv, exp, "128.70", locator="分配")
        fs.add("total", source="deterministic_computation", derivation="票面全额",
               value={"amount": "128.70"}, locator="derived")
        registry_dir = self.w04 / "task-registry-sim"
        hints, notes = scan_task_registry(registry_dir, ["00301234"])
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["task_id"], "TSK-9001")
        self.assertEqual(hints[0]["evidence"], "authorized_revision*.numbers")
        report = reconcile(fs, registry_dir=str(registry_dir))
        self.assertFalse(report.blocked)                  # 提示级，不阻断
        self.assertEqual(check_by_name(report, "cross_task_invoice_hints").status, "info")
        self.assertEqual(report.hints[0]["registry_file"], "TSK-9001.form.json")

    def test_missing_registry_degrades(self):
        hints, notes = scan_task_registry(self.w04 / "no-such-dir", ["00301234"])
        self.assertEqual(hints, [])
        self.assertTrue(any("降级" in note for note in notes))
        hints2, notes2 = scan_task_registry(None, ["00301234"])
        self.assertEqual(hints2, [])
        self.assertTrue(any("未提供" in note for note in notes2))


class FromPayloadInvariantTests(W04TestCase):
    """R4-P2a：from_payload 与 add() 共享全套构造不变量——手写载荷夹带违例事实同样拒绝。"""

    def payload(self, **overrides):
        fact = {"fact_id": "F-0001", "kind": "expense", "source": "material_extraction",
                "value": {"amount": "100.00", "layer": "detail"}, "locator": "ledger.xlsx#明细!B2",
                "derivation": None, "input_hashes": {"ledger": "a" * 64},
                "note": None, "created_at": "2026-10-24T00:00:00+00:00"}
        fact.update(overrides)
        return {"schema_version": FactSet.to_payload(FactSet())["schema_version"],
                "bindings": {}, "business_ref": None, "facts": [fact]}

    def test_valid_payload_roundtrip(self):
        restored = FactSet.from_payload(self.payload())
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored.get("F-0001").value["amount"], "100.00")

    def test_unknown_kind_or_source_rejected(self):
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(kind="mystery"))
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(source="hallucination"))

    def test_blank_locator_rejected(self):
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(locator="   "))

    def test_derived_without_derivation_rejected(self):
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(source="deterministic_computation",
                                              derivation=None))

    def test_user_instruction_with_hashes_rejected(self):
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(source="user_instruction",
                                              input_hashes={"x": "y"}))

    def test_forbidden_fields_rejected(self):
        with self.assertRaises(ValueError):
            FactSet.from_payload(self.payload(value={"amount": "100.00", "layer": "detail",
                                                     "quantity": 2, "unit_price": "50.00"}))


if __name__ == "__main__":
    unittest.main()
