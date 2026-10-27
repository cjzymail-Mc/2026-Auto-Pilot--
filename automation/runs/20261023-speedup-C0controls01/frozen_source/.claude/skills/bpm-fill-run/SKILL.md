---
name: bpm-fill-run
description: 读取指定历史报销单及本次材料，生成并校验 BPM 报销计划，通过本仓库 Playwright 执行新单填写和具体任务已授权的草稿保存。用于企业微信 OA 报销、复核及安全恢复；提交、流转、上传不在范围内。
---

# BPM 报销填写与草稿保存

在仓库根运行，先读 `AGENTS.md`。差旅分支读 [travel.md](references/travel.md)；准备 task、生成计划或排查校验失败时读 [plan-contract.md](references/plan-contract.md)。当前只有 `document_type=travel`，其他类型返回缺口，不套用旧差旅计划。

## 日常入口

接受用户的完整模板单号、本次材料目录、报销说明、预期操作人和保存要求。模板中的稳定身份、预算、收款资料可以有来源地复用；本次日期、费用、发票、金额和关联单据必须来自本次证据。缺项或冲突集中列出，不猜值，不默认替换关联单。

1. 用 `bpm_template.py` 精确读取指定模板，保留快照及哈希。缓存 CLI 与受登录会话保护的 live 只读函数见参考；不为找一张单而重新全量普查。
2. 用 `--task` 整理材料清单和独立解析输出；这一步不启动浏览器，也不自动生成可执行计划。CSV/XLSX 保留账号、单号前导零；PDF/图片通过可用的本地文档/视觉能力提取，再提供带原件哈希、页码/区域定位的复核 JSON。每个 PDF/图片原件需显式票据分类；发票身份去重、票面金额与主要费用行分配闭合，免票行有本次规则来源。关键值无法确定或 Excel/发票冲突则 `NEEDS_INPUT`，不上传第三方 OCR。
3. 生成 v1.0 `fill-plan`，每个执行值有来源定位。先离线验证，再执行：

```powershell
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45
```

`--task` 返回 `NEEDS_INPUT` 是准备结果，不等于已填写。无参数启动会拒绝；不存在固定旧单、固定人员或固定 run 的默认填写。

## 执行与恢复

新任务独立 run，同一任务重试必须绑定同一计划、操作人和配置哈希。新增行后重新定位，选择器按确切名称及业务编号唯一匹配。终局由独立 DOM 回读核对完整行数、身份、字段及 Decimal 金额闭合，不以固定匹配项数或写入函数自报成功验收。

恢复命令是：

```powershell
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

先查 `automation/task-registry/` 和 run 工件。已有保存意图、结果不确定或已保存记录只走只读核实，不重点击、不再建单。未保存页恢复目前仅盘点页面并返回 `NEEDS_INPUT`，不声称自动恢复；保留原页和恢复工件。不要删除 registry 或换 task_id 来规避重试保护。同一 profile 仅一个执行者。

## 授权与保存

默认 `fill_only`。只有用户对本具体任务明确要求保存，计划中有同 task_id 的 `save_draft` 授权，才进入 `SaveController`。普通 `_click_guard` 仍禁止“保存”；专用控制器在新单、身份、来源/配置/计划哈希、完整回读、终局截图及点击前复核通过后，仅允许一次精确“保存”。保存后必须取得唯一单号/UUID、确认未提交，重新打开并逐项核对，才能报告 `SUCCESS_DRAFT_SAVED`。

保存并提交、发送、提交、流转、审批、暂存、贴票和上传始终不在本任务范围；禁止直接写接口、放宽通用守卫、自动确认未知对话框。`SAVE_UNCERTAIN` 立即转只读核实。

## 环境与交付

- OA 必须 `--no-proxy-server` 直连，不经 VPN/Clash。本地登录态 24h TTL 滚动续期；服务端提前失效仍需人工扫码。
- `automation/.pw-profile/` 含活体 token，不复制进 git、日志、材料清单或报告。Windows 判活用 ctypes OpenProcess，禁用 `os.kill(pid, 0)`。
- 改过主探针先跑 `python -X utf8 stage1_probe_selftest.py` 全绿；统一离线验收为 `python -X utf8 verify_bpm_build.py`，结果及合成截图/哈希在 `automation/offline-verify/<run>/`。保留 600ms 轮询、Tab 失焦与重复回读等稳定机制，不承诺固定耗时。
- 结果以 `events.jsonl`、attempt 下 `stage1_result.json` 和证据为准。返回阶段/状态、run/attempt、缺口或差异、截图；只有持久化复核成功才返回新草稿单号、金额和未提交状态。区分代码实现、离线验证、真实填写验证和真实保存验证。

旧方案仅供显式只填不存回归：同时传具体 `--fill-plan` 路径、`--expect-name` 与 `--legacy-regression`；不用于日常任务或草稿保存。
