param(
  [string[]]$Files,
  [int]$X0 = 780,
  [int]$X1 = 1010,
  [int]$Y0 = 482,
  [int]$Y1 = 506,
  [int]$MinDark = 2,
  [int]$Lum = 150
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
if ($Files.Count -eq 1 -and $Files[0].Contains(',')) { $Files = $Files[0].Split(',') }
foreach ($f in $Files) {
  $bmp = [System.Drawing.Bitmap]::FromFile((Resolve-Path $f))
  $runs = New-Object System.Collections.ArrayList
  $inRun = $false; $s = 0
  for ($x = $X0; $x -le $X1; $x++) {
    $dark = 0
    for ($y = $Y0; $y -le $Y1; $y++) {
      $p = $bmp.GetPixel($x, $y)
      $l = 0.299 * $p.R + 0.587 * $p.G + 0.114 * $p.B
      if ($l -lt $Lum) { $dark++ }
    }
    if ($dark -ge $MinDark) {
      if (-not $inRun) { $inRun = $true; $s = $x }
    } else {
      if ($inRun) { $inRun = $false; [void]$runs.Add("$s..$($x-1)(w$($x-$s))") }
    }
  }
  if ($inRun) { [void]$runs.Add("$s..$X1(w$($X1-$s+1))") }
  $bmp.Dispose()
  $total = ($runs -join ' ')
  Write-Output "$f => $total"
}
