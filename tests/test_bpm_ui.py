"""Local Chromium tests. Every URL is intercepted; no OA/profile is accessed."""
import copy
import html
import json
import os
import shutil
import tempfile
import types
import unittest
from pathlib import Path

from bpm.plan import file_hash, load_type, plan_hash, validate_plan
from bpm.ui import StructuredProbe, DraftUIAdapter, UIBlocked
from bpm.verify import verify_snapshot
from test_bpm_verify import build_fixture


def form_html(plan, *, blank=False):
    config = load_type(plan["document_type"])
    headers = dict(plan["header"])
    headers.update(appliedName=plan["applicant"]["name"], corpCode=plan["applicant"]["company"],
                   appliedDeptName=plan["applicant"]["department"], bizStatus="编制中", bizNumber="")
    content = ['<!doctype html><meta charset="utf-8"><style>qd-dynamic-table{display:block}td,th{padding:5px}</style>',
               '<a id="user-profile-dd" class="profile-toggle-link"><span>' + plan["operator"] + '</span></a>',
               '<a href="/oa/home">首页</a><a href="/oa/reimburses">报销</a><a href="/oa/tasks">任务</a>']
    for prop, value in headers.items():
        ro = prop in ("totalCost", "appliedName", "appliedDeptName", "bizNumber", "bizStatus", "corpCode")
        content.append(f'<label for="{prop}0">{prop}</label><input id="{prop}0" name="{prop}0" '
                       f'value="{html.escape(str(value))}" {"readonly" if ro else ""}>')
    for key, spec in config["tables"].items():
        rows = [] if blank else plan["tables"][key]
        content.append(f'<qd-dynamic-table id="component-{key}"><span class="table-caption">'
                       f'{spec["title"]}</span><button title="新增" data-add="{key}">新增</button>')
        # Real PrimeNG layout splits header and body into separate tables.
        content.append(f'<table id="head-{key}"><thead><tr>' + ''.join(
            f'<th class="prop-{prop}">{col["label"]}</th>' for prop, col in spec["columns"].items())
            + '</tr></thead></table><div class="ui-table-scrollable-body">'
            + f'<table id="body-{key}"><tbody>')
        for row in rows:
            content.append('<tr>' + ''.join(f'<td>{html.escape(str(row["fields"][prop]))}</td>'
                                           for prop in spec["columns"]) + '</tr>')
        content.append('</tbody></table></div></qd-dynamic-table>')
    rel_props = ["bizTypeName", "bizNo", "bizDetailCost", "bizDetailNum", "usedCost", "cost"]
    content.append('<qd-dynamic-table id="component-detailrels"><span class="table-caption">关联单据明细</span>'
                   '<table><thead><tr>' + ''.join(f'<th class="prop-{p}">{p}</th>' for p in rel_props)
                   + '</tr></thead><tbody>')
    for r in plan["tables"]["relations"]:
        vals = [r["fields"]["bizTypeName"], r["fields"]["bizNumber"], "0", "0", "0", r["fields"]["nowCost"]]
        content.append('<tr>' + ''.join(f'<td>{html.escape(v)}</td>' for v in vals) + '</tr>')
    content.append('</tbody></table></qd-dynamic-table><button id="save">保存</button><script>')
    content.append('var columns=' + json.dumps({k: list(v["columns"]) for k, v in config["tables"].items()}) + ';')
    content.append('''
      function edit(td) {
        if(td.querySelector('input')) return;
        let v=td.textContent; td.textContent=''; let inp=document.createElement('input'); inp.value=v;
        inp.addEventListener('keydown', e=>{if(e.key==='Enter'){td.textContent=inp.value;}});
        td.appendChild(inp); inp.focus();
      }
      document.querySelectorAll('button[data-add]').forEach(b=>b.onclick=()=>{
        let key=b.dataset.add,tr=document.createElement('tr');
        columns[key].forEach(prop=>{let td=document.createElement('td');tr.appendChild(td);});
        document.querySelector('#body-'+key+' tbody').appendChild(tr);
      });
      document.addEventListener('dblclick',e=>{let td=e.target.closest('td');if(td)edit(td);});
    </script>''')
    return ''.join(content)


class DOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(headless=True, args=["--no-proxy-server"])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan, _ = build_fixture(self.root)
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=form_html(self.plan)))
        self.page.goto("https://bpm.qiaodan.com/oa/reimburse?type=new")
        self.p = object.__new__(StructuredProbe)
        self.p.page = self.page
        self.p.args = types.SimpleNamespace(expect_name=self.plan["operator"])
        self.p.run_dir = self.root
        self.p.attempt = self.root / "attempt_001"
        self.p.ev = self.p.attempt / "evidence"
        self.p.ev.mkdir(parents=True)
        self.p.fill_plan = self.plan
        self.p.type_config = load_type("travel")
        from bpm.types import resolve_type
        self.p.config_hash = resolve_type(self.plan["document_type"]).sha256
        self.p.bound_plan_hash = plan_hash(self.plan)
        self.p.plan_base = self.root
        self.p.native_dialogs = []
        # Authentication is fixture-provided; real run uses Probe.login_state.
        self.p.login_state = lambda page: ("LOGGED_IN", {}, {})
        self.p.adapter = DraftUIAdapter(self.p)

    def tearDown(self):
        requested = os.environ.get("BPM_TEST_EVIDENCE_DIR")
        if not requested:
            return
        output = Path(requested).resolve()
        allowed = Path(__file__).resolve().parents[1] / "automation" / "offline-verify"
        if not output.is_relative_to(allowed.resolve()):
            raise ValueError("test evidence must stay beneath automation/offline-verify")
        self.page.screenshot(path=str(self.p.ev / "fixture_final.png"), full_page=True)
        (self.p.ev / "fixture_snapshot.json").write_text(
            json.dumps(self.p.adapter.capture_snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.root, output / self._testMethodName)

    def test_independent_collector_reads_split_tables(self):
        snap = self.p.adapter.capture_snapshot()
        self.assertTrue(all(snap["completeness"].values()))
        self.assertEqual(snap["tables"]["banks"][0]["fields"]["account"], "001234567890")
        check = verify_snapshot(self.plan, snap)
        self.assertTrue(check["ok"], check["issues"])
        # Mutation after the writer returned success must still be detected.
        self.page.locator("#body-banks tbody td").nth(1).evaluate("e=>e.textContent='1234567890'")
        check = verify_snapshot(self.plan, self.p.adapter.capture_snapshot())
        self.assertFalse(check["ok"])

    def test_expected_name_in_body_cannot_impersonate_topbar_operator(self):
        self.page.locator("#user-profile-dd > span").evaluate("e=>e.textContent='其他操作人'")
        state, marks, _ = StructuredProbe.login_state(self.p, self.page)
        self.assertEqual(state, "UNKNOWN")
        snap = self.p.adapter.capture_snapshot()
        self.assertEqual(snap["page"]["operator"], "其他操作人")
        self.assertFalse(verify_snapshot(self.plan, snap)["ok"])

    def test_missing_table_cannot_pass_as_empty(self):
        self.page.locator("#component-costs").evaluate("e=>e.remove()")
        snap = self.p.adapter.capture_snapshot()
        self.assertFalse(snap["completeness"]["costs"])
        self.assertFalse(verify_snapshot(self.plan, snap)["ok"])

    def test_same_prop_other_title_is_not_selected(self):
        self.page.locator("#component-banks .table-caption").evaluate("e=>e.textContent='银行错误表'")
        with self.assertRaises(UIBlocked):
            self.p._table("banks")

    def test_unknown_and_duplicate_extra_tables_cannot_hide_rows(self):
        self.page.evaluate('''()=>{
          for(const value of ['99','']) {
            let d=document.createElement('qd-dynamic-table');d.style.display='block';
            d.innerHTML='<span class="table-caption">产品明细</span><table><thead><tr><th class="prop-cost">金额</th></tr></thead><tbody>'+
              (value?'<tr><td>'+value+'</td></tr>':'')+'</tbody></table>';document.body.appendChild(d);
          }
        }''')
        snap = self.p.adapter.capture_snapshot()
        self.assertEqual(len(snap["extra_tables"]["products"]), 1)
        self.assertFalse(verify_snapshot(self.plan, snap)["ok"])

    def test_exact_picker_rejects_longer_document_number_and_ambiguity(self):
        def popup(values):
            self.page.evaluate(r'''values=>{
                let d=document.createElement('div');d.className='ui-dialog';d.id='picker';
                d.innerHTML='<table><thead><tr><th>单号</th></tr></thead><tbody>'+values.map(v=>
                  '<tr onclick="this.classList.add(\'ui-state-highlight\')"><td>'+v+'</td></tr>').join('')+
                  '</tbody></table><div class="ui-dialog-footer"><button onclick="this.closest(\'.ui-dialog\').remove()">确定</button></div>';
                document.body.appendChild(d);
            }''', values)
        popup(["120260000010", "12026000001"])
        self.assertTrue(self.p._overlay_search_pick(self.page, self.page.main_frame, "12026000001", "test", prescan=True))
        popup(["12026000001", "12026000001"])
        self.assertFalse(self.p._overlay_search_pick(self.page, self.page.main_frame, "12026000001", "test", prescan=True))

    def test_array_executor_writes_more_than_two_rows_and_multiple_banks(self):
        # Real cell activation/row creation is exercised; picker behavior has its
        # own exact-identity test above. Pre-filled selector echoes isolate arrays.
        self.plan["tables"]["costs"] = [
            {"row_id": f"c{i}", "fields": dict(self.plan["tables"]["costs"][0]["fields"],
                                               reason=f"费用-{i}", cost=str(i))} for i in range(1, 5)]
        self.plan["tables"]["details"] = [
            {"row_id": f"d{i}", "fields": dict(self.plan["tables"]["details"][0]["fields"], digest=f"摘要-{i}")} for i in range(3)]
        self.plan["tables"]["banks"] = [
            {"row_id": f"b{i}", "fields": dict(self.plan["tables"]["banks"][0]["fields"], account=f"00{i}234567890")} for i in range(3)]
        self.page.set_content(form_html(self.plan))
        for key in ("costs", "details", "banks"):
            self.page.locator(f"#body-{key} tbody tr").last.evaluate("e=>e.remove()")
        original = self.p._ensure_row
        def ensure(key, index, fields=None):
            original(key, index, fields)
            # Simulate verified selector/system echo, preserving real editors for
            # the amount and free-text fields that this scenario checks.
            spec = self.p.type_config["tables"][key]["columns"]
            for prop, value in (fields or {}).items():
                if spec[prop]["editor"] in ("selector", "budget_dialog", "subject_dialog", "branch_dialog", "readonly"):
                    self.p._cell(key, index, prop).evaluate("(e,v)=>e.textContent=v", str(value))
        self.p._ensure_row = ensure
        self.p._fill_arrays()
        snap = self.p.adapter.capture_snapshot()
        self.assertEqual([len(snap["tables"][k]) for k in ("costs", "details", "banks")], [4, 3, 3])
        self.assertEqual(snap["tables"]["costs"][3]["fields"]["reason"], "费用-4")
        self.assertEqual(snap["tables"]["banks"][2]["fields"]["account"], "002234567890")

    def test_current_dropdown_panel_and_delayed_editor_are_used_once(self):
        self.page.evaluate("""()=>{
          let td=document.querySelector('#body-costs tbody td');td.textContent='';
          window.activations=0;
          td.ondblclick=e=>{e.stopPropagation();window.activations++;
            setTimeout(()=>{td.innerHTML='<div class="ui-dropdown ng-tns-c41-current"><label class="ui-dropdown-label">请选择</label><span class="ui-dropdown-trigger">下拉</span></div>';
              td.querySelector('.ui-dropdown-trigger').onclick=()=>{
                let d=document.createElement('div');d.className='ui-dropdown-panel ng-tns-c41-current';
                d.innerHTML='<ul><li>其它交通</li><li>其它交通补贴</li></ul>';
                d.querySelector('li').onclick=()=>{td.textContent='其它交通';d.remove();};document.body.appendChild(d);
              };},200);
          };
          let stale=document.createElement('div');stale.className='ui-dropdown-panel ng-tns-c41-old';
          stale.innerHTML='<li>其它交通</li>';document.body.appendChild(stale);
        }""")
        self.p._write('costs',0,'project','其它交通',picker=True)
        self.assertEqual(self.page.evaluate('activations'),1)
        self.assertEqual(self.p._read_rows('costs')[0]['fields']['project'],'其它交通')
        self.assertEqual(self.page.locator('.ng-tns-c41-old').count(),1)

    def test_native_bank_account_is_not_forced_through_shortcut_picker(self):
        self.page.evaluate("""()=>{
          let td=document.querySelector('#body-banks tbody td:nth-child(2)');
          window.accountActivations=0;td.ondblclick=()=>{window.accountActivations++};
          td.innerHTML='<div class="tableselect"><input maxlength="30"><button aria-label="选择表格数据">选取</button></div>';
          td.querySelector('button').onclick=()=>{throw new Error('wrong shortcut branch')};
          td.querySelector('input').onkeydown=e=>{if(e.key==='Enter'){let v=e.target.value;td.textContent=v}};
        }""")
        self.p._write('banks',0,'account','001234567890')
        self.assertEqual(self.p._read_rows('banks')[0]['fields']['account'],'001234567890')
        self.assertEqual(self.page.evaluate('accountActivations'),0)

    def test_table_locators_survive_dialog_body_class_changes(self):
        self.page.evaluate("document.body.className='ui-overflow-hidden'")
        cell=self.p._cell('costs',0,'reason')
        self.page.evaluate("document.body.className=''")
        self.assertEqual(cell.inner_text(),'测试行程')

    def test_cached_schema_detects_column_reorder_and_rebuilt_components(self):
        self.assertEqual(self.p._read_field('costs',0,'reason'),'测试行程')
        self.page.evaluate("""()=>{
          let c=document.querySelector('#component-costs');c.replaceWith(c.cloneNode(true));
          let h=document.querySelector('#head-costs tr');h.insertBefore(h.lastElementChild,h.firstElementChild);
          let r=document.querySelector('#body-costs tr');r.insertBefore(r.lastElementChild,r.firstElementChild);
        }""")
        self.assertEqual(self.p._read_field('costs',0,'reason'),'测试行程')
        self.assertEqual(self.p._read_field('costs',0,'project'),'其它交通')

    def test_ordinary_save_still_guarded_and_exact_capability_metadata(self):
        with self.assertRaises(RuntimeError):
            self.p._click_guard("保存")
        self.assertEqual(self.p.adapter.exact_save_button()["text"], "保存")
        self.page.locator("#save").evaluate("e=>e.textContent='保存并提交'")
        self.assertEqual(self.p.adapter.exact_save_button()["count"], 0)

    def _bind_changed_synthetic_facts(self):
        # Keep the executable plan tied to the updated synthetic source, so
        # these branch tests also run the real source/amount validator.
        proof = self.root / "facts.json"
        facts = json.loads(proof.read_text(encoding="utf-8"))
        facts.update({key: self.plan[key] for key in ("applicant", "header", "tables")})
        proof.write_text(json.dumps(facts, ensure_ascii=False), encoding="utf-8")
        digest = file_hash(proof)
        pointers = [f"/{block}/{key}" for block in ("applicant", "header") for key in self.plan[block]]
        pointers += [f"/tables/{table}/{index}/fields/{key}"
                     for table, rows in self.plan["tables"].items()
                     for index, row in enumerate(rows) for key in row["fields"]]
        self.plan["sources"] = {p: {"kind": "user", "path": str(proof), "sha256": digest, "locator": p}
                                for p in pointers}
        primary = "details" if self.plan["amount_rules"]["costs"] == "not_applicable" else "costs"
        self.plan["materials"]["no_invoice_rows"] = [
            {"plan_pointer": f"/tables/{primary}/{index}/fields/cost", "reason": facts["no_invoice_rule"],
             "proof": {"kind": "user", "path": str(proof), "sha256": digest, "locator": "/no_invoice_rule"}}
            for index, _ in enumerate(self.plan["tables"][primary])]
        self.p.bound_plan_hash = plan_hash(self.plan)
        self.assertEqual(validate_plan(self.plan, base_dir=self.root), [])

    def test_multiple_relation_types_execute_and_independently_reject_corruption(self):
        self.plan["tables"]["relations"] = [
            {"row_id": "r1", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000001", "nowCost": "10.00", "isLast": "是"}},
            {"row_id": "r2", "fields": {"bizTypeName": "出差单", "bizNumber": "12126000002", "nowCost": "10.00", "isLast": "否"}}]
        self._bind_changed_synthetic_facts()
        self.page.set_content(form_html(self.plan))
        self.page.locator("#body-relations tbody tr").last.evaluate("e=>e.remove()")
        original = self.p._ensure_row
        def ensure(key, index, fields=None):
            original(key, index, fields)
            if key == "relations":
                # Isolate array creation from modal discovery: emulate only
                # the selected object's exact identity, then exercise the real
                # type/number checks and amount/one-off cell editors.
                for prop in ("bizTypeName", "bizNumber"):
                    self.p._cell(key, index, prop).evaluate(
                        "(e,v)=>e.textContent=v", self.plan["tables"][key][index]["fields"][prop])
        self.p._ensure_row = ensure
        # The former synthetic second-type PASS did not prove real allocation
        # semantics. This branch is now explicitly outside the supported scope.
        with self.assertRaisesRegex(UIBlocked,"UNSUPPORTED_RELATION_DETAIL_BRANCH"):
            self.p._fill_arrays()
        snap=self.p.adapter.capture_snapshot()
        self.assertFalse(verify_snapshot(self.plan,snap)["ok"])

    def test_explicit_empty_costs_executes_and_never_masks_extra_or_missing_table(self):
        self.plan["tables"]["costs"] = []
        self.plan["amount_rules"].update(costs="not_applicable", costs_reason="测试明确费用说明不适用")
        self.plan["not_applicable"] = ["费用说明"]
        self._bind_changed_synthetic_facts()
        self.page.set_content(form_html(self.plan))
        self.p._fill_arrays()
        snap = self.p.adapter.capture_snapshot()
        self.assertTrue(snap["completeness"]["costs"])
        self.assertEqual(snap["tables"]["costs"], [])
        self.assertTrue(verify_snapshot(self.plan, snap)["ok"])
        self.page.evaluate("""()=>{
            let tr=document.createElement('tr');
            for(let i=0;i<8;i++){let td=document.createElement('td');td.textContent='unexpected';tr.appendChild(td);}
            document.querySelector('#body-costs tbody').appendChild(tr);
        }""")
        self.assertFalse(verify_snapshot(self.plan, self.p.adapter.capture_snapshot())["ok"])
        self.page.locator("#component-costs").evaluate("e=>e.remove()")
        self.assertFalse(verify_snapshot(self.plan, self.p.adapter.capture_snapshot())["ok"])
        self.page.set_content(form_html(self.plan))

    def test_real_ui_save_controller_reopens_intercepted_persisted_form(self):
        from bpm.save import SaveController
        saved_url = "https://bpm.qiaodan.com/oa/reimburse?type=view&id=" + "b" * 32
        saved_html = form_html(self.plan).replace('id="bizNumber0" name="bizNumber0" value=""',
                                                 'id="bizNumber0" name="bizNumber0" value="15426000002"')
        calls = []
        self.page.unroute("**/*")
        def serve(route):
            calls.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=saved_html)
        self.page.route("**/*", serve)
        self.page.locator("#save").evaluate("(e,url)=>e.onclick=()=>location.href=url", saved_url)
        result = SaveController(self.plan, self.p.adapter, self.p.attempt,
                                expected_operator=self.plan["operator"], journal_dir=self.root / "registry").run()
        self.assertEqual(result["status"], "SUCCESS_DRAFT_SAVED", result)
        self.assertGreaterEqual(len(calls), 2)  # post-save page and independent reopen
        self.assertTrue((self.p.ev / "draft_saved.png").is_file())

    def test_direct_or_changed_save_cannot_bypass_screenshot_and_revalidation(self):
        with self.assertRaises(UIBlocked):
            self.p.adapter.click_exact_save()
        self.p.adapter.screenshot("before_save")
        self.page.locator("#body-banks tbody td").nth(1).evaluate("e=>e.textContent='bad-account'")
        with self.assertRaises(UIBlocked):
            self.p.adapter.click_exact_save()

    def test_config_identity_drift_after_screenshot_prevents_ui_save_click(self):
        from dataclasses import replace
        from unittest import mock
        from bpm.types import resolve_type
        self.page.locator("#save").evaluate("e=>{window.saveClicks=0;e.onclick=()=>window.saveClicks++}")
        self.p.adapter.screenshot("before_save")
        changed = replace(resolve_type(self.plan["document_type"]), sha256="0" * 64)
        with mock.patch("bpm.types.resolve_type", return_value=changed):
            with self.assertRaises(UIBlocked):
                self.p.adapter.click_exact_save()
        self.assertEqual(self.page.evaluate("saveClicks"), 0)

    def test_targeted_live_list_discovery_is_local_intercepted_and_exact(self):
        from bpm.template import _target_list, open_exact_document
        number = "00123456789"
        items = [{"id": "b" * 32, "bizNumber": number + "0"},
                 {"id": "a" * 32, "bizNumber": number}]
        source = '''<!doctype html><meta charset="utf-8"><label for="BizNumber1">单据编号</label>
          <input id="BizNumber1"><label for="BizNumber22">关联单号</label><input id="BizNumber22">
          <table><thead><tr><th class="prop-submitType">类别</th></tr></thead></table>
          <button onclick="fetch('https://oa.api.qiaodan.com/reimburse/query/20/1?for=1')">查询</button>'''
        self.page.route("https://bpm.qiaodan.com/oa/reimburses", lambda route: route.fulfill(
            status=200, content_type="text/html", body=source))
        self.page.route("https://oa.api.qiaodan.com/**", lambda route: route.fulfill(
            status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
            body=json.dumps({"data": {"content": items}})))
        item, headers = _target_list(self.p, number)
        self.assertEqual(item["id"], "a" * 32)
        self.assertTrue(headers)
        self.assertEqual(self.page.locator("#BizNumber1").input_value(), number)
        self.assertEqual(self.page.locator("#BizNumber22").input_value(), "")
        self.assertEqual(open_exact_document(self.p, number, "a" * 32),
                         "https://bpm.qiaodan.com/oa/reimburse?type=view&id=" + "a" * 32)
        with self.assertRaises(ValueError):
            open_exact_document(self.p, number, "c" * 32)
        # A current creator filter can exclude a known history record. Only
        # explicit read-only research hints may resolve that case; save/reopen
        # lookup remains strict and cannot silently fall back to cached data.
        items.clear()
        hint = {"id": "a" * 32, "bizNumber": number}
        self.assertEqual(_target_list(self.p, number, identity_hint=hint)[0], hint)
        with self.assertRaises(ValueError):
            open_exact_document(self.p, number, "a" * 32)

    def test_history_view_research_reads_labels_and_rows_without_editing(self):
        from bpm.template import observe_template_view
        number, uid = "15426000002", "b" * 32
        url = "https://bpm.qiaodan.com/oa/reimburse?type=view&id=" + uid
        source = form_html(self.plan).replace('id="bizNumber0" name="bizNumber0" value=""',
                                              'id="bizNumber0" name="bizNumber0" value="' + number + '"')
        source += "<script>window.saveClicks=0;document.querySelector('#save').onclick=()=>window.saveClicks++;</script>"
        self.page.route(url, lambda route: route.fulfill(status=200, content_type="text/html", body=source))
        observation = observe_template_view(self.p, {"biz_number": number, "uuid": uid})
        self.assertEqual(observation["operator"], self.plan["operator"])
        self.assertFalse(observation["new_form_editors_verified"])
        details = [t for t in observation["tables"] if t["title"] == "报销明细"]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["rows"][0]["fields"]["digest"], self.plan["tables"]["details"][0]["fields"]["digest"])
        self.assertEqual(self.page.evaluate("saveClicks"), 0)
        self.assertTrue((self.p.ev / "template_view_observation.json").is_file())

    def _use_new_type_fixture(self, kind, **options):
        from test_bpm_new_types import build_type_plan
        from bpm.types import resolve_type
        self.plan, path = build_type_plan(self.root / kind, kind, **options)
        self.plan["authorization"]["mode"] = "save_draft"
        self.p.fill_plan = self.plan
        self.p.type_config = load_type(kind)
        self.p.config_hash = resolve_type(kind).sha256
        self.p.bound_plan_hash = plan_hash(self.plan)
        self.p.plan_base = path.parent
        self.p.args.expect_name = self.plan["operator"]
        self.page.set_content(form_html(self.plan))

    def test_express_multiline_independent_readback_rejects_last_row_drift(self):
        self._use_new_type_fixture("express", cost_count=3)
        self.p._fill_arrays()
        snapshot = self.p.adapter.capture_snapshot()
        self.assertTrue(verify_snapshot(self.plan, snapshot)["ok"])
        self.page.locator("#body-costs tbody tr").last.locator("td").nth(6).evaluate("e=>e.textContent='wrong last reason'")
        self.assertFalse(verify_snapshot(self.plan, self.p.adapter.capture_snapshot())["ok"])

    def test_wrong_category_blocks_before_any_business_row_write(self):
        from unittest import mock
        self._use_new_type_fixture("express")
        self.page.locator("#submitType0").evaluate("e=>{e.value='差旅费';e.readOnly=true}")
        with mock.patch.object(self.p, "_write") as write:
            with self.assertRaisesRegex(UIBlocked, "CATEGORY_READONLY_MISMATCH"):
                self.p._fill_arrays()
            write.assert_not_called()
        self.page.locator("#submitType0").evaluate("e=>e.readOnly=false")
        with mock.patch.object(self.p, "_ng_write", return_value=("OK", {}, {})), \
             mock.patch.object(self.p, "_write") as write:
            with self.assertRaisesRegex(UIBlocked, "CATEGORY_ECHO_MISMATCH"):
                self.p._fill_arrays()
            write.assert_not_called()

    def test_missing_employee_id_identity_blocks_before_any_business_write(self):
        # R7 v1 真实反例固化（run 20261024-160024-8502f91d）：页面默认申请人与计划
        # 不同、计划无 identity（缺申请人工号）→ COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED
        # 硬阻断，且必须发生在任何业务写入之前（header 未写、四张业务表零行）。
        from unittest import mock
        self.page.set_content(form_html(self.plan, blank=True))
        self.page.locator("#appliedName0").evaluate("e=>e.value='另一个人'")
        self.assertNotIn("identity", self.plan)
        with mock.patch.object(self.p, "_write_header") as write_header, \
             mock.patch.object(self.p, "_fill_arrays") as fill_arrays:
            with self.assertRaisesRegex(UIBlocked, "COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED"):
                self.p._phase_fill_ng(self.page, None, self.plan)
            write_header.assert_not_called()
            fill_arrays.assert_not_called()
        snap = self.p.adapter.capture_snapshot()
        self.assertTrue(all(not rows for rows in snap["tables"].values()))

    def test_exact_pick_missing_transient_failure_yields_no_partial_acceptance(self):
        # R7 v3 真实反例固化（run 20261024-162157-04150c78）：关联选择瞬时 0 候选 →
        # EXACT_PICK_MISSING 硬阻断不吞不补；已填行不得构成部分验收（独立回读必拒）。
        from unittest import mock
        self.plan["tables"]["relations"] = [
            {"row_id": "r1", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000001", "nowCost": "10.00", "isLast": "是"}},
            {"row_id": "r2", "fields": {"bizTypeName": "公出单", "bizNumber": "12026000002", "nowCost": "20.00", "isLast": "否"}}]
        self._bind_changed_synthetic_facts()
        self.page.set_content(form_html(self.plan))
        self.page.locator("#body-relations tbody tr").last.evaluate("e=>e.remove()")
        original = self.p._ensure_row
        def ensure(key, index, fields=None):
            original(key, index, fields)
            if key != "relations":
                return
            row = self.plan["tables"]["relations"][index]["fields"]
            if index == 0:
                # 行0照常完成（模拟已成功写入的行），为"部分状态"提供对照组。
                for prop in ("bizTypeName", "bizNumber"):
                    self.p._cell(key, index, prop).evaluate("(e,v)=>e.textContent=v", row[prop])
            else:
                # 行1复刻真实页关联号单元格：.tableselect 选择器按钮、无可写 input。
                cell = self.p._cell(key, index, "bizNumber")
                cell.evaluate("""e=>{e.textContent='';let s=document.createElement('span');
                    s.className='tableselect';let b=document.createElement('button');
                    b.setAttribute('aria-label','选择表格数据');s.appendChild(b);e.appendChild(s);}""")
                self.p._cell(key, index, "bizTypeName").evaluate("(e,v)=>e.textContent=v", row["bizTypeName"])
        self.p._ensure_row = ensure
        real_pick = self.p._overlay_search_pick
        def transient_zero_candidates(page, frame, keyword, tag, prescan=False, first_data_row=False):
            if "relations/1" in str(tag):
                return None  # 瞬时 0 候选（R7 v3 实测形态：prescan 无命中）
            return real_pick(page, frame, keyword, tag, prescan, first_data_row)
        with mock.patch.object(self.p, "_overlay_search_pick", side_effect=transient_zero_candidates):
            with self.assertRaisesRegex(UIBlocked, "EXACT_PICK_MISSING:relations/1/bizNumber"):
                self.p._fill_arrays()
        snap = self.p.adapter.capture_snapshot()
        # 行0完整；行1行体已挂但关联号因瞬时 0 候选未写入（不吞不补，保持阻断现场）。
        self.assertEqual(snap["tables"]["relations"][0]["fields"]["bizNumber"], "12026000001")
        self.assertEqual(snap["tables"]["relations"][1]["fields"]["bizNumber"], "")
        self.assertFalse(verify_snapshot(self.plan, snap)["ok"])  # 部分状态不得通过独立回读

    def test_header_generated_default_bank_is_distinguished_from_existing_data(self):
        self._use_new_type_fixture("express")
        self.page.set_content(form_html(self.plan, blank=True))
        before = self.p.adapter.capture_snapshot()
        self.p.pre_header_snapshot = copy.deepcopy(before)
        fields = dict(self.plan["tables"]["banks"][0]["fields"], payee=self.plan["applicant"]["name"], cost="")
        self.page.evaluate("fields=>{let tr=document.createElement('tr');Object.values(fields).forEach(v=>{let td=document.createElement('td');td.textContent=v;tr.appendChild(td)});document.querySelector('#body-banks tbody').appendChild(tr)}", fields)
        self.p._check_initial_page()
        self.p.pre_header_snapshot = None
        with self.assertRaisesRegex(UIBlocked, "INITIAL_BANK_IDENTITY_MISMATCH"):
            self.p._check_initial_page()

        self.p.pre_header_snapshot = copy.deepcopy(before)
        self.p.pre_header_snapshot["tables"]["banks"] = [{"fields": fields}]
        with self.assertRaisesRegex(UIBlocked, "INITIAL_BANK_IDENTITY_MISMATCH"):
            self.p._check_initial_page()
        self.p.pre_header_snapshot = copy.deepcopy(before)
        self.p.pre_header_snapshot["completeness"]["banks"] = False
        with self.assertRaisesRegex(UIBlocked, "INITIAL_BANK_IDENTITY_MISMATCH"):
            self.p._check_initial_page()
        self.p.pre_header_snapshot = before
        self.page.locator("#body-banks tbody td").last.evaluate("e=>e.textContent='1.00'")
        with self.assertRaisesRegex(UIBlocked, "INITIAL_BANK_IDENTITY_MISMATCH"):
            self.p._check_initial_page()


    def test_product_add_control_observation_captures_actual_row_editors(self):
        from automation.prepare_type_replay_test import inspect_product_controls
        self._use_new_type_fixture("rd_materials")
        self.page.set_content(form_html(self.plan, blank=True))
        controls = inspect_product_controls(self.p)
        self.assertEqual({c["prop"] for c in controls}, {"code", "name", "purchaser", "price", "description"})
        self.assertTrue((self.p.ev / "product_add_controls.json").is_file())

    def test_rd_archive_picker_fifth_table_save_reopen_and_readonly_recovery(self):
        from bpm.save import SaveController
        self._use_new_type_fixture("rd_materials", product_count=3)
        products = [row["fields"] for row in self.plan["tables"]["products"]]
        self.page.evaluate(r"""products=>{
          document.querySelector('#body-products tbody').textContent='';
          document.querySelector('#body-products').addEventListener('dblclick',e=>{
            let cell=e.target.closest('td');
            if(!cell || cell.cellIndex!==1)return;
            e.stopPropagation();cell.textContent='';
            let host=document.createElement('span');host.className='tableselect';
            host.innerHTML='<input readonly><button aria-label="选择表格数据">选择</button>';cell.appendChild(host);
            host.querySelector('button').onclick=()=>{
            let dialog=document.createElement('div');dialog.className='ui-dialog';
            dialog.innerHTML='<table><tbody></tbody></table><div class="ui-dialog-footer"><button>确定</button></div>';
            let chosen=null;
            for(let product of products){
              let row=document.createElement('tr');row.innerHTML='<td>'+product.code+'</td><td>'+product.name+'</td>';
              row.onclick=()=>{dialog.querySelectorAll('tr').forEach(x=>x.classList.remove('ui-state-highlight'));row.classList.add('ui-state-highlight');chosen=product};
              dialog.querySelector('tbody').appendChild(row);
            }
            dialog.querySelector('button').onclick=()=>{
              if(!chosen)return;
              let row=cell.parentElement;
              ['code','name','purchaser','price','description'].forEach((key,i)=>row.cells[i].textContent=chosen[key]);dialog.remove();
            };
            document.body.appendChild(dialog);
            };
          });
        }""", products)
        self.p._fill_arrays()
        snapshot = self.p.adapter.capture_snapshot()
        check = verify_snapshot(self.plan, snapshot)
        self.assertTrue(check["ok"], check)
        self.assertEqual(check["amounts"]["products"], "12.00")
        self.assertTrue(snapshot["completeness"]["products"])
        saved_url = "https://bpm.qiaodan.com/oa/reimburse?type=view&id=" + "b" * 32
        saved_html = form_html(self.plan).replace('id="bizNumber0" name="bizNumber0" value=""',
                                                'id="bizNumber0" name="bizNumber0" value="15426000002"')
        self.page.unroute("**/*")
        self.page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=saved_html))
        self.page.locator("#save").evaluate("(e,url)=>e.onclick=()=>location.href=url", saved_url)
        def controller():
            return SaveController(self.plan, self.p.adapter, self.p.attempt, expected_operator=self.plan["operator"],
                                  base_dir=self.p.plan_base, journal_dir=self.root / "registry")
        first = controller().run()
        self.assertEqual(first["status"], "SUCCESS_DRAFT_SAVED", first)
        second = controller().run()
        self.assertEqual(second["status"], "SUCCESS_DRAFT_SAVED", second)
        self.page.locator("#body-products tbody tr").last.locator("td").nth(3).evaluate("e=>e.textContent='5.00'")
        self.assertFalse(verify_snapshot(self.plan, self.p.adapter.capture_snapshot(), phase="after_save")["ok"])
        self.page.evaluate("""()=>{
          let th=document.createElement('th');th.className='prop-count';th.textContent='unmodeled quantity';
          document.querySelector('#head-products tr').appendChild(th);
          document.querySelectorAll('#body-products tbody tr').forEach(r=>{let td=document.createElement('td');td.textContent='2';r.appendChild(td)});
        }""")
        check = verify_snapshot(self.plan, self.p.adapter.capture_snapshot(), phase="after_save")
        self.assertIn("UNMODELED_BUSINESS_FIELD", [i["code"] for i in check["issues"]])


class DeadIntentSupersedeTests(unittest.TestCase):
    """R7 零写入死意图显式接替：仅 FORM_INTENT+四表全空证据+无存活页才可接替。"""

    def setUp(self):
        from bpm.ui import supersede_dead_form_intent
        self.supersede = supersede_dead_form_intent
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.registry = self.root / "task-registry"
        self.registry.mkdir()
        self.runs = self.root / "runs"
        prior_attempt = self.runs / "20261024-000000-prior" / "attempt_001" / "evidence"
        prior_attempt.mkdir(parents=True)
        (prior_attempt / "blocked_readback.json").write_text(json.dumps(
            {"page": {"is_new": True}, "applicant": {"name": "旧默认人"},
             "tables": {"relations": [], "details": [], "costs": [], "banks": []}}), encoding="utf-8")
        self.lifecycle = self.registry / ("a" * 64 + ".form.json")
        self.lifecycle.write_text(json.dumps(
            {"task_id": "TSK-R7", "state": "FORM_INTENT", "run": "20261024-000000-prior",
             "attempt": "attempt_001", "plan_hash": "1" * 64}), encoding="utf-8")
        self.new_run = self.runs / "20261024-000100-new"
        self.new_run.mkdir(parents=True)

    def call(self, pages=(), log_event=None):
        return self.supersede(self.lifecycle, runs_root=self.runs, new_run_dir=self.new_run,
                              new_attempt="attempt_001", new_plan_hash="2" * 64, ctx_pages=pages,
                              log_event=log_event)

    def test_zero_write_intent_superseded_with_audit_history(self):
        events = []
        self.assertTrue(self.call(log_event=lambda **kw: events.append(kw)))
        state = json.loads(self.lifecycle.read_text(encoding="utf-8"))
        self.assertEqual(state["plan_hash"], "2" * 64)
        self.assertEqual(state["run"], "20261024-000100-new")
        record = state["superseded_intents"][-1]
        self.assertEqual(record["event"], "PLAN_REVISION_ZERO_WRITE_SUPERSEDE")
        self.assertEqual(record["plan_hash"], "1" * 64)
        self.assertEqual(events[0]["event"], "form_intent_superseded")

    def test_nonempty_tables_refuse_and_file_untouched(self):
        before = self.lifecycle.read_text(encoding="utf-8")
        snapshot = self.runs / "20261024-000000-prior" / "attempt_001" / "evidence" / "blocked_readback.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["tables"]["details"] = [{"row_id": "d0"}]
        snapshot.write_text(json.dumps(payload), encoding="utf-8")
        self.assertFalse(self.call())
        self.assertEqual(self.lifecycle.read_text(encoding="utf-8"), before)

    def test_missing_evidence_refuses(self):
        (self.runs / "20261024-000000-prior" / "attempt_001" / "evidence" / "blocked_readback.json").unlink()
        self.assertFalse(self.call())

    def test_save_states_never_supersede(self):
        for state_name in ("SAVE_INTENT", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED"):
            payload = json.loads(self.lifecycle.read_text(encoding="utf-8"))
            payload["state"] = state_name
            self.lifecycle.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(self.call(), state_name)

    def test_live_oa_form_page_refuses(self):
        page = types.SimpleNamespace(url="https://bpm.qiaodan.com/oa/reimburse?type=new")
        self.assertFalse(self.call(pages=[page]))
        other = types.SimpleNamespace(url="https://bpm.qiaodan.com/oa/home")
        self.assertTrue(self.call(pages=[other]))

    def test_written_but_never_saved_intent_rebuilds_with_row_audit(self):
        snapshot = self.runs / "20261024-000000-prior" / "attempt_001" / "evidence" / "blocked_readback.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["tables"]["relations"] = [{"row_id": "r0"}, {"row_id": "r1"}]
        payload["tables"]["details"] = [{"row_id": "d0"}]
        snapshot.write_text(json.dumps(payload), encoding="utf-8")
        result = self.runs / "20261024-000000-prior" / "attempt_001" / "stage1_result.json"
        result.write_text(json.dumps({"task_status": "NEEDS_INPUT", "save_status": "NOT_ATTEMPTED"}),
                          encoding="utf-8")
        self.assertTrue(self.call())
        record = json.loads(self.lifecycle.read_text(encoding="utf-8"))["superseded_intents"][-1]
        self.assertEqual(record["event"], "DEAD_INTENT_REBUILD_SUPERSEDE")
        self.assertEqual(record["lost_page_rows"], {"relations": 2, "details": 1, "costs": 0, "banks": 0})

    def test_written_intent_without_save_status_proof_refuses(self):
        snapshot = self.runs / "20261024-000000-prior" / "attempt_001" / "evidence" / "blocked_readback.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["tables"]["relations"] = [{"row_id": "r0"}]
        snapshot.write_text(json.dumps(payload), encoding="utf-8")
        # 缺 stage1_result（save 证据不可知）→ 拒绝
        self.assertFalse(self.call())
        # save 曾有不确定态 → 拒绝
        result = self.runs / "20261024-000000-prior" / "attempt_001" / "stage1_result.json"
        result.write_text(json.dumps({"task_status": "NEEDS_INPUT", "save_status": "SAVE_UNCERTAIN"}),
                          encoding="utf-8")
        self.assertFalse(self.call())


if __name__ == "__main__":
    unittest.main()
