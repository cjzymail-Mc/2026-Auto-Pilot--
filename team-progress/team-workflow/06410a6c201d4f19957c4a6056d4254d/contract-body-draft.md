### 冻结合同（2026-10-28，profile=full）

**① 任务终态**：BPM-FASTLANE-20261028-V2 计划 G1—G5 全部落地——`bpm/oneshot.py` 单会话贯通执行入口（任务/已就绪计划两输入分支）、A1 日常自动保存授权编译器（三分支＋最终计划四绑定＋重试幂等）、同 context 只读副页全量持久化核验＋完成后立即交付＋限时保页、G4 分阶段计时与 1/1/1/1 生命周期计数、G5 受影响文档同步；C01—C13 判据逐项满足并留证据，单份结果记录与 STATE 收尾；无用户当次真实业务输入时真实首验如实标"待验"并列缺口，不宣称全包真实验收。

**② 权威源·主线·范围**：权威源＝repo `AGENTS.md`＋任务 source（src-8a759dc1）＋本合同；详细执行规格＝`feature02-扩展更多单据类型/2026-10-28 单会话贯通执行与日常自动保存接线施工计划.md` §3/§5/§6/§8。冲突优先级：用户最新明确指令＞repo 硬规则/已封决策＞本合同＞检查点计划＞历史说明。允许写：`bpm/oneshot.py`(新)；`bpm/ui.py`、`bpm/fill_cli.py`、`bpm/request.py`、`bpm/plan_generate.py`、`bpm/template.py`、`bpm/login.py`、`bpm/save.py` 按需窄改；`bpm/browser_probe.py` 窄改后先 selftest 全绿再实单；schema 仅最小兼容调整不新增用户材料格式；`tests/`；`.claude/skills/bpm-fill-run/` 手册与登记；`docs/repository-layout.md`；`AGENTS.md` 入口短指针；`feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md`；`STATE.md`；`automation/runs/<新run>/`。只读：原件目录、`automation/task-registry/`、`.pw-profile/`、`.local-session/`、历史 runs、`team-progress/team-workflow/` 归档、自驾合同与工程、`bpm/session.py`（不改期限/身份规则）、`bpm/chain.py`、workflow helper。禁止：计划外 OA 业务写入（G2 编译的同任务 `save_draft` 仅在用户当次提供真实输入时单次执行）、保存并提交/发送/流转/审批/暂存/贴票/上传、改 workflow helper/状态机、恢复自驾工程、回读缓存、常驻服务、`chain.py` 扩建、办公/福利页面、无限期留页、控件等待优化、删锁/换 task_id/清 registry。保留无关工作树改动。

**③ 全局 done_when**（=计划 §6 C01—C13；验证＝结果记录逐项证据＋原始工件）：
- D1(C01) `bpm.oneshot` 两输入分支落地；任务分支模板/身份→最终计划真实接线；旧命令兼容（验证：模块实现＋两分支离线测试＋旧 CLI 回归）。
- D2(C02) 单会话与锁所有者契约、借用方不重复 launch/close/加解锁、驻留与异常清理（验证：离线测试＋events）。
- D3(C03) 正常认证复用路径业务执行者/浏览器实例/业务 context/锁所有者各一次；驱动子进程与扫码例外按 G4 记录（验证：events 阶段事件计数）。
- D4(C04) 授权三分支、真实用途依据、最终计划四绑定、重试幂等；无自引用、冻结后不改绑（验证：离线授权测试）。
- D5(C05) SaveController/adapter 新鲜复核保留；至多一次唯一保存；registry 优先只读核实（验证：代码 diff 无放宽＋测试）。
- D6(C06) 终局独立 DOM 全量回读覆盖行数、身份、全部字段、金额闭合（验证：verify_snapshot 集成测试）。
- D7(C07) 无回读缓存；人工/异步变化反例、各中断状态、仅盘点未保存页边界（验证：故障注入测试）。
- D8(C08) 同 context 自有只读副页重开、全量持久化核验与截图、唯一单号/UUID/未提交；主 tab 未被核验导航或关闭（验证：保存后核验测试）。
- D9(C09) 终局落盘后立即交付；限时驻留零业务写入、持锁、下一任务占用边界（验证：短驻留夹具测试）。
- D10(C10) 硬禁令、凭证隔离、30 天规则、全新扫码与他人页面保护不变（验证：click_guard 回归＋git 无敏感入档）。
- D11(C11) 针对性相关验证＋`verify_bpm_build.py` 统一离线验收全绿（验证：offline-verify 产物）。
- D12(C12) 合法真实首验及阶段计时；可比部分才报速度差异；无输入则明确"真实保存待验"并列缺口（验证：run 证据或缺口清单）。
- D13(C13) G5 受影响文档如实同步、保留自驾等未完成范围；单份收尾结果及必要 STATE 快照（验证：文件实物）。

**④ 检查点路线**（依赖序）：CP0 差异核对与计时基线→CP1 G1 两分支骨架＋共享会话/页面归属契约（ui/fill_cli/template/login 借用接口正式接入）→CP2 G2 授权编译器＋四绑定与重试→CP3 G3 副页全量核验＋立即交付＋限时保页→CP4 离线回归（新测试＋相关既有测试；改 browser_probe 先 selftest）→CP5 真实首验（仅当用户当次提供输入；否则列缺口）→CP6 G4 度量与生命周期计数→CP7 G5 文档同步→CP8 ENHANCED_FINAL fresh 终审→CP9 收尾（结果记录/STATE/mc-update→pin→session-new）。每 CP 证据入 `automation/runs/` 或 round 目录。

**⑤ 红线·禁止·人工门**：四红线（销毁性/不可逆；对外交付物与 Ldterm；同 failure_key 三次熔断；推翻已封决策）照 team-task 全文；本项目另禁：计划外 OA 业务写入、非授权保存/提交族点击、代扫登录、注入旧凭证、临时 context 接管他人未保存页、放宽 click_guard/registry/Decimal 闭合/新鲜回读/600ms 轮询/Tab 失焦、回读缓存、多档配置中心、控件等待优化。已前置授权（用户 run 启动）：允许写清单内仓库写入、真实 OA 只读探查/查询/模板读取、离线验证运行、`automation/runs/<新run>/` 写入。后置人工门（PENDING_HUMAN_NONBLOCKING 攒批）：git commit、任何 rm/伸敏感目录类权限命令、对外发布。缺真实业务输入不阻断离线施工，如实标待验。P0.5 风险 envelope：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。

**⑥ 纠偏三问与陪审扳机**：按 team-task SKILL「spawn 短锚与里程碑五件套」节执行，不在本合同复制；首次非红线失败走 FIRST_FAILURE_MXP_REVIEW（一次性 mc-expert HISTORY）。

**⑦ 交接口径**：里程碑五件套指针同上；本轮最终交接按 team-workflow relay §2（handoff-input.json＋artifacts 哈希＋非空 evidence＋failure_counts 全量）。
