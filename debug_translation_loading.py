#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试翻译加载
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

def debug_translation_loading():
    """调试翻译加载过程"""
    print("🔍 调试翻译加载过程...")
    
    # 创建应用
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    print(f"📋 系统语言环境: {QLocale.system().name()}")
    print(f"📋 是否为中文: {QLocale.system().language() == QLocale.Chinese}")
    
    # 加载翻译（模拟main_window.py中的逻辑）
    translator = QTranslator()
    locale = QLocale.system()
    
    if locale.language() == QLocale.Chinese:
        print("🔄 尝试加载中文翻译...")
        
        # 尝试从当前目录加载
        if translator.load("xexunrtt_en.qm"):
            app.installTranslator(translator)
            print("✅ 中文翻译从当前目录加载成功")
            
            # 测试翻译
            test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
            print(f"📋 翻译测试: 'JLink Debug Log' → '{test_text}'")
            
        elif translator.load(":/xexunrtt_en.qm"):
            app.installTranslator(translator)
            print("✅ 中文翻译从资源加载成功")
            
            # 测试翻译
            test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
            print(f"📋 翻译测试: 'JLink Debug Log' → '{test_text}'")
        else:
            print("❌ 中文翻译加载失败")
            return False
    else:
        print("ℹ️ 使用英文界面（默认）")
    
    # 测试关键翻译
    print("\n🧪 测试关键翻译:")
    key_texts = [
        "Sent:",
        "Compact Mode(&M)",
        "Connection(&C)",
        "Tools(&T)",
        "Help(&H)"
    ]
    
    for text in key_texts:
        translated = QCoreApplication.translate("main_window", text)
        print(f"  '{text}' → '{translated}'")
    
    return True

def test_ui_creation_with_translation():
    """测试带翻译的UI创建"""
    print("\n🧪 测试带翻译的UI创建...")
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        
        # 检查是否有更新翻译的方法
        if hasattr(main_window, '_update_ui_translations'):
            print("✅ 找到 _update_ui_translations 方法")
            main_window._update_ui_translations()
            print("✅ 已调用 _update_ui_translations")
        else:
            print("❌ 没有找到 _update_ui_translations 方法")
        
        # 检查菜单
        menubar = main_window.menuBar()
        print("📋 菜单项:")
        for action in menubar.actions():
            if action.menu():
                print(f"  - {action.text()}")
        
        # 检查紧凑模式动作
        if hasattr(main_window, 'compact_mode_action'):
            compact_text = main_window.compact_mode_action.text()
            print(f"📋 紧凑模式动作: '{compact_text}'")
        
        main_window.close()
        return True
        
    except Exception as e:
        print(f"❌ 测试UI创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_translation_files():
    """检查翻译文件"""
    print("\n🔍 检查翻译文件:")
    
    files_to_check = [
        "xexunrtt_en.ts",
        "xexunrtt_en.qm",
        "resources_rc.py"
    ]
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"  ✅ {filename}: {size} 字节")
        else:
            print(f"  ❌ {filename}: 不存在")

def main():
    """主函数"""
    print("🔧 调试翻译加载问题")
    print("=" * 60)
    
    # 检查翻译文件
    check_translation_files()
    
    # 调试翻译加载
    loading_ok = debug_translation_loading()
    
    # 测试UI创建
    ui_ok = test_ui_creation_with_translation()
    
    print("\n" + "=" * 60)
    
    if loading_ok and ui_ok:
        print("🎉 调试完成")
        
        print("\n💡 可能的解决方案:")
        print("1. 检查程序是否正确调用了 _update_ui_translations")
        print("2. 确保翻译在UI创建后被应用")
        print("3. 验证QAction的文本是否需要手动更新")
        print("4. 检查是否需要调用 retranslateUi")
        
    else:
        print("❌ 调试发现问题")
        
        if not loading_ok:
            print("- 翻译加载有问题")
        if not ui_ok:
            print("- UI创建有问题")

if __name__ == "__main__":
    main()
