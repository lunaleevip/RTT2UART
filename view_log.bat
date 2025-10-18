@echo off
chcp 65001 >nul
REM 查看 XexunRTT 日志文件

set LOG_FILE=%LOCALAPPDATA%\XexunRTT\logs\xexunrtt.log

echo ======================================================================
echo 📝 XexunRTT 日志查看器
echo ======================================================================
echo.

if not exist "%LOG_FILE%" (
    echo ❌ 日志文件不存在: %LOG_FILE%
    echo.
    echo 💡 提示:
    echo    - 请先运行一次程序生成日志
    echo    - 日志文件路径: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

echo 📁 日志文件: %LOG_FILE%
echo.

REM 获取文件大小
for %%A in ("%LOG_FILE%") do set size=%%~zA
set /a size_kb=%size%/1024
echo 📊 文件大小: %size_kb% KB
echo.

REM 显示选项菜单
echo 请选择操作:
echo.
echo   1. 查看完整日志
echo   2. 查看最后 50 行
echo   3. 查看最后 100 行
echo   4. 查看最后 500 行
echo   5. 搜索关键字
echo   6. 清空日志文件
echo   7. 用记事本打开
echo   8. 用 VS Code 打开
echo   9. 退出
echo.
set /p choice="请输入选项 (1-9): "

if "%choice%"=="1" (
    echo.
    echo ======================================================================
    echo 完整日志内容:
    echo ======================================================================
    type "%LOG_FILE%"
    echo.
    echo ======================================================================
) else if "%choice%"=="2" (
    echo.
    echo ======================================================================
    echo 最后 50 行:
    echo ======================================================================
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 50"
    echo.
    echo ======================================================================
) else if "%choice%"=="3" (
    echo.
    echo ======================================================================
    echo 最后 100 行:
    echo ======================================================================
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 100"
    echo.
    echo ======================================================================
) else if "%choice%"=="4" (
    echo.
    echo ======================================================================
    echo 最后 500 行:
    echo ======================================================================
    powershell -Command "Get-Content '%LOG_FILE%' -Tail 500"
    echo.
    echo ======================================================================
) else if "%choice%"=="5" (
    echo.
    set /p keyword="请输入搜索关键字: "
    echo.
    echo ======================================================================
    echo 搜索结果: "!keyword!"
    echo ======================================================================
    findstr /i "!keyword!" "%LOG_FILE%"
    echo.
    echo ======================================================================
) else if "%choice%"=="6" (
    echo.
    set /p confirm="确定要清空日志文件吗? (y/N): "
    if /i "!confirm!"=="y" (
        echo. > "%LOG_FILE%"
        echo ✅ 日志文件已清空
    ) else (
        echo ❌ 取消操作
    )
) else if "%choice%"=="7" (
    echo.
    echo 正在用记事本打开...
    notepad "%LOG_FILE%"
) else if "%choice%"=="8" (
    echo.
    echo 正在用 VS Code 打开...
    code "%LOG_FILE%"
) else if "%choice%"=="9" (
    exit /b 0
) else (
    echo.
    echo ❌ 无效选项
)

echo.
pause

