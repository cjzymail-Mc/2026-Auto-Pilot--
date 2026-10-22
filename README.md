# 2026-Auto-Pilot 企业微信

Agent 自动操作企业微信 OA：当前主线是 **BPM 报销单整单自动填写**，未来扩展到更多报销类型与单据自动填报。

- 上游战果（2026-10-22，attempt_023）：模板 32 字段 **28 项回读一致**（87.5%），唯一 mismatch 是「差旅↔差旅费」词表尾缀，一行 `_norm` 修复量级
- 详细战报：`docs/session报告/2026-10-22-session报告任务总结.md`；逐轮事件流水在 `automation/runs/<run>/events.jsonl`，每轮结论以其为准

## 目录

```
stage1_browser_probe.py   主探针：登录→测绘→fill→回读→截图（须在仓库根目录运行）
stage1_probe_selftest.py  离线自测（改探针后先跑这个）
automation/
  runs/                   23 个 attempt 的证据工件（events.jsonl/stage1_result.json/截图/回读）
  .pw-profile/            浏览器 profile + session_state.json（登录态，TTL 4h 滚动续期）
  form-schema.json        表单结构字典（v0.2，PrimeNG prop-* 枚举）
  fixtures/               自测夹具
templates/                报销单模板原图 + OCR 切块（新报销类型的入口材料）
docs/
  路线与评估/             技术路线决策（浏览器路线 vs IA2、Windows-MCP 实测）
  探索与复盘/             页面探索报告、效率复盘
  session报告/            会话分析报告 + session-digest 原始分片
legacy-ia2/               IA2 无障碍时代的 650 个探索产物（只读存档，勿再追加）
Windows-MCP/              外部工具 repo（.git 保留，gitignore 不入库；本地 CEF/IA2 改造以 patches/ 补丁随本 repo 固化）
patches/                  Windows-MCP 本地改造补丁（基于上游 5b24a8a；恢复=clone 上游+git apply）
```

## 运行须知（坑都在这）

0. **一键启动填写轮**：`python fill_once.py`（只填不存 + 浏览器驻留 45 分钟待审；探针额外参数原样透传，如 `--keep-open-minutes 90`）。预期：登录态直注免扫码、填写 ~4 分钟（238s 确定性）。改过探针必须先跑 `python -X utf8 stage1_probe_selftest.py` 再来。
1. **cwd 必须是仓库根**：探针内用 `automation\runs\...` 相对路径，挪动 `stage1_browser_probe.py` 或 `automation/` 的相对位置会破（`fill_once.py` 已内置自动 chdir）。
2. **代理**：WinINET 系统代理=Clash 会劫持内网域名 bpm.qiaodan.com（192.168.34.10），Chromium 启动必须带 `--no-proxy-server`（探针已内置）。
3. **登录**：唯一通道是企微 CorpApp QR iframe（appid=wx7792ec86613522f1）。登录态存 sessionStorage（qd_access_token 等 3 键）随 cookies 落盘，4h TTL 滚动续期；过期或注入被拒则回落扫码（约 21s）。
4. **只填不存红线**：`no_save_guard`（保存/发送/流转/提交/上传/暂存/贴票/审批 一律禁点）。⚠️ 保存授权用户已口头松口（2026-10-22 10:48）但从未正式落到工作指令，**未澄清前维持只填不存**；若放开，先终局截图+回读核对再点。
5. **Windows 凶器**：探针判活勿用 `os.kill(pid, 0)`——Windows 上等价 CTRL_C_EVENT 会杀掉停靠浏览器，用 ctypes OpenProcess。
6. **表单是 Angular PrimeNG**（非 SpreadJS）：字段包装在 `div.row.dfc-container.prop-*`，标签在旁 `label.display-label`；dblclick 进 ui-editing-cell 才挂控件；弹表选行守三硬规则（表头永不选 / prescan 优先 / 选中态核验+确认留痕）。

## 下一步

见任务总结报告第四节：差旅费词表归一 → 保存授权澄清 → 新报销类型模板扩展（`templates/` + fill_plan 流程）。
