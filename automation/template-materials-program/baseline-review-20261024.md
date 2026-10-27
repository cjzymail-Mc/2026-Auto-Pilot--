# W00 接手基线复核结论（2026-10-24）

复核人：round-1 执行 B（run_id 20261024-100330-35ce11c1，合同 ctr-4199eb39）。方法：对任务书 §3 差距表逐项以盘上文件一手核验（存在性、内容、哈希），不重做已通过部分。哈希为 SHA-256 前 16 位（完整值见 progress.json 引用文件时可按此复核）。

## A. 已成立项（直接承接，不重做）

| # | 结论 | 证据（文件 + sha256/16 + 关键事实） |
|---|---|---|
| A1 | 类型机制封闭注册 travel/express/rd_materials，schema/配置接入 | `bpm_types.py` 5d8b8b216059e682，L16-18（label/api_code 08/15/11）；`automation/document-types/` 三配置在盘 |
| A2 | 快递复杂结构授权历史回放真实填写 + 独立核验通过 | `automation/runs/types-express-complex-R2/attempt_001/evidence/independent_verification.json` c2c49b82028b1841：ok=true，details 1/costs 8/banks 4 全对齐，四层金额闭合 347.50 |
| A3 | 研发复杂结构授权历史回放真实填写 + 独立核验通过 | `automation/runs/types-rd-complex-R2/attempt_001/evidence/independent_verification.json` fa0e7265772f850d：ok=true（18 档案/4 明细/4 银行口径见该 run） |
| A4 | 差旅正式入口真实整单填写（只填不存） | run `20261021-131724-1c1aadbd`（events.jsonl 6104848f1fe8b403，追加式 762 行）：attempt_026 SUCCESS_FILL_ONLY、29/32 零 mismatch、tech 107.6s、≥45s 死等段 6→0（上轮 round-2 ENHANCED_FINAL GO） |
| A5 | 统一离线构建通过 | `automation/offline-verify/types-real-fill-final-20261023/build_result.json` 154f409934e1a184：OFFLINE_PASS、production_access/writes=false——只证明该冻结版本，不把固定测试数当新版本阈值 |
| A6 | 业务 skill 与计划契约在盘 | `.claude/skills/bpm-fill-run/SKILL.md` a340260a8f01855e + `references/plan-contract.md` 0c708e50b07eb3fe（另有 travel/express/rd-materials 三类型分则） |
| A7 | task-registry 现状 | 7 个 `*.form.json`；无 SAVE_INTENT/SAVE_UNCERTAIN/保存成功记录——本轮不触碰、只读核实语义保持 |
| A8 | 上轮提速与内层观测交付在盘 | `docs/路线与评估/2026-10-23-round2-死等消除与内层观测-前后对照.md` + `recalc_timeline.py` + attempt_026 工件（按冻结范围承接，不重做） |

## B. 差距项（=后续工作包输入，本轮 W02 处理 B1/B2）

| # | 差距 | 影响 | 归属 |
|---|---|---|---|
| B1 | 材料 manifest v1.0 单 root：`validate_image_documents` 要求提取 JSON 与原件同清单，而 `prepare_materials` 强制输出在 root 之外（`fill_once.py:106` 输出到 run/materials）——派生复核 JSON 无法合法存在 | PDF/图片发票链路在「原件只读 + 派生输出」约束下无法闭合；任务书 §5.1 结构矛盾 | **W02（本轮）** |
| B2 | `validate_value_proof` 的 `proof.get("kind","user")` 静默默认 user——agent 推断可伪装成用户确认 | 来源语义不实；任务书 §5.4 红线 | **W02（本轮）** |
| B3 | `--task` 准备返回 NEEDS_INPUT 后，原件→事实→对账→计划的链路需 agent 手工拼接，无内部阶段状态区分 | 用户仍需等待 agent 手工生成计划 | W03/W04/W05 |
| B4 | PDF/图片提取要求外部另给复核 JSON；agent 自提取/自复核/缺口定位未建 | 用户或人工步骤仍承担 OCR 复核 | W03 |
| B5 | 其余五类（低值办公/福利劳保/其他/维修/会议）未注册未建模 | 八类覆盖缺 5 类 | W07/W08 |
| B6 | 三类均无「本次原始资料→真实填写」第三层端到端证据（现有为第二层回放） | 最终工作方式未验收 | W06（每类一笔） |
| B7 | 新 session 独立使用验收未做 | 完成定义第 1 条未验 | W10 |
| B8 | 上轮挂账：P2-1 header status="None" 字符串瑕疵、P2-2 recalc _ln 死字段、P2-3 工件 git commit（用户侧遗留决策）、P2-4 legacy 旧 token 键名清理（权限类，人工） | 非阻断 | PENDING_HUMAN_NONBLOCKING / 后续轮候选 |

## C. 结论

任务书 §3 差距表与本仓库 2026-10-24 实际状态一致：三类执行/回放/离线/提速均按其冻结范围成立（A1-A8），原始资料驱动主线（B1-B7）为真实缺口。本轮 W02 只处理 B1/B2（结构矛盾 + 来源语义），其余差距按工作包归属推进。
