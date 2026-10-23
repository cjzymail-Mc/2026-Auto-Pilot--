<!-- team-task-source id="src-15c8cfe6" sha256="15c8cfe66b601aaf152fad372e251d569ee564514a30883a6b6eda65f828a80d" status="open" -->
# 本次任务

为 BPM 报销单探针建立**动作级计时证据链**，并据此解释当前两大耗时疑点——关联单据类型选择处的 ~45 秒间隙、汇总行填写 ~101 秒——为后续的预算依赖顺序调整与状态驱动等待提供实测依据。本轮只加观测、不改行为。

## 范围

1. **埋点**：在 `stage1_browser_probe.py` 关键动作处增加计时记录（打开选择器、等待候选、点击选项、确认、回显、字段核验），每条含开始/结束/耗时/重试次数/异常类型，追加写入当轮 `automation/runs/<run>/events.jsonl`；"捕获异常后继续"的超时单独标记，与正常耗时区分。
2. **离线分析先行**：先用现有工件（最新完整填写轮的 `events.jsonl`、evidence 文件时间戳、对应代码路径）列出 45 秒间隙与 101 秒汇总行的假设清单，再以新埋点数据逐条证实/证伪。
3. **实测一轮**：埋点自检通过后，经 `python -X utf8 fill_once.py` 跑一轮真实填写（只填不存），产出带计时的 events.jsonl 与截图工件。若登录态过期需人工扫码，按人工门（WAIT_HUMAN）收口并留原始阻断证据，不绕过。
4. **耗时分析报告**：落盘 `docs/`，给出整单耗时分段分解表、45 秒间隙定论（发生在哪个动作、哪类等待、可否安全缩短）、汇总行 ~101 秒时间构成；证据不足处明确标注，不臆断。

## 保留项（本轮一律不动）

- 防御性等待（600ms 轮询、Tab blur+3×重读）与默认超时参数：保持原值，只测量不优化。
- 填写业务逻辑、字段填写顺序、预算链顺序、词表/金额归一规则：不改。
- `no_save_guard` 及保存/提交/上传/暂存类守卫：不可绕过、不可削弱；全程只填不存。
- 现有未提交工作区改动（`stage1_browser_probe.py`、`fill_once.py` 等的 M 状态）：在其基础上增量修改，不回滚不重写。
- `legacy-ia2/` 只读；`automation/.pw-profile/` 不进 git/日志/报告。
- 不把 `form-schema.json` 加载进主探针、不做状态驱动等待改造（属后续任务，本轮仅为其产出证据）。

## 验证方法

- 改动探针后硬性前置：`python -X utf8 stage1_probe_selftest.py` 全绿。
- 埋点格式自检：不连 OA 冒烟验证新增计时事件为合法 JSONL 追加、字段齐全。
- 实测轮：`python -X utf8 fill_once.py` 完整走完，新 run 的 `events.jsonl` 中关键动作均有耗时记录，回读与终局截图工件齐备。
- 报告每个结论可指回具体 `events.jsonl` 行或 evidence 文件。

## done_when

1. `stage1_browser_probe.py` 含动作级计时埋点（开始/结束/耗时/重试次数/异常类型；异常超时单独标记），`stage1_probe_selftest.py` 全绿。
2. 至少一轮带埋点的真实填写完成（或因登录人工门以 WAIT_HUMAN 收口并留原始证据），当轮 `events.jsonl` 含完整计时数据。
3. 耗时分析报告落盘 `docs/`：整单耗时分段分解、45 秒间隙定论（或明确声明证据不足）、汇总行 ~101 秒构成，结论全部可回溯到工件。
4. 填写行为零变化：防御性等待参数、字段顺序、保存守卫未被修改（diff 可证）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261023-102207-15c8cfe6" contract_id="ctr-d1e7876b" source_block_id="src-15c8cfe6" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-23）

**终态**：`stage1_browser_probe.py` 具备动作级计时埋点（每动作开始/结束/耗时/重试次数/异常类型，捕获后继续的超时单独标记，ms 粒度，追加进当轮 `automation/runs/<run>/events.jsonl`），selftest 全绿；完成一轮带埋点的真实填写（只填不存）或以 WAIT_HUMAN 收口；`docs/` 落盘耗时分析报告（整单分段分解表、45s 间隙定论或证据不足声明、汇总行 ~101s 构成，结论可回溯 events.jsonl 行/evidence 文件）；填写行为零变化（diff 可证）。

**本轮做**：
1. 埋点（仅增量观测代码）：计时段覆盖 `_phase_fill_ng` 各 section、`_pick_option`（开浮层/轮询/点选）、`_fill_ng_cell`（激活/写入/回读）、`_cell_table_pick`、`_overlay_search_pick` 子步（dump/搜索/行点/确认）、`_fill_ng_table_row` 逐列、`_try_budget_pick`、goto/截图。
2. 离线假设清单先行：45s 间隙（候选：`_pick_candidates` 无显式超时 `element_handle()`、`_dialog_close_guarded` 默认超时 `click()`）与 147s 间隙（明细 2 行+汇总行逐列无事件）假设逐条列于报告，再以新埋点数据证实/证伪。
3. 实测一轮：`python -X utf8 fill_once.py`（主线 run 证据链追加 attempt_025）；登录过期回落扫码 → WAIT_HUMAN 收口并留原始阻断证据。
4. 报告落盘 `docs/`（含分段分解表、45s 定论、101s 构成、证据不足处显式标注）。

**本轮不做**：不改任何等待数值/默认超时/字段顺序/预算链顺序/词表/金额归一；不做状态驱动等待改造；不把 form-schema.json 加载进主探针；不回滚现有未提交工作区改动；不点任何保存类按钮。

**允许写**：`stage1_browser_probe.py`（增量埋点）、`docs/` 新报告、`automation/runs/<run>/` 运行工件、`team-task.md` 合同区、`team-progress.md`。
**只读**：`fill_once.py`、`fill_plan.json`、`automation/form-schema.json`、`stage1_probe_selftest.py`（仅当埋点确需适配时允许增量新增断言，禁止放松既有断言）。
**禁止**：`automation/.pw-profile/` 任何内容复制进 git/日志/报告；`legacy-ia2/` 追加；绕过或削弱 `no_save_guard`。

**红线**（AGENTS.md 全量并入）：①只填不存（保存/发送/流转/提交/上传/暂存/贴票/审批一律禁点）；②`.pw-profile` 活体 token 不进 git/日志/报告；③结论以 `automation/runs/<run>/` 工件为准（events.jsonl/evidence/stage1_result.json），聊天叙事为辅；④`legacy-ia2/` 只读。附加：防御性等待（600ms 轮询、Tab blur+3×重读）与 45s 默认超时保持原值（只测量不优化）；改探针后必须 `python -X utf8 stage1_probe_selftest.py` 全绿才能实测。

**风险 envelope**（P0.5 已登记）：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。

**done_when（带验证）**：
1. 埋点在场 + selftest 全绿 → 验证：selftest 退出码 0；diff 显示探针改动仅为观测性增量。
2. 一轮带埋点实测完成（或 WAIT_HUMAN 收口留原始证据）→ 验证：新 attempt 的 events.jsonl 含 timing 事件（合法 JSONL、字段齐全）+ 终局截图在 evidence/。
3. 报告落盘 docs/ → 验证：分段分解表各段之和≈总耗时、45s 有定论或明确证据不足、101s 有构成分解，每条结论可指回工件。
4. 行为零变化 → 验证：git diff 无等待数值/业务逻辑/字段顺序/守卫改动，diff 摘录附于报告。
<!-- /team-task-contract -->
