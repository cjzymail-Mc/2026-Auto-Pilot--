# 快递费与研发材料费 runbook 收尾结果

日期：2026-10-27。已按[轻量施工计划](2026-10-27%20快递费与研发材料费runbook轻量收尾施工计划.md)完成 C01—C06，结论限于限定范围文档收尾。9 项文档测试及独立合成情景走读通过；本次无真实 OA 操作。

## 修改与范围

- [快递费手册](../.claude/skills/bpm-fill-run/references/express.md)：补齐适用/排除条件、材料、字段来源表、费用说明两条路径、主要票据层、多明细/多收款对账、正式命令、独立回读与停点；修正模板人员与当前操作人混用。
- [研发材料费手册](../.claude/skills/bpm-fill-run/references/rd-materials.md)：补齐采购/完整编号/当前档案对应、五表字段来源、行金额与票据分配、税费冲突处理、精确选档知识与异常停点。
- [入口与未来扩展说明](../.claude/skills/bpm-fill-run/入口与未来扩展说明.md)：登记两份限定范围 runbook，保留原自驾条目；[统一入口](../.claude/skills/bpm-fill-run/SKILL.md)原路由已可用，未修改。
- 计划中的 `feature02/` 是不存在的简写目录；本记录落在计划实际所在的 `feature02-扩展更多单据类型/`，STATE 计划/结果链接按真实路径更新，不另建重复目录或修改原计划。
- 本包仅离线文档维护，不登录/访问 OA，不读取认证目录或个人会话元数据，不生成业务计划/manifest，不填写、保存或提交，不启动旧自驾 workflow 或其他类别施工。

## 证据层次

| 层次 | 本次核对结论与直接入口 |
|---|---|
| 快递历史真实回放 | [结果](../automation/runs/20261024-173807-72170651/attempt_001/stage1_result.json)：`SUCCESS_FILL_ONLY / NOT_ATTEMPTED`；[独立回读](../automation/runs/20261024-173807-72170651/attempt_001/evidence/independent_verification.json)：`ok=true / issues=[]`，明细 1、费用 8、银行 4，分别与总额闭合 |
| 研发历史真实回放 | [结果](../automation/runs/20261024-174803-cd2e04e4/attempt_001/stage1_result.json)：`SUCCESS_FILL_ONLY / NOT_ATTEMPTED`；[独立回读](../automation/runs/20261024-174803-cd2e04e4/attempt_001/evidence/independent_verification.json)：`ok=true / issues=[]`，档案 18、明细 4、银行 4，分别与总额闭合 |
| 当前文档验证 | 下方文档测试、人工式字段/源码阅读核对及独立合成情景走读；不新增真实填写证据 |
| 新业务与真实保存 | 本次未执行；具体任务另用当次原件验证身份、选择器、字段和独立回读。保存/唯一新身份/未提交/重开持久化按公共入口另取证 |

旧证据、原始哈希与历史路径保持原样；样本行数不是未来固定值。类型配置中的 pending 标签不在本包修改，也不据此抹去历史回放或推断新业务已验收。

## 离线检查

在仓库根执行一次：

```powershell
python -X utf8 -m unittest discover -s tests -p "test_skill_docs.py" -v
```

实际输出摘要：`Ran 9 tests in 0.047s`、`OK`，exit=0。覆盖入口 frontmatter、路由/引用、现有脚本旗标、六阶段 API 及公共红线。未增加措辞测试，未跑全量构建或真实浏览器测试。

现有测试不覆盖两份手册全文，因此另由主施工者阅读核对：

- 对照两类配置 `header/tables`、`bpm/plan.py` 的空表/行结构/金额/来源校验，检查表内全部实际字段和带出值；express 四表，研发另有 products。
- 对照 `bpm/materials.py:validate_image_documents` 与 `bpm/plan_generate.py:_primary_table`：快递 costs 非空且 sum 时主要层为 costs，否则 details；研发显式指定 products，金额字段 price。
- 对照 `bpm/ui.py:_fill_product` 及 `_header_generated_default_bank`：完整编号选档、带出字段回读、新页自动空银行行的受限接受条件未被手册放宽。
- 对照 `bpm/fill_cli.py`、`bpm/template.py`：手册引用的 CLI、`--lookup-list`、`--observe-view` 与其他参数真实存在；不把库函数或测试脚本虚构成新业务入口。
- 相对链接按实际目录逐一解析；修改范围、最终哈希及只读工件完整性见下文。

## 最终范围与完整性

本包实际修改两份手册、登记说明、STATE，并新增本结果记录，共 5 份文档；统一入口原路由与公共红线保持原字节。STATE 已替换待施工结论并保留自驾暂停、恢复入口及业务待验边界。

施工前后对 136 个只读文件进行字节 SHA256 比较，零变化、零新增：覆盖 `bpm/`、`tools/`、`tests/`（排除缓存）、schema、类型配置、两份历史 run 的既有工件、AGENTS、统一入口、自驾手册、原施工计划，以及用户已有的类型盘点和临时文件。此比较仅证明所列范围的完整性；没有读取认证目录或个人会话元数据。

最终检查覆盖统一入口、两份手册、登记、STATE 和本结果共 6 个文件，75 处本地链接全部可解析；独立走读记录的 7 份文档字节数及 SHA256 与交付文件全部一致，后续未改受审手册。Git 差异范围符合本包 5 份文档，用户已有未提交文件保留原样；STATE 为 40 行。

## 独立情景走读

<!-- INDEPENDENT_WALKTHROUGH_START -->
**独立离线情景走读（2026-10-27）**

走读者未参与本包施工，先独立完成四例判断，之后才打开本结果文件的分配区定位写入；未读取其余章节结论。输入仅为下列七份文档及本次匿名合成题面，未读 STATE、施工计划、旧答案、历史业务证据、测试、业务代码或受保护会话目录；没有访问 OA/浏览器、运行业务 CLI、生成业务计划或 manifest。以下定位、人员、模板、金额及材料观察均是场景假定，不能当作真实执行证据。

共用入口为 [SKILL.md 的“模板与场景路由”“日常入口”](../.claude/skills/bpm-fill-run/SKILL.md#模板与场景路由)：按本次完整模板号核实表单与类别，再加载专册；不让用户选择内部类型或编写内部 JSON。本题已假定模板、身份与公共表头依据齐备，因此不重复制造这些材料缺口。真实业务仍需重新探查身份、锁、registry 和页面，再定向核实模板；本次仅沿既有材料定位分析，不能将合成观察编译为真实事实或宣称 `PLAN_VALIDATED` / `EXECUTION_READY`。

**E1：文档支持继续归集、对账；明确只填不存。**

- 入口/类型：经共用模板假定走 `express / 快递费 / 15`，进入 [快递手册“材料与适用判断”](../.claude/skills/bpm-fill-run/references/express.md#材料与适用判断)。无关联、无物品档案，符合普通全额范围；express 不增加 products 表或 products 空表理由。
- 字段与金额：Sheet1 第 2/3 行分别支持费用项目、起止日期、地点、次数、行总额、项目说明；按各自现有字段定位绑定来源，不虚构列号。次数 2/1 是有源正数，60.00/40.00 已是行总额，不再次相乘。同预算项目归为一条明细 100.00；收款名单第 2/3 行支持甲 60.00、乙 40.00，并保留“费用行→明细分组→收款人”的对应记录。Decimal 核算为 Σcosts=60.00+40.00=Σdetails=100.00=Σbanks=60.00+40.00=totalCost；三个层次不相加。
- 票据与空表：费用说明非空，`amount_rules.costs="sum"`、`cost_amount_semantics="line_total"`。发票 A 的主要分配层为 `/tables/costs/0/fields/cost` 60.00 与 `/tables/costs/1/fields/cost` 40.00，逐票 100.00、逐行全覆盖；不再分到汇总明细。`relations=[]` 及其 `table_applicability` 理由取本次“无关联”说明。原件、复核 JSON、分类、票据身份去重及字节哈希的真实绑定仍须在后续实际材料处理中完成。
- 缺口/下一步：题面范围内未见业务材料或规则缺口；不将未展示的真实原件/哈希当作已经核验。合适下一步是完成有源归集、复核和对账，再在另行真实任务中按正式顺序生成、验证计划；验证通过且实际身份/选项等门禁通过才填写并独立 DOM 全值回读，保持 `fill_only`。依据：[快递手册“字段来源与映射”“核算与空表规则”“正式操作顺序与停点”](../.claude/skills/bpm-fill-run/references/express.md#字段来源与映射)，[公共契约“输入与准备”“PDF/图片分类与发票金额核对”](../.claude/skills/bpm-fill-run/references/plan-contract.md#pdf图片分类与发票金额核对)。

**E2：停止于材料冲突/不支持范围；空费用说明不是阻断原因。**

- 入口/类型：按共用假定仍是快递费，使用同一专册；本次有源“不适用”允许 `costs=[]`，有源“无关联”允许 `relations=[]`，各自登记空表理由。`amount_rules.costs="not_applicable"` 并有非空 `costs_reason`；费用金额语义仍为 `line_total`。主要票据层因此是 `/tables/details/0/fields/cost`，不是空 costs，也不创建虚拟费用行。
- 字段与金额：结算与该明细均为 100.00，付款为 100.00，表间本可闭合；但唯一复核票面为 120.00。分配 100.00 会少覆盖票面 20.00，分配 120.00 又超过该主要行的 100.00，两条全额等式无法同时成立。
- 缺口/下一步：用户“余 20.00 忽略”属于部分票面报销，专册明确排除；不能改票面、增加无来源费用、把该票排除后改填免票，或任选结算数据消除冲突。应集中报告结算行、明细及该发票受影响的金额/定位，停在 `NEEDS_INPUT`，保留后续提供一致有效材料或另行评估新模型的缺口。本题“不补其他票”不会使现有冲突变为可执行，不生成可执行真实计划或继续填写。依据：[快递手册“材料与适用判断”第 4 项及“核算与空表规则”第 2/4 项](../.claude/skills/bpm-fill-run/references/express.md#核算与空表规则)，[公共契约票据分配与全额覆盖规则](../.claude/skills/bpm-fill-run/references/plan-contract.md#pdf图片分类与发票金额核对)。
- 定位推演：若只将题面发票改为恰好 100.00，其余条件不变，票据可全额分配至该 details 行 100.00，Σdetails=Σbanks=totalCost=100.00；空 costs 与空 relations 均有各自本次理由，文档允许继续归集/验证路线。仍须真实来源绑定及当次空表、独立回读验收，不能据此宣称该分支已真实填写通过。这说明本例停点在票面冲突/部分报销，而非费用说明为空。

**R1：文档支持继续归集、对账；明确只填不存。**

- 入口/类型：经共用模板假定走 `rd_materials / 研发材料费 / 11`，进入 [研发手册“材料与适用判断”](../.claude/skills/bpm-fill-run/references/rd-materials.md#材料与适用判断)。现有完整档案号唯一、price 为明确行总额、无关联且无需独立费用说明，属于限定支持范围。
- 字段与金额：采购第 2/3 行及本次档案核对记录共同绑定字符串编号 `000101` / `000102`，保留前导零；核对名称物料甲/乙、购买人采购甲/乙、价格 80.00/120.00。备注分别取本次来源“批次甲”和精确空字符串，空字符串也保留字段及来源，不因空值省略。购买人、当前人员和供应商收款人分别取证；付款使用本次供应商丙凭据。两档案按同一预算归为明细 200.00，供应商付款 200.00，Σproducts.price=80.00+120.00=Σdetails.cost=Σbanks.cost=totalCost=200.00，不做数量计价或叠加各层。
- 票据与空表：`amount_rules.products="sum"`、`product_amount_semantics="line_total"`；costs 为 `not_applicable`，保留非空理由及 `cost_amount_semantics="line_total"`。`table_applicability` 空表键恰为 relations/costs，理由分别绑定本次“无关联”“无需独立费用说明”。发票 200.00 分配至 `/tables/products/0/fields/price` 80.00 和 `/tables/products/1/fields/price` 120.00；即使 costs 为空也不回退到 details，逐票与逐档案行均全覆盖。
- 缺口/下一步：题面范围内未见实质材料或支持规则缺口；真实原件、复核及哈希绑定仍待实际材料阶段核验。完成有源归集、逐行采购/档案/预算/供应商对账后，真实任务才按专册进入计划验证与正式填写：新增物品档案行，双击名称单元格打开选择器，完整编号精确选入现有档案；编号、购买人、价格只读带出并核对，不新建或强写价格。最终核验主表及五表全值/行数、空表真实性、金额和额外/重复/缺失行；本次意图保持 `fill_only`。依据：[研发手册“字段来源与映射”“金额与支持边界”“正式操作顺序与停点”](../.claude/skills/bpm-fill-run/references/rd-materials.md#字段来源与映射)，[公共契约研发档案专段](../.claude/skills/bpm-fill-run/references/plan-contract.md#可执行计划)。

**R2：停止于缺失证据与多个明确不支持请求。**

- 入口/类型：模板假定仍指向研发材料费，不能为绕过边界改成快递或其他类型；但这不等于本次采购适用该专册的可填写范围。
- 字段与核算：名称“物料甲”不足以唯一确认现有档案，缺完整编号、当前档案 name/purchaser/price 等可核对记录及有源行总额。数量 3 与单价 50.00 不能由 agent 相乘填补 OA 档案行金额；150.00 的算术结果不是本模型接受的行金额来源。题面也未给可据以建立 products 主要票据覆盖的本次发票/逐行免票依据，不能由名称或金额代替。
- 缺口/下一步：近似选档、无档案就新建、数量乘单价计价均被专册明确排除；即使共用假定中的账户/联行号完整且支行唯一，也不能把模板员工旧账户当成供应商收款依据，须核对本次凭据的对象与实际付款关系。应一次列出完整现有编号/唯一档案核对、明确行总额、票据或适用免票依据等缺口，以及账户复用冲突和不支持要求，停在 `NEEDS_INPUT`。只有后续材料与请求真正落入现有限定范围才重新判断；不能替用户猜编号、新建档案、改只读价格或移用旧员工账户，也不自动启动新模型施工。依据：[研发手册“材料与适用判断”第 1—4 项、“字段来源与映射”银行行及“金额与支持边界”第 4 项](../.claude/skills/bpm-fill-run/references/rd-materials.md#材料与适用判断)，[统一入口未知/未建模分支停点与历史复用纪律](../.claude/skills/bpm-fill-run/SKILL.md#完整链路模板单号原始资料--执行就绪)。

**文档可操作性判断。**四例均能从统一入口找到准确专册，再从字段映射、主要票据层、空表规则和停点得出合适下一步；未发现妨碍这四例判断的实质性缺失。公共 plan-contract 的票据通用段写“费用说明不适用时指向 details”，不能脱离同文研发专段阅读：研发专段和研发专册均明确 products.price 优先且不回退，R1 的路线因此可唯一确定；这是阅读层级的提醒，不将其判为本次阻断。登记文件明确“手册固化/实现/离线/真实填写/真实保存”分层；[完整链路参考](../.claude/skills/bpm-fill-run/references/full-chain.md#六阶段与调用方式)只到执行就绪，仍须按入口继续正式执行与独立回读，不能把准备返回 `NEEDS_INPUT` 或阶段就绪当成填写交付。

**审阅文档冻结指纹。**下表为本次实际读取的最终文档相对路径及原始文件字节 SHA256（含实际编码与换行，不是解析后逻辑内容哈希）；计算口径依 [evidence-hash-semantics.md“规则”](../.claude/skills/bpm-fill-run/references/evidence-hash-semantics.md#规则今后所有-run-内采集脚本)。未跟随文档中的历史业务证据、配置、代码、STATE 或其他类型手册链接。

| 实际读取文档（相对仓库根） | 字节数 | SHA256_file |
|---|---:|---|
| `.claude/skills/bpm-fill-run/SKILL.md` | 12449 | `cb72bc0951b9e8a7c7cee029bd97adb63c7ff499a74418d777aeac47731a851c` |
| `.claude/skills/bpm-fill-run/references/express.md` | 9872 | `4f547e454c6454d4a729a1d2aac4cc1aeea67d4ad10a553b82c2b5a3d3ec63a2` |
| `.claude/skills/bpm-fill-run/references/rd-materials.md` | 10021 | `a9b26844b4f6bafaf96d646135705b21226749b67d2015eb033727a29e62b336` |
| `.claude/skills/bpm-fill-run/入口与未来扩展说明.md` | 3506 | `d088e11412609f65f98b75a836cd9ed4ddc21db957eac1705808e134163232f7` |
| `.claude/skills/bpm-fill-run/references/plan-contract.md` | 13134 | `733d8d2c2c2643da666fea58fa5bb8cc1ada2967c9b233445b3a5b75ea61b424` |
| `.claude/skills/bpm-fill-run/references/full-chain.md` | 6905 | `bce5a011ac2b50d1a380436ffac752a4464a6e3e149f4e9c48e53e750edd88ca` |
| `.claude/skills/bpm-fill-run/references/evidence-hash-semantics.md` | 1981 | `9fdc31dde0d367c6dc89ebc734134c707f5ff49abae16c91be82c4118a77e2f1` |

本区只证明所列文档版本下的离线材料决策走读：E1/R1 有后续路线，E2/R2 应停止。它不是业务计划校验、真实填写、保存、重开持久化或冷启动验收，不增加任何真实业务成功证据。
<!-- INDEPENDENT_WALKTHROUGH_END -->

## 收尾判据

| ID | 当前结论 |
|---|---|
| C01 | 通过：两份手册具备字段来源、计算语义、正式工具、操作顺序、异常与交付；主施工核对及独立走读无实质缺口 |
| C02 | 通过：普通全额/现有档案行金额边界保留，未支持分支明确停止，未放宽业务校验 |
| C03 | 通过：原统一路由保留，登记已更新，自驾条目保留 |
| C04 | 通过：历史回放、当前文档、新业务待验与保存待验已分开 |
| C05 | 通过：9 项文档检查及独立四例走读通过；无需修订受审手册，合成材料不作为真实执行证据 |
| C06 | 通过：仅 5 份范围内文档发生本包变更，STATE 已同步，136 个只读文件哈希不变；无 OA/业务状态操作 |

## 后续缺口

当前未发现必须修改业务代码才能完成本包限定范围文档的核心规则缺口。未支持分支保留明确停点，不列为自动施工任务。

- 新业务验收：触发为另行启动具体真实报销；现有证据仅为授权历史回放，影响是不能宣称新原件/当前页面已验收；最小后续工作是按当次材料和手册完成真实填写及独立回读，快递费用说明为空分支须当次取证。
- 真实保存验收：两份历史结果均为 `NOT_ATTEMPTED`，影响是不能报告真实保存成功；仅在具体任务的授权及公共门禁成立后，以唯一草稿身份、未提交和重开全值回读取证，不牵引本包施工保存工程。
