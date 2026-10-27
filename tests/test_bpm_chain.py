"""Round-10（ctr-8cb7b247 §3）bpm_chain 链产品化测试：入口参数/链产物 schema/失败段。

三个必测面：
1. 入口参数——rd_materials 无家族构建器显式拒绝、缺参数 argparse 报错，均不落任何文件；
2. 链产物 schema——真实跑一条 welfare_labor 合成离线链（含真实 fill_once
   --validate-only 子进程），断言 events 分段/P2-2 零 kind=user/计划过 schema 与
   validate_plan/P2-3 回退操作人留 operator_note；
3. 失败段——金额闭合破坏的材料复跑，非零退出 + plan_generation_failed 事件 + 无计划产物。

合成材料明示 synthetic/test_only，不入业务 manifest；链为 validate-only，不触碰浏览器。
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R9_WELFARE = ROOT / "automation/runs/20261024-194500-welfareloop"
MATERIAL = R9_WELFARE / "originals/synthetic_welfare_r9.json"
SNAPSHOT = R9_WELFARE / "template_snapshot.json"


def _chain_argv(run_dir, material=MATERIAL, operator_fallback="链测试操作人"):
    return ["--material", str(material), "--document-type", "welfare_labor",
            "--run-dir", str(run_dir), "--template-snapshot", str(SNAPSHOT),
            "--template-number", "15426071883", "--round", "10",
            # 会话记录指向不存在文件：测试不依赖本机登录态，走显式回退（P2-3 注记路径）
            "--session-record", str(Path(run_dir).parent / "missing-session.json"),
            "--operator-fallback", operator_fallback]


def _run_cli(argv):
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "bpm_chain.py"), *argv],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", timeout=300)


class ChainEntryTests(unittest.TestCase):
    def test_rd_materials_rejected_without_family_builder_and_no_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "rd-run"
            completed = _run_cli(["--material", str(MATERIAL), "--document-type", "rd_materials",
                                  "--run-dir", str(run_dir), "--template-snapshot", str(SNAPSHOT),
                                  "--template-number", "15426104120", "--round", "10"])
            self.assertEqual(completed.returncode, 2)
            self.assertIn("CHAIN_FAMILY_NOT_IMPLEMENTED", completed.stdout)
            self.assertFalse(run_dir.exists(), "入口拒绝不得创建 run 目录")

    def test_missing_required_argument_is_argparse_error(self):
        completed = _run_cli(["--document-type", "welfare_labor"])  # 缺 material 等必选参数
        self.assertEqual(completed.returncode, 2)
        self.assertIn("usage:", completed.stderr)


class ChainArtifactSchemaTests(unittest.TestCase):
    """真实链复跑（含 validate-only 子进程）+ 链产物 schema 与 P2 折入断言。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.tmp.name) / "welfare-chain"
        completed = _run_cli(_chain_argv(cls.run_dir))
        assert completed.returncode == 0, completed.stdout + completed.stderr
        cls.completed = completed

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_events_segments_and_kind_user_guard(self):
        events = [json.loads(line) for line in
                  (self.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
        names = [item["event"] for item in events]
        # round-9 分段标记：新 run 首段 segment=1；链各阶段事件齐备
        self.assertEqual(events[0]["event"], "chain_segment_start")
        self.assertEqual(events[0]["segment"], 1)
        self.assertEqual(events[0]["chain_tool"], "bpm_chain")
        for stage in ("operator_resolved", "prepare_dual_materials", "register_request",
                      "template_bound", "agent_extraction_review", "factset_built", "reconcile",
                      "reuse_matrix", "blueprint_assembled", "kind_user_guard", "plan_ready",
                      "execution_ready", "chain_result"):
            self.assertIn(stage, names, stage)
        guard = events[names.index("kind_user_guard")]
        # P2-2：合成链（synthetic=true）零 kind=user
        self.assertTrue(guard["synthetic"])
        self.assertEqual(guard["user_kind_sources"], 0)

    def test_plan_schema_and_p2_folds(self):
        import jsonschema
        plan = json.loads((self.run_dir / "fill_plan.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "automation/fill-plan.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(plan, schema)   # 链产物符合 v1.0 契约 schema
        self.assertEqual(plan["document_type"], "welfare_labor")
        # P2-2：免票依据与空表理由 proof.kind 均为 material（合成不冒充 user）
        for pointer, source in plan["sources"].items():
            self.assertNotEqual(source.get("kind"), "user",
                                "合成链出现 kind=user: {0}".format(pointer))
        for row in plan["materials"]["no_invoice_rows"]:
            self.assertEqual(row["proof"]["kind"], "material")
        # P2-4（自主裁决①）：test_context 精确四键保留，authorization_path=材料工件路径
        self.assertEqual(set(plan["test_context"]),
                         {"purpose", "round", "authorization_path", "authorization_sha256"})
        self.assertTrue(plan["test_context"]["authorization_path"].startswith("originals/"))
        result = json.loads((self.run_dir / "chain_result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "CHAIN_COMPLETE")
        self.assertFalse(result["browser_launched"])
        self.assertIn("P2-4", result["test_context_semantics"])

    def test_execution_ready_with_operator_note(self):
        readiness = json.loads((self.run_dir / "execution_ready.json").read_text(encoding="utf-8"))
        # 真实 validate-only 子进程全绿 + P2-3 回退操作人注记
        self.assertEqual(readiness["status"], "EXECUTION_READY")
        self.assertFalse(readiness["browser_launched"])
        self.assertEqual(readiness["operator"]["name"], "链测试操作人")
        self.assertIn("--expect-name \"链测试操作人\"", readiness["suggested_command"])
        events = [json.loads(line) for line in
                  (self.run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        operator_event = next(item for item in events if item["event"] == "operator_resolved")
        self.assertFalse(operator_event["measured"])
        self.assertIn("S1 实测登录值", operator_event["operator_note"])


class ChainFailureSegmentTests(unittest.TestCase):
    def test_broken_closure_leaves_plan_generation_failed_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            material = Path(tmp) / "broken_material.json"
            payload = json.loads(MATERIAL.read_text(encoding="utf-8"))
            payload["header"]["totalCost"] = "9999.99"   # 破坏金额闭合（其余不动）
            material.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            run_dir = Path(tmp) / "broken-chain"
            completed = _run_cli(_chain_argv(run_dir, material=material))
            self.assertEqual(completed.returncode, 1)
            events = [json.loads(line) for line in
                      (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            failed = [item for item in events if item["event"] == "plan_generation_failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0]["code"], "CHAIN_AMOUNT_CLOSURE_BROKEN")
            self.assertEqual(failed[0]["stage"], "agent_extraction_review")
            self.assertFalse((run_dir / "fill_plan.json").exists(), "失败链不得留计划产物")
            result = json.loads((run_dir / "chain_result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "CHAIN_FAILED")


if __name__ == "__main__":
    unittest.main()
