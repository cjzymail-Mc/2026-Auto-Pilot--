"""Explicit existing-draft revision, retaining the original creation journal.

No new-form navigation, write API, submit capability, or intent reset exists here.
One revision journal per original journal hash shares the original task lock.
"""
from pathlib import Path
import hashlib,json,re
from urllib.parse import parse_qs,urlsplit

from bpm.save import SaveController,SaveError,config_hash
from bpm.ui import DraftUIAdapter,UIBlocked,StructuredProbe
from bpm.browser_probe import PASS,BLOCKED
from bpm.verify import verify_snapshot

KEYS={"schema_version","mode","task_id","identity","prior_plan_hash",
      "prior_journal_sha256","revised_plan_hash","allow_submit","statement","edit_url"}

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def revision_authorization(plan,proof_path,proof_sha256,registry):
    """Re-read the immutable explicit authorization and original saved journal."""
    from bpm.plan import plan_hash
    try:
        path=Path(proof_path)
        if _sha(path)!=proof_sha256:raise ValueError('Revision authorization hash changed')
        proof=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(proof,dict) or set(proof)!=KEYS:raise ValueError('Exact revision authorization keys required')
        if (proof['schema_version']!='1.0' or proof['mode']!='revise_existing_draft'
                or proof['task_id']!=plan['task_id'] or proof['allow_submit'] is not False
                or not isinstance(proof['statement'],str) or not proof['statement'].strip()
                or proof['revised_plan_hash']!=plan_hash(plan)
                or proof['prior_plan_hash']==proof['revised_plan_hash']):
            raise ValueError('Explicit changed-plan revision authorization required')
        for key in ('prior_plan_hash','prior_journal_sha256','revised_plan_hash'):
            if not re.fullmatch('[0-9a-f]{64}',str(proof[key])):raise ValueError('Invalid revision hash')
        identity=proof['identity']
        if (not isinstance(identity,dict) or set(identity)!={'uuid','biz_number','status'}
                or not re.fullmatch('[0-9a-f]{32}',str(identity.get('uuid','')))
                or not re.fullmatch(r'\d{8,}',str(identity.get('biz_number','')))
                or identity.get('status')!='编制中'):
            raise ValueError('Unique compiling draft identity required')
        route=urlsplit(proof['edit_url']);query=parse_qs(route.query)
        if (route.scheme!='https' or route.netloc!='bpm.qiaodan.com' or route.path!='/oa/reimburse'
                or query!={'type':['edit'],'id':[identity['uuid']]} or route.fragment):
            raise ValueError('Observed exact edit route required')
        name=hashlib.sha256(plan['task_id'].encode('utf-8')).hexdigest()
        original=Path(registry)/(name+'.json')
        if _sha(original)!=proof['prior_journal_sha256']:raise ValueError('Original saved journal changed')
        state=json.loads(original.read_text(encoding='utf-8'))
        if (state.get('task_id')!=plan['task_id'] or state.get('status')!='SUCCESS_DRAFT_SAVED'
                or state.get('plan_hash')!=proof['prior_plan_hash'] or state.get('identity')!=identity
                or state.get('config_sha256')!=config_hash(plan['document_type'])):
            raise ValueError('Original successful draft binding differs')
        return proof
    except (OSError,ValueError,TypeError,KeyError) as exc:
        raise SaveError(str(exc)) from None

class DraftRevisionController(SaveController):
    def __init__(self,plan,adapter,attempt_dir,*,revision_authorization_path,
                 revision_authorization_sha256,expected_operator=None,base_dir=None,journal_dir=None):
        super().__init__(plan,adapter,attempt_dir,expected_operator=expected_operator,
                         base_dir=base_dir,journal_dir=journal_dir)
        self.proof_path=Path(revision_authorization_path)
        self.proof_sha=revision_authorization_sha256
        self.proof=revision_authorization(plan,self.proof_path,self.proof_sha,self.registry)
        self.original_journal=self.journal
        # A changed authorization cannot create a second click opportunity for
        # this original saved state. The same task lock is deliberately retained.
        revision_dir=self.registry/'revisions'/self.journal.stem
        revision_dir.mkdir(parents=True,exist_ok=True)
        self.journal=revision_dir/(self.proof['prior_journal_sha256']+'.json')

    def _preflight(self):
        issues=super()._preflight()
        try:
            current=revision_authorization(self.plan,self.proof_path,self.proof_sha,self.registry)
            if current!=self.proof:raise SaveError('Revision binding changed')
            if self.state and self.state.get('revision_authorization_sha256')!=self.proof_sha:
                raise SaveError('Existing revision authorization differs')
        except SaveError as exc:
            issues.append({'code':'REVISION_BINDING_INVALID','message':str(exc)})
        return issues

    def _transition(self,status,**extra):
        return super()._transition(status,revision_authorization_sha256=self.proof_sha,
            original_save_journal=str(self.original_journal),
            original_save_journal_sha256=self.proof['prior_journal_sha256'],
            existing_identity=self.proof['identity'],**extra)

    def _verify(self,snapshot,phase='before_save'):
        return verify_snapshot(self.plan,snapshot,
            phase='before_revision' if phase=='before_save' else phase,
            existing_identity=self.proof['identity'],base_dir=self.base_dir)

    def _reconcile(self,observation=None):
        issues=self._preflight()
        if issues:return self._transition('SAVE_UNCERTAIN',issues=issues,reason='Revision binding changed; no click')
        if observation is None:observation=self.adapter.inspect_uncertain()
        if (not isinstance(observation,dict) or observation.get('identity')!=self.proof['identity']):
            return self._transition('SAVE_UNCERTAIN',reason='Existing draft identity differs; no click')
        return super()._reconcile(observation)

class DraftRevisionUIAdapter(DraftUIAdapter):
    def __init__(self,probe,*,revision_authorization_path,revision_authorization_sha256,journal_dir):
        super().__init__(probe)
        self.proof_path=Path(revision_authorization_path)
        self.proof_sha=revision_authorization_sha256
        self.registry=Path(journal_dir)
        self.proof=revision_authorization(probe.fill_plan,self.proof_path,self.proof_sha,self.registry)

    def verify_before_save(self,snapshot):
        try:
            current=revision_authorization(self.p.fill_plan,self.proof_path,self.proof_sha,self.registry)
            if current!=self.proof:raise SaveError('Revision binding changed')
        except SaveError:
            return {'ok':False,'issues':[{'code':'REVISION_BINDING_INVALID'}]}
        return verify_snapshot(self.p.fill_plan,snapshot,phase='before_revision',
            existing_identity=self.proof['identity'],base_dir=self.p.plan_base)

    def reopen(self,identity):
        from bpm.template import open_exact_document
        if identity!=self.proof['identity']:raise UIBlocked('REVISION_IDENTITY_CHANGED')
        page=self.open_verification_page()
        route=open_exact_document(self.p,identity['biz_number'],expected_uuid=identity['uuid'],page=page)
        page.goto(route,wait_until='domcontentloaded',timeout=45000)
        latest=None
        for _ in range(40):
            page.wait_for_timeout(600)
            latest=self.capture_snapshot(page)
            if verify_snapshot(self.p.fill_plan,latest,phase='after_save',base_dir=self.p.plan_base)['ok']:
                return latest
        return latest

def bind_and_fill_revision(probe,plan_path,*,revision_authorization_path,
                           revision_authorization_sha256,journal_dir):
    """Borrow the current guarded owner/context; never launch or navigate anew.

    This first implementation permits append-only expense/detail rows, an
    explicit remark/total correction, and existing bank amount corrections.
    Original business rows and all persons/bank identifiers are immutable.
    """
    from bpm.plan import load_plan,plan_hash
    plan_path=Path(plan_path).resolve()
    plan=load_plan(plan_path,expected_operator=probe.args.expect_name)
    proof=revision_authorization(plan,revision_authorization_path,
                                 revision_authorization_sha256,journal_dir)
    prior=probe.fill_plan
    if plan_hash(prior)!=proof['prior_plan_hash']:
        raise UIBlocked('REVISION_PRIOR_PLAN_MISMATCH')
    for key in ('task_id','document_type','operator','applicant','identity','template'):
        if prior.get(key)!=plan.get(key):raise UIBlocked('REVISION_STABLE_IDENTITY_CHANGED:'+key)
    for key,value in prior['header'].items():
        if key not in ('description','totalCost') and plan['header'].get(key)!=value:
            raise UIBlocked('REVISION_HEADER_SCOPE_CHANGED:'+key)
    for table in ('relations','costs','details'):
        original=prior['tables'][table];revised=plan['tables'][table]
        if revised[:len(original)]!=original or (table=='relations' and revised!=original):
            raise UIBlocked('REVISION_EXISTING_ROWS_CHANGED:'+table)
    if len(plan['tables']['banks'])!=len(prior['tables']['banks']):
        raise UIBlocked('REVISION_BANK_COUNT_CHANGED')
    for old,new in zip(prior['tables']['banks'],plan['tables']['banks']):
        if (old['row_id']!=new['row_id'] or {k:v for k,v in old['fields'].items() if k!='cost'}
                !={k:v for k,v in new['fields'].items() if k!='cost'}):
            raise UIBlocked('REVISION_BANK_IDENTITY_CHANGED')
    initial=probe.adapter.capture_snapshot()
    verified=verify_snapshot(prior,initial,phase='before_revision',
        existing_identity=proof['identity'],base_dir=probe.plan_base)
    probe.save('revision_initial_verification.json',json.dumps(verified,ensure_ascii=False,indent=2))
    if not verified['ok']:raise UIBlocked('REVISION_INITIAL_READBACK_MISMATCH')
    # Reject a consumed/rebound revision slot before making even unsaved edits.
    controller=DraftRevisionController(plan,probe.adapter,probe.attempt,
        revision_authorization_path=revision_authorization_path,
        revision_authorization_sha256=revision_authorization_sha256,
        expected_operator=probe.args.expect_name,base_dir=plan_path.parent,journal_dir=journal_dir)
    if controller.journal.exists():raise UIBlocked('REVISION_EXISTS_READ_ONLY_RECONCILIATION_REQUIRED')
    probe.fill_plan=plan;probe.fill_plan_path=plan_path;probe.plan_base=plan_path.parent
    probe.bound_plan_hash=plan_hash(plan);probe.config_hash=config_hash(plan['document_type'])
    probe.adapter=DraftRevisionUIAdapter(probe,revision_authorization_path=revision_authorization_path,
        revision_authorization_sha256=revision_authorization_sha256,journal_dir=journal_dir)
    header=initial['header']
    probe.locked_identity={key:header.get(key) for key in ('createdName','createdDeptName','appliedName','appliedBy','appliedDeptName','corpCode')}
    probe.result.update(plan_hash=probe.bound_plan_hash,task_id=plan['task_id'],
        fill_plan_file=str(plan_path),execution_mode='existing_draft_revision',save_status='NOT_ATTEMPTED')
    probe.log_event(event='existing_draft_revision_bound',task_id=plan['task_id'],
        uuid=proof['identity']['uuid'],prior_plan_hash=proof['prior_plan_hash'],
        revised_plan_hash=proof['revised_plan_hash'],prior_journal_sha256=proof['prior_journal_sha256'])
    probe._write_header()
    for table in ('costs','details','banks'):
        fresh=load_plan(plan_path,expected_operator=probe.args.expect_name)
        if plan_hash(fresh)!=probe.bound_plan_hash or config_hash(plan['document_type'])!=probe.config_hash:
            raise UIBlocked('REVISION_SOURCE_PLAN_OR_CONFIG_CHANGED')
        probe._invalidate_tables();probe._assert_identities_locked()
        start=0 if table=='banks' else len(prior['tables'][table])
        for index in range(start,len(plan['tables'][table])):
            fields=plan['tables'][table][index]['fields']
            probe._ensure_row(table,index,fields)
            order=['reimItem','digest','budgetNo','subjectName'] if table=='details' else []
            for prop in order+[key for key in fields if key not in order]:
                if table=='banks' and prop!='cost':continue
                if table=='details' and prop in ('budgetDeptName','budgetItemName','budgetOwner'):continue
                probe._write(table,index,prop,fields[prop])
            probe.log_event(event='revision_row_written',table=table,row=index,row_id=plan['tables'][table][index]['row_id'])
        probe._assert_identities_locked()
    probe.page.keyboard.press('Tab');probe.page.wait_for_timeout(800)
    return DraftRevisionController(plan,probe.adapter,probe.attempt,
        revision_authorization_path=revision_authorization_path,
        revision_authorization_sha256=revision_authorization_sha256,
        expected_operator=probe.args.expect_name,base_dir=plan_path.parent,journal_dir=journal_dir)


class RevisionProbe(StructuredProbe):
    """Official oneshot operation borrowing the normal owner/entry/finally chain."""
    def __init__(self,args,*,plan_path,proof_path,proof_sha,registry):
        super().__init__(args)
        self.revision_plan_path=Path(plan_path)
        self.revision_proof_path=Path(proof_path)
        self.revision_proof_sha=proof_sha
        self.revision_registry=Path(registry)

    def phase_fill(self):
        from bpm.plan import load_plan,plan_hash
        from bpm.query import QueryCLI
        from bpm.template import open_exact_document
        from types import SimpleNamespace
        try:
            if any(not page.is_closed() for page in self.protected_restored_forms):
                raise UIBlocked('RESTORED_FORM_REQUIRES_OWNER')
            plan=load_plan(self.revision_plan_path,expected_operator=self.args.expect_name)
            proof=revision_authorization(plan,self.revision_proof_path,
                                         self.revision_proof_sha,self.revision_registry)
            controller=DraftRevisionController(plan,self.adapter,self.attempt,
                revision_authorization_path=self.revision_proof_path,
                revision_authorization_sha256=self.revision_proof_sha,
                expected_operator=self.args.expect_name,base_dir=self.revision_plan_path.parent,
                journal_dir=self.revision_registry)
            readonly=controller.journal.exists()
            if readonly:
                # Intent/uncertainty/success never re-enters the edit/fill path.
                self.fill_plan=plan;self.fill_plan_path=self.revision_plan_path
                self.plan_base=self.revision_plan_path.parent;self.bound_plan_hash=plan_hash(plan)
                self.config_hash=config_hash(plan['document_type'])
                self.adapter=DraftRevisionUIAdapter(self,revision_authorization_path=self.revision_proof_path,
                    revision_authorization_sha256=self.revision_proof_sha,journal_dir=self.revision_registry)
                controller.adapter=self.adapter
                route=open_exact_document(self,proof['identity']['biz_number'],expected_uuid=proof['identity']['uuid'])
                self.page.goto(route,wait_until='domcontentloaded',timeout=45000)
                for _ in range(40):
                    self.page.wait_for_timeout(600)
                    snapshot=self.adapter.capture_snapshot()
                    if all(snapshot['page'].get(key)==value for key,value in proof['identity'].items()):
                        break
                else:
                    raise UIBlocked('REVISION_READ_ONLY_IDENTITY_UNPROVEN')
                # Reconciliation has the already bound identity; no edited form
                # or main-page observation is needed for a pending click result.
                if controller.journal.is_file():
                    state=json.loads(controller.journal.read_text(encoding='utf-8'))
                    if state.get('status') not in {'SAVE_INTENT','SAVE_UNCERTAIN','SUCCESS_DRAFT_SAVED'}:
                        raise UIBlocked('EXISTING_REVISION_REQUIRES_READ_ONLY_REVIEW')
            else:
                query=object.__new__(QueryCLI);query.p=self;query.page=self.page
                query.retries=0;query.timings={}
                query.o=SimpleNamespace(number=proof['identity']['biz_number'],snapshot=False)
                query.open_list();query.clear_default_creator()
                found=query.number_flow({})
                if (found.get('status')!='ok' or len(found.get('candidates',[]))!=1
                        or found['candidates'][0]['id'].replace('-','')!=proof['identity']['uuid']):
                    raise UIBlocked('REVISION_EXACT_LIST_IDENTITY_MISMATCH')
                row=self.page.locator('tbody tr').filter(has_text=proof['identity']['biz_number'])
                if row.count()!=1:raise UIBlocked('REVISION_LIST_ROW_NOT_UNIQUE')
                row.locator(':scope > td').first.click(timeout=8000)
                button=self.page.get_by_role('button',name='修改所选项',exact=True)
                if button.count()!=1 or not button.is_enabled():raise UIBlocked('REVISION_EDIT_ENTRY_UNAVAILABLE')
                self._click_guard('修改所选项');button.click(timeout=8000)
                for _ in range(40):
                    self.page.wait_for_timeout(600)
                    snapshot=self.adapter.capture_snapshot()
                    if snapshot['page']['url']==proof['edit_url'] and snapshot['page']['biz_number']==proof['identity']['biz_number']:
                        break
                controller=bind_and_fill_revision(self,self.revision_plan_path,
                    revision_authorization_path=self.revision_proof_path,
                    revision_authorization_sha256=self.revision_proof_sha,journal_dir=self.revision_registry)
            result=controller.run()
            self.result.update(execution_mode='existing_draft_revision',read_only_reconciliation=readonly,
                draft_revision_save=result,task_status=result['status'],save_status=result['status'])
            self.checks['c7_fill_new'].update(status=PASS if result['status']=='SUCCESS_DRAFT_SAVED' else BLOCKED,
                reason='Explicit same-draft revision: '+result['status'])
        except (UIBlocked,SaveError,OSError,ValueError) as exc:
            self.result.update(task_status='NEEDS_INPUT',revision_issue=type(exc).__name__+': '+str(exc))
            self.checks['c7_fill_new'].update(status=BLOCKED,reason='Revision stopped; no retry: '+type(exc).__name__)
        return self.checks['c7_fill_new']['status']
