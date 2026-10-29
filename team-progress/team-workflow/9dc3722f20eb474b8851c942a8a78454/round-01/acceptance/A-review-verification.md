# A 验收记录（round 1，2026-10-27）

A 窗口（session 210983fd，glm-5.3）对基线 `BPM-COMMON-20261027-V1`（sha256 31f03d44…，join 时冻结）28 项判据的独立验收。全部结论来自本轮 A 自行检查/复算/复跑，不承重引用 B 自述或 ENHANCED_FINAL/走读结论（两者仅作交叉对照）。

## A 侧独立动作

1. **哈希**：复算 handoff 15 个产物 + 11 条 evidence 哈希，全部一致（无漂移）；final-hashes.txt 与 handoff 一致。
2. **测试复跑**：`python -X utf8 -m unittest discover -s tests` → Ran 430 tests, OK (skipped=4), exit 0（A 本机独立执行，非引用）。
3. **offline-verify**：`automation/offline-verify/20261027-192354-draft-build/` build_result=OFFLINE_PASS、430 tests、probe-selftest exit 0；source_manifest 含 `bpm/query.py = d7d6482d…`（最终哈希，覆盖成立；P2-1 勘误后指针正确）。
4. **真实 run 证据**：逐一解析 kw2/tpl2/zero2/creator4—7/dept6—7 的 `query_result.json`（状态/分支/候选/范围/耗时/retries 全字段）；kw2 首候选 UUID `c10c49a2…` 与 tpl2 快照 uuid 相等（列表↔详情身份交叉一致）。
5. **Decimal 闭合复算**：从 `automation/runs/20261027-common-accept-tpl2/template_snapshot.json` 原件独立重算——products 18 行按 purchaser 四组（庄旭宏 1906.80/张宇昂 3079.90/陈晶 3698.90/韩晓 1249.56），Σproducts=Σdetails=Σbanks=totalCost=9935.16，EQUAL；relations/detailrels/costs=0；submitType=11、document_type=rd_materials。
6. **只读与生命周期**：20 个 20261027-common-accept-* run 各恰 1 次 `profile_lock_acquired` + 1 次 `query_close`；events 认证扫描仅 cookie/origin 计数（`session_state_injected/saved`），无 cookie/token/storage 原值；kw2 stage1 `finish_reason=READ_ONLY_QUERY_OK`。
7. **材料入口独立实跑**（A 自备匿名夹具：stats.csv 前导零＋broken.xlsx＋自建文本 PDF，TEMP 隔离目录）：
   - 源缺失 → `PREPARE_REJECTED`（fail-closed）；
   - 正常 → `PREPARE_COMPLETE`：3 文件、pdf_text_extracted=1、CSV `00743001` 前导零保留为字符串、PDF 文本 `A-REVIEW-FX TEXT 001 9935.16` 带 page/bbox/region 且 `source_sha256` 绑定、`extraction_role=raw_embedded_text` 无 reviewed 标记、broken.xlsx `NEEDS_INPUT`（BadZipFile 登记缺口不吞批）、双根 manifest（originals/derived 分离、派生 sources 绑定原件哈希）。
8. **代码/文档审读**：`bpm/query.py` 全文（互斥必填/空条件拒绝/limit 1—20/三分支 OR 合并按 bizNumber+UUID 去重/createdAt 降序并列标记/精确全等前导零/多 UUID 即停/partial≠zero≠failed/expect_response 先注册后点击/查询按钮过 _click_guard/组织选择歧义 fail-closed/禁用确定不点击/finally 只关自建 context 释放自持锁/有界 login_wait）；common-operations.md 六用法与实现逐一相符（含 --research-raw 指引、perf/bpm_chain/collect_materials 范围如实）；purchased-samples.md 七部分/六映射/待补 5 项；五方接线 diff 逐行核对（AGENTS 仅入口短说明；STATE 按快照标准替换并保留自驾 CANCELLED 等未解项；.gitignore 仅追加 tpl2 三文件）；`bpm/materials.py` 仅三处窄改，`collect_materials` 未动；types.py/document-types/browser_probe/login/template/extraction/save/ui/verify 零改动。
9. **边界核查**：tpl2 三个含银行资料文件 `git check-ignore` 命中（.gitignore 792—794）；测试名覆盖 §5 反例清单（query 21 项含 URL 匹配/前缀不命中/凭证不泄露，materials 10 项含保护路径/嵌套/覆盖拒绝/原件零漂移）；分支原始行含 appliedPhone 与已提交历史证据先例一致（HEAD 20261021 run 即有），不构成基线违例；旧 run 242ccba1 归档记录 external-archive-20261027.md 在盘。

## 判据结论（28/28 PASS_DYNAMIC）

C01—C13、BND-01—06、OUT-01—04、ACC-01—04、IMPL-01 全部 PASS_DYNAMIC，证据见上与 review-input.json。

## 遗留（非阻断，B 已在施工结果 §六.5 如实登记）

- P2-4①③：keyword_flow 死变量 / clear-icon dispatch_event 绕 _click_guard（计划 G2 本身要求触发 UI 事件并回读，已满足；守卫为纵深建议）。
- P2-4②：`--snapshot` 遇未登记类别以 traceback fail-closed（不产伪快照、不注册类型），CLI 层缺“指向 --research-raw”的用户可读指引；文档层指引已在 common-operations §2。留待下次触达 query.py 的任务。
- 同名多工号歧义未真实触发（张伟 0 命中构造性证伪；`len(hits)!=1→raise` 守卫路径已经 creator6/7 动态实证）。
- 外购样品 5 项业务口径待本次原件；新业务填写/真实保存未验（合同明确排除，已如实分列）。

以上均不构成判据未达标；按“局部受阻不冒充全部完成”要求已在结果记录与 STATE 分列。
