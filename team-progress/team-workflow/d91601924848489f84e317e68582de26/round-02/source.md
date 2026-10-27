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
