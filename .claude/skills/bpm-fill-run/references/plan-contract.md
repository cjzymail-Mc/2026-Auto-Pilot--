# Task 与可执行计划 v1.0

## 输入与准备

Task 是业务请求，不是浏览器可执行数据。`automation/task.schema.json` 要求：schema_version、task_id、document_type、operator、template_biz_number、materials_dir、statement、authorization；可选 template_snapshot_path。相对路径以 task 文件目录为基准。

```json
{
  "schema_version": "1.0",
  "task_id": "travel-本次任务唯一标识",
  "document_type": "travel",
  "operator": "预期操作人",
  "template_biz_number": "完整模板单号数字串",
  "materials_dir": "本次材料目录",
  "statement": "本次实际报销说明",
  "authorization": {
    "mode": "fill_only",
    "task_id": "travel-本次任务唯一标识",
    "statement": "用户对本次任务的实际指令",
    "allow_submit": false
  }
}
```

以上仅为字段说明，模板单号必须替换成真实数字串。明确要求保存时 mode 才能是 `save_draft`，不能从“实现保存功能”推断对某张真实单据的保存授权。

`fill_once.py --task` 生成新 run 的 task.json、材料 manifest、按原件 SHA256 命名的 parsed 输出及 preparation_result.json，状态 `NEEDS_INPUT`。原件只读；输出目录与原件目录分开。相同内容合并为一个 material_id，重复文件另列 duplicate_paths，不按文件名生成费用行。

CSV 按字符串读取，定位 `row:2/column:1`（从 1 起）。XLSX 定位 `Sheet!A1`，文本账号保留原样；明确零掩码可保留前导零。普通数值只可按已知金额/数量语义使用，标识符精度不可靠或公式未复核时不得执行。

PDF/图片的 Python 准备器返回缺口；由当前环境可用的本地文档/视觉工具提取并复核。**电子发票 PDF 优先机读内嵌文本层**（确定性解析，逐位票号/金额），视觉读取仅交叉验证或无文本层时主通道；票号级事实建议"机读+汇总单(票据)视图互证"双通道裁决（实测单次视觉读数会出现连续票号幻觉）。单独 JSON 的结构为：schema_version="1.0"、reviewed=true、reviewed_by、original_path、original_sha256、records；每条 record 有唯一字符串 record_id、fields；每个字段有字符串 value 和原件页码/区域 locator。文件与原件哈希绑定，计划指向该 JSON 中 `/records/0/fields/字段名/value`；原件与复核 JSON 都应纳入材料清单。关键值不清晰则保留缺口，不猜账号、发票号或金额。

## 可执行计划

完整形状见 `automation/fill-plan.schema.json`，业务校验为 `bpm.plan.load_plan` / `validate_plan`。结构与业务约束必须同时通过。

| 键 | 含义 |
|---|---|
| schema_version / config_version | 当前均为字符串 "1.0" |
| task_id / document_type / operator | 唯一任务、travel/express/rd_materials、预期操作人；新类型真实验收状态单独报告 |
| applicant | name、company、department；与页面独立核对，**每个值均纳入 sources**（身份类值不允许无来源执行） |
| identity（可选） | applicant_employee_id、creator_name、creator_department；每个值均纳入 sources。初始选申请人并核对完整组织，之后锁定人员；从不写制单人 |
| test_context（可选） | purpose、round、authorization_path、authorization_sha256；具体测试授权文件哈希必须吻合，强制 fill_only，并使用独立临时 context |
| template | biz_number、captured_at、snapshot_path、sha256；编号/时间与快照内容一致 |
| materials | manifest_path、manifest_sha256；PDF/图片需 image_documents 分类及票据核对；无票行可声明 no_invoice_rows |
| header | corpCode、bizOrign、budgetYears、payType、currencyType、submitType、description、totalCost；corpCode 等码类字段须填**当前页面显示名**而非 API 原码，并与 applicant.company 一致（见 travel.md） |
| tables | travel/express 为 relations、details、costs、banks；rd_materials 另有 products，均为 `{row_id, fields}` 行数组 |
| sources | 每个申请人/表头/表格执行值的 JSON pointer → 来源证明 |
| authorization | mode、task_id、statement、allow_submit=false |
| unresolved / not_applicable | 可执行时 unresolved 必须为空；不适用项及理由明确记录 |
| amount_rules | costs=sum/not_applicable；cost_amount_semantics=line_total/unit_price_times_count；空费用表需 costs_reason |

新类型每张空表必须在 `table_applicability` 中登记 `{表键:{"reason":"本次不适用原因"}}`，键集合与实际空表完全一致；每条 reason 通过 `/table_applicability/表键/reason` 纳入 sources，不能以历史模板为当次不适用依据。新类型只接受 `line_total`；目前非空 relations 均未建模。

研发物品档案范围要求 products 至少一行，costs 为空；products 字段精确为 code（数字字符串）、name、purchaser、price（金额字符串）、description（允许精确空字符串）。普通新业务的编号、购买人及费用事实不得取旧单。用户明确授权的历史回放测试须另存带历史源/授权哈希的 test-only 事实材料，备注明确不保存，test_context 强制 fill_only；不能将其当新费用或保存授权。`amount_rules` 增加 `products="sum"`、`product_amount_semantics="line_total"`；产品价格合计与表头/报销明细/银行各自闭合，不能把各层相加重复计费。发票及免票指针使用 `/tables/products/行号/fields/price`，不再分配到 details.cost。数量/单价乘数量及部分票面报销仍拒绝。

来源 kind 为 `material`、`template`、`user` 时，必须有 path、locator、sha256，文件内容及定位值均须吻合。JSON locator 用 JSON pointer；CSV/XLSX 见上。相对证明路径以计划文件目录为基准，不以 run 快照目录为基准。当前值不能仅写“来自 OCR”或“用户已确认”而缺文件/定位证明。

`manifest.root` 必须解析为存在且非保护路径的材料目录。每个主文件 path 均须处于该 root，relative_path 与目录内实际相对路径精确一致；重复文件也须为规范目录内相对路径，禁止绝对路径、`..`、路径不一致及符号链接逃逸。不能只拿任意文件的哈希冒充本次材料。

同一值有 Excel、发票或用户声明等多份依据时，用该 source 的 `corroborates` 数组登记其他 `{path,locator,sha256}` 证明（可带 kind=user/material）。定位值逐一按字符串或 Decimal 比较，冲突阻断，不任选一个来源。

`derived` 目前只支持 `operation=sum`、`inputs=[其他计划金额 pointer]` 的精确和；不支持重复输入或推导链。日期、费用、关联编号及发票等本次事实不可从历史 template 来源取得。收款账号、编号始终字符串精确匹配；浮点、科学计数、额外金额字段与未建模借款抵扣不被接受。

报销明细 digest 是本次费用摘要，必须使用当次 `material` 或 `user` 主证据；历史 template 不能作为主来源，即使追加 corroborates 也不豁免。稳定费用项目/预算名称与本次摘要分别取证。

配置把 API 属性映射到实际中文标题、标签及编辑类型，不采用默认猜测。`plan_hash` 是排序规范 JSON 的 SHA256；run 的 task_binding.json 绑定 task、operator、plan_sha256 和执行配置 config_sha256。保存控制器还在点击前及持久化复核期间检查配置未漂移。修改计划、材料或配置后重新校验，不复用旧验收结论。

不同申请人必须补齐完整 identity 才能选择；空白新页以姓名及完整工号唯一选中，再核对公司、部门及制单人未变。费用填写后不改人员。test_context 不是保存授权；显式 null、未知字段、不完整身份及授权哈希漂移均拒绝。测试轮分别登记目的与源码/计划/配置哈希，不能借换测试身份规避既有填写或保存意图。

执行只缓存阶段内的表/列结构，增行、选择器关闭和阶段切换后失效；结构顺序或标题变化会重新测绘，元素和值不跨重建缓存。最终完整 DOM 回读始终新采集。events.jsonl 中 UI_START → READBACK_END 是页面执行窗口；browser_session_start、entry_plan_validation_binding 和保存另报。tools/diagnostics/perf.py 按区间并集计算，未覆盖时间不归因于模型；未自动测量的全局模型调用及外部诊断次数明确留空。

## PDF/图片分类与发票金额核对

清单中每个唯一 PDF/图片原件 SHA256 都必须在 `materials.image_documents` 恰好出现一次。未分类文件视为可能发票，返回缺口；文件名不能替代分类证据。

- `kind=not_invoice`：字段为 original_sha256、kind、reason、proof。proof 是定位到 reason 原文的 `{path,locator,sha256}`；例如用户明确说明某张图片只是行程附件。不能凭视觉猜测省略分类记录。
- `kind=invoice`：字段为 original_sha256、kind、extraction_path、extraction_sha256、records。原件和复核 extraction JSON 必须同在 manifest，extraction 中 original_sha256 必须与该原件一致。复核 JSON 的每条 record 都需唯一字符串 invoice_number，可选 invoice_code，以及 amount 或 total_amount；本契约中二者均指价税合计/应付总额，两个同时存在必须一致。税前金额另记 net_amount、税额另记 tax_amount，不可把税前 amount 与含税 total_amount 混用或静默任选一个；口径不明确就返回缺口。每个字段有原件页码/区域 locator。跨不同扫描文件出现相同 invoice_code+invoice_number 会被拒绝，字节不同不代表不同发票。
- 每条 invoice records 引用复核 JSON 的 record_id，并填写 allocations，或填写 source-backed not_applicable（reason、proof）。不得同时分配并排除。

分配只针对一套主要费用：costs 非空且声明 sum 时指向 costs；费用说明明确 not_applicable 时指向 details。不能同时分配 summary 和费用行重复计票。例如：

```json
{
  "original_sha256": "原件SHA256",
  "kind": "invoice",
  "extraction_path": "reviewed-invoice.json",
  "extraction_sha256": "复核JSON的SHA256",
  "records": [{
    "record_id": "invoice-0001",
    "allocations": [{"plan_pointer": "/tables/costs/0/fields/cost", "amount": "20.00"}]
  }]
}
```

每张发票分配之和等于复核票面金额；每个被分配的计划费用行，其来自全部发票的分配之和也必须等于该行计划金额，因此 Excel 20 元与发票 21 元无法通过。当前不支持部分报销票面金额、按单价乘数量的票据分配；遇到这些口径返回不支持，不套用合计规则。

只要存在主要费用行，每行都必须有票据分配，或出现在 `materials.no_invoice_rows`：每项包含 plan_pointer、reason、proof，明确本次该行无需发票的规则与来源。零 PDF/图片也执行相同覆盖校验；仅有 Excel、CSV 或用户金额事实不能替代免票依据。补贴不按历史名称自动认定免票。离线合成夹具也须明确记录“仅用于合成测试、不适用于生产”的免票规则和来源，不隐式放宽生产边界。

## 执行、保存和状态

`--validate-only` 离线通过后，普通执行新建独立 run。可用 `--run` 指定新标识；重试用 `--resume-run`，不得混用。`--legacy-regression` 只允许显式旧格式计划的只填不存回归，不能用于 canonical 计划或保存。

`automation/task-registry/` 按 task_id 哈希记录填写/保存意图，跨 run 保留。重复任务不自动再建单。已写 `SAVE_INTENT`、`SAVE_UNCERTAIN` 或已保存时只核实唯一身份、重新打开及回读，不第二次保存。未保存页面当前只盘点并返回 `NEEDS_INPUT`；无法自动恢复时给出原页与工件位置，不自行重建。

保存控制器要求本任务 save_draft、无未决缺口、完整独立回读、金额闭合、终局截图和点击前再次复核；仅可见、可用且唯一的精确“保存”按钮。未知对话框不自动确认。保存结果需唯一新单号与 UUID、未提交状态、重开后完整回读及截图，toast/HTTP 200 不能单独作为成功证据。

| 终局状态 | 对用户的解释 |
|---|---|
| SUCCESS_FILL_ONLY | 已填完并独立核对；未保存 |
| SUCCESS_DRAFT_SAVED | 草稿身份唯一、未提交，重开持久化回读通过 |
| NEEDS_INPUT | 缺材料/来源/唯一选项、支持边界或安全恢复所需信息 |
| READBACK_MISMATCH | 实际页面与计划不同，报告差异与截图 |
| SAVE_UNCERTAIN | 可能已保存；仅只读核实，不重试保存/建单 |
| WAIT_HUMAN_LOGIN | 等待企微人工扫码，保留现有工件 |

交付引用 `automation/runs/<run>/events.jsonl`、`attempt_NNN/stage1_result.json` 与 evidence，保存控制器证据也位于该 attempt。材料准备结果在 run 根。区分“已实现/离线通过”与“已真实填写/真实保存”；实单输入缺失时明确列缺口，不把合成测试当成实单验收。


## 自驾新规则的来源与计划绑定

V3历史R=M+T模型不改。新模型使用可选 `self_drive_coverage`，由现有plan_generate生成并在validate_plan/load_plan独立重读来源、规则哈希、餐补参与日和逐组件/逐单金额；不能同时声明旧coverage。正式离线命令、来源包及限定支持结构见 [self-drive-inputs.md](self-drive-inputs.md)。通行票完整分配、油票覆盖不入费用、公里/餐补的有源政策免票保持分离；无真实输入时只到离线阶段，不填不存。
