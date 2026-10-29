# Windows-MCP 固定版本重建说明

本页用于分享父仓库后复现早期 CEF/IA2 桌面探索环境。当前报销生产实现位于 `bpm/`、`tools/`，使用 Playwright；运行它们不要求安装 Windows-MCP。目录定位见 [repository-layout.md](repository-layout.md)。

**状态：重建步骤尚未在干净环境实跑验收。** 2026-10-29 只做了本地源码、补丁、依赖声明及命令语法核对，没有 clone、安装依赖、启动服务或操作桌面/OA。下述安装、测试命令是待执行步骤，不是通过记录；本页也不构成 OA 访问或改变网络/MCP 配置的授权。

## 固定基线与分享范围

| 项目 | 固定值 / 来源 |
|---|---|
| 上游源码 | [CursorTouch/Windows-MCP](https://github.com/CursorTouch/Windows-MCP)；重建取源码，不用 PyPI 最新包替代本地补丁版 |
| Git 提交 | `5b24a8ab5c453e691feb6402cf455d83cf10998e`；不要直接使用 clone 后的 main |
| 项目版本 | 该提交的 `pyproject.toml` 为 `windows-mcp 0.8.8`，要求 Python `>=3.14` |
| Python 基线 | 该提交的 `.python-version` 为 `3.14.7`；与父项目执行器的 Python 环境分开 |
| 依赖锁 | 该提交的 `uv.lock`；开发依赖在 `project.optional-dependencies.dev`，用 `--extra dev`，不是 `--group dev` |
| 本地补丁 | [windows-mcp@5b24a8a-cef-ia2.patch](../patches/windows-mcp@5b24a8a-cef-ia2.patch)，修改 `src/windows_mcp/tree/service.py` 与 `tests/test_tree_service.py` |
| 补丁 Git blob | `20c65bf261f4537b04aff1ea8ec45912a32ac9ba`；下方用父仓库的 Git 换行过滤规则核验，兼容正常的 LF/CRLF 检出 |
| 本次补丁文件 SHA256 | `6ca3948247ecea2eb856860743e464b3fff333d4216ac3bf19cf79166b024bc1`，对应本次核对的 LF 文件；不同换行的工作副本不能仅凭裸字节 SHA256 判定内容漂移 |

`Windows-MCP/` 有自己的 `.git`，被父仓库 [.gitignore](../.gitignore) 排除；补丁文件本身已由父仓库跟踪。`legacy-ia2/` 是本地只读历史存档，新克隆缺少其中的探针、截图和运行输出是预期状态。分享重建所需的是父仓库中的说明与补丁，加上固定提交的上游源码；不要复制原机器的 `.venv`、认证缓存或个人 MCP 配置。

## 前置环境

- Windows 10/11，Git 与 uv 已安装且可从 PowerShell 调用。依据为固定源码的 README 和 `pyproject.toml`，其他系统不在本文验证范围。
- Python 使用固定源码的 `3.14.7`；uv 可按 `.python-version` 管理解释器。首次同步可能需要下载 Python 和依赖，须在允许下载的环境执行，不为重建改动现有代理、路由或安全设置。
- 以下代码块按顺序在同一 PowerShell 会话执行，起始目录为**接收方的父仓库根目录**。目标 `Windows-MCP/` 必须不存在；当前机器已有该目录时应停止，另选干净的父仓库副本验证，不覆盖已有工作。

## 取得固定源码并应用补丁

先核验随父仓库收到的补丁，再 clone。没有 `--depth 1`，避免浅克隆缺少固定提交；所有原生命令失败都应停下核查。

```powershell
$parentRepo = (Get-Location).Path
$wmcpDir = Join-Path $parentRepo 'Windows-MCP'
$patchRelative = 'patches/windows-mcp@5b24a8a-cef-ia2.patch'
$patchFile = Join-Path $parentRepo $patchRelative
$baseCommit = '5b24a8ab5c453e691feb6402cf455d83cf10998e'
$expectedPatchBlob = '20c65bf261f4537b04aff1ea8ec45912a32ac9ba'

Get-Command git, uv -ErrorAction Stop | Out-Null
if (-not (Test-Path -LiteralPath $patchFile -PathType Leaf)) {
    throw '缺少父仓库补丁；先确认当前目录与收到的文件。'
}
if (Test-Path -LiteralPath $wmcpDir) {
    throw 'Windows-MCP 目录已存在；保留它，另选干净副本重建。'
}

# 不加 -w：只核验内容，不写 Git 对象；按父仓库规则处理文本换行。
$patchBlob = git -C $parentRepo hash-object --path="$patchRelative" "$patchFile"
if ($LASTEXITCODE -ne 0) { throw '补丁 Git 内容校验失败。' }
if ($patchBlob.Trim() -ne $expectedPatchBlob) { throw '补丁与固定基线不同，停止。' }

git clone --no-checkout https://github.com/CursorTouch/Windows-MCP.git "$wmcpDir"
if ($LASTEXITCODE -ne 0) { throw 'clone 失败；保留现场，不继续。' }
git -C "$wmcpDir" checkout --detach $baseCommit
if ($LASTEXITCODE -ne 0) { throw '固定提交不可用；不要改用 main。' }
$actualHead = git -C "$wmcpDir" rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw '无法核对 HEAD。' }
if ($actualHead.Trim() -ne $baseCommit) { throw 'HEAD 与固定提交不符。' }

git -C "$wmcpDir" apply --check "$patchFile"
if ($LASTEXITCODE -ne 0) { throw '补丁预检失败；不要强制应用。' }
git -C "$wmcpDir" apply "$patchFile"
if ($LASTEXITCODE -ne 0) { throw '补丁应用失败；保留现场核查。' }
git -C "$wmcpDir" diff --stat
if ($LASTEXITCODE -ne 0) { throw '无法读取补丁结果。' }
```

该补丁的预期差异为两文件、116 行新增/9 行删除。数量只作辅助检查；继续前还要核对完整 diff 和上述版本/补丁身份，不能只凭行数相同判为成功。

## 同步依赖与必要验证

以下步骤尚未在干净环境执行。`--frozen` 使用固定源码已有的锁文件，不以重算锁文件来消除失败；`--extra dev` 安装其中声明的 pytest 等测试依赖。

```powershell
uv --directory "$wmcpDir" sync --frozen --extra dev
if ($LASTEXITCODE -ne 0) { throw '依赖同步失败；不继续验证。' }
uv --directory "$wmcpDir" run --frozen --extra dev python --version
if ($LASTEXITCODE -ne 0) { throw '解释器检查失败。' }
uv --directory "$wmcpDir" run --frozen --extra dev windows-mcp --help
if ($LASTEXITCODE -ne 0) { throw '源码 CLI 检查失败。' }
uv --directory "$wmcpDir" run --frozen --extra dev pytest tests/test_tree_service.py
if ($LASTEXITCODE -ne 0) { throw 'TreeService 回归失败。' }
git -C "$wmcpDir" status --short
if ($LASTEXITCODE -ne 0) { throw '无法检查重建后的工作区。' }
```

逐项记录实际命令、退出码、Python/uv 版本、提交与补丁身份及输出。`uv.lock` 不应因 frozen 同步被改写；预期源码改动仍是补丁的两个文件，出现额外改动先核查。

这些检查至多证明源码 CLI 与目标单元回归通过，**不等于当前桌面的 CEF/IA2 能力验收**。如需重新启用桌面路线，还须另行验证 MCP 握手、目标窗口前台状态、Snapshot 字段与截图的一致性，以及授权范围内的只读导航；不自动注册 MCP、创建开机任务或启动网络服务，也不因重建而执行报销业务。

## 历史证据与本次验证分层

- [Windows-MCP 路线实测报告](路线与评估/Windows-MCP路线实测报告.md)记录了 CEF/IA2 补丁后的控件树读取和只读操控闭环，也记录了前台窗口要求、全桌面预算及重复渲染等限制。它证明历史环境中该路线可行，不能证明任意新机器可直接使用。
- 2026-10-29 本地离线核对：固定 HEAD 正确；现有工作树 diff 与父仓库补丁字节级一致；补丁与父仓库 HEAD 中的已跟踪文件一致；针对原始 Git 索引的 `git apply --cached --check` 和针对现有工作树的 `git apply --reverse --check` 均返回 0，索引字节未变。未实际应用或撤销补丁。
- 本次还核对了固定源码的 Python 版本、`dev` extra、锁内 pytest 依赖和本页 PowerShell 语法及链接。**干净 clone、依赖同步、CLI/单测运行、MCP 握手和当前桌面实测仍未执行。**

## 常见问题与回退

| 情况 | 处理 |
|---|---|
| 已有 `Windows-MCP/`，或目录有用户修改 | 停止上述 clone 流程；保留原目录和 diff，在另一份干净父仓库中验证。不执行 reset/clean 或自动删除目录 |
| 找不到固定提交 | 核对来源与完整提交，确认是否使用了浅克隆或上游历史发生变化；不替换成 main/最新版凑通过 |
| 补丁哈希或 apply 预检失败 | 先核对固定 HEAD、补丁 Git blob、换行规则与是否已应用；不要跳过校验或用强制/reject 模式继续 |
| 缺少 pytest | 使用 `--extra dev`；这是 optional-dependencies extra，不是名为 dev 的 dependency group |
| Python/锁定依赖无法取得 | 保留失败输出，在允许下载的环境解决依赖；不修改 OA 网络或安全配置、不通过更新锁文件冒充同一基线 |
| CLI/单测通过，但 Snapshot 无 OA 字段 | 回到历史报告核对前台窗口、CEF 子窗口、IA2 唤醒及预算条件；保留差异，按当前机器另验，不能把历史成功作为当次通过 |
| 分享后没有 `legacy-ia2/` 原始探针或截图 | 本地存档未随 Git 分享是预期状态；如确需重现原探针，另行取得适用工件，不复制业务资料或认证目录 |

重建失败时保留隔离目录和输出，继续使用现有 Playwright 生产入口；这项外部依赖的失败不要求改动报销执行器。若要撤销现有补丁，应先保存全部本地差异并确认归属，再单独评估；本文不提供覆盖或清理已有环境的自动回退步骤。
