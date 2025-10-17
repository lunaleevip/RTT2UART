# 安装更纱黑体（Sarasa Gothic）字体
# 这是专为编程设计的开源字体，完美支持中英文等宽

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  更纱黑体字体安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否有管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "❌ 错误：需要管理员权限来安装字体" -ForegroundColor Red
    Write-Host "   请右键点击此脚本，选择 '以管理员身份运行'" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "✅ 管理员权限已确认" -ForegroundColor Green
Write-Host ""

# 下载链接
$downloadUrl = "https://github.com/be5invis/Sarasa-Gothic/releases/download/v1.0.20/Sarasa-TTC-1.0.20.7z"
$tempDir = "$env:TEMP\SarasaFont"
$downloadFile = "$tempDir\Sarasa.7z"
$extractDir = "$tempDir\Extracted"

# 创建临时目录
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractDir | Out-Null

Write-Host "📥 正在下载更纱黑体字体..." -ForegroundColor Cyan
Write-Host "   大小约 ~75MB，请耐心等待..." -ForegroundColor Yellow
Write-Host ""

try {
    # 下载字体包
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadFile -UseBasicParsing
    Write-Host "✅ 下载完成" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ 下载失败: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "请手动下载：" -ForegroundColor Yellow
    Write-Host "   $downloadUrl"
    Write-Host ""
    Write-Host "或访问官方仓库：" -ForegroundColor Yellow
    Write-Host "   https://github.com/be5invis/Sarasa-Gothic/releases" -ForegroundColor Cyan
    Write-Host ""
    pause
    exit 1
}

# 解压（需要7-Zip）
Write-Host "📦 正在解压字体文件..." -ForegroundColor Cyan

# 检查是否安装了7-Zip
$7zipPath = "$env:ProgramFiles\7-Zip\7z.exe"
if (-not (Test-Path $7zipPath)) {
    $7zipPath = "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
}

if (-not (Test-Path $7zipPath)) {
    Write-Host "❌ 未找到 7-Zip，请先安装 7-Zip" -ForegroundColor Red
    Write-Host "   下载地址: https://www.7-zip.org/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "或使用 Scoop 安装：" -ForegroundColor Yellow
    Write-Host "   scoop install 7zip" -ForegroundColor Cyan
    Write-Host ""
    pause
    exit 1
}

try {
    & $7zipPath x $downloadFile "-o$extractDir" -y | Out-Null
    Write-Host "✅ 解压完成" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ 解压失败: $_" -ForegroundColor Red
    pause
    exit 1
}

# 安装字体
Write-Host "🔧 正在安装字体..." -ForegroundColor Cyan
Write-Host ""

$fonts = Get-ChildItem -Path $extractDir -Filter "Sarasa*.ttc" -Recurse
$installedCount = 0
$FONTS = 0x14

foreach ($font in $fonts) {
    # 只安装等宽版本（Mono）
    if ($font.Name -like "*Mono*" -and $font.Name -like "*SC*") {
        try {
            $fontName = $font.BaseName
            Write-Host "   安装: $fontName" -ForegroundColor Gray
            
            # 复制到字体目录
            $fontFile = "$env:WinDir\Fonts\$($font.Name)"
            Copy-Item -Path $font.FullName -Destination $fontFile -Force
            
            # 注册字体
            $regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
            Set-ItemProperty -Path $regPath -Name "$fontName (TrueType)" -Value $font.Name -ErrorAction SilentlyContinue
            
            $installedCount++
        } catch {
            Write-Host "   ⚠️  安装失败: $($font.Name)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "✅ 字体安装完成！共安装 $installedCount 个字体文件" -ForegroundColor Green
Write-Host ""

# 清理临时文件
Write-Host "🧹 清理临时文件..." -ForegroundColor Cyan
Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "✅ 清理完成" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装成功！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "请按照以下步骤操作：" -ForegroundColor Yellow
Write-Host "  1. 重新启动 XexunRTT 应用程序" -ForegroundColor White
Write-Host "  2. 在主界面找到 '字体:' 下拉框" -ForegroundColor White
Write-Host "  3. 选择 'Sarasa Mono SC' 或 'Sarasa Term SC'" -ForegroundColor White
Write-Host "  4. 现在中英文应该完美对齐了！" -ForegroundColor White
Write-Host ""
Write-Host "提示：如果没有看到新字体，请注销后重新登录 Windows" -ForegroundColor Cyan
Write-Host ""
pause

