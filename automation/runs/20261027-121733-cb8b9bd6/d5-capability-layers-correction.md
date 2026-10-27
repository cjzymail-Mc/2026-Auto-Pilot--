# §2(4)/A1 口径纠正记录 + 身份关系字段（D5）

run: 20261027-121733-cb8b9bd6 ｜ 合同 ctr-2433e4a3 D5 ｜ 用户 2026-10-27 两条指示 ｜ 2026-10-27
性质：**设计修订记录（新文件）**。不改动 R1 冻结的 `p1-entry-design.md`（含其历史哈希记录）；
本记录是其后续修订口径，冲突处以本记录为准。

## 1. §2(4) 纠正：capability_layers 不是保存入口拒绝条件

R1 设计中「能力检查层 capability_layers」曾可能被读作：能力分层未达标时，
对已获授权的保存请求作入口拒绝。**该口径纠正为：**

1. **capability_layers 只作如实分层报告**：报告某类型当前到达的能力层
   （离线通过 / 真实填写通过 / 真实保存通过……），供派工与风险判断参考；
   它不构成对任何具体保存请求的入口拒绝条件。
2. **保存许可的判定链不变**：当次请求意图（save_draft）＋ 同 task_id 的当次
   授权 ＋ 现有 `SaveController` 保护链（完整独立回读、身份/来源/配置/计划绑定、
   金额闭合、终局截图、点击前复核）。能力分层结论不增不减这条链。
3. **本历史占位案例不追溯**：round-1 冻结 V3 案例（已占用公出单＋占位关联）
   强制 `fill_only` 不变——不为其补造"真实保存证据"，也不因本纠正改判其历史验收。

## 2. A1 增补的轮次归属（本轮不实施）

BPM-SELFDRIVE-20261027-A1（日常真实任务自动保存草稿）属 **round-3 入口接线**：
真实新任务经 `fill_once` 入口携带 `save_draft` 授权，由 SaveController 按上述判定链
执行一次唯一精确保存。本轮（R2）零业务写入，不实施保存改造；本记录只落口径与
身份关系字段，为 round-3 提供不变量。

## 3. 身份关系字段（本轮已落地）

新增 `bpm_identity.py` + `automation/task.schema.json` 可选 `identity_relations`：

| 角色 | 语义 | 来源示例 |
|---|---|---|
| login_operator 登录操作人 | 当前 OA 会话登录身份 | oa_profile（顶栏/个人资料只读核实） |
| form_creator 新页制单人 | 真实新报销页观测的系统默认制单人 | template_page / system_observation |
| expense_owner 费用所属人 | 本批费用/公出事实行所属人（可与他人不同） | workout_detail（事实行人员） |

不变量（红线级，`tests/test_bpm_identity.py` 固化）：

- 角色未知 ⇒ `IDENTITY_ROLE_UNKNOWN` 缺口按 NEEDS_INPUT 上报；不猜名、不沿用历史姓名；
- **不为套用案例对照值换人**：预期与实测制单人不一致 ⇒
  `IDENTITY_EXPECTATION_MISMATCH` 真实缺口（`expected_mismatch_gap`），不换人、不改预期；
- **不默认零餐补**：餐补 C 仅在制单人身份合法成立（实名在案＋可核实来源，
  `creator_identity_established`）时按其参与日计；不成立 ⇒
  `MEAL_BASIS_CREATOR_UNKNOWN` 缺口（`meal_basis_gap`），不得把 C 置 0 继续算；
- user_statement 仅是声明，单独不构成"身份合法成立"。

已知风险（只读核实，不阻塞本轮）：当前探查身份与本批费用所属人不同——
按上表分角色记录后即为正常形态（操作人≠所属人合法），真实差异按缺口上报。

## 4. 与冻结件的关系

- R1 `p1-entry-design.md` 原文与其哈希记录不动；本文件为前进式修订口径。
- `bpm_save.py` 零改动；`_click_guard`/锁/registry/保存边界未放宽。
- 本记录不含案例对照值/真实单号/人名（P2-3 清污口径），可安全进入后续轮引用。
