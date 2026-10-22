# Capture a screen region and Windows-OCR it (upscaled). Usage:
#   pwsh -File cap_ocr.ps1 -X0 840 -Y0 405 -X1 1370 -Y1 720 -Out dlg [-Scale 4] [-Bin 0]
param(
  [int]$X0, [int]$Y0, [int]$X1, [int]$Y1,
  [string]$Out = 'cap',
  [int]$Scale = 4,
  [int]$Bin = 0   # 0=off, else luminance threshold (e.g. 175) for binarization
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
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
if ($Bin -gt 0) {
  for ($x = 0; $x -lt $big.Width; $x++) {
    for ($y = 0; $y -lt $big.Height; $y++) {
      $p = $big.GetPixel($x, $y)
      $l = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
      $v = if ($l -lt $Bin) { 0 } else { 255 }
      $big.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($v, $v, $v))
    }
  }
}
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
