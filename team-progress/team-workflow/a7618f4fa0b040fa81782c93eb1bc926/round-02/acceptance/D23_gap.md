# Round-2 A 验收证据：D23 工程检查 — FAIL（一处绑定缺口）

验收人：A 窗口（session 9ba961a6，run a7618f4f…）。日期：2026-10-24。

## 已核验通过部分

- 全量测试独立复跑：`python -X utf8 -m unittest discover -s tests` → **146/146 OK**（99.3s；133 基线零回归+13 新增）。
- 新测试独立复跑：`test_bpm_extraction.py` → 13/13 OK。
- 统一离线构建：`automation/offline-verify/template-materials-20261024-111625/build_result.json` OFFLINE_PASS、production_access=False、capability-tests 146 项 exit 0、run 名唯一。
- stage1_browser_probe.py 未改（selftest exit 0）；守卫无变化。
- R2-P1 修复核验：bpm_materials.py L245-246、L517-518 相对 derived_root 一律以 manifest 所在目录解析，与 L233 校验 base_dir 一致；CWD 回归×2 测试独立复跑通过。

## 判定 FAIL 的缺口（B 已自报为 R2-P5，A 确认属实）

**本轮主交付模块 `bpm_extraction.py` 未进入统一构建的冻结源清单**：
`source_manifest.json`（44 键）顶层键不含 `bpm_extraction.py`；grep 命中仅为 `tests/test_bpm_extraction.py`（测试文件路径）。即 OFFLINE_PASS 的冻结哈希未绑定本轮核心新模块，"最终统一离线构建…代码/证据哈希对应"存在一个洞。

处置：计入 failure_counts（`review|content|source_manifest_coverage|D23`，首次）；R2-P5 转入 Round-3 任务必做项（更新 verify_bpm_build.py 源清单机制，使根模块自动纳入并冻结，补唯一 run 重建）。修复并复验前 D23 保持 FAIL。
