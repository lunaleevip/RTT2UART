#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT macOS 构建启动器
自动检测环境并选择最佳构建方式
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

def detect_environment():
    """检测当前运行环境"""
    system = platform.system()
    machine = platform.machine()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    return {
        'system': system,
        'machine': machine,
        'python_version': python_version,
        'is_macos': system == 'Darwin',
        'is_windows': system == 'Windows',
        'is_linux': system == 'Linux'
    }

def check_build_scripts():
    """检查构建脚本是否存在"""
    scripts = {
        'native_macos': Path('build_macos.py'),
        'cross_platform': Path('build_cross_platform.py'),
        'complete_macos': Path('build_macos_complete.py'),
        'main_window': Path('main_window.py'),
        'requirements': Path('requirements.txt')
    }
    
    status = {}
    for name, path in scripts.items():
        status[name] = path.exists()
    
    return status

def show_environment_info(env):
    """显示环境信息"""
    print("🔍 当前环境信息")
    print("-" * 30)
    print(f"操作系统: {env['system']} ({env['machine']})")
    print(f"Python 版本: {env['python_version']}")
    
    if env['is_macos']:
        macos_version = platform.mac_ver()[0]
        print(f"macOS 版本: {macos_version}")
    
    print()

def show_build_options(env, scripts):
    """显示构建选项"""
    print("🍎 macOS 构建选项")
    print("=" * 40)
    
    if env['is_macos'] and scripts['native_macos']:
        print("✅ 选项 1：原生 macOS 构建（推荐）")
        print("   - 在 macOS 上运行")
        print("   - 生成完整的 .app 应用程序包")
        print("   - 自动创建 DMG 安装包")
        print("   - 最佳兼容性和性能")
        print()
    
    if scripts['cross_platform']:
        print("🌍 选项 2：跨平台构建")
        print(f"   - 在 {env['system']} 上运行")
        print("   - 生成可在 macOS 上运行的文件")
        print("   - 需要在 macOS 上进行最终打包")
        print("   - 适合没有 macOS 环境的开发者")
        print()
    
    if scripts['complete_macos']:
        print("📦 选项 3：完整 macOS 包构建（推荐）")
        print(f"   - 在 {env['system']} 上运行")
        print("   - 生成90%完整的 .app 应用程序包")
        print("   - 包含完整的目录结构和元数据")
        print("   - 只需在 macOS 上运行最终化脚本")
        print("   - 最接近原生构建的效果")
        print()
    
    print("❌ 选项 4：退出")
    print()

def run_native_build():
    """执行原生 macOS 构建"""
    print("🚀 启动原生 macOS 构建...")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, 'build_macos.py'], check=True)
        print("\n✅ 原生构建完成！")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 原生构建失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 构建过程中出现错误：{e}")
        return False

def run_cross_build():
    """执行跨平台构建"""
    print("🌍 启动跨平台构建...")
    print("=" * 50)
    
    try:
        result = subprocess.run([sys.executable, 'build_cross_platform.py'], check=True)
        print("\n✅ 跨平台构建完成！")
        print("\n📋 下一步操作：")
        print("1. 将 dist_macos/ 目录传输到 macOS 系统")
        print("2. 将 package_macos.sh 脚本传输到 macOS 系统")
        print("3. 在 macOS 上运行：./package_macos.sh")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 跨平台构建失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 构建过程中出现错误：{e}")
        return False

def run_complete_build():
    """执行完整 macOS 包构建"""
    print("📦 启动完整 macOS 包构建...")
    print("=" * 50)
    
    try:
        # 首先确保有跨平台构建输出
        if not Path('dist_macos/XexunRTT').exists():
            print("🔄 先执行跨平台构建...")
            cross_result = subprocess.run([sys.executable, 'build_cross_platform.py'], check=True)
        
        # 然后执行完整包构建
        result = subprocess.run([sys.executable, 'build_macos_complete.py'], check=True)
        print("\n✅ 完整 macOS 包构建完成！")
        print("\n📋 下一步操作：")
        print("1. 将 XexunRTT_macOS_Package/ 目录传输到 macOS 系统")
        print("2. 在 macOS 上运行：./finalize_macos_app.sh")
        print("3. 享受完整的 XexunRTT.app 应用程序！")
        print("\n✨ 优势：")
        print("  - 90% 的工作在 Windows 上完成")
        print("  - 包含完整的 .app 目录结构")
        print("  - 自动化的最终化脚本")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 完整构建失败：{e}")
        return False
    except Exception as e:
        print(f"\n❌ 构建过程中出现错误：{e}")
        return False

def show_usage_guide():
    """显示使用指南"""
    print("\n📚 使用指南")
    print("=" * 40)
    print("1. 构建完成后，检查生成的文件：")
    print("   - 原生构建：dist/XexunRTT.app")
    print("   - 跨平台构建：dist_macos/XexunRTT/")
    print()
    print("2. 安装 J-Link 驱动：")
    print("   - 访问 SEGGER 官网下载 J-Link Software Pack")
    print("   - 安装适合 macOS 的版本")
    print()
    print("3. 首次运行：")
    print("   - 右键点击应用程序选择'打开'")
    print("   - 或在系统偏好设置中允许运行")
    print()
    print("4. 技术支持：")
    print("   - 查看 README_macOS.md 或 macOS_Build_Guide.md")
    print("   - GitHub Issues: https://github.com/xexun/RTT2UART")

def main():
    """主函数"""
    print("🍎 XexunRTT macOS 构建启动器")
    print("=" * 50)
    
    # 检测环境
    env = detect_environment()
    show_environment_info(env)
    
    # 检查构建脚本
    scripts = check_build_scripts()
    
    # 检查必要文件
    if not scripts['main_window']:
        print("❌ 错误：未找到 main_window.py")
        print("💡 请确保在 RTT2UART 项目根目录中运行此脚本")
        return False
    
    while True:
        # 显示构建选项
        show_build_options(env, scripts)
        
        # 获取用户选择
        try:
            if env['is_macos'] and scripts['native_macos']:
                choice = input("请选择构建方式 (1-4): ").strip()
            else:
                choice = input("请选择构建方式 (2-4): ").strip()
        except KeyboardInterrupt:
            print("\n👋 已取消构建")
            return False
        
        # 处理选择
        if choice == '1' and env['is_macos'] and scripts['native_macos']:
            success = run_native_build()
            if success:
                show_usage_guide()
            return success
            
        elif choice == '2' and scripts['cross_platform']:
            success = run_cross_build()
            if success:
                show_usage_guide()
            return success
            
        elif choice == '3' and scripts['complete_macos']:
            success = run_complete_build()
            if success:
                show_usage_guide()
            return success
            
        elif choice == '4':
            print("👋 已退出构建")
            return True
            
        else:
            print("❌ 无效选择，请重新输入")
            continue

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 构建被用户取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 启动器出现错误：{e}")
        sys.exit(1)
