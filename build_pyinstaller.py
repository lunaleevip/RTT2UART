#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller构建脚本
用于将RTT2UART程序打包成单个EXE文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def clean_build():
    """清理之前的构建文件"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 清理spec文件
    for spec_file in Path('.').glob('*.spec'):
        print(f"删除spec文件: {spec_file}")
        spec_file.unlink()

def build_exe():
    """使用PyInstaller构建EXE"""
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # 打包成单个文件
        '--windowed',                   # Windows GUI程序（不显示控制台）
        '--name=XexunRTT',             # 程序名称
        '--icon=Jlink_ICON.ico',       # 程序图标
        '--add-data=xexunrtt.qm;.',    # 添加翻译文件
        '--add-data=qt_zh_CN.qm;.',    # 添加Qt翻译文件
        '--add-data=JLinkCommandFile.jlink;.',  # JLink配置文件
        '--add-data=JLinkDevicesBuildIn.xml;.', # JLink设备数据库
        '--add-data=cmd.txt;.',        # 命令文件
        '--add-data=picture;picture',  # 图片目录
        '--hidden-import=xml.etree.ElementTree',  # 隐式导入XML模块
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui', 
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=pylink',
        '--hidden-import=serial',
        '--hidden-import=serial.tools.list_ports',
        '--hidden-import=logging',
        '--hidden-import=logging.handlers',
        '--collect-all=PySide6',       # 收集所有PySide6模块
        '--collect-all=pylink',        # 收集所有pylink模块
        '--collect-all=serial',        # 收集所有serial模块
        '--exclude-module=tkinter',    # 排除不需要的模块
        '--exclude-module=unittest',
        '--exclude-module=test',
        '--exclude-module=email',
        '--exclude-module=http',
        '--exclude-module=urllib',
        '--exclude-module=pydoc',
        '--distpath=dist',             # 输出目录
        '--workpath=build',            # 工作目录
        '--specpath=.',                # spec文件位置
        'main_window.py'               # 主程序文件
    ]
    
    print("开始PyInstaller构建...")
    print("命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 构建成功完成!")
        
        # 检查生成的文件
        exe_path = Path('dist/XexunRTT.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 生成的EXE文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")
        else:
            print("❌ 未找到生成的EXE文件")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 构建过程中出现错误: {e}")
        return False
    
    return True

def create_startup_script():
    """创建启动脚本"""
    script_content = """@echo off
echo Starting XexunRTT v1.0.5...
echo.
if exist "dist\\XexunRTT.exe" (
    echo Found XexunRTT.exe, starting...
    start "" "dist\\XexunRTT.exe"
    echo XexunRTT started successfully!
) else (
    echo Error: XexunRTT.exe not found in dist folder!
    echo Please run build_pyinstaller.py first.
)
echo.
pause
"""
    
    with open('run_pyinstaller.bat', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("✅ 创建启动脚本: run_pyinstaller.bat")

def main():
    """主函数"""
    print("🚀 RTT2UART PyInstaller 构建工具")
    print("=" * 50)
    
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
    
    # 构建EXE
    if build_exe():
        create_startup_script()
        print("\n🎉 构建完成!")
        print("📁 EXE文件位置: dist/XexunRTT.exe")
        print("🚀 运行启动脚本: run_pyinstaller.bat")
        return True
    else:
        print("\n❌ 构建失败!")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
