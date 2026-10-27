<!-- team-task-source id="src-c1c5d877" sha256="c1c5d87735271f3b6d503bd302b8e9471947049b83b6e12c6badb1e9929d37b3" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 7
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 7 —— CASE-07 正式入口真实填写 + 随机测试占位关联（fill_only，B1–B5 证据链）

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 7，合同 `BPM-MATERIALS-20261026-V3`（§5.3 占位关联规则、§7 填写纪律、§10.3 B1–B5 为本轮规则原文）。已交付并经 A 验收（18 项 PASS_DYNAMIC）：CASE-01/02/03 事实-映射-逐票对照、round-5 卫生修复、CASE-05/06 模板与计划——`automation/runs/20261026-172300-v3r06-template-plan/`：模板 15426095951 快照（travel 兼容，uuid 92d41ffd…，三员=陈晶/116070053）、fill-plan v1.0（sha256 0d5b22cd…/plan_hash 1b3ba0b9…，details 2+costs 20+banks 1 三向闭合 1924.93==R，coverage F=2518.10>R 严格门槛通过，relations 留空+理由，来源 170）、复用矩阵、validate-only PLAN_VALIDATED。**本轮把该计划写入真实 OA 新页并执行受限随机测试占位关联；全程 fill_only 不保存。**

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环，计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. 前置（只读）
- `python -X utf8 bpm_login.py` 只读探查（refresh token 边界 2026-11-23，以当次为准）；当前登录须为陈晶/116070053 且与计划 operator 一致，不符则阻断报告，不硬填。探查记录仅 `.local-session/`。
- 执行前核对：`automation/task-registry/` 无冲突 SAVE_INTENT/SAVE_UNCERTAIN 涉及本任务；plan_hash/config/模板/材料哈希绑定链与 round-6 交付一致；coverage 门槛 F>R 再核验通过后才进入业务写入（时序入 events）。

### 2. 执行计划变体与占位关联建模（V3 §5.3）
- 以 round-6 fill-plan 为基线生成执行变体（v1.1，含 oa_test_relations 占位意图块），变体生成逻辑、差异与哈希落 run 目录；除关联占位外任何值不得偏离 v1.0（金额/行数/来源零改动）。
- `oa_test_relations` 建模要求：每条占位行 `test_placeholder=true` 标记；来源=真实关联控件可选单据（弹出窗实际枚举值），**随机选择方法与种子记录在案**；行数不强行等于真实票数/公出单数；与 `actual_trip_matches` 两套数据分开建模、核验、报告，零混淆零编造单号/UUID/selected 对象。若 schema/执行代码需扩展占位语义，按工程条款走测试与构建。
- 禁区：不修改/释放旧报销单关联；不重新占用已用真实公出单；**若选择动作本身产生即时持久占用等业务变更，立即停止该动作并如实报告**（V3 §5.3 停止条款）。

### 3. 正式入口真实填写（V3 §7、§10.3 B4）
- 由唯一浏览器执行者以正式入口执行（`fill_once.py --fill-plan "<执行变体>" --expect-name "陈晶" --keep-open-minutes <N>`；Chromium `--no-proxy-server` 直连）：新页全部应填表与业务行经真实原生控件写入——header、details 2 行（预算字段联动选择）、costs 20 行（其它交通，逐行日期/地点/金额/事由）、banks 1 行、关联表占位选择；保留既有 Tab 失焦、600ms 轮询、重复稳定回读机制；evaluate 仅读取与必要定位，不直接赋值/伪造选择对象/拦截响应。
- **零保存**：普通 `_click_guard` 全程生效，不点保存/提交/发送/流转/上传/暂存/贴票/审批，未知弹框不自动确认；不写接口。
- B4 证据：events（含执行版本、行数、时序）、终局整页截图、各表填写过程截图；改 `stage1_browser_probe.py` 须先 `python -X utf8 stage1_probe_selftest.py` 全绿。

### 4. B5 新鲜 DOM 独立回读（V3 §10.3 B5）
- 填写完成后由独立读取路径重新采集实际 DOM 全量：全部字段、四表行数组、金额、关联表选中对象；与计划（含占位意图）全量 diff——额外/重复/缺失逐项列明；各层金额复算（明细合计/应报总额/银行合计/R）；占位选择对象与真实值零覆盖（占位带出的日期/人员/余额/金额不得改真实费用）。
- 回读快照+哈希落 run 目录（机器可读+可读双版本），供 A 离线独立复核；不以写入函数返回值当验收。

### 5. 证据、台账与交接
- 新 run 目录 `automation/runs/<时间戳>-v3r07-fill/`：events.jsonl 追加式、执行变体与差异说明、B4/B5 全套证据、未保存页盘点（页面/锁/registry 状态）与交接；凭证原值不入任何工件。
- `automation/template-materials-program/progress.json` 补 V3-R07：层次标注"真实控件已验证（填写+回读，未保存）"；占位关联单独一节（方法/种子/选中对象/读回/与真实对照分离声明）。
- 源码/schema/测试有改动：全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify；未改则沿用并说明。默认不 commit；73 原件第 7 轮零漂移复核。
- P6 收尾 + finish；handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- fill_only：本轮**不测保存**，不验收新单号/UUID/保存后重开/持久化；未保存不阻塞完成。既有 SaveController/守卫/registry 保护原样保留。
- 单 profile 单执行者；不导航/关闭其他执行者未保存页；重型浏览器操作错峰，A 不同时占用。
- 真实材料/凭证不入 Git；Python `-X utf8`、cwd 仓库根、不走 VPN/Clash。
- 观察项 3 条不阻塞；B6 独立复核与 B7 终局标记、CASE-08 新 session 使用验收留 round 8。

## done_when
1. 正式入口真实填写完成：计划全部值写入真实 OA 新页（header+details 2+costs 20+banks 1+占位关联），B4 证据链完整（events/版本/行数/终局截图），零保存类点击。
2. 随机测试占位关联按 §5.3 交付：真实可选单据+随机方法与种子+精确选择+完整回读+test_placeholder 标记+独立成表，与 actual_trip_matches 零混淆；旧单关联未动、无重新占用；如遇即时占用风险已按停止条款处理并报告。
3. B5 新鲜 DOM 独立回读交付：全量 diff（额外/重复/缺失清零或逐项解释）、金额各层复算==R、占位值零覆盖真实值；快照+哈希可离线复核。
4. 台账 V3-R07（含占位关联一节与层次标注）；新 run 证据齐全；P6 + finish 交接哈希一致；失败字典 {D23:1, D22:1} 原样带入。
<!-- /team-task-source -->
