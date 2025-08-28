@echo off
chcp 65001 >nul
echo 🔄 XexunRTT 增量更新工具
echo ================================

set "CURRENT_DIR=%~dp0"
set "EXE_FILE=XexunRTT.exe"
set "BACKUP_EXT=.backup"

echo 📁 当前目录: %CURRENT_DIR%

REM 检查是否存在EXE文件
if not exist "%CURRENT_DIR%%EXE_FILE%" (
    echo ❌ 未找到 %EXE_FILE% 文件
    echo 💡 请确保在正确的程序目录中运行此脚本
    pause
    exit /b 1
)

echo 📋 当前文件信息:
for %%F in ("%CURRENT_DIR%%EXE_FILE%") do (
    echo    文件大小: %%~zF 字节
    echo    修改时间: %%~tF
)

echo.
echo 🔄 创建备份...
copy "%CURRENT_DIR%%EXE_FILE%" "%CURRENT_DIR%%EXE_FILE%%BACKUP_EXT%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ 备份创建成功: %EXE_FILE%%BACKUP_EXT%
) else (
    echo ❌ 备份创建失败
    pause
    exit /b 1
)

echo.
echo 💡 增量更新说明:
echo    📦 只需要替换: %EXE_FILE% 文件
echo    📁 无需更新: _internal 目录中的库文件
echo    🔧 配置文件: config.ini 会自动保留
echo.
echo 🚀 请将新的 %EXE_FILE% 文件放在此目录中
echo 📋 更新完成后，可以删除 %EXE_FILE%%BACKUP_EXT% 备份文件
echo.
echo 🔙 如需恢复备份，运行: copy "%EXE_FILE%%BACKUP_EXT%" "%EXE_FILE%"
echo.
pause
