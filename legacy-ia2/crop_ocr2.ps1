# Crop wecom_explore_2.png into regions, then Windows-OCR each region (2x upscale).
$ErrorActionPreference = 'Stop'
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

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (-not $engine) { throw 'no OCR engine' }
$dir = $PSScriptRoot
$src = [System.Drawing.Image]::FromFile((Join-Path $dir 'wecom_explore_2.png'))

# name => x1,y1,x2,y2 (screen coords)
$regions = @{
    'r2_header'  = @(0, 0, 1920, 175)
    'r2_leftnav' = @(0, 175, 320, 1200)
    'r2_form_a'  = @(320, 100, 1150, 660)
    'r2_form_b'  = @(1100, 100, 1920, 660)
    'r2_form_c'  = @(320, 620, 1150, 950)
    'r2_form_d'  = @(1100, 620, 1920, 950)
    'r2_bottom'  = @(320, 900, 1920, 1200)
}

$sb = New-Object System.Text.StringBuilder
foreach ($name in ($regions.Keys | Sort-Object)) {
    $r = $regions[$name]
    $w = $r[2] - $r[0]; $h = $r[3] - $r[1]
    $bmp = New-Object System.Drawing.Bitmap($w, $h)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle(0, 0, $w, $h)),
        (New-Object System.Drawing.Rectangle($r[0], $r[1], $w, $h)), [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()

    # 2x upscale for OCR
    $big = New-Object System.Drawing.Bitmap(($w * 2), ($h * 2))
    $g2 = [System.Drawing.Graphics]::FromImage($big)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($bmp, 0, 0, ($w * 2), ($h * 2))
    $g2.Dispose(); $bmp.Dispose()

    $tmp = Join-Path $env:TEMP ("ocr2_" + $name + ".png")
    $big.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $big.Dispose()

    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])

    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("===== $name (offset $($r[0]),$($r[1])) lines=$(@($result.Lines).Count) =====")
    foreach ($line in @($result.Lines)) {
        $words = @($line.Words)
        if ($words.Count -eq 0) { continue }
        $br = $words[0].BoundingRect
        $sx = [math]::Round($r[0] + $br.X / 2)
        $sy = [math]::Round($r[1] + $br.Y / 2)
        [void]$sb.AppendLine(("{0,5},{1,5}  {2}" -f $sx, $sy, $line.Text))
    }
    $stream.Dispose()
    Remove-Item $tmp -ErrorAction SilentlyContinue
}
$src.Dispose()
[System.IO.File]::WriteAllText((Join-Path $dir 'ocr_result2.txt'), $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output 'DONE -> ocr_result2.txt'
