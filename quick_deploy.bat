@echo off
chcp 65001 >nul
REM XexunRTT 快速部署脚本

echo ======================================================================
echo 🚀 XexunRTT 快速部署工具
echo ======================================================================
echo.

REM 检查参数
if "%~1"=="" (
    echo ❌ 错误: 请提供新版本文件路径
    echo.
    echo 使用方法:
    echo    quick_deploy.bat dist\XexunRTT_v2.5.exe
    echo    quick_deploy.bat dist\XexunRTT_v2.5.exe "修复Bug"
    echo.
    pause
    exit /b 1
)

REM 激活虚拟环境
if exist "env\Scripts\activate.bat" (
    echo 正在激活虚拟环境...
    call env\Scripts\activate.bat
) else (
    echo ⚠️  警告: 虚拟环境不存在，使用系统Python
)

REM 执行部署
if "%~2"=="" (
    python deploy_update.py "%~1" --max-patches 10
) else (
    python deploy_update.py "%~1" --notes "%~2"  --max-patches 10
)

REM 显示结果
if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo ✅ 部署成功!
    echo ======================================================================
    echo.
    echo 💡 下一步: 将 updates 目录中的文件上传到服务器
    echo.
) else (
    echo.
    echo ======================================================================
    echo ❌ 部署失败
    echo ======================================================================
    echo.
)

pause
