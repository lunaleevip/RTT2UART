@echo off
REM 在虚拟环境中直接运行主程序
echo 激活虚拟环境并运行程序...
call env\Scripts\activate.bat
python main_window.py
pause

