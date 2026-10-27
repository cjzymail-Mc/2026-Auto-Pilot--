# CASE-08 新 session 使用验收 —— 结论报告（B 汇总签发）

任务条款：team-task src-82e4775e 待做 2；合同 ctr-3057b56a 冻结范围 2；V3 §10.5/§9。
执行方式：全新 general-purpose subagent（零对话上下文继承），白名单输入清单先于启动落盘（`case08-input-manifest.md`），产物全部在 `case08/`，其输入读取日志 `case08/input-log.md`（#1–22）可逐项审计。
一句话结论：**零上下文新 session 仅凭生产 skill + 冻结合同 + 73 原件，独立走通"理解→复算→自有 v1.0→validate-only 全绿"，且与已交付链核心事实全部收敛一致（R=1924.93、coverage 全链、27 票号集合、banks、身份）；3 项非金额差异均如实记录且不构成缺陷。**

## 一、阶段一（独立重建，零交付物输入）

- 材料准备：自建 `task.json`（task_id v3r08-case08-15426095951）→ `fill_once.py --task` 独立 run `20261026-193100-0527f5dc`（NEEDS_INPUT/MATERIALS_READY，材料/parsed 为其自产）。
- 模板：census 缓存定向读取 15426095951（snapshot sha be71cb92…，与 B 侧 live 快照 7c71bd42… 在阶段二逐字段核对一致）。
- 原件理解：72 PDF 渲染 74 PNG + PyMuPDF 文本层机读（pdf-text/ 72+index）；电子发票**文本层机读为主通道**，视觉仅交叉验证。
- 独立复算：K=1438、M=1438.00、T=486.93（27 票逐张机读）、R=1924.93、O=2031.17、F=2518.10、margin=593.17（F>R 严格门槛通过）——与交付链完全一致（`fact-recompute.json`）。
- 自有 v1.0：`case08/fill-plan-v1.0.json`（sha e600f67a…，canonical ec2c811b…）`--validate-only` → **PLAN_VALIDATED**（validate-output.txt）。
- 52 唯一票据身份判定与交付链一致：1210 = 两张不同票（19977515+20519372）→ 52 而非 53；**0904 = 16104706**（机读定案；agent 视觉曾误读 16104645，被"机读+汇总单互证"双通道纠出——该发现已促成 skill 文档补丁，见下）。

## 二、阶段二（事后审计比对；比对用交付物在阶段一回报后才提供）

比对报告 `case08/comparison-report.md` + `comparison.json`。核心结论 **全部一致**：

| 比对面 | 判定 |
|---|---|
| vs 已交付 v1.0（0d5b22cd…） | R/coverage/27 票号集合/banks/身份/relations 处置同构——**一致**；27 票号集合逐张全等（含 0904 定案值与 1210 两票处理） |
| vs B5 独立回读（v3r07 attempt_001） | 行数 1/2/20/1、四向金额 1,924.93 闭合、身份一致（relations 1 行 = 合同授权占位路径，边界不同不构成冲突） |
| vs CASE-03 逐票对照 | 12 匹配 Σ221.02 + 15 无匹配 Σ265.91 = 486.93 == T，Σ闭合一致 |
| vs 模板快照 | live 与 census 逐字段一致（差异仅采集时间/来源） |

**3 项非金额差异（不静默、均非缺陷）**：
1. **码 vs 显示名**：交付链用显示名（厦门乔丹科技有限公司/乔丹科技/转账/人民币），验收方用模板 API 原码（1003/QDTech/02/RMB）。快照自注 codes require current display resolution → **交付链的显示名口径更符合真实填写要求**；两版均过 validate（校验器只查 corpCode==company 自洽）——属校验器放行宽度，已记观察项。
2. **证据深度**：验收方完成 72 PDF 全分类 + 27 票全额分配闭合；交付链为 20 条混合免票理由（0 image_documents）。金额同、证据形态不同。
3. **建模粒度**：costs 20 逐段行 vs 2 汇总行；details 行序互换、digest 措辞不同。均合法。

## 三、skill 可操作性发现与处置（`case08/skill-operability-assessment.md`）

| # | 发现 | 处置（本轮收口） |
|---|---|---|
| 1 | 冷启动无"PDF 票面机读优先"指引；视觉幻觉 3 次（0906/0904/0928） | **已补文档**：SKILL.md 步骤 2 + plan-contract.md PDF/图片段，"机读文本层优先、视觉仅交叉验证、票号级双通道裁决" |
| 2 | digest 的 material/user 限制与可用 locator 现实错配（xlsx 表头带换行） | 保留现约束（行为不变）；`agent_reviewed` 放行建议登记为后续观察（代码变更，超出本轮纯文档收口范围） |
| 3 | corpCode≡applicant.company 渲染值约束只在报错出现 | **已补文档**：plan-contract.md header 行 + travel.md 既有规则互引 |
| 4 | identity/applicant 需 sources 但 schema 文档未列 | **已补文档**：plan-contract.md applicant 行显式"每个值均纳入 sources" |
| 5 | oa_test_relations 真实枚举在只读阶段不可达 | 非缺口，如实记录（合同设计即如此：占位路径需真实填写授权，属 round-7 已验路径） |
| 6 | parsed 对 PDF 全 NEEDS_INPUT 占位、prepare 双根目录须不存在 | 小问题，记观察项，不改代码 |

## 四、白名单纪律审计

- 允许输入仅 5 项（冻结合同/skill+references/模板单号/73 原件目录/合同自带规则），禁止清单（v3r06/v3r07 交付物、CASE-01/02/03 内部 JSON、任何 B 侧内部工件）在阶段一期间未提供；`input-log.md` 逐文件记录（#1–22）。
- **读取范围如实界定（勘误后口径，见 input-log 末尾加法订正）**：白名单 5 项全部命中（#1–9；#11 census 缓存属白名单"环境边界"节预授权项）；此外阶段一另有**三类白名单字面之外的环境/基础设施读取**——①#10 `automation/task-registry/` 11 件 .form.json 只读查询（为核对既有 task_id 冲突；经独立复核与 mc-expert 终审双重核实：表单仅含 task_id/plan_sha256/operator/mode/state/run/attempt 等任务身份元数据，**无任何本案事实、金额、票号或结论**，不构成对零上下文边界的污染，但确属白名单字面之外的读取，如实登记）；②#12–15 验收员自产工件与 73 原件的机读提取（rendered/pdf-text/xlsx 盘点/其自身 --task run 产物，非禁读交付物）；③#16–17 仓库工具与配置源码（fill-plan.schema.json/bpm_plan.py/travel.json 等，代码非数据，用于校验契约核对）。input-log 原句"`automation/task-registry/` 未查询"与 #10 自相矛盾，已加法订正。
- 比对用交付物（已交付 v1.0、B5 回读、CASE-03 对照、live 快照）在阶段一回报后才逐项标注"仅比对用"提供（#19–22）。
- 零业务写入：CASE-08 全程零浏览器业务动作（模板走 census 缓存）、零保存类点击、零 registry 变更、零旧单修改。

## 五、过程如实记录

- 执行中断一次：agent 撞 GLM 账号级 5 小时用量上限（HTTP 429，19:55:21，重置 21:27:45）；处置=定时等待重置后恢复**同一 agent 上下文**继续（保零上下文继承边界与已核实进展），未由 B 主会话代做其工作。

## 六、验收判定（B 按合同条款 2 签发）

**PASS_DYNAMIC**：新 session 凭 skill 官方入口 + 白名单输入可独立推进到 PLAN_VALIDATED（真实验证器子进程全绿，非纸面自评）；双独立会话零通信收敛同一事实链；差异全部如实记录且无一影响金额或安全边界。skill 缺口处置：4 项文档补丁本轮落地（SKILL.md×1 + plan-contract.md×3 + travel.md 前期 1），1 项行为建议转后续观察。
