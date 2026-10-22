Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

$path = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_now.png"
$bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "截屏已保存: $path"
Write-Host "分辨率: $($bounds.Width)x$($bounds.Height)"
