#Requires -Version 7.0
<#
.SYNOPSIS
  从【本机】已装的 codex 提取 Windows 原生二进制，打进分发包的 codex-offline/。

.DESCRIPTION
  优先从 PATH 中的 Windows 原生 codex.exe 打包（含桌面 App 安装）；找不到时才使用 npm 平台包。
  跑完把整个 [4-skill一键Codex-glm配置] 文件夹（含生成的 codex-offline/）拷给同事即可。
  同事机器无需 Node/npm——install 脚本会直接用提取出来的 exe。

  原生安装直接取 EXE；npm 安装则跳过需要 Node 的 JS launcher，取平台二进制。
  实测 codex.exe 可脱离 Node 独立运行（codex.exe --version 直通）。

  注：分发包文件夹名含方括号；读取和复制文件使用 -LiteralPath，避免通配符匹配。

.PARAMETER OutDir
  输出目录，默认本脚本旁边的 codex-offline/。
#>
[CmdletBinding()]
param(
  [string]$OutDir = ""
)
$ErrorActionPreference = "Stop"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot "codex-offline" }

function Write-Step { param($m) Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Write-Ok   { param($m) Write-Host "    [OK] $m" -ForegroundColor Green }
function Write-Warn2{ param($m) Write-Host "    [!]  $m" -ForegroundColor Yellow }
function Die        { param($m) Write-Host "`n[X] $m" -ForegroundColor Red; exit 1 }

# ============================================================
Write-Step "第 1 步 / 定位本机 codex 平台二进制"
# ============================================================
$native = Get-Command codex -CommandType Application -ErrorAction SilentlyContinue | Where-Object { $_.Source -match '^[A-Za-z]:.*\.exe$' } | Select-Object -First 1
if ($native) {
  $stream = [IO.File]::OpenRead($native.Source)
  try { $header = [byte[]]::new(8); [void]$stream.Read($header, 0, 8) } finally { $stream.Dispose() }
  if ($header[0] -ne 0x4d -or $header[1] -ne 0x5a) { Die '原生 Codex 文件不是 Windows EXE，未打包。' }
  $binDir = Split-Path $native.Source -Parent
  $plat = $binDir
  $npmRoot = '(not required: native Codex on PATH)'
  Write-Ok "使用当前 PATH 中的原生 Codex：$($native.Source)"
} else {
  $npmRoot = (npm root -g 2>$null).Trim()
  if (-not $npmRoot -or -not (Test-Path -LiteralPath $npmRoot)) {
    Die "取不到 npm 全局 root（npm root -g 空/不存在）。本脚本要在【已用 npm 装了 codex 的机器】上跑。先 npm i -g @openai/codex 再来。"
  }
  Write-Ok "npm 全局 root: $npmRoot"

  # codex 的平台包（@openai/codex-win32-x64）可能装在带哈希的目录里（如 .codex-hkz3TuwA），
  # 路径不固定，所以递归找，再挑出真正带 vendor\...\bin\codex.exe 的那个。
  $cands = Get-ChildItem -LiteralPath $npmRoot -Recurse -Directory -Filter "codex-win32-x64" -ErrorAction SilentlyContinue
  $plat = $null
  foreach ($d in $cands) {
    if (Test-Path -LiteralPath (Join-Path $d.FullName "vendor\x86_64-pc-windows-msvc\bin\codex.exe")) {
      $plat = $d.FullName; break
    }
  }
  if (-not $plat) {
    Die "在 npm 全局目录下没找到 codex-win32-x64 平台包（带 vendor\...\bin\codex.exe）。确认本机 codex 装好了（codex --version 能跑）再来。"
  }
  $binDir = Join-Path $plat "vendor\x86_64-pc-windows-msvc\bin"
  Write-Ok "平台包: $plat"
}

# ============================================================
Write-Step "第 2 步 / 提取二进制到 $OutDir"
# ============================================================
[void][IO.Directory]::CreateDirectory($OutDir)
$toPack = @("codex.exe", "codex-code-mode-host.exe")
foreach ($f in $toPack) {
  $src = Join-Path $binDir $f
  if (-not (Test-Path -LiteralPath $src)) {
    Write-Warn2 "$f 不存在，跳过（主 CLI codex.exe 必须有；host 是可选子组件，缺了不影响基本使用）"
    continue
  }
  Copy-Item -LiteralPath $src (Join-Path $OutDir $f) -Force
  Write-Ok "$f ($([math]::Round((Get-Item -LiteralPath $src).Length / 1MB, 1)) MB)"
}
$codexExe = Join-Path $OutDir "codex.exe"
if (-not (Test-Path -LiteralPath $codexExe)) { Die "提取失败：codex.exe 没拷出来。" }

# ============================================================
Write-Step "第 3 步 / 验证 + 生成 MANIFEST"
# ============================================================
# 实跑 --version（带超时保护，防卡）
# 注：Start-Process -FilePath 也走通配符，$codexExe 路径含方括号会炸 → 用 .NET Process（字面路径）
$selfVer = "(未取到)"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $codexExe
$psi.Arguments = "--version"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)
if ($p.WaitForExit(20000)) {
  $selfVer = $p.StandardOutput.ReadToEnd().Trim()
  if (-not $selfVer) { $selfVer = "(空输出，exit=$($p.ExitCode))" }
} else {
  $p.Kill(); $selfVer = "(--version 超时 20s)"
}
Write-Ok "codex.exe 自报版本: $selfVer"

$lines = @()
$lines += "codex offline bundle - MANIFEST"
$lines += "================================"
$lines += "extracted (this machine) : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$lines += "source npm root          : $npmRoot"
$lines += "source platform pkg      : $plat"
$lines += "codex.exe self-version   : $selfVer"
$lines += "target platform          : x86_64-pc-windows-msvc (Windows x64)"
$lines += ""
$lines += "files:"
foreach ($f in $toPack) {
  $fp = Join-Path $OutDir $f
  if (Test-Path -LiteralPath $fp) {
    $sha = (Get-FileHash -LiteralPath $fp -Algorithm SHA256).Hash
    $szMB = [math]::Round((Get-Item -LiteralPath $fp).Length / 1MB, 1)
    $lines += "  - $f"
    $lines += "      size   : $szMB MB"
    $lines += "      sha256 : $sha"
  }
}
$lines += ""
$lines += "本目录由 pack-codex-offline.ps1 从本机原生安装或 npm 平台包提取。"
$lines += "install-codex-glm.ps1 会把 codex.exe 拷到目标机器的 ~/.codex-bin/ 并加入用户 PATH。"
$lines += "codex-glm 函数走 PATH 调用 codex；目标机器无需 Node.js / npm（codex.exe 是独立 Rust 二进制）。"
Set-Content -LiteralPath (Join-Path $OutDir "MANIFEST.txt") -Value $lines -Encoding UTF8
Write-Ok "MANIFEST.txt 已写"

# ============================================================
Write-Step "完成"
# ============================================================
$totalMB = [math]::Round((Get-ChildItem -LiteralPath $OutDir -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host @"
    提取到：$OutDir
    体积 ：约 $totalMB MB（codex.exe 本身 325MB 静态二进制，正常）

    下一步：把整个 [4-skill一键Codex-glm配置] 文件夹（含这个 codex-offline/）
    整个拷给同事 → 他在自己机器跑 install-codex-glm.ps1 即可。
"@ -ForegroundColor White
