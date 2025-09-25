#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT v2.1.1 单文件版本构建脚本
生成单个EXE文件，便于分发和使用
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import time

def create_onefile_spec():
    """创建单文件版本的spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# XexunRTT v2.1.1 单文件版本构建配置

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path.cwd()))

# 分析配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        ('xexunrtt_complete.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
    ],
    hiddenimports=[
        # 核心模块
        'xml.etree.ElementTree',
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pylink',
        'serial',
        'serial.tools.list_ports',
        'logging',
        'logging.handlers',
        'configparser',
        'threading',
        'queue',
        'time',
        'datetime',
        'uuid',
        'pathlib',
        'shutil',
        'psutil',
        'qdarkstyle',
        
        # 编码相关
        'encodings.utf_8',
        'encodings.gbk',
        'encodings.cp936',
        'encodings.ascii',
        
        # Qt资源
        'resources_rc',
        
        # UI文件
        'ui_rtt2uart_updated',
        'ui_sel_device',
        'ui_xexunrtt',
        
        # 其他核心模块
        'rtt2uart',
        'config_manager',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减少体积
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'PyQt5',
        'PyQt6',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ配置
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE配置 - 单文件模式
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XexunRTT_v2.1.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 启用UPX压缩
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Jlink_ICON.ico',  # 程序图标
    version_file=None,
    onefile=True,  # 关键：启用单文件模式
)
"""
    
    return spec_content

def clean_build_dirs():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name)
    
    # 删除旧的spec文件
    spec_files = ['XexunRTT_onefile_v2_1_1.spec']
    for spec_file in spec_files:
        if os.path.exists(spec_file):
            print(f"🧹 删除spec文件: {spec_file}")
            os.remove(spec_file)

def build_onefile():
    """构建单文件版本"""
    print("🔄 XexunRTT v2.1.1 单文件版本构建工具")
    print("=" * 60)
    print("🎯 目标: 生成单个EXE文件，便于分发")
    print("💡 特点: 所有依赖打包到一个文件中")
    print()
    
    # 清理构建目录
    clean_build_dirs()
    
    # 创建spec文件
    spec_filename = "XexunRTT_onefile_v2_1_1.spec"
    spec_content = create_onefile_spec()
    
    with open(spec_filename, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"✅ 创建单文件spec文件: {spec_filename}")
    
    # 构建命令
    python_exe = sys.executable
    build_cmd = [python_exe, '-m', 'PyInstaller', '--clean', '--noconfirm', spec_filename]
    
    print("🚀 开始构建单文件版本...")
    print("构建命令:", ' '.join(build_cmd))
    print("-" * 60)
    
    # 记录开始时间
    start_time = time.time()
    
    # 执行构建
    try:
        result = subprocess.run(build_cmd, capture_output=False, text=True)
        if result.returncode == 0:
            build_time = time.time() - start_time
            print("-" * 60)
            print("✅ 单文件版本构建成功!")
            
            # 检查生成的文件
            exe_path = Path("dist") / "XexunRTT_v2.1.1.exe"
            if exe_path.exists():
                file_size = exe_path.stat().st_size
                file_size_mb = file_size / (1024 * 1024)
                
                print(f"📦 生成的单文件: {exe_path}")
                print(f"📏 文件大小: {file_size_mb:.1f} MB")
                print(f"⏱️ 构建时间: {build_time:.1f} 秒")
                
                print("\n🎯 单文件版本特点:")
                print("- 📦 所有依赖打包到一个EXE文件")
                print("- 🚀 无需安装，双击即可运行")
                print("- 💾 首次运行会自解压到临时目录")
                print("- 📁 配置文件仍保存在用户目录")
                
                print("\n🚀 使用方法:")
                print("1. 复制XexunRTT_v2.1.1.exe到任意目录")
                print("2. 双击运行即可，无需其他文件")
                print("3. 首次运行可能需要稍等解压时间")
                
                print("\n💡 性能说明:")
                print("- 启动速度比多文件版本稍慢")
                print("- 运行时性能完全相同")
                print("- 适合单机部署和便携使用")
                
            else:
                print("❌ 未找到生成的EXE文件")
                return False
        else:
            print("❌ 构建失败")
            return False
            
    except Exception as e:
        print(f"❌ 构建过程出现异常: {e}")
        return False
    
    return True

def create_portable_package():
    """创建便携版包"""
    exe_path = Path("dist") / "XexunRTT_v2.1.1.exe"
    if not exe_path.exists():
        print("❌ 未找到单文件EXE，跳过便携版创建")
        return
    
    print("\n🔧 创建便携版包...")
    
    # 创建便携版目录
    portable_dir = Path("dist") / "XexunRTT_v2.1.1_Portable"
    portable_dir.mkdir(exist_ok=True)
    
    # 复制EXE文件
    portable_exe = portable_dir / "XexunRTT_v2.1.1.exe"
    shutil.copy2(exe_path, portable_exe)
    
    # 创建说明文件
    readme_content = """# XexunRTT v2.1.1 便携版

## 🚀 快速开始
1. 双击 `XexunRTT_v2.1.1.exe` 即可运行
2. 首次运行会自动创建配置文件
3. 无需安装任何其他软件

## 📁 文件说明
- `XexunRTT_v2.1.1.exe`: 主程序（单文件版本）
- 配置文件: 自动保存在 `%APPDATA%\\XexunRTT\\`

## 🎯 版本特性
- ✅ 修复Worker缓存污染BUG
- ✅ 修复滚动条锁定状态保存BUG
- ✅ 完整的中英文翻译支持
- ✅ 设备选择索引修复

## 💡 使用提示
- 首次启动可能需要10-15秒（自解压）
- 后续启动速度正常
- 可复制到U盘等移动设备使用

## 📞 技术支持
版本: v2.1.1
构建日期: 2025-09-23
"""
    
    readme_file = portable_dir / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ 便携版包创建完成: {portable_dir}")
    print(f"📦 包含文件: EXE + README")

def main():
    """主函数"""
    try:
        success = build_onefile()
        if success:
            create_portable_package()
            print("\n" + "=" * 60)
            print("🎉 XexunRTT v2.1.1 单文件版本构建完成!")
            print("\n📁 输出文件:")
            print("- dist/XexunRTT_v2.1.1.exe (单文件版本)")
            print("- dist/XexunRTT_v2.1.1_Portable/ (便携版包)")
        else:
            print("\n❌ 构建失败")
            return 1
    except KeyboardInterrupt:
        print("\n⚠️ 构建被用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 构建过程出现异常: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
