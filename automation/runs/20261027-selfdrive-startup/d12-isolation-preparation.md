# D12 隔离启动只读调查（协调工程资料，非新增授权）

用途：供原生 A 后续派工和阶段二核查准备。本文不是 D12 阶段一的现成输入包，也不代表冷启动或业务执行已通过。

调查来源：Codex 只读准备 agent `/root/skill_review`。调查未启动模型业务 session，未访问 OA、凭证、会话记录或 registry 内容，未修改文件。实现与正式验收仍由既定原生 A/B 工作流负责。

## 本机确证

- 原生程序 `C:/Users/xy198/.local/bin/claude.exe`，本机版本 `2.1.299`。
- 本机 help 的 `--safe-mode` 关闭 CLAUDE.md、skills、插件、hooks、MCP、自定义命令和 agent 等，保留认证、模型和原生工具。程序内嵌实现也确认 safe-mode 的自动记忆判定为 off。
- `--restricted` 忽略 user/project/local settings，将文件工具限制在 cwd 和显式 add-dir；默认移除 Bash，只有显式列入 tools 才恢复。
- 本机支持 `--strict-mcp-config`、`--disable-slash-commands`、`--tools`、`--allowedTools`、`--permission-mode dontAsk`、`--session-id`。
- 本机设置 schema 的 `autoMemoryEnabled:false` 表示不读写自动记忆。`claudeMdExcludes` 不能排除 managed/policy 文档。
- `--bare` 也跳过记忆与 CLAUDE.md，但改变认证路径；调查未核实其认证适用性，因此不作首选。

仓库普通启动的自动注入入口：根 CLAUDE.md 引入 AGENTS.md，后者要求接手读 STATE，目前缺 D12 的局部无答案例外。施工包已授权在长期说明中落实必要例外，不应以此漏掉其余红线。

## 供后续评估的启动形态

使用全新的独立交互 session、全新 UUID 和无答案 cwd；不 resume/continue/fork/worktree，不用 `-p`。沿用本机合法 GLM 认证/provider 环境，记录来源但绝不记录密钥或认证环境值。

参数形态为：

```text
claude.exe --safe-mode --restricted --strict-mcp-config --disable-slash-commands
  --tools Read,Glob,Grep,Bash --permission-mode dontAsk
  --allowedTools <逐项限定的读工具及最终正式入口命令>
  --session-id <全新UUID> --name D12-independent-generation -- <无答案启动说明>
```

这是待最终入口完工后再绑定的参数形态，不是可直接照抄运行的完成方案。safe-mode 关闭 slash skill，所以应将已冻结的业务 SKILL/runbook 作为明确可读输入，再由新 session 调用正式 Python 入口。不要开放整个仓库给文件工具，也不要使用 `--add-dir` 根目录来绕过白名单。argv 的路径/通配符/引号必须按实际 CLI 验证，不能从本文假定授权已通过。

## 启动前应冻结的输入白名单

1. 无答案 D12-INPUT：原始用户意图、指定模板完整单号、同一登记任务身份、必要测试用途和受限历史占位 fill_only 边界；不携带匹配结论或预期金额。
2. 原始材料和原始公里表；保留原字节，不提供旧解析事实、计划或映射答案。
3. 已完工冻结的入口 SKILL、自驾 runbook、规则/场景配置、逐文件明确的必要源码和 schema。不能跟随其中指向 STATE、合同案例、旧 runs、测试夹具的非白名单链接。
4. 无答案长期红线说明：身份现场核验、单 profile、锁、registry/未保存页、保存授权与恢复边界、凭证保护。不得原样灌入当前 AGENTS/STATE。
5. 必要环境及认证能力引用。凭证和本机会话记录不复制，由正式入口在原保护位置进行动态检查。

每件输入记录 SHA-256；启动记录 cwd、argv、程序版本/哈希和新 session UUID。保留原始工具轨迹，抽取 Read/Grep/Glob 路径、Bash 命令及正式入口产物。阶段一事实/计算/计划先冻结哈希，阶段二核查者才能读答案证据。非白名单读取或恢复旧 session 会使该次独立生成无效，不能事后归为环境输入。

## 必须在开跑前闭合的限制

- 恢复 Bash 后，restricted 的文件工具限制不能证明 Python 子进程不会读取仓库其他文件。只允许最终正式入口及明确阶段命令，核对依赖和实际程序来源/读取记录；CLI 工具轨迹不能替代程序内部读取审计。
- 调查时 full-chain 仍仅到 validate-only，自驾模块只是库。必须等正式整链完工后再绑定可执行命令；库函数或临时 run 驱动不能冒充最终正式入口。
- 本方案尚无真实冷启动执行证据；A 应按最终产物与冻结合同自行核验，保留实现、离线、真实填写及真实保存的层次区别。
