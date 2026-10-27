<!-- team-task-source id="src-3e99d777" sha256="3e99d777e64c4fadbd31c60354dcfed7dbeec59247fc5a871ee033893dc876b2" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 9
failure_counts: {"review|content|source_manifest_coverage|D23": 1}

<!-- round: 9 -->
# 本次任务：五类接入施工首件放量（02/04 config→封闭注册→离线链）+ D18 离线矩阵补行 + D22 验收方案准备

背景（自足）：Round-8 已完成三类真实闭环（travel r7 / express r8 / rd r8，均 SUCCESS_FILL_ONLY+独立回读零差异）、P1-a 追认关闭、五类研究 4/5（七类码 08/11/15/02/04/01/24 实测互异）、`code-adaptation-prep-02-04.md` 9 落点映射就绪。A 验收 20 PASS / 1 BLOCKED / 6 FAIL；D19 已翻 PASS_DYNAMIC。真实发票原件（D4）与三类"本次原始材料"（D11/D20）为用户供料依赖，已登记不阻塞。06 会议支出 census 0 候选，待用户供号。

## 待做条款

### 1. 写授权增补（本轮合同新增，先声明）
- 授权写入：`bpm_types.py`（封闭注册扩展）、`automation/document-types/*.json`（低值办公 02 / 福利劳保 04 新 config 文件）、对应 `tests/`。
- 授权依据：冻结任务书 §8.2 五类接入循环 + round-8 `code-adaptation-prep-02-04.md` A 表第 1-2 级（config 落盘→封闭注册→离线链）。
- **边界**：新增 JSON 不自动启用类型（D12 明文）；本轮注册为**离线链可用**，不授权 02/04 真实页面控件测试、不注册业务填写路径、不在真实 OA 创建 02/04 新页——真实控件测试待离线全绿后下一轮按结果另行授权。

### 2. 02 低值办公 / 04 福利劳保 接入首件（主靶，按 A 表 1-2 级）
- 按研究工件（research_dijiazhi_15426101596.md / research_fulilabao_15426071883.md）实测结构落 config：主/子表字段与编辑类型、submitType/类型码（02/04，实测证据指针随件）、reimItem 前缀模式（02001/04003）、detailrels 形态（02 非零绑定 / 04 零金额）、banks 分摊闭合规则、invoice=false 文档级免票通道。
- `bpm_types.py` 封闭注册两个新类型（类型名/码/表集合/amount_rules/空表适用性），schema 校验、行数组、选择器契约与三类同构。
- 离线链验证：合成材料（明示 synthetic，不入业务 manifest）→ 提取→FactSet→reconcile→复用矩阵→blueprint→generate_fill_plan→validate_plan 零 issues→**validate-only 子进程 exit 0**（不开真实页面）。
- 每类至少 3 个离线单测（注册/校验/链路）；差异说明落 `automation/document-types/<type>.notes.md`（与研究工件的差异对照）。

### 3. D18 离线矩阵补行（≥4 个新测试）
- PDF/图片变体：多页 PDF 逐页锚点、一页多票拒绝/拆分策略（合成件，明示测试用）。
- Excel 变体：多 sheet、公式单元格取值、汇总/明细并存、隐藏行/筛选态（合成 xlsx）。
- 数值保真：前导零票号/账号、长账号、金额 Decimal 精度（0.005 级）在提取→事实→计划三段不丢。
- 已有反例不回归；每行测试对应矩阵条目在注释/文档中标注。

### 4. D22 新 session 使用验收——方案准备（不实施）
- 产出 `automation/offline-verify/d22-acceptance-plan-<时间戳>/D22_plan.md`：验收范围（新 session 从登录探查到填写交付的哪些环节）、入口清单与所需参数、证据要求、判定标准、当前入口缺口（若 probe/入口需改动，列出改动点但**不实施**——改动另行授权）。
- 目的：W10 前置方案，供 A/用户审后下轮授权实施。

### 5. mc-expert 三条观察处置（小）
- 链 events 双前缀单例化（chain 重跑时旧前缀清理或显式分段标记，不破坏 append-only 语义的可选方案落地其一）。
- research events 键名消歧（authorization 字样仅键名无值——改名）。
- no-residue 原始布尔与终判布尔命名消歧。

## 保留项与边界
- fill_only；不测保存、不验收保存成功；SaveController/守卫/registry/legacy 原样；本轮**不触碰真实 OA 页面**（除登录探查例行的只读身份核验外零导航零点击）。
- 合成材料仅测试用、明示标注、不入业务 manifest、不虚构业务。
- 探针/入口文件（stage1_browser_probe.py/fill_once.py）本轮零改动；`bpm_plan_generate.py`/`bpm_ui.py` 常设清单内最小改动+测试+留痕；其他新文件先停-增补-再写。
- 单 profile 单执行者；不自动 commit。

## 验证
- 全量 `python -X utf8 -m unittest discover -s tests` 全绿（含 ≥10 新测试）；`verify_bpm_build.py --run template-materials-<时间戳>` 唯一 run PASS（source_manifest 自动冻结新文件）。
- 02/04 离线链 validate-only 双双 exit 0；config 与研究工件差异对照齐备。
- D22 方案工件落盘；三条观察处置留痕。

## done_when
1. 02/04 config+封闭注册+离线链走通（validate-only exit 0，零真实页面动作），每类 ≥3 单测。
2. D18 ≥4 个新离线矩阵测试落盘全绿并标注矩阵条目。
3. D22 验收方案工件落盘（含入口缺口清单，不实施改动）。
4. 三条 mc-expert 观察处置完毕。
5. 全量测试全绿 + 唯一 run OFFLINE_PASS + skill 轮末快照。
6. 交接齐备：改动+哈希、新文件清单、台账 W07/W08 更新、下一轮入口（02/04 真实控件测试授权申请 或 D22 实施）。
<!-- /team-task-source -->
