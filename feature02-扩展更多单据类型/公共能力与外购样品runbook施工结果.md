# 公共能力与外购样品 runbook 施工结果

编号：`BPM-COMMON-20261027-V1` 施工收尾。日期：2026-10-27。执行：team-workflow run `9dc3722f20eb474b8851c942a8a78454` round 1（team_run `20261027-181944-b25a30da`，合同 ctr-a820e88c）。按[施工计划](2026-10-27%20各类runbook公共能力调用路径轻量固化施工计划.md)完成 G1—G5；本文分别报告**公共能力、模板研究、场景手册、后续业务待验**四块结论。

## 一、改动清单

| 类别 | 文件 | 内容 |
|---|---|---|
| 新增代码 | `bpm/query.py` | 只读查询入口（`python -X utf8 -m bpm.query`）：关键词三分支 OR 合并去重/制单时间降序/精确单号/`--snapshot` 模板读取；显式筛选（制单人/部门/日期，人名按「姓名 [工号]」、组织按纯名称唯一命中，歧义/父节点/禁用确认一律 fail-closed）；一次受锁只读会话；`query_result.json` 含范围/耗时/取证充分性 |
| 代码窄改 | `bpm/materials.py` | ①`_safe_material` 保护集补 `.local-session`（枚举前拒绝）；②`extract_structured` xlsx 分支损坏件登记不吞批；③新增 `prepare_command`/`plan_pdf_text_pass`/`summarize_prepared` 与 `prepare` CLI（PDF 嵌入文本层经 `register_derived` 绑定原件哈希） |
| 新增测试 | `tests/test_bpm_query.py`（21 项）、`tests/test_bpm_materials_cli.py`（10 项） | 参数/URL 匹配/OR 合并/排序并列/零结果区分/前导零/多 UUID/保护路径/嵌套覆盖拒绝/损坏件/原件零漂移 |
| 新增文档 | `.claude/skills/bpm-fill-run/references/common-operations.md`、`references/purchased-samples.md` | 公共调用参考（六用法）；外购样品场景 runbook（七部分） |
| 文档接线 | `SKILL.md`、`入口与未来扩展说明.md`、`references/rd-materials.md`、`AGENTS.md`、`docs/repository-layout.md` | 公共参考指针+查询入口短说明；外购样品路由与登记；研发手册场景指针；命令归类 |

未改动：`bpm/browser_probe.py`、`bpm/login.py`、`bpm/template.py`、`bpm/extraction.py`、workflow helper、类型配置、历史证据、task-registry、自驾工程（保持暂停）。

## 二、C01—C13 判据核验

| ID | 结论 | 证据 |
|---|---|---|
| C01 查询入口双模式、无全表普查、范围清楚 | 通过 | `bpm/query.py`（`--keyword`/`--number` 互斥必填、空条件拒绝、limit 1—20）；真实 run `automation/runs/20261027-common-accept-kw2/query_result.json`（scope 含默认筛选清除回读+账号）；显式筛选实证 `…-creator5/4/6`（制单人收窄/正确零结果/未找到 fail-closed）与 `…-dept6/7`（具体部门收窄/父节点清洁报错）；单测 `ValidateCliTests` |
| C02 身份/锁/会话生命周期、单浏览器 | 通过 | kw2/tpl2/zero2 各 run `events.jsonl`：单次 `profile_lock_acquired`、close 释放；LoginProbe 自动发现账号（陈晶）并核对；finally 只关自建 context 与自持锁 |
| C03 排序/OR/唯一/并列/不完整结果 | 通过 | kw2：三分支 8/20/9 条合并去重 5 候选、createdAt 降序、最新单第一、双字段命中合并、`tied_with_latest` 标记；单测 `MergeCandidatesTests`/`ClassifyOutcomeTests`（partial≠零结果≠ok） |
| C04 模板读取复用原校验、不放宽 | 通过 | `bpm/query.py` 仅调用 `fetch_template`（含 `lookup_list` identity hint——历史制单人≠当前登录人场景，主表 bizNumber/UUID 仍实时核验）+`observe_template_view`；`bpm/template.py` 零改动 |
| C05 材料入口免 OA、双根、PDF 可追溯、复核不冒充 | 通过 | CLI 实跑匿名夹具（CSV+坏 xlsx+损坏 PDF+文本 PDF）：`PREPARE_COMPLETE`、4 文件、`pdf_text_extracted=1`（derived 绑定原件哈希）、损坏件 gap 点名；单测 27 项（materials 全组） |
| C06 保护目录/不覆盖/不泄露 | 通过 | 单测 `ProtectedPathTests`/`PrepareBoundaryTests`（`.local-session`/`.pw-profile`/`.git` 枚举前拒绝；输出必须新目录；互不嵌套；原件字节零漂移）；`EvidenceHygieneTests`（候选字段无认证名）；git status 无敏感入档 |
| C07 公共参考命令真实存在 | 通过 | `common-operations.md` 六用法命令/API 全部对勘实现（`bpm.query`/`bpm.materials prepare`/`FactSet`/`reconcile`/`build_reuse_matrix`/`generate_fill_plan`/`validate_plan`/`verify_snapshot` 符号 grep 核实）；test_skill_docs.py 9 项通过 |
| C08 离线回归+真实三分支+只读未变填写 | 通过 | `verify_bpm_build.py` → `OFFLINE_PASS`（selftest+430 tests，覆盖最终 `bpm/query.py` 哈希：`automation/offline-verify/20261027-192354-draft-build/`；显式筛选修复前的 184250 目录对应旧哈希，已作废）；真实验收仅 GET 查询/只读 view 导航，零业务写入端点 |
| C09 模板实时定向核实、差异记录、不硬编码 | 通过 | `automation/runs/20261027-common-accept-tpl2/template_snapshot.json`（sha256 `4efaf3a0…`）：18 档案/4 明细/4 银行/关联 0/费用说明 0 与历史一致；**新发现**：旧快照 products 投影仅 price，本次含完整 code/name/purchaser（见 §四）；手册无固定人员/单号/行数/金额 |
| C10 手册七部分完整、缺口精确 | 通过 | `purchased-samples.md`：适用范围/输入/业务规则及来源（实证+待补 5 项）/字段映射/操作步骤/异常停点/验证与交付；归组规则有实证依据（按购买人、逐人闭合） |
| C11 路由可发现、通用路由保留、无新类型 | 通过 | SKILL 路由行+入口说明登记行+rd-materials 场景指针；`bpm/types.py` 与 `automation/document-types/` 零改动（无新 document_type、无执行器复制） |
| C12 独立走读完成、实质问题修正 | 通过（走读记录见 §五） | 独立只读 agent 走读报告：无 must_fix；最终文档哈希在 §五 |
| C13 结果记录+STATE 更新 | 通过 | 本文件+STATE.md 短摘要替换 |

## 三、真实只读验收（本次证据，全部新正式命令）

| 分支 | run | 结果 | 耗时 |
|---|---|---|---|
| 关键词「外购样品」 | `20261027-common-accept-kw2` | ok；5 候选降序，最新 `15426104120`（2026-10-20）；历史制单人（庄旭宏）≠当前登录人（陈晶）路径验证 | 10.1s（含启动 1.1/认证 2.2/查询 3.0） |
| 精确单号+快照 | `20261027-common-accept-tpl2` | ok；唯一 UUID；快照+只读页面核实；operator 核对陈晶 | 14.6s（查询 7.7/详情 6.8） |
| 唯一随机关键词 `ZLSJ-SUIJI-20261027-QX8K` | `20261027-common-accept-zero2` | `zero_results`、三分支全 ok、`sufficient_evidence=true`——与程序失败明确区分 | 9.9s |
| 显式筛选收窄（制单人=庄旭宏） | `20261027-common-accept-creator5` | ok；默认筛选（陈晶）清除→庄旭宏筛选回读→精确收窄至其 5 张外购样品单（首条即模板 `15426104120`，totalCost 9935.16 与快照一致） | 14.7s |
| 显式筛选零结果与 fail-closed | `…-creator4`（陈晶+日期：`zero_results` 且语义正确）/`…-creator6`（不存在人名：`SCOPEFILTERERROR`、查询未执行、不静默缩范围） | 显式筛选三态实证：成功收窄／正确零结果／未找到即停 | 14.8s / 9.8s |
| 部门筛选（具体部门/父节点） | `…-dept6`（运动表现研究部：ok，首条 `15426104120` 的 appliedDeptName 精确匹配）/`…-dept7`（科技中心＝不可选父节点：清洁 `SCOPEFILTERERROR`，不点击禁用「确定」） | 部门行选择器经真实筛选区 dump 实证（`AppliedDeptPath`）；组织节点按纯名称唯一命中，人名按「姓名 [工号]」 | 32.2s / 10.5s |
| 匿名材料夹具 CLI | 临时目录（不入库） | `PREPARE_COMPLETE`；文本 PDF 提取绑定哈希；坏 xlsx/损坏 PDF 登记缺口不吞批 | <2s |

对比 2026-10-27 临时 lookup（登录至确认 8 分 21 秒、7 次临时探查）：正式入口查询分支总耗时约 10—15 秒，含组织选择对话框的显式部门筛选流程约 32 秒。首跑暴露并修复五处真实缺陷（证据保留于 `…-kw`/`…-tpl`/`…-creator…creator3`/`…-dept…dept5` run）：①Playwright predicate 收到 Response 对象而非 URL 字符串；②`_target_list` 重新加载列表页后默认制单人筛选复位，跨制单人读取需 `lookup_list` hint 交接；③组织选择器只输入不回车、树从未过滤——按 `ui.py` 申请人选择实证范式改为 fill+Enter+「姓名 [工号]」式唯一命中；④部门行类名 `AppliedDeptPath` 初版无实证，经真实筛选区 dump 证实并加漂移兜底（标签文本定位会误中申请人行）；⑤父级中心节点不可选导致「确定」禁用、旧版裸超时——改为禁用即清洁报错，人名/组织两种判别模式分立。零结果 `sufficient_evidence` 语义修正。

## 四、G5 模板研究（R1—R3）

**R1 复用与差异**（`20261027-common-accept-tpl2` vs `type-template-15426104120-20261023-194712`）：
- 行数结构一致：明细 4、物品档案 18、银行 4、关联/关联明细/费用说明 0、附件 25。
- **实质差异**：旧快照 products 投影仅 `price`；本次含完整 `code/name/purchaser/price`（如 `26103134 特步越野背包 陈晶 439.04`）。旧研究不能替代本次档案字段核对。
- 归组实证：档案按 `purchaser` 分组合计=明细行金额逐人相等（张宇昂 3079.90 / 韩晓 1249.56 / 陈晶 3698.90 / 庄旭宏 1906.80），总合计 9935.16=totalCost（Decimal 闭合）。同一预算号 `15625120075 年度预算项目`。

**R3 差异表**：

| 判定 | 项 |
|---|---|
| 直接复用（零适配） | LoginProbe 认证/锁生命周期；fetch_template/observe_template_view 只读核验；parse_list_items/exact_list_item；rd_materials 类型配置与执行器（档案行金额/空关联/空费用说明/普通全额分配）；fill_once 计划-校验-填写链；materials 双根准备 |
| 需补业务口径（手册 §3 待补 5 项，取得本次原件后确认） | 报销范围/用途；新样品无档案处理；含税/折扣/运费/退款/外币；合购/跨预算归组；票据分配与无票依据 |
| 需另行适配代码 | **无**——实证结构完全落在 rd_materials 支持范围内；超出场景（无档案/数量分配/非空关联等）按手册 §6 停点处理，是业务停点不是代码缺口 |

## 五、独立走读

独立只读 agent（一次性，不另起浏览器、不读认证文件）合并审阅公共参考+新手册+路由：**五问全 PASS、事实核对全通过、must_fix 无**；两条建议级措辞优化已采纳修订（SKILL 路由行判别特征、§5.4 计划契约链接），修订后 test_skill_docs 复跑通过。走读报告与最终文档哈希见 `team-progress/team-workflow/9dc3722f20eb474b8851c942a8a78454/round-01/{walkthrough-report.md,final-hashes.txt}`。

## 六、遗留项与后续验证边界

1. **业务待验（不冒充完成）**：外购样品真实原件驱动的填写、金额分配、真实保存均未执行——本次仅模板研究与手册；取得材料后按手册 §5—§7 另行验收。
2. 待补业务口径 5 项（§四 R3 表）；`collect_materials` 仍限自驾票种，其他票种语义归集待真实样本另列任务。
3. 公共能力不改变自驾工程暂停状态、不改变任何类型的能力验收状态；`bpm.query` 真实验收覆盖计划 §5 全部五项（关键词/单号/零结果三分支＋单次单浏览器生命周期＋匿名材料夹具），显式筛选亦已三态实证：制单人收窄（`…-creator5`）/正确零结果+日期回读（`…-creator4`）/未找到 fail-closed（`…-creator6`）/具体部门收窄（`…-dept6`）/父级中心节点清洁报错（`…-dept7`）。部门须给到可选的具体部门，父级中心节点不可选（实证）；同名多工号人员仍未真实触发（需真实同名对，构造无法复现），由「姓名 [工号]」唯一判别+fail-closed 守卫覆盖。
4. 临时工件处置：`automation/runs/20261027-purchased-sample-lookup/`（含 lookup.py）及两个 purchased-sample-login run 保留为历史证据，不作正式入口依赖；正式查询入口已替代其用途。
5. ENHANCED_FINAL 判决（2026-10-27，`round-01/enhanced-final-verdict.md`）：**GO**（八面全过、哈希双算 VALID、UNVERIFIED_SCOPE=NONE、无 P0/P1），四个 P2 处置——P2-1/P2-2 本文已按原始 events 实值订正（C08 指向 192354；dept6 32.2s／dept7 10.5s／zero2 9.9s）；P2-3 tpl2 三个含真实收款账户文件已按既有惯例 `.gitignore` per-path 排除（仅本地保留，`git check-ignore` 已验证）；P2-4 三项代码卫生（keyword_flow 死变量、`--snapshot` 未登记类别 traceback 缺用户指引、clear-icon `dispatch_event` 绕 `_click_guard`）留待下次触达 `bpm/query.py` 的任务处理，不构成本轮承重缺陷。
