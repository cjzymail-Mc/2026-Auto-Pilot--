# team-progress
> run_id: 20261027-181944-b25a30da
> source_block_id: src-b25a30da
> contract_id: ctr-a820e88c
> effective_contract_id: ctr-a820e88c
> run_status: COMPLETE
> author_runtime: CLAUDE_GLM
> risk_class: MEDIUM
> risk_owner: USER
> risk_source: USER_STANDING_POLICY_20260904
> runtime_policy: GLM_ALLOWED
> risk_escalation: NONE
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
> P1已核事实: 见「进度日志」2026-10-27 P1 条目（代码/交互/文档三层，路径均可复核）

runtime_evidence=CLAUDE_GLM/glm-5.3（workflow helper `enter`/`permit` 已从本 session transcript 一手验证：`C:\Users\xy198\.claude-glm\projects\D--Downloads-Mc-Claude-Code-Workshop-2026-Auto-Pilot-----\706c8bdb-305d-42e6-8d16-94b8465b838f.jsonl`）

workflow 上下文（team-workflow-run 受控委托）：
- workflow_run=9dc3722f20eb474b8851c942a8a78454 / workflow_round=1 / entry=team-workflow-run
- 授权：用户 2026-10-27 18:19 于本窗口 `/team-workflow run feature02-扩展更多单据类型/2026-10-27 各类runbook公共能力调用路径轻量固化施工计划.md`（B 的 run 启动授权；A 未加入，max_round=null 仅限首轮，不派第二轮）
- source_sha256=b25a30dae4579ca0c64062ba51479601564701449e7dcfbd87416f7d19594271
- 累积 failure_counts={}（workflow failures 为空，无历史迁移）
- 前置维护：旧 run 242ccba1…（CANCELLED 终态孤儿）已按 U6 外部归档至其 `final/`，记录见 `team-progress/team-workflow/242ccba1c43343f687aa1db0ae014f5b/external-archive-20261027.md`

## 漏斗默认·待确认
## 自主裁决(B)
- D1 拓扑落点：recommended=T2（C1=1/C2=1/C3=2/C4=1 总分 5），realized=T3。依据=成功率（SKILL「T3 选型纠偏」：单点串行流水线、执行体握全量 G1—G5、走读/终审均为一次性只读把关角色，无多执行体共享写状态；C4 的交接是 reviewer 事件式，常驻队反而引入 flaky mailbox 失败面）。assurance_profile=ENHANCED（GLM runtime 命中；新公共 CLI 入口；workflow 跨 session 接力），ENHANCED_FINAL fresh 终审不因 T3 减免。置信度高。

routing_mode=AUTO
recommended_topology=T2
realized_topology=T3
assurance_profile=ENHANCED
drive_mode=B
author_runtime=CLAUDE_GLM
risk_class=MEDIUM
risk_owner=USER
runtime_policy=GLM_ALLOWED
risk_escalation=NONE

## 失败陪审（failure_key / failure_count / mxp候选排序 / 本次选项 / 尝试结果）
## OPEN_BLOCKERS
## PENDING_HUMAN_NONBLOCKING
## 进度日志
- 2026-10-27 18:2x P0/P0.5 完成：init 接入起草任务（src-b25a30da），风险 envelope 落盘（GLM 常设 MEDIUM/B+AUTO）。
- 2026-10-27 18:4x P2/P3 完成：chop-task contract-only（continue-defaults；八项交底自检无事实层缺口、无问卷）；冻结合同 ctr-a820e88c（profile=full）追加至 team-task.md，fixture 链校验通过（注：本条曾在一次 Python replace 中因锚点不匹配静默丢失，本轮补录）。
- 2026-10-27 18:4x CP1/CP2 完成：bpm/query.py（+tests/test_bpm_query.py 21 项）、materials CLI（prepare_command/plan_pdf_text_pass/summarize_prepared + _safe_material 补 .local-session + extract_structured 坏 xlsx 不吞批 + tests/test_bpm_materials_cli.py 10 项）。
- 2026-10-27 18:4x CP3 完成：common-operations.md 六用法（API 符号逐一 grep 对勘）+ SKILL/入口说明/repository-layout/AGENTS 接线。
- 2026-10-27 18:5x CP4/CP5 完成：430 tests OK + OFFLINE_PASS（offline-verify/20261027-184250-draft-build）；真实只读三分支 kw2（ok，10.1s，庄旭宏≠陈晶跨制单人路径）/tpl2（ok，14.6s，快照 sha256=4efaf3a0…，products 投影比旧快照完整、按购买人归组逐人闭合 9935.16）/zero2（zero_results，sufficient=true 与 failed 区分）；匿名夹具 CLI 实跑 PREPARE_COMPLETE。首跑两真实缺陷修复（predicate 收 Response 对象；跨制单人 lookup_list hint），证据保留 -kw/-tpl run。
- 2026-10-27 18:5x CP6 完成：purchased-samples.md（七部分+实证归组+待补口径 5 项）+路由登记（SKILL/入口说明/rd-materials 指针）；test_skill_docs 9 项通过；结果记录（C01—C13 逐项证据+R3 差异表）落盘；STATE 更新。
- 2026-10-27 19:0x CP7 完成：一次性只读 Explore agent 合并走读公共参考+新手册+路由——五问全 PASS、must_fix 无、2 条建议级修订已采纳（SKILL 判别特征措辞、§5.4 plan-contract 链接），test_skill_docs 复跑 9 OK；报告归档 round-01/walkthrough-report.md。
- 2026-10-27 19:1x CP8 前置自查补验（超出计划 §5 最低要求的显式筛选实证，全部只读）：发现并修复组织选择器三处真实缺陷——③只输入不回车树从未过滤（范式复用 ui.py fill+Enter+「姓名 [工号]」）；④部门行类名 AppliedDeptPath 初版臆测、经真实筛选区 dump 实证+漂移兜底；⑤父级中心节点「确定」禁用旧版裸超时、改清洁报错且人名/组织判别分立。新增实证 run：creator4（陈晶+日期→正确零结果）/creator5（庄旭宏→收窄其 5 单，首条 15426104120 totalCost 9935.16 吻合）/creator6+7（不存在人名/张伟→fail-closed 查询未执行）/dept6（运动表现研究部→收窄 appliedDeptName 精确匹配）/dept7（科技中心父节点→禁用确认不点击）；430 tests OK + OFFLINE_PASS 重跑（offline-verify/20261027-192354-draft-build）；manifest v3 冻结（15 产物实算哈希，enhanced-final-manifest.txt）；common-operations.md 补部门口径注、结果记录/STATE 同步。
- 2026-10-27 19:2x CP8 完成：新鲜一次性 mc-expert ENHANCED_FINAL（envelope 全字段：MEDIUM/USER/GLM_ALLOWED/manifest v3/UNVERIFIED_SCOPE=NONE 及同名歧义不可构造声明）审计 15 产物与 8 审计面——**VERDICT=GO**（8 面全过=7 动态+1 静态、哈希开审/收审双算 VALID、UNVERIFIED_SCOPE=NONE、封印决策无触碰、无 P0/P1）。reviewer 独立复算：430 tests 复跑、tpl2 快照哈希+Decimal 归组闭合、dept6 appliedDeptName 原件证实、20 run 锁计数、阳控三件确证「失败被安全拦截」。4 个 P2 均不阻断：P2-1/P2-2（结果记录 C08 指旧 offline 目录、dept6 耗时 15.1s 应为 32.2s）已按其许可当场订正并以 manifest v4 重冻（仅施工结果.md 变哈希，其余 14 项与获 GO 状态逐字节一致）；P2-3（tpl2 三个含真实收款账户文件）已按既有惯例 .gitignore per-path 排除并 git check-ignore 验证，本地保留；P2-4 三项代码卫生留待下次触达 query.py。判决原文存档 round-01/enhanced-final-verdict.md。
- 2026-10-27 19:3x CP9 收尾：合同 fixture 复核全绿（79 contract cases + structural checks，exit 0）。收尾三步按 run skill 执行实质——mc-update：两道闸评估（频次/去重），本轮全部可固化事实已由 repo 文档承载（STATE/结果记录/公共参考），repo 记忆零写入、harness 记忆无新增（既有两条 memory 仍有效），formal /mc-update 留用户触发（其 skill 文档禁 model-driven 调用）；pin：本 harness 无该入口，实质（关键事实固化）已由 STATE+结果记录承载；session-new：按「沿母本仅固化文件」以本 progress+handoff-input.json 承载冷启动交接，不重开窗口。三段预测核对：mc-update「不改仓库业务文件」命中（仅 .gitignore 防护性追加与 progress 定稿，无产物变更）；pin「幂等无重复」命中（零动作）；session-new「无仓库写入、不清空窗口」命中。

  - `bpm/query.py` 不存在（计划前提成立）；`bpm/` 已有 login/template/materials/extraction/session/collect/ui/browser_probe 等模块。
  - `bpm/login.py` LoginProbe(Probe)：phase_entry→PASS/LOGIN_REQUIRED、wait_login、未指定 expect_name 时自动发现当前账号名；args 用 SimpleNamespace(run/doc_id/expect_name/force_scan/tech_budget/login_wait/wall_cap/fill_plan/login_only/keep_open_minutes/interactive_pick)。
  - `bpm/template.py`：fetch_template(probe, number, *, lookup_list=None, raw=False)（raw=未登记类别研究旁路）、observe_template_view(probe, snapshot)（type=view&id=<uuid> 只读页+operator 核对）、parse_list_items(body)、live_template(...)、CLI 已有 --live/--census/--research-raw/--lookup-list/--observe-view。
  - `bpm/materials.py`：prepare_dual_materials(directory, output_dir)（v2.0 双根、输出 exist_ok=False）、inventory_materials、extract_structured、register_derived、_validated_root/_check_files_in_root 保护路径基础。
  - `bpm/extraction.py`：extract_pdf_text/run_pdf_extraction/render_to_files/review_pass/extract_workbook/extract_csv_table；barstub 仅供测试。
  - `bpm/browser_probe.py` Probe：run_dir=automation/runs/<run>、attempt_NNN 自增、log_event→events.jsonl 追加、save/shot、atomic_result、acquire_lock/release_lock(executor.lock)、_click_guard、_inject_session_state/_save_session_state、_close_browser、Budget。
  - `tools/diagnostics/type_query.py` TypeQuery（诊断工具，不 import 进生产）：ROWS_PROP_JS 行解析（PrimeNG 拆表陷阱）、query_click（查询/搜索/检索 按钮守卫）、read_all_pages 翻页去重、org_select 组织弹窗；G2 交互模式以此为参照抽共享。
  - `automation/runs/20261027-purchased-sample-lookup/lookup.py`（保留证据）：关键词字段 #Description15(主表备注)/#Digest19(明细摘要)/#Description20(明细备注)；清默认制单人筛选=.form-row.CreatedPath .clear-icon dispatch_event + 回读 #CreatedPath2==''；精确单号 #BizNumber1；查询响应匹配 urlsplit 后 host=oa.api.qiaodan.com + /reimburse/query/\d+/\d+ + status 200；排序表头 th.prop-createdAt。
  - `bpm/collect.py` collect_materials 限通行费/油票/汇总单（CLASS_TOLL/FUEL_INVOICE），G3 不改名不泛化。
  - Skill：SKILL.md 路由段+日常入口+六阶段；references/ 7 文件；入口与未来扩展说明.md 有登记表（新手册按 references/<场景名>.md 登记）；docs/repository-layout.md 需登记新命令归类。
  - 登录 run：20261027-163651 FATAL PermissionError（Windows 权限，已重试）→ 163652 SUCCESS_LOGIN_ONLY；lookup events 显示 16:40 起 profile 锁序贯获取。
  - tests/ 29 个测试文件含 test_skill_docs.py（文档测试）、test_bpm_materials_dual.py、test_bpm_extraction.py、test_bpm_template.py。
  - STATE.md 工作树 M 为上一 session 交付施工计划的未提交更新（本任务上下文），保留不动。


## 当前现状
CP0—CP9 全部完成：ENHANCED_FINAL **GO**（manifest v3 审定；v4 仅含其许可的 P2-1/P2-2 勘误+P2 处置记录），合同链 fixture 复核全绿，收尾三步实质执行完毕。本轮交付：bpm.query 正式查询入口（含显式筛选三态实证）、bpm.materials prepare CLI、公共调用参考、外购样品 runbook 及五方路由登记；430 tests+OFFLINE_PASS（192354 覆盖最终哈希）。

## 下一步
B 首轮完成，A 未加入（max_round=null 仅首轮）：finish 交接后静默 3600s wait 等 A 验收；A 晚到读盘即可。不派第二轮、不自动重跑。P2-4 三项代码卫生与外购样品业务口径 5 项属后续任务输入，不属本轮。

## 卡点
## 收尾复盘
- 漂移苗头与纠正来源 + 陪审触发/跳过原因：CP8 前自查发现计划 §5 反例清单中「用户显式筛选不被清掉/同名组织歧义」仅有构造级实现——不等到终审暴露，先行真实补验并连锁发现修复三处缺陷（回车缺失/臆测类名/禁用确认裸超时），证据链留 -creator*/-dept* run；陪审触发=ENHANCED_FINAL 强制（MEDIUM+GLM 终审硬门），无跳过；失败陪审未触发（failure_counts 空）。
- 收尾三段预测（CP9 执行前落盘）：①mc-update——预期将本轮「公共入口+外购样品手册完成、自驾仍暂停」写入跨会话记忆，不改仓库文件，输出成功清单；②pin——预期固定本轮关键记忆条目（新入口命令与登记状态），幂等、不重复；③session-new——预期沿母本仅固化会话交接文件，不真清空/关闭 B 窗口，无仓库写入。三步均不应触碰 .team-workflow-state.json、run 工件或 manifest 哈希；任何一步产生 repo 文件变化即异常停止复核。
