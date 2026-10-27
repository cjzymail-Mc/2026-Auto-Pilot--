# Round-8 五类研究续推总结（run 20261024-180000-research-r8）

## 本轮新增（2/3 余类，第 3 类 06 无候选）

| 类别 | 码（实测） | 样本单号 | 工件 | 关键新形态 |
|---|---|---|---|---|
| 其他费用 | 01 | 15425125587 | research_qitafeiyong_15425125587.md | details 无预算变体（budgetKey="__"/budgetYears 空）、申请书关联多明细部分占用、bizCost>totalCost |
| 维修费 | 24 | 15426015123 | research_weixiufei_15426015123.md | 税额三值模型（cost/taxCost/realCost=cost−taxCost）、对公收款人银行行 |
| 各项会议支出 | 06 | —（census list 469 行 0 候选） | 不做（按合同§2 自主裁决③改选 01+24） | — |

- raw fetch 预算：计划 2 发、实际 2 发（≤5 达标）；均 --login-wait 0、observed_reimburse_uuid_get 只读、captured_exact_list_identity 锚定（census 142146 list_items_api.json sha 66963f8a…）。
- 零注册零启用零写页面。

## 五类总进度（含 round-7）

- 已研究 4/5：02 低值办公（15426101596）、04 福利劳保（15426071883）、01 其他费用（15425125587）、24 维修费（15426015123）。
- 未研究 1/5：06 各项会议支出——**census 142146 list 证据 0 候选**，需新 list 窗口或用户供单号后补。
- 类型码七类实测互异：08/11/15/02/04/01/24（证据链在各研究件 §6）。
- 代码适配准备：code-adaptation-prep-02-04.md（A 落点映射 9 项 + B 实施顺序 + C 边界；零实施）。

## 共用能力互证更新（跨 01/24 与 02/04）

- 文档级 invoice=false：四类（02/04/01/24）全部实测 → 通道设计输入已足。
- 申请书关联（bizType=34）：四类全部实测（travel 公出单之外的第二关系族）。
- costs 空表理由机制：01/24/rd 三型实测，复用 rd costs_reason。
- 税额模型与对公收款人为 24 独有；无预算 details 为 01 独有——接入设计需分型承载，不并入共用通道。
