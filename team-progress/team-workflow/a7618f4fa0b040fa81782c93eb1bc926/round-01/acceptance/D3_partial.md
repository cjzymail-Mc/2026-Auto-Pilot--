# Round-1 A 验收证据：D3 部分核验（核心已验、判据整体未达）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

## 已验证核心（W02 双根契约）

- `bpm_materials.py`（sha256 ac94d926… 对账一致）：DUAL_MANIFEST_VERSION="2.0"；DERIVED_ROLES 封闭枚举（parsed_extraction/reviewed_extraction/ocr_result/render/run_evidence）；DUAL_PROOF_KINDS=(material,user,agent_reviewed)；validate_dual_manifest / register_derived / prepare_dual_materials / dual_hash_sets 在位。
- 根边界：register_derived 用 `_safe_material` + `is_relative_to(derived_root)` 拒绝根外路径与重复注册（L245-247）；v2.0 校验要求 originals_root/derived_root 互不嵌套。
- 来源语义：agent 生成物仅可 corroborate 为 agent_reviewed，且必须哈希匹配某派生工件（L418-419）；kind 不再静默默认 user（B2 差距闭合）。
- 旧契约兼容：v1.0 路径不变、可读（测试 test_v1_contract_still_readable 过）。
- 独立复跑 7/7 OK（见 D23.md）。

## 判据整体判定：FAIL（尚有未达子句）

D3 原文含"按内容哈希盘点文件，**区分原件、重复副本、统计表、发票、结算凭据、说明及其他相关材料**"。当前 prepare_dual_materials 完成内容哈希盘点与重复副本识别（dual_hash_sets），但**语义类别区分**（统计表/发票/结算凭据/说明）属 W03 原件理解，未实现。

→ 本轮签 FAIL（非缺陷，为按计划未达范围）；W03 落地后转 PASS 复核。证据：本文件 + progress.json W03="待做"。
