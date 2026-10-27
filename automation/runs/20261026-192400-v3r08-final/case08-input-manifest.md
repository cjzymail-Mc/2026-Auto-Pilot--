# CASE-08 新 session 使用验收 —— 输入白名单清单（启动前落盘，可审计）

冻结依据：team-task src-82e4775e 待做条款 2；合同 ctr-3057b56a 冻结范围 2；V3 §10.5/§9。
落盘时间：2026-10-26 19:3x（先于 CASE-08 agent 启动）。

## 允许输入（白名单，逐项给路径/值）

| # | 输入 | 路径 / 值 |
|---|---|---|
| 1 | 冻结需求合同（含 §4/§5 业务规则原文） | `feature01-细化报销skill/2026-10-26 真实公出案例独立解析与OA填写施工合同-冻结V3.md`（sha256 d437988d…，A 绑定基线） |
| 2 | 生产 skill 正文及其 references | `.claude/skills/bpm-fill-run/SKILL.md` + `references/`（travel.md、plan-contract.md、full-chain.md、express.md、rd-materials.md、evidence-hash-semantics.md；travel.md 本轮已补 oa_test_relations 正式生成路径一节） |
| 3 | 用户指定模板单号 | `15426095951`（用户 2026-10-26 原话指定，round-6 起已解禁） |
| 4 | 原件目录 | `feature01-细化报销skill/12月公出-发票/`（73 件原件） |
| 5 | 业务规则 | 由 #1 合同 §4（覆盖模型/公里规则）/§5（含 §5.3 占位关联纪律）自带，不另喂 |

## 明确禁止（B 承诺不喂，agent 亦不得在比对阶段前读取）

- `automation/runs/20261026-172300-v3r06-template-plan/fill-plan.json`（已交付 v1.0）及该 run 全部产物
- `automation/runs/20261026-181500-v3r07-fill/`、`automation/runs/20261026-183000-v3r07-fill/`（v1.1/枚举/B5）
- CASE-01/02/03 内部 FactSet/映射/对照 JSON（`case01-facts.json`、`case02-mapping.json`、`actual_trip_matches.json` 等）
- 任何 B 或上游 agent 生成的内部 JSON/复核 JSON/私有驱动脚本

比对阶段（agent 自有 v1.0 通过 validate-only 并回报后）才由 B 提供已交付 v1.0 等**事后审计证据**，逐项标注"仅比对用"。

## 环境边界声明（如实）

- CASE-08 agent 为全新 subagent，零对话上下文继承；其系统层自动注入的仓库级 CLAUDE.md/AGENTS.md（硬规则）属 harness 环境而非 B 喂入的数据输入，在此如实声明。
- agent 产物落 `automation/runs/20261026-192400-v3r08-final/case08/`；其自带输入读取日志（每个实际打开的文件）为其产出之一。
- 浏览器仅允许只读正式入口（`bpm_login.py`/`bpm_template.py --live`）且与 B 主会话错峰（B 本轮零浏览器业务动作）；不可用时按任务条款以缓存/skill 官方缓存路径只读核验并如实记录。
- 零业务写入：不新建报销页、不填写、不保存、不动 registry、不改旧单。
