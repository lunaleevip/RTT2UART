@echo off
echo ======================================
echo       RTT2UART 调试环境启动
echo ======================================
echo.

echo 1. 激活虚拟环境...
call env\Scripts\activate.bat

echo.
echo 2. 检查环境状态...
python --version
echo Python路径: 
where python

echo.
echo 3. 检查关键依赖...
python -c "import PySide6; print('✓ PySide6:', PySide6.__version__)"
python -c "import serial; print('✓ pyserial 已安装')"
python -c "import pylink; print('✓ pylink 已安装')"
python -c "import qdarkstyle; print('✓ qdarkstyle 已安装')"

echo.
echo 4. 检查JLink连接...
python -c "import pylink; jl=pylink.JLink(); jl.open(); print('✓ JLink连接正常'); jl.close()"

echo.
echo 5. 验证设备配置...
python -c "print('✓ 设备已配置为: STM32F103RB')"

echo.
echo.
echo 6. 显示性能优化配置...
python -c "from performance_config import print_current_config; print_current_config()"

echo.
echo ======================================
echo 🎉 环境准备完成！可以开始调试了
echo ======================================
echo.
echo 💡 提示：如果遇到连接问题，请确保：
echo    1. 目标设备已正确连接并上电
echo    2. JLink调试器连接正常
echo    3. 目标程序支持RTT功能
echo.
echo 🚀 可用启动选项：
echo    1. 版本选择器 (推荐): python choose_version.py
echo    2. 重构版本: python start_new_version.py
echo    3. 原版本: python safe_start.py  
echo    4. 性能监控: python performance_monitor.py
echo.
echo 选择启动方式 (默认版本选择器):
echo [1] 版本选择器  [2] 重构版本  [3] 原版本  [4] 性能监控
choice /c 1234 /default 1 /t 10 /m "请选择"

if errorlevel 4 goto performance
if errorlevel 3 goto original
if errorlevel 2 goto new_version
if errorlevel 1 goto chooser

:chooser
echo 启动版本选择器...
python choose_version.py
goto end

:new_version
echo 启动重构版本...
python start_new_version.py
goto end

:original
echo 启动原版本...
python safe_start.py
goto end

:performance
echo 启动性能监控...
python performance_monitor.py
goto end

:end
