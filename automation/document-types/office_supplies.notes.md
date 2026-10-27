# office_supplies（02 低值易耗品、办公用品采购）首件备注 — round-9 / ctr-15712bcb

## 定位

注册表新增类型（`bpm_types.py` `_REGISTRY`），`execution_state=offline_modeled_live_pending`：
**离线链可用，真实页面控件/填写路径零动作**（合同本轮零浏览器；新增 JSON 不自动启用类型，D12）。

## 研究工件 → 配置 差异对照

| 研究工件（输入） | 配置/实现（输出） | 说明 |
|---|---|---|
| `runs/20261024-170000-fiveresearch/raw_15426101596_dijiazhi.json`（只读 GET） | 表列集/只读回读字段（details 8 列 + genreId 等 readback_extra） | 列集与 express 完全一致（实测比对）；`budgetOwner` 只读回读保留 |
| 同上 detailrels：申请书(bizType 34) 非零绑定（bizDetailCost/bizDetailNum 真实值） | `extra_table_projections.detailrels.observed_relation_types` 记录形态；`supported_relation_types=[]` | **裁决①**：plan 级非空 relations 不建模（`bpm_plan.py` 非 travel 非空 relations 拒绝维持；该文件本轮不在授权面）。形态仅存证 |
| 同上 `main.invoice=false`（文档级无发票） | `invoice_policy={document_level, required=false, evidence=…}` | **裁决②**：本轮为 config 声明级通道（`resolve_type` 校验形状+来源）；plan 级强制留待 bpm_plan 授权轮 |
| 同上 `details[0].reimItem="02001"` | `reim_item_prefix.observed_values=["02001"]` | 枚举不穷举；编辑器联动待真实页观察 |
| census `submitType` 码 02 | `category.api_code="02"`、label 用渲染原文 | census：`runs/20261023-142146-travelcensus/travel_census.json` |

## 离线链首件（level 2）

- run：`runs/20261024-193500-officeloop/`（合成材料明示 synthetic/test_only，不入业务 manifest）
- 结果：`validate_plan` 零 issues → `fill_once --validate-only` 子进程 exit 0 → `EXECUTION_READY`
- plan sha256 `65ef8a98…`（文件），plan_hash `d426d31c…`（规范哈希）；42 sources
- 形态：details 1 / costs 1 / banks 3，1234.56 四向闭合；plan 级 relations 空 + 材料来源理由
- 单元测试：`tests/test_bpm_type_round9.py::OfficeSuppliesRound9Tests`（注册/负例配置/离线计划/边界，5 项）

## 已知缺口（下轮输入）

1. `automation/fill-plan.schema.json` 的 `document_type`/`submitType` enum 仍为 travel/express/rd_materials 三类——schema 本轮不在授权面，未同步 02/04；生产路径不消费该 enum（`validate_plan` 为准），但 schema 与注册表已不一致，需下轮授权后同步。
2. ~~真实新页控件观察未做~~ → **2026-10-26 部分回填**（round-10/V3-R02，见文末「观察状态回填」节）：reimItem 02 枚举/类别联动 8 表/关联类型枚举已实测（attempt_007）；budgetNo/subjectName `NO_TABLE_DIALOG` 未解、申请书 picker 与真实填写仍待类型接入轮。
3. plan 级 invoice_policy 强制（与行级 no_invoice_rows 并存语义）待 bpm_plan 授权轮。

## 观察状态回填（round-10/V3-R02 补做，2026-10-26）

r10 计划的"观察结果回填 config + notes 修订"当时未执行（V3-R00 §4 登记），本轮按 V3 round-2 任务条款 3 补做：

- **已实测**（证据 `automation/runs/20261024-213500-type0204-observe/attempt_007/evidence/observe_result.json`，status=OBSERVED，纪律=只读控件观察零业务写入）：
  - 类别联动后 8 表结构全量列 props（关联单据/关联单据明细/报销明细/费用说明/银行信息/确认人/审批记录/附件）；
  - reimItem 02 行编辑器=dropdown，枚举 {培训费, 业务招待费, 其他, 办公费} 5 项（`row_editors_after_reim_02.json`）；此前 `reim_item_prefix.observed_values=["02001"]` 为研究单实测值，与新页枚举标签体系并存（码值映射待类型接入轮实测补全）；
  - 关联单据类型枚举 20 项，含"公出单""出差单"；header 编辑器形态（appliedName=当前操作人 只读等）。
- **未解**：budgetNo/subjectName `mode=table_dialog, status=NO_TABLE_DIALOG`——既有工件定位已穷尽（tables_02.json 仅列定义；行编辑器证据只捕获 reimItem），需新假设下局部复测。
- **口径修正（V3 §12.1/D22 同源）**：save/reopen 核验不再是当前轮待验条件，仅在_future_获得明确保存授权的轮次观察；`required_observations` 文案已同步。
