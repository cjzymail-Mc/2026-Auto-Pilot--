# STATE.md — 当前接手快照

最后核对：2026-10-27（另行授权的仓库归类整理完成，根文件 43→21，离线验证通过：399 项中 395 通过、4 项既有跳过；原自驾施工 workflow 仍为 CANCELLED，业务最终终审未做）。  
维护标准见 [AGENTS.md](AGENTS.md#文档分工与-statemd-维护标准)：替换旧结论、近期结果最多 3 项、目标 40—60 行，详细过程留原工件。

## 当前工作与下一步

- [自驾公出技能固化施工合同 V1](feature01-细化报销skill/2026-10-27%20报销单-自驾公出类技能固化施工合同-V1.md)（BPM-SELFDRIVE-20261027-V1）workflow run `242ccba1c43343f687aa1db0ae014f5b` round 2（合同 ctr-2433e4a3）：**用户 2026-10-27 指令"先暂停施工，完成 skill 搭建即可"→ A 发 stop、B 检查点收束后 pause 确认，run 已按状态机转入 CANCELLED（终态）。R2 未 finish、不宣称 DONE；resume 不适用于 CANCELLED**。
- Skill 搭建后，已按用户另行指令完成仓库归类整理：实现归入 `bpm/`，工具归入 `tools/`，保留七个根命令兼容入口。见 [目录与旧路径映射](docs/repository-layout.md)、[整理验收结果](automation/maintenance/20261027-repo-layout/result.json)。原自驾施工继续暂停，未重新启动 workflow，也未填写或保存 OA。
- 续作方式（用户明确启动完整施工新任务后）：原窗口按合法流程 `archive` 并核对已归档任务字节，再准备新 run；不自动恢复 CANCELLED。R2 [暂停点 manifest](automation/runs/20261027-121733-cb8b9bd6/artifact-manifest-r2fix2.txt)保留历史；此后另有 Skill 文档和仓库目录修订，源码及部分类型解析器哈希已变。恢复时须按新路径比对并重冻当前哈希，再做 fresh ENHANCED_FINAL、P6 收尾和独立验收，不能改旧计划/registry/manifest 绕过漂移。
- 未完成工程：含餐补计划与来源绑定、A1 同任务自动保存授权接线、真实公出匹配/统计 MD、Excel 回填与重算、正式整链和 D12 冷启动；完成后再更新手册能力状态。首次审计 P2-1/P2-2/P2-3 及旧失败历史继续保留。
- U1—U5 说明升级已安装，helper/状态机未改；孤儿恢复仍交外部 agent，见 [U6 指南](feature01-细化报销skill/team-workflow升级建议.md#u6外部-agent-维护保留精简指南框架)。

## 最近已证实的结果

1. **10 月 27 日 R2 主体+窄审修复离线全绿（含修复后新鲜验证）。**D02 30 天迁移（REUSE_DAYS=30、旧记录收紧 min(原窗口,扫码+30d)）；D04 识票归集 `bpm_collect.py`（73 原件只读→32 身份 27 通行费 Σ486.93+5 油票、GAP=0、汇总单互证 10/10、幂等防覆盖、72 规范副本，与人工对照表逐日一致差异 0）；D3 下游多 record；P2-2/P2-3 机制化清污；§2(4) 纠正+[D5 记录](automation/runs/20261027-121733-cb8b9bd6/d5-capability-layers-correction.md)+`bpm_identity.py`+task.schema 身份关系字段。**Codex 两轮窄审反例（写回滚动 24h/坏 meta 拒绝不一致/删键降级链）全部隔离验证成立并修复**：persist_state 锚点保持+覆盖前拒绝、_meta_valid 三处统一；修复后 394 tests OK exit=0 + OFFLINE_PASS（offline-verify/20261027-121733-cb8b9bd6-r2fix2/）。零业务写入、73 原件零漂移。证据：`automation/runs/20261027-121733-cb8b9bd6/`（events 全链）。
2. **10 月 27 日 Skill 文档搭建及后续仓库归类整理完成。**[早先 Skill-only 结果](automation/runs/20261027-skill-scaffold/result.json)保留文档校验与独立情景复核历史；现行目录见上方整理结果。29 个文件迁移、七入口兼容，399 项测试中 395 通过、4 项既有跳过；独立静态复核及守卫 AST 比对完成。手册固化与目录整理均不代表自驾整链、D12 或真实填写/保存验收完成。
3. **10 月 27 日样本逐项核算完成（R1 落地）。**self_drive 规则/模型/§6.1 反例全过；09-05/09-28 差异与日期问题见 [逐项核算](automation/runs/20261027-sample15425123013-live/逐项金额核算.md)。30 元/日餐补 300、总额 2224.93 为离线对照值（只进测试不进生产路由）。

## 业务范围与验收边界

- [BPM-SELFDRIVE-20261027-V1](feature01-细化报销skill/2026-10-27%20报销单-自驾公出类技能固化施工合同-V1.md)仍是未完成工程基线，当前仅完成用户要求的 Skill 文档收尾；旧 [V3 合同](feature01-细化报销skill/2026-10-26%20真实公出案例独立解析与OA填写施工合同-冻结V3.md)及原件、历史证据只读。
- 金额双模型并存：旧 `fuel_pool_strict_surplus` 零改动；新 `self_drive_strict_surplus_v1` 须绑定 self_drive.json 版本与哈希、生产调用显式 `rules=`，历史餐补值传入即拒。油票只作覆盖不加报，汇总单不重复计费。
- 身份关系：登录操作人/新页制单人/费用所属人分开记录；角色未知、预期不符、制单人未成立均按 NEEDS_INPUT 缺口，不换人凑对照值、不默认零餐补。
- 会话写回纪律（本轮窄审固化）：真旧无 meta 文件写回保留原 mtime（24h 锚不滚动）；坏 meta（坏 schema/缺标识/显式 null）读取/复制/写回三处统一拒绝，非扫码覆盖前拒绝并保持原字节；真实新扫码合规重建不受影响。

## 恢复入口与当次必查

- workflow 状态：run `242ccba1…` 已 CANCELLED（用户暂停，13:11 B 检查点确认），不代表工程 DONE。不能由终态推断交互 session 进程已退出或历史业务页已关闭；后续仍现场核实执行者、waiter、锁、registry 和页面，勿杀进程或强关旧页。续作按上方合法新任务入口；旧 V3 run 已 archive。
- `20261027-074251-9d71443f` 为 SUCCESS_FILL_ONLY，用户自述已手动保存、agent 未核实，registry 仍按只填不存记录。
- 新业务执行前重新核实 profile 锁、业务 registry、未保存页和当前身份（11:20:45 探查为陈晶 authenticated，effective_reuse_until 2026-11-23，以当次探查为准）。本地复用上限现行为 30 天（D02 已实施；旧 60 天记录自动收紧）。
- 历史登录复用证据见 [10 月 24 日验证 run](automation/runs/20261024-104301-login60/)；它不证明现在仍有效。

## 按需深入

- R2 工件：`automation/runs/20261027-121733-cb8b9bd6/`（collect/ 归集产物、p2-3 复扫、D5 记录、r2fix-isolated-verification、两份 manifest、events 全链）；离线构建三目录（385/392/394 历史快照，r2fix2 为现行）。R1 工件：`automation/runs/20261027-111853-f2789e00/`。
- V3 独立验收与证据清单：[A-verification.md](team-progress/team-workflow/d91601924848489f84e317e68582de26/round-08/acceptance/A-verification.md)、[final-manifest.json](automation/runs/20261026-192400-v3r08-final/final-manifest.json)。
- 日常业务入口：[bpm-fill-run](.claude/skills/bpm-fill-run/SKILL.md)；操作规则与维护标准：[AGENTS.md](AGENTS.md)。下一阶段更新本快照时替换过期条目，不在末尾追加工作日志。
