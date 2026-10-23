<!-- team-task-source id="src-77386fbb" sha256="77386fbbf5f96077e9d18f57c282891631ee061cfd244982fbbf2a5f8f380e17" status="open" -->
workflow_run: 9b0a6332fea8480283a898e5c01a6ed9
workflow_round: 2
failure_counts: {"review|content|internal_exception_unrecorded|D2": 1}

# 本次任务（round 2：补齐内层观测 + 消除两处死等 + 优化后整单实测与对照初版）

背景（round-01 已交付，勿重做）：动作级计时已在盘——attempt_025（automation/runs/20261021-131724-1c1aadbd/）29/32 零 mismatch、timing 159 条全 outcome=ok；两大死等已定论：① 关联单据/单据类型 `overlay_pick_row` 45822ms（events.jsonl L365）= `_pick_row` 选中态核验 `get_attribute`（stage1_browser_probe.py:2026，无显式超时）在「点行即关浮层、行 detach」上烧满默认 45s、:2029 `except Exception: pass` 吞掉；② 汇总行预算科目格 `cell_fill` 91803ms（L466）= `_fill_ng_cell` :1819 `inp.fill` 无显式超时在 readonly 列挂载的不可操作 input 上烧满 45s×2、:1823 `except Exception: continue` 吞掉，终值实际由预算联动（budget_pick，L487/L505 同函数 p-dialog 场景仅 1861/1893ms）带出并回读 matched。反向对照与离线复证 E1/E2 见 docs/路线与评估/2026-10-23-报销单填写耗时-动作级计时证据链.md。

本轮目标：让被内层吞掉的异常与重试在事件层可见（D2），消除上述两处纯死等且业务结果不退化（D4/D1），产出优化后真实整单结果与前后对照初版（D5/D6），并修订报告两处口径（D3）。全程只填不存。

## 待做条款

### 1. D2 观测补齐（只加记录，行为语义不变）
- 在 `_pick_row` 选中态核验的 except（:2029 一带）与 `_fill_ng_cell` 写入循环的 except（:1823 一带）**吞掉异常之前**，记录脱敏异常类型、该次调用耗时、继续/重试行为（追加 timing 子事件或等价字段）；异常仍按原流程处理（该 pass 仍 pass、该 continue 仍 continue）。
- 关键调用带尝试序号与总尝试次数：至少覆盖 `_fill_ng_cell` 激活循环（dblclick→fill→click→fill 逐次）与 `_pick_row` 核验链。
- 区分「函数正常返回 / 业务结果成功 / 内部捕获过异常」：外层 outcome=ok 时内层捕获须可见（如 inner_timeout 计数/子事件）；字段失败返回值（CELL_NOT_EDITABLE 等）进入业务结果事件。不得把约 45s 耗时直接改标 timeout——以实际捕获的异常为准。
- 离线验证（不连 OA）五类场景各有输出工件：正常成功、缺失元素、不可编辑元素、内部捕获后继续、再次尝试。

### 2. D4-a 单据类型浮层死等消除（dropdown 点行即关场景）
- 前置判据：区分两类场景——自动关闭的单据类型 dropdown 浮层（点行即关、行 detach）vs 需选中+确认的 p-dialog 弹表（单号弹表、预算联动，点行不关窗）。判据写明（如浮层容器类型/关闭行为），不得统一默认。
- 优化：`get_attribute` 选中态核验前加 count() 存在性守卫或显式短超时（repo 先例：`_cell_info` :1754-1756），不再对已确认消失的行等满默认 45s。**全局默认超时 45000 与防御性等待（600ms 轮询、Tab blur+3×回读）不动**——只做局部守卫/局部显式超时。
- 后置条件：dropdown 场景用适合该浮层的选中核验（如点击前后浮层状态、回显字段值、外层 overlay_pick 成功路径）；确认式弹表路径的现有「选中态+确认」验证保持不变且仍有效。
- 失败路径：核验不通过 → 记录并按现有失败处理停止/报告，不默认成功；不得以 force/JS 点击代替必要校验。

### 3. D4-b 预算科目格死等消除（readonly 挂不可操作 input）
- 前置判据：经规则与页面证据确认「该列值将由预算联动带出」（模板三预算列为只读回显；budget_pick 段 table_pick 回填并回读 matched 是既有事实）后，跳过通用写入循环对该列的重复 `inp.fill` 死等路径；或等效 actionability 预判/显式短超时。**不能仅凭「当前没有 input」判断只读**。
- 后置条件：该格实际值仍经预算选择、联动带出、严格回读验证（budget_respected=true 不变）；编辑态延迟挂载的合法编辑器（双击后才出现 input 的可写列）必须继续支持——跳过规则不得误伤此类控件（局部验证覆盖）。
- 失败路径同上：不一致 → 停止并报告。

### 4. D5 验证与优化后真实填写
- 每次改 `stage1_browser_probe.py` 后、真实填写前：`python -X utf8 stage1_probe_selftest.py` 全绿（新增观测/优化如需扩展 selftest 不变量一并交付）。
- 局部验证至少四类场景（离线 DOM 夹具或探针内嵌自检均可，工件留盘）：点击后消失的浮层、需选中+确认的表格弹窗、预算不可编辑回显字段、双击后才挂载的合法编辑器。
- 全绿后 `python -X utf8 fill_once.py` 跑一轮真实填写（只填不存）：新 attempt 完整工件（events.jsonl 计时/内层观测、stage1_result.json、回读、终局截图）；回读 29/32 零 mismatch 不退化、结构性留空三项（项目说明/行程说明/报销类别 submitType）如实单列不猜填。登录人工门或资源阻断则按 WAIT_HUMAN 留原始证据收口，不绕过、不以离线页面替代。

### 5. D6 对照初版 + D3 报告修订
- 优化前后同口径对照表（落盘 docs/ 或报告内新章节）：目标动作级（overlay_pick_row、cell_fill(预算科目) 优化前后 dur 与内层异常记录）+ fill 跨度/顶层段合计；列出登录、模板规模、网络/机器等已知差异；238s/330s/308.6s 均为历史单次观测如实并列；120～180s 是实验目标非承诺，未达到就报实际效果与原因。
- 死等消除证明须定位到目标调用（不再出现 ≈45000ms×N 的 dur，且内层异常/重试在新观测中可见），仅总时长变短不算。
- 报告修订两处：① 35.2s「未细包缝隙」桶中已埋点项单列——related_once cell 9.8s（原文已明示）与 screenshot 3 处 ~2.4s（L344/453/472，A 复算顶层 18 事件合计 286.0s，其中 screenshot 未单列）；② 附统一复算脚本（从 events.jsonl 重算顶层段/热点/缝隙），A 验收直接重跑。

## 范围与保留项（全部沿用，逐条红线）
1. 只填不存：保存/发送/流转/提交/上传/暂存/贴票/审批 一律禁点；no_save_guard 不绕过不削弱。
2. 600ms 防御轮询、Tab blur+3×回读、全局默认超时 45000 原值不动（本轮全部为局部守卫/局部短超时/跳过已确认无效路径）；不做全面缩短等待或状态驱动等待替换。
3. 不以 force/JS 点击代替必要校验；存在性判断类改动必须同时验证业务后置条件。
4. 不静默改账号、金额、日期、关联单据或预算目标；不放宽业务匹配规则制造通过；关联公出单替代仍留既有授权记录与人工眼审事项。
5. automation/.pw-profile/ 不进 git/日志/报告（事件只记条数）；legacy-ia2/ 只读；其他 session 既有改动不误归本轮、不回滚。
6. 单执行者/profile 锁、--no-proxy-server、ctypes 判活、Python -X utf8 沿用；浏览器被占用记资源阻断，不删活锁、不强关未保存表单。
7. events.jsonl 追加式、不修写历史；新 attempt 独立留证；异常记录脱敏（无凭证/完整敏感请求）。
8. 结构性留空三项不猜填。

## 验证方法
- selftest 全绿记录 + 五类离线观测验证工件 + 四类局部验证工件齐备。
- 优化后新 attempt：stage1_result.json 判 29/32 零 mismatch、SUCCESS_FILL_ONLY、budget_respected=true；events.jsonl 中两处目标动作 dur 显著下降且内层异常/尝试计数可见；确认式弹表/预算联动路径事件正常。
- 对照表与修订报告落盘，A 可用所附复算脚本从原始 events.jsonl 直接重算。

## done_when
1. D2：两处内层 except 吞掉前有脱敏异常类型+耗时+继续行为记录；尝试序号/总次数可查；五类离线验证工件在盘。
2. D4：两处死等消除（目标调用级证据），前置判据/后置条件/失败路径三件齐；确认式弹表与预算联动回读不受损。
3. D5：selftest 全绿 + 四类局部验证 + 优化后真实填写一轮完整工件（29/32 零 mismatch 不退化；或人工门 WAIT_HUMAN 留证）。
4. D6/D3：同口径前后对照表 + 报告修订（缝隙桶单列已埋点项、附复算脚本）落盘 docs/。
5. 全程红线零触碰（diff 与事件可证）。

criteria 对照：D1（不退化/红线）、D2（条款1）、D3（条款5②）、D4（条款2/3）、D5（条款4）、D6（条款5①）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261023-122409-77386fbb" contract_id="ctr-a10bb3f6" source_block_id="src-77386fbb" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-23）

**终态**：两处内层 except（`_pick_row` 核验链 / `_fill_ng_cell` 写入循环）吞掉异常前有脱敏异常类型+该次耗时+继续/重试行为记录，关键调用带尝试序号/总尝试次数，外层 outcome=ok 时内层捕获可见；两处死等消除有目标调用级证据（单据类型浮层 overlay_pick_row 45822ms、汇总行预算科目格 cell_fill 91803ms 不再出现 ≈45000ms×N）；selftest 全绿 + 五类离线观测工件 + 四类局部验证工件 + 优化后真实填写一轮完整工件（29/32 零 mismatch 不退化、budget_respected=true）；同口径前后对照表与报告修订（缝隙桶单列已埋点项、附统一复算脚本）落盘 docs/。全程只填不存，全局默认超时 45000 与防御性等待原值不动。

**本轮做**：
1. D2 观测补齐（只加记录、行为语义不变）：`_pick_row` except（:2029 一带）与 `_fill_ng_cell` except（:1823 一带）吞掉前记录脱敏异常类型、该次调用耗时、继续/重试行为（异常仍按原流程处理，该 pass 仍 pass、该 continue 仍 continue）；至少 `_fill_ng_cell` 激活循环（dblclick→fill→click→fill 逐次）与 `_pick_row` 核验链带尝试序号与总尝试次数；外层 outcome=ok 时内层捕获须可见（如 inner_timeout 计数/子事件）；CELL_NOT_EDITABLE 等字段失败返回值进业务结果事件。不得把约 45s 耗时直接改标 timeout——以实际捕获的异常为准。
2. D4-a 单据类型浮层死等消除：前置判据区分「点行即关、行 detach 的 dropdown 浮层」vs「选中+确认的 p-dialog 弹表」（判据写明，不得统一默认）；`get_attribute` 选中态核验前加 count() 存在性守卫或显式短超时（repo 先例 `_cell_info` :1753-1757）；dropdown 场景后置核验用适合该浮层的判据（浮层状态/回显字段/外层成功路径）；确认式弹表现有「选中态+确认」验证保持不变且仍有效；核验不通过→记录并按现有失败处理停止/报告，不默认成功。
3. D4-b 预算科目格死等消除：经规则与页面证据确认该列值由预算联动带出后，跳过通用写入循环对该列的重复 `inp.fill` 死等路径，或等效 actionability 预判/显式短超时（`select_option` 分支一并覆盖）；不能仅凭「当前没有 input」判断只读；该格实际值仍经预算选择、联动带出、严格回读验证（budget_respected=true 不变）；双击后才挂载的合法编辑器必须继续支持（局部验证覆盖不误伤）。
4. D5 验证与实测：每次改 `stage1_browser_probe.py` 后先 `python -X utf8 stage1_probe_selftest.py` 全绿再跑（新增观测/优化如需扩展 selftest 不变量一并交付）；五类离线观测场景（正常成功/缺失元素/不可编辑元素/内部捕获后继续/再次尝试）与四类局部验证场景（点击后消失的浮层/需选中+确认的表格弹窗/预算不可编辑回显字段/双击后才挂载的合法编辑器）各有输出工件留盘；全绿后 `python -X utf8 fill_once.py` 真实一轮（只填不存）：新 attempt 完整工件（events.jsonl 计时/内层观测、stage1_result.json、回读、终局截图），29/32 零 mismatch 不退化、结构性留空三项如实单列不猜填；登录人工门或资源阻断按 WAIT_HUMAN 留原始证据收口，不绕过、不以离线页面替代。
5. D6 对照 + D3 报告修订：同口径前后对照表落盘（目标动作级 overlay_pick_row / cell_fill(预算科目) 优化前后 dur 与内层异常记录 + fill 跨度/顶层段合计；列出登录、模板规模、网络/机器等已知差异；238s/330s/308.6s 均为历史单次观测如实并列，120～180s 是实验目标非承诺，未达到就报实际效果与原因）；死等消除证明定位到目标调用，仅总时长变短不算；报告修订两处（① 35.2s 缝隙桶单列已埋点项：related_once cell 9.8s 与 screenshot 3 处 ~2.4s（L344/453/472）；② 附统一复算脚本从 events.jsonl 重算顶层段/热点/缝隙，A 可直接重跑）。

**本轮不做**：不改全局默认超时 45000、600ms 防御轮询、Tab blur+3×回读（全部为局部守卫/局部短超时/跳过已确认无效路径；不做全面缩短等待或状态驱动等待替换）；不重做 round-1 已 PASS_DYNAMIC 的 D1/D7 交付物（D3 仅按条款5②修订两处口径）；不静默改账号、金额、日期、关联单据或预算目标；不放宽业务匹配规则制造通过；不修写 events.jsonl 历史；不回滚/误归其他 session 既有改动；不点任何保存类按钮；结构性留空三项不猜填。

**允许写**：`stage1_browser_probe.py`（D2 观测增量 + D4 两处局部守卫）、`stage1_probe_selftest.py`（仅增量新增断言，禁止放松既有断言）、repo 根新离线验证脚本（如 `stage1_offline_verify.py`）、`automation/offline-verify/`（离线 DOM 夹具与五类/四类工件）、`automation/runs/<run>/`（真实运行工件，events.jsonl 追加式）、`docs/路线与评估/`（对照表/复算脚本新文档 + round-1 计时报告两处口径修订与新章节，diff 可证）、`team-task.md` 合同区、`team-progress.md`、memory。
**只读**：`fill_once.py`、`automation/form-schema.json`、round-1 归档工件与 attempt_025、`templates/`、`patches/`、`automation/.pw-profile/`、`legacy-ia2/`。
**禁止**：`automation/.pw-profile/` 任何内容复制进 git/日志/报告（事件只记条数）；`legacy-ia2/` 追加；绕过或削弱 `no_save_guard`；以 force/JS 点击代替必要校验；伪造/复用旧 run id 或 attempt 冒充新证据。

**红线**（AGENTS.md 全量并入 + 任务「范围与保留项」8 条）：①只填不存（保存/发送/流转/提交/上传/暂存/贴票/审批一律禁点）；②`.pw-profile` 活体 token 不外泄；③结论以 `automation/runs/<run>/` 工件为准（events.jsonl 追加式/evidence/stage1_result.json），聊天叙事为辅，异常记录脱敏；④`legacy-ia2/` 只读。附加：存在性判断类改动必须同时验证业务后置条件；单执行者/profile 锁、`--no-proxy-server`、ctypes 判活、`python -X utf8` 沿用；浏览器被占用记资源阻断，不删活锁、不强关未保存表单；改探针后必须 selftest 全绿再实测。

**风险 envelope**（P0.5 已登记）：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。

**done_when（带验证）**：
1. D2 内层观测 → 验证：两处 except 吞前记录在场（代码 diff + 五类离线工件）；尝试序号/总次数可查；新 attempt events.jsonl 中内层异常可见（外层 ok 时 inner 计数/子事件非空），且无「把 45s 耗时直接改标 timeout」的造假标记。
2. D4 两处死等消除 → 验证：目标调用级证据（优化后 overlay_pick_row / 预算科目 cell_fill 不再出现 ≈45000ms×N，内层异常/尝试计数可见）；前置判据/后置条件/失败路径三件齐；确认式弹表与预算联动路径事件正常、budget_respected=true。
3. D5 → 验证：selftest 全绿记录 + 五类离线观测 + 四类局部验证工件齐备 + 优化后真实一轮完整工件（29/32 零 mismatch、SUCCESS_FILL_ONLY、budget_respected=true）或人工门 WAIT_HUMAN 留证。
4. D6/D3 → 验证：同口径对照表 + 报告两处修订 + 复算脚本落盘 docs/，复算脚本从原始 events.jsonl 重算结果与报告一致。
5. 红线零触碰 → 验证：git diff 与 events.jsonl 可证（无保存类点击、全局 45000 与防御等待原值在、.pw-profile 不外泄）。
<!-- /team-task-contract -->
