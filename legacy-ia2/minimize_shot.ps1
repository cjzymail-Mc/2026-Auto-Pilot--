# Minimize terminal windows, take a clean screenshot, restore them.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class W32 {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  public struct RECT { public int L, T, R, B; }
}
'@

$wins = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 } |
    Select-Object Id, ProcessName, MainWindowTitle, MainWindowHandle

# log all windows for reference
$log = ($wins | ForEach-Object { "$($_.ProcessName) | $($_.MainWindowTitle) | $($_.MainWindowHandle)" }) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'window_list.txt'), $log, (New-Object System.Text.UTF8Encoding($false)))

# terminal-class processes whose window is big enough to cover the page
$handles = New-Object System.Collections.ArrayList
foreach ($w in $wins) {
    if ($w.ProcessName -match 'mintty|WindowsTerminal|^cmd$|powershell|conhost') {
        $r = New-Object W32+RECT
        [void][W32]::GetWindowRect($w.MainWindowHandle, [ref]$r)
        $area = ($r.R - $r.L) * ($r.B - $r.T)
        if ($area -gt 300000) {
            Write-Output ("MINIMIZE: {0} '{1}' rect={2},{3},{4},{5}" -f $w.ProcessName, $w.MainWindowTitle, $r.L, $r.T, $r.R, $r.B)
            [void]$handles.Add($w.MainWindowHandle)
        }
    }
}

try {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 6) }   # SW_MINIMIZE
    Start-Sleep -Milliseconds 800

    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
    $g.Dispose()
    $out = Join-Path $PSScriptRoot 'wecom_explore_2.png'
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output "SCREENSHOT SAVED: $out"
}
finally {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 9) }   # SW_RESTORE
    Start-Sleep -Milliseconds 300
    Write-Output ("RESTORED {0} window(s)" -f $handles.Count)
}
