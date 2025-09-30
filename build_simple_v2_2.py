#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT v2.2 简化构建脚本
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def clean_build_dirs():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"已清理目录: {dir_name}")
            except Exception as e:
                print(f"清理目录失败 {dir_name}: {e}")

def main():
    """主函数"""
    print("XexunRTT v2.2 构建工具")
    print("=" * 40)
    
    # 清理旧文件
    clean_build_dirs()
    
    # 构建命令
    cmd = [
        'pyinstaller', 
        '--onefile',
        '--windowed',
        '--icon=Jlink_ICON.ico',
        '--version-file=version_info_v2_2.txt',
        '--add-data=xexunrtt_complete.qm;.',
        '--add-data=qt_zh_CN.qm;.',
        '--add-data=JLinkCommandFile.jlink;.',
        '--add-data=JLinkDevicesBuildIn.xml;.',
        '--add-data=cmd.txt;.',
        '--add-data=picture;picture',
        '--hidden-import=xml.etree.ElementTree',
        '--hidden-import=PySide6.QtCore',
        '--hidden-import=PySide6.QtGui',
        '--hidden-import=PySide6.QtWidgets',
        '--hidden-import=pylink',
        '--hidden-import=serial',
        '--hidden-import=serial.tools.list_ports',
        '--hidden-import=logging',
        '--hidden-import=configparser',
        '--hidden-import=threading',
        '--hidden-import=queue',
        '--hidden-import=qdarkstyle',
        '--hidden-import=resources_rc',
        '--hidden-import=ui_xexunrtt',
        '--hidden-import=rtt2uart',
        '--hidden-import=config_manager',
        '--hidden-import=dis',
        '--hidden-import=inspect',
        '--name=XexunRTT_v2.2',
        'main_window.py'
    ]
    
    print("开始构建...")
    print(f"命令: {' '.join(cmd[:3])} ...")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("构建成功!")
        
        # 检查生成的文件
        exe_path = Path('dist/XexunRTT_v2.2.exe')
        if exe_path.exists():
            file_size = exe_path.stat().st_size / (1024 * 1024)
            print(f"生成文件: {exe_path}")
            print(f"文件大小: {file_size:.1f} MB")
            return True
        else:
            print("未找到生成的EXE文件")
            return False
            
    except subprocess.CalledProcessError as e:
        print("构建失败!")
        print(f"错误: {e}")
        if e.stderr:
            print(f"错误输出: {e.stderr}")
        return False
    except Exception as e:
        print(f"构建异常: {e}")
        return False

if __name__ == '__main__':
    success = main()
    if success:
        print("\nv2.2构建完成!")
        print("新功能:")
        print("- 筛选TAB支持正则表达式")
        print("- 单个TAB独立正则配置")
        print("- 修复TAB切换重复数据问题")
        print("- 增加MAX_TAB_SIZE到32个")
    else:
        print("\n构建失败")
    
    sys.exit(0 if success else 1)
