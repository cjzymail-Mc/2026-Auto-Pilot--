# AGENTS.md — coding agent 接手须知

BPM 报销自动填报：Playwright 操作企业微信 OA（bpm.qiaodan.com，Angular PrimeNG）。先读本文件和 [STATE.md](STATE.md)，再按当前任务读取合同/证据；总览见 [README.md](README.md)，业务操作按 [bpm-fill-run skill](.claude/skills/bpm-fill-run/SKILL.md)。

## 文档分工与 STATE.md 维护标准

- **AGENTS.md 保留长期规则**：安全边界、操作入口、协作约束、验证要求。只有长期规则改变才更新；不追加某轮进展、具体扫码日期、历史运行摘要或待评估方案全文。
- **STATE.md 是当前接手快照**：只保留当前目标/阶段、最近关键结果、未解事项/下一步、必要的合同与恢复入口。具体轮次、命令输出、失败过程和审查细节留在既有 run、team-progress 或专题记录，STATE 只链接。
- **有实质变化才更新**：用户决定、阶段完成、阻断变化或接手路线改变时更新；收尾前检查是否需要同步。没有变化不追加条目，也不为刷新日期重写。
- **替换旧结论，不追加流水账**：最近关键结果最多 3 项；已解决事项退出待办，旧成果不再影响接手时移除摘要、保留必要入口。仍有效的未解风险、授权限制和恢复线索不能仅因日期久或条数超限删除；可合并为一句并链接详细记录。
- **控制篇幅**：STATE 目标 40—60 行，原则不超过 80 行；超出时先合并、删重复、将细节链接到已有记录，不靠超长单行规避。使用简短段落/列表，不建立逐日更新区、完成事项长表或每轮归档副本。
- **结论须有证据**：标注最后核对日期与范围；关键完成/阻断项附直接证据路径，区分已实现、离线通过、真实填写通过、真实保存通过。未核实写“待核实”，建议写“待评估”，不能自动转成实施任务或授权。
- **动态事实不固化**：workflow 阶段、进程、锁、registry、未保存页和登录有效性在实际操作前重新核实。STATE 不替代 helper/原始工件，不复制凭证、个人会话元数据、人员/银行资料或绝对机器路径。
- **规则只放一处**：STATE 引用本文件，不复述长期红线；本文件引用 STATE，不复制当前进展。维护文档不改冻结合同、历史原始证据或运行状态。

Skill 框架、runbook 登记及新增手册规范见 [入口与未来扩展说明](.claude/skills/bpm-fill-run/入口与未来扩展说明.md)。

## 红线

1. 默认 `fill_only`。普通 `_click_guard` 继续禁止保存/发送/流转/提交/上传/暂存/贴票/审批。仅用户对本具体任务明确要求保存、计划有同 task_id 的 `save_draft` 授权，专用 `SaveController` 才可在完整独立回读、身份/来源/配置/计划绑定、金额闭合、终局截图和点击前复核通过后，执行一次唯一精确“保存”。禁止保存并提交、未知弹框自动确认、直接写接口及放宽通用守卫；施工授权不等于虚构实单保存授权。
2. `automation/.pw-profile/` 含活体凭证，绝不复制进 Git、日志、报告、材料清单或测试工件。`automation/.local-session/` 的个人会话元数据也不进入 Git、通用案例、材料 manifest 或跨 agent 消息；禁止 `git add -f`。
3. 结果以 `automation/runs/<run>/events.jsonl`（追加式）、`attempt_NNN/stage1_result.json` 及该 attempt 证据为准；准备结果在 run 根。报告保存成功必须证明唯一新单号/UUID、未提交状态及重开持久化回读；fill_only 验收不要求这些，也不测试保存按钮。
4. `automation/task-registry/` 保留跨 run 意图。已有 `SAVE_INTENT`、`SAVE_UNCERTAIN` 或保存成功记录只读核实，禁止再保存/另建。未保存页恢复当前仅盘点并返回 `NEEDS_INPUT`；不得删 registry、换 task_id 或强关旧页规避。单 profile 单执行者，探查不得导航或关闭其他执行者的未保存页。
5. `legacy-ia2/` 本地只读存档（2026-10-27 历史净化起不入库，新克隆缺件为预期状态；原件在维护备份与本地 ignore 清单）。缺原件、模板或登录条件时继续独立可做工作并如实留缺口，不虚构业务、不将历史验收冒充当次结果。

## 协作与异常处理

- 使用 Claude-GLM team-workflow 时保持 A/B 两个独立 session 常驻。等待方挂唯一 Bash `run_in_background:true` helper wait（3600 秒），通过原生通知唤醒，先 status 再接棒；不以人工轮询替代，不另增常驻调度角色。重型测试/构建/OCR/整单错峰；宿主要求停止时遵守，不无限重挂。
- A 按冻结基线验收和派工，B 仅按自足 team-task 与当轮合同执行；多 agent 按文件所有权分工并交接原始证据，不覆盖他人修改。施工和内容验收由 agent 完成，不要求用户现场对照、手工保存或验收签字。
- 中断先核实工件、执行者、锁、registry 和页面。不得手改状态、清失败计数、换绑 session 或基线；status 仅反映 workflow 状态，不证明 waiter/进程仍存活。
- **孤儿恢复由外部 agent 处理，team-workflow 不内建通用恢复机制。**按需读 [升级建议 U6 的精简维护指南](feature01-细化报销skill/team-workflow升级建议.md#u6外部-agent-维护保留精简指南框架)及其事故记录；先只读诊断，在当次明确授权内维护，保留旧状态字节、失败历史和可回退证据，再按正常入口交接。历史事故授权不是未来清理许可。
- 待评估的升级项以专题文档为准；未获选择不自动实施。阶段合格后继续推进合同终点，不因局部完成或离线通过就宣布整体完成。

## 正常入口与材料边界

业务开工先 `python -X utf8 bpm_login.py` 只读探查当前身份；需要全新扫码时用 `--force-scan`。登录入口不预设姓名；业务 `--expect-name` 必须来自本次真实探查或核对用户明确预期，不沿用历史姓名。

```powershell
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

- 无参数不填写，不默认用旧人、旧 run 或旧计划。`--task` 只准备材料并返回 `NEEDS_INPUT`；agent 核对本次材料后生成 v1.0 可执行计划，不要求用户编写内部 JSON。新任务新 run；同任务重试须计划/操作人/配置哈希完全相同。旧格式仅显式给具体计划及 `--legacy-regression` 做只填不存回归。
- 模板按完整单号定向读取，不为找单号普查全部历史。`bpm_template.py` 支持 `--census` 缓存，或 `--live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"`；live 用同 profile 锁及临时 context，不操作恢复的原页。
- 历史仅复用有依据的稳定身份、预算和收款资料；本次日期/费用/发票/金额/关联编号不得从旧单推导。CSV/XLSX 保留前导零；执行值具备 path/locator/sha256 来源，模板、材料、计划和配置哈希参与绑定。关键原件值不清晰时集中报告缺口。
- PDF/图片须 image_documents 分类，复核 JSON 原件与提取哈希入同一 manifest。票据身份去重，票面与主要费用行分配闭合；免票行有 no_invoice_rows 理由及来源，corroborates 校验不同来源一致。Excel/票面冲突阻断，部分票面报销与数量乘单价分配不支持。具体案例的覆盖模型/测试占位例外仅按该合同执行，不推广为全局放宽。

## 校验、测试与环境

- 类型以 `bpm/types.py` 封闭注册、`automation/document-types/` 配置及实际验证证据为准；“已注册”不等于“真实整单已验收”。travel/express 使用 relations/details/costs/banks 行数组；rd_materials 另有 products，按现有档案完整编号选择并核对 name/purchaser/price/description，不新造档案。选择器须精确唯一命中。
- 金额用 Decimal；totalCost、明细和银行合计闭合，费用说明金额语义明确。新类型空表须 table_applicability 的当次来源理由；研发物品价格合计闭合，发票按 products.price 分配，只支持费用说明为空、价格为行总额的范围。新类型非空关联、未建模数量/单价乘数量、借款抵扣、附件/贴票及未支持业务继续拒绝。
- 真实 Chromium/Playwright 验收覆盖当次身份、选择器、类别联动、全部行写入和独立 DOM 全值/行数/金额、额外/重复/缺失数据核对；按合同完成新 session 使用验收。静态 HTML、localhost、接口回放、直接改 DOM 或写入函数返回不能替代真实填写。
- 修改 `bpm/browser_probe.py` 或其兼容入口后，先 `python -X utf8 stage1_probe_selftest.py` 全绿再实单；相关改动执行 `python -X utf8 -m unittest discover -s tests`。保留 600ms 轮询、Tab 失焦及重复回读，不优化防御等待、不承诺固定耗时。
- 统一离线验收 `python -X utf8 verify_bpm_build.py` 覆盖 selftest、单元/本地 DOM 测试、合成截图及哈希，产物在 `automation/offline-verify/<run>/`，不连接生产 OA。纯文档修改核对内容、引用与边界；涉及真实业务行为时按合同验收。
- cwd 为仓库根；`fill_once.py` 自动 chdir。Python 一律 `-X utf8`；Chromium 必须 `--no-proxy-server` 直连 OA，不走 VPN/Clash。Windows 判活用 ctypes OpenProcess，禁 `os.kill(pid,0)`，会杀停靠浏览器。

## 登录身份与期限

- 每次业务开工、扫码成功及账号切换后，先取得 profile 锁，检查本机元数据/已知期限，再通过真实 OA 顶栏/个人资料及已观察的只读认证响应核实人员与登录有效性。缓存 JSON、残留姓名、文件存在或 mtime 均不足以证明登录有效。
- 尽量取得 user_id/employee_id/name/company/department，记录来源、时间和核实层次；未知为 null 并说明原因。区分操作人、制单人、申请人，后两者从真实新页观测，不按历史模板改写。同名、身份不唯一或来源冲突时阻断相关写入；用户明确预期与实际不符则拒绝，不改预期。执行前及终局再次核对；账号变化不继续旧人的任务、不迁移旧 registry。
- 扫码成功和每次探查后原子更新 `automation/.local-session/<profile_id>/session_record.json` 及仅含当前 profile 引用的 `current.json`。profile_id 为本机随机标识；使用前以 `git check-ignore` 核实排除。不同同事/机器不共享认证文件。元数据仅含最小身份/状态/时间/期限依据/本地凭证引用，禁止完整认证响应、手机号、银行资料、cookie/token/storage 原值。
- 本地最大复用窗口为真实扫码起点后 30 天；`local_reuse_until = last_scan_at + 30 天`（60 天时期旧合法记录生效窗口收紧为 `min(原窗口, last_scan_at+30 天)`，不整体作废、不延长），与已知相关服务端期限取更早边界，不能保证 30 天免扫码。普通探查/写回不重置起点；只有实际观察到合法刷新才更新对应期限并留依据，不拿无关 cookie 期限代替 OA 会话期限。登录页如有合规保持登录选项可选适用最长值，不伪造设置或修改凭证期限。
- 缺可信扫码时间的旧状态仍限 24h，不从 mtime 反推 last_scan_at，不触碰文件伪造续期。新扫码用全新临时 context，不注入旧凭证。失效时停写并按 `WAIT_HUMAN_LOGIN` 保留页面/工件；账号持有人扫码，agent 不代扫、不绕过，其余独立工作继续。

会话记录字段契约（时间使用带时区 ISO 8601；未知用 null，不能猜测）：

| 字段组 | 必需内容 |
|---|---|
| 记录身份 | schema_version、profile_id、OA origin、随机 session_generation（非服务端 session ID） |
| 当前人员 | principal 的五项身份字段、default_creator/default_applicant 实际观测、identity_source、identity_checked_at、identity_verification_level |
| 扫码与核验 | last_scan_at（仅真实扫码更新）、last_authenticated_at、last_checked_at、auth_status：authenticated/expired/needs_scan/unknown/identity_mismatch |
| 期限 | local_reuse_days=30（旧记录可存 60，生效窗口按 min 收紧）、local_reuse_until、server_expires_at、expiry_source、relevant_credential_expires_at、effective_reuse_until；服务端最大期限未知保持 null |
| 凭证引用 | credential_ref 仅限受保护目录内本机相对引用；last_check_reason 为无敏感值简述 |

登录改造须覆盖两名不同人员/同名、账号切换、缓存身份不符、30 天边界（含 60 天旧记录收紧三档）、服务端提前失效、未知到期、缺扫码时间、mtime 改动及脱敏/Git 排除，并有真实浏览器登录/身份/工作前探查验证；时间边界可离线模拟。依据：[Playwright 认证状态](https://playwright.dev/python/docs/auth)、[OWASP 会话过期](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html#session-expiration)。

## 代码与证据入口

目录职责与旧代码路径映射见 [仓库目录与维护入口](docs/repository-layout.md)；业务实现位于 `bpm/`，诊断和验证工具位于 `tools/`，根目录保留常用命令兼容入口。

- 任务/计划/材料：`fill_once.py`、`bpm/plan.py`、`bpm/materials.py`、`bpm_template.py` 及 `automation/*schema.json`。
- UI/回读/保存：`bpm/ui.py`、`bpm/verify.py`、`bpm/save.py`、`stage1_browser_probe.py`；登录：`bpm_login.py`、`bpm/session.py`。
- 逐轮证据：`automation/runs/`、`team-progress/team-workflow/`；能力与历史结果按 [STATE.md](STATE.md) 的直接证据入口查阅，不沿用历史 attempt 匹配计数。
