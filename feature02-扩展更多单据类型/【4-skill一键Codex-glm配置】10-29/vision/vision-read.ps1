#Requires -Version 7.0
<#
.SYNOPSIS
  codex-glm 视觉助手：固定 glm-5.3-flash 直读本地图片（对标 claude-glm 的 vision-reader）。
.DESCRIPTION
  由 CODEX_HOME 全局 AGENTS.md 的视觉路由规则在图片任务时调用；主会话保持 glm-5.3，不因图片整会话切换。

  为什么走本机 LiteLLM（http://127.0.0.1:4000）而不是脚本直连 https://api.z.ai：
  codex 的 Windows 沙箱用受限令牌跑命令，Schannel 出站 TLS 在其中会失败
 （SEC_E_NO_CREDENTIALS「安全包中没有可用的凭证」，2026-10-28 实测；沙箱外直跑同命令正常）。
  本机回环明文 HTTP 不经 Schannel；HTTPS 一段由沙箱外的 LiteLLM 进程完成，仍直达
  Zhipu coding 端点。全程只用 ZHIPU_API_KEY（由 LiteLLM 侧读取），不经 OpenRouter。

  代理未运行时自动拉起（同 codex-glm 启动函数逻辑）。
  退出码：0=成功；1=API 调用失败；2=输入/配置错误。
.EXAMPLE
  pwsh -NoProfile -ExecutionPolicy Bypass -File vision-read.ps1 -ImagePath D:\pic.png -Question "图里的编号和金额是多少？只回 JSON"
#>
param(
  [Parameter(Mandatory = $true)][string]$ImagePath,
  [string]$Question = '请完整识别并转述这张图片中所有可见文字，保留数字精度、前导零与跨行内容；未标注或不清晰的字段输出 null 并说明缺口，不要猜测。'
)
$ErrorActionPreference = 'Stop'

$resolved = Resolve-Path -LiteralPath $ImagePath -ErrorAction SilentlyContinue
if (-not $resolved) { [Console]::Error.WriteLine("codex-glm vision: 图片不存在: $ImagePath"); exit 2 }
$ImagePath = $resolved.ProviderPath
$ext = [IO.Path]::GetExtension($ImagePath).ToLowerInvariant()
$media = switch ($ext) {
  '.png'  { 'image/png' }
  '.jpg'  { 'image/jpeg' }
  '.jpeg' { 'image/jpeg' }
  '.webp' { 'image/webp' }
  '.gif'  { 'image/gif' }
  default { [Console]::Error.WriteLine("codex-glm vision: 不支持的图片类型 $ext（支持 png/jpg/jpeg/webp/gif）。"); exit 2 }
}
$bytes = [IO.File]::ReadAllBytes($ImagePath)
if ($bytes.Length -gt 5MB) {
  [Console]::Error.WriteLine("codex-glm vision: 图片 $([math]::Round($bytes.Length / 1MB, 1))MB 超过 5MB 上限，请先压缩或降分辨率。")
  exit 2
}
$b64 = [Convert]::ToBase64String($bytes)

# LiteLLM 代理就绪检查（未运行则自动拉起；Zhipu/OpenRouter 会话都能用）
$liteDir = "$env:USERPROFILE\.codex-glm\litellm"
$listening = { [bool](Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue) }
if (-not (& $listening)) {
  [Console]::Error.WriteLine('[codex-glm vision] LiteLLM 代理未运行，自动拉起（首次约 10-20s）...')
  Start-Process -FilePath 'pwsh.exe' -ArgumentList '-NoProfile', '-File', ('"{0}"' -f "$liteDir\start-glm-proxy.ps1") -WindowStyle Hidden `
    -RedirectStandardOutput "$liteDir\proxy.log" -RedirectStandardError "$liteDir\proxy.err.log"
  for ($i = 0; $i -lt 60; $i++) {
    if (& $listening) { break }
    Start-Sleep -Milliseconds 500
  }
  if (-not (& $listening)) {
    [Console]::Error.WriteLine("codex-glm vision: LiteLLM 代理未能就绪，无法调用 glm-5.3-flash；请查看 $liteDir\proxy.err.log")
    exit 2
  }
}

$body = @{
  model      = 'glm-5.3-flash'
  max_tokens = 4096
  messages   = @(@{
    role    = 'user'
    content = @(
      @{ type = 'image_url'; image_url = @{ url = "data:$media;base64,$b64" } }
      @{ type = 'text';      text = $Question }
    )
  })
} | ConvertTo-Json -Depth 8

try {
  $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:4000/v1/chat/completions' -Method Post -NoProxy -TimeoutSec 180 `
    -Headers @{ Authorization = 'Bearer sk-codex-local' } `
    -ContentType 'application/json' -Body $body
} catch {
  $msg = "$_"
  $inner = $_.Exception
  $depth = 0
  while ($inner.InnerException -and $depth -lt 4) {
    $inner = $inner.InnerException
    $msg += " | inner[$depth]: $($inner.Message)"
    $depth++
  }
  [Console]::Error.WriteLine("codex-glm vision: glm-5.3-flash 调用失败: $msg")
  exit 1
}
if ($resp.model) { [Console]::Error.WriteLine("[codex-glm vision] 实际应答模型: $($resp.model)") }
$resp.choices[0].message.content
