<!-- team-task-source id="src-c685aed0" sha256="c685aed06ccc4f9df15dd673597f5c045639e69e2ae0a42af9da2f4726121cfc" status="open" -->
workflow_run: d91601924848489f84e317e68582de26
workflow_round: 4
failure_counts: {"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}

# 本次任务：V3 round 4 —— CASE-03 真实公出单模块逐票查证与对照报告

背景（自足）：workflow run `d91601924848489f84e317e68582de26` round 4，合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md` §5 为本轮规则原文）。已交付并经 A 验收：CASE-01 事实层 `automation/runs/20261026-115500-v3r02-case01/case01-facts.json`（52 唯一身份逐值锚点）、CASE-02 `automation/runs/20261026-131000-v3r03-case02/case02-mapping.json`（20 行↔27 张唯一通行费恰一次分配，每票有行定位）及覆盖实算 K=1438/M=1438.00/T=486.93/R=1924.93/O=2031.17/F=2518.10/margin=593.17（F>R 门槛通过，仅观测结论不预设 OA 动作）。原对应公出单已被原报销单使用（既有案例，不推断其审批/支付状态）。**本轮只做公出单模块只读查证与真实逐票对照报告；OA 填写、随机测试占位关联（oa_test_relations/test_placeholder）留 CASE-07，不在本轮执行，也不得提前混淆。**

**历史累计失败字典（不清零、不改名；同问题沿原 key 累计）：**

```json
{"review|content|source_manifest_coverage|D23": 1, "review|content|active_output_semantics|D22": 1}
```

两项均已闭环（D23=V3-R00 唯一构建；D22=V3-R02 三态语义），计数保留为历史；本轮无新增失败即原样带入。

## 待做条款

### 1. 登录与身份（只读前置）
- 先 `python -X utf8 bpm_login.py` 只读探查当前登录：profile 锁、会话元数据、当前人员与有效性（已知 refresh token 边界 2026-11-23，以当次探查为准）。需要新扫码时按 `WAIT_HUMAN_LOGIN` 保留页面/工件并停等账号持有人，agent 不代扫、不绕过。
- 身份探查结果记录到 `automation/.local-session/`（不入工件、不入 Git）；本轮零业务写入，公出单模块全程只读。

### 2. 真实公出单模块定向查询（V3 §5）
- 由唯一浏览器执行者（单 profile 单执行者，Chromium `--no-proxy-server`）进入真实 OA **公出单模块**，按原件实际申请人、年份（2025）、日期/时段（期间链 2025-08-25→12-10 内 10 个出行日：0825/0904/0906/0917/0928/1028/1112/1124/1204/1210，以票面 travel_date 与 mapping 行日期为准）、起讫地（翔安/池店/晋江南/石狮北石湖/同安 ↔ 厦门/晋江总部，站点↔地址两套词汇按 CASE-02 登记口径）与业务信息**定向查询**；处理分页、筛选、详情消歧。
- 已被历史报销使用的公出单可能不在"可关联"弹窗中：**查不到可用选项不等于单据不存在**，必须到模块里找；不为找单号普查全部历史（AGENTS 红线）。

### 3. 逐票匹配与 actual_trip_matches（一票不漏）
- 每张去重后的 27 张真实通行费票据都有**独立匹配记录**：每票精确指向唯一经证据确认的目标，或如实登记零匹配/多候选未解（报具体缺口+查询证据+排除理由），不得漏票、不得随机指认、不得凭金额或同日即判匹配。
- 往返分票、一个公出行程包含多段收费、同日多张公出单等情况逐票展开真实关系与依据；不凭数量相等强造双射、不把多票汇总成一条冒充逐票对应。
- 每票记录（V3 §5 报告最小字段）：票据 ID、源文件/页、票号、实际通行日期/路线、金额、Excel 行定位（沿用 case02-mapping 行号）、**完整公出单号/唯一身份**、申请人、行程区间与路线、匹配依据、候选及排除理由、实际占用状态、详情/截图证据、最终结论。
- `actual_trip_matches` 交付机器可读 + 用户可读双版本；与 oa_test_relations/test_placeholder 概念严格分离——**本轮不选任何占位单**，报告中不得出现占位语义。

### 4. 完整性核验（可复算）
- 匹配报告票据 ID 集合 == 27 张去重通行费集合（一张不漏）；每票恰一条最终结论。
- 金额合计 == T=486.93；关联公出单去重数、各单对应票数、对应 Excel 行数可独立复算。
- 油票参与金额覆盖，不强行要求每张油票对应某张公出单。
- 终局由 A 换库/换路径独立复算，不以执行函数返回值当验收。

### 5. 证据、台账与交接
- 新 run 目录（`automation/runs/<时间戳>-v3r04-case03/`）：events.jsonl 追加式、每票查询/详情截图与 DOM 快照哈希、probe 结果；凭证原值不入任何工件。
- `automation/template-materials-program/progress.json` 补 V3-R04；**errata 追加一行订正**：round-3 .gitignore erratum 中 `.claude/settings.local.json` 行归属应为"A 侧 2026-10-26 13:15:01 按用户明确要求写入（禁用后台 shell 内存回收 env 的配套 ignore），非 B 写入"（A 已以 git diff + mtime 实证；`automation/.local-session/` 行确系工作流前遗留，原结论该部分不变）。
- 改动 `stage1_browser_probe.py` 须先 `python -X utf8 stage1_probe_selftest.py` 全绿再实单；未改则不跑。源码/schema 有改动时全量 `python -X utf8 -m unittest discover -s tests` + 唯一新 offline-verify run；纯查证轮无源码改动可沿用并说明。
- P6 收尾 + finish；handoff 哈希绑定实际文件；失败字典原样带入。

## 保留项与边界
- fill_only：本轮公出单模块**零写入**、零审批、零占用、零关联选择；不改旧报销单、不重新占用已用单据、不测保存。
- 原件目录只读（73 件零漂移）；派生文件不入原件目录；不接入其他类别、不做模板普查；模板身份缺口维持 PENDING_HUMAN_NONBLOCKING（CASE-05/06 前须用户提供完整模板单号）。
- 默认不 commit；真实材料/凭证不入 Git 与工件；Python `-X utf8`、cwd 仓库根、不走 VPN/Clash。
- 观察项（非阻塞、有余力再做）：schema 字节基线、capability 子集 299≠308、P2-2 test_bpm_round10_sync docstring、P2-3 source.md sha256 属性名。
- 登录失效/扫码中断按既有机制停等，不作为阻塞项伪造通过；真实公出单零匹配或多候选未解时如实报缺口（V3 §13 边界），正确拒绝可验收、不冒称匹配通过。

## 验证
- 逐票链：27/27 每票有最终结论或如实缺口；匹配依据可从 facts/mapping 与模块详情双侧复推；候选/排除有证据。
- 完整性：票据集合、金额合计 T、公出单去重/对应票数/行数三向可复算；actual_trip_matches 与占位概念零混淆。
- 证据：模块进入/查询/详情/分页的真实浏览器证据齐全且哈希落盘；登录探查记录在案；零业务写入。
- 台账 V3-R04 + errata 订正一行 + 交接哈希一致；失败字典承接。

## done_when
1. CASE-03 完成：真实公出单模块定向查询与逐票查证执行完毕，27/27 每票有"已验证匹配（完整单号+详情+证据）"或"如实缺口（零匹配/歧义+查询证据+理由）"，一张不漏、无强造对应；完整性三向复算（票据集合/T 合计/单-票-行计数）一致。
2. actual_trip_matches 机器可读+用户可读双版本交付，与任何占位关联概念严格分离（本轮零占位选择）。
3. 真实浏览器证据链（模块进入、查询、详情、分页）与登录探查记录完整落盘；全程零业务写入、零审批、零占用。
4. 台账更新至 V3-R04 含 .gitignore erratum 归属订正一行；P6 + finish 交接哈希与实物一致；历史失败字典 {D23:1, D22:1} 原样带入。
<!-- /team-task-source -->


<!-- team-task-contract run_id="20261026-141933-c685aed0" contract_id="ctr-50808d2d" source_block_id="src-c685aed0" status="frozen" profile="minimal" -->
## 基线
- 需求源：team-task.md src-c685aed0（workflow round 4，A publish 派发）；规则原文=冻结V3 §5。
- 上游已验收工件：case01-facts.json（52 身份）、case02-mapping.json（20 行↔27 票恰一次）、覆盖实算 R=1924.93/F=2518.10/margin=593.17。

## 冻结范围（本轮唯一交付：CASE-03 公出单模块逐票查证）
1. 只读登录探查（bpm_login.py；失效按 WAIT_HUMAN_LOGIN 停等，不代扫）。
2. 真实公出单模块定向查询：申请人/年份 2025/10 个出行日（0825/0904/0906/0917/0928/1028/1112/1124/1204/1210，以票面 travel_date 与 mapping 行日期为准）/起讫地（站点↔地址两套词汇按 CASE-02 口径）；处理分页/筛选/详情消歧；查不到可用选项不等于单据不存在，必须进模块找；不为找单号普查全部历史。
3. 27 张去重通行费逐票匹配记录 actual_trip_matches（机器可读+用户可读双版本）：每票完整公出单号/唯一身份、申请人、行程区间与路线、匹配依据、候选及排除理由、实际占用状态、详情/截图证据、最终结论；或如实登记零匹配/多候选缺口（查询证据+排除理由）；不漏票、不随机指认、不凭金额或同日强判、不把多票汇总成一条；与 oa_test_relations/test_placeholder 占位概念严格分离（本轮零占位选择）。
4. 完整性三向复算：匹配报告票据 ID 集合==27 张集合、金额合计==T=486.93、关联公出单去重数/各单对应票数/对应 Excel 行数可独立复算；油票只参与覆盖不强求逐张对应；终局 A 换库/换路径独立复算。
5. 证据与台账：新 run 目录 events.jsonl 追加式、每票查询/详情截图与 DOM 快照哈希、probe 结果；progress.json 补 V3-R04 + errata 订正 round-3 .gitignore 归属一行（A 侧 2026-10-26 13:15:01 按用户明确要求写入，非 B 写入；.local-session 行结论不变）；改 stage1_browser_probe.py 须先 selftest 全绿；源码/schema 有改动时全量 unittest+唯一 offline-verify，纯查证轮无源码改动可沿用并说明。

## 红线（不变）
fill_only：公出单模块零写入/零审批/零占用/零关联选择；不改旧报销单、不重占已用单据；原件 73 件零漂移、派生不入原件目录；凭证原值不入工件/Git；默认不 commit；.pw-profile 不复制；legacy-ia2 只读；不导航/关闭其他执行者未保存页；Python -X utf8；Chromium --no-proxy-server 直连；失败字典 {D23:1, D22:1} 原样带入。

## 验收（done_when）
27/27 每票"已验证匹配（完整单号+详情+证据）"或"如实缺口"；三向复算一致；真实浏览器证据链（模块进入/查询/详情/分页）+登录探查记录完整；零业务写入；台账 V3-R04+errata 一行；P6+finish 交接哈希与实物一致。
<!-- /team-task-contract -->
