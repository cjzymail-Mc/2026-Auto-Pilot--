<!-- team-task-source id="src-563fa8e5" sha256="563fa8e545f2b5fdfbe65afb845d8db2b6fbb181ddaaf90b977ff10f3ab73aa0" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 2
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 2 —— CASE-01 真实原件全量理解（票面级事实/去重/期间核定）+ D22 活跃输出语义修复 + 承接登记项

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 2，基线为冻结合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md`）。round 1（R00 盘点，A 验收 7 项 PASS_DYNAMIC）已交付：73 件案例清单（`automation/runs/20261026-100322-v3r00-inventory/case-file-manifest.json`，字节全唯一、4 同尺寸簇待核身）、Excel 只读结构（`汇总` 单 sheet、行3 表头、G 列过路费、去返成对）、差异清单 DELTA-1..9、台账纠偏。本轮按 V3 §2.3 第 1 步开工真实原件理解；Excel 回填（CASE-02）默认下轮，本轮提前完成 CASE-01 且资源允许可同轮开工但不作 done_when 必须项。

**历史累计失败字典（不清零、不改名、不隐去；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

- D23（source_manifest 覆盖）：round 1 已以 60 键唯一构建闭环，计数保留为历史。
- D22（活跃输出语义）：**本轮修复项**——`verify_bpm_build.py` 产出的 `build_result.json` `missing_real_inputs` 仍无条件列 `specific_create_and_save_instruction`（V3 §12.1 点名要求修正的表述；证据 `automation/offline-verify/materials-v3r00-20261026-101500/build_result.json`）。修复属首败，按 team-task 规则走失败陪审记录后再实施。

## 待做条款

### 1. D22 修复：统一构建输出语义 fill_only 化（小改面，先陪审记录）
- `verify_bpm_build.py` 及相关 config：`missing_real_inputs` 输出语义改为区分场景——当前 V3 fill_only 主线下 `specific_create_and_save_instruction` 不再作为无条件 missing 项（可按构建参数/配置声明为"非本轮要求"或不列入）；`current_material_directory` 按真实案例供料状态表达（已供料时不得仍报缺失）。`real_save_verified=false` 保留"未测"语义不改。
- 配套测试更新（现有 tests 对应断言同步），不放宽任何保存守卫、不改 SaveController。
- 修复后跑全量 `python -X utf8 -m unittest discover -s tests` 与唯一新 offline-verify run（命名 `materials-v3r02-<时间戳>`）冻结证据；source_manifest 覆盖口径维持 60 键标准，新增/修改文件如实入清单。

### 2. CASE-01：73 件原件全量票面级理解（本轮主体，重型任务错峰）
- **全部消费**：case manifest 73 件每件有分类结论（真实油票 / 通行费发票 / 收费票据 / 票据汇总单(票据) / 行程汇总单 / 重复副本 / 其他），产出去重索引：所有文件 → 唯一票据身份映射（同票不同扫描去重；相同金额不同票不得误删；文件数≠可计费票数）。
- **逐票票面事实**：每张唯一票据登记票号（前导零/长票号保字符串）、开票日期、实际通行日期/时间、路线/起讫、金额口径（税前/税额/价税合计分别记录不混用）、出/入口等关键值；关键值必须回原 PDF 页真实复核（记录页码/区域定位 + 截图或文本抽取依据），不以文件名或 OCR 单次返回直接采信。4 个同尺寸簇逐票核身（内容比对给出去重/保留结论）。
- **油票 5 份**：逐份核实价税合计、开票方、日期、票号；模糊/作废/红字按实际登记。
- **汇总单交叉核对**：每组"通行费电子票据汇总单(票据)/(行程)"与其独立发票做数量+金额交叉核对；不一致处查明或登记为未解冲突（未解冲突不得计入 T/O）。
- **期间/年份核定**：从票面通行日期/区间 + Excel 行日期核定实际期间与去返方向；不按目录名/文件名猜；开票日≠通行日分别记录；跨年/目录与票面不一致留差异与裁决依据。
- **多页/一页多票**：现有 `bpm_extraction.py` 一页多票显式拒绝分支保持；本批若遇该形态按拒绝分支处理并登记，不静默只取第一张。
- 产出：机器可读票据事实层（逐票 JSON，含每值来源 path/page/sha256）+ 人工可读报告，落 `automation/runs/<新run>-v3r02-case01/`；K/M/T/R/O/F 数值只能从票面/单元格推导或标缺口，**零预设业务答案**。
- 原件全程只读（对齐 case manifest 与维护快照哈希）；派生文件不写回原件目录；PDF 渲染/OCR 按批处理、同一时段最多一个重型任务。

### 3. 承接登记项（小改面）
- 02/04 `automation/document-types/*.json` `required_observations` 回填 + 对应 notes.md 修订（round 1 登记的 r10 遗漏）；改面限于该两类型 config/notes。
- 台账（progress.json/notes.md）记录 R00-report §4 多票断言测试指针勘误（承重在 tests/test_bpm_extraction.py::D18；冻结件 R00-report.md 不改）。
- 模板身份缺口维持 PENDING_HUMAN_NONBLOCKING：本轮可从既有归档/原报销单上下文做只读检索核实，仍无果则如实保留，不冒充、不阻塞 CASE-01。

### 4. 台账与交接
- progress.json：work_packages/CASE-01 状态、验证层次、unclosed_defects 更新（D22 修复后状态、未解冲突、模板缺口）；rounds 补 V3-R02。
- team-task P0–P6 完整流程、必要独立审查、finish 交接；交接哈希绑定实际文件；失败字典原样携带（D22 若未修复沿 key 累计为 2）。

## 保留项与边界
- fill_only：不测保存、不验收保存成功/新单号/重开；守卫与 registry 保护原样。
- 本轮浏览器动作仍仅限只读（如需登录例行核验）；公出单模块查询与 OA 填写仍留后续轮。
- Excel 原件不改不回填；CASE-02 回填副本非本轮必须项。
- 不接入其他类别扩展、不重做三类回放、不做模板普查；02/04 改面仅限第 3 条登记项。
- 默认不 commit；真实材料不入 Git/通用测试夹具；凭证与会话元数据不入工件；单 profile 单执行者。
- Python 一律 `-X utf8`，cwd 仓库根；改过 `stage1_browser_probe.py` 先 selftest 全绿再实单。

## 验证
- D22：新 offline-verify run 的 build_result 输出不再把 `specific_create_and_save_instruction` 列为当前主线 missing 项；全量测试绿；对应测试断言更新。
- CASE-01：73 件分类结论无遗漏；去重索引双向可查（文件↔唯一票据）；每票事实含来源定位与哈希；汇总单交叉核对结论明确（一致/差异/未解）；期间核定有票面+Excel 依据链；4 同尺寸簇有核身结论；人工可读报告可读完整。
- 原件 73 件哈希与 round 1 manifest 逐件一致（零变更）。
- 台账/交接：progress.json 更新属实；handoff 哈希与实物一致；失败字典承接完整。

## done_when
1. D22 修复落地并经唯一新 offline-verify run 冻结：`missing_real_inputs` 语义 fill_only 化、配套测试更新、全量 unittest 全绿；或如实登记未闭合原因（沿 key 累计）。
2. CASE-01 全量完成：73 件分类+去重索引+逐票票面事实（关键值回原页复核）+油票逐份核实+汇总单交叉核对+4 同尺寸簇核身+期间/年份核定依据链，机器可读+人工可读双落盘；未解项如实登记，零预设业务答案；原件零变更。
3. 承接项完成：02/04 required_observations 回填+notes 修订；台账记录 R00-report §4 勘误；模板身份缺口状态更新（仍缺则保留 PENDING_HUMAN_NONBLOCKING）。
4. progress.json 台账更新至 V3-R02；P6 收尾 + finish 交接，handoff 哈希与实物一致；历史失败字典 `{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}`（或 D22 累计后新值）原样带入。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261026-112422-563fa8e5" contract_id="ctr-fe416d87" source_block_id="src-563fa8e5" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-26 · run 20261026-112422-563fa8e5）

**终态**：round 2 以实物证据完成 D22 活跃输出语义修复（fill_only 化并冻结于唯一新 offline-verify run）、CASE-01 73 件真实原件全量票面级理解（分类/去重索引/逐票事实/汇总单交叉核对/同尺寸簇核身/期间核定依据链）、承接登记项（02/04 回填+勘误+模板缺口状态）与台账 V3-R02 纠偏，独立复核通过后 finish 交接 A；零预设业务答案、原件零变更；不宣称 V3 合同整体完成。

**本轮做**：team-task.md 待做条款 1–4 全部——D22 修复（verify_bpm_build 输出语义 missing/waived/supplied 三层参数化+配套新测试+全量 unittest+唯一 `materials-v3r02-<时间戳>` 构建）；CASE-01（73 件分类结论+文件↔唯一票据去重索引+逐票票面事实含页/坐标/哈希锚点与关键值回原页复核+油票 5 份逐份+汇总单(票据)/(行程)交叉核对+4 同尺寸簇核身+期间/年份核定依据链，机器可读+人工可读双落盘 `automation/runs/<新run>-v3r02-case01/`）；02/04 config `required_observations` 回填+notes 修订+台账记录 R00-report §4 勘误+模板身份缺口只读检索与状态更新；progress.json V3-R02+P6 收尾+finish。

**明确不做**：OA 业务行写入/保存/提交/上传/贴票/OA 关联选择；公出单模块查询；Excel 原件回填或修改（CASE-02 回填副本不承诺、默认下轮）；三类历史回放重跑；其他类别扩展与模板全量普查；git commit/push；修改冻结 V3、round-1 已冻结产物（R00-report.md、frozen-artifact-hashes.json rev2、round-01 归档）、旧维护归档、legacy-ia2/；代扫码；预设 K/M/T/R/O/F 范围裁定、票数、公出单号、模板号等业务答案。

**允许写**：`verify_bpm_build.py`（仅 D22 输出语义参数化与分层，不触碰测试执行/manifest 收集逻辑）与 `tests/` 新增对应断言文件；`automation/document-types/office_supplies.json`、`welfare_labor.json`、`office_supplies.notes.md`、`welfare_labor.notes.md`（仅 required_observations 回填与观察状态修订）；`automation/template-materials-program/progress.json` 与 `notes.md`；`automation/runs/<新run>/`（CASE-01 证据、提取脚本、登录例行 run 如需）；`automation/offline-verify/materials-v3r02-<时间戳>/`（唯一构建）；根 `team-progress.md`、根 `team-task.md`（仅追加本合同块）、根 `handoff-input.json`（finish 用）。

**只读**：`feature01-细化报销skill/12月公出-发票/`（73 件原件+xlsx，CASE-01 前后各一次全量哈希对账）；`automation/runs/` 既有 run（含 round-1 工件与四链）；`automation/task-registry/`；`automation/.pw-profile/`（凭证原值不读不复制）；`automation/.local-session/`（仅元数据；bpm_login.py 例行原子更新按 round-1 自主裁决②沿用）；`.team-workflow-state.json`（仅 helper 写）。

**禁止**：删除/回退他人未提交工作；git add -f/commit/push；把凭证或会话元数据写入任何工件、日志或报告；强删 profile 锁、导航或关闭其他执行者未保存页；对 round-1 已冻结产物的任何改写（勘误走台账新记录，不回写冻结件）；把 CASE-01 观测汇总值当业务最终口径（K/M/T/R/O/F 的范围裁定与覆盖门槛判定留 CASE-02/03/04）；绕过或放宽任何保存守卫与 SaveController。

**红线**：team-task 四红线（销毁性/不可逆操作；对外交付物触碰合规红线；同 failure_key 第 3 次失败熔断；推翻 KB 已封决策）；根 AGENTS.md 五条红线；本轮浏览器动作仅限只读登录/身份例行核验（如需），零业务行写入、零保存、零提交、零上传、零关联选择；重型任务（PDF 批量提取/渲染、全量测试、offline-verify 构建）串行错峰，同一时段最多一个。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE；一手证据=team-workflow helper runtime_evidence（B=session c05e555a-0c54-4418-96a2-d92a751dfbc9，model glm-5.3，transcript 已由 helper 核验落盘，round-2 enter/permit seq9 一致）。

**裁量推荐（B+AUTO 接管，逐条记入 team-progress 自主裁决区）**：D22 按 P1 失败陪审候选①实施（三层语义，缺省 fill_only；`exact_history_template_number` 真缺保留）；CASE-01 提取脚本落 run 目录复用 `bpm_extraction.extract_pdf_text`/`file_hash`/`render_to_files`，不改 `bpm_extraction.py` 本体（确需改则超出本轮代码写面，登记移交）；K/M/T/R/O/F 仅报观测值推导（T=唯一通行费票合计、O=唯一油票合计、K/M=Excel 单元格合计）并明示范围裁定留 CASE-02/03/04；汇总单交叉核对以 汇总单号+票据号码 双键；文件名后缀"2"≠重复，以票号/汇总单号定案；0906 目录 0905 文件名差异登记并以票面为准；未解冲突不计入 T/O；登录例行核验一次即可（复用 round-1 会话记录不必新探，除非构建或执行需要）。

**done_when 与验证**：D1–D4 逐条对应 team-task.md done_when 1–4 原文。验证方式：D1=新构建 build_result.json（fill_only 缺省下 `missing_real_inputs` 不再含 `specific_create_and_save_instruction`；`current_material_directory` 按 `--materials-dir` 供料状态分层）+全量 unittest 落盘日志+新测试在列；D2=CASE-01 逐票 JSON（每值 path/page/bbox/sha256 锚点）+人工报告+73 件前后哈希对账零变更+分类/去重双向索引+交叉核对结论+4 簇核身结论+期间核定依据链；D3=02/04 config/notes diff+台账勘误记录+模板缺口状态更新；D4=progress.json V3-R02+finish 交接哈希绑定实物+失败字典原样带入（D22 未修复沿 key 累计为 2）。验收按 team-task 四态签注；STATIC_ONLY 不冒充完成，浮至交付待确认项。
<!-- /team-task-contract -->
