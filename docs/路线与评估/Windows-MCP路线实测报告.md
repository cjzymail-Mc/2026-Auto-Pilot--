# Windows-MCP 路线实测报告:企业微信 OA 控件树可读性

> **冷启动自足文档** — 回答独立复评(`自动化热门repo.md` §4 第一步)提出的问题:
> "先验证当前 OA 控件树是否可读"。答案是:**可读,但走的不是 UIA,是 IA2;Windows-MCP 开箱即用读不到,需要一个小的适配。**
>
> | 项 | 值 |
> |---|---|
> | 实测日期 | 2026-10-20 下午 |
> | 执行者 | Claude Code CLI (GLM-5.3, Z.ai) |
> | 被测项目 | CursorTouch/Windows-MCP v0.8.8(源码克隆,`Windows-MCP/` 子目录) |
> | 运行环境 | Python 3.14.7(uv 托管自动下载)+ uv 0.13.0 |
> | 安全约束 | 全程只读查询(截屏/UIA/MSAA 查询),未发送任何点击/键盘事件,未碰 OA 任何写操作 |
> | 姊妹篇 | `企业微信-报销单-页面探索报告.md`(上午的 OCR 视觉路线) |

---

## 1. 结论(TL;DR)

| 问题 | 答案 |
|---|---|
| Windows-MCP 能安装运行吗? | ✅ `uv sync` + `uv run windows-mcp serve` 一次成功(自动拉 Python 3.14.7);stdio 握手 OK,21 个工具全部注册 |
| 标准 Snapshot 能读到 OA 页面吗? | ❌ **不能**。企业微信窗口在它的 UI 树里只有 9 个空 Pane,OA 内容零暴露 |
| OA 控件树本质上可读吗? | ✅ **可以**。通过 MSAA/IAccessible2(`AccessibleObjectFromWindow` 屏幕阅读器式查询)能拿到完整 Web DOM 无障碍树:**1500+ 节点(未触底)、1108 个有名称、54 按钮、22 表格、43 链接,含名称+值+精确坐标** |
| 为什么 Snapshot 读不到? | 企微 OA 跑在 **CEF(Chromium Embedded Framework)** 里:`WXWorkWebViewHostWindow → CefBrowserWindow → Chrome_RenderWidgetHostHWND`。Chromium 的无障碍树是**惰性**的,只有被 MSAA/UIA 查询"敲门"后才构建;且 Windows-MCP 的 IA2 回退路径**只对 Firefox 进程启用**(`is_window_browser` 按进程名判定,WXWork.exe 不在名单) |
| 额外发现 | document 节点的 value 暴露了 OA 完整 URL:**`https://bpm.qiaodan.com/oa/reimburse?type=new&t=…`** → 复评设想的 Playwright 浏览器路线有了明确入口 |

## 2. 实测过程

### 2.1 安装与服务验证

```bash
git clone --depth 1 https://github.com/CursorTouch/Windows-MCP.git
cd Windows-MCP && uv sync          # 自动下载托管 Python 3.14.7,装 win 依赖(含 comtypes/pywin32/dxcam)
uv run windows-mcp --help          # CLI OK
```

自写 stdio 探针 `wmcp_probe.py`(JSON-RPC over newline-delimited stdio,UTF-8 文件输出防 GBK 乱码):

- `initialize` 握手 ✅(server: windows-mcp 4.1.0 —— FastMCP 版本号,与包版本 0.8.8 不同,勿混淆)
- `tools/list` → 21 工具:Snapshot / Screenshot / Click / Type / Scroll / Move / Shortcut / WaitFor / Scrape / PowerShell / FileSystem / Process / Registry / Clipboard / App / …

### 2.2 标准 Snapshot:UIA 路线失败(证据)

`tools/call Snapshot {use_ui_tree:true, use_vision:false}`(8.4s / 10.5s 各一次):

- 窗口列表里能看到 `企业微信`(句柄 133590,1026×1160,与上午 `window_list.txt` 一致)
- 但 UI 树里企微零内容;终端窗口、任务栏都有深层树,排除"只挖焦点窗口"的猜测(源码确认:`get_window_wise_nodes` 顺序遍历**全部**窗口,无排除项)
- 两次 Snapshot 之间做过 IA2 唤醒,**Snapshot 依旧读不到** → 不是惰性激活时机问题,是它根本不走那条路

### 2.3 裸 UIA dump:确认 UIA 面只有 9 个空壳

`wmcp_rawdump.py`(用 Windows-MCP 自己的 `uia` 包装层递归枚举 h=133590):

```
[WindowControl] 企业微信 (WeWorkWindow) (0,0,1026,1160)
├─ TitleBarWindow / PerryShadowWnd          ← 空 Pane
└─ 企业微信-工作台
   └─ WXWorkWebViewHostWindow
      └─ CefBrowserWindow                   ← CEF!
         └─ Chrome_WidgetWin_1
            ├─ Chrome_RenderWidgetHostHWND (Document)  ← Web 渲染 HWND,无 UIA 子节点
            └─ (unnamed pane)
```

共 9 节点、2 有名。**OA 的所有内容都在 Chrome_RenderWidgetHostHWND 之后,UIA 面完全不可见。**

### 2.4 IA2 探测:突破口

`wmcp_ia2_probe.py`:EnumChildWindows 定位 `Chrome_RenderWidgetHostHWND`(hwnd=199980)→ `AccessibleObjectFromWindow(OBJID_CLIENT)` → 走 IAccessible 树。

**两个坑(复现必读)**:

1. 首次查询返回 1 个空 document —— Chromium 无障碍树**异步惰性构建**,敲门后需等待/重查(本例重查即出;不需要额外 hack)。
2. `QueryInterface` 的参数必须是**接口类**(IAccessible),传 `type(ptr)`(POINTER(IAccessible))会报 `expected LP_c_void_p instance` 且被 except 吞掉、表现为"0 个子节点"的假象 —— 第一轮误判即源于此。

**结果**(节选,完整证据 `wmcp_ia2_result3.txt`,1500 行):

- document: name=`新增报销`, value=`https://bpm.qiaodan.com/oa/reimburse?type=new&t=179246311699`, loc=(61,77,964,1082)
- **工具栏按钮带 y≈148(解开了上午 OCR 报告未解项 #1)**:保存 | 商旅订单 | 导入 | 发票识别 | 发送 | 流转 | 终止 | 返回
- **表头字段连值一起给出**(OCR 只能读标签):申请人=陈晶、申请日期=2026-10-20、职位=高级经理、申请部门=运动表现研究部、公司=厦门乔丹科技有限公司、单据编号/大写金额/预算年度/报销方式/币种
- **区块锚点与 OCR 报告 §6 地图完全吻合**:关联单据(541)/关联单据明细(600)/报销明细(699)/费用说明(770)/银行信息(835)/审批记录(965)/附件(1024),坐标同屏可比
- **OCR 看不见的新信息**:每个表格带工具栏(新增/插入/删除/复制/自动换行/向下填充选中单元格数据/**复制金额到本次报销金额**);附件区 `添加附件` 按钮;左侧导航还有屏外滚动项 `关联单据授权`(x=-126,证明树里连滚出视口的元素都有)

### 2.5 交叉验证

- 同一页面:IA2 结构 ↔ 上午 OCR 六轮结果 ↔ 截图,三者一致 → 树内容真实反映当前 OA 页面
- 注意:上午报告的是"报销单"草稿页签,本次 CEF 当前页是"新建报销单"页签(type=new),字段结构相同,状态不同

## 3. 路线评估(对照独立复评)

| 复评的判断 | 实测结果 |
|---|---|
| "能看到主窗口,不代表能看到内嵌 OA 表单的字段和按钮" | **应验且更具体**:UIA 面连一个字段都看不到;但 MSAA/IA2 面全量可见 |
| "UIA 通常也不能凭空读取未暴露的自绘控件" | 部分修正:CEF 不是"不暴露",是**按需暴露**——屏幕阅读器式查询即可点亮,之后稳定可读 |
| "Windows-MCP 是最贴近当前环境的首轮试验选择" | ✅ 判断正确:它的 `uia` 包装层和 `tree/ia2.py` 遍历器直接复用即达成目标;但**开箱即用的 Snapshot 对企微无效**,IA2 回退只接线了 Firefox |
| 已知风险(v0.8.8 控制门异常 #465 等) | 本次只用了只读路径,未触发;写操作(Click/Type)未实测 |

**结论:这条路线"能用",但用法是 —— Windows-MCP 作为库/工具箱复用 + 一份小适配,而不是直接把 Snapshot 当黑盒。**

### 可行的三种落地形态(按改动量排序)

1. **探针脚本 + Windows-MCP 动作层**(零改动):`wmcp_ia2_probe.py` 读结构和坐标 → 把坐标喂给 Windows-MCP 的 `Click/Type/Scroll`(其输入走 UIA 坐标系,与 `accLocation` 同为物理像素,无 DPI 换算)。今天已验证前半段。
2. **小补丁进 Windows-MCP**(推荐,~20 行):在 `tree/service.py` 的窗口处理里,检测窗口子 HWND 含 `Chrome_RenderWidgetHostHWND` 时调用已有的 `ia2.traverse_window()`,与 Firefox 分支并列。改完 Snapshot 就能直接产出企微 OA 的结构化树。
3. **Playwright 浏览器路线**(复评第二步,已被 URL 发现激活):OA 是 `bpm.qiaodan.com` 的 Web 应用。若登录态能在受控浏览器成立(企微扫码/SSO 待验证),按 DOM 选择器操作比坐标更稳。**需要先验证:新开浏览器是否要求重新登录、能否过 SSO。**

## 4. 后续建议(优先级)

1. 把 `wmcp_ia2_probe.py` 固化成"企微 OA 树读取器"(加 JSON 输出、按 role/名称过滤、找控件返回坐标),配合 Windows-MCP Click/Type 做一次**只读导航**验证(如切换页签后重读树)
2. 验证 Chromium 无障碍模式的**持续性**:企微重启后是否需要重新"敲门"(怀疑是;可把敲门做进读取器第一步)
3. 按 §3 形态 2 给 Windows-MCP 提 patch(本地改也行),让 Snapshot 原生支持 CEF 宿主
4. 评估 Playwright 路线:浏览器开 `bpm.qiaodan.com` 看登录跳转行为(只读)
5. 任何写操作(保存/发送/加行)仍按项目安全约束:**必须用户明确授权并指定目标后才可执行**

## 5. 资产清单(本次新增,均在 `【feature01-企业微信自动化办公】/`)

| 文件 | 作用 |
|---|---|
| `Windows-MCP/` | 上游仓库源码 + uv venv(Python 3.14.7),版本 0.8.8 |
| `wmcp_probe.py` | MCP stdio 客户端探针(mode: tools / call / chain 同会话多工具链),UTF-8 文件输出 |
| `wmcp_tools.json` | 21 个工具的完整 schema |
| `wmcp_args_snap.json` | Snapshot 调用参数 |
| `wmcp_snapshot1/2.txt` | 标准 Snapshot 两轮输出(UIA 路线,企微为空的证据) |
| `wmcp_rawdump.py` | UIA 原始子树 dump 工具 |
| `wmcp_rawdump_wxwork.txt` | h=133590 的 UIA 9 节点证据 |
| `wmcp_ia2_probe.py` | IA2 探测脚本(敲门 + 遍历,含两个坑的修复) |
| `wmcp_ia2_result.txt/2/3.txt` | IA2 三轮结果(3 是修复后完整版,1500 节点) |
| `wmcp_snapshot3.txt` | 补丁后 Snapshot 第三轮输出(8.6s 无错但 UI 树无 OA 节点、16 标志词计数全 0;详见 §6) |

---

## 6. 补丁与操控验证(2026-10-20 下午,Goal 执行)

> 承接 §3 落地形态 2 与 §4 建议 1/3:补丁落地后的三路验证(测试套件 / 补丁后 Snapshot / 只读操控)。
> **一句话结论:闭环打通。测试全绿(仅 2 个与补丁无关的环境致败项);首轮 Snapshot 丢 OA 节点的根因并非补丁——Snapshot 只遍历"前台活动窗口 + 任务栏等非应用控件"(`desktop/service.py` L174-190 的既有设计),企微不是前台窗口所以从未进入遍历;`App switch 企业微信` 把它带到前台后,标准 Snapshot 原生读出 OA 全树,Click 页签切换操控验证通过(前后快照结构性差异确凿)。**
>
> | 项 | 值 |
> |---|---|
> | 执行方式 | Workflow 多 agent 编排(测试/Snapshot 验证/入参研究三路并行)+ 主循环串行桌面闭环(复评 §5:同一桌面单代理串行操作) |
> | 改动范围 | `Windows-MCP/src/windows_mcp/tree/service.py` 三处 + `tests/` 测试桩 4 处签名修复 |
> | 安全约束 | 操控仅授权只读导航(切换页签后重读树);保存/发送等 OA 写操作未触碰 |

### 6.1 补丁内容

`Windows-MCP/src/windows_mcp/tree/service.py` 三处改动(即 §3 形态 2 的设计:把 CEF 宿主接进已有的 Firefox IA2 通道):

| # | 位置(约) | 改动内容 |
|---|---|---|
| 1 | L86-135(锚点 L99) | 新增模块级 `_cef_render_child_hwnd()`:Win32 检测窗口子 HWND 中的 `Chrome_RenderWidgetHostHWND` |
| 2 | L295-320(锚点 L302) | `get_window_wise_nodes` 增加 `is_cef` 探测,并把判定结果随窗口数据传递 |
| 3 | L960-1148(锚点 L1090-1148) | `get_nodes` 新增 CEF IA2 合并分支:对 CEF 窗口调用已有 `ia2.traverse_window()` 与 UIA 结果合并,与 Firefox 分支并列;含 3 次唤醒重试(对应 §2.4 Chromium 惰性构建坑)+ 预算封顶;并修正 `use_dom` 返回路径 |

配套:测试桩 4 处签名修复(与补丁后的新签名/结构对齐)。

### 6.2 验证结果汇总

#### A. 测试套件:✅ 补丁验证结果良好

| 项 | 命令/位置 | 结果 |
|---|---|---|
| 目标文件测试 | `uv run --extra dev pytest tests/test_tree_service.py -q` | **37 passed in 0.97s** |
| 全量套件 | 全仓 pytest | **2 failed, 1239 passed, 4 warnings in 133.12s** |
| 静态检查 | `ruff check src/windows_mcp/tree/service.py` | 仅 2 个 W293(空白行含空白,:646、:735)—— 均已知预先存在问题(此前记录的 :645 因补丁插入行偏移为 :646);补丁改动区域(约 L86-135 / L295-320 / L960-1090)无任何新发现 |

两个失败项核查(均与补丁无关):

| # | 失败测试 | 首错 | 判定 |
|---|---|---|---|
| 1 | `tests/test_control_mcp_gate.py::test_stateful_http_client_receives_unsolicited_state_log` | `RuntimeError: Client failed to connect: Using SOCKS proxy, but the 'socksio' package is not installed`(.venv/Lib/site-packages/fastmcp/client/client.py:1048) | 环境致败/疑似预先存在 |
| 2 | `tests/test_scrape_ssrf.py::test_safe_get_ignores_dns_that_changes_after_validation` | `assert 502 == 200`(tests/test_scrape_ssrf.py:205) | 同上 |

**排除证据**:① 两个测试均不在 tree 模块,不导入/不触碰 `src/windows_mcp/tree/service.py`;② `env` 可见 Git Bash 注入的 Clash 代理变量(`ALL_PROXY=socks5://127.0.0.1:7897`、`HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:7897`)泄漏进测试用 httpx 客户端;③ 用 `env -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY` 等清除后重跑这两个失败测试 → **2 passed, 1 warning in 9.94s**。结论:失败由环境代理变量所致,属环境/疑似预先存在问题,非补丁引入。

#### B. 补丁后 Snapshot:✅ 打通(首轮丢失 → 根因定位 → 前台切换后全树读出)

**B1 首轮现象**:Snapshot 调用本身成功(8.6s,无错误,输出 `wmcp_snapshot3.txt`),但企业微信窗口子树中**完全没有 OA 内容**:

- 16 个标志词(新增报销/报销单、保存/发送/流转/终止/发票识别、申请人/申请部门/预算年度/报销方式、报销明细/费用说明/银行信息/审批记录/附件)在快照中计数**全部为 0**
- 企微仅以三种"壳"形态出现:Opened Windows 表行(句柄 133590,与 IA2 dump 的 top hwnd 吻合)、任务栏按钮 `(418,1180) "企业微信 - 1 个运行窗口"`、托盘 `(1712,1180) "企业微信: 陈晶"`;UI 树仅有 `window "✳ 测试 claude-glm…"` / `window "WeMail"` / 无名空 window / 任务栏,无企微命名节点也无子树

交叉对比 `wmcp_snapshot3.txt` ↔ `wmcp_ia2_result3.txt`(5 个元素,**一致性不成立**):

| 元素 | `wmcp_ia2_result3.txt`(IA2 dump,齐全带坐标) | `wmcp_snapshot3.txt` |
|---|---|---|
| 新增报销 document | L11 `[document] '新增报销' val='https://bpm.qiaodan.com/oa/reimburse?type=new&t=179246311699' loc=(61,77,964,1082)` | 缺失(计数 0) |
| 保存 | L912 `[button] '保存' loc=(67,148,44,31)` | 缺失 |
| 发送 | L918 `[button] '发送' loc=(303,148,44,31)` | 缺失 |
| 申请人 | L939 `[text] '申请人' loc=(121,221,37,13)` | 缺失 |
| 报销明细 | L1226 `[text] '报销明细' loc=(94,699,49,15)` | 缺失 |

与 `wmcp_ia2_result3.txt` 交叉对比一致性不成立;同时排除了两大嫌疑:①探针经 `uv run` 确认加载的就是补丁仓库源码;②构件独立复测通过 —— `_cef_render_child_hwnd(133590)` → 返回 199980,`ia2.traverse_window(199980)` → interactive=74、informative=151(名称含 报销单/新增报销/保存)。

**B2 根因定位**(进程内诊断 `wmcp_diag.py`,一轮双实验):

| 实验 | 输入 | 结果 |
|---|---|---|
| Pass 1 全桌面 `Desktop.get_state` | 真实 Snapshot 同路径 | 7.7s,预算仅用 **31/500(未耗尽)**、无异常/重试日志、无 CEF merge 日志,标志词 0 |
| Pass 2 仅企微窗口 `tree.get_state(133590)` | 同一 TreeService | 12.4s,**`CEF IA2 merge for '企业微信' produced 74 interactive / 151 informative nodes`**,标志词全中 |

→ 补丁在真实代码路径完全可用;丢节点与预算、异常无关。真因在 `desktop/service.py` L174-190:**无 region 时,树遍历集合 = 活动窗口 + (controls − apps) 即任务栏/对话框类控件;其他应用窗口要 `if screenshot_region:` 才会并入**。快照时前台是终端,企微从未进入遍历集合 —— 这也一并解释了 §2.2 两轮标准 Snapshot 为空(企微当时同样不是前台窗口)。

**B3 解决与证据**:`App {mode:"switch", name:"企业微信"}` 把企微带到前台 → Snapshot(20.9s,`wmcp_snapshot4.txt`)—— 标准 Snapshot **原生读出 OA 全树**:

- 页签栏:`(85,130) tab "工作台"` / `(134,130) tab "报销单"` / `(204,130) tab "新增报销"`
- 工具栏 8 按钮带坐标:保存(89,163)/商旅订单/导入/发票识别/发送(325,163)/流转/终止/返回
- 表头字段**连值**:单据状态=编制中、申请人=陈晶、申请日期=2026-10-20、职位=高级经理、申请部门=运动表现研究部、币种=人民币、公司=厦门乔丹科技有限公司
- document 节点直给 URL:`https://bpm.qiaodan.com/oa/reimburse?type=new&t=…` [focused]
- 全部区块锚点与表格表头,与 §2.4 IA2 dump、上午 OCR 报告 §6 地图三方吻合

**附带发现(去重优化点)**:Chromium 无障碍被唤醒后 **UIA 面也能读出 CEF 内容** —— snapshot4 中同一内容出现两份渲染(嵌套"选项卡面板"块 + IA2 合并扁平块,坐标一致,报销单页签两处都是 (134,130))。后续可在 UIA 已取到 web 内容时跳过 IA2 合并或做节点级去重。

#### C. 只读操控(页签切换):✅ 通过

同会话四步链(`wmcp_steps2.json`,探针 chain 模式):Snapshot(22.9s)→ **Click loc=(134,130) 点"报销单"页签**(1.4s)→ Snapshot(17.2s)→ App switch 回终端。目标坐标由 snapshot4 树行与 IA2 dump(L903 `tab '报销单' loc=(110,117,48,27)`)双重确认;未触碰任何写操作按钮。

前后快照差异(全部符合"从新建表单切到列表页"的预期;判过标准是结构性变化,非仅"点击返回成功"):

| 信号 | before | after |
|---|---|---|
| document URL | `…/oa/reimburse?type=new&t=…` | **`…/oa/reimburses`(列表页)** |
| 页签面板 | 新增报销 | **报销单** |
| 工具栏 | 保存/商旅订单/导入/发票识别/发送/流转/终止/返回(8 个) | **查询/查看/添加新项/复制/删除/导入模板/导出/流程/更多操作/返回**(列表页工具栏) |
| "编制中"单据状态 | 有 | 无 |
| 快照体量 | 14724 字符 | 22961 字符;行级 diff:仅 before 346 行 / 仅 after 507 行 |
| 列表内容 | — | 搜索字段(单据编号/申请人/申请部门/制单人/收款人/摘要/业务终审人)+ 真实单据行(单据号 CWBX2018060014 等,2025-2026 各期)—— 全程只读查看 |

### 6.3 操控链路结论

**Snapshot(读)→ App switch(切窗)→ Click(动)→ Snapshot(验证)闭环:打通 ✅**

| 环节 | 状态 | 说明 |
|---|---|---|
| Snapshot 读 | ✅ | 前提:目标窗口必须是前台活动窗口(Snapshot 既有设计,非补丁问题);企微前台时 OA 全树原生读出 |
| App switch | ✅ | `App {mode:"switch", name:"企业微信"}`(thefuzz 窗口名模糊匹配,score_cutoff=70) |
| Click 动 | ✅ | Click 只收 `loc=[x,y]` 屏幕坐标(label 下标在快照文本中不打印,外部不可用);坐标来自 Snapshot 树行,与 IA2 同为物理像素,无 DPI 换算 |
| Snapshot 验证 | ✅ | 前后快照行级 diff,以结构性变化(URL/面板/工具栏/体量)判过 |

**标准操作序列(后续复用)**:`App switch 企业微信 → Snapshot → (从树行取目标坐标)→ Click → Snapshot 对比`。注意 **Click 必须与最近一次 Snapshot 同一 server 会话**(工具入口检查 desktop state,跨进程会话会报 "Desktop state is empty")—— 探针的 `chain` 模式即为此而设。

**已知边界与后续优化**:
1. 唤醒后 UIA 与 IA2 双份渲染(见 §6.2B 附带发现)→ 可做去重
2. 全桌面共享元素预算 500(本次企微前台时约用 300),OA 大页若超预算会截断;可用 `WINDOWS_MCP_MAX_TREE_ELEMENTS` 上调
3. 快照文本输出为单行 JSON 数组包一层(探针侧已可解析),如需人读可加展开
4. 浏览器/Electron 系(微信、钉钉等)同构场景可复用本补丁的判定思路:子 HWND 含 `Chrome_RenderWidgetHostHWND` 即走 IA2

### 6.4 新增证据文件(均在 `【feature01-企业微信自动化办公】/`)

| 文件 | 作用 |
|---|---|
| `wmcp_snapshot3.txt` | 补丁后 Snapshot 第三轮输出(8.6s 无错但无 OA 节点 —— "非前台窗口不遍历"的反向证据) |
| `wmcp_diag.py` + `wmcp_diag_run1/run2.log` + `wmcp_diag_summary.txt` | 进程内双 pass 诊断:全桌面路径(31/500 无异常无 merge)vs 仅企微窗口(merge 74+151,标志词全中)—— 根因定位证据 |
| `wmcp_steps1.json` | chain 步骤:App switch 企业微信 → Snapshot |
| `wmcp_snapshot4.txt` | **企微前台后的标准 Snapshot:OA 全树原生读出(读腿成立的正面证据)** |
| `wmcp_steps2.json` | chain 步骤:Snapshot → Click(134,130) → Snapshot → switch 回终端 |
| `wmcp_ctrl_before/click/after.txt` | 操控三件套:点击前基线 / Click 返回 / 点击后快照 |
| `wmcp_ctrl_diff.txt` | 前后行级 diff(仅 before 346 行 / 仅 after 507 行) |
| `wmcp_ctrl_after_signals.txt` | after 页关键信号抽取(列表 URL/工具栏/搜索字段/真实单据行) |
| `wmcp_switch_out.txt` / `wmcp_ctrl_switchback.txt` | App switch 前台切换与切回终端的返回文本 |

---

*报告完。上午 OCR 视觉路线的姊妹篇见 `企业微信-报销单-页面探索报告.md`;复评原文见 `自动化热门repo.md`。*
