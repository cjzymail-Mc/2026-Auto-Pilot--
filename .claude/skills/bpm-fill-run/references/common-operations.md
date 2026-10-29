# 公共能力调用参考（查单 / 读模板 / 材料准备 / 计划校验 / 执行 / 结果定位）

本参考只登记**何时调用、准确命令/API、输入输出、证据与失败下一步、真实支持范围**；业务规则、金额语义、类型判定与验收边界在各 runbook。所有命令在仓库根运行，Python 一律 `-X utf8`；真实 OA 交互一律 `--no-proxy-server` 直连（入口内部已配置）。

## 1. 查候选 / 读单据（`bpm.query`，2026-10-27 起正式入口）

**何时调用**：没有单号、要按关键词找最新/相关单据；或已有完整单号要做只读定位。不再临时写脚本开浏览器。

```powershell
# 关键词三分支（主表备注/明细摘要/明细备注）OR 查询，制单时间降序
python -X utf8 -m bpm.query --keyword "外购样品" --limit 5 --run "<本次run>"
# 可选收窄：--creator "姓名" --department "部门" --date-from 2026-10-01 --date-to 2026-10-27
# 注：--creator 须为人员姓名（同名多工号即停）；--department 须给到可选的具体部门——
# 父级中心节点（如“科技中心”）不可选，禁用的「确定」不点击、清洁报错（2026-10-27 实证）。
# 精确单号读取（保留前导零；多 UUID 即停）；--snapshot 另读模板快照并核验主表
python -X utf8 -m bpm.query --number "15426104120" --snapshot --run "<本次run>" --expect-name "<本次探查到的操作人>"
```

- **身份与会话**：入口内完成与 `bpm_login.py` 同等的真实认证（复用 `LoginProbe`），已认证即不再先跑独立登录；`--expect-name` 可选，指定后不符立即停止。锁/浏览器生命周期由入口自管：单次调用一个临时浏览器，结束自释放。
- **范围语义**：自动清除系统带出的“仅当前制单人”默认筛选并回读确认；用户显式给的 `--creator/--department/--日期` 保留。人员/组织多候选不任取首项，报歧义即停。
- **输出**：`automation/runs/<run>/query_result.json`（输入条件、实际范围、耗时、候选的完整单号/UUID/姓名/日期/类别/金额/状态/摘要/命中字段、取证是否充分）+ `events.jsonl` + `attempt_NNN/evidence/`。
- **失败下一步**：`WAIT_HUMAN_LOGIN` → 账号持有人扫码（`python -X utf8 bpm_login.py --force-scan`），agent 不代扫；`PROFILE_LOCKED` → 单 profile 单执行者，保留现场等待在途执行者；`zero_results` 与 `failed/partial` 是不同状态——部分分支失败不宣称“未找到”，补查或如实留缺口。
- **边界**：默认 `limit=5`（1—20）、分支翻页 `--pages`（默认 3）；不为找一张单普查全部历史；关键词命中字段是备注/摘要文本，不等于报销类别。

## 2. 定位摘要 vs 完整模板快照

只要定位（找到单、核对类别/金额/日期）用 §1 的关键词/单号查询，交付 `query_result.json` 候选即可。需要作为**填写模板**研究时才读完整快照：

```powershell
python -X utf8 bpm_template.py --live --expect-name "<操作人>" --template-number "<完整单号>" --output "automation/runs/<run>/template_snapshot.json" [--observe-view] [--research-raw]
```

- `bpm.query --number --snapshot` 与 `bpm_template.py --live` 复用同一 `fetch_template`（主表 bizNumber/UUID 实时核验 + 六子表读取）与 `observe_template_view`（只读 `type=view` 页 + 操作人核对）；查询入口从同一会话内完成，避免二次登录。
- `--research-raw` 仅未登记类别的只读结构研究，不产标准快照、不注册类型。历史只读页面观察不证明新建页编辑控件可用。
- 类别与路由以真实模板 `submitType` 为准（见 SKILL.md 路由节）；未知类别只读报告，不套相近配置。

## 3. 离线材料准备（`bpm.materials prepare`，2026-10-27 起正式入口）

**何时调用**：拿到本次原件目录（PDF/CSV/XLSX/图片），需要盘点、结构化提取、PDF 嵌入文本层时。不连 OA、不需要登录/模板单号/内部 JSON。

```powershell
python -X utf8 -m bpm.materials prepare --source "<本次原件目录>" --out "<独立的新派生目录>"
```

- 复用 `prepare_dual_materials`（v2.0 双根 manifest：原件只读、派生入独立根）+ `extract_structured`（CSV/XLSX 带定位的字符串语义，前导零保留；公式缓存/不可信数值显式待复核）+ `extract_pdf_text`（嵌入文本层，带页码/区域/bbox，经 `register_derived` 绑定原件哈希，原始提取角色不写 reviewed=true）。
- 源/输出目录互不嵌套；输出必须是不存在的新目录；`.pw-profile`/`.local-session`/`.git`/`legacy-ia2` 在枚举前拒绝；损坏件（坏 zip 的 xlsx、打不开的 PDF）登记缺口不吞掉其余文件。
- 输出 `prepare_summary.json`：文件/重复/解析数量、待复核清单、缺口、下一步入口。**完成仅代表材料准备完成**，不等于事实齐备或可填写。
- 扫描件/图片：`render_to_files` 渲染页 + 独立视觉复核（`review_pass` 登记复核值）；`barstub` 仅测试占位，不用于真实票据。文件哈希相同只表示字节相同；同票不同扫描的业务去重靠已复核票号，同额异票不合并。
- 票据**语义**归集：`bpm.collect.collect_materials` 当前仅支持通行费/油票及其汇总单（自驾 runbook 专用），未泛化为采购/快递/研发票据识别器；其他票种按各自 runbook 的人工复核清单处理，缺口如实登记。

## 4. 事实、对账与计划校验（离线 API）

| 用途 | API / 命令 |
|---|---|
| 结构化事实与对账 | `bpm.facts.FactSet` / `bpm.facts.reconcile(factset, …)` |
| 历史复用决策矩阵 | `bpm.request.build_reuse_matrix(snapshot, factset, decisions, *, user_policy=None)` |
| 生成计划 | `bpm.plan_generate.generate_fill_plan(factset, blueprint, *, base_dir, registry_dir=None)` |
| 离线校验计划 | `bpm.plan.validate_plan(plan, expected_operator=None, …)`；CLI：`python -X utf8 fill_once.py --fill-plan <计划.json> --expect-name <操作人> --validate-only` |
| 请求编排（离线复跑） | `python -X utf8 bpm_chain.py --material <既定材料.json> --document-type {travel,express,rd_materials,…} …`（validate-only，不触浏览器） |

`bpm_chain.py --material` 接受**既定材料 JSON**，不是任意 PDF/Excel 直接生成整单的通用命令；普通全额、油票覆盖等政策由各 runbook 选定的模型决定，本层不新增通用核算引擎。

## 5. 正式填写执行（已支持类型）

已支持类型（travel/express/rd_materials 等）一律走正式入口，不复制私有选择器。**单会话贯通入口（2026-10-28 起，实现＋离线验证；真实填写/保存待验）**为 `bpm.oneshot` 两分支：

```powershell
# 任务分支：同一会话内 身份→live 模板→事实补全→授权编译→计划生成/冻结→填写（模板值仅取本次 live 快照）
python -X utf8 -m bpm.oneshot --task "<任务.json>" --expect-name "<操作人>" [--keep-open-minutes 45]
# 既定计划分支：原样执行 v1.0 计划，不重读模板、不升级授权；--validate-only 返回 PLAN_VALIDATED / TASK_VALIDATED
python -X utf8 -m bpm.oneshot --fill-plan "<填报计划.json>" --expect-name "<操作人>" [--keep-open-minutes 45]
# 同绑定重试：复用原 run 冻结计划与授权记录；绑定不同即拒
python -X utf8 -m bpm.oneshot --task "<原任务.json>" --expect-name "<操作人>" --resume-run "<原run标识>"
```

- 任务分支**新开 run** 时，已有 `SAVE_INTENT`/`SAVE_UNCERTAIN`/已保存/不可读 journal 在启动浏览器前返回 `EXISTING_SAVE_INTENT`（exit 2），只走只读核实，不换 task_id 另建；`--fill-plan` 与 `--resume-run` 沿用既有入口行为（SaveController 在途只读核实兜底）。
- 终局 stdout 摘要在驻留结束后输出；立即交付锚点是 events 的 `result_delivered`（含 `finish_reason/task_status/save_status/plan_hash` 与生命周期计数）。
- 兼容分段入口（仅显式 `--fill-plan` 时等价）：

```powershell
python -X utf8 fill_once.py --fill-plan "<填报计划.json>" --expect-name "<操作人>" [--keep-open-minutes 45]
```

执行链为 `StructuredProbe`（精确唯一选择与写入）→ `DraftUIAdapter.capture_snapshot` → `bpm.verify.verify_snapshot`（独立 DOM 全值/行数/金额回读）。runbook 遇未支持控件按既有停点报告，不回临时脚本绕过校验；保存/提交族动作按 AGENTS 红线仅经专用授权路径。

## 6. 结果与耗时定位

- **每轮证据**：`automation/runs/<run>/events.jsonl`（追加式事件流）、`attempt_NNN/stage1_result.json`、attempt `evidence/` 目录；查询入口另有 run 根 `query_result.json`（含 `timings_s`：launch/auth/query/detail/total 与 retries）。
- **文件完整性**：沿用字节级 SHA-256 口径（`bpm.plan.file_hash`；证据语义见 [evidence-hash-semantics.md](evidence-hash-semantics.md)）。
- **耗时分析**：`tools.diagnostics.perf` 当前针对填写窗口（UI_START 起算）；查询/登录窗口无 UI_START，读 `query_result.json` 的分段耗时与 events 的 `timing` 事件，不把无 UI_START 的报告伪装成完整填写耗时报告。
- **单会话贯通分阶段诊断**（`bpm.oneshot` 任务分支，events 时间序）：`oneshot_task_offline_prepare`（`agent_offline_prepare_measured=false`——agent 离线材料理解/事实准备时长未计量）→ `template_live_read` → `facts_blueprint_completion` → `authorization_compile` → `plan_generation` → `plan_freeze`（`oneshot_plan_frozen`）→ 既有 `section_fill`/`independent_readback_verify` → `save_and_persisted_verify`（如授权保存）→ `result_delivered`（生命周期计数：正常认证复用路径 business_executors/browser_instances/business_contexts/lock_owners 各 1、driver_subprocesses=0，**按构造声明值**，fresh_scan 为动态位，逐 run 实测随真实首验落地；强制扫码等例外如实记录）。驻留（keep_open）不计入技术耗时。既有有效基线：`automation/runs/20261027-074251-9d71443f/events.jsonl`（真实差旅 20 行费用，技术耗时 307.8s；材料理解未计量）。


## 自驾新规则的来源与计划绑定

V3历史R=M+T模型不改。新模型使用可选 `self_drive_coverage`，由现有plan_generate生成并在validate_plan/load_plan独立重读来源、规则哈希、餐补参与日和逐组件/逐单金额；不能同时声明旧coverage。正式离线命令、来源包及限定支持结构见 [self-drive-inputs.md](self-drive-inputs.md)。通行票完整分配、油票覆盖不入费用、公里/餐补的有源政策免票保持分离；无真实输入时只到离线阶段，不填不存。

## 统一新建与同单修订入口（2026-10-29）

```powershell
python -X utf8 -m bpm.oneshot --task "已就绪任务.json" --expect-name "本次操作人"
python -X utf8 -m bpm.oneshot --fill-plan "计划.json" --expect-name "本次操作人"
python -X utf8 -m bpm.oneshot --fill-plan "修订计划.json" --prior-plan "原成功计划.json" --revision-authorization "明确修订授权.json" --expect-name "本次操作人" --validate-only
```

修订执行去掉validate-only；参数/授权工件由agent准备，不要求用户编写JSON。修订授权必须绑定原task、完整UUID/单号、原成功journal字节哈希及修订计划哈希，明确禁止提交。原计划须与原成功记录一致；原创建journal保留，修订在独立journal留痕且共享原task锁。

正常入口在一个guarded context内完成身份→精确列表/修改所选项→原单全量核实→限定新增费用/明细、备注与金额纠正→唯一保存→同context只读副页重开；不先另跑登录/模板脚本，不改申请人或银行身份、不重建原单。发现任何已有修订记录时不再进入编辑/填写，保存意图/未知结果/成功仅只读reconcile；其他已有状态要求只读审查。普通新建默认fill_only，只有本任务明确保存授权才保存，提交/流转持续禁止。

`fill_once.py --fill-plan`及含facts_payload的就绪task进程内转入上述正式入口，不再启动stage1子进程；无facts_payload的task仍只准备材料。显式legacy-regression仅保留原只填不存回归用途。运行时默认45分钟限时驻留属于交付后审阅，不是跨任务服务；同一阶段不靠关闭/重启浏览器推进，结束只关自有context并释放锁。

所有正式分支复用现有严格TLS/公司域与精确微信域守卫、禁ServiceWorker/WS上游、禁止重定向和--no-proxy-server；只从受保护原认证加载，保留原profile，不用缓存文件存在推断身份。维护/建设授权不等于线上业务授权。

本次仅补统一CLI并离线验证，未访问OA；此前真实测试保存与模拟边界见[脱敏证据索引](../../../../docs/oa-validation-20261029.md)。正式oneshot完整新材料首验仍待当次输入。最新本地构建结果单独记录，不把历史571项视作新增CLI首验。
