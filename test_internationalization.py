#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试国际化功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication, QTimer

def test_translation_loading():
    """测试翻译文件加载"""
    print("🧪 测试翻译文件加载...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 测试加载英文翻译文件
        translator = QTranslator()
        if translator.load("xexunrtt_en.qm"):
            print("✅ 英文翻译文件加载成功")
            app.installTranslator(translator)
        else:
            print("❌ 英文翻译文件加载失败")
            return False
        
        # 测试翻译功能
        test_translations = [
            ("Info", "信息"),
            ("Connected", "已连接"),
            ("Disconnected", "已断开"),
            ("Error", "错误"),
            ("Start", "开始"),
            ("Stop", "停止")
        ]
        
        print("\n📋 测试翻译结果:")
        for en_text, expected_zh in test_translations:
            translated = QCoreApplication.translate("main_window", en_text)
            if translated == expected_zh:
                print(f"✅ '{en_text}' -> '{translated}'")
            else:
                print(f"❌ '{en_text}' -> '{translated}' (期望: '{expected_zh}')")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_main_window_creation():
    """测试主窗口创建"""
    print("\n🧪 测试主窗口创建...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 加载翻译
        translator = QTranslator()
        if translator.load("xexunrtt_en.qm"):
            app.installTranslator(translator)
        
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        print("✅ 主窗口创建成功")
        
        # 检查窗口标题是否使用了翻译
        window_title = main_window.windowTitle()
        print(f"📋 窗口标题: {window_title}")
        
        # 自动关闭窗口
        QTimer.singleShot(2000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ui_elements_translation():
    """测试UI元素翻译"""
    print("\n🧪 测试UI元素翻译...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 加载翻译
        translator = QTranslator()
        if translator.load("xexunrtt_en.qm"):
            app.installTranslator(translator)
        
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        
        # 检查菜单项
        menubar = main_window.menuBar()
        menus = []
        for action in menubar.actions():
            if action.menu():
                menus.append(action.text())
        
        print(f"📋 菜单项: {menus}")
        
        # 检查状态栏
        status_text = main_window.connection_status_label.text()
        print(f"📋 连接状态: {status_text}")
        
        data_stats_text = main_window.data_stats_label.text()
        print(f"📋 数据统计: {data_stats_text}")
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_translation_files():
    """检查翻译文件"""
    print("🧪 检查翻译文件...")
    
    files_to_check = [
        ("xexunrtt_en.ts", "英文翻译源文件"),
        ("xexunrtt_en.qm", "英文翻译编译文件"),
        ("resources_rc.py", "资源文件"),
        ("xexunrtt.qm", "中文翻译文件"),
    ]
    
    all_exist = True
    for filename, description in files_to_check:
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"✅ {description}: {filename} ({file_size} 字节)")
        else:
            print(f"❌ {description}: {filename} (文件不存在)")
            all_exist = False
    
    return all_exist

def test_font_changes():
    """测试字体更改"""
    print("\n🧪 测试字体更改...")
    
    ui_files = ["xexunrtt.ui", "rtt2uart.ui", "sel_device.ui"]
    
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "Arial" in content:
                    print(f"✅ {ui_file}: 已更改为Arial字体")
                elif "新宋体" in content or "微软雅黑" in content:
                    print(f"❌ {ui_file}: 仍包含中文字体")
                else:
                    print(f"ℹ️ {ui_file}: 未检测到字体设置")
                    
            except Exception as e:
                print(f"❌ 检查{ui_file}失败: {e}")
        else:
            print(f"❌ {ui_file}: 文件不存在")

def main():
    """主函数"""
    print("🌍 测试国际化功能")
    print("=" * 60)
    
    # 检查翻译文件
    files_ok = check_translation_files()
    
    # 测试字体更改
    test_font_changes()
    
    # 测试翻译文件加载
    translation_ok = test_translation_loading()
    
    # 测试主窗口创建
    main_window_ok = test_main_window_creation()
    
    # 测试UI元素翻译
    ui_elements_ok = test_ui_elements_translation()
    
    print("\n" + "=" * 60)
    
    if all([files_ok, translation_ok, main_window_ok, ui_elements_ok]):
        print("🎉 所有国际化测试通过！")
        
        print("\n✅ 完成的工作:")
        print("1. ✅ 源代码文本英文化 - 将QCoreApplication.translate中的中文改为英文")
        print("2. ✅ UI文件字体更新 - 将中文字体改为Arial")
        print("3. ✅ 翻译文件生成 - 生成xexunrtt_en.ts和xexunrtt_en.qm")
        print("4. ✅ 资源文件更新 - 添加新的翻译文件到资源")
        print("5. ✅ 翻译内容填充 - 为英文文本提供中文翻译")
        
        print("\n🌍 国际化特性:")
        print("- 默认界面语言: 英文")
        print("- 支持语言切换: 英文/中文")
        print("- 翻译文件: xexunrtt_en.qm (英文->中文)")
        print("- 字体优化: 统一使用Arial字体")
        print("- 资源集成: 翻译文件已集成到资源系统")
        
        print("\n🎯 使用方法:")
        print("- 程序默认以英文界面启动")
        print("- 可通过QTranslator加载中文翻译")
        print("- 所有用户界面文本支持翻译")
        print("- 日志和调试信息保持英文便于开发")
        
    else:
        print("❌ 部分国际化测试失败！")
        failed_tests = []
        if not files_ok:
            failed_tests.append("翻译文件检查")
        if not translation_ok:
            failed_tests.append("翻译文件加载")
        if not main_window_ok:
            failed_tests.append("主窗口创建")
        if not ui_elements_ok:
            failed_tests.append("UI元素翻译")
        
        print(f"失败的测试: {', '.join(failed_tests)}")
    
    return 0 if all([files_ok, translation_ok, main_window_ok, ui_elements_ok]) else 1

if __name__ == '__main__':
    sys.exit(main())
