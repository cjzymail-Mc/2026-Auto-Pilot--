"""skill 文档结构化校验（W06 第2条）：.claude/skills/bpm-fill-run 增补后离线可验。

覆盖：frontmatter 可解析与路由关键词、references 链接完整性、命令示例引用的
脚本/旗标真实存在、新链路六阶段与函数名在场、保存/授权红线文字逐字不动。
"""
import importlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / ".claude" / "skills" / "bpm-fill-run"
SKILL = SKILL_DIR / "SKILL.md"

# 增补前既有红线文字（round-6 合同：逐字不动）
AUTHORIZATION_SECTION = """## 授权与保存

默认 `fill_only`。只有用户对本具体任务明确要求保存，计划中有同 task_id 的 `save_draft` 授权，才进入 `SaveController`。普通 `_click_guard` 仍禁止“保存”；专用控制器在新单、身份、来源/配置/计划哈希、完整回读、终局截图及点击前复核通过后，仅允许一次精确“保存”。保存后必须取得唯一单号/UUID、确认未提交，重新打开并逐项核对，才能报告 `SUCCESS_DRAFT_SAVED`。

保存并提交、发送、提交、流转、审批、暂存、贴票和上传始终不在本任务范围；禁止直接写接口、放宽通用守卫、自动确认未知对话框。`SAVE_UNCERTAIN` 立即转只读核实。"""

PROFILE_REDLINE = "- `automation/.pw-profile/` 含活体 token，不复制进 git、日志、材料清单或报告。Windows 判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。"

CHAIN_STAGES = ("请求登记", "模板决策", "原件理解", "事实与对账", "执行就绪")
CHAIN_FUNCTIONS = ("register_request", "resolve_template", "build_reuse_matrix",
                   "entries_from_matrix", "execution_ready", "operator_from_session_record")

# SKILL.md/references 命令示例引用的脚本旗标 → 必须出现在对应源码/文件
SCRIPT_FLAGS = {
    "fill_once.py": ["--task", "--fill-plan", "--expect-name", "--validate-only",
                     "--keep-open-minutes", "--resume-run", "--legacy-regression"],
    "bpm_template.py": ["--census", "--live", "--template-number", "--output",
                        "--expect-name", "--login-wait"],
}
SCRIPT_IMPLEMENTATIONS = {"fill_once.py": "bpm.fill_cli", "bpm_template.py": "bpm.template"}
SCRIPT_FILES = ("bpm_login.py", "stage1_browser_probe.py", "stage1_probe_selftest.py",
                "verify_bpm_build.py")


class SkillDocsTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")

    def test_skill_file_and_frontmatter(self):
        self.assertTrue(SKILL.is_file(), "SKILL.md 必须存在")
        match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", self.text, re.DOTALL)
        self.assertIsNotNone(match, "frontmatter 起止 --- 成对")
        front = match.group(1)
        name = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
        desc = re.search(r"^description:\s*(.+)$", front, re.MULTILINE)
        self.assertIsNotNone(name)
        self.assertEqual(name.group(1), SKILL_DIR.name, "frontmatter name 与目录名一致")
        self.assertIsNotNone(desc)
        self.assertGreater(len(desc.group(1).strip()), 20, "description 非空")

    def test_description_routes_new_chain(self):
        match = re.search(r"^description:\s*(.+)$", self.text, re.MULTILINE)
        for keyword in ("模板单号", "执行就绪", "链路"):
            self.assertIn(keyword, match.group(1),
                          "路由描述需含新链路关键词: {0}".format(keyword))

    def test_reference_links_resolve_inside_skill(self):
        links = re.findall(r"\]\((references/[^)#\s]+\.md)\)", self.text)
        self.assertGreaterEqual(len(links), 5)
        for link in links:
            target = (SKILL_DIR / link).resolve()
            self.assertTrue(str(target).startswith(str(SKILL_DIR.resolve())),
                            "引用必须落在 skill 目录内: {0}".format(link))
            self.assertTrue(target.is_file(), "引用文件必须存在: {0}".format(link))

    def test_command_examples_reference_real_scripts_and_flags(self):
        for script, flags in SCRIPT_FLAGS.items():
            self.assertTrue((ROOT / script).is_file(), script)
            implementation = importlib.import_module(SCRIPT_IMPLEMENTATIONS[script])
            source = Path(implementation.__file__).read_text(encoding="utf-8")
            for flag in flags:
                self.assertIn('"{0}"'.format(flag), source,
                              "{0} 未声明 {1}（命令示例不得虚构旗标）".format(script, flag))
        for script in SCRIPT_FILES:
            self.assertTrue((ROOT / script).is_file(), "命令示例引用的脚本必须存在: {0}".format(script))

    def test_new_chain_section_and_stages(self):
        self.assertIn("## 完整链路：模板单号+原始资料 → 执行就绪", self.text)
        for stage in CHAIN_STAGES:
            self.assertIn(stage, self.text, "新链路阶段语义必须在场: {0}".format(stage))
        for function in CHAIN_FUNCTIONS:
            self.assertIn(function, self.text, "新链路函数指引必须在场: {0}".format(function))

    def test_chain_functions_exist_in_code(self):
        source = (ROOT / "bpm/request.py").read_text(encoding="utf-8")
        for function in CHAIN_FUNCTIONS:
            self.assertIn("def {0}(".format(function), source,
                          "skill 指引的函数必须真实存在: {0}".format(function))

    def test_full_chain_reference_document(self):
        doc = SKILL_DIR / "references" / "full-chain.md"
        self.assertTrue(doc.is_file(), "full-chain.md 参考必须存在")
        body = doc.read_text(encoding="utf-8")
        for stage in CHAIN_STAGES:
            self.assertIn(stage, body)
        self.assertIn("--validate-only", body)
        self.assertIn("operator_from_session_record", body)
        self.assertIn("user_policy", body)
        self.assertIn("系统观察", body)
        self.assertIn("模板历史", body)

    def test_authorization_redline_text_untouched(self):
        self.assertIn(AUTHORIZATION_SECTION, self.text, "授权与保存红线段必须逐字保留")

    def test_profile_and_environment_redlines_untouched(self):
        self.assertIn(PROFILE_REDLINE, self.text, ".pw-profile 红线句必须逐字保留")
        for section in ("## 执行与恢复", "## 环境与交付"):
            self.assertIn(section, self.text)


if __name__ == "__main__":
    unittest.main()
