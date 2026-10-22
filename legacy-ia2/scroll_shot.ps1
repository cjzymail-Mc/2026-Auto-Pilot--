# Read-only interaction test: minimize terminals, scroll the WeCom form DOWN, screenshot, scroll back UP, restore.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class W32 {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, int dwData, UIntPtr dwExtraInfo);
  public struct RECT { public int L, T, R, B; }
}
'@

$wins = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 }

# minimize terminal windows (same filter as minimize_shot.ps1)
$handles = New-Object System.Collections.ArrayList
foreach ($w in $wins) {
    if ($w.ProcessName -match 'mintty|WindowsTerminal|^cmd$|powershell|conhost') {
        $r = New-Object W32+RECT
        [void][W32]::GetWindowRect($w.MainWindowHandle, [ref]$r)
        if ((($r.R - $r.L) * ($r.B - $r.T)) -gt 300000) {
            Write-Output ("MINIMIZE: {0} '{1}'" -f $w.ProcessName, $w.MainWindowTitle)
            [void]$handles.Add($w.MainWindowHandle)
        }
    }
}

$wx = $wins | Where-Object { $_.ProcessName -eq 'WXWork' } | Select-Object -First 1
if (-not $wx) { Write-Output 'WARN: WXWork window not found' }

try {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 6) }   # SW_MINIMIZE
    Start-Sleep -Milliseconds 700

    if ($wx) {
        [void][W32]::SetForegroundWindow($wx.MainWindowHandle)
        Start-Sleep -Milliseconds 500
    }

    # park cursor over the form area (safe: no control there, just form background)
    [void][W32]::SetCursorPos(500, 700)
    Start-Sleep -Milliseconds 300

    # scroll DOWN 6 notches (MOUSEEVENTF_WHEEL=0x800, negative = down)
    for ($i = 0; $i -lt 6; $i++) {
        [W32]::mouse_event(0x0800, 0, 0, -120, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 130
    }
    Start-Sleep -Milliseconds 800

    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
    $g.Dispose()
    $out = Join-Path $PSScriptRoot 'wecom_explore_3.png'
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output "SCREENSHOT: $out"

    # scroll back UP to restore original view
    for ($i = 0; $i -lt 6; $i++) {
        [W32]::mouse_event(0x0800, 0, 0, 120, [UIntPtr]::Zero)
        Start-Sleep -Milliseconds 110
    }
    Write-Output 'SCROLLED BACK UP'
}
finally {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 9) }   # SW_RESTORE
    Start-Sleep -Milliseconds 300
    Write-Output ("RESTORED {0} window(s)" -f $handles.Count)
}
