<!-- team-task-source id="src-7d069bdb" sha256="7d069bdb40cea09e76baab5658c9bf92ebca76a94d07bd8ba272dabe442eb13f" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 8
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 8 -->
# 本次任务：express + rd_materials 真实闭环（复制 travel 模式）+ P1-a 合同追认增补 + 五类研究续推 + 反例固化

背景（自足）：Round-7 已完成 travel 真实闭环（run 20261024-155625-travelloop：agent 自驱库函数链无预制 facts_payload/blueprint、真实 Chromium 4 次尝试含诚实失败-恢复、v4 SUCCESS_FILL_ONLY、独立回读零差异、633.84 四向闭合、页面盘点交接）；视觉复核机制已证（全页渲染+agent 视觉，真实发票原件缺口 REAL_TRAVEL_INVOICE_ORIGINALS_ABSENT 如实登记）；五类研究 2/5 落盘（02 低值办公、04 福利劳保）。A 验收 19 PASS / 1 BLOCKED / 7 FAIL，D1/D10 已翻 PASS_DYNAMIC。

## 待做条款

### 0. 合同追认增补（P1-a，先做，一次性）
- 在本轮 team-task.md 合同区**正式追认 round-7 两处合同外写入**：`bpm_plan_generate.py`（identity 绑定 + system_observation→必须绑定已登记观察工件否则拒绝，收紧来源证明）与 `bpm_ui.py`（`supersede_dead_form_intent` + 零写/写后未存两迁移，append-only、拒 SAVE_*、存活页拒接）。A 已核实（round-07/acceptance/A-verification.md §6）：守卫零改动、判据未放宽、测试覆盖、全留痕。
- 增补后两文件进入**常设允许写清单**（纪律：最小改动+对应测试+events 留痕）；**其他任何新文件**仍须先停-增补-再写，不得沿用本次追认外推。
- 增补记录进 events/台账，附 A 验收文件指针。

### 1. express 真实闭环（主靶 A）
- 复制 travel 闭环模式：从既有授权历史回放材料（types-express 系列 / attempt 历史原件，只读复制进新 run 派生区）出发，agent 自驱库函数链 register_request → resolve_template（缓存定向）→ 提取复核（locator+input_hashes）→ FactSet → reconcile → 复用矩阵 → blueprint → generate_fill_plan → validate_plan 零 issues → execution_ready（validate-only 子进程）。**禁止预制 facts_payload/blueprint 塞入口**。
- 真实 Chromium 正式入口执行（fill_only，不保存不提交）：运单/结算/发票与 Excel 统计对应主费用行，费用说明有/无分支按材料实情选择；全部行写入、选择器唯一命中。
- 完整独立 DOM 回读零差异 + 页面盘点交接（模式同 page_inventory_r7.json）。registry 纪律沿用（FORM_INTENT/supersede 路径已具备；遇死意图按证据门接替，SAVE_* 一律拒）。
- 失败-恢复诚实留痕（如 round-7 v1-v4 模式）；登录类外部阻断则登记缺口转做其余条款，不算失败轮。

### 2. rd_materials 真实闭环（主靶 B）
- 同模式：授权历史回放材料（types-rd 系列）→ agent 自驱链 → 真实填写 fill_only → 独立回读零差异 → 盘点交接。
- 范围限定（既有边界）：products 物品档案按现有档案完整编号选入并核对 name/purchaser/price/description，不新造档案；发票按 products.price 分配合计闭合；费用说明为空。超出范围的复杂分支如实登记不做。
- rd 如遇真实外部阻断（材料/页面能力缺口），诚实登记并说明缺口与所需输入，其余条款照常。

### 3. 五类研究续推（用户指令③延续）
- 其余三类（其他费用、维修费、各项会议支出）从 census 缓存候选单号做定向只读研究，**至少新增 2 类**六节研究工件（结构/字段/差异/规则草案/能力清单/类型码证据）；CLI 单发 ≤5 次、--login-wait 0、observed_get 只读、零注册零启用零写页面。
- 已研究两类（02/04）的"接入共享能力清单"推进为**代码适配准备工件**（差异落点映射到现有模块的改造点清单，不实施注册/启用）。

### 4. 反例固化（D18 推进）
- 把 round-7 四个真实反例中可离线固化者写成测试（不削弱现有防御）：①`COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED` 身份缺工号阻断；②registry FORM_INTENT 门+死意图接替证据门（零写档/写后未存档，SAVE_* 拒接）；③`EXACT_PICK_MISSING` 瞬时失败不产生部分验收；④写后页失 rebuild 的 lost_page_rows 记录。至少固化 2 个。

### 5. P2 小项（顺手）
- execution_ready 的 plan.sha256 字段名歧义（改 plan_hash 或双字段并留兼容）。
- supersede 活页检查 docstring 收窄为当前 context 语义。
- travelloop 式 events 字段格式与 fill run 统一（新增链统一 schema，不回改历史）。
- R6-P2-2 skill 措辞建议在维护窗口采纳（红线段逐字不动）。
- 未保存关页服务端无残留：以只读服务端观察补证一次（不写页面）。

## 保留项与边界
- fill_only；不测保存、不验收保存成功；SaveController/守卫/registry/legacy 原样；test_context 不升级。
- 原始材料只读（历史 run 工件零改动，复制进新 run 派生区）；不虚构业务事实；不新建真实报销。
- 单 profile 单执行者；探针如需改动先 selftest 全绿；不自动 commit；真实发票视觉复核缺口继续登记（用户供料后执行），不阻塞本轮。

## 验证
- 闭环实跑证据：每类 events 全链（agent 自驱中间工件）、attempt 纪录、独立回读零差异、终局截图、页面盘点。
- 全量 `python -X utf8 -m unittest discover -s tests` 全绿；`verify_bpm_build.py --run template-materials-<时间戳>` 唯一 run PASS。
- 研究工件 ≥2 类新增 + 代码适配准备 ≥1 份；反例测试 ≥2 个固化；skill 轮末快照落盘。

## done_when
1. express 闭环真实完成（SUCCESS_FILL_ONLY+独立回读零差异+盘点交接）或有完整外部阻断缺口登记且第 2-5 条完成。
2. rd_materials 闭环真实完成或诚实外部阻断缺口登记（说明缺口与所需输入）。
3. P1-a 追认增补已执行并留痕（合同区+events+台账）。
4. ≥2 类新研究工件 + 代码适配准备工件落盘。
5. ≥2 个反例测试固化；全量测试全绿 + 唯一 run OFFLINE_PASS；skill 快照落盘。
6. 交接齐备：改动+哈希、闭环 run/attempt/证据路径、台账 W06（三类实况）/W07 更新、下一轮入口（五类接入施工 or D22 新 session 验收准备）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-172415-7d069bdb" contract_id="ctr-633d23ae" source_block_id="src-7d069bdb" status="frozen" profile="minimal" -->
# 合同（round 8 · 0b826229 · minimal）：express+rd 真实闭环 + P1-a 追认 + 五类续推 + 反例固化

## 0. P1-a 合同追认（先做，一次性；A 已核实）

正式追认 round-7（run 20261024-152123-3e8d59be，合同 ctr-381e0163）两处合同外写入为既成授权事实：

- `bpm_plan_generate.py`：identity 绑定段 + system_observation→必须绑定派生根内 agent 登记观察工件否则拒绝（收紧来源证明，不放宽）。
- `bpm_ui.py`：`supersede_dead_form_intent` 及零写/写后未存两迁移（append-only、拒 SAVE_*、存活页拒接）。

授权依据（逐字）：A round-8 任务原文"### 0. 合同追认增补（P1-a，先做，一次性）——在本轮 team-task.md 合同区**正式追认 round-7 两处合同外写入**……A 已核实（round-07/acceptance/A-verification.md §6）：守卫零改动、判据未放宽、测试覆盖、全留痕"。时间/会话：2026-10-24 team-workflow round-8 source（src-7d069bdb，A 窗口 9ba961a6 发布，B 会话接棒 seq 39）。

自本合同起，上述两文件进入**常设允许写清单**（纪律：最小改动+对应测试+events 留痕）；其他任何新文件仍须先停-增补-再写，不沿用本次追认外推。追认记录进 events/台账。

## 1. 范围与授权链

- express 闭环：`automation/type-replay-plans/express-complex-R2-defaultbank/test-inputs/authorized_replay_facts.json`（只读复制进新 run）→ agent 自驱库函数链（register_request→模板缓存定向（type-view-15426094780 snapshot，lineage sha 绑定）→提取复核 locator+input_hashes→FactSet→reconcile→复用矩阵→blueprint→generate_fill_plan→validate 零 issues→execution_ready validate-only 子进程）→真实 Chromium fill_once --fill-plan --expect-name 陈晶（fill_only）→独立 DOM 回读零差异→页面盘点。禁止预制 facts_payload/blueprint 塞入口。
- rd_materials 闭环：同模式，材料 rd-complex-R2-namepicker/authorized_replay_facts.json，模板 type-view-15426104120 snapshot。products 按现有档案编号选入核对，不新造档案；发票按 products.price 分配合计闭合；费用说明为空（按材料实情）；超出范围的复杂分支如实登记不做。
- 授权语义随件：live-test-authorization.json（user_statement 逐字在盘，allow_save=false/allow_submit=false）+ test_only/not_new_expenses/no_invoice_rule 原文不得删除。
- registry 纪律沿用：FORM_INTENT/supersede 证据门接替，SAVE_* 一律拒；失败-恢复诚实留痕；登录类外部阻断→登记缺口转其余条款，不算失败轮。

## 2. 五类研究续推 + 代码适配准备

- 其余三类（01 其他费用/24 维修费/06 各项会议支出）从 census list 证据定向选号，**≥2 类**新增六节研究工件；`bpm_template.py --live --research-raw` 单发 ≤5 次、--login-wait 0、--expect-name 陈晶、observed_get 只读、零注册零启用零写页面；类型码从实测确定。
- 已研究两类（02/04）能力清单推进为**代码适配准备工件**≥1 份（差异落点映射到现有模块改造点清单，不实施注册/启用）。

## 3. 反例固化（D18）与 P2 小项

- round-7 四反例至少固化 2 个为测试：①COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED 阻断；②registry FORM_INTENT 门+死意图证据门；③EXACT_PICK_MISSING 瞬时失败不产生部分验收；④lost_page_rows 记录。
- P2：execution_ready plan.sha256→plan_hash（或双字段留兼容）；supersede docstring 收窄当前 context 语义；新增链 events schema 统一（不回改历史）；R6-P2-2 skill 措辞在维护窗口采纳（红线段逐字不动）；未保存关页服务端无残留以只读观察补证一次。

## 4. 允许写 / 只读 / 禁止

- 允许写：`bpm_plan_generate.py`、`bpm_ui.py`（P1-a 常设）、`bpm_request.py`（仅 P2 字段名最小改+测试）、`bpm_template.py`（仅研究旁路缺口最小补）、`bpm_extraction.py`（如视觉/渲染缺口最小补）、`tests/`、`.claude/skills/bpm-fill-run/`（措辞采纳，红线段逐字不动）、`automation/runs/<新run>/`、`automation/offline-verify/<run>/`、`automation/template-materials-program/`、`automation/type-extension/`（仅 events 性质记录，不改授权原文）、`team-task.md`（仅本合同块）、`team-progress.md`、memory。
- 只读：历史 run 工件（含 types-*、type-replay-plans、type-view/template、census、attempt_026、live-complex-demo）、`automation/task-registry/`（仅经 fill_once 正常登记）、`legacy-ia2/`、`automation/.pw-profile/`、`.local-session/`。
- 浏览器动作枚举（其余零导航零点击）：①express 填写一次+resume 纪律内重试 ②rd 填写一次+resume 纪律内重试 ③研究 raw fetch ≤5 次 --login-wait 0 ④P2 无残留只读列表观察一次。全部 fill_only。
- 禁止：保存/发送/流转/提交/上传/暂存/贴票/审批；不动 `stage1_browser_probe.py`/`fill_once.py`（如确需先 selftest 全绿且最小化）；不自动 commit；不虚构业务事实；test_context 不升级；凭证不入工件。

## 5. 验证（done_when 映射）

1. express 闭环 SUCCESS_FILL_ONLY+独立回读零差异+盘点交接，或完整外部阻断缺口登记且第 2-5 条完成。
2. rd 闭环同上或诚实缺口登记（说明缺口与所需输入）。
3. P1-a 追认执行留痕（合同区+events+台账）。
4. ≥2 类新研究工件+代码适配准备 ≥1 份落盘。
5. ≥2 反例测试固化；全量测试全绿+唯一 run OFFLINE_PASS；skill 快照落盘。
6. 交接齐备：改动+哈希、run/attempt/证据路径、台账 W06（三类实况）/W07 更新、下一轮入口。

<!-- /team-task-contract -->
