# Round-7 A 独立验收记录（travel 真实闭环轮）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。用户三点纠偏指令为本轮定向依据。

## 1. 冻结与红线核查

- 基线 sha256 `0d355d19…5f8bd0a`、criteria `1115c883…54339d` 复核一致；HEAD 仍 `9299545`（零 commit）。
- 交接 artifacts 16 项 + evidence_hashes 13 项哈希全对账：**0 缺失 0 不符**；evidence 清单 13 项全部存在且非空。
- `automation/task-registry/` 8 个 form.json：round-7 仅新增 1 条（task_id `20261024-r7-travelloop-15426093015`，state=FORM_INTENT）。全 registry **零 SAVE_INTENT/save_draft/SAVE_SUCCESS token**；superseded_intents 2 条全程留痕（零写迁移 + 写后未存 rebuild，lost_page_rows relations2/details1/costs1/banks1 逐表记录），未删 registry、未换 task_id、无强关痕迹。
- 守卫面：`stage1_browser_probe.py` mtime 10-24 10:43、`fill_once.py` 12:37（均早于本轮接棒 15:21），`bpm_save.py` 10-23 18:57 零改动；`bpm_ui.py` 内 `_click_guard` 调用面完整，保存路径仍要求 authorization.mode=save_draft+allow_submit=False（L1085）；`supersede_dead_form_intent` 明文拒绝 SAVE_* 状态接替（L41）。
- `.pw-profile/` 未出现在任何工件/证据路径；token 零泄漏。

## 2. travel 真实闭环（用户指令①②落地）——核实通过

- **材料**：originals/replay_r7.json（授权历史回放 rev02，sha `a80c424a…`，demo_only+not_new_expenses+关联替换逐字授权随件）；双根 manifest 校验通过，roles 全部合法枚举（user_request/run_evidence/decision_matrix/parsed_extraction）。
- **agent 自驱链**（chain_driver.py 亲读源码核实）：register_request（自然语言 statement+模板号+材料目录，正是 D1 的用户输入形态）→ resolve_template（census 定向）→ agent 提取复核（JSON 指针 locator+Decimal 四表闭合机械交叉核对）→ FactSet.add/add_expense/add_payee/add_no_invoice_basis（全 locator+input_hashes）→ reconcile 零 block → build_reuse_matrix（逐字段决策，用户授权替换逐条 basis）→ blueprint 组装 → generate_fill_plan → validate_plan(verify_sources=True) 零 issues → execution_ready（真实 validate-only 子进程）。**无预制 facts_payload/blueprint 塞入口**；events.jsonl 5 次 chain_start、2 个 PLAN_READY（5a47c96b→e917a10d 计划修订留痕）。
- **真实填写 4 次尝试**（全部 entry PASS、save_status=NOT_ATTEMPTED、expect 陈晶=当次登录身份）：
  - v1 160024：fill BLOCKED `COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED`（实页发现默认制单人≠申请人，页面零写入，blocked_readback 留证）；
  - v2 161207：registry FORM_INTENT 门（诚实阻断）→ supersede 零写迁移；
  - v3 162157：`EXACT_PICK_MISSING:relations/1/bizNumber` 瞬时失败（写后页失，lost_page_rows 留痕）→ 写后未存 rebuild 迁移；
  - v4 163009：**SUCCESS_FILL_ONLY**（wall 161s）。
- **独立回读**：independent_verification.json ok=true、issues=[]、行数 3/2/6/1 与计划一致、details=banks=costs=total=633.84 四向闭合。
- **页面交接**：page_inventory_r7.json 完整（操作人/申请人/工号/页面"编制中"/未保存无单号/行数/金额/关联单号/表头演示声明）。
- v1→v4 的失败-恢复链本身构成真实异常证据（见 D18 进展）。

## 3. 视觉复核（用户指令①）——机制已证，真实票缺口如实登记

- `bpm_extraction.py`：barstub 模块注记明确"纯测试引擎，仅驱动管线测试"（L16）；渲染页码贯通（L335）。
- run 20261024-164100-visualreview：合成两页发票（票面自明"非真实票"）→ render_to_files 全页 dpi150（页级 sha）→ **agent 视觉逐页读取（4.5v analyze_image，现有能力，零新框架）** → 8/8 字段与 ground truth 一致 → review_pass(verify=agent-visual) 入 manifest → vision_crosscheck 留证。
- `REAL_TRAVEL_INVOICE_ORIGINALS_ABSENT`：盘点结论"仓库内不存在任何真实 travel 发票原件"，登记 searched 范围，真实票面复核留待用户提供原件。**不虚构、不猜测**——与用户指令③一致。

## 4. 五类只读研究（用户指令③）——2/5 类落盘

- 低值办公 02（15426101596）、福利劳保 04（15426071883）raw 落盘 + 六节研究工件 ×2 + RESEARCH_SUMMARY；CLI 3 次 ≤5 预算、--login-wait 0、observed_get 只读、零注册零启用零写页面。
- 类型码证据链：08/11/15/02/04 全实测互异；P1-b 勘误已核实（两文件均含订正注，express(15) 证据指针改为 15426082926+15426083536 实测）。

## 5. 独立复跑

- `stage1_probe_selftest.py` exit 0（T1-T10 ALL PASS）。
- `python -X utf8 -m unittest discover -s tests`：**253/253 OK**（105s），与 B 申报一致。
- `verify_bpm_build.py --run template-materials-20261024-r7-acceptance` 独立唯一 run（结果见 build 日志；B 自报 20261024-165048-draft-build OFFLINE_PASS、capability 244）。

## 6. P1-a / P1-b 处置（治理）

- **P1-a**：round-7 冻结合同允许写清单确不含 `bpm_plan_generate.py`/`bpm_ui.py`（execution/team-task.md L71 亲核）；B 触发真实阻断后写入、主动申报未隐瞒。A 亲核改动面：plan_generate 为 identity 绑定+system_observation→必须绑定已登记观察工件否则拒绝（**收紧**来源证明）；bpm_ui 为 supersede+两迁移（append-only、SAVE 拒接、存活页拒接）。守卫零改动、判据未放宽、测试覆盖、全留痕。**处置：A 于 round-8 任务书内正式追认并纳入常设允许写清单（条件：最小改动+测试+events 留痕；新文件仍须先停-增补-再写）**，不新增 failure_counts key（属如实申报并补救的流程事件，非验收失败；repo 五条红线零违反）。
- **P1-b**：勘误已执行并核实（见 §4），新哈希与交接一致。

## 7. 判据变动

- **D1 → PASS_DYNAMIC**：register_request 输入形态=模板号+原始资料+业务说明（自然语言 statement）；全程零用户手写 task/OCR/映射/plan JSON；从请求连续推进到 SUCCESS_FILL_ONLY 交付，未停在"材料就绪请自行生成"。备注：本笔为授权历史回放材料；全新真实材料的同链复现由 D11/D20 各类型继续承载。
- **D10 → PASS_DYNAMIC**：正式入口真实执行链（4 attempts）、守卫/机制全保留、无绕行执行器（chain_driver 只编排不触浏览器）、身份/选择器/联动唯一准确、未保存页盘点交接。
- **D4 → BLOCKED**：全页渲染+agent 视觉复核机制已动态验证（合成两页 8/8、barstub 降级为纯测试注记）；判据要求的"至少一笔真实业务 PDF/图片复核记录"被外部输入缺口阻断（真实发票原件不存在，已登记 searched 范围）。属用户供料依赖，非代码缺口。
- D11/D12/D18/D19/D20：维持 FAIL，进展实记（见 pending-scope.md）。D22/D25 未动。

## 8. 结论

用户三点纠偏全部实质落地：①真实理解机制补齐（真实票缺口如实登记）；②agent 自驱内部步骤在真实会话走通；③缺材料未停工（五类研究推进）。本轮无虚报、无红线违例、无新 failure key。decision=rework（全局判据未全达），round-8 以 express/rd 闭环+合同增补为主靶。
