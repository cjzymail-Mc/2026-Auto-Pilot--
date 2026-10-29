# B 侧 ENHANCED_FINAL 终审证据（round 1，2026-10-28）

两轮 fresh mc-expert 一次性审计报告原文存档（GLM 中风险强制增强终审＋P2 修复后按原规则聚焦 delta 重审）。评审为只读 subagent，报告为模型输出、按本仓库验收纪律与工件核对采信。

## 第一轮：ENHANCED_FINAL（四产物哈希绑定）

> VERDICT: GO
> HASH_VALIDITY: VALID
> UNVERIFIED_SCOPE: NONE（C12「真实填写/真实保存待验」系冻结合同 D12 明示的如实申报项，全文档一致标注，非未声明夸大）

REVIEW_PROFILE=ENHANCED_FINAL AUTHOR_RUNTIME=CLAUDE_GLM RISK_CLASS=MEDIUM/GLM_ALLOWED ADMISSION=ADMITTED
REQUIREMENTS=team-task.md 冻结块 ctr-74b7c8ee（src-8a759dc1，自带 sha256=8a759dc18dbd…b17ecd）＋计划 BPM-FASTLANE-20261028-V2 §6
REVIEWED_ARTIFACT（SHA256 审前=审后重算一致，前 12 位）：
- bpm/oneshot.py = 0e03f05b514d（550 行）
- tests/test_bpm_oneshot.py = d8a21f6839a0（819 行）
- feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md = f953c5a84a43
- automation/offline-verify/20261028-142902-draft-build/build_result.json = 290c66d8ce27

【审计1 哈希与证据一致性——通过】
- build_result.json：probe-selftest exit_code=0/4.478s；capability-tests exit_code=0/240.353s/test_count=491。
- probe-selftest.log 末行原文：「SELFTEST ALL PASS（覆盖 T1–T10 + 状态机 + 回归守卫）」。
- capability-tests.log 末尾原文：「Ran 491 tests in 239.698s」「OK (skipped=4)」（239.698 为 unittest 内层计时，240.353 为外层，一致；487 ok＋4 skipped=491）。
- 交叉绑定：该 PASS build 的 source_manifest.json 内 bpm/oneshot.py、bpm/save.py、bpm/browser_probe.py 的 SHA-256 与当前工作区文件字节一致——受测代码＝在审代码，无测后漂移。

【审计2 完成判据抽查——结论与代码相符】
- C01：build_parser 互斥组 --task/--fill-plan（oneshot.py:506-508）；_run_task_branch（:396）离线校验→TaskBranchProbe.pending_task_prepare 挂在身份确认后、填写链前（browser_probe.py:3195-3208）→同一 probe 内 fetch_template（template.py:254，显式 page 参数）→complete_from_live_snapshot→授权编译→generate_fill_plan→冻结→bind_final_plan（ui.py:211）；_run_plan_branch（:373）load_plan 原样执行、不重读模板、validate-only 不启动浏览器。TaskBranchChainDOMTests 为真 headless Chromium 夹具，断言含 G2.5 复用不重读模板（test:581-593）与 TEMPLATE_PRE_FROZEN 负例（:595-602）。
- C04：compile_authorization（:106-141）三分支属实——synthetic/blueprint.test_context 强制 fill_only（:121-125）；declared fill_only（:126-128）；save_draft 需 save_basis，standing_policy 引用非 BPM-SELFDRIVE-20261027-A1 即 UNKNOWN_STANDING_POLICY 阻断（:131-134，白名单常量 :47），user_request 为另一合法 basis。validate_task（fill_cli.py:87-94）上游强制 save_basis 结构（kind∈{user_request,standing_policy}＋非空 reference），basis 缺失在到达编译器前即被拦。build_authorization_record（:144-159）四绑定（task_id/plan_hash/config_sha256/operator）、不嵌入计划无自引用；verify_record_bindings（:162-176）漂移即 AUTHORIZATION_BINDING_CONFLICT 停止。
- C08：ui.py open_verification_page（:1031）二次开抛 UIBlocked VERIFICATION_PAGE_ALREADY_OPEN；close_verification_page（:1042）finally 关自有副页、失败仅留事件；_readback_page（:1056）副页存活期默认路由副页、显式 page 参数优先；save.py:247-255 finally 关副页；主 tab 不被核验导航（3 项 DOM 测试实证）。
- C09：browser_probe.py main() finally 时序＝atomic_result（:3234）→probe_end（:3235）→_deliver_and_park（:3242）→驻留→_close_browser→release_lock（:3244，驻留全程持锁）；result_delivered（:3147）先于 park（:3165），驻留前 wall_cap 扩容（:3164）。DeliveryAndParkTests 7 项含真子进程 PROFILE_LOCKED 拒绝、stale 接管、release 只删自身 pid 锁（test:770-815）。
- C12：如实标「待验」，三项真实输入缺口集中列出（结果记录 §真实输入缺口；build_result.json real_fill_verified=false、real_save_verified=false、missing_real_inputs 两项）。

【审计3 待验范围声明——无冒充】
SKILL.md:46/64/88、common-operations.md:65、full-chain.md:3/5/29、travel.md:5、express.md:46、rd-materials.md:47、STATE.md:3/8/19/33、docs/repository-layout.md:34、AGENTS.md:52 全部一致标「实现＋离线验证；真实填写/保存待验」；两次中间 OFFLINE_FAILED（511 项测试基建缺陷）工件如实保留（20261028-135040/135848），演进 511→484→491 与记录叙述吻合。

【审计4 红线抽查——通过】
- 凭证泄漏：新产物 grep pw-profile/local-session 仅命中 _protected 防护守卫（oneshot.py:89）与 C10 陈述句，无凭证值或目录内容。
- fill_only 默认：synthetic/test_context 强制 fill_only；save_draft 需结构化 save_basis；allow_submit 恒 False（oneshot.py:138）。
- journal 防重复保存：任务分支新开 run 在浏览器启动前阻断（oneshot.py:442-472，EXISTING_SAVE_INTENT exit 2，UNREADABLE_JOURNAL 同样阻断＝fail-closed）；SaveController（save.py:195-211）对 SAVE_INTENT/SAVE_UNCERTAIN/SUCCESS_DRAFT_SAVED 一律只读 reconcile，_reconcile（:135）注释明确 uncertainty 不回流点击。

【发现（按严重度，均非阻断）】
- P2-1 「已有 journal 在启动浏览器前阻断」表述范围过宽：该预检仅在任务分支新开 run 路径实现（oneshot.py:462-472）；--fill-plan 分支与 --resume-run 不做浏览器前 journal 预检（与 legacy fill_cli --resume-run 行为一致，无倒退），依赖 SaveController 在途只读核实兜底——不会二次点击保存，但会先启动浏览器并重填出一个新的未存草稿页。最小修复：将 common-operations.md §5 该 bullet、full-chain.md:29 及结果记录 C05 措辞限定为「任务分支新开 run」，或给其余两分支补同款预检。
- P2-2 result_delivered 携带的 1/1/1/1/0 生命周期计数为写死常量（browser_probe.py:3152-3153）而非逐 run 实测；正常路径按构造成立（单 _launch/单 acquire_lock）、fresh_scan 为动态位，结果记录已注明真实路径计数随 C12 待验。最小修复：从实际 launch/lock 事件派生计数，或在事件字段注明 declared 性质。

VERIFIED_COMMANDS：python -X utf8 hashlib SHA-256（审前/审后各一轮，四产物一致）；tail/grep capability-tests.log、probe-selftest.log；grep 凭证泄漏抽查；python -X utf8 解析 4 份 build_result.json＋source_manifest.json 哈希交叉比对。承重八面（对象绑定/生命周期/时序权限/幂等重试/执行者矩阵/类型组合/接口发现/证据真实性）均 PASS，唯上述两处 P2 文档与度量精度建议留待下次触碰时收口。

---

## 第二轮：P2 修复聚焦 delta 重审（改动受审产物后按原终审规则复核）

> VERDICT: GO
> HASH_VALIDITY: VALID
> DELTA_CLEAN: YES

【代码核实（一手）】bpm/oneshot.py：:443 取 journal_state；:444-460 `if args.resume_run:` 子路径仅做绑定性校验（:446-453 task_binding 核心字段比对）＋冻结复用，无 journal 门；:461 起 `else:`（新开 run）:462-472 命中四状态（SAVE_INTENT/SAVE_UNCERTAIN/SUCCESS_DRAFT_SAVED/UNREADABLE_JOURNAL）→ 输出 `EXISTING_SAVE_INTENT`（browser_launched:false）并 return 2。_run_plan_branch（:373-393）全程无 journal 预检。施工结果.md:66 的代码指针 oneshot.py:462-472 与实际门块一致；oneshot.py:110/:442 注释说「由调用方在启动浏览器前完成」，指任务分支调用点，非全分支声明。

【哈希（review 前后两次计算一致，无漂移）】bpm/oneshot.py = 0e03f05b514d（=原审）；tests/test_bpm_oneshot.py = d8a21f6839a0（=原审）；automation/offline-verify/20261028-142902-draft-build/build_result.json = 290c66d8ce27（=原审）→ 代码/测试/构建产物零字节改动。feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md = 7c48b2a9a3fb（新哈希，本轮唯一变动的受审产物）。

【改动范围（mtime 一手）】本轮仅动所称 6 文件，时间聚集 2026-10-28T15:13:53—15:14:38：AGENTS.md(15:13:53)、SKILL.md(15:14:01)、full-chain.md(15:14:04)、施工结果.md(15:14:30)、common-operations.md 与 STATE.md(15:14:38)；team-progress.md(14:54:30)、team-task.md(12:10:24)、travel/express/rd-materials、docs/repository-layout.md 均停在施工期时间戳，无未申报改动。

【措辞核对（grep「浏览器前」「journal」全库命中逐一核过）】SKILL.md:55、common-operations.md:76、full-chain.md:29、AGENTS.md:52（"其新开 run"承任务分支主语）、施工结果.md:12/25/66 均精确限定「任务分支新开 run」＋「--fill-plan 与 --resume-run 沿用 SaveController 在途只读核实」；无任何文件仍声称所有分支浏览器前阻断。

【P2-2 标注】施工结果.md:23（C03）与 common-operations.md:91 均已标「按构造声明值、fresh_scan 为动态位、逐 run 实测随真实首验/C12 落地」；bpm/browser_probe.py:3152-3153 证实 1/1/1/1/0 为 `_deliver_and_park` 内硬编码构造值——标注与事实相符。

【收口节】施工结果.md:62-67「终审发现与后续收口项」与实际改动相符：所列 5 文件措辞均核实精确限定；未把 STATE.md 计入「已限定为新开 run」清单——与实际相符；C12 待验如实保留、未被收口节扩大成已验证。

【非阻断残留（本轮未引入新不一致，下次触碰相应文件时可选收紧）】
- STATE.md:19「journal 保存意图任务分支浏览器前阻断」限定到「任务分支」但缺「新开 run」三字（任务分支 resume 子路径无此预检）；STATE 系快照索引，精确表述在其链接的施工结果.md:12，按 AGENTS.md 文档分工可接受。
- team-progress.md:43 CP1—CP3 历史施工日志「journal 进浏览器前阻断 exit 2」未带分支限定——原审基线内既有记录（mtime 14:54:30 早于本轮修复 15:13+），历史进度日志非规范文档，不属本轮改动引入。

结论：三受绑产物哈希与原审完全一致，本轮确为纯文档 delta；P2-1/P2-2 的修复在规范文档层准确落地，收口节描述如实，无新增不一致。原 GO 在新文档哈希（施工结果.md=7c48b2a9a3fb）下继续成立。
