# 启动前只读代码定位

用途：供新 workflow 的 A/B 判断现有实现和首轮配套范围，不是执行结果、验收通过或 D12 冷启动输入。定位来自两个只读 explorer；未修改源码、运行测试、读取个人会话/凭证或访问 OA。代码行号是施工前定位，实际以本轮文件为准。

## 30 天迁移

- `bpm_session.py`：`REUSE_DAYS`（约16行）、`state_usable`（66）、`attach_metadata`（100）、`write_record`（153）。实际判定来自受保护 state 的元数据，不能只改显示记录。
- 旧合法记录的可接受上限与新默认值分开。验证旧格式及可信扫码时间后，生效窗口取 `min(原合法窗口, 30天)`；保留更短窗口、原扫码起点、profile_id、session_generation。仅改默认常量会使当前 `days <= REUSE_DAYS` 拒绝所有旧60天记录，也会与非扫码写回/显示沿用旧值冲突。
- `stage1_browser_probe.py`：`SESSION_TTL`、`_session_state_usable`、`_inject_session_state`、`_save_session_state`；后者按读取旧state→attach→写state→write_record串联。判定、写回、显示与提示须一致，不能续期。`bpm_login.py` 保留真实 fresh_scan 识别及 force_scan 不注入旧凭证。
- 复用 `tests/test_bpm_session.py`、`stage1_probe_selftest.py` 的 `_t8_session` / `_t10_login_only`。补旧60天第29/30天、原7天不延长、非法61/非整数/bool/未来扫码/坏schema、更早refresh到期、缺扫码时间24h及mtime无效等边界。长期说明按合同同步，旧证据不改。

## 自驾覆盖、事实与计划

- `bpm_coverage.py` 当前 `CoverageInputs` 缺场景/规则版本与哈希、制单人、报销范围、参与日、唯一餐补归属和逐项来源。`evaluate_coverage` 固定旧公式，油票池列表未拒绝内部重复ID；`register_coverage_fact` 仅保留汇总，丢逐行/票据分配。
- `validate_coverage_block` 只校验声明自身；`bpm_plan.validate_plan` 目前调用它但不将声明总额与原始输入/计划金额绑定。主金额与明细/银行自身闭合仍可能与coverage互不一致。coverage新受保护路径也须进入来源校验，不能绕过现有标量检查。
- `bpm_plan_generate` 尚未把coverage事实搬到计划，现有派生绑定只支持既有金额指针sum，且计划拒绝派生链。公里政策和餐补不能伪装普通求和；使用场景限定的独立重算，不开放通用表达式系统。
- `bpm_facts.reconcile`、`bpm_plan_generate` 的分配过程、`bpm_materials` 的材料/票面校验，当前仍为整张票面→整条费用行。只增加餐补或schema分支仍会被这些路径挡住。须共同表达公里政策组成、实际通行费组成、餐补政策组成与油票覆盖池；不能把混合交通整行当免票，也不能放宽普通全票面分配规则。
- `automation/fill-plan.schema.json` 现为固定旧coverage封闭字段，须保留旧可选分支，新增明确模型/版本。规则哈希、原件/公里来源、唯一票据集合、人员与有效日集合、组成项映射及计划闭合纳入新分支。

## 正式入口与构建

- `bpm_request.register_request/resolve_template` 当前依赖结构化请求和缓存类别决策；未贯通真实模板→自驾场景→规则/能力路由。`execution_ready` 仅运行 validate-only 并返回命令。
- `bpm_chain` 当前需已整理JSON、明确类型和模板快照，再读取现成header/tables；终点仍为 `CHAIN_COMPLETE(validate_only=True, browser_launched=False)`。它不等于原始票据+公里表的用户入口或真实填写。
- `fill_once --task` 可推进事实到计划阶段但随即返回；真实浏览器在 `--fill-plan` 分支。上层入口须保留当前身份、来源绑定和registry检查并实际继续调用正式执行，不能把命令交给用户。
- `task.schema.json` / `validate_task` 的类型和身份兼容也要联动核实。沿用现有有限注册，不建设通用平台。
- `verify_bpm_build.py` 会收根目录 `bpm_*.py`，但新增场景JSON与runbook仍需显式进入源清单。
- 复用 `tests/test_bpm_coverage.py`、`test_bpm_plan_generate.py`、`test_bpm_request.py`、`test_bpm_chain.py`；现有coverage测试部分仅过滤coverage错误，不能证明全计划来源与金额一致。新增输入/规则漂移、声明与计划不一致、重复油票/餐补、范围外日期、组成项归属等负例，并保留旧类型/旧模型回归。

## 材料与公出查询的正式化接点

- `bpm_extraction.py` 已有 `extract_pdf_text`（逐页文本/bbox）、`extract_pdf_facts`、`run_pdf_extraction`、`render_pages/render_to_files`、`ocr_pass/review_pass`、`extract_workbook`；现有 `_recompute_simple_sum` 只覆盖字面数字区间的简单 SUM，不代表任意工作簿已可靠重算。
- 真实票面版式解析可参考只读旧脚本 `automation/runs/20261026-115500-v3r02-case01/case01_stage_b.py` 的 `anchor/nearest_right/column_row_values/parse_toll_invoice/parse_fuel_invoice/parse_summary`。Excel副本回填、COM重算和独立重新打开职责分别在旧 `20261026-131000-v3r03-case02/case02_stage_b.py` 与 `case02_stage_c.py`；正式化时去掉固定路径、sheet、列与行范围，不改旧脚本或原件。
- 现有 `extract_pdf_facts` 多身份拒绝保护应保留；归集层做逐页/区域分件，给唯一record_id及原件页/区域定位。下游 `bpm_facts.add_invoice_from_extraction` 和 `bpm_plan_generate` 现存 `records[0]` 路径必须同步处理，不能上游多票成功后下游仍只读第一票。`validate_reviewed_extraction` 已支持多记录、`validate_image_documents` 已有记录恰好一次对账要求，可继续承接。
- 公出查询当前主要在旧 `automation/runs/20261026-143340-v3r04-case03/` 的 `TripProbe/query_filters`、stage2b列表分页、stage3d/3e详情候选、stage4 matcher；较新完整详情读取见 `automation/runs/20261027-092454-xuliang-trip-mapping/xuliang_detail_probe.py`。正式 `bpm_template` 可复用锁/身份/临时context工程模式，但不是公出适配；`bpm_ui._fill_relation` 只选择已知编号，不承担真实查找。
- **人员参与和日期覆盖必须在同一事实行联合满足。**旧较新matcher中存在分别用两个 `any` 判断“该人在某行”与“日期被某行覆盖”的潜在误配；由不同人员行分别满足也可能被误判。正式匹配需保留全部details及行身份，针对同一行的 `appliedName`、`factStartTime/factEndTime`、`factNatureStartDate/factNatureEndDate` 联合判断后再归组，不能仅取第一个参与行、主表申请人或标题日期。这是代码风险定位，不认定本案例某张已核实单据错误。
- 正式分页须核总数、页码、唯一集合与终页；旧脚本某些提前终止分支仍报完成，不可照搬。捕获范围限已观察的业务查询响应，落盘哈希必须针对实际写入字节计算，不复用旧摘要序列化的不同哈希方式。

## 新增 A1 自动保存的最小接点

- 保存执行器已存在：`fill_once.main` 绑定计划后派发主探针，`bpm_ui.StructuredProbe.phase_fill` 完整独立回读通过且 `authorization.mode=save_draft` 才调用原 `SaveController`。无需再造保存控制器，不能普改历史链或guard。
- `bpm_save._preflight/run` 已校验同task_id、严格 `allow_submit=False`、声明/哈希/身份，并在点击前再核实、先落 `SAVE_INTENT`；已有意图/不确定/成功只读重开核实。`bpm_ui.click_exact_save` 还独立复核截图和唯一精确保存按钮，这些原样保留。
- 上游主要接点为 `bpm_request.REQUEST_KEYS/validate_request/register_request` 的执行意图与政策来源契约、`bpm_plan_generate` 的蓝图授权生成/绑定。当前 authorization 恰好四键，新增证明不能随意塞键；要同步 schema/计划及来源验证。`sources` 也不直接接受authorization指针，不能虚假登记无效来源。
- `fill_once.prepare_task` 当前未显式互校task与facts_payload/blueprint的task_id、operator及authorization；须防“任务只填，蓝图变保存”。旧 `bpm_chain` 硬编码fill_only并构造test_context，不能对整条历史/合成回放链全局改save_draft。
- 保存报告以真实 `draft_save/save_result` 与保存观察、重开快照/核验为准。`bpm_ui._reconcile` 现有更新draft_save/task_status却未同步save_status的路径值得核实，避免初始NOT_ATTEMPTED误导最终报告；这不是已验证的真实保存结果。
- 复用 `tests/test_bpm_save.py`、`test_bpm_ui.py` 和 `test_bpm_verify.py` 的授权/单按钮/漂移/未知弹框/重开/不确定拒绝测试。补请求→同任务授权策略、显式只填、历史占位拒存、task/蓝图意图不符、政策来源漂移及只读恢复报告一致。现有计划对test_context/oa_test_relations强制fill_only保持。
