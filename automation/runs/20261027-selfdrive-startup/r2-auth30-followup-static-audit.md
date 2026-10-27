# R2 会话修复追加窄审

Codex 协调工程审查，非新增人类授权。来源 `/root/login_migration_map`；只读，未运行测试/构建、未修改文件、未读真实认证/会话/registry。仅对下列所读字节负责，读取前后哈希一致。

第一项已闭合：`bpm_session.persist_state:175` 保留旧无 meta 的原 mtime，probe `_save_session_state:3101` 确实调用它，不再由普通写回滚动24h，也未补造扫码时间。

第二项仍有高置信组合链缺口：

1. `previous[META_KEY]` 存在，但 schema=2.0、缺标识或显式 null，`state_usable` 原先正确拒绝。
2. `attach_metadata:135–140` 返回 None，新 state 不再包含 META_KEY。
3. `persist_state:184–187` 覆盖原文件；坏 dict 情况刷新 mtime，null 情况虽保留 mtime，仍已把“坏元数据”变成“无元数据”。
4. `write_record:194–196` 因无 meta 返回 None；下次 `state_usable:101` 走 legacy 回退，在24h内由原拒绝变放行。

B 可使用现有无认证值合成 helper，在隔离临时目录验证：

```python
previous = legacy_state(T, days=30)
previous[META_KEY]['schema_version'] = '2.0'
# 将 previous 写到临时 p
assert state_usable(p, now=T + 3600) is False
current = state(T + 3600)  # 同 subject，无 META_KEY
assert attach_metadata(current, previous, now=T + 3600) is None
persist_state(p, current, previous)
# 所读代码会删掉坏 meta 并使下式为 True
assert state_usable(p, now=p.stat().st_mtime + 1) is True
```

现有新增测试只分别验证函数，没有覆盖此组合链。非扫码遇到“存在但无效”的旧 meta，必须在覆盖前拒绝，不能降级为 legacy。真实新扫码成功后的合规重建按既有授权逻辑处理，不能为堵此路径把合法新扫码也一概阻断。

```text
bpm_session.py 607ba660ff84f4deacbf4d2469b8efcab0b865f4f2a624b27458361a9b3c0fb1
stage1_browser_probe.py 118035948db6fde5367ba3110010113e07697bbfdfb8fef7ee510f379245b049
tests/test_bpm_session.py f3230c31ed405936170314406f72077127dd1d5cee24a3d05e9e5b2aeffd13e2
stage1_probe_selftest.py 247c7a6b7a5d939b6852ac2a83b65f82bbafe4e08302bb9d840873d01696560e
```

若验证成立，应补真实组合写回负例及原字节不变断言，再依最终新哈希自检/构建/终审；保留旧构建和审查尝试，不修改 task/source/criteria/失败历史。
