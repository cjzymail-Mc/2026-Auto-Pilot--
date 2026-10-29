# 外购样品手册独立走读报告（CP7，2026-10-27）

走读者：一次性只读 Explore agent（本轮主施工者之外的眼睛；不另起浏览器、未读认证文件、未改任何文件）。范围：purchased-samples.md、common-operations.md 全文，SKILL.md 路由/日常入口两节，入口与未来扩展说明登记表，rd-materials.md 全文；另抽查全部被引命令/API、证据目录与链接目标。

## 结论摘要

- 事实核对：common-operations.md 全部命令/API 存在且签名一致（bpm.query 参数/互斥/默认值、materials prepare、FactSet/reconcile、build_reuse_matrix、generate_fill_plan、validate_plan/file_hash、fill_once 参数链、verify_snapshot、perf 的 UI_START 口径、LoginProbe/fetch_template/observe_template_view/bpm_template 五参数、collect_materials 票种边界、StructuredProbe/capture_snapshot、bpm_chain --document-type choices）。
- purchased-samples.md §3 实证声明与 `automation/runs/20261027-common-accept-tpl2/template_snapshot.json` 逐项吻合（submitType=11、products 18 行字段 code/name/purchaser/price、details 4 行摘要「<购买人>外购样品费」、relations/costs 空、按 purchaser 分组合计=Σ明细=totalCost=9935.16 Decimal 闭合）。唯一 CANNOT_VERIFY：「附件 25 个」来自页面观察而非快照字段（旁注性质，文档自标「仅证存在性」）。
- 相对链接全部指向存在文件；SKILL/入口说明/rd-materials/手册四方路由与能力分层口径一致。
- 五问 Q1—Q5 全部 PASS（链路无断点；停点无绕过；不支持场景可识别；缺口具体不诱导虚构；原路由保留）。
- **must_fix：无**。建议级 2 条（已由主施工者采纳修订，见下）。

## 走读时点哈希（修订前）

- purchased-samples.md：`73993a8b69d2f0c0dcd5058635a07fb28f610872ddedd81ccebc10fa96121f34`
- common-operations.md：`7f828fece3209c8dcbda9caf3bef5ff9d5790657c7a64e8489aace9b4aa243f2`

## 采纳的建议级修订（主施工者执行，复核后以修订版哈希为准）

1. SKILL.md 路由行判别特征「现有档案行金额＋按购买人归组」→「外购样品业务证据＋按购买人归组」（原特征前半是 rd_materials 通用特征，非本场景判别点；§1 严格门本就兜底）。
2. purchased-samples.md §5.4 就地补 [plan-contract.md](../../../.claude/skills/bpm-fill-run/references/plan-contract.md) 显式链接（计划形状/blueprint 出处，不再仅靠跳转链推断）。

修订版最终哈希见同目录 `final-hashes.txt`（ENHANCED_FINAL 前实算）。test_skill_docs.py 修订后复跑通过。
