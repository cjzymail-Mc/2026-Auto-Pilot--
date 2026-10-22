Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen(0, 0, 0, 0, $bounds.Size)
$g.Dispose()

# 保存截屏供分析
$screenshotPath = "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll\screenshot_exact.png"
$bmp.Save($screenshotPath, [System.Drawing.Imaging.ImageFormat]::Png)

# 精确扫描左侧消息列表 - 找每个条目的精确边界
# 左侧列表宽度约280px，头像在x=60-110区域
# 用亮度变化找条目边界

Write-Host "=== 精确扫描左侧消息列表 ==="
Write-Host ""

# 计算每行在头像区域的亮度变化
# 扫描x=50-110区域
for ($y = 50; $y -lt 500; $y += 1) {
    $px60 = $bmp.GetPixel(60, $y)
    $px80 = $bmp.GetPixel(80, $y)
    $px100 = $bmp.GetPixel(100, $y)
    $bright60 = 0.299*$px60.R + 0.587*$px60.G + 0.114*$px60.B
    $bright80 = 0.299*$px80.R + 0.587*$px80.G + 0.114*$px80.B
    $bright100 = 0.299*$px100.R + 0.587*$px100.G + 0.114*$px100.B
    
    # 检测行边界：亮度变化大时
    if ($y -gt 50) {
        $prevPx60 = $bmp.GetPixel(60, $y-1)
        $prevBright60 = 0.299*$prevPx60.R + 0.587*$prevPx60.G + 0.114*$prevPx60.B
        $diff = [Math]::Abs($bright60 - $prevBright60)
        
        if ($diff -gt 15) {
            Write-Host "Y=$y 亮度变化=$diff  RGB=($($px60.R),$($px60.G),$($px60.B)) <- ($($prevPx60.R),$($prevPx60.G),$($prevPx60.B))"
        }
    }
}

$bmp.Dispose()
Write-Host ""
Write-Host "截屏已保存: $screenshotPath"
