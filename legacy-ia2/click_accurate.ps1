Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 根据截图分析结果：林鸿基是第4个条目
# Y范围：208-256，中心Y=232
# 头像中心X=48

$targetX = 48
$targetY = 232

# 验证目标位置的像素颜色
$verifyPx = $bmp.GetPixel($targetX, $targetY)
$brightness = 0.299*$verifyPx.R + 0.587*$verifyPx.G + 0.114*$verifyPx.B
Write-Host "目标 ($targetX, $targetY) RGB=($($verifyPx.R),$($verifyPx.G),$($verifyPx.B)) 亮度=$([math]::Round($brightness))"

# 再扫描Y=200-280区域确认边界
Write-Host ""
Write-Host "=== 验证Y=200~280区域 (X=60) ==="
for ($y = 200; $y -le 280; $y += 2) {
    $p = $bmp.GetPixel(60, $y)
    $b = 0.299*$p.R + 0.587*$p.G + 0.114*$p.B
    Write-Host "Y=$y RGB=($($p.R),$($p.G),$($p.B)) 亮度=$([math]::Round($b))"
}

$bmp.Dispose()

Write-Host ""
Write-Host "=== 执行点击 ==="
Write-Host "移动鼠标到 ($targetX, $targetY)..."
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($targetX, $targetY)
Start-Sleep -Milliseconds 500

# 单击
$user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll")]
public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru

$user32::mouse_event(0x0002, 0, 0, 0, 0)
Start-Sleep -Milliseconds 100
$user32::mouse_event(0x0004, 0, 0, 0, 0)
Write-Host "已点击！等待会话打开..."
Start-Sleep -Seconds 2

# 截屏确认
$bmp2 = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g2.Dispose()
$finalPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_clicked_final.png"
$bmp2.Save($finalPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp2.Dispose()
Write-Host "最终截屏已保存: $finalPath"
