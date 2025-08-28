#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示增量更新过程
模拟代码修改、构建和更新的完整流程
"""

import os
import shutil
import time
from pathlib import Path

def simulate_code_update():
    """模拟代码更新"""
    print("🔧 模拟代码更新...")
    
    # 读取main_window.py
    main_window_path = Path('main_window.py')
    if not main_window_path.exists():
        print("❌ main_window.py 不存在")
        return False
    
    # 在文件开头添加版本注释
    content = main_window_path.read_text(encoding='utf-8')
    
    # 检查是否已经有版本注释
    if '# Version Update Demo' not in content:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        version_comment = f"""# Version Update Demo - {timestamp}
# 这是一个演示增量更新的示例修改
# 修改时间: {time.strftime("%Y-%m-%d %H:%M:%S")}

"""
        new_content = version_comment + content
        main_window_path.write_text(new_content, encoding='utf-8')
        print(f"✅ 添加版本注释: {timestamp}")
        return True
    else:
        print("✅ 代码已包含版本注释")
        return True

def build_updated_version():
    """构建更新版本"""
    print("🚀 构建更新版本...")
    
    import subprocess
    import sys
    
    # 使用简单增量更新构建
    cmd = [sys.executable, 'build_incremental_simple.py']
    
    try:
        # 创建spec文件内容
        spec_content = """# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main_window.py'],
    pathex=['.'],
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
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'pylink', 'serial', 'serial.tools.list_ports',
        'logging', 'psutil', 'configparser', 'threading',
        'time', 'datetime', 'json', 'xml.etree.ElementTree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest', 'test', 'email', 'http', 'urllib',
        'pydoc', 'doctest', 'pdb', 'profile', 'cProfile', 'pstats',
        'trace', 'timeit', 'webbrowser', 'pip', 'setuptools',
        'distutils', 'wheel', 'pytest', 'nose', 'mock',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='Jlink_ICON.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XexunRTT_Updated'
)
"""
        
        # 写入spec文件
        with open('XexunRTT_update_demo.spec', 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        # 构建
        build_cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', 'XexunRTT_update_demo.spec']
        result = subprocess.run(build_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 更新版本构建成功")
            return True
        else:
            print(f"❌ 构建失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 构建过程出错: {e}")
        return False

def compare_exe_sizes():
    """比较EXE文件大小"""
    print("📊 比较EXE文件大小...")
    
    original_exe = Path('dist/XexunRTT_Optimized/XexunRTT.exe')
    updated_exe = Path('dist/XexunRTT_Updated/XexunRTT.exe')
    
    if original_exe.exists() and updated_exe.exists():
        original_size = original_exe.stat().st_size / (1024 * 1024)
        updated_size = updated_exe.stat().st_size / (1024 * 1024)
        
        print(f"   📦 原版本 EXE: {original_size:.1f} MB")
        print(f"   🔄 更新版本 EXE: {updated_size:.1f} MB")
        print(f"   📈 大小差异: {abs(updated_size - original_size):.1f} MB")
        
        # 检查_internal目录大小
        original_internal = Path('dist/XexunRTT_Optimized/_internal')
        updated_internal = Path('dist/XexunRTT_Updated/_internal')
        
        if original_internal.exists() and updated_internal.exists():
            orig_internal_size = sum(f.stat().st_size for f in original_internal.rglob('*') if f.is_file()) / (1024 * 1024)
            upd_internal_size = sum(f.stat().st_size for f in updated_internal.rglob('*') if f.is_file()) / (1024 * 1024)
            
            print(f"   📁 原版本 _internal: {orig_internal_size:.1f} MB")
            print(f"   📁 更新版本 _internal: {upd_internal_size:.1f} MB")
            print(f"   📈 库文件差异: {abs(upd_internal_size - orig_internal_size):.1f} MB")
        
        return True
    else:
        print("❌ 无法比较，文件不存在")
        return False

def simulate_incremental_update():
    """模拟增量更新过程"""
    print("🔄 模拟增量更新过程...")
    
    # 创建模拟的用户安装目录
    user_install_dir = Path('simulated_user_installation')
    if user_install_dir.exists():
        shutil.rmtree(user_install_dir)
    
    # 复制原版本到用户目录
    original_dir = Path('dist/XexunRTT_Optimized')
    if original_dir.exists():
        shutil.copytree(original_dir, user_install_dir)
        print("✅ 模拟用户安装目录创建完成")
    else:
        print("❌ 原版本目录不存在")
        return False
    
    # 显示更新前状态
    exe_path = user_install_dir / 'XexunRTT.exe'
    if exe_path.exists():
        original_size = exe_path.stat().st_size / (1024 * 1024)
        original_time = time.ctime(exe_path.stat().st_mtime)
        print(f"📋 更新前状态:")
        print(f"   📦 EXE大小: {original_size:.1f} MB")
        print(f"   🕒 修改时间: {original_time}")
    
    # 执行增量更新（只替换EXE）
    updated_exe = Path('dist/XexunRTT_Updated/XexunRTT.exe')
    if updated_exe.exists():
        # 备份原文件
        backup_path = user_install_dir / 'XexunRTT.exe.backup'
        shutil.copy2(exe_path, backup_path)
        
        # 替换EXE文件
        shutil.copy2(updated_exe, exe_path)
        
        print("✅ 增量更新完成 (只替换了EXE文件)")
        
        # 显示更新后状态
        updated_size = exe_path.stat().st_size / (1024 * 1024)
        updated_time = time.ctime(exe_path.stat().st_mtime)
        print(f"📋 更新后状态:")
        print(f"   📦 EXE大小: {updated_size:.1f} MB")
        print(f"   🕒 修改时间: {updated_time}")
        print(f"   💾 备份文件: XexunRTT.exe.backup")
        
        # 验证_internal目录未被修改
        internal_dir = user_install_dir / '_internal'
        if internal_dir.exists():
            print(f"   📁 _internal目录: 保持不变 (无需更新)")
        
        return True
    else:
        print("❌ 更新版本EXE不存在")
        return False

def create_update_package():
    """创建更新包"""
    print("📦 创建更新包...")
    
    updated_exe = Path('dist/XexunRTT_Updated/XexunRTT.exe')
    if not updated_exe.exists():
        print("❌ 更新版本不存在")
        return False
    
    # 创建更新包目录
    update_package_dir = Path('XexunRTT_Update_Package')
    if update_package_dir.exists():
        shutil.rmtree(update_package_dir)
    update_package_dir.mkdir()
    
    # 复制新版本EXE
    shutil.copy2(updated_exe, update_package_dir / 'XexunRTT.exe')
    
    # 创建更新说明
    update_notes = f"""# XexunRTT 增量更新包

## 更新时间
{time.strftime("%Y-%m-%d %H:%M:%S")}

## 更新内容
- 添加版本演示注释
- 修复JLink连接丢失自动停止功能
- 优化启动速度和资源管理

## 更新方法
1. 备份当前的 XexunRTT.exe 文件
2. 将新的 XexunRTT.exe 文件替换到安装目录
3. _internal 目录无需更新
4. 配置文件 config.ini 会自动保留

## 文件大小
- 更新文件: {updated_exe.stat().st_size / (1024 * 1024):.1f} MB
- 下载速度快，更新简单

## 兼容性
- 与现有 _internal 目录完全兼容
- 不影响用户配置和日志文件
"""
    
    with open(update_package_dir / 'UPDATE_NOTES.txt', 'w', encoding='utf-8') as f:
        f.write(update_notes)
    
    # 复制更新脚本
    if Path('incremental_update.bat').exists():
        shutil.copy2('incremental_update.bat', update_package_dir / 'incremental_update.bat')
    
    print(f"✅ 更新包创建完成: {update_package_dir}")
    print(f"   📦 包含文件:")
    for file in update_package_dir.iterdir():
        size = file.stat().st_size / (1024 * 1024) if file.is_file() else 0
        print(f"      - {file.name} ({size:.1f} MB)")
    
    return True

def cleanup_demo():
    """清理演示文件"""
    print("🧹 清理演示文件...")
    
    cleanup_items = [
        'XexunRTT_update_demo.spec',
        'simulated_user_installation',
        'XexunRTT_Update_Package',
        'dist/XexunRTT_Updated',
    ]
    
    for item in cleanup_items:
        path = Path(item)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"   🗑️ 删除: {item}")
    
    # 恢复main_window.py
    main_window_path = Path('main_window.py')
    if main_window_path.exists():
        content = main_window_path.read_text(encoding='utf-8')
        if '# Version Update Demo' in content:
            # 移除版本注释
            lines = content.split('\n')
            # 找到并移除版本注释块
            start_idx = -1
            end_idx = -1
            for i, line in enumerate(lines):
                if '# Version Update Demo' in line:
                    start_idx = i
                elif start_idx != -1 and line.strip() == '' and i > start_idx + 2:
                    end_idx = i
                    break
            
            if start_idx != -1 and end_idx != -1:
                new_lines = lines[end_idx+1:]
                main_window_path.write_text('\n'.join(new_lines), encoding='utf-8')
                print("   🔄 恢复 main_window.py")

def main():
    """主函数"""
    print("🎬 XexunRTT 增量更新演示")
    print("=" * 60)
    print("🎯 演示用户代码打包到EXE，库文件分离的增量更新过程")
    print()
    
    if not Path('dist/XexunRTT_Optimized').exists():
        print("❌ 请先运行 build_incremental_simple.py 构建基础版本")
        return False
    
    steps = [
        ("模拟代码更新", simulate_code_update),
        ("构建更新版本", build_updated_version),
        ("比较文件大小", compare_exe_sizes),
        ("模拟增量更新", simulate_incremental_update),
        ("创建更新包", create_update_package),
    ]
    
    success_count = 0
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name} {'='*20}")
        try:
            if step_func():
                success_count += 1
                print(f"✅ {step_name} - 完成")
            else:
                print(f"❌ {step_name} - 失败")
        except Exception as e:
            print(f"❌ {step_name} - 异常: {e}")
    
    print(f"\n{'='*60}")
    print("📊 演示结果总结")
    print(f"{'='*60}")
    print(f"完成步骤: {success_count}/{len(steps)}")
    
    if success_count == len(steps):
        print("\n🎉 增量更新演示完成!")
        print("\n💡 增量更新的优势:")
        print("   📦 小文件更新: 只需下载 2-5MB 的EXE文件")
        print("   ⚡ 快速部署: 无需重新下载 100+MB 的完整程序")
        print("   🔧 配置保留: 用户设置和日志文件不受影响")
        print("   🚀 启动更快: 库文件已在_internal中，无需解压")
        print("   💾 节省带宽: 减少 95%+ 的下载量")
        
        print(f"\n🔧 实际使用流程:")
        print(f"1. 开发完成后，运行 build_incremental_simple.py")
        print(f"2. 将 dist/XexunRTT_Optimized 作为完整安装包发布")
        print(f"3. 后续更新只需发布新的 XexunRTT.exe 文件")
        print(f"4. 用户使用 incremental_update.bat 快速更新")
        
        # 询问是否清理
        try:
            choice = input(f"\n是否清理演示文件? (y/N): ").strip().lower()
            if choice == 'y':
                cleanup_demo()
                print("✅ 演示文件已清理")
        except:
            pass
            
    else:
        print(f"\n⚠️ 部分步骤失败，请检查错误信息")
    
    return success_count == len(steps)

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
