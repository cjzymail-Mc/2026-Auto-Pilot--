# team-workflow 新任务收尾：独立前向复核

日期：2026-10-28。审阅范围为 `staged/team-workflow/` 下列冻结文件；只读检查候选代码与文档，所有执行均使用 TemporaryDirectory 合成仓库。没有修改实际 workflow state、任务/进度、共享技能母本、OA、凭证或真实会话，也没有向实际 GLM 窗口发消息。

## 结论

当前哈希集下，已复现的 4 类问题及其终态分支均已修复。未发现阻止所述新任务场景的剩余高置信缺陷。独立实跑证明 DONE 自动归档、可核实静止的中断任务按 CANCELLED 退役后，均能继续创建不同 run 的 B_READY；不会把未完成任务记为 DONE。

此结论是代码/说明与隔离机制验证，不替代真实 Claude-GLM 双窗口生产验收。最终文档正确区分了可自动处理与必须保留现场的情况：旧执行者/waiter 存活、根任务归属不明、绑定进程依据缺失、人工门或归档冲突均应停止依赖动作。原执行窗口可按正常 stop/pause 收束，不通过复制旧 session ID 获取执行权。

## 独立发现与修复复核

1. **新草稿被归入旧任务并清空（已修）。** 最小原反例：旧 B_RUNNING 状态遗留，根 team-task.md 已换成新的裸未执行草稿，系统盘点确认旧执行者退出；旧代码返回 NEW_TASK_READY 并清空新草稿。修复后以 source 块和进度身份验证旧归属。独立复验返回 SOURCE_BLOCK_AMBIGUOUS，state/任务/进度原字节均不变。另发现 `ready → stop(B) → CANCELLED` 尚无 last_live 时同样会清空新草稿；修复后该终态也验证合法发布字节，独立复验返回 PUBLICATION_FILE_DRIFT，三份根文件均不变。
2. **PID 复用后跳过当前相关命令（已修）。** 最小原反例：旧绑定记录 pid=22、起点=old，当前 pid=22 起点=new，当前命令明确带旧 run；旧代码因 pid 在 relevant_pids 中跳过命令检查并放行。修复后仅跳过已确认对应的存活会话，复用 PID 仍检查当前命令。独立复验返回 OLD_EXECUTORS_NOT_QUIESCENT / related_process_alive。
3. **绑定记录缺失被当作退出证明（已修）。** 最小原反例：sessions 目录存在但原 A/B 记录均消失，旧父 PID 留下一个 `python worker.py` 子进程，命令没有 repo/run 字串；旧代码返回 bound_processes=[]、blockers=[]。修复后要求每个绑定角色存在 live registry 或已捕获进程身份；缺少时返回 BOUND_PROCESS_EVIDENCE_MISSING。新增最小 PID/创建起点捕获供记录被删除后核实，保留子孙进程链检查。
4. **LIMIT/CANCELLED 的 unfinished 错为 false（已修）。** 旧返回值把 unfinished 等同于本次是否中断退役；现区分 interrupted 与 unfinished，后者由最终状态是否 DONE 决定。独立中断退役实跑为 CANCELLED + unfinished=true；DONE 实跑为 unfinished=false。

同一原 B 会话仍存活时会被保守阻断，这是明确保留的边界。最终 relay §5 已说明先正常 stop/pause 关闭在途工作，不因调用者与旧进程同窗就忽略后台执行；不列为缺陷。

## 最终独立执行结果

系统盘点接口使用合成 process snapshot、起点和 session roots；文件、归档及 Windows named mutex 使用真实临时目录和本机机制。未扫描或修改实际 workflow 现场。

| 场景 | 观察结果 |
|---|---|
| A/B 两绑定进程都有来源且已退出 | 静止核验通过 |
| 旧父进程退出，子进程只含相对命令 | related_process_alive，拒绝 |
| PID 已复用但当前命令带旧 run | related_process_alive，拒绝 |
| sessions 存在但所有绑定记录和已捕获依据缺失 | BOUND_PROCESS_EVIDENCE_MISSING，拒绝 |
| 注册行消失，但原角色保留最小 PID/创建起点 | 静止核验通过 |
| 合法孤儿退役 → 新草稿 → init | 原 state 原字节保留；旧 CANCELLED；不同新 run 为 B_READY |
| B_RUNNING 遗留 + 新裸草稿 | SOURCE_BLOCK_AMBIGUOUS；三根文件字节不变 |
| 无 last_live 的 CANCELLED + 新裸草稿 | PUBLICATION_FILE_DRIFT；三根文件字节不变 |
| 正常 DONE → prepare-new → 新草稿 → init | state 与任务/进度精确归档；根任务/进度清空；不同新 run 为 B_READY |

上述最终独立执行过程中所审五文件哈希均未变化。还检查了已有 receipt 重放、归档冲突、清理前后漂移判断及旧 waiter 读取指定旧 run 的不可覆盖终态归档：没有发现新 run 被旧 waiter 接管的控制流。

主代理提供的 `validation/workflow-tests.log` 经只读核对显示 `Ran 55 tests in 8.021s / OK`；该 55 项不是本 reviewer 重跑。此处的前向复核另外执行了上述实际行为场景，不以日志全绿代替推导。

## 文档可执行性

SKILL 的 run 入口先识别明确新任务，再调用 prepare-new，随后起草/init；重复当前任务走 status/resume。relay §5 说明调用者身份、原窗停止、原始证据、人工门、进程证据缺失、未完成缺口承接与业务现场边界，能够按说明完成可核实场景。终态归档不需要旧窗口授权身份，外部 actor 也不获得 A/B 执行权。代码会在未知情况保留现场，文档没有把这类拒绝包装成任务完成。

## 审阅文件 SHA256

所有路径相对 `staged/team-workflow/`。

| 文件 | SHA256 |
|---|---|
| SKILL.md | `dec8520b228f587adddd1e56a61bb5547e80771be8b5969c6a7cd7830d614a52` |
| references/relay.md | `a6e559f8d62dfa3aba07dcdd02d8a03f54fd29697edefd828224575579f1a7f8` |
| scripts/workflow.py | `55c8ff1e86545c3c263a3cc727662c273d666dc81a7328cda0505496a7b04093` |
| scripts/prepare_new.py | `0b2dd1ae42eecf0cf38e3f79768a897c3fb09299b601a308798cf2c68889d1d3` |
| fixtures/test_prepare_new.py | `e59d423cf2829a380bad6605ee117bdeadad5d5e54e878b5a11e9cbbce6503bc` |
