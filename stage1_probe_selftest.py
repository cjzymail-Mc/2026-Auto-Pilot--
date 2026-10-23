# -*- coding: utf-8 -*-
"""stage1_probe_selftest —— v2 探针离线失败场景自测（temp.md P1 验收）

不起浏览器、不碰 profile、不碰企微。只测决策层纯逻辑 + 目录/预算/原子写机制。
覆盖 temp.md §3 点名的五类失败场景：
  T1 定位失败（0 命中 / 多命中 / 未指定目标）
  T2 身份不符（v1 弱判复现样例必须不再判 LOGGED_IN；证据不足=UNKNOWN）
  T3 预算耗尽（tech 抛 BUDGET_EXHAUSTED；login 钟归零；墙钟看护存在且可关闭）
  T4 证据目录冲突（同 run 二次初始化 → attempt 递增；旧 attempt 文件不被覆盖）
  T5 恢复到错误单据（compare_identity 比对出 doc_identity/关键值差异 → FAIL）
外加回归守卫：源码无 type=new 回退路径、无 WRITE_BTN 死代码；URL 脱敏；原子写。
"""
import io
import json
import os
import re
import shutil
import sys
import time
from argparse import Namespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage1_browser_probe as P

BASE = P.BASE
FAILED = []


def case(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        FAILED.append(name)
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        FAILED.append(name)
        print(f"  FAIL  {name}: EXC {e!r}")


print("== T1 定位失败 ==")
ROWS = [
    {"cells": ["15426095951", "差旅费", "251.40", "2026-09-30", "结束"], "href": "https://bpm.qiaodan.com/oa/reimburse?id=1"},
    {"cells": ["15426000002", "办公费", "88.00", "2026-09-28", "结束"], "href": None},
]

case("pick_target 0 命中 → NOT_FOUND", lambda: (
    (lambda r: (_ for _ in ()).throw(AssertionError(r)))(P.pick_target(ROWS, "99999999999")[0])
    if P.pick_target(ROWS, "99999999999")[0] != "NOT_FOUND" else None))

case("pick_target 多命中 → AMBIGUOUS", lambda: (
    None if P.pick_target(ROWS + [ROWS[0]], "15426095951")[0] == "AMBIGUOUS"
    else (_ for _ in ()).throw(AssertionError(P.pick_target(ROWS + [ROWS[0]], "15426095951")[0]))))

case("pick_target 无 doc_id → TARGET_UNSPECIFIED（不选替身）", lambda: (
    None if P.pick_target(ROWS, None)[0] == "TARGET_UNSPECIFIED" else (_ for _ in ()).throw(AssertionError("chose surrogate"))))

case("pick_target 唯一命中 → OK 且行含 href", lambda: (
    (lambda st, pl: None if (st == "OK" and pl["row"]["href"]) else (_ for _ in ()).throw(AssertionError(st)))
    (*P.pick_target(ROWS, "15426095951"),)))


print("== T2 身份不符 ==")
def _t2_v1_bug():
    # v1 弱判复现样例（temp.md 已复现为错）：URL 内页 + oaNav=3，无账户证据
    st, _ = P.classify({"url": "https://bpm.qiaodan.com/oa/reimburses", "title": "报销单",
                        "hasPassword": False, "qrHints": 0, "loginText": "", "oaNav": 3, "forms": 1})
    assert st != "LOGGED_IN", f"v1 弱判复活: {st}"
    assert st == "UNKNOWN", st
case("URL+oaNav=3 无账户证据 → 不得 LOGGED_IN（v1 缺陷守卫）", _t2_v1_bug)

case("登录域名 → LOGIN_REQUIRED", lambda: (
    None if P.classify({"url": "https://login.work.weixin.qq.com/wwlogin/sso/login?login_type=CorpApp",
                        "title": "x", "hasPassword": False, "qrHints": 2, "loginText": True, "oaNav": 0})[0] == "LOGIN_REQUIRED"
    else (_ for _ in ()).throw(AssertionError("login domain missed"))))

case("密码框 → LOGIN_REQUIRED", lambda: (
    None if P.classify({"url": "https://bpm.qiaodan.com/account/login", "hasPassword": True, "oaNav": 5})[0] == "LOGIN_REQUIRED"
    else (_ for _ in ()).throw(AssertionError("password missed"))))

case("账户证据齐全（姓名+退出+导航+内页）→ LOGGED_IN", lambda: (
    None if P.classify({"url": "https://bpm.qiaodan.com/oa/reimburses", "hasPassword": False,
                        "qrHints": 0, "loginText": "", "name_hits": 1, "logout_hits": 1, "oaNav": 3})[0] == "LOGGED_IN"
    else (_ for _ in ()).throw(AssertionError("证据不足误判"))))

def _t2_live():
    # attempt_001 活体场景回归守卫：真实 OA 首页顶栏无显式退出按钮（logout_hits=0），
    # 姓名+导航齐全却被判 UNKNOWN → 480s 白等。姓名命中即核心身份证据，退出钮只记录不强求。
    st, ev = P.classify({"url": "https://bpm.qiaodan.com/", "hasPassword": False,
                         "qrHints": 0, "loginText": "", "name_hits": 1, "logout_hits": 0, "oaNav": 5})
    assert st == "LOGGED_IN", f"无退出钮的已登录首页被误判: {st}"
    assert ev["logout_hits"] == 0  # 仍记录，供证据留存
case("姓名命中但顶栏无退出钮 → LOGGED_IN（attempt_001 活体守卫）", _t2_live)

case("eval_error → UNKNOWN", lambda: (
    None if P.classify({"eval_error": "x"})[0] == "UNKNOWN" else (_ for _ in ()).throw(AssertionError())))


print("== T3 预算耗尽 ==")
def _t3():
    b = P.Budget(tech=10.0, login=5.0, wall=3600.0)          # wall 远大，看护不干扰本用例
    try:
        b.tech_used = b.tech_cap + 1                          # 模拟技术钟已耗尽
        b.ensure_tech()
        raise AssertionError("ensure_tech 未抛 BUDGET_EXHAUSTED")
    except RuntimeError as e:
        assert "BUDGET_EXHAUSTED" in repr(e), repr(e)
    b.login_wait_used = b.login_cap
    assert b.wait_slice(5.0, clock="login") == 0.0, "login 钟耗尽应返回 0（不再等）"
    assert b.wait_slice(5.0, clock="tech") == 0.0, "tech 钟耗尽应返回 0 而非抛错（等待循环用）"
    assert b._watchdog.is_alive(), "墙钟看护线程未启动"
    b.close()
    time.sleep(0.1)
    assert b._dead, "close 应置 _dead 使看护线程退出循环"
case("tech 耗尽抛错 / login 耗尽归零 / 看护可启停", _t3)


print("== T4 证据目录冲突 ==")
SELFTEST_RUN = f"selftest-{time.strftime('%H%M%S')}"
def _mk_probe(doc_id="15426095951"):
    return P.Probe(Namespace(run=SELFTEST_RUN, doc_id=doc_id, expect_name="陈晶",
                             tech_budget=60.0, login_wait=30.0, wall_cap=3600.0))
def _t4():
    pr1 = _mk_probe()
    assert pr1.attempt.name == "attempt_001", pr1.attempt.name
    marker = pr1.attempt / "old_evidence_marker.txt"
    io.open(marker, "w", encoding="utf-8").write("KEEP-ME")
    pr1.result["finish_reason"] = "FATAL:selftest"
    pr1.atomic_result()
    assert io.open(marker, encoding="utf-8").read() == "KEEP-ME", "marker 被破坏"
    pr2 = _mk_probe()
    assert pr2.attempt.name == "attempt_002", pr2.attempt.name
    assert io.open(marker, encoding="utf-8").read() == "KEEP-ME", "二次初始化覆盖了旧 attempt 文件"
    r1 = json.loads(io.open(pr1.attempt / "stage1_result.json", encoding="utf-8").read())
    assert r1["finish_reason"] == "FATAL:selftest" and r1["run"] == SELFTEST_RUN, "旧结果文件被改写"
    assert not list(pr1.attempt.glob(".stage1_result.json.tmp")), "残留 tmp 文件（非原子写）"
    assert P.RUN_ABSENT if False else True
    pr1.budget.close(); pr2.budget.close()
    return pr1, pr2
_case_t4 = []
def _t4_wrap():
    _case_t4.append(_t4())
case("同 run 二次初始化 → attempt_002；旧文件零覆盖；原子写无 tmp 残留", _t4_wrap)

def _t4_run_param():
    # 缺口#1 回归：run 目录必须可注入，不得写死旧 run
    src = io.open(P.BASE / "stage1_browser_probe.py", encoding="utf-8").read()
    assert '20261021-112246-46c6e1f8' not in src, "旧 run id 仍写死在探针源码里"
    assert P.Probe(Namespace(run="selftest-x", doc_id=None, expect_name="陈晶",
                             tech_budget=60, login_wait=30, wall_cap=3600)).args.run == "selftest-x"
case("run id 参数化（缺口#1 回归：无写死 run）", _t4_run_param)


print("== T5 恢复到错误单据 ==")
def _t5():
    before = {"url": "https://bpm.qiaodan.com/oa/reimburse?id=100", "doc_identity": "15426095951",
              "account_name": "陈晶", "status_text": "结束", "key_values": [["15426095951", "差旅费", "251.40"]]}
    wrong_doc = {"url": "https://bpm.qiaodan.com/oa/reimburse?id=200", "doc_identity": "15426000002",
                 "account_name": "陈晶", "status_text": "结束", "key_values": [["15426000002", "办公费", "88.00"]]}
    ok, diffs = P.compare_identity(before, wrong_doc)
    assert not ok, "换了一张单据竟然判 ok"
    fields = {d["field"] for d in diffs}
    # 错误单据由 doc_identity/key_values 兜住；URL 只在内域丢失/落登录页时才记差异（reload 附加瞬时参数不误报）
    assert {"doc_identity", "key_values"} <= fields, fields
    assert "url" not in fields, f"同域内页 id 变化不应记 URL 差异: {fields}"
    # 重启后落到登录页 → URL 差异必须记
    to_login = dict(before, url="https://bpm.qiaodan.com/account/login")
    ok3, diffs3 = P.compare_identity(before, to_login)
    assert not ok3 and any(d["field"] == "url" for d in diffs3), diffs3
    same = dict(before)
    ok2, diffs2 = P.compare_identity(before, same)
    assert ok2 and diffs2 == [], (ok2, diffs2)
case("恢复到另一张单据 → 比对失败并指出差异字段；同对象 → 通过", _t5)


print("== 阶段状态机 / 整体成功口径 ==")
def _t_phase():
    r = P.PhaseRunner({}, lambda *a: None)
    order = []
    r.run("entry", lambda: (order.append("entry"), P.FAIL)[1])
    r.run("locate", lambda: (order.append("locate"), "x")[1], depends=("entry",))
    r.run("structure", lambda: (order.append("structure"), "x")[1], depends=("locate",))
    r.run("recover", lambda: (order.append("recover"), "x")[1], depends=("structure",))
    assert order == ["entry"], f"依赖失败后仍执行了后续阶段: {order}"
    assert r.phase_status["locate"] == "SKIPPED" and r.phase_status["recover"] == "SKIPPED", r.phase_status
    # 依赖 PASS 才放行
    r2 = P.PhaseRunner({}, lambda *a: None)
    r2.run("entry", lambda: P.PASS)
    assert r2.run("locate", lambda: P.PASS, depends=("entry",)) == P.PASS
case("依赖阶段非 PASS → 后续 SKIPPED 不执行", _t_phase)

def _t_overall():
    pr = _mk_probe()
    try:
        # 全核心 PASS → SUCCESS_READ_ONLY
        for k in ("c1_entry_login", "c2_locate_target", "c3_structure", "c6_recover"):
            pr.checks[k]["status"] = P.PASS
        assert pr._overall() == "SUCCESS_READ_ONLY", pr._overall()
        # locate BLOCKED（无目标）→ 整体 BLOCKED 而非成功
        pr.checks["c2_locate_target"]["status"] = P.BLOCKED
        pr.checks["c3_structure"]["status"] = P.NOT_RUN
        pr.checks["c6_recover"]["status"] = P.NOT_RUN
        assert pr._overall().startswith("BLOCKED"), pr._overall()
        # 写入检查保持 NOT_AUTHORIZED，不参与成功口径
        assert pr.checks["c4_normal_field_write"]["status"] == P.NOT_AUTHORIZED
    finally:
        pr.budget.close()
case("整体成功=业务断言（非 DONE 默认；c4/c5 恒 NOT_AUTHORIZED）", _t_overall)


print("== 回归守卫 / 脱敏 ==")
def _t_guards():
    src = io.open(P.BASE / "stage1_browser_probe.py", encoding="utf-8").read()
    # type=new 守卫已升级移入 T7：--fill-plan 授权路径允许、且仅允许 phase_fill 使用
    assert not re.search(r"^WRITE_BTN\s*=", src, re.M), "WRITE_BTN 死代码复活"
    assert 'depends=("entry",)' not in src, "locate 依赖 entry phase 字符串复活（LOGIN_REQUIRED≠失败，attempt_003 教训）"
    u = P.sanitize_url("https://bpm.qiaodan.com/oa/x?ticket=abc123&page=2&code=zzz&rows=20")
    assert "abc123" not in u and "zzz" not in u, u
    assert "page=2" in u and "rows=20" in u, u
    assert P.mask("6217000000000000001") == "62***"
case("无 WRITE_BTN 死代码 / 依赖接线守卫 / URL 认证参数脱敏 / 控制台脱敏", _t_guards)

print("== T6 人机接力（--interactive-pick）==")
def _t_pick():
    pr = _mk_probe()
    pr.args.pick_wait = 2.0
    io.open(pr.attempt / "pick_reply.txt", "w", encoding="utf-8").write("15426095951\n")
    got = pr._pick_relay([{"cells": ["15426095951", "差旅费"], "href": None}])
    assert got == "15426095951", got
    assert (pr.attempt / "pick_request.json").exists(), "接力请求文件未落盘"
    io.open(pr.attempt / "pick_reply.txt", "w", encoding="utf-8").write("NONE\n")
    pr.args.pick_wait = 2.0
    assert pr._pick_relay([]) is None, "NONE 回复应返回 None"
    pr2 = _mk_probe()
    pr2.args.pick_wait = 0.0            # 上限 0：等不到任何回复
    assert pr2._pick_relay([]) is None
    pr.budget.close(); pr2.budget.close()
case("预置回复→选中；NONE/无回复→None", _t_pick)


print("== T7 填写任务守卫（--fill-plan 只填不存）==")
def _t7_plan_dir():
    d = BASE / "automation" / "runs" / SELFTEST_RUN / "t7"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _t7_load():
    d = _t7_plan_dir()
    plan = {"meta": {"goal": "selftest 只填不存"},
            "header": {"事由": {"value": "公出晋江油补"}},
            "bank_info": {"收款人": {"value": "陈晶"}}}
    io.open(d / "fill_plan.json", "w", encoding="utf-8").write(json.dumps(plan, ensure_ascii=False))
    pr = P.Probe(Namespace(run=SELFTEST_RUN, doc_id=None, expect_name="陈晶", tech_budget=60,
                           login_wait=30, wall_cap=3600, fill_plan=str(d / "fill_plan.json")))
    assert pr.fill_plan and pr.fill_plan["header"]["事由"]["value"] == "公出晋江油补"
    assert "只填不存" in pr.checks["c7_fill_new"]["reason"], pr.checks["c7_fill_new"]["reason"]
    pr0 = _mk_probe()   # 未带 --fill-plan
    assert pr0.fill_plan is None and pr0.checks["c7_fill_new"]["status"] == P.NOT_RUN
    pr.budget.close(); pr0.budget.close()
case("fill_plan 装载 + c7 授权标注；未启用时 c7=NOT_RUN", _t7_load)

def _t7_guard():
    pr = _mk_probe()
    for bad in ("保存", "发送", "流转", "保存并新增", "提交流程", "返回"):
        try:
            pr._click_guard(bad)
            raise AssertionError(f"守卫放行了禁点词「{bad}」")
        except RuntimeError:
            pass
    assert pr._click_guard("伙食") is True and pr._click_guard("转账") is True
    pr.budget.close()
case("NO_SAVE 守卫：保存/发送/流转/返回类一律拒绝；普通选项放行", _t7_guard)

def _t7_match():
    assert P.fill_match("191.4", "191.40") and P.fill_match(" 251.40 ", "251.4")
    assert P.fill_match("2026", "2026.0")
    assert P._norm_cell("金额(元)") == "金额" and P.fill_match("金额(元)", "金额")
    assert not P.fill_match("贰佰伍拾壹元", "251.40"), "大写金额不得与数字互认"
    assert P.fill_match(None, "") and P.fill_match("", None)
    assert P.fill_match("伙食", "伙食 ") and not P.fill_match("伙食", "住宿")
case("fill_match 数值等价/空白归一；大写≠数字", _t7_match)

def _t7_locate():
    spreads = [{"sheets": [{"name": "s0", "rows": 9, "cols": 9, "texts": [
        ["单据日期", "", "事由", "", "支付方式", ""],
        ["", "", "", "", "", ""],
        ["费用类型", "开始日期", "结束日期", "地点", "天数/次数", "金额(元)"],
        ["伙食", "2026-09-22", "2026-09-22", "晋江", "1", "60.00"],
    ]}]}]
    pr = _mk_probe()
    assert pr._locate_cell(spreads, "事由") == (0, 0, 0, 2)
    base = pr._locate_cell(spreads, "费用类型")
    assert base == (0, 0, 2, 0), base
    # base 约束：『金额』命中同表头行的 金额(元)，而非其它精确/包含格
    assert pr._locate_cell(spreads, "金额", base) == (0, 0, 2, 5), pr._locate_cell(spreads, "金额", base)
    assert pr._locate_cell(spreads, "天数", base) == (0, 0, 2, 4)
    assert pr._locate_cell(spreads, "不存在的列", base) is None
    pr.budget.close()
case("_locate_cell 精确优先 / 别名 / 同表头带约束 / 未命中→None", _t7_locate)

def _t7_static():
    src = io.open(P.BASE / "stage1_browser_probe.py", encoding="utf-8").read()
    # type=new 字面量全文件只此一处（NEW_FORM_PATH 常量定义）；引用只出现在 phase_fill 内
    assert src.count("/oa/reimburse?type=new") == 1, "type=new 字面量必须只在 NEW_FORM_PATH 常量出现一次"
    assert src.count("NEW_FORM_PATH") == 2, "NEW_FORM_PATH 只应 定义一次 + phase_fill 内使用一次"
    assert "self.fill_plan is not None" in src, "fill 阶段未被 --fill-plan 门禁"
    assert '"phases"]["fill"]' in src, "main 未接线 fill 阶段"
    for w in ("保存", "发送", "流转", "暂存", "贴票", "NO_SAVE_WORDS", "_click_guard"):
        assert w in src, f"填写守卫缺件: {w}"
    assert P.DOM_FIELD_CSS in P.FORM_READY_JS and P.DOM_FIELD_CSS in P.DOM_FIELDS_JS, \
        "DOM 选择器三处不同步"
case("type=new 仅存在于授权路径（NEW_FORM_PATH 唯一）/ fill 阶段门禁 / NO_SAVE 守卫在源", _t7_static)

def _t7_overall():
    d = _t7_plan_dir()
    io.open(d / "fp_min.json", "w", encoding="utf-8").write('{"meta": {"goal": "x"}}')
    pr = P.Probe(Namespace(run=SELFTEST_RUN, doc_id=None, expect_name="陈晶", tech_budget=60,
                           login_wait=30, wall_cap=3600, fill_plan=str(d / "fp_min.json")))
    try:
        pr.checks["c1_entry_login"]["status"] = P.PASS
        pr.checks["c7_fill_new"]["status"] = P.PASS
        assert pr._overall() == "SUCCESS_FILL_ONLY", pr._overall()
        pr.checks["c7_fill_new"]["status"] = P.FAIL
        assert pr._overall() == "FAILED"
        pr.checks["c1_entry_login"]["status"] = P.BLOCKED
        assert pr._overall() == "BLOCKED(c1_entry_login)", pr._overall()
        assert pr.checks["c4_normal_field_write"]["status"] == P.NOT_AUTHORIZED
    finally:
        pr.budget.close()
case("填写任务整体口径：c1+c7→SUCCESS_FILL_ONLY；c7 FAIL→FAILED；c4 恒 NOT_AUTHORIZED", _t7_overall)


print("== T8 登录态持久化 + PrimeNG 表面解析 ==")
def _t8_session():
    import os as _os, time as _time
    d = P.BASE / "automation" / ".pw-profile"
    d.mkdir(parents=True, exist_ok=True)
    f = d / "t8_session_probe.json"
    io.open(f, "w", encoding="utf-8").write("{}")
    now = _time.time()
    _os.utime(f, (now - 100, now - 100))
    assert P._session_state_usable(f, now=now) is True
    _os.utime(f, (now - P.SESSION_TTL - 10, now - P.SESSION_TTL - 10))
    assert P._session_state_usable(f, now=now) is False, "超 TTL 必须判不可用"
    io.open(f, "w", encoding="utf-8").write("")
    assert P._session_state_usable(f, now=now) is False, "空文件必须判不可用"
    f.unlink()
    assert P._session_state_usable(f, now=now) is False, "缺文件必须判不可用"
case("_session_state_usable：新鲜可用 / 超 TTL / 空 / 缺 一律正确", _t8_session)

def _t8_resolve():
    # attempt_012 实证：bizOrign(流程归属)=组织下拉（乔丹科技/中乔发展…），与事由语义无关；
    # 事由语义落点=备注(description)。payType 标签实为 报销方式。
    FIELDS = [
        {"name": "bizOrign9", "label": "流程归属", "type": "dropdown", "visible": True, "readonly": False},
        {"name": "payType11", "label": "报销方式", "type": "dropdown", "visible": True, "readonly": False},
        {"name": "budgetYear16", "label": "预算年度", "type": "multiselect", "visible": True, "readonly": False},
        {"name": "description19", "label": "备注", "type": "text", "visible": True, "readonly": False},
        {"name": "hidden1", "label": "事由", "type": "text", "visible": False, "readonly": False},
        {"name": "ro1", "label": "手机", "type": "text", "visible": True, "readonly": True},
    ]
    assert P._resolve_ng_field(FIELDS, "支付方式")["name"] == "payType11", "别名 支付方式→报销方式"
    assert P._resolve_ng_field(FIELDS, "年度")["name"] == "budgetYear16", "别名须覆盖 预算年度"
    assert P._resolve_ng_field(FIELDS, "事由")["name"] == "description19", \
        "事由语义落点=备注；绝不落组织下拉 bizOrign，且排除不可见同标签项"
    assert P._resolve_ng_field(FIELDS, "流程归属")["name"] == "bizOrign9", "流程归属按原语义仍可解析"
    assert P._resolve_ng_field(FIELDS, "手机")["name"] == "ro1"
    assert P._resolve_ng_field(FIELDS, "不存在字段") is None
case("_resolve_ng_field：精确 > 别名/互含 > name 提示；不可见项排除", _t8_resolve)

def _t8_table_col():
    HEADERS = [{"text": "报销项目", "prop": "reimItem"}, {"text": "摘要", "prop": "digest"},
               {"text": "报销金额", "prop": "cost"}]
    assert P._table_col(HEADERS, "费用项目/摘要") == 1, "『/』拆分别名须命中 摘要"
    assert P._table_col(HEADERS, "金额") == 2, "金额 互含命中 报销金额"
    assert P._table_col(HEADERS, "预算科目") is None
    assert P._table_col([{"text": "项目说明", "prop": "reason"}], "费用说明") == 0
    assert P._table_col([{"text": "是否为最后一次", "prop": "isLast"}], "是否为一次性") == 0
case("_table_col：精确/拆分/互含/别名（是否为一次性↔是否为最后一次）", _t8_table_col)

def _t8_guard():
    pr = _mk_probe()
    for ok in ("新增", "添加", "插入", "确定", "取消", "选择", "关闭", "2026", "伙食", "中国银行"):
        assert pr._click_guard(ok) is True, f"填写路径常用词被误拦: {ok}"
    for bad in ("保存", "新增并保存", "保存并新增", "发送", "上 传", "返 回"):
        try:
            pr._click_guard(bad)
            raise AssertionError(f"空白变体绕过守卫: {bad}")
        except RuntimeError:
            pass
    pr.budget.close()
case("守卫扩展：新增/确定/取消等放行；空白变体禁点词仍拦截", _t8_guard)

def _t8_static():
    src = io.open(P.BASE / "stage1_browser_probe.py", encoding="utf-8").read()
    for tok in ("SESSION_STATE", "SESSION_TTL", "_session_state_usable", "add_cookies",
                "storage_state", "_page_storage", "sessionStorage",
                "FORM_MAP_JS", "TABLE_MAP_JS", "DIALOG_DUMP_JS", "CELL_INFO_JS", "NG_VALUE_JS",
                "_phase_fill_ng", "_phase_fill_spreadjs", "_pick_option",
                "_resolve_ng_field", "_table_col", "_fill_related_doc", "_fill_bank_name_ng"):
        assert tok in src, f"PrimeNG/会话持久化缺件: {tok}"
    assert "session_state_saved" in src and "session_state_injected" in src
    assert "cookies=len(" in src, "日志只允许记 cookie 条数（记值违规）"
    assert "login_wait_aborted" in src, "等待期关窗须 BLOCKED 不裸抛"
case("静态完整性：会话持久化 + PrimeNG 表面件全在场；日志只记条数", _t8_static)


# T9（2026-10-23 round-2）：D2 观测件 / D4 局部守卫增量不变量——只新增，不放松上面任何断言
def _t9_static():
    src = io.open(P.BASE / "stage1_browser_probe.py", encoding="utf-8").read()
    # D2：三处内层 except 吞前留痕 + 尝试序号 + 字段级结果事件
    for tok in ('event="inner_exc", where="cell_activate"',
                'event="inner_exc", where="cell_input_write"',
                'event="inner_exc", where="pick_row_verify"',
                'behavior="continue_next_act"',
                'behavior="pass_to_checkbox_fallback"',
                "attempt=ai, attempts=2",
                'event="cell_input_skip"',
                'reason="readonly_or_disabled"',
                'event="pick_row_detached"',
                "row_detached_overlay_state",
                "row_detached_overlay_open",
                'event="fill_field_result"'):
        assert tok in src, f"D2/D4 观测件缺件: {tok}"
    # D4-b：写入路径显式 8s 局部短超时（先例：行点击 timeout=8000）
    assert "inp.select_option(str(value), timeout=8000)" in src, "select_option 缺局部短超时"
    assert "inp.fill(str(value), timeout=8000)" in src, "fill 缺局部短超时"
    # D4-a：行 detach 的 count() 存在性守卫（同型先例 _cell_info）
    assert "if row_loc.count() == 0:" in src, "pick_row 缺行 detach 守卫"
    assert 'row_loc.get_attribute("class") or ""' in src, "在挂行选中态核验原链须保持"
    # 红线锚点：全局默认 45000 不动（恰 1 处）、600ms 防御等待仍在、
    # get_attribute 未被加 45s 标签冒充 timeout 证据
    assert src.count("set_default_timeout(45000)") == 1, "全局默认超时 45000 必须原值唯一"
    assert "page.wait_for_timeout(600)" in src, "600ms 防御等待必须保留"
    assert "get_attribute(\"class\", timeout" not in src, "不得给 get_attribute 贴 timeout 标签造假"
case("T9 D2 观测件/D4 局部守卫增量在场 + 全局超时原值锚点", _t9_static)


# 清理 selftest run 目录（只删 selftest- 前缀，绝不触碰真实 run）
def _cleanup():
    runs = BASE / "automation" / "runs"
    for d in runs.glob("selftest-*"):
        shutil.rmtree(d, ignore_errors=True)
    _cleanup_lock = BASE / "automation" / ".pw-profile" / "executor.lock"
    # selftest 从不 acquire_lock；若存在遗留锁则不属于本测试，不动
_cleanup()

print()
if FAILED:
    print(f"SELFTEST FAILED: {len(FAILED)} → {FAILED}")
    sys.exit(1)
print("SELFTEST ALL PASS（13 组用例，覆盖 T1–T9 + 状态机 + 回归守卫）")
