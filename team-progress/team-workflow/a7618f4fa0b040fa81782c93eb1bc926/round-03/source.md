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
