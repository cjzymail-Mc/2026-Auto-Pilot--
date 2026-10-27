[Console]::OutputEncoding = [Text.Encoding]::UTF8
$o = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" |
     Where-Object { $_.CommandLine -match 'pw-profile' }
if ($o) { $o | ForEach-Object { 'orphan pid=' + $_.ProcessId } }
else { 'no orphan chrome on pw-profile' }
