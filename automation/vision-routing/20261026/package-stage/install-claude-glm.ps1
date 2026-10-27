#Requires -Version 7.0
<#
.SYNOPSIS
  配置或更新 claude-glm：独立启动环境、auto mode 和 Windows Bash PATH 修复。
.DESCRIPTION
  需要已安装 Claude Code、Git for Windows 和 Python 3.10+；本包不安装这些程序。
  先验证配置与 Bash 语法，再备份更新 settings、私有 PATH 钩子和 .bashrc。
  已有的其他钩子、插件和 Bash 函数保留；重复安装不会追加多个启动函数。
.PARAMETER SkipSmoke
  只更新配置，不发送智谱 API 请求。适合已验证过 Key 的机器。
.PARAMETER UserDirectory
  默认使用 USERPROFILE。Git Bash 的用户目录重定向时，可指定对应的 Windows 路径。
.PARAMETER ZhipuBaseUrl
  冒烟检查使用的智谱 Anthropic 接口地址；不改变启动器的三条 provider 路线。
.EXAMPLE
  pwsh -ExecutionPolicy Bypass -File .\install-claude-glm.ps1
.EXAMPLE
  pwsh -ExecutionPolicy Bypass -File .\install-claude-glm.ps1 -SkipSmoke
#>
[CmdletBinding()]
param(
  [string]$ZhipuBaseUrl = 'https://api.z.ai/api/anthropic',
  [switch]$SkipSmoke,
  [string]$UserDirectory = $env:USERPROFILE
)
$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot

function Write-Step { param($m) Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Write-Ok { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "    [!] $m" -ForegroundColor Yellow }

function ConvertTo-BashPath([string]$Path) {
  $value = $Path.Replace('\', '/')
  if ($value -match '^([A-Za-z]):/') { return '/' + $Matches[1].ToLowerInvariant() + $value.Substring(2) }
  return $value
}
function Quote-BashPath([string]$Path) {
  # Native Python accepts C:/... directly even when MSYS argument conversion is disabled.
  return '"' + $Path.Replace('\', '/').Replace('`', '\`').Replace('$', '\$').Replace('"', '\"') + '"'
}
function Assert-PrivatePath([string]$Path) {
  if ((Test-Path -LiteralPath $Path) -and ((Get-Item -LiteralPath $Path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "目标是目录/文件链接，未覆写：$Path。请使用 GLM 独立目录。"
  }
}
function Write-WithBackup([string]$Path, [byte[]]$Bytes) {
  Assert-PrivatePath $Path
  if (Test-Path -LiteralPath $Path) {
    $old = [IO.File]::ReadAllBytes($Path)
    if ([Convert]::ToBase64String($old) -ceq [Convert]::ToBase64String($Bytes)) { return }
    $backup = $Path + '.bak-claude-glm-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    Copy-Item -LiteralPath $Path -Destination $backup
    Write-Ok "已备份：$backup"
  }
  [IO.File]::WriteAllBytes($Path, $Bytes)
}
function Find-GitBash {
  $candidates = [Collections.Generic.List[string]]::new()
  $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($git) {
    $gitRoot = Split-Path (Split-Path $git.Source -Parent) -Parent
    $candidates.Add((Join-Path $gitRoot 'bin\bash.exe'))
    if ((Split-Path $gitRoot -Leaf) -eq 'mingw64') { $candidates.Add((Join-Path (Split-Path $gitRoot -Parent) 'bin\bash.exe')) }
  }
  foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
    if ($root) { $candidates.Add((Join-Path $root 'Git\bin\bash.exe')) }
  }
  foreach ($candidate in $candidates | Select-Object -Unique) {
    $gitRoot = Split-Path (Split-Path $candidate -Parent) -Parent
    if ((Test-Path -LiteralPath $candidate) -and (Test-Path -LiteralPath (Join-Path $gitRoot 'usr\bin\cygpath.exe'))) { return $candidate }
  }
  throw '没找到 Git for Windows 的 bash.exe / cygpath.exe。WSL 的 bash 不适用于本包。'
}
function Find-Python {
  $python = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch '[\\/]Microsoft[\\/]WindowsApps[\\/]' } | Select-Object -First 1
  $resolved = $null
  if ($python -and $python.Source -notmatch '[\\/]Microsoft[\\/]WindowsApps[\\/]') {
    $resolved = & $python.Source -c 'import sys; print(sys.executable)' 2>$null
  }
  if (-not $resolved) {
    $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) { $resolved = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null }
  }
  if (-not $resolved -or -not (Test-Path -LiteralPath ([string]$resolved).Trim())) { throw '没找到真正的 Python。请安装 Python 3.10+ 并重新打开终端。' }
  $resolved = ([string]$resolved).Trim()
  & $resolved -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'
  if ($LASTEXITCODE -ne 0) { throw 'Python 版本低于 3.10。' }
  return $resolved
}

function Install-ClaudeGlmConfiguration([string]$GlmDirectory, [string]$BashExe, [string]$PythonExe) {
  $privateHooks = Join-Path $GlmDirectory 'local-hooks'
  $privateVision = Join-Path $GlmDirectory 'vision-routing'
  $agentPath = Join-Path $privateVision 'agents.json'
  $routingPath = Join-Path $privateVision 'routing.md'
  $settingsPath = Join-Path $GlmDirectory 'settings.json'
  $hookPath = Join-Path $privateHooks 'prepare-bash-env.py'
  foreach ($path in @($GlmDirectory, $privateHooks, $privateVision, $settingsPath, $hookPath, $agentPath, $routingPath)) { Assert-PrivatePath $path }
  $template = Get-Content -LiteralPath (Join-Path $ScriptDir 'claude-glm-settings.json') -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
  $settings = if (Test-Path -LiteralPath $settingsPath) {
    Get-Content -LiteralPath $settingsPath -Raw -Encoding utf8 | ConvertFrom-Json -AsHashtable
  } else { [ordered]@{} }
  if ($settings -isnot [Collections.IDictionary]) { throw 'settings.json 顶层必须是 JSON 对象，未覆写。' }
  foreach ($name in $template.Keys) { if (-not $settings.Contains($name)) { $settings[$name] = $template[$name] } }
  if ($settings['env'] -isnot [Collections.IDictionary] -or $settings['permissions'] -isnot [Collections.IDictionary]) { throw 'settings 的 env / permissions 必须是对象，未覆写。' }
  foreach ($name in $template['env'].Keys) { if (-not $settings['env'].Contains($name)) { $settings['env'][$name] = $template['env'][$name] } }
  $settings['env']['CLAUDE_CODE_MAX_CONTEXT_TOKENS'] = '1000000'
  $settings['env']['CLAUDE_CODE_AUTO_MODE_SERVER'] = '0'
  $settings['env']['CLAUDE_CODE_GIT_BASH_PATH'] = $BashExe
  $settings['permissions']['defaultMode'] = 'auto'
  # Migrate the old Haiku-bound default; the launcher pins each provider's main model.
  $settings['model'] = 'glm-5.3'
  $settings['_comment'] = $template['_comment']
  if (-not $settings.Contains('hooks')) { $settings['hooks'] = [ordered]@{} }
  if ($settings['hooks'] -isnot [Collections.IDictionary]) { throw 'settings 的 hooks 必须是对象，未覆写。' }
  $command = (Quote-BashPath $PythonExe) + ' ' + (Quote-BashPath $hookPath)
  $pathHook = [ordered]@{ type = 'command'; command = $command; shell = 'bash'; timeout = 10 }
  $groups = @($settings['hooks']['SessionStart'] | Where-Object { $null -ne $_ })
  $found = $false
  foreach ($group in $groups) {
    $entries = @($group['hooks'])
    for ($i = 0; $i -lt $entries.Count; $i++) {
      if ([string]$entries[$i]['command'] -match '[/\\]local-hooks[/\\]prepare-bash-env\.py') { $entries[$i] = $pathHook; $found = $true }
    }
    $group['hooks'] = $entries
  }
  if (-not $found) { $groups = @([ordered]@{ hooks = @($pathHook) }) + $groups }
  $settings['hooks']['SessionStart'] = $groups
  $json = ($settings | ConvertTo-Json -Depth 50) + "`n"
  [void]($json | ConvertFrom-Json)
  $agentBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'vision-routing/agents.json'))
  $routingBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'vision-routing/routing.md'))
  $agentDefinition = [Text.Encoding]::UTF8.GetString($agentBytes) | ConvertFrom-Json -AsHashtable
  if ($agentDefinition['vision-reader']['model'] -cne 'glm-5.3-flash' -or ($agentDefinition['vision-reader']['tools'] -join ',') -cne 'Read') {
    throw '视觉agent配置必须为glm-5.3-flash且仅Read，未安装。'
  }
  if ($routingBytes.Length -eq 0) { throw '视觉路由规则为空，未安装。' }
  [void][IO.Directory]::CreateDirectory($privateVision)
  Write-WithBackup $agentPath $agentBytes
  Write-WithBackup $routingPath $routingBytes
  $hookBytes = [IO.File]::ReadAllBytes((Join-Path $ScriptDir 'prepare-bash-env.py'))
  [void][IO.Directory]::CreateDirectory($privateHooks)
  # Install the hook before registering it, leaving shared hooks directories untouched.
  Write-WithBackup $hookPath $hookBytes
  Write-WithBackup $settingsPath ([Text.UTF8Encoding]::new($false).GetBytes($json))
  Write-Ok "GLM 配置与私有 PATH 钩子已就位：$GlmDirectory"
}

function Install-ClaudeGlmLauncher([string]$BashrcPath, [string]$BashExe) {
  Assert-PrivatePath $BashrcPath
  $snippet = [IO.File]::ReadAllText((Join-Path $ScriptDir 'claude-glm.bashrc.snippet')).TrimEnd()
  $content = if (Test-Path -LiteralPath $BashrcPath) { [IO.File]::ReadAllText($BashrcPath) } else { '' }
  # Support the two formats distributed by this package: legacy braces and isolated subshell.
  $pattern = '(?ms)^[\t ]*claude-glm\(\)[\t ]*(?:\{\r?\n.*?^\}|\(\r?\n.*?^\))'
  $definitions = [regex]::Matches($content, $pattern)
  if ($definitions.Count -gt 1) { throw '.bashrc 有多个 claude-glm 定义，未覆写。请先确认要保留哪一个。' }
  $newFunction = [regex]::Match($snippet, $pattern)
  if (-not $newFunction.Success) { throw '分发包启动函数格式不正确，未覆写。' }
  if ($definitions.Count -eq 1) {
    $definition = $definitions[0]
    $updated = $content.Substring(0, $definition.Index) + $newFunction.Value + $content.Substring($definition.Index + $definition.Length)
  } elseif ($content -match '(?m)^[\t ]*(?:function[\t ]+)?claude-glm[\t ]*\(') {
    throw '旧 claude-glm 使用本包不识别的定义格式，未追加第二个函数。'
  } else {
    $updated = $content + "`n`n" + $snippet + "`n"
  }
  if ($updated -ceq $content) { Write-Ok '.bashrc 启动函数已是新版，无需改动'; return }
  $parent = Split-Path $BashrcPath -Parent
  [void][IO.Directory]::CreateDirectory($parent)
  $validationFile = $BashrcPath + '.validate-' + [guid]::NewGuid().ToString('N')
  try {
    [IO.File]::WriteAllText($validationFile, $updated, [Text.UTF8Encoding]::new($false))
    # File argument is essential: bash -n -c "source file" never parses the sourced file.
    $syntaxOutput = & $BashExe --noprofile --norc -n $validationFile 2>&1
    if ($LASTEXITCODE -ne 0) { throw ".bashrc 语法检查失败，原文件未修改：$syntaxOutput" }
    Write-WithBackup $BashrcPath ([Text.UTF8Encoding]::new($false).GetBytes($updated))
  } finally {
    if (Test-Path -LiteralPath $validationFile) { [IO.File]::Delete($validationFile) }
  }
  Write-Ok 'claude-glm 函数已更新；其他 Bash 内容保留，语法检查通过'
}

Write-Step '第 1 步 / 前置检测'
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) { throw '请先安装 Claude Code；本包只配置，不安装本体。' }
$claudeVer = & claude --version
Write-Ok "Claude Code：$claudeVer"
if ([string]$claudeVer -notmatch '(\d+\.\d+\.\d+)' -or [version]$Matches[1] -lt [version]'2.1.299') {
  throw '本视觉路由包已在Claude Code 2.1.299验证，请升级到2.1.299或更新版后安装。'
}
$bashExe = Find-GitBash
$pythonExe = Find-Python
Write-Ok "Git Bash：$bashExe"
Write-Ok "Python：$pythonExe"
$zhipuKey = $env:ZHIPU_API_KEY
if (-not $zhipuKey) { $zhipuKey = [Environment]::GetEnvironmentVariable('ZHIPU_API_KEY', 'User') }
if (-not $SkipSmoke -and -not $zhipuKey) { throw '没找到 ZHIPU_API_KEY；请设用户级环境变量，或用 -SkipSmoke 先更新配置。' }
$userPath = [IO.Path]::GetFullPath($UserDirectory)

Write-Step '第 2 步 / 更新 GLM 配置与私有 PATH 钩子'
$glmDir = Join-Path $userPath '.claude-glm'
Install-ClaudeGlmConfiguration $glmDir $bashExe $pythonExe

Write-Step '第 3 步 / 更新 Git Bash 启动函数'
$bashrcPath = Join-Path $userPath '.bashrc'
Install-ClaudeGlmLauncher $bashrcPath $bashExe

if (-not $SkipSmoke) {
  Write-Step '第 4 步 / 智谱直连冒烟（会产生少量 API 用量）'
  $headers = @{ 'x-api-key' = $zhipuKey; 'anthropic-version' = '2023-06-01' }
  $body = @{ model = 'glm-5.3'; max_tokens = 64; messages = @(@{ role = 'user'; content = 'Reply OK.' }) } | ConvertTo-Json -Depth 6
  try {
    # Keep the credential in memory, not in a curl command line or temporary file.
    $response = Invoke-RestMethod -Uri ($ZhipuBaseUrl.TrimEnd('/') + '/v1/messages') -Method Post -Headers $headers -ContentType 'application/json' -Body $body -NoProxy -TimeoutSec 30
    if ($response.model -ne 'glm-5.3' -or $response.type -ne 'message') { throw '响应不是预期的 glm-5.3 message。' }
    Write-Ok '智谱鉴权与 glm-5.3 响应检查通过'
  } catch {
    $message = $_.Exception.Message.Replace($zhipuKey, '<redacted>')
    throw "配置已写入，但冒烟未通过：$message。可用 -SkipSmoke 重跑配置或检查网络/套餐用量。"
  }
} else { Write-Ok '已跳过联网冒烟，仅更新配置' }

Write-Step '完成'
Write-Host '新开 Git Bash，在项目目录运行 claude-glm（默认选 1）。接续原会话：claude-glm --resume。'
Write-Host '默认主模型glm-5.3；Zhipu图片任务委派glm-5.3-flash。auto mode与PATH钩子保留。旧会话不会自动获得新启动参数。'
Write-Host "settings：$glmDir\settings.json`n启动函数：$bashrcPath`n私有钩子：$glmDir\local-hooks\prepare-bash-env.py"
