<!-- team-task-source id="src-b25a30da" sha256="b25a30dae4579ca0c64062ba51479601564701449e7dcfbd87416f7d19594271" status="open" -->
# 本次任务：公共能力调用路径＋「报销单—外购样品」runbook 轻量施工（BPM-COMMON-20261027-V1）

按 `feature02-扩展更多单据类型/2026-10-27 各类runbook公共能力调用路径轻量固化施工计划.md`（BPM-COMMON-20261027-V1，已交付未施工）完成 G1—G5 全部必做项，按其 §6 C01—C13 完成判据验收，交付一份统一结果记录。计划文档的 §3 逐项条款、§5 验收方法与 §6 判据表是本任务的具体执行规格；与 repo 硬规则冲突时以 AGENTS.md 为准。

## 交付物（G1—G5）

1. **G1+G2 查询入口**：新增 `bpm/query.py`（`python -X utf8 -m bpm.query`，不加根目录兼容壳）。`--keyword`/`--number` 二选一必填，可选 `--creator`/`--department`/制单日期起止/`--expect-name`/`--limit`(默认5，1—20)/`--snapshot`。一次受锁保护只读会话内完成认证、查询、翻页、详情与模板快照；复用 `bpm.login.LoginProbe`、`bpm.template.fetch_template`、`observe_template_view`，不为公共入口重构既有 CLI。输出落 `automation/runs/<run>/events.jsonl` + attempt 目录 + 小型 `query_result.json`。计划 §3 G1/G2 的逐条行为边界（清默认筛选并回读、三字段 OR 合并去重、制单时间降序、并列返回候选、零结果与失败区分、单号字符串不前缀命中、未知类别指向 `--research-raw`）全部落实。
2. **G3 材料准备入口**：`bpm/materials.py` 增加薄 CLI（或独立 `bpm/materials_cli.py` 同步文档）：`python -X utf8 -m bpm.materials prepare --source <原件目录> --out <独立派生目录>`。复用 `prepare_dual_materials`/`inventory_materials`/`extract_structured`/`extract_pdf_text`/`register_derived`/`render_to_files`，v2.0 双根 manifest；源/输出目录互不嵌套、保护路径（.pw-profile/.local-session/.git 等）拒绝、不覆盖既有派生目录；`collect_materials` 保持自驾专用范围不改名不泛化。
3. **G4 公共调用参考**：新建 `.claude/skills/bpm-fill-run/references/common-operations.md`，覆盖计划列出的六个用法（查候选/读单据、定位摘要 vs 完整快照、离线准备、FactSet/reconcile/计划校验、正式填写执行、结果与耗时定位）；同步 Skill、入口与未来扩展说明、self-drive/travel/express/rd-materials 手册的必要引用，AGENTS.md 加查询入口短指针，`docs/repository-layout.md` 登记新命令归类。仅替换确有重复或失真的公共调用描述，业务规则与历史验收证据保留。
4. **G5 外购样品 runbook**：新建 `.claude/skills/bpm-fill-run/references/purchased-samples.md`（七部分完整）；R1 复用 G2 验收时的 `15426104120` 定向只读核实（不另开多轮研究）；R2 字段映射表逐项给来源或精确缺口；R3 差异表（直接复用/需补口径/需适配代码）；R4 场景路由登记（真实类别 rd_materials/研发材料费/11 + 外购样品业务证据）；R5 独立只读走读。不绑定庄旭宏/固定单号/18行/历史金额；缺本次原件时写明具体缺口不虚构规则。
5. **结果记录**：`feature02-扩展更多单据类型/公共能力与外购样品runbook施工结果.md`，分别报告公共能力/模板研究/场景手册/后续待验，列 C01—C13 逐项证据、准确命令、实测耗时、遗留项；STATE.md 用短摘要替换「待施工」条目。

## 范围与允许写清单

- 新增/修改：`bpm/query.py`（新）、`bpm/materials.py` 或 `bpm/materials_cli.py`、确有需要时 `bpm/login.py`/`bpm/template.py`/`bpm/extraction.py` 窄改；`tests/` 相关新测试；上述 skill 手册/参考/入口文档；结果记录与 STATE.md；`automation/runs/<新run>/` 证据目录。
- 施工顺序：核对当前工作区差异（git status 有 purchased-sample-lookup 等未跟踪工件，保留为证据不覆盖）→ G1/G2 → G3 → G4 → 离线检查 → 真实只读验收（含 G5 模板核实）→ G5 手册/路由/走读 → 收尾。
- 优先复用现有库（template/type_query/materials/extraction/ui）；诊断普查工具不作生产依赖，可提少量共享函数不整份复制。

## 保留项与禁止

- 真实 OA 仅限只读：登录探查、查询、筛选、翻页、查看既有单据、模板读取。不新建/复制/填写/保存/提交/上传/审批/改关联；不改默认 fill_only 守卫。
- 不恢复暂停的自驾工程；不改 workflow helper/状态机、旧任务/计划/冻结合同/历史证据/已归档 run；不新增运行时 `document_type`，不复制执行器，不接保存授权接线，不建常驻服务/通用恢复机制/新状态机。
- 原件只读；派生结果写独立新目录；profile、个人会话元数据、银行资料不入通用文档/合成夹具/Git；默认查询只取定位所需摘要。
- 单 profile 单执行者；临时 context 不接管/导航/关闭他人未保存页；锁被占用保留现场并报告；不删锁、不换 task_id、不清 registry、不强关浏览器。
- 不接入未完成分支（数量×单价、部分票面分配、跨部门预算、物品档案创建、办公/福利类型）；超范围缺陷单列不扩建。
- 正常路径不要求用户编写内部 JSON、提供登录姓名、现场逐项核验或验收签字；无法获得的认证条件与业务歧义集中报告。

## 验证方法

1. **离线与回归**：计划 §5「离线与回归」的反例清单（查询：默认制单人限制/显式筛选保留/同名歧义/OR合并/排序分页/前导零/合法query string/零结果与超时区分/身份不符/锁冲突/资源释放/日志不泄认证值；材料：随机文件名/同内容多文件/同额异票/混合PDF/前导零/损坏件/原件字节不变/保护路径拒绝）；复用对应模板/材料/提取/登录/session/技能文档既有测试；改 `bpm/browser_probe.py` 或兼容入口先 `python -X utf8 stage1_probe_selftest.py` 全绿再实单；相关改动跑 `python -X utf8 -m unittest discover -s tests`；`verify_bpm_build.py` 按受影响范围需要运行。
2. **真实只读验收**（用新正式命令，不临时另写驱动）：关键词「外购样本」检索验范围/排序/去重/详情；完整单号读 `15426104120` 模板及只读页面，验单号/UUID 一致与历史制单人≠当前登录人路径；唯一随机关键词零结果与程序失败区分；每次运行只启动一个临时浏览器、600ms 稳定等待保留、报告实测阶段耗时；匿名非自驾夹具（采购票据 PDF＋统计 XLSX）走材料入口。登录过期/身份冲突用离线替身，不破坏真实凭证。
3. **独立走读**：一名独立只读 agent 合并审阅公共参考+新手册+路由（不另起浏览器、不读认证文件、不改状态），覆盖计划 §5 走读清单；实质问题修订并复核，记录最终文档哈希。
4. 缺登录/权限/样本不可见时完成离线实现与文档、如实保留未完成真实验收项，不写成全部通过。

## done_when

- C01—C13 全部满足（计划 §6 判据表逐条），并在结果记录中逐项给出证据路径与实测记录。
- `bpm.query` 关键词查询、精确单号读取（含 `15426104120` 实时定向核实）与零结果三分支有本次真实只读 run 证据；材料入口匿名夹具走通；相关离线回归绿。
- `common-operations.md`、`purchased-samples.md`、路由登记（Skill/入口说明/研发手册指针/AGENTS 指针/repository-layout）全部就位且命令与实际实现一致。
- 独立走读完成、实质问题修正并留最终哈希；结果记录与 STATE 更新落盘；无未声明的越界改动（真实 OA 零业务写入、自驾工程保持暂停、原件字节零漂移）。
<!-- /team-task-source -->
<!-- team-task-contract run_id="20261027-181944-b25a30da" contract_id="ctr-a820e88c" source_block_id="src-b25a30da" status="frozen" profile="full" -->
### 冻结合同（2026-10-27，profile=full）

**① 任务终态**：BPM-COMMON-20261027-V1 计划 G1—G5 全部落地——两个可运行薄入口（`bpm/query.py` 关键词/单号只读查询、`bpm.materials` 离线准备 CLI）、公共调用参考 `common-operations.md`、「报销单—外购样品」初版 runbook `purchased-samples.md` 及路由登记、相关测试与真实只读验收、独立走读、统一结果记录与 STATE 收尾；C01—C13 判据逐项满足并留证据。

**② 权威源·主线·范围**：权威源=repo `AGENTS.md`＋任务 source（src-b25a30da）＋本合同；详细执行规格=`feature02-扩展更多单据类型/2026-10-27 各类runbook公共能力调用路径轻量固化施工计划.md` §3/§5/§6。冲突优先级：用户最新明确指令＞repo 硬规则/已封决策＞本合同＞检查点计划＞历史说明。允许写：`bpm/query.py`(新)、`bpm/materials.py` 或新薄 CLI 模块、`bpm/login.py`/`bpm/template.py`/`bpm/extraction.py`/`bpm/browser_probe.py` 窄改（改后先 selftest 全绿）、`tests/`、`.claude/skills/bpm-fill-run/` 手册与登记、`docs/repository-layout.md`、`AGENTS.md` 入口短指针、`feature02-…/公共能力与外购样品runbook施工结果.md`、`STATE.md`、`automation/runs/<新run>/`。只读：原件目录、`automation/task-registry/`、`.pw-profile/`、`.local-session/`、历史 runs、`team-progress/team-workflow/` 归档、自驾合同与工程。禁止：任何 OA 业务写入（新建/填写/保存/提交/上传/审批/改关联）、改 workflow helper/状态机、新增运行时 document_type、泛化 collect_materials、删锁/换 task_id/清 registry。保留无关工作树改动（STATE.md 未提交更新、purchased-sample 未跟踪工件等）。

**③ 全局 done_when**（=计划 §6 C01—C13；验证=结果记录逐项证据＋原始工件）：
- D1(C01) 查询入口关键词找候选+单号读取可用；无空条件全表普查；实际筛选范围清楚（验证：`python -X utf8 -m bpm.query` 三分支真实 run + 离线反例测试）。
- D2(C02) 身份/锁/会话生命周期正确；单次调用一个临时浏览器（验证：events.jsonl 无重复锁获取、close 事件齐全）。
- D3(C03) 排序/OR 合并/唯一单号/并列/不完整结果正确（验证：离线反例 + 关键词真实 run 的 query_result.json）。
- D4(C04) 模板读取复用原校验；旧 CLI 保护不放宽；未知类别只读报告（验证：15426104120 快照 + 代码 diff 无放宽）。
- D5(C05) 材料入口免 OA 身份、复用双根 manifest、PDF 文本可追溯（验证：匿名夹具 prepare run + manifest 结构）。
- D6(C06) 保护目录边界反例通过；无覆盖历史/泄露认证（验证：反例测试 + git 确认无敏感入档）。
- D7(C07) 公共参考命令/API 实际存在；手册可发现可复用（验证：test_skill_docs.py + 走读）。
- D8(C08) 离线回归通过＋真实关键词/精确模板/零结果三分支证据；只读验收未变填写（验证：unittest + events.jsonl 无写入端点）。
- D9(C09) 15426104120 实时定向核实；旧研究复用并记录差异；未硬编码（验证：本次 template_snapshot.json + 手册无固定值）。
- D10(C10) 外购样品手册七部分完整；字段来源/归组/金额/档案匹配有依据或精确缺口（验证：purchased-samples.md + 独立走读）。
- D11(C11) 路由登记可发现；研发通用路由保留；无新增类型/执行器复制（验证：SKILL/入口说明/rd-materials 指针 + types.py diff）。
- D12(C12) 独立走读完成、实质问题修正；手册完成/口径待补/真实新业务待验分别记录（验证：走读报告 + 最终哈希）。
- D13(C13) 结果记录列改动/C01—C12/命令/证据/耗时/遗留；STATE 短摘要替换待施工状态（验证：两文件实物）。

**④ 检查点路线**（依赖序）：CP0 工作区差异核对→CP1 G1/G2 query.py 实现+单测→CP2 G3 materials CLI+单测→CP3 G4 公共参考与登记→CP4 离线回归（unittest；如改 browser_probe 先 selftest）→CP5 真实只读验收三分支+匿名夹具（含 G5 R1 模板核实，同 context 复用证据）→CP6 G5 手册/路由/差异表→CP7 独立走读（一次性只读 agent）→CP8 ENHANCED_FINAL fresh 终审→CP9 收尾（结果记录/STATE/mc-update→pin→session-new）。每 CP 证据入 `automation/runs/` 或 round 目录；G5 R2 缺原件按计划登记缺口不阻断。

**⑤ 红线·禁止·人工门**：四红线（销毁性/不可逆；对外交付物与 Ldterm；同 failure_key 三次熔断；推翻已封决策）照 team-task 全文；本项目另禁：OA 业务写入、保存/提交族点击、代扫登录、注入旧凭证、临时 context 接管他人未保存页、把查询 POST 误判写入或开放任意请求工具、数量×单价/部分票面/非空关联分支放行。已前置授权（用户 run 启动）：真实 OA 只读查询/翻页/详情/模板读取、本机新 run 目录写入、上述允许写清单。后置人工门（PENDING_HUMAN_NONBLOCKING 攒批）：git commit、任何 rm/伸敏感目录类权限命令、对外发布。缺登录/权限时离线替身验证+如实缺口，不伪造账号或凭证状态。

**⑥ 纠偏三问与陪审扳机**：按 team-task SKILL「spawn 短锚与里程碑五件套」节执行，不在本合同复制；首次非红线失败走 FIRST_FAILURE_MXP_REVIEW（T3 派一次性 mc-expert HISTORY）。

**⑦ 交接口径**：里程碑五件套指针同上；本轮最终交接按 team-workflow relay §2（handoff-input.json＋artifacts 哈希＋非空 evidence＋failure_counts 全量）。
<!-- /team-task-contract -->
