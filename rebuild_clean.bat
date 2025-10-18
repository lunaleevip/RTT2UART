@echo off
chcp 65001 >nul
REM XexunRTT 清理并重新编译脚本

echo ======================================================================
echo 🔧 XexunRTT 清理并重新编译
echo ======================================================================
echo.

REM 激活虚拟环境
if exist "env\Scripts\activate.bat" (
    echo [1/5] 正在激活虚拟环境...
    call env\Scripts\activate.bat
) else (
    echo ⚠️  警告: 虚拟环境不存在，使用系统Python
)

echo.
echo [2/5] 清理旧的构建文件...
if exist "build" (
    rmdir /s /q build
    echo    ✅ 已删除 build 目录
)
if exist "dist" (
    rmdir /s /q dist
    echo    ✅ 已删除 dist 目录
)

echo.
echo [3/5] 清理 PyInstaller 缓存...
set CACHE_DIR=%LOCALAPPDATA%\pyinstaller
if exist "%CACHE_DIR%" (
    rmdir /s /q "%CACHE_DIR%"
    echo    ✅ 已清理 PyInstaller 缓存
) else (
    echo    ℹ️  PyInstaller 缓存不存在
)

echo.
echo [4/5] 开始编译...
echo ======================================================================
pyinstaller XexunRTT_onefile_v2_2.spec

if %errorlevel% equ 0 (
    echo.
    echo ======================================================================
    echo [5/5] 测试启动...
    echo ======================================================================
    
    REM 查找生成的 EXE 文件
    for %%f in (dist\XexunRTT_*.exe) do (
        echo.
        echo 找到编译文件: %%f
        echo 文件大小: 
        dir "%%f" | findstr "XexunRTT"
        echo.
        echo 正在测试启动（5秒后自动关闭）...
        start "" "%%f"
        timeout /t 5 /nobreak >nul
        
        REM 检查进程是否还在运行
        tasklist | findstr /i "XexunRTT" >nul
        if %errorlevel% equ 0 (
            echo    ✅ 程序启动成功！
            taskkill /f /im XexunRTT_v*.exe >nul 2>&1
        ) else (
            echo    ⚠️  程序可能启动失败，请手动测试
        )
    )
    
    echo.
    echo ======================================================================
    echo ✅ 编译完成！
    echo ======================================================================
    echo.
    echo 📦 编译文件位置: dist\
    echo 💡 提示: 请手动运行程序确认所有功能正常
    echo.
) else (
    echo.
    echo ======================================================================
    echo ❌ 编译失败
    echo ======================================================================
    echo.
    echo 请检查错误信息并修复后重试
    echo.
)

pause

