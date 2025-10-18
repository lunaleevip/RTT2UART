@echo off
REM XexunRTT 自动更新快速测试脚本
REM 一键完成测试环境搭建和测试

echo ========================================
echo XexunRTT 自动更新快速测试
echo ========================================
echo.

REM 检查虚拟环境
if not exist "env\Scripts\activate.bat" (
    echo [错误] 虚拟环境不存在
    echo 请先创建虚拟环境: python -m venv env
    pause
    exit /b 1
)

REM 激活虚拟环境
call env\Scripts\activate.bat

REM 检查依赖
echo [1/4] 检查依赖...
pip show bsdiff4 >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 bsdiff4...
    pip install bsdiff4
)

echo.
echo [2/4] 切换到测试模式...
python switch_update_server.py test

echo.
echo [3/4] 设置测试环境...
echo.
echo 即将启动测试服务器，请按照提示操作
echo.
pause

echo.
echo [4/4] 启动测试服务器...
echo.
python test_update_local.py

echo.
echo 测试完成!
echo.
echo 如果要切换回生产模式，请运行:
echo   python switch_update_server.py production
echo.
pause

