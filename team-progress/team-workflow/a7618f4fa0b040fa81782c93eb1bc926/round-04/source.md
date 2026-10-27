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
