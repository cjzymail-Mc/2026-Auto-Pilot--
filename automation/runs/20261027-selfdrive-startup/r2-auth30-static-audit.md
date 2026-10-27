# R2 会话迁移窄范围静态审查

来源：Codex 主协调窗口委派 `/root/login_migration_map` 对本轮实现作只读审查。这是工程审查证据，不是新增人类授权，也不代替原生 A 验收或规定终审。未运行测试/构建，未读取真实凭证、本机会话或 registry。所读源码前后哈希一致。

## 发现一：旧无扫码元数据的普通探查写回会滑动 24h 边界

- `bpm_session.py:80–82 state_usable` 通过旧文件 mtime 判断 24h。
- `attach_metadata:119–121` 在没有可信扫码记录时返回 None。
- `stage1_browser_probe.py:3095–3099 _save_session_state` 忽略该返回值，仍替换旧文件，刷新 mtime。
- 最小静态反例：原 mtime=T；T+23h 的普通探查通过并写回；T+46h 又因为新 mtime 在 24h 内而可复用。可反复滚动，超过最初保守边界。
- 现有 legacy 测试只检查读取与 attach；T10 mock 了实际持久化，没有覆盖该写回链。B 应用无认证值的隔离临时文件验证，不能使用真实 profile。修复必须保留无可信扫码时间的事实，不能补写今天扫码或给予新的 30 天窗口。

## 发现二：坏元数据的读取/非扫码写回拒绝不一致

- `state_usable:83–98` 校验 schema/start/days，却未校验 profile_id/session_generation。仅 schema=1.0、合法 start 和 days=60 的不完整记录可能返回 True，直到 `write_record:161–170` 才拒绝缺标识。
- `attach_metadata:117–118` 对同 subject 的任意非空旧 dict 原样复制；write_record 不完整复核 schema/start/days，可能将坏 schema 输出为 schema=1.0、authenticated 的展示记录。
- 显式 META_KEY:null 会误走无元数据 legacy 回退。应区分真正缺少元数据的合法旧状态与元数据存在但损坏的状态，在读取、attach 及非扫码写回前保持一致拒绝。

## 确认正确的部分

可信元数据的新默认 30 天、旧合法 60 天按 min 收紧、较短 7 天窗口、更早 refresh 到期、恰界过期、同 subject 普通写回保持扫码起点/profile/generation，均在所读源码中正确。保留旧 local_reuse_days=60 的历史值而另算实际边界本身不是缺陷。

## 所读字节 SHA-256

```text
bpm_session.py 12a8e5076eaec0d5f0aba40c6c7c03c4ef33629307f5d7fb72946b8aed25b64b
stage1_browser_probe.py 2edd7dbaf6fde84cdb79bc4c88acac051ed80816e95a984b1a228ee7aac922ce
tests/test_bpm_session.py 2b250ce1e2b9c95aa978577f161e5bfad426d61e213934e1d7efc0c1e298a9b0
stage1_probe_selftest.py 247c7a6b7a5d939b6852ac2a83b65f82bbafe4e08302bb9d840873d01696560e
```

这两个问题直接位于已授权 R2 的缺扫码时间/mtime/坏 schema/普通探查不续期范围。若隔离验证成立，应在本轮范围修复并补足真实写回链负例；改探针须先 selftest，全量构建及终审依据最终新哈希，不沿用修复前 385 测试作为修复后证明。不要改 task/source/criteria 或失败历史来处理发现。
