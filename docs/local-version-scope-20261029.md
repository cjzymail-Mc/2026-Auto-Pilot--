# 2026-10-29 本地版本范围

本版本只含相关源码、合成测试、契约和通用说明；统一CLI离线通过，未访问OA。历史业务验证单列，不扩大模拟或用户人工反馈的技术验收范围。

以下文件按明确清单审查和暂存，不使用git add .：

- `.claude/skills/bpm-fill-run/SKILL.md`
- `.claude/skills/bpm-fill-run/references/common-operations.md`
- `.claude/skills/bpm-fill-run/references/express.md`
- `.claude/skills/bpm-fill-run/references/full-chain.md`
- `.claude/skills/bpm-fill-run/references/plan-contract.md`
- `.claude/skills/bpm-fill-run/references/purchased-samples.md`
- `.claude/skills/bpm-fill-run/references/rd-materials.md`
- `.claude/skills/bpm-fill-run/references/self-drive-inputs.md`
- `.claude/skills/bpm-fill-run/references/self-drive.md`
- `.claude/skills/bpm-fill-run/references/travel.md`
- `.claude/skills/bpm-fill-run/入口与未来扩展说明.md`
- `.gitignore`
- `AGENTS.md`
- `README.md`
- `STATE.md`
- `automation/document-types/office_supplies.notes.md`
- `automation/document-types/welfare_labor.notes.md`
- `automation/fill-plan.schema.json`
- `bpm/browser_probe.py`
- `bpm/fill_cli.py`
- `bpm/login.py`
- `bpm/materials.py`
- `bpm/network_guard.py`
- `bpm/oneshot.py`
- `bpm/plan.py`
- `bpm/plan_generate.py`
- `bpm/query.py`
- `bpm/revision.py`
- `bpm/save.py`
- `bpm/self_drive_plan.py`
- `bpm/self_drive_workbook.py`
- `bpm/template.py`
- `bpm/test_draft_authorization.py`
- `bpm/ui.py`
- `bpm/verify.py`
- `docs/local-version-scope-20261029.md`
- `docs/oa-validation-20261029.json`
- `docs/oa-validation-20261029.md`
- `docs/repository-layout.md`
- `docs/runbook-maturity.md`
- `docs/unified-cli-acceptance-20261029.json`
- `docs/unified-cli-source-manifest-20261029.json`
- `feature02-扩展更多单据类型/2026-10-27 各类runbook公共能力调用路径轻量固化施工计划.md`
- `feature02-扩展更多单据类型/2026-10-28 oneshot真实首验接续计划.md`
- `feature02-扩展更多单据类型/2026-10-28 单会话贯通执行与日常自动保存接线施工计划.md`
- `feature02-扩展更多单据类型/2026-10-28 自驾Excel副本回填与重算收尾结果.md`
- `feature02-扩展更多单据类型/2026-10-28 自驾来源绑定与新入口离线收尾结果.md`
- `feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md`
- `tests/test_bpm_login_reuse.py`
- `tests/test_bpm_materials_cli.py`
- `tests/test_bpm_network_guard.py`
- `tests/test_bpm_oneshot.py`
- `tests/test_bpm_query.py`
- `tests/test_bpm_revision.py`
- `tests/test_bpm_self_drive_plan.py`
- `tests/test_bpm_self_drive_workbook.py`
- `tests/test_bpm_template.py`
- `tests/test_bpm_test_draft_authorization.py`
- `tests/test_bpm_ui.py`
- `tests/test_bpm_unified_cli.py`

排除：真实OA运行转储/HTML/截图、私人原件/银行/票据/人员资料、认证缓存/profile/订阅、本机登录与网络复现日志、并发工作流handoff/review及GLM配置。原始文件本地保留；既有历史记录不篡改，本次不是历史清理。机器索引只留必要匿名元数据、相对通用源码路径和哈希。

正式oneshot新材料首验与原生企微客户端仍待验证；不新建remote，不push。
