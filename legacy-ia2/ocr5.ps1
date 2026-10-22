# OCR wecom_explore_4.png left half (user's new split layout), 2x upscale
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
if (-not $engine) { throw 'OCR engine init failed' }
$dir = $PSScriptRoot
$src = [System.Drawing.Image]::FromFile((Join-Path $dir 'wecom_explore_4.png'))

$regions = [ordered]@{
    'r4_band1' = @(0, 0, 1050, 400)
    'r4_band2' = @(0, 350, 1050, 800)
    'r4_band3' = @(0, 750, 1050, 1200)
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("=== OCR of wecom_explore_4.png (left half, new split layout) ===")

foreach ($name in $regions.Keys) {
    $r = $regions[$name]
    $scale = 2
    $w = [int]($r[2] - $r[0]); $h = [int]($r[3] - $r[1])
    $w2 = [int]($w * $scale); $h2 = [int]($h * $scale)

    $bmp = New-Object System.Drawing.Bitmap($w2, $h2)
    $bmp.SetResolution(192, 192)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $dst = New-Object System.Drawing.Rectangle(0, 0, $w2, $h2)
    $srcR = New-Object System.Drawing.Rectangle([int]$r[0], [int]$r[1], $w, $h)
    $g.DrawImage($src, $dst, $srcR, [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()

    $tmp = Join-Path $env:TEMP ("ocr5_" + $name + ".png")
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()

    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])

        $allLines = @($result.Lines)
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("===== $name rect=$($r[0]),$($r[1]),$($r[2]),$($r[3]) lines=$($allLines.Count) =====")
        foreach ($line in $allLines) {
            $words = @($line.Words)
            if ($words.Count -eq 0) { continue }
            $br = $words[0].BoundingRect
            $sx = [math]::Round($r[0] + $br.X / $scale)
            $sy = [math]::Round($r[1] + $br.Y / $scale)
            [void]$sb.AppendLine(("{0,5},{1,5}  {2}" -f $sx, $sy, $line.Text))
        }
        $stream.Dispose()
        Remove-Item $tmp -ErrorAction SilentlyContinue
    } catch {
        [void]$sb.AppendLine("ERROR in ${name}: " + $_.Exception.Message)
    }
}
$src.Dispose()
[System.IO.File]::WriteAllText((Join-Path $dir 'ocr_result5.txt'), $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output "DONE"
