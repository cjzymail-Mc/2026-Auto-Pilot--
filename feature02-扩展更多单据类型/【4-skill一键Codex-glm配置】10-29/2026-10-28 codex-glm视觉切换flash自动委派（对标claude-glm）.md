# codex-glm 视觉切换 flash 自动委派（2026-10-28，对标 claude-glm）

> 性质：方案切换记录。用户拍板：放弃修复旧 `zai-vision-primary-glm46v` MCP（glm-4.6v）路线，codex-glm 沿用 claude-glm 的方案——常规默认 glm-5.3，图片任务自动切换视觉模型 glm-5.3-flash。**约束：全程 Zhipu API（ZHIPU_API_KEY 直达 z.ai 端点），不经 OpenRouter。**

## 方案对照

| 环节 | claude-glm（10-26 已实测） | codex-glm（本次） |
|---|---|---|
| 主模型 | glm-5.3（Zhipu anthropic 端点） | glm-5.3（LiteLLM → coding 端点，不变） |
| 路由规则注入 | `--append-system-prompt` routing.md | `$CODEX_HOME/AGENTS.md` 全局规则（标记块） |
| 视觉执行体 | `--agents` vision-reader 子 agent（模型 glm-5.3-flash，仅 Read） | `vision-read.ps1` 脚本（模型切换在脚本内固定，确定性） |
| flash 到达路径 | 直连 api.z.ai/api/anthropic | 脚本 → 本机 LiteLLM（明文 HTTP）→ coding 端点 |
| 触发方式 | 模型遵循启动规则（软路由） | 同左：模型遵循 AGENTS.md 规则，非 MIME 硬拦截 |

Codex 无 `--agents` 注入机制，且未验证子 agent 能否摄取图片像素，故视觉执行体用确定性脚本而非 custom agent；「自动切换」= 规则引导主模型调脚本，模型切换由脚本固定完成。

## 实测踩到的两个坑（均已定案）

1. **codex Windows 沙箱内出站 TLS 全废**：脚本直连 `https://api.z.ai` 在沙箱内报 `Authentication failed | inner: 安全包中没有可用的凭证`（Schannel SEC_E_NO_CREDENTIALS，受限令牌拿不到凭证）；同一命令沙箱外正常。**解法**：脚本改调本机 LiteLLM `http://127.0.0.1:4000/v1/chat/completions`（回环明文，不经 Schannel），HTTPS 一段由沙箱外的 LiteLLM 进程完成，仍直达 Zhipu。代理未运行时脚本自动拉起（同启动函数逻辑）。
2. **LiteLLM 桥前缀只服务 responses 客户端**：`openai/chat_completions/<model>` 写法的条目被直接 chat/completions 调用时会向上游发错模型名（实测 glm-5.3 也 400 Unknown Model，即日常主流量没暴露此问题只因 codex 走 responses 桥）。**解法**：flash 条目用标准 openai 兼容写法 `openai/glm-5.3-flash`；主模型条目不动。

前置探测：glm-5.3-flash 在 coding 端点（api.z.ai/api/coding/paas/v4）可用（200，无订阅 429）；本机 codex 0.164.0 全局 AGENTS.md 加载正常（Windows 历史_bug codex#8759 未复现）。

## 验证矩阵（测试图真值：CODE VZ-88042 / AMT 1,234.56，System.Drawing 生成）

| 场景 | 结果 | 证据 |
|---|---|---|
| 脚本直跑（沙箱外，经 LiteLLM） | PASS | `实际应答模型: glm-5.3-flash`；`{"code":"VZ-88042","amount":"1,234.56"}` 逐字符一致 |
| **codex exec 端到端（沙箱内）** | PASS | prompt 只给图片路径和问题、不点名脚本/flash；主 glm-5.3 自主调脚本 → flash 应答 → JSON 字段与真值一致（对标 claude-glm 10-26 验收口径） |
| 失败路径诚实性 | PASS | 早期沙箱 TLS 失败时主模型返回 `null` JSON 并转述报错，未编造图片内容 |
| 安装器第 6 步隔离验证（临时目录执行从安装器原文抽取的代码块） | PASS（20/20） | 新建 / 外部内容+过期块替换 / 外部内容追加三分支 + 幂等重跑 + 覆盖备份阳性对照。首轮 17/20 抓出**幂等 bug**（END 标记后的换行未被消费 → 每重跑一次文件末尾多一空行、重复备份），修复后复跑全绿 |

## 落地清单

**live（`~/.codex-glm/`）**：

| 文件 | 动作 |
|---|---|
| `AGENTS.md`（新增） | 视觉路由规则块（BEGIN/END 标记，供安装器幂等管理） |
| `vision/vision-read.ps1`（新增） | 图片→glm-5.3-flash 助手；自动拉起 LiteLLM；回显实际应答模型 |
| `litellm/glm-config.yaml` | 新增 `glm-5.3-flash` 条目（备份 `.bak-vision-flash-20261028-120800`）；代理已重启加载 |
| `config.toml` | 移除 `zai-vision-primary-glm46v` MCP 条目（备份 `.bak-vision-relocate-20261028-113737`）；连带清掉上午误复制的 `mcp/` 旧脚本 |

**dist（`[4-skill一键Codex-glm配置]/`）**：`vision/vision-read.ps1` + `vision/AGENTS-vision-routing.md` 新增；安装器新增第 6 步（部署脚本 + 幂等合并 AGENTS.md 标记块，原 6/7/8 顺延为 7/8/9）；yaml 同步 flash 条目；README 补段/文件清单/排错。

## 退役与回滚

- 退役：glm-4.6V MCP 路线（@z_ai/mcp-server 包装）。原始脚本与冷启动文档仍在 Info Classifier repo `调试-修复记录/`（历史档案，不动）。
- 回滚视觉：删 `~/.codex-glm/AGENTS.md` 标记块 + `vision/` 目录；yaml flash 条目按 `.bak-vision-flash-*` 恢复并重启代理。
- 回滚 MCP（如需）：config.toml 按 `.bak-vision-relocate-*` 恢复（注意其指向的脚本已归档，需先还原脚本位置）。

## 验收要点（同事机器）

1. 安装器 9 步全绿，第 6 步显示「视觉脚本就位 / 视觉路由块已写入」。
2. 新开 PowerShell → `codex-glm` 选 Zhipu → 贴一个真实图片任务（不点名脚本）→ 回答应来自 flash（看 `[codex-glm vision] 实际应答模型: glm-5.3-flash` 证据行）。
3. 全局 AGENTS.md 在 Windows 有历史加载 bug（codex#8759）：若路由没触发，先 `codex --version` 再实测一次；本机 0.164.0 正常。

## 边界

- 自动委派是软路由（模型遵循规则），非按文件类型硬拦截——与 claude-glm 同口径。
- 图片须有本地路径（≤5MB，png/jpg/jpeg/webp/gif）；粘贴图先落盘；PDF 有文字层优先文字提取。
- OpenRouter 路线（路由 2）会话里视觉脚本同样可用（脚本自动拉起 LiteLLM），flash 仍走 Zhipu。
- OCR 结果仍须业务核验；未标注字段 null，不猜测（规则已写入 AGENTS.md 块）。
