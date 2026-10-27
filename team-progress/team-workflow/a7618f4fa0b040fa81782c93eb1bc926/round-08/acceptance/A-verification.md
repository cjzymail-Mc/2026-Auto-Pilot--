# Round-8 A 独立验收记录（express+rd 双闭环轮）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

## 1. 冻结与红线核查

- 基线 `0d355d19…`、criteria `1115c883…` 一致；HEAD 仍 `9299545`（零 commit）。
- 交接 artifacts 21 项 + evidence_hashes 9 项哈希全对账 **0 差异**；evidence 9 项全存在非空。
- registry：新增 2 条 FORM_INTENT（`20261024-r8-expressloop-15426094780`、`20261024-r8-rdloop-15426104120`），**零 SAVE token**、零 supersede（两笔均首发成功）、无删除/换 id/强关。
- 守卫面：`stage1_browser_probe.py`（10-24 10:43）/`fill_once.py`（12:37）round-8 零改动核实；`bpm_save.py` 未动；`.pw-profile/` 不在任何工件/证据路径。

## 2. P1-a 合同追认（第 0 条）——核实通过

- `automation/type-extension/ratification-20261024-round8.json`：`P1_A_RATIFICATION_EXECUTED`，授权依据指回 A round-8 任务原文与 round-07/acceptance/A-verification.md §6，常设允许写清单生效 + scope_guard（其他新文件仍先停-增补-再写，不外推）。
- 合同区 §0 与台账留痕核对一致。**P1-a 关闭**。

## 3. express 真实闭环——核实通过

- run 20261024-174500-expressloop：agent 自驱链 96 sources、零预制 payload；plan_hash `a494e784…` 链 PLAN_READY = stage1 = IV **三点一致**。
- 空表裁决：relations=0 有 not_applicable 当次理由（授权回放原表为空），符合"空表须当次来源理由"边界。
- fill 20261024-173807-72170651：**SUCCESS_FILL_ONLY** 首发（wall 164.8s），save NOT_ATTEMPTED，expect=陈晶（本次登录身份）。
- 独立回读 IV ok=true、issues=[]，行数 0/1/8/4 与计划一致，details=banks=costs=total=**347.50** 四向闭合。
- page_inventory_r8_express.json 完整（含 applicant_employee_id=116070053 及来源注记"页面登录默认 preserve_system_defaults，区别 round-7 picker"——身份来源层次记录规范）。

## 4. rd_materials 真实闭环——核实通过

- run 20261024-175000-rdloop：155 sources；plan_hash `dcf4f895…` 三点一致；amount_rules costs=not_applicable（当次理由）+products=sum 行总额，符合研发边界（费用说明为空、档案价格为行总额）。
- fill 20261024-174803-cd2e04e4：**SUCCESS_FILL_ONLY** 首发（wall 199.1s），save NOT_ATTEMPTED。
- IV ok=true、issues=[]：details4/costs0/banks4/**products18**（物品档案 18 行按现有编号选入未新造），details=banks=products=total=**9935.16** 四向闭合。
- page_inventory_r8_rd.json 完整。

## 5. 五类研究续推——4/5 落盘

- 01 其他费用（15425125587）：details 无预算变体 budgetKey=__、申请书(34)多明细部分占用、bizCost>totalCost 形态记录。
- 24 维修费（15426015123）：税额三值模型 cost/taxCost/realCost、对公收款人银行行。
- 06 会议支出：census list 0 候选，**如实登记未做**（需新 list 窗口或用户供号）——符合"缺口不虚构"。
- `code-adaptation-prep-02-04.md`：A 表 9 落点映射 + B 实施顺序 + C 明确不做，零实施。
- 七类码 08/11/15/02/04/01/24 实测互异；CLI 2/5 预算、只读零注册零启用（events 核实）。

## 6. 反例固化与 P2——核实通过

- `tests/test_bpm_ui.py` 新增两测试亲核在文件中：`COMPLETE_APPLICANT_EMPLOYEE_ID_REQUIRED`（页面默认≠计划且无 identity→硬阻断+零写）与 `EXACT_PICK_MISSING`（0 候选→硬阻断+部分状态必拒）。
- P2 五项：plan_hash 双字段（bpm_request.py+测试）；supersede docstring 收窄；events schema 统一；SKILL.md 措辞采纳（红线段不动，test_skill_docs 9/9）；**服务端无残留只读观察** run 20261024-181500-noresidue：登录人默认列表 17 行零筛选零点击，round-8 两笔今日创建 0 行/回放关键词 0 命中；存量 10-23 草稿 15426104612（live-complex-demo 时期）单列登记不触碰；attempt_001 收尾 AttributeError **诚实披露**，attempt_002 干净重跑两轮一致。

## 7. 独立复跑

- selftest exit 0；`unittest discover -s tests`：**255/255 OK**（110.6s，+2 与 B 申报一致）；verify_bpm_build 唯一 run OFFLINE_PASS（见 20261024-r8-acceptance-build.log；B 自报 r8final OFFLINE_PASS）。

## 8. 判据变动

- **D19 → PASS_DYNAMIC**：三类（travel r7 / express r8 / rd r8）各有真实 Chromium 整单 B1-B7 证据（入口/身份/唯一命中/联动/整单 events/新鲜 DOM 快照/agent 结论/盘点+终局截图）；判据未排除回放材料作为 B1-B7 载体。
- D11/D20 维持 FAIL：判据明文要求"本次原始资料/本次真实业务"（仅历史回放不计为通过）——三类机制层全通，等待本次真实材料（外部供料缺口，与 D4 同类）。
- D12 维持 FAIL：研究 4/5 + 适配准备落盘，注册/接入施工未开始（需 round-9 合同授权 bpm_types.py/document-types）。
- D18 维持 FAIL：+2 反例测试固化+无残留观察；PDF/Excel 变体行与保存行仍缺。
- D22/D25 未动；D4 维持 BLOCKED。

## 9. 结论

五项条款全部完成且证据链完整；失败-诚实披露-干净重跑的纪律（noresidue attempt_002）值得记录。无虚报、无红线违例、无新 failure key。当前 20 PASS / 1 BLOCKED / 6 FAIL。decision=rework，round-9 主靶：五类接入施工（02/04 首件放量）+ D18 离线矩阵补行 + D22 准备。
