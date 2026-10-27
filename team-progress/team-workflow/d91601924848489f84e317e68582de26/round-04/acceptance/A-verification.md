# Round-04 A 独立验收（CASE-03 公出单模块逐票查证）

- A session：`0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`｜run `d91601924848489f84e317e68582de26`｜round 4｜B 交接 2026-10-26 15:41:03
- 验收脚本：`C:/Users/xy198/AppData/Local/Temp/a_r04_verify.py`（A 独立编写，只读仓库，不写业务产物）；机器结果见本目录 `hash-recheck.json`
- 基线复核：冻结 V3 sha256 `d437988d…5c977ef0d` 逐字匹配（连续第 4 轮）

## 一、独立复算结果（全部 A 亲算，非引用 B 报告）

1. **交接哈希**：handoff 14 项 artifacts（含 evidence_hashes）逐项 sha256 全中；`final-artifact-hashes.json` 内部 6 键亦逐一绑定实际文件字节。
2. **原件零漂移（连续第 4 轮）**：`12月公出-发票` 73 件 vs R00 manifest 73/73 sha256 全等，无新增/漂移；派生文件未入原件目录。
3. **27 票集合恒等**：`actual_trip_matches.json` 27 条 identity 集合 == CASE-01 facts 27 张去重通行费（逐票 amount、源文件 sha256 与 facts 全等）；excel_row 逐票 == case02-mapping 分配（每票恰一次，distinct 行 4..23 共 20）。
4. **Decimal 三向**：A 重算 Σ(MATCHED)=221.02、Σ(NO_MATCH)=265.91、Σ(总)=486.93 == T（case02-coverage）；逐日金额/票数与文件内嵌 completeness_checks 全等；summary/per_doc 块与 A 重算全等；per-doc 2/4/2/2/2=12、行 22-23｜18,18,19,19｜12-13｜10-11｜6-7 与 mapping 全等。
5. **MATCHED 同日证据下钻**：5 张对应单全部位于 chen-docs 13 单（uuid/appliedAt/reimed/bizReason/place 字段全等）；api-detail 文件 sha256 == manifest == matched_doc.evidence；**A 直接解析 5 份详情 JSON，逐票找到 appliedName=陈晶 且 factStartTime/factEndTime（实际公出时间，非仅自然区间）当日覆盖通行日**；每个 matched 日的覆盖单唯一（09-05→12025092237 等 5/5 UNIQUE-CONSISTENT），无双射强造。
6. **NO_MATCH 反证下钻**：本人 13 单详情逐行扫描，**零条陈晶行覆盖任一缺口日**；8 张同事候选原始 JSON 逐行重算——bizNumber/sha200 全对、行级 appliedName 均不含陈晶（A 重算 chen_in_rows=false 8/8）、covers 与 B 声明一致（B 统一用 factNature* 自然行程区间，见观察 O2）。
7. **宽窗完整性**：5 页原始 JSON——请求路径/页码、CreatedAt/AppliedAt 宽窗、CreatedPath="/" 过滤逐页核实；96 行 96 唯一单号；列表申请人=陈晶恰 13 行 == chen-docs 13 单集合恒等；缺口日 [D,D+6] 候选 A 从 96 单原始数据独立重算，B 采集的 8 单 = 窗内全部非本人单（5 日全 COMPLETE，无静默收窄）。
8. **attempt_010 作废属实**：events 12 条 `v3c_api_fallback` 全部命中 `/WorkOut/3f260a65…`（12025073893 的 uuid），与 36 位正则 vs 32 位无杠实形缺陷陈述一致；原 26 份 api-fallback 文件保留未删；details3d-manifest.invalid_prior_evidence 登记；attempt_011/012 双通道（GET 200 bizNumber 互证 + 查看路由截图/文本）替代有效。
9. **零写入**：events 215 条无任何写动词；199 份 API 捕获全部为 GET 详情或 POST 查询类（/WorkOut/query、/KindlyTips/query，模块只读查询 API）；无保存/提交/选择关联/占用类动作；`session_state_saved` 仅 profile 持久化。
10. **零源码改动**：R03 handoff 22 项 artifacts 与当前盘上逐字节全等（含 bpm_coverage/bpm_facts/bpm_plan/fill-plan.schema/test_bpm_coverage）；纯查证轮按合同第 5 条沿用 V3-R03 全量 308 OK unittest 与唯一 offline-verify，A 认可。
11. **分离纪律**：actual_trip_matches/CASE-03-report 无 `oa_test_relations`/`test_placeholder` 键；“占位”仅出现在严格分离声明句；本轮零占位选择。
12. **台账**：progress.json V3-R04 入账，errata 第 4 行 = .gitignore 归属订正（A 侧 13:15:01 按用户要求写入），与 A 实证一致；observations_next_round 含 B 自登 P2×3 与既有两项；失败字典 {D23:1, D22:1} 原样承接。
13. **凭证红线**：run 目录全文本 grep（eyJ/refresh_token/session_state.json）零命中。

## 二、A 发现的观察项（不阻塞，转 round-5）

- **O1（P2，证据哈希语义）**：`wide-query-manifest.json` 各页 sha256 = 紧凑 `json.dumps(捕获对象)` 的哈希，**不是文件字节哈希**（details3d/candidates3e/final-artifact-hashes 均为文件字节）。A 已用逻辑 JSON 哈希 5/5 复核内容完好、无篡改，但按文件字节验证会失配。下轮统一为文件字节哈希或显式登记 hash_semantics，不得回改历史文件伪造一致（新增订正 sidecar/说明即可）。
- **O2（P3，字段语义文档化）**：candidates3e 与 actual_trip_matches 排除块的 traveler_rows/covers_day 统一取 `factNatureStartDate/EndDate`（含途自然区间）；12025095297 实际公出时间仅 09-18（自然区间 09-17..09-18）。语义单一一致但未在文档写明；结论不受影响（行级无陈晶与日期字段选择无关）。下轮在 manifest/schema 说明或报告中写明字段口径。
- **O3（P3，D08 字段完备）**：matched_doc 无显式 `applicant`/`user_id` 键（申请人=陈晶由 own-13 + chen_trip + 详情行承载）。下轮补显式字段，避免多人员单歧义。
- 沿用 B 自登 P2×3（active_run_profile 旧快照、ui_text 裸文件名、文本噪声）与既有两项（schema 字节基线、capability 299≠308）。

## 三、判据签核（相对 round-3 的变化）

- **D07 → PASS_DYNAMIC**：真实公出单模块入口/宽窗定向查询/分页/详情证据链完整（B1-B2 级）；96+13+8 单证据可复算；已用单不靠可关联弹窗、进模块实证；未知不臆断。
- **D08 → PASS_DYNAMIC**：27/27 独立匹配记录一票不漏；全部最小字段具备（申请人经 own-13/详情行承载，O3 补显式键）；三向完整性 A 全部独立复算通过；12 MATCHED 同日唯一对应、15 NO_MATCH 如实缺口含行级反证，无强造双射、无汇总冒充。
- **D27 → PASS_DYNAMIC**：期间/方向由票面通行日+公出单明细+Excel 核定；0906 目录名 vs 0905 票面按票面裁决留痕；无预设业务答案。
- **D09 仍 FAIL**（计划内）：真实侧 actual_trip_matches 已交付且分离纪律已验证；oa_test_relations/test_placeholder 侧待 CASE-07（模板→计划→填写链之前置未到），不提前判过。
- 其余 14 项 PASS 维持；D01/D10/D11/D12/D17/D18/D19/D24/D26 维持 FAIL（模板身份缺口 PENDING_HUMAN_NONBLOCKING，等用户提供完整模板单号后进入 CASE-05..08）。

## 四、结论

round-4 CASE-03 高质量交付：12/15 匹配-缺口划分证据充分、可复算、诚实；attempt_010 缺陷发现-作废-替代处理规范；零写入零源码改动。decision=rework → round-5 派工证据卫生修复（O1/O2/O3 + 观察项），并明确模板单号人工缺口状态。
