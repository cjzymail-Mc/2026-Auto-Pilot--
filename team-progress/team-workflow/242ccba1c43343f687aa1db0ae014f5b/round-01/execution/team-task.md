<!-- team-task-source id="src-f2789e00" sha256="f2789e0058dd84f256c13fe00fc96573b683b9af6585165ae6a13bbd55709976" status="open" -->
# 本次任务

按 `feature01-细化报销skill/2026-10-27 报销单-自驾公出类技能固化施工合同-V1.md`（合同编号 `BPM-SELFDRIVE-20261027-V1`）启动新工作包首轮：**P0 接手核实 + P1 入口/规则版本化设计落地 + P2 规则计算核心与经典反例测试**。本轮全部离线与只读，为后续识票归集、Excel 回填、公出匹配、30 天会话改造与真实串联建立可验收地基。

## 范围

1. **P0 接手核实**（只读，产物落新 `automation/runs/<新run>/`）：
   - 完整读 `AGENTS.md`、`STATE.md`、`.claude/skills/bpm-fill-run/SKILL.md` 及本合同；盘点当前工作树（区分本轮新增与 rounds 3–10 既有未提交 diff）、执行者/锁/task-registry/遗留页面，输出可复用基础与缺口清单。
   - `python -X utf8 bpm_login.py` 只读探查当前登录身份并记录（认证失效则如实留缺口，不冒用历史姓名）；指定参考单 `15425123013`（制单人徐亮）只读核验真实表单种类与费用类别（差旅费/08），可引用已有 live 快照 `automation/runs/20261027-sample15425123013-live/`，需要新鲜读取时用 `bpm_template.py --live` 并与快照互证。浏览器只读动作错峰，单 profile 单执行者。
2. **P1 入口与规则版本化**：
   - 产出统一入口设计决策记录：模板读取→真实表单/类别核实→场景识别（采用证据+排除依据）→能力检查→按需加载 runbook 的路由方式，及"两类用户输入（材料目录/多路径 + 指定单号 + 一句意图）"的接单形态；不要求用户写内部 JSON。本轮不改 `SKILL.md` 正文，设计留档供后续轮实施。
   - 新增版本化自驾规则配置 `automation/business-scenarios/self_drive.json`：场景 ID/版本、适用表单（travel/差旅费/08）、公里单价 1.00 元/km、餐补 30.00 元/有效公出日（仅本次报销单制单人、本次范围∩已核实参与日、按日去重）、`R=M+T+C`、`F=O+T`、严格门槛 `F>R`（等于/小于均拒绝）、规则来源与哈希绑定字段；程序可读可校验。
3. **P2 规则计算核心与反例测试**：
   - 新增 `bpm_self_drive.py`：Decimal 两位精度金额模型（逐行交通=公里×1.00+该行唯一通行票合计；M/T/C/R/O/F；严格覆盖判定），输入绑定原始票据/公里/公出日来源，不与 coverage 声明块自比。
   - 落实合同 §6.1 脱敏反例/正向对照测试：09-05 交通 +2.00 与 09-28 交通 −2.00 抵消不放行（总额 1924.93 相等也必须逐行定位失败）；09-28 单 `12025098708` +4.00、12-10 单 `12025123375` −10.00 逐单定位；正向对照 `12025092018` 437.18（191.28+185.90+30+30）不得被错误派生值误判；日期反例（11-12 误写 11-14、11-24 误写 12-24）识别；新规则餐补（30/日）与历史餐补（12/18/24/36/48）分开建模不混淆；`F=R`、`F<R` 拒绝且无浮点容差。夹具脱敏，不含账号/手机号/会话元数据/凭证。
   - 修改主探针则先 `python -X utf8 stage1_probe_selftest.py` 全绿（本轮原则上不改探针）；相关改动跑 `python -X utf8 -m unittest discover -s tests`；新源码/规则/测试纳入源清单并跑 `python -X utf8 verify_bpm_build.py`（产物落 `automation/offline-verify/<新run>/`，不连生产 OA）。

## 保留项与红线（本轮不做/不变）

- 本轮零业务写入：不新建报销页、不填写、不保存、不上传/贴票/审批；浏览器仅只读正式入口且错峰。
- 30 天会话改造（60→30 收紧及旧记录 `min(原窗口,30天)` 迁移）属后续阶段，本轮只记录现状与设计要点，不改 `bpm_session.py`。
- 识票归集/规范命名/Excel 副本回填、真实公出单匹配与写入前 MD、`SKILL.md`/`references/self-drive.md` runbook 实质修订、正式入口真实串联与 D12 冷启动验收：均由后续轮派工，本轮不实施。
- 冻结 V3、旧 runs、旧 task-registry、原材料目录 `feature01-细化报销skill/12月公出-发票/`、`legacy-ia2/` 全部只读零漂移；`automation/.pw-profile/`、`automation/.local-session/` 不入任何工件/Git；案例对照值（交通 1924.93、餐补 300.00、合计 2224.93）只作离线测试对照，不写进生产路由逻辑。
- 旧失败 key `review|content|source_manifest_coverage|D23`、`review|content|active_output_semantics|D22` 历史各计 1，原样承接不隐去。

## done_when

1. P0 盘点工件落新 run 目录：工作树/执行者/锁/registry/页面盘点 + 可复用基础与缺口清单；当前身份只读探查结果（或如实认证缺口）；样本 15425123013 表单/类别核验证据。
2. `automation/business-scenarios/self_drive.json` v1 落地，含版本、规则来源、单价、模型与严格门槛字段，加载校验代码与测试通过。
3. `bpm_self_drive.py` 金额模型实现且 §6.1 全部反例/正向对照/日期反例/新旧行为分离测试通过：抵消不放行、437.18 不误判、逐行/逐单精确定位、`F>R` 严格无容差。
4. 全量 unittest 无回归；`verify_bpm_build.py` 通过且新文件纳入源清单，产物可回读。
5. 零业务写入与只读零漂移声明（含 73 原件或本批材料哈希盘点不变），证据与事件入 `automation/runs/<新run>/events.jsonl`。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261027-111853-f2789e00" contract_id="ctr-640d0763" source_block_id="src-f2789e00" status="frozen" profile="minimal" -->
# 任务：BPM-SELFDRIVE-20261027-V1 首轮——P0 接手核实 + P1 规则版本化 + P2 计算核心与反例测试

## 本次任务

- 终态一句话：新工作包地基落成——接手盘点工件、版本化自驾规则配置 v1、`bpm_self_drive.py` 金额模型与合同 §6.1 全部反例测试通过，全量回归与离线构建绿，零业务写入零漂移。
- 本轮做：P0 盘点（工作树/执行者/锁/registry/页面 + 身份只读探查 + 样本 15425123013 差旅费/08 核验）；P1 统一入口设计决策记录 + `automation/business-scenarios/self_drive.json` v1；P2 `bpm_self_drive.py`（M/T/C/R/O/F、逐行交通、严格 F>R、新餐补 30/日与历史餐补分离）+ §6.1 脱敏反例/正向对照/日期反例测试。
- 明确不做：30 天会话改造（只记录设计要点，不改 `bpm_session.py`）；识票归集/Excel 回填；公出匹配 MD；`SKILL.md`/`references/self-drive.md` 实质修订；真实串联与 D12 冷启动；保存/提交/上传。
- 允许写：`automation/business-scenarios/`（新）、`bpm_self_drive.py`（新）、`tests/test_bpm_self_drive.py`（新）、`verify_bpm_build.py`（仅源清单补 self_drive.json 一行）、`automation/runs/20261027-111853-f2789e00/`（新 run 工件）、`team-progress.md`、`handoff-input.json`。
- 只读：冻结 V3 及其 run 工件、旧 runs、`automation/task-registry/`、原材料目录 `feature01-细化报销skill/12月公出-发票/`（73 件零漂移）、`legacy-ia2/`、`STATE.md`、样本 live 快照（引用不复制）、`automation/.pw-profile/`、`automation/.local-session/`（不入工件/Git）。
- 禁止：任何 OA 业务写入（新建报销页/填写/保存/提交/上传/贴票/审批）；改 `SKILL.md`、`bpm_session.py`、`stage1_browser_probe.py`（本轮原则不改探针）；放宽 `_click_guard`/锁/registry/保存边界；案例对照值（1924.93/300.00/2224.93）写进生产路由逻辑。
- 红线：四红线（销毁性操作/对外交付/Ldterm/推翻已封决策）+ 本项目禁改冻结产物；凭证与会话元数据不入 Git/工件；同 key 失败 3 次熔断；浏览器只读错峰、单 profile 单执行者。

## done_when（字面可判；至少 1 条可外部取证）

- [ ] D1: P0 盘点工件落 `automation/runs/20261027-111853-f2789e00/`：工作树/执行者/锁/registry/页面盘点 + 可复用基础与缺口清单 + 身份探查结果 + 样本 15425123013 表单/类别核验证据（验证：目录内文件存在且四要素齐备，events.jsonl 有对应事件）。
- [ ] D2: `automation/business-scenarios/self_drive.json` v1 落地，含场景 ID/版本/适用表单（travel/差旅费/08）/公里 1.00/餐补 30.00/R=M+T+C/F=O+T/严格 F>R/规则来源字段，加载校验代码与测试通过（验证：tests.test_bpm_self_drive 配置用例绿）。
- [ ] D3: `bpm_self_drive.py` 金额模型实现且 §6.1 反例全绿：09-05 +2.00 与 09-28 −2.00 抵消不放行、09-28 单 +4.00 与 12-10 单 −10.00 逐单定位、437.18 正向对照不误判、11-12→11-14 与 11-24→12-24 日期反例识别、新 30/日与历史 12/18/24/36/48 分离、F=R/F<R 拒绝无浮点容差（验证：指定用例名单逐一通过）。
- [ ] D4: 全量 `python -X utf8 -m unittest discover -s tests` 无回归；`python -X utf8 verify_bpm_build.py --run <新run>` OFFLINE_PASS 且 self_drive.json 入源清单（验证：命令输出与 offline-verify 产物）。
- [ ] D5: 零业务写入与只读零漂移：73 原件哈希盘点不变、registry 零改动、无保存类点击（验证：盘点对照输出 + events.jsonl 声明）。
<!-- /team-task-contract -->
