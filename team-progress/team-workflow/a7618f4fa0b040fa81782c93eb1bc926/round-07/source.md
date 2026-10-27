<!-- team-task-source id="src-3e8d59be" sha256="3e8d59beb60260bc2310eba76ad3bf9c3b9e5e23271dc6332f934f59a5e9e13e" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 7
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 7 -->
# 本次任务：travel 真实闭环（原始资料→agent 自驱全链→真实网页填写→独立 DOM 验收）+ 真实发票视觉复核 + 五类只读研究

**本任务来自用户 2026-10-24 三点纠偏的直接指令，不是可选优化。用户原话要点：①图片识别目前只有 barstub 测试引擎、扫描 PDF 只渲染首页——要用现有视觉/PDF 能力补齐真实理解，不建复杂 OCR 框架；②计划生成依赖预制 facts_payload/blueprint——下一轮要证明 agent 能自行完成这些内部步骤，不是只验证测试代码组装好的输入；③缺八类新材料不能整体停工——缺材料只阻断对应新业务验收，五类历史结构只读研究、规则建模、代码适配照常推进。优先完成一类"原始资料→agent 提取复核→计划→真实网页填写→独立 DOM 验收"闭环；不要再以一轮纯离线通过代替这一步。保存成功验收继续排除。**

背景（自足）：W00-W05 及 W06 前置已交付（总台账/双根契约/提取管线/事实对账/计划生成/请求与模板决策/validate-only 执行就绪/skill 增补/live 模板只读读取已验：模板 15426095951 live 与缓存一致、登录态有效）。差旅是三类中最成熟（attempt_026 真实整单 SUCCESS_FILL_ONLY、29/32 零 mismatch）。本轮把它走成第三层证据。

## 待做条款

### 1. travel 真实闭环（主靶，用户指令①②的落地）
- **原始资料来源**：从既有授权历史业务的 run 工件中只读选取一套真实差旅原始材料（发票 PDF/图片、费用 Excel——如 attempt_026 或 types-* 系列中实际用过的原件；不虚构、不新建业务，test_context 沿用既有回放授权，模式 fill_only）。材料复制进本轮独立 run 的派生工作区（原件只读）。
- **agent 自驱全链（不是测试代码组装）**：在真实会话运行时，agent 依次调用库函数完成 register_request → resolve_template → 提取复核 → FactSet → reconcile → blueprint/复用矩阵 → generate_fill_plan → PLAN_READY → execution_ready(validate-only)。**禁止为通过链条预写 facts_payload/blueprint 再塞给入口**；入口若缺内部衔接，补的是入口编排（agent 步骤驱动），不是更多测试固定输入。过程留 events/中间工件。
- **真实网页填写（B1-B7 相关段）**：正式入口 `fill_once --fill-plan ... --expect-name <本次登录身份> --keep-open-minutes 45` 真实 Chromium 执行：真实身份、选择器唯一命中、类别/预算/银行/关联联动、全部行写入。**fill_only，不保存不提交。**
- **完整独立 DOM 回读**：终局新鲜快照核对全部计划值/行数/金额/额外数据，零差异才过；不以写入函数返回当验收。
- **页面状态与交付**：未保存页盘点交接（页面身份、内容、截图、处置建议），run/attempt/events/终局截图齐备。
- 若登录失效/profile 被占：按 WAIT_HUMAN_LOGIN 机制留页面与工件、登记缺口，**当轮转做第 2/3 条**，不算失败轮；不扫码不等待。

### 2. 真实发票视觉复核补齐（用户指令①）
- `bpm_extraction.py` 扫描渲染改**全页**（不只首页）；页级定位贯通。
- 真实路径识别用**本环境现有能力**：文本 PDF 走文本层；扫描件/图片渲染后由 **agent 视觉复核**（模型看渲染图逐字段核对票号/日期/金额/主体，产出 reviewed_extraction 并逐字段留证）；barstub 降级为纯测试引擎不再作为"真实路径"声明。
- 不引入新第三方 OCR 框架；最小必要依赖需说明。在本轮选用的真实差旅发票上实际运行并留复核工件；模糊值按 GAP_FIELDS 登记不猜。
- 离线单测保持全绿（现有 7+13 相关测试不回归；渲染页数断言更新为全页）。

### 3. 五类只读研究推进（用户指令③，并行项）
- 从 census 缓存候选单号（低值办公 15426101596 等、福利劳保 15426071883 等）做定向只读研究：主/子表结构、字段与编辑类型、与三类的差异、预算/收款/关联形态。
- 产出≥2 类研究工件（差异说明+规则建模草案+接入所需共享能力清单）；**不注册、不启用、不写页面**。内部类型标识/API 代码从证据确定，不从中文名猜。

### 4. 顺带（小）
- R6-P2-1：skill 文件轮末快照随 run 落盘（本轮起执行）。
- R6-P2-2 措辞建议记台账（冻结探针会话维护性写入 vs 只读字面歧义）。

## 保留项与边界
- fill_only；不测保存、不验收保存成功；SaveController/守卫/registry 原样；test_context 强制 fill_only 不升级。
- 原始材料只读（历史 run 工件零改动，复制进新 run 派生区）；不虚构新业务事实；不新建真实报销（用的是授权历史业务材料驱动新页填写练习，属既有回放授权范围）。
- 单 profile 单执行者；探针如需改动先 selftest 全绿；不自动 commit。

## 验证
- 闭环实跑证据：events 全链（含 agent 自驱中间工件）、终局截图、独立回读零差异报告、页面盘点。
- 视觉复核工件：真实发票渲染图+逐字段复核记录+哈希绑定。
- 全量 `python -X utf8 -m unittest discover -s tests` 全绿；`verify_bpm_build.py --run template-materials-<时间戳>` 唯一 run PASS。
- 五类研究工件≥2 份。

## done_when
1. travel 闭环真实完成并有完整证据链（原始材料→agent 自驱→真实填写 fill_only→独立 DOM 回读零差异→页面交接）；或登录类外部阻断时有完整缺口登记+第 2/3 条完成。
2. agent 自驱内部步骤在真实会话中走通（无预制 facts_payload/blueprint 塞入口），入口编排缺口（若有）已修复并留 events。
3. 全页渲染+agent 视觉复核在≥1 张真实差旅发票上运行并留证；barstub 不再被声明为真实路径引擎。
4. ≥2 类五类研究工件落盘。
5. 全量测试全绿+唯一 run OFFLINE_PASS；skill 快照落盘。
6. 交接齐备：改动+哈希、闭环 run/attempt/证据路径、台账 W06（三类端到端：travel 完成/阻塞实况）与 W07 研究状态更新、下一轮入口（express/rd 闭环 或 五类接入施工）。
<!-- /team-task-source -->
