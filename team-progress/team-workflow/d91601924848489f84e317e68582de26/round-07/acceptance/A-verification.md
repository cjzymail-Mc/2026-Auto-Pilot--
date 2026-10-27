# Round-07 A 独立验收（CASE-07 正式入口真实填写 + 受限随机测试占位关联）

- A session：`0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`｜run `d91601924848489f84e317e68582de26`｜round 7｜B 交接 seq 35
- 验收脚本：A 多段独立复算（本目录 `hash-recheck.json`）+ A 亲跑全量 unittest；基线 sha256 连续第 7 轮逐字匹配

## 一、交接与红线

1. **交接 28 项哈希全中**（两 run 目录 17 文件 + 源码/schema/测试 3 + offline-verify 3 + 台账/进度 2 等）；73 原件连续第 7 轮零漂移；凭证 grep（eyJ/refresh_token）两 run 全净。
2. **零保存**：两 run events（27+751 条）save 类命中仅 `session_state_saved`（profile 持久化，非 OA）；`stage1_result.save_status=NOT_ATTEMPTED`、`task_status=SUCCESS_FILL_ONLY`；registry 为 FORM_INTENT（非 SAVE_INTENT），conflicts=NONE；未保存页盘点诚实——url `/oa/reimburse?type=new`、biz_number=""、uuid=""、状态"编制中"、`closing_own_test_context_only=true`。
3. **门槛时序**：18:26:51 `variant_v11_built.coverage_recheck_pass=true` → 18:27:24 登录探查（陈晶/116070053 authenticated）→ 18:29:26 preflight（coverage_gate F=2518.10>R=1924.93 PASS + 绑定链核实）→ 18:29:45 fill_start——业务写入前门槛全过，时序入 events。

## 二、随机占位关联（V3 §5.3）逐项复算

1. **枚举真实**：attempt_002 relation_enumeration——关联弹窗默认首屏 20 行（分页器"共 76 条"），未翻页未检索，`selection_performed=false`、`bizNumber_after_close=''`、titlebar X 关闭，零选择零副作用。
2. **随机可复现**：A 重算 sha256("20261026-180546-c1c5d877-case07")[:16]=`6074a75771428d7e` 与声明一致；`random.Random("6074a75771428d7e").randrange(20)`=6 与声明一致；枚举第 6 行=**12024070132**（陈晶 2024-07-01 项目跟进）——种子→索引→单号三段 A 全部独立复现。
3. **排除项实证**：旧模板已用公出单 **12026096668 不在可关联弹窗**（首屏 20 行均无；2026-09-23 单据按最新序应居首而缺席=系统过滤已用单），同时印证合同 §5.1"已用单不在弹窗≠不存在"；`exclusion_hits=0`。
4. **分离与标记**：v1.1 `oa_test_relations` 块 `test_placeholder=true` + 用途引用 §5.3 + 方法/种子/枚举 sha256 绑定 + 与 actual_trip_matches 分离声明；占位行数 1（不强行等于 27 票/12 匹配单）；带出只读字段（bizCost/totalReimedCost 0.00、nowCost 1,924.93 readonly）零覆盖真实费用。

## 三、计划变体与真实填写复算

1. **v1.0→v1.1 零漂移**：A 全叶路径 diff=**39 条**，逐条落入 9 个声明簇之外为零；details/costs/banks/header/coverage 逐字节相等；公共来源值零变化；input_plan_snapshot 与 v1.1 字节相同（6c9d1b6f…）；variant-validate `validate_plan_issues=[]`。
2. **B5 回读逐字段**：header 27 键、四表 1/2/20/1 行数全等；costs 20×7 字段**零失配**；details/banks/header/relations 仅千分位显示格式差（数值等价 A 全部判定 True）；**金额四向 1924.93==R**（明细/费用行/银行/应报总额）；extra/duplicate/missing=0/0/0；completeness 六表全 true；validation invalid_fields=[]。
3. 页面关闭盘点与终局截图（v1_final.png/v1_relations_after.png）哈希入交接。

## 四、源码与构建

- 改动恰为声明的 bpm_plan.py（oa_test_relations 支持）+ fill-plan.schema.json + 新增 tests/test_bpm_oa_test_relations.py；A 对照 V3-R05 source manifest 逐文件复核**无未声明源码改动**（bpm_ui.py 未变——"对齐 _pick_option"系驱动脚本对齐既有语义，非源码改）。
- **A 亲跑全量 unittest：316 tests OK (skipped=4)** 与 B 一致；唯一新构建 `materials-v3r07-20261026-1900` OFFLINE_PASS（含 probe-selftest）。
- 台账 V3-R07（占位关联单独一节+层次"真实控件已验证·填写+回读·未保存"）；errata 仍 5 行。

## 五、判据签核

- **D09 → PASS_DYNAMIC**：两套数据分开建模/核验/报告、test_placeholder 真实控件选取+完整回读、随机方法与种子可复现、行数不强凑、占位零覆盖、fill_only 零保存、旧单未动、真实对照未受影响、例外未变全局开关——全部达标。
- **D12 → PASS_DYNAMIC**：正式入口原生控件全行写入、金额闭合、evaluate 只读定位、守卫全程、未保存状态如实报告、既有报销单只读、registry 无规避。
- D17 进至 B1–B5 完成（B6/B7 留 round 8）；D11/D24 推进（独立复核+用户报告留 round 8）；D01/D18/D19/D26 维持 FAIL——合计 **20 PASS_DYNAMIC / 7 FAIL**。

## 六、结论

round-7 主线高质量交付：真实 OA 全行填写+可复现随机占位+零保存纪律完备，A 从种子到 DOM 逐层独立复算全部吻合。decision=rework → round 8 派 B6 独立复核 + B7 终局标记 + CASE-08 新 session 使用验收 + 用户报告与最终交付（潜在收尾轮）。
