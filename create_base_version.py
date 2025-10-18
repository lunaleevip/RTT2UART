#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成基础版本的 version.json 文件
用于首次部署时创建初始版本信息
"""

import sys
import json
import hashlib
from pathlib import Path

try:
    from version import VERSION
except ImportError:
    VERSION = "2.4"


def calculate_hash(file_path):
    """计算文件SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def create_base_version_json(exe_file, platform="win", output_dir="./base_version"):
    """
    创建基础版本的 version.json
    
    Args:
        exe_file: exe文件路径
        platform: 平台 (win/macos/linux)
        output_dir: 输出目录
    """
    exe_path = Path(exe_file)
    
    if not exe_path.exists():
        print(f"❌ 错误: 文件不存在: {exe_path}")
        return False
    
    print("=" * 70)
    print("创建基础版本信息")
    print("=" * 70)
    print()
    
    # 计算哈希和大小
    print(f"📄 文件: {exe_path.name}")
    print("🔄 计算哈希值...")
    
    file_hash = calculate_hash(exe_path)
    file_size = exe_path.stat().st_size
    
    print(f"✅ SHA256: {file_hash}")
    print(f"✅ 大小: {format_size(file_size)}")
    print()
    
    # 根据平台确定文件名
    platform_suffix = {
        'win': 'win',
        'macos': 'macOS',
        'linux': 'linux'
    }.get(platform.lower(), 'win')
    
    file_name = f"XexunRTT_v{VERSION}_{platform_suffix}.exe"
    if platform.lower() == 'macos':
        file_name = file_name.replace('.exe', '.app')
    elif platform.lower() == 'linux':
        file_name = file_name.replace('.exe', '')
    
    # 创建version.json内容
    version_data = {
        "version": VERSION,
        "platform": platform.lower(),
        "hash": file_hash,
        "file": file_name,
        "size": file_size,
        "release_notes": f"## XexunRTT v{VERSION} 基础版本\n\n### ✨ 功能特性\n- RTT调试功能\n- 串口转发\n- 日志记录\n- 自动更新\n- 文件完整性验证\n\n### 📝 说明\n这是 {platform.upper()} 平台的基础版本，后续更新将支持增量补丁下载。",
        "patches": {},
        "history": []
    }
    
    # 创建输出目录
    output_path = Path(output_dir) / platform.lower()
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 保存 version.json
    version_file = output_path / "version.json"
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(version_data, f, indent=2, ensure_ascii=False)
    
    print(f"📝 生成 version.json")
    print(f"   路径: {version_file.absolute()}")
    print()
    
    # 复制exe文件到输出目录
    import shutil
    dest_file = output_path / file_name
    
    # 如果源文件名不同，先复制再重命名
    if exe_path.name != file_name:
        print(f"📦 复制文件: {exe_path.name} → {file_name}")
        shutil.copy2(exe_path, dest_file)
    else:
        print(f"📦 复制文件: {file_name}")
        shutil.copy2(exe_path, dest_file)
    
    print(f"   路径: {dest_file.absolute()}")
    print()
    
    # 显示摘要
    print("=" * 70)
    print("✅ 基础版本创建完成!")
    print("=" * 70)
    print()
    print(f"📋 版本信息:")
    print(f"   版本号: {VERSION}")
    print(f"   平台: {platform.upper()}")
    print(f"   文件: {file_name}")
    print(f"   大小: {format_size(file_size)}")
    print(f"   哈希: {file_hash[:32]}...")
    print()
    print(f"📁 输出目录: {output_path.absolute()}")
    print()
    print("📤 下一步:")
    print(f"   1. 将 {output_path.absolute()} 目录中的文件上传到服务器:")
    print(f"      http://sz.xexun.com:18899/uploads/xexunrtt/updates/{platform.lower()}/")
    print()
    print("   2. 确保服务器配置正确:")
    print("      - version.json 可访问")
    print(f"      - {file_name} 可下载")
    print()
    print("   3. 测试更新功能:")
    print("      python test_update_cli.py connect")
    print()
    
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='创建基础版本的 version.json',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # Windows 平台
  python create_base_version.py XexunRTT_v2.4.exe --platform win
  
  # macOS 平台
  python create_base_version.py XexunRTT.app --platform macos
  
  # Linux 平台
  python create_base_version.py XexunRTT --platform linux
        '''
    )
    
    parser.add_argument('exe_file', help='可执行文件路径')
    parser.add_argument('--platform', '-p', choices=['win', 'macos', 'linux'], 
                       default='win', help='平台 (默认: win)')
    parser.add_argument('--output', '-o', default='./base_version',
                       help='输出目录 (默认: ./base_version)')
    
    args = parser.parse_args()
    
    success = create_base_version_json(
        args.exe_file,
        args.platform,
        args.output
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

