<!-- team-task-source id="src-20e40597" sha256="20e405971acafa5544c47bd3d7338e81e2514c164bdb67cc0da2c7e87173f38d" status="open" -->
workflow_run: a7618f4fa0b040fa81782c93eb1bc926
workflow_round: 2
failure_counts: {}

<!-- round: 2 -->
# 本次任务：报销材料主线 W03 —— 原件理解（PDF/图片/Excel 提取复核 + 语义盘点 + 缺口登记）

总目标背景（自足）：本程序多轮交付"用户仅给完整模板单号+本次原始资料（PDF/图片/Excel），agent 自行提取复核→事实→对账→计划→真实填写→独立回读验收"。Round-1 已交付 W00 总台账（`automation/template-materials-program/progress.json`，唯一权威）与 W02 原件/派生双根契约（`bpm_materials.py`：`prepare_dual_materials`/`register_derived`/`validate_dual_manifest`/`dual_hash_sets`，manifest v2.0，role 封闭枚举 parsed_extraction/reviewed_extraction/ocr_result/render/run_evidence，来源 kind 含 agent_reviewed，禁止 agent 推断伪装 kind=user）。本轮按主线优先做 W03：让 agent 能自行理解原件并产出真实复核记录，用户不再需要提供 OCR 复核 JSON。本轮仍全部离线，不连 OA、不做浏览器操作。

验收口径继承：只填不存，不测保存按钮；守卫/SaveController/registry 原样；不虚构实单；缺真实业务材料时用合成测试材料推进并如实登记缺口，不以缺材料为由停工。

## 待做条款

### 1. PDF/图片提取与真实复核（主线核心）
- 文本 PDF：提取文本并保留版面定位（页码/区域/坐标或等价锚点），产出结构化事实：票据身份（发票号/代码）、开票日期、开票主体、价税合计，以及费用行所需项目/明细/金额；明确区分税前金额、税额、应付总额。
- 扫描件/图片：本地渲染 + 本环境可用的视觉/OCR 能力；OCR 原始输出以 role=ocr_result 落派生根，经复核后的事实以 role=reviewed_extraction 落派生根；两层不得混写。
- 所有派生产物一律经 `register_derived` 写入派生根并绑定原件 sha256（sources=原件哈希），`generated_by` 记录 agent/工具、`generated_at` 时间、复核方式；关键值（票号/金额/日期/账号）复核必须回到原页/原区域对照，复核记录留证。
- `reviewed=true` 仅表示实际执行的复核过程，不得把 OCR 裸输出直接标为已复核。
- 不得上传原件到任何第三方 OCR/云端服务；只用本地能力。
- 优先复用仓库现有依赖（openpyxl 等已在用）；确需新增 PDF/OCR 库时在交接清单列明用途与版本，不引入无调用者的重框架。

### 2. Excel/CSV 语义解析
- 识别工作表、表头、正文、合计、小计、备注、隐藏数据与筛选行、重复统计范围；不默认第一张表/第一列是费用明细。
- 保留 `工作表!单元格` 或 CSV 行列定位贯穿到派生事实。
- 前导零与长票号/账号/运单号一律字符串原值；原文件已丢精度的编号不得补零修复（登记缺口）。
- 公式单元格取可靠缓存值或经本地重算/公式复核；不得拿公式文本当金额。
- 禁止"每个非空行生成一条报销费用"机械转换：区分统计合计与明细是否同一费用、跨 sheet/跨文件重复、隐藏/筛选行是否在范围内（数量相同金额相同≠重复业务，仅提示待对账）。

### 3. 语义类别盘点（补 Round-1 D3 尾款）
- 在双根 manifest 盘点基础上按内容哈希给出原件语义分类：原件/重复副本/统计表/发票/结算凭据/说明及其他相关材料。
- 文件名不得单独作为类别或发票身份证据；分类须给内容依据（如版面特征/关键词/表结构），不确定的标"待定"并说明，不硬猜。

### 4. 缺口登记结构
- 关键值不清晰（模糊字符、丢精度、多候选）时产出结构化缺口：文件、页码/单元格、区域、候选值或不确定原因、受影响费用行；清晰文件继续处理，不因个别缺口中断整批。

### 5. 顺手项（小改，不扩大范围）
- R2-P1（原 P2-1）：`register_derived` 中 `derived_root` 直接取 manifest 原值解析（L245），与 `validate_dual_manifest(base_dir=manifest_path.parent)`（L233）不一致——相对根在非预期 CWD 下写错位置。统一按 manifest 所在目录解析，并加"任意 CWD 下相对 derived_root 正确解析"回归测试。
- R2-P2（原 P2-2）：合同/交接文档统一 `python -X utf8 -m unittest discover -s tests` 命令写法，避免子集模式与全量口径混淆（构建内子集模式可保留但须注明口径）。
- 编号规范：本轮起新登记项用轮次前缀（R2-Pn），不再与历史 Pn 混用。

## 保留项与边界
- 原件只读：合成测试材料放 tests/fixtures 或临时目录，不动 `automation/runs/` 旧工件、task-registry、legacy-ia2；不自动 commit、不上传材料。
- 不改 `stage1_browser_probe.py`/`bpm_save.py`/守卫；不连 OA；不新建虚构报销业务（合成材料仅用于机制测试）。
- 旧 manifest v1.0 读取与拒绝漂移语义不降级；正在填写/保存中的任务不自动迁移。
- agent 推断不得写成 kind=user 或"用户已确认"。

## 验证（全部离线）
- 新增单测（合成 fixtures）至少覆盖：文本 PDF 提取+页/区域定位+复核分层；图片/OCR→ocr_result 与 reviewed_extraction 两层落盘且绑定原件哈希；xlsx 多 sheet/汇总 vs 明细/隐藏筛选行/前导零/公式缓存校验/跨表重复识别；CSV 行列定位与丢精度登记；语义分类（发票/统计表/重复副本/说明）+ 文件名不作证据反例；缺口结构化登记；R2-P1 相对根回归。
- `python -X utf8 -m unittest discover -s tests` 全绿（存量 133 不回归）。
- `python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>`（唯一 run）PASS。
- 本轮预期不触碰 `stage1_browser_probe.py`；若确需，先 `python -X utf8 stage1_probe_selftest.py` 全绿再收口。

## done_when
1. PDF/图片链路：合成文本 PDF 与图片各≥1 例端到端——提取事实带定位、OCR 层与复核层分离、经 register_derived 入派生根并绑定原件哈希、复核记录含工具/时间/方式。
2. Excel/CSV 链路：上述解析点全部有通过的单测；无机械行转换路径。
3. 语义类别盘点机制+测试落地（≥发票/统计表/重复副本/说明四类判别+文件名反例）。
4. 缺口登记结构化并有单测（模糊值→定位缺口、清晰件继续）。
5. R2-P1 修复+回归测试通过。
6. 全量 unittest 全绿；verify_bpm_build 唯一 run OFFLINE_PASS 留盘。
7. 交接齐备：改动文件+sha256 清单、测试结果、progress.json 的 W03 状态与证据更新、P2-n 挂账轮次前缀化、下一轮入口建议（W04 事实与对账 / W05 计划衔接）。
<!-- /team-task-source -->

<!-- team-task-contract run_id="20261024-105600-20e40597" contract_id="ctr-1f52c622" source_block_id="src-20e40597" status="frozen" profile="minimal" -->
### 冻结合同（2026-10-24，round 2）

**终态**：W03 原件理解离线落地——文本 PDF（版面定位+票据事实：票号/代码/日期/主体/价税合计与税前/税额/总额区分）、图片（本地渲染+ocr_result 与 reviewed_extraction 两层分离）、Excel/CSV（多 sheet/汇总 vs 明细/隐藏筛选行/前导零/公式缓存/跨表重复识别/CSV 行列定位与丢精度登记）、语义类别盘点、结构化缺口登记四链路机制+单测全绿；R2-P1 相对根修复；全量 133+新增零回归；唯一离线构建 OFFLINE_PASS；progress.json W03 状态与证据更新；交接含 R2-Pn 前缀化挂账与 W04/W05 入口。

**本轮做**：
1. W03 新模块落四链路；所有派生产物经 register_derived 入派生根并绑定原件 sha256（sources=原件哈希），generated_by/generated_at/复核方式如实记录；`reviewed=true` 仅记实际执行的复核过程，OCR 裸输出不得标已复核；不上传原件到任何第三方/云端（本地能力：pypdf/fitz/PIL/openpyxl + agent 视觉；无 tesseract → 可插拔本地引擎接口）。
2. R2-P1：bpm_materials.py 中 derived_root 解析（register_derived L245 与 validate_image_documents L516）统一按 manifest 所在目录，加任意 CWD 回归测试；R2-P2：合同/交接统一 `python -X utf8 -m unittest discover -s tests` 写法（定向用 `-p` 模式并注明口径）。
3. 验证全离线：新增单测覆盖任务书列举面（PDF 定位+复核分层/图片两层落盘/xlsx 语义/CSV 定位与丢精度/语义分类+文件名反例/缺口登记/R2-P1 回归）；全量 discover 全绿（133 基线零回归）；verify_bpm_build 唯一新 run PASS。

**本轮不做**：不连 OA、不做浏览器操作；不接入新报销类别；不改 stage1_browser_probe.py/bpm_save.py/守卫；不动 automation/runs/ 旧工件、task-registry、legacy-ia2；不自动 commit、不上传材料；不做 W04 事实对账、W05 计划衔接（仅留入口）；不虚构实单（合成材料仅机制测试）。

**允许写**：新模块 `bpm_extraction.py`（命名可裁量，落点见裁量项）、`bpm_materials.py`（仅 R2-P1 相对根解析修复）、`tests/`（新增测试文件与 fixtures）、`automation/template-materials-program/`（台账更新）、`team-progress.md`、`team-task.md`（仅本合同追加）。
**只读**：`fill_once.py`、`bpm_types.py`、`bpm_plan.py`、`bpm_ui.py`、`bpm_verify.py`、`bpm_save.py`、`stage1_browser_probe.py`、`automation/runs/`、`automation/task-registry/`、`automation/offline-verify/` 既有产物、`.pw-profile/`、`legacy-ia2/`。
**禁止**：删除或重写旧 run/registry/证据；放宽通用守卫或保存保护；agent 推断写 kind=user 或「用户已确认」；OCR 裸输出标 reviewed=true；公式文本当金额；「每个非空行=一条费用」机械转换；上传原件到第三方；虚构实单或保存验收。

**红线**：继承根 AGENTS.md 全部红线（只填不存；.pw-profile/ 活体 token 绝不入 git/日志/报告；legacy-ia2/ 只读；registry 只读核实；单 profile 单执行者；不走 VPN/代理；Python 一律 -X utf8）。team-task 四红线：①销毁性/不可逆操作；②对外交付物；③同一 failure_key 三次失败熔断；④推翻已封决策。B 模式权限类命令后置人工门，不在中途发起。

**P0.5 风险 envelope**：author_runtime=CLAUDE_GLM；risk_class=MEDIUM；risk_owner=USER；risk_source=USER_STANDING_POLICY_20260904；runtime_policy=GLM_ALLOWED；risk_escalation=NONE（同 round-1 常设策略；runtime 一手证据已记 progress 头）。

**裁量项（contract-only：写推荐+依据，P6 执行期按 B 默认落实并记自主裁决）**：
- 模块落点：新建 `bpm_extraction.py`（推荐依据：bpm_materials.py 已 ~650 行且关注点=契约校验，W03=提取管线，分离后现有 v1/v2 契约零改动即零回归面）。
- OCR 后端：无 tesseract/pytesseract → 定义封闭的本地引擎接口（registry 可插拔，generated_by 如实记引擎名与版本）；单测用确定性 stub 引擎驱动两层机制；agent 视觉复核产物走同一 register_derived 通道。不为此新增第三方 OCR/重框架。
- fixtures：tests/fixtures/w03/（合成文本 PDF 用 pypdf 生成、PNG 用 PIL 绘制、xlsx 用 openpyxl 构造；不含任何真实业务数据）。
- R2-P1 修复范围：L245（register_derived）与 L516（validate_image_documents）两处 derived_root 解析一并挂 manifest 所在目录。

**done_when（字面可判；全部离线验证）**：
- D1: 合成文本 PDF 与图片各 ≥1 例端到端：提取事实带页码/区域定位；ocr_result 与 reviewed_extraction 两层分离落派生根且 sources=原件 sha256；复核记录含工具/时间/方式。（验证：`python -X utf8 -m unittest discover -s tests -p "test_bpm_extraction.py"` 对应测试全绿 + manifest 结构断言）
- D2: Excel/CSV 解析单测全过：多 sheet/汇总 vs 明细区分/隐藏与筛选行/前导零字符串原值/公式缓存值校验/跨表重复识别/CSV 行列定位与丢精度缺口登记；代码中不存在「每个非空行生成一条费用」机械路径。（验证：同上定向 discover）
- D3: 语义类别盘点机制+测试：≥发票/统计表/重复副本/说明四类判别 + 文件名不作类别证据反例；不确定标「待定」并说明。
- D4: 缺口结构化登记有单测：模糊/丢精度值→含文件/页或单元格/区域/候选或原因/受影响行的缺口对象；清晰件继续处理不被中断。
- D5: R2-P1 修复 + 「任意 CWD 下相对 derived_root 正确解析」回归测试通过。
- D6: `python -X utf8 -m unittest discover -s tests` 全绿（133 基线零回归）；`python -X utf8 verify_bpm_build.py --run template-materials-<当前时间戳>` 唯一新 run OFFLINE_PASS 且产物留盘。
- D7: 交接齐备：改动文件清单+sha256、测试结果、progress.json 的 W03 状态与证据更新、P2-n 挂账轮次前缀化（R2-Pn）、下一轮入口建议（W04/W05）写明于 team-progress.md 收尾段及台账。
<!-- /team-task-contract -->
