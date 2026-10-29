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
