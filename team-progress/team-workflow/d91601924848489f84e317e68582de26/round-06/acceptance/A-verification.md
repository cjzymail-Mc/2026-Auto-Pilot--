# Round-06 A 独立验收（CASE-05 模板定向读取 + CASE-06 可执行计划）

- A session：`0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`｜run `d91601924848489f84e317e68582de26`｜round 6｜B 交接 seq 30
- 验收脚本：`C:/Users/xy198/AppData/Local/Temp/a_r06_verify.py`（只读）+ A 亲跑 `fill_once.py --validate-only`；机器结果见本目录 `hash-recheck.json`
- 基线 sha256 `d437988d…5c977ef0d` 逐字匹配（连续第 6 轮）

## 一、CASE-05 模板定向读取（真实控件·只读）

1. **交接 13 项哈希全中**；73 原件连续第 6 轮零漂移；events 19 条零写动词，`exact_template_read` 实测在案；凭证 grep 全净。
2. 模板身份：`15426095951` / uuid `92d41ffd042746e390f0a070118ca1d9` / document_type **travel**（兼容成立）；三员身份链同一=陈晶/116070053（登录探查 + 快照 createdName/createdBy 双观测）；applicant 陈晶/运动表现研究部。
3. 实结构完整入快照：details 2 / costs 2 / relations 1 / banks 1 / products 0 / detailrels 1（六种表均观察，travel 无物品档案成立）；旧单 totalCost 251.40、描述"公出晋江油补"仅作历史记录；**旧 relation 公出单 12026096668 已被旧单使用 → 计划禁复用，实测未复用**。
4. 快照双副本（run 根 7c71bd42… / attempt evidence 58e0ccf2…）A 逐键比对**零语义差异**（仅序列化不同），errata 第 5 行如实登记双哈希与 events 追加式口径——诚实处理，非篡改。

## 二、CASE-06 可执行计划（A 全量独立复算）

1. **金额三向闭合**：details 2 行（通行费 486.93 + 公里补贴 1438.00）== costs 20 行合计 == banks 1 行 == header totalCost == **1924.93 == R**。
2. **20 行逐行复算全中**：每行 cost == 原件 G+H；reason 内"公里补贴 X 元（Y 公里×1元/公里）+通行费 Z 元（发票 …）"的 X/Y/Z == 原件 G/F/H 列值；行内发票号集合 == case02-mapping 该行票据集合；起止日期 == mapping 行日期 20/20。
3. **coverage 块**：K=1438/rate=1.00/M=1438.00/T=486.93/R=1924.93/O=2031.17/F=2518.10/margin=593.17、strict_gate="greater" 与 round-3 已验实算全等。
4. **来源 170 = template 14 + material 156**：template 侧仅 applicant 身份、banks 收款四字段、details 预算字段（×2 行）——恰为合同允许的稳定身份/预算/收款复用；本次日期/费用/发票/金额/关联编号零旧单推导（旧 totalCost 251.40、旧描述均未抄入，新描述"2025年8月至12月公出自驾公里补贴及通行费"如实）。
5. **关联与占位分离**：relations 留空 + not_applicable 双理由（旧单已用禁复用；随机测试占位留 CASE-07 实测，零编造单号/UUID/selected）；计划无 `oa_test_relations`/`test_placeholder` 键；与 actual_trip_matches 分离声明明确。
6. **A 亲跑 `fill_once.py --fill-plan … --validate-only`：PLAN_VALIDATED，plan_sha256 `1b3ba0b9…` 与 B 输出逐字一致**（browser_launched=false，幂等复现）。
7. 复用矩阵 18 行（12 替换/4 采用/2 不适用）双版本；预算年度决策有据（随填报年 2026，非抄旧单；旧单同值系巧合已注明）；公司标签取公出单模块实测非旧单推导。

## 三、构建与台账

- 源码/schema/测试零改动：A 比对 V3-R05 source manifest 63/63 逐字节一致 → 沿用 `materials-v3r05-20261026-162500` OFFLINE_PASS 合法（合同第 5 条）。
- 台账 V3-R06 入账；**模板缺口 CLOSED 且引用用户原话**（"模板单号是 15426095951…"，非 agent 自查）；errata 增至 5 行（新增行为 P2-1/P2-2 双哈希口径订正，加法式）。
- 层次标注诚实：模板读取=真实控件已验证（只读）、计划 validate-only=离线已验证、OA 填写/占位关联=未测（CASE-07/08 输入）。

## 四、判据签核

- **D10 → PASS_DYNAMIC**：登录自发现+身份链、指定模板定向核实（单号/UUID/类别/主表/全部适用子表+快照哈希）、复用矩阵逐字段决策、每执行值 path/locator/sha256 来源、预算与收款有据复用不无条件抄旧——全部达标。
- D11/D24 部分推进但为复合判据（含正式填写与 DOM 回读），维持 FAIL；D01/D09/D12/D17/D18/D19/D26 维持 FAIL（CASE-07/08 计划内）。
- 其余 17 项 PASS 维持 → 本轮合计 **18 PASS_DYNAMIC / 9 FAIL**。

## 五、结论

round-6 高质量交付：模板链与计划层全部可独立复算，validate-only A/B 同哈希双验证，复用与占位分离纪律严格。decision=rework → round 7 派 CASE-07 正式入口真实填写 + 随机测试占位关联（fill_only，B4/B5 证据链）。
