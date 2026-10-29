# A 独立验收记录（round 1，2026-10-28）

验收人：A（session aa74f509-c035-472c-8cbc-5cbf1e5341a4）。基线：`feature02-扩展更多单据类型/2026-10-28 单会话贯通执行与日常自动保存接线施工计划.md`（sha256 `6b442f26…`，验收前重算一致）。criteria 16 项（C01—C13＋D14/D15/D16，`criteria-input.json` sha256 `02f24af4…`）。

## 本轮新增/重验（全部 A 一手执行）

1. **基线与产物绑定**：基线文档验收前重算 sha256 一致；handoff 21 项产物逐项实算 sha256 全部匹配（脚本批量核对，ALL_MATCH）。
2. **独立复跑统一离线验收**：`python -X utf8 verify_bpm_build.py` → **OFFLINE_PASS**，probe-selftest 4.454s exit 0，capability-tests 491 项 242.957s exit 0（日志尾 `Ran 491 tests in 242.273s / OK (skipped=4)`），产物 `automation/offline-verify/20261028-153836-draft-build/`；其 build_result.json `real_fill_verified=false`、`real_save_verified=false`、`missing_real_inputs=[exact_history_template_number, current_material_directory]` 与 B 声明一致。
3. **代码实物走读**（非仅采信 B 报告）：
   - `bpm/oneshot.py`：`--task`/`--fill-plan` 互斥组；任务分支顺序＝离线校验→journal 门（新开 run 子路径，:462-472，四状态阻断 exit 2）→`TaskBranchProbe.pending_task_prepare`（身份确认后、填写前）内 live 模板→`complete_from_live_snapshot`（模板值仅取本次快照，TEMPLATE_VALUE_PRE_SUPPLIED/TEMPLATE_PRE_FROZEN/SNAPSHOT_FIELD_MISSING/TEMPLATE_NUMBER_CONFLICT 结构化缺口）→`compile_authorization` 三分支（synthetic/test_context 强制 fill_only；declared fill_only；save_draft 需结构化 save_basis，standing_policy 白名单 A1，越界 UNKNOWN_STANDING_POLICY）→生成→冻结（`authorization_record.json` 四绑定、独立落盘无自引用）→`verify_record_bindings`→`bind_final_plan`；`allow_submit` 恒 False（:138）；G2.5 resume 复用冻结产物不重读模板；`--validate-only` 两分支均不启动浏览器；`_protected` 拒绝 .pw-profile/.git/legacy-ia2 路径。
   - `bpm/browser_probe.py`：`NO_SAVE_WORDS` 十四词全禁令与 `_click_guard` 原样；600ms 轮询保留（:1619-1620/:1985/:2056）；`SESSION_TTL=30天`；main() finally 时序＝atomic_result→probe_end→`_deliver_and_park`（result_delivered 先发布、wall_cap 驻留扩容、park 后 `_close_browser`→`release_lock`，锁覆盖驻留期）；prepare 挂钩在 entry_ok 后调用（:3191-3208）。
   - `bpm/ui.py`：`open_verification_page`（同 context `ctx.new_page()`、二次开拒绝、page_role=verification 事件）；`close_verification_page`（finally 关自有副页）；`_readback_page`（副页存活期路由副页、显式 page 优先）；`capture_snapshot` 每次实读无缓存。
   - `bpm/save.py`：点击前 config 哈希复核、`click_exact_save`、`_reconcile` 不确定性不回流点击；finally 关副页。
4. **守卫与文档不变项**：AGENTS.md 红线 1 逐字未动（与会话开始版本比对），仅正常入口节增加 oneshot 指针（:52）；SKILL.md（:46/:55/:64/:88/:102）、common-operations.md（:65-91）、full-chain.md（:3/:5/:29）、repository-layout.md（:34）、STATE.md、travel/express/rd-materials 手册均登记且统一标注"实现＋离线验证；真实填写/保存待验"；P2-1 限定措辞（journal 预检仅任务分支新开 run）各文档一致；purchased-samples 待补口径与自驾缺口保留。
5. **范围核查（D14）**：工作树改动均在合同允许清单内；`bpm/chain.py`、`bpm/session.py`、workflow helper、tools/ 未动；`tests/test_bpm_template.py` 仅 1 行 fake 签名补 `page=None`（配合 template.py 显式 page 参数，属 tests 允许范围）；.gitignore 增项为前轮（2026-10-27）敏感观测本地忽略，非本轮引入。无自驾恢复、无常驻服务、无控件等待改动、无回读缓存、无 chain 扩建。
6. **测试结构**：`tests/test_bpm_oneshot.py` 33 项直接用例（授权编译 6/schema 3/模板补全 5/授权记录 2/CLI 5/任务分支 DOM 链 2/副页 3/交付驻留 7）＋`VerificationSidePageDOMTests` 继承 `test_bpm_ui.DOMTests` 28 项；任务分支链为真 headless Chromium 全链（含 G2.5 复用不重读模板断言 :580-593、TEMPLATE_PRE_FROZEN 负例 :595-602）。
7. **过程工件**：两次 OFFLINE_FAILED（20261028-135040/135848，测试基建缺陷）与中间 484 项 PASS（20261028-141210）均保留，演进 511→484→491 与记录叙述吻合。

## 有效旧证据

- G4 基线 `automation/runs/20261027-074251-9d71443f/events.jsonl`（2026-10-27，20 行费用 SUCCESS_FILL_ONLY fill-plan 直填链）：本轮用作基线引用（307.8s 技术耗时等），B 一手复核数值；适用性＝仅作不可比同口径参考（缺任务分支全链与材料理解计时），结果记录已如实标"提速待测"，不作生产提速实证。
- 既有 458 项回归（前轮 430＋本轮新增）中覆盖的中断状态、恢复边界、click_guard、Decimal 闭合等用例随本轮 491 全量由 A 复跑确认为绿。

## 未解项

- **真实首验/真实保存待验（C12 条件分支，非缺陷）**：本会话无用户当次真实业务输入（完整模板单号＋本次材料＋执行意图三项缺口集中列于施工结果记录）。按基线 §5.5/§8，结论为"实现及离线完成，真实保存待验"，B 未冒充真实验收。续作入口：`feature02-扩展更多单据类型/2026-10-28 oneshot真实首验接续计划.md`。
- **B 自报非阻断残留（不构成基线缺口）**：`--fill-plan`/`--resume-run` 的浏览器前 journal 预检与 lifecycle 计数逐 run 实测派生，留待下次代码触碰（终审 P2 已按最小修复收口文档表述，代码行为与 legacy 无倒退；基线未要求该两分支浏览器前预检）。

## 逐项判定

| ID | 判定 | 依据（本轮 A 一手） |
|---|---|---|
| C01 | PASS_DYNAMIC | 代码走读＋两分支互斥/顺序核实；TaskBranchChainDOMTests 真浏览器全链；旧命令三行保留于 AGENTS.md:45-48；491 回归含旧行为；无全场景理解宣称 |
| C02 | PASS_DYNAMIC | TaskBranchProbe 复用 Probe.main 生命周期；template.py 显式 page 参数（正式接口）；锁 finally 释放且覆盖驻留；DeliveryAndParkTests 锁序列 3 项 |
| C03 | PASS_DYNAMIC | result_delivered 生命周期计数事件＋离线断言（test:711）；fresh_scan 动态位；按构造声明值已如实标注、逐 run 实测随 C12（基线 G4.1 钩子真实首验时生效） |
| C04 | PASS_DYNAMIC | compile_authorization 三分支代码＋6 测试；四绑定无自引用（test:381）；漂移拒绝（test:398）；G2.5 复用不重读模板（test:580-593） |
| C05 | PASS_DYNAMIC | save.py 新鲜复核链原样（仅加 finally 关副页）；journal 门（:462-472）＋test:449；SaveController 在途只读核实保留 |
| C06 | PASS_DYNAMIC | capture_snapshot 每次实读；链测试 capture→verify_snapshot 全量通过（test:577-579）；Decimal 三向闭合随 491 回归 |
| C07 | PASS_DYNAMIC | 无回读缓存（代码核实）；状态表语义保留（WAIT_HUMAN_LOGIN 保留 test:736、prepare 缺口不驻留快释放 test:728、--resume-run 绑定不同即拒 :452-453）；人工/异步反例随既有回归绿 |
| C08 | PASS_DYNAMIC | ui.py 副页三方法代码＋VerificationSidePageDOMTests 3 项（副页路由主 tab type=new 保持、保存链 finally 关副页、二次开拒绝） |
| C09 | PASS_DYNAMIC | _deliver_and_park 时序代码＋DeliveryAndParkTests 7 项（先发布后驻留、零驻留、早退/期满、占用拒绝、release 只删自身 pid） |
| C10 | PASS_DYNAMIC | 红线 1 逐字未动；NO_SAVE_WORDS 十四词/_click_guard/SESSION_TTL 30 天原样；_protected 守卫＋产物哈希核对无凭证外泄；他人页面保护随回归 |
| C11 | PASS_DYNAMIC | **A 独立复跑 OFFLINE_PASS**（20261028-153836-draft-build：selftest 4.454s＋491 项 242.957s OK skipped=4）；过程工件保留；browser_probe 改动后 selftest 先绿 |
| C12 | PASS_DYNAMIC | 无真实输入分支成立：三项缺口集中列出（结果记录 §真实输入缺口＋build_result missing_real_inputs）；G4 基线一手复核＋钩子就位；提速如实标待测；无历史占位冒充、无整体真实验收宣称 |
| C13 | PASS_DYNAMIC | 六文档＋三手册同步核实（统一状态标注）；自驾/外购样品缺口保留；单份结果记录 C01—C13 逐项＋证据入口；STATE 符合快照标准；无凭证/银行信息复制 |
| D14 | PASS_DYNAMIC | git 改动清单核对：chain.py/session.py/workflow helper/tools 未动；无范围外施工与承诺；test_bpm_template.py 1 行属允许 tests 范围 |
| D15 | PASS_DYNAMIC | browser_probe 窄改（prepare 钩子＋result_delivered＋_deliver_and_park 抽取，行为不变注释）；600ms 轮询/Tab 失焦/重复回读保留；selftest 全绿（A 复跑 4.454s）；无 monkeypatch |
| D16 | PASS_DYNAMIC | 进度记录无对已定策略的重复征询；PENDING_HUMAN_NONBLOCKING 空；缺口集中单列；计划文档非保存授权（save_basis/journal 门代码强制） |

结论：16/16 PASS_DYNAMIC；B 合法完成（COMPLETE＋P6✓，failure_counts 空）；C12 按基线自身条件分支通过（真实首验待用户输入，非缺陷）。
