#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动优化的PyInstaller构建脚本
专门针对减少启动时间进行优化
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_fast_spec():
    """创建快速启动优化的spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# 快速启动优化的PyInstaller配置文件
# 专门针对减少启动时间进行优化

import sys
from pathlib import Path

# 分析配置 - 启动优化
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        # 只包含必要的数据文件
        ('xexunrtt.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
    ],
    hiddenimports=[
        # 只包含必要的隐式导入
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pylink',
        'serial',
        'serial.tools.list_ports',
        'logging',
        'psutil',  # 进程管理需要
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 大幅减少不需要的模块 - 提高启动速度
        'tkinter',
        'unittest', 
        'test',
        'email',
        'http',
        'urllib',
        'pydoc',
        'doctest',
        'pdb',
        'profile',
        'cProfile',
        'pstats',
        'trace',
        'timeit',
        'webbrowser',
        'pip',
        'setuptools',
        'distutils',
        'wheel',
        'pytest',
        'nose',
        'mock',
        # 排除PySide6中不需要的大模块
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.QtAxContainer',
        'PySide6.QtBluetooth',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtDBus',
        'PySide6.QtDesigner',
        'PySide6.QtGraphs',
        'PySide6.QtGraphsWidgets',
        'PySide6.QtHelp',
        'PySide6.QtHttpServer',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtNetworkAuth',
        'PySide6.QtNfc',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtPositioning',
        'PySide6.QtPrintSupport',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtSensors',
        'PySide6.QtSerialBus',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSql',
        'PySide6.QtStateMachine',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtTest',
        'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools',
        'PySide6.QtWebChannel',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebSockets',
        'PySide6.QtWebView',
        'PySide6.QtXml',
    ],
    # 启动优化设置
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,  # 保持False以减少启动时间
)

# PYZ配置 - 启动优化
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE配置 - 快速启动版本
exe = EXE(
    pyz,
    a.scripts,
    [],  # 不包含binaries和datas在这里，用onedir模式
    exclude_binaries=True,  # 使用目录模式而不是单文件模式
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不使用UPX压缩
    console=False,  # Windows GUI应用
    disable_windowed_traceback=False,
    icon='Jlink_ICON.ico',
)

# COLLECT - 目录模式，启动更快
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XexunRTT_Fast'
)
"""
    
    with open('XexunRTT_fast.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 创建快速启动spec文件: XexunRTT_fast.spec")

def build_fast_onefile():
    """构建优化的单文件版本"""
    print("🚀 构建优化的单文件版本...")
    
    # 优化的单文件构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # 单文件模式
        '--windowed',                   # GUI程序
        '--name=XexunRTT_Fast',        # 程序名称
        '--icon=Jlink_ICON.ico',       # 程序图标
        # 只添加必要的数据文件
        '--add-data=xexunrtt.qm;.',
        '--add-data=qt_zh_CN.qm;.',
        '--add-data=JLinkCommandFile.jlink;.',
        '--add-data=JLinkDevicesBuildIn.xml;.',
        '--add-data=cmd.txt;.',
        '--add-data=picture;picture',
        # 只包含必要的隐式导入
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=pylink',
        '--hidden-import=serial',
        '--hidden-import=serial.tools.list_ports',
        '--hidden-import=logging',
        '--hidden-import=psutil',
        # 不使用collect-all，只导入需要的模块
        # 排除大量不必要的模块
        '--exclude-module=tkinter',
        '--exclude-module=unittest',
        '--exclude-module=test',
        '--exclude-module=email',
        '--exclude-module=http',
        '--exclude-module=urllib',
        '--exclude-module=pydoc',
        '--exclude-module=PySide6.Qt3DAnimation',
        '--exclude-module=PySide6.Qt3DCore',
        '--exclude-module=PySide6.Qt3DRender',
        '--exclude-module=PySide6.Qt3DExtras',
        '--exclude-module=PySide6.QtCharts',
        '--exclude-module=PySide6.QtDataVisualization',
        '--exclude-module=PySide6.QtWebEngineCore',
        '--exclude-module=PySide6.QtWebEngineWidgets',
        '--exclude-module=PySide6.QtMultimedia',
        '--exclude-module=PySide6.QtQml',
        '--exclude-module=PySide6.QtQuick',
        # 其他优化选项
        '--noupx',                     # 不使用UPX压缩
        '--strip',                     # 去除调试符号
        '--distpath=dist_fast',        # 输出到专门目录
        '--workpath=build_fast',       # 专门工作目录
        '--specpath=.',
        'main_window.py'
    ]
    
    print("构建命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 快速版本构建成功!")
        
        # 检查生成的文件
        exe_path = Path('dist_fast/XexunRTT_Fast.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 生成的EXE文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")
            print(f"💡 启动优化: 减少了 {214.6 - size_mb:.1f} MB")
        else:
            print("❌ 未找到生成的EXE文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    
    return True

def build_fast_onedir():
    """使用spec文件构建目录模式（启动最快）"""
    print("🚀 构建目录模式版本（启动最快）...")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        'XexunRTT_fast.spec'
    ]
    
    print("构建命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 目录模式构建成功!")
        
        # 检查生成的文件
        exe_path = Path('dist/XexunRTT_Fast/XexunRTT.exe')
        if exe_path.exists():
            print(f"📦 生成的EXE文件: {exe_path}")
            print("🚀 这个版本启动最快！")
            
            # 创建启动脚本
            create_fast_startup_script()
        else:
            print("❌ 未找到生成的EXE文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    
    return True

def create_fast_startup_script():
    """创建快速启动脚本"""
    script_content = """@echo off
echo 🚀 XexunRTT 快速启动版本
echo.

REM 检查目录版本（启动最快）
if exist "dist\\XexunRTT_Fast\\XexunRTT.exe" (
    echo 📁 启动目录版本（最快）...
    start "" "dist\\XexunRTT_Fast\\XexunRTT.exe"
    echo ✅ 已启动目录版本
    goto :end
)

REM 检查优化单文件版本
if exist "dist_fast\\XexunRTT_Fast.exe" (
    echo 📦 启动优化单文件版本...
    start "" "dist_fast\\XexunRTT_Fast.exe"
    echo ✅ 已启动优化版本
    goto :end
)

REM 检查标准版本
if exist "dist\\XexunRTT.exe" (
    echo 📦 启动标准版本...
    start "" "dist\\XexunRTT.exe"
    echo ✅ 已启动标准版本
    goto :end
)

echo ❌ 未找到任何版本的程序文件！
echo 请先运行构建脚本：
echo   python build_fast_startup.py

:end
echo.
pause
"""
    
    with open('run_fast.bat', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("✅ 创建快速启动脚本: run_fast.bat")

def clean_build():
    """清理构建文件"""
    dirs_to_clean = ['build', 'dist', 'build_fast', 'dist_fast', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 清理spec文件
    for spec_file in Path('.').glob('*_fast.spec'):
        print(f"🧹 删除spec文件: {spec_file}")
        spec_file.unlink()

def main():
    """主函数"""
    print("⚡ XexunRTT 快速启动构建工具")
    print("=" * 50)
    print("🎯 专门优化启动速度，解决EXE启动慢的问题")
    print()
    
    # 检查必要文件
    required_files = [
        'main_window.py',
        'xexunrtt.qm', 
        'Jlink_ICON.ico',
        'JLinkCommandFile.jlink'
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
    
    print("🔧 启动优化策略:")
    print("  1️⃣ 目录模式 - 启动最快（推荐）")
    print("  2️⃣ 优化单文件 - 体积小，启动较快")
    print()
    
    success = False
    
    # 1. 构建目录模式（启动最快）
    print("=" * 30)
    print("1️⃣ 构建目录模式版本...")
    create_fast_spec()
    if build_fast_onedir():
        success = True
        print("✅ 目录模式构建成功！启动速度最快")
    
    print()
    
    # 2. 构建优化单文件版本
    print("=" * 30)
    print("2️⃣ 构建优化单文件版本...")
    if build_fast_onefile():
        success = True
        print("✅ 优化单文件构建成功！体积更小")
    
    if success:
        print()
        print("🎉 快速启动版本构建完成!")
        print()
        print("📁 可用版本:")
        
        # 检查目录版本
        if Path('dist/XexunRTT_Fast/XexunRTT.exe').exists():
            print("  🚀 目录版本: dist/XexunRTT_Fast/XexunRTT.exe (启动最快)")
        
        # 检查单文件版本
        if Path('dist_fast/XexunRTT_Fast.exe').exists():
            size_mb = Path('dist_fast/XexunRTT_Fast.exe').stat().st_size / (1024 * 1024)
            print(f"  📦 单文件版本: dist_fast/XexunRTT_Fast.exe ({size_mb:.1f} MB)")
        
        print()
        print("🚀 使用快速启动脚本: run_fast.bat")
        print()
        print("💡 启动速度对比:")
        print("  目录版本    ⚡⚡⚡⚡⚡ (最快)")
        print("  优化单文件  ⚡⚡⚡⚡")
        print("  标准单文件  ⚡⚡")
        
        return True
    else:
        print("\n❌ 构建失败!")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
