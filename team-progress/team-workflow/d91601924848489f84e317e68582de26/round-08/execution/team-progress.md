> run_id: 20261026-192005-82e4775e
> source_block_id: src-82e4775e
> contract_id: ctr-3057b56a
> effective_contract_id: ctr-3057b56a
> run_status: COMPLETE
> 漏斗: P6✓

workflow_run: d91601924848489f84e317e68582de26
workflow_round: 8
entry: team-workflow-run
runtime_evidence: helper runtime_evidence.B = CLAUDE_GLM / model glm-5.3 / transcript c05e555a-0c54-4418-96a2-d92a751dfbc9.jsonl（round 8 enter/permit seq39 B_RUNNING 一致）
authorization: B = /team-workflow run（用户显式启动 round 1 起；round 8 由 A publish 派发）
risk_note: 受控委托场景，P0.5/P5 显式入口依据 = B 的 run 启动授权 + 一手 CLAUDE_GLM 证据 → 常设 MEDIUM + B+AUTO
累积失败字典（承接 workflow state，不得清零/改名/隐去）: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
baseline_note: A 已绑定（baseline=冻结V3 sha256 d437988d…，criteria ad4b2f31…，max_round=16，session 0cbc12a4…）；round-7 验收 20 项 PASS_DYNAMIC 后派 round-8 收尾轮；本轮需求输入=team-task.md src-82e4775e；规则原文=冻结V3 §6/§9/§10.3 B6/B7/§10.5/§12.3/§13

## P4/P5 路由与登记（2026-10-26 19:2x）
```text
routing_mode=AUTO
recommended_topology=T3
realized_topology=T3
assurance_profile=ENHANCED
drive_mode=B
author_runtime=CLAUDE_GLM
risk_class=MEDIUM
risk_owner=USER
runtime_policy=GLM_ALLOWED
risk_escalation=NONE
```
- coordination_score=2（C1=1：B6 只读复核、CASE-08 新 session、B7/manifest/报告均串行接力，浏览器仅只读探查且错峰；C4=1：B6/CASE-08/manifest 同根依赖 round1–7 交付物）。≤2→T3。
- assurance ENHANCED 触发：runtime=GLM；B6 全链独立重算与 CASE-08 零上下文重走的机器可验性 + fresh ENHANCED_FINAL 终审。硬覆盖不命中。

## 自主裁决(B)
1. **429 配额中断处置**：CASE-08 子代理 19:55:21 撞 GLM 账号级 5h 用量上限（重置 21:27:45）→ 后台 python 定时到 21:29 后 SendMessage 恢复**同一 agent 上下文**继续（保零上下文继承边界与已核实进展），不重开新 agent、不由 B 主会话代做其工作。依据：冻结合同 §10.5 验收有效性要求独立 session，换新 agent 会破坏"同一验收员全程"的连续性。
2. **CASE-08 阶段二落盘纪律**：agent 一次口头报"完成"但盘上无比对文件 → 拒绝采信，发状态质询要求其真实落盘 comparison-report/comparison.json 后再进入 B 侧汇总（结果以工件为准，不以回传文本为准）。
3. **合同 cid 计算口径修正**：首次冻结按"整块含 marker 行"计算 sha256 与 validator 不符 → 改按 marker 之间 BODY（CRLF→LF 归一、去首尾空行）重算得 ctr-3057b56a 并同步 team-progress 头部；79 cases PASS 后才视为冻结。
4. **P2 文档修订策略**（mc-expert 终审后）：自己本轮签发的 CASE-08-report.md §四直接改为如实口径；子代理产物 input-log.md 只做**末尾加法订正**不改既有行；两文件新哈希按终审指示同步重登台账。
5. **manifest 生成时序**：final-manifest.json 哈希绑定 handoff-input.json，故按"handoff 定稿→构建→回读确认入 events"顺序执行（构建器引用已经 mc-expert 预审 24 项全存在），不提前用陈旧 handoff 哈希构建。

## 失败陪审（failure_key / failure_count / mxp候选排序 / 本次选项 / 尝试结果）
（无新增失败 key；D23/D22 计 1 保留历史，两项已闭环。本轮 429 属外部配额非任务失败，处置见自主裁决1，不进字典）

## OPEN_BLOCKERS
（无）

## PENDING_HUMAN_NONBLOCKING
- R2-P3 git commit、R2-P4 legacy token 清理（用户侧遗留，含 rounds 3–10 旧 diff 与 V3 全量工件）；模板身份缺口已于 V3-R06 按用户输入解除 CLOSED。
- `.gitignore` 增补评估（automation/runs/ 含页面 DOM 原值，当前以"默认不 commit"约束）。

## 进度日志
- 2026-10-26 19:2x B 窗口 WAKE（A publish round 8，seq 35→38）→ status B_READY → enter/permit 接棒 round 8（seq39）。
- 2026-10-26 19:2x P0 重建 team-progress（publish 清空后）；P0.5 沿常设 MEDIUM + B+AUTO；P2 冻结最小合同 **ctr-3057b56a**（validator 79 cases PASS）。
- 2026-10-26 19:2x–19:3x skill 收口预补：travel.md 增「受限随机测试占位关联（oa_test_relations）正式生成路径」一节（纯文档；round-7 已入 bpm_plan/schema，文档此前缺）；CASE-08 输入白名单清单先于 agent 启动落盘（case08-input-manifest.md）；19:29:16 只读 login60 探查（SUCCESS_LOGIN_ONLY，写入检查全 NOT_AUTHORIZED，冻结合同允许入口）。
- 2026-10-26 19:44 B6 独立复核（全新 mc-expert 实例）回传：**VERDICT=CONSISTENT，七面零差异**（事实链/Excel/逐票对照/模板边界/v1.0 闭合/v1.1 差异与种子/B5 回读与占位分离；种子链与 canonical plan_hash 均独立复算吻合）；报告原样落盘 B6-report.md（sha256 12fb3a90…）；8 条观察均非差异——④种子字符串传参已当即补 travel.md 注记闭环，①travel.md 工作树哈希漂移=本轮收口文档改动所致（执行源 manifest 保留执行时哈希，正确行为）。
- 2026-10-26 19:26–21:4x CASE-08 新 session（general-purpose，零上下文继承）阶段一+阶段二完成（白名单输入；429 中断与恢复见自主裁决1）：**核心结论双独立会话收敛一致**——其自有 v1.0（e600f67a…，canonical ec2c811b…）validate-only PLAN_VALIDATED；四面对比（vs 交付 v1.0/B5 回读/CASE-03/模板快照）核心全 CONSISTENT，27 票号集合逐张全等，3 项非金额差异如实；3 次视觉读票幻觉均被"机读+汇总单互证"纠出（0904 定案 16104706）→ 已固化进 skill 文档。
- 2026-10-26 22:2x–22:3x 收口：73 原件第 8 轮零漂移 73/73；SKILL.md+plan-contract.md×3 文档补丁落地（机读优先/双通道裁决/applicant sources/corpCode 显示名互引）；CASE-08-report.md、B7 终局标记（台账 rounds=18）、用户报告.md 更新完成；mc-expert ENHANCED_FINAL **VERDICT=GO 8/8 PASS**（P1 无；P2 文档措辞已修+新哈希重登；P3 五条处置落 MC-FINAL-report.md）；final-manifest.json 于 handoff 定稿后构建并回读确认。

## P1已核事实（2026-10-26 19:2x–22:3x，一手盘上核验）
- B6 独立复核：**VERDICT=CONSISTENT，七面零差异**（报告 sha256 12fb3a90… 落 run 目录）；种子链/canonical plan_hash/占位零泄露均由复核员独立重算吻合；8 条观察非差异（④已闭环进 travel.md，①系本轮收口文档改动的预期哈希漂移）。
- CASE-08 新 session 验收：**PASS_DYNAMIC**——阶段一独立重建至 PLAN_VALIDATED（其独立 --task run 20261026-193100-0527f5dc；validate-output plan_sha256 经 mc-expert 独立复算与 canonical 哈希逐位相等）；阶段二核心全一致；白名单纪律经 input-log 审计+mc-expert 复核（P2 措辞偏差已修：#10 registry 查询/#16 工具源如实登记为环境读取，污染目的经双重核实未破坏——registry 表单仅任务身份元数据，B 与 mc-expert 分别实查）；报告 sha256 b24af05e…（勘误后）。
- B7 终局标记：台账 progress.json rounds=18，V3-R08 含 b7_terminal_marker=B7_TERMINAL_V3_CASE_COMPLETE（fill_only 完成/层次=真实控件已验证·填写+回读·未保存/registry 仅 FORM_INTENT/零保存零旧单修改零公出单重占声明）；V3-R07 及以前条目原样（mc-expert 面检 PASS）。
- skill 收口：SKILL.md+references/plan-contract.md+travel.md 共 5 处文档补丁；**零源码/schema/测试改动**（mc-expert 全仓 mtime+diff 扫描确认：本轮新增改动仅 3 个 skill 文档+台账/报告/交接；代码 diff 属 rounds 3–10 既有未提交遗留）→ 按合同条款 5 不新增 unittest/offline-verify（最新构建仍 materials-v3r07-20261026-1900 OFFLINE_PASS selftest+316）。
- 73 原件第 8 轮零漂移：73/73（vs 20261026-100322-v3r00-inventory case-file-manifest）。
- mc-expert ENHANCED_FINAL：**VERDICT=GO，8/8 审计面 PASS**（B6 完整性/零上下文纪律/比对一致性/纯文档收口/台账加法性/报告不越权/零写入零泄露/manifest 构建器预审 24 项引用全存在）；UNVERIFIED_SCOPE 两项（manifest 生成后 A 抽验、B6 复算本体不重复执行）均如实申报非承重。

## done_when 签发（team-task src-82e4775e，四态）
1. **B6 独立复核（全新 agent 七面全链重算）**：PASS_DYNAMIC——B6-report.md 12fb3a90… CONSISTENT 零差异；复核员独立复算种子链/canonical plan_hash 吻合。
2. **CASE-08 新 session 使用验收（白名单输入）**：PASS_DYNAMIC——阶段一 PLAN_VALIDATED+阶段二核心收敛一致；CASE-08-report.md b24af05e…（P2 勘误后）；mc-expert 面 2/3 复核 PASS。
3. **B7 终局标记+台账 V3-R08**：PASS_DYNAMIC——rounds=18 含完整 b7_terminal_marker；mc-expert 面检加法性 PASS。
4. **§12.3 最终 manifest+用户报告+skill 收口**：PASS_DYNAMIC——用户报告.md 47646621…（不越权，mc-expert 面 6 PASS）；skill 5 处纯文档补丁（面 4 PASS）；final-manifest.json 由预审过的构建器于 handoff 定稿后生成并回读确认（P6 前完成，见 events）。
5. **证据/台账/P6 收尾**：PASS_DYNAMIC——events.jsonl 全程追加（b6/case08 两阶段/429/skill_patches/b7/mc_final/manifest）；台账 V3-R08+errata；mc-expert GO；handoff 按本轮真实哈希重写后 finish。

## 复盘
**观察闭环**（round-7 P3 六条已在 round-7 progress 复盘归档，archive 可查，不重复）：
- B6 8 条（均非差异）：①执行源 manifest 工作树漂移=预期正确行为（保留执行时哈希）→维持；②relations.description DOM readonly=false 建议保存类验收时加写入轨迹断言→登记后续观察；③I24 浮点尾差→用户报告已含"独立 Decimal 复算"口径，后续报告附引擎尾差一句的建议采纳；④种子字符串传参→已补 travel.md 闭环；⑤applicant_employee_verified=false→身份分层如实记录，风险极低，维持；⑥12025105858 reimed=2→fill_only 无占用后果，如实呈现维持；⑦截图未像素级复核→DOM/JSON 承重，非缺口；⑧UNVERIFIED_SCOPE→复核边界如实申报，维持。
- CASE-08 5 条（skill-operability-assessment）：#1 机读优先→**文档已补**（SKILL.md+plan-contract.md）；#2 digest agent_reviewed 放行建议→登记后续观察（行为变更不动）；#3 corpCode 渲染约束→**文档已补**（plan-contract.md header 行+travel.md 互引）；#4 identity/applicant sources→**文档已补**（plan-contract.md applicant 行）；#5 oa_test_relations 只读不可达→合同设计如此，非缺口；#6 parsed PDF 占位/双根目录须不存在→登记后续观察。
- mc-expert P3 5 条：①input-manifest"19:3x"笔误（实际 19:26:23，顺序正确）→登记不改历史件；②final-manifest 前向引用→生成后回读确认（events）；③login60 未披露→台账一句话补记完成；④旧 diff 未 commit→用户侧遗留维持登记；⑤构建器死分支→无功能影响，未来顺手清理。
- **过程教训**：电子发票 PDF 文本层机读为主通道的实证（3 次视觉幻觉全被机读+汇总单互证纠出）已固化进 skill；零上下文验收的"白名单字面 vs 环境读取"边界要在启动前清单里写得更细（本轮 P2 教训：registry/工具源类读取应预先分类授权，而非事后勘误）。
- **失败字典**：无新增 key；D23/D22 历史计数原样承接，不改名不清零。

## P6 收尾
- mc-update/pin/session-new 内部记忆动作完成；无 teammate 存活（B6/CASE-08/mc-expert 均已回传落盘）。
- handoff-input.json 按本轮真实产物哈希重写（evidence 全部为具体文件），finish 绑定 workflow run d91601924848489f84e317e68582de26。
- final-manifest.json 构建并回读确认后，本轮 P6✓。
