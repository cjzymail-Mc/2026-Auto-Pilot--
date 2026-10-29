import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from contextlib import nullcontext

from bpm.plan import file_hash, validate_plan
from bpm.oneshot import compile_authorization
from test_bpm_plan import build_valid_plan


class ExplicitHistoricalDraftTests(unittest.TestCase):
    def test_delayed_test_blueprint_installs_guard_before_first_page(self):
        from bpm.ui import StructuredProbe
        p = object.__new__(StructuredProbe)
        p.fill_plan = None
        p._preparation = {'payload': {'blueprint': {'test_context': {'purpose': 'test'}}}}
        p._timing = lambda _: nullcontext()
        p.ctx = SimpleNamespace(pages=[], new_page=MagicMock())
        p._guarded_browser = object()
        p._launch_isolated_guarded_context = MagicMock()
        p._inject_session_state = MagicMock()
        with patch('bpm.browser_probe.Probe._launch') as persistent_launch:
            p._launch()
        persistent_launch.assert_not_called()
        p._launch_isolated_guarded_context.assert_called_once()
        p._inject_session_state.assert_called_once()
        p.ctx.new_page.assert_called_once()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan, _ = build_valid_plan(self.root)
        self.plan['authorization']['mode'] = 'save_draft'
        # Update the independent source, rather than weakening source checks.
        proof = self.root / 'originals/reviewed_facts.json'
        facts = json.loads(proof.read_text(encoding='utf-8'))
        facts['header']['description'] = '测试、勿流转；历史样本测试，不作为新费用'
        proof.write_text(json.dumps(facts,ensure_ascii=False),encoding='utf-8')
        self.plan['header']['description'] = facts['header']['description']
        for source in self.plan['sources'].values():
            source['sha256'] = file_hash(proof)
        for row in self.plan['materials']['no_invoice_rows']:
            row['proof']['sha256'] = file_hash(proof)
        from test_bpm_plan import refresh_manifest
        refresh_manifest(self.root,self.plan)
        evidence = self.root / 'authorization.json'
        block = {'task_id': self.plan['task_id'], 'document_type':'travel',
                 'mode':'save_draft','allow_submit':False,'marker':'测试、勿流转',
                 'scope':'historical_sample'}
        evidence.write_text(json.dumps(dict(block,user_statement='明确授权本历史样本保存测试草稿，严禁流转'),ensure_ascii=False),encoding='utf-8')
        self.plan['test_context'] = {'purpose':'历史样本测试','round':'authorized-draft',
            'authorization_path':str(evidence),'authorization_sha256':file_hash(evidence)}
        self.plan['test_draft_authorization'] = dict(block,authorization_path=str(evidence),authorization_sha256=file_hash(evidence))

    def test_explicit_authorized_draft_passes_full_validation(self):
        self.assertEqual(validate_plan(self.plan,base_dir=self.root),[])

    def test_ordinary_test_still_rejects_save(self):
        del self.plan['test_draft_authorization']
        self.assertTrue(any('fill_only' in x['message'] for x in validate_plan(self.plan)))

    def test_wrong_task_type_marker_or_evidence_rejected(self):
        for key, value in [('task_id','different'),('document_type','express'),
                           ('allow_submit',True),('marker','测试'),
                           ('authorization_sha256','0'*64),('scope','new_expense')]:
            with self.subTest(key=key):
                plan=copy.deepcopy(self.plan)
                plan['test_draft_authorization'][key]=value
                self.assertTrue(validate_plan(plan,base_dir=self.root))
        self.plan['header']['description']='历史费用'
        self.assertTrue(validate_plan(self.plan,verify_sources=False))

    def test_compile_keeps_test_context_and_requires_specific_user_request(self):
        task={'task_id':self.plan['task_id'],'document_type':'travel',
              'authorization':dict(self.plan['authorization'],save_basis={'kind':'user_request','reference':'current explicit authorization'})}
        authorization,meta=compile_authorization(task,self.plan)
        self.assertEqual(authorization['mode'],'save_draft')
        self.assertEqual(meta['branch'],'explicit_historical_test_draft')
        self.assertIn('test_context',self.plan)
        task['synthetic']=True
        self.assertEqual(compile_authorization(task,self.plan)[0]['mode'],'fill_only')
        del task['synthetic']
        task['authorization']['save_basis']={'kind':'standing_policy','reference':'BPM-SELFDRIVE-20261027-A1'}
        self.assertEqual(compile_authorization(task,self.plan)[0]['mode'],'fill_only')
