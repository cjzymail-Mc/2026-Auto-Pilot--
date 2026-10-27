# Round-08 A 独立验收（B6 独立复核 + CASE-08 新 session 使用验收 + B7 终局标记 + §12.3 最终交付）——终局轮

- A session：`0cbc12a4-0aa0-4f70-acee-a054cbedf5a0`｜run `d91601924848489f84e317e68582de26`｜round 8｜B 交接 seq 40
- A 独立复算（本目录 `hash-recheck.json`）：基线/清单 sha256 连续第 8 轮逐字匹配；18/18 交接哈希全中；73 原件第 8 轮零漂移；凭证 grep 唯一命中为 MC-FINAL 政策性提及（JWT 形 token 0 个）。

## 一、B6 独立复核（D17-B6；供 D01/D11/D18/D26）

- 报告为全新 mc-expert 实例（零上下文继承）**逐字落盘**，B 未改写；七面全部**从原始证据独立重算**而非摘要互证：①73 原件逐件 sha256 对账 73/73；②不采信 facts 分类、从 raw OCR 按 y 带聚簇独立抽取票面得 T=486.93/O=2031.17；③openpyxl 双通道独立读副本（H4:H23 20 值全对、I 列公式保持、原件 src_sha_before==after）；④**13 张公出单从 attempt_011 api-detail 原始 body 重建覆盖日独立重判**：MATCHED=12 Σ221.02 / NO_MATCH=15 Σ265.91，与 CASE-03 报告 0 diff；⑤170 源逐项分类（template 14 仅身份/收款/预算，禁入类 0 命中）；⑥计划四向闭合 Decimal 逐行复算；⑦v1.1 深度 diff 14 叶路径全落 9 簇 + 种子链本地重放（string-seed→6→12024070132）；⑧B5 回读从原始 DOM 行数组重算（金额四向 1924.93、12 张真实单号泄露数 0、relations.description 判定为系统带出且有事件轨迹佐证）。VERDICT=**CONSISTENT**，8 条观察均如实且不构成差异（含 I24 浮点尾差、travel.md 工作树漂移以 manifest 执行时哈希为准的口径）。

## 二、CASE-08 新 session 使用验收（D19）

- **白名单先验可审计**：`case08-input-manifest.md` mtime 19:26:23 先于 agent 全部产物（machine-parse 22:00/fill-plan 22:17）；允许输入恰 5 项（冻结合同/skill+references/模板号 15426095951/73 原件目录/合同自带规则），禁读清单明确；比对用交付物在阶段一回报后才提供（input-log #19–22）。
- **独立重建**：零上下文 session 自建 task → 自有 `--task` run `20261026-193100-0527f5dc`（79 文件，A 实查存在）→ census 缓存定向读模板 → 72 PDF PyMuPDF 机读主通道+视觉交叉 → 独立复算 K=1438/M=1438.00/T=486.93/R=1924.93/O=2031.17/F=2518.10/margin=593.17、52 唯一身份、1210 两票、0904=16104706 定案（A 抽验 fact-recompute.json 全部数值与交付链吻合）→ 自有 v1.0（canonical ec2c811b…）`--validate-only` **PLAN_VALIDATED**（A 复核 validate-output.txt）。
- **四面对比**核心全 CONSISTENT（27 票号集合逐张全等、R/coverage/banks/身份、B5 回读、CASE-03 Σ闭合）；3 项非金额差异（码 vs 显示名/证据深度/建模粒度）如实且不涉金额与安全边界。
- **纪律**：3 次视觉读票幻觉被"机读+汇总单互证"双通道纠出；429 用量中断如实记录、定时恢复**同一 agent 上下文**（零上下文边界保持，B 未代做）；P2（input-log"registry 未查询"与 #10 矛盾 + 报告过度声明）经 mc-expert 终审触发**加法订正**——订正链 A 逐行核对：registry 11 件表单经 B 与 mc-expert 双重实查仅任务身份元数据（operator=陈晶 为旧 demo 字段），无本案金额/票号/结论，不构成污染；零业务写入（模板走 census 缓存，浏览器零动作）。
- skill 可操作性 6 发现：4 项文档补丁落地（A 内容抽验：travel.md 含 oa_test_relations 生成路径+seed 字符串注记、SKILL.md 机读优先、plan-contract.md corpCode/applicant sources），1 项行为建议转观察、1 项非缺口——session 在补丁前已凭现行 skill 走通，补丁为经验固化，无需重试。

## 三、B7 终局标记与交付（D17-B7/D24）

- 台账 V3-R08 `b7_terminal_marker=B7_TERMINAL_V3_CASE_COMPLETE`：fill_only 完成（层次=真实控件已验证·填写+回读·未保存）、未保存证据（NOT_ATTEMPTED/编制中/无单号/无 UUID/干净关闭）、保存类点击 0（6/7/8 轮合计）、旧单未改未释放、12026096668 未重占、registry 仅 FORM_INTENT、**not_claimed 明示不宣称重新报销成功**。
- `final-manifest.json`（sha a8ac7147… 与 events `final_manifest_built` 绑定一致）：**A 逐项验证 24/24 path 存在且 sha256 相符，0 bad 0 missing**，8 区结构覆盖 §12.3 全项（含 handoff-input.json 定稿版）；构建于 handoff 定稿后并回读确认（P3-2 前向引用闭环）。
- `用户报告.md`：类别/模板/三员、K/M/T/R/O/F/margin 表、12 匹配单号+15 无匹配逐票摘要、fill_only 状态与占位分离、B6/CASE-08 摘要、证据索引、剩余观察——**不宣称重新报销成功**，A 通读无越权表述。

## 四、零改动与零写入核实

- 源码/schema/测试零改动：A 以 mtime 扫描（核心 .py/schema 全部早于 round-8 窗口 19:24–22:53；bpm_plan.py 18:12/schema 18:13 为 round-7 既有）+ 与 round-7 handoff 绑定哈希交叉（唯一差异 progress.json 为声明改动）；docs-only 改动按任务条款不新增构建，materials-v3r07 OFFLINE_PASS 沿用。
- 本轮 events 11 条零保存类事件；唯一浏览器动作 19:29:16 login60 只读探查（run 目录实查存在）；73 原件零漂移；失败字典 {D23:1, D22:1} 原样带入（均已闭环，计数为历史）。

## 五、判据终局签核（27/27）

- **D01 PASS_DYNAMIC**：全链各阶段产物均 agent 生成（r02–r08 工件链），用户输入仅模板单号+原件+规则；CASE-08 反向证明仅凭该输入可走通全链；未出现要求用户编写内部 JSON 的停等。
- **D11 PASS_DYNAMIC**：§6 正式路径连续衔接（门槛先于写入已验 r07；正式入口 fill_once/bpm_plan/bpm_template/bpm_ui/bpm_verify 全链复用）；skill 经 4+1 文档补丁覆盖"真实 PDF/Excel→模板→计划→填写→回读→交付"完整操作，机读优先与占位生成路径入文档；回放 JSON CLI 非最终用户入口。
- **D17 PASS_DYNAMIC**：B1（r06/r07 登录+三员核实+模板身份）、B2（r04 逐票查询/详情/对照）、B3（r07 类别/预算/银行联动+占位单独标记）、B4（r07 全行真实填写+events+终局截图）、B5（r07 新鲜 DOM 全量回读）、**B6（本轮全量独立复核 CONSISTENT）**、**B7（本轮终局标记+页面状态交接）**——七关全部实证据落盘。
- **D18 PASS_DYNAMIC**：A1–A9 逐条随专项证据翻转（A1 输入纯度、A2 理解+来源哈希、A3 回填+重算、A4 覆盖+逐票、A5 正式填写+分离核验、A6 独立核对无未解差异、A7 B6 独立复核、A8 身份+未保存+无旧单修改、A9 交付齐全）。
- **D19 PASS_DYNAMIC**：CASE-08 按合同完成——白名单先验、独立理解/复算/自有计划/validate-only 全绿、已完成填写分支只读核验、不重复新建/不绕 registry/不改旧单；新 session 使用验收在本案例范围内完成。
- **D24 PASS_DYNAMIC**：§12.3 最低交付物 24 项 manifest 逐项哈希绑定（A 24/24 复核）+ 用户报告 + 每轮交接（r01–r08 handoff 齐全）。
- **D26 PASS_DYNAMIC**：完成定义整体核签——原件独立理解✓、回填与重算 R 正确✓、F=2518.10>R=1924.93 严格✓、逐票对照完整✓、占位按合同绑定✓、模板/身份准确✓、正式入口全部写入✓、B1–B7/A1–A9 全过✓、交付齐全✓、零保存/零提交/零旧单修改/零重占✓；无"拒绝行为正确"替代情形（门槛实过）；七类扩展未进入本轮 criteria；不冒称、不自动加轮。

## 六、结论

round-8 以只读/离线方式收口全部剩余判据，B6 七面独立复核与 CASE-08 双独立会话收敛为终局提供最强证据；红线（零保存、零业务写入、凭证隔离、registry 只读、原件零漂移）全程保持。27/27 全 PASS_DYNAMIC，decision=**pass**。
