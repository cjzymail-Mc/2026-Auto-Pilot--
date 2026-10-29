# 完整链路参考：模板单号+原始资料 → 执行就绪

适用：已支持且输入可核实的类型，用户仅提供完整模板单号、本次原始材料目录（PDF/图片/Excel）与业务说明，由 agent 完成提取、复核、对账、计划与执行准备。本页描述现有六阶段 API；阶段 6 之后，已支持类型可由单会话入口 `python -X utf8 -m bpm.oneshot --task …` 把模板→最终计划→填写贯通为一次执行（实现＋离线验证，真实填写/保存待验）。不能把阶段产物当填写完成，也不要求用户手跑内部命令。

自驾公出先读 [self-drive.md](self-drive.md) 的装配状态：材料/计算组件已有，含餐补计划、Excel/真实公出匹配及完整执行接线尚未完成，且完整施工已暂停。不得因本页有六阶段表就宣称自驾整链可用。日常真实任务自动保存的用户策略由 `bpm.oneshot` 的授权编译接入（离线验证通过、真实保存待验）；自驾执行接线未完成时按其手册停在安全阶段，不直接保存。

## 六阶段与调用方式

| 阶段 | 入口 | 产物/语义 |
|---|---|---|
| 1 请求登记 | `bpm.request.register_request(fields, manifest_path=…)` | 齐备请求落双根派生根（role=user_request，`source_semantics=user_instruction`）；缺模板单号/材料目录/业务说明 → `NEEDS_INPUT`+GAP_FIELDS，不落盘。键集封闭：`template_biz_number/materials_dir/statement/declared_category/applicant/payee_hint/budget/relation_refs/user_policy`。 |
| 2 模板决策 | `bpm.request.resolve_template(census, 单号, declared_category=…)` | `cached_template` 缓存定向唯一命中（fetch/children 全 200）；类别走封闭注册（travel=差旅费/08、express=快递费/15、rd_materials=研发材料费/11）。声明类别与模板矛盾 → `CONFLICT` 集中报告，不悄悄换类；未登记类别 → `identify_unknown` 只读识别（writable=false，不映射任何已注册类别绕过）。live 定向读取（可回退）用 `bpm_template.py --live --expect-name <当前已确认操作人> --template-number <完整单号> --output automation/runs/<独立run>/template_snapshot_live.json`，CLI 自带同 profile 锁与只读 context；登录失效即登记缺口，不扫码不等待。 |
| 3 原件理解 | `fill_once.py --task "任务.json" --expect-name "操作人"` | 双根 manifest v2.0 + 独立解析/复核 JSON；CSV/XLSX 保留前导零与原件哈希；PDF/图片显式票据分类；不上传第三方 OCR。真实识别路径：文本 PDF 走嵌入文本层（多页行级锚点）；扫描件/图片由 `bpm.extraction.render_pages/render_to_files` 全页渲染后 agent 视觉复核（`review_pass` verify=agent-visual，逐字段页/区域锚点+复核者留证）；`barstub` 仅为管线测试引擎，不作真实原件识别。 |
| 4 事实与对账 | `bpm.facts.FactSet`（add/add_invoice/add_expense/add_payee/…） | 每个事实有 kind/source/locator/input_hashes；模板事实绑定快照哈希，费用/明细/收款 Decimal 闭合。普通全额模型再校验完整票面分配；不能把该等式套成自驾覆盖池 F=应报 R。自驾见专用手册：R 与 F 分开建模，专用计划绑定未接通时停止写入。 |
| 5 计划 | `bpm.request.build_reuse_matrix` → `entries_from_matrix` → `bpm.plan_generate.generate_fill_plan` | 六字段组逐字段决策（adopt/replace/identify/not_applicable）：current_business 与 proven_references 禁 adopt 模板来源；旧年度预算、历史申请人 adopt 须 `user_policy` 确认；值一律 fact_id 绑定；产物落派生根 role=decision_matrix。生成 v1.0 fill-plan 并 `validate_plan(verify_sources=True)` 零 issues。 |
| 6 执行就绪 | `bpm.request.execution_ready(plan_path, operator_evidence)` | 真实子进程 `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <身份> --validate-only` exit 0 + `PLAN_VALIDATED` 才算全绿；输出 `{status: EXECUTION_READY, plan{path,sha256}, operator{name,source,basis}, suggested_command(含 --keep-open-minutes), browser_launched:false}`。 |

## 操作人来源纪律（阶段 6 前置）

- 合法来源封闭两值：本次请求 `user_policy`（用户有明确预期时与实测核对）或系统观察（本次 `bpm_login.py` 真实探查后引用 `operator_from_session_record` 的本机记录）。`auth_status=authenticated` 和非空姓名是该辅助函数的条件，缓存 JSON 不能单独证明当前认证有效，也不要求用户事先知道姓名。
- 模板历史申请人/操作人永远不是来源，同名也不可据此推导；来源越界（如 template/template_history）直接 ValueError。
- 缺证据 → `NEEDS_INPUT` + GAP_FIELDS 缺口（不猜姓名、不调 CLI、不启动浏览器）。
- `.local-session` 为 Git 排除的本机记录：只读取 `principal.name` 与核验层次，不复制凭证引用或其余元数据进任何工件。

## 与旧入口的关系

`--task` / `--fill-plan --validate-only` / `--fill-plan --keep-open-minutes` 三命令原样保留：本链路阶段 3 直接复用 `--task`，阶段 6 的就绪判定复用 `--validate-only` 子进程，最终真实执行仍可用第三条命令（或按 SKILL.md 恢复纪律 `--resume-run`）。本链路只是上层编排，不改变 `fill_once.py` 任何参数语义。

**单会话贯通入口 `bpm.oneshot` 的就绪检查与衔接**（模板→最终计划）：任务分支要求任务 JSON 带 agent 离线准备的 `facts_payload`（FactSet 载荷＋blueprint＋材料 manifest），`--validate-only` 不启动浏览器、返回 `TASK_VALIDATED` 及编译出的授权模式即就绪；正式执行时在**同一 probe 会话**内 live 读取本次模板（阶段 2 的 live 定向读取规则不变：唯一单号命中、同 profile 锁），模板值仅取本次快照（预供模板值、快照缺字段、预冻结快照、单号冲突均为结构化缺口，见 `complete_from_live_snapshot`），随后授权编译→计划生成→冻结→四绑定→进入既有填写链。`--fill-plan` 分支的就绪检查就是 `load_plan` 完整校验（`PLAN_VALIDATED`），授权与计划原样执行。任务分支新开 run 的既有 journal 保存意图在启动浏览器前阻断；`--fill-plan`/`--resume-run` 沿用既有入口的 SaveController 在途只读核实。

## 阶段状态与缺口

- 阶段机（`bpm.fill_cli.prepare_task`）：`MATERIALS_READY → FACTS_BUILT → RECONCILED → PLAN_READY / NEEDS_INPUT`。
- 一切缺口用 GAP_FIELDS 形状（file/locator/region/candidates/reason/affected_rows）集中登记，不猜值；live 模板读取失败/TTL 不足/profile 被占同样登记后继续离线部分。

## events 与观察处置（round-9 / ctr-15712bcb §4 三观察落点）

- **链重跑分段标记（观察①）**：同一 run 内 chain 重跑不清理旧 events（append-only 语义不破坏）；每次驱动启动先记 `chain_segment_start`，`segment` = 既有 events 行数 + 1（见 `runs/20261024-193500-officeloop`、`runs/20261024-194500-welfareloop`：段 1/2/11/19 与 1/4/9 逐段可辨）。审计读 events 时按段分组，段间同名事件互不覆盖。
- **research 探针事件中 `authorization` 字样（观察②）**：仅出现在 `exact_template_read` 等事件的 `header_names` 数组里，是**只读观测到的 HTTP 请求头名清单**（值永不记录），不是业务写入授权记录。扫 events 判授权语义时不得把该字样当作授权证据。后续若获授权改探针，键名可改 `observed_request_header_names` 消歧；观测到的 header 名本身是证据，不改值。
- **no-residue 工件布尔命名（观察③）**：原始观测布尔（如 `created_today_rows`、`keyword_hit_rows` 等计数/命中事实）与终判布尔（`round8_residue.none` 这类裁决）分层命名：计数/命中用 `observed_*` 或具体计数名，终判用 `<scope>_residue.none` 形态且必须由原始观测派生。历史 `no_residue_verdict_final.json` 原样保留不改名，新产物沿用本约定。
