---
name: bpm-fill-run
description: 读取指定历史报销单及本次材料，生成并校验 BPM 报销计划，通过本仓库 Playwright 执行新单填写和具体任务已授权的草稿保存。也覆盖"用户仅给模板单号+原始资料"的完整链路：请求登记→模板决策→原件理解→事实对账→计划→执行就绪（离线推进到 validate-only 全绿）。用于企业微信 OA 报销、复核及安全恢复；提交、流转、上传不在范围内。
---

# BPM 报销填写与草稿保存

在仓库根运行，先读 `AGENTS.md`。按用户业务选择参考：差旅 `travel` 读 [travel.md](references/travel.md)，快递费 `express` 读 [express.md](references/express.md)，研发材料费 `rd_materials` 读 [rd-materials.md](references/rd-materials.md)。准备 task、生成计划或排查校验失败时读 [plan-contract.md](references/plan-contract.md)。三类使用独立配置和 schema 分支；快递普通全额及研发物品档案行金额路径已接入代码，复杂历史回放真实填写已通过，实际保存/重开及新业务材料验收仍待具体输入与授权。未知类别、未建模关联/数量分支继续拒绝。

## 日常入口

接受用户的完整模板单号、本次材料目录、报销说明、预期操作人和保存要求。模板中的稳定身份、预算、收款资料可以有来源地复用；本次日期、费用、发票、金额和关联单据必须来自本次证据。缺项或冲突集中列出，不猜值，不默认替换关联单。

用户要求保留登录人默认资料时，不主动选择或改写申请人/制单人，也不要求用户重复提供系统已带出的身份。实际新单的默认资料只读记录并用于核验，不从历史模板换人；预期操作人使用本次用户确认的姓名。

1. 用 `bpm_template.py` 精确读取指定模板，保留快照及哈希。缓存 CLI 与受登录会话保护的 live 只读函数见参考；不为找一张单而重新全量普查。
2. 用 `--task` 整理材料清单和独立解析输出；这一步不启动浏览器，也不自动生成可执行计划。CSV/XLSX 保留账号、单号前导零；PDF/图片通过可用的本地文档/视觉能力提取，再提供带原件哈希、页码/区域定位的复核 JSON。每个 PDF/图片原件需显式票据分类；发票身份去重、票面金额与主要费用行分配闭合，免票行有本次规则来源。关键值无法确定或 Excel/发票冲突则 `NEEDS_INPUT`，不上传第三方 OCR。
3. 生成 v1.0 `fill-plan`，每个执行值有来源定位。先离线验证，再执行：

```powershell
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45
```

`--task` 返回 `NEEDS_INPUT` 是准备结果，不等于已填写。无参数启动会拒绝；不存在固定旧单、固定人员或固定 run 的默认填写。

## 完整链路：模板单号+原始资料 → 执行就绪

用户只给完整模板单号、原始材料目录与业务说明时，走六阶段链路（阶段语义与调用方式详见 [full-chain.md](references/full-chain.md)）：请求登记（`bpm_request.register_request`）→ 模板决策（`resolve_template` 缓存定向唯一命中；未登记类别转只读识别，不映射绕过）→ 原件理解（`--task` 双根清单+复核 JSON）→ 事实与对账（`bpm_facts` + `bpm_plan_generate` 推进到 `PLAN_READY`）→ 计划 → 执行就绪（`bpm_request.execution_ready`：真实 `--validate-only` 子进程全绿后输出计划路径/sha256、操作人证据、建议执行命令；不启动浏览器）。

- 操作人证据来源封闭：本次请求 `user_policy` 或系统观察（`operator_from_session_record` 只读 Git 排除的 `.local-session` 会话记录）；模板历史人员不可推导本次操作人，缺来源按 GAP_FIELDS 缺口返回，不猜姓名。
- 历史复用逐字段过六字段组矩阵（`build_reuse_matrix`/`entries_from_matrix`）：本次日期/费用/发票/金额与关联/收款禁 adopt 模板旧值；旧年度预算、历史申请人沿用须用户政策显式确认；值一律 FactSet 事实绑定。
- 请求与矩阵产物落双根 manifest 派生根（role=user_request/decision_matrix，版本化哈希可追溯）；各阶段缺口统一 GAP_FIELDS 形状，`NEEDS_INPUT` 不落盘、不猜值。
- 与旧入口关系：上文 `--task`/`--fill-plan` 三命令保留兼容；本链路是其上层编排，终点是"执行就绪"结论，真实浏览器执行与恢复仍按下文入口纪律进行，保存授权红线不变。

## 执行与恢复

新任务独立 run，同一任务重试必须绑定同一计划、操作人和配置哈希。新增行后重新定位，选择器按确切名称及业务编号唯一匹配。终局由独立 DOM 回读核对完整行数、身份、字段及 Decimal 金额闭合，不以固定匹配项数或写入函数自报成功验收。

申请人与操作人不同时，补齐来源明确的 `identity.applicant_employee_id/creator_name/creator_department`；只在空白新页首次选择申请人，核对姓名、工号、公司和部门，再锁定申请人与制单人。费用填写后禁止改人员。当前正式支持公出单一对一关联明细；其他关联分支先报告不支持，不套用一对一规则。关联明细为空即失败。系统空值的具体条件见差旅参考，禁止全局空转零。

正式入口连续执行各行，不加载旧 run 的 review_actions.py，不逐格派发命令。当前组件下拉按新鲜动态面板关联精确选项；预算先选单再选科目；账号使用实际原生可写控件，支行按完整联行号选择并核对全称。阶段内只缓存表列结构，增行/选单/表单重建后失效；最终全页回读独立重新采集。

本轮提速方案第 2.1 节已授权真实控件、未保存测试单和必要 C0/C1 回归，无需重复申请同范围许可。使用带授权路径与哈希的 `test_context` 登记具体测试目的和轮次，强制 fill_only、独立临时 context，证据完整后正常关闭本轮测试页。已保存样张 15426104612 只读保护；不可将测试许可扩大为新测试单保存许可。

恢复命令是：

```powershell
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

先查 `automation/task-registry/` 和 run 工件。已有保存意图、结果不确定或已保存记录只走只读核实，不重点击、不再建单。未保存页恢复目前仅盘点页面并返回 `NEEDS_INPUT`，不声称自动恢复；保留原页和恢复工件。不要删除 registry 或换 task_id 来规避重试保护。同一 profile 仅一个执行者。

## 授权与保存

默认 `fill_only`。只有用户对本具体任务明确要求保存，计划中有同 task_id 的 `save_draft` 授权，才进入 `SaveController`。普通 `_click_guard` 仍禁止“保存”；专用控制器在新单、身份、来源/配置/计划哈希、完整回读、终局截图及点击前复核通过后，仅允许一次精确“保存”。保存后必须取得唯一单号/UUID、确认未提交，重新打开并逐项核对，才能报告 `SUCCESS_DRAFT_SAVED`。

保存并提交、发送、提交、流转、审批、暂存、贴票和上传始终不在本任务范围；禁止直接写接口、放宽通用守卫、自动确认未知对话框。`SAVE_UNCERTAIN` 立即转只读核实。

## 环境与交付

- OA 必须 `--no-proxy-server` 直连，不经 VPN/Clash。每次开工先用 `python -X utf8 bpm_login.py` 验证当前账号和登录态；重新扫码用 `--force-scan`，不预设固定姓名。新扫码本地复用上限 60 天，已知 refresh token 期限更早则取更早期限，不随文件写回续期；旧无元数据状态仍限 24h，服务端失效需重新扫码。人员与期限记录在 Git 排除的 `.local-session/`，账号以本次真实探查为准。
- `automation/.pw-profile/` 含活体 token，不复制进 git、日志、材料清单或报告。Windows 判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。
- 改过主探针先跑 `python -X utf8 stage1_probe_selftest.py` 全绿；统一离线验收为 `python -X utf8 verify_bpm_build.py`，结果及合成截图/哈希在 `automation/offline-verify/<run>/`。保留 600ms 轮询、Tab 失焦与重复回读等稳定机制，不承诺固定耗时。
- 结果以 `events.jsonl`、attempt 下 `stage1_result.json` 和证据为准。返回阶段/状态、run/attempt、缺口或差异、截图；只有持久化复核成功才返回新草稿单号、金额和未提交状态。区分代码实现、离线验证、真实填写验证和真实保存验证。

旧方案仅供显式只填不存回归：同时传具体 `--fill-plan` 路径、`--expect-name` 与 `--legacy-regression`；不用于日常任务或草稿保存。
