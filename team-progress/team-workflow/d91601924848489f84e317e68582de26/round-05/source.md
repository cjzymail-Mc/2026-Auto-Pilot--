<!-- team-task-source id="src-e6a907d0" sha256="e6a907d067968926d1ea65c3765ef259a17d886e58efff6000f00fd224e896c5" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 5
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 5 —— 证据卫生修复轮（CASE-03 工件修缮 + 观察项闭环）

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 5，合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md`）。round 4 已交付并经 A 验收（D07/D08/D27 新增 PASS_DYNAMIC，共 17 项通过）：CASE-03 公出单模块逐票查证 `automation/runs/20261026-143340-v3r04-case03/`（27 票 12 MATCHED/15 NO_MATCH，Σ221.02+265.91=486.93==T，一票不漏）。A 验收证据见 `team-progress/team-workflow/d91601924848489f84e317e68582de26/round-04/acceptance/A-verification.md` 与 `hash-recheck.json`。本轮修复 A 验收发现的证据卫生项并闭环已登记观察项；**不进入 CASE-05/06/07/08**（模板身份缺口维持 PENDING_HUMAN_NONBLOCKING，等用户提供完整模板单号，不得为找单号普查历史）。CASE-07 的随机测试占位关联（oa_test_relations/test_placeholder）继续冻结，本轮零 OA 浏览器操作。

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环，计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. O1 修复：wide-query-manifest 哈希语义（A 验收 P2）
- 现状：`automation/runs/20261026-143340-v3r04-case03/wide-query-manifest.json` 各页 `sha256` 是捕获对象紧凑 `json.dumps` 的哈希，非落盘文件字节哈希（evidence writer 用 indent=1）；与 details3d/candidates3e/final-artifact-hashes 的文件字节口径不一致，程序化按字节校验会失配。A 已用逻辑哈希 5/5 复核内容完好、无篡改。
- 修复：对该 manifest 做**加法式**订正——每页增加 `sha256_file`（A/任何人可复算的文件字节 sha256）与顶层 `hash_semantics` 说明（保留原 `sha256` 字段并注明其为 logical-json 口径，不删除不改值，不回改任何原始 evidence 文件）。同步在 `final-artifact-hashes.json` 补登该 manifest 修订后哈希。
- 根因收口：排查 stage2b 消费的 capture 记录 `c["sha256"]` 来自共享探针库还是 run 内脚本。若在共享代码（如 stage1_browser_probe.py 或其引用的捕获工具），修正为"落盘后按文件字节计算"或双字段输出；**改 stage1_browser_probe.py 须先 `python -X utf8 stage1_probe_selftest.py` 全绿再动其他**。若仅 run 内脚本，在 `.claude/skills/bpm-fill-run/references/` 增补一条采集哈希口径规范防复发。

### 2. O2 修复：covers_day/traveler_rows 日期字段口径文档化（A 验收 P3）
- 现状：candidates3e-manifest 与 actual_trip_matches 排除块的 traveler_rows/covers_day 统一取 `factNatureStartDate/EndDate`（含途自然行程区间），未文档化；12025095297 实际公出时间（factStartTime/factEndTime）仅 09-18，自然区间 09-17..09-18，两口径分歧（A 重算 8/8 单一自然区间口径、结论不受影响）。
- 修复：在 candidates3e-manifest 顶层加 `date_field_semantics` 说明字段（加法式，不删不改旧值）；actual_trip_matches 的 `scope_note` 或新增说明块写明排除块行程区间=自然区间口径、matched 块 chen_trip=实际公出时间口径（两口径在 12 张 MATCHED 票上等价，A 已核）；修订后同步 final-artifact-hashes 与台账。

### 3. O3 修复：matched_doc 补显式 applicant（A 验收 P3，D08 字段完备）
- 对 `actual_trip_matches.json` 12 条 MATCHED 记录的 `matched_doc` 加法式补 `applicant: "陈晶"` 与 `applicant_user_id: "116070053"`（来源：attempt_011 详情 body 的 appliedName/appliedBy，A 已核对 5 单；补字段时逐单回读对应 api-detail JSON 取值，不从报告倒抄）。CASE-03-report.md 逐单表加"申请人"列或在表头注一行说明。修订后同步 final-artifact-hashes 与台账。

### 4. 观察项闭环（progress.json observations_next_round 已登记项）
- P2-1 active_run_profile 旧快照：按当前实际状态刷新该块（workflow_round=4 完成、round 5 进行、team_run/contract 现值）。
- P2-2 matched_doc.evidence.ui_text 裸文件名：统一为与 api_file/ui_screenshot 一致的 run 相对路径（修订 actual_trip_matches 时一并处理，加法/等价替换并台账说明）。
- schema 字节基线：为 `automation/fill-plan.schema.json` 建立可字节对比基线（构建前 .bak 快照入 offline-verify run 目录，或 git 提交一次现状作为基线——默认不 commit，优先 .bak 方案），并在台账登记基线位置。
- capability 子集 299≠308 与 P2-3 文本噪声、P2-2 test_bpm_round10_sync docstring、source.md sha256 属性名：逐项处置（修/登记不做的原因），台账留痕；**不做纯装饰性改动**。

### 5. 台账与交接
- `automation/template-materials-program/progress.json` 补 V3-R05：列明每项修复的 before/after 哈希；observations_next_round 更新（闭环项移除、保留项说明）；模板身份缺口维持 PENDING_HUMAN_NONBLOCKING 并写明"等待用户提供完整模板单号后进入 CASE-05"。
- 本轮改动规则：若第 1/4 条触及仓库源码/schema/测试（含 stage1_browser_probe.py、verify_bpm_build、skill references），执行全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify run；若仅 run 内工件加法订正与文档，零源码改动可沿用 V3-R03 构建并说明（合同第 5 条）。改 stage1_browser_probe.py 先 selftest 全绿。
- 新 run 目录 `automation/runs/<时间戳>-v3r05-hygiene/`：events.jsonl、修复脚本、修订前后哈希对照表；凭证原值不入任何工件；P6 收尾 + finish，handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- 零 OA 浏览器操作、零业务写入、零占位选择；不进入 CASE-05..08；不为模板做普查或猜测。
- 73 原件目录只读零漂移（第 5 轮复核）；历史文件不回改：wide-query-manifest/candidates3e/actual_trip_matches 只做加法式订正（新增字段/说明），不删除、不改写既有键值；attempt_010 作废文件原样保留。
- 默认不 commit；真实材料/凭证不入 Git；Python `-X utf8`、cwd 仓库根；改共享探针先 selftest。
- 修复不得引入新语义分歧：所有新增字段先在本轮 handoff 写清口径，A 将按文件字节复算验证。

## done_when
1. O1/O2/O3 三项修复完成：wide-query-manifest 每页有可复算 `sha256_file` + 语义说明（原 sha256 保留）；candidates3d/3e 口径说明字段就位；actual_trip_matches 12 条 matched_doc 有显式 applicant/applicant_user_id 且与 api-detail 原始值一致；final-artifact-hashes.json 同步修订后哈希。
2. 观察项按第 4 条逐项处置并台账留痕（active_run_profile 刷新、ui_text 路径统一、schema 字节基线建立、其余修/登记）。
3. 若有源码/schema/测试改动：selftest（如触及 probe）全绿 + 全量 unittest OK + 唯一新 offline-verify OFFLINE_PASS；否则零源码改动说明并沿用 V3-R03 构建。
4. 新 run 目录证据齐全（修复脚本/前后哈希/events）；台账 V3-R05 + observations 更新 + 模板缺口 PENDING_HUMAN_NONBLOCKING 状态明确；P6 + finish 交接哈希与实物一致；失败字典 {D23:1, D22:1} 原样带入。
<!-- /team-task-source -->
