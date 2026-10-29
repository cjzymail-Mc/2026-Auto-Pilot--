# PowerShell 原生 codex-glm 搭建记录（对标 claude-glm）

> 日期：2026-07-10 ｜ feature-04 ｜ 模式 /free（B 自主 + mc-expert 陪审）
> 状态：✅ **全部验证通过（含用户手工验证 2026-07-11）**
>   - [1] Zhipu（z.ai 国内直连 via LiteLLM）— `codex exec` 答"2" + approve-for-me（auto-review→glm-4.5-air）手工验证通过
>   - [2] OpenRouter 直连 — `codex exec` 答"2"（approve-for-me 不可用，见 Auto-review 小节）
> 对照：WSL 版 → `[2-WSL+Codex配置-glm]/codex-glm-搭建与升级-修复记录.md`；claude-glm 母本 → `C:\Users\xy198\.bashrc`

---

## 目标

PowerShell 敲 `codex-glm` → 菜单选 provider → 走 GLM 的独立 codex 会话，与默认 codex（gpt-5.6-sol + ChatGPT）隔离。对标 `claude-glm`。

## 架构

```
codex-glm  (pwsh profile 函数，菜单 [1]Zhipu / [2]OpenRouter)
  └─ 临时 CODEX_HOME = ~/.codex-glm   独立目录，不碰默认 ~/.codex
      └─ config.toml：定义两个 model_providers

  [1] Zhipu：codex -c model=glm-5.2 -c model_provider=zai-litellm
       └─ localhost:4000 LiteLLM（responses→chat 翻译 + tool_filter 滤非function工具）
           └─ z.ai /api/coding/paas/v4/chat/completions  （国内直连，NO_PROXY）

  [2] OpenRouter：codex -c model=z-ai/glm-5.2 -c model_provider=openrouter
       └─ openrouter.ai/api/v1/responses  （responses 直连，走 Clash）

  退出后 try/finally 恢复 CODEX_HOME，当前终端裸 codex 仍是默认账号
```

## 为什么两路（协议根因）

**实测（2026-07-10 curl 直测）**：codex 0.122+ 强制 Responses 协议（0.144 同）；z.ai/DeepSeek 均无 responses 路由（404，chat/completions 200），**仅 OpenRouter 网关支持 responses**。
- 要 **z.ai 国内直连 + 无中转费** → 须本地 LiteLLM 翻译（responses→chat），即 WSL 那套
- 要 **零本地依赖** → 走 OpenRouter（国外，走 Clash，有中转费）

两路都给，菜单选。claude 能三家直连是 Anthropic 协议的奢侈，codex 没有。

---

## 落地配置

### 1. `~/.codex-glm/config.toml`（独立目录，两个 provider）

```toml
model = "z-ai/glm-5.2"                       # 默认值（菜单会 -c override）
model_provider = "openrouter"
model_context_window = 200000

[model_providers.openrouter]
name = "OpenRouter"
base_url = "https://openrouter.ai/api/v1"
env_key = "OPENROUTER_API_KEY"
wire_api = "responses"

[model_providers.zai-litellm]
name = "Z.ai via LiteLLM (responses->chat 翻译)"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_KEY"                      # 本地代理握手 key（函数设为 sk-codex-local）
wire_api = "responses"
```

### 2. pwsh profile `codex-glm` 函数（菜单版 + LiteLLM 懒启动 + 选 Zhipu 临时清 proxy）

profile：`D:\Documents and Settings\xy198\Documents\PowerShell\Microsoft.PowerShell_profile.ps1`（`.bak-before-codex-glm-20260710`）

```powershell
function codex-glm {
  param([switch]$Zhipu, [switch]$OpenRouter)
  if ($OpenRouter) { $choice = "2" }
  elseif ($Zhipu) { $choice = "1" }
  else {
    Write-Host "  [1] Zhipu (z.ai 国内直连 via LiteLLM)  [2] OpenRouter (直连)"
    $choice = Read-Host "输入 1/2 (回车默认 1=Zhipu)"
  }
  $oldHome = $env:CODEX_HOME
  $proxyVars = @("HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","ALL_PROXY","all_proxy")
  $savedProxy = @{}
  try {
    $env:CODEX_HOME = "$env:USERPROFILE\.codex-glm"
    if ($choice -eq "2") {
      codex -c 'model="z-ai/glm-5.2"' -c 'model_provider="openrouter"' @args
    } else {
      # 选 Zhipu：临时清掉所有代理变量（z.ai 国内直连，codex 侧也别走 Clash）；finally 恢复
      foreach ($v in $proxyVars) {
        if (Test-Path "Env:$v") { $savedProxy[$v] = (Get-Item "Env:$v").Value; Remove-Item "Env:$v" -ErrorAction SilentlyContinue }
      }
      $env:LITELLM_KEY = "sk-codex-local"
      $litellmDir = "$env:USERPROFILE\.codex-glm\litellm"
      if (-not (Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process pwsh.exe -ArgumentList "-NoProfile","-File","$litellmDir\start-glm-proxy.ps1" -WindowStyle Hidden -RedirectStandardOutput "$litellmDir\proxy.log" -RedirectStandardError "$litellmDir\proxy.err.log"
        for ($i=0;$i -lt 60;$i++){ if(Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue){break}; Start-Sleep -Milliseconds 500 }
      }
      codex -c 'model="glm-5.2"' -c 'model_provider="zai-litellm"' @args
    }
  } finally {
    $env:CODEX_HOME = $oldHome
    # 恢复临时清掉的 proxy（当前终端其他命令照常走 Clash）
    foreach ($v in $proxyVars) { if ($savedProxy.ContainsKey($v)) { Set-Item "Env:$v" $savedProxy[$v] } }
  }
}
```

### 3. LiteLLM 三件套 `~/.codex-glm/litellm/`

- **`glm-config.yaml`**（⚠️ **纯 ASCII**，见下方 Windows 坑②）：`model_name: glm-5.2` → `litellm_params.model: openai/chat_completions/glm-5.2`（前缀触发 responses→chat 翻译桥）+ `api_base: z.ai coding` + `api_key: os.environ/ZHIPU_API_KEY` + `drop_params: true` + `callbacks: [tool_filter.proxy_handler_instance]` + `master_key: sk-codex-local`
- **`tool_filter.py`**：CustomLogger 的 `async_pre_call_hook`，剔除非 function 类型工具（codex 0.142+ 多发 web_search/image_generation，z.ai chat 接口只认 function，否则 400）。对标 WSL。
- **`start-glm-proxy.ps1`**：设 `NO_PROXY=api.z.ai,open.bigmodel.cn` + 清 Clash 代理变量（z.ai 国内直连）+ 取 ZHIPU_API_KEY（继承优先/User 兜底）+ `cd $litellmDir + PYTHONPATH`（让 tool_filter 可 import）+ 启动 venv 的 litellm。

### 4. `~/.litellm-env`（Python venv + litellm[proxy] 1.91.1）

```powershell
python -m venv ~/.litellm-env
$env:HTTPS_PROXY="http://127.0.0.1:7897"      # 见 Windows 坑①
~/.litellm-env/Scripts/python.exe -m pip install "litellm[proxy]"
```

---

## 验证（已实测）

| 路径 | 命令 | 结果 |
|---|---|---|
| OpenRouter | `codex exec -c model=z-ai/glm-5.2 -c model_provider=openrouter "1+1=?"` | model=z-ai/glm-5.2 provider=openrouter → "2" ✓ |
| Zhipu via LiteLLM | `codex exec -c model=glm-5.2 -c model_provider=zai-litellm "1+1=?"` | model=glm-5.2 provider=zai-litellm → "2" ✓ |
| LiteLLM 翻译桥 | `curl localhost:4000/v1/responses` | 返回标准 responses，text="pong" ✓ |
| codex-auto-review 别名 | `curl localhost:4000/v1/responses -d model=codex-auto-review` | 经 LiteLLM→glm-4.5-air 返回 "ok" ✓（reviewer 走轻量模型；glm-4.7-flash 限流429 不用） |

**默认 codex 未污染**：每次 smoke 都 `CODEX_HOME=.codex-glm` 跑出 GLM（隔离生效）；默认 `~/.codex/config.toml` 全程未改（仍 gpt-5.6-sol）；函数 try/finally 恢复 CODEX_HOME。

---

## ℹ️ "Model metadata not found" 警告（无害，无法消除）

每次启动 codex-glm 都会打印：
> `warning: Model metadata for glm-5.2 not found. Defaulting to fallback metadata; this can degrade performance and cause issues.`

**根因**：codex 内置一张**写死在 Rust 二进制里**的模型 metadata 表（gpt/claude 等）。自定义 provider 接进来的模型（glm-5.2，无论走 OpenRouter 还是 LiteLLM）**永远不在表里** → 启动必打这行。npm 包里**没有可编辑的 catalog 文件**（只有 package.json），改不了。

**实测（2026-07-11）**：设全 model metadata 字段（config 里 `model_context_window=200000` + `-c model_max_output_tokens=8192`）**也不能消除警告**——这些字段只 override 具体值，不改变"模型不在内置表"的查表结果。两次对比警告照打。

**实质影响：几乎没有。**
- `context_window`：config 已设 `200000`（glm-5.2 真实窗口），codex 用真实值、**不是 fallback**，最关键项已准。
- `max_output_tokens` 等其他项用 fallback 默认值——编码单次输出很少撞上限，可忽略。
- 功能完全正常（GLM 正常干活，多次验证答对）。

**结论：忽略它**。这是 codex 对"非内置模型"的固有提示，所有走 Ollama/LiteLLM/OpenRouter 接第三方模型的用户都会遇到（GitHub [#12100](https://github.com/openai/codex/issues/12100) / [#14757](https://github.com/openai/codex/issues/14757)）。不是报错，不用管。

---

## 🔧 Auto-review 报错（approve-for-me 用 codex-auto-review 模型）

**现象**：codex-glm 里 permission 选 "approve for me"，报：
> `Automatic approval review failed: /responses: Invalid model name passed in model=codex-auto-review`

**根因**：config 里 `approvals_reviewer = "auto_review"` 启用 codex 的 [Auto-review](https://developers.openai.com/codex/concepts/sandboxing/auto-review)——approve-for-me 时起一个**独立 reviewer agent**，调专用模型 `codex-auto-review` 审查每次自动批准。这模型名 OpenAI 专用，你的 provider（z.ai/OpenRouter）没有 → "Invalid model name"。reviewer 用主 provider（错误从 provider 返回）。**不是 proxy 问题、也不是 glm 接不了模型**（glm 对话正常）。

**解法（已落地，仅 Zhipu 路径）**：LiteLLM 的 glm-config.yaml 加一条别名，让 reviewer 走**轻量模型**（review 是高频轻量审查，用 glm-5.2 浪费）。实测（2026-07-11）z.ai 端点：glm-4.7-flash 存在但**限流 429**（flash 类低价模型阈值低，高频 auto-review 易撞 → reviewer 失败 = approve 被 deny）；glm-4.5-air / glm-4.7 稳定 200。**选 glm-4.5-air**（轻量 + 稳定）：
```yaml
  - model_name: codex-auto-review
    litellm_params:
      model: openai/chat_completions/glm-4.5-air   # 轻量；glm-4.7-flash 限流429，air 稳定200
      api_base: https://api.z.ai/api/coding/paas/v4
      api_key: os.environ/ZHIPU_API_KEY
```

**⚠️ 限制**：仅 **Zhipu（LiteLLM）路径**有效（LiteLLM 能加别名）。**OpenRouter 路径加不了别名**，approve-for-me 仍报错——OpenRouter 路径别用 approve-for-me；要 auto-approve 就走 Zhipu，或在 config 删 `approvals_reviewer`（两路通用，但失去 auto-approve）。

**✅ 用户手工验证通过（2026-07-11）**：`codex-glm -Zhipu` + permission 选 "approve for me"，auto-review 走 glm-4.5-air 正常工作，不再报 "Invalid model name"。

---

## ⚠️ Windows 移植坑（WSL→Windows 真实差异，WSL 无）

| # | 坑 | 现象 | 解法 |
|---|---|---|---|
| ① | **pip SSL EOF** | `pip install` 报 `SSLEOFError UNEXPECTED_EOF_WHILE_READING` | Clash **TUN 模式**劫持大流量 SSL 打断 Python openssl。解：pip 显式走 Clash **HTTP 代理 127.0.0.1:7897**（绕 TUN）+ 用**官方 PyPI**（国外经节点稳）；清华镜像（国内）经 TUN 反而断。WSL 不经 Windows TUN，故无此问题。 |
| ② | **yaml gbk 解码错** | litellm 启动报 `UnicodeDecodeError: 'gbk' codec can't decode byte 0x80` | Windows Python locale=**gbk**，`yaml.safe_load` 用 gbk 读 UTF-8 中文 yaml 炸。解：**glm-config.yaml 纯 ASCII**（英文注释）。WSL 的 Python locale=UTF-8 无此问题。 |
| ③ | key 变量名 | claude-glm 用 `ZHIPU_API_KEY`，WSL codex 用 `GLM_API_KEY` | 本套统一 `ZHIPU_API_KEY`（Windows 系统环境变量），litellm config 里 `os.environ/ZHIPU_API_KEY`。 |

---

## 日常使用

```powershell
codex-glm                  # 弹菜单（回车默认 Zhipu）
codex-glm -Zhipu           # 直选 z.ai 国内直连（headless 友好，绕过菜单）
codex-glm -OpenRouter      # 直选 OpenRouter
codex                      # 不带 -glm，仍是默认 gpt-5.6-sol 账号（未污染）
```
> 首次用需**新开 PowerShell 窗口**（加载 profile 注册函数）。选 Zhipu 时 LiteLLM 代理自动懒启动（首次约 11s），之后复用。

## 故障速查

| 症状 | 处理 |
|---|---|
| `codex-glm` 命令不存在 | 新开 pwsh 窗口，或 `. $PROFILE` 重载 |
| Zhipu 路径卡住/报错 | 看 `~/.codex-glm/litellm/proxy.err.log`；确认 ZHIPU_API_KEY 在系统环境变量 |
| OpenRouter 不通 | 检查 Clash 运行（TUN 或 HTTP 代理均可） |
| `400 tools[N].type illegal`（z.ai） | tool_filter 钩子没生效：确认 `start-glm-proxy.ps1` 里 `cd $litellmDir + PYTHONPATH` + 重启代理 |
| approve-for-me 报 `codex-auto-review` Invalid model | auto-review 用 OpenAI 专用模型名；**Zhipu 路径靠 LiteLLM 别名已解**，**OpenRouter 路径别用 approve-for-me**（见 Auto-review 小节） |
| LiteLLM 启动报 gbk/yaml 错 | glm-config.yaml 必须**纯 ASCII**（坑②） |
| 想换模型 | 改 `glm-config.yaml` 的 `model_name`/`litellm_params.model`（z.ai 端），或 codex `-c model=` |
| `Model metadata not found` 警告 | **无害，无法消除**，忽略即可（见上方专门小节） |

## 安全

- key 全走系统环境变量（OPENROUTER_API_KEY / ZHIPU_API_KEY），config/yaml 零明文。
- profile 改动有 `.bak-before-codex-glm-20260710` 可回滚；LiteLLM 配置独立于默认 `.codex`，物理隔离。
