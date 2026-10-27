# Round-7 A 验收证据：未达判据清单（更新）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

| ID | 判据 | Round-7 状态 | 归属 |
|---|---|---|---|
| D4 | PDF/图片真实理解 | **BLOCKED**：机制全备并动态验证（全页渲染+agent 视觉 4.5v，合成两页 8/8；barstub 降级纯测试注记）；"至少一笔真实业务 PDF/图片复核"被外部缺口阻断——`REAL_TRAVEL_INVOICE_ORIGINALS_ABSENT`（盘点 searched 范围内无真实发票原件）。用户提供真实发票原件后即可执行，非代码缺口 | 供料依赖；round-8 不阻塞 |
| D11 | 三类端到端 | travel 闭环机制完整走通（本笔为授权历史回放，判据明文"仅历史回放不计为通过"）→ travel 仍需"本次原始资料"一笔；express/rd 闭环未做 | **Round-8 主靶** |
| D12 | 五类接入 | 2/5 类研究工件落盘（02 低值办公、04 福利劳保，类型码全实测）；其余三类（其他费用/维修费/会议支出）研究未做；接入施工（注册/schema/共享能力）未开始 | Round-8 并行 |
| D18 | 异常矩阵 | 新增真实反例：`COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED`（当前默认身份差异）、registry FORM_INTENT 门+死意图接替、`EXACT_PICK_MISSING` 瞬时、写后页失 rebuild；尚待离线测试固化 + 保存反例行（保存验收继续排除） | 滚动 |
| D19 | 浏览器 B1-B7 | travel B1-B7 已有真实整单证据（入口/身份/唯一命中/联动/整单 events/新鲜 DOM/agent 结论/盘点+终局截图）；express/rd 未做 | Round-8 |
| D20 | A1-A9 | travel A1-A9 逐项已备（回放材料基础上）；express/rd 未做；判据为"每类" | Round-8 |
| D22 | 新 session 验收 | 未做 | W10 |
| D25 | 完成定义六条 | 未全部成立；B 未虚报 | 终局门 |

D1、D10 本轮翻转为 PASS_DYNAMIC（依据见 A-verification.md §7）；D4 由 FAIL 转记 BLOCKED。当前 19 PASS / 1 BLOCKED / 7 FAIL。decision=rework，无新 failure key（D23 维持 1/3）。

Round-8 方向（详见任务书）：express+rd 真实闭环（同 travel 模式）、P1-a 合同追认增补、五类研究续三类、P2 小项、D18 新反例测试固化。
