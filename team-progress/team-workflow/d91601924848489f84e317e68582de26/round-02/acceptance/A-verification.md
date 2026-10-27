# A 独立验收记录 — round 2（CASE-01 原件理解 + D22 修复）

- workflow_run: `d91601924848489f84e317e68582de26` / round 2 / 2026-10-26（北京时间）
- A session: `0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`；基线重核 sha256 `d437988d…`（与 join 冻结一致）
- 验收方法：A 一手复算与独立抽取——交接 21 项哈希重算、73 原件对 round-1 manifest 全量重哈希、fact 层 Decimal 重算 T/O、72 PDF↔52 身份分区校验、**以 fitz 独立抽取 8 个 PDF（含 0906 拆分票/0917 不对称/1210 疑重扫全部异常组）文本层比对全部 fact 值**、20 张票据汇总单声明额 vs 引用票独立求和、Excel openpyxl 独立读、D22 构建输出与新测试实读、git 写面/凭证 grep。

## 一、A 独立核验事实

1. **交接哈希**：round-02 handoff 21 项 artifacts 全部重算一致；evidence 路径齐备。
2. **原件零漂移**：73 件对 round-1 case manifest 逐件重哈希 0 变更（连续两轮零触碰）。
3. **CASE-01 事实层独立复算**：
   - 身份分区：72 个 PDF 各恰好归属 1 个唯一身份（xlsx 按 gap `workbook:not_pdf_pipeline` 登记不强行分类）；52 身份 = 27 toll + 5 fuel + 20 summary ✓。
   - T：A 从 per-file facts 以 Decimal 独立求和 27 张唯一通行费 = **486.93** ✓；O：5 张油票 = **2031.17** ✓；与 observed_totals 一致，无身份内金额矛盾。
   - **PDF 文本层独立抽核**：fitz 抽取 8 文件（4 通行费含三组异常 + 2 油票 + 2 汇总单），B 记录的全部 fact 值（票号/日期/金额/税额/站名/购销方/引用票号）在原 PDF 文本中逐值命中，零缺失——fact 层非内部自洽而是原件可证。
   - 1210「晋江-厦门1 (2).pdf」实证为**不同发票**（票号 20519372/金额 15.53 vs 19977515/4.42），与「晋江-厦门1.pdf」分立身份正确，非重复扫描误判。
   - 汇总单交叉：A 独立对 20 张票据版汇总单声明额 vs 其引用票求和 = **20/20 全等，0 差异**；B 的 consistency 97 checks、大写↔小写 72/72、价税闭合 25/25、mismatches=[] 亦经文件实读确认。
   - 4 同尺寸字节簇均判不同身份（identity 不同）✓；期间链 2025-08-25→12-10 由票面 travel_date（含 0906 目录 vs 0905 票面差异如实登记）+开票日分离记录。
4. **Excel 独立读**（openpyxl，只读）：表头行 3（公里数/补贴金额（油车1元/公里，电车0.15）/过路费（据实）/合计/备注）；A 独立 Σkm = **1438** = Σ补贴 ✓；**G 列（过路费）全部为空**——原件确未回填，副本回填留 CASE-02。
5. **D22 修复实证**：新构建 `materials-v3r02-20261026-121653` build_result `missing_real_inputs=["exact_history_template_number"]`（真缺保留），`specific_create_and_save_instruction` 不再列为 missing；`verify_bpm_build.py:42-59` `real_input_layers(missing/supplied/waived)` 三态实现 + `real_input_semantics` 输出；`tests/test_bpm_build_output_semantics.py` 5 测试含阳性对照（`test_explicit_save_requirement_restores_missing_semantics`）；全量 **287 tests OK (skipped=4)** 落盘；manifest 61 键含新测试文件；守卫未放宽（production_writes=false，real_save_verified=false 保留"未测"语义）。
6. **承接项**：02/04 `required_observations` 已回填 OBSERVED（引用 attempt_007 证据路径）；台账 errata 记录 R00-report §4 测试指针勘误（承重 D18MatrixTests，冻结件未改）；模板身份缺口维持 PENDING_HUMAN_NONBLOCKING 不冒充。
7. **台账**：progress.json rounds 补 V3-R02（合同 ctr-fe416d87、工件清单）、unclosed_defects 更新（D22 标注 V3-R02 已修复）、errata 1 项。
8. **安全边界**：git HEAD 仍 `9299545`、staged 0；本轮改面=合同允许文件（verify_bpm_build.py/tests/document-types×4/台账×2），tracked M 列表仍仅 r10 前存在项；凭证 grep 仅命中自测用例名（`_session_state_usable`），无凭证值；73 原件与两轮 manifest 零漂移。
9. **零预设**：observed_totals 明确"仅观测、范围裁定留 CASE-02/03/04"；T/O/Σkm 均为票面/单元格观测非业务结论；R/F/coverage_margin 未出现。

## 二、逐条签注（D01–D27）

| ID | 状态 | 依据 |
|---|---|---|
| D01 | FAIL | 全链未到（CASE-02..08 未开）；fact 层为其原件理解段奠定了实证基础。 |
| D02 | FAIL | T/O 已观测（A 复算 ✓）；K 范围裁定、M/R 计算、F>R 门槛未做（CASE-02/04）。 |
| D03 | FAIL | O 集合已确立且仅观测；"不借票/不虚增 R"的执行链待 CASE-04 落地。 |
| D04 | **PASS_DYNAMIC** | 分类/去重/映射/前导零字符串/回原页锚点/税额口径/汇总单交叉全交付并经 A 独立 PDF 抽核与 20/20 复算（事实 3）。 |
| D05 | FAIL | 回填副本未做（G 列确证为空，CASE-02 范围）；原件两轮零漂移 ✓。 |
| D06 | FAIL | 覆盖分支未实现（DELTA-1 登记在案，CASE-04）。 |
| D07 | FAIL | 公出单模块未进入（计划内，CASE-03）。 |
| D08 | FAIL | 逐票对照报告未产出（fact 层已备其票据侧输入）。 |
| D09 | FAIL | 两套关联表未产出。 |
| D10 | FAIL | 身份/模板：模板缺口维持；字段复用矩阵/来源链待计划阶段。 |
| D11 | FAIL | 正式链未执行。 |
| D12 | FAIL | OA 填写未执行（本轮零浏览器动作，合规）。 |
| D13 | PASS_DYNAMIC | 边界不变量全守（事实 8：改面受限、无类别扩展、无回退、无保存测试）。 |
| D14 | PASS_DYNAMIC | R00 证据链存续、失败字典 {D23:1,D22:1} 原样带入交接、台账续维护。 |
| D15 | PASS_DYNAMIC | 本轮结论（T/O/52 身份/287 测试/构建）全部哈希绑定且 A 复算属实。 |
| D16 | FAIL | F>R/=</<、0.01 边界等反例测试未实现（CASE-04 范围）。 |
| D17 | FAIL | B2–B7 未执行（B1 证据存续）。 |
| D18 | FAIL | 汇总索引未达（A2 已就绪、A3 部分：Σkm 观测）。 |
| D19 | FAIL | 未执行（CASE-08）。 |
| D20 | PASS_DYNAMIC | 接力实证：A 侧 wait bcz7mq000 由 B finish 事件唤醒（seq 9→10）；上轮 waiter 被内存回收后经用户明示重挂，机制与记录均留痕。 |
| D21 | PASS_DYNAMIC | 287 OK 落盘、唯一构建 OFFLINE_PASS、manifest 61 键、探针零改动。 |
| D22 | **PASS_DYNAMIC** | 修复实证（事实 5）：输出语义三态化、真缺项保留、阳性对照测试、全量绿。首试修复成功，历史计数 1 保留不累计。 |
| D23 | PASS_DYNAMIC | 台账 V3-R02/errata/unclosed 更新且与 runs 权威证据一致。 |
| D24 | FAIL | 交付物缺：已核对副本、金额表、公出单报告、OA 结果、用户报告。 |
| D25 | PASS_DYNAMIC | 零 commit/staged、凭证不入工件（事实 8）。 |
| D26 | FAIL | 案例闭环未达（进行中 2/16 轮）。 |
| D27 | FAIL | 票面+Excel 侧已闭合（零预设、期间/差异如实）；公出单侧证据链待 CASE-03，复合要求未全达。 |

## 三、结论

- 9 项 PASS_DYNAMIC（D04 新增、D22 转通过，D13/D14/D15/D20/D21/D23/D25 保持），18 项 FAIL（均为 CASE-02..08 计划内未开工）。
- B 的 round-2 交付质量高：fact 层经 A 换库独立抽核零缺失，金额/交叉全部独立复算一致，D22 首试修复带阳性对照。
- decision=rework → round 3：CASE-02（范围裁定+副本回填+可靠重算）+ CASE-04（R=M+T、F=O+T>R 严格覆盖分支+反例测试）。
- 失败字典不变：`{review|content|source_manifest_coverage|D23: 1, review|content|active_output_semantics|D22: 1}`（两项均已闭环，计数保留为历史）。

## 四、A 侧留痕

- 机器可读复算记录：同目录 `hash-recheck.json`。
- A 未修改 B 任何业务产物；73 原件在本验收期间保持零漂移。
