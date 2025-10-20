@echo off
chcp 65001 >nul
REM XexunRTT 精简部署脚本 - 只保留最新版本和1个补丁

echo ======================================================================
echo 🚀 XexunRTT 精简部署工具 (空间优化版)
echo ======================================================================
echo.
echo 📌 配置: 只保留最新 1 个补丁，自动清理旧文件
echo.

REM 检查参数
if "%~1"=="" (
    echo ❌ 错误: 请提供新版本文件路径
    echo.
    echo 使用方法:
    echo    quick_deploy_minimal.bat dist\XexunRTT_v2.5.exe
    echo    quick_deploy_minimal.bat dist\XexunRTT_v2.5.exe "修复Bug"
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

REM 执行部署 (只保留1个补丁)
echo.
echo 正在部署（max-patches=1）...
if "%~2"=="" (
    python deploy_update.py "%~1" --max-patches 1
) else (
    python deploy_update.py "%~1" --notes "%~2" --max-patches 1
)

REM 显示结果和文件大小
if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo ✅ 精简部署成功!
    echo ======================================================================
    echo.
    echo 📊 updates 目录内容:
    dir /b updates
    echo.
    echo 📦 总大小:
    for /f "tokens=3" %%a in ('dir /s updates ^| find "个文件"') do set total=%%a
    echo    %total% 字节
    echo.
    echo 💡 下一步: 将 updates 目录中的文件上传到服务器
    echo    - version.json (必需)
    echo    - XexunRTT_v*.exe (最新版本)
    echo    - patch_*.patch (最新1个补丁)
    echo.
) else (
    echo.
    echo ======================================================================
    echo ❌ 部署失败
    echo ======================================================================
    echo.
)

pause

