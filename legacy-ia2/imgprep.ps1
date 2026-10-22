param(
  [string]$Mode = 'scale',
  [string]$In,
  [string]$Out,
  [int]$Scale = 3,
  [string]$Crop = ''
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$inPath = [IO.Path]::GetFullPath($In)
$outPath = [IO.Path]::GetFullPath($Out)
$src = [System.Drawing.Image]::FromFile($inPath)
try {
  if ($Mode -eq 'crop') {
    $p = $Crop.Split(',')
    $x = [int]$p[0]; $y = [int]$p[1]; $w = [int]$p[2]; $h = [int]$p[3]
    $bmpW = $w * $Scale; $bmpH = $h * $Scale
  } else {
    $x = 0; $y = 0; $w = $src.Width; $h = $src.Height
    $bmpW = $w * $Scale; $bmpH = $h * $Scale
  }
  $bmp = New-Object System.Drawing.Bitmap($bmpW, $bmpH)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::Bicubic
  $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
  $dest = New-Object System.Drawing.Rectangle(0, 0, $bmpW, $bmpH)
  $srcR = New-Object System.Drawing.Rectangle($x, $y, $w, $h)
  $g.DrawImage($src, $dest, $srcR, [System.Drawing.GraphicsUnit]::Pixel)
  $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Output "SAVED $outPath ${bmpW}x${bmpH}"
} finally { $src.Dispose() }
