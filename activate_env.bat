@echo off
chcp 65001
REM 激活虚拟环境并运行调试
echo 激活虚拟环境...
call env\Scripts\activate.bat
echo 虚拟环境已激活，当前Python路径：
where python
echo.
echo 安装的包列表：
pip list
echo.
echo 要运行主程序，请执行：
echo python main_window.py
echo.
echo 要退出虚拟环境，请输入 deactivate
cmd /k
