# Round-9 A 验收证据：未达判据清单（更新）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

| ID | 判据 | Round-9 状态 | 归属 |
|---|---|---|---|
| D4 | PDF/图片真实理解 | 维持 **BLOCKED**：真实发票原件仍缺（供料依赖） | 用户供料 |
| D11 | 三类端到端 | 不变：三类机制层全通（r7/r8），待"本次原始材料"各一笔 | 用户供料 |
| D12 | 五类接入 | 02/04 达"config+封闭注册+离线链 validate-only"级（2/5）；真实页面观察/控件测试/端到端未开始；06 无候选（4/5 研究已备） | **Round-10 主靶**（控件观察授权→逐步放量） |
| D18 | 异常矩阵 | +4 行（多页 PDF/一页双票契约/Excel 变体/数值保真）；不同扫描同票、相同金额不同业务、含税未税混淆等仍缺；保存行按指令排除 | 滚动 |
| D20 | A1-A9 | 不变：三类机制证据齐备（回放基础），待本次真实业务 | 用户供料 |
| D22 | 新 session 验收 | 方案就绪（S1-S9+G1-G6 缺口表），实施待授权 | **Round-10 起**（G1 链产品化可先行） |
| D25 | 完成定义六条 | 未全部成立；B 未虚报 | 终局门 |

无判据翻转（20 PASS / 1 BLOCKED / 6 FAIL 维持）。decision=rework，无新 failure key（D23 维持 1/3）。

Round-10 方向（详见任务书）：①附属同步三项（verify_bpm_build manifest document-types 清单、fill-plan.schema.json enum 五类型、bpm_extraction 一页多票显式拒绝+测试）——补 A 的 round-9 授权遗漏；②02/04 只读控件观察（真实新页类别联动/选择器枚举只读观察，零业务行零保存，页面放弃留痕，config required_observations 回填）；③D22 G1 实施 bpm_chain.py（链产品化，折入 P2-2/P2-3/P2-4）。
