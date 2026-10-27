# Round-05 A 独立验收（证据卫生修复轮）

- A session：`0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`｜run `d91601924848489f84e317e68582de26`｜round 5｜B 交接 seq 25
- 验收脚本：`C:/Users/xy198/AppData/Local/Temp/a_r05_verify.py`（只读仓库）+ A 亲跑全量 unittest；机器结果见本目录 `hash-recheck.json`
- 基线 sha256 `d437988d…5c977ef0d` 逐字匹配（连续第 5 轮）

## 一、三项修复独立复核

1. **O1（wide-query-manifest 哈希语义）**：5 页 `sha256_file` A 逐页重算 == attempt_007 证据文件字节 5/5；原 `sha256`（logical 口径）键值原样保留且 A 用紧凑序列化公式复验 5/5 仍成立；顶层 `hash_semantics` 就位。加法式订正达标，无历史回改。
2. **O2（日期口径文档化）**：candidates3e 与 actual_trip_matches 均有 `date_field_semantics`——matched=实际公出时间（factStart/EndTime）、排除块=自然区间（factNature*）、12 张 MATCHED 等价说明与 12025095297 分歧示例齐备，且引用 A round-4 验收为等价依据。
3. **O3（显式 applicant）**：12/12 matched_doc 有 `applicant=陈晶`+`applicant_user_id=116070053`，A 逐条回对 attempt_011 api-detail 原始行（appliedName/appliedBy）全中；`ui_text` 统一 `attempt_011/evidence/` 前缀 12/12；CASE-03-report 逐单表升级 8 列（申请人列含 陈晶(116070053)）。

## 二、修复后内容完整性（防修复致损）

- actual_trip_matches：27 票 identity 唯一、12/15 划分、Σ 221.02/265.91/总 486.93==T、per-doc 2/4/2/2/2 与行分配——与 round-4 验收基线全等，仅新增字段。
- `final-artifact-hashes.json`：7 个文件键 + revision 键，逐键 == 盘面字节；`revision-hashes.json` before==round-4 finish 权威值、after==当前盘面（A 复算双向全中）。
- 73 原件连续第 5 轮零漂移；attempt_010 作废件 26 个原样保留。

## 三、源码/构建面

- 改动面与交接一致：`verify_bpm_build.py`（capability pattern `test_bpm_*.py`→`test_*.py`，299→308 全量等价）、`tests/test_bpm_round10_sync.py`（docstring 订正）、新增 skill reference `evidence-hash-semantics.md`（1981B，含文件字节口径与双日期口径规范）。
- **stage1_browser_probe.py 未动**（mtime 2026-10-24 10:43，早于本工作流全部轮次）；schema/bpm_facts/bpm_plan/bpm_coverage 逐字节未变（== round-3 交接值）；schema 字节基线 `materials-v3r05-20261026-162500/fill-plan.schema.json.v3r05-baseline.bak` 建立，ba7b065f… 与 V3-R03 一致。
- **A 亲跑 `python -X utf8 -m unittest discover -s tests`：308 tests OK (skipped=4)**，与 B 报告及唯一新构建 `materials-v3r05-20261026-162500` OFFLINE_PASS 一致。
- 卫生轮 events 19 条零写动词、零浏览器调用；凭证 grep（eyJ/refresh_token）全净。

## 四、台账

progress.json V3-R05 入账（before/after 指针）、errata 仍 4 条未增删、observations 闭环后余 3 条保留项；模板缺口在本轮台账仍为 PENDING_HUMAN_NONBLOCKING——**注：用户已于 2026-10-26 16 时后在 A 窗口提供完整模板单号 `15426095951`（陈晶最近一张报销单），该人工缺口实际已解除**，round-6 任务书将携带此输入并要求台账同步 CLOSED。

## 五、判据签核

卫生轮不改变判据状态：17 项 PASS_DYNAMIC 维持（D21/D23 本轮改动进一步增强），10 项 FAIL 维持（CASE-05..08 未开工；模板号已到，round-6 进入主线）。decision=rework → round 6 = CASE-05 模板定向读取 + CASE-06 计划生成（validate-only 止）。
