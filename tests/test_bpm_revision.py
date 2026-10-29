import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from bpm.plan import plan_hash,file_hash
from bpm.save import SaveError,config_hash
from bpm.revision import DraftRevisionController
from bpm.verify import verify_snapshot
from test_bpm_verify import build_fixture
from test_bpm_save import Adapter

class RevisionAdapter(Adapter):
    def click_exact_save(self):
        paths=list((self.attempt.parent/'save_tasks/revisions').glob('*/*.json'))
        assert len(paths)==1 and json.loads(paths[0].read_text())['status']=='SAVE_INTENT'
        self.clicks+=1
        if self.timeout:raise TimeoutError()

class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.plan,self.snap=build_fixture(self.root)
        self.prior_hash=plan_hash(self.plan)
        self.identity={'uuid':'b'*32,'biz_number':'15426000002','status':'编制中'}
        self.registry=self.root/'save_tasks';self.registry.mkdir()
        self.original=self.registry/(hashlib.sha256(self.plan['task_id'].encode()).hexdigest()+'.json')
        self.original.write_text(json.dumps({'task_id':self.plan['task_id'],'plan_hash':self.prior_hash,
            'config_sha256':config_hash('travel'),'status':'SUCCESS_DRAFT_SAVED','identity':self.identity}),encoding='utf-8')
        self.original_bytes=self.original.read_bytes()
        self.plan['header']['description']='明确同单修订测试'
        facts=self.root/'facts.json';data=json.loads(facts.read_text(encoding='utf-8'))
        data['header']['description']=self.plan['header']['description'];facts.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        for source in self.plan['sources'].values():
            if source['path']==str(facts):source['sha256']=file_hash(facts)
        for row in self.plan['materials']['no_invoice_rows']:row['proof']['sha256']=file_hash(facts)
        self.snap['header']=copy.deepcopy(self.plan['header'])
        self.snap['page'].update(self.identity,is_new=False,url='https://bpm.qiaodan.com/oa/reimburse?type=edit&id='+'b'*32)
        self.attempt=self.root/'attempt_001';self.attempt.mkdir()
        self.adapter=RevisionAdapter(self.snap,self.attempt)
        self.adapter.identity=copy.deepcopy(self.identity)
        self.proof_path=self.root/'revision-authorization.json'
        self.proof={'schema_version':'1.0','mode':'revise_existing_draft','task_id':self.plan['task_id'],
            'identity':self.identity,'prior_plan_hash':self.prior_hash,'prior_journal_sha256':file_hash(self.original),
            'revised_plan_hash':plan_hash(self.plan),'allow_submit':False,'statement':'明确授权修订该未提交草稿，禁止流转',
            'edit_url':self.snap['page']['url']}
        self.write_proof()

    def write_proof(self):
        self.proof_path.write_text(json.dumps(self.proof,ensure_ascii=False),encoding='utf-8')
        self.proof_sha=file_hash(self.proof_path)

    def controller(self):
        return DraftRevisionController(self.plan,self.adapter,self.attempt,expected_operator=self.plan['operator'],
            revision_authorization_path=self.proof_path,revision_authorization_sha256=self.proof_sha,journal_dir=self.registry)

    def test_success_preserves_original_and_repeat_reconciles_only(self):
        result=self.controller().run()
        self.assertEqual(result['status'],'SUCCESS_DRAFT_SAVED')
        self.assertEqual(self.adapter.clicks,1)
        self.assertEqual(self.original.read_bytes(),self.original_bytes)
        self.assertEqual(self.controller().run()['status'],'SUCCESS_DRAFT_SAVED')
        self.assertEqual(self.adapter.clicks,1)

    def test_wrong_uuid_does_not_click(self):
        self.adapter.snapshot['page'].update(uuid='c'*32,url='https://bpm.qiaodan.com/oa/reimburse?type=edit&id='+'c'*32)
        self.assertEqual(self.controller().run()['status'],'READBACK_MISMATCH')
        self.assertEqual(self.adapter.clicks,0)

    def test_non_compiling_does_not_click(self):
        self.adapter.snapshot['page']['status']='审批中'
        self.assertEqual(self.controller().run()['status'],'READBACK_MISMATCH')
        self.assertEqual(self.adapter.clicks,0)

    def test_new_form_cannot_use_revision_authorization(self):
        self.adapter.snapshot['page'].update(is_new=True,uuid='',biz_number='',url='https://bpm.qiaodan.com/oa/reimburse?type=new')
        self.assertEqual(self.controller().run()['status'],'READBACK_MISMATCH')
        self.assertEqual(self.adapter.clicks,0)

    def test_old_plan_or_changed_proof_rejected(self):
        self.proof['prior_plan_hash']=self.proof['revised_plan_hash'];self.write_proof()
        with self.assertRaises(SaveError):self.controller()
        self.assertEqual(self.adapter.clicks,0)

    def test_unknown_save_only_reconciles_no_second_click(self):
        self.adapter.timeout=True
        self.assertEqual(self.controller().run()['status'],'SAVE_UNCERTAIN')
        self.adapter.timeout=False
        self.assertEqual(self.controller().run()['status'],'SUCCESS_DRAFT_SAVED')
        self.assertEqual(self.adapter.clicks,1)
        self.assertEqual(self.original.read_bytes(),self.original_bytes)

    def test_different_revision_hash_cannot_create_second_intent(self):
        self.assertEqual(self.controller().run()['status'],'SUCCESS_DRAFT_SAVED')
        # No new task, proof filename or changed plan can evade this original
        # saved-state journal slot. Different plan is rejected before click.
        self.plan['not_applicable'].append('a later proposed revision')
        self.proof['revised_plan_hash']=plan_hash(self.plan);self.write_proof()
        with self.assertRaises(SaveError):self.controller().run()
        self.assertEqual(self.adapter.clicks,1)

    def test_original_journal_drift_before_click_blocks(self):
        controller=self.controller();original_shot=self.adapter.screenshot
        def shot(name):
            result=original_shot(name);self.original.write_bytes(self.original_bytes+b' ');return result
        self.adapter.screenshot=shot
        self.assertEqual(controller.run()['status'],'NEEDS_INPUT')
        self.assertEqual(self.adapter.clicks,0)

    def test_saved_identity_conflict_stays_uncertain(self):
        self.adapter.identity={**self.identity,'uuid':'c'*32}
        self.assertEqual(self.controller().run()['status'],'SAVE_UNCERTAIN')
        self.assertEqual(self.controller().run()['status'],'SAVE_UNCERTAIN')
        self.assertEqual(self.adapter.clicks,1)

    def test_revision_verifier_requires_explicit_target(self):
        self.assertFalse(verify_snapshot(self.plan,self.snap,phase='before_revision')['ok'])
        self.assertFalse(verify_snapshot(self.plan,self.snap)['ok'])
        self.assertTrue(verify_snapshot(self.plan,self.snap,phase='before_revision',existing_identity=self.identity)['ok'])

if __name__=='__main__':unittest.main()
