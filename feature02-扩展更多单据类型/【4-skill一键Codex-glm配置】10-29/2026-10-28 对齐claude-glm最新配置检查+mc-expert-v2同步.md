# 对齐 claude-glm 最新配置检查 + mc-expert v2 同步（2026-10-28）

> 性质：本分发包的更新记录。以 claude-glm 10-26/10-27 的最新配置为输入，逐项判定是否需要同步到 codex-glm 分发包；顺带做了一次包 vs live 全量漂移扫描。结论：claude-glm 三项更新均不迁移，唯一真漂移是 mc-expert 陪审 agent 副本落后母本，已同步。

## 检查输入：claude-glm 最新配置（10-26 / 10-27）

| claude-glm 更新 | 内容 | codex-glm 判定 |
|---|---|---|
| 10-26 视觉自动委派 | `--agents` 启动注入 glm-5.3-flash Read-only vision-reader + `--append-system-prompt` 路由规则；要求 Claude Code ≥ 2.1.299 | **不迁移**。`--agents` / `--append-system-prompt` 是 Claude Code CLI 专属启动参数，Codex CLI 无对应入口；Codex 的 custom agent（mc-expert.toml）是按需 spawn 的陪审代理，不是会话级视觉路由 |
| 10-27 后台 shell 回收禁用 | settings env 补 `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP="1"`（team-workflow 低内存杀空闲 wait 事件） | **不迁移**。`CLAUDE_CODE_*` env 只有 Claude Code 读；Codex 无后台 shell 回收机制，写入无效 |
| 10-27 启动降级 | vision-routing 文件缺失从 `return 1` 堵死改为警告 + 正常启动 | **无同类问题**。codex-glm 启动器唯一的硬失败是 LiteLLM 代理未就绪——那是 Zhipu 路线的硬依赖（没有翻译桥就到不了 z.ai），失败有明确日志指引，且 OpenRouter 路线与原生 codex 不受影响，不存在「可选增强堵死入口」的结构 |

模型与上下文两侧本已一致（Zhipu 主模型 glm-5.3 / OpenRouter 备用 z-ai/glm-5.2 / 1M 窗口），无需动作。auto_review 映射 glm-4.5-air 是 2026-08 实测选择（glm-4.7-flash 429），不动。

## 漂移扫描：包 vs live（`~/.codex-glm`）vs 母本

| 文件 | 结果 | 判定 |
|---|---|---|
| `codex-glm-config.toml` | 核心配置零漂移；live 多出 `[projects.*]` / `[hooks.state]` / `[mcp_servers.*]` 机器私料 | 08-10 已列「有意排除」，不动 |
| `litellm/glm-config.yaml` | 仅换行符差异（CRLF） | 不动 |
| `litellm/tool_filter.py` | 仅换行符差异 | 不动 |
| `litellm/start-glm-proxy.ps1` | 仅数组元素空格差（08-10 已知） | 不动 |
| `codex-glm-profile-func.ps1` | 函数体与本机 profile 内完全一致 | 不动 |
| `agents/mc-expert.toml` | **真漂移**：包副本停在 10-12 版（无 profile 概念），Mc-Expert-repo 母本 10-27 已升 review-contract v2（HISTORY / ENHANCED_FINAL 双 profile、AUTHOR_RUNTIME/RISK_CLASS envelope、高风险 CUTOVER_NATIVE_REQUIRED、共享机械否决器） | **本次同步** |

本机 live `~/.codex-glm/agents` 是指向母本的 junction，live 已经是 v2，本机无需部署动作。

## 改了什么

| 文件 | 改动 |
|---|---|
| `agents/mc-expert.toml` | 整体替换为母本 v2，仅一处适配：contract 读取路径从母本绝对路径改为「安装位 `~/.codex-glm/agents/review-contract-v2.md` 优先、母本绝对路径兜底」；头部加一行分发副本说明 |
| `agents/review-contract-v2.md`（新增） | 母本 `.agents/mc-expert-common/review-contract-v2.md` 字节级副本（SHA256 一致）；ENHANCED_FINAL 终审必需，无 fixtures 运行时依赖 |
| `install-codex-glm.ps1` | 第 5 步从单文件改为双文件循环部署（mc-expert.toml + review-contract-v2.md），agents 为链接时照旧整体跳过（break 不逐文件重复警告）；备份逻辑不变；顶部 `.DESCRIPTION` 步骤清单同步 |
| `README.md` | 新增「2026-10-28 对齐检查与 mc-expert v2 同步」段；文件清单补 `agents/review-contract-v2.md` 行 |

路径适配的理由：母本 toml 把 contract 路径写死为 `D:/Downloads/.../Mc-Expert-repo/...`，只在装了 Mc-Expert-repo 的机器上成立；分发包要冷启动自足（08-10 定下的原则），contract 必须随包走。本机 agents 是 junction、安装器跳过部署，安装位不存在 → 走母本兜底路径，行为不变；同事机器由安装器部署 contract → 走安装位。

## 没动的

- `litellm/` 三件套、`codex-glm-config.toml`、`codex-glm-profile-func.ps1`、`pack-codex-offline.ps1`（不涉及 agents 内容）。
- `litellm/__pycache__/tool_filter.cpython-312.pyc`：未入 git 的本地运行残留，无害留置。
- 母本侧（Mc-Expert-repo）零改动：只读取，未写。

## 验证

- `install-codex-glm.ps1` 通过 PowerShell 解析器校验（`[Parser]::ParseFile`，无错误）。
- 包内 `mc-expert.toml` 通过 TOML 语法解析（Python `tomllib`）；与母本 diff 仅 2 行（头部说明 + contract 路径）。
- `review-contract-v2.md` 与母本 SHA256 一致。
- 第 5 步新部署逻辑用临时目录做过隔离验证：两文件成功部署；目标文件被改动后重跑会先生成 `.bak-install-*` 备份再覆盖（阳性对照通过）。

> **补记（同日下午）**：上表「10-26 视觉自动委派 **不迁移**」的**结论**已被用户当天下午的决策推翻——codex-glm 改为对标 claude-glm 落地视觉切换（主 glm-5.3 + 图片自动委派 glm-5.3-flash）。**机制判断仍成立**（`--agents`/`--append-system-prompt` 确实是 Claude Code 专属，无法照搬），只是「机制不可迁移 → 结论不迁移」这步被用户改成了「机制不可迁移 → 换 Codex 侧等价机制（全局 AGENTS.md 规则 + vision-read.ps1 确定性脚本）实现同一目标」。实施记录见本目录 `2026-10-28 codex-glm视觉切换flash自动委派（对标claude-glm）.md`。另：上表判定 live config.toml 的 `[mcp_servers.*]` 为「机器私料不动」——其中的 `zai-vision-primary-glm46v` 条目同日随视觉方案切换退役移除。

## 验收要点（给下一棒 / 同事）

- 同事机器跑 `install-codex-glm.ps1`，第 5 步应显示「mc-expert 陪审 agent 就位：…mc-expert.toml（+ review-contract-v2.md）」，且 `~/.codex-glm/agents/` 下两文件都在。
- 想验陪审 v2：让 codex-glm 请 mc-expert，子代理第一行回显 `PROVIDER_ROUTE=1=Zhipu | ...`；带 `REVIEW_PROFILE=ENHANCED_FINAL` 的调用应能读到 contract 并输出八个审计面，不再返回旧版四字段之外的拒绝。
- 本机无感：live 走 junction 已是 v2 + 母本兜底路径，无需重装。
