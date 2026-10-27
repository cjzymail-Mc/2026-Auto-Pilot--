"""Stage a minimal update to the user's existing portable config package."""
from pathlib import Path
import json
import hashlib

HERE = Path(__file__).resolve().parent
PACKAGE = Path(r"D:\Downloads\Mc Claude Code Workshop\Mc-emoji\[feature-04-Hot-Fix-Clash+wsl-codex]\[3-Openrouter+claude配置-glm]\claude-glm-dist")
STAGE = HERE / "package-stage"
STAGE.mkdir(exist_ok=True)
SOURCES = {}


def read(name):
    p = PACKAGE / name
    SOURCES[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text(encoding="utf-8-sig")


def write(name, text):
    p = STAGE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


settings = json.loads(read("claude-glm-settings.json"))
settings["model"] = "glm-5.3"
settings["_comment"] += " Main model is explicitly glm-5.3; Zhipu loads the fixed glm-5.3-flash Read-only visual agent at startup. Other provider routes and explicit --model are preserved."
write("claude-glm-settings.json", json.dumps(settings, ensure_ascii=False, indent=2) + "\n")

snippet = read("claude-glm.bashrc.snippet")
live = (Path.home() / ".bashrc").read_text(encoding="utf-8")
start = live.index("claude-glm() (")
end = live.index("\n)\n", start) + 2
function = live[start:end]
portable = '''  # Use the Git Bash running this launcher, including custom install locations.
  if [[ -x /usr/bin/cygpath ]]; then
    export CLAUDE_CODE_GIT_BASH_PATH="$(/usr/bin/cygpath -w "$BASH")"
  fi'''
assert function.count('  export CLAUDE_CODE_GIT_BASH_PATH="C:/Program Files/Git/bin/bash.exe"') == 1
function = function.replace('  export CLAUDE_CODE_GIT_BASH_PATH="C:/Program Files/Git/bin/bash.exe"', portable)
write("claude-glm.bashrc.snippet", "# claude-glm: isolated provider settings; main GLM-5.3 and Zhipu-only Flash vision routing.\n# 2026-10-26 portable distribution update.\n" + function + "\n")

installer = read("install-claude-glm.ps1")
installer = installer.replace("  $privateHooks = Join-Path $GlmDirectory 'local-hooks'", "  $privateHooks = Join-Path $GlmDirectory 'local-hooks'\n  $privateVision = Join-Path $GlmDirectory 'vision-routing'\n  $agentPath = Join-Path $privateVision 'agents.json'\n  $routingPath = Join-Path $privateVision 'routing.md'", 1)
installer = installer.replace("@($GlmDirectory, $privateHooks, $settingsPath, $hookPath)", "@($GlmDirectory, $privateHooks, $privateVision, $settingsPath, $hookPath, $agentPath, $routingPath)", 1)
installer = installer.replace("  $settings['permissions']['defaultMode'] = 'auto'", "  $settings['permissions']['defaultMode'] = 'auto'\n  # Migrate the old Haiku-bound default; the launcher pins each provider's main model.\n  $settings['model'] = 'glm-5.3'", 1)
anchor = "  $hookBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'prepare-bash-env.py'))"
replacement = '''  $agentBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'vision-routing/agents.json'))
  $routingBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'vision-routing/routing.md'))
  $agentDefinition = [Text.Encoding]::UTF8.GetString($agentBytes) | ConvertFrom-Json -AsHashtable
  if ($agentDefinition['vision-reader']['model'] -cne 'glm-5.3-flash' -or ($agentDefinition['vision-reader']['tools'] -join ',') -cne 'Read') {
    throw '视觉agent配置必须为glm-5.3-flash且仅Read，未安装。'
  }
  if ($routingBytes.Length -eq 0) { throw '视觉路由规则为空，未安装。' }
  [void][IO.Directory]::CreateDirectory($privateVision)
  Write-WithBackup $agentPath $agentBytes
  Write-WithBackup $routingPath $routingBytes
''' + anchor
assert installer.count(anchor) == 1
installer = installer.replace(anchor, replacement, 1)
anchor = 'Write-Ok "Claude Code：$claudeVer"'
replacement = anchor + r'''
if ([string]$claudeVer -notmatch '(\d+\.\d+\.\d+)' -or [version]$Matches[1] -lt [version]'2.1.299') {
  throw '本视觉路由包已在Claude Code 2.1.299验证，请升级到2.1.299或更新版后安装。'
}'''
assert installer.count(anchor) == 1
installer = installer.replace(anchor, replacement, 1)
installer = installer.replace("Write-Host 'auto mode 保持开启，使用客户端分类器；收到 GLM 回复且能执行命令才算端到端验收。'", "Write-Host '默认主模型glm-5.3；Zhipu图片任务委派glm-5.3-flash。auto mode与PATH钩子保留。旧会话不会自动获得新启动参数。'", 1)
write("install-claude-glm.ps1", installer)

for name in ["agents.json", "routing.md"]:
    text = (Path.home() / ".claude-glm/vision-routing" / name).read_text(encoding="utf-8")
    write("vision-routing/" + name, text)
# An unchanged existing dependency makes the staged package self-contained for temporary-home checks.
write("prepare-bash-env.py", read("prepare-bash-env.py"))

readme = read("README.md")
section = '''## 2026-10-26 主模型与视觉自动委派

- 默认模型明确为 `glm-5.3`，迁移旧的 `model=haiku`。启动脚本显式选择各provider的主模型，用户手工传入的 `--model` 仍优先，Haiku映射不再决定主会话。
- Zhipu菜单1加载私有 `vision-routing/agents.json` 和 `routing.md`。主会话遇到需要看图的任务，调用固定 `glm-5.3-flash`、仅有Read工具的 `vision-reader`，结果交回主会话继续工作。
- DeepSeek/OpenRouter不加载这套GLM视觉定义。普通代码子agent及现有hooks/插件保持原有配置。无需Vision MCP、额外API Key或新增常驻窗口。
- 新增两个配置文件会由安装器部署、验证并备份；其他账户或共享agents目录不写入。最低采用本次已实测的Claude Code 2.1.299。
- 视觉自动委派依靠明确的agent描述与启动规则，已经过实际链路验证；不是按文件类型硬拦截的确定性路由。图片附件须有可访问的本地路径；扫描PDF先渲染图片。有文字层的PDF继续优先文字提取。
- 识别可能出错。未标注字段必须null，关键号码/金额继续核验。若启用了 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`，需先关闭，才能使用独立视觉模型。

本机真实模型、字段及分发包验证结论见上层 `2026-10-26 glm-5.3主模型与Flash视觉自动委派实测.md`。原始错误样本亦保留，不把模型识别包装成必然正确。

'''
readme = readme.replace("## 2026-10-12 同步内容", section + "## 2026-10-12 同步内容", 1)
readme = readme.replace("| Claude Code | `claude --version` | 先通过官方渠道安装；本包不装本体 |", "| Claude Code 2.1.299+ | `claude --version` | 本轮路由的实测版本；本包不装本体 |", 1)
readme = readme.replace("并应用 1M 上下文、客户端分类器和 auto 默认模式。", "并应用 1M 上下文、客户端分类器、auto 默认模式，以及显式主模型 glm-5.3。", 1)
readme = readme.replace("| `prepare-bash-env.py` | 已验证的 Windows PATH 修复钩子，Python 标准库，无外部依赖 |", "| `prepare-bash-env.py` | 已验证的 Windows PATH 修复钩子，Python 标准库，无外部依赖 |\n| `vision-routing/agents.json` | 固定Flash、仅Read的视觉子agent定义 |\n| `vision-routing/routing.md` | Zhipu分支的自动委派及事实输出规则 |", 1)
write("README.md", readme)
(HERE / "package-source-hashes.json").write_text(json.dumps(SOURCES, ensure_ascii=False, indent=2), encoding="utf-8")
print("Staged portable package in", STAGE)
