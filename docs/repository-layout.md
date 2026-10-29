# 仓库目录与维护入口

根目录保留项目规则、说明、常用命令兼容入口及 workflow 必需文件。业务实现集中在 `bpm/`，诊断和验证工具集中在 `tools/`；新增文件按用途归类。

```text
repo/
├─ README.md / AGENTS.md / CLAUDE.md / STATE.md
├─ fill_once.py / bpm_login.py / bpm_template.py / bpm_chain.py
├─ stage1_browser_probe.py / stage1_probe_selftest.py / verify_bpm_build.py
├─ bpm/                         业务实现与统一仓库路径定位
├─ tools/
│  ├─ diagnostics/              事件耗时、类型查询、历史内容普查
│  ├─ verification/             自测、离线 DOM 验证、统一构建验证
│  └─ legacy/                   历史一次性辅助脚本
├─ tests/                       自动化测试与合成夹具
├─ .claude/skills/bpm-fill-run/  统一 Skill、手册及入口与未来扩展说明
├─ automation/                  schema、类型/场景配置及既有运行工件
├─ docs/                        项目说明、探索与复盘
├─ feature01-细化报销skill/      既有需求、冻结合同与案例原件
├─ team-progress/               workflow 历史与交接证据
├─ templates/                   参考模板图与识别材料
├─ patches/                     外部工具补丁
├─ Windows-MCP/                 独立外部仓库
└─ legacy-ia2/                  只读历史存档
```

## 业务代码与命令

业务库统一使用 `bpm.<模块>` 导入。`bpm/paths.py` 负责定位仓库根，配置、运行目录、profile 和 registry 继续使用既有位置；禁止由某个业务模块的所在目录另建一套运行数据目录。

| 职责 | 实现 |
|---|---|
| 任务入口、只读登录、只读查询、模板、离线链编排 | `bpm/fill_cli.py`、`bpm/login.py`、`bpm/query.py`（`python -X utf8 -m bpm.query`，关键词/精确单号只读查询）、`bpm/template.py`、`bpm/chain.py` |
| 单会话贯通执行（任务/既定计划两分支；授权编译、副页核验、立即交付与限时驻留） | `bpm/oneshot.py`（普通新建/显式同单修订统一入口；`python -X utf8 -m bpm.oneshot --task|--fill-plan …`；实现＋离线验证，真实填写/保存待验，见 [施工结果](../feature02-扩展更多单据类型/单会话贯通与自动保存接线施工结果.md)） |
| 原件、材料、事实与计划 | `bpm/collect.py`、`bpm/extraction.py`、`bpm/materials.py`（含 `python -X utf8 -m bpm.materials prepare` 离线准备 CLI）、`bpm/facts.py`、`bpm/request.py`、`bpm/plan.py`、`bpm/plan_generate.py` |
| 身份、类型及场景金额规则 | `bpm/identity.py`、`bpm/types.py`、`bpm/coverage.py`、`bpm/self_drive.py` |
| 浏览器、会话、填写、独立核验与保存 | `bpm/browser_probe.py`、`bpm/session.py`、`bpm/ui.py`、`bpm/verify.py`、`bpm/save.py`、`bpm/revision.py`（原task/UUID/journal绑定的受限同单修订） |

根目录七个 Python 文件只转发到对应实现，保留既有命令和参数。开发、排错及源码审计应读取实际实现。兼容入口的模块导入指向同一个实现对象，避免身份判断或测试替身落到另一份模块状态。

## 工具与历史脚本

以下命令在仓库根显式运行；诊断工具保留原有使用边界，目录迁移不构成访问 OA 或扩大普查的授权。

| 原位置 | 新位置 / 调用方式 |
|---|---|
| `bpm_perf.py` | `tools/diagnostics/perf.py`；`python -X utf8 -m tools.diagnostics.perf <run目录>` |
| `list_type_query.py` | `tools/diagnostics/type_query.py`；`python -X utf8 -m tools.diagnostics.type_query ...` |
| `travel_census.py` | `tools/diagnostics/travel_census.py`；`python -X utf8 -m tools.diagnostics.travel_census ...` |
| `stage1_offline_verify.py` | `tools/verification/offline_dom.py`；`python -X utf8 -m tools.verification.offline_dom` |
| `stage1_probe_selftest.py` | `tools/verification/probe_selftest.py`；原根目录命令兼容保留 |
| `verify_bpm_build.py` | `tools/verification/build.py`；原根目录命令兼容保留 |
| `_gen_manifest.py`、`_schema_v02.py`、`_chk_orphan2.ps1` | `tools/legacy/`，按历史用途保留；说明见该目录的 [README](../tools/legacy/README.md) |

其他旧 `bpm_<模块>.py` 的实现迁到 `bpm/<模块>.py`；`fill_once.py` 的实现是 `bpm/fill_cli.py`，`stage1_browser_probe.py` 的实现是 `bpm/browser_probe.py`。完整路径映射及迁移前源码哈希见 [迁移记录](../automation/maintenance/20261027-repo-layout/before-manifest.json)。

## Windows-MCP 的定位与重建入口

当前 `bpm/`、`tools/` 的生产执行使用 Playwright，Windows-MCP 不是报销流程的必需依赖。`Windows-MCP/` 是被父仓库忽略的独立外部仓库，用于早期 CEF/IA2 桌面路线探索；历史能力与限制见 [路线实测报告](路线与评估/Windows-MCP路线实测报告.md)。

父仓库保留 [CEF/IA2 补丁](../patches/windows-mcp@5b24a8a-cef-ia2.patch)。需要复现桌面探索时，按 [Windows-MCP 固定版本重建说明](windows-mcp-rebuild.md) 核对版本、应用补丁并另行验证；**干净环境重建步骤尚未实跑验收**，不要求新接手者先安装它。

## 证据、工作流与后续维护

- workflow 的根状态、team-task、team-progress 及本轮输入/备份保留原位，继续由既有 helper 和合法归档流程管理。终态不表示这些文件可直接删除或搬走。
- 冻结合同、案例原件、旧 run、旧 manifest、registry、认证文件及 `legacy-ia2/` 保持历史原样。旧文档中的代码路径可按本文件映射到现行实现。
- 迁移会改变源码及部分类型解析器哈希。新任务绑定现行代码；旧任务仍按原计划、身份和配置哈希核对，不能通过改写旧计划、registry 或历史 manifest 绕过不一致。
- 统一构建清单递归覆盖 `bpm/`、诊断/验证工具、七个兼容入口和 Skill 文档。自测的源码守卫直接读取 `bpm/browser_probe.py`，测试覆盖全部现行实现。
- 迁移前副本仅覆盖明确列出的源码、测试和文档，位于迁移记录同目录的 Git 排除 `before/`；认证、个人会话元数据及业务记录不进入该副本。
- 本次归类整理只调整工程结构；业务能力、尚未完成的自驾接线及验收状态仍见 [STATE.md](../STATE.md)。

自驾新规则来源准备与计划绑定：`bpm/self_drive_plan.py`（纯离线，接入plan_generate/plan）；能力与验证分层统一查 [runbook-maturity.md](runbook-maturity.md)。

已知V3版式公里表副本回填与持久化重算：`bpm/self_drive_workbook.py`，与self_drive_plan来源准备衔接，独立隐藏Excel实例仅操作本次副本。
