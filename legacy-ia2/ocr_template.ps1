param([string]$ImagePath, [string]$OutPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]

function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}

$langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
$langList = ($langs | ForEach-Object { $_.LanguageTag }) -join ','

$engine = $null
foreach ($l in $langs) { if ($l.LanguageTag -like 'zh*') { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($l); break } }
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine("LANGS=$langList")
[void]$sb.AppendLine("MAXDIM=$([Windows.Media.Ocr.OcrEngine]::MaxImageDimension)")
if (-not $engine) {
  [void]$sb.AppendLine("NO_ENGINE")
  [IO.File]::WriteAllText($OutPath, $sb.ToString(), [Text.Encoding]::UTF8)
  Write-Output "NO_ENGINE langs=$langList"
  exit 2
}

$path = [IO.Path]::GetFullPath($ImagePath)
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($path)) ([Windows.Storage.StorageFile])
$imgSrc = Await ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($imgSrc)) ([Windows.Graphics.Imaging.BitmapDecoder])
$soft = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
[void]$sb.AppendLine("IMG=$($soft.PixelWidth)x$($soft.PixelHeight)")

$res = Await ($engine.RecognizeAsync($soft)) ([Windows.Media.Ocr.OcrResult])
$i = 0
foreach ($line in $res.Lines) {
  $txt = $line.Text
  $words = @($line.Words)
  if ($words.Count -gt 0) {
    $r = $words[0].BoundingRect
    $px = [int][double]$r.X; $py = [int][double]$r.Y; $pw = [int][double]$r.Width; $ph = [int][double]$r.Height
    [void]$sb.AppendLine("$px,$py ${pw}x$ph  $txt")
  } else {
    [void]$sb.AppendLine(",,,,  $txt")
  }
  $i++
}
[void]$sb.AppendLine("TOTAL_LINES=$i")
[IO.File]::WriteAllText($OutPath, $sb.ToString(), [Text.Encoding]::UTF8)
Write-Output "DONE lines=$i"
