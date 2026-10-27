# Round-01 A 独立全局验收记录（run 242ccba1c43343f687aa1db0ae014f5b）

- 验收人：A（CLAUDE_GLM glm-5.3，session 9acdfc57-4f2d-476f-bc24-b23bedb77a24）
- 时间：2026-10-27（北京时间）；基线 BPM-SELFDRIVE-20261027-V1 sha256 `4ac8adbe…`（复核一致）；criteria 16 项冻结 sha256 `a7c1f532…`（team-progress/…/criteria.json 复算一致）
- 交接：handoff_sha256 `96bbd3a1…`，outcome=complete，B 自报 5 项 done_when 全 PASS；本记录为 A 独立复核，不采信 B/MC 自述作为结论。

## 独立验证与结果

| # | 验证项 | A 的独立方法 | 结果 |
|---|---|---|---|
| 1 | 交接工件零漂移 | 复算 handoff 全部 12 件（含 events.jsonl、team-progress.md、STATE.md）sha256 | 全 MATCH |
| 2 | 全量回归独立复跑 | `python -X utf8 -m unittest discover -s tests` | 345 OK（skipped=4），exit 0；日志存本目录 capability-tests-rerun.log |
| 3 | 构建产物 | 读 build_result.json + source_manifest.json | OFFLINE_PASS；probe-selftest exit 0；3 新件（self_drive.json/bpm_self_drive.py/tests）入清单且哈希同交接值；production_access=false；save 指令按 fill_only 理由 waived（V3 旧 D22 输出语义在本轮口径下正确） |
| 4 | 计算核心代码审读 | 通读 bpm_self_drive.py（307 行）、self_drive.json | 模型/门槛/分离纪律与合同 §4.4 一致：Decimal 两位、拒浮点、通行票恰分配一次、油票不入行、有效日 ISO 去重、F>R 严格无容差、rules 绑定校验 rate/meal/version、配置封闭校验 |
| 5 | §6.1 反例测试实质 | 通读 tests/test_bpm_self_drive.py 29 用例 | 抵消不放行（内嵌 381.76 合计相等前提）、逐单 +4.00/−10.00 累计 −6.00、437.18 正向对照（原件复算路径 185.90 + 污染派生值 439.18 显式区分 + 隔离对照）、日期反例（11-12→11-14、11-24→12-24）、历史餐补五值绑配置全拒、F=R/F<R/+0.01 边界、旧模型 R=M+T 分离回归；断言非恒真 |
| 6 | 73 原件零漂移 | 以 v3r00 基线 manifest（groups/rel/sha256）独立复算材料目录全部文件哈希 | 73/73 matched，changed/new/missing 均空 |
| 7 | 守护/既有模块零改动 | 与最近一次含 bpm_coverage 的先前构建清单（materials-v3r07-20261026-1900）比对 17 个模块哈希 | 16 件 SAME；唯 verify_bpm_build.py DRIFT，实读 L33-35 确认仅“注释 + self_drive.json 源清单一行”（round-1 任务明示的源清单纳入，授权范围内） |
| 8 | 零业务写入 | events.jsonl 全 16 事件分类 + 写入类关键词扫描 | 浏览器相关仅 identity_probe_done（11:20:45 只读探查）；write-ish 候选 0；registry 12 件 FORM_INTENT 零保存意图（p0-inventory + events 互证） |
| 9 | git 面 | git status 快照对照开工前 | tracked 修改集 = rounds 3-10 遗留集，无新增越界；新 untracked 仅 bpm_self_drive.py、automation/business-scenarios/、本轮 runs/offline-verify 目录 |
| 10 | 生产面案例答案扫描 | grep 对照值/单号/人名/日期（bpm_*.py、business-scenarios、skill 全文） | self_drive.json 零命中（属实）；发现 4 处生产说明泄漏：bpm_self_drive.py:143（真实公出单号）、:262（437.18）、:282-283（日期反例）、references/express.md:5（“系统默认陈晶”，rounds 3-10 遗留）——均非路由逻辑值，用户已裁定按后续自足任务清除，不计本轮缺陷 |
| 11 | P0/P1 交付审读 | p0-inventory.json 六要素、p1-entry-design.md 全文 | 六要素齐备；设计管线与 §3.1/§3.2 一致。用户指出 §2(4)“real_save_verified=false 入口拒保存”与 A1 增补形成阻断循环——R1 冻结设计留历史，后续接线把“验证层次如实报告”与“当次 save_draft 授权 + SaveController 保护”分离；本历史占位案例仍强制 fill_only，不为补真实保存证据造单 |

## 复跑纪律说明

本轮 A 验证曾一次命令内连续跑两遍全量（tail 摘要 + -v 存档）。按用户 2026-10-27 指示，后续全量回归单次运行即捕获日志与退出码；已通过且无新变化不重复全量。本记录以 -v 存档运行（capability-tests-rerun.log）为准。

## 判据签署（D01—D16，全量覆盖）

| ID | 状态 | 依据（详） |
|---|---|---|
| D01 | FAIL | 统一入口仅设计（p1-entry-design），fill_once/bpm_request/bpm_chain 未贯通到真实填写；计划内后续阶段 |
| D02 | FAIL | 30 天迁移未实施（本轮明示只记录设计 §4）；身份探查/60 天现状如实留档 |
| D03 | FAIL | 路由管线未实现；self_drive.json identification/capability_layers 已备 |
| D04 | FAIL | 识票归集未开工（round-2 目标） |
| D05 | FAIL | Excel 副本回填未开工 |
| D06 | FAIL | 公出匹配未开工 |
| D07 | FAIL | 计算核心+严格覆盖已离线验证（上表 #4/#5），但事实/计划/coverage 绑定与写入前重算未建 |
| D08 | FAIL | 计算器层 §6.1 反例全绿（A 复跑）；原件/材料级夹具与整链定位待后续 |
| D09 | PASS_DYNAMIC | 本轮对既有代码唯一改动=源清单一行（#7 内容核实）；守护文件哈希零变；全量 345 OK 独立复跑；既有负例仍在套件内通过 |
| D10 | FAIL | 真实填写未开始 |
| D11 | FAIL | registry 只读/零保存已核（#8）；占位与真实分离建模未建 |
| D12 | FAIL | 未开始；#10 污染扫描为其前置已做首轮 |
| D13 | FAIL | SKILL/runbook/README 未修订（STATE 已按标准更新，#1） |
| D14 | PASS_DYNAMIC | 原件 73/73 零漂移（#6）、守护模块零改动（#7）、证据落新 runs/offline-verify（#9）、探针未改、全局配置/helper 未动 |
| D15 | FAIL | 本轮 selftest/unittest/构建纪律已独立复核通过；最终报告四层次分层与单次运行纪律属收尾要求，待后续 |
| D16 | PASS_DYNAMIC | 本轮零填写零保存零上传，fill_only 边界保持，验证全由 agent 完成；注：A1 增补后 D16 后续按“本案例 fill_only + 日常真实任务自动保存”双轨口径复核 |

failure_counts：{}——本轮无真实缺陷（#10 四处与 §2(4) 口径、P2-2、身份差异风险均经用户裁定为后续轮任务项，非本轮应交付未交付）。

## 下一轮派工要点（进 team-task 草稿）

1. D02 30 天迁移（bpm_session + 探针一致 + 边界测试族 + SKILL/AGENTS 60→30 同步）。
2. D04 识票归集正式化（多票分件/规范命名/可逆映射/去重幂等 + 下游 records[0] 同步；73 原件只读归集）。
3. P2-2 机制化（生产调用强制 rules=load_self_drive_rules()，测试固化）；P2-3 + express.md 案例答案/身份硬编码清除 + 生产面零命中复扫。
4. §2(4) 纠正落后续实现与说明（A1：验证层次报告与当次授权分离）；身份关系字段建模（§4.1/§4.4：不换人凑值、不默认零餐补，冲突留证上报）。
5. 回归纪律：单次运行存日志+退出码，无新变化不重复全量。
