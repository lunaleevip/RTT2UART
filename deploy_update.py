#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速部署更新工具
自动化生成补丁、上传服务器的完整流程
"""

import os
import sys
import json
import argparse
from pathlib import Path
import subprocess

try:
    from generate_patch import generate_patch, calculate_hash, format_size, update_version_file
except ImportError:
    print("错误: 需要 generate_patch.py 文件")
    sys.exit(1)


def deploy_update(new_version: str, 
                 new_file: Path,
                 old_versions: list,
                 release_notes: str,
                 output_dir: Path,
                 upload_server: str = None,
                 upload_path: str = None):
    """
    完整的部署流程
    
    Args:
        new_version: 新版本号
        new_file: 新版本文件
        old_versions: 旧版本文件列表
        release_notes: 更新说明
        output_dir: 输出目录
        upload_server: 上传服务器地址 (可选)
        upload_path: 服务器上的路径 (可选)
    """
    
    print("=" * 70)
    print("XexunRTT 更新部署工具")
    print("=" * 70)
    print()
    
    # 1. 验证文件
    print("📋 步骤 1/5: 验证文件")
    print("-" * 70)
    
    if not new_file.exists():
        print(f"❌ 错误: 新版本文件不存在: {new_file}")
        return False
    
    print(f"✅ 新版本文件: {new_file.name}")
    print(f"   大小: {format_size(new_file.stat().st_size)}")
    
    valid_old_versions = []
    for old_file in old_versions:
        old_path = Path(old_file)
        if old_path.exists():
            valid_old_versions.append(old_path)
            print(f"✅ 旧版本文件: {old_path.name}")
        else:
            print(f"⚠️  跳过不存在的文件: {old_file}")
    
    if not valid_old_versions:
        print("⚠️  警告: 没有有效的旧版本文件,将只提供完整下载")
    
    print()
    
    # 2. 准备输出目录
    print("📂 步骤 2/5: 准备输出目录")
    print("-" * 70)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 输出目录: {output_dir.absolute()}")
    print()
    
    # 3. 生成补丁
    print("🔧 步骤 3/5: 生成补丁文件")
    print("-" * 70)
    
    import shutil
    
    # 复制新版本文件
    new_file_name = f"XexunRTT_v{new_version}.exe"
    new_file_dest = output_dir / new_file_name
    shutil.copy2(new_file, new_file_dest)
    
    new_hash = calculate_hash(new_file)
    new_size = new_file.stat().st_size
    
    print(f"✅ 新版本已复制: {new_file_dest.name}")
    print(f"   SHA256: {new_hash[:16]}...")
    print()
    
    # 生成补丁
    patches = {}
    
    if valid_old_versions:
        for old_file in valid_old_versions:
            # 提取版本号
            old_version = old_file.stem.split('_v')[-1]
            
            print(f"正在生成补丁: {old_version} → {new_version}")
            
            # 生成补丁文件名
            patch_name = f"patch_{old_version}_to_{new_version}.patch"
            patch_file = output_dir / patch_name
            
            # 生成补丁
            patch_size = generate_patch(old_file, new_file, patch_file)
            
            # 记录信息
            patch_key = f"{old_version}_{new_version}"
            patches[patch_key] = {
                'file': patch_name,
                'size': patch_size,
                'from_version': old_version,
                'to_version': new_version
            }
            
            print()
    
    # 4. 更新 version.json
    print("📝 步骤 4/5: 更新版本信息")
    print("-" * 70)
    
    version_info = {
        'version': new_version,
        'hash': new_hash,
        'file': new_file_name,
        'size': new_size,
        'release_notes': release_notes,
        'patches': patches
    }
    
    version_file = output_dir / 'version.json'
    update_version_file(version_file, version_info)
    print()
    
    # 5. 上传到服务器 (可选)
    if upload_server and upload_path:
        print("🚀 步骤 5/5: 上传到服务器")
        print("-" * 70)
        
        try:
            upload_to_server(output_dir, upload_server, upload_path)
            print("✅ 上传完成")
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            print("   请手动上传文件到服务器")
    else:
        print("📤 步骤 5/5: 手动上传")
        print("-" * 70)
        print(f"请将以下目录的所有文件上传到服务器:")
        print(f"   {output_dir.absolute()}")
        print()
        print("需要上传的文件:")
        for file in output_dir.iterdir():
            if file.is_file():
                print(f"   - {file.name} ({format_size(file.stat().st_size)})")
    
    print()
    print("=" * 70)
    print("✅ 部署准备完成!")
    print("=" * 70)
    print()
    
    # 显示摘要
    print("📊 更新摘要:")
    print(f"   版本: {new_version}")
    print(f"   文件: {new_file_name} ({format_size(new_size)})")
    print(f"   哈希: {new_hash[:32]}...")
    
    if patches:
        print(f"   补丁数量: {len(patches)}")
        total_patch_size = sum(p['size'] for p in patches.values())
        avg_ratio = (1 - total_patch_size / (new_size * len(patches))) * 100
        print(f"   平均节省: {avg_ratio:.1f}%")
    
    print()
    print("📝 更新说明:")
    for line in release_notes.split('\n'):
        print(f"   {line}")
    
    return True


def upload_to_server(local_dir: Path, server: str, remote_path: str):
    """
    上传文件到服务器 (使用 SCP)
    
    Args:
        local_dir: 本地目录
        server: 服务器地址 (user@host)
        remote_path: 远程路径
    """
    
    print(f"正在上传到 {server}:{remote_path}")
    
    # 使用 SCP 上传
    cmd = [
        'scp', '-r',
        f"{local_dir}/*",
        f"{server}:{remote_path}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"SCP failed: {result.stderr}")
    
    print("上传成功")


def interactive_mode():
    """交互式模式"""
    
    print("=" * 70)
    print("XexunRTT 更新部署向导")
    print("=" * 70)
    print()
    
    # 获取新版本信息
    new_version = input("请输入新版本号 (如 2.3.0): ").strip()
    new_file = input("请输入新版本文件路径: ").strip()
    
    # 获取旧版本
    print("\n请输入旧版本文件路径 (每行一个,输入空行结束):")
    old_versions = []
    while True:
        old_file = input(f"旧版本 {len(old_versions) + 1} (或按回车结束): ").strip()
        if not old_file:
            break
        old_versions.append(old_file)
    
    # 获取更新说明
    print("\n请输入更新说明 (输入END结束):")
    release_notes_lines = []
    while True:
        line = input()
        if line.strip().upper() == 'END':
            break
        release_notes_lines.append(line)
    release_notes = '\n'.join(release_notes_lines)
    
    # 输出目录
    output_dir = input("\n输出目录 (默认: ./updates): ").strip()
    if not output_dir:
        output_dir = "./updates"
    
    # 是否上传
    upload = input("\n是否上传到服务器? (y/N): ").strip().lower()
    upload_server = None
    upload_path = None
    
    if upload == 'y':
        upload_server = input("服务器地址 (如 user@host): ").strip()
        upload_path = input("远程路径 (如 /var/www/html/updates): ").strip()
    
    print()
    
    # 执行部署
    return deploy_update(
        new_version=new_version,
        new_file=Path(new_file),
        old_versions=old_versions,
        release_notes=release_notes,
        output_dir=Path(output_dir),
        upload_server=upload_server if upload_server else None,
        upload_path=upload_path if upload_path else None
    )


def main():
    parser = argparse.ArgumentParser(
        description='XexunRTT 更新部署工具',
        epilog='如果不提供参数,将进入交互式模式'
    )
    
    parser.add_argument('--new-version', '-v', help='新版本号')
    parser.add_argument('--new-file', '-n', help='新版本文件路径')
    parser.add_argument('--old-versions', '-o', nargs='+', help='旧版本文件路径')
    parser.add_argument('--release-notes', '-r', default='', help='更新说明')
    parser.add_argument('--output-dir', '-d', default='./updates', help='输出目录')
    parser.add_argument('--upload-server', '-s', help='上传服务器 (user@host)')
    parser.add_argument('--upload-path', '-p', help='服务器路径')
    parser.add_argument('--interactive', '-i', action='store_true', help='交互式模式')
    
    args = parser.parse_args()
    
    # 如果没有必需参数,进入交互模式
    if args.interactive or not (args.new_version and args.new_file):
        success = interactive_mode()
    else:
        success = deploy_update(
            new_version=args.new_version,
            new_file=Path(args.new_file),
            old_versions=args.old_versions or [],
            release_notes=args.release_notes,
            output_dir=Path(args.output_dir),
            upload_server=args.upload_server,
            upload_path=args.upload_path
        )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

