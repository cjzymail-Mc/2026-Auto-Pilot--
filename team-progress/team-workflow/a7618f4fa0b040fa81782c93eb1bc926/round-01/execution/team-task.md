<!-- team-task-source id="src-35ce11c1" sha256="35ce11c17950d2f3bff8e33799b5a193bfb85cecb4e0973307359c97a8b18133" status="open" -->
# 本次任务：报销材料主线 W00+W02 —— 接手基线总台账 + 原件/派生双根工作区契约

用户 2026-10-24 启动《指定模板和原始资料驱动报销完整开发任务书》（feature01-细化报销skill/2026-10-24 指定模板和原始资料驱动报销完整开发任务书.md），总目标为多轮交付：用户仅指定完整模板单号并提供本次原始资料（PDF/图片/Excel 等），agent 自行提取复核、建立本次事实、对账、生成有来源计划，经正式入口真实填写新单（fill_only 只填不存），并自行完整独立回读与 agent 独立验收后交付。用户不写内部 JSON、不承担施工人工核验或验收签字。本轮只做该总目标中可独立离线完成的主线起点：W00（接手基线与总台账）与 W02（原始资料工作区契约）；其余工作包留后续轮。

验收范围口径（继承任务书最新修订）：本轮不测保存按钮、不验收保存成功/新单号/重开持久化；现有保存守卫、SaveController 与 registry 只读核实规则原样保留。继承根 AGENTS.md 全部红线。

## 背景（自足，无需另读任务书即可执行）

- 类型机制现状：`bpm_types.py` 封闭注册 travel/express/rd_materials 三类；快递 8 费用/4 银行、研发 18 档案/4 明细/4 银行的授权历史回放真实填写已通过（证据：automation/runs/types-express-complex-R2/attempt_001/evidence/independent_verification.json、automation/runs/types-rd-complex-R2/attempt_001/evidence/independent_verification.json）；差旅正式入口有真实整单填写证据（attempt_026：SUCCESS_FILL_ONLY、29/32 零 mismatch、107.6s）。
- 最新统一离线构建：automation/offline-verify/types-real-fill-final-20261023/build_result.json 记录 OFFLINE_PASS——只证明该冻结版本，不把固定测试数当新版本阈值。
- 当前材料 manifest 要求单一 root，且复核 JSON 与原件处于同一受控清单；原件必须只读、派生输出（渲染页/OCR/复核事实/运行证据）不得写回用户资料目录——这是 W02 要解决的结构矛盾。
- 上轮已交付 D2 内层观测与两处死等消除（45822→825ms / 91803→1654ms），按其冻结范围承接，不重做。

## 待做条款

### 1. W00 基线复核与总台账
- 逐项复核最新代码/配置/证据并产出复核结论（哪些已成立、哪些是差距，引用具体文件与哈希）：`bpm_types.py` 三类注册与 schema、上述三类真实回放/填写证据、`.claude/skills/bpm-fill-run/SKILL.md` 及其 references/plan-contract.md 契约、最新离线构建记录、task-registry 现状。不重做已通过部分，不回退他人改动。
- 建立 `automation/template-materials-program/`：`progress.json` 为唯一权威进度台账，至少记录各工作包（W00-W10）/类型/场景 ID、状态（待做/进行中/待复核/缺外部输入/已验证，已验证须带证据层次与引用）、未关闭缺陷、缺失输入、授权范围、正在占用的 run/profile、下一项可执行工作；另维护一份人类可读 Markdown 推进摘要，与 JSON 冲突时以 JSON 为准。
- 台账不复制凭证、不贴材料敏感值；真实任务证据继续引用 `automation/runs/<run>/`、`automation/offline-verify/<run>/` 权威产物，不另建成功日志。

### 2. W02 原件/派生双根工作区契约
- 设计并实现版本化的「原件根 + 派生根」双根契约（或等价约束实现），解决原件只读目录与 agent 工作输出目录的矛盾。须保留：原件/派生角色区分、来源关系、原件哈希、派生哈希、合法根边界（根外路径逃逸拒绝）。
- 旧契约保持可读及拒绝漂移语义；不自动迁移正在填写或保存中的任务；渲染页、OCR 结果、复核事实与运行证据落入派生工作区，不会被下一次材料盘点误当新原件。
- 同步更新 schema/解析器/核验：新契约有明确版本标识；新来源种类同步 schema、解析器、核验与拒绝反例；不得把 agent 推断伪装成 kind=user 通过校验。
- 复核 JSON 与原件哈希绑定关系按现有 manifest 语义升级，保持可追溯（原件哈希、提取哈希入同一清单的既有要求不降级）。

### 3. 验证（全部离线，不连 OA）
- 新契约单元测试至少覆盖：合法双根通过；根外路径拒绝；原件哈希漂移拒绝；旧契约兼容读取；agent 推断来源不得通过 kind=user 校验（反例）。
- `python -X utf8 -m unittest discover -s tests` 全绿（既有测试不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（run 名唯一）PASS，产物入 `automation/offline-verify/<run>/`。
- 本轮预期不改 `stage1_browser_probe.py`；若实现中确需触碰，必须先 `python -X utf8 stage1_probe_selftest.py` 全绿再收口。

## 保留项与边界

- 只填不存；不新增保存按钮测试或保存成功验收；不虚构实单、不为找单号普查全部历史、不新建虚构报销。
- 本轮不接入新报销类别（第二批/第三批五类留后续轮）；不做真实浏览器操作（B1-B7 属每类真实业务验收轮）。
- 不修改 `automation/runs/` 旧工件、task-registry、legacy-ia2；不自动 commit、不上传业务材料。
- 若配置/schema 改动导致有效配置哈希变化或旧任务不能继续，在台账中说明兼容边界，不自动重写旧记录、不用强关旧页/删锁/task_id 轮换处理冲突。

## done_when

1. `automation/template-materials-program/progress.json` 建立且 W00-W10 各项状态有证据引用，W00 复核结论（成立项/差距项+文件与哈希）落盘。
2. 原件/派生双根契约实现并有上述五类单元测试（合法双根、越界拒绝、漂移拒绝、旧契约兼容、来源种类反例）全部通过。
3. `python -X utf8 -m unittest discover -s tests` 全绿；`verify_bpm_build.py` 新唯一 run 离线 PASS，产物留盘。
4. 交接工件齐备：改动文件清单+哈希、测试结果、台账更新、下一轮可直接执行的入口（建议指向 W03 原件理解/W05 计划衔接主线）写明。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-100330-35ce11c1" contract_id="ctr-4199eb39" source_block_id="src-35ce11c1" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24）

**终态**：报销材料主线 W00+W02 离线落地——`automation/template-materials-program/` 唯一进度台账建立（W00-W10 状态+证据引用+W00 基线复核结论）；`bpm_materials.py` 契约升级为版本化「原件根+派生根」双根契约（manifest v2.0；v1.0 旧语义不变仍可读仍拒漂移），五类新契约行为全部有单元测试，全套离线检查通过并留盘。

**本轮做**：
1. W00：复核 `bpm_types.py` 三类注册、三类真实回放/填写证据、bpm-fill-run skill 与 plan-contract 契约、最新离线构建、task-registry 现状，成立项/差距项+文件与哈希落盘；建立 `automation/template-materials-program/progress.json`（唯一权威台账）+ 人类可读 Markdown 摘要（与 JSON 冲突以 JSON 为准）。
2. W02：`bpm_materials.py` 实现 v2.0 双根 manifest：`originals_root`/`derived_root`/`files`/`derived_files`（角色区分、来源关系、原件哈希、派生哈希、合法根边界、两根互不嵌套）；`validate_image_documents`/`validate_value_proof` 兼容 v2.0（提取 JSON 归派生根并绑定原件哈希；来源种类显式化，agent 推断不得以 kind=user 通过校验）；`automation/fill-plan.schema.json` valueProof 等最小同步；不自动迁移正在填写或保存中的旧任务。
3. 验证（全部离线）：五类新契约单元测试（合法双根通过/根外路径拒绝/原件哈希漂移拒绝/旧 v1.0 契约兼容读取/agent 推断 kind=user 反例拒绝）；`python -X utf8 -m unittest discover -s tests` 全绿；`python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` PASS 且产物入 `automation/offline-verify/<run>/`。

**本轮不做**：不接入新报销类别；不做真实浏览器操作（B1-B7 属每类真实业务验收轮）；不测试保存按钮、不验收保存成功；不改 `stage1_browser_probe.py`（若实现中确需触碰，先 `stage1_probe_selftest.py` 全绿再收口）；不改 `automation/runs/` 旧工件、task-registry、legacy-ia2；不自动 commit、不上传业务材料。

**允许写**：`bpm_materials.py`、`bpm_plan.py`（仅 v2.0 上下文最小接线，改动须记进度日志理由与 diff 摘要，预计不需要）、`automation/fill-plan.schema.json`（valueProof/来源相关最小增量）、`tests/`（新增测试文件或追加测试类）、`automation/template-materials-program/`（新建）、`team-progress.md`、`team-task.md`（仅本合同追加）。
**只读**：`fill_once.py`、`bpm_types.py`、`bpm_ui.py`、`bpm_verify.py`、`bpm_save.py`、`stage1_browser_probe.py`、`automation/runs/`、`automation/task-registry/`、`automation/offline-verify/` 既有产物、`.pw-profile/`、`legacy-ia2/`。
**禁止**：删除或重写旧 run/registry/证据；放宽通用守卫或保存保护；把 agent 推断记为 kind=user；虚构实单或保存验收。

**红线**：继承根 AGENTS.md 全部红线（默认只填不存；`.pw-profile/` 活体 token 绝不入 git/日志/报告；`legacy-ia2/` 只读；registry 只读核实、不删不换 task_id；单 profile 单执行者；不走 VPN/代理）。team-task 四红线：①销毁性/不可逆操作；②对外交付物；③同一 failure_key 三次失败熔断；④推翻已封决策。B 模式权限类命令（rm/伸敏感目录/对外）后置人工门，不在中途发起。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM；risk_class=MEDIUM；risk_owner=USER；risk_source=USER_STANDING_POLICY_20260904；runtime_policy=GLM_ALLOWED；risk_escalation=NONE。runtime 一手证据：team-workflow helper 从本 session 原始 JSONL 证明 CLAUDE_GLM/glm-5.3（progress 头已记录）。

**裁量项（contract-only：写推荐+依据，P6 执行期按 B 默认落实并记自主裁决）**：
- 模块落点：扩展 `bpm_materials.py`（推荐依据：单一权威、现有 import 链零破坏）而非新模块。
- materials 层 proof 新来源命名：`agent_reviewed`（依据：与 plan 级 `derived`（=显式 sum 计算）语义区分防歧义）；v2.0 下 kind 必填无默认。
- derived role 封闭枚举：`{parsed_extraction, reviewed_extraction, ocr_result, render, run_evidence}`（依据：任务书 §5.1 列举的派生物；代码内封闭，扩展走代码变更）。
- 台账路径：`automation/template-materials-program/`（任务书 §12.1 建议直接采用）。

**done_when（字面可判；全部离线验证）**：
- D1: `automation/template-materials-program/progress.json` 在场，含 W00-W10 各工作包条目（状态+证据引用），W00 复核结论（成立/差距+文件与哈希）落盘。（验证：`python -X utf8 -c "import json;d=json.load(open('automation/template-materials-program/progress.json',encoding='utf-8'));..."` 抽查结构 + 复核结论文件在场）
- D2: 双根契约实现且五类单元测试全过：合法双根通过/根外路径拒绝/原件哈希漂移拒绝/旧 v1.0 契约兼容/agent 推断 kind=user 被拒。（验证：`python -X utf8 -m unittest tests.test_bpm_materials -v` 全绿且新增测试类覆盖五类各至少一断言）
- D3: `python -X utf8 -m unittest discover -s tests` 退出码 0（0 failures/0 errors）。
- D4: `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 产出 `OFFLINE_PASS`，产物在 `automation/offline-verify/<run>/`。（验证：build_result.json status==OFFLINE_PASS）
- D5: 交接工件齐备：改动文件清单+sha256、测试结果、台账更新、下一轮入口（建议指向 W03/W05 主线）写明于 team-progress.md 收尾段及台账。
<!-- /team-task-contract -->
