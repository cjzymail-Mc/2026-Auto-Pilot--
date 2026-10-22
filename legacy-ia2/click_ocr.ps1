# Click a screen point, then immediately capture+OCR a region (catch transient popups).
# Usage: -X 538 -Y 436 -X0 460 -Y0 440 -X1 900 -Y1 660 -Out dd [-Delay 800] [-Scale 6]
param(
  [int]$X, [int]$Y,
  [int]$X0, [int]$Y0, [int]$X1, [int]$Y1,
  [string]$Out = 'dd',
  [int]$Delay = 800,
  [int]$Scale = 6,
  [int]$Clicks = 1
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# bring WeCom foreground is caller's job; just activate window under point? No - send click directly.
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class UserInput {
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
  public const uint LEFTDOWN = 0x02, LEFTUP = 0x04;
}
"@
[UserInput]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 150
for ($i = 0; $i -lt $Clicks; $i++) {
  [UserInput]::mouse_event([UserInput]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
  [UserInput]::mouse_event([UserInput]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
  if ($i -lt $Clicks - 1) { Start-Sleep -Milliseconds 120 }
}

Start-Sleep -Milliseconds $Delay

# --- capture + OCR (same as cap_ocr.ps1) ---
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine,Windows.Media.Ocr,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult,Windows.Media.Ocr,ContentType=WindowsRuntime]
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}
$dir = $PSScriptRoot
$w = $X1 - $X0; $h = $Y1 - $Y0
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($X0, $Y0, 0, 0, (New-Object System.Drawing.Size($w, $h)))
$g.Dispose()
$raw = Join-Path $dir "$Out.png"
$bmp.Save($raw, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
$src = [System.Drawing.Image]::FromFile($raw)
$big = New-Object System.Drawing.Bitmap ($w * $Scale), ($h * $Scale)
$g2 = [System.Drawing.Graphics]::FromImage($big)
$g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g2.DrawImage($src, 0, 0, $w * $Scale, $h * $Scale)
$g2.Dispose(); $src.Dispose()
$up = Join-Path $dir "${Out}_${Scale}x.png"
$big.Save($up, [System.Drawing.Imaging.ImageFormat]::Png)
$big.Dispose()
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($up)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$sbmp = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$res = Await ($engine.RecognizeAsync($sbmp)) ([Windows.Media.Ocr.OcrResult])
$lines = @()
foreach ($l in $res.Lines) {
  $box = ($l.Words | Select-Object -First 1).BoundingRect
  $sx = [math]::Round($X0 + $box.X / $Scale); $sy = [math]::Round($Y0 + $box.Y / $Scale)
  $lines += ("{0,4},{1,4}  {2}" -f $sx, $sy, ($l.Text -join ' '))
}
Write-Output ("LINES={0}" -f $lines.Count)
$lines | ForEach-Object { Write-Output $_ }
