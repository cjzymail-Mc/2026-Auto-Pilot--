# AGENTS.md — coding agent 接手须知

BPM 报销自动填报：Playwright 操作企业微信 OA（bpm.qiaodan.com，Angular PrimeNG）。总览见 `README.md`；日常业务入口 `.claude/skills/bpm-fill-run/SKILL.md`。

## 红线

1. 默认只填不存；普通 `_click_guard` 继续禁止保存/发送/流转/提交/上传/暂存/贴票/审批。仅用户对本具体任务明确要求保存、计划有同 task_id 的 `save_draft` 授权时，专用 `SaveController` 可在完整回读、终局截图及点击前复核后执行一次精确“保存”。禁止“保存并提交”、未知弹框自动确认、直接写接口及放宽通用守卫。施工授权不等于对虚构实单的保存授权。
2. `automation/.pw-profile/` 含活体登录 token，绝不复制进 git、日志、报告、材料清单或测试工件。
3. 结果以 `automation/runs/<run>/events.jsonl`（追加式）、`attempt_NNN/stage1_result.json` 及该 attempt 证据为准；准备结果在 run 根。保存成功必须证明唯一新单号/UUID、未提交状态及重开持久化回读。
4. `automation/task-registry/` 保存跨 run 任务意图。已有 `SAVE_INTENT`、`SAVE_UNCERTAIN` 或保存成功记录只读核实，禁止再次保存/另建。未保存页恢复当前仅盘点并返回 `NEEDS_INPUT`；不得删 registry、换 task_id 或强关旧页来规避。单 profile 只允许一个执行者。
5. `legacy-ia2/` 只读存档，勿追加。

## 正常入口

```powershell
python -X utf8 fill_once.py --task "任务.json" --expect-name "操作人"
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --validate-only
python -X utf8 fill_once.py --fill-plan "填报计划.json" --expect-name "操作人" --keep-open-minutes 45
python -X utf8 fill_once.py --fill-plan "原填报计划.json" --expect-name "操作人" --resume-run "原run标识"
```

无参数不填写，不默认使用历史人员、旧 run 或旧计划。`--task` 只做材料准备，返回 `NEEDS_INPUT`；必须核对本次材料再生成 v1.0 可执行计划。新任务新 run，同一任务重试需计划/操作人/配置哈希完全相同。旧格式仅显式传具体 `--fill-plan` 路径及 `--legacy-regression` 做只填不存回归。

先按完整单号定向读模板；`bpm_template.py` 支持 `--census` 缓存读取，或 `--live --expect-name "操作人" --template-number "完整单号" --output "automation/runs/独立准备run/template_snapshot.json"`。live 使用同 profile 锁及临时 context，不操作恢复的原页，详见 skill。不要为找单号普查全部历史。历史仅复用有依据的稳定身份、预算和收款资料，本次日期/费用/发票/金额/关联编号不得从旧单推导。CSV/XLSX 与复核 JSON 保留前导零和原件哈希；关键图片/PDF 值不清晰则集中报告缺口。

## 校验与支持边界

- 当前类型 `travel`；四主表是 relations/details/costs/banks 行数组，不再使用 row1/row2 固定结构。选择器按精确名称和编号唯一命中，不默认第一项、不替换关联单。
- 每个执行值有 path/locator/sha256 等来源；模板、材料、计划及配置哈希参与执行绑定。金额用 Decimal；totalCost、报销明细合计和银行合计闭合，费用说明金额语义明确，空表必须显式不适用并有理由。未建模借款抵扣、附件、贴票、产品表和新类型先拒绝。
- PDF/图片原件需 image_documents 明确分类，复核 JSON 原件与提取哈希均入同一 manifest。发票身份去重、票面金额与主要费用行分配闭合，免票行有 no_invoice_rows 理由和来源；corroborates 校验不同来源一致。Excel/票面金额冲突阻断，部分票面报销与数量乘单价票据分配不支持。
- 终局独立读 DOM，核对全部计划值、身份、行数、额外/重复/缺失数据及金额；不以写入函数返回或历史“29/32”当验收。
- 改过 `stage1_browser_probe.py` 必须先 `python -X utf8 stage1_probe_selftest.py` 全绿，再实单运行；相关改动执行 `python -X utf8 -m unittest discover -s tests`。保留 600ms 轮询、Tab 失焦和重复回读等已验证稳定机制，不优化防御等待、不承诺固定耗时。
- 统一离线验收可跑 `python -X utf8 verify_bpm_build.py`，包括 selftest、全部单元/本地 DOM 测试及合成截图和哈希工件，产物在 `automation/offline-verify/<run>/`；不连接生产 OA。
- 区分“代码已实现”“离线已验证”“真实填写已验证”“真实保存已验证”。缺真实单号和本次材料时推进代码/测试，明确实单缺口，不新建虚构报销。

## Windows / 登录与网络

- cwd 必须仓库根；`fill_once.py` 自动 chdir。
- **不走 VPN/Clash**，Chromium 必须 `--no-proxy-server`（探针已内置），直连 OA 内网。
- 登录态 `automation/.pw-profile/session_state.json`：24h TTL 滚动续期；OA 服务端提前失效仍需人工扫码，不保证服务端 24h 会话。
- Python 一律 `-X utf8`。Windows 判活用 ctypes OpenProcess；禁 `os.kill(pid,0)`，会杀停靠浏览器。

## 目录速查

| 路径 | 用途 |
|---|---|
| fill_once.py / bpm_plan.py / bpm_materials.py | 任务与计划入口、来源/金额验证、材料清单及解析 |
| bpm_template.py | 精确模板读取；缓存 / 已认证 live CLI 与库函数 |
| bpm_ui.py / bpm_verify.py / bpm_save.py | 多行执行、完整独立快照、受控保存 |
| stage1_browser_probe.py | 浏览器/登录/profile 锁/普通守卫及主执行 |
| automation/task.schema.json / fill-plan.schema.json | v1.0 输入与执行契约 |
| automation/document-types/travel.json | 差旅中文字段/编辑类型、支持枚举及额外表投影 |
| automation/runs/<run>/ / automation/task-registry/ | 逐轮证据 / 跨 run 意图与保存核实 |
| templates/ / docs/ / patches/ | 参考原图 / 路线和历史报告 / Windows-MCP 补丁 |

历史 attempt_026 是旧填写证据，不是当前自动保存验收；新能力以实际构建报告和当次 run 工件为准。当前施工未提供本次真实材料与模板，实单验证仍需该输入。
