# Round-4 A 验收证据：D8 / D9（翻转）/ 维持项

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。方法：12/12 工件哈希对账 + 独立复跑 + 代码面 + 红线核验。

## D8 计划生成与衔接 — PASS_DYNAMIC（自 FAIL 翻转）

- `bpm_plan_generate.py`（sha256 3c6015fc… 对账一致）代码面：双前置门（reconcile blocked 拒绝 L145-148；blueprint.current_bindings 交 check_version_drift + 逐事实工件 sha256 现场重算交叉核验，漂移即拒）；locator 统一 `file#inner` 坐标且拒跨文件偷换（L50-53）；template 事实必须与计划模板快照哈希一致（L128）；user_instruction 禁绑派生工件（L132）；产出当场过 `bpm_plan.validate_plan(verify_sources=True)`，失败即 PlanGenerationError 不放宽（L15-16）。
- `fill_once.py`（sha256 6f67e20a…）阶段机：MATERIALS_READY→FACTS_BUILT→RECONCILED→PLAN_READY（L127-155）；对账阻断/生成器缺陷分别落 RECONCILIATION_BLOCKED/GENERATOR_INVALID 结构化缺口；facts_payload 为可选 agent 中间产物键（L65、L138），无该键旧断言全部保持——旧 `--task` 语义兼容。
- 独立复跑：test_bpm_plan_generate.py **16/16 OK**（含 travel e2e validate 空 issues+load_plan 回读、六道前置门反例、express 免票+双空表、阶段衔接四例含旧断言保持）；全量 **190/190 OK**（104s，174 基线零回归）。
- "不再停在'请用户提供 fill-plan'"由阶段机+测试直接验证；真实材料场景计划生成随 W06 复验。

## D9 版本与输入绑定 — PASS_DYNAMIC（自 FAIL 翻转）

七类绑定链现状核验：模板（快照哈希一致门 L128）、原件/派生（manifest v2.0 + input_hashes）、事实（FactSet 版本化+工件哈希）、计划（validate_plan verify_sources 全来源哈希）、规则配置/执行源码（既有 v1.0 计划-配置哈希执行绑定，未改动）、操作人（既有 expect_name 绑定语义保持）。漂移测试：六道前置门反例（含改原件/工件哈希/模板快照不符）独立复跑通过；旧 run/manifest/registry 未被改写（真 registry 150 分钟零改动、HEAD 9299545 不变）。R2-P5 glob 机制首次带新模块过统一构建：source_manifest 49 键，`bpm_plan_generate.py` 在清单且哈希==盘上（A 直接核验）。

## 维持 PASS 复核（要点）

- **D14**：主线 W02→W03→W04→W05 连续闭合；next=W01/W06。✔
- **D15/D16**：单执行者+ENHANCED_FINAL fresh GO（13 件双轮重算、跨轮哈希矩阵六只读模块三轮一致、79 合同链 cases）；交接五项齐备+R4-P2 四条加固挂账。✔
- **D17**：层次标注不变；离线构建如实。✔
- **D21/D26**：纯离线、守卫在位、零生产访问、不虚构；合成 fixtures 仅测试。✔
- **D24/D27**：台账 W05=已验证（5 证据项）+round-4；八类真实材料缺口如实保留。✔

## 挂账确认（非本轮缺陷，转 Round-5）

R4-P2 四条加固（expect_money 缺 amount 键自比恒真 / from_payload 未共享 add() 构造不变量 / 空 input_hashes 绕 drift 门 / _dec 正例同义反复断言）——测试质量与门加固项，A 确认转入 Round-5 任务必做。
