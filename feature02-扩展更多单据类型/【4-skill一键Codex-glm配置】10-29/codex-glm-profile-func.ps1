# ==================== codex-glm: GLM 账号（独立账号与环境恢复）====================
# 这段由 install-codex-glm.ps1 安装；已有函数会先备份再原位更新。
# 本包保留 2026-08-17 已验通的 LiteLLM Responses->Chat 路线；不声明服务商永久缺少 Responses。
# 两路 provider：
#   [1] Zhipu      —— z.ai 国内直连，经本地 LiteLLM 翻译（responses->chat + 展开协作工具），无中转费
#   [2] OpenRouter —— 网关直连 responses，零本地依赖，走 Clash，有中转费
# 函数里的 codex 走 PATH 调用——install 会确保 PATH 里有 codex：
#   要么这台机器已装 codex（npm 等），要么 install 离线装到 ~/.codex-bin 并加入了用户 PATH。
# 独立 CODEX_HOME=~/.codex-glm 整目录隔离，不动默认 ~/.codex（原生 codex 的 gpt 账号）。
# 用法：codex-glm（弹菜单） | codex-glm -Zhipu | codex-glm -OpenRouter | 末尾透传 codex 参数
function codex-glm {
  param(
    [switch]$Zhipu,
    [switch]$OpenRouter
  )
  if ($OpenRouter) { $choice = "2" }
  elseif ($Zhipu) { $choice = "1" }
  else {
    Write-Host ""
    Write-Host "  选择 provider:"
    Write-Host "    [1] Zhipu      (z.ai 国内直连 via LiteLLM, glm-5.3)"
    Write-Host "    [2] OpenRouter (直连, glm-5.2 备用路线)"
    Write-Host ""
    $choice = Read-Host "  输入 1/2 (回车默认 1=Zhipu)"
  }
  # Save both value and presence, including the local proxy credential.
  # Restore on success, interruption, and exceptions; no environment leaks to the next codex.
  $proxyVars = @("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy")
  $sessionEnvVars = @("CODEX_HOME", "CODEX_GLM_PROVIDER_ROUTE", "LITELLM_KEY") + $proxyVars
  $savedEnv = @{}
  foreach ($v in $sessionEnvVars) {
    if (Test-Path "Env:$v") { $savedEnv[$v] = (Get-Item "Env:$v").Value }
  }
  try {
    $env:CODEX_HOME = "$env:USERPROFILE\.codex-glm"
    if ($choice -eq "2") {
      $env:CODEX_GLM_PROVIDER_ROUTE = "2=OpenRouter | Codex -> https://openrouter.ai/api/v1 -> z-ai/glm-5.2"
      Write-Host "  [codex-glm 路径] $env:CODEX_GLM_PROVIDER_ROUTE" -ForegroundColor Cyan
      codex -c 'model="z-ai/glm-5.2"' -c 'model_provider="openrouter"' @args
    } else {
      $env:CODEX_GLM_PROVIDER_ROUTE = "1=Zhipu | Codex -> http://127.0.0.1:4000/v1 (LiteLLM responses->chat) -> https://api.z.ai/api/coding/paas/v4 | glm-5.3"
      Write-Host "  [codex-glm 路径] $env:CODEX_GLM_PROVIDER_ROUTE" -ForegroundColor Cyan
      # 选 Zhipu：临时清掉所有代理变量（z.ai 国内直连，codex 侧也别走 Clash）；函数退出后 finally 恢复
      foreach ($v in $proxyVars) {
        Remove-Item "Env:$v" -ErrorAction SilentlyContinue
      }
      $env:LITELLM_KEY = "sk-codex-local"
      $litellmDir = "$env:USERPROFILE\.codex-glm\litellm"
      if (-not (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue)) {
        Write-Host "  → 启动 LiteLLM 翻译代理（首次约 10-20s）..." -ForegroundColor Yellow
        Start-Process -FilePath "pwsh.exe" -ArgumentList "-NoProfile","-File",('"{0}"' -f "$litellmDir\start-glm-proxy.ps1") -WindowStyle Hidden -RedirectStandardOutput "$litellmDir\proxy.log" -RedirectStandardError "$litellmDir\proxy.err.log"
        for ($i = 0; $i -lt 60; $i++) {
          if (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue) { break }
          Start-Sleep -Milliseconds 500
        }
        if (-not (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue)) {
          throw "LiteLLM 代理未就绪，未启动 Codex；请查看 $litellmDir\proxy.err.log"
        }
      }
      codex -c 'model="glm-5.3"' -c 'model_provider="zai-litellm"' @args
    }
  } finally {
    foreach ($v in $sessionEnvVars) {
      if ($savedEnv.ContainsKey($v)) { Set-Item "Env:$v" $savedEnv[$v] }
      else { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
    }
  }
}
