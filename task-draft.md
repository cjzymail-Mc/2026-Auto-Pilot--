# 本次任务

BPM-SELFDRIVE-20261027-V1 round 2（承接 round-1 review `174e9324…` 派工）：**D02 30 天会话迁移 + D04 识票归集正式化 + R1 遗留约束机制化/清污**。本轮全部离线；预计零浏览器动作（如确需只读探查，按 AGENTS 入口单执行者错峰）。A1 增补（BPM-SELFDRIVE-20261027-A1：日常真实任务自动保存草稿）本轮**不实施保存改造**，属 round-3 入口接线；本轮只落 §2(4) 口径纠正记录与身份关系字段。

## 范围

1. **D02 本地复用 60→30 天迁移**（合同 §4.1/§6.2/D02）：
   - `bpm_session.py`：`REUSE_DAYS` 60→30 新默认；旧合法记录生效窗口 = `min(原合法窗口, last_scan_at+30天)`——未满 30 天不拒、恰满/超过失效、更短旧窗口不延长；保留扫码起点/profile_id/session_generation；缺可信扫码时间旧状态仍保守 24h；不凭 mtime/补写续期；读取判定、非扫码探查写回、显示期限同一口径。
   - `stage1_browser_probe.py` 仅在期限判定/提示一致性所必需时改（`SESSION_TTL`/`_session_state_usable`/`_inject_session_state`/`_save_session_state` 链同口径）；保留 600ms 轮询、Tab 失焦、重复回读；改探针先 `python -X utf8 stage1_probe_selftest.py` 全绿再收尾。
   - 测试族（离线模拟即可，真实登录后续轮验证）：复用 `tests/test_bpm_session.py`、selftest `_t8_session`/`_t10_login_only`；补旧 60 天记录第 29/30/31 天三档、原 7 天不延长、更早 refresh token 到期、未知到期、缺扫码时间、mtime 改动、非整数/未来扫码/坏 schema 拒绝、探查写回不续期、写回与显示一致；既有两人/同名/账号切换/缓存身份不符用例保持通过。
   - 长期说明同步：`.claude/skills/bpm-fill-run/SKILL.md` 与 `AGENTS.md` 中"60 天"改"30 天"（只改规则行与链接，不写案例答案或流水账）。
2. **D04 识票归集正式化**（合同 §4.2/D04，全离线）：
   - 新增归集模块（建议 `bpm_collect.py`，职责清晰即可）：对 `feature01-细化报销skill/12月公出-发票/` 73 原件**只读**识别——PDF 文本层优先（PyMuPDF 逐页/bbox），无文本层页按仓库视觉路由复核，不上传第三方 OCR；逐页分类（发票/汇总单(票据/行程双版式)/油票），多票容器按页/区域分件取证（唯一 record_id + 原件页/区域定位；保留 `bpm_extraction.extract_pdf_facts` 多身份拒绝保护，分件后逐票调用）；规范命名 `日期_票种_方向或路线_票号_短哈希.pdf` 平铺**整理副本**到新 run 目录（缺字段按明确规则，不猜值、不覆盖、防重名）；原件↔原哈希↔唯一票据身份↔副本名/哈希可逆映射；同票不同扫描去重、同金额不同票不合并；同一输入重跑幂等。
   - **下游同步**：`bpm_facts.add_invoice_from_extraction` 与 `bpm_plan_generate` 现存 `records[0]` 路径改为完整处理多 record（上游分件成功后下游不得只读第一票）；`validate_reviewed_extraction`/`validate_image_documents` 既有对账承接。
   - 汇总单仅交叉核对不计费；开票日期/行程日期/目录日期分开；票号/金额机读+汇总单互证。
   - 测试：合成多票/重名/重复扫描/漏票负例 + 真实材料确定性产物（映射清单哈希入 run 证据）；若内容识别与既有 27 票核实清单有出入，如实列差异报告，不为凑数改判。
3. **P2-2 机制化**（MC-R1 P2-2）：生产路径调用 `evaluate_self_drive` 必须显式绑定 `rules=load_self_drive_rules()`——新增测试固化（扫描生产模块源码中的调用点，未绑 `rules=` 即测试失败）；`bpm_self_drive.py` 本体语义不变（None=原始计算器口径仅限测试）。
4. **P2-3 案例答案清污**（用户 2026-10-27 裁定，D12 前置）：`bpm_self_drive.py` docstring 三处（L143 真实公出单号 12025092018、L262 437.18、L282-283 日期反例值）改为不含案例值的通用表述；`.claude/skills/bpm-fill-run/references/express.md:5` "系统默认陈晶"改为不预设姓名表述；随后生产面（bpm_*.py、automation/business-scenarios/、skill 全文、verify_bpm_build.py）grep 复扫对照值/真实单号/人名/案例日期并落扫描记录（目标零命中；测试目录与 run 证据目录除外）。R1 已冻结产物（含旧版 `bpm_self_drive.py` 哈希）不改写历史，仅前进式修改当前文件。
5. **§2(4)/A1 口径纠正记录 + 身份关系字段**（用户 2026-10-27 两条指示）：
   - 新设计修订记录（不改 R1 冻结的 p1-entry-design.md）：能力检查层 capability_layers 只作**如实分层报告**，不作为对已获当次 `save_draft` 授权保存的入口拒绝条件；保存许可以"当次请求意图 + 同 task_id 授权 + 现有 SaveController 保护链"判定；本历史占位案例（已占用公出单+占位关联）强制 fill_only 不变，不为补真实保存证据造单。
   - 请求/事实层新增字段与校验（离线）：区分 登录操作人/新页制单人/费用所属人，记录来源；餐补 C 仅在本次报销单真实制单人身份合法成立时按其参与日计——**不为套用案例对照值换人、不默认零餐补**；身份关系不成立时作为真实缺口按 NEEDS_INPUT/外部认证条件上报并留证（当前探查身份与本批费用所属人不同，属已知风险，只读核实，不阻塞本轮独立施工）。schema 联动（`automation/task.schema.json` 等）按需最小增改。
6. **验证纪律**（用户 2026-10-27）：全量回归**单次运行即捕获日志与退出码**（如 `python -X utf8 -m unittest discover -s tests -v > <offline-verify>/<run>/capability-tests.log 2>&1; echo exit=$?`）；已通过且无新变化不重复全量。改探针先 selftest 全绿。`python -X utf8 verify_bpm_build.py` 纳入本轮全部新文件并 OFFLINE_PASS。

## 保留项与红线（本轮不做/不变）

- 零业务写入：不新建报销页、不填写、不保存、不上传/贴票/审批；A1 保存实施、真实串联、公出匹配、Excel 回填、runbook 修订、D12 冷启动均属后续轮。
- `bpm_save.py`、`bpm_coverage.py`（旧模型）零改动；`_click_guard`/锁/registry/保存边界不放宽；`automation/task-registry/`、旧 runs、冻结 V3、`legacy-ia2/`、原材料目录只读（原件 73 件哈希收尾盘点零漂移）。
- 案例对照值（1924.93/300.00/2224.93/437.18/真实单号/案例日期）只存在于合同 §5/§6.1 授权的离线测试；任何 STATE/合同/案例答案不得进入未来 D12 冷启动输入（本轮清污即其前置）。
- 旧失败 key `review|content|source_manifest_coverage|D23`、`review|content|active_output_semantics|D22` 历史计数原样承接；不清理 registry、不换 task_id。
- 全局 team-workflow/helper、settings/hooks、权限策略、部署发布不在范围。

## done_when

1. `bpm_session.py` 30 天迁移落地：新默认+旧记录收紧规则实现，边界测试族全绿（第 29/30/31 天、更短旧窗口、更早服务端、缺扫码时间、mtime、写回不续期、显示一致），探针（若改）selftest 全绿；SKILL.md/AGENTS.md 60→30 同步。
2. 识票归集模块 + 73 原件只读归集产物落新 run：可逆映射、去重、幂等、防覆盖、多票分件与下游 `records[0]` 同步均有测试与真实产物证据；识别差异（若有）如实列报。
3. P2-2 强制绑定测试固化并通过；P2-3 三处 docstring + express.md 身份表述清除，生产面复扫记录落档且零命中。
4. §2(4)/A1 纠正记录与身份关系字段/校验/测试落地（不改 R1 冻结件、不实施保存）。
5. 全量 unittest 单次运行日志+退出码捕获、verify_bpm_build OFFLINE_PASS 新文件入源清单、events 零业务写入、原件零漂移收尾盘点；STATE.md 按维护标准更新。
