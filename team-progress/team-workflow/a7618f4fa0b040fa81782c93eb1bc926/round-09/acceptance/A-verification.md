# Round-9 A 独立验收记录（02/04 离线首件轮）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

## 1. 冻结与红线核查

- 基线 `0d355d19…`、criteria `1115c883…` 一致；HEAD 仍 `9299545`（零 commit）。
- 交接 artifacts 20 项 + evidence_hashes 11 项哈希全对账 **0 差异**；evidence 11 项全存在非空。
- **本轮零浏览器动作核实**：registry 维持 10 条 FORM_INTENT 零新增；SKILL.md sha `b41e9e4e…` 与 R8 逐字节一致（红线段零触碰）；`.pw-profile/` 零出现。
- 授权面纪律：写入文件全部在 round-9 合同授权清单内（bpm_types.py/document-types/tests/full-chain.md/runs/offline-verify/台账）；`verify_bpm_build.py`/`fill-plan.schema.json`/`bpm_extraction.py` 未触碰并**主动披露**未同步项（见 §4）。

## 2. 02/04 首件放量——核实通过

- `bpm_types.py` 亲读：封闭注册扩为五类型（travel/express/rd_materials + office_supplies 02 / welfare_labor 04），`resolve_type` 保留 executable 门与 `execution_state=offline_modeled_live_pending` 检查——"新增 JSON 不自动启用"边界在代码层成立。
- 两 config（office_supplies.json / welfare_labor.json）主/子表 schema 完整；notes.md 差异对照与实测证据指针（类型码 02/04、reimItem 02001/04003、detailrels 形态、invoice=false）齐备。
- 离线链双 EXECUTION_READY（officeloop 42 sources / welfareloop 26 sources）：**browser_launched=false、validate-only 子进程 PLAN_VALIDATED**，plan sha/plan_hash 与 events 一致；合成材料明示 synthetic/test_only 且不入业务 task-registry。
- 空表裁决：welfare costs=0 双理由（not_applicable + 材料来源）；单层 details 走 summary_layer:absent 分支留痕。

## 3. D18 补行 + D22 方案 + 三观察——核实通过

- `tests/test_bpm_extraction.py` D18MatrixTests 4 方法亲核（多页 PDF 逐页锚点跨页回锚 page:1/page:2；一页双票一票一件契约钉板——首匹配单记录、二票值不混入、显式拒绝列未授权缺口；Excel 多 sheet/公式可重算 gap/汇总明细跨表候选/隐藏行金额仍入 SUM；数值保真前导零+19 位账号→Decimal 0.005 阻断→banks 0.305 拒绝）。
- `tests/test_bpm_type_round9.py` 6 方法×subTest=14 用例（注册身份/7 种负例 config 突变/离线计划零 issues/UNSUPPORTED_RELATION/主表-免票行/空表双理由）。
- D22_plan.md（7 节）：S1-S9 范围、证据与 PASS/FAIL/BLOCKED 判定、G1-G6 缺口表（G1 链产品化/G2 02-04 控件/G3 schema enum/G4 一页多票/G5 供料/G6 登录窗口 2026-11-23）与实施前置五条——**方案产物，未实施**（bpm_chain.py 不存在，符合授权边界）。
- 三观察：chain_segment_start 分段标记落地（append-only 语义保留，officeloop 1/2/11/19 含失败段）；research 键名约定入 full-chain.md（本轮零 authorization 键）；no-residue 布尔分层命名约定。

## 4. 披露处置与 A 侧归因

- **verify_bpm_build source_manifest 未含 02/04 config、fill-plan.schema.json enum 未同步、一页多票显式拒绝未实现**——三项均为 round-9 授权面遗漏（A 责任），B 零越界并如实披露；02/04 config 绑定经 resolve_type digest（含 config sha）+链产物+notes+handoff 成立。**D23 维持 PASS_DYNAMIC**（manifest 机制与所覆盖文件一致性未破；新文件同步列 round-10 首项授权），不加 failure key。
- P2-1 披露精度指正已处置（notes 补记 config sha，最终 sha `f1eaa161…` 与 handoff 一致）；P2-2/P2-3/P2-4 转 D22 实施轮。

## 5. 独立复跑

- selftest exit 0；`unittest discover -s tests` **Ran 273 tests, OK**（+18 与申报一致：14 类型+4 D18；skipped=4 为 Round9TypeCommon 参数化基类占位，同用例在 02/04 两个子类下实际执行）；verify_bpm_build 唯一 run **OFFLINE_PASS**（A 侧 capability 264 与 B 自报 r9final 一致）。

## 6. 判据状态（无翻转）

- D12 维持 FAIL：02/04 达到"规则/配置+封闭注册+离线链"级（5 类中 2 类），§8.2 循环的"真实页面观察/真实控件测试/真实端到端"未开始（待授权/供料）；06 无候选。
- D18 维持 FAIL：+4 行落地；不同扫描同票、相同金额不同业务、含税/未税混淆等行仍缺，保存行按用户指令排除。
- D22 维持 FAIL：方案就绪，实施待授权。
- D4 BLOCKED / D11 / D20 / D25 不变。

## 7. 结论

四条款全部完成、授权边界零越界、披露完整；当前 20 PASS / 1 BLOCKED / 6 FAIL，无新 failure key（D23 维持 1/3）。decision=rework。Round-10 主靶：①附属同步三项授权落地（manifest/schema enum/一页多票拒绝）；②02/04 只读控件观察授权（真实页面、零业务行、零保存、页面放弃留痕）；③D22 G1 实施（bpm_chain.py 链产品化，含 P2-2/P2-3/P2-4）。
