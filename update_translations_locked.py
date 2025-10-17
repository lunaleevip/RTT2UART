#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新翻译文件并自动锁定UI翻译

这个脚本解决了 pyside6-lupdate 的一个设计问题：
每次运行 lupdate 扫描 .ui 文件时，会将所有UI相关的翻译标记为 type="unfinished"，
导致已完成的翻译失效。

这个脚本会：
1. 运行 pyside6-lupdate 扫描所有源文件
2. 自动为已有翻译的条目移除 type="unfinished" 标记
3. 为常见的UI元素自动添加翻译
4. 重新编译 .qm 文件
"""

import re
import subprocess
import sys

# 主界面和连接对话框的完整翻译映射
UI_TRANSLATIONS = {
    # 主界面按钮
    "Open Folder": "打开文件夹",
    "Reconnect": "重连",
    "Disconnect": "断开",
    "Clear": "清空",
    "Restart APP": "重启应用",
    
    # 主界面选项
    "Lock Vertical": "锁定垂直",
    "Lock Horizontal": "锁定水平",
    "Light Mode": "浅色模式",
    "Auto Reconnect": "自动重连",
    "Font:": "字体：",
    "Size:": "大小：",
    
    # 连接对话框
    "Connection to J-Link": "连接到 J-Link",
    "USB": "USB",
    "Existing Session": "现有会话",
    "TCP/IP": "TCP/IP",
    "Serial NO": "序列号",
    "↻": "↻",
    "Refresh JLink devices": "刷新 JLink 设备",
    "Serial Forward Settings": "串口转发设置",
    "LOG Current Tab Selection": "LOG 当前标签选择",
    "DATA (RTT Channel 1)": "DATA (RTT 通道 1)",
    "Forward Content:": "转发内容：",
    "Specify Target Device": "指定目标设备",
    "...": "...",
    "Target Interface And Speed": "目标接口和速率",
    "SWD": "SWD",
    "JTAG": "JTAG",
    "4000 kHz": "4000 kHz",
    "Reset target": "复位目标",
    "Log Split": "日志拆分",
    "UART Config": "UART 配置",
    "Port:": "端口：",
    "Baud rate:": "波特率：",
    "Scan": "扫描",
    "Start": "开始",
}

def run_lupdate():
    """运行 pyside6-lupdate 扫描源文件"""
    print("=" * 60)
    print("步骤 1: 运行 pyside6-lupdate 扫描源文件...")
    print("=" * 60)
    
    cmd = [
        "pyside6-lupdate",
        "main_window.py",
        "rtt2uart.py", 
        "ui_rtt2uart_updated.py",
        "ui_xexunrtt.py",
        "xexunrtt.ui",
        "rtt2uart_updated.ui",
        "-ts", "xexunrtt_complete.ts",
        "-noobsolete"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    print(result.stdout)
    if result.returncode != 0:
        print(f"错误: {result.stderr}", file=sys.stderr)
        return False
    return True

def fix_translations(ts_file):
    """修复翻译文件"""
    print("\n" + "=" * 60)
    print("步骤 2: 修复翻译...")
    print("=" * 60)
    
    with open(ts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 统计
    fixed_unfinished = 0
    added_translation = 0
    
    # 1. 移除已有翻译的 type="unfinished" 标记
    pattern1 = r'<translation type="unfinished">(.+?)</translation>'
    matches = re.findall(pattern1, content)
    if matches:
        content = re.sub(pattern1, r'<translation>\1</translation>', content)
        fixed_unfinished = len(matches)
        print(f"✓ 移除了 {fixed_unfinished} 个已有翻译的 unfinished 标记")
    
    # 2. 为空翻译添加对应的中文
    for source_text, trans_text in UI_TRANSLATIONS.items():
        escaped_source = re.escape(source_text)
        pattern = rf'(<source>{escaped_source}</source>\s*)<translation type="unfinished"></translation>'
        
        new_content, count = re.subn(
            pattern, 
            rf'\1<translation>{trans_text}</translation>',
            content
        )
        
        if count > 0:
            content = new_content
            added_translation += count
            print(f"✓ 添加翻译: {source_text} -> {trans_text}")
    
    # 写回文件
    with open(ts_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n总计:")
    print(f"  - 修复了 {fixed_unfinished} 条已有翻译")
    print(f"  - 添加了 {added_translation} 条新翻译")
    
    return fixed_unfinished + added_translation > 0

def compile_qm():
    """编译 .qm 文件"""
    print("\n" + "=" * 60)
    print("步骤 3: 编译 .qm 文件...")
    print("=" * 60)
    
    cmd = ["pyside6-lrelease", "xexunrtt_complete.ts", "-qm", "xexunrtt_complete.qm"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    print(result.stdout)
    if result.returncode != 0:
        print(f"错误: {result.stderr}", file=sys.stderr)
        return False
    return True

def main():
    print("\n🔧 开始更新翻译文件...\n")
    
    # 1. 运行 lupdate
    if not run_lupdate():
        print("\n❌ lupdate 失败")
        return 1
    
    # 2. 修复翻译
    if not fix_translations("xexunrtt_complete.ts"):
        print("\n⚠️  没有需要修复的翻译")
    
    # 3. 编译 qm
    if not compile_qm():
        print("\n❌ 编译失败")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ 翻译更新完成！")
    print("=" * 60)
    print("\n现在可以运行程序查看效果")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
