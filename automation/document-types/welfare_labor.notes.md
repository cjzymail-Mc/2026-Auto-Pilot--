# welfare_labor（04 福利费、劳保用品）首件备注 — round-9 / ctr-15712bcb

## 定位

注册表新增类型（`bpm_types.py` `_REGISTRY`），`execution_state=offline_modeled_live_pending`：
**离线链可用，真实页面控件/填写路径零动作**（合同本轮零浏览器；新增 JSON 不自动启用类型，D12）。

## 与 office_supplies（02）的关键差异

| 维度 | 02 | 04 |
|---|---|---|
| 主费用表 | costs（`amount_rules.costs="sum"`） | **details**（costs `not_applicable` + `costs_reason`） |
| FactSet 分层 | details=summary 层，costs=detail 层 | **details 即 detail 层（单层）**，无汇总层；reconcile `summary_detail_consistency` 走 `summary_layer: absent` 分支（首件实测） |
| detailrels 形态 | 申请书(34) 非零绑定 | **福利申请单(74) 零金额**（bizDetailCost/bizDetailNum/usedCost 全 0.00，`zero_fields`+`system_field_rules` 逐字段实测依据） |
| costs 适用性 | 默认可用 | `costs_applicability.default=not_applicable`（研究样本 costs 全空；材料须携带当次理由） |
| 免票行落点 | costs 行 | **details 行**（primary=details） |

## 研究工件 → 配置 差异对照

| 研究工件（输入） | 配置/实现（输出） | 说明 |
|---|---|---|
| `runs/20261024-170000-fiveresearch/raw_15426071883_fulilabao.json` | 表列集同 express（实测比对） | 跨部门预算形态（budgetDeptName≠申请人部门）进 `required_observations`，不做枚举假设 |
| 同上 detailrels 福利申请单(74) 全零 | `observed_relation_types` + `zero_fields` + `system_field_rules` | **裁决①**：plan 级非空 relations 不建模（维持拒绝）；形态仅存证 |
| 同上 `main.invoice=false` | `invoice_policy={document_level, required=false}` | **裁决②**：声明级通道（`resolve_type` 形状校验）；plan 级强制待授权轮 |
| 同上 `details[0].reimItem="04003"` | `reim_item_prefix.observed_values=["04003"]` | 枚举不穷举 |
| census 码 04 | `category.api_code="04"` | census 实测 |

## 离线链首件（level 2）

- run：`runs/20261024-194500-welfareloop/`（合成材料明示 synthetic/test_only，不入业务 manifest）
- 结果：`validate_plan` 零 issues → `fill_once --validate-only` 子进程 exit 0 → `EXECUTION_READY`
- plan sha256 `a4c4da99…`，plan_hash `246027c4…`；26 sources
- 形态：details 1 / costs 0（not_applicable + 双理由：`amount_rules.costs_reason` 与 `table_applicability.costs.reason`）/ banks 1，2345.67 三方闭合
- 单元测试：`tests/test_bpm_type_round9.py::WelfareLaborRound9Tests`（注册/负例配置/离线计划/空表理由，5 项）

## 已知缺口（下轮输入）

1. 原首件记录的schema enum缺口已由后续轮次修复：当前 `automation/fill-plan.schema.json` 已包含02/04及对应submitType。注册/schema可用不等于真实整单已验收；其余控件/关联/业务缺口按下文保留。
2. ~~真实新页控件观察未做~~ → **2026-10-26 部分回填**（round-10/V3-R02，见文末「观察状态回填」节）：reimItem 04 枚举/类别联动 8 表/关联类型枚举已实测（attempt_007）；budgetNo/subjectName `NO_TABLE_DIALOG` 未解、福利申请单 picker 零金额复现/跨部门预算范围/真实填写仍待类型接入轮。
3. plan 级 invoice_policy 强制待 bpm_plan 授权轮。

## 观察状态回填（round-10/V3-R02 补做，2026-10-26）

r10 计划的"观察结果回填 config + notes 修订"当时未执行（V3-R00 §4 登记），本轮按 V3 round-2 任务条款 3 补做：

- **已实测**（证据 `automation/runs/20261024-213500-type0204-observe/attempt_007/evidence/observe_result.json`，status=OBSERVED，纪律=只读控件观察零业务写入）：
  - 类别联动后 8 表结构（同 02 形态）；reimItem 04 行编辑器=dropdown，枚举 {宿舍费用, 食堂费用, 住房补贴, 团建费, 员工福利} 6 项；关联类型枚举 20 项含"公出单""出差单"；header 编辑器形态。
- **未解**：budgetNo/subjectName `NO_TABLE_DIALOG`（与 02 同形态，根因同待新假设复测）。
- **口径修正（V3 §12.1/D22 同源）**：save/reopen 核验不再是当前轮待验条件，仅在_future_获得明确保存授权的轮次观察；`required_observations` 文案已同步。
