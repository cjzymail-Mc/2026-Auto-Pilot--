# 2026-Auto-Pilot 企业微信

通过 Playwright 操作企业微信 OA（bpm.qiaodan.com）的 Angular PrimeNG 报销表单：指定历史模板、本次材料 → 可追溯计划 → 新单填写 → 独立回读 → 对本具体任务已授权的草稿保存。除差旅外，快递普通全额及研发物品档案行金额路径已接入代码；两类已完成用户授权的复杂历史回放真实填写与独立回读；真实保存、重开与未提交持久化验收尚未执行。提交、发送、流转、审批和上传不在范围内。

## 当前入口

在仓库根运行，先读 [AGENTS.md](AGENTS.md) 和 [bpm-fill-run skill](.claude/skills/bpm-fill-run/SKILL.md)。不再使用固定人员、固定旧计划或无参数填写。

代码归入 `bpm/`，诊断与验证工具归入 `tools/`，根目录常用命令保留兼容入口；目录职责与旧路径映射见 [仓库目录与维护入口](docs/repository-layout.md)。

```powershell
# 整理 task 与本次材料，不启动浏览器；返回准备工件和缺口
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"

# 完整 v1.0 计划先离线校验，再执行
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45

# 同一计划/操作人/配置绑定的安全重试
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

Task 提供完整模板单号、材料目录和本次说明；准备器只整理原件清单及解析输出，agent 核对后生成可执行 fill-plan。CSV/XLSX 支持字符串标识符和单元格来源；PDF/图片需本地提取及带原件哈希、页码/区域的复核 JSON，不能猜关键值。详见 [task/plan 契约](.claude/skills/bpm-fill-run/references/plan-contract.md) 和 [差旅规则](.claude/skills/bpm-fill-run/references/travel.md)。

类型由 `bpm/types.py` 封闭注册，入口、执行 run、UI 阶段及保存控制器共用配置身份；已有 travel 的原配置文件 SHA256 保持兼容。`express`（[快递规则](.claude/skills/bpm-fill-run/references/express.md)）支持四表普通全额；`rd_materials`（[研发材料规则](.claude/skills/bpm-fill-run/references/rd-materials.md)）增加第五表 products（物品档案），按完整编号选择现有档案并核对价格行额。空表理由须当次来源证明；新类型非空关联、研发数量乘单价及无档案建新物品均未开放。未建模业务字段不会被忽略。两类复杂历史回放真实填写已通过（快递 8 条费用/4 条银行；研发 18 条档案/4 条明细/4 条银行），上述历史轮均只填不存；10月29日快递及自驾另有明确授权的历史测试保存与独立重开，自驾含五日模拟且关联跳过，研发当日档案不可选未保存。见[最新证据索引](docs/oa-validation-20261029.md)，不外推新原件或正式oneshot全链。

PDF/图片原件须逐个分类；发票票号去重、复核金额与主要费用行分配闭合，补贴等免票行记录本次来源依据。Excel 与发票冲突会阻断；部分票面报销、数量乘单价的票据分配当前不支持。配置 capabilities 单独标注历史证据、离线验证及实单待验收状态。

`bpm_template.py --census ... --template-number ... --output automation/runs/.../template_snapshot.json` 从既有采集工件精确读取唯一模板。当前定向读取可用 `bpm_template.py --live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"`，它取得同一 profile 锁，在临时 context 内做完整单号查询和已观察 GET，不导航或关闭恢复的原页。

## 保存与恢复边界

默认 `fill_only`。用户对具体任务明确要求保存，才能写同 task_id 的 `save_draft` 授权。普通点击守卫仍禁止“保存”；专用 `SaveController` 在完整独立回读、身份/来源/计划/配置哈希、金额闭合、终局截图和点击前复核通过后，至多点击一次唯一精确“保存”。重开新单、核对完整数据及未提交状态后，才报告草稿已保存。

全局 `automation/task-registry/` 保留任务填写/保存意图。保存超时或结果不确定时只读核实，不再次点保存、不另建一张。未保存页面的自动恢复尚未实现，当前仅盘点页面并返回 `NEEDS_INPUT`。不要删除 registry 或换 task_id 绕过保护。同一 profile 只允许一个执行者。

## 环境要求

- **不走 VPN/代理**：Chromium 必须带 `--no-proxy-server`（探针已内置），直连 OA 内网；Clash 系统代理会导致连接失败。
- **登录**：`python -X utf8 bpm_login.py --force-scan` 打开全新扫码窗口并发现当前账号；每次开工先 `python -X utf8 bpm_login.py` 只读验证复用。成功扫码后的本地最大窗口为 30 天（旧 60 天记录按原窗口与扫码后 30 天的更早边界收紧），从扫码时间固定计时，不随文件写回续期；已知 refresh token 到期更早则取更早期限。旧无扫码元数据的文件仍按 24h 处理。服务端失效仍需重新扫码，不能保证 30 天免扫码。身份及期限 JSON 在 Git 排除的 `automation/.local-session/`，凭证仅在 `.pw-profile/`。
- **敏感文件**：`.pw-profile/` 含活体 token，不复制到 git、日志、报告、材料清单或测试工件。
- **Windows**：Python 一律 `-X utf8`；判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。`fill_once.py` 自动切回仓库根。
- **稳定机制**：保留探针既有轮询、Tab 失焦和重复回读，不承诺固定运行耗时。改过 `bpm/browser_probe.py` 或其兼容入口后先执行 `python -X utf8 stage1_probe_selftest.py` 全绿，再进行任何实单运行，并按改动执行 `tests/`。

统一离线验收命令为 `python -X utf8 verify_bpm_build.py`：运行主探针自测、全部单元/本地 DOM 测试，生成合成截图证据、哈希与结果到 `automation/offline-verify/<run>/`。它不操作生产 OA，离线全绿也不能替代本次实单验收。

schema 契约测试依赖可用 `python -X utf8 -m pip install -r requirements-dev.txt` 安装。人员按用户要求保留登录默认时，只读记录默认带出并核验，不主动改申请人或制单人。

仅登录并驻留 24 小时：

```powershell
python -X utf8 stage1_browser_probe.py --expect-name "操作人" --login-only --login-wait 1800 --keep-open-minutes 1440
```

## 代码与证据

| 路径 | 用途 |
|---|---|
| fill_once.py | task 准备、计划前置校验、独立 run 与绑定重试 |
| bpm/plan.py / bpm/materials.py | 计划/来源/金额校验、原件去重与结构化解析 |
| bpm_template.py | 精确缓存模板及已认证 live 只读模板 CLI/函数 |
| bpm/ui.py / bpm/verify.py / bpm/save.py | 行数组执行、独立快照验收、受控保存与只读核实 |
| stage1_browser_probe.py / bpm_login.py / bpm/session.py | profile 独占、真实账号探查、扫码后最长 30 天本地复用、直连及普通点击守卫 |
| automation/*schema.json / document-types/travel.json | task/plan 契约与差旅 UI 配置 |
| automation/runs/<run>/ | task_binding、材料工件、追加 events.jsonl、attempt_NNN 结果/证据 |
| automation/task-registry/ | 跨 run 的任务意图与保存核实记录，不得随意清理 |
| tests/ / stage1_probe_selftest.py | 合成场景测试与旧安全边界自测 |
| legacy-ia2/ / patches/ | 只读旧探索档案（本地存档，含真实卡号部分不入库）/ Windows-MCP 改造补丁 |

正式 `fill_once.py` 已完成已授权示范数据的真实新建未保存整单验证：3 关联、2 报销明细、6 费用说明、1 收款，完整独立回读无差异。C0 实测 UI_START → READBACK_END 为 191.48 秒；进一步优化的 C1 及适用范围见[提速验收记录](feature01-细化报销skill/2026-10-23%20提速施工验收记录.md)。这不代表新业务材料理解或自动保存已实单验收。

申请人与操作人不同时，计划须提供有来源的 `identity`，先核对完整人员工号及组织、选择申请人，再锁定申请人和制单人，之后不改人员。当前真实支持公出单的一对一关联明细；上方本次报销为只读汇总，金额写入准确关联明细。账号按原生可写编辑器处理，支行按完整联行号选择后核对全称；预算与科目每行独立选择。

已声明的关联明细投影为空、缺表或行数不符均拒绝。公出单一对一分支的三个系统零值列，仅在实际只读且原始显示为空时允许配置中的字段级空值；其他类型、缺列、无只读证据、错误值和非零分摊不兼容。保留原始空字符串，最终独立回读不使用写入缓存。

开发测试可使用有哈希绑定授权的 `test_context`，强制 `fill_only`，在独立临时 context 中复用受保护登录态。每轮登记新测试任务与用途，禁止借测试身份绕过原任务保存意图。原已保存演示单 15426104612 只读保护；测试授权不含新测试单保存。

`python -X utf8 -m tools.diagnostics.perf automation/runs/本轮run` 从追加事件复算 UI 窗口、动作区间并集和未覆盖时间；嵌套时间不累加。源码清单为 execution_source_manifest.json，阶段边界复核计划、来源及配置，最终独立 DOM 回读保持新鲜。

历史 attempt_026 的填写结果与旧探索材料保持原样，供回归追溯：[施工方案](feature01-细化报销skill/2026-10-23%20历史单据加本次材料新建填报并保存草稿实施方案.md)、[历史会话报告](docs/session报告/2026-10-22-session报告任务总结.md)。旧格式只在显式 `--fill-plan "旧计划路径" --expect-name "操作人" --legacy-regression` 时进入只填不存回归，不能用于自动保存。新计划不得沿用旧表中金额不闭合或来源不确定的数据。

## 正式执行入口

日常就绪任务/计划优先 `python -X utf8 -m bpm.oneshot --task|--fill-plan … --expect-name "本次操作人"`，不以临时脚本分段重启浏览器。`fill_once.py` 的v1执行进程内复用同一入口；无facts_payload的task仍只准备材料。

同单修订显式传 `--fill-plan "修订计划.json" --prior-plan "原成功计划.json" --revision-authorization "明确修订授权.json"`，先加 `--validate-only`。必须绑定原task/UUID/journal，已有修订意图只读恢复，不再编辑或保存。完整约束与停点见[公共调用参考](.claude/skills/bpm-fill-run/references/common-operations.md)。本次收尾不访问OA；正式新材料全链和原生客户端首验仍未完成。
