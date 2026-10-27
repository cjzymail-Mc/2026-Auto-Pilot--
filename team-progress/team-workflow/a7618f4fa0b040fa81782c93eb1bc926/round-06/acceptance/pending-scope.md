# Round-6 A 验收证据：未达判据清单（含用户纠偏上收）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

| ID | 判据 | Round-6 状态 | 归属 |
|---|---|---|---|
| D1 | 用户输入全链路 | 机制全备但未实跑：agent 自驱内部步骤（事实/blueprint/计划）未证（用户纠偏②）；真实请求→填写交付未做 | **Round-7 主靶** |
| D4 | PDF/图片真实理解 | 管线可运行≠真实理解：barstub 仅自制图、扫描 PDF 仅首页渲染（用户纠偏①，bpm_extraction.py:115）；需全页渲染+agent 视觉复核真实发票 | **Round-7 主靶** |
| D10 | 正式执行串联 | validate-only 就绪机制已验，但入口在缺预制 facts_payload 时停 MATERIALS_READY——agent 运行时自驱未证（用户纠偏②，fill_once.py:128）；**不翻转** | **Round-7 主靶** |
| D11 | 三类端到端 | 无第三层证据。**Round-7 必须启动**：授权历史业务原始材料→真实网页填写→独立 DOM 验收闭环（fill_only） | Round-7 起 |
| D12 | 五类接入 | 未注册；只读研究/规则建模/代码适配未启动（用户纠偏③：不得因缺新材料停工） | Round-7 并行 |
| D18 | 异常矩阵 | 进展：bizDate/payeeName 冒充反例+重复行拒绝入库；保存反例行未做 | 滚动 |
| D19 | 浏览器 B1-B7 | live 模板读取已做（B1 模板部分）；B2-B7 未做 | Round-7 |
| D20 | A1-A9 | 未做 | Round-7 起 |
| D22 | 新 session 验收 | 未做 | W10 |
| D25 | 完成定义六条 | 未全部成立；B 未虚报 | 终局门 |

结论：decision=rework。**Round-7 按用户指令定向**：①travel 一类真实闭环（原始资料→agent 自驱全链→真实网页填写 fill_only→独立 DOM 验收），不再接受纯离线轮替代；②真实发票全页渲染+agent 视觉复核；③并行五类只读研究≥2 类。无人工门、无熔断。
