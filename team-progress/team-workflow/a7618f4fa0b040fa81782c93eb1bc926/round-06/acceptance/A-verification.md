# Round-6 A 验收证据：维持项 + 用户三点纠偏落档

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。方法：13/13 工件哈希对账 + 独立复跑 + live run 证据核验 + 红线核验。用户在验收期间下达三点纠偏（见文末），已并入本轮判定与下轮任务。

## 核验通过部分

- 13/13 哈希对账一致；`fill_once.py` 与 round-4 冻结值逐字节一致（零 diff 声明属实）。
- 独立复跑：test_bpm_request **28/28**、test_skill_docs **9/9**（红线句逐字 pin）、全量 **236/236**（218 基线零回归）。
- skill 增补结构核验：SKILL.md+references/full-chain.md 在盘，授权/保存红线段未被触碰（test_skill_docs pin 通过即证）。
- live 模板读取（automation/runs/20261024-150200-tpllive/）：events 链 precheck→profile_lock_acquired→preflight→session_state_injected→exact_template_read→**SUCCESS_TEMPLATE_READ_ONLY**→tpllive_compare；live_vs_cached_compare.json `consistent:true`；**零新建、零填写**；唯一含"save"字样事件为 `session_state_saved`——AGENTS 强制的会话 TTL 原子回写（非业务保存，且 last_scan_at 未重置/期限未续期，B 挂账 P2-2 措辞歧义已记录）。
- execution_ready 机制代码面：validate-only 真实子进程全绿才产 EXECUTION_READY；操作人来源封闭两值（user_policy|system_observation），越界 ValueError；缺证据 NEEDS_INPUT 不猜姓名。
- 红线：HEAD 9299545、registry 安静、legacy/旧 run 零触碰、凭证零泄漏。

## 用户三点纠偏（2026-10-24，本轮验收期间）

1. **图片识别仍偏测试管线**：唯一内置引擎 barstub（自制条纹图）、扫描 PDF 渲染仅取首页——证明管线可运行，不证明真实多页发票可被正确理解。要求：用现有视觉/PDF 能力补齐（全页渲染+agent 视觉复核），**不建复杂 OCR 框架**。→ D4 维持 FAIL 且缺口聚焦于此（bpm_extraction.py:115）。
2. **日常入口未完整串通**：计划生成依赖预构造 facts_payload/blueprint（测试代码组装）；缺它们时准备入口停在 MATERIALS_READY。要求：下轮证明 **agent 运行时自驱**这些内部步骤。→ **D10 不翻转，维持 FAIL**（fill_once.py:128）。
3. **不得因缺八类新材料整体停工**：缺材料只阻断对应新业务验收；五类历史结构只读研究、规则建模、代码适配照常推进。→ D12 研究部分下轮启动；不允许再以纯离线轮替代真实闭环。

## 判定影响

Round-6 交付本身按其合同核验合格（串联机制/skill/live 只读/R5-P2 均真实落地），但按用户口径：D1/D4/D10 的"完成"被上收——执行就绪只是机制，agent 自驱+真实理解+真实填写才是判据。维持 17 PASS / 10 FAIL；无新 failure key（用户纠偏属范围上收与下轮方向，非本轮合同违约；D23 维持 1/3）。
