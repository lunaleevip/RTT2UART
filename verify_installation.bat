@echo off
chcp 65001 >nul
echo 🔍 XexunRTT 更新验证工具
echo ================================

set "CURRENT_DIR=%~dp0"
set "EXE_FILE=XexunRTT.exe"

echo 📁 当前目录: %CURRENT_DIR%

echo.
echo 📋 文件结构检查:

REM 检查EXE文件
if exist "%CURRENT_DIR%%EXE_FILE%" (
    echo ✅ 主程序: %EXE_FILE%
    for %%F in ("%CURRENT_DIR%%EXE_FILE%") do (
        echo    大小: %%~zF 字节 ^(%.1f MB^)
    )
) else (
    echo ❌ 缺少主程序: %EXE_FILE%
)

REM 检查_internal目录
if exist "%CURRENT_DIR%_internal" (
    echo ✅ 库目录: _internal/
    
    REM 检查重要的库
    if exist "%CURRENT_DIR%_internal\PySide6" (
        echo ✅ Qt库: PySide6/
    ) else (
        echo ❌ 缺少Qt库: PySide6/
    )
    
    if exist "%CURRENT_DIR%_internal\base_library.zip" (
        echo ✅ Python标准库: base_library.zip
    ) else (
        echo ❌ 缺少Python标准库: base_library.zip
    )
    
) else (
    echo ❌ 缺少库目录: _internal/
)

REM 检查配置文件
if exist "%CURRENT_DIR%config.ini" (
    echo ✅ 配置文件: config.ini
) else (
    echo ⚠️ 配置文件: config.ini (首次运行时会自动创建)
)

echo.
echo 🎯 增量更新优势:
echo    📦 快速更新: 只需替换 %EXE_FILE% (约2-5MB)
echo    💾 节省空间: 库文件重用 (约40MB+)
echo    🔧 保留配置: 用户设置不丢失
echo    ⚡ 启动更快: 库文件无需解压
echo.
pause
