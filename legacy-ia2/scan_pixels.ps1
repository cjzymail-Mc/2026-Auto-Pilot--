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
    public static extern bool GetCursorPos(out POINT lpPoint);
}
public struct POINT { public int x; public int y; }
"@

$bounds = [Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

Write-Host "=== 精确扫描左侧消息列表 ==="
Write-Host ""

# 扫描左侧列表区域（x: 0-280, y: 60-600）
# 排除搜索栏区域（y: 0-60左右）
# 每个条目约60px高
# 条目1(运动表现研究部): y≈80-140
# 条目2(面料测试&样衣): y≈140-200
# 条目3(网球俱乐部): y≈200-260
# 条目4(林鸿基): y≈260-320

# 方法：找选中状态的高亮条——但林鸿基可能没被选中
# 更可靠：在y=260-320范围内找非纯白区域，定位头像位置

Write-Host "扫描y=260-320区域（林鸿基所在条目范围）："
for ($y = 260; $y -le 320; $y += 3) {
    $colors = @()
    for ($x = 5; $x -le 100; $x += 5) {
        $p = $bmp.GetPixel($x, $y)
        $colors += "($($p.R),$($p.G),$($p.B))"
    }
    $firstPx = $bmp.GetPixel(5, $y)
    $secondPx = $bmp.GetPixel(30, $y)
    $thirdPx = $bmp.GetPixel(60, $y)
    $fourthPx = $bmp.GetPixel(100, $y)
    Write-Host "Y=$y : x5=($($firstPx.R),$($firstPx.G),$($firstPx.B)) x30=($($secondPx.R),$($secondPx.G),$($secondPx.B)) x60=($($thirdPx.R),$($thirdPx.G),$($thirdPx.B)) x100=($($fourthPx.R),$($fourthPx.G),$($fourthPx.B))"
}

# 再扫描更宽的范围以确认条目边界
Write-Host ""
Write-Host "扫描y=70-400范围，找每个条目的起始Y（找条目间分隔线/颜色变化）："
for ($y = 70; $y -le 400; $y += 2) {
    $px = $bmp.GetPixel(60, $y)
    $pxLeft = $bmp.GetPixel(5, $y)
    $brightness = [int](0.299*$px.R + 0.587*$px.G + 0.114*$px.B)
    $brightLeft = [int](0.299*$pxLeft.R + 0.587*$pxLeft.G + 0.114*$pxLeft.B)
    if ($brightness -lt 230 -or $brightLeft -lt 230) {
        Write-Host "Y=$y 亮度=$brightness(x60)/$brightLeft(x5) RGB60=($($px.R),$($px.G),$($px.B)) RGB5=($($pxLeft.R),$($pxLeft.G),$($pxLeft.B))"
    }
}

$bmp.Dispose()
