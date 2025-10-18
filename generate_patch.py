#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成差异补丁工具
用于在服务器端创建版本间的差异补丁文件
"""

import os
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List

try:
    import bsdiff4
except ImportError:
    print("错误: 需要安装 bsdiff4")
    print("请运行: pip install bsdiff4")
    exit(1)


def calculate_hash(file_path: Path) -> str:
    """计算文件SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_patch(old_file: Path, new_file: Path, patch_file: Path):
    """
    生成差异补丁
    
    Args:
        old_file: 旧版本文件
        new_file: 新版本文件  
        patch_file: 输出的补丁文件
        
    Returns:
        (patch_size, old_hash): 补丁大小和旧文件哈希值
    """
    print(f"正在生成补丁: {old_file.name} -> {new_file.name}")
    
    # 读取文件
    with open(old_file, 'rb') as f:
        old_data = f.read()
    
    with open(new_file, 'rb') as f:
        new_data = f.read()
    
    # 计算旧文件哈希（用于完整性验证）
    old_hash = calculate_hash(old_file)
    
    # 生成补丁
    patch = bsdiff4.diff(old_data, new_data)
    
    # 保存补丁
    with open(patch_file, 'wb') as f:
        f.write(patch)
    
    # 统计信息
    old_size = len(old_data)
    new_size = len(new_data)
    patch_size = len(patch)
    
    ratio = (1 - patch_size / new_size) * 100 if new_size > 0 else 0
    
    print(f"  旧文件: {format_size(old_size)}")
    print(f"  旧文件哈希: {old_hash[:16]}...")
    print(f"  新文件: {format_size(new_size)}")
    print(f"  补丁: {format_size(patch_size)}")
    print(f"  节省流量: {ratio:.1f}%")
    
    return patch_size, old_hash


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def update_version_file(version_file: Path, version_info: Dict):
    """
    更新version.json文件
    
    Args:
        version_file: version.json路径
        version_info: 新的版本信息
    """
    # 读取现有的version.json
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {
            'version': '',
            'hash': '',
            'file': '',
            'size': 0,
            'patches': {},
            'release_notes': '',
            'history': []
        }
    
    # 保存旧版本到历史
    if data.get('version'):
        data['history'].append({
            'version': data['version'],
            'hash': data['hash'],
            'file': data['file'],
            'size': data['size']
        })
    
    # 更新当前版本信息
    data['version'] = version_info['version']
    data['hash'] = version_info['hash']
    data['file'] = version_info['file']
    data['size'] = version_info['size']
    data['release_notes'] = version_info.get('release_notes', '')
    
    # 添加补丁信息
    if 'patches' not in data:
        data['patches'] = {}
    
    if version_info.get('patches'):
        data['patches'].update(version_info['patches'])
    
    # 保存
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n版本信息已更新: {version_file}")


def main():
    parser = argparse.ArgumentParser(description='生成差异补丁工具')
    parser.add_argument('new_version', help='新版本号 (如: 2.3.0)')
    parser.add_argument('new_file', help='新版本文件路径')
    parser.add_argument('--output-dir', '-o', default='./updates',
                       help='输出目录 (默认: ./updates)')
    parser.add_argument('--old-versions', '-v', nargs='+',
                       help='旧版本文件路径 (支持多个)')
    parser.add_argument('--release-notes', '-r', default='',
                       help='更新说明')
    
    args = parser.parse_args()
    
    # 准备目录
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理新版本文件
    new_file = Path(args.new_file)
    if not new_file.exists():
        print(f"错误: 新版本文件不存在: {new_file}")
        return 1
    
    new_hash = calculate_hash(new_file)
    new_size = new_file.stat().st_size
    
    print(f"新版本: {args.new_version}")
    print(f"文件: {new_file.name}")
    print(f"大小: {format_size(new_size)}")
    print(f"哈希: {new_hash}")
    print()
    
    # 复制新版本文件到输出目录
    new_file_name = f"XexunRTT_v{args.new_version}.exe"
    new_file_dest = output_dir / new_file_name
    
    import shutil
    shutil.copy2(new_file, new_file_dest)
    print(f"新版本文件已复制到: {new_file_dest}")
    print()
    
    # 生成补丁
    patches = {}
    
    if args.old_versions:
        print("正在生成补丁...")
        print("-" * 60)
        
        for old_version_path in args.old_versions:
            old_file = Path(old_version_path)
            if not old_file.exists():
                print(f"警告: 旧版本文件不存在,跳过: {old_file}")
                continue
            
            # 从文件名提取版本号
            # 假设文件名格式: XexunRTT_v2.2.0.exe
            old_version = old_file.stem.split('_v')[-1]
            
            # 生成补丁文件名
            patch_name = f"patch_{old_version}_to_{args.new_version}.patch"
            patch_file = output_dir / patch_name
            
            # 生成补丁（返回补丁大小和源文件哈希）
            patch_size, old_hash = generate_patch(old_file, new_file, patch_file)
            
            # 记录补丁信息（包含源文件哈希用于完整性验证）
            patch_key = f"{old_version}_{args.new_version}"
            patches[patch_key] = {
                'file': patch_name,
                'size': patch_size,
                'from_version': old_version,
                'to_version': args.new_version,
                'from_hash': old_hash  # 添加源文件哈希，用于完整性验证
            }
            
            print()
    
    # 更新version.json
    version_info = {
        'version': args.new_version,
        'hash': new_hash,
        'file': new_file_name,
        'size': new_size,
        'release_notes': args.release_notes,
        'patches': patches
    }
    
    version_file = output_dir / 'version.json'
    update_version_file(version_file, version_info)
    
    print("\n" + "=" * 60)
    print("完成!")
    print(f"请将 {output_dir} 目录下的所有文件上传到您的HTTP服务器")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    exit(main())

