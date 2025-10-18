@echo off
REM XexunRTT 快速部署更新脚本
REM 用于快速生成并部署新版本更新

echo ========================================
echo XexunRTT 快速部署工具
echo ========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python,请先安装Python
    pause
    exit /b 1
)

REM 检查依赖
echo [1/4] 检查依赖...
pip show bsdiff4 >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 bsdiff4...
    pip install bsdiff4
)

pip show requests >nul 2>&1
if errorlevel 1 (
    echo [安装] 正在安装 requests...
    pip install requests
)

echo [完成] 依赖检查完成
echo.

REM 获取新版本信息
echo [2/4] 配置新版本
set /p NEW_VERSION="请输入新版本号 (如 2.3.0): "
set /p NEW_FILE="请输入新版本exe路径: "

if not exist "%NEW_FILE%" (
    echo [错误] 文件不存在: %NEW_FILE%
    pause
    exit /b 1
)

REM 查找旧版本
echo.
echo [3/4] 查找旧版本文件...
set OLD_VERSIONS=
for %%f in (XexunRTT_v*.exe) do (
    if not "%%f"=="%NEW_FILE%" (
        echo [发现] %%f
        set OLD_VERSIONS=!OLD_VERSIONS! "%%f"
    )
)

if "%OLD_VERSIONS%"=="" (
    echo [警告] 未找到旧版本文件
    set /p CONTINUE="是否继续 (只提供完整下载)? (y/N): "
    if /i not "!CONTINUE!"=="y" (
        echo 已取消
        pause
        exit /b 0
    )
)

REM 获取更新说明
echo.
set /p RELEASE_NOTES="请输入更新说明 (简短): "

REM 执行部署
echo.
echo [4/4] 生成更新文件...
echo.

python deploy_update.py ^
    --new-version "%NEW_VERSION%" ^
    --new-file "%NEW_FILE%" ^
    %OLD_VERSIONS% ^
    --release-notes "%RELEASE_NOTES%" ^
    --output-dir "./updates"

if errorlevel 1 (
    echo.
    echo [错误] 部署失败
    pause
    exit /b 1
)

echo.
echo ========================================
echo 完成!
echo ========================================
echo.
echo 生成的文件在: .\updates\
echo.
echo 下一步:
echo 1. 检查 updates\version.json 内容
echo 2. 将 updates\ 目录下的所有文件上传到服务器
echo 3. 确保服务器URL配置正确
echo.

REM 询问是否打开输出目录
set /p OPEN_DIR="是否打开输出目录? (y/N): "
if /i "%OPEN_DIR%"=="y" (
    explorer updates
)

pause

