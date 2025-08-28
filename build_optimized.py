#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
优化的PyInstaller构建脚本
专门针对减少杀毒软件误报进行优化
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_optimized_spec():
    """创建优化的spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# 优化的PyInstaller配置文件
# 专门针对减少杀毒软件误报进行优化

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path.cwd()))

# 分析配置
a = Analysis(
    ['new_main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        ('xexunrtt.qm', '.'),
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
        # 减少误报的关键模块
        'encodings.utf_8',
        'encodings.gbk',
        'encodings.cp936',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块以减少体积和误报
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
        # 排除开发工具
        'pip',
        'setuptools',
        'distutils',
        'wheel',
        # 排除测试框架
        'pytest',
        'nose',
        'mock',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ配置
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE配置 - 优化版本信息
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 不使用UPX压缩，避免误报
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windows GUI应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Jlink_ICON.ico',
    # 版本信息 - 有助于减少误报
    version='version_info.txt'
)
"""
    
    with open('XexunRTT_optimized.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 创建优化的spec文件: XexunRTT_optimized.spec")

def create_version_info():
    """创建版本信息文件"""
    version_info = """# UTF-8
#
# 版本信息文件 - 有助于减少杀毒软件误报
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 5, 0),
    prodvers=(1, 0, 5, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'XexunRTT Development Team'),
            StringStruct(u'FileDescription', u'RTT to UART Debug Tool'),
            StringStruct(u'FileVersion', u'1.0.5.0'),
            StringStruct(u'InternalName', u'XexunRTT'),
            StringStruct(u'LegalCopyright', u'Copyright © 2024 XexunRTT Team'),
            StringStruct(u'OriginalFilename', u'XexunRTT.exe'),
            StringStruct(u'ProductName', u'XexunRTT - RTT2UART Debug Tool'),
            StringStruct(u'ProductVersion', u'1.0.5.0'),
            StringStruct(u'Comments', u'Professional RTT to UART conversion tool for embedded development')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    
    print("✅ 创建版本信息文件: version_info.txt")

def build_optimized():
    """使用优化配置构建"""
    print("🚀 开始优化构建...")
    
    # 清理之前的构建
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 创建配置文件
    create_optimized_spec()
    create_version_info()
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',  # 清理缓存
        '--noconfirm',  # 不询问覆盖
        'XexunRTT_optimized.spec'
    ]
    
    print("🔨 执行构建命令...")
    print("命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 优化构建成功完成!")
        
        # 检查生成的文件
        exe_path = Path('dist/XexunRTT.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 生成的EXE文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")
            
            # 显示优化信息
            print("\n🛡️ 反病毒优化措施:")
            print("  ✅ 添加了详细的版本信息")
            print("  ✅ 排除了不必要的模块")
            print("  ✅ 禁用了UPX压缩")
            print("  ✅ 使用了标准的GUI配置")
            print("  ✅ 包含了完整的元数据")
            
        else:
            print("❌ 未找到生成的EXE文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 构建过程中出现错误: {e}")
        return False
    
    return True

def main():
    """主函数"""
    print("🛡️ XexunRTT 优化构建工具")
    print("专门针对减少杀毒软件误报进行优化")
    print("=" * 60)
    
    # 检查必要文件
    required_files = [
        'new_main_window.py',
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
    
    # 执行优化构建
    if build_optimized():
        print("\n🎉 优化构建完成!")
        print("📁 EXE文件位置: dist/XexunRTT.exe")
        print("\n💡 减少误报的建议:")
        print("  1. 首次运行时选择'允许'或'信任'")
        print("  2. 将程序添加到杀毒软件白名单")
        print("  3. 从可信任的来源下载和分发")
        print("  4. 提供源代码链接增加可信度")
        return True
    else:
        print("\n❌ 优化构建失败!")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
