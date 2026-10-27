# P1 统一入口与规则版本化设计决策记录

run: 20261027-111853-f2789e00 ｜ 合同: BPM-SELFDRIVE-20261027-V1（§1/§3.1/§4.4）｜ 冻结合同: ctr-640d0763
日期: 2026-10-27 ｜ 状态: 设计落档（本轮不改 SKILL.md 正文；实施属后续轮 P3-P5）

## 1. 用户接单形态（两类输入，不要求用户写内部 JSON）

用户只给两样东西 + 一句意图：

1. **材料**：一个或多个材料路径（目录或文件混给，如 `feature01-细化报销skill/12月公出-发票/` +
   公里统计 Excel + 补充扫描件）。路径由用户本次给出，不沿用旧 run 的材料目录。
2. **指定单号**：一个完整模板单号（如 `15425123013`），供 `bpm_template.py --live` 定向读取。
3. **一句意图**：自然语言（如"自驾公出的报销，按 30 元餐补新规则填"）。

入口负责把这三样编译成内部 task/plan JSON（agent 核对材料后生成 v1.0 可执行计划，
沿用 fill_only 默认与现有 task/fill-plan schema），用户全程不见内部 JSON。

## 2. 路由管线（模板读取 → 表单/类别核实 → 场景识别 → 能力检查 → runbook 加载）

```text
[输入] 材料(多路径) + 指定单号 + 一句意图
  ↓
(1) 模板读取    bpm_template.py --live --template-number <完整单号> --output <run>/template_snapshot.json
                （同 profile 锁 + 临时 context，不触恢复页；沿用现有入口，不新建浏览器通道）
  ↓
(2) 表单/类别核实  快照中 submitType/bizOrign/类别树 → (document_type, submit_type_code)，
                与 bpm_types 封闭注册 + automation/document-types/ 配置对照；
                不匹配/未知 → 安全停止（缺口报告），不猜测类别
  ↓
(3) 场景识别    判定是否 self_drive：采用证据（公里统计表含用户公里数、通行费票据集合、
                覆盖池油票、真实公出单事实行）+ 排除依据（不能仅凭单号/备注"公出油补"/存在
                交通费判定）。识别输出必须同时列两类依据；冲突/多候选只读整理缺口，不默认路由。
                依据 automation/business-scenarios/self_drive.json 的 identification 块。
  ↓
(4) 能力检查    按场景配置 capability_layers 逐层判定：code_implemented / offline_verified /
                real_fill_verified / real_save_verified。real_save_verified=false 时保存类
                操作在入口层即拒绝（不依赖执行器自觉）；real_fill 未验证时明确告知阶段边界。
  ↓
(5) runbook 加载  按场景加载 references/self-drive.md（后续轮产出）；未识别场景回落既有
                travel 流程；无 runbook 的已识别场景按能力缺口停止。
```

## 3. 规则版本化与绑定（本轮已落地）

- 配置: `automation/business-scenarios/self_drive.json` v1.0.0（schema_version 1.0，
  scenario_id=self_drive，model=self_drive_strict_surplus_v1，rate 1.00、meal 30.00、
  strict_gate=greater，separation 块含 historical_meal_values_not_reused）。
- 加载: `bpm_self_drive.load_self_drive_rules()` 封闭校验（结构/数值/来源齐全才返回）；
  `rules_sha256()` 提供配置哈希。
- 绑定: 未来自驾 plan 的 self_drive_coverage 块必须携带 config_sha256 =
  rules_sha256(配置)；计算入口 `evaluate_self_drive(inputs, rules=...)` 强制输入
  rate/meal/version 与配置一致——历史餐补值（12/18/24/36/48）与旧模型输入在此被拒。
- 并存: 旧 `fuel_pool_strict_surplus`（R=M+T，无餐补）零改动并存；旧任务计划不带
  self_drive 配置哈希 → 不会被路由到新模型（不静默升级）。案例对照值
  （1924.93/300.00/2224.93）只存在于离线测试，不进生产路由逻辑。

## 4. 30 天会话改造设计要点（本轮只记录，不改 bpm_session.py）

- 现状: `bpm_session.py` REUSE_DAYS=60；.local-session 记录 last_scan_at +
  effective_reuse_until=min(local 60 天, server refresh token 期限)。
- 改造方向（后续轮）: REUSE_DAYS 60→30；旧记录迁移规则 `effective_reuse_until =
  min(原窗口, last_scan_at+30天)`——不续期、不因迁移提前失效；探查写回不重置起点；
  模拟测试覆盖 30 天边界三档（未满/恰满/超过）+ 更短旧窗口。
- 入口联动: 能力检查层在业务开工前读 session_record 的 effective_reuse_until，
  过期即停（WAIT_HUMAN_LOGIN 语义），不冒用历史姓名。

## 5. 本轮实现映射（P2 与本设计的关系）

| 设计件 | 本轮落地 | 后续轮 |
|---|---|---|
| self_drive.json 配置 | ✅ v1.0.0（rules_frozen_implemented_offline） | 随规则演进升 version |
| load/rules_sha256/evaluate | ✅ bpm_self_drive.py | 事实层 register helper、plan schema 键 |
| §6.1 反例测试 | ✅ tests/test_bpm_self_drive.py（29 用例） | 材料侧反例（识票/Excel 回填）随 P2 后续轮 |
| 入口管线 (1)-(5) | 设计定稿（本文件） | fill_once/bpm_types 路由实现 |
| runbook | 未开始 | references/self-drive.md |
| 30 天会话 | 要点记录（§4） | bpm_session.py 改造 + 模拟测试 |

## 6. 边界与不做

- 本轮零业务写入；浏览器只读动作仅已完成的身份探查 ×1（11:20:45）。
- 本设计不放宽 _click_guard/锁/registry/保存边界；能力检查层的"拒绝保存"是新增只读
  门禁语义，不改变 SaveController 既有授权体系。
- 案例对照值不写进 self_drive.json（配置只含规则参数，不含本例金额）。
