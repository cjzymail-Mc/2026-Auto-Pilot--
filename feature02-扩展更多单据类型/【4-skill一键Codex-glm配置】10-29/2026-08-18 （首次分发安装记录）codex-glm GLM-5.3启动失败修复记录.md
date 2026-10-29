# codex-glm GLM-5.3 启动失败修复记录

> 日期：2026-08-18  
> 状态：已修复并验收  
> 范围：Windows PowerShell `codex-glm` → 本地 LiteLLM → Z.ai `glm-5.3`

## 结论

`glm-5.3` 模型配置本身没有故障。本次实际叠加了两个独立问题：

1. `C:\Users\xy147\.litellm-env` 是损坏残留：有 `Scripts\litellm.exe`，但没有 `Scripts\python.exe`。按目录或单个入口文件判断会出现“假绿”。
2. 改用正常的 `.litellm-env312` 后，LiteLLM 已成功启动；随后的 HTTP 500 根因是 `api.z.ai` 当时 DNS 解析失败，日志为 `ClientConnectorDNSError ... [getaddrinfo failed]`，不是模型名或 reasoning 参数错误。

同一个修复后的 LiteLLM 进程对 `glm-5.2` 和 `glm-5.3` 连续 A/B 请求，两者均成功返回，排除 GLM-5.3 升级本身导致的协议故障。

## 链路

```text
codex-glm
  → CODEX_HOME=C:\Users\xy147\.codex-glm
  → http://127.0.0.1:4000/v1  (LiteLLM Responses → Chat 翻译)
  → https://api.z.ai/api/coding/paas/v4
  → glm-5.3
```

Zhipu 路线仍保持直连：启动脚本清理 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`，并设置 `NO_PROXY`。本次没有修改 PowerShell profile 中的绕过代理规则。

Codex provider 配置继续放在独立的用户级 `C:\Users\xy147\.codex-glm\config.toml`。官方配置参考说明 provider 类配置应放在用户级配置，项目级 `.codex/config.toml` 会忽略 `model_provider` / `model_providers`：<https://learn.chatgpt.com/docs/config-file/config-reference>

## 现场证据

- 损坏环境：`.litellm-env | dir=True | python=False | litellm=True`
- 可用环境：`.litellm-env312 | python=True | litellm=True | Python 3.12.6`
- LiteLLM 启动日志：`Application startup complete` + `Uvicorn running on http://127.0.0.1:4000`
- 失败第一层异常：`Cannot connect to host api.z.ai:443 ... [getaddrinfo failed]`
- 后续同解释器检查：`api.z.ai` DNS 解析到 `128.1.150.233`，TCP 443 成功
- A/B 验收：`glm-5.2 = success`，`glm-5.3 = success`

`Received Model Group=glm-5.3` 只表示 LiteLLM 当时正在路由的模型，不是错误原因。判断根因必须继续向下看到第一个原始异常。

## 精确修复

仅修改一个分发包脚本：

```text
[4-skill一键Codex-glm配置](1)\litellm\start-glm-proxy.ps1
```

修复点：

- 优先检查标准 `.litellm-env`，不可用时回退 `.litellm-env312`。
- 只有同一 venv 内同时存在 `Scripts\python.exe` 和 `Scripts\litellm.exe` 才允许启动。
- `ZHIPU_API_KEY` 读取顺序补全为 Session → User → Machine。
- 不修改 GLM-5.3 YAML、Z.ai API base、thinking/reasoning 参数或直连规则。

修复脚本已同步到 live：

```text
C:\Users\xy147\.codex-glm\litellm\start-glm-proxy.ps1
```

包内与 live SHA256 一致：

```text
9A0ED11C009725404E02B1184FF0ED2A525282B3AE69EDC648CF3CF2568916C8
```

原 live 脚本备份：

```text
C:\Users\xy147\.codex-glm\litellm\start-glm-proxy.ps1.bak-codex-fix-20260818-115220
```

## 冷启动最短检查

1. 先读工作区 `AGENTS.md`、分发包 `README.md` 和本记录。
2. 确认 `ZHIPU_API_KEY` 至少在 Session / User / Machine 其一层存在，不输出 key 明文。
3. 检查 venv 必须同时有 `Scripts\python.exe` 和 `Scripts\litellm.exe`；只有目录或 `litellm.exe` 不算成功。
4. 新开 PowerShell，执行 `codex-glm`；它会在 4000 端口无监听时懒启动 LiteLLM。
5. 失败时只看 `C:\Users\xy147\.codex-glm\litellm\proxy.err.log` 的第一个原始异常，不要围绕最后一层包装错误反复重试。

```powershell
Get-NetTCPConnection -LocalPort 4000 -State Listen -ErrorAction SilentlyContinue
Resolve-DnsName api.z.ai -Type A
Get-Content "$env:USERPROFILE\.codex-glm\litellm\proxy.err.log" -Tail 80
Invoke-RestMethod -Uri 'http://127.0.0.1:4000/v1/models' -Headers @{ Authorization='Bearer sk-codex-local' }
```

## 错误分层

| 信号 | 所属层 | 处理 |
|---|---|---|
| venv 有目录/入口，但缺 `python.exe` | Python 环境 | 判定为损坏 venv，使用完整 venv；不继续换命令碰运气 |
| `Application startup complete` 后出现 `getaddrinfo failed` | DNS / 网络 | 检查 `Resolve-DnsName api.z.ai`；不改模型参数 |
| Z.ai 已返回 HTTP 4xx JSON | API / 模型参数 | 再检查模型名、key、endpoint 和 request body |
| `Model metadata for glm-5.3 not found` | Codex 内置模型表 | 已知无害警告，不当成 LiteLLM 启动失败 |

## 回滚

如需恢复本次修复前的 live 脚本：

```powershell
Copy-Item -LiteralPath `
  'C:\Users\xy147\.codex-glm\litellm\start-glm-proxy.ps1.bak-codex-fix-20260818-115220' `
  -Destination 'C:\Users\xy147\.codex-glm\litellm\start-glm-proxy.ps1' -Force
```

回滚只影响 LiteLLM 启动脚本，不触碰原生 `C:\Users\xy147\.codex`。
