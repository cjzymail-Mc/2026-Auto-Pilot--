Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MouseSim {
    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int x, int y);
}
"@

# 先截屏
$bounds = [Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 保存截屏用于分析
$screenshotPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_current.png"
$bmp.Save($screenshotPath, [Drawing.Imaging.ImageFormat]::Png)

# 扫描左侧区域，找到深色像素的精确Y坐标（文字/头像区域）
Write-Host "精确扫描左侧列表..."

# 先扫描大范围找到所有非白色像素
$darkRows = @()
for ($y = 60; $y -lt 600; $y++) {
    $darkCount = 0
    for ($x = 5; $x -lt 150; $x += 5) {
        $p = $bmp.GetPixel($x, $y)
        if ($p.R -lt 200 -or $p.G -lt 200 -or $p.B -lt 200) {
            $darkCount++
        }
    }
    if ($darkCount -gt 8) {
        $darkRows += $y
    }
}

# 找连续深色行区域（联系人条目）
if ($darkRows.Count -gt 0) {
    Write-Host "找到深色行区域:"
    $startY = $darkRows[0]
    $prevY = $startY
    $groups = @()
    $currentGroup = @($startY)
    
    for ($i = 1; $i -lt $darkRows.Count; $i++) {
        if ($darkRows[$i] - $prevY -le 3) {
            $currentGroup += $darkRows[$i]
        } else {
            $groups += ,@($currentGroup[0], $currentGroup[-1], $currentGroup.Count)
            $currentGroup = @($darkRows[$i])
        }
        $prevY = $darkRows[$i]
    }
    $groups += ,@($currentGroup[0], $currentGroup[-1], $currentGroup.Count)
    
    $itemIndex = 0
    foreach ($g in $groups) {
        $itemCenterY = [math]::Round(($g[0] + $g[1]) / 2)
        Write-Host "  条目$itemIndex : Y=$($g[0])-$($g[1]) 高度=$($g[2])px 中心Y=$itemCenterY"
        $itemIndex++
    }
    
    # 林鸿基是第4个可见条目（index=3）
    if ($groups.Count -ge 4) {
        $targetGroup = $groups[3]
        $targetY = [math]::Round(($targetGroup[0] + $targetGroup[1]) / 2)
        $targetX = 20  # 头像中心X
        
        Write-Host ""
        Write-Host "=== 林鸿基（第4条目）==="
        Write-Host "Y范围: $($targetGroup[0])-$($targetGroup[1])"
        Write-Host "目标坐标: ($targetX, $targetY)"
        
        # 验证该位置像素
        $verifyPx = $bmp.GetPixel($targetX, $targetY)
        Write-Host "目标像素RGB: ($($verifyPx.R),$($verifyPx.G),$($verifyPx.B))"
        
        # 移动并点击
        [MouseSim]::SetCursorPos($targetX, $targetY)
        Start-Sleep -Milliseconds 300
        Write-Host "鼠标已移动至 ($targetX, $targetY)"
        Start-Sleep -Milliseconds 200
        
        # 点击
        [MouseSim]::mouse_event(0x0002, 0, 0, 0, 0)
        Start-Sleep -Milliseconds 100
        [MouseSim]::mouse_event(0x0004, 0, 0, 0, 0)
        Start-Sleep -Milliseconds 500
        Write-Host "已点击！"
        
        # 再次截屏确认
        $bmp2 = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
        $g2 = [Drawing.Graphics]::FromImage($bmp2)
        $g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
        $g2.Dispose()
        $finalPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_clicked.png"
        $bmp2.Save($finalPath, [Drawing.Imaging.ImageFormat]::Png)
        $bmp2.Dispose()
        Write-Host "点击后截屏已保存"
    } else {
        Write-Host "未找到足够的条目（共$($groups.Count)个）"
    }
} else {
    Write-Host "未找到深色行"
}

$bmp.Dispose()
