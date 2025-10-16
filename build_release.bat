@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ================================================================
echo   XexunRTT 一键构建脚本
echo ================================================================
echo.

REM 读取版本号
for /f "tokens=2 delims==" %%i in ('python -c "from version import VERSION; print(VERSION)"') do set VERSION=%%i
echo [INFO] 当前版本: v%VERSION%
echo.

REM 步骤1: 更新翻译文件
echo [1/4] 更新翻译文件...
echo ----------------------------------------------------------------
call update_translations.bat
if errorlevel 1 (
    echo [ERROR] 翻译文件更新失败！
    pause
    exit /b 1
)
echo [OK] 翻译文件更新完成
echo.

REM 步骤2: 清理旧的构建文件
echo [2/4] 清理旧的构建文件...
echo ----------------------------------------------------------------
if exist build (
    echo 删除 build 目录...
    rmdir /s /q build
)
if exist dist\XexunRTT*.exe (
    echo 删除旧的 EXE 文件...
    del /q dist\XexunRTT*.exe
)
echo [OK] 清理完成
echo.

REM 步骤3: 构建EXE
echo [3/4] 构建可执行文件...
echo ----------------------------------------------------------------
python build.py
if errorlevel 1 (
    echo [ERROR] 构建失败！
    pause
    exit /b 1
)
echo [OK] 构建完成
echo.

REM 步骤4: 显示构建结果
echo [4/4] 构建结果
echo ----------------------------------------------------------------
for %%f in (dist\XexunRTT*.exe) do (
    echo 文件名: %%~nxf
    echo 大小:   %%~zf 字节
    echo 路径:   %%~ff
)
echo.

echo ================================================================
echo   构建完成！
echo ================================================================
echo.
echo 下一步操作:
echo   1. 测试运行: dist\XexunRTT_v%VERSION%.exe
echo   2. 提交代码: git add . ^&^& git commit
echo   3. 创建标签: git tag v%VERSION%
echo.
pause

