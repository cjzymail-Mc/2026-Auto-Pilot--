# 历史一次性辅助脚本

这里保留原根目录的一次性脚本，便于追溯；文件字节保持原样，不作为日常入口，也不参与生产构建执行。

| 文件 | 原用途与边界 |
|---|---|
| `_gen_manifest.py` | 为旧 run 生成 manifest；包含旧机器绝对路径，顶层代码会写文件 |
| `_schema_v02.py` | 根据旧 attempt 证据修改 form-schema；顶层代码会覆盖配置 |
| `_chk_orphan2.ps1` | 旧 profile 浏览器进程的只读排查脚本 |

不要通过 import、批量运行或测试发现执行这些历史脚本。现行验证入口为仓库根 `verify_bpm_build.py`，维护方式见 [仓库目录说明](../../docs/repository-layout.md)。
