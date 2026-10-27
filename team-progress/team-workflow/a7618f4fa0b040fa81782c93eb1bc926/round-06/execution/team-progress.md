# 团队进度 — W06 前置（round 6）

> run_id: 20261024-140229-b401214d
> source_block_id: src-b401214d
> contract_id: ctr-ed80c9d0
> effective_contract_id: ctr-ed80c9d0

- workflow_run: a7618f4fa0b040fa81782c93eb1bc926 / workflow_round: 6 / entry: team-workflow-run（B 窗口）
- task_source_sha256: b401214dffa10e3c04e78977335b8b8816a246d01c975f2a8d19961bae7eff71
- runtime_evidence: GLM（本 B 会话原始 JSONL，helper enter/permit 已核）
- 累积失败字典（A 侧加载，逐字回传）: {"review|content|source_manifest_coverage|D23": 1}

## P0 · run bootstrap

- [x] enter 接棒成功（B_RUNNING, round 6）；permit 核对 team_run=20261024-140229-b401214d、source=src-b401214d、failures D23=1。
- [x] 任务输入=team-task.md round-6 source block（四条待做：D10 执行串联 / skill 链路增补 / live 模板读取尝试（可回退）/ R5-P2 顺带）；repo 硬规则=AGENTS.md 全量；生产 skill=../team-task/SKILL.md 全文（P0-P6 细则自 funnel-gate 读取）。
- [x] 不寻找/不读取 A 的独立基线或 criteria 清单；本轮验收依据=当前 task source+生效合同。

## P0.5 · 硬规则与风险登记

- 红线继承 AGENTS.md 全量 + 任务"保留项与边界"：只填不存；`.pw-profile`/`.local-session` 不入 git/日志/材料清单/测试工件；`task-registry`/`legacy-ia2`/旧 run 只读；除第 3 条只读 live 外零网络零浏览器；不自动 commit；单 profile 单执行者（live 走 CLI 自带锁）。
- 风险 envelope: author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。
- 失败陪审前置：累计 failure_count=1（review|content|source_manifest_coverage|D23，计数调整权在 A）；本轮无新增失败面。

## P1 · 盘点与可执行性核实

- [x] `fill_once.py --fill-plan <计划> --expect-name <身份> --validate-only` 行为核实（:236-254）：load_plan 全量校验后打印 `{"status":"PLAN_VALIDATED","plan_sha256":...,"browser_launched":false}` exit 0；任何 PlanError/ValueError → NEEDS_INPUT+issues exit 2；validate-only 分支在浏览器子进程派发（:268）之前返回，绝不启动浏览器。`--expect-name` 为 plan 校验必填。
- [x] `bpm_template.py --live` 行为核实（:312-401）：互斥 --census/--live；--template-number/--output 必填；输出必须为 `automation/runs/<简单run-id>/<新文件>.json`；live 自带同 profile executor 锁+专用只读 context（ReadOnlyProbe 不导航不关他人未保存页）；`--login-wait 0` 使登录失效时不等待扫码（wait_login 立即返回 → NEEDS_INPUT exit 2）；成功写快照+`template_read_end` events。
- [x] 会话身份前置事实（.local-session 只读，不入工件原值）：principal 陈晶/116070053，auth_status=authenticated，identity_source=live_authenticated_account_header_and_token_subject，effective_reuse_until=2026-11-23T02:42:23Z（JWT refresh token 到期，早于本地 60 天上限）→ 今日 TTL 元数据有效，live 尝试具备前置条件。
- [x] skill 目录结构盘点：`.claude/skills/bpm-fill-run/` = SKILL.md（frontmatter name/description+日常入口/执行与恢复/授权与保存/环境与交付）+ references/{travel,express,rd-materials,plan-contract}.md；repo 无现成 skill 校验器 → 按合同交付 `tests/test_skill_docs.py` 结构化校验。
- [x] 可执行性判定：四条待做全部可离线推进（第 3 条 live 单次尝试、两种结果均算完成）；无阻断 FACT、无 PREFERENCE 缺口需问卷。

## P2 · 改写与合同冻结

- [x] chop-task contract-only（caller=team-task mode=contract-only run_id=20261024-140229-b401214d source_block_id=src-b401214d input_policy=initial）：无阻断 FACT 缺口（八类真实原件未提供属任务书已声明的待验外部输入，非本轮合同缺口），不产问卷；合同按 minimal profile 起草。
- [x] 合同正文规范化 SHA-256 前 8 位 = ctr-ed80c9d0；追加至 team-task.md（append-only，原 source block 未动）；写前查重：本 run+source 原无 frozen 块。

## P3 · 冻结与登记

- [x] 首次冻结：progress contract_id=effective_contract_id=ctr-ed80c9d0；合同链校验见下方验证记录。

## P4 · 生产（B+AUTO，单执行体）

- [x] ①D10 执行串联：`bpm_request.py` 新增 `OPERATOR_SOURCES`/`validate_operator_evidence`/`operator_from_session_record`/`execution_ready`（真实 `fill_once --validate-only` 子进程编排，exit 0+PLAN_VALIDATED 才全绿；缺身份→NEEDS_INPUT+GAP_FIELDS 不猜姓名；来源越界 ValueError；`fill_once.py` 零 diff）。测试 6 项：就绪两态+模板来源拒绝+坏计划透传 issues+缺计划文件+session record helper 三态。
- [x] ②skill 增补：SKILL.md description 路由关键词+「完整链路」节+`references/full-chain.md`；授权与保存/执行恢复/环境交付红线段逐字不动。`tests/test_skill_docs.py` 9/9（frontmatter/引用落 skill 内且存在/命令旗标对照源码 add_argument/六阶段+函数对照 def/红线句逐字 pin）。系统 skill 注册表已实时加载新 description（路由可用性佐证）。
- [x] ③live 模板读取首试成功：`automation/runs/20261024-150200-tpllive/`——TTL 前置事件（authenticated，reuse_until 2026-11-23T02:42:23Z）→ `--live --login-wait 0` 入口即 LOGGED_IN → SUCCESS_TEMPLATE_READ_ONLY（15426095951 live afa5534c…）→ 与缓存快照（20261023-142146 census ffc75d19…）核对 uuid/类别/header 键集/表名/行数/表头身份**全部一致**（live_vs_cached_compare.json + CONSISTENT 事件）。events 全程只读链：precheck→lock→inject→read→compare；零新建零填写零触碰未保存页。
- [x] ④R5-P2：bizDate/payeeName 模板冒充反例实例化+重复 (group,field) 构造期拒绝（均入库测试）+`_load_doc` 取舍注释。
- [x] ⑤验证：`test_bpm_request` 28/28；全量 236/236 全绿（218 基线零回归+skill docs 9）；唯一 run `template-materials-20261024-w06-final` OFFLINE_PASS（probe-selftest 0+capability 227）。台账 W06=进行中（前置轮交付+主体验收待外部材料）、round-6 条目、notes.md round-6 节、next_actionable 更新。
- 冻结哈希（sha256）：bpm_request.py 9b72299e…/test_bpm_request.py b0916385…/test_skill_docs.py b6dc4763…/SKILL.md 4670f110…/full-chain.md babb88cf…/progress.json 7459f61f…/notes.md aec79949…/build_result.json 9191bd23…/source_manifest.json 2ca42a8e…/live 快照 afa5534c…/cached 快照 ffc75d19…/compare 2a47e12a…。冻结权威零改动：fill_once.py 6f67e20a…、stage1_browser_probe.py c538df89…、bpm_facts.py 8124a07e…、bpm_plan.py ee3f1ee1…、bpm_template.py d7b0ad55…（与 round-4/5 冻结值逐字节一致）。
- 已知口径说明：verify_bpm_build 清单为 bpm glob 口径，`tests/test_skill_docs.py` 与 `references/full-chain.md` 不在其 source_manifest 内（verify_bpm_build.py 不在本轮允许写面，不改）；两者哈希经 handoff+台账绑定，A 可独立复算。

## P5 · 独立复核（登记门）

- [x] mc-update / pin / session-new 三段预判：本轮交付经验（live 首试成功路径/--login-wait 0 纪律/validate-only 串联/verify_bpm_build bpm-glob 口径）均已落 repo 台账 notes.md round-6 节，属 repo 已记录事实不另入长期记忆；pin 无新增；session-new 仅固化文件不重开窗口（见收尾）。
- [x] fresh ENHANCED_FINAL（mc-expert, review-contract-v2）**VERDICT=GO**：ADMITTED（CLAUDE_GLM×MEDIUM→必须 ENHANCED_FINAL，本次即是）；HASH_VALIDITY=VALID（17 件产物+5 件冻结权威双轮复算零漂移，冻结权威对 round-5 基线逐字节一致——审计注明对 git HEAD 有 diff 属 round1-5 未提交累积的预期，判据为 manifest 哈希）；八面全 PASS_DYNAMIC（object_binding/lifecycle_identity/timing_permissions/idempotency_retry/executor_matrix/type_cross_product/interface_discovery/fixture_truth）；UNVERIFIED_SCOPE=NONE（六条 done_when 逐条独立复验；B1-B7 未被声称完成无冒充）；独立复跑：全量 236 OK、定向 28/9 OK、自建 run `template-materials-20261024-r6audit` OFFLINE_PASS、四项动态阳性对照（非法来源 ValueError/expired→None/authenticated→零凭证泄漏/合法就绪）全 PASS；红线核查通过（凭证零泄漏、task-registry/legacy-ia2/旧 run 今日零触碰、HEAD 仍 9299545、除 tpllive 一次只读 live 外零浏览器、授权红线段双重锚定=测试逐字 pin+frozen_source 快照内容一致）。
- 审计 FINDINGS 三条 P2（记录级，无承重 FAIL）：①SKILL.md round-5 基线无盘上字节副本（round1-6 未提交演化，manifest 只存哈希），"diff 定位增补仅在新区"不能独立反向复算——建议下轮起 skill 文件轮末快照随 run 落盘或落实 R2-P3 git commit（A/用户侧决策）；②live 时点 `.local-session` 被**冻结的** stage1_browser_probe.py:3089 会话维护性写入（AGENTS.md 强制的探查后原子更新，非本轮编排代码；last_scan_at 未重置、期限仍取服务端更早值）——合同"只读（不写回）"对"冻结 CLI 自带会话维护"存在字面歧义，建议后续合同显式豁免说明；③handoff 时序提示（本轮收尾即更新）。

## P6 · 收尾

- [x] 三段预判完成（见 P5 首条）；无跨窗口消息依赖（handoff 走 finish 提交）。
- [x] handoff-input.json 更新为 round-6：outcome=complete、artifacts+sha256、evidence、failure_counts 逐字回传 `{"review|content|source_manifest_coverage|D23": 1}`（D23 计数调整权在 A）；summary 含审计 P2 三条与下一轮入口。
- [x] 台账（progress.json/notes.md）round-6 落账；唯一验收 run=w06-final OFFLINE_PASS（审计自建 r6audit 不计）。
- [x] 团队关闭：本轮 B+AUTO 单执行体，无 teammate 需 shutdown；后台审计 agent 已交付终止。
- [x] 原子收口：run_status=COMPLETE + P6✓（本行与上一行同批写入，见文件末状态行）。

## 收尾复盘

- 交付对合同的六条 done_when 全数达成且经独立终签 GO；live 模板读取一次成功（超合同"两种结果均算完成"的下限：实际是成功+全一致留证）。
- 裁决记录：verify_bpm_build.py 不在本轮允许写面 → 新增 test_skill_docs.py/full-chain.md 不进 bpm-glob source_manifest，以 handoff+台账哈希绑定替代（A 可独立复算）；live 前置 TTL 事件只记 auth_status/姓名/期限/来源，无凭证引用。
- 遗留给 A/下轮：审计 P2-1（skill 文件轮末快照或 R2-P3 commit）、P2-2（冻结 CLI 会话维护写入的合同豁免措辞）；八类真实原件仍缺（W06 主体验收前置）；W07 两类研究可先行。
- 无未决人工门、无熔断、无 HALTED。

> run_status: COMPLETE
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
