<!-- team-task-source id="src-82e4775e" sha256="82e4775ed8f1d61bf51e9a68a0d3cfea470e029a48ff7f6b57a488ce54f159db" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 8
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 8 —— B6 独立复核 + B7 终局标记 + CASE-08 新 session 使用验收 + 用户报告与最终交付（潜在收尾轮，全程只读/离线，不新建业务页不保存）

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 8，合同 `BPM-MATERIALS-20261026-V3`（重点 §6 正式路径连续衔接、§10.3 B6/B7、§10.5/§9 CASE-08、§12.3 交付清单、§13 完成定义）。round 1–7 已交付并经 A 验收 20 项 PASS_DYNAMIC：CASE-01/02 事实与回填（`automation/runs/20261026-115500-v3r02-case01/`、`20261026-131000-v3r03-case02/`）、CASE-03 逐票公出单对照（`20261026-143340-v3r04-case03/`，12 MATCHED Σ221.02 + 15 NO_MATCH Σ265.91）、round-5 卫生修复、CASE-05/06 模板与计划（`20261026-172300-v3r06-template-plan/`，模板 15426095951、fill-plan v1.0 sha256 0d5b22cd…/plan_hash 1b3ba0b9…）、CASE-07 正式入口真实填写+受限随机占位关联（`20261026-181500-v3r07-fill/`、`20261026-183000-v3r07-fill/`，v1.1 sha256 6c9d1b6f…，种子 6074a75771428d7e→第 6 行 12024070132，SUCCESS_FILL_ONLY、save_status=NOT_ATTEMPTED、未保存测试页已干净关闭：编制中/无单号/无 UUID）。**本轮不重填、不重开业务页；全部工作为独立复核、新 session 使用验收、终局标记与交付。**

剩余 7 条 FAIL 判据即本轮对象：D01（agent 自行全链、用户不编内部 JSON）、D11（§6 正式路径连续衔接+skill 覆盖完整操作）、D17（B6/B7）、D18（A1–A9 汇总，随专项证据翻转）、D19（CASE-08）、D24（§12.3 交付物+用户报告）、D26（§13 完成定义，A 终局整体核签）。

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环，计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. B6 独立复核（V3 §10.3 B6；供 D01/D11/D17/D18/D26）
- 由**另一 agent/独立过程**（建议 mc-expert 只读陪审或全新 subagent，不得复用本轮实现的对话上下文）依据**真实原件、Excel、匹配报告、计划和 DOM 证据**重新核对：73 原件→52 唯一→K=1438/M=1438.00/T=486.93/R=1924.93/O=2031.17/F=2518.10/coverage_margin=593.17 与严格门槛；Excel 行 4–23 逐行 F/G/H/I 与原件票面；27 票逐票公出单对应（12 MATCHED/15 NO_MATCH）；模板复用边界（template 14 仅身份/预算/收款）；计划 v1.0 三向闭合与 v1.1 差异 9 簇；B5 回读金额四向与占位分离。**全覆盖审查结果，不得只读 success 摘要或拿计划自证计划**；发现差异逐项列出（文件/页/cell/单据及影响），可当场修复的修复并复验，不可修复的如实登记。
- 独立复核报告（含其输入清单、复算过程、结论、与既有交付的差异表）+ 哈希绑定落本轮 run 目录。

### 2. CASE-08 新 session 使用验收（V3 §10.5/§9；供 D19/D01/D11）
- 安排**未参与实现的新 session**（全新 subagent/独立过程，零上下文继承），输入清单**仅限**：冻结合同路径、`.claude/skills/bpm-fill-run/SKILL.md`（及其 references）、用户指定模板单号 15426095951、原件目录 `feature01-细化报销skill/12月公出-发票/`、业务规则（合同 §4/§5 已含）。**禁止喂** fill-plan v1.0/v1.1、FactSet、OCR 复核 JSON、私有驱动或任何内部生成 JSON；输入清单本身落盘可审计。
- 该 session 须自行完成：理解原件并复算事实链（至少 K/M/T/R/O/F/coverage 与 52 去重）→ 按正式入口（bpm_materials/bpm_plan 或 skill 指引路径）生成**自己的** v1.0 计划 → `--validate-only` 通过 → 与已交付 v1.0 核心表/金额比对（此时才把已交付计划作为**事后审计证据**提供，标注"仅比对用"）→ 只读核验既有证据（缓存模板快照、B5 回读快照、逐票匹配报告）。
- 填写已完成且页面已关：走"已完成填写"分支——**只读独立核验，不重复新建业务页、不绕过 registry、不改旧单、不保存**；如需登录/模板活读，走 `bpm_login.py`/`bpm_template.py --live` 只读正式入口并错峰（单 profile 单执行者），不可用时以缓存快照只读核验并如实记录。
- 若新 session 暴露 skill/合同可操作性缺口：修 **skill 文档**（不改冻结合同）后换**另一个**新 session 重试；验收标准=新 session 仅凭允许输入能走通"理解→复算→计划→验证→只读核验"。
- 其理解/复算/计划/验证/核验全套记录（含 transcript 引用或工件）+ 哈希落 run 目录。

### 3. B7 终局标记与页面状态交接（V3 §10.3 B7；供 D17/D24）
- 在 `automation/template-materials-program/progress.json` 台账终局标记本真实案例考核：**fill_only 完成**，层次="真实控件已验证·填写+回读·未保存"（round-7 已建条目本轮收口），并记录：未保存状态结论（编制中、无 bizNumber/uuid、own_test_page_close）、run/attempt 索引（r06 计划 + r07 两 run）、全部证据路径索引、页面盘点（无遗留业务页、锁释放、registry FORM_INTENT 无 SAVE_INTENT）。无保存/提交/旧单修改/公出单重新占用，逐项明确声明。

### 4. §12.3 交付清单 + 用户报告（供 D24/D26/D11）
- 产出**最终交付 manifest**（机器可读 JSON）：逐项列 §12.3 全部交付物（原件 manifest/分类去重索引/提取复核记录与哈希；已核对工作簿副本+cell 变更+重算与独立复算；逐票凭据清单与 K/M/T/R/O/F/margin/严格门槛；公出单查询/详情证据+逐票对应报告双版本+缺失/歧义/重复清单；模板快照/复用矩阵/事实层/业务规则/受限测试关联依据/可执行计划与验证结果/随机占位单独列表；真实 OA 执行结果/独立 DOM 快照/diff/终局截图/未保存页盘点/独立审查报告；每轮交接）的路径+sha256+内容要点，A 将逐项抽验。
- 产出**用户报告**（用户可读 Markdown，落 `feature01-细化报销skill/` 或本轮 run 目录并在 manifest 引用）：实际模板/类别（travel、15426095951、三员=陈晶/116070053）、公里与通行费构成（K→M、T 27 票、R 组成）、待报额与票据覆盖（R=1924.93、F=2518.10、margin 593.17、严格大于通过）、每张票对应公出单结果摘要（12 匹配单号+15 无匹配，指向 CASE-03 报告）、真实填写状态（SUCCESS_FILL_ONLY、未保存、无新单号、测试页已关、占位关联 12024070132 为随机测试且与真实对照分离）与全部证据链接；**不宣称重新报销成功**；剩余观察项如实列出。
- **skill 收口**：核对 `.claude/skills/bpm-fill-run/SKILL.md` 覆盖"真实 PDF/Excel→模板→计划→真实填写→回读→交付"完整正式操作（含受限测试关联的正式生成路径——round-7 已将 oa_test_relations 纳入 bpm_plan/schema），不把回放 JSON CLI 当最终用户入口；缺口仅补文档与 references，不改冻结合同。

### 5. 证据、台账与交接
- 新 run 目录 `automation/runs/<时间戳>-v3r08-final/`：events.jsonl、B6 报告、CASE-08 输入清单与全套产出、最终 manifest、用户报告、B7 终局标记；凭证原值不入任何工件。
- 源码/schema/测试若改动：全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify；纯文档/skill md 改动说明即可不新构建。默认不 commit；73 原件第 8 轮零漂移复核。
- 遗留观察项（P3×6+3 旧）本轮逐条关闭或登记去向；P6 收尾 + finish；handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- **本轮零业务写入**：不新建报销页、不重填、不保存、不动 registry 意图、不改旧单；浏览器只允许只读正式入口（bpm_login/bpm_template live）且错峰。
- 单 profile 单执行者；不导航/关闭其他执行者页面；A 不同时占用浏览器。
- 真实材料/凭证不入 Git；Python `-X utf8`、cwd 仓库根、不走 VPN/Clash。
- 冻结合同不可修改；skill/文档可补；B6/CASE-08 发现的差异不得静默吞掉。

## done_when
1. B6 独立复核交付：独立过程从原件到 DOM 全链重算复核（非摘要互证），差异清单完整（或明确零差异），报告+输入清单+哈希入 run 目录；发现问题已修复复验或如实登记。
2. CASE-08 交付：新 session 输入清单仅含允许项（可审计证明未喂内部 JSON），其自行产出理解/复算/自有 v1.0 计划/validate-only 通过/与交付链比对/只读核验记录全套入 run 目录；skill 可操作性缺口（如有）已修复并经另一新 session 复验。
3. B7 终局标记入台账：fill_only 完成+页面状态交接（未保存/无单号/无 UUID/页面盘点/run 索引/证据索引/无保存类动作声明）。
4. 最终交付 manifest 覆盖 §12.3 全项（路径+sha256+要点）；用户报告交付且不宣称重新报销成功；skill 覆盖完整正式路径。
5. 新 run 证据齐全；73 原件第 8 轮零漂移；有代码改动则全量 unittest 通过+唯一新 offline-verify；P6 + finish 交接哈希一致；失败字典 {D23:1, D22:1} 原样带入。
<!-- /team-task-source -->
