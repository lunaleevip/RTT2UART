#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单有效的增量更新构建脚本
将用户代码打包到EXE中，第三方库放在_internal文件夹
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_simple_incremental_spec():
    """创建简单有效的增量更新spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# 增量更新构建配置
# 策略：使用onedir模式，但通过自定义配置实现用户代码和库文件分离

import sys
from pathlib import Path

block_cipher = None

# 分析配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        # 数据文件
        ('xexunrtt.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
    ],
    hiddenimports=[
        # 必要的隐式导入
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pylink',
        'serial',
        'serial.tools.list_ports',
        'logging',
        'psutil',
        'configparser',
        'threading',
        'time',
        'datetime',
        'json',
        'xml.etree.ElementTree',
        'encodings.utf_8',
        'encodings.gbk',
        'encodings.cp936',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块
        'tkinter', 'unittest', 'test', 'email', 'http', 'urllib',
        'pydoc', 'doctest', 'pdb', 'profile', 'cProfile', 'pstats',
        'trace', 'timeit', 'webbrowser', 'pip', 'setuptools',
        'distutils', 'wheel', 'pytest', 'nose', 'mock',
        # 排除PySide6中不需要的大模块
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtMultimedia', 'PySide6.QtQml',
        'PySide6.QtQuick', 'PySide6.QtWebView', 'PySide6.QtXml',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,  # 使用标准archive，但后续我们会分离文件
)

# 标准PYZ配置
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE配置 - 使用onedir模式
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 使用onedir模式
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='Jlink_ICON.ico',
)

# COLLECT配置
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XexunRTT_Incremental'
)
"""
    
    with open('XexunRTT_simple_incremental.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 创建简单增量更新spec文件: XexunRTT_simple_incremental.spec")

def build_simple_incremental():
    """构建简单增量更新版本"""
    print("🚀 构建简单增量更新版本...")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'XexunRTT_simple_incremental.spec'
    ]
    
    print("构建命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 简单增量更新版本构建成功!")
        
        # 检查生成的文件
        exe_path = Path('dist/XexunRTT_Incremental/XexunRTT.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 生成的EXE文件: {exe_path}")
            print(f"📏 EXE文件大小: {size_mb:.1f} MB")
            
            # 检查_internal目录
            internal_dir = exe_path.parent / '_internal'
            if internal_dir.exists():
                total_size = sum(f.stat().st_size for f in internal_dir.rglob('*') if f.is_file())
                internal_size_mb = total_size / (1024 * 1024)
                print(f"📁 _internal目录大小: {internal_size_mb:.1f} MB")
                print(f"📊 总大小: {size_mb + internal_size_mb:.1f} MB")
                
                # 分析_internal目录内容
                print(f"\n📋 _internal目录结构:")
                for item in sorted(internal_dir.iterdir()):
                    if item.is_dir():
                        count = len(list(item.rglob('*')))
                        print(f"   📁 {item.name}/ ({count} 个文件)")
                    else:
                        size = item.stat().st_size / (1024 * 1024)
                        print(f"   📄 {item.name} ({size:.1f} MB)")
        else:
            print("❌ 未找到生成的EXE文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    
    return True

def optimize_for_incremental_update():
    """优化增量更新结构"""
    print("🔧 优化增量更新结构...")
    
    dist_dir = Path('dist/XexunRTT_Incremental')
    if not dist_dir.exists():
        print("❌ 构建目录不存在")
        return False
    
    exe_path = dist_dir / 'XexunRTT.exe'
    internal_dir = dist_dir / '_internal'
    
    if not exe_path.exists() or not internal_dir.exists():
        print("❌ 必要文件不存在")
        return False
    
    # 创建优化后的目录
    optimized_dir = Path('dist/XexunRTT_Optimized')
    if optimized_dir.exists():
        shutil.rmtree(optimized_dir)
    optimized_dir.mkdir(parents=True)
    
    # 复制EXE文件
    shutil.copy2(exe_path, optimized_dir / 'XexunRTT.exe')
    
    # 复制_internal目录
    shutil.copytree(internal_dir, optimized_dir / '_internal')
    
    # 创建版本信息文件
    version_info = f"""# XexunRTT 增量更新信息
VERSION=1.0.0
BUILD_DATE={Path().cwd()}
EXE_SIZE={exe_path.stat().st_size}
LIBRARIES_SIZE={sum(f.stat().st_size for f in internal_dir.rglob('*') if f.is_file())}

# 更新说明
# 1. 用户代码更新：替换 XexunRTT.exe
# 2. 库文件更新：替换 _internal 目录（很少需要）
# 3. 配置文件：config.ini 会自动创建和更新
"""
    
    with open(optimized_dir / 'version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    
    print(f"✅ 优化完成: {optimized_dir}")
    return True

def create_update_tools():
    """创建更新工具"""
    
    # 创建更新脚本
    update_script = """@echo off
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
"""
    
    with open('incremental_update.bat', 'w', encoding='utf-8') as f:
        f.write(update_script)
    
    print("✅ 创建更新脚本: incremental_update.bat")
    
    # 创建验证脚本
    verify_script = """@echo off
chcp 65001 >nul
echo 🔍 XexunRTT 更新验证工具
echo ================================

set "CURRENT_DIR=%~dp0"
set "EXE_FILE=XexunRTT.exe"

echo 📁 当前目录: %CURRENT_DIR%

echo.
echo 📋 文件结构检查:

REM 检查EXE文件
if exist "%CURRENT_DIR%%EXE_FILE%" (
    echo ✅ 主程序: %EXE_FILE%
    for %%F in ("%CURRENT_DIR%%EXE_FILE%") do (
        echo    大小: %%~zF 字节 ^(%.1f MB^)
    )
) else (
    echo ❌ 缺少主程序: %EXE_FILE%
)

REM 检查_internal目录
if exist "%CURRENT_DIR%_internal" (
    echo ✅ 库目录: _internal/
    
    REM 检查重要的库
    if exist "%CURRENT_DIR%_internal\\PySide6" (
        echo ✅ Qt库: PySide6/
    ) else (
        echo ❌ 缺少Qt库: PySide6/
    )
    
    if exist "%CURRENT_DIR%_internal\\base_library.zip" (
        echo ✅ Python标准库: base_library.zip
    ) else (
        echo ❌ 缺少Python标准库: base_library.zip
    )
    
) else (
    echo ❌ 缺少库目录: _internal/
)

REM 检查配置文件
if exist "%CURRENT_DIR%config.ini" (
    echo ✅ 配置文件: config.ini
) else (
    echo ⚠️ 配置文件: config.ini (首次运行时会自动创建)
)

echo.
echo 🎯 增量更新优势:
echo    📦 快速更新: 只需替换 %EXE_FILE% (约2-5MB)
echo    💾 节省空间: 库文件重用 (约40MB+)
echo    🔧 保留配置: 用户设置不丢失
echo    ⚡ 启动更快: 库文件无需解压
echo.
pause
"""
    
    with open('verify_installation.bat', 'w', encoding='utf-8') as f:
        f.write(verify_script)
    
    print("✅ 创建验证脚本: verify_installation.bat")

def analyze_exe_content():
    """分析EXE文件内容"""
    print("🔍 分析EXE文件内容...")
    
    exe_path = Path('dist/XexunRTT_Incremental/XexunRTT.exe')
    if not exe_path.exists():
        print("❌ EXE文件不存在")
        return
    
    # 尝试使用PyInstaller工具分析
    try:
        cmd = [sys.executable, '-m', 'PyInstaller.utils.cliutils.archive_viewer', str(exe_path)]
        print("🔧 尝试分析EXE文件结构...")
        print("💡 如果要查看详细内容，可以手动运行:")
        print(f"   python -m PyInstaller.utils.cliutils.archive_viewer \"{exe_path}\"")
    except Exception as e:
        print(f"⚠️ 无法自动分析EXE内容: {e}")

def clean_build():
    """清理构建文件"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 清理spec文件
    for spec_file in Path('.').glob('*incremental*.spec'):
        print(f"🧹 删除spec文件: {spec_file}")
        spec_file.unlink()

def main():
    """主函数"""
    print("🔄 XexunRTT 简单增量更新构建工具")
    print("=" * 60)
    print("🎯 策略: 使用标准onedir模式实现增量更新")
    print("💡 优势: EXE文件相对较小，库文件分离，便于增量更新")
    print()
    
    # 检查必要文件
    required_files = [
        'main_window.py',
        'rtt2uart.py',
        'config_manager.py',
        'xexunrtt.qm', 
        'Jlink_ICON.ico',
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ 缺少必要文件:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    # 清理之前的构建
    clean_build()
    
    # 构建
    create_simple_incremental_spec()
    if not build_simple_incremental():
        return False
    
    # 优化结构
    optimize_for_incremental_update()
    
    # 创建更新工具
    create_update_tools()
    
    # 分析结果
    analyze_exe_content()
    
    print(f"\n🎉 增量更新版本构建完成!")
    
    # 显示结果
    original_dir = Path('dist/XexunRTT_Incremental')
    optimized_dir = Path('dist/XexunRTT_Optimized')
    
    if original_dir.exists():
        exe_size = (original_dir / 'XexunRTT.exe').stat().st_size / (1024 * 1024)
        internal_size = sum(f.stat().st_size for f in (original_dir / '_internal').rglob('*') if f.is_file()) / (1024 * 1024)
        
        print(f"\n📊 文件大小分析:")
        print(f"   📦 XexunRTT.exe: {exe_size:.1f} MB (用户代码+必要库)")
        print(f"   📁 _internal/: {internal_size:.1f} MB (第三方库)")
        print(f"   📋 总大小: {exe_size + internal_size:.1f} MB")
        
        print(f"\n💡 增量更新效果:")
        print(f"   🔄 更新时只需替换: {exe_size:.1f} MB (EXE文件)")
        print(f"   💾 无需更新: {internal_size:.1f} MB (库文件)")
        print(f"   📈 更新效率提升: {internal_size / (exe_size + internal_size) * 100:.1f}%")
    
    print(f"\n📁 生成的目录和文件:")
    print(f"   📂 dist/XexunRTT_Incremental/ - 标准构建结果")
    print(f"   📂 dist/XexunRTT_Optimized/ - 优化后的发布版本")
    print(f"   🔧 incremental_update.bat - 增量更新工具")
    print(f"   🔍 verify_installation.bat - 安装验证工具")
    
    print(f"\n🚀 使用方法:")
    print(f"1. 📦 首次发布: 复制 XexunRTT_Optimized 整个目录")
    print(f"2. 🔄 增量更新: 只替换 XexunRTT.exe 文件")
    print(f"3. 📋 配置保留: config.ini 等用户文件自动保留")
    print(f"4. 🛠️ 库文件更新: 极少需要，如需要则替换 _internal 目录")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
