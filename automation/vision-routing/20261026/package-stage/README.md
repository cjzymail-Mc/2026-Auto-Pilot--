# 一键配置 claude-glm（Git Bash 配置包）

把本文件夹拷到已安装 Claude Code 的 Windows 电脑，运行安装脚本后，在 Git Bash 中使用 `claude-glm`。本包配置独立的 `~/.claude-glm` 账号，不安装 Claude Code 本体。

## 2026-10-26 主模型与视觉自动委派

- 默认模型明确为 `glm-5.3`，迁移旧的 `model=haiku`。启动脚本显式选择各provider的主模型，用户手工传入的 `--model` 仍优先，Haiku映射不再决定主会话。
- Zhipu菜单1加载私有 `vision-routing/agents.json` 和 `routing.md`。主会话遇到需要看图的任务，调用固定 `glm-5.3-flash`、仅有Read工具的 `vision-reader`，结果交回主会话继续工作。
- DeepSeek/OpenRouter不加载这套GLM视觉定义。普通代码子agent及现有hooks/插件保持原有配置。无需Vision MCP、额外API Key或新增常驻窗口。
- 新增两个配置文件会由安装器部署、验证并备份；其他账户或共享agents目录不写入。最低采用本次已实测的Claude Code 2.1.299。
- 视觉自动委派依靠明确的agent描述与启动规则，已经过实际链路验证；不是按文件类型硬拦截的确定性路由。图片附件须有可访问的本地路径；扫描PDF先渲染图片。有文字层的PDF继续优先文字提取。
- 识别可能出错。未标注字段必须null，关键号码/金额继续核验。若启用了 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`，需先关闭，才能使用独立视觉模型。

本机真实模型、字段及分发包验证结论见上层 `2026-10-26 glm-5.3主模型与Flash视觉自动委派实测.md`。原始错误样本亦保留，不把模型识别包装成必然正确。

## 2026-10-12 同步内容

本次同步 2026-10-09 已验证的修复：

- 启动函数在子 shell 中设置账号、模型和代理；退出、出错或缺少 Key 时，父终端环境保持原样。
- 保留 `permissions.defaultMode="auto"`，设置 `CLAUDE_CODE_AUTO_MODE_SERVER="0"`，明确使用客户端分类器。这里的 `0` 选择审批检查路径，auto mode 仍开启；检查请求按智谱原有规则消耗额度。
- 补入 `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000`。默认压缩设置仍为窗口 `400000`、比例 `60`；本机历史会话在约 22.8 万～24.7 万 token 时压缩。
- 自带已验证的 Windows PATH 修复钩子。安装到私有 `~/.claude-glm/local-hooks/`，通过 `SessionStart` 和 `CLAUDE_ENV_FILE` 在 Bash 命令执行前修正分号形式的 Windows PATH。
- 安装器会先验证再备份更新旧启动函数，重复执行不追加第二个函数；保留用户自己的其他钩子、插件和已有压缩窗口设置。

本机 2026-10-09 端到端证据：Claude Code **2.1.295 + glm-5.3 + 智谱 Key** 在 `auto` 模式下成功执行 Git/Python 检查，PATH 钩子成功，`permission_denials=[]`。本次分发包更新另做临时用户目录安装、重复安装、环境隔离和 PATH 验证；不把旧记录改写为新日期的联网验收。

官方依据：[客户端分类器变量](https://code.claude.com/docs/en/env-vars)、[会话环境钩子](https://code.claude.com/docs/en/hooks#persist-environment-variables)、[自定义模型上下文窗口](https://code.claude.com/docs/en/model-config#correct-the-window-for-a-gateway-or-custom-model-id)。

## 安装前提

| 必备 | 检查方法 | 说明 |
|---|---|---|
| PowerShell 7 | `pwsh --version` | 不使用系统自带的 PowerShell 5.1 |
| Claude Code 2.1.299+ | `claude --version` | 本轮路由的实测版本；本包不装本体 |
| Git for Windows | Git Bash 能打开 | 安装器会检测 Git Bash 和 `cygpath`，避免误用 WSL 的 `bash` |
| Python 3.10+ | `python --version` | PATH 钩子只用标准库，不安装 pip 包；Store 占位程序不算 Python |
| 智谱 Key | `[bool][Environment]::GetEnvironmentVariable("ZHIPU_API_KEY","User")` | 设为用户环境变量后新开终端；只显示是否存在，不展示 Key |

可选：`DEEPSEEK_API_KEY` 对应路线 2；`OPENROUTER_API_KEY` 和可用代理对应路线 3。

本包保留已验证的模型路线：Zhipu 使用 `glm-5.3`，OpenRouter 备用使用 `z-ai/glm-5.2`，DeepSeek 使用原有 `deepseek-v4-pro[1m]` / `deepseek-v4-flash`。这不是对其他平台最新上架模型的声明。

## 安装或更新

在本文件夹中打开 PowerShell 7：

```powershell
pwsh -ExecutionPolicy Bypass -File .\install-claude-glm.ps1
```

脚本检测前提，更新 settings 和私有钩子，更新 `.bashrc` 中的新旧格式启动函数，最后发送一条小规模智谱请求检查 Key、接口与模型。请求会产生少量 API 用量。

已经确认 Key 和模型可用，只同步本次修复时：

```powershell
pwsh -ExecutionPolicy Bypass -File .\install-claude-glm.ps1 -SkipSmoke
```

安装器会按新机器实际的 Python、Git Bash 和用户目录生成钩子命令，不使用本机 `xy198` 的路径。若 Git Bash 用户目录重定向，用 `-UserDirectory '对应的 Windows 用户目录'` 指定；该目录必须与 Git Bash 中的 `~` 对应。

已有 settings 会合并更新：保留其他钩子、插件、自定义选项和已设置的压缩窗口，补齐缺失默认值，并应用 1M 上下文、客户端分类器、auto 默认模式，以及显式主模型 glm-5.3。只安装本包的 PATH 钩子；不复制本机的 StopFailure、UserPromptSubmit 或共享目录生态。

## 使用与验收

新开 Git Bash，在项目目录运行：

```bash
claude-glm
```

回车默认选 `[1] Zhipu`。接续原会话：

```bash
claude-glm --resume
```

看到 GLM 回复、auto 模式可用，并能执行 `git --version` / `python --version`，才算这台机器的端到端验收。普通 Bash、原生 Claude 和其他账号的设置不会因一次 `claude-glm` 调用而残留 GLM 环境变量。

## 故障速查

| 症状 | 处理 |
|---|---|
| 没找到 Claude Code / Git Bash / Python | 先补齐安装前提，再运行本脚本 |
| 提示免费分类器接口不兼容 | auto mode 可继续使用。本包设置 `CLAUDE_CODE_AUTO_MODE_SERVER=0` 使用客户端检查，保持 `defaultMode=auto` |
| `git: command not found`，但 Git 已安装 | 重跑安装器同步 PATH 钩子，新开 Git Bash 后 `claude-glm --resume`；确认 SessionStart 钩子没有报错 |
| 想更新旧启动函数 | 直接重跑安装器；无需手工删除函数，也不会重复追加 |
| Bash 原文件语法错误或多个同名函数 | 安装器拒绝覆写/重复追加。先查看提示修复原文件，再重跑 |
| 安装目标是目录链接 | 私有配置/钩子目录不能指向共享源；使用独立 `.claude-glm/local-hooks`，不通过 `hooks` 链接写共享仓库 |
| 新函数没有生效 | 新开 Git Bash；旧终端内已加载的函数不会因磁盘文件改变而自动替换 |
| 冒烟失败 | 配置已就位；检查网络、Key、智谱套餐额度和接口。可用 `-SkipSmoke` 重跑配置，实际 GLM 回复仍需单独验收 |

## 文件与回滚

| 文件 | 用途 |
|---|---|
| `install-claude-glm.ps1` | 安装/更新入口，检测实际运行路径、验证、备份与合并配置 |
| `claude-glm-settings.json` | 基础默认配置；路径钩子的实际命令由安装器生成 |
| `claude-glm.bashrc.snippet` | 在子 shell 中运行的三 provider 启动函数 |
| `prepare-bash-env.py` | 已验证的 Windows PATH 修复钩子，Python 标准库，无外部依赖 |
| `vision-routing/agents.json` | 固定Flash、仅Read的视觉子agent定义 |
| `vision-routing/routing.md` | Zhipu分支的自动委派及事实输出规则 |

设置、已有私有钩子与 `.bashrc` 改动前，会生成 `.bak-claude-glm-时间戳`；相同内容重复安装不产生额外备份。回滚时恢复对应原文件，再新开 Git Bash。Key 只从环境变量读取；冒烟请求通过内存中的 HTTP 请求头传递，不写到命令行或临时文件。

上层文件夹的 7/8 月脚本与记录保留当时事实；当前可安装的版本以本 `claude-glm-dist/` 为准。
