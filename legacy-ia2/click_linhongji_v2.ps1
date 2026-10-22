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
    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int nIndex);
}
"@

# 截全屏
$bounds = [Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 左侧消息列表区域（约宽280px），我们逐行扫描找"林鸿基"文字区域
# 企业微信联系人列表每个条目约 62px 高
# 先截取左侧列表区域
$listLeft = 0
$listWidth = 300
$listTop = 30
$listBottom = 600

# 在左侧列表区域逐像素扫描找文字特征
# "林鸿基"三个字大约占据 48-60px 宽，16-20px 高
# 在深色背景上找浅色文字区域（或浅色背景上找深色文字区域）

Write-Host "扫描左侧消息列表寻找林鸿基位置..."

$targetY = -1
$targetX = -1

# 扫描策略：从顶部开始，每隔几个像素采样，找颜色变化区域
# 企业微信左侧列表背景色通常较浅(约245-255)，文字颜色较深
for ($y = $listTop; $y -lt $listBottom; $y += 5) {
    $rowPixels = @()
    for ($x = 0; $x -lt 100; $x += 3) {
        $pixel = $bmp.GetPixel($x, $y)
        $brightness = [int](0.299*$pixel.R + 0.587*$pixel.G + 0.114*$pixel.B)
        $rowPixels += $brightness
    }
    # 计算该行的平均亮度
    $avgBright = ($rowPixels | Measure-Object -Average).Average
    # 找文字行：有亮度变化（文字区域）
    if ($avgBright -lt 230 -and $avgBright -gt 50) {
        Write-Host "Y=$y 亮度=$([math]::Round($avgBright)) 可能有文字"
    }
}

# 更精确的方法：用坐标估计法
# 林鸿基在"网球俱乐部"下方，"文件传输助手"上方
# 一般企业微信左侧列表：搜索栏约45px，消息标题约35px，然后每个联系人条目约62px
# 林鸿基大约在第5-6项位置

# 条目起始Y = 45(搜索栏) + 35(消息标题) + 5*62(第6项) ≈ 390
$baseY = 80  # 列表内容起始
$itemHeight = 62
$hongjiIndex = 4  # 第5项（0-indexed）
$targetY = $baseY + $hongjiIndex * $itemHeight + ($itemHeight/2)  # 条目中心
$targetX = 35  # 头像中心X

Write-Host ""
Write-Host "估算林鸿基位置: X=$targetX, Y=$targetY"

# 先移动到该位置看看
[MouseSim]::SetCursorPos($targetX, $targetY)
Start-Sleep -Milliseconds 300

# 获取当前像素颜色，确认不是空白
$pixelAtTarget = $bmp.GetPixel($targetX, $targetY)
Write-Host "目标位置像素: R=$($pixelAtTarget.R) G=$($pixelAtTarget.G) B=$($pixelAtTarget.B)"

# 如果颜色太亮（空白区域），微调位置
if ($pixelAtTarget.R -gt 240 -and $pixelAtTarget.G -gt 240 -and $pixelAtTarget.B -gt 240) {
    Write-Host "目标区域为白色，可能是空白区域，尝试调整位置..."
    # 尝试上下偏移找非白色区域
    for ($offset = -30; $offset -le 30; $offset += 5) {
        if ($offset -eq 0) { continue }
        $testY = $targetY + $offset
        if ($testY -lt 0 -or $testY -gt $bounds.Height) { continue }
        $testPixel = $bmp.GetPixel(50, $testY)
        if ($testPixel.R -lt 220 -or $testPixel.G -lt 220 -or $testPixel.B -lt 220) {
            Write-Host "找到非空白区域: Y=$testY, RGB=($($testPixel.R),$($testPixel.G),$($testPixel.B))"
            $targetY = $testY
            break
        }
    }
}

# 最终移动并点击
[MouseSim]::SetCursorPos($targetX, $targetY)
Start-Sleep -Milliseconds 500
Write-Host ""
Write-Host "最终目标: ($targetX, $targetY)"
Write-Host "鼠标已移动到林鸿基位置！"

# 左键单击
[MouseSim]::mouse_event(0x0002, 0, 0, 0, 0)  # 按下
Start-Sleep -Milliseconds 100
[MouseSim]::mouse_event(0x0004, 0, 0, 0, 0)  # 抬起
Start-Sleep -Milliseconds 500
Write-Host "已点击！"

# 再截屏确认
$bmp2 = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
$g2 = [Drawing.Graphics]::FromImage($bmp2)
$g2.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g2.Dispose()
$screenshotAfter = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_final.png"
$bmp2.Save($screenshotAfter, [Drawing.Imaging.ImageFormat]::Png)
$bmp2.Dispose()
$bmp.Dispose()

Write-Host "最终截屏已保存: $screenshotAfter"
