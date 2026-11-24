# 2026-11-20 全量单测基线（请假单改动 A/B 归因）

**方法**：同一命令 `python -X utf8 -m unittest discover -s tests`（仓库根执行），对工作树做 `git stash push -u` 前后各跑一次全量，逐名比对 `FAIL/ERROR` 清单。两次计数均为 **Ran 640 tests，22 失败 / 33 错误 / 4 跳过**，名单逐名一致（diff 为空）——请假单新增（`bpm/leave.py`、`bpm/leave_save.py`、`references/leave.md`）及配套文档改动**零新增失败**。

## 与历史基线的关系

- [2026-11-17 基线](../feature03-自动审批快递单/自动审批验证-20261117.json)记录 633 项 18 失败/33 错误/4 跳过；本日为 640 项 22 失败/33 错误/4 跳过。
- 增量 4 个失败为 `test_skill_docs` 的 3 FAIL + 1 ERROR（断言 `## 完整链路：模板单号+原始资料 → 执行就绪` 旧标题及配套路由文案），经 stash A/B 验证在 11-18 出差单文档提交（7954cf2/b370515，标题改为「报销完整链路…」）后即存在，与请假单改动无关。
- 错误数 33 与 11-17 基线持平，均在既有清单内；不称仓库全绿。
- 注：一次在 `tests/` 目录内裸跑 `discover` 的结果（578 项/21F/38E）含 6 个 `loader._FailedTest` 导入伪影（目录内 `import bpm` 路径不通），不作基线依据。

## 复核命令

```powershell
python -X utf8 -m unittest discover -s tests -v 2>&1 | Select-String "^(FAIL|ERROR): |^(OK|FAILED|Ran )"
```
