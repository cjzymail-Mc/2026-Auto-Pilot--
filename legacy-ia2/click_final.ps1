Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds

# 精确扫描左侧区域找头像特征（圆形头像通常有特定颜色范围）
# 林鸿基条目位置：条目5，起始Y=310，中心Y=340，头像X中心≈60
# 先截屏
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 扫描第5个条目（Y=310-370）的像素特征
Write-Host "=== 扫描条目5区域 (Y=310-370) 寻找头像 ==="
$targetArea = $bmp.Clone([System.Drawing.Rectangle]::FromLTRB(0, 310, 280, 370), $bmp.PixelFormat)

# 在Y=310-370范围内逐行扫描x=0-80（头像区域）
for ($y = 310; $y -le 370; $y += 2) {
    $pixels = @()
    for ($x = 5; $x -le 80; $x += 5) {
        $p = $bmp.GetPixel($x, $y)
        $pixels += "($($p.R),$($p.G),$($p.B))"
    }
    Write-Host "Y=$y : $($pixels -join ' ')"
}

# 找条目5中颜色最丰富的区域（头像）
$bestX = 0
$bestY = 0
$bestScore = 0

for ($y = 312; $y -lt 368; $y += 2) {
    for ($x = 5; $x -lt 80; $x += 3) {
        $p = $bmp.GetPixel($x, $y)
        # 计算颜色"丰富度"——头像通常不是纯白/纯灰
        $maxC = [Math]::Max([Math]::Max($p.R, $p.G), $p.B)
        $minC = [Math]::Min([Math]::Min($p.R, $p.G), $p.B)
        $range = $maxC - $minC  # 颜色范围，头像通常有较大颜色变化
        $brightness = (0.299*$p.R + 0.587*$p.G + 0.114*$p.B)
        
        # 头像不是纯白也不是纯黑，颜色有变化
        if ($range -gt 15 -and $brightness -gt 30 -and $brightness -lt 240) {
            $score = $range + (255 - [Math]::Abs($brightness - 128))
            if ($score -gt $bestScore) {
                $bestScore = $score
                $bestX = $x
                $bestY = $y
            }
        }
    }
}

if ($bestScore -gt 50) {
    Write-Host ""
    Write-Host "=== 找到最佳头像位置 ==="
    Write-Host "坐标: ($bestX, $bestY)"
    Write-Host "颜色分数: $bestScore"
    $p = $bmp.GetPixel($bestX, $bestY)
    Write-Host "RGB: ($($p.R),$($p.G),$($p.B))"
} else {
    Write-Host "未找到丰富色彩区域，使用估算位置 (60, 340)"
    $bestX = 65
    $bestY = 340
}

$bmp.Dispose()

# 移动鼠标到头像位置并点击
Write-Host ""
Write-Host "=== 执行操作 ==="
Write-Host "移动鼠标到 ($bestX, $bestY)..."
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($bestX, $bestY)
Start-Sleep -Milliseconds 500

# 左键单击
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($bestX, $bestY)
Start-Sleep -Milliseconds 200

$user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll")]
public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru

$user32::mouse_event(0x0002, 0, 0, 0, 0)  # 按下
Start-Sleep -Milliseconds 100
$user32::mouse_event(0x0004, 0, 0, 0, 0)  # 抬起
Start-Sleep -Milliseconds 300
Write-Host "已点击！等待会话打开..."

# 等一会再截屏确认
Start-Sleep -Seconds 2

$bmp2 = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g2.Dispose()
$finalPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_final2.png"
$bmp2.Save($finalPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp2.Dispose()
Write-Host "最终截屏已保存: $finalPath"
