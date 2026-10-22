# P1 完成记录 — 探针八项缺口修复 + 离线失败场景验证（run 20261021-131724-1c1aadbd）

产物：`stage1_browser_probe.py`（就地重写为 v2）+ `stage1_probe_selftest.py`（离线自测）。
自测输出原件：`evidence/p1_selftest_output.txt`（10 组用例全 PASS，EXIT=0）。

## 八项缺口 → 修复对照（temp.md §3 表）

| # | 缺口 | v2 处置（源码锚点） |
|---|---|---|
| 1 | run 目录写死旧 run | `--run` 参数（默认自动生成）；每次尝试独立 `attempt_NNN/`；结果原子写 tmp+`os.replace`；旧 run/attempt 文件零覆盖（自测 T4 实证） |
| 2 | phase() 吞错继续跑 | `PhaseRunner` 状态机：依赖非 PASS → 后续 SKIPPED；整体成功=`_overall()` 只认 c1/c2/c3/c6 业务断言（自测"阶段状态机/整体成功口径"组） |
| 3 | classify 弱判（URL+oaNav=3→LOGGED_IN） | 三证：域名非登录 + 账户姓名命中 + 退出入口 + 导航；证据不足=UNKNOWN。v1 缺陷样例进自测做永久守卫（T2 首条） |
| 4 | locate 无目标确认 | `--doc-id` 显式目标；`pick_target` 0 命中=NOT_FOUND、多命中=AMBIGUOUS、无 doc-id=TARGET_UNSPECIFIED，一律停止不进替身（T1） |
| 5 | type=new 自动回退 | 删除；structure 只检查已确认目标行，无链接可导航即 FAIL。WRITE_BTN 死代码一并删除（corrections.md #9 处置=删），源码回归守卫防复活 |
| 6 | recover 只 reload | 刷新前后 `_identity_snapshot`（单据编号**从页面正文实证在场**、账户、状态、关键值）→ `compare_identity` 比对；浏览器重启后登录态 + 目标可再定位双验证（T5） |
| 7 | 预算未强制 | `Budget` 三钟全 `time.monotonic()`：tech 入口 `ensure_tech` 抛 BUDGET_EXHAUSTED、等待切片归零、墙钟看护线程超时落盘+`os._exit(83)`；结束前 ctx.close()+pw.stop()（T3） |
| 8 | 结构扫描太浅 | `BLOCKS_READ_JS` 按命名区块（报销明细/费用说明/银行信息等）读表头+行+列+编辑器控件+框架组件类名+实际显示值，跨全部 frame；代表性字段实读（T 结构路径随 P2 在线验证） |

## 离线失败场景（temp.md 验收点名五类）

| 场景 | 用例 | 结果 |
|---|---|---|
| 定位失败 | 0 命中→NOT_FOUND；多命中→AMBIGUOUS；无目标→不选替身 | PASS |
| 身份不符 | v1 弱判样例不得 LOGGED_IN；登录域/密码框→LOGIN_REQUIRED；证据不足→UNKNOWN | PASS |
| 预算耗尽 | tech 耗尽抛错；login 钟归零收尾；看护线程启停 | PASS |
| 证据目录冲突 | 同 run 二次初始化→attempt_002，旧 attempt 文件逐字未动，无 tmp 残留 | PASS |
| 恢复到错误单据 | 换单→doc_identity+key_values 差异暴露；落登录页→URL 差异；同对象→通过 | PASS |

自测过程中修掉 3 处：`wait_slice(tech)` 透传抛错（等待助手改为归零，抛错职责在阶段入口）；自测守卫过钝（文件头注释含旧 run 字样→去掉）；T5 期望错（URL 严格相等会在 reload 瞬时参数下误报，错误单据由 doc_identity 兜住）。另主动加固 1 处：`_identity_snapshot` 原方案 doc_identity 取自 args（自比自），改为页面正文实证单据编号在场。

## 六检查项状态机

c1/c2/c3/c6 起始 NOT_RUN、逐相赋值 PASS/BLOCKED/FAIL+原因+证据路径；c4/c5 恒 NOT_AUTHORIZED（只读探针不写入，写入须 temp.md P4 显式授权）——无任何缺省成通过。

## P2 用法（需用户在场扫码）

```
python -X utf8 stage1_browser_probe.py --run 20261021-131724-1c1aadbd --doc-id <目标单据编号>
```
- 登录等待 480s 单独计时；二维码过期自动刷新登录页（独立 Chromium 内，不碰企微客户端页签）
- 未给 --doc-id 也可先跑：停在 TARGET_UNSPECIFIED，交付列表范围盘点
- 证据全部落 `automation/runs/20261021-131724-1c1aadbd/attempt_NNN/`；events.jsonl 为 run 级可变追加文件
