#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能更新部署工具 - 自动识别版本并生成补丁

使用方法:
    python deploy_update.py dist/XexunRTT_v2.5.exe
    或
    python deploy_update.py dist/XexunRTT_v2.5.exe --notes "修复Bug"
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
import shutil
import hashlib
import datetime

try:
    import bsdiff4
    BSDIFF_AVAILABLE = True
except ImportError:
    BSDIFF_AVAILABLE = False
    print("⚠️  警告: bsdiff4 未安装，无法生成补丁（仅提供完整更新）")
    print("   安装: pip install bsdiff4")


def calculate_hash(file_path: Path) -> str:
    """计算文件SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def extract_version_from_filename(filename: str) -> str:
    """
    从文件名提取版本号
    
    支持格式:
        XexunRTT_v2.4.exe → 2.4
        XexunRTT_v2.5.1.exe → 2.5.1
        XexunRTT_v3.3.4.1.exe → 3.3.4.1
        XexunRTT_2.4.exe → 2.4
    """
    patterns = [
        r'[vV](\d+\.\d+(?:\.\d+){0,2})',  # v2.4 / v2.5.1 / v3.3.4.1
        r'_(\d+\.\d+(?:\.\d+){0,2})',      # _2.4 / _2.5.1 / _3.3.4.1
        r'(\d+\.\d+(?:\.\d+){0,2})',       # 2.4 / 2.5.1 / 3.3.4.1
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
    
    return None


def generate_patch(old_file: Path, new_file: Path, patch_file: Path) -> tuple:
    """
    生成补丁文件
    
    Returns:
        (patch_size, old_hash, should_use_full_update)
    """
    if not BSDIFF_AVAILABLE:
        raise ImportError("bsdiff4 not available")
    
    # 读取文件
    with open(old_file, 'rb') as f:
        old_data = f.read()
    
    with open(new_file, 'rb') as f:
        new_data = f.read()
    
    # 计算旧文件哈希
    old_hash = hashlib.sha256(old_data).hexdigest()
    
    # 计算文件大小
    old_size = len(old_data)
    new_size = len(new_data)
    
    # 生成补丁
    patch_data = bsdiff4.diff(old_data, new_data)
    patch_size = len(patch_data)
    
    # 检查补丁效率：如果补丁大小超过新文件的60%，建议使用完整更新
    # 对于PyInstaller打包的EXE，bsdiff4效率可能较低
    patch_ratio = patch_size / new_size if new_size > 0 else 1.0
    should_use_full_update = patch_ratio > 0.6
    
    # 保存补丁
    with open(patch_file, 'wb') as f:
        f.write(patch_data)
    
    return len(patch_data), old_hash, should_use_full_update


def load_version_json(version_file: Path) -> dict:
    """加载现有的 version.json"""
    if version_file.exists():
        with open(version_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'version': '0.0',
        'hash': '',
        'file': '',
        'size': 0,
        'patches': {},
        'release_notes': '',
        'history': []
    }


def save_version_json(version_file: Path, data: dict):
    """保存 version.json"""
    with open(version_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def deploy_update(new_file: Path, 
                 release_notes: str = None,
                 output_dir: Path = None,
                 max_patches: int = 10,
                 skip_inefficient_patches: bool = False,
                 patch_efficiency_threshold: float = 0.6) -> bool:
    """
    智能部署更新
    
    Args:
        new_file: 新版本文件 (如 dist/XexunRTT_v2.5.exe)
        release_notes: 更新说明（可选）
        output_dir: 输出目录（默认: updates）
        max_patches: 最多保留多少个版本的补丁（默认: 3）
    """
    
    print("=" * 70)
    print("🚀 XexunRTT 智能更新部署工具")
    print("=" * 70)
    print()
    
    # ========== 步骤 1: 验证和提取版本 ==========
    print("📋 步骤 1/6: 验证文件并提取版本")
    print("-" * 70)
    
    if not new_file.exists():
        print(f"❌ 错误: 文件不存在: {new_file}")
        return False
    
    # 从文件名提取版本号
    new_version = extract_version_from_filename(new_file.name)
    if not new_version:
        print(f"❌ 错误: 无法从文件名提取版本号: {new_file.name}")
        print("   文件名应类似: XexunRTT_v2.5.exe 或 XexunRTT_2.5.exe")
        return False
    
    print(f"✅ 新版本文件: {new_file.name}")
    print(f"   版本号: v{new_version}")
    print(f"   大小: {format_size(new_file.stat().st_size)}")
    print()
    
    # ========== 步骤 2: 准备输出目录 ==========
    print("📂 步骤 2/6: 准备输出目录")
    print("-" * 70)
    
    if output_dir is None:
        output_dir = Path('updates')
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 输出目录: {output_dir.absolute()}")
    print()
    
    # ========== 步骤 3: 读取现有 version.json ==========
    print("📝 步骤 3/6: 读取现有版本信息")
    print("-" * 70)
    
    version_file = output_dir / 'version.json'
    version_data = load_version_json(version_file)
    
    old_version = version_data.get('version', '0.0')
    old_file_name = version_data.get('file', '')
    old_hash = version_data.get('hash', '')
    
    print(f"   当前版本: v{old_version}")
    if old_file_name:
        print(f"   当前文件: {old_file_name}")
        print(f"   当前哈希: {old_hash[:16]}...")
    else:
        print("   ⚠️  这是首次部署")
    print()
    
    # ========== 步骤 4: 计算新版本信息 ==========
    print("🔍 步骤 4/6: 计算新版本信息")
    print("-" * 70)
    
    new_hash = calculate_hash(new_file)
    new_size = new_file.stat().st_size
    new_file_name = f"XexunRTT_v{new_version}.exe"
    
    print(f"   SHA256: {new_hash}")
    print(f"   大小: {format_size(new_size)}")
    print()
    
    # 检查是否与当前版本相同
    if old_version == new_version and old_hash == new_hash:
        print("⚠️  警告: 新版本与当前版本完全相同（版本号和哈希都一致）")
        print("   跳过部署")
        return False
    
    # ========== 步骤 5: 复制新版本文件 ==========
    print("📦 步骤 5/6: 复制新版本文件")
    print("-" * 70)
    
    new_file_dest = output_dir / new_file_name
    shutil.copy2(new_file, new_file_dest)
    print(f"✅ 已复制: {new_file_name}")
    print()
    
    # ========== 步骤 6: 生成补丁 ==========
    print("🔧 步骤 6/6: 生成补丁文件")
    print("-" * 70)
    
    patches = version_data.get('patches', {})
    history = version_data.get('history', [])
    
    # 🔑 生成最近10个版本到最新版本的补丁
    if BSDIFF_AVAILABLE:
        # 收集所有可用的历史版本
        available_versions = []
        
        # 添加当前旧版本（如果存在）
        if old_file_name and old_version != new_version and old_version != '0.0':
            old_file_path = output_dir / old_file_name
            if old_file_path.exists():
                available_versions.append({
                    'version': old_version,
                    'file': old_file_path,
                    'hash': old_hash
                })
        
        # 从历史记录中查找其他版本
        for hist in history:
            hist_version = hist.get('version')
            if hist_version and hist_version != new_version:
                # 尝试查找历史版本的文件
                # 可能的文件名格式
                possible_names = [
                    f"XexunRTT_v{hist_version}.exe",
                    f"XexunRTT_{hist_version}.exe",
                    f"XexunRTT_v{hist_version}_win.exe"
                ]
                
                for name in possible_names:
                    hist_file = output_dir / name
                    if hist_file.exists():
                        # 检查是否已经添加
                        if not any(v['version'] == hist_version for v in available_versions):
                            available_versions.append({
                                'version': hist_version,
                                'file': hist_file,
                                'hash': hist.get('hash', calculate_hash(hist_file))
                            })
                        break
        
        # 按版本号排序，保留最近10个
        available_versions.sort(key=lambda x: x['version'], reverse=True)
        available_versions = available_versions[:10]
        
        if available_versions:
            print(f"找到 {len(available_versions)} 个历史版本，生成补丁到 v{new_version}")
            print()
            
            patch_count = 0
            for ver_info in available_versions:
                ver = ver_info['version']
                ver_file = ver_info['file']
                ver_hash = ver_info['hash']
                
                print(f"正在生成补丁: v{ver} → v{new_version}")
                
                try:
                    # 生成补丁文件名
                    patch_name = f"patch_{ver}_to_{new_version}.patch"
                    patch_file = output_dir / patch_name
                    
                    # 生成补丁
                    patch_size, old_file_hash, should_use_full_update = generate_patch(ver_file, new_file, patch_file)
                    
                    # 计算节省比例
                    save_ratio = (1 - patch_size / new_size) * 100
                    patch_ratio = (patch_size / new_size) * 100 if new_size > 0 else 0
                    
                    print(f"   ✅ 补丁大小: {format_size(patch_size)}")
                    print(f"   💰 节省流量: {save_ratio:.1f}%")
                    print(f"   📄 补丁文件: {patch_name}")
                    
                    # 检查补丁效率阈值（使用传入的阈值，而不是固定的0.6）
                    is_inefficient = patch_ratio > patch_efficiency_threshold
                    
                    # 如果补丁效率低，给出警告
                    if is_inefficient:
                        print(f"   ⚠️  警告: 补丁大小占新文件的 {patch_ratio:.1f}%，效率较低")
                        if skip_inefficient_patches:
                            print(f"   🚫 跳过此补丁（已启用跳过低效率补丁选项）")
                            # 删除已生成的补丁文件
                            if patch_file.exists():
                                patch_file.unlink()
                            continue
                        else:
                            print(f"   💡 建议: 对于此版本更新，使用完整文件更新可能更合适")
                            print(f"   💡 提示: 使用 --skip-inefficient 参数可自动跳过低效率补丁")
                    elif patch_ratio > 0.4:
                        print(f"   ⚠️  注意: 补丁大小占新文件的 {patch_ratio:.1f}%，可能由于PyInstaller打包结构导致")
                    
                    # 记录补丁信息（即使效率低也记录，让用户选择）
                    patch_key = f"{ver}_{new_version}"
                    patches[patch_key] = {
                        'file': patch_name,
                        'size': patch_size,
                        'from_version': ver,
                        'to_version': new_version,
                        'from_hash': old_file_hash,
                        'efficiency_warning': is_inefficient  # 标记效率警告
                    }
                    
                    patch_count += 1
                    
                except Exception as e:
                    print(f"   ⚠️  补丁生成失败: {e}")
                
                print()
            
            print(f"✅ 成功生成 {patch_count} 个补丁文件")
        else:
            print("   ℹ️  首次部署或无历史版本文件，无需生成补丁")
    else:
        print("   ⚠️  跳过补丁生成 (bsdiff4 未安装)")
    
    print()
    
    # ========== 清理旧补丁 ==========
    # 保留最近 max_patches 个版本的补丁
    if len(patches) > max_patches:
        print(f"🧹 清理旧补丁 (保留最近 {max_patches} 个)")
        print("-" * 70)
        
        # 按版本排序
        sorted_patches = sorted(patches.items(), key=lambda x: x[1]['to_version'], reverse=True)
        patches_to_keep = dict(sorted_patches[:max_patches])
        patches_to_remove = dict(sorted_patches[max_patches:])
        
        for patch_key, patch_info in patches_to_remove.items():
            patch_file = output_dir / patch_info['file']
            if patch_file.exists():
                patch_file.unlink()
                print(f"   🗑️  删除: {patch_info['file']}")
        
        patches = patches_to_keep
        print()
    
    # ========== 更新历史记录 ==========
    # 将当前版本加入历史
    if old_version != '0.0' and old_version != new_version:
        history.append({
            'version': old_version,
            'hash': old_hash,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
        # 只保留最近 10 个历史版本
        if len(history) > 10:
            history = history[-10:]
    
    # ========== 生成更新说明 ==========
    if release_notes is None:
        release_notes = f"XexunRTT v{new_version} 更新"
    
    # ========== 更新 version.json ==========
    print("📝 更新版本配置文件")
    print("-" * 70)
    
    version_data = {
        'version': new_version,
        'hash': new_hash,
        'file': new_file_name,
        'size': new_size,
        'release_notes': release_notes,
        'patches': patches,
        'history': history
    }
    
    save_version_json(version_file, version_data)
    print(f"✅ 已更新: {version_file.name}")
    print()
    
    # ========== 显示摘要 ==========
    print("=" * 70)
    print("✅ 部署完成!")
    print("=" * 70)
    print()
    
    print("📊 部署摘要:")
    print(f"   版本: v{new_version}")
    print(f"   文件: {new_file_name} ({format_size(new_size)})")
    print(f"   哈希: {new_hash[:32]}...")
    
    if patches:
        print(f"   补丁数量: {len(patches)}")
        total_patch_size = sum(p['size'] for p in patches.values())
        if len(patches) > 0:
            avg_patch_size = total_patch_size / len(patches)
            avg_ratio = (1 - avg_patch_size / new_size) * 100
            print(f"   平均补丁大小: {format_size(avg_patch_size)}")
            print(f"   平均节省流量: {avg_ratio:.1f}%")
    
    print()
    print("📝 更新说明:")
    for line in release_notes.split('\n'):
        print(f"   {line}")
    
    print()
    print("📂 需要上传到服务器的文件:")
    print(f"   目录: {output_dir.absolute()}")
    print()
    
    # 列出所有需要上传的文件
    files_to_upload = []
    for file in output_dir.iterdir():
        if file.is_file():
            files_to_upload.append(file)
            print(f"   ✅ {file.name} ({format_size(file.stat().st_size)})")
    
    print()
    print("💡 提示:")
    print(f"   将以上文件上传到服务器的更新目录")
    print(f"   服务器 URL 配置在 auto_updater.py 中")
    print()
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='XexunRTT 智能更新部署工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用示例:
  # 部署新版本 (自动识别版本号)
  python deploy_update.py dist/XexunRTT_v2.5.exe
  
  # 指定更新说明
  python deploy_update.py dist/XexunRTT_v2.5.exe --notes "修复Bug"
  
  # 指定输出目录
  python deploy_update.py dist/XexunRTT_v2.5.exe --output updates
  
  # 自定义保留补丁数量
  python deploy_update.py dist/XexunRTT_v2.5.exe --max-patches 5

注意:
  - 文件名必须包含版本号，如: XexunRTT_v2.5.exe
  - 会自动从 updates/version.json 读取历史版本并生成补丁
  - 补丁文件会自动生成并保存到输出目录
        '''
    )
    
    parser.add_argument('new_file', 
                       help='新版本文件路径 (如 dist/XexunRTT_v2.5.exe)')
    parser.add_argument('--notes', '-n', 
                       help='更新说明')
    parser.add_argument('--output', '-o', 
                       default='updates',
                       help='输出目录 (默认: updates)')
    parser.add_argument('--max-patches', '-m', 
                       type=int, 
                       default=3,
                       help='最多保留的补丁数量 (默认: 3)')
    parser.add_argument('--skip-inefficient', '-s',
                       action='store_true',
                       help='跳过低效率补丁（补丁大小超过新文件60%%时）')
    parser.add_argument('--patch-threshold', '-t',
                       type=float,
                       default=0.6,
                       help='补丁效率阈值，超过此比例视为低效率 (默认: 0.6，即60%%)')
    
    args = parser.parse_args()
    
    # 执行部署
    success = deploy_update(
        new_file=Path(args.new_file),
        release_notes=args.notes,
        output_dir=Path(args.output),
        max_patches=args.max_patches,
        skip_inefficient_patches=args.skip_inefficient,
        patch_efficiency_threshold=args.patch_threshold
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
