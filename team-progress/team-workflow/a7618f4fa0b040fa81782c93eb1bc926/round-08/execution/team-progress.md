# 团队进度 — express+rd 真实闭环 + P1-a 追认 + 五类续推 + 反例固化（round 8）

> run_id: 20261024-172415-7d069bdb
> source_block_id: src-7d069bdb
> contract_id: ctr-633d23ae
> effective_contract_id: ctr-633d23ae

- workflow_run: a7618f4fa0b040fa81782c93eb1bc926 / workflow_round: 8 / entry: team-workflow-run（B 窗口）
- task_source_sha256: 7d069bdb40cea09e76baab5658c9bf92ebca76a94d07bd8ba272dabe442eb13f
- runtime_evidence: GLM（本 B 会话原始 JSONL，helper enter/permit 已核，seq 39）
- B 的 run 启动授权: /team-workflow run（2026-10-24，用户显式）；A review 已绑定（round-7 rework → 本轮任务）
- 累积失败字典（A 侧加载，逐字回传）: {"review|content|source_manifest_coverage|D23": 1}

## 进度日志

- [2026-10-24 17:2x] enter+permit 成功（seq 39，B_RUNNING round 8，stop_requested=false）；team-task round-8 source block 已读全文；team-task SKILL.md 全文已读（P0-P6 权威）。

## 当前现状

P3 完成：合同 ctr-633d23ae 冻结（含 P1-a 追认条款+常设允许写清单+浏览器动作枚举）；chop contract-only 返回 FROZEN。

## P0.5 · 风险登记

- author_runtime=CLAUDE_GLM（一手：本会话 JSONL，helper enter/permit seq 39 已核）；risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED（常设策略，与前七轮同 envelope）。无 HIGH 事实、无对外/DLP。

## P1 · 盘点与可执行性核实（已核事实+证据指针）

- [x] **授权载体（真实用户原话在盘）**：`automation/type-extension/live-test-authorization.json`——user_statement"你从历史表单中挑选一些复杂度高的单据作为模板，进行真实填写测试，我给你授权，继续"+prior_personnel_instruction"每次新建单据都会自动填写登陆人信息，这些你不用管，按默认，（本机是陈晶）"；allow_history_replay=true/allow_fill=true/**allow_save=false/allow_submit=false**/personnel_policy=preserve_system_defaults。express 与 rd 两回放事实件 lineage.authorization_path 均指向它且 sha MATCH。
- [x] **express 回放材料**：`automation/type-replay-plans/express-complex-R2-defaultbank/test-inputs/authorized_replay_facts.json`（test_only+not_new_expenses+no_invoice_rule 原文"仅为用户明确授权的历史数据未保存测试，不申报新费用、不代表业务免票依据"；applicant 陈晶=登录默认；header totalCost 347.50/desc"样品寄送"；details 1/costs 8/banks 4/relations 0+table_applicability 理由）。模板缓存定向：type-view-15426094780 snapshot（lineage template_sha256 MATCH）。
- [x] **rd 回放材料**：`automation/type-replay-plans/rd-complex-R2-namepicker/test-inputs/authorized_replay_facts.json`（同语义；applicant 陈晶；totalCost 9935.16/desc 科技中心26年9月外购样品；details 4/products 18/banks 4；relations+costs 空表 table_applicability 理由）。模板缓存定向：type-view-15426104120 snapshot（MATCH）。
- [x] **两类快照在盘完整**：express 94780（uuid f9eaadcf…，details1/costs8/banks4，347.50）；rd 104120（uuid c10c49a2…，details4/products18/banks4，9935.16）。resolve_template 需 census 格式而 census 142146 仅 travel——改以缓存快照为模板源（lineage sha 绑定），不额外 live 读模板（记自主裁决①）。
- [x] **applicant=登录默认**：两材料 applicant 陈晶+preserve_system_defaults → 无需 identity 选择器（区别 round-7 徐亮）；页面默认应与计划一致，若实跑仍阻断按诚实失败留痕。
- [x] **五类余三类及码**：census submittype_map 全八类：01 其他费用/24 维修费/06 各项会议支出（02/04 已做，08/11/15 注册）。候选单号从 list 证据（census 142146 list_items_api.json 469 行）按类别名定向。
- [x] **反例证据在盘**：v1 缺工号阻断 20261024-160024-8502f91d/blocked_readback；v2 registry 门 20261024-161207-a630166f；v3 EXACT_PICK_MISSING 20261024-162157-04150c78；写后页失 lost_page_rows 同 v3 stage1_result。
- [x] P2 小项五条均有明确落点（bpm_request execution_ready 字段名/bpm_ui docstring/链 events schema/skill 措辞/服务端只读观察一次）。
- 无阻断 FACT；裁量项（模板源取缓存快照、闭环顺序、研究类别选取）入合同推荐。

## P4/P5 · 路由登记

- P4：coordination_score=T3（单执行体串行流水线：链→填→读→盘点，关键门一次性 reviewer）；assurance_profile=ENHANCED（GLM MEDIUM 必然命中）。
- P5：routing_mode=AUTO / realized_topology=T3 / drive_mode=B（用户 /team-workflow run 常设授权）；OPEN_BLOCKERS 空、阻断 FACT 无、冻结合同 ctr-633d23ae 机械核验 PASS（79 cases）。

## 自主裁决(B)

- ①模板源取缓存快照（type-view snapshot，lineage sha MATCH）而非 live 重读：AGENTS"缓存读取或 live"二选一，缓存可用优先（成功率最高+零额外浏览器动作）；resolve_template 需 census 格式而 census 仅 travel——以快照直接绑定 template 事实（sha 一致性等效），记入合同§1。
- ②闭环顺序 express→rd：express 表面更简单（无 products 档案选择），首件先小后大。
- ③研究类别优先 其他费用(01)+维修费(24)：list 证据候选量决定，若候选缺失改 06 各项会议支出。

## 卡点

无。

## 漏斗默认·待确认 / 自主裁决(B) / OPEN_BLOCKERS / PENDING_HUMAN_NONBLOCKING

（空）

## P4 执行记录（round 8 · ctr-633d23ae）

- **P1-a 追认**：合同 §0 逐字引用 A 任务原文+standing 允许写清单生效；记录件 automation/type-extension/ratification-20261024-round8.json + notes.md R8 条目。
- **express 闭环**：chain 20261024-174500-expressloop（agent 自驱链 96 sources，无预制 payload；模板源=缓存快照自主裁决①，lineage sha MATCH）→ fill 20261024-173807-72170651 首发 SUCCESS_FILL_ONLY（relations0/details1/costs8/banks4；347.50 四向闭合；iv ok=true issues=[]；save NOT_ATTEMPTED）→ page_inventory_r8_express.json（sha 21939aad…）。
- **rd 闭环**：chain 20261024-175000-rdloop（155 sources；amount_rules costs=not_applicable+理由/products=sum 行总额）→ fill 20261024-174803-cd2e04e4 首发 SUCCESS_FILL_ONLY（details4/costs0/banks4/products18；18 行现有档案编号选入未新造；9935.16 四向闭合）→ page_inventory_r8_rd.json（sha 02330bec…）。
- **五类研究**：run 20261024-180000-research-r8——01 其他费用 15425125587（无预算 details 变体/申请书多明细部分占用/bizCost>totalCost）+ 24 维修费 15426015123（税额三值模型/对公收款人）；raw fetch 2/5、--login-wait 0、只读零注册零启用；06 会议支出 0 候选未做（裁决③）；代码适配准备 code-adaptation-prep-02-04.md（9 落点+实施顺序，零实施）；RESEARCH_SUMMARY_R8.md。研究进度 4/5，七类码实测互异。
- **反例固化**：①COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED（页面默认≠计划且无 identity→阻断+header/四表零写）③EXACT_PICK_MISSING（瞬时 0 候选→硬阻断+部分状态 verify_snapshot 必拒）两测试入 tests/test_bpm_ui.py（R7 v1/v3 实证复刻）；②④ R7 已随 supersede 测试组在场。
- **P2 小项全落**：execution_ready plan_hash 双字段留兼容（bpm_request.py+test 断言非文件哈希）；supersede 活页检查 docstring 收窄当前 context 语义（bpm_ui.py，零行为改动）；新链 events schema 统一 event 键；R6-P2-2 只读措辞采纳 SKILL.md（红线段逐字不动，test_skill_docs 9/9）；服务端无残留只读观察 run 20261024-181500-noresidue（round-8 两笔今日创建 0 行/关键词 0 命中；存量 10-23 草稿 15426104612 属 live-complex-demo 时期单列登记；attempt_001 收尾异常诚实披露，attempt_002 干净重跑，两轮 17 行一致）。
- **验证**：全量 255/255 OK（新增 2 反例测试）；verify_bpm_build 唯一 run template-materials-20261024-181500-r8final OFFLINE_PASS（selftest+capability 246+合成工件）；skill 轮末快照入 expressloop（6 文件+index sha 5214a477…，SKILL.md b41e9e4e…）。
- 台账 notes.md：W06 三类全闭环 / W07 研究 4/5 + 适配准备 / R8 P2 与反例记录。

## P6 · 终审与收口

- fresh mc-expert ENHANCED_FINAL：**PASS_WITH_NOTES / GO**——八项全 PASS（P1-a 追认/express 闭环/rd 闭环/研究工件/反例测试/P2 五项/测试构建/红线抽查），哈希独立重算全 MATCH，独立重跑 255 OK + 33 OK + 9 OK + selftest ALL PASS。三条非阻塞观察（链 events 双前缀单例化建议/research events 键名/no-residue 布尔命名）记入下轮建议。真实浏览器填写未由陪审复跑（复跑即合同外浏览器动作），以原始工件链+hash 三点闭合验收，属既定形态。

> run_status: COMPLETE
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
