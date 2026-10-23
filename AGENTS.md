# AGENTS.md — coding agent 接手须知

BPM 报销单自动填报：Playwright 探针操作企业微信 OA（bpm.qiaodan.com，Angular PrimeNG 表单）。人类视角总览见 `README.md`；本文件是给 agent 的操作手册。

## 红线（违反即事故）

1. **只填不存**：保存/发送/流转/提交/上传/暂存/贴票/审批 一律禁点（`no_save_guard` 在探针源码守卫，勿绕过）。保存授权未正式澄清，由用户执行或用户明确授权后才做（点前终局截图+回读复核）。
2. **`automation/.pw-profile/` 含活体登录 token**：绝不复制进 git/日志/报告（已 gitignore）。
3. **结论以工件为准**：`automation/runs/<run>/` 的 `events.jsonl`（追加式）/ `evidence/` / `stage1_result.json` 是唯一权威，聊天叙事为辅。
4. `legacy-ia2/` 只读存档，勿追加。

## 启动一轮填写（正常路径 ~5 分钟，勿考古）

```bash
python -X utf8 fill_once.py        # 探针参数原样透传，如 --keep-open-minutes 90
```

repo 级 skill：`bpm-fill-run`（`.claude/skills/`）。改过 `stage1_browser_probe.py` → **必须**先 `python -X utf8 stage1_probe_selftest.py` 全绿再跑。探针 238s 确定性耗时——防御性等待（600ms 轮询、Tab blur+3×重读）是 23 个 attempt 换来的稳定性，**勿优化**。

## 环境坑（Windows）

- cwd 必须仓库根（探针相对路径依赖；`fill_once.py` 已自动 chdir）
- Clash 系统代理劫持内网域名：Chromium 必须 `--no-proxy-server`（探针已内置）
- 判活用 ctypes OpenProcess；**禁** `os.kill(pid,0)`（Windows 上等价 CTRL_C_EVENT，会杀停靠浏览器）
- Python 一律 `-X utf8`（默认 GBK 乱码）
- 登录态 `automation/.pw-profile/session_state.json`：10h TTL 滚动续期（2026-10-23 由 4h 调整）；过期回落企微扫码需人工（~21s）

## 目录速查

| 路径 | 用途 |
|---|---|
| `stage1_browser_probe.py` | 主探针：登录→测绘→fill→回读→截图 |
| `fill_once.py` | 一键填写轮入口（固化 run id / fill-plan / keep-open） |
| `automation/runs/<run>/attempt_NNN/` | 每轮证据工件；`events.jsonl` 跨 attempt 追加 |
| `automation/form-schema.json` | 表单结构字典 v0.2（PrimeNG prop-* 枚举） |
| `templates/` | 新报销类型模板原图 + OCR 切块（扩展入口） |
| `patches/` | Windows-MCP 本地改造补丁（嵌套 repo 本体已 gitignore） |
| `docs/` | 路线决策 / 探索复盘 / session 报告 |

## 当前状态（2026-10-22）

- attempt_024：**29/32 零 mismatch**（差旅费↔差旅词表已修）；待用户眼审关联公出单换选 `12026075605`
- 结构性留空非失败：`项目说明`/`行程说明`（表单无此字段）、`报销类别 submitType`（模板未涉及）
- 遗留决策：保存授权口径未澄清；git 首次提交未做（.gitignore 已备好）
