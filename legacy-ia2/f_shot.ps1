# Minimize terminal windows, take a clean screenshot (of foreground WeCom OA), restore them.
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
$handles = New-Object System.Collections.ArrayList
foreach ($w in (Get-Process | Where-Object { $_.MainWindowHandle -ne 0 })) {
    if ($w.ProcessName -match 'mintty|WindowsTerminal|^cmd$|powershell|conhost') {
        $r = New-Object W32+RECT
        [void][W32]::GetWindowRect($w.MainWindowHandle, [ref]$r)
        $area = ($r.R - $r.L) * ($r.B - $r.T)
        if ($area -gt 300000) { [void]$handles.Add($w.MainWindowHandle) }
    }
}
try {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 6) }
    Start-Sleep -Milliseconds 800
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
    $g.Dispose()
    $out = Join-Path $PSScriptRoot 'f_shot1.png'
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output "SCREENSHOT SAVED"
}
finally {
    foreach ($h in $handles) { [void][W32]::ShowWindow($h, 9) }
    Start-Sleep -Milliseconds 300
    Write-Output ("RESTORED {0} window(s)" -f $handles.Count)
}
