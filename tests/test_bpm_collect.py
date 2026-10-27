# -*- coding: utf-8 -*-
"""bpm_collect 单元测试（BPM-SELFDRIVE-20261027-V1 R2 D04）。

合成 PDF（fitz 文本层）覆盖：页分类、身份去重/不合并、多页拆分、同页多票 GAP、
无文本层 GAP、缺字段占位、汇总单交叉核对、幂等重跑、防覆盖。
不读真实材料目录（真实 73 件归集由 run 脚本落 automation/runs/<run>/collect/）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # PyMuPDF

import bpm.collect as bpm_collect
from bpm.collect import (CLASS_FUEL_INVOICE, CLASS_SUMMARY_BY_TICKET,
                         CLASS_SUMMARY_BY_TRIP, CLASS_TOLL_INVOICE,
                         CLASS_UNKNOWN, CollectionError, classify_page_text,
                         collect_materials, cross_check_summaries)

TOLL_LINES = ["福建增值税电子普通发票", "发票号码：00301256001123456789",
              "发票代码：03512250030", "开票日期：2025年08月25日",
              "通行日期起 2025-08-25", "价税合计（小写）22.64"]
SUMMARY_LINES = ["收费公路通行费电子票据汇总单（按票据索引）", "汇总单号：3520250800404681",
                 "票据号码 00301256001123456789", "交易金额 ¥22.64"]


def make_pdf(path, pages_lines):
    """合成带嵌入文本层的 PDF：每行一个 span（与真实票据文本层同构）。"""
    doc = fitz.open()
    for lines in pages_lines:
        page = doc.new_page(width=595, height=842)
        y = 100
        for line in lines:
            page.insert_text((50, y), line, fontname="china-s", fontsize=12)
            y += 24
    doc.save(str(path))
    doc.close()


def toll_lines(number="00301256001123456789", date="2025年08月25日", total="22.64"):
    return ["福建增值税电子普通发票", "发票号码：{0}".format(number),
            "发票代码：03512250030", "开票日期：{0}".format(date),
            "通行日期起 2025-08-25", "价税合计（小写）{0}".format(total)]


class ClassifyTests(unittest.TestCase):
    def test_classify_variants(self):
        self.assertEqual(classify_page_text("\n".join(SUMMARY_LINES)), CLASS_SUMMARY_BY_TICKET)
        trip = SUMMARY_LINES[:1] + ["（按行程索引）", "汇总单号：3520250800404681", "交易金额 ¥22.64"]
        self.assertEqual(classify_page_text("\n".join(trip)), CLASS_SUMMARY_BY_TRIP)
        self.assertEqual(classify_page_text("\n".join(toll_lines())), CLASS_TOLL_INVOICE)
        fuel = ["成品油", "电子发票（普通发票）", "发票号码：25357000000191876369",
                "开票日期：2025年12月01日", "价税合计（小写）200.00"]
        self.assertEqual(classify_page_text("\n".join(fuel)), CLASS_FUEL_INVOICE)
        self.assertEqual(classify_page_text("随便一张说明纸"), CLASS_UNKNOWN)

    def test_route_stem_strips_suffix(self):
        self.assertEqual(bpm_collect._route_from_stem("0825厦门到晋江发票"), "厦门到晋江")
        self.assertEqual(bpm_collect._route_from_stem("1210晋江-厦门1"), "晋江到厦门")
        self.assertEqual(bpm_collect._route_from_stem("油票1"), "")


class CollectCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="collect-test-"))
        self.materials = self.tmp / "materials"
        self.out = self.tmp / "out"

    def test_single_toll_invoice_identity_and_copy(self):
        (self.materials / "0825").mkdir(parents=True)
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf", [toll_lines()])
        manifest = collect_materials(self.materials, self.out)
        self.assertEqual(len(manifest["identities"]), 1)
        record = manifest["identities"][0]
        self.assertEqual(record["class"], CLASS_TOLL_INVOICE)
        self.assertEqual(record["issue_date"], "2025-08-25")
        self.assertEqual(record["face_total"], "22.64")
        self.assertTrue(record["record_id"].startswith("inv-"))
        self.assertEqual(len(record["record_id"]), 12)
        self.assertEqual(record["copy_name"],
                         "20250825_通行费发票_厦门到晋江_00301256001123456789_{0}.pdf".format(
                             record["record_id"][4:]))
        copy_path = self.out / "collected" / record["copy_name"]
        self.assertTrue(copy_path.is_file())
        self.assertEqual(copy_path.read_bytes(),
                         (self.materials / "0825" / "0825厦门到晋江发票.pdf").read_bytes())
        # 可逆映射：文件 → 身份 → 副本
        entry = manifest["files"][0]
        self.assertEqual(entry["identities"], ["00301256001123456789"])
        self.assertEqual(entry["copy"], record["copy_name"])
        self.assertEqual(manifest["gaps"], [])

    def test_duplicate_scan_same_identity_merges(self):
        (self.materials / "1210").mkdir(parents=True)
        make_pdf(self.materials / "1210" / "1210晋江-厦门1.pdf", [toll_lines()])
        make_pdf(self.materials / "1210" / "1210晋江-厦门1 (2).pdf", [toll_lines()])
        manifest = collect_materials(self.materials, self.out)
        self.assertEqual(len(manifest["identities"]), 1)
        self.assertEqual(len(manifest["identities"][0]["scans"]), 2)
        copies = list((self.out / "collected").iterdir())
        self.assertEqual(len(copies), 1)   # 重复扫描不产生第二副本
        files_by_rel = {f["rel"]: f for f in manifest["files"]}
        self.assertEqual(files_by_rel["1210/1210晋江-厦门1.pdf"]["copy"],
                         files_by_rel["1210/1210晋江-厦门1 (2).pdf"]["copy"])

    def test_same_amount_different_numbers_not_merged(self):
        (self.materials / "0825").mkdir(parents=True)
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf",
                 [toll_lines(number="00301256001111111111")])
        make_pdf(self.materials / "0825" / "0825晋江到厦门发票.pdf",
                 [toll_lines(number="00301256002222222222")])
        manifest = collect_materials(self.materials, self.out)
        self.assertEqual(len(manifest["identities"]), 2)   # 金额相同不合并，身份优先

    def test_identity_face_conflict_reported(self):
        (self.materials / "1210").mkdir(parents=True)
        make_pdf(self.materials / "1210" / "1210晋江-厦门1.pdf", [toll_lines(total="22.64")])
        make_pdf(self.materials / "1210" / "1210晋江-厦门1 (2).pdf", [toll_lines(total="30.00")])
        manifest = collect_materials(self.materials, self.out)
        kinds = [gap["gap"] for gap in manifest["gaps"]]
        self.assertIn("identity_face_conflict", kinds)   # 差异如实列报，不改判

    def test_multi_page_file_splits_per_page(self):
        (self.materials / "1204").mkdir(parents=True)
        make_pdf(self.materials / "1204" / "1204两票合一.pdf",
                 [toll_lines(number="00301256003333333333"),
                  toll_lines(number="00301256004444444444", date="2025年12月05日")])
        manifest = collect_materials(self.materials, self.out)
        numbers = {r["number"] for r in manifest["identities"]}
        self.assertEqual(numbers, {"00301256003333333333", "00301256004444444444"})
        for record in manifest["identities"]:
            self.assertEqual(record["scans"][0]["file"], "1204/1204两票合一.pdf")
            self.assertIn("page:", record["scans"][0]["locator"])
        self.assertEqual(len(list((self.out / "collected").iterdir())), 2)

    def test_multi_identity_single_page_is_gap(self):
        (self.materials / "1204").mkdir(parents=True)
        both = toll_lines(number="00301256005555555555") + ["发票号码：00301256006666666666"]
        make_pdf(self.materials / "1204" / "1204同页两票.pdf", [both])
        manifest = collect_materials(self.materials, self.out)
        self.assertEqual(manifest["identities"], [])   # 同页多票不拆，整页 GAP
        kinds = [gap["gap"] for gap in manifest["gaps"]]
        self.assertIn("multi_identity_single_page", kinds)

    def test_no_text_page_needs_visual_review(self):
        (self.materials / "0904").mkdir(parents=True)
        doc = fitz.open()
        doc.new_page()   # 空白页：无文本层
        doc.save(str(self.materials / "0904" / "0904扫描图.pdf"))
        doc.close()
        manifest = collect_materials(self.materials, self.out)
        kinds = [gap["gap"] for gap in manifest["gaps"]]
        self.assertIn("needs_visual_review", kinds)
        self.assertEqual(manifest["identities"], [])

    def test_missing_date_placeholder_and_gap(self):
        (self.materials / "0906").mkdir(parents=True)
        lines = [line for line in toll_lines() if not line.startswith("开票日期")]
        make_pdf(self.materials / "0906" / "0906(x0905文件)厦门到晋江发票.pdf", [lines])
        manifest = collect_materials(self.materials, self.out)
        record = manifest["identities"][0]
        self.assertEqual(record["issue_date"], "")
        self.assertTrue(record["copy_name"].startswith("无日期_"))
        kinds = [gap["gap"] for gap in manifest["gaps"]]
        self.assertIn("issue_date_missing", kinds)

    def test_no_route_segment_omitted(self):
        (self.materials / "油票").mkdir(parents=True)
        make_pdf(self.materials / "油票" / "油票1.pdf",
                 [["成品油", "电子发票（普通发票）", "发票号码：25357000000191876369",
                   "开票日期：2025年12月01日", "价税合计（小写）200.00"]])
        manifest = collect_materials(self.materials, self.out)
        copy_name = manifest["identities"][0]["copy_name"]
        self.assertTrue(copy_name.startswith("20251201_油票_25357000000191876369_"))
        self.assertNotIn("到", copy_name)   # 方向缺失省略该段，不猜值

    def test_non_pdf_material_mapped_without_copy(self):
        self.materials.mkdir(parents=True)
        (self.materials / "12月-自驾公出公里数统计表.xlsx").write_bytes(b"fake-xlsx")
        make_pdf(self.materials / "0825厦门到晋江发票.pdf", [toll_lines()])
        manifest = collect_materials(self.materials, self.out)
        entry = {f["rel"]: f for f in manifest["files"]}["12月-自驾公出公里数统计表.xlsx"]
        self.assertEqual(entry["kind"], "non_pdf_material")
        self.assertIsNone(entry["copy"])
        copies = list((self.out / "collected").iterdir())
        self.assertEqual(len(copies), 1)   # 只有发票产副本


class ColumnarLayoutTests(unittest.TestCase):
    """真实通行费发票版式回归：标签/值分行分 span，靠几何行绑定（2026-10-27 D04 实测版式）。"""

    def test_columnar_label_value_binding(self):
        tmp = Path(tempfile.mkdtemp(prefix="collect-col-"))
        (tmp / "materials" / "0825").mkdir(parents=True)
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        rows = [
            (432, 30, "发票代码:"), (490, 30, "035002400112"),
            (432, 44, "发票号码:"), (490, 44, "16304714"),
            (432, 58, "开票日期:"), (490, 58, "2025年08月26日"),
            (432, 72, "校验码:"),  (490, 72, "04536 86912 96402 57294"),
            (50, 120, "福建增值税电子普通发票"),
            (50, 150, "通行日期起 20250825"),
            (439, 264, "￥21.98"), (563, 264, "￥0.66"),
            (458, 284, "（小写）"), (505, 284, "￥22.64"),
        ]
        for x, y, text in rows:
            page.insert_text((x, y), text, fontname="china-s", fontsize=9.5)
        doc.save(str(tmp / "materials" / "0825" / "0825厦门到晋江发票.pdf"))
        doc.close()
        manifest = collect_materials(tmp / "materials", tmp / "out")
        self.assertEqual(len(manifest["identities"]), 1)
        record = manifest["identities"][0]
        self.assertEqual(record["number"], "16304714")
        self.assertEqual(record["code"], "035002400112")
        self.assertEqual(record["issue_date"], "2025-08-26")
        self.assertEqual(record["face_total"], "22.64")   # 不误绑合计行 21.98（不同视觉行）
        self.assertEqual(manifest["gaps"], [])


class SummaryCrossCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="collect-xcheck-"))
        self.materials = self.tmp / "materials"
        (self.materials / "0825").mkdir(parents=True)

    def test_totals_match_and_number_presence(self):
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf", [toll_lines()])
        make_pdf(self.materials / "0825" / "0825通行费电子票据汇总单(票据).pdf", [SUMMARY_LINES])
        make_pdf(self.materials / "0825" / "0825通行费电子票据汇总单(行程).pdf",
                 [["收费公路通行费电子票据汇总单（按行程索引）",
                   "汇总单号：3520250800404681", "交易金额 ¥22.64"]])
        manifest = collect_materials(self.materials, self.tmp / "out")
        self.assertEqual(len(manifest["summaries"]), 2)
        variants = {s["variant"] for s in manifest["summaries"]}
        self.assertEqual(variants, {CLASS_SUMMARY_BY_TICKET, CLASS_SUMMARY_BY_TRIP})
        results = cross_check_summaries(manifest, root=self.materials)
        result = [r for r in results if r["dir"] == "0825"][0]
        # 票据+行程双版式同 汇总单号：按单号去重后不双计，总额恰与面值互证
        self.assertEqual(result["summary_file_count"], 2)
        self.assertEqual(result["summary_number_count"], 1)
        self.assertEqual(result["summary_transaction_total"], "22.64")
        self.assertEqual(result["invoice_face_total"], "22.64")
        self.assertTrue(result["totals_match"])
        self.assertEqual(result["toll_identity_count"], 1)
        self.assertEqual(result["numbers_missing_from_summary"], [])

    def test_totals_mismatch_reported_not_raised(self):
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf", [toll_lines()])
        make_pdf(self.materials / "0825" / "0825通行费电子票据汇总单(票据).pdf",
                 [["收费公路通行费电子票据汇总单（按票据索引）",
                   "汇总单号：3520250800404681", "票据号码 00301256001123456789",
                   "交易金额 ¥30.00"]])
        manifest = collect_materials(self.materials, self.tmp / "out")
        result = cross_check_summaries(manifest, root=self.materials)[0]
        self.assertFalse(result["totals_match"])   # 差异如实列报，不抛错不改判
        self.assertEqual(result["summary_transaction_total"], "30.00")

    def test_missing_number_from_summary_listed(self):
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf", [toll_lines()])
        make_pdf(self.materials / "0825" / "0825通行费电子票据汇总单(票据).pdf",
                 [["收费公路通行费电子票据汇总单（按票据索引）",
                   "汇总单号：3520250800404681", "交易金额 ¥22.64"]])
        manifest = collect_materials(self.materials, self.tmp / "out")
        result = cross_check_summaries(manifest, root=self.materials)[0]
        self.assertEqual(result["numbers_missing_from_summary"], ["00301256001123456789"])


class DeterminismTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="collect-det-"))
        self.materials = self.tmp / "materials"
        (self.materials / "0825").mkdir(parents=True)
        make_pdf(self.materials / "0825" / "0825厦门到晋江发票.pdf", [toll_lines()])
        make_pdf(self.materials / "0825" / "0825通行费电子票据汇总单(票据).pdf", [SUMMARY_LINES])

    def test_rerun_manifest_byte_identical(self):
        first = collect_materials(self.materials, self.tmp / "out1")
        second = collect_materials(self.materials, self.tmp / "out2")
        dump1 = json.dumps(first, ensure_ascii=False, sort_keys=True)
        dump2 = json.dumps(second, ensure_ascii=False, sort_keys=True)
        self.assertEqual(dump1, dump2)   # 幂等：不同输出目录同输入 → 逐字节一致
        # 同一输出目录重跑不新增文件
        before = sorted(p.name for p in (self.tmp / "out1" / "collected").iterdir())
        collect_materials(self.materials, self.tmp / "out1")
        after = sorted(p.name for p in (self.tmp / "out1" / "collected").iterdir())
        self.assertEqual(before, after)

    def test_anti_overwrite_guard(self):
        collect_materials(self.materials, self.tmp / "out")
        copy = next((self.tmp / "out" / "collected").iterdir())
        copy.write_bytes(b"tampered")   # 目标副本被改写后内容不同
        with self.assertRaises(CollectionError):
            collect_materials(self.materials, self.tmp / "out")

    def test_write_copies_false_no_files(self):
        manifest = collect_materials(self.materials, self.tmp / "out", write_copies=False)
        self.assertEqual(len(manifest["identities"]), 1)
        self.assertFalse((self.tmp / "out" / "collected").exists())


if __name__ == "__main__":
    unittest.main()
