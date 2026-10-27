# template-materials 推进摘要（人类可读版）

> 权威来源是同目录 `progress.json`；本摘要与它冲突时以 JSON 为准。更新时间：2026-10-26 10:35（V3-R00 纠偏，见文末「V3-R00 纠偏」节）。

## 这个程序在做什么

用户只给「完整模板单号 + 本次原始资料（PDF/图片/Excel）+ 业务说明」，agent 自行提取复核、建立本次事实、对账、生成有来源计划，经正式入口真实填写新单（fill_only 只填不存），并自行完整独立回读与验收。用户不写内部 JSON、不承担施工人工核验。范围：近两年盘点八类报销，先闭合现有三类，再分批接入其余五类。

## 当前状态（2026-10-24，round 2）

- **W00 基线复核**：✅ round-1 完成（`baseline-review-20261024.md` A1-A8 成立/B1-B8 差距）。
- **W02 原件/派生双根契约**：✅ round-1 完成（manifest v2.0；127/127+OFFLINE_PASS；旧 v1.0 语义不变）。
- **W03 原件理解**：✅ round-2 完成（离线已验证）——新模块 `bpm_extraction.py` 四链路：①文本 PDF 行级锚点（页/区域/bbox）提取票据事实+价税 Decimal 闭合复核；②图片本地渲染+封闭 OCR 引擎注册（本机无 tesseract，未新增第三方库；barstub 确定性像素引擎驱动测试），ocr_result 原始层与 reviewed_extraction 复核层分离落派生根、逐字段复核证据留痕；③xlsx 多 sheet/隐藏行/筛选/合计行/公式缓存或本地 SUM 重算（公式文本永不当金额）/前导零原值/跨表重复仅提示待对账；CSV 行列定位+科学计数/尾零丢精度登记；④语义类别盘点（内容哈希判重、关键词+表结构判类，文件名不作证据，不确定标待定）+结构化缺口登记（清晰件不中断）。附带闭合 R2-P1（register_derived/validate_image_documents 相对 derived_root 统一挂 manifest 目录，任意 CWD 回归×2）。13 项新测试 + 全量 146/146 + OFFLINE_PASS（`automation/offline-verify/template-materials-20261024-111625/`）。
- 其余工作包（W01/W04-W10）：待做，缺八类「本次真实原始材料」这一外部输入（不虚构、如实挂缺）。

## 已成立的能力（不重做）

travel/express/rd_materials 三类封闭注册 + 授权历史回放真实填写 + 差旅正式整单 attempt_026（SUCCESS_FILL_ONLY）+ 双根材料契约 v2.0 + 原件理解四链路（以上均离线已验证）。

## 红线备忘

只填不存（本轮不测保存）；`.pw-profile` 凭证不入库；旧 run/registry/legacy-ia2 只读；不自动 commit；原件只读、派生物进工作区；不上传原件到第三方。

## 下一轮入口

W04 本次事实与对账（消费 W03 产物建立本次业务事实与金额闭合）/ W05 计划衔接（内部阶段状态区分）。挂账：R2-P3（git commit 用户决策）、R2-P4（legacy token 清理人工）。

## Round 3（2026-10-24，ctr-1eecdddb）：W04 事实层与对账 + R2-P5

**R2-P5 闭合（先做）**：`verify_bpm_build.py` 源清单改为 显式 CODE ∪ 根目录 `bpm_*.py` ∪ `fill_once.py`（排序去重）。先导唯一 run `template-materials-20261024-1158-r2p5fix` OFFLINE_PASS，manifest 45 键含 `bpm_extraction.py`（12246426…与冻结哈希一致）后才动 W04；终局 run `template-materials-20261024-w04-final` 47 键再含 `bpm_facts.py`。后续新增 bpm_* 根模块自动纳入冻结。

**W04a 事实层（`bpm_facts.py`）**：
- 稳定 ID `F-0001…`；分配/免票依据引用 fact_id（add_allocation 校验 invoice_ref/expense_ref 存在且类型正确），不复制票号/金额。
- 来源封闭枚举五类如实标注；`user_instruction` 禁携带派生工件绑定（agent 推断不伪装用户）；`deterministic_computation` 强制 derivation；locator 必填。
- 版本化：FactSet.bindings + 每事实 input_hashes（如 extraction:<original_sha256>）；`check_version_drift` 比对当前工件哈希 → affected/needs_replan，只标记不改写（Fact 为 frozen dataclass；工件消失也视为受影响）。

**W04b 对账（`reconcile`，先于业务写入）**：11 项检查——票面跨扫一致 / 票据 Decimal 闭合（部分票面、票面≠分配阻断）/ 费用行覆盖（未覆盖、免票无理由拒绝）/ 汇总 vs 明细 / 总额分层闭合（跨层相加双计不接受）/ 适用说明按类别 / 范围一致性 / 收款身份组（残缺、同名跨源冲突阻断；缺位=候选未建非冲突）/ 未知材料边界阻断 / 同金额不禁报（显式 pass）/ 跨任务发票提示（只读 registry，numbers 数组或全文命中，提示级不阻断，缺目录降级）。数量乘单价与借款抵扣在事实构造期即 ValueError。

**验证**：`tests/test_bpm_facts.py` 28/28（W03 真实产物集成：reviewed_extraction 建票、Excel 112.00 vs 票面 128.70 冲突双向定位、同票双扫描单计、duplicate_copy 组级消费一次、同号不同票面阻断）；全量 discover 174/174（146 基线零回归）。

**给 W05 的入口**：上游=FactSet（含 bindings/input_hashes）+ reconcile 报告（blocked=False 为生成计划前置门）；计划生成从事实引用取值而非重读原件；材料换版本先跑 check_version_drift，needs_replan=True 则重新规划不迁移旧事实。

## Round 4（2026-10-24，ctr-afabdc8a）：W05 计划生成与衔接 + R3-P2 两小修

**R3-P2a/b 闭合（先行）**：`bpm_facts.py` `_dec` 对超 2 位小数金额（100.004/0.005/1.234 类）显式 raise「金额语义歧义需显式处理」，不再静默 quantize；`reconcile` 收款身份组新增**同账号不同户名**检测（同 account 不同 name → payee_identity block，detail 携双方 locators，R3-P2b）。round-3 终审遗留两 P2 均落测试。

**W05a 事实→计划生成器（`bpm_plan_generate.py` 新模块）**：
- 双前置门先于任何产出：reconcile blocked 拒绝（阻断项=业务缺口）；`check_version_drift`（blueprint.current_bindings）+ 每事实工件哈希现场重算交叉核验，漂移拒绝（needs_replan 语义）。
- 来源坐标统一 `file#inner`（xlsx `Sheet!A1` / JSON 指针 / CSV `row:N/column:N`）；覆盖 locator 允许全坐标但拒绝跨文件偷换。
- fact.source→kind 封闭映射：material_extraction 按 manifest originals/derived 实测哈希落位 material/agent_reviewed；template 哈希须与模板快照一致；user_instruction→user 且禁绑派生工件；deterministic_computation→derived（显式 sum inputs，现场重算闭合）；**system_observation v1 显式拒绝**（真实系统观察证明属 W06+）。
- 金额值必须与事实金额一致（防值漂移）；invoice_extractions 绑定 reviewed 提取做票号/票面/原件哈希三核，分配按主表（primary_expense_table 或 costs-sum 规则同 validate 口径）过滤、合计须与票面闭合；免票依据→no_invoice_rows 有源 proof。
- 产出**当场过 `validate_plan(verify_sources=True)`**，失败即 PlanGenerationError(issues)，不放宽不绕过；返回 plan+fact_bindings（每指针 fact_id/fact_source/artifact_sha256）+对账报告。

**W05b 准备链路衔接（`fill_once.py` + `automation/task.schema.json`）**：task 新增可选键 `facts_payload`（**agent 中间产物**：FactSet 载荷+blueprint，非用户手写内部 JSON）；prepare_task 阶段机 `MATERIALS_READY→FACTS_BUILT→RECONCILED→PLAN_READY`，PLAN_READY 时 fill_plan.json 落 run、gaps=[]、fact_bindings 回传；对账阻断→`RECONCILIATION_BLOCKED`、生成器缺陷→`GENERATOR_INVALID`，均带 GAP_FIELDS 形状结构化缺口；**无 facts_payload 的旧断言全部保持**（NEEDS_INPUT/MATERIALS_READY/不启浏览器）。`FactSet.from_payload` 反序列化（键集/重复 ID 校验）支撑 JSON 往返。

**验证**：`tests/test_bpm_plan_generate.py` 16/16（R3-P2 两小修+往返；travel e2e validate 空 issues+load_plan 回读；六道前置门反例；express 免票+双空表全集有源理由+budgetOwner；阶段衔接四例含旧断言保持）；全量 190/190（174 基线零回归）；`template-materials-20261024-w05-final` OFFLINE_PASS，source_manifest 49 键**自动含 bpm_plan_generate.py**（R2-P5 glob 机制首次带新模块过统一构建）。

**裁决记录**：双根 manifest `derived_root` 为绝对路径属 v1 既有契约——目录搬迁会使提取工件脱离派生根被 `bpm_materials` 显式拒绝，故 payload 与工件同根生成，不引入搬迁语义（测试注释已固化）。

**给 W01 的入口**：自然语言请求→唯一模板→类别识别→复用/替换矩阵，可消费 facts_payload 形态（user_instruction 事实+blueprint）串入正式路径。**给 W06 的入口**：三类端到端成熟化消费 PLAN_READY 产物直接进 `--fill-plan` 执行链；缺本次真实原件时如实记缺外部输入。

## Round 5（2026-10-24，ctr-1a5b516d）：W01 用户请求与模板决策 + R4-P2 加固

**R4-P2 四条闭合（先行）**：`bpm_facts` 抽取 `_validate_fact_invariants` 由 `add()` 与 `from_payload()` 共享（反序列化不再宽松于构造）；`bpm_plan_generate` expect_money 缺 amount 键显式失败 + 前置门 3 拒绝无 `input_hashes` 的被绑定 material/template 事实（拒绝而非自动补绑定——生成器不代事实主张来源）；`_dec` 正例断言真实量化结果。

**W01a 请求登记**：结构化请求（模板单号/材料目录/业务说明必填，可选明确指定+用户政策，封闭键集）→ `register_derived` role=`user_request` 版本化工件落派生根（sources=本次原件哈希，user_instruction 语义标注）；缺要素 NEEDS_INPUT+GAP_FIELDS 且不落盘。

**W01b 模板核对（仅缓存路径）**：`resolve_template` 走 `cached_template` 定向读取（唯一命中/全 200/corpus path+sha 留证）；类别 code/label→封闭注册；声明类别与模板矛盾 → **集中冲突报告拒绝**（不悄悄换类）；normalize 先抛非类别错误时回查原始 doc 判根因（未登记类别可能先卡 uuid）。live OA 读模板留 W06。

**未知类别只读识别（D13）**：`identify_unknown` 报告（观察类别/注册对照/不支持部分/结构证据/登记开发子任务建议/**writable=false**）；写入路径全拒（resolve_type/build_reuse_matrix），不映射『其他费用』绕过。

**W01c 复用矩阵**：六字段组封闭规则——form_identity 仅 identify；stable_context adopt 须依据+**旧年度预算须 user_policy.budget.reuse=confirmed**；current_person 不被模板历史人员覆盖（identity_reuse 确认才可 adopt）；current_business/proven_references **禁模板来源**；empty_tables 只 not_applicable 带理由。adopt/replace 必绑 fact_id，值从事实取（fact_field 映射+字段级 locator 覆盖）。三冒充反例专测：模板旧金额冒充本次值、旧年度预算无条件沿用、模板历史申请人覆盖。

**验证**：`tests/test_bpm_request.py` 19/19（含矩阵 blueprint→`generate_fill_plan`→`validate_plan(verify_sources=True)` 空 issues 贯通——W01 真实形状快照覆盖任务根后全链闭合）；全量 218/218（190 基线零回归）；`template-materials-20261024-w01-final` OFFLINE_PASS，source_manifest 51 键自动含 `bpm_request.py`。

**裁决记录**：`bpm_materials.DERIVED_ROLES` 显式扩 `user_request`+`decision_matrix`（封闭枚举扩充）；P2-3 采拒绝不自动补绑定；矩阵→blueprint 以 `entries_from_matrix` 库函数返回绑定项建议、agent 组装，不新增 CLI 不动 fill_once。

**给 W06 的入口**：live 模板读取接 `bpm_template` 既有 live CLI（--live --expect-name --template-number）；B1-B7 执行计划消费 PLAN_READY 产物；真实原件缺口继续如实登记（八类未提供，不虚构）。

## Round 6（2026-10-24，ctr-ed80c9d0，team_run 20261024-140229-b401214d）：W06 前置

**D10 执行串联**：`bpm_request.execution_ready(plan_path, operator_evidence)`——真实子进程 `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <身份> --validate-only` exit 0+`PLAN_VALIDATED` 才算全绿；输出 EXECUTION_READY（计划路径+sha256、操作人证据、建议执行命令含 `--keep-open-minutes 45`、browser_launched=false）。操作人来源封闭两值 `user_policy|system_observation`（`validate_operator_evidence` 越界即 ValueError；模板历史人员不可推导）；`operator_from_session_record` 只读 Git 排除的 `.local-session` 记录（auth_status=authenticated 且 principal.name 非空才可用，basis 只含姓名+核验层次，不复制凭证引用/其余元数据）；缺证据 → NEEDS_INPUT+GAP_FIELDS 不猜姓名不调 CLI。不改 `fill_once.py` 任何参数语义（本轮零 diff）。

**skill 新链路增补**：SKILL.md frontmatter description 增路由关键词+新增「完整链路：模板单号+原始资料 → 执行就绪」节（六阶段+操作人纪律+矩阵规则+旧入口关系）；新增 `references/full-chain.md`（阶段表/操作人来源纪律/与旧入口关系/阶段状态与缺口）。保存/授权红线段与执行恢复/环境交付段逐字不动。结构化校验 `tests/test_skill_docs.py` 9/9：frontmatter/引用完整性/命令旗标真实存在（对照 fill_once.py、bpm_template.py 源码 add_argument 字面量）/六阶段与函数在场（对照 bpm_request.py def）/红线句逐字 pin。

**live 模板读取首试（成功）**：`automation/runs/20261024-150200-tpllive/`——前置 TTL 事件（auth_status=authenticated，effective_reuse_until 2026-11-23T02:42:23Z）→ `bpm_template.py --live --expect-name 陈晶 --template-number 15426095951 --login-wait 0`（CLI 自带 profile 锁+只读 context，登录失效即 fail-fast 不扫码）→ 入口即 LOGGED_IN → SUCCESS_TEMPLATE_READ_ONLY（live 快照 sha afa5534c…）→ 与缓存快照（20261023-142146 census，ffc75d19…）核对 **uuid/类别/header 键集/表名/行数/表头身份字段全部一致**（live_vs_cached_compare.json + tpllive_compare CONSISTENT 事件）。全程零新建、零填写、不触碰未保存页（events 全程只读链可证）。注：`--login-wait 0` 是本轮纪律（失效不等待），live CLI 默认 480s 供日常用户在场场景。

**R5-P2 三条**：旧日期（current_business/bizDate）与旧收款（proven_references/payeeName）模板冒充反例实例化入库；`build_reuse_matrix` 重复 (group,field) 行构造期显式拒绝（后行覆盖前行歧义）；`_load_doc` 与 `bpm_template` 解析重复的取舍注释（耦合成本>重复成本，corpus 格式变更两处同步）。

**验证**：`tests/test_bpm_request.py` 28/28（19+9 新增：执行串联 6+反例 2+重复行 1）；全量 236/236 全绿（218 基线零回归+test_skill_docs 9）；`template-materials-20261024-w06-final` OFFLINE_PASS（probe-selftest 0+capability 227）。注意：verify_bpm_build 清单为 bpm glob 口径，`test_skill_docs.py` 与 `full-chain.md` 不在其列（改 verify_bpm_build.py 不在本轮允许写面），哈希经 handoff 绑定。

**给下一轮的入口**：W06 真实端到端——A1-A9 提取+B1-B7 真实填写消费 PLAN_READY/EXECUTION_READY 产物（建议命令形制已就绪）；八类本次真实原件未提供前如实记缺；W07 两类研究（低值易耗/其他费用盘点）可先行。

**R7 台账更新（2026-10-24，round-7 ctr-381e0163）**：

**R6-P2-2 措辞建议（记台账）**：探针/文档中"冻结探针会话维护性写入"与"只读"字面易生歧义——建议统一措辞为"**只读=零业务导航/零业务点击/零表单写入；会话维护性写入仅限受保护目录内会话状态与事件流水**"，在 SKILL.md 与 AGENTS.md 的只读段落显式并列两者，避免后来者把 `_save_session_state`/events.jsonl 追加误判为违反只读。本轮 SKILL.md 红线段逐字不动，建议留待下一轮 skill 维护窗口采纳。

**W06 三类端到端实况**：travel **真实闭环完成**（20261024-155625-travelloop：授权回放材料→agent 自驱链 register_request→resolve_template→提取复核→FactSet→复用矩阵→blueprint→generate_fill_plan（87 sources）→validate-only 全绿→真实 Chromium 填写 4 次尝试：v1 缺 identity 阻断→v2 registry 门→v3 关联选择瞬时失败+写后页失→**v4 SUCCESS_FILL_ONLY**（attempt 3/2/6/1 行，details/banks/costs/total 633.84 闭合，independent_verification ok=true，save_status NOT_ATTEMPTED））。两次可审计 registry 迁移：零写 supersede + 写后未存 rebuild（`bpm_ui.supersede_dead_form_intent`，SAVE_* 态永不迁移）。express/rd 闭环待下轮。生成器扩展：identity 绑定 + system_observation→agent_reviewed（须派生根内 agent 登记观察工件）。

**W07 研究状态**：五类新增 2 类实测落盘（20261024-170000-fiveresearch）——低值办公 submitType=02、福利劳保 submitType=04（与 08/11/15 五码互异，全实测）；福利劳保 costs 全空→primary=details 佐证；两份六节研究工件+raw JSON；缺口：编辑器联动/reimItem 与预算枚举来源未捕获。顺带修复 bpm_template raw 转储 Decimal 序列化（`_json_default`）。

**R8 P1-a 合同追认（2026-10-24）**：round-8 合同 ctr-633d23ae §0 正式追认 round-7 两处合同外写入（bpm_plan_generate.py identity+system_observation 收紧；bpm_ui.py supersede_dead_form_intent），授权依据=A round-8 任务原文（A 已核实 acceptance §6：守卫零改动/判据未放宽/测试覆盖/全留痕）；两文件自即日起进入常设允许写清单（最小改动+测试+events 留痕纪律），其他新文件仍须先停-增补-再写。记录件 automation/type-extension/ratification-20261024-round8.json。

**W06 三类实况（R8 更新，全闭环）**：express **真实闭环完成**（chain run 20261024-174500-expressloop：agent 自驱链 96 sources，plan_hash a494e784…；fill run 20261024-173807-72170651 首发即 SUCCESS_FILL_ONLY，独立回读 relations0/details1/costs8/banks4 全对，347.50 四向闭合，save NOT_ATTEMPTED；page_inventory_r8_express.json）。rd_materials **真实闭环完成**（chain run 20261024-175000-rdloop：155 sources，plan_hash dcf4f895…；fill run 20261024-174803-cd2e04e4 首发即 SUCCESS_FILL_ONLY，relations0/details4/costs0/banks4/products18 全对，18 行物品档案按现有编号选入未新造，9935.16 四向闭合（details=products=banks=total），费用说明空按材料理由；page_inventory_r8_rd.json）。travel 见 R7 条目。**三类全部真实闭环（fill_only）**。

**W07 研究状态（R8 更新，4/5）**：新增 01 其他费用（15425125587，details 无预算变体 budgetKey=__/申请书多明细部分占用）与 24 维修费（15426015123，税额三值 cost/taxCost/realCost 模型+对公收款人）；06 各项会议支出 census list 0 候选未研究。七类类型码实测互异（08/11/15/02/04/01/24）。代码适配准备工件 code-adaptation-prep-02-04.md 落盘（9 项落点映射+实施顺序，零实施）。run 20261024-180000-research-r8，raw fetch 2/5 预算。

**R8 反例固化与 P2**：①COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED 零业务写入阻断 + ③EXACT_PICK_MISSING 无部分验收 两测试固化（tests/test_bpm_ui.py，R7 v1/v3 证据复刻）；②④已于 R7 随 supersede 测试组固化。P2：execution_ready plan_hash 双字段（bpm_request）；supersede 活页检查 docstring 收窄当前 context 语义（bpm_ui）；新链 events schema 统一 event 键（两 chain_driver）；R6-P2-2 只读措辞采纳进 SKILL.md（红线段逐字不动，test_skill_docs 9/9）；服务端无残留只读观察（run 20261024-181500-noresidue：round-8 两笔填写今日创建 0 行/关键词 0 命中；存量 10-23 草稿 15426104612 单列登记非本轮残留）。全量 255/255 + verify_bpm_build OFFLINE_PASS（template-materials-20261024-181500-r8final）。

**R9 台账更新（2026-10-24，round-9 ctr-15712bcb，team_run 20261024-192351-3e99d777）**：

**W08 02/04 首件放量（离线链层，config→注册→离线链）**：`automation/document-types/office_supplies.json`（02 低值易耗品、办公用品采购；details/costs 双层，primary=costs）与 `welfare_labor.json`（04 福利费、劳保用品；costs not_applicable、primary=details、detailrels 零金额 system_field_rules 逐字段实测）落盘；`bpm_types.py` 封闭注册扩展两类型（`offline_modeled_live_pending`，含 `invoice_policy` 形状校验：{mode,required,evidence} 封闭键+来源证据）；`<type>.notes.md` 差异对照+缺口（含 fill-plan.schema.json enum 未同步，本轮未授权面）。离线链首件双双 EXECUTION_READY：officeloop（run 20261024-193500-officeloop：42 sources，plan sha 65ef8a98…/plan_hash d426d31c…，1234.56 四向闭合，validate-only exit 0）；welfareloop（run 20261024-194500-welfareloop：26 sources，plan sha a4c4da99…/plan_hash 246027c4…，2345.67 三方闭合，details 单层=detail 层走 summary_layer:absent 分支）。合成材料明示 synthetic/test_only 不入业务 manifest；裁决①plan 级 relations 空+材料理由；裁决②invoice_policy 本轮声明级。单元测试 tests/test_bpm_type_round9.py 14 项（每类 5 实测：注册/负例配置/离线计划/边界/主表或空表理由）。

**D18 离线矩阵补行**：tests/test_bpm_extraction.py 新增 D18MatrixTests 4 测试全绿（21/21）：多页 PDF 逐页锚点（跨页要素 e2e 回锚 page:1/page:2）；一页双票钉现行一票一件契约（首匹配单记录、二票值不混入事实/闭合、原文留原始层；显式拒绝/拆分需授权改 bpm_extraction.py，缺口已登记）；Excel 多 sheet/公式取值/汇总明细跨表候选（含不匹配候选 False 如实记）/隐藏行筛选态（隐藏行金额仍计入 SUM 与明细合计）；数值保真三段（前导零+19 位长账号文本原值→FactSet Decimal 0.005 级差额阻断→计划 banks 原样+0.305 拒绝）。

**D22 方案（W10 前置，不实施）**：automation/offline-verify/d22-acceptance-plan-20261024-195544/D22_plan.md——S1-S9 环节范围/入口参数/证据/判定（PASS/FAIL/BLOCKED）/6 项入口缺口（G1 链产品化 bpm_chain.py 承 B3、G2 02/04 控件授权、G3 schema enum 同步、G4 一页多票拒绝、G5 用户供料、G6 登录窗口）。

**mc-expert 三观察处置（R8 转来）**：①链 events 双前缀→chain_segment_start 分段标记落地（segment=既有行数+1，append-only 不破坏；officeloop 段 1/2/11/19、welfareloop 段 1/4/9 实测）；②research events `authorization` 字样=只读观测 HTTP 头名清单（header_names 数组，值永不记录），非业务授权证据——约定写入 skill references/full-chain.md，键名改 observed_request_header_names 待授权改探针（本轮探针零改动）；③no-residue 布尔命名分层约定（原始观测 observed_*/计数名 vs 终判 <scope>_residue.none 且由观测派生）写入 full-chain.md，历史 verdict 原样不改。

**skill 变更**：references/full-chain.md 新增「events 与观察处置」节（红线段零触碰，test_skill_docs 9/9）。

**R9 验证与披露**：全量 273/273 OK（255 基线+14 类型+4 D18；test_bpm_request 注册表集合断言随授权扩展同步为五类型，census 夹具类别仍判 UNSUPPORTED 语义不变）；verify_bpm_build 唯一 run `template-materials-20261024-200500-r9final` OFFLINE_PASS（probe-selftest 0+capability 264）。**披露**：verify_bpm_build.py source_manifest 的 document-types 清单为显式硬编码旧三类（verify_bpm_build.py 不在本轮授权面），02/04 新 config 未入该 manifest 冻结——其哈希由链 run（resolve_type 摘要含 config sha→plan sources）、notes.md 与 handoff 哈希表绑定；manifest 清单同步列入下轮授权候选。skill 轮末快照：runs/20261024-194500-welfareloop/skill_snapshot（6 文件；SKILL.md 哈希与 R8 一致 b41e9e4e… 证红线零触碰）。

**R9 补记（P2-1 处置，audit 后追加）**：02/04 config sha256 原值入台账——office_supplies.json `e9cd75555a6e54ba9b6dcece18f21bb24797b8397202b2aec6e7e70f7a80e484`、welfare_labor.json `347c6c51684c8f6301b34f7c0e929012a24565d20cb7e0183568f59a42e6265c`（此前后披露句"由 notes/handoff 绑定"超前于事实，mc-expert P2-1 指正；本条+R9 handoff artifacts 表补齐该绑定）。另记 P2-3：两合成链 execution_ready.suggested_command 内嵌 --expect-name "陈晶"（user_policy 合成值）——真实使用时须以 S1 登录探查实测值替换（D22 §2 已有此要求）。R9 ENHANCED_FINAL 陪审：PASS + GO（17/17 哈希前后 MATCH、独立重跑 273/14/21/9/selftest+双链 validate-only 全绿、四红线干净；P2-2 kind=user 真实链断言/D22 实施时落实）。


---

## V3-R00（2026-10-26，team_run 20261026-095208-a68a0869 / ctr-08d9de84）

**本轮做了什么（细节以 `automation/runs/20261026-100322-v3r00-inventory/R00-report.md` 为准）：**

- **调度接手**：旧 run a7618f4f…（round 10 B_RUNNING 断点）已按用户 2026-10-26 授权操作员维护归档 `RETIRED_NOT_COMPLETED`；V3 新工作流正常 init/enter，代码在途成果核实后保留。
- **r10 三项冻结闭环（D23）**：manifest 五类型/schema enum/一页多票拒绝 = 代码✓测试✓；唯一构建 `materials-v3r00-20261026-101500` **OFFLINE_PASS**（selftest + 273 capability tests；source_manifest 60 键含五类型 config+notes、bpm_chain.py、22 个 tests，哈希绑定抽验一致）。全量单测另跑 282 OK(skipped=4)。四链（travel/express/office/welfare）chain_result plan sha256 重算全匹配，绑定核实后复用。
- **02/04 分类**：attempt_007 已实测（submitType 38 枚举/8 表结构/reimItem 02=5 项 04=6 项/关联类型枚举含公出单）vs 未解（budgetNo/subjectName `NO_TABLE_DIALOG`，既有工件定位穷尽）。**遗漏登记**：r10 计划的 config required_observations 回填+notes 修订未落地（不在 R00 授权写面，移交类型接入工作包）。
- **真实公出案例盘点（只读）**：73 文件逐件 sha256（10 日期组 67+油票 5+xlsx 1，字节级全唯一，4 同尺寸簇待 CASE-01 逐票核身）；Excel `汇总` 单 sheet 结构固化（行3 表头/去返成对/行4-24 数据/空尾行 25-38/stray=标题行误报禁清理）；**模板身份缺口登记**（全部冻结文档无本案例指定单号）；模型差异清单 `case-model-deltas.json`（R=M+T、F=O+T 严格>F>R、油票仅覆盖、汇总单不计费、副本回填、公出单逐票、两套关联分离、日期三方定）。
- **登录/身份**：`20261026-100537-login60` 只读核验 PASS（陈晶/116070053 authenticated，effective_reuse_until 2026-11-23）；registry 10 条全 FORM_INTENT、无任何保存意图。
- **台账纠偏**：missing_inputs 改"真实公出原件已供料+模板号缺口"；02/04 type_status 纠偏已注册+live 部分；authorization_scope/browser 改 V3 口径；rounds 补 7-10 历史断点与 V3-R00；unclosed_defects 4 项（D23 已闭环仅留历史计数说明）。

**下一轮入口**：CASE-01 真实原件理解起步；前置=本案例模板号闭合（用户明确或原报销单上下文核实）。02/04 回填/NO_TABLE_DIALOG 不阻塞本案例。


---

## V3-R02（2026-10-26，team_run 20261026-095208-a68a0869 / ctr-fe416d87）

**D22 修复（active_output_semantics）**：`verify_bpm_build.py` 新增 `real_input_layers(materials_dir, save_instruction_required)` 三态语义——`missing`（真缺口，如 exact_history_template_number）/`supplied`（--materials-dir 实供）/`waived`（fill_only 主线保存指令豁免，带理由）；`missing_real_inputs` 不再把 fill_only 豁免项冒充真缺口。新 CLI `--materials-dir`/`--save-instruction-required`；配套 `tests/test_bpm_build_output_semantics.py` 5 测试。唯一构建 `materials-v3r02-20261026-121653` **OFFLINE_PASS**（selftest + 278 capability tests，实跑 `--materials-dir feature01-细化报销skill/12月公出-发票`：supplied 生效）；全量 `unittest discover` 287 tests OK(skipped=4)（日志 `runs/20261026-115500-v3r02-case01/unittest-discover.log`）。

**CASE-01 真实原件独立解析（完成）**：证据 `automation/runs/20261026-115500-v3r02-case01/`（阶段 A/B/C/D 脚本+facts+consistency+raw 73 件+evidence 9 渲染+`CASE-01-report.md`）。要点：73 件→**52 唯一身份**（27 通行费 T=486.93；5 油票 O=2031.17 全 2025-12-12 中国石化 95#，购方厦门乔丹科技；20 汇总单身份×(票据)+(行程) 双版式成对非重复）；4 同尺寸字节簇全判 different_identities_not_duplicates；交叉核验全绿（声明票数 40/40、页脚金额 40/40、Σ成员独立票面=声明 40/40、被引用票独立在档且金额一致 54/54、无缺失引用；大写↔小写 72/72 中文大写转 Decimal；价税闭合 25/25）；行程链 10 组往返 2025-08-25→12-10（标准 翔安↔池店 22.64；0906 票面 09-05 vs 文件夹 0906 拆分票 4.4x+15.5x；0917 去翔安→石狮北石湖 31.93/返 石狮北石湖→**同安站** 36.97；0928 石狮北石湖往返 31.93；1210 返程晋江南→翔安拆分票）；Excel 21 行=10 序号×去返+合计行，Σkm=Σ补贴=**1438**（0917/0928 去 65 返 67 不对称如实登记）；T/O 仅观测、O>T 严格成立，**范围裁定（R=M+T、覆盖模型）零预设留 CASE-02/03/04**；原件两次全量 sha256 对账 round-1 manifest 零漂移；视觉抽检 toll 首件逐字段一致+0917 行程站名拼接与原始行坐标吻合。

**承接登记项**：02/04 `required_observations` 回填 OBSERVED（attempt_007 指针）+ 两 notes.md 增「观察状态回填」节（save/reopen 口径按 V3 §12.1/D22 同步为未来保存授权轮）；**errata**：R00-report §4『一页多票拒绝』测试指针勘误——承重断言在 `tests/test_bpm_extraction.py::D18MatrixTests::test_d18_pdf_one_page_two_invoices_pins_single_record_contract`（D18 §3-1；类名初记 MultiPageRenderTests 系误，mc-expert 终审 P2-1 订正，单测运行 OK），`test_bpm_round10_sync.py` 无多票测试（progress.json errata[0]，冻结件不改）；模板身份缺口维持 PENDING_HUMAN_NONBLOCKING（本轮未获新单号输入）。

**下一轮入口**：CASE-02 Excel 同结构副本回填真实通行费+可靠重算（上游=CASE-01 facts；覆盖/范围模型先行定义）；模板号缺口仍待用户明确。


---

## V3-R03（2026-10-26，team_run 20261026-125832-39b87f83 / ctr-14bb5408）

**CASE-02（完成）**：`runs/20261026-131000-v3r03-case02/`——stage A 裁定（主键=票面 travel_date+行方向；20/20 行、27/27 票恰一次分配、零缺口、行金额=汇总单声明全真；0917 返程同安站差异登记）；stage B COM 副本回填（列位纠偏：实物 H=过路费，任务文"G 列"系 round-1 字母口径差；H4..H23 逐票金额、I4..I23 补 =G+H 公式、I24 SUM 沿用、F/G/J 零触碰、公里保留）；stage C 新进程重开实测（I24=1924.93=独立 Decimal 逐行+总额复算，mismatches=0，73 件原件事后零漂移）；变更清单+CASE-02-report.md。K=1438 M=1438.00 T=486.93 R=1924.93。

**CASE-04（完成）**：`bpm_coverage.py` 新模块（fuel_pool_strict_surplus：K/M/T/R/O/F/margin/严格门槛 F>R；油票覆盖池不入行、富余不加报）五处分离——事实层 FACT_KINDS+coverage_evaluation（deterministic_computation）、schema 可选 coverage 块、validate_plan 可选键+COVERAGE_GATE_BLOCKED、evaluate_coverage 独立核验、run 双报告；`tests/test_bpm_coverage.py` 21 反例（F>R/F=R/F<R/±0.01 边界、富余不改 R、重复/未分配/油票入行拒绝、通用闭合零放宽回归、计划/schema 一致性）。真例：R=1924.93 F=2518.10 margin=593.17 **门槛 PASS**（gate=False 即阻断 OA 写入，V3 §13.1）。

**验证**：全量 unittest 308 OK(skipped=4)（+21 新）；唯一构建 materials-v3r03-20261026-131656 OFFLINE_PASS（selftest+299 capability；manifest 63 键自动含 bpm_coverage.py/test/schema/plan/facts）。

**下一轮入口**：CASE-03 公出单模块逐票查找报告（浏览器只读）；模板号缺口仍 PENDING_HUMAN_NONBLOCKING。
