#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试当前翻译问题
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

def check_translation_files():
    """检查翻译文件状态"""
    print("🔍 检查翻译文件状态")
    print("=" * 50)
    
    files_to_check = [
        "xexunrtt_complete.qm",
        "xexunrtt_complete.ts", 
        "xexunrtt_en.qm",
        "resources_rc.py"
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            mtime = os.path.getmtime(filename)
            import datetime
            mod_time = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"✅ {filename}: {size} 字节, 修改时间: {mod_time}")
        else:
            print(f"❌ {filename}: 不存在")

def check_specific_translations():
    """检查具体的翻译内容"""
    print("\n🔍 检查具体翻译内容")
    print("=" * 50)
    
    # 检查翻译文件中的具体内容
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译源文件不存在: {ts_file}")
        return False
    
    with open(ts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查图片中显示的未翻译文本
    missing_texts = [
        "Clear Current Page",
        "Open Log Folder", 
        "Open Config Folder",
        "Enable Verbose Log",
        "Disable Verbose Log",
        "Serial Forward Settings",
        "LOG Current Tab",
        "DATA (RTT Channel 1)",
        "Disable Forward",
        "Forward",
        "Reconnect",
        "Disconnect", 
        "Connection Settings"
    ]
    
    print("🔍 检查缺失的翻译文本:")
    found_count = 0
    for text in missing_texts:
        if f"<source>{text}</source>" in content:
            print(f"  ✅ '{text}' 存在于翻译文件中")
            found_count += 1
        else:
            print(f"  ❌ '{text}' 不存在于翻译文件中")
    
    print(f"\n📊 翻译覆盖率: {found_count}/{len(missing_texts)} ({found_count/len(missing_texts)*100:.1f}%)")
    
    return found_count > 0

def test_runtime_translation():
    """测试运行时翻译"""
    print("\n🔍 测试运行时翻译")
    print("=" * 50)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 加载翻译文件
    translator = QTranslator()
    translation_loaded = False
    
    if translator.load("xexunrtt_complete.qm"):
        app.installTranslator(translator)
        translation_loaded = True
        print("✅ xexunrtt_complete.qm 加载成功")
    elif translator.load(":/xexunrtt_complete.qm"):
        app.installTranslator(translator)
        translation_loaded = True
        print("✅ xexunrtt_complete.qm 从资源加载成功")
    else:
        print("❌ xexunrtt_complete.qm 加载失败")
        return False
    
    # 测试具体翻译
    print("\n🧪 测试具体翻译:")
    test_cases = [
        ("main_window", "Clear Current Page(&C)", "清除当前页面(&C)"),
        ("main_window", "Open Log Folder(&O)", "打开日志文件夹(&O)"),
        ("main_window", "Open Config Folder(&F)", "打开配置文件夹(&F)"),
        ("main_window", "Enable Verbose Log", "启用详细日志"),
        ("main_window", "Disable Verbose Log", "禁用详细日志"),
        ("main_window", "Reconnect(&R)", "重新连接(&R)"),
        ("main_window", "Disconnect(&D)", "断开连接(&D)"),
        ("main_window", "Connection Settings(&S)...", "连接设置(&S)..."),
        ("dialog", "Disable Forward", "禁用转发"),
        ("xexun_rtt", "Send", "发送")
    ]
    
    all_working = True
    for context, english, expected_chinese in test_cases:
        actual = QCoreApplication.translate(context, english)
        if actual == expected_chinese:
            print(f"  ✅ {context}: '{english}' → '{actual}'")
        elif actual != english:
            print(f"  🔧 {context}: '{english}' → '{actual}' (部分翻译)")
        else:
            print(f"  ❌ {context}: '{english}' → '{actual}' (无翻译)")
            all_working = False
    
    return all_working

def analyze_main_window_program():
    """分析主程序的翻译加载"""
    print("\n🔍 分析主程序翻译加载")
    print("=" * 50)
    
    # 检查main_window.py中的翻译加载代码
    main_file = "main_window.py"
    if not os.path.exists(main_file):
        print(f"❌ 主程序文件不存在: {main_file}")
        return False
    
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查翻译加载相关代码
    if "xexunrtt_complete.qm" in content:
        print("✅ 主程序使用 xexunrtt_complete.qm")
    elif "xexunrtt_en.qm" in content:
        print("⚠️ 主程序仍使用 xexunrtt_en.qm (需要更新)")
    else:
        print("❌ 主程序没有翻译加载代码")
    
    # 检查_update_ui_translations方法
    if "_update_ui_translations" in content:
        print("✅ 主程序有 _update_ui_translations 方法")
    else:
        print("❌ 主程序缺少 _update_ui_translations 方法")
    
    return True

def main():
    """主函数"""
    print("🔧 调试当前翻译问题")
    print("=" * 60)
    
    # 1. 检查翻译文件
    check_translation_files()
    
    # 2. 检查翻译内容
    has_translations = check_specific_translations()
    
    # 3. 测试运行时翻译
    runtime_ok = test_runtime_translation()
    
    # 4. 分析主程序
    main_ok = analyze_main_window_program()
    
    print("\n" + "=" * 60)
    
    if has_translations and runtime_ok and main_ok:
        print("🎯 翻译系统基本正常，问题可能在:")
        print("1. 某些UI元素是动态创建的，没有应用翻译")
        print("2. 翻译更新没有正确触发")
        print("3. 某些翻译文本的上下文不匹配")
        
        print("\n💡 建议解决方案:")
        print("1. 重新扫描所有源文件生成完整翻译")
        print("2. 检查动态创建的UI元素翻译")
        print("3. 强制更新所有UI元素的翻译")
    else:
        print("❌ 翻译系统存在问题:")
        if not has_translations:
            print("- 翻译文件内容不完整")
        if not runtime_ok:
            print("- 运行时翻译加载失败")
        if not main_ok:
            print("- 主程序翻译配置有问题")

if __name__ == "__main__":
    main()
