# 新任务前自动收尾

2026-10-28。用户要求：旧 workflow 已完成时自动归档；旧 workflow 意外中断时，处理旧状态、归档后继续明确的新任务。

实现入口为共享 `team-workflow/scripts/workflow.py prepare-new`，由技能在明确的新任务启动前调用；普通状态查询、重复进入当前任务和原任务 resume 不触发清理。当前真实 session 可收尾终态，外部维护如实记录 actor，不冒用旧 A/B ID。

- DONE/LIMIT/CANCELLED：核对旧根文件归属，先保留原字节与最终归档，再清空旧 task/progress、移除活动 state。
- 非终态：一次性核对绑定进程、进程创建时间、相关子进程及 waiter；确认静止且文件属于旧任务后，保留原状态/合同/失败历史，记 CANCELLED 并归档，未完成不签 DONE。未来 init/join/enter 保存最小进程身份，缺乏可核实进程依据的历史 run 保留现场并报告缺口。
- 官方 archive 已完成但根目录遗留旧文件：仅在字节与该 run 的 final 一致时自动清理。新草稿、运行中的任务、未知状态、归档冲突和同一基线人工门继续保留。
- 中途失败按同一 receipt 重试；旧 wait 可读取已归档终态，不接入新 run。没有常驻服务、自动杀进程、业务续填或保存授权变化。

验证：原 33 项回归＋22 项新增测试，共 **55 项通过**，包含 Windows 事件/互斥锁/真实子进程、角色与来源归属、PID 复用、缺失进程依据、清理中断重试和新草稿保护。日志：[workflow-tests.log](validation/workflow-tests.log)。本机真实只读 Windows 进程盘点通过：[windows-census.json](validation/windows-census.json)；沙箱内 WMI 被拒后，经只读提权验证，不杀进程、不导出命令行。

技能 YAML 可解析，原 frontmatter 完整保留。Codex quick_validate 对前后两版均因既有 Claude 专用 `argument-hint` / `disable-model-invocation` 返回 1；没有删字段换取通过，见 [skill-validation.json](validation/skill-validation.json)。独立核查及文件哈希见 [review.md](review.md)、[候选清单](candidate-hashes.json)，安装结果见 [installed.json](validation/installed.json)。

本次工作期间，另一个 Claude-GLM 会话已完成旧 run `9dc3722f20eb474b8851c942a8a78454` 的官方归档，并于 12:03 启动 FASTLANE 新 run `06410a6c201d4f19957c4a6056d4254d`。该事实只说明当时现场，不冒称由本次新入口完成。此安装不改实际 state、team-task 或 team-progress，不干预正在进行的新任务；未启动 OA、未改业务 registry 或凭证。

验证层次：自动收尾实现及隔离机械测试通过；实际旧阻塞已由另一会话解除。新入口的真实 Claude-GLM 新任务端到端使用仍待下一次合适任务观察，不用合成夹具冒充真实双窗口验收。

只安装五个文件：workflow.py、新 prepare_new.py、新 test_prepare_new.py、SKILL.md、relay.md。修改前原字节在 `before/`，安装采用原/候选哈希检查并经运行时 junction 回读。回退前先确认安装文件仍等于本次候选哈希；有后续改动时不可直接覆盖，新增文件亦不得误删后续版本。
