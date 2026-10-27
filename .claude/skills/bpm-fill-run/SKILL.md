---
name: bpm-fill-run
description: 根据模板单号、原始材料和执行意图，处理企业微信 OA 报销链路、执行就绪检查、已支持类型的填写与授权草稿保存；结合真实模板识别自驾公出等场景并加载手册。用于材料整理、报销填报、复核和安全恢复；自驾整单接线尚未完成时停止相关写入，禁止提交、流转及上传。
---

# BPM 报销填写与草稿保存

在仓库根运行，普通业务先读 `AGENTS.md`。用户只需提供本次材料、参考单据完整单号和执行意图，不要求其选择内部类型、提供内部 JSON 或预先知道登录姓名。纯材料整理或 Skill 维护按本次范围执行，不为完成离线工作打开 OA。

维护 Skill 框架、runbook 登记或新增场景时，读 [入口与未来扩展说明](入口与未来扩展说明.md)。

## 模板与场景路由

先由本次真实模板核实表单种类、费用类别及唯一单号，再结合材料和意图选择手册：

- `travel / 差旅费 / 08` 且具备公里表、通行费/油票及自驾证据：读 [self-drive.md](references/self-drive.md)。不能只凭备注、单号或“有交通费”认定自驾。
- 其他已支持差旅：读 [travel.md](references/travel.md)；快递费 `express` 读 [express.md](references/express.md)；研发材料费 `rd_materials` 读 [rd-materials.md](references/rd-materials.md)。保留三类独立配置和 schema 分支。
- 准备 task、计划或排查来源/金额校验时读 [plan-contract.md](references/plan-contract.md)；既有请求编排读 [full-chain.md](references/full-chain.md)。不必加载无关类型手册。

输出采用证据、排除依据及当前执行能力。未知类别、歧义、多候选、未建模关联/数量分支或缺执行适配时报告具体缺口，不套用相近类型。当前自驾已具备规则、计算和材料归集组件，Excel/真实公出匹配/含餐补计划及完整执行串联仍未装配；**本次用户已暂停完整施工与真实验收，Skill 文档搭建不表示这些能力已完成**。

单独获授权的无答案使用验收按冻结输入白名单读取长期红线，不自动加载 `STATE.md`、合同案例章节、旧解析/计划/匹配答案或反例夹具；这不豁免身份、锁、registry 和来源校验。当前尚未执行该冷启动验收。

## 日常入口

仅整理/核对材料且用户不要求连接 OA 时，走相应手册的离线分析与归集库路径，不调用需要 `--expect-name` 的业务准备 CLI，不要求补模板单号或操作人。原件不清、材料冲突仍须报告；线上参与事实可明确保留待核，不为消除该缺口突破离线范围。

接受完整模板单号、本次材料路径（可分别指定目录与文件）及一句执行意图。先用 `bpm_login.py` 真实探查当前人员，再生成内部任务和业务 CLI 的 `--expect-name`；用户另有明确预期时必须与实测一致。模板仅提供经适用性核实的稳定结构、预算和收款参考，本次日期、费用、发票、金额及关联单据来自本次证据。缺项或冲突集中列出，不猜值，不默认替换关联单。

不要求用户重复提供系统已带出的身份。区分当前登录操作人、真实新页制单人/申请人、费用所属人和收款人；未知记缺口，不从历史模板换人。未获本次代办依据时，不主动改写系统默认人员；同名或身份来源冲突先阻断相关写入。

1. 用 `bpm_template.py` 定向读取真实指定模板，保留快照及哈希，优先采用受登录会话保护的 live 入口；不为找一张单全量普查。只读允许必要的精确查询、翻页和查看详情，不进行业务持久写入，不导航或关闭他人的未保存页；认证状态/事件的受控本机维护不等于业务写入。缓存只能作有来源的结构参考，不能证明当前身份或代替本次事实。
2. 业务准备可用 `--task` 整理清单及独立解析输出；此步不启动浏览器，也不自动生成可执行计划。CSV/XLSX 保留账号、单号前导零。**PDF 优先机读文本层**，关键票号/代码/金额/日期由原图视觉、汇总资料等适用的独立通道复核；已有汇总单须参与逐票互证，冲突不能忽略。扫描件/图片逐页视觉提取并独立复核，不把同一次读数复制当成互证；无可靠复核依据或关键值不清则待复核/`NEEDS_INPUT`，不能宣布可执行事实齐备，也不把汇总单强加为所有任务的必备材料。保留原件哈希、页码/区域和复核记录，逐件分类、去重，按对应模型校验票据分配及政策来源；不上传第三方 OCR。
3. 生成 v1.0 `fill-plan`，每个执行值有来源定位。先离线验证，再执行：

```powershell
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45
```

`--task` 返回 `NEEDS_INPUT` 是准备结果，不等于已填写。无参数启动会拒绝；不存在固定旧单、固定人员或固定 run 的默认填写。

## 完整链路：模板单号+原始资料 → 执行就绪

已支持且输入可核实的类型按六阶段编排（详见 [full-chain.md](references/full-chain.md)）：请求登记（`bpm.request.register_request`）→ 模板决策（`resolve_template`；未登记类别转只读识别，不映射绕过）→ 原件理解（`--task` 双根清单+复核 JSON）→ 事实与对账（`bpm_facts` + `bpm_plan_generate`）→ 计划 → 执行就绪（`bpm.request.execution_ready`：真实 `--validate-only` 子进程通过）。随后由 agent 按本次意图执行受支持的正式填写/保存入口，不把建议命令交给用户手跑。

- 操作人证据来源封闭：本次请求 `user_policy` 或本次真实系统观察（`operator_from_session_record` 仅引用探查后 Git 排除的本机记录）；缓存 JSON 本身不能证明当前登录有效。模板历史人员不可推导本次操作人，缺来源按 GAP_FIELDS 返回，不猜姓名。
- 历史复用逐字段过六字段组矩阵（`build_reuse_matrix`/`entries_from_matrix`）：本次日期/费用/发票/金额与关联/收款禁 adopt 模板旧值；旧年度预算、历史申请人沿用须用户政策显式确认；值一律 FactSet 事实绑定。
- 请求与矩阵产物落双根 manifest 派生根（role=user_request/decision_matrix，版本化哈希可追溯）；各阶段缺口统一 GAP_FIELDS 形状，`NEEDS_INPUT` 不落盘、不猜值。
- 与旧入口关系：上文三命令保留兼容；当前代码的上层编排只到 `EXECUTION_READY`，不是所有场景均已自动贯通。`NEEDS_INPUT`、`PLAN_READY`、`EXECUTION_READY` 均为阶段状态，不能冒充填写交付。自驾目前缺装配时按其手册停在安全阶段并说明缺口，不绕过校验或要求用户补内部 JSON。

## 执行与恢复

新任务独立 run，同一任务重试必须绑定同一计划、操作人和配置哈希。新增行后重新定位，选择器按确切名称及业务编号唯一匹配。终局由独立 DOM 回读核对完整行数、身份、字段及 Decimal 金额闭合，不以固定匹配项数或写入函数自报成功验收。

申请人与操作人不同时，补齐来源明确的 `identity.applicant_employee_id/creator_name/creator_department`；只在空白新页首次选择申请人，核对姓名、工号、公司和部门，再锁定申请人与制单人。费用填写后禁止改人员。当前正式支持公出单一对一关联明细；其他关联分支先报告不支持，不套用一对一规则。关联明细为空即失败。系统空值的具体条件见差旅参考，禁止全局空转零。

正式入口连续执行各行，不加载旧 run 的 review_actions.py，不逐格派发命令。当前组件下拉按新鲜动态面板关联精确选项；预算先选单再选科目；账号使用实际原生可写控件，支行按完整联行号选择并核对全称。阶段内只缓存表列结构，增行/选单/表单重建后失效；最终全页回读独立重新采集。

测试用途必须有本次具体材料/任务的来源和授权边界，使用带路径与哈希的 `test_context` 登记目的；旧案例许可不自动成为新任务许可。受限占位只在其明确绑定的 `fill_only` 测试中使用，真实匹配与测试关联分开取证，不能保存为真实报销或释放旧关联。已有未保存页继续按恢复边界处理，不强关旧页换任务绕过。

恢复命令是：

```powershell
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

先查 `automation/task-registry/` 和 run 工件。已有保存意图、结果不确定或已保存记录只走只读核实，不重点击、不再建单。未保存页恢复目前仅盘点页面并返回 `NEEDS_INPUT`，不声称自动恢复；保留原页和恢复工件。不要删除 registry 或换 task_id 来规避重试保护。同一 profile 仅一个执行者。

## 日常保存策略

用户已要求日常真实报销在填写并完整独立核验后自动保存草稿，严禁流转/提交；明确“只填”“暂不保存”时执行 `fill_only`，受限历史占位测试也必须不存。规则来源为仓库 `BPM-SELFDRIVE-20261027-A1` 增补。

下节的默认 `fill_only` 是未取得同任务保存授权时的运行时门禁。日常策略须编译为本次请求、同 `task_id` 的 `save_draft` 授权及来源/哈希绑定，再调用现有 `SaveController`；不能把一段策略文字当作已经完成授权。该自动编译与自驾执行接线尚未完成，应明确报告能力缺口，不要求用户手写 JSON 或手动保存，也不放宽旧守卫。`real_save_verified=false` 只表示证据层次，不能单独成为已合法授权任务的永久保存禁令。

## 授权与保存

默认 `fill_only`。只有用户对本具体任务明确要求保存，计划中有同 task_id 的 `save_draft` 授权，才进入 `SaveController`。普通 `_click_guard` 仍禁止“保存”；专用控制器在新单、身份、来源/配置/计划哈希、完整回读、终局截图及点击前复核通过后，仅允许一次精确“保存”。保存后必须取得唯一单号/UUID、确认未提交，重新打开并逐项核对，才能报告 `SUCCESS_DRAFT_SAVED`。

保存并提交、发送、提交、流转、审批、暂存、贴票和上传始终不在本任务范围；禁止直接写接口、放宽通用守卫、自动确认未知对话框。`SAVE_UNCERTAIN` 立即转只读核实。

## 环境与交付

- OA 必须 `--no-proxy-server` 直连，不经 VPN/Clash。需要读取 OA 或实际填报时，先用 `python -X utf8 bpm_login.py` 验证当前账号和登录态；纯离线材料/Skill 维护不为此打开 OA。重新扫码用 `--force-scan`，不预设固定姓名。新扫码本地复用上限 30 天，旧 60 天记录收紧到 min(原窗口, 扫码+30 天)；已知 refresh token 期限更早则取更早期限，不随文件写回续期；旧无元数据状态仍限 24h，服务端失效需重新扫码。人员与期限记录在 Git 排除的 `.local-session/`，账号以本次真实探查为准。
- `automation/.pw-profile/` 含活体 token，不复制进 git、日志、材料清单或报告。Windows 判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。
- 改过 `bpm/browser_probe.py` 或其兼容入口后先跑 `python -X utf8 stage1_probe_selftest.py` 全绿；统一离线验收为 `python -X utf8 verify_bpm_build.py`，结果及合成截图/哈希在 `automation/offline-verify/<run>/`。保留 600ms 轮询、Tab 失焦与重复回读等稳定机制，不承诺固定耗时。
- 结果以 `events.jsonl`、attempt 下 `stage1_result.json` 和证据为准。返回阶段/状态、run/attempt、缺口或差异、截图；只有持久化复核成功才返回新草稿单号、金额和未提交状态。区分代码实现、离线验证、真实填写验证和真实保存验证。

旧方案仅供显式只填不存回归：同时传具体 `--fill-plan` 路径、`--expect-name` 与 `--legacy-regression`；不用于日常任务或草稿保存。
