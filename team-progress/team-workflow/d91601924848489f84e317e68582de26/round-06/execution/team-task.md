<!-- team-task-source id="src-db223254" sha256="db2232545dcdc4f1f0d2f6b668c8d1a6da2a47e58d0ee61e33acc2215ef48cd7" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 6
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 6 —— CASE-05 模板定向读取 + CASE-06 可执行计划生成（validate-only 止）

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 6，合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md` §6 为本轮规则原文）。已交付并经 A 验收：CASE-01 facts（`automation/runs/20261026-115500-v3r02-case01/case01-facts.json`，52 唯一身份）、CASE-02 映射+回填副本+覆盖实算（`automation/runs/20261026-131000-v3r03-case02/`，K=1438/M=1438.00/T=486.93/R=1924.93/O=2031.17/F=2518.10/margin=593.17，F>R 通过）、CASE-03 逐票对照（`automation/runs/20261026-143340-v3r04-case03/actual_trip_matches.json`，12 MATCHED/15 NO_MATCH，已含显式 applicant 与日期口径说明）、round-5 证据卫生修复（哈希口径/日期语义/申请人列）。

**用户输入（本轮新解锁，来源=用户 2026-10-26 在 A 窗口原话）："模板单号是 15426095951，也就是【陈晶】最近的一张报销单，继续"。** 模板身份缺口 PENDING_HUMAN_NONBLOCKING 自此解除；台账须把该缺口登记为 CLOSED 并引用上述来源（单号+用户原话+日期），不得写成本工作流 agent 自行发现。

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环，计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. 登录与身份前置（只读）
- 先 `python -X utf8 bpm_login.py` 只读探查：profile 锁、会话元数据（refresh token 边界 2026-11-23，以当次探查为准）、当前登录人员与有效性。需要新扫码按 `WAIT_HUMAN_LOGIN` 停等账号持有人，agent 不代扫。探查记录仅入 `automation/.local-session/`（不入工件、不入 Git）。
- 记录身份链三员：登录操作人（当次探查）、模板单制单人/申请人（从模板快照实际读取，不预设三者相同）。若当前登录人非陈晶或与模板/案例归属冲突，如实记录并按 AGENTS 身份规则阻断相关写入，不把费用挂错人，不硬编 --expect-name。

### 2. CASE-05 模板定向读取（V3 §6）
- 由唯一浏览器执行者执行 `python -X utf8 bpm_template.py --live --expect-name "<本次探查姓名>" --template-number "15426095951" --output "automation/runs/<本轮run>/template_snapshot.json"`：同 profile 锁、临时 context、`--no-proxy-server` 直连，不导航/关闭其他执行者页面，不做模板普查。
- 快照与哈希落 run 目录；核实并记录：完整单号 15426095951、唯一 UUID、单据类别（须为报销单且与 travel 类型兼容——不兼容则如实报告结构差异并停在该步，不硬套）、主表全部字段、relations/details/costs/banks 四表实际结构与列语义、页面"物品档案"类额外表是否存在（travel 应无 products）。未知字段 null 并注明原因；"选择器未出现"不得推断为业务状态。
- 模板读取属只读观察：不点保存/提交/流转，不动旧单。

### 3. 字段复用矩阵（V3 §6）
- 对模板快照逐字段形成 采用/替换/不适用 决策及依据：仅稳定身份、预算、收款资料可在有证据时复用（记录来源单元格/响应与哈希）；**本次日期、费用明细、发票、金额、关联编号一律来自本次原件（facts/mapping/coverage），不得从旧单推导或抄写**。矩阵落 run 目录（机器可读+可读双版本）。

### 4. CASE-06 可执行计划生成与完整验证（V3 §6、§7 前置）
- 依 `automation/task.schema.json`/`fill-plan.schema.json` 生成 v1.0 fill-plan：类型 travel；行数据来自 case02-mapping 20 行（公里补贴+逐票通行费）；金额 Decimal——totalCost、报销明细合计、银行收款合计与 R=1924.93 闭合；coverage 块（model=fuel_pool_strict_surplus，K/M/T/R/O/F/margin 全量+来源）按 round-3 已建模 schema 落入；每个执行值有 path/locator/sha256 来源。
- 关联表（relations）与随机测试占位：**本轮不开 OA 新页、不选取任何关联单据**。计划中对关联行的处理须显式建模且与 actual_trip_matches 严格分离：或按 schema 留空+登记 table_applicability 理由（占位选择留 CASE-07 实测），或建立 test_placeholder 标记的待观测占位结构——两种都不得编造单号/UUID/selected 对象，不得混入真实逐票对照表。
- 验证：`python -X utf8 fill_once.py --fill-plan "<计划>" --expect-name "<本次探查>" --validate-only` 通过（或如实报告具体阻断：文件/页/cell/单据及影响）；`--task` 路径如使用则仅做材料准备并返回 NEEDS_INPUT 语义，不直接进入填写。
- 计划哈希、配置哈希、模板快照哈希、facts/mapping/coverage 哈希写入执行绑定；新旧计划不一致时按新任务新 run 规则处理。

### 5. 证据、台账与交接
- 新 run 目录 `automation/runs/<时间戳>-v3r06-template-plan/`：events.jsonl 追加式、模板快照+哈希、复用矩阵、fill-plan、validate 结果；凭证原值不入任何工件；登录探查记录仅 .local-session。
- `automation/template-materials-program/progress.json` 补 V3-R06：**模板缺口 CLOSED（用户 2026-10-26 提供 15426095951，引用原话）**；层次标注区分"代码已实现/离线已验证/真实控件已验证"——本轮模板读取=真实控件已验证（只读），计划 validate-only=离线已验证，不冒充填写已验证。
- 源码/schema 有改动时全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify；未改则沿用 V3-R05 构建并说明。改 `stage1_browser_probe.py` 须先 selftest 全绿（预计不改）。
- P6 收尾 + finish；handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- fill_only：本轮零业务写入、不开新页填写、不选关联、不测保存（OA 填写与占位关联是 CASE-07）。
- 73 原件目录只读零漂移（第 6 轮复核）；模板旧单只读，不修改不重新占用；不接入其他类别；不做模板普查。
- 默认不 commit；真实材料/凭证不入 Git；Python `-X utf8`、cwd 仓库根、不走 VPN/Clash、Chromium `--no-proxy-server`。
- 保留观察项 3 条（active_run_profile 终态刷新时机、detail3d 文本噪声、source.md 属性名）不阻塞；有余力按台账处置。

## done_when
1. 模板 15426095951 快照+哈希落盘：单号/UUID/类别/主表/四表结构完整记录，travel 兼容性有结论（兼容→继续；不兼容→如实差异报告且后续条款以阻断记录交付）；登录操作人/制单人/申请人三员身份链在案。
2. 字段复用矩阵双版本交付：逐字段决策+来源；本次日期/费用/发票/金额/关联编号零旧单推导。
3. fill-plan v1.0 生成并通过 validate-only（或具体阻断报告）：金额三向闭合 R=1924.93、coverage 块全量、值来源齐备、占位语义与真实对照严格分离且零编造。
4. 台账 V3-R06 + 模板缺口 CLOSED（含用户原话来源）；新 run 证据齐全；P6 + finish 交接哈希一致；失败字典 {D23:1, D22:1} 原样带入。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261026-171850-db223254" contract_id="ctr-cfe67f13" source_block_id="src-db223254" status="frozen" profile="minimal" -->
## 基线
- 需求源：team-task.md src-db223254（workflow round 6，A publish 派发）；规则原文=冻结V3 §6。
- 模板单号 15426095951=用户 2026-10-26 在 A 窗口提供（原话入任务文）；模板缺口解除来源=用户输入，台账按 CLOSED+引用原话登记，不写成本工作流 agent 自行发现。
- 上游已验收：facts（8d5581dec67c5a9c…）/mapping（a899944ea27c16fb…）/actual_trip_matches（round-5 订正后终态）/coverage 模型（R=1924.93/O=2031.17/F=2518.10/margin=593.17）。

## 冻结范围（本轮唯一交付：CASE-05 模板定向读取 + CASE-06 计划生成 validate-only 止）
1. 登录前置（只读）：bpm_login.py 探查，身份链三员（登录操作人/模板制单人/申请人——后两者从模板快照实读，不预设相同）；失效按 WAIT_HUMAN_LOGIN 停等；记录仅 .local-session。
2. CASE-05：bpm_template.py --live --template-number 15426095951 --expect-name 本次探查姓名 → template_snapshot.json+哈希；核实单号/UUID/类别（须报销单且 travel 兼容；不兼容则如实差异报告并停在后续填写条款）；主表全字段+relations/details/costs/banks 四表结构；travel 应无 products；未知 null 注原因；零保存/零流转/不动旧单。
3. 字段复用矩阵：逐字段 采用/替换/不适用+依据；仅稳定身份/预算/收款可证据复用；日期/费用/发票/金额/关联编号一律本次原件，零旧单推导；双版本落 run 目录。
4. CASE-06：fill-plan v1.0（travel；20 行来自 case02-mapping；Decimal 三向闭合 R=1924.93；coverage 块全量+来源；值有 path/locator/sha256）；relations 本轮零 OA 开页零选择——schema 留空+table_applicability 理由或 test_placeholder 待观测结构，零编造单号/UUID/selected，与 actual_trip_matches 严格分离；fill_once.py --validate-only 通过或如实阻断报告；计划/配置/模板/facts/mapping/coverage 哈希入执行绑定。
5. 台账交接：progress.json V3-R06+模板缺口 CLOSED（用户原话来源）；层次标注（模板读取=真实控件已验证只读/validate-only=离线已验证，不冒充填写）；零源码改动则沿用 V3-R05 构建并说明；新 run 目录 automation/runs/<时间戳>-v3r06-template-plan/（events 追加式/快照/矩阵/计划/validate 结果）；73 原件第 6 轮零漂移复核；P6+finish 哈希绑定实物。

## 红线（不变）
fill_only：零业务写入、不开新页填写、不选关联、不测保存（OA 填写与占位=CASE-07）；模板旧单只读不修改不重占；不做模板普查；凭证原值不入工件/Git；.pw-profile 不复制；默认不 commit；Python -X utf8；Chromium --no-proxy-server 直连；不导航/关闭其他执行者未保存页；失败字典 {D23:1, D22:1} 原样带入。

## 验收（done_when）
1. 模板 15426095951 快照+哈希落盘：单号/UUID/类别/主表/四表结构完整+travel 兼容结论（或如实差异阻断记录）；三员身份链在案。
2. 复用矩阵双版本：逐字段决策+来源；本次业务要素零旧单推导。
3. fill-plan v1.0 validate-only 通过（或具体阻断报告）：三向闭合 R=1924.93/coverage 全量/来源齐备/占位与真实对照严格分离零编造。
4. 台账 V3-R06+缺口 CLOSED（用户原话）；新 run 证据齐全；P6+finish 哈希一致；失败字典原样。
<!-- /team-task-contract -->
