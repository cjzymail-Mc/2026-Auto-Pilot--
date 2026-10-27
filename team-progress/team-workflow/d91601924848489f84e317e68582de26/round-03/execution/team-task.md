<!-- team-task-source id="src-39b87f83" sha256="39b87f837605d19fe9b36997ec434bff5dbc51bd28e1a7167e67cdff49939a5f" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 3
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 3 —— CASE-02 工作簿范围裁定与副本回填重算 + CASE-04 严格票据覆盖模型与有效反例

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 3，合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md` §4 为本轮规则原文）。round 2 已交付并经 A 验收：CASE-01 事实层 `automation/runs/20261026-115500-v3r02-case01/case01-facts.json`（52 唯一身份：27 张唯一通行费票价税合计观测和 T=486.93、5 张油票 O=2031.17、20 汇总单身份；每值有 page/bbox/sha256 锚点；期间链 2025-08-25→12-10）；Excel 原件 `feature01-细化报销skill/12月公出-发票/12月-自驾公出公里数统计表.xlsx`（`汇总` 单 sheet、行3 表头、行4-24 数据 21 行、Σ公里数=Σ补贴=1438 观测、G 列过路费全空、表头含"油车1元/公里、电车0.15元/公里"双档与备注孰低原则说明）。**范围裁定（哪些行/票纳入 K/T）尚未做，禁止预设 R/F/覆盖结论。**

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环（D23=V3-R00 唯一构建；D22=V3-R02 三态语义+5 测试），计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. CASE-02：范围裁定 → 同结构副本回填 → 可靠重算（V3 §4.3 全条）
- **范围裁定**：建立"Excel 行 ↔ 唯一通行费票据"的逐票映射——以票面 travel_date/起讫站与行日期/出发地-目的地对应，处理往返成对、同日多行、多票到同一行；每张纳入票据恰好指向行内一次分配；无法分配/重复分配/跨日歧义登记缺口，不平均摊分、不按文件序。用户公里规则=**1 元/公里（本案例冻结实测口径）**；表头"电车 0.15"档与备注孰低原则若与用户规则冲突，以用户规则为准并留冲突记录，不静默改行值。K=纳入行真实公里数合计、M=K×1.00。
- **回填副本**：在原件目录外制作保持原结构/公式/格式的回填副本（建议名 `12月-自驾公出公里数统计表-已核对.xlsx`，落本轮 run 目录）；G 列逐票回填确定的真实通行费金额（同行多票逐票列来源后求和）；区分"有证据的零通行费"与"未找到票据"（后者留空+登记，不填 0 掩盖）；保留用户公里数/历程/格式，不得按票据反改公里。
- **可靠重算**：核对 H 合计列实际公式语义（应为 补贴+过路费；若与规则不同保留原值并有据修正记录受影响单元格）；副本保存后**重新打开**读实际计算值，与独立 Decimal 逐行+总额复算一致；只读旧缓存值不算。R=待报销总额=M+T（T=纳入范围去重通行费合计）。
- **交付**：cell 级变更清单（sheet/cell、原值/公式、新值/公式、对应票据 identity、推导、哈希）；原件 73 件哈希对 round-2 manifest 零漂移。

### 2. CASE-04：严格票据覆盖分支 + 有效反例（V3 §4.1/§4.4 全条）
- **模型分离**：把本案例覆盖规则（R=M+T 按公里政策+真实通行费；F=O+T 覆盖凭据总额；允许填写条件 **F>R 严格大于**，coverage_margin=F-R）与现有"每张票面金额与费用行分配完全相等"通用规则**分开建模**，在事实层、配置/schema、计划验证、独立核验、报告五处一致表达：适用业务、规则来源（V3 §4.1 用户公里规则）、票据集合、公里及通行范围、R/F/差额、严格门槛。
- **不放宽通用约束**：不删通用票据校验、不伪造免票理由、不把 F 改成 R、不把油票金额硬凑到公里行；travel/express/rd_materials 既有金额路径回归保持全绿。
- **有效反例（离线测试）**：F>R / F=R / F<R、差 0.01 元边界——仅严格大于通过，等于/小于在写入前拒绝；覆盖富余→R 不增加、不按油票加报；用明确合成夹具测试（真实金额/人员不作代码默认值），不预设本案例"应当通过"。
- **本案例计算报告**：K、单价、M、T、R、O、F、coverage_margin 及各自原件/单元格来源（值来自 CASE-01/02 事实层推导）；若证据裁定后 F≤R，正确行为=准确报告不足并阻断 OA 写入（V3 §13.1），仍交付副本与模型，不补票/不改公里/不制造金额。
- 涉及 schema/config/计划验证代码改动按需最小化；新增测试纳入 manifest。

### 3. 台账与交接
- progress.json：work_packages CASE-02/04 状态、验证层次、unclosed_defects/missing_inputs 更新、rounds 补 V3-R03。
- 若本轮源码/schema 有改动：全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify run 冻结；未改源码可沿用并说明。
- P6 收尾 + finish；handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- fill_only；本轮零浏览器业务动作（无需登录例行核验可不跑）；OA 填写/公出单模块留后续轮。
- 原件目录只读（xlsx 与 73 件零漂移）；派生文件不入原件目录。
- 不接入其他类别、不做模板普查；模板身份缺口维持 PENDING_HUMAN_NONBLOCKING。
- 默认不 commit；真实材料/凭证不入 Git 与工件；Python `-X utf8`、cwd 仓库根。
- 观察项（非阻塞、有余力再做）：tests/test_bpm_round10_sync docstring 陈旧（P2-2）；round-1 source.md sha256 属性名误导（P2-3）。

## 验证
- 范围裁定链：每张纳入票据有行定位与依据；未纳入/歧义票有登记理由；K/M/T 有来源。
- 副本：A 可独立重开复算逐行+总额=独立 Decimal；变更清单与实际 diff 一致；原件零漂移。
- 覆盖模型：五处一致；反例测试全绿；通用回归全绿；F/R/coverage_margin 报告值可从事实层复推。
- 台账/交接哈希一致；失败字典承接。

## done_when
1. CASE-02 完成：范围裁定依据链 + 同结构回填副本（G 列逐票、零值区分、公里保留）+ 重新打开验证的可靠重算 + 独立 Decimal 复算一致 + cell 变更清单 + 原件 73 件零漂移；歧义/缺口如实登记。
2. CASE-04 完成：覆盖分支五处一致分离落地；F>R/F=R/F<R/0.01 边界反例与覆盖富余反例测试全绿；通用约束回归全绿；K/单价/M/T/R/O/F/coverage_margin 带来源报告（或 F≤R 时正确阻断报告）。
3. 台账更新至 V3-R03；P6 + finish 交接哈希与实物一致；历史失败字典原样带入。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261026-125832-39b87f83" contract_id="ctr-14bb5408" source_block_id="src-39b87f83" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-26 · run 20261026-125832-39b87f83）

**终态**：round 3 以实物证据完成 CASE-02（范围裁定依据链 + 原件目录外同结构副本 H 列逐票回填 + 保存后重开实测的重算核验 + 独立 Decimal 复算一致 + cell 级变更清单 + 原件零漂移）与 CASE-04（fuel_pool_strict_surplus 覆盖模型五处一致分离 + F>R/F=R/F<R/0.01 边界与覆盖富余反例测试全绿 + 通用约束回归全绿 + 本案例 K/单价/M/T/R/O/F/coverage_margin 带来源报告），台账 V3-R03 纠偏，独立复核通过后 finish 交接 A；零浏览器业务动作；不宣称 V3 整体完成。

**本轮做**：team-task.md 待做条款 1-3 全部——CASE-02 范围裁定（Excel 行↔唯一通行费票据逐票映射：以票面 travel_date+起讫站方向 对 行日期+出发地→目的地方向；往返成对/同日多行/多票到同一行显式处理；每张纳入票恰指向行内一次分配；歧义登记不摊分；用户公里规则 1 元/公里为准，表头电车 0.15 档与孰低原则作冲突记录不改值）→副本回填（COM 复制原件到 run 目录，H 过路费列逐票金额、行内 I 合计补 =G+H 公式、I24 总计沿用 SUM；区分有证据零通行费与未找到票据；公里数/格式原样保留）→可靠重算（副本保存后新开 Excel 进程读实际计算值 vs 独立 Decimal 逐行+总额）→变更清单（cell/原值/新值/票据 identity/推导/哈希）+73+1 件哈希对账；CASE-04 覆盖模型（新模块 bpm_coverage.py：K/M/T/R=M+T、O/F=O+T、coverage_margin=F-R、严格门槛 F>R；事实层 FACT_KINDS 受控加 coverage_evaluation 一行、fill-plan.schema.json 可选 coverage_policy 块、validate_plan 可选 coverage 键+严格门校验、独立核验函数、run 目录双报告；油票仅覆盖池不加报、富余不改 R）+合成夹具反例测试（明确合成金额/人员，真实值不作代码默认；仅 F>R 通过，F=R/F<R/±0.01 边界拒绝）+travel/express/rd_materials 既有回归全绿+全量 unittest+唯一新 offline-verify 构建（源码有改，materials-v3r03-<时间戳>）；progress.json V3-R03+P6+finish。

**明确不做**：OA 业务行写入/保存/提交/上传/贴票/关联选择；公出单模块查询（CASE-03 留后）；Excel 原件任何写回（副本仅在 run 目录）；修改冻结 V3/round-1、2 已冻结产物（R00-report、frozen-artifact-hashes rev2、round-01/02 归档、round-2 handoff）；三类历史回放重跑；其他类别扩展与模板普查；git commit/push；代扫码；预设覆盖结论（F≤R 时如实阻断报告，不补票/不改公里/不制造金额）；改 A 的验收文件。

**允许写**：`bpm_coverage.py`（新）；`bpm_facts.py`（仅 FACT_KINDS 增 coverage_evaluation 一行，其余不动）；`bpm_plan.py`（仅可选 coverage 键解析+严格门校验，不改既有校验）；`automation/fill-plan.schema.json`（仅可选 coverage_policy 块）；`tests/test_bpm_coverage.py`（新）；`automation/runs/<新run>-v3r03-case02/`（裁定/回填/重算/变更清单/覆盖报告脚本与产物，含副本 xlsx）；`automation/offline-verify/materials-v3r03-<时间戳>/`（唯一构建）；`automation/template-materials-program/progress.json` 与 `notes.md`；根 `team-progress.md`、根 `team-task.md`（仅追加本合同块）、根 `handoff-input.json`（finish 用）。

**只读**：`feature01-细化报销skill/12月公出-发票/` 全目录（74 件含 xlsx，前后各一次全量哈希对账）；`automation/runs/20261026-115500-v3r02-case01/`（facts 上游）及既有 run；`automation/task-registry/`；`.team-workflow-state.json`（仅 helper 写）。

**禁止**：删除/回退他人未提交工作；git add -f/commit/push；凭证/会话元数据入任何工件；改写 reconcile() 通用票据闭合语义或删除通用校验；把油票金额分配进公里行或按油票加报；用真实案例金额作测试夹具默认值；对冻结产物的任何改写（勘误走台账新记录）。

**红线**：team-task 四红线（销毁性/不可逆；对外交付合规；同 failure_key 第 3 次熔断；推翻 KB 已封决策）；根 AGENTS.md 五条红线；本轮零浏览器动作（无需登录例行核验可不跑）；重型任务（COM 回填/全量测试/offline-verify 构建）串行错峰。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE；一手证据=helper runtime_evidence（B=session c05e555a-0c54-4418-96a2-d92a751dfbc9，model glm-5.3，round-3 enter/permit seq14 一致）。

**裁量推荐（B+AUTO 接管，逐条记入 team-progress 自主裁决区）**：任务文"G 列回填过路费"与实物不符（G=补贴金额、H=过路费（据实）、I=合计），按语义回填 H 并在变更清单/台账登记字母口径差，不机械执行 G；行内 I 列原件无公式（仅 I24=SUM），补行内 =G+H 公式属"据实合计"设计列的补全并在变更清单记录（非改既有公式）；0917 返程票面终点同安站 vs 行目的地厦门总部，按日期+方向映射成立、差异登记不阻断；0906 组文件夹名与票面日期差一日以票面为准（round-2 已登记）；油票不入行分配，仅覆盖池；COM 写副本前后各做原件哈希对账。

**done_when 与验证**：D1-D3 逐条对应 team-task.md done_when 1-3 原文。D1=裁定 JSON（每票行定位+依据+歧义登记）+副本（H 逐票/I 公式/I24 沿用）+重开实测值=独立 Decimal 复算（逐行+总额 R=M+T）+变更清单与实际 diff 一致+74 件零漂移；D2=模型五处一致（bpm_coverage/bpm_facts FACT_KINDS/schema coverage_policy/validate_plan 严格门/独立核验+run 双报告）+反例与边界测试全绿+通用回归全绿+全量 unittest+唯一构建 OFFLINE_PASS+K/单价/M/T/R/O/F/margin 带来源报告（或 F≤R 阻断报告）；D3=progress.json V3-R03+P6+finish 哈希绑定实物+失败字典 {D23:1,D22:1} 原样带入。验收按 team-task 四态签注；STATIC_ONLY 不冒充完成。
<!-- /team-task-contract -->
