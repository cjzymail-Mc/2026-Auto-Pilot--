# codex-glm 冷启动配置复盘

记录日期：2026-07-14  
适用场景：在一台新 Windows 电脑上，保留原生 `codex` / GPT 账号不受影响，额外配置一个独立的 `codex-glm` 启动入口，走 Zhipu GLM + 本地 LiteLLM 代理。

## 最终目标

配置完成后应满足：

```powershell
codex
```

仍然使用原生 Codex 账号和默认目录：

```text
C:\Users\<用户名>\.codex
```

新增命令：

```powershell
codex-glm
```

单独使用 GLM 配置目录：

```text
C:\Users\<用户名>\.codex-glm
```

核心隔离点是 `codex-glm` 函数运行时临时设置：

```powershell
$env:CODEX_HOME = "$env:USERPROFILE\.codex-glm"
```

函数退出后恢复原来的 `CODEX_HOME`。不要为了用 GLM 全局设置 `CODEX_HOME`，否则可能污染原生 `codex` 账号。

## 今天踩过的坑

### 1. Python 3.14 不能用于 LiteLLM 1.91.1

`litellm==1.91.1` 要求 Python 版本：

```text
>=3.10, <3.14
```

本机一开始是 Python 3.14，导致不适合安装 LiteLLM。解决方案是额外安装 Python 3.12，不要卸载 3.14。

推荐安装：

```text
Python 3.12.x 64-bit
```

官方下载页：

```text
https://www.python.org/downloads/windows/
```

安装后检查：

```cmd
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" --version
```

如果 `py -3.12 --version` 不可用，不代表 Python 3.12 没装好，可能只是 Python Launcher 没识别。可以直接用完整路径。

### 2. 旧 venv 可能是 Python 3.14 创建的

如果之前用 Python 3.14 创建过：

```text
C:\Users\<用户名>\.litellm-env
```

即使后来装了 Python 3.12，这个 venv 仍然可能指向 3.14。

本次最终采用新目录，避免残留：

```text
C:\Users\<用户名>\.litellm-env312
```

对应代理脚本应调用：

```powershell
& "$env:USERPROFILE\.litellm-env312\Scripts\litellm.exe" --config "$litellmDir\glm-config.yaml" --host 127.0.0.1 --port 4000
```

2026-07-15 补充：分发包里的 `litellm/start-glm-proxy.ps1` 曾残留旧路径：

```powershell
& "$env:USERPROFILE\.litellm-env\Scripts\litellm.exe" --config "$litellmDir\glm-config.yaml" --host 127.0.0.1 --port 4000
```

这会导致明明手工安装了 `.litellm-env312`，但代理仍然启动失败。应统一改成 `.litellm-env312`。

### 3. ZHIPU_API_KEY 可能配置在 Machine 级

原脚本只检查了：

- 当前会话 `$env:ZHIPU_API_KEY`
- User 级环境变量

但本机实际 key 配在 Machine 级。脚本和 `start-glm-proxy.ps1` 都需要兼容 Machine 级：

```powershell
$env:ZHIPU_API_KEY = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "Machine")
```

推荐实际读取顺序：

```powershell
if (-not $env:ZHIPU_API_KEY) {
    $env:ZHIPU_API_KEY = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "User")
}
if (-not $env:ZHIPU_API_KEY) {
    $env:ZHIPU_API_KEY = [Environment]::GetEnvironmentVariable("ZHIPU_API_KEY", "Machine")
}
if (-not $env:ZHIPU_API_KEY) {
    Write-Error "ZHIPU_API_KEY 未设（Session/User/Machine 级环境变量均未找到）"; exit 1
}
```

检查 key 是否存在：

```powershell
$session = [bool]$env:ZHIPU_API_KEY
$user = [bool][Environment]::GetEnvironmentVariable('ZHIPU_API_KEY','User')
$machine = [bool][Environment]::GetEnvironmentVariable('ZHIPU_API_KEY','Machine')
"session=$session user=$user machine=$machine"
```

只要 `session/user/machine` 其中一个为 `True` 即可。

### 4. PowerShell 脚本里 `-Path$变量` 会出错

原安装脚本有几处写法类似：

```powershell
New-Item -ItemType Directory -Force -Path$BackupDir
```

这在 PowerShell 里是不可靠/错误的，应改成：

```powershell
New-Item -ItemType Directory -Force -Path $BackupDir
```

已修过的典型位置：

```powershell
-Path $BackupDir
-Path $codexBinDir
-Path $litellmDir
-Path $profileParent
```

### 5. pip 访问清华源可能 SSL/代理握手失败

清华源可能出现：

```text
SSLEOFError
UNEXPECTED_EOF_WHILE_READING
```

阿里源也可能因网络卡住。最后用户手工在 `cmd.exe` 中 pip 安装成功。

建议新电脑直接用 `cmd.exe` 执行下面命令，少踩 PowerShell quoting / sandbox 问题。

### 6. pip 后台进程可能卡住

安装中断后，可能残留：

```text
pip.exe
python.exe
```

导致下一次安装卡住或目录被占用。

cmd 停止命令：

```cmd
taskkill /F /IM pip.exe
taskkill /F /IM python.exe
```

注意：这会杀掉当前用户正在跑的 Python 进程。确认没有其他重要 Python 任务再执行。

### 7. PowerShell profile 路径可能有两个

本机出现了两个 profile 路径：

```text
C:\Users\xy58\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
D:\Documents and Settings\xy58\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
```

一个普通 PowerShell 会话读 `C:\Users\...`，另一个环境读 `D:\Documents and Settings\...`。

新电脑上要检查：

```powershell
$PROFILE.CurrentUserCurrentHost
```

如果环境特殊，可能需要把 `codex-glm` 函数写入多个 profile。

### 8. OpenRouter 没配 key 时不要放进启动菜单

当前没有配置：

```text
OPENROUTER_API_KEY
```

因此启动菜单里不要提供 OpenRouter 选项，避免误选后失败。

当前策略：

- `codex-glm` 默认只走 Zhipu
- `codex-glm -Zhipu` 只走 Zhipu
- `codex-glm -OpenRouter` 只提示未配置并退出

等以后配置好 OpenRouter key，再恢复入口。

2026-07-15 补充：当前 `codex-glm-profile-func.ps1` 不再弹 provider 菜单，默认直接走 Zhipu；`-OpenRouter` 参数只保留为显式提示入口。

## 新电脑冷启动步骤

### 第 1 步：先确认原生 codex 已可用

```cmd
codex --version
```

如果已输出版本，例如：

```text
codex-cli 0.144.4
```

说明原生 codex 可用。后续不要重装 codex，不要改 `~\.codex`。

### 第 2 步：安装 Python 3.12

下载并安装 Python 3.12 64-bit。

建议安装时勾选：

```text
Add python.exe to PATH
Install launcher for all users
```

检查：

```cmd
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" --version
```

应输出类似：

```text
Python 3.12.x
```

### 第 3 步：创建 LiteLLM 专用 venv

在 `cmd.exe` 中执行：

```cmd
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv "%USERPROFILE%\.litellm-env312"
```

检查：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\python.exe" --version
```

必须是 Python 3.12.x。

### 第 4 步：安装 LiteLLM

如果使用 Clash，优先试官方 PyPI + 本机代理：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\pip.exe" install -U "litellm[proxy]==1.91.1" -i https://pypi.org/simple --proxy http://127.0.0.1:7897
```

如果官方 PyPI 不通，试阿里源：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\pip.exe" install -U "litellm[proxy]==1.91.1" -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com
```

验证：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\litellm.exe" --version
```

成功标志：

```text
LiteLLM: Current Version = 1.91.1
```

### 第 5 步：确认 ZHIPU_API_KEY

PowerShell 中检查：

```powershell
$session = [bool]$env:ZHIPU_API_KEY
$user = [bool][Environment]::GetEnvironmentVariable('ZHIPU_API_KEY','User')
$machine = [bool][Environment]::GetEnvironmentVariable('ZHIPU_API_KEY','Machine')
"session=$session user=$user machine=$machine"
```

如果都为 `False`，需要手工配置环境变量。

User 级配置示例：

```powershell
[Environment]::SetEnvironmentVariable("ZHIPU_API_KEY", "你的key", "User")
```

Machine 级配置需要管理员权限，不建议默认使用，除非你明确要全局配置。

配置后新开 PowerShell。

### 第 6 步：写入独立配置目录

从分发包目录执行：

```powershell
$glmDir = Join-Path $env:USERPROFILE '.codex-glm'
$litellmDir = Join-Path $glmDir 'litellm'
New-Item -ItemType Directory -Force -Path $litellmDir | Out-Null
Copy-Item -LiteralPath .\codex-glm-config.toml -Destination (Join-Path $glmDir 'config.toml') -Force
foreach ($f in @('glm-config.yaml','tool_filter.py','start-glm-proxy.ps1')) {
  Copy-Item -LiteralPath (Join-Path '.\litellm' $f) -Destination (Join-Path $litellmDir $f) -Force
}
```

确认：

```powershell
Get-ChildItem "$env:USERPROFILE\.codex-glm"
Get-ChildItem "$env:USERPROFILE\.codex-glm\litellm"
```

应至少有：

```text
config.toml
litellm\glm-config.yaml
litellm\tool_filter.py
litellm\start-glm-proxy.ps1
```

### 第 7 步：写入 codex-glm 函数

检查 profile 路径：

```powershell
$PROFILE.CurrentUserCurrentHost
```

追加函数：

```powershell
$profilePath = $PROFILE.CurrentUserCurrentHost
$profileParent = Split-Path $profilePath -Parent
if (-not (Test-Path -LiteralPath $profileParent)) {
  New-Item -ItemType Directory -Force -Path $profileParent | Out-Null
}
if (-not (Test-Path -LiteralPath $profilePath)) {
  New-Item -ItemType File -Force -Path $profilePath | Out-Null
}
if (-not (Select-String -Path $profilePath -Pattern 'function codex-glm' -Quiet)) {
  $bak = "$profilePath.bak-codex-glm-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
  Copy-Item -LiteralPath $profilePath -Destination $bak -Force
  $snippet = Get-Content -LiteralPath .\codex-glm-profile-func.ps1 -Raw
  Add-Content -LiteralPath $profilePath -Value "`r`n`r`n$snippet" -Encoding UTF8
}
```

新开 PowerShell 后验证：

```powershell
Get-Command codex-glm
```

### 第 8 步：启动 LiteLLM 代理做健康检查

PowerShell：

```powershell
$litellmDir = Join-Path $env:USERPROFILE '.codex-glm\litellm'
Start-Process -FilePath 'pwsh.exe' `
  -ArgumentList '-NoProfile','-File',"$litellmDir\start-glm-proxy.ps1" `
  -WindowStyle Hidden `
  -RedirectStandardOutput "$litellmDir\proxy.log" `
  -RedirectStandardError "$litellmDir\proxy.err.log"
```

检查端口：

```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
```

检查模型接口：

```powershell
Invoke-RestMethod `
  -Uri 'http://127.0.0.1:4000/v1/models' `
  -Headers @{Authorization='Bearer sk-codex-local'} |
  ConvertTo-Json -Depth 4
```

成功时应看到：

```json
{
  "data": [
    {
      "id": "glm-5.2"
    }
  ]
}
```

### 第 9 步：使用 codex-glm

新开 PowerShell：

```powershell
codex-glm
```

或显式：

```powershell
codex-glm -Zhipu
```

原生账号仍使用：

```powershell
codex
```

## 当前建议保留的 codex-glm 行为

当前没有 OpenRouter key，因此 `codex-glm-profile-func.ps1` 应保持：

```powershell
if ($OpenRouter) {
  Write-Warning "OpenRouter 暂未配置 OPENROUTER_API_KEY，当前已禁用。请先配置后再恢复入口。"
  return
}
```

不要在菜单里显示 OpenRouter。

## 常用排错命令

查看 LiteLLM 错误日志：

```powershell
Get-Content "$env:USERPROFILE\.codex-glm\litellm\proxy.err.log" -Tail 80
```

查看 LiteLLM 普通日志：

```powershell
Get-Content "$env:USERPROFILE\.codex-glm\litellm\proxy.log" -Tail 80
```

查看 4000 端口监听：

```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
```

停止 4000 端口对应进程：

```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
  }
```

验证 LiteLLM：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\litellm.exe" --version
```

验证 codex：

```cmd
codex --version
```

验证 codex-glm 函数：

```powershell
Get-Command codex-glm
```

## 不要做的事

不要全局设置：

```powershell
$env:CODEX_HOME = "$env:USERPROFILE\.codex-glm"
```

不要覆盖：

```text
C:\Users\<用户名>\.codex
```

不要在 OpenRouter key 未配置前恢复 OpenRouter 菜单。

不要用 Python 3.14 创建 LiteLLM venv。

## 本次最终状态参考

本机最终确认过：

```text
codex-cli 0.144.4
LiteLLM: Current Version = 1.91.1
Python 3.12.6
LiteLLM proxy: http://127.0.0.1:4000
GLM model id: glm-5.2
```

两个 profile 都同步写入过 `codex-glm` 函数：

```text
C:\Users\xy58\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
D:\Documents and Settings\xy58\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
```

其中第二个 profile 前面有 Clash 代理配置，替换 `codex-glm` 函数时不要误删前面的代理配置。

## 2026-07-15 本机 xy147 落地补充

本机用户：

```text
xy147
```

本次采用用户手工在 `cmd.exe` 中安装 LiteLLM，验证结果：

```cmd
"%USERPROFILE%\.litellm-env312\Scripts\litellm.exe" --version
```

输出：

```text
LiteLLM: Current Version = 1.91.1
```

实际写入的 `codex-glm` 配置目录：

```text
C:\Users\xy147\.codex-glm
```

目录内关键文件：

```text
C:\Users\xy147\.codex-glm\config.toml
C:\Users\xy147\.codex-glm\litellm\glm-config.yaml
C:\Users\xy147\.codex-glm\litellm\tool_filter.py
C:\Users\xy147\.codex-glm\litellm\start-glm-proxy.ps1
```

实际写入的 PowerShell profile：

```text
D:\Documents and Settings\xy147\Documents\PowerShell\Microsoft.PowerShell_profile.ps1
```

写入前备份：

```text
D:\Documents and Settings\xy147\Documents\PowerShell\Microsoft.PowerShell_profile.ps1.bak-codex-glm-20260715-093921
```

本机 `ZHIPU_API_KEY` 检查结果：

```text
session=True user=False machine=True
```

说明 key 实际来自 Machine 级环境变量，`start-glm-proxy.ps1` 必须支持 Machine 级读取。

本机 LiteLLM 代理验证：

```text
LiteLLM proxy: http://127.0.0.1:4000
进程 PID: 11640
```

`/v1/models` 返回：

```json
{
  "data": [
    {
      "id": "glm-5.2",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    },
    {
      "id": "codex-auto-review",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai"
    }
  ],
  "object": "list"
}
```

本机已确认：

```powershell
Get-Command codex-glm
```

返回：

```text
codex-glm    Function
```

本次同步修正分发包文件：

```text
litellm/start-glm-proxy.ps1
codex-glm-profile-func.ps1
```

修正点：

- `start-glm-proxy.ps1` 使用 `.litellm-env312`，不再使用旧的 `.litellm-env`。
- `start-glm-proxy.ps1` 按 Session -> User -> Machine 顺序读取 `ZHIPU_API_KEY`。
- `codex-glm-profile-func.ps1` 默认直接走 Zhipu，不再显示 OpenRouter 菜单。
- `codex-glm -OpenRouter` 当前只提示未配置 `OPENROUTER_API_KEY` 并退出。

新开 PowerShell 后使用：

```powershell
codex-glm
```

或：

```powershell
codex-glm -Zhipu
```

原生账号仍使用：

```powershell
codex
```





## ------------------------------- 用户备注 2026-07-15 --------------------------------

>>>>>>>>>>>>>>>>>>>>>>>  2026-07-09 codex 正式上线！！ >>>>>>>>>>>>>>>>>>>>>>>>>

1、Powershell 可以直接安装 codex了！（需安装nodejs + 配置 vpn）
下载并安装 nodejs: https://nodejs.org/en/download
pwshell 的 bashrc 文件 物理路径：C:\Users\你的用户名\Documents\PowerShell\
#首次使用通常不存在，用该命令创建
if (!(Test-Path -Path $PROFILE)) { New-Item -Type File -Path $PROFILE -Force }

#推荐用vs code 打开

code $PROFILE   # 用 VS Code 打开

配置 powershell proxy：

-------------
#==================== Clash Proxy for PowerShell ====================

$proxy = "http://127.0.0.1:7897"

$proxySocks = "socks5://127.0.0.1:7897"

#HTTP/HTTPS 代理

$env:HTTP_PROXY = $proxy

$env:HTTPS_PROXY = $proxy

$env:http_proxy = $proxy

$env:https_proxy = $proxy



#SOCKS5（npm 经常更稳定）

$env:ALL_PROXY = $proxySocks

$env:NO_PROXY = "localhost,127.0.0.1,::1,.local"

#Git 代理（和 Git Bash 保持一致）
#git config --global http.proxy "socks5h://127.0.0.1:7897"
#git config --global https.proxy "socks5h://127.0.0.1:7897"


# npm 专用代理设置
npm config set proxy $proxy
npm config set https-proxy $proxy

#或者用 socks5
#npm config set proxy "socks5h://127.0.0.1:7897"
#npm config set https-proxy "socks5h://127.0.0.1:7897"
Write-Host "? PowerShell 已切换到 Clash 代理 (7897端口)" -ForegroundColor Green
#==================== Clash Proxy for PowerShell ====================
-------------
npm安装codex：npm install -g @openai/codex
升级codex：npm update -g @openai/codex
-------------
#测试网络（可选）
Invoke-WebRequest -Uri https://www.google.com -UseBasicParsing -Proxy $env:http_proxy | Select-Object StatusCode
curl -I https://www.google.com







> 上次我手工pip安装的 依赖包，因为我在cmd中安装更方便，你将命令发给我，我继续手工安装
>> 注意：fangcaixia 电脑安装依赖包需要接近10分钟，需要耐心等待


  你在 cmd.exe 里执行下面两步即可。

  先确认 Python 3.12 路径存在：

  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" --version

  创建 LiteLLM 专用 venv：

  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv "%USERPROFILE%\.litellm-env312"

  安装 LiteLLM，优先用官方 PyPI + Clash 本地代理：

  "%USERPROFILE%\.litellm-env312\Scripts\pip.exe" install -U "litellm[proxy]==1.91.1" -i
  https://pypi.org/simple --proxy http://127.0.0.1:7897

  如果上面官方源失败，再试阿里源：

  "%USERPROFILE%\.litellm-env312\Scripts\pip.exe" install -U "litellm[proxy]==1.91.1" -i
  https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

  安装完成后验证：

  "%USERPROFILE%\.litellm-env312\Scripts\litellm.exe" --version

  期望看到类似：

  LiteLLM: Current Version = 1.91.1

  你装完后告诉我结果，我继续帮你写入 ~\.codex-glm 配置和 codex-glm PowerShell 函数。
