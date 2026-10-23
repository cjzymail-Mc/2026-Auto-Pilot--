---
name: bpm-fill-run
description: 在本 repo（2026-Auto-Pilot 企业微信）启动一轮 BPM 报销单自动填写（只填不存）。当用户要求填报销单/复跑填写轮/自动填上时触发；先读 repo README 再动手，不重新考古推导命令。
---

# bpm-fill-run（BPM 报销单填写轮 · 薄入口）

> repo 级 skill（随本仓库 git 走，2026-10-22 由 user-scope 迁入）。

## 唯一启动命令

```bash
cd "D:/Technique Support/Claude Code Learning/2026-Auto-Pilot 企业微信"
python -X utf8 fill_once.py            # 额外参数原样透传，如 --keep-open-minutes 90
```

`fill_once.py` 已固化：run id（attempt 自动递增）、expect-name、fill-plan 路径、keep-open 45min、登录态 TTL 预检（>9h 提示需人工扫码；TTL=10h，2026-10-23 起）。

## 执行节奏（目标：分钟级，不考古）

1. **不读散落工件重建上下文**——repo README「运行须知」第 0 条是唯一权威入口；本 skill 与其保持一致，冲突以 README 为准。
2. 启动前仅两个检查：①改过 `stage1_browser_probe.py` → 必须先跑 `python -X utf8 stage1_probe_selftest.py`（全绿才跑）；②`fill_once.py` 的登录态预检输出。
3. 探针运行约 **238s 确定性耗时**（防御性等待是稳定性成本，勿优化）；后台跑 + 轮询 `events.jsonl` 尾部，`FILL_DONE` 即填写完成、浏览器驻留待审。
4. 填完立即向用户报审：读 `stage1_result.json` 的 `fill_summary` + `evidence/fill_readback.json` 逐项表，**显式标出授权替代项**（如关联单号换选），附 attempt 目录截图路径。

## 红线（违反即事故）

- **只填不存**：保存/发送/流转/提交/上传/暂存/贴票一律禁点（`no_save_guard` 在源码守卫，勿绕过）。保存授权口径未正式澄清前，保存动作由用户执行或用户明确授权后才做（点前终局截图+回读复核）。
- `automation/.pw-profile/` 含活体登录 token：绝不复制进 git/日志/报告，不提交。
- 结论以 `automation/runs/<run>/` 工件为准（events.jsonl / fill_readback.json），聊天叙事为辅。

## 已知坑速查（详见 README 运行须知）

cwd 必须仓库根｜Clash 代理须 `--no-proxy-server`（已内置）｜判活用 ctypes OpenProcess 非 `os.kill`｜表单是 PrimeNG：dblclick 进编辑态、弹表选行守三硬规则。
