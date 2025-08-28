@echo off
echo Starting XexunRTT v1.0.5...
echo.
if exist "dist\XexunRTT.exe" (
    echo Found XexunRTT.exe, starting...
    start "" "dist\XexunRTT.exe"
    echo XexunRTT started successfully!
) else (
    echo Error: XexunRTT.exe not found in dist folder!
    echo Please run build_pyinstaller.py first.
)
echo.
pause
