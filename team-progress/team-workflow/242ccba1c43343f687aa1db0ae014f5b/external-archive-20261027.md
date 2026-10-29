# 外部维护记录：CANCELLED 终态孤儿归档（2026-10-27 18:20）

按 AGENTS.md「孤儿恢复由外部 agent 处理」及 [U6 精简维护指南](../../../feature01-细化报销skill/team-workflow升级建议.md#u6外部-agent-维护保留精简指南框架)执行。当次授权：用户于新 session（`706c8bdb-305d-42e6-8d16-94b8465b838f`）执行 `/team-workflow run feature02-扩展更多单据类型/2026-10-27 各类runbook公共能力调用路径轻量固化施工计划.md`，明确启动新任务；STATE.md 亦预写续作方式为「原窗口 archive → 新 run」。

## 只读定位结论

- run `242ccba1c43343f687aa1db0ae014f5b`（BPM-SELFDRIVE-20261027-V1）phase=CANCELLED（终态，round 2，用户 13:11 指令暂停施工、B 检查点收束确认）。
- 原绑定 B（`c05e555a…`）/A（`9acdfc57…`）session transcript 最后活动均定格 2026-10-27 15:19:57，至维护时刻静默约 3 小时；新窗口 helper `archive` 因 `WINDOW_ROLE_MISMATCH` 拒绝，属原窗口不可达的终态孤儿。
- 根 team-task.md / team-progress.md 哈希与 state `last_live` 记录一致（eaf909ca… / db5ec5c5…），现场未漂移。

## 实际迁移项（字节保留，sha256 已回读校验一致）

| 原根文件 | 归档目标 | sha256 |
|---|---|---|
| `.team-workflow-state.json`（2551B） | 本目录 `final/state-final.json` | 21a71b256b9d5c7a…bea7dec1a |
| `team-task.md`（14351B，R2 末轮任务） | 本目录 `final/team-task.md` | effea9f03e7a2ce4…1a1bfcbf |
| `team-progress.md`（8927B，R2 暂停进度，非收口） | 本目录 `final/team-progress.md` | 42f25f72f9785c8e…73c72fb8 |

操作与 helper `archive` 等价（`workflow.py:403-407`：archive_live → final/、state-final.json、删除根 state）；额外移除非收口根 team-progress.md 是为满足 `prepared_task` 的 `OLD_RUN_UNCLOSED` 检查，其字节已先归档。

## 回退条件

将上述 `final/` 三文件按原名复制回仓库根即可恢复归档前状态（state 仍为 CANCELLED 终态；如需重开须再次走合法入口）。未改动本目录其余归档（round-01 全套、round-02 source.md、criteria、before-start、provenance-erratum）及任何业务原件、registry、锁、页面。

## 后续

旧 run 记录为**未完成退役**（R2 未 finish，不宣称 DONE；自驾工程暂停状态与遗留见 STATE.md）。新 workflow 按用户指令以「公共能力调用路径＋外购样品 runbook 施工计划（BPM-COMMON-20261027-V1）」起草首轮任务并在新 session 正常 `init`，不继承旧 run 失败计数（state `failures` 为空，无需迁移）。
