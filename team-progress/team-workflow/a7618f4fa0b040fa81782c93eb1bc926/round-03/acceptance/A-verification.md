# Round-3 A 验收证据：D6 / D7（翻转）/ D23（翻转）/ 维持项

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。方法：14/14 工件哈希对账 + 独立复跑 + 代码面 + 红线核验。

## D23 工程检查 — PASS_DYNAMIC（R2-P5 对因闭合，自 Round-2 FAIL 翻转）

- `verify_bpm_build.py`（sha256 05a1c3a3… 对账一致）源清单机制改为 显式 CODE ∪ 根目录 `bpm_*.py` glob ∪ `fill_once.py`——结构性防再漏（后续 bpm_* 新模块自动冻结）。
- 终局 run `template-materials-20261024-w04-final`：source_manifest **47 键**，A 直接核验 `bpm_extraction.py`、`bpm_facts.py`、`verify_bpm_build.py` 均在清单且**哈希==盘上文件**。
- 先导 run `template-materials-20261024-1158-r2p5fix`（45 键，首次含 bpm_extraction.py=12246426…）证明修复先于 W04 施工。
- 全量 174/174 独立复跑 OK（146 基线零回归+28 新增）；新测试 test_bpm_facts.py 28/28 独立复跑 OK。
- failure_counts 中 `review|content|source_manifest_coverage|D23` 维持 1 不新增（对因闭合、无同 key 复犯）。

## D6 版本化业务事实层 — PASS_DYNAMIC（自 FAIL 翻转）

`bpm_facts.py`（sha256 8ec2fa75… 对账一致）代码面核验：
- 来源封闭枚举五类；`user_instruction` 绑定派生工件即 ValueError（L113-114，agent 推断禁伪装用户）；`deterministic_computation` 强制 derivation（L111-112）。
- 稳定 ID `F-0001…`（L116）；分配/免票引用 fact_id 不复制值（invoice_ref/expense_ref 校验 L200-202）。
- `check_version_drift` 只标记 needs_replan 不改写 frozen Fact（材料换版本→识别受影响→重新规划）。
- 未建模形态构造期 ValueError（L74-76：quantity×unit_price 等，不改名绕过）。
- 28/28 测试含 W03 产物集成（reviewed_extraction 建票）与 13 项反例实质断言。
- 真实业务事实工件随 W06 落地后复验（不影响本轮判据成立）。

## D7 对账先于写入 — PASS_DYNAMIC（自 FAIL 翻转）

reconcile 11 检 + 反例测试独立复跑通过：同票多扫归并且跨扫票面一致、票据 Decimal 闭合（含部分票面）、费用行覆盖与免票依据（免票无理由阻断 L210）、汇总 vs 明细、总额分层闭合含跨层双计拒绝、适用说明按类别、范围一致、收款身份组残缺/同名冲突阻断、未知材料边界、同金额不禁报、跨任务发票提示（只读 task-registry、提示级降级安全——fixtures 用 tests/fixtures/w04/task-registry-sim 模拟，真 registry 零触碰）。
- Excel 112.00 vs 票面 128.70 双向定位阻断有实测。
- 数量乘单价与借款抵扣构造期拒绝。

## 维持 PASS 复核（要点）

- **D14**：台账 W02/W03/W04 已验证、next=W05；主线 W02→W03→W04 连续无跳类。✔
- **D15**：单执行者+ENHANCED_FINAL fresh 首审 GO（13 件哈希零漂移）；真 registry 安静（120 分钟零改动）；HEAD 9299545 无新 commit。✔
- **D16**：交接五项齐备+R3-P2 挂账（_dec 静默 quantize、同账号不同名检测）归 W05。✔
- **D17**：层次标注不变，离线=离线。✔
- **D21/D26**：纯离线、守卫在位（_click_guard×10/SaveController×1）、不虚构、合成材料仅测试。✔
- **D24**：台账字段组完整、rounds[3] 绑定、notes 含 W05 入口。✔
- **D27**：八类真实材料缺口保留如实；独立工作持续推进。✔
