<!-- team-task-source id="src-b401214d" sha256="b401214dffa10e3c04e78977335b8b8816a246d01c975f2a8d19961bae7eff71" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 6
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 6 -->
# 本次任务：W06 前置 —— 执行串联与 skill 链路增补（+live 模板读取尝试 + R5-P2 顺带）

总目标背景（自足）：多轮交付"用户仅给模板单号+原始资料，agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。已交付 W00-W05（全离线）：总台账、双根契约（`bpm_materials.py`）、原件理解（`bpm_extraction.py`）、事实与对账（`bpm_facts.py`）、计划衔接（`bpm_plan_generate.py`+`fill_once.py` 阶段机至 PLAN_READY）、请求与模板决策（`bpm_request.py`：register_request/resolve_template/build_reuse_matrix/identify_unknown）。构建源清单 glob 自动冻结。本轮把"计划→执行"最后一段串起来（离线可验部分），并把新链路写进业务 skill；live 模板读取作为 W06 首个实况项尝试（可回退）。真实填写（B2-B7）仍待八类真实原件（外部输入，未提供）。

验收口径继承：只填不存；守卫/SaveController/registry 原样；不虚构实单；缺真实材料登记缺口不停工；本轮除只读 live 模板读取（若登录可用）外零浏览器操作、不新建不填写任何单据。

## 待做条款

### 1. D10 执行串联（离线核心）
- 上层衔接：PLAN_READY 产出的 fill-plan 文件 → `python -X utf8 fill_once.py --fill-plan <计划> --expect-name <本次身份> --validate-only` 全绿 → 输出"执行就绪"结论（计划路径、哈希、操作人、建议执行命令含 --keep-open-minutes 参数形制；不自动启动浏览器）。
- 操作人来源合规：--expect-name 值只能来自本次请求记录的 user_policy/系统观察事实，不得从模板历史人员推导；无本次身份来源时执行就绪判"缺输入"并给缺口，不猜姓名。
- 串联测试：合成场景 请求→…→PLAN_READY→validate-only 通过→执行就绪输出；身份缺失场景→准确缺口。
- 不改变 fill_once 既有参数语义；新增仅为上层编排（模块名自定，如 bpm_request.py 内或新模块）。

### 2. skill 链路增补（.claude/skills/bpm-fill-run/）
- SKILL.md/references 增补：新链路（请求登记→模板决策→原件理解→事实对账→计划→执行就绪）的调用方式与阶段语义；与既有 --task/--fill-plan 入口的关系（旧入口保留兼容）。
- 修改后用可用的 skill 校验工具验证结构、引用完整性；验证新 session 路由可按 skill 找到入口（离线可验部分）。
- 不改 skill 中保存/授权相关红线文字。

### 3. live 模板读取尝试（W06 首个实况项，可回退）
- 前置：`automation/.pw-profile/session_state.json` 登录态 TTL 检查；取得 profile 锁（单执行者纪律）。
- 若登录有效：`bpm_template.py --live --expect-name <当前已确认操作人> --template-number <三类之一完整单号> --output automation/runs/<独立run>/template_snapshot_live.json` 定向读取一张模板快照，与缓存快照核对一致性（uuid/类别/关键结构），留 run 工件。**不新建、不打开新单填写页、不触碰任何未保存页。**
- 若登录失效/TTL 不足/profile 被占：不扫码不等待，登记准确缺口（GAP_FIELDS 形状入台账 missing_inputs），继续离线部分——两种结果均算完成本项。
- live 前后各截取 events 证据；全程只读。

### 4. R5-P2 三条顺带（记录级）
- 旧日期/旧收款冒充反例实例化存档（把 round-5 三反例模式扩展到日期/收款两个字段并入库测试）。
- 矩阵重复 (group,field) 行显式拒绝。
- `_load_doc` 解析重复维护成本：最小重构或注释说明取舍（不强制）。

## 保留项与边界
- 除第 3 条只读 live 外零网络零浏览器；不动守卫、旧 run（live 输出进新独立 run 目录）、task-registry、legacy-ia2；不自动 commit。
- live 读取严格限既有授权范围（定向模板查询）；失败即登记，不重试刷屏、不强占 profile。
- 原件只读；合成 fixtures 放 tests/。

## 验证
- 新增单测：执行就绪两态（齐备→就绪输出/缺身份→缺口）、R5-P2 前两条、矩阵重复行拒绝。
- live 尝试的两种结果均有工件（成功：快照+核对记录；失败：缺口登记）。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 218 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS；skill 校验工具对修改后的 skill 通过。

## done_when
1. PLAN_READY→validate-only→执行就绪 串联实现+测试（两态；不启动浏览器）。
2. skill 增补完成并通过校验工具；新 session 路由（离线可验部分）通过。
3. live 模板读取尝试留证（成功核对一致 或 失败准确缺口登记），无任何新建/填写动作。
4. R5-P2 前两条落地+测试；第三条处置说明。
5. 全量 unittest 全绿；唯一 run OFFLINE_PASS。
6. 交接齐备：改动+sha256、测试结果、台账 W06 状态更新（按实况）、下一轮入口（W06 真实端到端待外部材料 / W07 两类研究可先行）。
<!-- /team-task-source -->
