# 完整链路参考：模板单号+原始资料 → 执行就绪

适用：用户仅提供完整模板单号、本次原始材料目录（PDF/图片/Excel）与业务说明，要求 agent 自行完成提取、复核、对账、计划与执行准备。全部阶段可离线推进到"执行就绪"；真实浏览器填写仍按 SKILL.md「日常入口/执行与恢复」的命令与纪律进行，保存授权红线不变。

## 六阶段与调用方式

| 阶段 | 入口 | 产物/语义 |
|---|---|---|
| 1 请求登记 | `bpm_request.register_request(fields, manifest_path=…)` | 齐备请求落双根派生根（role=user_request，`source_semantics=user_instruction`）；缺模板单号/材料目录/业务说明 → `NEEDS_INPUT`+GAP_FIELDS，不落盘。键集封闭：`template_biz_number/materials_dir/statement/declared_category/applicant/payee_hint/budget/relation_refs/user_policy`。 |
| 2 模板决策 | `bpm_request.resolve_template(census, 单号, declared_category=…)` | `cached_template` 缓存定向唯一命中（fetch/children 全 200）；类别走封闭注册（travel=差旅费/08、express=快递费/15、rd_materials=研发材料费/11）。声明类别与模板矛盾 → `CONFLICT` 集中报告，不悄悄换类；未登记类别 → `identify_unknown` 只读识别（writable=false，不映射任何已注册类别绕过）。live 定向读取（可回退）用 `bpm_template.py --live --expect-name <当前已确认操作人> --template-number <完整单号> --output automation/runs/<独立run>/template_snapshot_live.json`，CLI 自带同 profile 锁与只读 context；登录失效即登记缺口，不扫码不等待。 |
| 3 原件理解 | `fill_once.py --task "任务.json" --expect-name "操作人"` | 双根 manifest v2.0 + 独立解析/复核 JSON；CSV/XLSX 保留前导零与原件哈希；PDF/图片显式票据分类；不上传第三方 OCR。真实识别路径：文本 PDF 走嵌入文本层（多页行级锚点）；扫描件/图片由 `bpm_extraction.render_pages/render_to_files` 全页渲染后 agent 视觉复核（`review_pass` verify=agent-visual，逐字段页/区域锚点+复核者留证）；`barstub` 仅为管线测试引擎，不作真实原件识别。 |
| 4 事实与对账 | `bpm_facts.FactSet`（add/add_invoice/add_expense/add_payee/…） | 每个事实有 kind/source/locator/input_hashes；模板事实必须绑定快照哈希；金额 Decimal 闭合（totalCost=明细合计=收款合计=票据分配）。 |
| 5 计划 | `bpm_request.build_reuse_matrix` → `entries_from_matrix` → `bpm_plan_generate.generate_fill_plan` | 六字段组逐字段决策（adopt/replace/identify/not_applicable）：current_business 与 proven_references 禁 adopt 模板来源；旧年度预算、历史申请人 adopt 须 `user_policy` 确认；值一律 fact_id 绑定；产物落派生根 role=decision_matrix。生成 v1.0 fill-plan 并 `validate_plan(verify_sources=True)` 零 issues。 |
| 6 执行就绪 | `bpm_request.execution_ready(plan_path, operator_evidence)` | 真实子进程 `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <身份> --validate-only` exit 0 + `PLAN_VALIDATED` 才算全绿；输出 `{status: EXECUTION_READY, plan{path,sha256}, operator{name,source,basis}, suggested_command(含 --keep-open-minutes), browser_launched:false}`。 |

## 操作人来源纪律（阶段 6 前置）

- 合法来源封闭两值：本次请求 `user_policy`（用户在请求中确认的操作人）或系统观察（`bpm_request.operator_from_session_record(<.local-session 记录>)`：`auth_status=authenticated` 且 `principal.name` 非空才可用）。
- 模板历史申请人/操作人永远不是来源，同名也不可据此推导；来源越界（如 template/template_history）直接 ValueError。
- 缺证据 → `NEEDS_INPUT` + GAP_FIELDS 缺口（不猜姓名、不调 CLI、不启动浏览器）。
- `.local-session` 为 Git 排除的本机记录：只读取 `principal.name` 与核验层次，不复制凭证引用或其余元数据进任何工件。

## 与旧入口的关系

`--task` / `--fill-plan --validate-only` / `--fill-plan --keep-open-minutes` 三命令原样保留：本链路阶段 3 直接复用 `--task`，阶段 6 的就绪判定复用 `--validate-only` 子进程，最终真实执行仍用第三条命令（或按 SKILL.md 恢复纪律 `--resume-run`）。本链路只是上层编排，不改变 `fill_once.py` 任何参数语义。

## 阶段状态与缺口

- 阶段机（`fill_once.prepare_task`）：`MATERIALS_READY → FACTS_BUILT → RECONCILED → PLAN_READY / NEEDS_INPUT`。
- 一切缺口用 GAP_FIELDS 形状（file/locator/region/candidates/reason/affected_rows）集中登记，不猜值；live 模板读取失败/TTL 不足/profile 被占同样登记后继续离线部分。
