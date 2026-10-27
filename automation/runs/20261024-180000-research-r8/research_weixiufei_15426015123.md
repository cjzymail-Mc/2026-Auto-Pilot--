# 五类只读研究工件 4/5：维修费（submitType=24）

- 研究对象：历史单 15426015123（庄旭宏，2026-01-28 创建，减震性能试验机维修报销，totalCost 1500.00，bizStatus=5）
- 证据：`raw_15426015123_weixiu.json`（sha256 37d954c2880f1503337362d9764d36ed89e260ed866d56ce3d39265597afb5e9，uuid ff77492f86f4403fa501ebd9a33083e6，live GET observed_reimburse_uuid_get，--login-wait 0 单发）
- 身份锚定：captured_exact_list_identity ← census 20261023-142146 `list_items_api.json`（sha 66963f8a…），fresh main 与号/UUID 双匹配
- 只读边界：本 fetch 仅枚举 UI 查询 + GET；未注册类型、未启用写入路径、未开编辑页。
- 类别选取依据：census list 469 行中 submitType=24 共 2 条（06 各项会议支出 0 条，按合同§2/自主裁决③改选 01+24）；本单为 2026 年度最新且带税额模型。

## 1. 主表结构（main）

金额族：`totalCost=1500.00`、`payCost=1500.00`、`loanCost=0.00`、`quitCost=0.00`、**`taxCost=172.57`（非零！已研究七类中首个文档级税额模型）**、`currencyType=RMB`、`payType="02"`。
关键开关：**`invoice=false`（文档级无发票）**、`else=false`、`inLast=false`、`xSmartStatus=0`、`bizStatus=5`。
类别码：**`submitType="24"`**（本类身份码，实测）；`budgetYears="2026"`。

## 2. 子表结构与字段清单（children 全六表）

| 子表 | 行数 | 要点 |
|---|---|---|
| details | 1 | **全预算变体**（同 02 形状）：reimItem=**24001**、budgetId/budgetDetId/budgetNo=15625120075、budgetBizOrigin=QDTech、budgetYear=2026、budgetDept=MK33/科技中心、budgetItemCode=1/budgetItemName=年度预算项目、subjectName=维修费、digest=设备维修、cost=1500.00、**taxCost=172.57、realCost=1327.43 = cost − taxCost**、budgetUseCost=1500.00、genreId="" |
| costs | 0 | 费用说明空（同 rd/01 的 costs 空分支） |
| relations | 1 | bizSystem=OA、**bizType=34（申请书）**、bizNumber=10126012488、bizCost=1500.00、nowCost=1500.00、isLast="0" |
| banks | 1 | **对公收款人**：高铁检测仪器（东莞）有限公司、account=667857740755、中国银行东莞南城支行、cost=1500.00（单行=totalCost 闭合） |
| products | 0 | 空（本类不用物品档案） |
| detailrels | 1 | 申请书 10126012488 明细：digest=设备维修费、bizDetailCost=1500.00、bizDetailNum=1.00、cost=1500.00（全额占用） |

## 3. 与已研究六类（08/11/15/02/04/01）差异

1. **税额三值模型（本类独有）**：details 同行 cost=1500.00 / taxCost=172.57 / **realCost=1327.43=cost−taxCost**，且 main.taxCost=172.57 与行级一致。已研究各型 taxRate/taxCost 恒 0。接入时金额闭合规则需明确闭合基准（本样本：cost（含税）对齐 totalCost/banks/relations.nowCost/budgetUseCost；realCost 为派生不含税值）。
2. **对公收款人银行行**：payee 为公司名+对公账户。现有 banks 建模（travel/express/rd）均对私多收款人；对公单收款人是新形态（无需开户行 picker 联动差异待证）。
3. relations=申请书（34）单明细全额占用（同 02/04 形态；区别 01 的多明细部分占用）。
4. details 全预算字段形状与 02 完全同形（budgetOwner 除外——本样本无 budgetOwner 键，02 样本有）。
5. costs 空、文档级 invoice=false、products 空——与 01/02/04 共性。

## 4. 规则建模草案（draft，未注册未启用）

- 类型码 24、reimItem 枚举至少含 24001（样本 1；枚举不穷举）。
- 金额闭合：details.cost = banks 合计 = totalCost = relations.nowCost = budgetUseCost（1500.00 实测）；**realCost=cost−taxCost 派生**；main.taxCost=Σ行 taxCost。
- 关联规则：申请书 bizType=34；单明细全额占用（cost=bizDetailCost）。
- 免票：文档级 invoice=false（行级免票机制不需要）。
- 空表：costs 空需 table_applicability 当次理由（同 rd 模式）。
- **未建模待证**：taxCost 的 UI 录入方式（手输/税率联动）、对公账户 picker 行为、genreId 语义——需真实编辑页观察，本轮只读不验证。

## 5. 接入所需共享能力清单

1. 税额三值行模型（cost/taxCost/realCost）+ 文档级税额合计校验（与 01/02/04 共用闭合框架的扩展维度）。
2. 对公收款人银行行支持（payee 公司名+对公账户；picker 联动差异待证）。
3. 关联类型"申请书"（34）注册（与 01/02/04 共用）。
4. 文档级 invoice=false 建模（与 01/02/04 共用）。
5. costs 空表理由机制（复用 rd 已有）。

## 6. 类型码证据（从证据确定，非中文名猜测）

- `submitType="24"`：raw_15426015123 main 实测（本工件证据文件）。
- 与 census list 469 行 submitType 分布互证：24 共 2 条，本单 bizNumber 15426015123 在列（另一条 15425042138 灯具维修 9728.00 未取数）。
- 申请书 bizType=34：relations/detailrels 行实测。
- reimItem=24001：details 行实测。
- **七类实测互异汇总**：08 差旅费 / 11 研发材料费 / 15 快递费 / 02 低值易耗品办公用品 / 04 福利费劳保用品 / 01 其他费用 / **24 维修费（本件）**。

## 样本与缺口声明

单样本研究（24 类仅 2 候选，取 2026 最新带税额单）；税额录入交互、对公 picker、budgetOwner 缺席是否本类固定——均为接入前缺口，需授权真实编辑页观察或用户供料补充。本研究零注册零启用零写页面。
