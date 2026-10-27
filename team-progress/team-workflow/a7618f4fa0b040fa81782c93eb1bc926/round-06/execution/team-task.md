<!-- team-task-source id="src-b401214d" sha256="b401214dffa10e3c04e78977335b8b8816a246d01c975f2a8d19961bae7eff71" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 6
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 6 -->
# 本次任务：W06 前置 —— 执行串联与 skill 链路增补（+live 模板读取尝试 + R5-P2 顺带）

总目标背景（自足）：多轮交付"用户仅给模板单号+原始资料，agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。已交付 W00-W05（全离线）：总台账、双根契约（`bpm_materials.py`）、原件理解（`bpm_extraction.py`）、事实与对账（`bpm_facts.py`）、计划衔接（`bpm_plan_generate.py`+`fill_once.py` 阶段机至 PLAN_READY）、请求与模板决策（`bpm_request.py`：register_request/resolve_template/build_reuse_matrix/identify_unknown）。构建源清单 glob 自动冻结。本轮把"计划→执行"最后一段串起来（离线可验部分），并把新链路写进业务 skill；live 模板读取作为 W06 首个实况项尝试（可回退）。真实填写（B2-B7）仍待八类真实原件（外部输入，未提供）。

验收口径继承：只填不存；守卫/SaveController/registry 原样；不虚构实单；缺真实材料登记缺口不停工；本轮除只读 live 模板读取（若登录可用）外零浏览器操作、不新建不填写任何单据。

## 待做条款

### 1. D10 执行串联（离线核心）
- 上层衔接：PLAN_READY 产出的 fill-plan 文件 → `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <本次身份> --validate-only` 全绿 → 输出"执行就绪"结论（计划路径、哈希、操作人、建议执行命令含 --keep-open-minutes 参数形制；不自动启动浏览器）。
- 操作人来源合规：--expect-name 值只能来自本次请求记录的 user_policy/系统观察事实，不得从模板历史人员推导；无本次身份来源时执行就绪判"缺输入"并给缺口，不猜姓名。
- 串联测试：合成场景 请求→…→PLAN_READY→validate-only 通过→执行就绪输出；身份缺失场景→准确缺口。
- 不改变 fill_once 既有参数语义；新增仅为上层编排（模块名自定，如 bpm_request.py 内或新模块）。

### 2. skill 链路增补（.claude/skills/bpm-fill-run/）
- SKILL.md/references 增补：新链路（请求登记→模板决策→原件理解→事实对账→计划→执行就绪）的调用方式与阶段语义；与既有 --task/--fill-plan 入口的关系（旧入口保留兼容）。
- 修改后用可用的 skill 校验工具验证结构、引用完整性；验证新 session 路由可按 skill 找到入口（离线可验部分）。
- 不改 skill 中保存/授权相关红线文字。

### 3. live 模板读取尝试（W06 首个实况项，可回退）
- 前置：`automation/.pw-profile/session_state.json` 登录态 TTL 检查；取得 profile 锁（单执行者纪律）。
- 若登录有效：`bpm_template.py --live --expect-name <当前已确认操作人> --template-number <三类之一完整单号> --output automation/runs/<独立run>/template_snapshot_live.json` 定向读取一张模板快照，与缓存快照核对一致性（uuid/类别/关键结构），留 run 工件。**不新建、不打开新单填写页、不触碰任何未保存页。**
- 若登录失效/TTL 不足/profile 被占：不扫码不等待，登记准确缺口（GAP_FIELDS 形状入台账 missing_inputs），继续离线部分——两种结果均算完成本项。
- live 前后各截取 events 证据；全程只读。

### 4. R5-P2 三条顺带（记录级）
- 旧日期/旧收款冒充反例实例化存档（把 round-5 三反例模式扩展到日期/收款两个字段并入库测试）。
- 矩阵重复 (group,field) 行显式拒绝。
- `_load_doc` 解析重复维护成本：最小重构或注释说明取舍（不强制）。

## 保留项与边界
- 除第 3 条只读 live 外零网络零浏览器；不动守卫、旧 run（live 输出进新独立 run 目录）、task-registry、legacy-ia2；不自动 commit。
- live 读取严格限既有授权范围（定向模板查询）；失败即登记，不重试刷屏、不强占 profile。
- 原件只读；合成 fixtures 放 tests/。

## 验证
- 新增单测：执行就绪两态（齐备→就绪输出/缺身份→缺口）、R5-P2 前两条、矩阵重复行拒绝。
- live 尝试的两种结果均有工件（成功：快照+核对记录；失败：缺口登记）。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 218 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS；skill 校验工具对修改后的 skill 通过。

## done_when
1. PLAN_READY→validate-only→执行就绪 串联实现+测试（两态；不启动浏览器）。
2. skill 增补完成并通过校验工具；新 session 路由（离线可验部分）通过。
3. live 模板读取尝试留证（成功核对一致 或 失败准确缺口登记），无任何新建/填写动作。
4. R5-P2 前两条落地+测试；第三条处置说明。
5. 全量 unittest 全绿；唯一 run OFFLINE_PASS。
6. 交接齐备：改动+sha256、测试结果、台账 W06 状态更新（按实况）、下一轮入口（W06 真实端到端待外部材料 / W07 两类研究可先行）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-140229-b401214d" contract_id="ctr-ed80c9d0" source_block_id="src-b401214d" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24）

**终态**：离线链路"请求→模板决策→原件理解→事实→对账→计划"末端补上 D10 执行串联——PLAN_READY 计划经 `fill_once.py --fill-plan <计划> --expect-name <本次身份> --validate-only` 全绿后产出结构化"执行就绪"结论（计划路径+sha256、操作人及其来源证据、建议执行命令含 `--keep-open-minutes` 形制；不启动浏览器）；操作人只能来自本次请求 user_policy 或系统观察事实（封闭来源枚举），缺来源判缺输入给 GAP_FIELDS 缺口，不从模板历史人员推导。业务 skill `.claude/skills/bpm-fill-run/` 增补新链路调用方式与阶段语义（旧入口保留兼容），保存/授权红线文字逐字不动，结构/引用/路由经可复核校验。live 模板读取作为 W06 首个实况项单次尝试（可回退）：TTL 前置+profile 锁+`--login-wait 0` 不扫码不等待；成功则快照+缓存一致性核对（uuid/类别/关键结构）+独立 run 工件与 events 证据，失败/TTL 不足/锁被占则 GAP_FIELDS 形状缺口入台账 missing_inputs 后继续离线，两种结果均算完成。R5-P2 顺带：旧日期/旧收款冒充反例实例化入库测试、矩阵重复 (group,field) 行显式拒绝、`_load_doc` 重复维护取舍注释。全量 unittest 全绿（存量 218 零回归）+ 唯一 run OFFLINE_PASS + skill 校验通过。

**本轮做**：
1. D10 执行串联（离线核心）：在 `bpm_request.py`（或同级新模块，不改 `fill_once.py` 语义）新增执行就绪编排——操作人证据 `operator_evidence {name, source∈{user_policy,system_observation}, basis?}` 封闭校验；就绪判定实际调用 `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <身份> --validate-only` 子进程并解析其 JSON 输出（PLAN_VALIDATED+plan_sha256、exit 0 才算全绿）；系统观察来源提供从 Git 排除的 session record 提取 principal.name 的只读 helper（auth_status 非 authenticated 或缺 name 即缺输入，不复制任何凭证原值）；无身份来源→NEEDS_INPUT+GAP_FIELDS 缺口不猜姓名。测试两态：合成场景 请求→登记→模板决策→矩阵→计划→validate-only 通过→执行就绪输出（含建议命令形制）；身份缺失→准确缺口。
2. skill 链路增补：`.claude/skills/bpm-fill-run/SKILL.md`+`references/` 增补新链路（请求登记→模板决策→原件理解→事实对账→计划→执行就绪）调用方式与阶段语义、与既有 `--task`/`--fill-plan` 入口关系（旧入口保留兼容）；"授权与保存"及各红线段文字逐字保留。repo 无现成 skill 校验器 → 交付结构化校验测试 `tests/test_skill_docs.py`：frontmatter 可解析、references 链接全部落在本 skill 目录内且文件存在、命令示例引用的脚本/旗标在代码中真实存在、新链路六阶段关键词与路由描述在场、红线关键句不变；新 session 路由（离线可验部分）= 描述+路由段足以按名找到入口。
3. live 模板读取尝试（可回退，单次）：前置只读 TTL 核对（session record effective_reuse_until 与 auth_status）；`bpm_template.py --live` 自带同 profile 锁与专用只读 context；`--login-wait 0` 保证登录失效时不扫码不等待；输出 `automation/runs/<独立简单run-id>/template_snapshot_live.json`；成功后与缓存快照核对 uuid/类别/关键结构并落核对工件；live 前后 events 证据（CLI 自带 template_read 计时与 template_read_end + 补一致性核对事件）。任一失败（登录失效/TTL 不足/锁被占/网络）→ 缺口按 GAP_FIELDS 形状登记台账 missing_inputs，继续离线部分，不重试刷屏、不强占 profile；两种结果均算完成本项。全程不新建、不打开新单填写页、不触碰任何未保存页。
4. R5-P2 三条顺带：①旧日期（current_business）与旧收款（proven_references）模板值冒充本次值反例实例化测试入库；②`build_reuse_matrix` 重复 (group,field) 行显式拒绝；③`_load_doc` 与 `bpm_template` 缓存读取的解析重复维护成本以注释说明取舍（不强制重构）。

**本轮不做**：不改 `fill_once.py`/`stage1_browser_probe.py` 参数语义与守卫（SaveController/`_click_guard`/registry 原样）；除第 3 条只读 live 模板读取外零网络零浏览器；不真实填写、不新建任何单据、不测试保存按钮；不动旧 run 工件（live 输出进新独立 run 目录）、`automation/task-registry/`、`legacy-ia2/`；不自动 commit、不上传业务材料；不为凑 live 结果重试刷屏或等待扫码；不虚构八类真实原件（外部输入，缺则如实登记缺口）。

**允许写**：`bpm_request.py`（D10 编排+operator helper）、`tests/test_bpm_request.py`、`tests/test_skill_docs.py`（新）、`.claude/skills/bpm-fill-run/SKILL.md`+`references/*.md`（仅增补，红线段逐字不动）、`automation/runs/<独立run>/`（live 尝试与核对工件）、`automation/template-materials-program/progress.json`+`notes.md`（台账）、`automation/offline-verify/<run>/`（唯一验收 run）、`team-task.md` 合同区、`team-progress.md`、memory。
**只读**：`fill_once.py`、`stage1_browser_probe.py`、`bpm_template.py`、`bpm_plan.py`、`bpm_types.py`、`automation/.pw-profile/`、`automation/.local-session/`（live 前置读取不写回）、`automation/task-registry/`、`legacy-ia2/`、旧 run 工件、`templates/`、`patches/`。
**禁止**：`.pw-profile`/`.local-session` 任何凭证或元数据复制进 git/日志/材料清单/测试工件；绕过或削弱守卫与 registry 保护；live 读取之外的任何浏览器导航或点击；模板历史人员冒充本次操作人；为通过校验放宽 `bpm_plan` 判据；伪造 live 结果或缓存核对结论。

**红线**（AGENTS.md 全量并入 + 任务"保留项与边界"）：①默认只填不存（保存/发送/流转/提交/上传/暂存/贴票/审批一律禁点）；②`.pw-profile` 活体 token 不外泄；③结果以 `automation/runs/<run>/` 工件为准（events.jsonl 追加式），聊天叙事为辅，异常记录脱敏；④`legacy-ia2/` 只读。附加：单 profile 只允许一个执行者（live 走 CLI 自带锁）；`--no-proxy-server`、`python -X utf8`、ctypes 判活沿用；不改 `stage1_browser_probe.py`（如意外改动须 `stage1_probe_selftest.py` 全绿后再任何实单动作）。

**风险 envelope**（P0.5 已登记）：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。

**done_when（带验证）**：
1. PLAN_READY→validate-only→执行就绪串联实现+两态测试 → 验证：就绪态测试断言输出含计划路径/sha256/操作人证据/建议命令（含 `--keep-open-minutes`）且 `browser_launched` 为 false；缺身份态断言 GAP_FIELDS 缺口且不猜姓名；`fill_once.py` 参数语义零改动（git diff 可证）。
2. skill 增补并通过校验 → 验证：`tests/test_skill_docs.py` 全绿（结构/引用/命令存在性/红线句不变/路由段在场）；SKILL.md 红线段与增补前逐字一致（diff 定位增补仅在新区）。
3. live 模板读取尝试留证 → 验证：成功路径有 `template_snapshot_live.json`+缓存一致性核对工件+events；失败路径有 GAP_FIELDS 形状缺口登记入台账 missing_inputs；两种结果其一在案即算完成，且全程无新建/填写动作（events 可证）。
4. R5-P2 落地 → 验证：日期/收款两反例测试与重复 (group,field) 拒绝测试入库全绿；`_load_doc` 取舍注释在场。
5. `python -X utf8 -m unittest discover -s tests` 全绿（存量 218 零回归）+ `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 唯一 run PASS。
6. 交接齐备 → 验证：handoff 含改动+sha256、测试结果、台账 W06 状态（live 结果按实况）、下一轮入口（W06 真实端到端待外部材料 / W07 两类研究可先行）。
<!-- /team-task-contract -->
