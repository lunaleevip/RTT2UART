# -*- coding: utf-8 -*-
"""
构建工具脚本
用于更新翻译文件和生成 UI 文件
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """运行命令并打印结果"""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
            print(result.stdout)
        print(f"✓ {description} - 成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} - 失败")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
        return False
    except Exception as e:
        print(f"✗ {description} - 错误: {e}")
        return False


def generate_ui_files():
    """生成所有 UI 文件"""
    ui_dir = Path("ui")
    ui_files = list(ui_dir.glob("*.ui"))
    
    if not ui_files:
        print("未找到 UI 文件")
        return False
    
    success = True
    for ui_file in ui_files:
        py_file = ui_dir / f"ui_{ui_file.stem}.py"
        cmd = ["pyside6-uic", str(ui_file), "-o", str(py_file)]
        if not run_command(cmd, f"生成 {py_file.name}"):
            success = False
    
    return success


def update_translations():
    """更新翻译文件"""
    # 源文件列表
    sources = [
        "main_window.py",
        "rtt2uart.py",
        "ansi_terminal_widget.py",
        "ui_constants.py",
        "ui/xexunrtt.ui",
        "ui/rtt2uart_updated.ui",
        "ui/sel_device.ui",
    ]
    
    # 翻译文件
    ts_files = [
        "lang/xexunrtt_zh_CN.ts",
        "lang/xexunrtt_zh_TW.ts",
    ]
    
    # 更新翻译文件
    for ts_file in ts_files:
        cmd = ["pyside6-lupdate"] + sources + ["-ts", ts_file]
        if not run_command(cmd, f"更新 {ts_file}"):
            return False
    
    return True


def compile_translations():
    """编译翻译文件"""
    lang_dir = Path("lang")
    ts_files = list(lang_dir.glob("*.ts"))
    
    if not ts_files:
        print("未找到翻译文件")
        return False
    
    success = True
    for ts_file in ts_files:
        qm_file = ts_file.with_suffix(".qm")
        cmd = ["pyside6-lrelease", str(ts_file), "-qm", str(qm_file)]
        if not run_command(cmd, f"编译 {qm_file.name}"):
            success = False
    
    return success


def main():
    """主函数"""
    print("XexunRTT 构建工具")
    print("="*60)
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python build_tools.py ui          - 生成 UI 文件")
        print("  python build_tools.py trans       - 更新翻译文件")
        print("  python build_tools.py compile     - 编译翻译文件")
        print("  python build_tools.py all         - 执行所有操作")
        return 1
    
    command = sys.argv[1].lower()
    
    if command == "ui":
        success = generate_ui_files()
    elif command == "trans":
        success = update_translations()
    elif command == "compile":
        success = compile_translations()
    elif command == "all":
        success = (
            generate_ui_files() and
            update_translations() and
            compile_translations()
        )
    else:
        print(f"未知命令: {command}")
        return 1
    
    print("\n" + "="*60)
    if success:
        print("✓ 所有操作完成")
        return 0
    else:
        print("✗ 某些操作失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())

