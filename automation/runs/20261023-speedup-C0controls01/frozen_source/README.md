# 2026-Auto-Pilot 企业微信

通过 Playwright 操作企业微信 OA（bpm.qiaodan.com）的 Angular PrimeNG 报销表单。当前实现差旅分支：指定历史模板、本次材料 → 可追溯计划 → 新单填写 → 独立回读 → 对本具体任务已授权的草稿保存。提交、发送、流转、审批和上传不在范围内。

## 当前入口

在仓库根运行，先读 [AGENTS.md](AGENTS.md) 和 [bpm-fill-run skill](.claude/skills/bpm-fill-run/SKILL.md)。不再使用固定人员、固定旧计划或无参数填写。

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

PDF/图片原件须逐个分类；发票票号去重、复核金额与主要费用行分配闭合，补贴等免票行记录本次来源依据。Excel 与发票冲突会阻断；部分票面报销、数量乘单价的票据分配当前不支持。配置 capabilities 单独标注历史证据、离线验证及实单待验收状态。

`bpm_template.py --census ... --template-number ... --output automation/runs/.../template_snapshot.json` 从既有采集工件精确读取唯一模板。当前定向读取可用 `bpm_template.py --live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"`，它取得同一 profile 锁，在临时 context 内做完整单号查询和已观察 GET，不导航或关闭恢复的原页。

## 保存与恢复边界

默认 `fill_only`。用户对具体任务明确要求保存，才能写同 task_id 的 `save_draft` 授权。普通点击守卫仍禁止“保存”；专用 `SaveController` 在完整独立回读、身份/来源/计划/配置哈希、金额闭合、终局截图和点击前复核通过后，至多点击一次唯一精确“保存”。重开新单、核对完整数据及未提交状态后，才报告草稿已保存。

全局 `automation/task-registry/` 保留任务填写/保存意图。保存超时或结果不确定时只读核实，不再次点保存、不另建一张。未保存页面的自动恢复尚未实现，当前仅盘点页面并返回 `NEEDS_INPUT`。不要删除 registry 或换 task_id 绕过保护。同一 profile 只允许一个执行者。

## 环境要求

- **不走 VPN/代理**：Chromium 必须带 `--no-proxy-server`（探针已内置），直连 OA 内网；Clash 系统代理会导致连接失败。
- **登录**：本地 `automation/.pw-profile/session_state.json` 为 24h TTL 滚动续期。服务端会话提前失效仍需人工扫码；这不等于服务端保证 24 小时免扫码。
- **敏感文件**：`.pw-profile/` 含活体 token，不复制到 git、日志、报告、材料清单或测试工件。
- **Windows**：Python 一律 `-X utf8`；判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。`fill_once.py` 自动切回仓库根。
- **稳定机制**：保留探针既有轮询、Tab 失焦和重复回读，不承诺固定运行耗时。改过主探针先执行 `python -X utf8 stage1_probe_selftest.py` 全绿，再进行任何实单运行，并按改动执行 `tests/`。

统一离线验收命令为 `python -X utf8 verify_bpm_build.py`：运行主探针自测、全部单元/本地 DOM 测试，生成合成截图证据、哈希与结果到 `automation/offline-verify/<run>/`。它不操作生产 OA，离线全绿也不能替代本次实单验收。

仅登录并驻留 24 小时：

```powershell
python -X utf8 stage1_browser_probe.py --expect-name "操作人" --login-only --login-wait 1800 --keep-open-minutes 1440
```

## 代码与证据

| 路径 | 用途 |
|---|---|
| fill_once.py | task 准备、计划前置校验、独立 run 与绑定重试 |
| bpm_plan.py / bpm_materials.py | 计划/来源/金额校验、原件去重与结构化解析 |
| bpm_template.py | 精确缓存模板及已认证 live 只读模板 CLI/函数 |
| bpm_ui.py / bpm_verify.py / bpm_save.py | 行数组执行、独立快照验收、受控保存与只读核实 |
| stage1_browser_probe.py | profile 独占、24h 登录态、直连、主执行及普通点击守卫 |
| automation/*schema.json / document-types/travel.json | task/plan 契约与差旅 UI 配置 |
| automation/runs/<run>/ | task_binding、材料工件、追加 events.jsonl、attempt_NNN 结果/证据 |
| automation/task-registry/ | 跨 run 的任务意图与保存核实记录，不得随意清理 |
| tests/ / stage1_probe_selftest.py | 合成场景测试与旧安全边界自测 |
| legacy-ia2/ / patches/ | 只读旧探索档案 / Windows-MCP 改造补丁 |

当前代码包含上述 v1 路径及离线验证；真实填写与真实保存是否通过，必须以相应 run 工件另行确认。当前施工任务未提供本次真实模板单号和材料目录，不能据此宣称端到端实单已完成。

历史 attempt_026 的填写结果与旧探索材料保持原样，供回归追溯：[施工方案](feature01-细化报销skill/2026-10-23%20历史单据加本次材料新建填报并保存草稿实施方案.md)、[历史会话报告](docs/session报告/2026-10-22-session报告任务总结.md)。旧格式只在显式 `--fill-plan "旧计划路径" --expect-name "操作人" --legacy-regression` 时进入只填不存回归，不能用于自动保存。新计划不得沿用旧表中金额不闭合或来源不确定的数据。
