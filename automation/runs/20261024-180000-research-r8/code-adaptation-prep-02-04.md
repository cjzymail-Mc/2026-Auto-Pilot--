# 代码适配准备工件：02 低值办公 / 04 福利劳保 接入落点映射（round-8，不实施）

- 输入：round-7 两份六节研究工件能力清单（research_dijiazhi_15426101596.md §5、research_fulilabao_15426071883.md §5，含 P1-b 勘误后版本 sha a1d88975…/08cb1027…）+ round-8 新增 01/24 研究的共用能力互证。
- 性质：**改造点清单与落点映射，零注册零启用零实施**。实施需后续轮次合同显式授权（bpm_types 封闭注册表新增属合同外新文件/新注册，须先停-增补-再写）。

## A. 落点映射总表（能力缺口 → 现有模块改造点）

| # | 能力缺口（02/04 清单原文摘要） | 现有落点（文件/函数） | 改造点 | 证据依据 |
|---|---|---|---|---|
| 1 | 类别码注册 "02"/"04" + 类型自发现映射 | `bpm_types.py` 封闭注册表（resolve_type/TYPE_REGISTRY）+ submittype_map（census 142146 实测 02/04 码） | 新增两个注册项（document_type 名、config 路径、sha 绑定）；自发现映射加 02/04 行 | 两研究件 §6 类型码实测；submitType 与 document_type 名映射表已存在于 census 证据 |
| 2 | 类型配置文件（表列/编辑器/能力面） | `automation/document-types/`（travel/express/rd_materials 三件为模板形状） | 新建 `office_supplies.json`/`welfare_labor.json`：tables=details/costs/relations/banks（products 不列即不支持）；details 列含预算族（02 全预算形；04 同）；costs 列复用 travel 七列（cost/count/endDate/project/projectPlace/reason/startDate）；capabilities 按 02/04 实测能力列举；unsupported 列已知不支持面 | 02/04 研究件 §2 子表字段清单；travel.json/express.json 配置形状 |
| 3 | reimItem 类别内枚举（02001…/04003…） | `automation/document-types/<新>.json`（编辑类型/枚举列）+ bpm_ui 选择器 | 编辑页 reimItem picker 枚举未捕获（两件均列缺口）→ 配置中列 required_observations，不猜枚举；首接轮需真实编辑页观察补 | 两研究件 §5 第 2 条缺口声明 |
| 4 | 预算维度选择器三级联动 + budgetUseCost 闭合 | `bpm_ui.py` details 写入路径（现 reimItem/budgetNo/subjectName 已有 order+picker 逻辑，travel 实测）+ `bpm_plan.py` 金额校验 | 复用现有 details picker 顺序；新增 budgetUseCost 与 cost 的闭合校验规则（02 样本 budgetUseCost=cost=9974.76） | travel details order 注释（bpm_ui._fill_arrays）；02 研究件 §2 |
| 5 | 文档级 invoice=false 免票语义通道 | `automation/fill-plan.schema.json` + `bpm_plan.py` validate_plan + `bpm_verify.py` | 计划层新增文档级 invoice 布尔（区别行级 materials.no_invoice_rows）；validate 规则：invoice=false 时行级发票分配拒绝、免票语义落文档级；verify 对应快照键 | 02/04/01/24 四类 main.invoice=false 实测；travel 行级机制对照 |
| 6 | costs 行日期区间校验 + count 整数语义 | `bpm_plan.py` 现有 costs 校验（travel 已用同列形） | 复用；仅加 start≤end 与 count≥1 整数断言（若无） | 02 costs startDate/endDate/count=90 实测；travel costs 同列形 |
| 7 | detailrels 非空关联支持（申请书 34） | `bpm_ui.py` extra_table_projections.detailrels（现仅 travel 注册 supported_relation_types=["公出单"]）+ relations picker | 02/04（及 01/24 互证） relations=申请书 bizType=34；注册 34 进 supported_relation_types；picker 候选按 bizType 过滤 | 四类研究件 relations 行实测 bizType=34 |
| 8 | 04 跨部门预算（按预算主体查询）+ 空 costs 理由枚举 | `automation/document-types/welfare_labor.json`（required_observations）+ table_applicability 理由机制（rd 已有） | 预算选择器数据源半径为观察缺口（不猜）；costs 空理由复用 rd costs_reason 机制，新增枚举值由配置承载 | 04 研究件 §5 第 3/4 条 |
| 9 | detailrels 零金额（04）与非零（02）透传 | `bpm_verify.py` 快照核对（extra_tables 透传已有） | 零金额行不参与金额闭合、行数仍核对的规则分支 | 04 研究件 §5 第 5 条 |

## B. 实施顺序建议（首件验收逐级放量）

1. **第 1 级（纯配置）**：A#2 两份 config 文件落盘（不注册）+ 离线 schema 校验测试——最便宜环节拦列形错误。
2. **第 2 级（注册+离线链）**：A#1 注册 + A#5 计划层 invoice 通道 + 合成材料 agent 自驱链（复用 round-8 expressloop chain_driver 模式）validate 零 issues。
3. **第 3 级（真实闭环）**：授权回放材料（需用户提供或授权历史复杂单）→ 真实 Chromium fill_only + 独立回读（模式同 round-8 express/rd 闭环）。**reimItem 枚举/预算选择器观察（A#3/A#8）在本级首单补**。
4. 每级验收：全量 unittest + verify_bpm_build 唯一 run PASS。

## C. 明确不做（本轮边界重申）

- 不注册、不启用、不写 bpm_types.py、不建 config 文件本体（本工件仅映射）。
- 02/04 各 1 样本，枚举/选择器交互未观察项全部列缺口，不以推断充证据。
- 需用户/后续合同输入：02/04 授权回放材料或真实编辑页观察授权；reimItem 枚举证据。
