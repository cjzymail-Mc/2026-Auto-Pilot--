"""Import, path and source-binding regressions for the repository layout.

CLI checks use only --help or missing-argument rejection; they never launch OA,
load credentials or acquire a production profile lock.
"""
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bpm.paths import ROOT
from tools.verification.build import CODE


ENTRIES = {
    "fill_once": "bpm.fill_cli",
    "bpm_login": "bpm.login",
    "bpm_template": "bpm.template",
    "bpm_chain": "bpm.chain",
    "stage1_browser_probe": "bpm.browser_probe",
    "verify_bpm_build": "tools.verification.build",
}


class RepositoryLayoutTests(unittest.TestCase):
    def test_compatibility_imports_share_the_actual_module(self):
        # Separate module objects would make patches, Probe subclasses and
        # runtime identity checks observe different state.
        for old, new in ENTRIES.items():
            with self.subTest(entry=old):
                self.assertIs(importlib.import_module(old), importlib.import_module(new))

    def test_auth_registry_and_configuration_paths_stay_at_the_repository_root(self):
        from bpm import browser_probe, fill_cli, plan, request, self_drive, session, template, types, ui
        self.assertEqual(ROOT, Path(__file__).resolve().parents[1])
        for value in (browser_probe.BASE, fill_cli.ROOT, plan.ROOT, request._ROOT,
                      self_drive.ROOT, session.ROOT, template.ROOT, types.ROOT, ui.ROOT):
            self.assertEqual(value, ROOT)
        self.assertEqual(browser_probe.PROFILE, ROOT / "automation/.pw-profile")
        self.assertEqual(browser_probe.SESSION_STATE,
                         ROOT / "automation/.pw-profile/session_state.json")
        self.assertEqual(session.LOCAL_ROOT, ROOT / "automation/.local-session")
        self.assertEqual(fill_cli.RUNS, ROOT / "automation/runs")
        self.assertEqual(types.resolve_type("travel").path,
                         ROOT / "automation/document-types/travel.json")

    def test_existing_help_commands_work_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            for old in ENTRIES:
                with self.subTest(entry=old):
                    result = subprocess.run(
                        [sys.executable, "-X", "utf8", str(ROOT / (old + ".py")), "--help"],
                        cwd=temporary, capture_output=True, text=True,
                        encoding="utf-8", timeout=20)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("usage:", result.stdout)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_missing_task_still_refuses_without_creating_a_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(ROOT / "fill_once.py")],
                cwd=temporary, capture_output=True, text=True,
                encoding="utf-8", timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertIn("required", result.stderr)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_manifest_covers_implementations_entry_points_and_skill_documents(self):
        expected = {path.relative_to(ROOT).as_posix()
                    for path in (ROOT / "bpm").rglob("*.py")}
        expected.update(path.relative_to(ROOT).as_posix()
                        for path in (ROOT / "tools/verification").rglob("*.py"))
        expected.update(path.relative_to(ROOT).as_posix()
                        for path in (ROOT / ".claude/skills/bpm-fill-run").rglob("*.md"))
        expected.update(old + ".py" for old in ENTRIES)
        expected.add("stage1_probe_selftest.py")
        self.assertTrue(expected.issubset(CODE), sorted(expected - set(CODE)))
        self.assertEqual(len(CODE), len(set(CODE)))
        for relative in CODE:
            self.assertTrue((ROOT / relative).is_file(), relative)
            self.assertNotIn("/before/", relative)
            self.assertNotIn(".pw-profile", relative)
            self.assertNotIn(".local-session", relative)
