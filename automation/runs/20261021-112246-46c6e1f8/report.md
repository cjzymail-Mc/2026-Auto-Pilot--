# Run 20261021-112246-46c6e1f8 核验报告（Stage0 + Stage1）

合同：ctr-a8dea6f2（minimal）｜拓扑 T3/B/AUTO｜assurance=ENHANCED
权威任务规格：`10-21 优化-提升效率/feature01独立评估与解决方案-astra.md`（§3/§5/§10/§12）

## Stage 0：只读恢复草稿与环境核查（完成）

### 环境核查记录（脱敏）
| 项 | 值 |
|---|---|
| Claude Code | 2.1.177；CLAUDE_CONFIG_DIR=C:/Users/xy24/.claude-glm；模型 glm-5.3 |
| 生效 env | MAX_CONTEXT_TOKENS=1000000 / AUTO_COMPACT_WINDOW=400000 / AUTOCOMPACT_PCT=60（与配置包声明一致；astra §2.3 名义压缩 240K vs 生产日志实测 107K~114K 差异仍在，本轮只记录不修改） |
| 企微 | WXWork.exe PID 13276 运行中 |
| Windows-MCP | repo 在 feature01/Windows-MCP，server 4.1.0 经 `uv run windows-mcp serve` 正常握手（本轮两次 chain 实测） |
| Playwright | 1.58.0 + chromium-1208（本机已装，无需新安装） |
| OA | https://bpm.qiaodan.com/oa/reimburse（IA2 document 节点一手证据） |

### 草稿现状（证据：evidence/s0_ia2_snapshot.txt、s0_nav_draftlist.txt）
1. 企微 OA webview 当前为**空白「新增报销」**表单，URL 时间戳 t=1792542932968（2026-10-21 11:15 新开）。
2. 报销单模块列表（默认筛选=当前用户制单）可见 3 张历史单据：2026-09-30 / 2025-12-15 / 2025-08-26，状态均为「结束」；**无 10-20/21 草稿或单据行**（未逐状态页签翻查，按默认列表口径）。
3. 结论：**昨日事故表单从未保存为草稿**；11:15 页面重载后未保存内容已清空。复盘记载的事故（银行账号曾被写成日期、转账金额曾被写成行程说明）发生在未保存表单内，**无持久化数据污染**。

### 差异清单
字段级「当前值 vs 期望值」差异清单**不适用**（目标草稿不存在于系统中）。已知异常的全部损失=未保存表单内容丢失，已由页面重载终结；无需回滚修复（符合 astra §5「未知原值不做猜测回滚」）。

### 允许动作现状
- 本轮合同范围：只读。OA 写入零授权（astra 明文）。下一阶段如需写入验证，须用户显式指定授权草稿与字段。

### 附带结构发现（供 form-schema 初稿）
- 表单区块：关联单据明细 / 报销明细（报销项目·摘要·科目余额·报销金额）/ 费用说明（费用类型·开始日期·次数天·金额·项目说明）/ 银行信息（收款人·账号·开户行·联行号·转账金额·备注）。
- 表单按钮：保存、删除、「复制金额到本次报销金额」、自动换行。
- 列表页列：单据编号·状态·制单人·部门·公司·年份·支付方式·费用类型·金额·制单日期·终审人。
- IA2 能力实证：表单页字段 value 节点不物化（r108–r118 共 11 份历史快照 + 今晨快照均为 0），列表页筛选编辑器可带 value → IA2 路线对表单「读值」必须先聚焦单元格（操控级动作），对「填前核对/填后回读」均不满足只读约束。

## Stage 1：浏览器路线可行性检查（30 分钟技术预算）

### 执行与预算（D4 证据：events.jsonl 时间戳）
| 尝试 | 时间 | 技术用时 | 结果 |
|---|---|---|---|
| #1 | 11:48:04–11:48:50 | 39.5s | goto `net::ERR_CONNECTION_CLOSED` → 失败陪审（failure_key=stage1-entry-nav-err-connection-closed，count=1，HISTORY mc-expert 复核） |
| #2 | 11:57:26–12:05:40 | 5.4s 技术段 + 481.9s 登录等待（单独计时） | 导航成功 → 停在登录关口 |

**技术预算合计 44.9s ≪ 1800s（budget_respected=true）；登录等待按 astra §3 单独记录未计入。**

### 环境根因（已坐实，一手证据）
- WinINET 系统代理开启且指向 Clash：`ProxyEnable=0x1 / ProxyServer=127.0.0.1:7897`；OA 域名解析内网 192.168.34.10，经代理即断（curl 实测：代理超时 / 直连 200）。
- **结论：后续所有浏览器自动化访问 OA 必须绕代理（`--no-proxy-server` 或显式 `--proxy-server + bypass`），已固化为执行器约束。**

### 六检查项结果（astra §3 表）
| 检查项 | 结果 | 证据指针 |
|---|---|---|
| 1 浏览器入口与登录 | **部分通过**：独立浏览器可达 OA（绕代理后 200→SSO 链→登录页正常渲染，nav 1.6s）；登录未建立（480s 无人工扫码） | stage1_result.json.entry（redirect_chain 3 跳全 200）；evidence/stage1_1_entry.png/.html；stage1_2_login_gate.png；events.jsonl stage1_login_gate_stop |
| 2 草稿定位 | **受登录阻塞**（未进入 OA 内部） | 同上 |
| 3 页面结构 | **受登录阻塞**（未进入；Stage0 IA2 已有区块级结构兜底，见 form-schema.json v0.1） | 同上 |
| 4 普通字段写入 | **待验**（astra §3：第一轮只读；无授权写入草稿 → 路线状态=只读可用、写入待验） | 合同 D5；astra §3 line124 |
| 5 困难字段（选择器/表格单元格） | 同上待验 | 同上 |
| 6 恢复能力 | **受登录阻塞**（未进入） | 同上 |

### 登录机制查明（本轮新增关键事实）
- OA 登录 = **企业微信 CorpApp SSO**：`/account/login` 页唯一登录元素为 iframe（`login.work.weixin.qq.com/wwlogin/sso/login?login_type=CorpApp&appid=wx7792ec86613522f1&agentid=1000002&redirect_uri=https://bpm.qiaodan.com`，480×416，wwLogin-1.0.0.js）。**无密码框、无表单** → 独立浏览器侧登录=手机企微扫码，唯一通道。
- 本机企微客户端桥接（`localhost.work.weixin.qq.com:50010/checkLoginState`）在独立 Chromium 下 `ERR_CONNECTION_RESET` → 客户端自动 SSO 未发生（未重试，按登录关口规则停）。
- 登录前 cookie 仅 `ww_lang`；凭证零复制（cookie 只记名不记值，合同红线遵守）。

### 路线结论（§3 三分类，落第二档）
**受登录或系统能力阻塞（登录维度）** —— 但技术侧两大不确定已消除：
1. 网络层：独立浏览器**可以**到达 OA（须绕 Clash 代理，方法已固化）；
2. 登录层：机制完全查明（企微 QR SSO），剩余动作=**人工扫一次码**即可继续完成检查项 2/3/6。

**下一轮建议**（不在本轮范围）：用户在场时扫码一次 → 复跑本探针（登录后阶段自动续跑 2/3/6 项）→ 按结果把 form-schema 的 PENDING(DOM) 定位方法回填，并对授权测试草稿做检查项 4/5 写入验证。浏览器 profile 已持久化于 `automation/.pw-profile`，登录态建立后应验证跨重启有效性（astra §3）。
