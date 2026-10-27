# 五类只读研究工件 2/2：福利费、劳保用品（submitType=04）

- 研究对象：历史单 15426071883（庄旭宏，2026-07-07，科技中心 2026 年第三季度团建费，totalCost 5250.00，bizStatus 结束）
- 证据：`raw_15426071883_fulilabao.json`（sha256 54456f5f808775c5c13b8a67896aaa77f0448a09f40f165418d1c563a61b2c7e，uuid 030a11e82ac9406b87b9880020bc2014，live GET observed_reimburse_uuid_get，--login-wait 0 单发）
- 身份锚定：captured_exact_list_identity ← census 20261023-142146 `list_items_api.json`（sha 66963f8a…），fresh main 与号/UUID 双匹配
- 只读边界：未注册类型、未启用写入路径、未开编辑页。

## 1. 主表结构（main，57 键，与 02 类逐键同形）

金额族：`totalCost=5250.00`、`bizCost=5250.00`、`payCost=5250.00`、`loanCost/quitCost/taxCost=0.00`、`upperCost=伍仟贰佰伍拾元`（与 totalCost 一致）、`exchangeRate=1.0000`。
关键开关：**`invoice=false`（文档级无发票）**、`bankWay=1`。
类别码：**`submitType="04"`**（本类身份码）；`payType="02"`（转账）；`bizOrigin=QDTech`（注意 budgetBizOrigin=QDFZ 与主表 bizOrigin 不同源）。
身份/组织：appliedBy 240600122 / 庄旭宏 / MK3305；createdBy=appliedBy。
结论：主表结构与 02 类及三类完全同形，无新增键——**类别差异全部落在子表形态与代码上**。

## 2. 子表结构与字段清单（children 全六表）

| 子表 | 行数 | 要点 |
|---|---|---|
| details | 1 | **reimItem=04003**，budgetNo=15626010048，budgetBizOrigin=QDFZ，budgetOwner=21，**budgetDept=TCHR 集团人力行政中心（跨部门预算：申请人部门 MK3305 ≠ 预算部门 TCHR）**，budgetItemName=员工福利费-部门团建费，subjectName=职工薪酬-福利费-团建费，subjectTotalCost=227850.00/subjectSurplus=129390.00，budgetUseCost=5250.00，cost=5250.00，serialNumber=0；**本行无 genreId 键**（服务端省略） |
| **costs** | **0** | **空表——本类费用不落 costs 行** |
| relations | 1 | **bizType=74（福利申请单）**，bizNumber=11826070006，bizCost=nowCost=5250.00，isLast="0" |
| banks | 1 | 庄旭宏 5250.00（=totalCost 闭合；单收款人） |
| products | 0 | 空 |
| detailrels | 1 | **bizDetailCost=0.00, bizDetailNum=0.00, usedCost=0.00**（关联行存在但明细级额度全零，与 02 类非零形态相反） |

## 3. 与三类（travel=08 / express=15 / rd_materials=11）及 02 类差异

1. **costs 空表 → 主费用表=details**：直接佐证现有 `_primary_table` 规则（costs 求和且非空才取 costs，否则 details）；与 rd_materials（products 主表）构成第三种主表取向。
2. **跨部门预算**：budgetDept（TCHR）≠ appliedDept（MK3305）——现有三类 details 建模未区分"申请部门预算"与"承担部门预算"，接入时 budgetDeptName 不能从申请人部门推导（红线：历史仅复用有依据的稳定身份，不得从旧单推导当次值）。
3. **relations 新 bizType=74（福利申请单）**：关联选择器按 bizTypeName 搜索的既有机制可复用，但类别→可关联单据类型的联动未观察。
4. detailrels 行存在但金额全零：**本类关联不要求明细级额度绑定**（与 02 类相反）——接入时 detailrels 可按"存在即透传、金额零不校验闭合"处理，待多样本确认。
5. 文档级 invoice=false 与 02 类一致；banks 单行=totalCost 闭合。
6. reimItem=04003：类别内费用项代码，前缀 04 与 submitType 同源（两类别两样本前缀一致，模式证据增强但仍非通则）。

## 4. 规则建模草案（draft，未注册未启用）

- 类型注册：`welfare_labor`（建议名），submitType="04"，四表 relations/details/banks + **primary_expense_table=details**（costs 恒空，table_applicability 须有当次来源理由，理由类型=本类历史单 costs 全空证据）。
- 金额闭合：totalCost=details 合计=banks 合计（本单 5250.00 三向闭合）；taxRate=0、loanCost=0 拒绝借款抵扣语义不变。
- details 行：预算维度聚合层即主费用层——每行绑定 budgetKey；**budgetDept/budgetDeptName 必须来自预算选择器实测，禁止从申请人部门推导**。
- costs 表：空表常量，`table_applicability.costs` 必填当次来源理由。
- relations：bizType=74 福利申请单关联，nowCost≤bizCost 沿用。
- detailrels：零金额形态，建模为可选透传，不参与闭合。
- 拒绝项沿红线：附件、贴票、外币、借款抵扣。

## 5. 接入所需共享能力清单

1. 类别码注册（"04"）+ 类型自发现映射。
2. reimItem 类别内枚举来源（04003…）：未捕获 → 缺口。
3. 预算选择器（含跨部门预算：按预算主体而非申请人部门查询）+ budgetUseCost 闭合。
4. primary=details 的空 costs table_applicability 来源理由类型（现有机制可直接复用，需新增理由枚举值"本类历史单 costs 全空"）。
5. detailrels 零金额形态的透传规则（与 02 类非零形态合并设计）。
6. 文档级 invoice=false 语义通道（与 02 类共用）。

## 6. 类型码证据（从证据确定，非中文名猜测）

| submitType | 类别 | 证据文件 |
|---|---|---|
| "08" | 差旅费 travel | automation/runs/20261024-155625-travelloop/template_snapshot.json |
| "11" | 研发物品 rd_materials | automation/runs/type-template-15426075122-20261023-194729、15426094566-20261023-194720、15426104120-20261023-194712（3 份实测=11） |
| "15" | 快递 express | automation/runs/type-template-15426082926-20261023-194703、15426083536-20261023-194654（2 份实测=15） |
| "02" | 低值易耗品、办公用品采购 | 本 run raw_15426101596_dijiazhi.json |
| **"04"** | **福利费、劳保用品** | **本 run raw_15426071883_fulilabao.json main.submitType** |

> 2026-10-24 勘误（ENHANCED_FINAL P1-b）：初版第 6 节误将 15426094566 目录引为 15 的证据（该目录实测 submitType=11）；15 的正确证据为 15426082926 与 15426083536 两份，已订正。

## 样本与缺口声明

单样本研究；编辑器联动（福利申请单关联来源、预算跨部门选择界面）未观察；reimItem 枚举未捕获；genreId 在本类行缺席的语义未知；detailrels 零金额结论待多样本。均不阻塞只读结论，为接入施工前必补证据。
