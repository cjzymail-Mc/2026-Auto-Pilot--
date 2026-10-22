# Continue this conversation with terminal scrollback enabled.
# Use -NewChat to start a new conversation with the same display mode.
[CmdletBinding()]
param(
    [switch]$NewChat,
    [string]$SessionId = '01a132c0-edac-7c13-9f7e-f827645ed41c'
)

$ErrorActionPreference = 'Stop'
$codexCommand = Get-Command codex.exe -CommandType Application -ErrorAction SilentlyContinue
$codexExecutable = if ($codexCommand) {
    $codexCommand.Source
} else {
    Join-Path $env:LOCALAPPDATA 'Programs\codex\bin\codex.exe'
}

if (-not (Test-Path -LiteralPath $codexExecutable -PathType Leaf)) {
    throw 'Codex executable was not found. Install Codex or add codex.exe to PATH.'
}

$codexLaunchArguments = @('--no-alt-screen', '--cd', $PSScriptRoot)
if (-not $NewChat) {
    if ([string]::IsNullOrWhiteSpace($SessionId)) {
        throw 'Specify a session ID, or use -NewChat to start a new conversation.'
    }
    $codexLaunchArguments = @('resume', $SessionId) + $codexLaunchArguments
}

& $codexExecutable @codexLaunchArguments
if ($LASTEXITCODE -ne 0) {
    throw "Codex exited with code $LASTEXITCODE."
}
