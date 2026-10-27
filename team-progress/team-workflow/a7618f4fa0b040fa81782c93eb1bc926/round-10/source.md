<!-- team-task-source id="src-1faaa1c3" sha256="1faaa1c3230fb419d45669085933da4dfc7888450ffded51f9bb0eec52c2f8ee" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 10
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 10 -->
# 本次任务：附属同步三项落地 + 02/04 只读控件观察 + D22 G1 链产品化（bpm_chain.py）

背景（自足）：Round-9 已完成 02/04 首件放量（config+封闭注册+离线链双 EXECUTION_READY，零浏览器动作）、D18 +4 行、D22 方案（G1-G6 缺口表）、三观察处置；全量 273 tests OK、OFFLINE_PASS。A 验收 20 PASS / 1 BLOCKED / 6 FAIL（无翻转）。round-9 披露三项授权面遗漏（A 责任）本轮首项补齐。供料依赖延续：真实发票原件（D4）、三类/02/04/06"本次原始材料"、06 候选单号。登录窗口 G6：refresh token 实测至 2026-11-23。

## 待做条款

### 1. 附属同步三项（补 round-9 授权遗漏，先做）
- `verify_bpm_build.py`：source_manifest 的 document-types 清单同步五类型（02/04 config 入 manifest 冻结，config sha 进构建产物）。
- `automation/fill-plan.schema.json`：document_type enum 同步五类型（D22 G3）。
- `bpm_extraction.py`：一页多票**显式拒绝**（检测到一页内多票身份即 GAP 登记/阻断，不拆分——拆分策略未授权，D22 G4 部分落地）+ 对应测试（现有"一票一件契约"测试不回归）。
- 各配测试；manifest 冻结后跑唯一 run 验证 02/04 config 进入绑定。

### 2. 02/04 只读控件观察（真实页面，本轮唯一浏览器动作）
- **授权范围**：真实 OA 新页打开 02 低值办公与 04 福利劳保各一次，**只读观察**：类别选择联动（submitType→reimItem 枚举 02xxx/04xxx 实测）、申请书(34)/福利申请单(74) picker 数据形态、跨部门预算选择器数据范围、必填/编辑器形态。**零业务行写入、零保存、零提交**；观察完成页面放弃（不保存关闭），留页面盘点与终局截图。
- 观察结果回填两 config 的 required_observations（或等价字段）+notes.md 修订（观察证据指针：run/attempt/截图 sha）。
- 纪律沿用：单 profile 单执行者、登录态例行动态核验（操作人取当次实测）、`--no-proxy-server`、WAI_HUMAN_LOGIN 机制兜底；登录失效不扫码不等待，转做其余条款并登记缺口。
- **不注册业务填写路径**：观察仅支撑 config 完备；02/04 真实填写授权另行申请（下轮入口）。

### 3. D22 G1：链产品化 bpm_chain.py（离线，零浏览器）
- 新增 `bpm_chain.py`：把 round-7/8/9 各 run 手写 chain_driver 的公共链（register_request→resolve_template→提取复核→FactSet→reconcile→复用矩阵→blueprint→generate_fill_plan→validate_plan→execution_ready）产品化为 CLI/库入口（承 baseline B3），消除"每 run 手写驱动"。
- 要求：分类型参数化（五类型至少三类可跑：travel/express 用 r7/r8 同形授权回放材料复跑 validate-only；02/04 用合成材料）；events schema 统一（沿用 round-9 分段标记）；失败留 plan_generation_failed 段；**不触碰浏览器**（validate-only 路径）。
- 折入 P2-2/P2-3/P2-4：真实链断言 kind=user 严格对应用户真实供料（离线合成链断言 synthetic 不冒充 user）；suggested_command 的 --expect-name 以实测值注入；test_context.authorization_path 键名改为不误导的命名（兼容旧键读取）。
- 测试：≥3 个（入口参数/链产物 schema/失败段）。

### 4. 顺带（小）
- 台账更新（W07 02/04 观察状态、W08 接入进度、bpm_chain 交付记录）。
- 06 会议支出：仍无候选则维持登记（用户供号后研究）。

## 保留项与边界
- fill_only；不测保存；SaveController/守卫/registry/legacy 原样；本轮浏览器动作**仅限第 2 条**的只读观察（两页、零业务行、零保存）；probe/入口文件（stage1_browser_probe.py/fill_once.py）零改动。
- 授权写清单：第 1 条三文件+tests；`bpm_chain.py`（新）+tests；02/04 config+notes 回填；runs/offline-verify 工件；skill 快照轮末落盘（SKILL.md 红线段逐字不动）；台账/team-progress。其他新文件先停-增补-再写；常设清单（bpm_plan_generate.py/bpm_ui.py）内最小改动+测试+留痕。
- 合成材料明示 synthetic 不入业务 manifest；不虚构业务；不自动 commit；单 profile 单执行者。

## 验证
- 三项同步落地并有测试；唯一 run OFFLINE_PASS 且 02/04 config 进 manifest 冻结。
- 02/04 观察证据链：新页身份/联动枚举实测记录、零业务行证明（页面盘点+截图）、config 回填 diff。
- bpm_chain.py 三类型 validate-only 复跑 exit 0（travel/express 授权回放、02/04 合成），events 分段规范。
- 全量 `python -X utf8 -m unittest discover -s tests` 全绿。

## done_when
1. manifest/schema enum/一页多票拒绝三项落地+测试，唯一 run OFFLINE_PASS 含 02/04 config 冻结。
2. 02/04 只读控件观察完成：联动/枚举/picker/预算选择器实测入 config+notes，页面放弃留痕零业务行零保存；或登录类外部阻断有完整缺口登记且其余条款完成。
3. bpm_chain.py 交付：三类 validate-only 复跑 exit 0、events 规范、P2-2/P2-3/P2-4 折入、≥3 测试。
4. 全量测试全绿+唯一 run PASS+skill 快照落盘。
5. 交接齐备：改动+哈希、观察证据路径、台账 W07/W08 更新、下一轮入口（02/04 业务填写路径授权申请 或 D22 实施 G2 合入）。
<!-- /team-task-source -->
