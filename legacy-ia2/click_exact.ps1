Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds

# 先截屏分析当前状态
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 从之前分析，林鸿基是第4个条目（运动表现研究部→服装面料→网球俱乐部→林鸿基）
# 条目1(Y≈60-135)、条目2(Y≈140-215)、条目3(Y≈220-295)、条目4(Y≈300-375)
# 林鸿基条目Y=300-375，头像中心Y≈337，头像中心X≈92

# 但上次点到了文件传输助手（第5个），说明实际条目4偏上
# 我们再重新扫描：从Y=280开始扫描，找到第4个非纯白密集行区域

Write-Host "=== 重新精确扫描左侧列表找林鸿基 ==="

# 逐行扫描x=60-120区域，统计非白像素
$entryBoundaries = @()
$inEntry = $false
$entryStart = 0

for ($y = 60; $y -lt 500; $y++) {
    $darkCount = 0
    for ($x = 60; $x -lt 120; $x += 3) {
        $p = $bmp.GetPixel($x, $y)
        if ($p.R -lt 230 -or $p.G -lt 230 -or $p.B -lt 230) {
            $darkCount++
        }
    }
    
    if ($darkCount -gt 10 -and -not $inEntry) {
        $inEntry = $true
        $entryStart = $y
    } elseif ($darkCount -le 5 -and $inEntry) {
        $inEntry = $false
        $entryHeight = $y - $entryStart
        if ($entryHeight -gt 30 -and $entryHeight -lt 120) {
            $entryBoundaries += @{start=$entryStart; end=$y; height=$entryHeight}
        }
    }
}

# 如果扫描到文件尾还在entry内
if ($inEntry) {
    $entryHeight = 500 - $entryStart
    if ($entryHeight -gt 30 -and $entryHeight -lt 120) {
        $entryBoundaries += @{start=$entryStart; end=500; height=$entryHeight}
    }
}

Write-Host "找到 $($entryBoundaries.Count) 个条目:"
for ($i = 0; $i -lt $entryBoundaries.Count; $i++) {
    $e = $entryBoundaries[$i]
    $centerY = [math]::Round(($e.start + $e.end) / 2)
    Write-Host "  条目$($i+1): Y=$($e.start)-$($e.end) 高=$($e.height)px 中心Y=$centerY"
}

# 林鸿基是第4个条目
if ($entryBoundaries.Count -ge 4) {
    $target = $entryBoundaries[3]
    $targetY = [math]::Round(($target.start + $target.end) / 2)
    $targetX = 92
    
    Write-Host ""
    Write-Host "=== 林鸿基（第4条目）==="
    Write-Host "Y范围: $($target.start)-$($target.end)"
    Write-Host "目标坐标: ($targetX, $targetY)"
    
    # 验证目标像素
    $verifyPx = $bmp.GetPixel($targetX, $targetY)
    Write-Host "目标RGB: ($($verifyPx.R),$($verifyPx.G),$($verifyPx.B))"
    
    # 额外验证：确认这个位置不是文件传输助手
    # 文件传输助手有绿色箭头图标，林鸿基是真人头像
    $isFileTransfer = ($verifyPx.R -gt 200 -and $verifyPx.G -gt 200 -and $verifyPx.B -gt 200)
    if ($isFileTransfer) {
        Write-Host "警告：该位置可能是空白区域，尝试偏移..."
    }
    
    $bmp.Dispose()
    
    # 执行点击
    Write-Host ""
    Write-Host "移动鼠标到 ($targetX, $targetY)..."
    [System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($targetX, $targetY)
    Start-Sleep -Milliseconds 300
    
    # 单击
    $user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll")]
public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, int dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru
    
    $user32::mouse_event(0x0002, 0, 0, 0, 0)
    Start-Sleep -Milliseconds 100
    $user32::mouse_event(0x0004, 0, 0, 0, 0)
    Write-Host "已点击！等待打开会话..."
    Start-Sleep -Seconds 2
    
    # 截屏确认
    $bmp2 = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
    $g2 = [System.Drawing.Graphics]::FromImage($bmp2)
    $g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
    $g2.Dispose()
    $finalPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_after_click2.png"
    $bmp2.Save($finalPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp2.Dispose()
    Write-Host "最终截屏: $finalPath"
} else {
    Write-Host "条目数量不足（$($entryBoundaries.Count)个），请检查屏幕"
    $bmp.Dispose()
}
