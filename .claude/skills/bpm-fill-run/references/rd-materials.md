# 研发材料费 runbook：现有物品档案与行金额

适用于真实模板确认为 `rd_materials / 研发材料费 / 11`，本次材料可精确对应现有物品档案、`price` 为档案行金额且关联/费用说明均为空的任务。配置为 [rd_materials.json](../../../../automation/document-types/rd_materials.json)。这一路径不代表所有采购或研发业务都支持。

公共身份、登录、锁、registry、恢复及同任务保存授权按 [统一入口](../SKILL.md)；来源与计划形状按 [plan-contract.md](plan-contract.md)，现有上层编排见 [full-chain.md](full-chain.md)。纯离线整理不调用线上入口。下列线上步骤仅用于另行获授权的具体业务，本次手册收尾不执行。

## 材料与适用判断

- 业务执行需要本次完整模板单号、采购材料/统计与报销范围、发票或逐行免票依据、完整现有档案编号及其对应关系、预算与收款依据。材料应能解释每条档案金额，不从历史模板借用档案或费用。
- 本次采购/统计逐行对应“完整编号→当前档案→票据/免票依据→报销明细→收款对象”。编号缺失、仅有相似名称、同号匹配不唯一或金额冲突时列缺口；不近似匹配、不取第一项。
- 操作人取当次真实认证，申请人/制单人取当前新页观测。购买人是物品档案字段，收款人是付款对象，均不因当前登录人而自动改写。区分供应商与员工收款，不把模板个人账户默认用于供应商。
- 本版要求 `products` 至少一行，`relations=[]`、`costs=[]`。无物品档案、新建档案、非空关联/费用说明、数量乘单价或数量票据分配、部分票面报销、借款抵扣及附件/贴票/上传/提交均不在本范围。

## 字段来源与映射

每个执行值按公共契约绑定 `path / locator / sha256`，保留采购行/单元格、复核 JSON pointer 和原件页/区域；当前档案核对记录也需本次可定位来源。模板仅提供经核实的稳定参考，不能作为本次档案编号、购买人和费用的来源。

| OA 字段或字段组 | 本次来源及定位 | 变换/计算 | 核验与缺项处理 |
|---|---|---|---|
| 人员与公司：`applicant`、`identity`、`header.corpCode` | 当次身份依据、当前新页人员/组织观测及必要代办依据 | 当前显示名，人员角色分别记录 | 人员/工号/组织按统一入口核实，不从模板改人；来源冲突停写 |
| 主表：`bizOrign / budgetYears / payType / currencyType / submitType / description` | 当前页面选项、本次采购说明/预算/付款要求的定位 | 类别精确为“研发材料费”；年度、币种、方式及非空备注按本次事实 | API 原码不作显示名，旧年度不默认沿用；缺依据报缺口 |
| 主金额：`totalCost` | 本次确认的档案行金额及采购对账记录 | Decimal 求和，核对页面计算值 | 正金额；档案、明细、银行各自闭合，不叠加各层 |
| 物品档案：`products.code / name / purchaser / price / description` | 本次采购/统计行的完整编号及当前档案核对记录；备注取本次材料 | 完整数字编号保持字符串/前导零；`price` 是行金额，`description` 可精确为空但仍须来源 | 唯一选中后核对编号、名称、购买人、价格、备注；只读带出值不伪造，空备注不表示可省略字段 |
| 报销明细：`reimItem / digest / budgetNo / subjectName / cost` | 本次采购分组/摘要、预算和对应档案行金额定位 | 按真实项目/预算归组，先预算单后科目；多品类预算逐行选择 | 项目/预算精确匹配，摘要取本次来源；分组与档案对应，合计等于主金额 |
| 明细带出：`budgetDeptName / budgetItemName / budgetOwner` | 当前预算选择后的带出值与本次预算依据 | 只读回显，不直接写入 | 独立核对部门/项目/归属，带出不符即停写 |
| 空关联、空费用说明：`relations / costs` | 本次“无关联、无需独立费用说明”的范围依据及定位 | 两表为空，各有 `table_applicability` reason；费用规则同时声明不适用 | 两个理由分别有源，不能用旧单空表证明；不能把未识别费用藏进空表 |
| 银行：`payee / account / bank / bankCode / cost` | 本次供应商/员工收款凭据、完整账户/联行号及分配金额定位 | 标识符保留前导零，按真实付款对象分组；开户行带出核对 | 收款人与采购付款关系对账、银行合计闭合；不能用员工旧账户替代供应商 |
| 发票及免票覆盖（计划材料层） | 本次发票原件/复核 JSON、采购与档案对应记录、适用免票依据 | 仅分配到 `/tables/products/行号/fields/price` | 每票全额、每档案行全覆盖；跨材料互证不一致或来源不明时阻断 |

## 金额与支持边界

1. `amount_rules.products="sum"`、`product_amount_semantics="line_total"`；费用说明为空仍需 `costs="not_applicable"`、非空 `costs_reason`、`cost_amount_semantics="line_total"`。`table_applicability` 的空表键恰为 relations/costs，每条 reason 均纳入 sources。
2. Σproducts.price = Σdetails.cost = Σbanks.cost = totalCost。多档案可按采购/预算归为多明细、多收款人，须留下逐行对应与分组对账；三个层次是同一金额，不能相加。
3. 票据分配主要层始终是 products.price，即使 costs 为空也不回退到 details.cost。每票分配和等于复核票面总额，每档案行的全部分配和等于该行金额；无票行需 `materials.no_invoice_rows` 的 reason/proof。原件与复核 JSON 同入 manifest，票据身份去重，不以免票绕过冲突。
4. 采购材料上有数量、单价，不代表 OA price 是单价。仅当证据明确给出与现有档案一致的行总额、执行与票据覆盖均不依赖未建模的数量分配时，才能按本范围处理；不能自行做乘法来填缺失行金额。要求数量×单价计算/数量票据分配时停为不支持。
5. 含税/未税、税额、折扣、运费及尾差按本次凭据解释；票面 amount/total_amount 的口径遵守公共契约，不默认税率、容差或把附加金额加到档案价格。若不能与现有档案行金额精确对应，保留冲突与受影响行，不改只读价格凑平。

## 正式操作顺序与停点

1. 区分离线整理与线上执行；线上先按统一入口运行 `python -X utf8 bpm_login.py`，再用 `bpm_template.py --live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"` 定向核实模板（运行时同样使用 `python -X utf8`）。只接受本类别及本次适用结构。
2. agent 用 `python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"` 准备材料；返回 `NEEDS_INPUT` 后继续完成采购/档案编号对应、发票提取与独立复核、金额对账和来源绑定。无完整编号或档案字段不齐时先报缺口，不生成可执行真实计划。
3. 生成包含五张表的 v1.0 计划（四张基础表外增加 products），核对各档案全部字段、空表理由、预算/付款对象、主要票据层与哈希。运行 `python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only`；通过后按具体任务意图运行 `python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45`。
4. 正式执行器在“物品档案”点“新增”生成行，**双击名称单元格打开选择器→以完整编号精确选入现有档案**。工具栏“插入”只是行插入，不是档案选择入口。编号、购买人、价格只读带出；名称为选档入口，备注可编辑。核对 code/name/purchaser/price/description 后继续，不用普通输入伪造带出值，不创建档案。
5. 按本次计划连续完成明细、逐行预算及银行等适用字段；增行/选档后重新定位。独立 DOM 回读当前身份、类别联动、全部主表和五表全值/行数，核对档案与预算带出值、金额及额外/重复/缺失档案。空表必须真实存在且读取完整；不能把隐藏/未加载当空。
6. 档案无唯一匹配、只读价格/购买人与证据冲突、预算/账户不唯一或未支持结构时停止并报告 `NEEDS_INPUT`；实际页面差异留 `READBACK_MISMATCH` 证据。不改编号、档案或金额来绕过。保存/重开、未保存页恢复、系统生成空银行行按统一入口及正式执行器保护处理，不另建类型专用策略。

## 验证层次与交付

- **历史真实回放已证实**：[stage1_result.json](../../../../automation/runs/20261024-174803-cd2e04e4/attempt_001/stage1_result.json) 为 `SUCCESS_FILL_ONLY`、`save_status=NOT_ATTEMPTED`；[独立回读](../../../../automation/runs/20261024-174803-cd2e04e4/attempt_001/evidence/independent_verification.json) 为 `ok=true / issues=[]`，18 条档案、4 条明细、4 条银行，档案/明细/银行与主金额分别闭合。这是授权历史回放，不证明本次采购原件、所有分支或真实保存已验收，行数不是固定值。
- **本次文档收尾**：仅验证手册、链接、命令与决策可操作性；配置 pending 状态不因本文改变，已验证范围以直接证据为准。
- **后续新业务**：用当次采购/票据和现有完整编号验证身份、选择器、实际档案选入、价格与各表独立回读。真实保存、唯一新单号/UUID、未提交及重开持久化按公共入口另取证，不牵引本包实施保存工程。其他材料结构先另行建模与验收。

交付引用当次 `events.jsonl`、`attempt_NNN/stage1_result.json`、独立回读及截图，区分档案选择/填写结果与保存结果；缺口注明来源定位及受影响档案行，不把历史 G1—G7/G9 或本次文档走读冒充新业务验收。
