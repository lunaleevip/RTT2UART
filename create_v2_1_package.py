#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建XexunRTT v2.1.0发布包
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

def create_release_package():
    """创建v2.1.0发布包"""
    
    # 检查构建文件是否存在
    if not os.path.exists('dist_v2_1/XexunRTT_v2.1.exe'):
        print("❌ 未找到构建的EXE文件")
        return False
    
    # 创建发布包目录名
    today = datetime.now().strftime('%Y%m%d')
    release_dir = f'XexunRTT_v2.1.0_日志拆分功能版_{today}'
    
    # 清理并创建发布目录
    if os.path.exists(release_dir):
        shutil.rmtree(release_dir)
    os.makedirs(release_dir)
    
    print(f"📁 创建发布目录: {release_dir}")
    
    # 要复制的文件列表
    files_to_copy = [
        ('dist_v2_1/XexunRTT_v2.1.exe', 'XexunRTT_v2.1.0.exe'),
        ('dist_v2_1/config.ini', 'config.ini'),
        ('dist_v2_1/cmd.txt', 'cmd.txt'),
        ('dist_v2_1/v2.1功能说明.md', 'v2.1.0功能说明.md'),
    ]
    
    # 复制文件
    for src, dst in files_to_copy:
        if os.path.exists(src):
            dst_path = os.path.join(release_dir, dst)
            shutil.copy2(src, dst_path)
            print(f"📋 复制文件: {dst}")
        else:
            print(f"⚠️ 文件不存在: {src}")
    
    # 创建使用说明文件
    usage_content = """# XexunRTT v2.1.0 使用说明

## 版本信息
- 版本: v2.1.0
- 发布日期: """ + datetime.now().strftime('%Y-%m-%d') + """
- 特性: 日志拆分功能

## 快速开始
1. 双击 `XexunRTT_v2.1.0.exe` 启动程序
2. 在主界面找到"日志拆分"复选框
3. 根据需要勾选或取消勾选该功能

## 新功能说明
### 日志拆分功能
- **勾选时**: 每次连接都会创建新的时间戳目录来保存日志
- **不勾选时**: 延续使用上次的日志目录
- **默认状态**: 开启（推荐）

### 使用场景
- 多次调试时需要分别保存日志
- 需要按时间整理调试记录
- 避免日志文件混乱

## 文件说明
- `XexunRTT_v2.1.0.exe`: 主程序文件
- `config.ini`: 配置文件（程序首次运行时会自动创建）
- `cmd.txt`: 命令配置文件
- `v2.1.0功能说明.md`: 详细功能说明

## 技术支持
如有问题请参考详细功能说明文档。
"""
    
    usage_file = os.path.join(release_dir, '使用说明.txt')
    with open(usage_file, 'w', encoding='utf-8') as f:
        f.write(usage_content)
    print("📄 创建使用说明: 使用说明.txt")
    
    # 创建ZIP发布包
    zip_filename = f'{release_dir}.zip'
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(release_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # 使用相对路径作为压缩包内的路径
                arcname = os.path.relpath(file_path, release_dir)
                zipf.write(file_path, arcname)
                print(f"📦 打包: {arcname}")
    
    print(f"\n🎉 发布包创建完成!")
    print(f"📁 发布目录: {release_dir}")
    print(f"📦 ZIP文件: {zip_filename}")
    
    # 显示文件大小信息
    zip_size = os.path.getsize(zip_filename) / (1024 * 1024)
    exe_size = os.path.getsize(os.path.join(release_dir, 'XexunRTT_v2.1.0.exe')) / (1024 * 1024)
    print(f"📏 EXE大小: {exe_size:.1f} MB")
    print(f"📏 ZIP大小: {zip_size:.1f} MB")
    
    return True

if __name__ == '__main__':
    print("📦 XexunRTT v2.1.0 发布包创建工具")
    print("=" * 50)
    
    if create_release_package():
        print("\n✅ 发布包创建成功!")
    else:
        print("\n❌ 发布包创建失败!")
