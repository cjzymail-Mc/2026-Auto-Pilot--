# ENHANCED_FINAL 终审判决存档（CP8，2026-10-27）

一次性新鲜 mc-expert（无上游结论输入）对 manifest v3 的 15 个冻结产物按 review-contract-v2.md 审计。信封：MEDIUM/USER/GLM_ALLOWED/ARTIFACT_MANIFEST v3/UNVERIFIED_SCOPE=NONE。本文件为 reviewer 输出原文存档（含其审计过程叙述）；哈希绑定对象为同目录 enhanced-final-manifest.txt v3。

## 审计过程叙述

按契约 §4 从最终产物与原始证据出发独立复核，未采信作者自核表与走读结论：

1. **哈希双算**：开审时与收审前各实算一次 manifest 全部 15 个 SHA-256，两次结果一致且与 manifest v3、`team-progress/team-workflow/9dc3722f20eb474b8851c942a8a78454/round-01/final-hashes.txt` 完全一致，无漂移。
2. **产物原文**：通读 `bpm/query.py`（511 行全文）、`tests/test_bpm_query.py`（21 项）、`tests/test_bpm_materials_cli.py`（10 项）、`bpm/materials.py` 新增 CLI 段、两份新手册、STATE.md、结果记录、team-task.md 冻结合同与施工计划；五份接线文档用 `git diff` 逐行核对（SKILL/入口说明/rd-materials/AGENTS/repository-layout，改动与声明一致，无越界、自驾路由行及暂停声明原样保留）。
3. **原始 run 证据**：直接解析 9 个验收 run 与 11 个失败链 run 的 `query_result.json`/`events.jsonl`；三个 fail-closed 阳性对照（creator6/creator7/dept7）逐一确认状态为 SCOPEFILTERERROR、`query_s=null`（查询未执行）、候选空、不点击禁用「确定」——是真失败被安全拦截而非成功；20 个 run 全部 `profile_lock_acquired=1 / query_close=1`（单锁单浏览器）；events 仅含 cookie 计数无认证原值；kw2 stage1_result 的写类检查全部 NOT_AUTHORIZED。
4. **独立复算与复跑**：`python -X utf8 -m unittest discover -s tests` → **Ran 430 tests, OK (skipped=4)，exit 0**；`bpm.query --help` 与 `bpm.materials prepare --help` 实测可用；公共参考引用的全部 API（FactSet/reconcile/build_reuse_matrix/generate_fill_plan/validate_plan/file_hash/collect_materials）grep 核实在库；tpl2 快照 sha256 复算一致（4efaf3a0…），并从原始快照重算按购买人归组 Decimal 闭合（张宇昂 3079.90/韩晓 1249.56/陈晶 3698.90/庄旭宏 1906.80，products=details=banks=totalCost=9935.16 全等）、submitType=11、18 档案/4 明细/4 银行/关联 0——结果记录 §四实证声明逐项属实；dept6「appliedDeptName 精确匹配」在分支响应原件 `keyword_Description15_response.json` 首行得到证实。
5. **offline-verify 取证**：184250/190917/192354 三目录 build_result 均 OFFLINE_PASS 430 tests，但 **184250 的 source_manifest 中 query.py=62b28860…（旧哈希），192354 = d7d6482d…（最终哈希）**——envelope 声明的覆盖关系属实，而冻结果记录 C08 引用的是已作旧的 184250（见 P2-1）。
6. **封印决策**：STATE/SKILL/结果记录三处均保留自驾 CANCELLED 与「不自动恢复」表述，续作入口要求用户显式新任务；未发现任何恢复/改写痕迹，无 P0。
7. **银行资料卫生**：15 个 manifest 产物零银行数据；真实账号仅存在于 tpl2 的 `template_snapshot.json`、`template_view_observation.json`（及按当日分级口径默认仅本地的 `template_view.png`），三者 `git check-ignore` 全部未命中且 git 未跟踪（提交属后置人工门）——见 P2-3。

## 固定输出

```text
REVIEW_PROFILE=ENHANCED_FINAL
AUTHOR_RUNTIME=CLAUDE_GLM
ADMISSION=ADMITTED
REVIEWED_ARTIFACT=bpm/query.py SHA256_BEFORE=d7d6482dfc20b1f7413a1feda7ce48ce2f86d3afa40df2c7fb72b0caa3581c1f SHA256_AFTER=d7d6482dfc20b1f7413a1feda7ce48ce2f86d3afa40df2c7fb72b0caa3581c1f HASH_VALIDITY=VALID（15/15 双算一致，含 team-task.md=4a5f388e…）
REQUIREMENTS=team-task.md SHA256=4a5f388ee914fb0b4dfe5f30aeb9989e1e65fccb226017ac2af70a5f350c6f83（src-b25a30da + 冻结合同 ctr-a820e88c 全文在档）
KB_INDEX=D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/.agents/mc-expert-common/review-contract-v2.md
KB_EVIDENCE=上述 contract；D:/Downloads/Mc Claude Code Workshop/Mc-Expert-repo/MEMORY.md（本次以 contract 为主轴即可闭合，无需深挖源 repo；无 KB 补洞项）

CHECKS
- object_binding: PASS_DYNAMIC  15/15 产物直接打开+开审/收审双算哈希，与 manifest v3 及 round-01/final-hashes.txt 三方一致；C01—C13 逐条对照原文与原始工件，非转述。
- lifecycle_identity: PASS_DYNAMIC  src-b25a30da/ctr-a820e88c/team_run 20261027-181944-b25a30da 与 round-01 目录（enhanced-final-manifest.txt/final-hashes.txt/walkthrough-report.md）自洽；每 run 单 attempt、事件链完整（lock→session→clear→query→close）；11 个失败 run 原始失败状态保留（缺陷发现-修复链可追溯）。
- timing_permissions: PASS_DYNAMIC  expect_response 先注册后点击；清默认筛选后回读非空即 ScopeFilterError；`_click_guard` 拒绝 NO_SAVE_WORDS（含空白抹平防绕过）；stage1_result 写类检查 NOT_AUTHORIZED；唯一 POST 为列表查询（已实证端点）；finally 仅关自建 context、释放自持锁。
- idempotency_retry: PASS_DYNAMIC  材料输出必须新目录/互不嵌套/原件零漂移有动态单测并随 430 全绿；查询失败落盘不覆盖旧 attempt；全部 run retries=0；失败链各为不同缺陷、修复后新 run，无同 failure_key 三连。
- executor_matrix: PASS_STATIC  合同 CP0—CP9 明确 B 施工/独立只读 agent 走读（报告+修订前后双哈希在档）/CP8 fresh ENHANCED_FINAL（本轮）/git commit 后置人工门；各角色产物均在盘，无「规范有、无人负责」项。
- type_cross_product: PASS_DYNAMIC  互斥/空条件/空白关键词/limit 0·21 拒·1·20 收/snapshot 仅随 number/日期格式与顺序/run-id 正则/保护目录枚举前拒/嵌套与覆盖拒/损坏件不吞批/前缀不命中/前导零/多 UUID——单测（我复跑的 430 内）+ 真实 run 双覆盖；未登记类别 fail-closed（见 P2-4 措辞缺口）。
- interface_discovery: PASS_DYNAMIC  两个 CLI --help 实测；公共参考全部命令/API 对勘存在；SKILL 路由行/入口说明登记行/rd-materials 场景指针/AGENTS 短指针/repository-layout 归类经 git diff 逐行核实；test_skill_docs 9 项在 430 内通过（引用链接完整性覆盖两份新手册存在性）。
- fixture_truth: PASS_DYNAMIC  三个阳性对照原始 JSON 证实「失败被安全拦截」：creator6（不存在人名）、creator7（张伟 0 命中）均 SCOPEFILTERERROR 且查询未执行；dept7 父节点禁用「确定」不点击、清洁报错；zero2 三分支全 ok 的 zero_results 与 kw 的 failed 明确区分；快照哈希、归组闭合、appliedDeptName、offline-verify 哈希覆盖均由我独立复算证实。

FINDINGS
- P2-1（冻结果记录证据指针失真）: 位置=feature02-…/公共能力与外购样品runbook施工结果.md §二 C08。事实=引用 offline-verify/20261027-184250，其 source_manifest 的 query.py=62b28860…（旧版）；覆盖最终哈希 d7d6482d… 的是 192354（OFFLINE_PASS/430 tests/exit 0，我已核实）。影响=C13「证据」指针指向作废运行，读者按图索骥会拿到旧代码的验证（envelope 已诚实声明作废，实质证据在盘）。最小修复=该行改指 192354（或补注 184250 为旧版作废），随下次文档修订以新哈希入库。
- P2-2（冻结果记录耗时失真）: 位置=同文件 §三部门行。事实=dept6 写 15.1s，原始证据双源（events query_close 与 query_result.json）均为 total_s=32.2s；dept7 10.6 vs 10.5、zero2 9.8 vs 9.9 为舍入级。影响=C13「实测耗时」数字失真；效率结论不受实质影响（32.2s 仍远优于对照 8m21s）。最小修复=按 events 实值订正，同 P2-1 顺带修。
- P2-3（银行资料入库风险——证据归档 commit 前必须处理）: 位置=automation/runs/20261027-common-accept-tpl2/{template_snapshot.json, attempt_001/evidence/template_view_observation.json, attempt_001/evidence/template_view.png}。事实=前两个 JSON 含真实收款户名/账号/行号，PNG 按 2026-10-27 截图分级长期口径「真实表单画面默认仅本地保留」；三者 `git check-ignore` 均未命中任何规则，当前未跟踪（提交属后置人工门），结果记录/STATE 未标记排除要求。影响=若证据归档直接 `git add automation/runs/20261027-common-accept-*`，将违反任务冻结禁令「银行资料不入 Git」并逆转同日完成的 516 文件历史净化。最小修复=提交前对上述三文件（及任何目视含银行资料的 PNG）按既有 per-path template_snapshot.json 惯例追加 .gitignore 排除，或在结果记录遗留项注明。
- P2-4（代码细节，非承重）: ①bpm/query.py keyword_flow 中 merged_input 计算后未使用（真实合并走全量分支项）、run() 中 ok 赋值未用——死代码；②--snapshot 对未登记类别：fetch_template→normalize 抛 TypeConfigError(ValueError) 未捕获，以 traceback 非零退出（fail-closed、不产伪快照），但缺计划 G2 要求的「明确说明并指向 --research-raw」的用户可读指引；③clear-icon 用 dispatch_event("click") 绕过 _click_guard（选择器限定筛选行+回读确认，实际风险低，防御纵深建议改走守卫或加白名单断言）。

VERIFIED_COMMANDS=sha256sum 15 产物×2 轮（一致，exit 0）；python -X utf8 -m unittest discover -s tests（Ran 430, OK skipped=4，exit 0）；python -X utf8 -m bpm.query --help / -m bpm.materials prepare --help（exit 0）；python 解析 20 个 run 的 query_result/events 及 tpl2 快照（含 Decimal 闭合、appliedDeptName、锁计数，exit 0）；git diff/check-ignore/ls-files/show（exit 0）。证据路径=automation/runs/20261027-common-accept-{kw2,tpl2,zero2,creator4..7,dept6,dept7,…}/、automation/offline-verify/20261027-{184250,192354}-draft-build/、team-progress/team-workflow/9dc3722f20eb474b8851c942a8a78454/round-01/
UNVERIFIED_SCOPE=NONE（作者声明及理由经我核实成立：同名多工号变体需组织内真实同名对，张伟 0 命中已构造性证伪，且与动态实证的 len(hits)!=1→raise 走同一代码路径，部门侧同类守卫经 dept7 动态触发；生产 OA 只读不可重放属方法边界，已用原始工件内部一致性+哈希+独立复算替代，快照/事件/耗时三方吻合。）
VERDICT=GO
```

**判定说明**：八面全过（7 动态 + executor_matrix 静态）、哈希双算有效、无未声明未验证范围、封印决策无触碰、无 P0/P1。四个 P2 均不改变任何验收判断：P2-1/P2-2 是冻结果记录内的两处事实性失真（实质证据已在盘并经我独立复核），可随下次文档修订订正后以新哈希入库；P2-3 是后置 commit 人工门的强制处理项（提交前排除三个含银行资料文件），不构成本轮产物缺陷；P2-4 为低风险代码卫生项。放行生效前提：证据归档 commit 前落实 P2-3。
