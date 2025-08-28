@echo off
echo 启动RTT性能测试工具...
echo.

REM 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" (
    echo 激活虚拟环境...
    call venv\Scripts\activate.bat
)

REM 运行性能测试
echo 启动性能测试...
python test_performance.py

pause
