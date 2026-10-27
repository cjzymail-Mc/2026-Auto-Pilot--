<!-- team-task-source id="src-30ee7ae1" sha256="30ee7ae1c16fe9ee95b9114c05807c5ebc55f59a88852a7573b8bff73bf82bb1" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 5
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 5 -->
# 本次任务：报销材料主线 W01 —— 用户请求与模板决策（+R4-P2 四条加固 + 未知类别只读识别）

总目标背景（自足）：多轮交付"用户仅给模板单号+原始资料，agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。已交付：W00 总台账；W02 双根契约（`bpm_materials.py`）；W03 原件理解（`bpm_extraction.py`）；W04 事实与对账（`bpm_facts.py` FactSet/reconcile）；W05 计划衔接（`bpm_plan_generate.py` 双前置门生成器 + `fill_once.py` 阶段机 MATERIALS_READY→…→PLAN_READY，模板事实须与快照哈希一致）。构建源清单 glob 化自动冻结。本轮做 W01：把"用户自然语言请求→唯一模板→类别识别→逐字段复用决策"串成正式路径（离线，用缓存模板快照；live 读模板留 W06 浏览器轮）。全部离线，不连 OA。

验收口径继承：只填不存；守卫/SaveController/registry 原样；不虚构实单；合成材料仅机制测试；缺真实材料登记缺口不停工。

## 待做条款

### 1. R4-P2 四条加固（先行，测试质量与门加固）
- expect_money：缺 amount 键时不得自比恒真——键缺失/类型不符须显式失败。
- FactSet.from_payload：反序列化必须共享 add() 全套构造不变量（未知类别/来源、user_instruction 禁派生绑定等在反序列化路径同样生效）。
- 空 input_hashes 事实不得绕过 drift 门：生成器/漂移检查对无绑定哈希的事实按最高风险处理（拒绝或强制补绑定），不静默放行。
- _dec 正例断言实质化：正例须断言真实解析结果（如 Decimal("12.30")），不用同义反复断言。

### 2. W01a 请求登记
- 用户自然语言请求 → 结构化请求记录（版本化工件落派生根）：完整模板单号、材料目录、业务说明/应报范围、可选明确指定（申请人/收款对象/预算/关联单据）、用户政策（默认身份等）。
- 请求记录带来源（user_instruction 语义）；缺必要素（无模板号/无材料定位）→ 准确 NEEDS_INPUT 附 GAP_FIELDS 缺口，不猜。

### 3. W01b 唯一模板核对与类别识别（离线缓存路径）
- 用 `bpm_template.py` 缓存快照（--census 既有缓存）按完整单号定向读取：核对唯一 UUID、类别、数据完整性；快照+哈希留证。
- 类别识别：从快照主表/配置映射 document_type（travel/express/rd_materials）；用户业务说明与模板类别矛盾 → 集中报告，不悄悄换类/换模板。
- live OA 读模板不在本轮（W06 浏览器轮做）；本轮不新增任何网络访问。

### 4. W01c 逐字段复用/替换矩阵
- 产出可审查矩阵工件：「模板字段 → 采用(稳定复用)/替换(本次来源)/不适用(理由) → 本次值来源（fact_id/locator/哈希或用户指令）」，覆盖字段组：
  - 表单类别、结构、字段和历史填写形态（识别用，不直接抄值）；
  - 公司、流程归属、币种、预算及稳定收款资料（本次适用且有依据才复用，旧年度/旧收款对象不无条件沿用）；
  - 当前默认申请人/制单人（按本次用户政策，不被模板历史人员覆盖）；
  - 日期、期间、业务说明、费用行、金额、发票身份（仅本次材料/系统观察/明确计算）；
  - 关联编号、物品档案编号、收款对象（必须证明属于本次，系统唯一命中）；
  - 空表与不适用字段（本次业务材料和已确认规则解释，不因模板为空自动为空）。
- 反例测试：模板旧日期/旧金额/旧收款冒充本次值 → 拒绝；旧年度预算无条件沿用 → 拒绝。
- 矩阵作为 template blueprint 输入接入 W05 生成器（模板快照哈希绑定）合成场景贯通。

### 5. 未知/未登记类别只读识别（D13 补齐）
- 快照类别不在封闭注册内 → 定向只读识别输出：具体不支持部分、已有证据（快照字段/结构差异）、登记开发子任务建议；不执行任何未知表单写入，不映射到"其他费用"绕过。
- 单测：未知类别快照 → 识别报告 + 写入拒绝。

## 保留项与边界
- 全离线；不动守卫、旧 run、task-registry、legacy-ia2；不自动 commit；不改 `stage1_browser_probe.py`。
- 缓存快照只读取证；不为找单号普查全部历史（只用完整单号定向缓存命中）。
- 历史仅复用有依据的稳定身份/预算/收款资料；本次日期/费用/发票/金额/关联编号不得从旧单推导（反例必测）。

## 验证（全部离线）
- 新增单测：R4-P2 四条；请求登记（齐备/缺要素两态）；模板核对（唯一性/类别矛盾集中报告）；矩阵（五类字段组覆盖+两个冒充反例）；生成器贯通（矩阵 blueprint→计划→validate 通过）；未知类别识别+写入拒绝。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 190 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS，新模块自动入 source_manifest。

## done_when
1. R4-P2 四条加固落地+通过测试。
2. 请求登记→模板核对→类别识别→复用矩阵链路实现+测试（含缺要素 NEEDS_INPUT、类别矛盾集中报告、两个冒充反例）。
3. 矩阵 blueprint 接入生成器合成场景贯通（validate 通过）。
4. 未知类别只读识别+拒绝写入有测试。
5. 全量 unittest 全绿；唯一 run OFFLINE_PASS。
6. 交接齐备：改动文件+sha256、测试结果、progress.json 的 W01 状态更新、下一轮入口建议（W06 浏览器轮准备：live 模板读取+B1-B7 执行计划；真实材料缺口如实登记）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-131905-30ee7ae1" contract_id="ctr-1a5b516d" source_block_id="src-30ee7ae1" status="frozen" profile="minimal" -->
# Round-5 合同：W01 用户请求与模板决策（+R4-P2 加固 + 未知类别只读识别）

## 0. 先序条款
1. R4-P2 四条加固先行落地并过测试，再做 W01 主体。
2. 全程离线：零网络、零浏览器、不连 OA；不动守卫/SaveController/registry/legacy-ia2/旧 run；不自动 commit。

## 1. 允许写面（冻结边界）
- 新增 `bpm_request.py`（W01a 请求登记 / W01b 缓存定向模板核对+类别识别 / 未知类别只读识别 / W01c 复用矩阵+矩阵→blueprint 模板绑定项）。
- `bpm_facts.py`：`FactSet.from_payload` 共享 `add()` 全套构造不变量（抽取共享校验路径，fact_id/created_at 保持原值语义不变）。
- `bpm_plan_generate.py`：①expect_money 缺 amount 键显式失败；②被绑定的 material_extraction/template 事实缺 input_hashes → 生成器拒绝（按最高风险处理，不自动补绑定——补绑定=生成器代事实主张来源）。
- `bpm_materials.py`：`DERIVED_ROLES` 封闭枚举追加 `user_request`、`decision_matrix` 两值（一行+注释，其余不动）。
- 新增 `tests/test_bpm_request.py` + `tests/fixtures/w01/`（全合成 census corpus：travel 正例 doc+未知类别 doc）；`tests/test_bpm_plan_generate.py`、`tests/test_bpm_facts.py` 按上列修复同步增改。
- 台账：`automation/template-materials-program/progress.json`、`notes.md`。
- 只读：`bpm_template.py`/`bpm_types.py`/`bpm_plan.py`/`bpm_extraction.py`/`fill_once.py`/`stage1_browser_probe.py`/`verify_bpm_build.py` 等其余全部。

## 2. R4-P2 验收
- D-P2a：`from_payload` 反序列化路径与 `add()` 同一套不变量（未知类别/来源、locator 非空、deterministic_computation 必带 derivation、user_instruction 禁派生绑定、_FORBIDDEN 字段拒绝）——各至少一反例测试。
- D-P2b：expect_money 绑定缺 amount 键的金额事实 → PlanGenerationError（不再自比恒真）；正例（expense/total/payee 正常金额）不回归。
- D-P2c：被绑定 material_extraction/template 事实 input_hashes 为空 → 生成器拒绝（显式错误信息）；正例补齐绑定（模板事实绑快照哈希）后贯通。
- D-P2d：`_dec` 正例断言实质化（断言真实量化结果如 Decimal("12.30")），bad 例保持 assertRaises。

## 3. W01a 请求登记
- 结构化请求记录字段：完整模板单号（数字串）、材料目录、业务说明/应报范围、可选明确指定（申请人/收款对象/预算/关联单据/声明类别）、用户政策（默认身份等）。
- 登记=版本化工件落双根 manifest 派生根（`register_derived` role=user_request，sources=本次原件哈希）；记录携带 user_instruction 语义来源标注。
- 缺必要素（无模板单号/无材料定位）→ 返回 NEEDS_INPUT + GAP_FIELDS 形状结构化缺口（file/locator/region/candidates/reason/affected_rows），不猜、不落盘。

## 4. W01b 唯一模板核对与类别识别（仅缓存路径）
- 用 `bpm_template.cached_template(census_path, 完整单号)` 定向读取：唯一命中、fetch/children 全 200、快照（uuid/document_type/applicant/header/tables/model_observation）+corpus path+sha256 留证；不普查历史、不新增网络。
- 类别识别：快照 submitType（code 或 label）→ 封闭注册 document_type；请求记录带声明类别且与模板类别矛盾 → 集中冲突报告并拒绝继续（不悄悄换类/换模板）。
- live OA 读模板明确不在本轮（W06）。

## 5. 未知/未登记类别只读识别
- 快照类别不在封闭注册 → 输出只读识别报告：观察到的类别值、注册内类别对照、不支持部分（无可执行 config/编辑器列定义）、已有证据（主表/子表结构差异）、登记开发子任务建议；显式 writable=false。
- 任何未知类别写入路径拒绝（不映射"其他费用"绕过）；单测覆盖识别报告+写入拒绝两态。

## 6. W01c 逐字段复用/替换矩阵
- 矩阵行覆盖六组：①表单类别/结构/字段/历史填写形态（识别用，不直接抄值）②公司/流程归属/币种/预算及稳定收款资料（本次适用且有依据才复用）③当前默认申请人/制单人（按本次用户政策，不被模板历史人员覆盖）④日期/期间/业务说明/费用行/金额/发票身份（仅本次材料/系统观察/明确计算）⑤关联编号/物品档案/收款对象（必须证明属于本次）⑥空表与不适用字段（本次业务材料和已确认规则解释）。
- 每行决策 ∈ {adopt, replace, identify, not_applicable} + 本次值来源（fact_id/locator/sha256 或用户指令文本）；矩阵工件 role=decision_matrix 落派生根。
- 冒充反例（必须测）：模板旧日期/旧金额/旧收款冒充本次值 → 构造期拒绝；旧年度预算无条件沿用（无用户确认）→ 拒绝；模板历史申请人覆盖本次用户政策 → 拒绝。
- 贯通：矩阵决策驱动 blueprint 模板绑定项（模板快照哈希绑定）→ `generate_fill_plan` → `validate_plan(verify_sources=True)` 空 issues（合成 travel 场景端到端）。

## 7. 验证与交接
- 新增/修改测试全绿；`python -X utf8 -m unittest discover -s tests` 全量绿（存量 190 零回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<时间戳>`（唯一 run）OFFLINE_PASS，`bpm_request.py` 自动入 source_manifest。
- 台账 W01 状态更新+round-5 条目；notes 记 W06 入口（live 模板读取+B1-B7 执行计划；真实材料缺口如实登记）。
- 交接：改动文件+sha256、测试结果、失败计数透传（D23=1 由 A 复核）。

## 8. 裁量项裁决记录（P2 推荐落地）
- 新模块名 `bpm_request.py`（W01 四能力一体，冻结面隔离；R2-P5 glob 自动纳入）。
- 派生角色枚举扩 user_request+decision_matrix（封闭枚举显式扩充，不做宽容补全）。
- P2-3 采"拒绝"而非"自动补绑定"（生成器不代事实主张来源）。
- 矩阵→blueprint 以库函数返回模板绑定项建议，agent 组装 blueprint；不新增 CLI、不动 fill_once。
- fixtures w01 全合成 corpus（不依赖真实 run 目录，测试自足）。
<!-- /team-task-contract -->
