# B6 独立复核报告 — V3 round 8（全新过程，零上下文继承）

> 落盘说明（B orchestrator 注）：本文件为 B6 复核 agent（mc-expert 陪审位，ENHANCED_FINAL 语义，全新实例零上下文继承）最终回传报告的**逐字原样落盘**，B 未改写内容；落盘时间 2026-10-26 19:4x，sha256 见同目录 events.jsonl 与 final-manifest.json。

复核员：B6（mc-expert 陪审位，ENHANCED_FINAL 语义）。只读执行：Read/Grep/Glob + 只读 Python（Decimal/openpyxl/hashlib）复算；未修改任何文件、未连接生产 OA、未读取 `.pw-profile/`、`.local-session/` 或任何凭证目录。

仓库根（下文所有相对路径的基址）：`D:\Downloads\Mc Claude Code Workshop\2026-Auto-Pilot 企业微信\`

契约封套：REVIEW_PROFILE=ENHANCED_FINAL（一致性审计语义）｜AUTHOR_RUNTIME=CLAUDE_GLM｜ADMISSION=ADMITTED（fill_only 只读复核，MEDIUM 语境）｜HASH_VALIDITY=VALID（review 全程只读，读取时哈希与各 run 自记录哈希互证，无漂移）

---

## 一、输入清单（实际打开的文件 + sha256 前 16）

**A 组：73 件原件**（`feature01-细化报销skill/12月公出-发票/`，72 PDF + 1 XLSX）
逐件重算 sha256，与 `case01-facts.json` files[] manifest 及 raw/*.json 内嵌 sha **73/73 全等，0 mismatch**。逐件哈希表已存在于 `case01-facts.json`（8d5581dec67c5a9c，其正确性由我逐件复算证实）。XLSX 原件 `2a8866e6a84cd9ff`；原件统计表被 CASE-02 证明未改动（src_sha_before==after）。

**B 组：raw 解析档 73 件**（`automation/runs/20261026-115500-v3r02-case02…` 即 `20261026-115500-v3r02-case01/raw/`）
全部程序化读取用于独立票面抽取；73 件 sha16 串联哈希 `17b09be8b8baff98`（首件 51c99b6eae4abec2 / 末件 3fa9d8cd79900eda）。

**C 组：attempt_011 / attempt_012 证据 JSON**（case03 run）
41 件（api-detail×13 + api-v3d×28）串联 `eb55a2be05dc64a2`；10 件（api-cand×8 + entry×2）串联 `bc8fcc902d84caae`。逐件 sha 在 Face 3 中对被引用者全部核验。

**D 组：交付工件 36 件（逐件 sha16）**

| sha16 | 文件 |
|---|---|
| 8d5581dec67c5a9c | runs/20261026-115500-v3r02-case01/case01-facts.json |
| 002aa570a94d81f5 | …case01/case01-consistency.json |
| 3ff24c3deb285c59 | …case01/CASE-01-report.md |
| a899944ea27c16fb | runs/20261026-131000-v3r03-case02/case02-mapping.json |
| 09c26a5ee5989f66 | …case02/case02-coverage.json |
| ba9e674050bf9e57 | …case02/case02-backfill.json |
| cccd3d8124b1d940 | …case02/case02-reopen-verify.json |
| f4fa1d1c4e82beac | …case02/12月-自驾公出公里数统计表-已核对.xlsx |
| 60ec7bef28224732 | …case02/CASE-02-report.md |
| 7419ab8a01ddd7cc | …case02/CASE-02-04-report.md |
| 7da036aabed9b56c | runs/20261026-143340-v3r04-case03/actual_trip_matches.json |
| 43da29d997a50d01 | …case03/chen-docs.json |
| 214dca93d64275a8 | …case03/CASE-03-report.md |
| 0d5b22cd6f12058d | runs/20261026-172300-v3r06-template-plan/fill-plan.json（v1.0） |
| 7c71bd42b9730635 | …r06/template_snapshot.json |
| 8cbafac3bacfc832 | …r06/field-reuse-matrix.json |
| d78b16bce9b14b25 | …r06/materials-manifest.json |
| a6583a298da434eb | …r06/case06-task-material.json |
| 27bf28a02bcba051 | …r06/CASE-06-report.md |
| 6c9d1b6fd719124e | runs/20261026-181500-v3r07-fill/fill-plan-v11.json |
| 0c6aa2250020bcd4 | …r07-181500/variant-diff.json |
| dfb18044c0851afa | …r07-181500/variant-validate.json |
| c45d6c4d5eadba3b | …r07-181500/materials-manifest.json |
| 579151b67f3f1a7a | …r07-181500/B5-report.md |
| 369a47938da2215e | …r07-181500/attempt_002/evidence/relation_enumeration.json |
| 6c9d1b6fd719124e | runs/20261026-183000-v3r07-fill/input_plan_snapshot.json（与 v1.1 字节级同一） |
| c67e34c4e4a36170 | …r07-183000/task_binding.json |
| a10d9f47c9247d9e | …r07-183000/execution_source_manifest.json |
| d30ec412e4ce723f | …r07-183000/events.jsonl（可变追加文件，按 run 注记不参与终局哈希） |
| 6ef51f876152dd7a | …r07-183000/attempt_001/stage1_result.json |
| 868a920d1c0310b1 | …attempt_001/evidence/independent_readback.json |
| 170cbdb5d182240c | …attempt_001/evidence/independent_verification.json |
| 9b85018210b77011 | …attempt_001/evidence/test_page_close_inventory.json |
| 2a8866e6a84cd9ff | feature01…/12月公出-发票/12月-自驾公出公里数统计表.xlsx（原件） |
| d437988d7b2f29b7 | feature01…/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md |
| 1da6e1e15f01b99f | …case03/attempt_007/evidence/wide-rows-page01.json（materials-manifest 第 5 项，哈希核实） |

（材料 manifest 五项上游链全部核验：case06-task-material / case02-mapping / case02-coverage / case01-facts / wide-rows-page01 的 manifest 记录哈希均与实际文件一致。）

---

## 二、七面复算（方法 / 数字 / 差异表）

### 面 1 事实链（73→52 去重；K/M/T/R/O/F/margin）— 零差异

方法：① 73 原件逐件 sha256 与两套 manifest 对账；② 不采信 facts 分类，从 raw OCR 文本按 y 带聚簇成行独立抽取「价税合计（小写）」、发票号码/代码、汇总单号；③ 原始 XLSX 用 openpyxl 直读求和；④ 全程 Decimal。

- 哈希对账：73/73 全等，0 mismatch。
- 独立分类：通行费 PDF 27（发票代码均 035002400112，发票号码 27 个互异，无重复件）；油票 PDF 5（20 位发票号码互异）；汇总单 PDF 40 → 20 个唯一汇总单号，每个恰为「(票据)+(行程)」一对一配对，0 畸形。唯一身份 = 27+5+20 = **52**，与 facts identities 52 全等；27 张通行费身份集与 case03 发票身份集 sym-diff 为空。
- 通行费逐票票面（价税合计，27/27 全抽非抽样）：22.64×16（0825×2、0904×2、1028×2、1112×2、1124×2、1204×2、1210 去程 1）＋拆分组 0905（4.41+15.54 / 4.42+15.53）、0917（15.69+16.24 / 16.24+20.73）、0928（16.24+15.69 / 16.24+15.69）、1210 返程（4.42+15.53）。**T = 486.93**。
- 油票逐票：444.15（393.05+51.10）、414.68（366.97+47.71）、300.00（265.49+34.51）、433.16（383.33+49.83）、439.18（388.65+50.53），价税闭合 5/5 真，**O = 2031.17**。
- 原始表 F4:F23 独立求和：**K = 1438**（7×146 + 152 + 2×132）；G 列合计 1438。
- 闭合：M=1438.00，R=M+T=**1924.93**，F=O+T=**2518.10**，margin=**593.17**，**F>R 严格成立**（2518.10 > 1924.93）。

差异表：与任务声明及 facts observed_totals（K/T/O）、identities 计数——**零差异**。CASE-01-report 不含 R/F/margin 属既定口径分工（观测值留 CASE-02 裁定），非缺口。

### 面 2 Excel 回填 — 零差异

方法：openpyxl 双通道（公式 + 缓存值）读副本 `12月-自驾公出公里数统计表-已核对.xlsx`；H 列与我按「票面日期+方向」独立聚合的 20 段 Leg 金额三方对照（我的 OCR 票面 ↔ mapping 分配 ↔ 单元格值）。

- H4:H23 共 20 值全对，含拆分段：19.95×3（0905 去/返、1210 返）、31.93×3（0928 两段、0917 去）、36.97（0917 返）、其余 22.64。
- I4:I23 全为 `=G{r}+H{r}`；I24 保持 `=SUM(I4:I23)`；缓存 I24=1924.9300000000005（计算引擎浮点尾差，见观察③），Decimal 语义 1438.00+486.93=1924.93。
- backfill 变更恰为 H4:H23 值 + I4:I23 公式（changes=20，km_preserved 全 true）；F/G/J、I24 公式、行 3 表头、行结构 untouched；副本 sha f4fa1d1c4e82beac 与 manifest 一致；**原件 src_sha_before==after（未被改动）**。
- mapping 闭合：27 票每票恰一次分配、无重复；每行 row_toll_total == 汇总单 declared_total == H 单元格 == 我的票面和；coverage 模型 fuel_pool_strict_surplus、strict_gate=greater、gate_passed=true，与我的 F/R/margin 复算全等；重开实测（reopen-verify）与我的独立读数一致。

差异表：文件/单元格/单据/金额——**零差异**。

### 面 3 逐票公出单对照 — 零差异

方法：**不重放报告结论，从 13 张本人单的 attempt_011 api-detail 原始 body 重建**陈晶（appliedName）行级日期覆盖（factStartTime/factEndTime 逐日展开），对 27 票 travel_date 独立重判；再核报告侧元数据。

- 13 单原始 body 重建覆盖日：{04-21, 07-15, 08-20, 08-25, 09-05, 10-17, 10-28, 11-12, 12-04, 12-26, 2026-07-24, 2026-09-22}。
- 我的重判：**MATCHED=12，Σ=221.02**（12025085485×2=45.28、12025092237×4=39.90、12025105858×2=45.28、12025115547×2=45.28、12025121473×2=45.28；5 单 12 票）；**NO_MATCH=15，Σ=265.91**（09-04:45.28、09-17:68.90、09-28:63.86、11-24:45.28、12-10:42.59）。总计 27 票 Σ=486.93。
- 对照报告：逐票裁定、单号、金额、Σ、per_doc 计数、按日合计——**0 diff**（我判定 NO_MATCH 而报告 MATCHED 或反之者：0）。
- 证据核验：12 条 MATCHED 的 api-detail 文件存在且 sha256 与内嵌 api_sha256 全等；applicant（陈晶/116070053）与 body 行名一致；15 条 NO_MATCH 引用的 8 个同事候选文件（api-cand）全部存在、原始 body traveler_rows 均不含陈晶；27 票 excel_row 与 case02 分配行号全等。

差异表：单据/裁定/Σ——**零差异**。如实记录项：12025105858 自身 reimed=2（已被旧报销使用），报告原样呈现，非差异。

### 面 4 模板复用边界 — 零差异

方法：枚举 fill-plan v1.0 sources 全 170 键按 kind 分类，逐一打开 template_snapshot.json 对值；禁入类正则扫描。

- **170 = template 14 + material 156**。14 项 template 源逐项定性：身份 2（applicant.name=陈晶、applicant.department=运动表现研究部）、收款 4（banks/0 account/bank/bankCode/payee）、预算 8（details/0 与 details/1 的 budgetDeptName/budgetItemName/budgetNo/subjectName，后者 locator 复用模板 details/0 行）。**禁入类（日期/费用/发票/金额/关联编号）template 源命中数 = 0**。
- 14 项记录的 snapshot sha 与实际 template_snapshot.json（7c71bd42b9730635）全等；模板旧值（明细 cost 191.40/60.00、旧 digest/reimItem）无一进入计划（计划明细=通行费 486.93/公里补贴 1438.00，全部 material 源）。
- field-reuse-matrix：采用 4 / 替换 12 / 不适用 2（共 18 行），规则文本与边界一致；material 156 项全部指向 case06-task-material.json 且 sha a6583a298da434eb 与实际文件全等。
- 模板单号 15426095951 与用户 2026-10-26 提供记录一致。

差异表：源/字段/哈希——**零差异**。

### 面 5 计划 v1.0 三向闭合 — 零差异

方法：Decimal 逐行复算 + 与我的 Face-2 独立值逐项对（不是与计划自证）。

- 行数：details **2** / costs **20** / banks **1** / relations 0（v1.0）。
- 20 行 costs 逐行：cost == 公里补贴 + 该行通行费（我的值）；日期 == mapping 日期；reason 内发票号集合 == 该行分配集合（含拆分票行，修正我首轮正则后 20/20 通过）；**Σcosts = Σdetails = Σbanks = header.totalCost = 1924.93**（四向全等）。
- details 拆分 486.93（=我的 T）+1438.00（=我的 M）；coverage 块 F=2518.10 > R=1924.93 语义 strict greater，与 case02-coverage 一致。
- no_invoice_rows 20 条恰好覆盖全部 20 行 costs（油票覆盖模型理由齐备）；materials manifest sha 与实际一致。

差异表：行/金额/闭合——**零差异**（首轮 Σcosts=1249.32 系我的正则漏拆分票导致 7 行跳加，脚本缺陷已修正，终判以修正后 0 diff 为准）。

### 面 6 v1.1 差异与种子 — 零差异

方法：两 plan 对象深度递归 diff（逐叶路径）独立执行；种子链本地复算；枚举证据哈希与内容核验。

- 我的 diff 叶路径 14 条，映射：/task_id（1）、/authorization/task_id+/authorization/statement（2）、/test_context/purpose+round（2）、/not_applicable/0（1）、/tables/relations LEN 0→1（1）、/oa_test_relations ADDED（1）、/sources//tables/relations/0/fields/{bizNumber,bizTypeName,isLast,nowCost}（4）、/materials/{manifest_path,manifest_sha256}（2）＝14。**全部落入 variant-diff 声明的 9 个 allowed_change_clusters，簇外漂移 0**（与 zero_drift_outside_clusters=true 互证）。其余（header/coverage/amount_rules/applicant/template/details/costs/banks）字节级不动。
- 哈希链：v1.0 文件 sha 0d5b22cd…==baseline_sha256；v1.1 sha 6c9d1b6f…==variant-validate.v11_sha256。
- 种子复算（本地 Python 重放）：`sha256("20261026-180546-c1c5d877").hexdigest()[:16] = 6074a75771428d7e`（与 plan 记录全等）→ `random.Random("6074a75771428d7e").randrange(20) = 6` → 枚举 rows[6] 单据编号 = **12024070132**。全链可复算。注意：种子必须以字符串传入 Random；`int(seed,16)` 会得 9（见观察④）。
- 枚举证据：真实关联弹窗默认首屏 20/76 行、未翻页未检索、selection_performed=false；被占用的原公出单 12026096668 不在候选（0 命中）；文件 sha 369a4793…==plan 内嵌 enumeration_sha256。

差异表：簇/哈希/种子——**零差异**。

### 面 7 B5 回读与占位分离 — 零差异

方法：不采信 independent_verification 摘要，从 independent_readback 原始 DOM 行数组自行重算；计划↔DOM 逐字段对比（含逗号归一）；执行链哈希与事件轨迹核验。

- 绑定链：input_plan_snapshot 与 v1.1 深度 diff = **0**（文件 sha 同为 6c9d1b6f）；task_binding.plan_sha256 8eea9c05… 我复现为**计划对象的 canonical JSON（sort_keys+紧凑分隔符）哈希**，与 events 中 entry_plan_validation_binding / structured_fill_start 记录一致；config_sha256 == travel.json（执行源 manifest 内）。
- 四表行数组：relations 1 / details 2 / costs 20 / banks 1；计划字段 vs DOM 值逐字段（2+1+1×20+4×2 等全部承重字段）：**0 值差、0 缺失**。
- 金额四向（从 DOM 原值 Decimal 重算）：Σdetails=Σcosts=Σbanks=header.totalCost=**1924.93**。
- 占位分离：relations 唯一行 bizNumber=**12024070132**；12 张 MATCHED 真实单号在整个 readback（含 detailrels 投影）中泄露数 = **0**；detailrels 唯一投影行 bizNo=12024070132、cost=1,924.93、其余只读空白；附件未建模区为空。
- 带出只读字段零覆盖：DOM-only 字段中 bizCost/totalReimedCost/budgetOwner/subjectTotalCost/subjectSurplus/bank/bankCode 等全部 readonly=true 且计划零源；relations.description="陈晶(2024-06-24)"（DOM readonly=false）判定为**选单系统带出**：证据=relations 行无 structured_row_written 事件（23 条写入事件恰为 20 costs+2 details+1 banks）、写入走 picker_open→picker_select_confirm（18:30:01→03）、计划无该字段源、B5 报告§带出字段零覆盖核查已如实披露。
- 行为边界：save_status=NOT_ATTEMPTED；own_test_page_close unsaved=true/save_attempted=false（keep_open 15 分钟后仅关自有测试页）；页面终态编制中、无单号无 UUID；表单自动带出的默认收款行（payee/account 与计划相合，cell_already_equal×2）已被事件披露；授权链：close inventory 的 authorization_sha256 == 冻结 V3 合同实际 sha d437988d7b2f29b7（核实）。

差异表：行/值/金额/占位/只读——**零差异**。

---

## 三、结论

**VERDICT=CONSISTENT**

七面全部从原始证据独立重算，与既有交付（facts/mapping/coverage/backfill/actual_trip_matches/fill-plan v1.0/v1.1/readback/verification）**零实质差异**；执行链哈希（v1.0→v1.1→快照→events→readback→冻结合同）全程闭合。映射到共享 review contract：承重检查（对象绑定/身份生命周期/时序权限/证据真实性）全过，UNVERIFIED_SCOPE 见下（均非七面承重项）。

VERIFIED_COMMANDS（要点）：python -X utf8 只读复算脚本 ×12（哈希对账、OCR 行聚簇抽取、openpyxl 双通道、映射三方对照、13 单覆盖重放、深度 diff、canonical 哈希复现、种子重放、readback 逐字段对比），全部 exit 0，证据即上述 run 目录原档。

## 四、遗留风险 / 观察（均不构成差异）

1. **执行源 manifest 工作树漂移 1 项**：`execution_source_manifest.json` 39 项中 `.claude/skills/bpm-fill-run/references/travel.md` 与当前工作树哈希不一致（执行后工作树改动；manifest 保留执行时哈希，证据链自洽）。未来任何人复核需按 manifest 哈希而非当前文件。
2. **relations.description 的 DOM readonly=false**：其「带出」结论靠事件轨迹+计划无源+披露支撑，DOM 元数据本身不承重。若日后做保存类验收，建议对该字段增加写入轨迹断言。
3. **I24 缓存值浮点尾差** 1924.9300000000005：计算引擎浮点产物，Decimal 语义与全部交付口径为 1924.93，无失真；建议后续报告可附一句引擎尾差说明避免误读。
4. **种子传入方式**：`random.Random(seed)` 的 seed 须为字符串 "6074a75771428d7e"（int(seed,16) 会得 index 9）。方法字符串语义正确但建议在 oa_test_relations 里补注「seed 以字符串传入」防未来重放误用。
5. **applicant_employee_verified=false**（该轮事件）：employee_id 未在该 run 核到（creator_unchanged=true、登录探查身份=陈晶）。身份分层如实记录，风险极低。
6. **12025105858 reimed=2**：MATCHED 真实单中一张已被旧报销使用，报告如实呈现；本案 fill_only 未写任何真实关联，无占用后果。
7. PNG/HTML 截图仅核存在与清单，未做像素级复核（DOM/JSON 证据已承重，非缺口）。
8. UNVERIFIED_SCOPE：未重开生产 OA 做「占位无持久占用」的新 session 二次复验（采信页面编制中/无单号/干净关闭证据）；未重跑 PDF 解析器本体（以 raw 提取为票面真相源）；未重跑 unittest/verify_bpm_build 离线链（非七面范围）。

（KB 健康度：本次咨询未发生「为偏好/决策/反射翻源档」的 KB 缺口，无补洞建议。）
