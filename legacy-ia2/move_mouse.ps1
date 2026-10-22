Add-Type -AssemblyName System.Windows.Forms
# 获取屏幕分辨率
$screenWidth = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
$screenHeight = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
# 右上角位置：宽度的95%，高度的5%（留一点边距避免跑到屏幕外）
$x = [int]($screenWidth * 0.95)
$y = [int]($screenHeight * 0.05)
Write-Host "屏幕分辨率: ${screenWidth}x${screenHeight}"
Write-Host "正在移动鼠标到: ($x, $y) - 屏幕右上角附近"
[System.Windows.Forms.Cursor]::Position = New-Object System.Drawing.Point($x, $y)
Write-Host "鼠标已移动到右上角，请查看屏幕确认。"
