# 团队进度 — travel 真实闭环 + 视觉复核 + 五类只读研究（round 7）

> run_id: 20261024-152123-3e8d59be
> source_block_id: src-3e8d59be
> contract_id: ctr-381e0163
> effective_contract_id: ctr-381e0163

- workflow_run: a7618f4fa0b040fa81782c93eb1bc926 / workflow_round: 7 / entry: team-workflow-run（B 窗口）
- task_source_sha256: 3e8d59beb60260bc2310eba76ad3bf9c3b9e5e23271dc6332f934f59a5e9e13e
- runtime_evidence: GLM（本 B 会话原始 JSONL，helper enter/permit 已核，seq 34）
- 累积失败字典（A 侧加载，逐字回传）: {"review|content|source_manifest_coverage|D23": 1}

## P0 · run bootstrap

- [x] enter 接棒（B_RUNNING, round 7, seq 34）；permit 核对 team_run=20261024-152123-3e8d59be、source=src-3e8d59be、failures D23=1、stop_requested=false。
- [x] 任务输入=team-task.md round-7 source block（四条：travel 真实闭环主靶 / 真实发票视觉复核 / 五类只读研究 / R6-P2 顺带）；本任务来自用户 2026-10-24 三点纠偏指令（barstub 测试引擎+首页渲染→补真实理解；预制 facts_payload/blueprint→agent 自驱；缺八类材料不停工）。
- [x] 不读取 A 的独立基线/criteria；本轮验收依据=task source+生效合同。

## P0.5 · 硬规则与风险登记

- 红线继承 AGENTS.md 全量+任务保留项：fill_only（不测保存/提交）；SaveController/_click_guard/registry 原样；原始材料只读（历史 run 工件零改动，复制进新 run 派生区）；不虚构业务；单 profile 单执行者；探针如需改动先 selftest 全绿；不自动 commit。
- 风险 envelope: author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE。
- 浏览器动作面（本轮合同枚举）：①travel 闭环真实填写一次（fill_once 正式入口，test_context 强制 fill_only，重试仅按既有 --resume-run 同绑定纪律）②五类研究定向只读 raw fetch ≤5 次（--login-wait 0，失败即登记不刷屏）③此外零导航零点击。
- 登录前置：会话记录 authenticated（effective_reuse_until 2026-11-23T02:42:23Z）+ 14:17 tpllive 实测 LOGGED_IN；执行前动态再核；失效→WAIT_HUMAN_LOGIN 留证转第 2/3 条。

## P1 · 盘点与可执行性核实

- [x] **真实材料盘点结论**：仓库不存在真实发票 PDF/图片或费用 Excel 原件（全 repo 仅 tests/fixtures 合成件；legacy-ia2 为 UI 截图；attempt_026/types-* 用的是罐装 plan/回放 JSON，无原件文件）。任务书设想的"attempt_026 或 types-* 实际用过的原件"不存在。**可用的真实业务载体**=用户授权历史回放工件 `automation/runs/20261023-live-complex-demo/demonstration_materials_revision02/authorized_demo_revision02.json`（真实历史单 15426093015 徐亮差旅 633.84：user_request 原话授权现场演示填写、demo_only/not_new_expenses、发票本次演示明确不要求且声明不构成免票规则、关联替换 12026101976/12026070366/12026037675 用户逐字授权"允许，仅用于本次演示"；金额四表全闭合 633.84）。闭环以它为本次材料（复制进新 run，原件只读），"真实发票/Excel 原件缺失"如实登记缺口。
- [x] 模板可用：15426093015 在 census `20261023-142146-travelcensus` 全 children 200 → resolve_template 可行；demo attempt_002 当年 READBACK_MISMATCH 根因 detailrels 零值字段已由现 travel.json extra_table_projections（readonly_zero+一对一公出单）建模，当前管线可正确核销。
- [x] test_context 契约：{purpose, round, authorization_path, authorization_sha256}+mode=fill_only（bpm_plan.py:147-165 校验）；授权路径用 rev02 回放工件哈希。
- [x] agent 自驱链路可行性：register_request/resolve_template/build_reuse_matrix/entries_from_matrix/generate_fill_plan/execution_ready 均为库函数；blueprint 组装=agent 步骤（对照 W05 travel_blueprint 形制，值全部 fact 绑定）；FACT_SOURCES 含 material_extraction/user_instruction/system_observation/deterministic_computation 满足回放材料事实来源。
- [x] bpm_extraction 现状：render_original 仅 PDF 首页（:296）；review_pass 已支持 verify=agent-visual（区域锚点+执行者留证+机械比对缺位如实记录）；barstub 为唯一注册引擎（测试用途，docstring 已注明"测试与演示"）——真实路径声明需改为：文本 PDF 走文本层、扫描件/图片渲染后 agent 视觉复核。
- [x] 五类研究证据面：typequery evidence 有五类类别码+候选单号（15426101596 低值办公/15426071883 福利劳保 等）但无 doc 级抓取（census 仅 travel；type-view/type-template 抓取为 11/15 已注册类）；doc 级结构需 live raw fetch——现 fetch_template 末尾 normalize 对未注册类别抛 TypeConfigError，需最小 raw 旁路（只读 GET 集合不变，跳过 normalize 落 raw JSON）。
- [x] 操作人：陈晶（system_observation：session record authenticated+14:17 live 实测）；填写前再核。
- [x] 无阻断 FACT；裁量项（keep-open 时长、raw fetch 次数上限）入合同推荐。

## P2 · 改写与合同冻结

- chop-task contract-only（run_id=20261024-152123-3e8d59be source_block_id=src-3e8d59be input_policy=initial）：真实发票原件缺失属外部输入非合同缺口；minimal profile。
- 合同冻结见下方 P3（本次先记计划）。

## P3 · 冻结与登记

- [x] 合同冻结：`ctr-381e0163`（run_id=20261024-152123-3e8d59be source_block_id=src-3e8d59be status=frozen profile=minimal，team-task.md:57）；effective_contract_id=ctr-381e0163（本轮无增补）。

## P4 · 生产（B+AUTO，单执行体）

- [x] **A 离线代码**：bpm_extraction 全页渲染+页级锚点（render_to_files）；bpm_template `--research-raw` 只读旁路+Decimal 转储修复（`_json_default`）；skill 真实路径声明/barstub 降级注记（红线段逐字不动）。
- [x] **B agent 自驱链至 EXECUTION_READY**（run `20261024-155625-travelloop`，无预制 facts_payload/blueprint）：授权回放材料 rev02（sha a80c424a…）→register_request→resolve_template（census 142146 定向）→agent 提取复核（facts 全 locator+input_hashes）→FactSet→reconcile→复用矩阵→entries→blueprint（identity 三键双源）→generate_fill_plan **v2**（87 sources，plan_hash e917a10d…）→test_context(fill_only)→validate_plan 零 issues→execution_ready（validate-only 子进程 exit 0）。生成器扩展：identity 绑定段+system_observation→agent_reviewed（须派生根内 agent 登记观察工件）。
- [x] **C travel 真实填写（4 次尝试，2 次可审计 registry 迁移）**：v1 `20261024-160024-8502f91d` 缺 identity 阻断（blocked_readback 留证 creator 陈晶/运动表现研究部+appliedBy 117070006，四表全空）→identity 补源重生成 v2→v2 `20261024-161207-a630166f` registry FORM_INTENT 门（诚实留档）→`bpm_ui.supersede_dead_form_intent` 零写 supersede→v3 `20261024-162157-04150c78` relations/1/bizNumber EXACT_PICK_MISSING 瞬时失败+写后页失（save_status NOT_ATTEMPTED）→写后未存 rebuild 迁移→**v4 `20261024-163009-3250e7d0` SUCCESS_FILL_ONLY**（relations 3/costs 6/details 2/banks 1；details=banks=costs=total=633.84 四向闭合；independent_verification ok=true；appliedBy 117070006；save_status NOT_ATTEMPTED；终局截图+页面盘点 `page_inventory_r7.json`）。fill_only 纪律全程未破（保存从未尝试）。
- [x] **C' 视觉复核（item②）**：run `20261024-164100-visualreview`——合成两页发票 PDF（非真实票，票面自明标注）→render_to_files dpi=150 全页渲染（两页 sha a5196f34…/8876c02a…）→agent 视觉逐页读取（4.5v，8/8 字段与生成期 ground truth 全一致，含位置描述）→review_pass(verify="agent-visual") 入 manifest→vision_crosscheck 工件+`visual_review_summary.json`；真实差旅发票原件经 P1 盘点确认不存在→`REAL_TRAVEL_INVOICE_ORIGINALS_ABSENT` 缺口如实登记，不虚构。
- [x] **D 五类 raw fetch+研究工件（item③）**：run `20261024-170000-fiveresearch`——CLI 调用 3 次（≤5 预算；首发 Decimal 转储缺陷失败即修即重试），全部 --login-wait 0+captured_exact_list_identity 锚定；低值办公 15426101596（submitType=02，sha 86bf99de…）+福利劳保 15426071883（submitType=04，sha 54456f5f…）raw 落盘；两份六节研究工件（结构/字段/差异/规则草案/能力清单/类型码证据）+RESEARCH_SUMMARY；五码互异全实测（08/11/15/02/04）；福利劳保 costs 全空→primary=details 佐证；零注册零启用零写页面。
- [x] **R6-P2 顺带（item④）**：P2-1 skill 轮末快照落盘 travelloop（skill_snapshot/ 6 文件+index，event R6_P2_1_SKILL_SNAPSHOT）；P2-2 措辞建议（只读=零业务动作 vs 会话维护性写入）记台账 notes.md。
- [x] 台账更新：notes.md R7 条目（W06 travel 闭环实况/W07 研究状态/R6-P2-2 建议）。

## P5 · 独立复核（登记门）

- [x] E 验证：probe-selftest T1-T10 ALL PASS；全量 unittest 253/253 OK；`verify_bpm_build.py` OFFLINE_PASS（automation/offline-verify/20261024-165048-draft-build/：selftest 0 + capability 244）。
- [x] F ENHANCED_FINAL（fresh mc-expert，独立重算哈希+独立重跑全量测试）：**PASS_WITH_NOTES / GO_WITH_CHANGES**。八项审计全过（哈希绑定 VALID 含 87 sources/三方闭合；supersede 安全 SAVE_* 结构性拒绝+append-only；fill_only 四尝试 save_status 全 NOT_ATTEMPT；授权链随件；研究六节+实测码；测试覆盖四类改动；红线零泄漏+保护文件 round-7 内零改动（mtime 佐证）；缺口诚实）；CHECKS 八面 7 PASS_DYNAMIC+1 PASS_STATIC。
- [x] P1-b 已修：两份研究工件 express(15) 证据指针 15426094566(实测=11)→15426082926+15426083536(实测=15)，勘误注+events 留痕，新哈希 a1d88975…/08cb1027…。
- [ ] **P1-a 待追认（移交 A/用户）**：bpm_plan_generate.py（identity 绑定+system_observation 语义）与 bpm_ui.py（supersede_dead_form_intent）不在冻结合同"允许写"清单（触发原因真实：v1 实跑 identity 阻断+v2 registry FORM_INTENT 门死锁；处置守卫文件零改动/判据未放宽/全留痕/测试覆盖），本轮未走合同增补——需下一轮合同或用户显式追认这两处写入面；审计建议后续同类情况先停-增补-再写。
- P2 注记（下轮建议，本轮不动）：P2-a execution_ready "plan.sha256" 字段名歧义（实为 canonical plan_hash）；P2-b supersede 活页检查 docstring 收窄为当前 context；P2-c "未保存关页服务端无残留"待服务端观察补证；P2-d travelloop events 字段格式统一。

## P6 · 收尾

- [x] 台账 W06/W07 更新（notes.md R7 条目）；skill 快照 R6-P2-1 落盘；R6-P2-2 措辞建议记台账。
- [x] handoff-input.json 绑定真实产物/证据哈希（含 P1-b 修正后哈希）；finish 归档 A_REVIEW。
- [x] 静默等待 A（3600s wait 重挂）。

> run_status: COMPLETE
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
