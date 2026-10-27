# CASE-08 对 bpm-fill-run skill 的可操作性评估（阶段一，零上下文继承视角）

评估人：CASE-08 独立验收员（冷 session，仅凭 SKILL.md + references/ + 冻结合同 + 原件）。只评文档可操作性，未改任何代码。

## 能跑通的部分（有效设计）

1. **入口链路自洽**：`fill_once.py --task`（NEEDS_INPUT/MATERIALS_READY）→ 人核材料 → 自组 v1.0 `--fill-plan --validate-only` → PLAN_VALIDATED，全离线、零浏览器、守卫语义清楚。冷 session 可仅凭 SKILL.md 复现。
2. **证据语法闭环**：sha256 逐值绑定 + locator（json pointer / csv 行列 / xlsx 单元格）+ derived 只许显式 sum + template 历史字段黑名单 + digest 必须 material/user——把"编数字"的路基本堵死；本次 0904 视觉误读正是被"汇总单+机读双 locator"纠出的。
3. **双根材料 v2.0**（originals 只读 + derived 抽取/事实工件）解决了"PDF 无法直接当 locator"的问题，`register_derived` 幂等注册好用。
4. **coverage 块**（fuel_pool_strict_surplus）与 `evaluate_coverage` 纯函数复算是本案命脉：K×rate=M、R=M+T、F=O+T、F>R 严格门槛在一处声明、两处独立校验（构建期断言 + validate_plan），覆盖富余不加报的分离原则在 schema/验证器/事实工件三层一致。

## 卡点与发现（按影响排序）

1. **冷启动没有"PDF 票面机读"指引**：SKILL/references 引导走"渲染 PNG→视觉读取"，但电子发票 PDF 均有文本层，`fitz` 一行即可确定性取票号/金额。视觉通道幻觉率高（本轮 3 次翻车：0906 家族幻觉、0904 票号误读、0928 四读同号串扰），若非坚持"汇总单互证+机读复核"极易出错账。建议 skill 增加"优先文本层机读、视觉仅补缺"条款。
2. **digest 的 material/user 限制与可用 locator 现实错配**：原件里可作 digest 的字符串只有 xlsx 表头单元格（F3"公里数"、H3"过路费\n（据实）"），导致计划 digest 被迫带换行符、语义打折。建议为 digest 放行 `agent_reviewed`（或提供"digest 措辞白名单"工件角色）。
3. **applicant.company ≡ corpCode 渲染值**这一约束只在报错里出现（IDENTITY_MISMATCH "rendered company must match applicant.company"）；本 OA corpCode 显示值是 "1003" 而非公司名，冷 session 需要一次试错才能发现。建议写进 references/travel.md。
4. **identity/applicant 字段需要 sources 但 schema 文档未列**：同样是跑一次才报 SOURCE_MISSING；模板快照 locator（/applicant/appliedBy 等）可用但无文档。
5. **oa_test_relations 占位路径**（本案例合同允许）需要真实枚举+填写授权，阶段一只读边界内不可达——非缺口，如实记录：真实逐票公出单对照仍待阶段二（另表建模，不与占位混淆）。
6. 小问题：parsed/*.json 对 PDF 全是 NEEDS_INPUT 占位（无文本层抽取），--task 产物对 PDF 类材料帮助有限；`prepare_dual_materials` 输出目录必须不存在（重跑要手工清理）。

## 结论

skill 契约本身可独立操作到 PLAN_VALIDATED（本案实证）；主要改进空间在"机读优先"指引与 source 约束的文档化。
