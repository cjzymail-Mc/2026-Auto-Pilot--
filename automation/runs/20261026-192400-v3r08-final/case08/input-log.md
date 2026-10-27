# CASE-08 独立验收员 input-log（阶段一）

记录人：CASE-08 新 session 验收员（零上下文继承，仅白名单输入）
工作目录：automation/runs/20261026-192400-v3r08-final/case08/
规则：自此刻起，实际读取的每一个文件记入本日志（路径+用途+读取时间，北京时间）。

## 白名单输入读取记录

| # | 时间 | 路径 | 用途 |
|---|---|---|---|
| 1 | 2026-10-26 19:26 | feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md | 冻结需求合同全文（重点 §4 业务规则/覆盖模型、§5 纪律、§3 固定输入、§10.5 新 session 使用验收） |
| 2 | 2026-10-26 19:26 | .claude/skills/bpm-fill-run/SKILL.md | 生产 skill 正文：日常入口、完整链路、执行与恢复、授权与保存、环境 |
| 3 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/travel.md | travel 路线参考：模板读取（缓存/live）、四表、金额闭合、oa_test_relations 正式生成路径 |
| 4 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/plan-contract.md | task/fill-plan v1.0 契约：schema 字段、来源/哈希、发票分类与分配、状态表 |
| 5 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/full-chain.md | 六阶段链路与调用方式、操作人来源纪律、阶段状态 |
| 6 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/evidence-hash-semantics.md | 采集哈希口径（sha256_file 为权威）、factStart/factNature 口径 |
| 7 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/express.md | 白名单 references 全读要求（本案例不适用，仅通读） |
| 8 | 2026-10-26 19:28 | .claude/skills/bpm-fill-run/references/rd-materials.md | 同上（不适用，仅通读） |
| 9 | 2026-10-26 19:29 | feature01-细化报销skill/12月公出-发票/（目录列表+全 73 件文件名） | 原件盘点：10 日期目录 67 PDF + 1 xlsx + 油票 5 PDF = 73 件 |
| 10 | 2026-10-26 19:29 | automation/task-registry/*.form.json（11 件，只读查询） | 核对既有 task_id/意图，确认无冲突；发现 v3r07-case07-fill-20261026 为已交付任务，本验收用独立新 task_id |
| 11 | 2026-10-26 19:31 | automation/runs/20261023-104616/105801/135739/140250/142146-travelcensus/travel_census.json（结构与 15426095951 命中检查） | 2026-10-23 官方 travel census 缓存；142146 缓存 docs 含 bizNumber=15426095951，作为 bpm_template --census 输入 |

## 禁读目录遵守声明

未读取（阶段二比对授权前）：automation/runs/20261026-172300-v3r06-template-plan/、20261026-181500-v3r07-fill/、20261026-183000-v3r07-fill/、20261026-115500-v3r02-case01/、20261026-131000-v3r03-case02/、20261026-143340-v3r04-case03/ 的任何内部内容；未改 registry；零业务写入。

## 环境探查与工具使用记录（追加中）

## 追加读取记录（#12 起，续跑段）

12. `case08/rendered/render_index.json` + 72 份 PNG 渲染件（本 run 内 `bpm_extraction.render_to_files` 自产工件；其中 0928×4、1028×4 经 Read 铸 CDN URL 后 analyze_image 逐位读取，视觉交叉验证用）。
13. 72 份原件 PDF 的**内嵌文本层**（PyMuPDF 只读提取 → `case08/pdf-text/*.txt`，`_index.json`）：机读主通道，逐票票号/代码/金额/日期确定性解析（`case08/parse_all_pdfs.py` → `machine-parse.json`）。
14. `12月-自驾公出公里数统计表.xlsx` 全量只读盘点（openpyxl read_only，`case08/dump_xlsx.py`）：sheet 汇总 38×10，表头 F3/H3/G3、行程行 4-23、B36 备注规则、I24 公式。
15. `automation/runs/20261026-193100-0527f5dc/`（本人 --task 产物，非禁读）：`materials/manifest.json`（73 件哈希清单）、`materials/parsed/*.json`（解析存根，均 NEEDS_INPUT 占位）、`task.json`、`preparation_result.json` 头部。
16. 仓库工具源（只读，校验契约用）：`automation/fill-plan.schema.json`、`bpm_plan.py`、`bpm_materials.py`、`bpm_coverage.py`、`automation/document-types/travel.json`、`fill_once.py` 相关节选。
17. `automation/runs/20261023-142146-travelcensus/travel_census.json`（travel.json 引用的闭包能力证据，非禁读目录）：核实 reimItem 观测值域（08005/08008/08009/08010/08023/08024）与公出油补历史做法、submitType 显示值。
18. `case08/template_snapshot.json` 二次核对（census 缓存来源，身份/银行/预算字段 locator 用）。

禁读六目录全程未读；`automation/task-registry/` 未查询；零业务写入；`.pw-profile`/凭证未触碰、未入任何工件。

## 阶段二比对读取记录（#19–22，授权只读，零业务写入）

19. `automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json`（delivered v1.0，sha 0d5b22cd…）：header/tables/coverage/not_applicable/materials 全量读取，costs reason 内 27 票号抽取比对。
20. `automation/runs/20261026-183000-v3r07-fill/attempt_001/evidence/independent_readback.json` 与 `independent_verification.json`（B5 回读）：行数/四向金额/身份/校验结论。
21. `automation/runs/20261026-143340-v3r04-case03/actual_trip_matches.json`（CASE-03 逐票公出单对照）：summary 12 MATCHED Σ221.02 / 15 NO_MATCH Σ265.91 与 T 自洽核验。
22. `automation/runs/20261026-172300-v3r06-template-plan/template_snapshot.json`（定向 live 版）：与我 census 缓存版身份/预算/收款/relations 字段一致性比对。

产出：`comparison-report.md` + `comparison.json`。禁读目录中其余文件仍未读；未改任何 delivered 工件。


## 加法订正（B 于 mc-expert 终审 P2 后追加，2026-10-26 22:3x；不改上方任何既有行）

1. **订正上文"禁读六目录全程未读；`automation/task-registry/` 未查询"一句**：与本日志 #10 矛盾——#10 已如实记录 19:29 只读查询过 `automation/task-registry/*.form.json` 11 件（核对既有 task_id 冲突）。正确口径=task-registry **已查询（只读）**，查询内容经独立复核仅含任务身份元数据（task_id/plan_sha256/operator/mode/state/run/attempt），无本案事实/金额/票号/结论；六项禁读交付目录全程确实未读（该部分原句仍然成立）。
2. **白名单字面之外的读取分类补注**（均属环境/基础设施，非禁读交付物）：#10 registry 查询（见上）；#12–15 本验收员自产工件及 73 原件机读提取（rendered/pdf-text/xlsx 盘点/自身 --task run 20261026-193100-0527f5dc 产物）；#16–17 仓库工具/配置源码（fill-plan.schema.json、bpm_plan.py、bpm_materials.py、bpm_coverage.py、document-types/travel.json、fill_once.py 节选；代码非数据）。#11/#18 census 缓存属输入白名单"环境边界"节预授权项。
3. 由本订正引起的哈希链更新：本文件与 CASE-08-report.md 新哈希由 B 同步登记入 `automation/template-materials-program/progress.json` V3-R08 条目。
