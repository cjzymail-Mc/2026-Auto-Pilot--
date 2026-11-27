# 请假单（明确事实填报，核验后自动保存草稿）

适用于用户以明确事实（请假类型、起止日期时分、事由）发起的真实新「请假单」。走 `/oa/leaves` 列表与 `/oa/leave?type=new` 表单（`qd-leave-detail`），由 `bpm.leave` 执行。按 [AGENTS.md](../../../../AGENTS.md) 的真实请假单日常授权（2026-11-20）：核验后**自动保存草稿**并提醒用户审核；**严禁提交、流转或推送**，任何模式都不点击这些动作。当次明确「只填」「先审」「暂不保存」优先，此时只填并驻留现场审阅、用户手工保存。

## 日常流程

1. **从用户指示取本次事实。** facts 文件四要素 `leave_type/start/end/reason`（`YYYY-MM-DDTHH:MM`，end 晚于 start），`statement` 记录当次来源或本日常授权依据；不从历史单或默认值推断。跨天请假、类型超出支持清单或事实缺项时先向用户集中核实。
2. **登录并核实身份。** 复用当前 OA 登录与独占 profile 锁；`--expect-name` 来自本次真实探查。新页自动带出申请人/制单人/部门/公司，须与当前操作人一致；单据状态为「编制中」且无单号，否则停止。
3. **填写并独立回读。** 请假类型经 p-dropdown 精确选项（回读取 input 值或 `.ui-dropdown-label`）；事由写入空白可编辑输入框；请假明细表「新增」一行，双击请假开始/结束单元格用日期时间控件写入并轮询回读到确认时分。自然日/工作日/实际起止由 OA 计算（2026-11-20 实测 8:30–13:00 计「3小时30分钟」，午休扣除为系统行为，不代改）。
4. **自动保存草稿（日常默认）。** 同 run 两段式：先用最短驻留完成只填与整单回读并自然收尾；确认原窗口退出、registry 无在途意图后，携带 `--draft-request` 保存授权执行草稿分支。授权由 agent 编译，绑定 `task_id`、`mode=save_draft`、`allow_submit=false`、facts 文件哈希、`prior_attempt` 及其 `leave_readback.json` 哈希、起止时点，`statement` 记录当次请求或 2026-11-20 日常授权依据。保存后取得唯一 UUID/单号、确认「编制中」并只读重开核对，才可报告 `SUCCESS_DRAFT_SAVED`，随后提醒用户审核。**提交、流转、推送始终不在范围内。**

## 执行与验收

```powershell
# 结构探查（新环境/结构变化时）
python -X utf8 -m bpm.leave --run "<本次run>" --observe [--api-scan]
# 第一段：填写+整单回读，最短驻留自然收尾
python -X utf8 -m bpm.leave --run "<本次run>" --facts "<事实.json>" --expect-name "<操作人>" --keep-open-minutes 1
# 授权编译后先验证
python -X utf8 -m bpm.leave --run "<本次run>" --facts "<事实.json>" --draft-request "<保存授权.json>" --expect-name "<操作人>" --validate-only
# 第二段：草稿保存（去掉 --validate-only）
```

- 保存控制器复用通用 `SaveController`（`bpm/leave_save.py`）：journal 防重复、保存意图先落盘、一次精确「保存」点击、响应身份、只读重开核对；`SAVE_UNCERTAIN` 立即转只读核实，不重试点击。
- 保存 POST 闸门仅放行主 frame 单次发出的 `https://oa.api.qiaodan.com/Leave`，请求体须含本次事由和操作人，响应须对应同一请求。若保存返回编制中的单号和 UUID，表单单号一致，且后续 `/flow/generate` 被拦并出现唯一「服务器连接失败」弹窗，保留弹窗并转入只读重开。重开回读通过后才报告保存成功。
- 网络守卫两段式：填写阶段端点级白名单（GET/HEAD/OPTIONS，另放行 `oa.api.qiaodan.com/Leave/query/20/1`、`kindlytips/query`、`affiche/homequerybyoption`；填写时点另放行 `ams.api.qiaodan.com/shiftapi/getleavereckon` 计算读）。只填审阅模式交付后调用 `enable_manual_review` 卸载端点路由再驻留，用户手工保存才能到达接口（2026-11-20 实证：不卸载会显示「服务器连接失败」）；保存分支全程保留端点路由。
- 页内 PrimeNG 对话框一律 dismiss（先 Escape，仅允许点取消/关闭类按钮），绝不点确定/是；统计分析类请求（rybbit）持续拒绝。
- 当前支持：单行明细、年假（已实测填写）；类型下拉其余选项（事假/病假/产假等）结构同源、未逐一实测。不支持：多行明细、关联单据填写、附件上传、工作交接/备注自动填写（保留默认空）、实际起止改写（系统自动带出）。
- 失败恢复时，`NEEDS_INPUT` 驻留现场供排查。已有保存意图、结果不明或已保存时，以原任务的响应和回读证据只读核实，禁止再次保存或重建。

## 真实验收与证据

2026-11-20 首次真实任务完成结构探查（attempt_007）及年假填写和独立 DOM 回读（attempt_011）。该单由用户手工保存并自述已流转。

2026-11-27 首次真实自动保存返回 HTTP 200，后续流程请求被拦后，旧代码将弹窗判为 `SAVE_UNCERTAIN`。同任务只读重开确认草稿为「编制中」，全部明细与点击前一致。证据见 `automation/runs/20261127-leave/` 的 attempt_002 保存观察和 attempt_003 重开验证。修复后已离线测试弹窗判定，待下一笔真实授权业务验证新版端到端保存。

执行结果以 `automation/runs/<run>/events.jsonl` 的 `result_delivered`、attempt 的 `leave_readback.json`、`review.png` 及保存分支的 `save_result.json` 为准。真实运行原始工件仅留本机。
