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

<!-- team-task-contract run_id="20261024-152123-3e8d59be" contract_id="ctr-381e0163" source_block_id="src-3e8d59be" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24）

**终态**：travel 走通第三层证据闭环——以用户授权历史回放工件（真实单 15426093015 徐亮差旅 633.84，rev02：四表金额闭合、关联替换逐字授权、发票本次演示明确不要求且不构成免票规则）为本次材料（原件只读复制进新独立 run），agent 在真实会话依次自驱库函数 register_request→resolve_template（census 20261023-142146 缓存定向）→提取复核（agent 对 JSON 材料逐字段提取留 locator+input_hashes）→FactSet→复用矩阵→blueprint/计划→generate_fill_plan→PLAN_READY→execution_ready（真实 --validate-only 全绿）；**不预写 facts_payload/blueprint 塞入口**，入口若缺编排补编排。随后正式入口 `fill_once --fill-plan … --expect-name 陈晶`（本次登录身份，system_observation）真实 Chromium 填写（test_context 强制 fill_only；--keep-open-minutes 5：本轮无人现场检查，终局盘点/截图在窗口内完成即闭页，任务书 45 分钟形制为现场演示场景），终局独立 DOM 回读零差异才过，未保存页盘点交接（身份/内容/截图/处置建议）。真实发票视觉复核：bpm_extraction 渲染改全 PDF 页+页级锚点贯通；扫描件/图片由 agent 视觉复核（看渲染图逐字段核对留证，review_pass verify=agent-visual），barstub 降级为纯测试引擎、真实路径声明改为"文本层/agent 视觉"；在现有 PDF 材料上实际运行留复核工件；**真实差旅发票原件经盘点确认仓库不存在（全 repo 仅合成 fixtures）→ 按缺口登记，不虚构**。五类只读研究：bpm_template 增最小 `--research-raw` 只读旁路（同 GET 集合、跳过 normalize、落 raw JSON，不注册不启用不写页面）后，对 ≥2 个五类候选单号单次 live raw fetch（--login-wait 0，失败即登记），产出差异说明+规则建模草案+接入所需共享能力清单；类型码从证据确定。顺带：R6-P2-1 skill 文件轮末快照随 run 落盘（本轮起执行）；R6-P2-2 措辞建议记台账。

**本轮做**：
1. travel 真实闭环（主靶）：新独立 run `automation/runs/20261024-<ts>-travelloop/`——材料复制（rev02 JSON+清单）、agent 自驱链每步留中间工件+events（请求登记/模板快照/提取复核记录/FactSet 导出/矩阵/计划/execution_ready）、真实填写、独立回读、页面盘点。登录失效/profile 被占→WAIT_HUMAN_LOGIN 留证转第 2/3 条不算失败轮；填写失败如实记 attempt 工件，可按既有 --resume-run 同绑定纪律重试一次，不改守卫不放宽判据。
2. 视觉复核补齐：`render_original` 全页渲染（PDF 每页 PNG，图片原样），`ocr_pass`/相关路径页级贯通；单测渲染页数断言更新为全页（存量 7+13 相关测试零回归）；在≥1 份多页 PDF 材料上实际运行 agent 视觉复核（渲染图→逐字段核对→review_pass 留证：值+页/区域锚点+复核者+机械比对缺位如实记录）；barstub 注记为纯测试引擎，真实路径=文本层或 agent 视觉（模块+skill 文档同步）；真实发票原件缺口 GAP_FIELDS 登记。
3. 五类研究：`bpm_template.py --live --research-raw`（新增旁路：仅输出 raw {number,uuid,main,children} JSON 至 run 目录；无 normalize/无注册/无页面写）+对低值办公 15426101596、福利劳保 15426071883（或证据在册的同五类号）各≤1 次单发尝试；每类产出研究工件（主/子表结构+字段清单+与三类差异+规则建模草案+接入共享能力清单+类型码证据）；live 失败→基于 typequery 列表证据的浅层研究工件+缺口登记，仍需≥2 份。
4. 顺带：轮末把 `.claude/skills/bpm-fill-run/SKILL.md`+`references/*.md` 快照复制进本轮 run 目录并记哈希（R6-P2-1）；台账记 R6-P2-2 措辞建议（冻结探针会话维护性写入 vs"只读"字面歧义，建议后续合同显式豁免）。
5. 验证与台账：全量 `python -X utf8 -m unittest discover -s tests` 全绿（236 基线+新增零回归）；`python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 唯一 OFFLINE_PASS；改 `bpm_extraction.py`/`bpm_template.py` 后相关单测先行；不自动 commit。

**本轮不做**：不测保存/提交（fill_only；SaveController/守卫/registry 原样）；不虚构真实发票/Excel 原件或新业务事实（回放材料如实标注 demo_only/not_new_expenses）；除合同枚举浏览器动作（①闭环填写一次+resume 纪律内重试 ②研究 raw fetch ≤5 次）外零导航零点击；不动 `stage1_browser_probe.py`/`fill_once.py`（如确需改动先 selftest 全绿且最小化，并在此合同外不得扩大）；历史 run 工件（含 live-complex-demo、attempt_026、types-*、census）零改动（只读复制）；`automation/task-registry/` 只经 fill_once 正常登记；`legacy-ia2/` 只读；不注册/不启用五类任何写入路径；不引入第三方 OCR 框架。

**允许写**：`bpm_extraction.py`（全页渲染+页级锚点+barstub 注记）、`bpm_template.py`（仅 research-raw 旁路+其单测）、`bpm_request.py`（仅当闭环暴露编排缺口时最小补）、`tests/`（新增/更新）、`.claude/skills/bpm-fill-run/`（真实路径声明/barstub 降级注记；红线段逐字不动）、`automation/runs/<新run>/`（travelloop/研究/视觉复核工件+skill 快照）、`automation/offline-verify/<run>/`（唯一验收）、`automation/template-materials-program/`（台账）、`team-task.md` 合同区、`team-progress.md`、memory。
**只读**：`fill_once.py`、`stage1_browser_probe.py`、`bpm_plan.py`、`bpm_facts.py`、`bpm_materials.py`、`bpm_types.py`、`automation/.pw-profile/`、`automation/.local-session/`（探针自身会话维护写入按 R6-P2-2 已知口径）、`automation/task-registry/`、`legacy-ia2/`、全部历史 run 工件、`templates/`、`patches/`。
**禁止**：`.pw-profile`/`.local-session` 凭证或元数据复制进 git/日志/材料清单/测试工件；绕过/削弱守卫与 registry；为通过回读放宽 `bpm_plan`/verify 判据；伪造 live/raw/回读结果；为闭环预写 facts_payload/blueprint 再塞入口；把回放演示扩大为保存授权。

**红线**（AGENTS.md 全量并入+任务保留项）：①默认只填不存（保存/发送/流转/提交/上传/暂存/贴票/审批一律禁点）；②`.pw-profile` 活体 token 不外泄；③结果以 `automation/runs/<run>/` 工件为准（events.jsonl 追加式），聊天叙事为辅，异常脱敏；④`legacy-ia2/` 只读。附加：单 profile 单执行者；`--no-proxy-server`、`python -X utf8`、ctypes 判活沿用；`--login-wait 0` 纪律（失效不扫码不等待）；回放材料的 demo_only/not_new_expenses 语义随件携带不得删除。

**风险 envelope**（P0.5 已登记）：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。

**done_when（带验证）**：
1. travel 闭环真实完成有完整证据链（材料复制件+agent 自驱中间工件+events+真实填写 attempt+独立 DOM 回读零差异报告+页面盘点+终局截图），或登录类阻断有完整缺口登记且第 2/3 条完成 → 验证：run 目录工件齐备、events 全链可重放、回读报告零 mismatch（或 WAIT_HUMAN 缺口在案）。
2. agent 自驱内部步骤真实走通（无预制 facts_payload/blueprint 塞入口）→ 验证：链路各步中间工件+events 在案且值全部可溯源到回放材料/模板/系统观察；入口编排缺口（若有）修复留 diff+events。
3. 全页渲染+agent 视觉复核实际运行留证；barstub 不再被声明为真实路径引擎 → 验证：多页渲染页数断言/复核工件（值+锚点+复核者+机械比对缺位记录）在案；模块与 skill 文档真实路径声明已改；真实发票原件缺口已登记。
4. ≥2 份五类研究工件落盘 → 验证：每份含结构/字段/差异/规则草案/能力清单/类型码证据；live raw fetch 工件或失败缺口在案；无任何注册/启用/写页面动作。
5. 全量测试全绿+唯一 run OFFLINE_PASS+skill 快照落盘 → 验证：unittest 输出、build_result.json、快照文件+哈希清单。
6. 交接齐备 → 验证：handoff 含改动+sha256、闭环 run/attempt/证据路径、台账 W06（travel 实况）/W07（研究状态）更新、下一轮入口。
<!-- /team-task-contract -->
