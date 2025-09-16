#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT v2.1 专用构建脚本
包含日志拆分功能的版本构建
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

def create_v2_1_spec():
    """创建v2.1版本的spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# XexunRTT v2.1 版本构建配置
# 包含日志拆分功能

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
        ('xexunrtt.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
        ('config.ini', '.'),
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
        # v2.1新增模块
        'config_manager',
        'rtt2uart',
        'ansi_terminal_widget',
        # 编码支持
        'encodings.utf_8',
        'encodings.gbk',
        'encodings.cp936',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块
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
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ配置
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# EXE配置 - v2.1版本
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='XexunRTT_v2.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Jlink_ICON.ico',
    version='version_info_v2_1.txt'
)
"""
    
    with open('XexunRTT_v2_1.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 创建v2.1版本spec文件: XexunRTT_v2_1.spec")

def clean_build():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist_v2_1']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"🧹 清理目录: {dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)

def build_v2_1():
    """构建v2.1版本"""
    print("🚀 开始构建XexunRTT v2.1版本...")
    
    # 清理之前的构建
    clean_build()
    
    # 创建配置文件
    create_v2_1_spec()
    
    # 创建输出目录
    os.makedirs('dist_v2_1', exist_ok=True)
    
    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        '--distpath=dist_v2_1',
        'XexunRTT_v2_1.spec'
    ]
    
    print("🔨 执行构建命令...")
    print("命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ v2.1版本构建成功!")
        
        # 检查生成的文件
        exe_path = Path('dist_v2_1/XexunRTT_v2.1.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 生成的v2.1 EXE文件: {exe_path}")
            print(f"📏 文件大小: {size_mb:.1f} MB")
            
            # 复制配置文件
            config_files = ['config.ini', 'cmd.txt']
            for config_file in config_files:
                if os.path.exists(config_file):
                    shutil.copy2(config_file, 'dist_v2_1/')
                    print(f"📋 复制配置文件: {config_file}")
            
            # 创建版本说明文件
            create_version_readme()
            
            print("\n🎉 v2.1版本特性:")
            print("  ✅ 日志拆分功能")
            print("  ✅ 可选择每次连接使用新目录")
            print("  ✅ 保持上次日志目录选项")
            print("  ✅ 完整的配置管理")
            
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

def create_version_readme():
    """创建版本说明文件"""
    readme_content = f"""# XexunRTT v2.1 - 日志拆分功能版

## 版本信息
- 版本号: v2.1.0
- 构建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 特性: 日志拆分功能

## 新增功能

### 日志拆分功能
- 在主界面添加了"日志拆分"复选框
- 勾选时：每次连接会创建新的时间戳目录
- 不勾选时：继续使用上次的日志目录
- 默认状态：开启

### 相关配置
- 配置项位置：[Logging] 节中的 log_split
- 目录记忆：last_log_directory 记录上次使用的目录

## 实现文件
1. rtt2uart_updated.ui - UI界面更新
2. ui_rtt2uart_updated.py - UI代码重新生成
3. config_manager.py - 配置管理增强
4. main_window.py - 事件处理
5. rtt2uart.py - 核心逻辑支持

## 使用说明
1. 启动程序后在主界面可看到"日志拆分"选项
2. 勾选后每次连接都会创建新的日志目录
3. 不勾选则延续使用上次的目录
4. 配置会自动保存和恢复

## 技术实现
- 基于时间戳的目录命名
- 配置持久化存储
- UI事件与核心逻辑分离
- 向后兼容性保持
"""
    
    with open('dist_v2_1/v2.1功能说明.md', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("📄 创建版本说明: dist_v2_1/v2.1功能说明.md")

def create_release_package():
    """创建发布包"""
    if not os.path.exists('dist_v2_1/XexunRTT_v2.1.exe'):
        print("❌ 未找到构建的EXE文件，无法创建发布包")
        return False
    
    # 创建发布包目录
    release_dir = f"XexunRTT_v2.1_日志拆分功能版_{datetime.now().strftime('%Y%m%d')}"
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    
    os.makedirs(release_dir)
    
    # 复制文件到发布包
    files_to_copy = [
        ('dist_v2_1/XexunRTT_v2.1.exe', 'XexunRTT_v2.1.exe'),
        ('dist_v2_1/config.ini', 'config.ini'),
        ('dist_v2_1/cmd.txt', 'cmd.txt'),
        ('dist_v2_1/v2.1功能说明.md', 'v2.1功能说明.md'),
    ]
    
    for src, dst in files_to_copy:
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(release_dir, dst))
            print(f"📦 打包文件: {dst}")
    
    # 创建zip包
    import zipfile
    zip_path = f"{release_dir}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(release_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, release_dir)
                zipf.write(file_path, arcname)
    
    print(f"📦 创建发布包: {zip_path}")
    return True

def main():
    """主函数"""
    print("🚀 XexunRTT v2.1 构建工具")
    print("日志拆分功能版本")
    print("=" * 60)
    
    # 检查必要文件
    required_files = [
        'main_window.py',
        'config_manager.py',
        'rtt2uart.py',
        'xexunrtt.qm', 
        'Jlink_ICON.ico',
        'JLinkCommandFile.jlink',
        'version_info_v2_1.txt'
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
    
    # 执行构建
    if build_v2_1():
        print("\n🎉 v2.1版本构建完成!")
        print("📁 EXE文件位置: dist_v2_1/XexunRTT_v2.1.exe")
        
        # 询问是否创建发布包
        try:
            create_package = input("\n是否创建发布包? (y/n): ").lower().strip()
            if create_package in ['y', 'yes', '是', '']:
                if create_release_package():
                    print("✅ 发布包创建完成!")
                else:
                    print("❌ 发布包创建失败!")
        except KeyboardInterrupt:
            print("\n构建完成，跳过发布包创建")
        
        return True
    else:
        print("\n❌ v2.1版本构建失败!")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
