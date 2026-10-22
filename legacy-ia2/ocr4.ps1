# Button-band OCR with preprocessing: 4x upscale + grayscale, normal & inverted passes
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
$scale = 4

function Convert-Bitmap($srcBmp, $invert) {
    $v = if ($invert) { -1.0 } else { 1.0 }
    $cm = New-Object System.Drawing.Imaging.ColorMatrix
    $cm.Matrix00 = 0.299 * $v; $cm.Matrix01 = 0.299 * $v; $cm.Matrix02 = 0.299 * $v
    $cm.Matrix10 = 0.587 * $v; $cm.Matrix11 = 0.587 * $v; $cm.Matrix12 = 0.587 * $v
    $cm.Matrix20 = 0.114 * $v; $cm.Matrix21 = 0.114 * $v; $cm.Matrix22 = 0.114 * $v
    $cm.Matrix33 = 1.0; $cm.Matrix44 = 1.0
    if ($invert) { $cm.Matrix40 = 1.0; $cm.Matrix41 = 1.0; $cm.Matrix42 = 1.0 }
    $out = New-Object System.Drawing.Bitmap($srcBmp.Width, $srcBmp.Height)
    $g = [System.Drawing.Graphics]::FromImage($out)
    $ia = New-Object System.Drawing.Imaging.ImageAttributes
    $ia.SetColorMatrix($cm)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $out.Width, $out.Height)
    $g.DrawImage($srcBmp, $rect, 0, 0, $srcBmp.Width, $srcBmp.Height, [System.Drawing.GraphicsUnit]::Pixel, $ia)
    $g.Dispose(); $ia.Dispose()
    return $out
}

function Invoke-OcrBitmap($bmp, $offX, $offY, $tag, $sb) {
    $tmp = Join-Path $env:TEMP ("ocr4_" + $tag + ".png")
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])
    foreach ($line in @($result.Lines)) {
        $words = @($line.Words)
        if ($words.Count -eq 0) { continue }
        $br = $words[0].BoundingRect
        $sx = [math]::Round($offX + $br.X / $scale)
        $sy = [math]::Round($offY + $br.Y / $scale)
        [void]$sb.AppendLine(("{0,5},{1,5}  {2}" -f $sx, $sy, $line.Text))
    }
    $stream.Dispose()
    Remove-Item $tmp -ErrorAction SilentlyContinue
}

# tag => x1, y1, x2, y2
$regions = [ordered]@{
    'e2_btnband'  = @(40, 850, 1050, 980)
    'e2_apprband' = @(40, 930, 1050, 1060)
    'e3_btnband'  = @(40, 850, 1050, 980)
    'e3_apprband' = @(40, 930, 1050, 1060)
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("=== Button-band OCR: 4x + grayscale, normal & inverted ===")

foreach ($tag in $regions.Keys) {
    $r = $regions[$tag]
    $srcFile = if ($tag.StartsWith('e2')) { 'wecom_explore_2.png' } else { 'wecom_explore_3.png' }
    $img = [System.Drawing.Image]::FromFile((Join-Path $dir $srcFile))

    $w = [int]($r[2] - $r[0]); $h = [int]($r[3] - $r[1])
    $w2 = [int]($w * $scale); $h2 = [int]($h * $scale)

    $bmp = New-Object System.Drawing.Bitmap($w2, $h2)
    $bmp.SetResolution(384, 384)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $dst = New-Object System.Drawing.Rectangle(0, 0, $w2, $h2)
    $srcR = New-Object System.Drawing.Rectangle([int]$r[0], [int]$r[1], $w, $h)
    $g.DrawImage($img, $dst, $srcR, [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()
    $img.Dispose()

    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("--- $tag [gray] ---")
    $gray = Convert-Bitmap $bmp $false
    Invoke-OcrBitmap $gray ([int]$r[0]) ([int]$r[1]) ("g_" + $tag) $sb
    $gray.Dispose()

    [void]$sb.AppendLine("--- $tag [inverted] ---")
    $inv = Convert-Bitmap $bmp $true
    Invoke-OcrBitmap $inv ([int]$r[0]) ([int]$r[1]) ("i_" + $tag) $sb
    $inv.Dispose()

    $bmp.Dispose()
}
[System.IO.File]::WriteAllText((Join-Path $dir 'ocr_result4.txt'), $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output "DONE"
