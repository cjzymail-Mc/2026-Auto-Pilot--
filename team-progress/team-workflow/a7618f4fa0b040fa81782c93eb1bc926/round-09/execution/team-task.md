<!-- team-task-source id="src-3e99d777" sha256="3e99d777e64c4fadbd31c60354dcfed7dbeec59247fc5a871ee033893dc876b2" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 9
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 9 -->
# 本次任务：五类接入施工首件放量（02/04 config→封闭注册→离线链）+ D18 离线矩阵补行 + D22 验收方案准备

背景（自足）：Round-8 已完成三类真实闭环（travel r7 / express r8 / rd r8，均 SUCCESS_FILL_ONLY+独立回读零差异）、P1-a 追认关闭、五类研究 4/5（七类码 08/11/15/02/04/01/24 实测互异）、`code-adaptation-prep-02-04.md` 9 落点映射就绪。A 验收 20 PASS / 1 BLOCKED / 6 FAIL；D19 已翻 PASS_DYNAMIC。真实发票原件（D4）与三类"本次原始材料"（D11/D20）为用户供料依赖，已登记不阻塞。06 会议支出 census 0 候选，待用户供号。

## 待做条款

### 1. 写授权增补（本轮合同新增，先声明）
- 授权写入：`bpm_types.py`（封闭注册扩展）、`automation/document-types/*.json`（低值办公 02 / 福利劳保 04 新 config 文件）、对应 `tests/`。
- 授权依据：冻结任务书 §8.2 五类接入循环 + round-8 `code-adaptation-prep-02-04.md` A 表第 1-2 级（config 落盘→封闭注册→离线链）。
- **边界**：新增 JSON 不自动启用类型（D12 明文）；本轮注册为**离线链可用**，不授权 02/04 真实页面控件测试、不注册业务填写路径、不在真实 OA 创建 02/04 新页——真实控件测试待离线全绿后下一轮按结果另行授权。

### 2. 02 低值办公 / 04 福利劳保 接入首件（主靶，按 A 表 1-2 级）
- 按研究工件（research_dijiazhi_15426101596.md / research_fulilabao_15426071883.md）实测结构落 config：主/子表字段与编辑类型、submitType/类型码（02/04，实测证据指针随件）、reimItem 前缀模式（02001/04003）、detailrels 形态（02 非零绑定 / 04 零金额）、banks 分摊闭合规则、invoice=false 文档级免票通道。
- `bpm_types.py` 封闭注册两个新类型（类型名/码/表集合/amount_rules/空表适用性），schema 校验、行数组、选择器契约与三类同构。
- 离线链验证：合成材料（明示 synthetic，不入业务 manifest）→ 提取→FactSet→reconcile→复用矩阵→blueprint→generate_fill_plan→validate_plan 零 issues→**validate-only 子进程 exit 0**（不开真实页面）。
- 每类至少 3 个离线单测（注册/校验/链路）；差异说明落 `automation/document-types/<type>.notes.md`（与研究工件的差异对照）。

### 3. D18 离线矩阵补行（≥4 个新测试）
- PDF/图片变体：多页 PDF 逐页锚点、一页多票拒绝/拆分策略（合成件，明示测试用）。
- Excel 变体：多 sheet、公式单元格取值、汇总/明细并存、隐藏行/筛选态（合成 xlsx）。
- 数值保真：前导零票号/账号、长账号、金额 Decimal 精度（0.005 级）在提取→事实→计划三段不丢。
- 已有反例不回归；每行测试对应矩阵条目在注释/文档中标注。

### 4. D22 新 session 使用验收——方案准备（不实施）
- 产出 `automation/offline-verify/d22-acceptance-plan-<时间戳>/D22_plan.md`：验收范围（新 session 从登录探查到填写交付的哪些环节）、入口清单与所需参数、证据要求、判定标准、当前入口缺口（若 probe/入口需改动，列出改动点但**不实施**——改动另行授权）。
- 目的：W10 前置方案，供 A/用户审后下轮授权实施。

### 5. mc-expert 三条观察处置（小）
- 链 events 双前缀单例化（chain 重跑时旧前缀清理或显式分段标记，不破坏 append-only 语义的可选方案落地其一）。
- research events 键名消歧（authorization 字样仅键名无值——改名）。
- no-residue 原始布尔与终判布尔命名消歧。

## 保留项与边界
- fill_only；不测保存、不验收保存成功；SaveController/守卫/registry/legacy 原样；本轮**不触碰真实 OA 页面**（除登录探查例行的只读身份核验外零导航零点击）。
- 合成材料仅测试用、明示标注、不入业务 manifest、不虚构业务。
- 探针/入口文件（stage1_browser_probe.py/fill_once.py）本轮零改动；`bpm_plan_generate.py`/`bpm_ui.py` 常设清单内最小改动+测试+留痕；其他新文件先停-增补-再写。
- 单 profile 单执行者；不自动 commit。

## 验证
- 全量 `python -X utf8 -m unittest discover -s tests` 全绿（含 ≥10 新测试）；`verify_bpm_build.py --run template-materials-<时间戳>` 唯一 run PASS（source_manifest 自动冻结新文件）。
- 02/04 离线链 validate-only 双双 exit 0；config 与研究工件差异对照齐备。
- D22 方案工件落盘；三条观察处置留痕。

## done_when
1. 02/04 config+封闭注册+离线链走通（validate-only exit 0，零真实页面动作），每类 ≥3 单测。
2. D18 ≥4 个新离线矩阵测试落盘全绿并标注矩阵条目。
3. D22 验收方案工件落盘（含入口缺口清单，不实施改动）。
4. 三条 mc-expert 观察处置完毕。
5. 全量测试全绿 + 唯一 run OFFLINE_PASS + skill 轮末快照。
6. 交接齐备：改动+哈希、新文件清单、台账 W07/W08 更新、下一轮入口（02/04 真实控件测试授权申请 或 D22 实施）。
<!-- /team-task-source -->
<!-- team-task-contract run_id="20261024-192351-3e99d777" contract_id="ctr-15712bcb" source_block_id="src-3e99d777" status="frozen" profile="minimal" -->
# 合同（round 9 · minimal）：02/04 接入首件（config→封闭注册→离线链）+ D18 矩阵 + D22 方案 + 三观察处置

## 0. 写授权增补（本轮新增，来源=任务 §1 逐字）

授权写入：`bpm_types.py`（封闭注册扩展两个新类型）、`automation/document-types/*.json`（02 低值办公 / 04 福利劳保 新 config）及同目录 `<type>.notes.md` 差异对照、对应 `tests/`。授权依据（任务原文逐字）："授权写入：`bpm_types.py`（封闭注册扩展）、`automation/document-types/*.json`（低值办公 02 / 福利劳保 04 新 config 文件）、对应 `tests/`"+"授权依据：冻结任务书 §8.2 五类接入循环 + round-8 `code-adaptation-prep-02-04.md` A 表第 1-2 级（config 落盘→封闭注册→离线链）"。边界（任务原文）："新增 JSON 不自动启用类型（D12 明文）；本轮注册为**离线链可用**，不授权 02/04 真实页面控件测试、不注册业务填写路径、不在真实 OA 创建 02/04 新页——真实控件测试待离线全绿后下一轮按结果另行授权"。

常设清单沿用（P1-a）：`bpm_plan_generate.py`/`bpm_ui.py` 最小改动+测试+留痕。

## 1. 02/04 接入首件（A 表 1-2 级；自主裁决①②③④）

- 类型注册：`office_supplies`（低值易耗品、办公用品采购，api_code 02）/ `welfare_labor`（福利费、劳保用品，api_code 04）——标签取 census submittype_map 实测渲染值（142146 travel_census.json），非中文名猜测。executable=True + execution_state=offline_modeled_live_pending（=离线链可用，同 express/rd 注册语义；真实页面测试本轮零动作）。
- config 按研究工件实测结构：02=details 全预算列+costs 七列（数量+日期区间）+多收款人 banks；04=details 全预算列（跨部门预算 evidence）+costs 空+单收款人 banks。detailrels 形态配置化记录：02 非零绑定（zero_fields=[]）、04 零金额（zero_fields=[bizDetailCost,bizDetailNum,usedCost]）；supported_relation_types 记录实测 [申请书(02, bizType34)]/[福利申请单(04, bizType74)] 仅作证据级声明。
- **自主裁决①（plan 级 relations 保持空）**：`bpm_plan.py:230` 非 travel 非空 relations 拒绝维持不动（该文件不在本轮授权清单）。02/04 离线链合成材料按空 relations+当次来源理由（round-8 express 模式）；实测关联形态在 config/notes 记录为接入缺口，plan 级非空 relations 建模留待后续轮次另行授权 bpm_plan.py。
- **自主裁决②（invoice=false 文档级通道=config 声明级）**：config 新增 `invoice_policy: {mode: document_level, required: false, evidence: <研究工件指针>}`（resolve_type/config 校验+单测覆盖）；plan 级强制校验（如拒绝行级 no_invoice_rows 并存）同样留待 bpm_plan.py 授权轮。
- 离线链：合成材料（明示 synthetic、不入业务 manifest、值取研究证据如 reimItem 02001/04003）→ 提取→FactSet→reconcile→复用矩阵→blueprint→generate_fill_plan→validate_plan 零 issues→`fill_once --validate-only` 子进程 exit 0（不开真实页面）。02 amount_rules={costs:sum, cost_amount_semantics:line_total}；04={costs:not_applicable, costs_reason:材料理由, cost_amount_semantics:line_total}（rd 模式）。模板块=研究 raw 快照只读复制派生（biz_number/captured_at/sha 绑定）。
- 每类 ≥3 单测（注册 resolve_type/校验负例/离线链路）；`automation/document-types/<type>.notes.md` 落与研究工件差异对照（含裁决①②缺口）。

## 2. D18 离线矩阵补行（≥4 新测试）

- PDF/图片变体（多页逐页锚点、一页多票拒绝/拆分策略）、Excel 变体（多 sheet、公式取值、汇总/明细并存、隐藏行/筛选态）、数值保真（前导零票号/账号、长账号、Decimal 0.005 级）在提取→事实→计划三段不丢。合成件明示测试用。每测试注释标注对应 D18 矩阵条目（任务 §3 三行）。落 tests/test_bpm_extraction.py（或同目录新测试文件）。

## 3. D22 新 session 使用验收方案（不实施）

- `automation/offline-verify/d22-acceptance-plan-<时间戳>/D22_plan.md`：验收范围/入口清单与参数/证据要求/判定标准/当前入口缺口（需改动处列点不实施）。供 A/用户审后下轮授权。

## 4. mc-expert 三观察处置（任务 §5）

- ①链 events 双前缀：**显式分段标记**方案落地——本轮新链 driver 起 events 追加 `chain_segment_start`（含段序号，由既有 events 行数推导），append-only 不回改；纪律写入 skill references/full-chain.md（红线段逐字不动）。历史 run 零改动。
- ②research events 键名消歧：定位 r8 研究事件流中含 authorization 字样的键名（仅键名无值），在 bpm_template.py 事件命名处最小改名（若属本轮可写面）或在 D22/notes 记录改名约定（若文件不在授权面）；不改历史 run 工件。
- ③no-residue 布尔命名消歧：命名约定（原始观察布尔 vs 归因终判布尔）记入 notes.md W07 与 D22 方案文档；历史 verdict 文件零改动。

## 5. 允许写 / 只读 / 禁止

- 允许写：`bpm_types.py`、`automation/document-types/`（新 config+notes）、`tests/`、`bpm_plan_generate.py`/`bpm_ui.py`（常设最小+测试+留痕，如需）、`.claude/skills/bpm-fill-run/references/`（链分段纪律措辞，红线段逐字不动）、`automation/runs/<新run>/`、`automation/offline-verify/<run>/`（含 D22 方案）、`automation/template-materials-program/`、`automation/type-extension/`（仅 events 记录）、`team-task.md`（仅本合同块）、`team-progress.md`、memory。
- 只读：历史 run 工件（含 round-8 全部 run）、`automation/task-registry/`、`legacy-ia2/`、`.pw-profile/`、`.local-session/`、census/type-view/研究 raw（只读复制进新 run）。
- **浏览器动作：本轮零动作**（无登录探查需求——无任何真实页面工作；任务 §保留项允许的例行身份核验本轮也不需要）。禁止：保存/发送/流转/提交/上传/暂存/贴票/审批；不动 `stage1_browser_probe.py`/`fill_once.py`/`bpm_plan.py`/`bpm_template.py`（除非§4②确认最小改名在授权面并先停-增补）；不自动 commit；合成材料不入业务 manifest、不虚构业务；凭证不入工件。

## 6. 验证（done_when 映射）

1. 02/04 config+封闭注册+离线链 validate-only 双 exit 0（零真实页面），每类 ≥3 单测。
2. D18 ≥4 新测试全绿并标注矩阵条目。
3. D22 方案工件落盘（含入口缺口清单，不实施）。
4. 三观察处置完毕留痕。
5. 全量测试全绿+唯一 run OFFLINE_PASS（source_manifest 冻结新文件）+skill 轮末快照。
6. 交接齐备：改动+哈希、新文件清单、台账 W07/W08、下一轮入口（02/04 真实控件测试授权申请 或 D22 实施）。

<!-- /team-task-contract -->
