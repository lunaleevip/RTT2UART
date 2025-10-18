@echo off
chcp 65001 >nul
REM 实时监控 XexunRTT 日志文件 (类似 Linux 的 tail -f)

set LOG_FILE=%LOCALAPPDATA%\XexunRTT\logs\xexunrtt.log

echo ======================================================================
echo 📡 XexunRTT 日志实时监控
echo ======================================================================
echo.

if not exist "%LOG_FILE%" (
    echo ❌ 日志文件不存在: %LOG_FILE%
    echo.
    echo 💡 提示: 请先运行一次程序生成日志
    echo.
    pause
    exit /b 1
)

echo 📁 日志文件: %LOG_FILE%
echo.
echo ⏳ 正在实时监控日志... (按 Ctrl+C 停止)
echo ======================================================================
echo.

REM 使用 PowerShell 实时监控日志
powershell -Command "Get-Content '%LOG_FILE%' -Tail 20 -Wait"

