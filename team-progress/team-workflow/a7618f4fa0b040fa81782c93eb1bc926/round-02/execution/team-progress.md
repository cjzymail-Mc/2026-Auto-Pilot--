# team-progress
> run_id: 20261024-105600-20e40597
> source_block_id: src-20e40597
> contract_id: ctr-1f52c622
> effective_contract_id: ctr-1f52c622
> run_status: COMPLETE
> author_runtime: CLAUDE_GLM
> risk_class: MEDIUM
> risk_owner: USER
> risk_source: USER_STANDING_POLICY_20260904
> runtime_policy: GLM_ALLOWED
> risk_escalation: NONE
> risk_envelope_runtime_evidence: helper workflow.py enter/permit round 2 从本 session 原始 JSONL 证明 CLAUDE_GLM/glm-5.3（session fb56811d-33fa-4ca7-99e1-82643f913df8）
> workflow_run: a7618f4fa0b040fa81782c93eb1bc926
> workflow_round: 2
> entry: team-workflow-run
> task_source_sha256: 20e405971acafa5544c47bd3d7338e81e2514c164bdb67cc0da2c7e87173f38d
> b_run_authorization: 用户显式 /team-workflow run（2026-10-24T10:03:30+08:00）；round-2 接棒=A publish 后 WAKE→enter（seq=9，B_RUNNING）
> workflow_failures_loaded: {}
> 上轮交接: round-1 review decision=rework（A 复核 8/8 哈希一致、133/133 复跑通过、18 项判据属后续工作包签 FAIL 驱动下轮，无交付缺陷/人工门/熔断）；本轮任务=W03 原件理解+R2-P1/R2-P2 顺手项
> 漏斗: P0✓ P0.5✓ P1✓ P2✓ P3✓ P4✓ P5✓ P6✓
> P1已核事实: 见下方进度日志 2026-10-24 P1✓ 条目

## 漏斗默认·待确认
## 自主裁决(B)
- 决策点：W03 模块落点 / 候选：新建 bpm_extraction.py vs 扩展 bpm_materials.py / 选：新建（合同裁量 1 推荐）/ 依据：bpm_materials 关注点=契约校验（~650 行），提取管线分离后 v1/v2 契约零改动即零回归面 / 置信：高。
- 决策点：无 tesseract 下的 OCR 后端 / 候选：装 pytesseract/tesseract vs 封闭本地引擎注册 / 选：后者——模块内 register_ocr_engine 注册制 + barstub 确定性像素引擎（真实读像素解码条码式数字）驱动测试；agent 视觉复核走 verify=agent-visual 通道且证据如实记 mechanical_crosscheck=unavailable / 依据：合同裁量 2 推荐 + 任务书禁第三方云端、不引入无调用者重框架 / 置信：高。
- 决策点：合成 PDF 生成工具 / 候选：合同推荐 pypdf vs fitz / 选：fitz（pypdf 6.8 无文本绘制 API，fitz 1.28 已在环境且支持中文排版+行级 bbox，先探针实证）/ 依据：偏离合同推荐处在此留痕（R2-P2 文档口径不变）/ 置信：高。
- 决策点：fixtures 生成方式 / 候选：静态文件入库 vs 测试内幂等生成器（stamp 控制重建） / 选：后者，ensure_fixtures() 落 tests/fixtures/w03/，内容全合成（发票字段/条码数字/工作簿均为虚构值）/ 依据：确定性+可重建+可审计 / 置信：高。
- 决策点：classify 判重数据源 / 候选：仅 files 条目 vs 并入 inventory duplicate_paths / 选：并入——inventory 以内容哈希判等把重复件收在 duplicate_paths 字段，不并入会漏判 duplicate_copy / 依据：round-1 契约既有语义（内容判等，名字不参与）/ 置信：高。
- 决策点：SUM 本地重算的小数语义 / 候选：原样 str 化 vs quantize 2dp / 选：quantize Decimal("0.01")（金额语义；首跑 str(112.0) 暴露 float 表示丢票面两位小数）/ 依据：AGENTS.md 金额 Decimal 纪律 / 置信：高。
- 决策点：收尾 loop mc-update 段 / 候选：跑固化 vs 判无不跑 / 选：不跑 / 依据：去重闸——本轮唯一新环境事实「fitz 可生成/行级提取中文 PDF（pypdf 无文本绘制 API）」已记录于本文件 P6a 与 notes.md，跨 repo 用户偏好/元规则层零新增，无用户工作方式纠偏 / 置信：高。
- 决策点：收尾 loop pin 段预判闸 / 候选：派 mc-expert 陪审 vs 无迹象跳过 / 选：跳过（不派陪审） / 依据：本轮用户零行为纠正（round-2 全程无用户输入；A 的 rework 属工作流角色输出非纠正）；reviewer 两条 P2 为工程建议已挂账 R2-P5/R2-P6 / 置信：高。
- 决策点：session-new 固化落点 / 候选：新建根 plan-*.md vs 沿 workflow 既有载体固化 / 选：后者（team-progress.md 状态区+D7 清单+handoff-input.json+helper finish 归档） / 依据：同 round-1 裁量先例——根 plan 文件越冻结合同允许写，冷启动锚点=state 文件+归档 progress+progress.json next_actionable（W04/W05 已落台账不重复规划） / 置信：高。
## 失败陪审（failure_key / failure_count / mxp候选排序 / 本次选项 / 尝试结果）
## OPEN_BLOCKERS
## PENDING_HUMAN_NONBLOCKING
## 进度日志
- 2026-10-24 10:56 P0✓ helper enter/permit round 2 成功（seq=9，B_RUNNING，team_run=20261024-105600-20e40597，src-20e40597，failures={}）。用 helper 已分配值初始化本 progress；round-1 progress 已由 helper 归档（pending_old 备份 69996ffb/2ffd4648）。上轮 P2-3/P2-4（git commit、legacy token 清理）仍为用户侧非阻断挂账。
- 2026-10-24 10:57 P0.5✓ 风险 envelope 落盘：CLAUDE_GLM + 用户常设策略（任务未指定等级）→ MEDIUM / USER / USER_STANDING_POLICY_20260904 / GLM_ALLOWED / NONE。team-workflow 受控委托（A publish 派工 + 用户 run 授权沿用）；四红线/阻断 FACT/陪审门不放松。
- 2026-10-24 10:58-11:02 P1✓ 定点核验（全部一手证据）：
  - 全量基线：`python -X utf8 -m unittest discover -s tests` → **Ran 133 tests OK**（98.2s）。127→133 增量=tests/test_bpm_session.py（6 个 test，mtime 10-24 10:40，round-1 执行窗口内用户侧并行新增，与 AGENTS.md 多人登录探查章节同向；本人 round-1 未触碰该文件）；单跑该文件 OK。本轮回归基线=133（与任务书「存量 133」一致）。
  - 本地依赖盘查：pypdf 6.8.0 / fitz(PyMuPDF) 1.28.0 / PIL 10.4.0 / openpyxl 3.1.5 / pandas 2.2.2 / numpy 2.1.1 / xlsxwriter 3.2.9；**无** pytesseract、tesseract 二进制、cv2、pdfplumber、PyPDF2 → 无经典本地 OCR 引擎。fitz 可渲染 PDF 页→PNG、可提文本+坐标；PIL 可合成测试图。「本环境可用的视觉能力」= agent 视觉（Read 图片）+ 代码侧可插拔引擎接口。
  - R2-P1 核位：bpm_materials.py L233 `validate_dual_manifest(manifest, base_dir=manifest_path.parent)` vs L245 `derived_root=_safe_material(Path(manifest["derived_root"]))`（按 CWD 解析，不一致）；另 L516 validate_image_documents 内 `_safe_material(Path(manifest["derived_root"]))` 同样未挂 base，需一并核对。
  - tests/ 布局：15 个测试文件、无 tests/fixtures/（本轮新建获任务明确许可「合成测试材料放 tests/fixtures 或临时目录」）；tests/ 整体未入 git（用户侧事务，不自动 commit）。
  - bpm_materials.py 现有 API（round-1 交付冻结）：prepare_dual_materials / register_derived(role, sources, generated_by) / validate_dual_manifest / dual_hash_sets；role 枚举已含 ocr_result/reviewed_extraction——W03 落点无需扩 role 枚举，双根契约不动语义。
- 2026-10-24 11:04 P2/P3✓ chop-task（被调用模式，八键合法）：source src-20e40597 hash 复算一致、恰 1 块 open、查重 0 合同块 → 追加冻结合同 **ctr-1f52c622**（初记 ctr-ca6d8a81 系手算哈希口径差——含尾换行未走 normalize_block_body，收口时 helper 拒绝后按 fixture block_id 机械修正，合同正文逐字节未动，见 P2-fix 条目；profile=minimal；同 round-1 同形先例 T3）。门禁：八项交底自检全在场；事实层缺口=0（合成材料获准、全离线、无外部输入依赖）→ 不产问卷；裁量 4 项（新模块 bpm_extraction.py 落点/无 tesseract 下封闭本地引擎接口/tests/fixtures/w03 生成策略/R2-P1 修复含 L245+L516 两处）写推荐进合同。verify_workflow_contract.py 全绿（79 cases + 结构检查）。
- 2026-10-24 11:34 P2-fix 合同链勘误（机械修正，非语义变更）：helper finish 报 `TEAM_CONTRACT_INVALID: base hash mismatch`——根因=本人追加合同时 contract_id 手算 sha256 前 8 位（ca6d8a81）含尾换行、未按 verify_workflow_contract.normalize_block_body（CRLF→LF+去首尾空行）口径；用 fixture 模块对盘上合同正文复算得正确 id **ctr-1f52c622**，仅改 marker 的 contract_id 属性与 progress 头两行，合同正文/其余冻结 14 件逐字节未动（终审 GO 的哈希绑定不受影响）。修正后 verify_workflow_contract.py 复跑全绿；progress.json rounds[1].contract_id 保留初记 ca6d8a81 作历史记录不回写（该文件在冻结清单内，勘误以本条目+team-task.md 有效链为准）。
- 2026-10-24 11:04 P4✓ 二轴路由：C1=0（单一串行改面：新模块+bpm_materials 定点修复+tests）C2=1（round-1 同形先例 ctr-4199eb39；提取管线需局部裁量）C3=1（契约→测试→构建串行检查点）C4=0（单执行体闭合）→ 合计 2 → **T3**；硬覆盖核对一致。assurance：GLM MEDIUM + 新模块机制面 → **ENHANCED**。
- 2026-10-24 11:04 P5✓ 登记门：drive_mode=B / routing_mode=AUTO（A publish 派工 + 用户 run 授权沿用）。B 前置核验：frozen effective contract ctr-ca6d8a81 ✓（verify PASS）/ OPEN_BLOCKERS 空 ✓ / 无阻断 FACT（无问卷）✓。
  routing_mode=AUTO
  recommended_topology=T3
  realized_topology=T3
  assurance_profile=ENHANCED
  drive_mode=B
  author_runtime=CLAUDE_GLM
  risk_class=MEDIUM
  risk_owner=USER
  runtime_policy=GLM_ALLOWED
  risk_escalation=NONE
- 2026-10-24 11:05-11:15 P6a✓ 施工完成（改动清单）：
  - **bpm_extraction.py（新建）**：四链路——①PDF：extract_pdf_text（fitz 行级 text+page+bbox+header/body/footer 区域带）→ extract_pdf_facts（标签驱动票据事实：发票号码/代码/开票日期/开票主体/不含税合计/税额/价税合计，逐字段锚点）+ 价税 Decimal 闭合（不闭合→结构化缺口）；run_pdf_extraction 端到端（嵌入文本层落 ocr_result + 逐字段回锚复核落 reviewed_extraction，review_evidence 记 raw-line-anchor-match+decimal_closure）。②图片：render_original（PDF 首页 fitz 渲染 PNG / 图片原样）+ 封闭 OCR 引擎注册（register_ocr_engine/run_ocr，无网络）+ barstub 确定性像素引擎；ocr_pass→role=ocr_result（裸输出永不带 reviewed）；review_pass（verify=raw-cross-check 逐字段与原始层比对，不一致即拒；verify=agent-visual 区域锚点+执行者留证并如实记机械比对缺位）；run_image_extraction 端到端两层。③表格：extract_workbook（openpyxl 双视图——sheet 可见性/隐藏行/autofilter/表头识别/合计行/公式缓存→本地仅重算 =SUM 字面区间（quantize 2dp）→否则缺口；编号列数值单元格→前导零丢精度缺口不补零；汇总=明细候选关系；跨表同额同日仅 reconciliation_hints 提示待对账）；extract_csv_table（行列定位、全字符串原值、科学计数/尾零丢精度缺口）。④语义盘点 classify_materials（内容哈希判重并入 duplicate_paths→duplicate_copy；PDF 关键词+版面→invoice；xlsx 合计/公式结构→summary_statement；纯文本无表格无票据词→explanation；其余 other_pending 带 basis+pending_reason；文件名/扩展名以外不作证据）+ GAP_FIELDS 封闭缺口结构（file/locator/region/candidates/reason/affected_rows，清晰件不中断）。
  - **bpm_materials.py（仅 R2-P1）**：register_derived L245 与 validate_image_documents L516 两处 derived_root 解析统一挂 manifest 所在目录（绝对根行为不变；提取 helpers _resolve_original 同口径）。
  - **tests/test_bpm_extraction.py + tests/fixtures/w03/**（全合成）：13 测试——PDF 端到端两层绑定/金额不闭合缺口/行锚点；图片两层+复核不一致拒绝+agent-visual 诚实证据；xlsx 语义+数值编号丢精度；CSV 定位+科学计数/尾零；分类四类+文件名反例（发票.pdf 无票据内容≠invoice）+内容判重；R2-P1 任意 CWD 相对根回归×2（register_derived 落点+validate_image_documents 全链）。
  - R2-P2：文档与合同命令统一 `unittest discover -s tests` 写法（定向 -p 注明口径；构建内 -p test_bpm_*.py 实覆盖全部测试文件，与全量等价，已在台账注明）。
- 2026-10-24 11:16 P6b✓ 测试：新契约定向 `discover -s tests -p test_bpm_extraction.py` 首跑 5 失败（相对根 fixture 未预建 work/ 目录、SUM 重算未 quantize、classify 未并入 duplicate_paths、两处用例期望错位）→ 属测试期实现迭代修复，非候选方案失败（未触发失败陪审）→ 复测 13/13 OK；全量 `python -X utf8 -m unittest discover -s tests` **146 tests OK**（133 基线+13 新，零回归，98.97s）；`verify_bpm_build.py --run template-materials-20261024-111625` → **OFFLINE_PASS**（probe-selftest exit 0 + capability-tests 146/146 exit 0）。
- 2026-10-24 11:20 P6c✓ 台账回写：progress.json W03→已验证（证据四件+层次）、R2-P3/R2-P4 前缀化挂账、next_actionable→W04/W05、rounds[1] 绑定 ctr-ca6d8a81；notes.md 同步。
- 2026-10-24 11:21 P6d 终产物冻结：14 件套 SHA-256 见下「D7 终产物冻结清单」；team-progress.md 为过程活档不入清单；本轮未触碰 stage1_browser_probe.py/bpm_plan.py/fill-plan.schema.json（合同只读面，字节未动）。
- 2026-10-24 11:22 P6e ENHANCED_FINAL 发起：终产物冻结并复算 SHA-256（14 件套），fresh 一次性只读 mc-expert 后台执行 review-contract-v2 ENHANCED_FINAL（八面审计），REVIEW_QUESTION=「ctr-ca6d8a81 done_when D1-D7 是否由最终产物与原始证据独立成立，可否终签 GO」。UNVERIFIED_SCOPE 申报：本轮范围内 NONE；范围外（浏览器操作/新报销类别/W04 对账/W05 计划衔接/保存语义）按合同「本轮不做」排除并已入台账。检查点 status：B_RUNNING/round 2/stop_requested=False。GO 前不写 COMPLETE。
- 2026-10-24 P6f ENHANCED_FINAL 结论（fresh reviewer，独立复算 14+2 件哈希前后一致、复跑 13/13 与 146/146、source block sha256 吻合）：ADMISSION=ADMITTED、HASH_VALIDITY=VALID、UNVERIFIED_SCOPE=NONE、八面检查全 PASS_DYNAMIC（object_binding/lifecycle_identity/timing_permissions/idempotency_retry/executor_matrix/type_cross_product/interface_discovery/fixture_truth）、D1-D7 全部 PASS_DYNAMIC、红线抽查零违例（只读面字节未动/无网络面/fixtures 全合成/无自动 commit）。**VERDICT=GO**（首次即终签，无需重审）。P2 挂账（不阻断，下轮顺带）：**R2-P5** 构建 source_manifest.json 未收录新模块 bpm_extraction.py——最小修复=下轮把 bpm_extraction.py 加入 verify_bpm_build.py source 清单（本轮 D7 清单+终审复算已兜底）；**R2-P6**（W04 使用注意）duplicate_copy 为组级分类，组内主路径也归该类，W04 对账仍消费组内一份原件，类别≠丢弃。
## 当前现状
P6✓ 收口完成：ENHANCED_FINAL 首审即 **GO**（P6f，八面全过+D1-D7 成立+红线零违例），收尾 loop 三段预判/决策落盘（见收尾复盘）。run_status=COMPLETE；handoff 交 A_REVIEW，静默等待 A 验收。

## D7 终产物冻结清单（本轮改动文件 + SHA-256）

改动/新增文件（14 件套，冻结哈希=终审 ENHANCED_FINAL 审定基础）：

| 文件 | SHA-256 |
|---|---|
| bpm_extraction.py | 122464266a0efd038dbeca018c216deb8ef94b758b8b63bc1a4b6ea546d8854c |
| bpm_materials.py | ce37d3b4bf9499714d8abff9ff9e747ff705b893861a1a27e44205496a164e02 |
| tests/test_bpm_extraction.py | 6cf620e19f33ad642102dd48b3351b12a34f71ebb002ee563ee03fd529fcb921 |
| tests/fixtures/w03/invoice.pdf（合成） | 1c398c49d3e21a6d504ae36ef780169813d77f0e0422c58ac2241e7f79b165d4 |
| tests/fixtures/w03/发票.pdf（合成文件名陷阱） | 341ec4960327f10ff1d8a229e9952a282e3221a0a92772d48127acbc58e0b599 |
| tests/fixtures/w03/bars.png（合成条码图） | c9f743f31c83ff285da5a0bf861fbbb15c5646cca5297aa90f23dea22095ac56 |
| tests/fixtures/w03/ledger.xlsx（合成） | 058edbefd96536696f44a220c9453ffe4655e97b28fced341a7990a21cfbff7b |
| tests/fixtures/w03/rows.csv（合成） | f1b86b7646abac650c5001cabdf2120e637a5b4311799d07a1655253b4a266ed |
| tests/fixtures/w03/费用说明.txt（合成） | bb31f99936a241d23db80b3eebe037ac88a258f66ffeb769df65be5bcd397c43 |
| tests/fixtures/w03/说明备份.txt（合成重复件） | bb31f99936a241d23db80b3eebe037ac88a258f66ffeb769df65be5bcd397c43 |
| tests/fixtures/w03/w03-v1（fixtures stamp） | 3494bc379d90386004c209efc1c654a52eca6da41400ba657bff5209b20da52c |
| automation/template-materials-program/progress.json | ae2716c012c1c8f3cf3b92627ea654af9507172fd3984b140611b89e7d49584b |
| automation/template-materials-program/notes.md | 428b4f5a473509061ca0b2f56bf6a9c7b627a6e13273d44ded3355b9d2a3f92e |
| automation/offline-verify/template-materials-20261024-111625/build_result.json | 9ebcbc92a6dac2430e0d419f4cb2c712b341d75a7eea86640d93145fddb98e34 |

- 测试结果：定向 `python -X utf8 -m unittest discover -s tests -p "test_bpm_extraction.py"` 13/13 OK；全量 `python -X utf8 -m unittest discover -s tests` **146 tests OK**（133 基线+13 新零回归，作者 98.97s）；`python -X utf8 verify_bpm_build.py --run template-materials-20261024-111625` **OFFLINE_PASS**（probe-selftest exit 0 4.47s + capability-tests 146/146 exit 0 103.0s；构建内子集模式 `-p test_bpm_*.py` 实覆盖全部测试文件，与全量 discover 等价）。
- 台账更新：progress.json（W03=已验证+证据四件+rounds[1] 绑定 ctr-ca6d8a81+R2-P3/R2-P4 前缀挂账+next_actionable=W04/W05）、notes.md 同步；逐文件哈希机械权威=automation/offline-verify/template-materials-20261024-111625/ 构建产物（source_manifest 覆盖 bpm_materials.py 等冻结源；本表为终稿复算值）。
- 下一轮入口：W04（本次事实与对账，消费 reviewed_extraction/语义盘点/缺口登记）/ W05（计划衔接、内部阶段状态区分）；挂账 R2-P3（git commit 用户决策）/R2-P4（legacy token 清理人工）；无新 P2 观察项。
- 合同链勘误（P2-fix）：有效合同 id=ctr-1f52c622（初记 ca6d8a81 为 id 派生口径差，机械修正于 marker/progress 头；合同正文与 14 件冻结哈希零变化；progress.json rounds[1] 保留历史初记值不回写）。
## 下一步
静默等待 A（/team-workflow review）；A 判 rework 时下一轮入口=W04（本次事实与对账）/W05（计划衔接），顺手项 R2-P5（build source 清单收录 bpm_extraction.py）；R2-P6 为 W04 使用注意；R2-P3/R2-P4 用户侧挂账。
## 卡点
无。
## 收尾复盘
- 漂移苗头与纠正来源 + 陪审触发/跳过原因：round-2 全程无用户直接输入（A rework 派工属工作流角色流转）；施工中无 AGENTS.md 再变更；失败陪审未触发（首跑 5 失败为测试期实现迭代——fixture 缺目录/quantize/判重并入/用例期望错位，均一次修复，非候选方案失败，未达 failure_key 扳机）。
- mc-update 段（预判→决策）：预判=无新可固化——本轮唯一新环境事实「fitz 1.28 可生成并行级提取中文 PDF（pypdf 6.8 无文本绘制 API，已探针实证）」已记录于本文件 P6a/自主裁决与 notes.md（去重闸拦截）；无用户工作方式纠偏、无跨 repo 元规则新增。决策=不跑 mc-update。
- pin 段（预判闸→决策）：预判=无词表漏网纠正迹象——round-2 用户对 agent 行为零输入零纠正；reviewer R2-P5/R2-P6 为工程建议非纠正残留，已入挂账。决策=跳过 pin 段、不派 mc-expert。落账：pin 0 / drop 0 / 降级 0。
- session-new 段（预判→决策）：预判=有可交接（round-2 完成态+W04/W05 入口+等 A 唤醒）。执行=沿母本仅固化文件、不重开 session：交接物=本文件状态区+D7 终产物冻结清单（14 件 sha256）+handoff-input.json+helper finish 归档（team-progress/team-workflow/<run>/round-02/）；不新建根 plan 文件（同 round-1 裁量先例：越冻结合同允许写，workflow 冷启动锚点=state+归档+台账）。主线回顾：progress.json next_actionable 已落 W04/W05=「已落」，只标指向不重复规划；无 STATE.md 不强造。幂等检查：本会话无既有同名 plan，无重复固化。
