# 配置 codex-glm（Windows / PowerShell 7）

供用户或 agent 使用：先检查本机，再选择“只更新启动函数”或“全新安装”，最后做真实验收。Key 从环境变量读取，禁止展示明文。

## 2026-10-28 对齐检查与 mc-expert v2 同步

- 对照 claude-glm 10-26/10-27 的三项更新逐一判定：视觉自动委派（`--agents` 启动注入 glm-5.3-flash）与 `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP` 是 Claude Code 专属机制，Codex CLI 无对应入口，不迁移；启动降级修复在 codex-glm 无同类问题（LiteLLM 是 Zhipu 路线硬依赖，失败时 OpenRouter 路线仍可用）。模型与上下文两侧本已一致（glm-5.3 主模型 / z-ai/glm-5.2 备用 / 1M 窗口）。
- 唯一真漂移：`agents/mc-expert.toml` 副本停在 10-12 版，Mc-Expert-repo 母本 10-27 已升级 review-contract v2（HISTORY / ENHANCED_FINAL 双 profile，高风险 CUTOVER_NATIVE_REQUIRED）。本包已同步 v2 副本，contract 读取路径改为「安装位 `~/.codex-glm/agents/review-contract-v2.md` 优先、母本绝对路径兜底」——本机 agents 是 junction、安装器跳过部署，走兜底路径；同事机器由安装器部署 contract，走安装位。
- 新增随包文件 `agents/review-contract-v2.md`（母本字节级副本，137 行，无 fixtures 运行时依赖）；安装器第 5 步同步部署两文件（agents 为链接时照旧整体跳过）。

详细检查过程见本目录 `2026-10-28 对齐claude-glm最新配置检查+mc-expert-v2同步.md`。

## 2026-10-28 视觉自动委派 glm-5.3-flash（对标 claude-glm，退役 4.6V MCP）

- 主模型 glm-5.3 不变；图片/截图/票据/扫描 PDF 渲染页由 CODEX_HOME 全局 `AGENTS.md` 规则引导，调 `vision-read.ps1` 固定走 **glm-5.3-flash**（Zhipu coding 端点，已实测可用）。全程只用 ZHIPU_API_KEY，不经 OpenRouter。
- 脚本不直连 HTTPS：codex 的 Windows 沙箱（受限令牌）会让 Schannel 出站 TLS 失败（`安全包中没有可用的凭证`）；脚本改调本机 LiteLLM（`http://127.0.0.1:4000` 明文），HTTPS 由沙箱外的 LiteLLM 进程完成。LiteLLM 未运行时脚本自动拉起。
- `glm-config.yaml` 新增 `glm-5.3-flash` 条目（标准 `openai/glm-5.3-flash` 写法；`openai/chat_completions/` 桥前缀只适用于 responses 客户端调用，直接 chat 调用会 400 Unknown Model）。
- 旧 `zai-vision-primary-glm46v` MCP 条目（@z_ai/mcp-server，glm-4.6v）已从 live config.toml 移除；其包装脚本本就不在分发包内。
- 全局 AGENTS.md 在 Windows 有历史加载 bug 报告（codex #8759）；本机 0.164.0 实测正常。新机器装完先跑一次真实图片任务确认路由生效。

完整过程与验证矩阵见本目录 `2026-10-28 codex-glm视觉切换flash自动委派（对标claude-glm）.md`。

## 本机评估（2026-10-12）

- 本机 Codex CLI：`0.162.1`，来自桌面 App 的 `bin/codex.exe`；没有 npm 全局 Codex 包。因此打包脚本现在优先使用 PATH 中的原生 EXE，npm 作为后备。
- 模型与审批配置已经一致：`glm-5.3`、1M 上下文、240K 自动压缩、`max` 思考、`workspace-write` + `on-request` + `auto_review`。这次不调整这些值。
- LiteLLM `1.91.1` 的虚拟环境完整；YAML 和工具翻译脚本与分发包一致。9 月的错误日志不能代表今天的故障。
- 已备份并更新本机启动函数，修复退出后残留 `LITELLM_KEY`；项目信任、钩子信任、视觉 MCP 保留。
- 实测通过：冷启动后 GLM-5.3 回复、只读 PowerShell 工具调用、退出环境恢复；`codex-auto-review` 路由返回 HTTP 200 和正确回复。未触发真实提权审批，OpenRouter 备用路线未实测。

## 已安装机器：优先只更新函数

在本目录运行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\install-codex-glm.ps1 -UpdateProfileOnly
```

它先备份，再更新 profile 中的单个函数；保留其他内容，重复运行不追加。新版完整恢复账号目录、路由、本地代理 Key 和代理变量，并正确处理有空格的代理脚本路径。

## 全新机器：安装

前提：PowerShell 7、Python 3.10+、用户环境变量 `ZHIPU_API_KEY`。检查 Key 只返回是否存在：

```powershell
[bool][Environment]::GetEnvironmentVariable('ZHIPU_API_KEY','User')
```

1. 打包者在已安装 Codex 的机器运行 `pack-codex-offline.ps1`，得到 `codex-offline/`。
2. 把整个本目录拷给安装者。
3. 安装者运行：

```powershell
pwsh -ExecutionPolicy Bypass -File .\install-codex-glm.ps1
```

安装器复用已有 Windows Codex，或从离线包安装；配置 LiteLLM、独立的 `~/.codex-glm` 和启动函数。完整安装会写入包内配置模板，覆盖前备份；已有机器优先用上面的只更新入口。`agents` 若是共享目录链接，则保留原内容。4000 端口已有服务时跳过启动/关闭冒烟；只清理本次创建的进程树。

## 使用和验收

新开 PowerShell，在项目目录运行 `codex-glm`；默认选 `[1] Zhipu`，`[2] OpenRouter` 为备用路线，需对应 Key 和可用网络。收到真实 GLM 回复且能执行一个只读命令才算成功。

```text
Zhipu: Codex -> localhost:4000 LiteLLM -> api.z.ai -> glm-5.3
OpenRouter: Codex -> openrouter.ai/api/v1 -> z-ai/glm-5.2
```

这些是本包当前固定路线。自动审批由 `approvals_reviewer=auto_review` 控制。[官方审批说明](https://learn.chatgpt.com/docs/sandboxing/auto-review)

## 排错与文件入口

- 启动失败先看 `~/.codex-glm/litellm/proxy.err.log` 的第一个原始错误；端口监听只说明服务启动，不代表 Key/模型可用。
- 确认虚拟环境同时有 `Scripts/python.exe` 和 `Scripts/litellm.exe`。
- 自定义模型元数据警告不等同请求失败；以实际回复和 HTTP 结果为准。
- 自动审批不扩大沙箱范围，仍可拒绝请求。不要改成绕过所有权限来解决普通配置问题。
- 需要回滚时恢复对应 `.bak-*`，再新开 PowerShell。
- `vision-read.ps1` 失败：看报错里的 inner 链与 `~/.codex-glm/litellm/proxy.err.log`。「安全包中没有可用的凭证」= codex 沙箱的 Schannel TLS 限制，本方案已通过本机 LiteLLM 绕过；若仍出现说明脚本被改回直连 HTTPS，恢复包内版本。
- 图片任务没自动走 flash：确认 `~/.codex-glm/AGENTS.md` 的 vision 标记块在位、codex 版本足够新（Windows 全局 AGENTS.md 有历史 bug，本机 0.164.0 实测正常）；重跑安装器可重新部署第 6 步。

| 文件 | 用途 |
|---|---|
| `install-codex-glm.ps1` | 安装或只更新 profile |
| `codex-glm-profile-func.ps1` | provider 选择、启动代理和完整环境恢复 |
| `codex-glm-config.toml` | 模型、上下文、provider 与审批模板 |
| `litellm/` | 代理配置、启动脚本和工具翻译 |
| `agents/mc-expert.toml` | GLM 自定义陪审代理；不保证等价其他模型 |
| `agents/review-contract-v2.md` | ENHANCED_FINAL 终审共享契约（Mc-Expert-repo 母本副本；agent 定义优先读安装位） |
| `vision/vision-read.ps1` | 图片理解助手：固定 glm-5.3-flash，经本机 LiteLLM 转发（避开沙箱 TLS 限制） |
| `vision/AGENTS-vision-routing.md` | 视觉路由规则块；安装器幂等合并进 `~/.codex-glm/AGENTS.md`（标记块内替换，其他内容保留） |
| `pack-codex-offline.ps1` | 打包本机原生 Codex 与可选 code-mode host |

其他机器也应完成真实回复和工具调用验收。
