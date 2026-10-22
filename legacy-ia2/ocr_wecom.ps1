# Windows.Media.Ocr local OCR: extract text + screen coords from crops
# Output written to ocr_result.txt (UTF-8) to avoid console encoding issues
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
if (-not $engine) { throw 'OCR engine init failed (no zh language pack?)' }

$dir = $PSScriptRoot
$outPath = Join-Path $dir 'ocr_result.txt'
$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("OCR lang: " + $engine.RecognizerLanguage.LanguageTag)

# file => screen offset of the crop
$targets = @(
    @{ file = 'wecom_1_crop_top.png';      ox = 0;   oy = 0   },
    @{ file = 'wecom_1_crop_leftnav.png';  ox = 0;   oy = 170 },
    @{ file = 'wecom_1_crop_main_up.png';  ox = 320; oy = 100 },
    @{ file = 'wecom_1_crop_main_mid.png'; ox = 320; oy = 600 },
    @{ file = 'wecom_1_crop_bottom.png';   ox = 0;   oy = 900 }
)

foreach ($t in $targets) {
    $srcPath = Join-Path $dir $t.file
    if (-not (Test-Path -LiteralPath $srcPath)) { [void]$sb.AppendLine("MISSING: " + $t.file); continue }
    try {
        $src = [System.Drawing.Image]::FromFile($srcPath)
        $w2 = $src.Width * 2; $h2 = $src.Height * 2
        $bmp = New-Object System.Drawing.Bitmap($w2, $h2)
        $bmp.SetResolution(192, 192)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.DrawImage($src, 0, 0, $w2, $h2)
        $g.Dispose(); $src.Dispose()

        $tmp = Join-Path $env:TEMP ("ocr_tmp_" + [IO.Path]::GetFileNameWithoutExtension($t.file) + ".png")
        $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()

        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])

        [void]$sb.AppendLine("")
        $allLines = @($result.Lines)
        [void]$sb.AppendLine("===== " + $t.file + " (offset " + $t.ox + "," + $t.oy + ") lines=" + $allLines.Count + " =====")
        foreach ($line in $allLines) {
            $words = @($line.Words)
            if ($words.Count -eq 0) { continue }
            $r = $words[0].BoundingRect
            $sx = [math]::Round($t.ox + $r.X / 2)
            $sy = [math]::Round($t.oy + $r.Y / 2)
            [void]$sb.AppendLine(("{0,5},{1,5}  {2}" -f $sx, $sy, $line.Text))
        }
        $stream.Dispose()
        Remove-Item $tmp -ErrorAction SilentlyContinue
    } catch {
        [void]$sb.AppendLine("ERROR in " + $t.file + " :: " + $_.Exception.GetType().Name + " :: " + $_.Exception.Message)
        if ($_.Exception.InnerException) { [void]$sb.AppendLine("  inner: " + $_.Exception.InnerException.Message) }
        continue
    }
}

[System.IO.File]::WriteAllText($outPath, $sb.ToString(), (New-Object System.Text.UTF8Encoding($false)))
Write-Output ("DONE -> " + $outPath)
