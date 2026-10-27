# 五类只读研究工件 3/5：其他费用（submitType=01）

- 研究对象：历史单 15425125587（庄旭宏，2025-12-24 创建，科技中心 置物柜及温湿度传感器采购，totalCost 5736.98，bizStatus=4 结束）
- 证据：`raw_15425125587_zhiwugui.json`（sha256 12b5c2c0fa917dc4943f8a161c5b3636cfcb3216b1fcf128455bd361f5256ac7，uuid acee850d3b124964a13d3d3befd4d8b0，live GET observed_reimburse_uuid_get，--login-wait 0 单发）
- 身份锚定：captured_exact_list_identity ← census 20261023-142146 `list_items_api.json`（sha 66963f8a…），fresh main 与号/UUID 双匹配
- 只读边界：本 fetch 仅枚举 UI 查询 + GET；未注册类型、未启用写入路径、未开编辑页。
- 类别选取依据：census list 469 行中 submitType=01 共 10 条（06 各项会议支出 0 条，按合同§2/自主裁决③改选 01+24）。

## 1. 主表结构（main）

金额族：`totalCost=5736.98`、`payCost=5736.98`、`loanCost=0.00`、`quitCost=0.00`、`taxCost=0.00`、`currencyType=RMB`、`payType="02"`（转账，独立字段勿与 submitType 混淆）。
关键开关：**`invoice=false`（文档级无发票）**、`else=false`、`inLast=false`、`xSmartStatus=0`、`bizStatus=4`。
类别码：**`submitType="01"`**（本类身份码，实测）。
**`budgetYears=""`（空！描述明示"不占用预算"，动用《2024年度职工小发明小创造扶持项目补助资金》）**——区别于已研究各型的年度预算字段。
身份/组织：appliedName 庄旭宏（科技中心）；主表其余键与 travel/express/rd/02/04 同形，无新增键。

## 2. 子表结构与字段清单（children 全六表）

| 子表 | 行数 | 要点 |
|---|---|---|
| details | 1 | **无预算变体**：reimItem=**01015**、budgetKey=**"__"**（无预算标记）、budgetYear=0、budgetItemCode=""、subjectTotalCost/subjectSurplus=0.00、budgetUseCost=5736.98、digest=上海博棒电子科技有限公司、cost=5736.98、taxRate/taxCost=0。**无 budgetDeptName/budgetNo/budgetItemName/subjectName 等预算字段**（区别于 02/24 的全预算 details） |
| costs | 0 | 费用说明空（同 rd 的 costs 空分支） |
| relations | 1 | bizSystem=OA、**bizType=34（申请书）**、bizNumber=10125122466、**bizCost=5740.00 > totalCost**（申请书金额大于本次报销额）、nowCost=5736.98、isLast="0" |
| banks | 2 | 方彩霞 2540.00（对私）+ 庄旭宏 3196.98（对私）= **5736.98 与 totalCost 闭合**（多收款人分摊） |
| products | 0 | 空（本类不用物品档案） |
| detailrels | 2 | 同一申请书 10125122466 两明细行：鞋类保温性能测试 bizDetailCost=2540.00→cost=2540.00；样品及设备收纳 bizDetailCost=**3200.00→cost=3196.98**（**部分占用：行 cost < 申请书明细可用额**） |

## 3. 与已研究五类（08/11/15/02/04）差异

1. **details 无预算变体（本类独有）**：budgetKey="__" + budgetYear=0 + 预算族字段缺席/清零；"不占用预算"语义由描述+字段共同承载。现有 details 建模（travel/express/rd/02/24）均假定预算族存在（空值也带字段），本类连字段形状都不同——接入时 details 列配置需支持"无预算列"分支或可空预算列。
2. **relations=申请书（bizType=34）**：travel 仅支持公出单；02/04 研究件也见 34；本类再次实测 34 且**关联多明细行（detailrels 2 行）+部分占用**——明细级分配（cost ≤ bizDetailCost）是 travel 单明细全额模式之外的新形态。
3. **budgetYears 空**：已研究各型均为具体年度字符串；本类空串与"不占用预算"联动。接入校验不应把空 budgetYears 当缺失阻断，应要求当次来源理由。
4. costs 空、文档级 invoice=false、多收款人分摊、products 空——与 02/04 共性，非本类新增。

## 4. 规则建模草案（draft，未注册未启用）

- 类型码 01、reimItem 枚举至少含 01015（样本 1；枚举不穷举）。
- 金额闭合：details.cost = banks 合计 = totalCost（5736.98 实测闭合）；relations.nowCost=totalCost。
- 关联规则：申请书 bizType=34；relations.bizCost ≥ nowCost 允许（5740≥5736.98）；detailrels 行 cost 之和应= totalCost（2540+3196.98），单行 cost ≤ 对应 bizDetailCost。
- 免票：文档级 invoice=false（行级免票机制不需要）。
- 空表：costs 空需 table_applicability 当次理由（同 rd 模式）；relations/products 非空/空按材料实情。
- **未建模待证**：无预算 details 的 UI 编辑器联动（无预算时 reimItem/预算选择器行为）、budgetKey="__" 是否本类固定值——需真实编辑页观察，本轮只读不验证。

## 5. 接入所需共享能力清单

1. details 无预算列变体支持（列配置级：预算族列可选）。
2. 关联类型"申请书"（34）注册进 extra_table_projections.detailrels.supported_relation_types，含多明细行选择与部分占用金额分配。
3. budgetYears 空值 + "不占用预算"来源理由建模。
4. 文档级 invoice=false 建模（与 02/04 共用）。
5. 多收款人分摊闭合（已有，banks 多行；复用）。

## 6. 类型码证据（从证据确定，非中文名猜测）

- `submitType="01"`：raw_15425125587 main 实测（本工件证据文件）。
- 与 census list 469 行 submitType 分布互证：01 共 10 条，本单 bizNumber 15425125587 在列。
- 申请书 bizType=34：relations/detailrels 行实测。
- reimItem=01015：details 行实测。
- **七类实测互异汇总**：08 差旅费 / 11 研发材料费 / 15 快递费 / 02 低值易耗品办公用品 / 04 福利费劳保用品 / **01 其他费用（本件）** / 24 维修费（见姊妹工件）。

## 样本与缺口声明

单样本研究（01 类 10 候选中选最复杂的预算关联描述单）；无预算 details 编辑器联动、申请书 picker 交互、budgetKey="__" 语义未在真实编辑页验证——均为接入前缺口，需授权真实编辑页观察或用户供料补充。本研究零注册零启用零写页面。
