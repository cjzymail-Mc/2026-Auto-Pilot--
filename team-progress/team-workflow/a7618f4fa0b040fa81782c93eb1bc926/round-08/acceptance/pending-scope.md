# Round-8 A 验收证据：未达判据清单（更新）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

| ID | 判据 | Round-8 状态 | 归属 |
|---|---|---|---|
| D4 | PDF/图片真实理解 | 维持 **BLOCKED**：机制已证（r7），真实发票原件仍缺（`REAL_TRAVEL_INVOICE_ORIGINALS_ABSENT` 延续） | 供料依赖 |
| D11 | 三类端到端 | 三类机制层闭环全通（travel r7 / express r8 / rd r8，均 SUCCESS_FILL_ONLY+独立回读零差异）；判据明文"仅历史回放不计为通过"——三类均待"本次原始资料"一笔 | 供料依赖；round-9 不阻塞 |
| D12 | 五类接入 | 研究 4/5（08/11/15/02/04/01/24 码实测；06 无候选）；`code-adaptation-prep-02-04.md` 9 落点就绪；注册/schema/共享能力施工未开始（B 已申请 bpm_types.py/document-types 写授权） | **Round-9 主靶** |
| D18 | 异常矩阵 | +2 反例测试固化（身份阻断/瞬时 picker）+服务端无残留只读观察；PDF/图片多页一页多票、Excel 多 sheet/公式/隐藏筛选等变体行与保存行仍缺 | Round-9 补离线矩阵行 |
| D20 | A1-A9 | 三类 A1-A9 机制证据齐备（回放材料基础）；判据要求"本次真实业务"一笔 | 供料依赖 |
| D22 | 新 session 验收 | 未做（B 建议准备入口） | W10；round-9 准备 |
| D25 | 完成定义六条 | 未全部成立；B 未虚报 | 终局门 |

D19 本轮翻转为 PASS_DYNAMIC（三类真实 Chromium 整单 B1-B7 证据齐备）。当前 **20 PASS / 1 BLOCKED / 6 FAIL**。decision=rework，无新 failure key（D23 维持 1/3）。

Round-9 方向（详见任务书）：五类接入施工 02/04 首件放量（A 表 1-2 级：config 落盘→封闭注册→离线链，新增写授权 bpm_types.py+automation/document-types/）、D18 离线矩阵补行（PDF/Excel 变体）、D22 新 session 验收准备、mc-expert 三条非阻塞观察（events 单例化/键名消歧/布尔命名）。
