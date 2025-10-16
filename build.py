#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一构建脚本 - 从version.py读取版本号并自动生成版本信息文件
支持平台: Windows, macOS, Linux
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

# 导入版本信息
try:
    from version import VERSION, VERSION_NAME, BUILD_TIME
except ImportError:
    print("错误: 无法导入version.py，请确保文件存在")
    sys.exit(1)

# 解析版本号（例如 "2.3" -> (2, 3, 0, 0)）
def parse_version(version_str):
    """将版本字符串解析为4位版本号元组"""
    parts = version_str.split('.')
    # 补齐到4位
    while len(parts) < 4:
        parts.append('0')
    # 只取前4位
    parts = parts[:4]
    return tuple(int(p) for p in parts)

# 获取平台信息
PLATFORM = platform.system()  # 'Windows', 'Darwin' (macOS), 'Linux'
IS_WINDOWS = PLATFORM == 'Windows'
IS_MACOS = PLATFORM == 'Darwin'
IS_LINUX = PLATFORM == 'Linux'

# 生成版本信息文件
def generate_version_info():
    """生成Windows版本信息文件（仅限Windows平台）"""
    # 非Windows平台不需要生成版本信息文件
    if not IS_WINDOWS:
        print(f"[SKIP] 当前平台 {PLATFORM} 不需要生成版本信息文件")
        return None
    
    version_tuple = parse_version(VERSION)
    version_str = '.'.join(str(v) for v in version_tuple)
    
    version_info_content = f"""# UTF-8
#
# 版本信息文件 v{VERSION} - 自动生成
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
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
            StringStruct(u'CompanyName', u'{VERSION_NAME} Development Team'),
            StringStruct(u'FileDescription', u'{VERSION_NAME} v{VERSION}'),
            StringStruct(u'FileVersion', u'{version_str}'),
            StringStruct(u'InternalName', u'{VERSION_NAME}'),
            StringStruct(u'LegalCopyright', u'Copyright © 2024-2025 {VERSION_NAME} Team'),
            StringStruct(u'OriginalFilename', u'{VERSION_NAME}.exe'),
            StringStruct(u'ProductName', u'{VERSION_NAME} v{VERSION}'),
            StringStruct(u'ProductVersion', u'{version_str}'),
            StringStruct(u'Comments', u'Build time: {BUILD_TIME}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    
    version_info_file = f'version_info_v{VERSION}.txt'
    with open(version_info_file, 'w', encoding='utf-8') as f:
        f.write(version_info_content)
    
    print(f"[OK] 生成版本信息文件: {version_info_file}")
    return version_info_file

# 更新spec文件中的version参数
def update_spec_file(spec_file, version_info_file):
    """更新spec文件中的version参数（仅限Windows）"""
    # 如果没有版本信息文件（非Windows平台），跳过
    if version_info_file is None:
        print(f"[SKIP] 非Windows平台，无需更新spec文件的version参数")
        return
    
    with open(spec_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换version参数
    import re
    content = re.sub(
        r"version='version_info_v\d+_\d+\.txt'",
        f"version='{version_info_file}'",
        content
    )
    
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"[OK] 更新spec文件: {spec_file}")

def get_spec_file():
    """根据平台获取对应的spec文件"""
    if IS_MACOS:
        return 'XexunRTT_cross_macOS.spec'
    else:
        # Windows和Linux使用同一个spec文件
        return 'XexunRTT_onefile_v2_2.spec'

def get_output_extension():
    """根据平台获取输出文件扩展名"""
    if IS_WINDOWS:
        return '.exe'
    elif IS_MACOS:
        return '.app'
    else:
        return ''  # Linux没有扩展名

def main():
    """主构建流程"""
    print(f"{'='*60}")
    print(f"  {VERSION_NAME} 构建脚本")
    print(f"  版本: v{VERSION}")
    print(f"  平台: {PLATFORM}")
    print(f"  构建时间: {BUILD_TIME}")
    print(f"{'='*60}\n")
    
    # 1. 生成版本信息文件（仅Windows）
    print("[1/3] 生成版本信息文件...")
    version_info_file = generate_version_info()
    
    # 2. 更新spec文件
    print("\n[2/3] 更新构建配置...")
    spec_file = get_spec_file()
    if os.path.exists(spec_file):
        update_spec_file(spec_file, version_info_file)
    else:
        print(f"警告: {spec_file} 不存在，将使用默认配置")
    
    # 3. 运行PyInstaller
    print("\n[3/3] 开始编译...")
    cmd = ['pyinstaller', spec_file, '--clean']
    print(f"执行命令: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd)
    
    # 4. 显示结果
    output_ext = get_output_extension()
    output_file = f"dist/{VERSION_NAME}_v{VERSION}{output_ext}"
    
    if result.returncode == 0:
        print(f"\n{'='*60}")
        print(f"  [SUCCESS] 构建成功！")
        print(f"  平台: {PLATFORM}")
        print(f"  输出文件: {output_file}")
        
        # 检查文件是否真的存在
        if IS_WINDOWS:
            exe_path = f"dist/{VERSION_NAME}_v{VERSION}.exe"
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path)
                print(f"  文件大小: {size:,} 字节 ({size/1024/1024:.2f} MB)")
        elif IS_MACOS:
            app_path = f"dist/{VERSION_NAME}_v{VERSION}.app"
            if os.path.exists(app_path):
                print(f"  应用包: {app_path}")
        else:  # Linux
            bin_path = f"dist/{VERSION_NAME}_v{VERSION}"
            if os.path.exists(bin_path):
                size = os.path.getsize(bin_path)
                print(f"  文件大小: {size:,} 字节 ({size/1024/1024:.2f} MB)")
        
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"  [ERROR] 构建失败！")
        print(f"  平台: {PLATFORM}")
        print(f"  错误代码: {result.returncode}")
        print(f"{'='*60}")
        sys.exit(result.returncode)

if __name__ == '__main__':
    main()

