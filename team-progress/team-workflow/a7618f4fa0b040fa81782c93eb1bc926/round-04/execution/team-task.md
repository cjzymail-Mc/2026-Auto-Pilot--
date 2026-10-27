<!-- team-task-source id="src-83144781" sha256="83144781bea2fd0d45f1e34af1326d2bd7389ce1df9c18d56bd1491b9c4d32c2" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 4
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 4 -->
# 本次任务：报销材料主线 W05 —— 计划生成与衔接（+R3-P2 两项小修）

总目标背景（自足）：多轮交付"用户仅给模板单号+原始资料，agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。已交付：W00 总台账（`automation/template-materials-program/progress.json` 唯一权威）；W02 双根契约（`bpm_materials.py` manifest v2.0）；W03 原件理解（`bpm_extraction.py`：PDF 两层/图片 OCR/xlsx·csv 语义解析/语义盘点/结构化缺口）；W04 事实与对账（`bpm_facts.py`：FactSet 稳定 ID F-0001…、五类来源封闭枚举、user_instruction 禁携派生绑定、check_version_drift 标记 needs_replan、reconcile 11 检+反例、未建模形态构造期 ValueError）。构建源清单已 glob 化（根目录 bpm_*.py 自动冻结）。本轮做 W05：从对账通过的事实自动生成可执行 v1.0 fill-plan 并衔接现有正式入口，消灭"解析完成但请用户/agent 手工生成计划"的断点。全部离线，不连 OA、不做浏览器操作。

验收口径继承：只填不存；守卫/SaveController/registry 原样；不虚构实单；合成材料仅机制测试；缺真实材料登记缺口不停工。

## 待做条款

### 1. R3-P2 两项小修（先行）
- R3-P2a：`bpm_facts.py` `_dec` 对超 2 位小数输入应 raise（明确报错），不得静默 quantize——金额语义歧义必须显式暴露；已有 2 位内行为不变。
- R3-P2b：收款身份组核对补"同账号不同户名"冲突检测（现有残缺/同名冲突之外的第三种阻断）。

### 2. W05a 事实→计划生成器（模块名自定，如扩展 bpm_facts 或新 bpm_plan_generate.py）
- 输入：对账通过的 FactSet（reconcile blocked=False 前置门）+ 类型规则（现有 travel/express/rd_materials 配置）；漂移先行：生成前必须 check_version_drift 无 needs_replan。
- 输出：v1.0 fill-plan（符合 `automation/fill-plan.schema.json` 与 `automation/task.schema.json` 既有契约），特征：
  - 每个执行值带来源：引用 fact_id + locator + 相关原件/派生工件 sha256（不复制无源值）；
  - 金额 Decimal；totalCost、明细合计、银行合计及各类适用金额层闭合（复用 reconcile 结论，不二次发明）；
  - 空表/不适用字段带 table_applicability 当次来源理由；免票行引用 no_invoice 事实依据；
  - 归并/拆分费用行须有本次材料与 OA 结构依据，保留原明细事实→计划行的映射（可追溯）；
  - 生成的计划必须通过现有 bpm_plan 正式校验（作为自动离线验证），失败即生成器缺陷，不得放宽校验。
- 不要求覆盖全部三类全部分支；至少 travel 或 express 一类合成场景端到端（材料→提取→事实→对账→计划→校验通过），另一类如时间允许补。

### 3. W05b 内部阶段状态与入口衔接
- 区分内部阶段（如 MATERIALS_READY / FACTS_BUILT / RECONCILED / PLAN_READY）与真正业务缺口 NEEDS_INPUT；"解析完成待生成计划"只能是内部阶段，不得作为对用户的终态。
- `fill_once.py --task` 现有准备路径衔接：材料齐备且对账通过时链路自动推进到 PLAN_READY（合成场景验证）；确缺业务输入时返回准确 NEEDS_INPUT 附结构化缺口（复用 GAP_FIELDS），不吞缺口、不把内部可推进误报为缺输入。
- 不改变现有 `--fill-plan --validate-only` / `--legacy-regression` 低层语义；新增衔接只发生在准备链路内部。

## 保留项与边界
- 不连 OA、不做浏览器操作；不改 `stage1_browser_probe.py`（若触碰先 selftest 全绿）；不动守卫、旧 run、task-registry、legacy-ia2；不自动 commit。
- 现有 v1.0 计划校验语义不放宽、不绕过；生成器产出的计划与手写计划同规同校。
- 原件只读；合成 fixtures 放 tests/；新依赖必要且最小化并在交接列明。

## 验证（全部离线）
- 新增单测：R3-P2a（>2 位小数 raise/2 位内不变）、R3-P2b（同账号不同名阻断）；生成器（来源绑定、金额闭合、空表理由、归并映射、漂移前置门、reconcile blocked 前置门、校验失败即失败反例）；阶段衔接（齐备→PLAN_READY、缺输入→NEEDS_INPUT+缺口、不误报）。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 174 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS，新模块自动入 source_manifest。

## done_when
1. R3-P2a/b 修复并有通过单测。
2. 至少一类合成场景端到端：合成材料→提取→事实→对账→自动生成 v1.0 计划→过 bpm_plan 正式校验，全链留工件哈希。
3. 内部阶段状态落地：齐备场景推进到 PLAN_READY；缺输入场景准确 NEEDS_INPUT+缺口；无"待 agent 生成计划"终态残留。
4. 全量 unittest 全绿；唯一 run OFFLINE_PASS。
5. 交接齐备：改动文件+sha256、测试结果、progress.json 的 W05 状态更新、下一轮入口建议（W01 模板决策矩阵 / W06 真实端到端准备）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-122428-83144781" contract_id="ctr-afabdc8a" source_block_id="src-83144781" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24，round 4）

**终态**：R3-P2 两小修落地（_dec 超 2 位小数 raise、收款同账号异名冲突阻断）；W05 计划生成与衔接落地——事实→计划生成器（reconcile blocked=False 与 check_version_drift 无漂移双前置门；每个执行值来源绑定 fact_id+locator+工件 sha256；金额 Decimal 三层闭合复用 reconcile 结论；免票行引用 no_invoice_basis 事实；空表/不适用带 table_applicability 有源理由；行映射 fact_bindings 可追溯；产出计划必须通过 bpm_plan.validate_plan 现行校验，失败即生成器缺陷不改校验）+ travel 合成场景端到端（材料→提取→事实→对账→自动生成→正式校验通过）全链留工件哈希；fill_once --task 准备链路内部阶段衔接（MATERIALS_READY/FACTS_BUILT/RECONCILED/PLAN_READY 与真缺口 NEEDS_INPUT 分离；"待生成计划"仅内部阶段不作终态；确缺输入返回结构化缺口复用 GAP_FIELDS；--fill-plan --validate-only/--legacy-regression 低层语义不动）；全量测试零回归；唯一 run OFFLINE_PASS 新模块自动入 source_manifest。

**本轮做**：
1. R3-P2a：bpm_facts._dec 输入超 2 位小数显式 raise（金额语义歧义不静默抹平），≤2 位行为不变。
2. R3-P2b：收款身份组补第三种阻断——同账号不同户名冲突（与既有残缺/同名异字段并存）。
3. W05a 新模块 bpm_plan_generate.py：generate_fill_plan(factset, blueprint)——前置门（reconcile blocked / drift needs_replan 任一命中即拒绝并给原因）；来源坐标 file#inner-locator 解析+与事实 input_hashes 交叉核验（无源值拒绝）；fact.source→plan source kind 映射（material_extraction→material/agent_reviewed 按工件在 originals/derived、template→template、user_instruction→user、deterministic_computation→derived sum、system_observation v1 显式拒绝并说明边界）；金额值必须等于所映射事实金额；totalCost 派生 sum；发票事实+分配→image_documents（record 分配闭合）；no_invoice_basis 事实→no_invoice_rows（有源理由）；返回 (plan, fact_bindings{pointer:{fact_id,kind,artifact_sha256}})；内部即调 validate_plan(verify_sources=True) 不通过即抛生成器错误。
4. W05b：fill_once.prepare_task 准备链路内部衔接——task 新增可选 facts_payload（agent 中间产物：FactSet 载荷+blueprint，非用户手写内部 JSON；validate_task 允许集与 task.schema.json 同步追加该可选键）；有载荷时自动 MATERIALS_READY→FACTS_BUILT（from_payload 反序列化）→RECONCILED（reconcile）→PLAN_READY（生成器+正式校验，计划写 run 内）；阻断/缺件返回 NEEDS_INPUT 附结构化缺口（GAP_FIELDS 形状）与所在阶段；无载荷行为与现有测试断言完全兼容（status/gaps 字段保留）。FactSet 增 from_payload（to_payload 对偶，附加不破坏 W04 语义）。
5. 验证全离线：新增单测——R3-P2a（>2 位 raise/≤2 位不变）、R3-P2b（同账号异名阻断）、生成器（来源绑定/金额闭合/空表理由/行映射/漂移前置门/reconcile 前置门/无源值拒绝/值≠事实拒绝/校验失败即失败反例）、e2e（travel 合成材料→run_pdf_extraction→事实→对账→生成→validate_plan 空_issues+load_plan 回读，工件哈希断言）、阶段衔接（齐备→PLAN_READY、缺件→NEEDS_INPUT+结构化缺口、无载荷旧断言不回归）；全量 discover 全绿（174 基线零回归）；唯一 run OFFLINE_PASS（bpm_plan_generate.py 经 glob 自动入 source_manifest）。

**本轮不做**：不连 OA、不做浏览器操作；不做 express/rd_materials 端到端（travel 一类达标即符合任务书"至少一类"）；不改 bpm_plan.py/bpm_materials.py/bpm_extraction.py 校验语义（生成器产计划与手写同规同校）；不动 stage1_browser_probe.py/守卫/SaveController；不动 automation/runs 旧工件、task-registry、legacy-ia2；不自动 commit；不虚构实单；system_observation 事实自动映射留 W06+（显式报错不静默）。

**允许写**：`bpm_facts.py`（仅 R3-P2a/b 修复与 from_payload 追加）、新模块 `bpm_plan_generate.py`、`fill_once.py`（仅 --task 准备链路内部阶段衔接；--fill-plan/--legacy-regression 路径不触碰）、`automation/task.schema.json`（仅追加可选 facts_payload 属性）、`tests/`（新增测试与 fixtures）、`automation/template-materials-program/`（台账更新）、`team-progress.md`、`team-task.md`（仅本合同追加）。
**只读**：`bpm_plan.py`、`bpm_materials.py`、`bpm_extraction.py`、`bpm_types.py`、`bpm_template.py`、`bpm_ui.py`、`bpm_verify.py`、`bpm_save.py`、`stage1_browser_probe.py`、`automation/fill-plan.schema.json`、`automation/document-types/`、`automation/runs/`、`automation/task-registry/`、`automation/offline-verify/` 既有产物、`.pw-profile/`、`legacy-ia2/`。
**禁止**：放宽/绕过 validate_plan、validate_dual_manifest、validate_image_documents 任一校验；删除或重写旧 run/registry/证据；写 task-registry；agent 推断写 user 来源或"用户已确认"；生成计划含无源值；把"待生成计划"作为对用户终态；自动 commit 或上传材料；虚构实单或保存验收。

**红线**：继承根 AGENTS.md 全部红线（只填不存；.pw-profile/ 活体 token 绝不入 git/日志/报告；legacy-ia2/ 只读；registry 只读核实；单 profile 单执行者；不走 VPN/代理；Python 一律 -X utf8）。team-task 四红线：①销毁性/不可逆操作；②对外交付物；③同一 failure_key 三次失败熔断（D23=1/3 已对因闭合且 A 判翻转 PASS，本轮防新增同 key——生成器入 glob 清单机制已自动覆盖）；④推翻已封决策。B 模式权限类命令后置人工门。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM；risk_class=MEDIUM；risk_owner=USER；risk_source=USER_STANDING_POLICY_20260904；runtime_policy=GLM_ALLOWED；risk_escalation=NONE（常设策略；runtime 一手证据已记 progress 头）。

**裁量项（contract-only：写推荐+依据，P6 执行期按 B 默认落实并记自主裁决）**：
- 生成器落点：新模块 `bpm_plan_generate.py`（推荐依据：生成/衔接与事实/对账分属两个聚合根——bpm_facts 保持 W04 冻结语义最小增量，生成器独立演进可单独冻结）。
- 来源坐标：统一 `file#inner-locator`（xlsx Sheet!A1 / JSON 指针 / CSV row:column），按事实 locator 前缀解析 base_dir 相对路径+实测 sha256 与 input_hashes 交叉核验（推荐依据：与 read_locator 既有能力一一对应，不发明新 locator 语法）。
- facts_payload 形状：{schema_version, facts(FactSet.to_payload), blueprint{...}, generated_by}，agent 中间产物不是用户输入（推荐依据：任务书"不要求用户编写内部 JSON"）。
- 阶段枚举与兼容：内部 stage 字段新增、status/gaps 旧字段保留（推荐依据：现有 test_bpm_plan/test_bpm_types 断言零破坏，衔接只在准备链路内部）。
- fixtures：tests/fixtures/w05/（travel_ledger.xlsx 多 sheet：明细/费用区间/收款；user_instructions.json；模板快照含 rendered_options），发票复用 w03 invoice.pdf+双根 manifest。

**done_when（字面可判；全部离线）**：
- D1: R3-P2a/b 有通过单测（>2 位小数 raise 且 ≤2 位不变；同账号异名收款阻断），全量旧测试不回归。
- D2: travel 合成场景端到端单测通过：合成材料→提取（run_pdf_extraction）→事实→对账（blocked=False）→自动生成 v1.0 计划→validate_plan(verify_sources=True) 返回空 issues 且 load_plan 回读一致；测试断言关键工件（双根 manifest、reviewed 派生、计划文件）sha256。
- D3: 生成器前置门与反例单测：reconcile blocked 拒绝、drift needs_replan 拒绝、无源值拒绝、值≠事实金额拒绝、破坏计划后 validate_plan 失败即生成器报错（不放宽）。
- D4: 阶段衔接单测：facts_payload 齐备→result.stage=PLAN_READY 且计划文件落 run；缺件→NEEDS_INPUT+GAP_FIELDS 形状结构化缺口；无 facts_payload 旧断言（NEEDS_INPUT/gaps/不启浏览器）全部保持。
- D5: `python -X utf8 -m unittest discover -s tests` 全绿（174 基线零回归）；`python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 唯一新 run OFFLINE_PASS 且 source_manifest 含 bpm_plan_generate.py。
- D6: 交接齐备：改动文件+sha256、测试结果、progress.json W05 状态与证据更新、下一轮入口建议（W01 模板决策矩阵 / W06 真实端到端准备）写明于 team-progress 收尾段及台账。
<!-- /team-task-contract -->
