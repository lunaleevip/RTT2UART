@echo off
chcp 65001 >nul
REM 启动程序并实时监控日志

echo ======================================================================
echo 🚀 XexunRTT 实时日志测试
echo ======================================================================
echo.

echo 将会同时打开:
echo   1. XexunRTT 程序
echo   2. 日志监控窗口
echo.
echo 按任意键开始...
pause >nul

REM 先清空旧日志（可选）
set LOG_FILE=%LOCALAPPDATA%\XexunRTT\logs\xexunrtt.log
if exist "%LOG_FILE%" (
    echo 清空旧日志...
    echo. > "%LOG_FILE%"
)

echo.
echo 正在启动...
echo.

REM 在新窗口中启动日志监控
start "日志监控" cmd /k tail_log.bat

REM 等待 1 秒
timeout /t 1 /nobreak >nul

REM 启动程序
if exist "dist\XexunRTT_v2.4.exe" (
    echo 启动: dist\XexunRTT_v2.4.exe
    start "XexunRTT" dist\XexunRTT_v2.4.exe
) else if exist "XexunRTT_v2.4.exe" (
    echo 启动: XexunRTT_v2.4.exe
    start "XexunRTT" XexunRTT_v2.4.exe
) else (
    echo ❌ 找不到 XexunRTT_v2.4.exe
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ 完成！
echo.
echo 💡 提示:
echo    - 查看"日志监控"窗口实时查看日志
echo    - 等待 5 秒后会触发自动更新检查
echo    - 按 Ctrl+C 可以停止日志监控
echo.

