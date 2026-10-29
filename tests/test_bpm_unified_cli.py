"""Offline official routing/ownership tests; no production browser is launched."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import bpm.oneshot as oneshot
import bpm.fill_cli as compat
import bpm.revision as revision
import test_bpm_revision as fixtures

class UnifiedCLITests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RevisionTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
        self.prior=self.root/'prior.json'
        # Current valid fixture is suitable for validation of prior binding;
        # its original SUCCESS journal/proof is re-bound before any operation.
        self.prior.write_text(json.dumps(self.fixture.plan,ensure_ascii=False),encoding='utf-8')
        from bpm.plan import plan_hash,file_hash
        self.fixture.proof['prior_plan_hash']=plan_hash(self.fixture.plan)
        self.original=json.loads(self.fixture.original.read_text())
        self.original['plan_hash']=self.fixture.proof['prior_plan_hash']
        self.fixture.original.write_text(json.dumps(self.original),encoding='utf-8')
        self.fixture.plan['not_applicable'].append('explicit second plan bound by sources')
        self.fixture.proof['revised_plan_hash']=plan_hash(self.fixture.plan)
        self.fixture.proof['prior_journal_sha256']=file_hash(self.fixture.original)
        self.fixture.write_proof()
        self.plan=self.root/'new.json';self.plan.write_text(json.dumps(self.fixture.plan,ensure_ascii=False),encoding='utf-8')
        self.patch=mock.patch.object(oneshot,'REGISTRY',self.fixture.registry)
        self.patch.start();self.addCleanup(self.patch.stop)

    def argv(self):
        return ['--fill-plan',str(self.plan),'--prior-plan',str(self.prior),
                '--revision-authorization',str(self.fixture.proof_path),'--expect-name',self.fixture.plan['operator']]

    def invoke(self,args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=oneshot.main(args)
        return code,json.loads(out.getvalue().strip().splitlines()[-1])

    def test_revision_validate_only_never_allocates_or_launches(self):
        with mock.patch.object(oneshot,'allocate_run') as allocate,mock.patch.object(revision,'RevisionProbe') as probe:
            code,data=self.invoke(self.argv()+['--validate-only'])
        self.assertEqual((code,data['status']),(0,'REVISION_VALIDATED'))
        self.assertFalse(data['browser_launched']);allocate.assert_not_called();probe.assert_not_called()

    def test_revision_missing_pair_and_task_mode_rejected_before_browser(self):
        for args in ([*self.argv()[:2],'--prior-plan',str(self.prior),'--expect-name',self.fixture.plan['operator']],
                     ['--task',str(self.plan),'--revision-authorization',str(self.fixture.proof_path),'--expect-name',self.fixture.plan['operator']]):
            code,data=self.invoke(args)
            self.assertEqual(code,2);self.assertFalse(data['browser_launched'])

    def test_old_plan_mismatch_is_rejected(self):
        data=json.loads(self.prior.read_text(encoding='utf-8'));data['not_applicable'].append('wrong prior')
        self.prior.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        code,out=self.invoke(self.argv()+['--validate-only'])
        self.assertEqual(code,2);self.assertIn('prior plan',out['issues'][0]['message'])

    def test_registry_hash_drift_is_rejected(self):
        self.fixture.original.write_text('{}',encoding='utf-8')
        code,out=self.invoke(self.argv()+['--validate-only'])
        self.assertEqual(code,2);self.assertIn('journal changed',out['issues'][0]['message'])

    def test_revision_routes_once_into_existing_owner_main(self):
        run=self.root/'run';run.mkdir()
        with mock.patch.object(oneshot,'allocate_run',return_value=run),mock.patch.object(revision,'RevisionProbe') as factory:
            factory.return_value.result={'finish_reason':'SUCCESS_DRAFT_SAVED'}
            code,_=self.invoke(self.argv())
        self.assertEqual(code,0);factory.assert_called_once();factory.return_value.main.assert_called_once()
        self.assertEqual(factory.call_args.args[0].fill_plan,str(self.prior))
        self.assertTrue(factory.call_args.args[0].owned_guarded_context)

    def test_compat_plan_and_revision_delegate_in_process(self):
        for args in ([ '--fill-plan',str(self.plan),'--expect-name',self.fixture.plan['operator']],self.argv()):
            with mock.patch.object(oneshot,'main',return_value=0) as unified,mock.patch.object(compat.subprocess,'call') as child:
                self.assertEqual(compat.main(args),0)
            unified.assert_called_once_with(args);child.assert_not_called()

    def test_compat_ready_task_delegates_but_bare_task_remains_preparation(self):
        task=self.root/'task.json';task.write_text(json.dumps({'facts_payload':'facts.json'}))
        args=['--task',str(task),'--expect-name',self.fixture.plan['operator']]
        with mock.patch.object(oneshot,'main',return_value=0) as unified:
            self.assertEqual(compat.main(args),0)
        unified.assert_called_once_with(args)

    def test_live_revision_phase_has_no_new_form_navigation(self):
        # Read-only intent path must not call the form writer/edit picker, even
        # when the revision journal contains an unresolved save outcome.
        p=object.__new__(revision.RevisionProbe)
        p.args=SimpleNamespace(expect_name=self.fixture.plan['operator'])
        p.revision_plan_path=self.plan;p.revision_proof_path=self.fixture.proof_path
        p.revision_proof_sha=self.fixture.proof_sha;p.revision_registry=self.fixture.registry
        p.protected_restored_forms=[];p.result={};p.attempt=self.root/'phase'
        p.checks={'c7_fill_new':{}}
        p.page=mock.Mock();p.adapter=mock.Mock()
        journal=self.root/'pending.json';journal.write_text(json.dumps({'status':'SAVE_UNCERTAIN'}))
        controller=mock.Mock();controller.journal=journal
        controller.run.return_value={'status':'SUCCESS_DRAFT_SAVED'}
        adapter=mock.Mock();adapter.capture_snapshot.return_value={'page':self.fixture.identity}
        with mock.patch.object(revision,'DraftRevisionController',return_value=controller),mock.patch.object(revision,'DraftRevisionUIAdapter',return_value=adapter),mock.patch.object(revision,'bind_and_fill_revision') as fill,mock.patch('bpm.template.open_exact_document',return_value='https://bpm.qiaodan.com/oa/reimburse?type=view&id='+'b'*32):
            self.assertEqual(p.phase_fill(),'PASS')
        fill.assert_not_called();p.page.get_by_role.assert_not_called()
        self.assertTrue(p.result['read_only_reconciliation']);controller.run.assert_called_once()

    def test_owned_guarded_context_is_used_without_test_marker(self):
        from bpm.ui import StructuredProbe
        from bpm.browser_probe import Probe
        p=object.__new__(StructuredProbe)
        p.args=SimpleNamespace(owned_guarded_context=True)
        p.fill_plan={};p._guarded_browser=mock.Mock();p.ctx=mock.Mock();p.ctx.pages=[]
        p._timing=mock.Mock(return_value=contextlib.nullcontext())
        p._launch_isolated_guarded_context=mock.Mock();p._inject_session_state=mock.Mock()
        with mock.patch.object(Probe,'_launch') as persistent:
            p._launch()
        p._launch_isolated_guarded_context.assert_called_once()
        p._inject_session_state.assert_called_once();persistent.assert_not_called()
        self.assertEqual(p.protected_restored_forms,[])

    def test_local_session_paths_are_protected_case_insensitively(self):
        self.assertTrue(oneshot._protected(Path('input/.LOCAL-SESSION/record.json')))

if __name__=='__main__':unittest.main()
