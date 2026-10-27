# Round-5 A 验收证据：D2 / D13（翻转）/ 维持项

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。方法：13/13 工件哈希对账 + 独立复跑 + 代码面 + 红线核验。

## D2 模板身份与逐字段复用 — PASS_DYNAMIC（自 FAIL 翻转）

- `bpm_request.py`（sha256 e1206c9b… 对账一致）代码面：`resolve_template` 缓存定向唯一命中，快照 uuid/applicant/header/corpus path+sha 留证；声明类别与模板矛盾 → `category_mismatch` 集中报告（L153），`declared_category_unregistered` 不悄悄换类；normalize 先抛非类别错误回查原始 doc 判根因。
- `build_reuse_matrix` 六字段组封闭规则（DECISIONS=adopt/replace/identify/not_applicable，L47）：form_identity 仅 identify；stable_context adopt 须依据+旧年度预算须 user_policy 确认；current_person 不被模板历史人员覆盖；current_business/proven_references 禁模板来源；empty_tables 只 not_applicable 带理由；adopt/replace 必绑 fact_id+fact_field 显式映射+字段级 locator。
- 独立复跑 test_bpm_request.py **19/19 OK**，含三冒充反例（模板旧金额冒充本次值 / 旧年度预算无确认沿用 / 模板历史申请人覆盖）与矩阵 blueprint→generate_fill_plan→validate_plan(verify_sources=True) 空 issues 贯通。
- 全量 **218/218 OK**（111.7s，190 基线零回归）。快照哈希绑定（travel/express 模板事实补快照哈希）由前置门 3 强制。
- live OA 模板读取属 W06 浏览器轮；本轮缓存路径判据成立。

## D13 未知模板只读识别 — PASS_DYNAMIC（自 FAIL 翻转）

`identify_unknown`（L182-213）：观察类别/注册对照/不支持部分/结构证据/登记开发子任务建议，**writable=false** 硬编码；resolve_type/build_reuse_matrix 写入路径全拒；明确"不得映射为任何已注册类别绕过（含『其他费用』语义）"。未知识别+写入拒绝有单测（resolve_template UNSUPPORTED 分支 L131/138 双入口）。

## R4-P2 四条闭合确认

`bpm_facts.py` 抽取 `_validate_fact_invariants` 由 add()/from_payload 共享（6 反例含 FORBIDDEN 字段反序列化拒绝）；`expect_money` 缺 amount 键显式失败；前置门 3 拒绝无 input_hashes 的被绑定事实（拒绝而非自动补绑定）；_dec 正例断言真实量化结果。均在 218 全量内由 A 复跑覆盖。

## 维持 PASS 复核（要点）

- **D14**：W00-W05 六包已验证，主线完整；next=W06。✔
- **D15/D16**：单执行者+fresh ENHANCED_FINAL GO（15 件双轮重算、stage1_browser_probe.py 与 fill_once.py 与 round-4 冻结值逐字节一致）；交接五项齐备+R5-P2 三条挂账。✔
- **D17/D21/D26**：零网络零浏览器（ENHANCED_FINAL 复核+构建 production_access=False）；守卫文件字节级未动；HEAD 9299545；registry 安静。✔
- **D24/D27**：台账 W01=已验证（7 证据项）+round-5；八类真实材料缺口如实。✔
- **D23**：glob 机制持续生效——manifest 51 键自动含 `bpm_request.py` 且哈希==盘上（A 直接核验）；DERIVED_ROLES 显式扩 user_request/decision_matrix 属受控契约演进。维持 PASS，failure_counts 1/3 不新增。
