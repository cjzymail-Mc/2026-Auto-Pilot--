# LiteLLM 翻译代理启动脚本（responses -> chat），z.ai 国内直连
# 对标 WSL 版 ~/start-glm-proxy.sh
# 由 codex-glm 函数用 Start-Process 后台拉起；前台运行 litellm（阻塞直到被 kill）
$ErrorActionPreference = "Stop"

$litellmDir = "$env:USERPROFILE\.codex-glm\litellm"

# z.ai 国内直连：设 NO_PROXY + 清 Clash 代理变量（避免被 Clash 带歪，对标 WSL P5）
$env:NO_PROXY = "localhost,127.0.0.1,::1,api.z.ai,open.bigmodel.cn"
$env:no_proxy = $env:NO_PROXY
foreach ($v in @("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy")) {
    Remove-Item "Env:$v" -ErrorAction SilentlyContinue
}

# 取 ZHIPU_API_KEY：优先继承的 $env（codex-glm 函数所在 pwsh 已加载），没有则 User 级兜底
if (-not $env:ZHIPU_API_KEY) {
    $env:ZHIPU_API_KEY = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "User")
}
if (-not $env:ZHIPU_API_KEY) {
    Write-Error "ZHIPU_API_KEY 未设（User 级环境变量）"; exit 1
}
$env:LITELLM_KEY = "sk-codex-local"

# 让 callbacks: tool_filter.proxy_handler_instance 能 import
Set-Location $litellmDir
$env:PYTHONPATH = "$litellmDir;$env:PYTHONPATH"

# 启动 litellm 代理（监听 127.0.0.1:4000）
& "$env:USERPROFILE\.litellm-env\Scripts\litellm.exe" --config "$litellmDir\glm-config.yaml" --host 127.0.0.1 --port 4000
