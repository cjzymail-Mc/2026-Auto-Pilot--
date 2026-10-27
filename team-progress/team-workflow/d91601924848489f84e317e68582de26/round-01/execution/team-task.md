<!-- team-task-source id="src-a68a0869" sha256="a68a0869c02dc31cfb09f1380fe6dffaf5902325c44d599d76541ccc451a6075" status="open" -->
# 本次任务：V3 首轮 R00 —— 断点接手盘点 + r10 在途核对冻结 + 02/04 缺口分类 + 真实公出案例供料盘点与差异清单

背景（自足）：本轮为冻结合同 `BPM-MATERIALS-20261026-V3`（`feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md`）新工作流首轮。合同唯一总体目标：独立解析 `feature01-细化报销skill/12月公出-发票/` 真实公出原件 → 保留用户公里数按 1 元/公里、真实通行费逐票回填同结构 Excel 副本并可靠重算（R=M+T）→ 去重油票+通行费总额 F=O+T **严格大于** R 才允许填 OA → 正式入口真实 Chromium/Playwright 只填不存（fill_only，不测保存/提交/持久化）→ 真实公出单模块逐票查找对照报告（一张不漏）；OA 关联表随机选真实可选单据仅作测试占位，与真实逐票匹配分开建模、分开报告。其他类别扩展不是本轮完成门槛。

调度事实：旧 workflow run `a7618f4fa0b040fa81782c93eb1bc926` 已按用户 2026-10-26 明确授权作操作员维护归档（`RETIRED_NOT_COMPLETED`，证据 `team-progress/team-workflow/a7618f4fa0b040fa81782c93eb1bc926/operator-recovery-20261026-v3/`）；旧根 handoff/review 属 round 9，不作 round 10 或本案例通过依据；旧 B_RUNNING 是历史断点不是当前活动状态；不恢复旧根文件、不修改冻结 V3、不把该维护授权推广为通用清理权限。

**历史累计失败字典（承接自旧 run，不得清零、改名或隐去；新 run 正常 init 初值不代表旧问题已通过）：**

```json
{"review|content|source_manifest_coverage|D23": 1}
```

对应缺陷：统一构建 source_manifest 覆盖不足（旧清单未把五类型 document-types config、新增模块等纳入冻结清单）。本轮核实 r10 在途同步项时沿用此口径；若同问题仍在，沿原 key 累计。

r10 断点事实（须按当前实物核实，不当作冻结通过版本）：`verify_bpm_build.py` source_manifest 五类型同步、`automation/fill-plan.schema.json` document_type enum 五类型、`bpm_extraction.py` 一页多票显式拒绝三项已有在途代码但未完成最终冻结/交接；`bpm_chain.py` 及四类 validate-only 工件（`automation/runs/20261024-211000-chain-r10-{travel,express,office,welfare}/`）存在但只是 JSON 回放/合成入口，不是真实 PDF/Excel 用户入口；02/04 真实观察留 `automation/runs/20261024-213500-type0204-observe/`，类别/枚举已实测、预算/科目仍 `NO_TABLE_DIALOG`。既有三类（travel/express/rd_materials）r7/r8 真实历史回放填写+独立 DOM 核验证据保留复用，不重做。

## 待做条款

### 1. R00 接手盘点（全部只读，实物证据）
- 业务 profile/锁/当前 OA 页/`automation/task-registry/` 盘点：取得 profile 锁后只读核实当前执行者、遗留页面与 registry 状态；不接管未知活页、不强删锁、不导航或关闭其他执行者未保存页；原页丢失或无法安全恢复则如实登记，不自动重建。
- 源码与未提交变更盘点：对照 r10 任务书（manifest 五类型 / schema enum / 一页多票拒绝 + bpm_chain.py + 02/04 config 回填）逐项核实三态——代码已落地 / 测试已配 / 证据已冻结；产出在途变更清单表。
- 四链产物与 02/04 观察工件：核实来源/类型/结果绑定后复用，不重跑；仅当代码变更使其失效时才重跑受影响链。

### 2. r10 在途差距核对与最小修复（只补影响本案例或构建证据真实性的遗漏）
- D23 口径：`verify_bpm_build.py` source_manifest 覆盖当前实际代码、schemas、五类型 document-types config、skill 及相关测试（含 `bpm_chain.py` 等新增模块）；不达标则补齐并配测试，跑唯一 offline-verify run 冻结证据（含 02/04 config sha 进构建产物）。
- schema enum 与一页多票显式拒绝同法核对：已正确落地的不重写，只补遗漏；多票不得静默只取第一张。
- 改过 `stage1_browser_probe.py` 先 `python -X utf8 stage1_probe_selftest.py` 全绿再实单；相关改动跑 `python -X utf8 -m unittest discover -s tests` 全量。

### 3. 02/04 观察缺口分类（不重跑整套观察）
- 将 `20261024-213500-type0204-observe` 已实测项（类别联动、枚举、picker 形态）与 `NO_TABLE_DIALOG` 未解项分开记录入台账；可从现有诊断/截图/页面结构做有据定位；不无限重试、不假报全过；该项留类型接入工作包，不阻塞本案例主线。

### 4. 真实公出案例供料盘点与差异清单（本轮只盘点+列差异，不预造业务结论）
- 盘点 `feature01-细化报销skill/12月公出-发票/` 全部文件：类型/数量/逐件 SHA-256/目录结构；油票（`油票/` 下 PDF 逐份登记）、通行费发票/收费票据、票据汇总单、行程汇总单、重复副本分类清点；空目录或缺件登记。
- 只读核实 `12月-自驾公出公里数统计表.xlsx` 结构：sheet/表头/公里行/日期路线列/通行费列/公式/合计/隐藏行/备注；原文件哈希落盘；**不回填、不改原件**。
- 模板身份现有依据核实：从用户既有指令、资料说明与已确认上下文定位本次完整模板单号并核实；确实未明确则只登记模板身份缺口，研究候选不冒充用户指定。
- 产出真实案例 vs 现有模型差异清单（后续 CASE 施工输入）：公里应报额 M=K×1、票据覆盖 F=O+T 且 F>R 严格门槛、工作簿副本回填+可靠重算、公出单模块逐票查找报告、随机测试关联（test_placeholder）与真实匹配（actual_trip_matches）分离、日期/期间从原件与真实系统定（不按目录名/文件名猜年月，开票日不自动替代通行日）。
- 本轮不预设票数、公里数、金额、覆盖结论、公出单号或模板号；在台账中把旧“差旅真实原件未提供”修正为“真实公出原件已供料”。

### 5. 唯一总台账纠偏与交接
- 修正 `automation/template-materials-program/progress.json`：区分验证层次（代码已实现/离线已验证/真实控件已验证/历史回放真实填写/本次原件端到端）、在途缺陷、R00 与 CASE 主线状态、下一批可执行入口；把仍把保存/重开当本轮待验的活跃表述修正为 fill_only 口径（历史报告原文不篡改）。
- 按团队流程完成必要独立审查与 P6 收尾后 finish 交 A；不把首轮交接说成合同完成。

## 保留项与边界
- fill_only：不测保存按钮、不验收保存成功/新单号/UUID/重开/持久化；SaveController、普通守卫、registry 保护原样保留。
- 本轮浏览器动作仅限只读盘点（登录/身份例行动态核验、profile/页/registry 只读核实）；零业务行写入、零保存、零提交、零上传、零 OA 关联选择；公出单模块查询与 OA 填写留后续轮次。
- 单 profile 单执行者；登录失效不代扫、不等待，转做其余条款并登记缺口；`--no-proxy-server` 直连；Windows 判活用现有安全实现。
- 旧归档目录与 `legacy-ia2/` 只读；不重做三类回放、不重建材料/事实/计划框架、不接入其他类别扩展、不做模板全量普查。
- 默认不 commit；真实业务材料不入 Git、不入通用测试夹具；`.pw-profile/` 凭证与本地会话元数据不进任何工件。
- Python 一律 `-X utf8`，cwd 仓库根。

## 验证
- 接手盘点三份实物清单落盘：① r10 在途变更三态表（源码/测试/证据指针）；② profile/锁/页/registry 盘点记录；③ 案例文件+哈希清单。
- r10 三项核对结论逐项绑定源码/测试/证据；修复项配测试；全量 unittest 全绿；唯一 offline-verify run 记录在案（或如实列出未闭合项及原因，不冒称 PASS）。
- 02/04 已实测/未解分类记录入台账，无整套观察重跑。
- Excel 只读结构核实报告（哈希+结构+公式口径，无臆测业务值）+ 案例差异建模清单 + 模板身份依据或缺口登记。
- 总台账纠偏后 diff 可查；handoff 交接哈希与实际文件一致。

## done_when
1. R00 盘点有实物证据：旧 run 归档状态、profile/锁/页/registry、r10 在途变更三态清单齐备；未接管未知活页、无业务重复写入或保存动作。
2. r10 在途三项与 bpm_chain/四链证据绑定核实完成：已正确落地项保留并引用既有证据，遗漏项补齐并配测试；全量测试全绿 + 唯一 offline-verify run 冻结记录（或如实登记未闭合项与原因）。
3. 02/04 已实测项与 `NO_TABLE_DIALOG` 未解项准确分类入台账，未整套重跑，未假报全过。
4. 真实案例盘点完成：文件+哈希清单、Excel 只读结构核实、模板身份依据或缺口登记、与现有模型差异清单（含 F>R 严格覆盖与随机测试关联/真实匹配分离的建模要点）；未预设任何业务答案。
5. 总台账纠偏至 fill_only 口径并区分验证层次；P6 收尾 + finish 交接，handoff 哈希与实物一致；历史失败字典 `{"review|content|source_manifest_coverage|D23": 1}` 原样带入交接（同问题沿原 key 累计，不改名不隐去）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261026-095208-a68a0869" contract_id="ctr-08d9de84" source_block_id="src-a68a0869" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-26 · run 20261026-095208-a68a0869）

**终态**：V3 新工作流首轮 R00 以实物证据完成断点接手盘点、r10 在途差距核对与证据冻结、02/04 观察缺口分类、真实公出案例供料盘点与差异清单、唯一总台账纠偏，独立复核通过后 finish 交接 A；本轮不宣称 V3 合同整体完成，不预设任何业务金额/票数/单号结论。

**本轮做**：team-task.md 待做条款 1–5 全部——R00 只读盘点（旧 run 归档状态/profile/锁/页/registry、r10 未提交在途变更三态表、四链与 02/04 工件绑定核实）；r10 差距核对与最小修复（D23 口径 source_manifest 覆盖、schema enum、一页多票显式拒绝）+测试+唯一 offline-verify run；02/04 已实测项与 NO_TABLE_DIALOG 未解项分类入台账；12月公出-发票/ 逐件 SHA-256 清单+分类清点+12月-自驾公出公里数统计表.xlsx 只读结构核实+模板身份依据核实+与现有模型差异清单；automation/template-materials-program/progress.json 纠偏至 fill_only 口径并区分验证层次；P6 收尾与 finish 交接。

**明确不做**：OA 业务行写入/保存/提交/上传/贴票/OA 关联选择；公出单模块查询；Excel 回填或修改案例原件；三类历史回放重跑；其他类别扩展与模板全量普查；git commit/push；修改冻结 V3、旧归档目录、legacy-ia2/；代扫码；预设票数/公里数/金额/覆盖结论/公出单号/模板号等业务答案。

**允许写**：根 team-progress.md、根 team-task.md（仅追加本合同块）、根 handoff-input.json（finish 用）；automation/runs/<新run>/（登录探查与 R00 证据工件）；automation/offline-verify/<新run>/（唯一构建 run）；automation/template-materials-program/progress.json 与 notes.md（台账纠偏）；代码修复仅限 verify_bpm_build.py、bpm_extraction.py、automation/fill-plan.schema.json、stage1_browser_probe.py（如需）及 tests/ 对应测试，且仅补核对出的遗漏，已正确落地项不重写；.claude/skills/bpm-fill-run/ 仅当构建校验要求同步时最小修订。

**只读**：feature01-细化报销skill/12月公出-发票/（含 xlsx 原件）、automation/runs/ 既有 run、既有 offline-verify 产物、automation/task-registry/、automation/.pw-profile/（凭证原值不读不复制）、automation/.local-session/（仅元数据）、旧 run 维护归档、legacy-ia2/、他人未提交变更。

**禁止**：删除/回退他人未提交工作；git add -f/commit/push；把凭证或会话元数据写入任何工件、日志或报告；强删 profile 锁、导航或关闭其他执行者未保存页；对未知活页自动重建；把旧归档内容恢复回活动根。

**红线**：team-task 四红线（销毁性/不可逆操作；对外交付物触碰合规红线；同 failure_key 第 3 次失败熔断；推翻 KB 已封决策）；根 AGENTS.md 五条红线（默认只填不存、.pw-profile 凭证绝不复制、task-registry 只读核实不规避、legacy-ia2 只读、单 profile 单执行者）；本轮浏览器动作仅限只读登录/身份核验与 registry/页面盘点，零业务行写入、零保存、零提交、零上传、零关联选择。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM / risk_class=MEDIUM / risk_owner=USER / risk_source=USER_STANDING_POLICY_20260904 / runtime_policy=GLM_ALLOWED / risk_escalation=NONE；一手证据=team-workflow helper runtime_evidence（B=session c05e555a-0c54-4418-96a2-d92a751dfbc9，model glm-5.3，transcript 已由 helper 核验落盘）。

**裁量推荐（B+AUTO 接管，逐条记入 team-progress 自主裁决区）**：登录失效→登记缺口并转其余条款（不扫码不等待）；offline-verify 唯一 run 命名 materials-v3r00-<时间戳>；R00 证据统一落 automation/runs/20261026-<时间戳>-v3r00-inventory/；02/04 定位仅用既有工件不再开浏览器；差异清单以 Markdown+机器可读 JSON 双落。

**done_when 与验证**：D1–D5 逐条对应 team-task.md done_when 1–5 原文。验证方式：D1=R00 盘点三份实物清单（automation/runs/<run>/ 下）+git 无业务源码意外写入；D2=r10 三态表+unittest discover 全绿日志+offline-verify build_result.json（OFFLINE_PASS 或如实列未闭合项）；D3=progress.json/notes 中 02/04 分类记录+无新观察 run 产生；D4=逐件 sha256 清单 JSON+Excel 只读结构报告+差异清单+模板身份依据或缺口登记；D5=progress.json 纠偏 diff+finish 交接哈希与实物一致+历史失败字典 {"review|content|source_manifest_coverage|D23": 1} 原样带入。验收按 team-task 四态签注；STATIC_ONLY 不冒充完成，浮至交付待确认项。
<!-- /team-task-contract -->
