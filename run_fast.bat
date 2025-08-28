@echo off
echo 🚀 XexunRTT 快速启动版本
echo.

REM 检查目录版本（启动最快）
if exist "dist\XexunRTT_Fast\XexunRTT.exe" (
    echo 📁 启动目录版本（最快）...
    start "" "dist\XexunRTT_Fast\XexunRTT.exe"
    echo ✅ 已启动目录版本
    goto :end
)

REM 检查优化单文件版本
if exist "dist_fast\XexunRTT_Fast.exe" (
    echo 📦 启动优化单文件版本...
    start "" "dist_fast\XexunRTT_Fast.exe"
    echo ✅ 已启动优化版本
    goto :end
)

REM 检查标准版本
if exist "dist\XexunRTT.exe" (
    echo 📦 启动标准版本...
    start "" "dist\XexunRTT.exe"
    echo ✅ 已启动标准版本
    goto :end
)

echo ❌ 未找到任何版本的程序文件！
echo 请先运行构建脚本：
echo   python build_fast_startup.py

:end
echo.
pause
