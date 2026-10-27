# MC-R1 ENHANCED_FINAL 审计报告（BPM-SELFDRIVE-20261027-V1 round 1）

- 审计对象：冻结合同 ctr-640d0763 D1-D5 最终产物（6 件，哈希绑定）
- reviewer：fresh mc-expert（ENHANCED_FINAL，GLM 栈；确定性承重由哈希/复跑/夹具对照承担）
- 时间：2026-10-27（B 收到报告后落档）
- **总判定：GO**（HASH_VALIDITY=VALID；D1-D5 逐条属实；§6.1 断言非恒真；无 blocker/major）

## 审计产物（sha256，审前=审后=声称）

| # | 文件 | sha256 |
|---|---|---|
| 1 | automation/business-scenarios/self_drive.json | de06680806a04123c6421147ad7bca9ae8404afdb7e891d5bc15f0777e224b62 |
| 2 | bpm_self_drive.py | ba33c3e21e32d07699a062aa813371b3affc101bffae999140400c67d04b2b9c |
| 3 | tests/test_bpm_self_drive.py | 36bd00e555f3547c9eaed459a4f8a8b6b0bd08fd715ff1f71a88adf0d67fb37c |
| 4 | automation/runs/20261027-111853-f2789e00/p1-entry-design.md | 63d38b85c8e1e04ea599481f9dd84936bdba14f303dc73e49011d8c1d3f7750f |
| 5 | automation/runs/20261027-111853-f2789e00/p0-inventory.json | 072e63ac79f924e53a94420c51bb1e0b1091294c0eba01064da656a7c8d1e2af |
| 6 | automation/offline-verify/20261027-111853-f2789e00/build_result.json | ef37b73e60b94ad7b3ca6c26ea7dbb4824b4a9edbf34d0ae86f4646bd18a3078 |

## 结论摘要

- D2 配置封闭校验 10 类篡改全拒；D3 抵消不放行/逐单 +4.00、−10.00 定位/437.18 正向对照
  不误判/日期反例识别/历史餐补五值分离/F=R、F<R 无容差——均为真实行为断言（内嵌阳性对照）。
- D4 reviewer 独立复跑：29 用例 OK、全量 345 OK（skipped=4）、OFFLINE_PASS、
  source_manifest 含 self_drive.json 同值哈希。
- D5 reviewer 独立复算 73 原件 0 漂移 0 新增；registry 12 件 mtime ≤07:42:57 零改动；
  浏览器仅身份探查 ×1。
- 越界：三新文件零手机号/实名/凭证；16 个案例对照金额在生产配置 self_drive.json 零命中
  （grep 实测），仅存在于合同授权的离线测试。

## FINDINGS（4 条 minor，无 blocker/major）

- **P2-1（证据形态，非缺陷）**：bpm_coverage.py / verify_bpm_build.py 为 rounds 3-10 遗留
  未跟踪文件，`git diff/status` 形态不成立；以两份 source_manifest 哈希全等（27863654…）+
  mtime 早于本轮 + 内容审读（仅 L33-35 注释与源清单一行增补）替代坐实零漂移。
- **P2-2（后续轮约束，须入下轮任务）**：`evaluate_self_drive` 不传 rules 时按输入口径计算
  （原始计算器语义，测试已显式声明）；"旧餐补值传入即拒"目前由生产调用方绑定 rules= 承载。
  **P3 正式入口接线时必须在调用处强制 `rules=load_self_drive_rules()`，否则分离保证是约定
  而非机制。**已录入 handoff 供 A 派下轮时纳入。
- P2-3（informational）：bpm_self_drive.py docstring 提及 437.18——说明文字非路由逻辑值，
  不违反对照值边界；后续可改为不含具体值表述。
- P2-4（informational）：p0-inventory 的"锁"盘点内嵌于叙述而非独立字段；D1 字面仍齐备，
  后续轮可结构化。

## 未重放范围（reviewer 声明，非承重）

身份探查不重入生产会话（单 profile 单执行者），以 events + session_record 一致性 +
快照互证采信；verify_bpm_build.py 字节级 git delta 不可证（未跟踪），以 manifest 哈希差 +
全量构建产物 + 独立复跑采信。

（完整命令清单与八面 CHECKS 明细见 reviewer 原始报告，转录于本 run events 与 team-progress。）
