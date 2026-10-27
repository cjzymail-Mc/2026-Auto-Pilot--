# A 独立验收记录 — round 3（CASE-02 范围裁定/副本回填/可靠重算 + CASE-04 严格覆盖模型）

- workflow_run: `d91601924848489f84e317e68582de26` / round 3 / 2026-10-26（北京时间）
- A session: `0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`；基线重核 sha256 `d437988d…`（与 join 冻结一致）
- 验收方法：A 一手复算与独立重跑——交接 22 项哈希重算、73 原件对 r00 manifest 全量重哈希（连续三轮零漂移）、**原件↔副本全 cell 级 diff（openpyxl 双开）**、副本缓存计算值逐行 Decimal 复算、K/M/T/R/O/F/margin 从原件工作簿+CASE-01 事实层独立重建、映射层 27 票恰一次分配与票面/sha256 交叉、**A 亲跑 21 项覆盖反例测试 + 全量 308 tests discover**、bpm_coverage/bpm_facts.reconcile/bpm_plan/schema 四处代码实读、构建/台账/凭证 grep/git 写面核查。

## 一、A 独立核验事实

1. **交接哈希**：round-03 handoff 22 项 artifacts 全部重算一致（0 mismatch）。
2. **原件零漂移**：73 件对 r00 manifest（100322；与 100302 逐件同一）重哈希 0 变更、无额外文件；原件 xlsx sha `2a8866e6…` 回填前后一致（backfill src_sha_before==after 亦证）——连续三轮零触碰。
3. **列位口径裁定（B 纠偏正确）**：A 实读原件表头行 3：F=公里数、G=补贴金额、**H=过路费（据实）**、I=合计、J=备注。round-2 A 记录及 round-3 任务文中"G 列"系字母口径误差；B 按实物工作簿裁定 H 列回填并登记，正确。
4. **CASE-02 范围裁定链**：20 数据行（行4-23）↔27 张唯一通行费**恰一次分配**（allocation index 27/27 无重复无遗漏，与 CASE-01 facts 27 身份集合全等）；每行发票合计==row_toll_total==对应汇总单 declared_total（数值 20/20 全等；A 初检 false 系 facts 原值带 `¥` 前缀的字符串口径差，数值比较通过，非 B 缺陷）；每票 amount 与 file sha256 对 CASE-01 facts 逐票全中；T=486.93；gaps=[]、closure 无缺口；0917 同安站/0906 票面 09-05/电车 0.15 档冲突三项如实登记不改值。
5. **副本回填（A 全 cell diff）**：改动集**恰为** H4..H23（None→逐票真实通行费）+ I4..I23（空→`=Gn+Hn`）共 40 格；I24 `=SUM(I4:I23)` 与原件逐字相同（原样沿用）；F 公里/G 补贴/J 备注/行24 F24 G24 H24 全部零触碰；单 sheet `汇总` 结构不变；公里数 1438 原样保留（未按票据反改）。cell 变更清单（backfill.json）与 A diff 逐格一致，含每格票据 identity/推导/sha256。
6. **可靠重算（A 独立 Decimal）**：副本经真实 Excel 保存的缓存计算值逐行 I==G+H（20/20）；I24 缓存 1924.9300000000005（浮点尾差如实记录）→ 分位 1924.93 == A 从**原件** F/G 列+映射票面重建的 R=M+T=1438×1.00+486.93=**1924.93**，逐行+总额 0 差异。K=ΣF4:F23=1438、M=1438.00、T=486.93、O=2031.17（5 油票）、F=2518.10、margin=593.17、**F>R 严格门槛通过**；coverage.json 全字段与 A 复算一致。
7. **CASE-04 五处分离落地**：①事实层 `bpm_facts.FACT_KINDS` 封闭注册 +`coverage_evaluation`（A 通读 reconcile() 第 1-6 节全为通用语义，零覆盖特判；行为证据：287 项既有测试全绿 + `test_register_coverage_fact_and_reconcile_untouched` + `test_generic_allocation_closure_not_relaxed`）；②schema `coverage` 块封闭（const 模型/严格门槛、11 键必填、金额 pattern）；③`bpm_plan.validate_plan` 可选 coverage 键→`validate_coverage_block`→`COVERAGE_GATE_BLOCKED` 写入前阻断；④`bpm_coverage.evaluate_coverage` 纯函数独立重算（CoverageError fail-closed、Decimal 精确到分、油票入行/重复/未分配/范围重叠全拒绝、O 只影响 F/margin 不增 R）；⑤双报告（case02-coverage.json + CASE-02-04-report.md）值与 A 复算全等。
8. **A 亲跑测试**：21 项覆盖反例（F>R 通过、F=R/F<R 阻断、±0.01 边界、富余不加报、重复/未分配/油票入行/范围重叠拒绝、通用闭合不放宽、无 coverage 计划向后兼容）**全绿**；全量 `unittest discover` **308 OK (skipped=4)**，与 B 落盘日志一致（287→308 恰增 21）。
9. **构建与台账**：唯一构建 `materials-v3r03-20261026-131656` OFFLINE_PASS、manifest 63 键、production_writes=false / real_save_verified=false（fill_only 语义不冒充）、missing 仅剩 `exact_history_template_number` 真缺；台账 rounds 补 V3-R03、errata 3（测试指针勘误/73↔74 口径勘误/.gitignore 澄清）。
10. **安全边界**：HEAD 仍 `9299545`、staged 0、无新 commit；tracked-M 面与工作流启动前一致；round-3 工件凭证 grep 全净；stage 脚本零 playwright/chromium/OA 引用（本轮零浏览器动作合规）；五源文件（bpm_coverage/tests/schema/bpm_facts/bpm_plan）均未入库不涉凭证。
11. **.gitignore erratum 闭环（A 侧补充归属）**：git diff 实证 `automation/.local-session/` 行系工作流前遗留；`.claude/settings.local.json` 行 mtime **13:15:01 = A 在本轮窗口内按用户明确要求写入**（CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP 环境变量配套 ignore，非 B 写入、无凭证内容）。B"非本轮 B 写、零写调用、不作追认先例"结论正确；"内容早于本工作流"归属细节对该行不准，留下轮一行 errata 订正。
12. **零预设复核**：round-2 的 observed_totals 仅观测立场在 round-3 兑现为裁定后实算（K/M/T/R/O/F 全带来源），A 从原件独立重建全链无借内部数字。

## 二、逐条签注（D01–D27）

| ID | 状态 | 依据 |
|---|---|---|
| D01 | FAIL | 全链未到：CASE-03（公出单查证）、CASE-05..08（模板/计划/OA/验收）未开；原件→事实→映射→副本→覆盖模型段已实证。 |
| D02 | **PASS_DYNAMIC** | K=1438（原件 F 列）、单价 1.00（V3 §4.1 用户规则）、M=1438.00、T=486.93、R=1924.93、O=2031.17、F=2518.10、margin=593.17，F>R 严格门槛模型+测试+schema+计划+报告五处一致，A 全链独立复算相等（事实 4-7）。 |
| D03 | **PASS_DYNAMIC** | 油票仅覆盖池不入行（O 只抬 F/margin 永不增 R，测试锁定）、汇总单仅交叉不重复计费、无借票虚增；真例计算在该规则下完成且 A 复算一致（事实 4/7）。 |
| D04 | PASS_DYNAMIC | 保持（round-2 签注）；本轮映射层 27 票交叉再证（事实 4）。 |
| D05 | **PASS_DYNAMIC** | 同结构副本、H 列逐票回填、零值/未找到区分（本例 20/20 有票无缺口）、公里保留、重开实测+独立 Decimal 复算、cell 变更清单、原件零漂移，A 全 cell diff 恰 40 格（事实 5/6）。 |
| D06 | **PASS_DYNAMIC** | 覆盖分支五处分离落地、通用约束零放宽（A 读码+全量回归）（事实 7/8）。 |
| D07 | FAIL | 公出单模块未进入（CASE-03，下轮）。 |
| D08 | FAIL | 逐票对照报告未产出（票据侧输入已就绪：mapping 27 票行定位+锚点）。 |
| D09 | FAIL | actual_trip_matches 与 oa_test_relations 两套关联表未产出（CASE-03/07）。 |
| D10 | FAIL | 模板身份缺口维持 PENDING_HUMAN_NONBLOCKING；正式身份链待 CASE-05。 |
| D11 | FAIL | 正式链未执行。 |
| D12 | FAIL | OA 填写未执行（本轮零浏览器动作，合规；CASE-07）。 |
| D13 | PASS_DYNAMIC | 边界不变量全守（事实 10：改面受限、无类别扩展、无保存测试、守卫未放宽）。 |
| D14 | PASS_DYNAMIC | R00 证据链存续、失败字典 {D23:1,D22:1} 原样带入、台账续维护+errata 3。 |
| D15 | PASS_DYNAMIC | 本轮全部结论哈希绑定且 A 一手复算（308 测试 A 亲跑、Excel A diff、Decimal A 重建）。 |
| D16 | **PASS_DYNAMIC** | 21 项反例测试 A 亲跑全绿：F>R/=/<、0.01 边界、富余不加报、重复/未分配/油票入行/重叠拒绝、通用闭合不放宽（事实 8）。 |
| D17 | FAIL | B2–B7 未执行（B1 证据存续）。 |
| D18 | FAIL | 汇总索引未达（票面+Excel 侧已闭，公出单/OA 侧待补）。 |
| D19 | FAIL | 未执行（CASE-08）。 |
| D20 | PASS_DYNAMIC | 接力实证：重启后 A 重挂 wait `bjyy51jg1` 由 B finish 事件原生唤醒（seq 14→15，回收已按用户配置禁用）；round-2 窗口内存回收事件及处置已留痕。 |
| D21 | PASS_DYNAMIC | 308 OK（A 重跑）、唯一构建 OFFLINE_PASS、manifest 63 键、探针零改动。 |
| D22 | PASS_DYNAMIC | 保持（历史计数 1 保留）。 |
| D23 | PASS_DYNAMIC | 台账 V3-R03/errata/unclosed 与 runs 权威证据一致；manifest 覆盖完整。 |
| D24 | FAIL | 已交付：已核对副本+金额/覆盖表；仍缺：公出单报告、OA 结果、用户报告。 |
| D25 | PASS_DYNAMIC | 零 commit/staged、凭证不入工件、原件零漂移（事实 2/10）。 |
| D26 | FAIL | 案例闭环未达（进行中 3/16 轮）。 |
| D27 | FAIL | 票面+Excel 侧闭合且 A 复算；公出单侧证据链待 CASE-03，复合要求未全达。 |

## 三、结论

- **14 项 PASS_DYNAMIC**（新增 D02/D03/D05/D06/D16，保持 D04/D13/D14/D15/D20/D21/D22/D23/D25），13 项 FAIL（均为 CASE-03/05..08 计划内未开工）。
- B 的 round-3 交付质量高：副本 40 格 diff 与清单逐格相符、重算链 A 独立重建零差异、覆盖模型分离干净且反例充分；列位纠偏（H 非 G）与 73↔74 口径勘误均为对实物的诚实校正。
- A 侧发现 1 项台账级订正（.gitignore erratum 归属，事实 11，非 B 缺陷），随下轮任务带入，不阻塞。
- decision=rework → round 4：**CASE-03 公出单模块逐票查证**（真实浏览器只读查证 27 票对应公出单、完整单号+证据、一张不漏；actual_trip_matches 单独建模）+ 台账 errata 一行订正 + 观察项延续；模板身份缺口继续 PENDING_HUMAN_NONBLOCKING（CASE-05/06 前须用户给完整模板单号）。
- 失败字典不变：`{review|content|source_manifest_coverage|D23: 1, review|content|active_output_semantics|D22: 1}`（两项均已闭环，计数保留为历史）。

## 四、A 侧留痕

- 机器可读复算记录：同目录 `hash-recheck.json`。
- A 未修改 B 任何业务产物；73 原件在本验收期间保持零漂移。
