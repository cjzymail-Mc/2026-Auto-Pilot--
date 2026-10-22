Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ===== 1. 截取全屏 =====
$screenBounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $screenBounds.Width, $screenBounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screenBounds.X, $screenBounds.Y, 0, 0, $screenBounds.Size)
$graphics.Dispose()

$screenshotPath = Join-Path "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll" "screenshot.png"
$bitmap.Save($screenshotPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()

Write-Host "截屏已保存: $screenshotPath"
Write-Host "屏幕分辨率: $($screenBounds.Width)x$($screenBounds.Height)"
