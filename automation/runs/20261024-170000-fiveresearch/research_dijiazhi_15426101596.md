# 五类只读研究工件 1/2：低值易耗品、办公用品采购（submitType=02）

- 研究对象：历史单 15426101596（张宇昂，2026-10-08，科技中心第三季度 AI 工具申购申请报销，totalCost 9974.76，bizStatus 结束）
- 证据：`raw_15426101596_dijiazhi.json`（sha256 86bf99dea2c0a820d72291d21b6277d4f3d1808dc87d2cf424dd854d9323572c，uuid 20a325a1c8bf441988a1ab69df60bfda，live GET observed_reimburse_uuid_get，--login-wait 0 单发）
- 身份锚定：captured_exact_list_identity ← census 20261023-142146 `list_items_api.json`（sha 66963f8a…），fresh main 与号/UUID 双匹配
- 只读边界：本 fetch 仅枚举 UI 查询 + GET；未注册类型、未启用写入路径、未开编辑页。

## 1. 主表结构（main，57 键全量盘点）

金额族：`totalCost=9974.76`、`bizCost=9974.76`、`payCost=9974.76`、`loanCost=0.00`、`quitCost=0.00`、`taxCost=0.00`、`upperCost=玖仟玖佰柒拾肆元柒角陆分`（与 totalCost 一致）、`currencyTotalCost`、`exchangeRate=1.0000`、`currencyType=RMB`。
关键开关：**`invoice=false`（文档级无发票）**、`sales=false`、`else=false`、`bankWay=1`、`flowNext=true`、`isBackFlow=false`。
类别码：**`submitType="02"`**（本类身份码）；`payType="02"`（转账，独立字段勿与 submitType 混淆）；`bizOrigin/bizOrign=QDTech`、`corpCode=1003`、`bizCategory=0`、`priorityCode=0`。
身份/组织：appliedBy 220602092 / appliedName 张宇昂 / appliedDept MK3305 运动表现研究部 / appliedCenterCode MK33；createdBy=appliedBy（同人）。
其余键与 travel/express/rd 主表同形（_v_、bizStatus=4、audit 族、appliedPath/createdPath、appliedPhone 等），主表结构无新增键。

## 2. 子表结构与字段清单（children 全六表）

| 子表 | 行数 | 字段（去 id/reimburseId 元数据） |
|---|---|---|
| details | 1 | realCost, detCost, reimedCost, digest, cost, serialNumber, taxRate, taxCost, **reimItem=02001**, budgetId, budgetDetId, budgetNo=15625120075, budgetBizOrigin, budgetOwner, budgetYear, budgetDept, budgetDeptName, budgetItemCode, budgetItemName=年度预算项目, subjectId, subjectName=办公费, subjectTotalCost, subjectSurplus, budgetUseCost, genreId(""), occupyRelationType, budgetKey, sortOrder |
| costs | 1 | startDate=2026-07-01, endDate=2026-09-30（**日期区间**）, project="other", projectPlace=厦门, reason, **count=90（数量）**, cost=9974.76 |
| relations | 1 | bizSystem=OA, **bizType=34（申请书）**, bizTypeName, bizId, bizNumber=10126100347, bizCost=9974.76, totalReimedCost=0, nowCost=9974.76, isLast="0" |
| banks | 3 | payee/account/bank/bankCode/cost/sortOrder/serialNumber：庄旭宏 4856.75 + 冯明 3597.00 + 余康 1521.01 = **9974.76 与 totalCost 闭合**（多收款人分摊） |
| products | 0 | 空（本类不用物品档案） |
| detailrels | 1 | bizType=34, bizNo=10126100347, bizDetailId, digest=AI工具会员功能, **bizDetailCost=9974.76, bizDetailNum=1.00**, usedCost=0, cost=9974.76（**非空明细级关联**） |

## 3. 与三类（travel=08 / express=15 / rd_materials=11）差异

1. **costs 列形与 travel/express 完全同形**（cost/count/endDate/project/projectPlace/reason/startDate），但语义为"数量+日期区间汇总行"：count=90、cost=行总额——**不是单价×数量模型**（区别于 rd products.price）。
2. **主表 invoice=false 文档级免票**：travel 是行级发票抽取/免票依据（no_invoice_rows），本类在 main 层一票否决，行级免票理由机制不需要；接入时免票语义应落在文档级。
3. **details 预算维度远超现有建模**：现有三类 details 仅建模 budgetDeptName/budgetItemName/budgetNo/budgetOwner/subjectName（+cost/digest/reimItem）；本类行携带 budgetId/budgetDetId/budgetKey/budgetItemCode/subjectId/subjectTotalCost/subjectSurplus/budgetUseCost/budgetYear/budgetBizOrigin/occupyRelationType/taxRate/taxCost 共 14 个未建模键。
4. **reimItem 为类别内费用项代码**：02001（办公费语义由 subjectName 佐证）——与 travel 的 reimItem 枚举不同源，类别接入需独立枚举来源。
5. **detailrels 非空**：现有"新类型暂不支持非空关联"红线正对应此形态；本类真实使用申请书明细行级额度绑定（bizDetailCost/bizDetailNum）。
6. banks 多收款人分摊（3 行合计=totalCost）：现有四表行数组天然支持，无结构差异，仅闭合规则。
7. relations 同形；新增 bizType=34（申请书）代码证据。

## 4. 规则建模草案（draft，未注册未启用）

- 类型注册：`low_value_office`（建议名），submitType="02"，四表 relations/details/costs/banks，无 products。
- 主表：primary=costs（非空且 rules.costs=sum）；totalCost=banks 合计=costs 合计=details 合计（本单 9974.76 四向闭合）；文档级 invoice=false 常量，行级免票机制不适用。
- details 行：预算维度聚合层（summary 层），每行必须绑定 budgetKey（budgetId+budgetItemCode+subjectId 复合）；amount=cost；budgetUseCost 与 cost 一致。
- costs 行：明细层（detail 层），count 为整数数量（≥1），cost 为行总额（**不建模单价乘数量**）；startDate/endDate 为区间校验（start≤end）；project 枚举见 travel 既有枚举（"other" 已在册）。
- relations：bizType=34 申请书关联，nowCost≤bizCost 校验沿用。
- detailrels：**接入前置条件**——需先扩展关联层支持（与 express 复杂研究结论合并处理），本草案标记为 executable=false 的阻塞项。
- 拒绝项（沿现有红线）：借款抵扣（loanCost≠0）、附件、贴票、外币（exchangeRate≠1）继续拒绝。

## 5. 接入所需共享能力清单

1. 类别码注册进 bpm_types 封闭注册表（"02"）+ 类型自发现映射更新。
2. reimItem 类别内费用项枚举来源（02001…）：需编辑页观察或接口枚举证据，本轮未捕获 → 缺口。
3. 预算维度选择器（budgetNo/budgetItem/subject 三级联动 + budgetUseCost 闭合校验）——现有三类 details 字段可复用为显示层，但选择器未建模。
4. 文档级 invoice=false 免票语义通道（区别于行级 no_invoice_rows）。
5. costs 行日期区间校验（start≤end）+ count 整数语义（travel costs 已有 count 列，可复用）。
6. detailrels 非空关联支持（与 express R1/R2 复杂研究共用同一能力缺口）。
7. genreId 语义未知（本单空串）→ 需编辑页观察，暂列观察缺口。

## 6. 类型码证据（从证据确定，非中文名猜测）

| submitType | 类别 | 证据文件 |
|---|---|---|
| "08" | 差旅费 travel | automation/runs/20261024-155625-travelloop/template_snapshot.json |
| "11" | 研发物品 rd_materials | automation/runs/type-template-15426075122-20261023-194729、15426094566-20261023-194720、15426104120-20261023-194712（3 份实测=11） |
| "15" | 快递 express | automation/runs/type-template-15426082926-20261023-194703、15426083536-20261023-194654（2 份实测=15） |
| **"02"** | **低值易耗品、办公用品采购** | **本 run raw_15426101596_dijiazhi.json main.submitType** |

> 2026-10-24 勘误（ENHANCED_FINAL P1-b）：初版第 6 节误将 15426094566 目录引为 15 的证据（该目录实测 submitType=11）；15 的正确证据为 15426082926 与 15426083536 两份，已订正。

辅证：reimItem "02001" 前缀与 submitType "02" 同源（单样本，不作通则）；payType "02"=转账为另一独立编码字段。

## 样本与缺口声明

单样本研究（同类历史单未逐一抽取，raw fetch 预算 ≤5 已用 2）；编辑器联动（类别→费用项→预算）未观察（合同零导航零点击约束）；reimItem/budget 枚举来源未捕获；genreId 语义未知。以上不阻塞只读结论，均为接入施工前必须补的证据。
