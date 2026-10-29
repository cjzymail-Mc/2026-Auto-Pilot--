#Requires -Version 7.0
<#
.SYNOPSIS
  一键安装/配置本地 codex-glm（对标 claude-glm）。无 VPN / 无 Node 也能装。

.DESCRIPTION
  同事在自己机器跑这个。会做这些事：
    1. 前置检测（PowerShell7 / Python / ZHIPU_API_KEY / 国内 PyPI 镜像可达）
    2. codex 处理：检测 PATH 里有没有 Windows 原生 codex
         - 有 → 跳过（复用已装的）
         - 没有 → 从分发包 codex-offline/ 离线装 codex.exe 到 ~/.codex-bin/ + 加用户 PATH
    3. 建 Python venv (~/.litellm-env) 装 litellm[proxy]（走国内 PyPI 镜像，不需 VPN）
    4. 拷 LiteLLM 三件套到 ~/.codex-glm/litellm/
    5. 拷 mc-expert 陪审 agent + 共享 review contract 到 ~/.codex-glm/agents/
    6. 部署视觉路由：vision-read.ps1（固定 glm-5.3-flash）+ AGENTS.md 标记块（幂等合并）
    7. 写 ~/.codex-glm/config.toml
    8. 往 $PROFILE 安装/更新 codex-glm 函数（先备份 + 幂等；保留其他内容）
    9. 冒烟：后台启 LiteLLM 代理确认翻译桥起得来，完事自动关掉

  跑完【新开一个 PowerShell 窗口】（让 profile 函数 + 新 PATH 生效），敲 codex-glm 就能用。

  注：分发包文件夹名含方括号；读取和复制文件使用 -LiteralPath，避免通配符匹配。

  前提（同事请先备齐）：
    - PowerShell 7（pwsh）
    - Python 3.10+（python.org 下，国内能访问）
    - ZHIPU_API_KEY 设为【用户级】环境变量
    - 不需要 Node / npm / Clash —— codex 走离线包，litellm 走国内镜像，z.ai 国内直连

.PARAMETER PypiMirror
  pip 装 litellm 用的国内 PyPI 镜像。默认清华 TUNA。换镜像改这个。

.PARAMETER LitellmVersion
  litellm 版本，默认 1.91.1（本机验证版）。装最新传 ""。

.PARAMETER UpdateProfileOnly
  只安装/更新 PowerShell profile 中的 codex-glm 函数，不安装依赖、不覆盖模型配置、不启动或停止代理。

.EXAMPLE
  pwsh -ExecutionPolicy Bypass -File .\install-codex-glm.ps1
#>
[CmdletBinding()]
param(
  [string]$PypiMirror = "https://pypi.tuna.tsinghua.edu.cn/simple",
  [string]$LitellmVersion = "1.91.1",
  [switch]$UpdateProfileOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

function Write-Step { param($m) Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn2{ param($m) Write-Host "    [!]  $m" -ForegroundColor Yellow }
function Die        { param($m) Write-Host "`n[X] $m" -ForegroundColor Red; exit 1 }

function Test-PortOpen([string]$HostName, [int]$Port) {
  try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $iar = $tcp.BeginConnect($HostName, $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(2000, $false)
    if ($ok) { $tcp.EndConnect($iar); $tcp.Close(); return $true }
    $tcp.Close(); return $false
  } catch { return $false }
}

# 检测 Windows 原生 codex（排除 WSL/Linux codex，专注 PowerShell 这一面）
function Find-WindowsCodex {
  $cmd = Get-Command codex -ErrorAction SilentlyContinue
  if (-not $cmd) { return $null }
  if ($cmd.CommandType -notin @('Application', 'ExternalScript')) {
    Write-Warn2 "PATH 里有个 codex，但它是 $($cmd.CommandType)（可能是别名/函数，或包了 wsl）→ 不算 Windows 原生，走离线装"
    return $null
  }
  $src = $cmd.Source
  if ($src -match '^[\\/]{2}wsl(?:\.localhost|\$)[\\/]|^/(?:mnt|usr|bin)/') {
    Write-Warn2 "PATH 里的 codex（$src）路径含 WSL/Linux 特征 → 不算 Windows 原生，走离线装"
    return $null
  }
  try {
    $p = Start-Process -FilePath $src -ArgumentList "--version" -NoNewWindow -PassThru `
      -RedirectStandardOutput "$env:TEMP\findcodex.ver" -RedirectStandardError "$env:TEMP\findcodex.err"
    if ($p.WaitForExit(15000)) {
      $v = (Get-Content -LiteralPath "$env:TEMP\findcodex.ver" -Raw).Trim()
      if ($v -match 'codex') { return $src }
      Write-Warn2 "codex（$src）--version 输出异常（$v）→ 不算可用，走离线装"
      return $null
    }
    $p.Kill()
    Write-Warn2 "codex（$src）--version 超时 → 不算可用，走离线装"
    return $null
  } catch {
    Write-Warn2 "codex（$src）实跑异常：$_ → 走离线装"
    return $null
  }
}

# 把目录加到用户级 PATH（备份原值 + 幂等）
function Add-ToUserPath([string]$Dir, [string]$BackupDir) {
  $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
  if (-not $userPath) { $userPath = "" }
  $parts = $userPath -split ';' | Where-Object { $_.Trim() -ne "" }
  $dirNorm = $Dir.TrimEnd('\').TrimEnd('/')
  foreach ($p in $parts) {
    if ($p.TrimEnd('\').TrimEnd('/') -ieq $dirNorm) {
      Write-Ok "用户 PATH 已含 $Dir（无需添加）"
      return
    }
  }
  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
  $bak = Join-Path $BackupDir ("user-PATH-backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".txt")
  Set-Content -LiteralPath $bak -Value $userPath -Encoding UTF8
  # 追加并写回（Windows 用户 PATH 有约 2047 字符限制，超了会被截断）
  $newPath = ((@($parts) + $Dir) -join ';')
  if ($newPath.Length -gt 2000) {
    Write-Warn2 "用户 PATH 写回后总长 $($newPath.Length) 字符，接近/超过 Windows 2047 上限——可能被截断。建议清理用户 PATH 里无用条目。"
  }
  [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
  Write-Ok "已把 $Dir 加入用户 PATH（原值备份: $bak；新窗口生效）"
  if ($env:PATH -notlike "*$dirNorm*") { $env:PATH += ";$Dir" }
}


function Install-CodexGlmProfile([string]$ProfilePath) {
  $snippetPath = Join-Path $ScriptDir "codex-glm-profile-func.ps1"
  if (-not (Test-Path -LiteralPath $snippetPath)) { throw "分发包缺文件：$snippetPath" }
  $snippet = Get-Content -LiteralPath $snippetPath -Raw -Encoding UTF8
  $snippetTokens = $null; $snippetErrors = $null
  $snippetAst = [System.Management.Automation.Language.Parser]::ParseInput($snippet, [ref]$snippetTokens, [ref]$snippetErrors)
  if ($snippetErrors.Count) { throw "启动函数语法无效，profile 未修改：$($snippetErrors[0].Message)" }
  $newFunctions = @($snippetAst.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "codex-glm"
  }, $true))
  if ($newFunctions.Count -ne 1) { throw "分发片段必须恰好定义一个 codex-glm 函数，profile 未修改。" }

  $exists = Test-Path -LiteralPath $ProfilePath
  $content = if ($exists) { [System.IO.File]::ReadAllText($ProfilePath) } else { "" }
  $profileTokens = $null; $profileErrors = $null
  $profileAst = [System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$profileTokens, [ref]$profileErrors)
  if ($profileErrors.Count) { throw "现有 profile 语法无效，未覆盖：$($profileErrors[0].Message)" }
  $oldFunctions = @($profileAst.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq "codex-glm"
  }, $true))
  if ($oldFunctions.Count -gt 1) { throw "profile 中有多个 codex-glm 定义，未覆盖；请先确认要保留哪一个。" }
  if ($oldFunctions.Count -eq 1) {
    $extent = $oldFunctions[0].Extent
    $updated = $content.Substring(0, $extent.StartOffset) + $newFunctions[0].Extent.Text + $content.Substring($extent.EndOffset)
  } else {
    $updated = $content.TrimEnd() + "`r`n`r`n" + $snippet.TrimEnd() + "`r`n"
  }
  if ($exists -and $updated -ceq $content) { Write-Ok "codex-glm 函数已是本包版本，profile 无需改动：$ProfilePath"; return }
  $updatedTokens = $null; $updatedErrors = $null
  [void][System.Management.Automation.Language.Parser]::ParseInput($updated, [ref]$updatedTokens, [ref]$updatedErrors)
  if ($updatedErrors.Count) { throw "更新后的 profile 语法无效，未写入：$($updatedErrors[0].Message)" }
  $parent = Split-Path $ProfilePath -Parent
  if (-not (Test-Path -LiteralPath $parent)) { [void][System.IO.Directory]::CreateDirectory($parent) }
  if ($exists) {
    $backup = "$ProfilePath.bak-codex-glm-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
    Copy-Item -LiteralPath $ProfilePath -Destination $backup
    Write-Ok "已备份旧 profile → $backup"
  }
  [System.IO.File]::WriteAllText($ProfilePath, $updated, [System.Text.UTF8Encoding]::new($false))
  Write-Ok "codex-glm 函数已安装/更新，其他 profile 内容保留：$ProfilePath"
}

if ($UpdateProfileOnly) {
  Write-Step "只更新 codex-glm 启动函数"
  Install-CodexGlmProfile $PROFILE.CurrentUserCurrentHost
  Write-Ok "完成。新开 PowerShell 窗口后生效；依赖、模型配置和正在运行的代理均未处理。"
  return
}

# ============================================================
Write-Step "第 1 步 / 前置检测"
# ============================================================
# Python（排除 Windows Store stub）
$pyExe = $null
$direct = Get-Command python -ErrorAction SilentlyContinue
if ($direct) {
  $verOut = & $direct.Source --version 2>&1
  if ($verOut -match '^Python\s+\d') { $pyExe = $direct.Source }
  else { Write-Warn2 "找到的 python 是 Windows Store stub（$($direct.Source)），跳过，改试 py launcher" }
}
if (-not $pyExe) {
  $launcher = Get-Command py -ErrorAction SilentlyContinue
  if ($launcher) {
    $resolved = & $launcher.Source -3 -c "import sys; print(sys.executable)" 2>$null
    if ($resolved) { $resolved = $resolved.Trim() }
    if ($resolved -and (Test-Path -LiteralPath $resolved)) { $pyExe = $resolved }
  }
}
if (-not $pyExe -or -not (Test-Path -LiteralPath $pyExe)) {
  Die "没找到真 Python（只找到 Store stub 或完全没有）。请装 Python 3.10+（python.org，装时勾 Add to PATH），重开 PowerShell 再跑。"
}
$pyVer = & $pyExe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
Write-Ok "Python $pyVer：$pyExe"

# ZHIPU_API_KEY
$zhipuKey = $env:ZHIPU_API_KEY
if (-not $zhipuKey) { $zhipuKey = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "User") }
if (-not $zhipuKey) {
  Die "没找到 ZHIPU_API_KEY。去 z.ai 控制台拿 key，设为【用户级】环境变量（系统属性→环境变量→用户变量→新建 ZHIPU_API_KEY），设完重开 PowerShell 再跑。"
}
Write-Ok "ZHIPU_API_KEY 已设（来源：$(if($env:ZHIPU_API_KEY){'当前会话'}else{'用户级'})）"

# 国内 PyPI 镜像可达性（warn 不阻断）
$mirrorHost = ([System.Uri]$PypiMirror).Host
if (-not (Test-PortOpen $mirrorHost 443)) {
  Write-Warn2 "PyPI 镜像 $mirrorHost 当前不可达。pip 装 litellm 可能失败——确认网络通畅，或用 -PypiMirror 换镜像。"
} else {
  Write-Ok "PyPI 镜像可达：$mirrorHost"
}

# ============================================================
Write-Step "第 2 步 / codex 处理（检测已装则跳过；否则离线装 + 加 PATH）"
# ============================================================
$glmDir = Join-Path $env:USERPROFILE ".codex-glm"
$existing = Find-WindowsCodex
if ($existing) {
  Write-Ok "检测到已装的 Windows 原生 codex：$existing → 跳过离线安装，复用它"
} else {
  $srcExe = Join-Path $ScriptDir "codex-offline\codex.exe"
  if (-not (Test-Path -LiteralPath $srcExe)) {
    Die "这台机器没装 codex，且分发包没有 codex-offline\codex.exe。请先在【有 codex 的机器】跑 pack-codex-offline.ps1 打包，再把整个文件夹拷过来。"
  }
  $codexBinDir = Join-Path $env:USERPROFILE ".codex-bin"
  New-Item -ItemType Directory -Force -Path $codexBinDir | Out-Null
  foreach ($f in @("codex.exe", "codex-code-mode-host.exe")) {
    $src = Join-Path $ScriptDir "codex-offline\$f"
    if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src (Join-Path $codexBinDir $f) -Force }
  }
  Write-Ok "离线 codex.exe 已拷到 $codexBinDir"
  Add-ToUserPath $codexBinDir $glmDir
  # 冒烟：离线 codex 能跑（捕获 stderr 便于排错）
  $cvErr = "$env:TEMP\codex-offline-install.err"
  $cv = & (Join-Path $codexBinDir "codex.exe") --version 2>$cvErr
  if ($LASTEXITCODE -eq 0 -and $cv) { Write-Ok "离线 codex 验证：$($cv.Trim())" }
  else { Write-Warn2 "离线 codex.exe --version 跑不起来（exit=$LASTEXITCODE）——可能缺 DLL 或被杀软拦，装完 codex-glm 大概率用不了。请直接跑 ~\.codex-bin\codex.exe --version 看报错（stderr 见 $cvErr），或截图问打包者。" }
}

# ============================================================
Write-Step "第 3 步 / 建 venv 并装 litellm[proxy]（走国内镜像）"
# ============================================================
$venv = Join-Path $env:USERPROFILE ".litellm-env"
$venvPy  = Join-Path $venv "Scripts\python.exe"
$venvPip = Join-Path $venv "Scripts\pip.exe"
$venvLitellm = Join-Path $venv "Scripts\litellm.exe"

if (Test-Path -LiteralPath $venvPy) {
  Write-Ok "venv 已存在，复用：$venv"
} else {
  Write-Host "    创建 venv：$venv"
  & $pyExe -m venv $venv
  if (-not (Test-Path -LiteralPath $venvPy)) { Die "venv 创建失败。看上面报错。" }
  Write-Ok "venv 创建完成"
}

$pkg = if ($LitellmVersion) { "litellm[proxy]==$LitellmVersion" } else { "litellm[proxy]" }
Write-Host "    pip 装 $pkg（走国内镜像 $PypiMirror，不需 VPN）..."
& $venvPip install --upgrade $pkg -i $PypiMirror
if ($LASTEXITCODE -ne 0) { Die "litellm 安装失败。确认网络能连 $mirrorHost，或用 -PypiMirror 换镜像（如 https://mirrors.aliyun.com/pypi/simple）。" }
if (-not (Test-Path -LiteralPath $venvLitellm)) { Die "litellm 装完但没找到 litellm.exe（$venvLitellm）。" }
Write-Ok "litellm 安装完成"

# ============================================================
Write-Step "第 4 步 / 拷 LiteLLM 三件套到 ~/.codex-glm/litellm/"
# ============================================================
$litellmDir = Join-Path $glmDir "litellm"
New-Item -ItemType Directory -Force -Path $litellmDir | Out-Null
$triplet = @("glm-config.yaml", "tool_filter.py", "start-glm-proxy.ps1")
foreach ($f in $triplet) {
  $src = Join-Path $ScriptDir (Join-Path "litellm" $f)
  if (-not (Test-Path -LiteralPath $src)) { Die "分发包缺文件：$src（安装包不完整，重新拷一份）" }
  $destination = Join-Path $litellmDir $f
  if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $src).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    Copy-Item -LiteralPath $destination -Destination ($destination + '.bak-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
  }
  Copy-Item -LiteralPath $src -Destination $destination -Force
}
Write-Ok "三件套就位：$litellmDir\{$($triplet -join ', ')}"

# ============================================================
Write-Step "第 5 步 / 拷 mc-expert 陪审 agent + 共享 review contract 到 ~/.codex-glm/agents/"
# ============================================================
# codex-glm 的 native 陪审子代理（custom agent）。codex 跑 spawn_agent(agent_type=mc-expert) 时
# 从 ~/.codex-glm/agents/ 加载。分发包自带独立副本（来自 Mc-Expert-repo 母本），装完即自足。
# review-contract-v2.md 是 ENHANCED_FINAL 终审共享契约；agent 定义里读「安装位优先、母本兜底」。
$agentsDir = Join-Path $glmDir "agents"
New-Item -ItemType Directory -Force -Path $agentsDir | Out-Null
foreach ($f in @('mc-expert.toml', 'review-contract-v2.md')) {
  $srcAgent = Join-Path $ScriptDir ("agents\" + $f)
  if (-not (Test-Path -LiteralPath $srcAgent)) {
    Die "分发包缺文件：$srcAgent（安装包不完整，重新拷一份）"
  }
  if ((Get-Item -LiteralPath $agentsDir).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    Write-Warn2 "agents 是共享目录链接，保留现有内容：$agentsDir"
    break
  }
  $destination = Join-Path $agentsDir $f
  if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $srcAgent).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    Copy-Item -LiteralPath $destination -Destination ($destination + '.bak-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
  }
  Copy-Item -LiteralPath $srcAgent -Destination $destination -Force
}
Write-Ok "mc-expert 陪审 agent 就位：$agentsDir\mc-expert.toml（+ review-contract-v2.md）"

# ============================================================
Write-Step "第 6 步 / 部署视觉路由（vision-read.ps1 + AGENTS.md 规则块）"
# ============================================================
# 对标 claude-glm 的 flash 视觉自动委派：主模型 glm-5.3 不变，图片任务由
# vision-read.ps1 固定走 glm-5.3-flash。脚本经本机 LiteLLM（http://127.0.0.1:4000）转发：
# codex 的 Windows 沙箱里 Schannel 出站 TLS 会失败（SEC_E_NO_CREDENTIALS），
# HTTPS 一段由沙箱外的 LiteLLM 进程完成，仍直达 Zhipu coding 端点。
# AGENTS.md 只追加/替换 BEGIN..END 标记块，用户自己的其他全局指令保留。
$visionDir = Join-Path $glmDir "vision"
New-Item -ItemType Directory -Force -Path $visionDir | Out-Null
$srcVision = Join-Path $ScriptDir "vision\vision-read.ps1"
if (-not (Test-Path -LiteralPath $srcVision)) { Die "分发包缺文件：$srcVision" }
$dstVision = Join-Path $visionDir "vision-read.ps1"
if ((Test-Path -LiteralPath $dstVision) -and (Get-FileHash -LiteralPath $srcVision).Hash -ne (Get-FileHash -LiteralPath $dstVision).Hash) {
  Copy-Item -LiteralPath $dstVision -Destination ($dstVision + '.bak-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
Copy-Item -LiteralPath $srcVision -Destination $dstVision -Force

$agentsPath = Join-Path $glmDir "AGENTS.md"
$srcBlock = Join-Path $ScriptDir "vision\AGENTS-vision-routing.md"
if (-not (Test-Path -LiteralPath $srcBlock)) { Die "分发包缺文件：$srcBlock" }
$block = [IO.File]::ReadAllText($srcBlock).TrimEnd() + "`r`n"
$blockBegin = '<!-- BEGIN codex-glm vision routing -->'
$blockEnd = '<!-- END codex-glm vision routing -->'
$agentsContent = if (Test-Path -LiteralPath $agentsPath) { [IO.File]::ReadAllText($agentsPath) } else { '' }
$bIdx = $agentsContent.IndexOf($blockBegin)
if ($bIdx -ge 0) {
  $eIdx = $agentsContent.IndexOf($blockEnd, $bIdx)
  if ($eIdx -ge 0) {
    # 连 END 标记后紧跟的一个换行一起消费：块本身以 CRLF 结尾，
    # 不吞这个换行会导致每次重跑文件末尾多一个空行（幂等破坏，隔离验证实测抓出）。
    $afterIdx = $eIdx + $blockEnd.Length
    $rest = $agentsContent.Substring($afterIdx)
    if ($rest.StartsWith("`r`n")) { $afterIdx += 2 } elseif ($rest.StartsWith("`n")) { $afterIdx += 1 }
    $updated = $agentsContent.Substring(0, $bIdx) + $block + $agentsContent.Substring($afterIdx)
  } else { $updated = $agentsContent.TrimEnd() + "`r`n`r`n" + $block }
} elseif ($agentsContent.Trim()) {
  $updated = $agentsContent.TrimEnd() + "`r`n`r`n" + $block
} else {
  $updated = "# codex-glm 全局指令`r`n`r`n" + $block
}
if ($updated -ceq $agentsContent) {
  Write-Ok "AGENTS.md 视觉路由块已是最新，无需改动：$agentsPath"
} else {
  if (Test-Path -LiteralPath $agentsPath) {
    Copy-Item -LiteralPath $agentsPath -Destination ($agentsPath + '.bak-codex-glm-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
  }
  [IO.File]::WriteAllText($agentsPath, $updated, [Text.UTF8Encoding]::new($false))
  Write-Ok "视觉路由块已写入 AGENTS.md（其他全局指令保留）：$agentsPath"
}
Write-Ok "视觉脚本就位：$dstVision（图片任务固定 glm-5.3-flash，经本机 LiteLLM）"

# ============================================================
Write-Step "第 7 步 / 写 ~/.codex-glm/config.toml"
# ============================================================
$srcToml = Join-Path $ScriptDir "codex-glm-config.toml"
if (-not (Test-Path -LiteralPath $srcToml)) { Die "分发包缺文件：$srcToml" }
$destination = Join-Path $glmDir 'config.toml'
if ((Test-Path -LiteralPath $destination) -and (Get-FileHash -LiteralPath $srcToml).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
  Copy-Item -LiteralPath $destination -Destination ($destination + '.bak-install-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
}
Copy-Item -LiteralPath $srcToml -Destination $destination -Force
Write-Ok "config.toml 就位：$glmDir\config.toml"

# ============================================================
Write-Step "第 8 步 / 注入 codex-glm 函数到 PowerShell profile（备份 + 幂等）"
# ============================================================
Install-CodexGlmProfile $PROFILE.CurrentUserCurrentHost
$profilePath = $PROFILE.CurrentUserCurrentHost

# ============================================================
Write-Step "第 9 步 / 冒烟验证（后台启 LiteLLM 代理测翻译桥，完事自动关掉）"
# ============================================================
$liteVer = & $venvLitellm --version 2>$null
Write-Ok "litellm 可执行：$venvLitellm ($liteVer)"

if (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue) {
  Write-Warn2 '4000 端口已有服务；跳过启动/关闭冒烟，保留原服务。请确认它是 GLM 的 LiteLLM。'
} else {
  $smokeErr = Join-Path $env:TEMP 'codex-glm-smoke.err.log'
  if (-not $env:ZHIPU_API_KEY) { $env:ZHIPU_API_KEY = $zhipuKey }
  $smokeProc = $null
  try {
    $smokeProc = Start-Process -FilePath 'pwsh.exe' `
      -ArgumentList '-NoProfile','-File',('"{0}"' -f "$litellmDir\start-glm-proxy.ps1") `
      -WindowStyle Hidden -PassThru `
      -RedirectStandardOutput (Join-Path $env:TEMP 'codex-glm-smoke.log') -RedirectStandardError $smokeErr
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
      if ($smokeProc.HasExited) { break }
      if (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue) { $ready = $true; break }
      Start-Sleep -Milliseconds 500
    }
    if ($ready) { Write-Ok '本次 LiteLLM 冒烟进程已启动；Key/模型仍需真实请求验收' }
    else { Write-Warn2 "代理未就绪，查看 $smokeErr" }
  } finally {
    # Kill only this invocation's owned process tree, never all listeners on a port.
    if ($smokeProc -and -not $smokeProc.HasExited) { $smokeProc.Kill($true); [void]$smokeProc.WaitForExit(5000) }
  }
}

# ============================================================
Write-Step "完成！下一步怎么用"
# ============================================================
Write-Host @"
    1. 【新开一个 PowerShell 窗口】（让 profile 函数 + 新加的 PATH 生效）
    2. 敲：codex-glm
       弹菜单选 [1] Zhipu（z.ai 国内直连 via LiteLLM，默认，无需额外 key）
                  [2] OpenRouter（需 VPN + OPENROUTER_API_KEY，没 VPN 跳过）
    3. 首次选 Zhipu 会自动后台启动 LiteLLM 翻译代理（约 10-20s），之后复用。
    4. 图片/截图/票据任务会自动走 glm-5.3-flash（vision-read.ps1，经本机 LiteLLM），主模型仍是 glm-5.3。
    5. 想用原生 codex（gpt 账号）直接敲 codex 即可，和 codex-glm 互不污染。
    6. 注意：一定通过 codex-glm 命令进入 GLM，别手动设 CODEX_HOME 直跑 codex。

    出问题看：
      LiteLLM 代理日志  : ~/.codex-glm/litellm/proxy.err.log
      修复/回滚         : 参考 README；保留现有配置，必要时恢复对应 .bak-* 备份
"@ -ForegroundColor White

Write-Host "`n安装产物：`n  codex = $(if($existing){$existing}else{"~/.codex-bin（离线，已加入 PATH）"})`n  venv = $venv`n  配置 = $glmDir`n  函数 = $profilePath`n" -ForegroundColor DarkGray
