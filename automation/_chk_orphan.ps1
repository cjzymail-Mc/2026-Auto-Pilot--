$orphans = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match 'pw-profile' }
if ($orphans) {
  $orphans | ForEach-Object {
    Write-Output ("orphan PID {0}" -f $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
} else {
  Write-Output "no orphan chrome on pw-profile"
}
