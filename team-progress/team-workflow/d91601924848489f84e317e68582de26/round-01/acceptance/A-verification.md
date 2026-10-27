# A 独立验收记录 — round 1（R00 接手盘点轮）

- workflow_run: `d91601924848489f84e317e68582de26` / round 1 / 2026-10-26（北京时间）
- A session: `0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`（helper join 10:25:21，baseline=冻结V3 `d437988d…`，criteria `ad4b2f31…` 27 条，max_round=16）
- 验收方法：本轮 A 直接盘上核验——交接哈希全量复算、案例清单反向枚举、原件对维护快照比对、registry/登录/构建工件实读、git 写面核对、活跃输出 grep；不采信 B 自述。本轮为 V3 §2.2 授权的 R00 盘点轮，CASE-01..08 未开工属计划内，相关 criteria 按真实状态签 FAIL（非处罚性）。

## 一、核验所得关键事实（A 一手）

1. **基线未漂移**：冻结V3 文件当前 sha256 = `d437988d7b2f29b7c8dd79cc1e8892f23e4ba2567a8932925cac36f5c977ef0d`，与 join 冻结值一致。
2. **交接哈希**：handoff.json 13 项 artifacts + 9 项 evidence 逐项重算 sha256 全部一致（程序化比对，含 frozen-artifact-hashes.json rev2 13 项 0 漂移）。A 首轮 ad-hoc 脚本报过 1 处 MISMATCH，经查为 A 本人誊抄笔误，以 handoff.json 原文值复核排除。
3. **旧 run 归档**：`operator-recovery-20261026-v3/recovery-result.json` status=`RETIRED_NOT_COMPLETED`，含 original_phase/round、protected_files_unchanged、original_failure_counts_preserved 字段；活动根无旧 state/task/progress 残留。
4. **登录/身份（只读）**：`20261026-100537-login60/attempt_001/stage1_result.json` c1=PASS（Live account verified），c4/c5 写入检查=NOT_AUTHORIZED，其余 NOT_RUN；events.jsonl 有 `stale_taken_over, old_pid=18236` 事件（与 recovery `profile_owner_alive=false` 互证，非强删活锁）；`.local-session` 记录 auth_status=authenticated、principal/user_id 已设（引用 B 探查记录：陈晶/116070053，identity_checked 2026-10-26T02:05:42Z）。
5. **registry**：10 个 form.json 逐份实读，全部 `FORM_INTENT`；save* 键全空，无 SAVE_INTENT/SAVE_UNCERTAIN/保存成功记录。
6. **案例清单反向枚举**：`12月公出-发票/` 磁盘 73 文件 = manifest 73 条，双向无缺无余；随机抽 6 件 + xlsx 共 7 件哈希实算全中；73 件 sha256 全唯一。**73 件全部与 2026-10-26 维护快照 protected-before.json 比对 0 变更**（原件本轮未被触碰的独立前证）。
7. **r10 在途三态**：R00-report §4 表 + 源码/测试指针；A 实读 `source_manifest.json` 60 键，含 bpm_chain.py、tests/test_bpm_chain.py、fill-plan/task 两 schema、7 个 document-types 文件（office_supplies/welfare_labor 等）、6 个 bpm-fill-run skill 文件、22 个测试；build_result `OFFLINE_PASS`，probe-selftest exit 0、capability-tests exit 0（282 tests OK skipped=4，日志落盘）。**D23（source_manifest 覆盖）以本构建证据闭环，历史计数 1 保留。**
8. **台账纠偏**：progress.json baseline_document→冻结V3；authorization_scope 三段（save=不测保存…/browser=V3 授权链…/materials=原件只读…）；missing_inputs 已改"原件已供料+模板号缺口+其他七类留后续"；type_status 五类型分层表述（代码+离线/回放已验/本次原件端到端未验；02/04 NO_TABLE_DIALOG 未解与已实测分开）；rounds 补 7-10 + V3-R00；unclosed_defects 4 项如实。notes.md 追加 V3-R00 段。
9. **不预设业务答案**：case-model-deltas.json（DELTA-1..9）仅含规则建模（R=M+T、F=O+T 严格大于、油票仅覆盖、汇总单不计费、actual_trip_matches/oa_test_relations 分离、test_placeholder）；全文唯一金额字符串为边界反例"0.01元"；K/M/T/R/O/F 无任何数值。DELTA-8 模板身份登记缺口并列出不得冒充的历史单号清单；excel-structure 报告仅结构（汇总单 sheet、行3表头、去返成对、stray=误报禁清理），原件哈希由 case manifest 承载（xlsx 实算比对通过）。
10. **安全边界**：git HEAD 仍 `9299545`（零新 commit）、staged 0、案例目录与三 run 目录均 untracked 未 add；`.gitignore` 生效覆盖 `.pw-profile/` 与 `.local-session/`（git check-ignore 实证）；round-1 工件 grep 无 session_state/refresh_token/access_token/cookie 凭证值。
11. **发现的真实残点（D22）**：`verify_bpm_build.py` 产出的 build_result.json `missing_real_inputs` 仍无条件列 `specific_create_and_save_instruction`（及未按案例供料更新的 `current_material_directory`）——V3 §12.1 点名要求在"当前活跃能力声明和输出语义"修正为 fill_only 口径的表述仍在活跃输出中。台账侧已纠偏，输出语义侧未改。另 skill references（travel.md:50"真实保存待验收"、express.md:13）为能力层次描述性措辞，判可接受、列观察项。

## 二、逐条签注（D01–D27）

| ID | 状态 | 依据（A 本轮核验） |
|---|---|---|
| D01 | FAIL | 用户零内部工件：流程未到——CASE 链未开工（当日仅 3 个盘点/登录 run）；无证据链可验。计划内未完成。 |
| D02 | FAIL | 金额模型未执行（无 K/M/T/R/O/F 实算工件）；建模已入 DELTA-1（见 D27 证据）。 |
| D03 | FAIL | 未执行（O/T 集合未建立）。 |
| D04 | FAIL | CASE-01 未开工：73 文件仅字节级清单+4 同尺寸簇登记，未逐票核身/去重/税额口径核对。 |
| D05 | FAIL | 无"已核对"副本（find 实证 NONE）；原件 0 变更（本轮合规，回填属 CASE-02）。 |
| D06 | FAIL | 覆盖分支未实现（DELTA-1 仅登记差异；代码/schema 未动）。 |
| D07 | FAIL | 公出单模块未进入（当日无相关 run）。 |
| D08 | FAIL | 逐票对照报告未产出。 |
| D09 | FAIL | 两套关联表未产出（命名与分离要求已入 DELTA 清单）。 |
| D10 | FAIL | 登录/身份动态核验已合规（事实4），但模板身份=缺口（事实9）、字段复用矩阵/来源链未建——整体未达。 |
| D11 | FAIL | 正式链未执行（无请求登记→填写→回读链路工件）。 |
| D12 | FAIL | OA 填写未执行；本轮浏览器动作仅只读登录（合规边界，事实4）。 |
| D13 | PASS_DYNAMIC | 边界不变量全守：零类别扩展、零代码回退（staged 0、既有 M 文件为 r10 前存在）、三类/02/04 能力未动、无保存测试、公出单模块未碰（当日 run 集合实证）。 |
| D14 | PASS_DYNAMIC | R00 全项核实：归档状态（事实3）、无未知活页（事实4 stale 互证）、registry 盘点（事实5）、r10 三态+D23 闭环（事实7）、02/04 分类（事实8）、案例盘点+模板缺口（事实6/9）、台账纠偏（事实8）、失败字典原样带入 handoff 与 state。 |
| D15 | PASS_DYNAMIC | 现存结论均分层并绑定哈希（type_status 分层表述、R00 结论绑定 frozen rev2/60 键 manifest/build_result）；后续新结论按轮复验。 |
| D16 | FAIL | 覆盖/反例测试未实现（现有 282 测试不含 F>R/=</<边界等本轮新增反例）。 |
| D17 | FAIL | B1 部分具备（登录/身份证据），B2–B7 未执行。 |
| D18 | FAIL | A1–A9 汇总：仅 A1 前提与身份子项就绪，其余未达。 |
| D19 | FAIL | 新 session 使用验收未执行（CASE-08）。 |
| D20 | PASS_DYNAMIC | 接力机制实证：A 侧唯一后台 wait（task b3xkgm986）由 B finish 事件原生唤醒（seq 4→5，elapsed 2468s），status 后接棒；B 侧无轮询/自造通信证据；重型任务本轮仅一次统一构建。 |
| D21 | PASS_DYNAMIC | 当前源码绑定验证闭合：unittest 282 OK(skipped=4) 落盘、唯一 offline-verify run OFFLINE_PASS（selftest+capability exit 0）、manifest 60 键覆盖五类型 config/新模块/schema/skill/22 tests；本轮零探针改动（r10 前绿证据+本构建复核）。后续源码变更须重验。 |
| D22 | FAIL | 台账/授权口径已纠偏（事实8）；但活跃输出语义残留：build_result `missing_real_inputs` 仍含 `specific_create_and_save_instruction`（事实11，V3 §12.1 点名项）。小缺口，转下轮修复。 |
| D23 | PASS_DYNAMIC | 唯一总台账=progress.json 实读核验（事实8）：层次/负责人/哈希/缺口/下一项齐备，rounds 权威以 runs/events 为准；A 未改 B 台账。 |
| D24 | FAIL | 交付物仅盘点子集（manifest/结构报告/差异清单）；已核对工作簿、逐票清单与金额表、公出单报告、OA 结果、用户报告均未产出。 |
| D25 | PASS_DYNAMIC | 零 commit（HEAD 9299545）、零 staged、真实材料/凭证目录 untracked+ignored 实证（事实10）；工件无凭证值。 |
| D26 | FAIL | 案例闭环未达（CASE-01..08 未执行）；无 F≤R 阻断情形（未到校验步骤）。 |
| D27 | FAIL | 不变量已守：零预设业务答案（事实9）✔；正项（票面/Excel/公出单定期间与去返）未执行——CASE-01/03 范围。 |

## 三、结论

- 7 项 PASS_DYNAMIC（D13/D14/D15/D20/D21/D23/D25），19 项 FAIL（其中 18 项为 CASE 主线计划内未开工、1 项 D22 为活跃输出语义残点），0 项 EXEMPT/STATIC_ONLY/BLOCKED。
- B 的 R00 交接诚实、证据可复算、无越权写入；round 1 team-task done_when 1–5 经 A 独立复核全部成立。
- decision=rework：按 V3 §2.3 顺序派 round 2（CASE-01 为主 + D22 输出语义修复 + 承接登记项）。
- 新增失败计数：`review|content|active_output_semantics|D22`: 1（首败，按规则陪审）；历史 `review|content|source_manifest_coverage|D23`: 1 保留（本轮已闭环，不改零）。

## 四、A 侧留痕

- 哈希复算与反向枚举原始输出见同目录 `hash-recheck.json`。
- 本验收未修改 B 的任何业务产物、合同或 progress；未触碰案例原件（73 件 0 变更含本验收期间）。
