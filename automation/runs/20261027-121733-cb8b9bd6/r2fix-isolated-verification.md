# Codex 窄审反例——隔离验证记录（修复前）

run: 20261027-121733-cb8b9bd6 ｜ 2026-10-27 ｜ 委派来源：Codex 主协调窗口（工程审查证据，非新增授权）
审查文件：[r2-auth30-static-audit.md](../20261027-selfdrive-startup/r2-auth30-static-audit.md)（所读哈希与本轮产物一致）

## 隔离验证（临时目录、无任何真实凭证/认证值，占位 cookie/JWT）

| # | 反例 | 复现方式 | 结果 |
|---|---|---|---|
| 1 | 无扫码 meta 旧状态滚动续期 | mtime=T 无 META_KEY 文件：T+23h `state_usable` True → 按 `_save_session_state` 现行为（attach 返回 None 仍 os.replace）写回，mtime=T+23h → T+46h `state_usable` 仍 **True** | **成立** |
| 2a | 读取/写回拒绝不一致（缺标识） | meta 含 schema/start/days=60 但缺 profile_id/session_generation：`state_usable` **True**，`write_record` 拒 "Invalid local profile identifier" | **成立** |
| 2b | 坏 meta 被 attach 原样复制 | 同 subject 占位 JWT + 旧 meta schema=2.0/days=999：`attach_metadata` 返回 `{"schema_version":"2.0", …, "local_reuse_days":999}` 原样复制并加 last_authenticated_epoch | **成立** |
| 2c | 显式 META_KEY:null 误走 legacy | `{"_bpm_login_metadata": null}` + mtime 24h 内：`state_usable` True（损坏被当合法无 meta 旧状态） | **成立** |

## 修复方向（合同 D02 范围内）

1. **锚点不滑动**：`bpm_session.persist_state(path, state, previous)`——普通探查写回时，previous 无可信扫码 meta（真旧文件）且新 state 仍未获 meta 的，替换后恢复原 mtime；探针 `_save_session_state` 改用该函数。不补扫码、不给新窗口。
2. **统一拒绝口径**：共享 `_meta_valid`（schema=1.0、start 有限数值、days∈[1,60]、profile_id/session_generation 各 32-hex）；`state_usable`/`attach_metadata` 非 scan 复制/`write_record` 三处同一拒绝；显式 `META_KEY:null` 判损坏拒绝（仅键缺席走 legacy mtime+24h）。
3. 补写回链负例测试；改探针后先 `stage1_probe_selftest.py` 全绿，再全量回归与离线构建（最终新哈希），修复前 385 全绿不作为修复后证明；最终 ENHANCED_FINAL 以修复后哈希重审。
