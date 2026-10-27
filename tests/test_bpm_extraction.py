"""W03 原件理解管线测试：全部合成 fixtures，无真实业务数据；全离线。"""
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import bpm.extraction as bpm_extraction
from bpm.extraction import (GAP_FIELDS, classify_materials, extract_csv_table, extract_pdf_facts,
                            extract_pdf_text, extract_workbook, ocr_pass, review_pass,
                            run_image_extraction, run_pdf_extraction)
from bpm.materials import inventory_materials, prepare_dual_materials, register_derived, validate_dual_manifest
from bpm.plan import file_hash, validate_plan

FIXTURES = Path(__file__).parent / "fixtures" / "w03"
STAMP = "w03-v1"


def _pdf(path, lines):
    import fitz

    document = fitz.open()
    page = document.new_page(width=595, height=842)
    for offset, text in lines:
        page.insert_text((72, offset), text, fontname="china-s", fontsize=11)
    document.save(path)
    document.close()


def ensure_fixtures():
    """幂等构建合成 fixtures：fitz 生成 PDF、PIL 条码图、openpyxl 工作簿、CSV、说明文本。"""
    if (FIXTURES / STAMP).is_file():
        return FIXTURES
    if FIXTURES.exists():
        shutil.rmtree(FIXTURES)
    FIXTURES.mkdir(parents=True)
    _pdf(FIXTURES / "invoice.pdf", [(90, "销售方名称：厦门某某科技有限公司"),
                                    (120, "开票日期：2026-10-20"),
                                    (150, "发票代码：044031900111"),
                                    (180, "发票号码：00301234"),
                                    (400, "合计（不含税）￥112.00"),
                                    (430, "税额（小写）￥16.70"),
                                    (460, "价税合计（小写）￥128.70")])
    _pdf(FIXTURES / "发票.pdf", [(120, "项目明细清单"), (160, "序号 名称 数量")])  # 文件名陷阱：内容不含发票要素
    (FIXTURES / "bars.png").write_bytes(bpm_extraction.draw_bars("861002"))
    from openpyxl import Workbook

    workbook = Workbook()
    detail = workbook.active
    detail.title = "明细"
    detail.append(["日期", "事由", "金额", "票号"])
    detail.append(["2026-10-01", "市内交通", 12.50, "0012345"])
    detail.append(["2026-10-02", "城际车票", 38.00, "0012346"])
    detail.append(["2026-10-03", "住宿", 6.20, "0012347"])
    detail.append(["2026-10-04", "会议用车", 55.30, "0012348"])
    detail.row_dimensions[4].hidden = True
    detail.auto_filter.ref = "A1:D5"
    summary = workbook.create_sheet("汇总")
    summary["A1"] = "合计"
    summary["B1"] = "=SUM(明细!C2:C5)"
    hidden = workbook.create_sheet("隐藏表")
    hidden.sheet_state = "hidden"
    hidden["A1"] = "内部留档"
    complex_sheet = workbook.create_sheet("复杂")
    complex_sheet["A1"] = "查找"
    complex_sheet["B1"] = '=VLOOKUP("市内交通",明细!A2:D5,3,FALSE)'
    workbook.save(FIXTURES / "ledger.xlsx")
    (FIXTURES / "rows.csv").write_text(
        "日期,单号,金额\n2026-10-02,0012345,25.00\n2026-10-03,1.23457E+12,30.00\n2026-10-04,1234567890123456780.0,9.90\n",
        encoding="utf-8")
    note = "费用情况说明：本次差旅为10月项目现场支持，交通与住宿均为本人垫付，明细见附件。"
    (FIXTURES / "费用说明.txt").write_text(note, encoding="utf-8")
    (FIXTURES / "说明备份.txt").write_text(note, encoding="utf-8")
    (FIXTURES / STAMP).write_text("synthetic fixtures only; regenerate by deleting this stamp", encoding="utf-8")
    return FIXTURES


class W03TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = ensure_fixtures()

    def prepared(self, names):
        """合成原件→双根工作区；返回 (manifest_path, manifest_dir, originals_dir)。"""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        for name in names:
            shutil.copy(self.fixtures / name, originals / name)
        manifest_path = prepare_dual_materials(originals, Path(temporary.name) / "work")
        return manifest_path, Path(temporary.name), originals


class PdfChainTests(W03TestCase):
    def test_pdf_extraction_end_to_end(self):
        manifest_path, _, _ = self.prepared(["invoice.pdf"])
        result = run_pdf_extraction(manifest_path, "invoice.pdf")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        roles = {entry["relative_path"]: entry["role"] for entry in manifest["derived_files"]}
        original_hash = file_hash(self.fixtures / "invoice.pdf")
        prefix = original_hash[:16]
        self.assertEqual(roles["ocr/{0}.json".format(prefix)], "ocr_result")
        self.assertEqual(roles["reviewed/{0}.json".format(prefix)], "reviewed_extraction")
        for relative in ("ocr/{0}.json".format(prefix), "reviewed/{0}.json".format(prefix)):
            entry = next(item for item in manifest["derived_files"] if item["relative_path"] == relative)
            self.assertEqual(entry["sources"], [original_hash])
        raw_payload = json.loads(next(Path(item["path"]) for item in manifest["derived_files"]
                                      if item["relative_path"] == "ocr/{0}.json".format(prefix)).read_text(encoding="utf-8"))
        self.assertNotIn("reviewed", raw_payload)  # 原始输出层永不携带复核标记
        payload = result["payload"]
        self.assertTrue(payload["reviewed"])
        self.assertIn("reviewed_at", payload)
        self.assertTrue(payload["method"])
        fields = payload["records"][0]["fields"]
        self.assertEqual(fields["invoice_number"]["value"], "00301234")
        self.assertEqual(fields["total_amount"]["value"], "128.70")
        self.assertIn("page:1/region:", fields["invoice_number"]["locator"])
        self.assertTrue(result["closure"]["closed"])
        self.assertEqual(payload["review_evidence"]["invoice_number"]["verified_via"], "raw-line-anchor-match")

    def test_pdf_amount_mismatch_registers_structured_gap(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "broken.pdf"
        _pdf(pdf_path, [(180, "发票号码：00998877"), (400, "合计（不含税）￥100.00"),
                        (430, "税额￥9.00"), (460, "价税合计（小写）￥200.00")])
        result = extract_pdf_facts(pdf_path)
        self.assertFalse(result["closure"]["closed"])
        self.assertEqual(len(result["gaps"]), 1)
        self.assertEqual(set(result["gaps"][0]), set(GAP_FIELDS))
        self.assertIn("不闭合", result["gaps"][0]["reason"])

    def test_pdf_lines_carry_page_region_bbox(self):
        lines = extract_pdf_text(self.fixtures / "invoice.pdf")["items"]
        line = next(item for item in lines if "发票号码" in item["text"])
        self.assertEqual(line["page"], 1)
        self.assertIn(line["region"], ("header", "body", "footer"))
        self.assertEqual(len(line["bbox"]), 4)


class ImageChainTests(W03TestCase):
    def test_image_two_layer_pipeline(self):
        manifest_path, _, _ = self.prepared(["bars.png"])
        result = run_image_extraction(manifest_path, "bars.png", engine="barstub")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        original_hash = file_hash(self.fixtures / "bars.png")
        prefix = original_hash[:16]
        ocr_entry = next(item for item in manifest["derived_files"] if item["relative_path"] == "ocr/{0}.json".format(prefix))
        reviewed_entry = next(item for item in manifest["derived_files"] if item["relative_path"] == "reviewed/{0}.json".format(prefix))
        self.assertEqual((ocr_entry["role"], reviewed_entry["role"]), ("ocr_result", "reviewed_extraction"))
        self.assertEqual(ocr_entry["sources"], [original_hash])
        self.assertEqual(reviewed_entry["sources"], [original_hash])
        raw_payload = json.loads(Path(ocr_entry["path"]).read_text(encoding="utf-8"))
        self.assertEqual(raw_payload["engine"], "barstub")
        self.assertEqual(raw_payload["items"][0]["text"], "861002")
        self.assertNotIn("reviewed", raw_payload)
        payload = result["review"]["payload"]
        self.assertEqual(payload["records"][0]["fields"]["code_1"]["value"], "861002")
        self.assertEqual(payload["review_evidence"]["code_1"]["verified_via"], "raw-item-cross-check")

    def test_review_rejects_value_disagreeing_with_raw_layer(self):
        manifest_path, _, _ = self.prepared(["bars.png"])
        ocr = ocr_pass(manifest_path, "bars.png", engine="barstub")
        with self.assertRaises(ValueError):
            review_pass(manifest_path, "bars.png", {"code_1": {"value": "999999", "raw_item": 0}},
                        reviewer="test-agent", method="local-engine-raw-cross-check",
                        ocr_relative_name=ocr["relative_name"])

    def test_agent_visual_review_records_honest_evidence(self):
        manifest_path, _, _ = self.prepared(["bars.png"])
        result = review_pass(manifest_path, "bars.png",
                             {"total": {"value": "861002", "page": 1, "region": "body", "bbox": [0, 12, 60, 28]}},
                             reviewer="test-agent+vision", method="agent-visual-region-recheck",
                             verify="agent-visual")
        evidence = result["payload"]["review_evidence"]["total"]
        self.assertEqual(evidence["verified_via"], "agent-visual-region-recheck")
        self.assertEqual(evidence["mechanical_crosscheck"], "unavailable-no-engine-output")
        self.assertTrue(result["payload"]["reviewed"])


class MultiPageRenderTests(W03TestCase):
    """全页渲染（2026-10-24）：PDF 每页渲染+页级锚点贯通，图片仍单页。"""

    @staticmethod
    def _bars_pdf(path, page_codes):
        import fitz

        document = fitz.open()
        for code in page_codes:
            page = document.new_page(width=400, height=120)
            page.insert_image(fitz.Rect(20, 40, 380, 100),
                              stream=bpm_extraction.draw_bars(code))
        document.save(path)
        document.close()

    def test_render_pages_covers_all_pdf_pages(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "multi.pdf"
        self._bars_pdf(pdf_path, ["861002", "112233", "445566"])
        pages = bpm_extraction.render_pages(pdf_path)
        self.assertEqual([page["page"] for page in pages], [1, 2, 3])
        self.assertTrue(all(page["png"][:8] == b"\x89PNG\r\n\x1a\n" for page in pages))

    def test_render_to_files_writes_each_page_with_hash(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "multi.pdf"
        self._bars_pdf(pdf_path, ["861002", "112233"])
        renders = bpm_extraction.render_to_files(pdf_path, Path(temporary.name) / "renders")
        self.assertEqual([r["page"] for r in renders], [1, 2])
        for render in renders:
            self.assertTrue(Path(render["path"]).is_file())
            self.assertEqual(render["sha256"], file_hash(render["path"]))

    def test_render_original_keeps_first_page_compat(self):
        pages = bpm_extraction.render_pages(self.fixtures / "invoice.pdf")
        self.assertEqual(len(pages), 1)
        self.assertEqual(bpm_extraction.render_original(self.fixtures / "invoice.pdf"), pages[0]["png"])

    def test_ocr_pass_page_numbers_follow_render_pages(self):
        # 页级贯通断言用页回显引擎：barstub 是像素精确解码器，PDF 栅格化重采样会
        # 破坏条带游程（这正是它只作为纯测试引擎的原因之一）；页码语义与解码无关。
        bpm_extraction.register_ocr_engine("echo-page", lambda png: [{"text": "echo", "bbox": [0, 0, 1, 1]}])
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "multi.pdf"
        self._bars_pdf(pdf_path, ["861002", "112233"])
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        shutil.copy(pdf_path, originals / "multi.pdf")
        manifest_path = prepare_dual_materials(originals, Path(temporary.name) / "work")
        ocr = ocr_pass(manifest_path, "multi.pdf", engine="echo-page")
        self.assertEqual(ocr["pages"], 2)
        self.assertEqual(ocr["raw"]["pages"], 2)
        self.assertEqual(sorted(item["page"] for item in ocr["raw"]["items"]), [1, 2])   # 页码=真实渲染页
        self.assertEqual(ocr["raw"]["engine"], "echo-page")


class WorkbookTests(W03TestCase):
    def test_workbook_semantics(self):
        result = extract_workbook(self.fixtures / "ledger.xlsx")
        sheets = result["sheets"]
        self.assertEqual(sheets["明细"]["header_row"], 1)
        self.assertIn(4, sheets["明细"]["hidden_rows"])
        self.assertEqual(sheets["明细"]["autofilter"]["ref"], "A1:D5")
        self.assertEqual(sheets["隐藏表"]["state"], "hidden")
        self.assertEqual(sheets["明细"]["cells"]["D2"]["value"], "0012345")  # 前导零原值保留
        self.assertEqual(sheets["明细"]["cells"]["D2"]["kind"], "text")
        formulas = {formula["ref"]: formula for sheet in sheets.values() for formula in sheet["formula_cells"]}
        self.assertEqual(formulas["汇总!B1"]["resolution"], "recomputed")
        self.assertEqual(Decimal(formulas["汇总!B1"]["resolved"]), Decimal("112.00"))
        self.assertEqual(formulas["复杂!B1"]["resolution"], "gap")
        gap_entry = next(entry for entry in result["gaps"] if entry["locator"] == "复杂!B1")
        self.assertEqual(set(gap_entry), set(GAP_FIELDS))
        self.assertEqual(sheets["汇总"]["summary_rows"][0]["amount"], "112.00")
        self.assertTrue(any(candidate["candidate_detail_sheet"] == "明细" and candidate["amount_match"]
                            for candidate in result["summary_candidates"]))
        self.assertEqual([name for name in dir(bpm_extraction) if "expense" in name], [])

    def test_numeric_id_column_registers_precision_gap(self):
        from openpyxl import Workbook

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "ids.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["运单号", "金额"])
        sheet.append([1234567, 10.00])
        workbook.save(path)
        result = extract_workbook(path)
        self.assertEqual(len(result["gaps"]), 1)
        self.assertEqual(result["gaps"][0]["locator"], "Sheet!A2")
        self.assertIn("丢精度", result["gaps"][0]["reason"])


class CsvTests(W03TestCase):
    def test_csv_positioning_and_precision_loss(self):
        result = extract_csv_table(self.fixtures / "rows.csv")
        self.assertEqual(result["header"], ["日期", "单号", "金额"])
        rows = {row["row"]: row["cells"] for row in result["rows"]}
        self.assertEqual(rows[2]["R2C2"]["value"], "0012345")  # 前导零天然保留
        locators = {entry["locator"] for entry in result["gaps"]}
        self.assertEqual(locators, {"R3C2", "R4C2"})
        for entry in result["gaps"]:
            self.assertEqual(set(entry), set(GAP_FIELDS))
            self.assertIn("丢精度", entry["reason"])


class ClassificationTests(W03TestCase):
    def test_categories_and_filename_is_not_evidence(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        for name in ("invoice.pdf", "发票.pdf", "ledger.xlsx", "费用说明.txt", "bars.png"):
            shutil.copy(self.fixtures / name, originals / name)
        result = classify_materials(inventory_materials(originals))
        categories = {}
        for entry in result["by_hash"].values():
            for relative in entry["relative_paths"]:
                categories[relative] = entry
        self.assertEqual(categories["invoice.pdf"]["category"], "invoice")
        self.assertNotEqual(categories["发票.pdf"]["category"], "invoice")  # 文件名不作证据
        self.assertIsNotNone(categories["发票.pdf"]["pending_reason"])
        self.assertEqual(categories["ledger.xlsx"]["category"], "summary_statement")
        self.assertEqual(categories["费用说明.txt"]["category"], "explanation")
        self.assertEqual(categories["bars.png"]["category"], "other_pending")
        for entry in result["by_hash"].values():
            self.assertTrue(entry["basis"])

    def test_duplicate_detection_is_content_based(self):
        entry = classify_materials(inventory_materials(self.fixtures.parent / "w03"))["by_hash"]
        duplicates = [item for item in entry.values() if item["category"] == "duplicate_copy"]
        self.assertTrue(duplicates)
        self.assertIn("sha256", duplicates[0]["basis"])
        self.assertEqual(sorted(duplicates[0]["relative_paths"]), ["说明备份.txt", "费用说明.txt"])


class RelativeRootRegressionTests(W03TestCase):
    """R2-P1：相对 derived_root 必须挂 manifest 所在目录解析，与 CWD 无关。"""

    def build_relative_manifest(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        originals = base / "originals"
        originals.mkdir()
        shutil.copy(self.fixtures / "invoice.pdf", originals / "invoice.pdf")
        files = []
        for item in inventory_materials(originals)["files"]:
            files.append(dict(item, path="originals/" + item["relative_path"]))
        (base / "work").mkdir()
        manifest = {"schema_version": "2.0", "originals_root": "originals", "derived_root": "work",
                    "files": files, "derived_files": []}
        manifest_path = base / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return base, manifest_path, files[0]["sha256"]

    def test_register_derived_resolves_manifest_dir_from_any_cwd(self):
        base, manifest_path, original_hash = self.build_relative_manifest()
        previous = os.getcwd()
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        os.chdir(elsewhere)
        try:
            register_derived(manifest_path, "reviewed/a.json", {"k": "v"}, role="run_evidence",
                             sources=[original_hash], generated_by="t")
        finally:
            os.chdir(previous)
        self.assertTrue((base / "work" / "reviewed" / "a.json").is_file())
        self.assertFalse((Path(elsewhere) / "work").exists())
        updated = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(validate_dual_manifest(updated, base_dir=base), [])

    def test_relative_root_extraction_pipeline_from_any_cwd(self):
        from bpm.materials import validate_image_documents

        base, manifest_path, original_hash = self.build_relative_manifest()
        previous = os.getcwd()
        elsewhere = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, elsewhere, True)
        os.chdir(elsewhere)
        try:
            result = run_pdf_extraction(manifest_path, "invoice.pdf")
            extraction_path = next(Path(entry["path"]) for entry in
                                   json.loads(manifest_path.read_text(encoding="utf-8"))["derived_files"]
                                   if entry["role"] == "reviewed_extraction")
        finally:
            os.chdir(previous)
        self.assertTrue(extraction_path.is_relative_to((base / "work").resolve()))
        plan = {"document_type": "travel", "amount_rules": {"costs": "sum", "cost_amount_semantics": "line_total"},
                "tables": {"costs": [{"row_id": "c0", "fields": {"cost": "128.70"}}]}}
        materials = {"image_documents": [{"original_sha256": original_hash, "kind": "invoice",
                                          "extraction_path": str(extraction_path),
                                          "extraction_sha256": file_hash(extraction_path),
                                          "records": [{"record_id": "invoice-1",
                                                       "allocations": [{"plan_pointer": "/tables/costs/0/fields/cost",
                                                                        "amount": "128.70"}]}]}]}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(validate_image_documents(materials, manifest, plan, base_dir=base), [])


class D18MatrixTests(W03TestCase):
    """D18 离线矩阵补行（round-9 / ctr-15712bcb §2）：对应任务 §3 三行矩阵条目。

    合成件明示测试用；已有反例（金额不闭合/丢精度 gap/复核否决）不在此重复，
    由原测试继续守。数值保真要求在提取→事实→计划三段不丢。
    """

    @staticmethod
    def _pdf_pages(path, pages):
        import fitz

        document = fitz.open()
        for lines in pages:
            page = document.new_page(width=595, height=842)
            for offset, text in lines:
                page.insert_text((72, offset), text, fontname="china-s", fontsize=11)
        document.save(path)
        document.close()

    def test_d18_pdf_multipage_page_anchors(self):
        # 【D18 矩阵条目 §3-1 PDF/图片变体·多页 PDF 逐页锚点】票面要素跨页分布时，
        # 每个事实的页/区域锚点必须指向真实所在页，端到端复核回锚原始行。
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "multipage-invoice.pdf"
        self._pdf_pages(pdf_path, [
            [(90, "销售方名称：厦门某某科技有限公司"), (120, "开票日期：2026-10-20"),
             (150, "发票代码：044031900111")],
            [(180, "发票号码：00309999"), (400, "合计（不含税）￥100.00"),
             (430, "税额（小写）￥16.00"), (460, "价税合计（小写）￥116.00")]])
        facts = extract_pdf_facts(pdf_path)
        self.assertEqual(facts["facts"]["invoice_code"]["anchor"]["page"], 1)
        self.assertEqual(facts["facts"]["invoice_number"]["anchor"]["page"], 2)
        self.assertEqual(facts["facts"]["total_amount"]["anchor"]["page"], 2)
        self.assertTrue(facts["closure"]["closed"])
        self.assertEqual(facts["closure"]["total"], "116.00")
        self.assertEqual({item["page"] for item in facts["lines"]}, {1, 2})
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        shutil.copy(pdf_path, originals / "multipage-invoice.pdf")
        manifest_path = prepare_dual_materials(originals, Path(temporary.name) / "work")
        result = run_pdf_extraction(manifest_path, "multipage-invoice.pdf")
        fields = result["payload"]["records"][0]["fields"]
        self.assertTrue(fields["invoice_number"]["locator"].startswith("page:2/region:"))
        self.assertTrue(fields["invoice_code"]["locator"].startswith("page:1/region:"))
        self.assertEqual(fields["invoice_number"]["value"], "00309999")

    def test_d18_pdf_one_page_two_invoices_pins_single_record_contract(self):
        # 【D18 矩阵条目 §3-1 PDF/图片变体·一页多票】【R10 §1 显式拒绝】一票一件契约：
        # 同一文件 ≥2 互异发票身份 → GAP 登记（candidates 双值、不拆分不并票），
        # 该文件拒绝作为单票证据；事实层维持首匹配、第二票值不得混入事实/闭合，
        # 第二票原文仍在原始层供人工核。单票文件（invoice.pdf）零身份 GAP 不回归。
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        pdf_path = Path(temporary.name) / "two-on-one.pdf"
        self._pdf_pages(pdf_path, [[
            (90, "销售方名称：厦门某某科技有限公司"), (120, "开票日期：2026-10-20"),
            (150, "发票代码：044031900111"), (180, "发票号码：00301111"),
            (400, "合计（不含税）￥100.00"), (430, "税额（小写）￥16.00"),
            (460, "价税合计（小写）￥116.00"),
            (520, "销售方名称：厦门另一家科技有限公司"), (550, "开票日期：2026-10-21"),
            (580, "发票代码：044031900222"), (610, "发票号码：00302222"),
            (640, "合计（不含税）￥200.00"), (670, "税额（小写）￥32.00"),
            (700, "价税合计（小写）￥232.00")]])
        facts = extract_pdf_facts(pdf_path)
        self.assertEqual(facts["facts"]["invoice_number"]["value"], "00301111")
        self.assertNotIn("00302222", json.dumps(facts["facts"], ensure_ascii=False))
        self.assertNotIn("232.00", json.dumps(facts["closure"], ensure_ascii=False))
        self.assertTrue(facts["closure"]["closed"])  # 闭合只反映首票三金额
        self.assertEqual(facts["closure"]["total"], "116.00")
        self.assertTrue(any("00302222" in item["text"] for item in facts["lines"]))
        # R10：多票身份 GAP 显式登记（号码+代码双身份各自登记）
        gaps = facts["gaps"]
        self.assertEqual(len(gaps), 2)
        for gap in gaps:
            self.assertEqual(set(gap), set(GAP_FIELDS))
            self.assertEqual(gap["affected_rows"], ["invoice-1"])
            self.assertIn("不拆分", gap["reason"])
        by_candidates = {tuple(gap["candidates"]) for gap in gaps}
        self.assertIn(("00301111", "00302222"), by_candidates)
        self.assertIn(("044031900111", "044031900222"), by_candidates)
        # 端到端：gaps 随 reviewed payload 落盘（人工/下游可见拒绝证据）
        originals = Path(temporary.name) / "originals"
        originals.mkdir()
        shutil.copy(pdf_path, originals / "two-on-one.pdf")
        manifest_path = prepare_dual_materials(originals, Path(temporary.name) / "work")
        result = run_pdf_extraction(manifest_path, "two-on-one.pdf")
        strip_file = lambda items: [{k: v for k, v in gap.items() if k != "file"} for gap in items]
        self.assertEqual(strip_file(result["gaps"]), strip_file(gaps))
        self.assertEqual(strip_file(result["payload"]["gaps"]), strip_file(gaps))
        # 单票不回归：fixture invoice.pdf 无身份 GAP
        single = extract_pdf_facts(self.fixtures / "invoice.pdf")
        self.assertFalse([gap for gap in single["gaps"] if "发票身份" in gap["reason"]])
        self.assertTrue(single["closure"]["closed"])

    def test_d18_excel_multisheet_formula_hidden_filter_summary(self):
        # 【D18 矩阵条目 §3-2 Excel 变体】多 sheet 并存 + 公式取值（可重算/不可重算）
        # + 汇总/明细跨表候选（含不匹配候选如实记 False）+ 隐藏行/筛选态：
        # 隐藏行金额仍计入 SUM 区间与明细合计（隐藏≠排除，语义钉板）。
        from openpyxl import Workbook

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "multisheet.xlsx"
        workbook = Workbook()
        a = workbook.active
        a.title = "明细A"
        a.append(["日期", "事由", "金额"])
        a.append(["2026-10-01", "市内交通", 10.00])
        a.append(["2026-10-02", "城际车票", 6.00])
        a.append(["2026-10-03", "住宿", 100.00])
        a.append(["2026-10-04", "杂费", 0.10])
        a.row_dimensions[4].hidden = True
        a.auto_filter.ref = "A1:C5"
        b = workbook.create_sheet("明细B")
        b.append(["日期", "事由", "金额"])
        b.append(["2026-10-01", "打印", 25.00])
        b.append(["2026-10-02", "装订", 25.00])
        summary = workbook.create_sheet("汇总")
        summary["A1"] = "合计"
        summary["B1"] = "=SUM(明细A!C2:C5)"  # 区间含隐藏行 4
        lookup = workbook.create_sheet("复杂")
        lookup["A1"] = "查找"
        lookup["B1"] = '=VLOOKUP("市内交通",明细A!A2:C5,3,FALSE)'
        workbook.save(path)
        result = extract_workbook(path)
        sheets = result["sheets"]
        self.assertEqual(set(sheets), {"明细A", "明细B", "汇总", "复杂"})
        self.assertEqual(sheets["明细A"]["hidden_rows"], [4])
        self.assertEqual(sheets["明细A"]["autofilter"]["ref"], "A1:C5")
        formulas = {formula["ref"]: formula for sheet in sheets.values() for formula in sheet["formula_cells"]}
        self.assertEqual(formulas["汇总!B1"]["resolution"], "recomputed")
        self.assertEqual(Decimal(formulas["汇总!B1"]["resolved"]), Decimal("116.10"))  # 含隐藏行 100.00
        self.assertEqual(formulas["复杂!B1"]["resolution"], "gap")
        gap_entry = next(entry for entry in result["gaps"] if entry["locator"] == "复杂!B1")
        self.assertEqual(set(gap_entry), set(GAP_FIELDS))
        candidates = {(c["candidate_detail_sheet"], c["amount_match"]) for c in result["summary_candidates"]}
        self.assertIn(("明细A", True), candidates)   # 汇总=明细A（含隐藏行）
        self.assertIn(("明细B", False), candidates)  # 不匹配候选如实 False，不静默丢
        for candidate in result["summary_candidates"]:
            self.assertIn("候选关系", candidate["note"])

    def test_d18_numeric_fidelity_leading_zero_long_account_decimal(self):
        # 【D18 矩阵条目 §3-3 数值保真】前导零票号/账号、19 位长账号、金额 Decimal
        # 0.005 级精度：提取→FactSet→计划三段不丢、不浮点污染、不静默舍入。
        from openpyxl import Workbook
        from bpm.facts import FactSet, reconcile
        from test_bpm_new_types import build_type_plan, refresh_type_proofs

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "banks.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "收款"
        sheet.append(["收款人", "账号", "金额"])
        sheet.append(["张三", "0012345678901234567", 0.10])  # 前导零+19 位：必须文本
        sheet.append(["李四", "6222020200112233445", 0.20])
        workbook.save(path)
        # 段1 提取：文本原值、无科学计数、无浮点尾数、无精度缺口
        result = extract_workbook(path)
        cells = result["sheets"]["收款"]["cells"]
        self.assertEqual(cells["B2"]["value"], "0012345678901234567")
        self.assertEqual(cells["B2"]["kind"], "text")
        self.assertEqual(cells["B3"]["value"], "6222020200112233445")
        dump = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("E+", dump)
        self.assertNotIn("0.30000000000004", dump)
        self.assertEqual(result["gaps"], [])
        # 段2 事实：Decimal 精确闭合；0.005 级差额必须被阻断而非舍入吞掉
        facts = FactSet(business_ref="d18-fidelity")
        expenses = [facts.add_expense("0.1" if index == 0 else "0.2", source="material_extraction",
                                      layer="detail", category="合成",
                                      locator="d18#/tables/details/{0}".format(index))
                    for index in range(2)]
        for expense in expenses:
            facts.add_no_invoice_basis(expense, reason="离线合成免票（明示测试用）",
                                       source="user_instruction", locator="d18#/no_invoice_rule")
        for index, (name, account) in enumerate((("张三", "0012345678901234567"),
                                                 ("李四", "6222020200112233445"))):
            facts.add_payee(name=name, account=account, branch="测试银行", interbank="001234",
                            amount="0.1" if index == 0 else "0.2", source="material_extraction",
                            locator="d18#/tables/banks/{0}".format(index))
        facts.add("total", source="deterministic_computation", value={"amount": "0.3"},
                  locator="derived:total#details-sum", derivation="0.10+0.20 Decimal 求和")
        self.assertFalse(reconcile(facts).blocked)
        wrong = FactSet(business_ref="d18-fidelity")
        for index in range(2):
            fact = wrong.add_expense("0.1" if index == 0 else "0.2", source="material_extraction",
                                     layer="detail", category="合成", locator="d18#/x{0}".format(index))
            wrong.add_no_invoice_basis(fact, reason="离线合成免票（明示测试用）",
                                       source="user_instruction", locator="d18#/no_invoice_rule")
        wrong.add("total", source="deterministic_computation", value={"amount": "0.305"},
                  locator="derived:total#details-sum", derivation="0.005 级差额陷阱")
        self.assertTrue(reconcile(wrong).blocked)  # 0.305≠0.30：半分级差额被拦
        # 段3 计划：前导零/长账号进 banks 原样校验；0.005 级总额在 validate_plan 被拒
        plan, plan_path = build_type_plan(Path(temporary.name) / "plan", "express",
                                          empty_costs=True)
        plan["header"]["totalCost"] = "0.30"
        plan["tables"]["details"][0]["fields"]["cost"] = "0.30"
        plan["tables"]["banks"][0]["fields"].update(account="0012345678901234567", cost="0.10")
        plan["tables"]["banks"].append({"row_id": "b1", "fields": dict(
            plan["tables"]["banks"][0]["fields"], account="6222020200112233445", cost="0.20")})
        refresh_type_proofs(plan, plan_path)
        self.assertEqual(validate_plan(plan), [])
        bad = copy.deepcopy(plan)
        bad["header"]["totalCost"] = "0.305"
        self.assertTrue(validate_plan(bad))


if __name__ == "__main__":
    unittest.main()
