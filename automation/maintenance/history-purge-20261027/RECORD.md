# 历史净化记录 — 2026-10-27

## 决定与授权

用户裁定（2026-10-27，本 session）：仓库历史中含真实银行卡号的文件**从 Git 全部历史移除**（非脱敏），本地保留原件；依据是价值评估——142 个含真实卡号文件均无运行/开发引用（legacy-ia2 在 `bpm/` 代码中仅为拒绝读取的黑名单；travel_census.json 只被工具写入；cropR12.txt 无引用；20261021 run 教训已固化进 AGENTS/tests）。

## 执行

1. 镜像备份：`../2026-Auto-Pilot-企业微信-mirror-backup-20261027.git`（含净化前全部历史，本地保存）
2. 原件暂存/回填：`../2026-Auto-Pilot-企业微信-purged-local-20261027/`（516 文件，净化后已复制回原路径，.gitignore 逐文件排除）
3. `git filter-repo --invert-paths --paths-from-file purge-list.txt --force`：移除 516 路径（142 个含真实卡号文本 + 374 个同证据目录截图，截图按"同组随组移除"过包含规则处理）
4. `git filter-repo --replace-text`：对残留的 3 个代码历史 blob（probe_selftest 历史版本的 mask 测试输入）做号码等价替换
5. 验证：`verify_purge.py` 扫描全部 2465 个 blob，真实卡号 **0 残留**

## 影响与后续约束

- **全部 commit hash 已变化**；旧 hash 映射见 `commit-map.txt`。外部对旧 hash 的引用（记忆、归档叙述）按 map 换算或视为历史注记。
- 新克隆不含 516 个净化文件；`legacy-ia2/`、`docs/session报告/session-digest/` 部分文件为"本地存档、缺件为预期状态"（AGENTS 红线 5 已同步措辞）。
- **远端处理**：净化前历史已推送过的远端仓库必须删除重建（服务端不可达对象可残留），不得以 force-push 覆盖了事；其他克隆全部作废。
- 净化前 11 个本轮 commit 与净化一起获得新 hash；`runbook`/STATE 引用的路径不受影响（路径未变）。

## 判定口径

- 真实卡号清单：14 个具体号码存仓库外 `../2026-Auto-Pilot-企业微信-purged-local-20261027/real-card-patterns-20261027.txt`（verify_purge.py 以 --patterns 读取；卡号本身不落 Git），与 `real-card-exclusion-20261027.txt`（当日新增文件排除，仅路径）同一口径。
- 截图过包含：与含卡号文本证据同目录的图片全部移除，不做逐张视觉判定（方向安全，原件本地保留）。
