Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 林鸿基条目区域（Y=300~375）
# 先扫描这一区域找非纯白像素，定位头像
Write-Host "=== 扫描林鸿基条目区域 (Y=300~375, X=0~150) ==="

# 方法：在Y=300~375范围内，找头像区域（X=60~120）
# 头像通常有颜色（不是纯白/纯灰背景）
$candidates = @()

for ($y = 302; $y -lt 373; $y++) {
    for ($x = 60; $x -lt 120; $x++) {
        $p = $bmp.GetPixel($x, $y)
        $maxC = [Math]::Max([Math]::Max($p.R, $p.G), $p.B)
        $minC = [Math]::Min([Math]::Min($p.R, $p.G), $p.B)
        $range = $maxC - $minC
        $brightness = (0.299*$p.R + 0.587*$p.G + 0.114*$p.B)
        
        # 头像特征：颜色丰富（range大）、不是太亮也不是太暗
        if ($range -gt 20 -and $brightness -gt 40 -and $brightness -lt 230) {
            $candidates += [PSCustomObject]@{x=$x; y=$y; range=$range; r=$p.R; g=$p.G; b=$p.B}
        }
    }
}

# 按颜色丰富度排序，找最佳头像位置
$sorted = $candidates | Sort-Object range -Descending | Select-Object -First 30

Write-Host "找到 $($candidates.Count) 个候选像素"
Write-Host "前10个最佳候选:"
$sorted | Select-Object -First 10 | ForEach-Object {
    Write-Host "  ($($_.x), $($_.y)) range=$($_.range) RGB=($($_.r),$($_.g),$($_.b))"
}

# 取最丰富的区域中心
if ($sorted.Count -gt 0) {
    $avgX = [math]::Round(($sorted | Measure-Object x -Average).Average)
    $avgY = [math]::Round(($sorted | Measure-Object y -Average).Average)
    
    Write-Host ""
    Write-Host "=== 最佳坐标 ==="
    Write-Host "头像中心: ($avgX, $avgY)"
    
    # 移动鼠标
    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($avgX, $avgY)
    Start-Sleep -Milliseconds 400
    Write-Host "鼠标已移动到 ($avgX, $avgY)"
    
    # 单击
    $user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll")]
public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru
    
    $user32::mouse_event(0x0002, 0, 0, 0, 0)
    Start-Sleep -Milliseconds 100
    $user32::mouse_event(0x0004, 0, 0, 0, 0)
    Write-Host "已单击！"
    Start-Sleep -Milliseconds 800
} else {
    Write-Host "未找到候选像素，使用估算位置 (92, 337)"
    $avgX = 92
    $avgY = 337
    
    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($avgX, $avgY)
    Start-Sleep -Milliseconds 300
    
    $user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll")]
public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru
    
    $user32::mouse_event(0x0002, 0, 0, 0, 0)
    Start-Sleep -Milliseconds 100
    $user32::mouse_event(0x0004, 0, 0, 0, 0)
    Write-Host "已单击！"
    Start-Sleep -Milliseconds 800
}

# 再截屏确认
$bmp2 = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g2 = [System.Drawing.Graphics]::FromImage($bmp2)
$g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g2.Dispose()
$finalPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_result.png"
$bmp2.Save($finalPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp2.Dispose()

$bmp.Dispose()
Write-Host "最终截屏: $finalPath"
