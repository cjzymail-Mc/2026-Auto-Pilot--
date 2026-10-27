# B-R1 轮报告（BPM-SELFDRIVE-20261027-V1 round 1）

- run: 20261027-111853-f2789e00 ｜ workflow: 242ccba1c43343f687aa1db0ae014f5b round 1
- 冻结合同: ctr-640d0763（minimal，T3+B+AUTO，ENHANCED）｜ 执行: B（CLAUDE_GLM，glm-5.3）
- 范围: P0 接手核实 + P1 入口/规则版本化设计落地 + P2 规则计算核心与经典反例测试（全离线只读）

## 交付物

| 交付 | 路径 | sha256 |
|---|---|---|
| P0 盘点（六要素） | automation/runs/20261027-111853-f2789e00/p0-inventory.json | 072e63ac79f924e53a94420c51bb1e0b1091294c0eba01064da656a7c8d1e2af |
| P1 入口设计决策 | automation/runs/20261027-111853-f2789e00/p1-entry-design.md | 63d38b85c8e1e04ea599481f9dd84936bdba14f303dc73e49011d8c1d3f7750f |
| 自驾规则配置 v1.0.0 | automation/business-scenarios/self_drive.json | de06680806a04123c6421147ad7bca9ae8404afdb7e891d5bc15f0777e224b62 |
| 金额模型模块 | bpm_self_drive.py | ba33c3e21e32d07699a062aa813371b3affc101bffae999140400c67d04b2b9c |
| 反例/规则测试（29 用例） | tests/test_bpm_self_drive.py | 36bd00e555f3547c9eaed459a4f8a8b6b0bd08fd715ff1f71a88adf0d67fb37c |
| 离线构建产物 | automation/offline-verify/20261027-111853-f2789e00/（build_result.json） | ef37b73e60b94ad7b3ca6c26ea7dbb4824b4a9edbf34d0ae86f4646bd18a3078 |
| MC 终审报告 | automation/runs/20261027-111853-f2789e00/MC-R1-report.md | 见文件 |
| 轮事件 | automation/runs/20261027-111853-f2789e00/events.jsonl | 追加式（14+1 条） |

另：`verify_bpm_build.py` 源清单 +`automation/business-scenarios/self_drive.json` 一行
（唯一代码改动；bpm_coverage.py 零改动——MC 以双 manifest 哈希全等坐实）；STATE.md 按
维护标准更新（session-new 母本固化件）。

## done_when 四态签字（B）

| # | 判据 | 状态 | 证据 |
|---|---|---|---|
| D1 | P0 盘点工件落新 run（工作树/执行者/锁/registry/页面 + 可复用基础与缺口 + 身份探查 + 样本 15425123013 核验），events 有对应事件 | **PASS_DYNAMIC** | p0-inventory.json 六要素；events.jsonl run_start→zero_business_write_closeout；身份探查 11:20:45 SUCCESS_LOGIN_ONLY（陈晶 authenticated，effective_reuse_until 2026-11-23）；样本经既有 live 快照核验（差旅费/08/2176.93/徐亮），未新增浏览器动作 |
| D2 | self_drive.json v1 含场景 ID/版本/适用表单/1.00/30.00/R=M+T+C/F=O+T/严格 F>R/规则来源，加载校验代码与测试通过 | **PASS_DYNAMIC** | 配置 sha256 de066808…；ConfigTests（加载/哈希稳定/10 类篡改全拒）绿；MC 复跑确认 |
| D3 | bpm_self_drive.py 金额模型 + §6.1 反例全绿（抵消不放行/逐单定位/437.18 不误判/日期反例/新旧分离/F=R、F<R 无容差） | **PASS_DYNAMIC** | 29 用例绿（ClassicCounterexampleTests/RulesBindingTests/SeparationTests 等）；MC 独立复跑 + 断言非恒真核验（内嵌阳性对照 381.76 抵消前提、439.18 污染派生值显式排除） |
| D4 | 全量 unittest 无回归；verify_bpm_build OFFLINE_PASS 且新文件入源清单 | **PASS_DYNAMIC** | 345 tests OK（skipped=4 既有）；OFFLINE_PASS（probe-selftest + capability-tests exit 0）；source_manifest 含 self_drive.json/bpm_self_drive.py/tests 三件 |
| D5 | 零业务写入与只读零漂移（73 原件不变/registry 零改动/无保存类点击） | **PASS_DYNAMIC** | 73/73 vs v3r00 基线 0 漂移 0 新增（本轮收尾第 10 次，MC 独立复算同）；registry 12 件 mtime ≤07:42:57；浏览器仅身份探查 ×1；events zero_business_write_closeout |

## MC 终审

fresh mc-expert ENHANCED_FINAL：**GO**（HASH_VALIDITY=VALID；无 blocker/major；4 条 minor：
P2-1 证据形态说明、**P2-2 后续轮约束——P3 接线时调用处必须强制 `rules=load_self_drive_rules()`**、
P2-3/P2-4 informational）。报告：MC-R1-report.md。

## 后续轮交接要点（供 A 派工）

1. P2-2（MC）：正式入口接线时强制 rules= 绑定，使历史餐补分离成为机制而非约定。
2. 合同 §7 下一阶段：识票归集/规范命名、Excel 副本回填、真实公出单匹配与写入前 MD、
   30 天会话改造、SKILL/self-drive runbook 实质修订、真实串联与 D12 冷启动。
3. 本轮案例对照值仅存在于 tests（合同 §5 授权），生产配置零命中（MC grep 实证）。
