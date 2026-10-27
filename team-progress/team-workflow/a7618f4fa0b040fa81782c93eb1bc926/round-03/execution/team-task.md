<!-- team-task-source id="src-e0a60bed" sha256="e0a60bedd2ada3a378c6188530f6edf5b76013ddc1299d4e063d520e584f9fc3" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 3
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 3 -->
# 本次任务：报销材料主线 W04 —— 本次业务事实层与对账（+R2-P5 构建源清单修复）

总目标背景（自足）：多轮交付"用户仅给模板单号+原始资料，agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。已交付：W00 总台账（`automation/template-materials-program/progress.json` 唯一权威）；W02 双根契约（`bpm_materials.py` manifest v2.0：`prepare_dual_materials`/`register_derived`/`validate_dual_manifest`，来源 kind=material/user/agent_reviewed，agent 推断禁伪装 user）；W03 原件理解（`bpm_extraction.py`：`run_pdf_extraction` 文本 PDF 两层分离、`ocr_pass`/`review_pass` 图片链路、xlsx/csv 语义解析、`SEMANTIC_CATEGORIES` 语义盘点、`GapLog` GAP_FIELDS 结构化缺口；测试 13/13、全量 146/146）。本轮做 W04：把 W03 的提取事实组织成版本化业务事实层，并建立先于任何业务写入的对账。全部离线，不连 OA、不做浏览器操作。

验收口径继承：只填不存；守卫/SaveController/registry 原样；不虚构实单；合成材料仅机制测试；缺真实材料登记缺口不停工。

## 待做条款

### 0. R2-P5（必做，先做）：构建源清单修复
- `verify_bpm_build.py` 的 source manifest（上轮 44 键）未纳入 `bpm_extraction.py`（grep 命中仅为测试文件路径）。修复清单机制：根目录业务模块（现有及本轮新增）自动或显式全部纳入冻结，杜绝"主交付模块不在 OFFLINE_PASS 绑定内"。
- 修复后先跑一次唯一 run 验证 `source_manifest.json` 确含 `bpm_extraction.py` 哈希，再做 W04（避免本轮新模块再次漏冻）。

### 1. W04a 版本化业务事实层（模块名自定，如 `bpm_facts.py`）
- 至少表达：本次业务身份/范围、费用事实、票据事实、预算/收款候选、必要关联/档案、适用性理由、来源定位、推导、未决问题。
- 来源封闭枚举并如实标注：原件（提取/复核工件）、准确模板、用户明确指令、当前系统观察、确定性计算；agent 推断一律非 user（沿用 agent_reviewed 语义），不把推断改写成"用户已确认"。
- 每条事实有稳定 ID；发票分配/费用行引用事实 ID 而非复制值。
- 版本化：记录所基于的 manifest/派生工件哈希；材料换版本后能识别受影响事实（哈希比对）并标记需重新规划，不修改既有事实来掩盖来源漂移。

### 2. W04b 对账（先于业务写入，程序化）
- 去重分层：同一发票不同扫描件、同一文件多张票、重复费用统计、汇总与明细重复计入；R2-P6：duplicate_copy 按"组"语义处理（组内副本去重，不逐文件误报）。
- 票据闭合：每张票面金额与其分配金额闭合（Decimal）；每个主要费用行有完整发票分配或有本次来源支持的免票依据（理由+来源）。
- 跨来源一致：Excel vs 发票、结算明细 vs 合计、费用说明 vs 报销范围；冲突阻断并准确定位（文件/页/单元格），不得任选一份当真。
- 分层金额闭合：报销总额、明细合计、收款合计、各类适用费用说明/档案金额分别闭合；不同层不得相加重复计费。
- 收款身份：收款人名称/账号/支行/联行号作为完整身份组核对，字段残缺或来源冲突阻断。
- 边界拒绝：未经建模的借款抵扣、部分票面报销、数量乘单价、未知业务表不得进入后续保存路径（明确报错，不改名绕过）。
- 同金额≠禁报；同一发票跨任务重复使用时提示已有意图/历史证据（与 task-registry 只读核实衔接，不换 task_id 绕过）。

## 保留项与边界
- 原件只读；合成 fixtures 放 tests/；不动 `automation/runs/` 旧工件、task-registry、legacy-ia2；不自动 commit；守卫与 `stage1_browser_probe.py` 预期不改（若触碰先 selftest 全绿）。
- 旧 manifest v1.0/v2.0 读取与漂移拒绝语义不降级；正在填写/保存中的任务不自动迁移。
- 新依赖仅在必要且在交接清单列明用途与版本。

## 验证（全部离线）
- 新增单测（合成 fixtures：文本 PDF+多 sheet xlsx+CSV+重复副本组合）覆盖上列每一项，含反例：票面≠分配、Excel 与票面冲突、未覆盖费用行、免票无理由、收款字段残缺、同票双扫描、组内副本、未知表、借款抵扣拒绝、同发票跨任务提示、版本漂移识别。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 146 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS，且 `source_manifest.json` 冻结本轮全部根模块（含 `bpm_extraction.py` 与新事实/对账模块）。

## done_when
1. R2-P5 闭合：新构建 source_manifest 含 `bpm_extraction.py` 及本轮新模块哈希（可复查）。
2. 事实层落地：五类来源如实标注、稳定 ID 被分配引用、版本漂移识别，均有通过单测。
3. 对账落地：去重/闭合/跨源冲突阻断/免票依据/收款身份/边界拒绝/跨任务发票提示全部有单测（含反例）。
4. R2-P6 组级去重语义有单测。
5. 全量 unittest 全绿；唯一 run OFFLINE_PASS。
6. 交接齐备：改动文件+sha256、测试结果、progress.json 的 W04 状态与证据更新、下一轮入口建议（W05 计划生成与衔接）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-114148-e0a60bed" contract_id="ctr-1eecdddb" source_block_id="src-e0a60bed" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24，round 3）

**终态**：R2-P5 闭合——统一构建 source_manifest 自动冻结全部根业务模块（含 bpm_extraction.py 与本轮新模块）；W04 落地——版本化业务事实层（稳定 ID、五类来源如实标注、agent 推断禁标 user、版本漂移识别标记需重规划）+ 程序化对账（组级去重/票据闭合/跨源冲突阻断/免票依据/分层金额闭合/收款身份组/边界拒绝/跨任务发票提示），全部有合成单测含反例；全量 discover 零回归；唯一 run OFFLINE_PASS 且源清单可复查；progress.json W04 状态与证据更新；交接含 W05 入口。

**本轮做**：
1. R2-P5（先做）：verify_bpm_build.py 源清单机制修复——显式 CODE ∪ 根目录 `bpm_*.py` glob ∪ fill_once.py，自动纳入杜绝主交付模块漏冻；修复后先跑唯一 run 验证 source_manifest.json 确含 bpm_extraction.py，再做 W04。
2. W04a 事实层（新模块 `bpm_facts.py`）：本次业务身份/范围、费用事实、票据事实、预算/收款候选、关联/档案、适用性理由、来源定位、推导、未决问题；来源封闭枚举 {material_extraction, template, user_instruction, system_observation, deterministic_computation} 如实标注（agent 推断禁标 user_instruction）；每条事实稳定 ID，发票分配/费用行引用 ID 不复制值；版本化记录所基 manifest/派生工件哈希，材料换版本按哈希比对识别受影响事实并标记需重新规划（不改写既有事实掩盖漂移）。
3. W04b 对账（程序化、先于任何业务写入）：组级去重（同票多扫/一文件多票/重复统计/汇总 vs 明细重复计入；R2-P6 组语义）；票面与分配 Decimal 闭合；每主要费用行完整分配或有来源免票依据；跨源一致（Excel vs 票面、结算明细 vs 合计、说明 vs 范围）冲突阻断并定位到文件/页/单元格；分层金额闭合（总额/明细/收款/适用说明/档案各自闭合，跨层不相加）；收款身份组（名称/账号/支行/联行号）残缺或冲突阻断；边界拒绝（借款抵扣/部分票面/数量乘单价/未知表→明确报错不改名绕过）；同金额不禁报；同发票跨任务只读扫描 task-registry *.form.json（numbers 数组/文本）出提示。
4. 验证全离线：新增单测（合成 fixtures：文本 PDF+多 sheet xlsx+CSV+重复副本组合）覆盖任务书反例清单逐项；全量 discover 全绿（146 基线零回归）；唯一 run OFFLINE_PASS 且 source_manifest 冻结本轮全部根模块。

**本轮不做**：不连 OA、不做浏览器操作；不接入新报销类别；不改 stage1_browser_probe.py/bpm_save.py/守卫/bpm_extraction.py/bpm_materials.py（消费其产物不改其语义）；不动 automation/runs/ 旧工件、task-registry（只读扫描）、legacy-ia2；不自动 commit、不上传材料；不做 W05 计划生成（仅留入口）；不虚构实单。

**允许写**：`verify_bpm_build.py`（仅 R2-P5 源清单机制）、新模块 `bpm_facts.py`、`tests/`（新增测试与 fixtures）、`automation/template-materials-program/`（台账更新）、`team-progress.md`、`team-task.md`（仅本合同追加）。
**只读**：`fill_once.py`、`bpm_types.py`、`bpm_plan.py`、`bpm_ui.py`、`bpm_verify.py`、`bpm_save.py`、`bpm_extraction.py`、`bpm_materials.py`、`bpm_template.py`、`stage1_browser_probe.py`、`automation/runs/`、`automation/task-registry/`、`automation/offline-verify/` 既有产物、`.pw-profile/`、`legacy-ia2/`。
**禁止**：删除或重写旧 run/registry/证据；写 task-registry；放宽通用守卫或保存保护；agent 推断写 user_instruction/kind=user 或「用户已确认」；同金额静默禁报或静默去重业务费用；跨层金额相加重复计费；为绕过对账阻断改名/改表；虚构实单或保存验收。

**红线**：继承根 AGENTS.md 全部红线（只填不存；.pw-profile/ 活体 token 绝不入 git/日志/报告；legacy-ia2/ 只读；registry 只读核实不删不换 task_id；单 profile 单执行者；不走 VPN/代理；Python 一律 -X utf8）。team-task 四红线：①销毁性/不可逆操作；②对外交付物；③同一 failure_key 三次失败熔断（已载入 review|content|source_manifest_coverage|D23=1，本轮修复对因处置，不新增同 key 失败）；④推翻已封决策。B 模式权限类命令后置人工门。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM；risk_class=MEDIUM；risk_owner=USER；risk_source=USER_STANDING_POLICY_20260904；runtime_policy=GLM_ALLOWED；risk_escalation=NONE（常设策略；runtime 一手证据已记 progress 头）。

**裁量项（contract-only：写推荐+依据，P6 执行期按 B 默认落实并记自主裁决）**：
- 模块落点：事实层与对账同落 `bpm_facts.py`（推荐依据：事实与对账同一聚合根——对账即事实间一致性校验，拆两模块徒增接口面；消费 W03 产物只 import 不改）。
- 源清单规则：显式 CODE 保留 ∪ 根目录 `bpm_*.py` glob ∪ `fill_once.py`（推荐依据：业务模块命名约定已统一 bpm_ 前缀，glob 自动覆盖未来新模块；研究探针 list_type_query/travel_census/_gen_manifest/_schema_v02 非主交付不纳入）。
- registry 提示实现：只读解析 `automation/task-registry/*.form.json`，发票号命中 `authorized_revision*.numbers` 数组或全文文本 → 提示项（task_id+文件名+证据），目录缺失/不可读降级为无提示不阻断。
- fixtures：复用 tests/fixtures/w03 生成器 + 新增 w04 组合场景（双扫描同票=同内容 PDF 复制两份、组内副本对、含借款抵扣字段反例 xlsx）。

**done_when（字面可判；全部离线验证）**：
- D1: R2-P5 闭合：新唯一 run 的 source_manifest.json 含 `bpm_extraction.py` 与本轮新模块 `bpm_facts.py` 的真实哈希。（验证：读构建产物 source_manifest.json 键与哈希抽查）
- D2: 事实层三要素均有通过单测：五类来源如实标注（agent 推断≠user_instruction 反例）；分配引用稳定事实 ID 而非复制值；版本漂移识别（改派生工件哈希→受影响事实被标记需重新规划、既有事实不被改写）。
- D3: 对账逐项有单测且反例清单逐条命中阻断：票面≠分配、Excel 与票面冲突、未覆盖费用行、免票无理由、收款字段残缺、同票双扫描（去重后单计）、未知表、借款抵扣拒绝、同发票跨任务提示；分层金额闭合与跨层重复计费拒绝。
- D4: R2-P6 组级去重语义有单测：duplicate_copy 组内副本按组去重不逐文件误报，组消费一份。
- D5: `python -X utf8 -m unittest discover -s tests` 全绿（146 基线零回归）；`python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 唯一新 run OFFLINE_PASS。
- D6: 交接齐备：改动文件清单+sha256、测试结果、progress.json 的 W04 状态与证据更新、下一轮入口建议（W05 计划生成与衔接）写明于 team-progress.md 收尾段及台账。
<!-- /team-task-contract -->
