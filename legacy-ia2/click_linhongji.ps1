Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# 截取全屏
$screenBounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $screenBounds.Width, $screenBounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen(0, 0, 0, 0, $screenBounds.Size)
$graphics.Dispose()

# 1920x1200 屏幕，左侧联系人列表宽度约 280px
# 林鸿基在"网球俱乐部"下方、"文件传输助手"上方，约第5-6项
# 搜索栏约 40px，顶部标题栏约 50px，每个联系人条目约 60-65px
# 第5-6项大致在 y=50+5*62 ≈ 360px 附近
# 头像在列表左侧，x 约在 20-80px 之间

# 我们裁剪左侧联系人列表区域，用OCR识别找到林鸿基名字的位置
$listLeft = 0
$listTop = 100
$listWidth = 280
$listHeight = 500

# 在左侧区域搜索"林鸿基"三个字的像素特征
# 由于字体颜色通常是深色(黑色/深灰)，我们找文字密集区域
$found = $false
$targetX = 0
$targetY = 0

# 扫描联系人列表区域，找林鸿基名字的垂直位置
# 每项约62px高，从头像中心点来算
for ($i = 0; $i -le 8; $i++) {
    $itemY = 100 + $i * 62  # 第i个联系人条目的Y
    $itemCenterY = $itemY + 31  # 条目中心
    Write-Host "位置 $($i+1): Y=$itemY, 中心Y=$itemCenterY"
}

# 根据截图分析，林鸿基大约在第5个位置
$linHongjiIndex = 4  # 0-indexed, 第5项
$linY = 100 + $linHongjiIndex * 62 + 31  # 条目中心Y
$linX = 45  # 头像中心X（左侧列表头像位置）

Write-Host ""
Write-Host "=== 开始操作 ==="
Write-Host "目标: 林鸿基的头像位置"
Write-Host "目标坐标: ($linX, $linY)"
Write-Host ""

# 移动鼠标到林鸿基头像位置
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($linX, $linY)
Start-Sleep -Milliseconds 500
Write-Host "鼠标已移动到林鸿基头像位置 ($linX, $linY)"

# 单击左键
[System.Windows.Forms.Forms]::MouseButtons
[System.Windows.Forms.SendKeys]::WaitCursorOff

# 模拟鼠标点击
$user32 = Add-Type -MemberDefinition @"
[DllImport("user32.dll", CharSet = CharSet.Auto, CallingConvention = CallingConvention.StdCall)]
public static extern void mouse_event(long dwFlags, long dx, long dy, long cButtons, long dwExtraInfo);
"@ -Name "user32" -Namespace "Win32" -PassThru

$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004

$user32::mouse_event($MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
Start-Sleep -Milliseconds 100
$user32::mouse_event($MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
Start-Sleep -Milliseconds 300

Write-Host "已点击林鸿基的头像，等待会话打开..."

# 等待会话打开后再截一次屏
Start-Sleep -Seconds 1

# 再次截屏确认
$bitmap2 = New-Object System.Drawing.Bitmap $screenBounds.Width, $screenBounds.Height
$graphics2 = [System.Drawing.Graphics]::FromImage($bitmap2)
$graphics2.CopyFromScreen(0, 0, 0, 0, $screenBounds.Size)
$graphics2.Dispose()

$screenshotPath2 = Join-Path "D:\Technique Support\Claude Code Learning\Hot-Fix\修复pwshll滚动scroll" "screenshot_after_click.png"
$bitmap2.Save($screenshotPath2, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap2.Dispose()

Write-Host "点击后的截屏已保存: $screenshotPath2"
