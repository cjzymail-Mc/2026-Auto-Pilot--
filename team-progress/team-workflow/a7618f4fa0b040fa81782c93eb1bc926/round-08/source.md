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
