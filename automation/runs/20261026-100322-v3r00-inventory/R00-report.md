# V3 首轮 R00 接手盘点报告

- workflow_run: d91601924848489f84e317e68582de26 / round 1 / team_run 20261026-095208-a68a0869
- 合同: ctr-08d9de84（minimal，2026-10-26 冻结，fixture 校验 PASS）
- 本报告只登记盘上事实与差距，不预设任何业务金额/票数/公里/单号结论。
- 证据目录：`automation/runs/20261026-100322-v3r00-inventory/`（本目录）；登录探查 `automation/runs/20261026-100537-login60/`。
- 勘误/废弃登记：`automation/runs/20261026-100302-v3r00-inventory/` 为清单首跑（与 100322 版仅 inventory_run/generated_at 两字段差异，其余逐字节同）——**已废弃，以本 100322 目录为准**，保留不删。recovery-result 实际路径为 `team-progress/team-workflow/a7618f4fa0b040fa81782c93eb1bc926/operator-recovery-20261026-v3/recovery-result.json`。

## 1. 调度与归档状态（实物核实）

- 旧 run `a7618f4fa0b040fa81782c93eb1bc926` 归档于 `operator-recovery-20261026-v3/`：`retired-live/.team-workflow-state.json` 实读 phase=B_RUNNING / round=10；`recovery-result.json` status=**RETIRED_NOT_COMPLETED**（非完成；根文件哈希备份于 root-files/，1625 受保护文件前后一致）。
- 活动根无旧 state/task/progress 残留；本轮新 run 已由 helper 正常 init/enter。
- 旧根 handoff/review 属 round 9（已随归档封存），不作 round 10 或本案例通过依据。

## 2. profile / 锁 / 登录 / 身份（本轮唯一浏览器动作，只读）

- **当前无遗留未知活页**：recovery-result quiescence（RETIRED_NOT_COMPLETED、business_execution=false、1625 受保护文件 unchanged）+ login60 run events.jsonl 的 stale 锁接管事件（old_pid=18236 与 recovery `profile_owner_alive=false` 互证，非强删活锁）+ 本轮零业务导航，三者共同闭合；本轮未接管任何未知活页。
- 例行动态核验：`python -X utf8 bpm_login.py` → run `20261026-100537-login60` attempt_001：`c1_entry_login=PASS（Live account verified）`，全部写入检查 NOT_AUTHORIZED/NOT_RUN，`finish_reason=SUCCESS_LOGIN_ONLY`， wall 5.1s；零业务行写入、零保存。profile 锁获取/释放正常（旧 executor.lock 登记 PID 已退出，未强删）。
- 会话记录（automation/.local-session/6f998b92…/session_record.json，探查后原子更新）：principal 陈晶 / user_id 116070053；identity_source=live_authenticated_account_header_and_token_subject（level=header_and_subject）；auth_status=authenticated；last_authenticated/identity_checked=2026-10-26T02:05:42Z（10:05:42 北京）；last_scan=2026-10-24T02:42:25Z；effective_reuse_until=2026-11-23T02:42:23Z（refresh token 声明，服务端最大不可知）；company/department/default_creator/default_applicant=null（未观察到）。
- 未观察组织/默认人员字段保持 null；后续轮真实新页再核对制单人/申请人分层。

## 3. task-registry 盘点（只读，10 条）

全部 state=FORM_INTENT；**无 SAVE_INTENT / SAVE_UNCERTAIN / 保存成功记录**（逐份扫描 save* 键均空）。明细：

| task_id | run | state |
|---|---|---|
| 20261023-user-complex-history-demo-15426093015 | 20261023-live-complex-demo | FORM_INTENT |
| type-replay-20261023-express-complex-R1 / R2(-defaultbank) | types-express-complex-R1/R2 | FORM_INTENT |
| type-replay-20261023-rd-complex-R1 / R2-namepicker | types-rd-complex-R1/R2 | FORM_INTENT |
| speedup-20261023-C0controls01 / C1 | 20261023-speedup-C0controls01/C1 | FORM_INTENT |
| 20261024-r7-travelloop-15426093015 | 20261024-163009-3250e7d0 | FORM_INTENT |
| 20261024-r8-expressloop-15426094780 | 20261024-173807-72170651 | FORM_INTENT |
| 20261024-r8-rdloop-15426104120 | 20261024-174803-cd2e04e4 | FORM_INTENT |

## 4. r10 在途变更三态表（代码 / 测试 / 证据冻结）

| r10 子项 | 代码已落地 | 测试已配 | 证据冻结 |
|---|---|---|---|
| verify_bpm_build source_manifest 五类型（02/04 config+notes 入清单） | ✅ `verify_bpm_build.py:24-27` 显式列 office_supplies/welfare_labor json+notes；根 `bpm_*.py` glob 自动纳入新模块（bpm_chain.py 在根） | ✅ tests/test_bpm_round10_sync.py::ManifestSyncTests | ✅ 本轮唯一 offline-verify run（§6 实读：manifest 60 键含五类型 config+notes） |
| fill-plan.schema.json document_type/submitType enum 五类型 | ✅ schema:31-38 五类型 enum；allOf 分支五类 | ✅ SchemaEnumSyncTests（含 officeloop/welfareloop r9 计划过 schema） | ✅ schema 在 manifest 内随构建冻结（哈希绑定） |
| bpm_extraction 一页多票显式拒绝 | ✅ bpm_extraction.py:220-232（≥2 互异发票身份→GAP 登记，不拆分不静默取首张） | ✅ test_bpm_round10_sync.py（多票断言拒绝）+ test_bpm_extraction.py | ✅ 同上（模块哈希入 manifest） |
| bpm_chain.py 链产品化 + 四类 validate-only | ✅ 根模块存在（manifest glob 纳入，哈希抽验匹配） | ✅ tests/test_bpm_chain.py | ✅ 四链工件绑定已核实（§5） |
| **02/04 config required_observations 回填 + notes.md 修订** | ❌ **未落地**：两 config 的 required_observations 仍为 round-9 待观察声明；notes.md 仍止于 round-9（“真实新页控件观察未做”），无 attempt/213500/round-10 指针 | —（属文档回填非代码） | ❌ 遗漏登记：**该文件不在本轮授权写面，移交下一轮**（类型接入工作包），本轮分类先落总台账（§7） |

- 在途未提交变更（git）：M=SKILL.md/.gitignore/AGENTS.md/README.md/报销类型盘点/fill_once.py(+296)/stage1_browser_probe.py(+99)/stage1_probe_selftest.py(+35)；D=旧根 handoff-input.json（已归档）；?? 含 automation/document-types/、fill-plan.schema.json、bpm_chain.py、runs/offline-verify 工件。默认不 commit、不回退。
- 全量单测：`python -X utf8 -m unittest discover -s tests` → **Ran 282 tests, OK (skipped=4)**（2026-10-26 10:06，当前在途字节）。

## 5. 四链工件绑定核实（复用，不重跑）

`automation/runs/20261024-211000-chain-r10-{travel,express,office,welfare}/chain_result.json` 逐份实读并重算 fill_plan.json sha256：

| run | document_type | synthetic | plan sha256 重算 | validate_only | browser |
|---|---|---|---|---|---|
| travel | travel | false（授权回放） | ✅ 匹配 | true | false |
| express | express | false（授权回放） | ✅ 匹配 | true | false |
| office | office_supplies | true（合成） | ✅ 匹配 | true | false |
| welfare | welfare_labor | true（合成） | ✅ 匹配 | true | false |

均 CHAIN_COMPLETE；operator=陈晶（system_observation，会话记录实测注入）。四链保持为 **JSON 回放/合成 validate-only 入口证据**，不是真实 PDF/Excel 用户入口（V3 §2.1 口径不变）。

## 6. 唯一 offline-verify 构建（本轮证据冻结，实读结论）

- 命令：`python -X utf8 verify_bpm_build.py --run materials-v3r00-20261026-101500`；产物 `automation/offline-verify/materials-v3r00-20261026-101500/`。
- build_result.json 实读：**status=OFFLINE_PASS**；probe-selftest exit 0（4.4s）；capability-tests exit 0（**273 项**，118.2s）；`real_fill_verified=False` / `real_save_verified=False` / `production_access=False`（fill_only 口径如实；登录探查另有独立 run 证据，不属本构建）。
- source_manifest.json 实读：**60 键**；16 项必含（五类型 config+notes、bpm_chain.py、bpm_extraction.py、verify_bpm_build.py、两 schema、skill SKILL.md+references、fill_once.py、stage1_browser_probe.py）**全部在列**；**tests/ 22 项入清单**；哈希抽验（bpm_chain.py、office_supplies.json）与盘上字节一致。D23 口径（manifest 覆盖当前实际代码/schemas/五类型 config/skill/相关测试）以本构建冻结闭环。

## 7. 02/04 观察分类（入总台账；不重跑整套观察）

实测工件：`automation/runs/20261024-213500-type0204-observe/attempt_007/evidence/observe_result.json`（status=OBSERVED；纪律=只读控件观察/零业务行/零保存/页弃置）。

**已实测（复用为 config 依据，下轮回填）**：
- submitType 38 项枚举（含“差旅费”“低值易耗品、办公用品采购”“福利费、劳保用品”等）；
- 类别联动后 8 表结构（关联单据/关联单据明细/报销明细/费用说明/银行信息/确认人/审批记录/附件；列 props 全量）；
- reimItem 枚举：02=〔培训费/业务招待费/其他/办公费〕5 项、04=〔宿舍费用/食堂费用/住房补贴/团建费/员工福利〕6 项；reimItem 行编辑器=dropdown（完整选择器已存 row_editors_after_reim_02.json）；
- 关联单据类型枚举 20 项（**含“公出单”“出差单”**——CASE-03 公出单模块查找的既有枚举依据）；
- header 编辑器形态与默认值（appliedName=陈晶 只读等）。

**未解（留类型接入工作包，不阻塞公出案例主线）**：
- budgetNo / subjectName 选择器 `mode=table_dialog, status=NO_TABLE_DIALOG`（02/04 同）。既有工件内定位已穷尽：tables_02.json 仅含列定义（预算部门/预算单/预算归属/预算科目为报销明细表列），行编辑器证据只捕获了 reimItem；无法从现有证据确定 dialog 未弹出的根因，需新假设下的局部复测（下轮授权内决定）。
- **遗漏登记**：r10 计划的“观察结果回填两 config required_observations + notes.md 修订”未执行（§4 末行），交下一轮。

## 8. 真实公出案例供料盘点（只读；不预设业务结论）

- 逐件清单：`case-file-manifest.json`（73 文件 / 3,281,451 字节 / 每件 sha256；生成器 v3r00_case_manifest.py 同目录）。
- 分组：10 日期组（0825:6 / 0904:6 / 0906:8 / 0917:8 / 0928:8 / 1028:6 / 1112:6 / 1124:6 / 1204:6 / 1210:7）+ 油票:5 + 根 xlsx:1。
- 结构观察（文件名层面，非票面事实）：每组=厦门↔晋江两方向“发票”+“通行费电子票据汇总单(票据)/(行程)”（含编号变体）；0906 目录内文件名带 0905；1210 含 `晋江-厦门1 (2).pdf` 疑似重扫；0917/0928 汇总单编号错位（(票据)/(票据)1、(行程)/(行程)2）。**目录/文件名不作期间证据**。
- 字节级查重：73 件 sha256 全唯一，无同字节副本；4 个同尺寸簇（模板同尺寸，内容待 CASE-01 逐票核身去重，不能按文件数计票数）。
- Excel 结构（只读，`excel-structure/inspect_excel_report.{json,md}`，inspect-excel-template COM 只读探针）：单 sheet `汇总`；行1 标题（合并）、行2 空、**行3 表头**：序号|时间|出发地|目的地|公里数|补贴金额(油车1元/公里 电车0.15元/公里)|过路费(据实)|合计|备注（A–I 列，J 为备注合并扩展）；数据行 4–24 左右，**去/返成对**（预览：序号1 2025-12-10 厦门总部↔泉州新刚鞋材 73km×2 行，补贴=公里×1；序号2 2025-12-04 厦门总部↔乔丹二厂 76km；序号3 2025-11-24 …）；H 合计列数据行空；G 过路费列数据行以 JSON 公式/值细查为准（--blanks 层显示 G4–G24 非空候选，需下轮逐格核）；行 25–38 空尾行；**stray 警告系标题行布局误报（主块启发式假设行1表头）——后续轮严禁按其建议“清理”任何单元格**。空 183/已填 117（61% 空，含未填过路费/合计列与空尾行）。
- **模板身份：登记缺口**。检索范围=冻结 V3/V2/V1、2026-10-24 任务书、feature01 全部 md：均未出现本案例的用户指定完整模板单号。已知单号（15426093015 差旅 r7 回放、15426094780 快递、15426104120 研发、15426095951 tpllive 只读、15426104612 提速观察）均为历史用途，**不能冒充本案例指定模板**。本案例类别归属（差旅费分支）与模板号须由用户明确或后续轮从原报销单上下文核实后定案。

## 9. 真实案例 vs 现有模型差异清单（后续 CASE 施工输入）

机器可读版：`case-model-deltas.json`。要点：

1. **金额模型**：R=M+T（K 公里×1 元+真实通行费）；覆盖校验 F=O+T **严格大于** R。现有 reconcile=票面全额分配闭合 → 需新增“票据覆盖（池）”分支，与普通全额分配分开建模（配置/schema/计划验证/独立核验一致），不得放宽通用约束。
2. **油票角色**：仅作覆盖（O），不加报、不进费用行、不参与逐票公出对应；现有“每票分配费用行”模型不适用。
3. **汇总单语义**：通行费电子票据汇总单(票据)/(行程)=汇总验证层，与独立发票不得相加；需显式映射到现有 汇总层 vs 明细层 校验。
4. **工作簿回填**：同结构副本回填 G 列过路费 + H 合计可靠重算（保留原公里数/公式语义，行3 表头/去返成对/空尾行结构保持）；现有 xlsx 链路只有读侧，写副本为新能力。
5. **公出单模块逐票查找**：全新只读查询能力；关联类型枚举已实测含“公出单”（§7）。
6. **两套关联数据分离**：`actual_trip_matches`（真实逐票对照，交用户）与 `oa_test_relations`（test_placeholder 随机可选占位，仅本案例 fill_only）分开建模/核验/报告。
7. **日期期间**：Excel 时间列含真实日期（预览见 2025-11-24/12-04/12-10 等，倒序）；文件夹组（0825…1210）与文件名须逐票对票面通行日，开票日≠通行日，不猜年月。
8. **fill_only 全程**；不测保存/新单号/重开/持久化。

## 10. 本轮未做 / 移交下一轮

- 02/04 config+notes 回填（授权面外，§7）。
- 票面内容级提取/去重/金额核对（CASE-01）、Excel 副本回填与重算（CASE-02）、公出单模块查询与逐票报告（CASE-03）、覆盖分支实现（CASE-04）、正式链与真实填写（CASE-05/06）、独立验收（CASE-07/08）。
- 模板身份缺口闭合（用户明确或原报销单上下文核实）。
