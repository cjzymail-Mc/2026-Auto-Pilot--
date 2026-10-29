"""bpm.materials prepare CLI 离线反例：保护路径、嵌套/覆盖拒绝、随机名与重复内容、
PDF 空文本与损坏件不吞掉其余、前导零保留、prepare_summary 口径。

用匿名合成夹具（普通采购票据 PDF + 统计 XLSX 形状），不触碰任何真实业务材料；
本文件不宣称非自驾票据业务解析或真实填写已验收。"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from bpm.materials import (prepare_command, plan_pdf_text_pass, summarize_prepared,
                           inventory_materials)

XLSX_HEAD = b"PK\x03\x04"  # 仅用于构造“非 PDF 二进制”形状，不追求可解析


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


class ProtectedPathTests(unittest.TestCase):
    def test_local_session_rejected_before_enumeration(self):
        with tempfile.TemporaryDirectory() as tmp:
            protected = write(Path(tmp) / "automation" / ".local-session" / "session_record.json", "{}")
            with self.assertRaises(ValueError):
                inventory_materials(protected.parent)

    def test_pw_profile_and_git_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in (".pw-profile", ".git"):
                d = write(Path(tmp) / name / "x.json", "{}")
                with self.assertRaises(ValueError):
                    inventory_materials(d.parent)


class PrepareBoundaryTests(unittest.TestCase):
    def test_output_must_be_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = write(Path(tmp) / "src" / "a.csv", "x,y\n1,2\n")
            out = Path(tmp) / "out"
            out.mkdir()
            with self.assertRaises(ValueError):
                prepare_command(str(src.parent), str(out))

    def test_output_nested_in_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            write(src / "a.csv", "x,y\n1,2\n")
            with self.assertRaises(ValueError):
                prepare_command(str(src), str(src / "derived"))

    def test_source_nested_in_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            src = out / "src"
            write(src / "a.csv", "x,y\n1,2\n")
            with self.assertRaises(ValueError):
                prepare_command(str(src), str(out))


class PrepareContentTests(unittest.TestCase):
    def prepare(self, tmp, files):
        src = Path(tmp) / "src"
        for rel, data in files.items():
            write(src / rel, data)
        out = Path(tmp) / "derived"
        return prepare_command(str(src), str(out)), src, out

    def test_csv_leading_zeros_and_duplicates_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_text = "单号,金额\n00154,99.00\n00154,99.00\n"
            summary, src, out = self.prepare(tmp, {"a.csv": csv_text, "copy of a.csv": csv_text})
            self.assertEqual(summary["status"], "PREPARE_COMPLETE")
            self.assertEqual(summary["files"]["total"], 1)          # 内容去重
            self.assertEqual(summary["files"]["duplicates"], 1)
            parsed = json.loads((out / "parsed" / _sha_of(src, "a.csv")).read_text(encoding="utf-8"))
            values = [c["value"] for c in parsed["cells"]]
            self.assertIn("00154", values)                           # 前导零保留为字符串

    def test_random_names_and_pdf_gap_do_not_swallow_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = {
                "统计表.xlsx": XLSX_HEAD + b"\x00" * 12,             # 坏 xlsx：提取失败但盘点保留
                "随机名-0001.pdf": b"%PDF-1.4 broken",               # 损坏 PDF
                "b.csv": "x\n1\n",
            }
            summary, src, out = self.prepare(tmp, files)
            self.assertEqual(summary["files"]["total"], 3)           # 损坏件不吞掉其余
            kinds = {g["kind"] for g in summary["gaps"]}
            self.assertTrue(any(k in kinds for k in ("pdf_read_failed", "no_embedded_text", "engine_unavailable")),
                            f"损坏/无文本 PDF 应登记具体缺口，got {summary['gaps']}")
            self.assertGreaterEqual(summary["files"]["structured"] + summary["files"]["structured_needs_review"]
                                     + summary["files"]["structured_needs_input"], 3)
            self.assertTrue(summary["pending_review"])               # 需复核清单非空且点名

    def test_original_bytes_unchanged_and_manifest_dual_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, src, out = self.prepare(tmp, {"a.csv": "x\n1\n"})
            before = {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "2.0")
            self.assertNotIn(str(out), str(manifest["originals_root"]))
            after = {p: p.read_bytes() for p in src.rglob("*") if p.is_file()}
            self.assertEqual(before, after)                         # 原件字节零漂移

    def test_summary_disclaims_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, _, _ = self.prepare(tmp, {"a.csv": "x\n1\n"})
            self.assertIn("不等于事实齐备", summary["note"])
            self.assertTrue(summary["next_entries"])


class PlanPdfPassTests(unittest.TestCase):
    def test_only_pdfs_selected_with_original_hashes(self):
        files = [
            {"relative_path": "a.pdf", "sha256": "h1", "path": "/x/a.pdf"},
            {"relative_path": "b.PDF", "sha256": "h2", "path": "/x/b.PDF"},
            {"relative_path": "c.csv", "sha256": "h3", "path": "/x/c.csv"},
            {"relative_path": "d.png", "sha256": "h4", "path": "/x/d.png"},
        ]
        plan = plan_pdf_text_pass(files)
        self.assertEqual([t["relative_path"] for t in plan], ["a.pdf", "b.PDF"])
        self.assertEqual([t["sha256"] for t in plan], ["h1", "h2"])


def _sha_of(src, rel):
    from bpm.plan import file_hash
    return file_hash(src / rel) + ".json"


if __name__ == "__main__":
    unittest.main()
