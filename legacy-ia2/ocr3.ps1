# OCR wecom_explore_3.png (scrolled-down form view), 2x upscale, write ocr_result3.txt
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
$src = [System.Drawing.Image]::FromFile((Join-Path $dir 'wecom_explore_3.png'))

# after scroll the form column is x=0..~1050; slice vertically + a 3x pass on the button band
$regions = [ordered]@{
    'r3_band1'   = @(0, 0, 1050, 400)
    'r3_band2'   = @(0, 350, 1050, 800)
    'r3_band3'   = @(0, 750, 1050, 1200)
    'r3_btns3x'  = @(300, 780, 1050, 980)   # 3x upscale on suspected button/section area
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("=== OCR of wecom_explore_3.png (form scrolled down 6 notches) ===")

foreach ($name in $regions.Keys) {
    $r = $regions[$name]
    $scale = if ($name -like '*3x') { 3 } else { 2 }
    $w = $r[2] - $r[0]; $h = $r[3] - $r[1]
    if ($w -le 0 -or $h -le 0) { continue }
    $w2 = $w * $scale; $h2 = $h * $scale
    $bmp = New-Object System.Drawing.Bitmap($w2, $h2)
    $bmp.SetResolution(192, 192)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle(0, 0, $w2, $h2)),
        (New-Object System.Drawing.Rectangle($r[0], $r[1], $w, $h)), [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()

    $tmp = Join-Path $env:TEMP ("ocr3_" + $name + ".png")
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()

    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])

        $allLines = @($result.Lines)
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("===== $name rect=$($r[0]),$($r[1]),$($r[2]),$($r[3]) scale=$scale lines=$($allLines.Count) =====")
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
[System.IO.File]::WriteAllText((Join-Path $dir 'ocr_result3.txt'), $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output "DONE"
