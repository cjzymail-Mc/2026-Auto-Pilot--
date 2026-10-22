param([string]$Keys)
$ws = New-Object -ComObject WScript.Shell
$ws.SendKeys($Keys)
