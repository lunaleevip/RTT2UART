#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试UI更新
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication

def test_translation_update():
    """测试翻译更新"""
    print("🔍 调试UI翻译更新...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 加载翻译
    translator = QTranslator()
    if translator.load("xexunrtt_en.qm"):
        app.installTranslator(translator)
        print("✅ 翻译已加载")
    else:
        print("❌ 翻译加载失败")
        return False
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        print("✅ 主窗口已创建")
        
        # 检查翻译前的状态
        print("\n🔍 翻译前状态:")
        if hasattr(main_window, 'compact_mode_action'):
            print(f"  Compact Mode Action: '{main_window.compact_mode_action.text()}'")
        if hasattr(main_window, 'connection_menu'):
            print(f"  Connection Menu: '{main_window.connection_menu.title()}'")
        if hasattr(main_window, 'tools_menu'):
            print(f"  Tools Menu: '{main_window.tools_menu.title()}'")
        
        # 手动调用翻译更新
        print("\n🔄 手动调用翻译更新...")
        if hasattr(main_window, '_update_ui_translations'):
            main_window._update_ui_translations()
            print("✅ _update_ui_translations 已调用")
        else:
            print("❌ 没有找到 _update_ui_translations 方法")
            return False
        
        # 检查翻译后的状态
        print("\n🔍 翻译后状态:")
        if hasattr(main_window, 'compact_mode_action'):
            print(f"  Compact Mode Action: '{main_window.compact_mode_action.text()}'")
        if hasattr(main_window, 'connection_menu'):
            print(f"  Connection Menu: '{main_window.connection_menu.title()}'")
        if hasattr(main_window, 'tools_menu'):
            print(f"  Tools Menu: '{main_window.tools_menu.title()}'")
        if hasattr(main_window, 'help_menu'):
            print(f"  Help Menu: '{main_window.help_menu.title()}'")
        
        # 检查窗口标题
        print(f"  Window Title: '{main_window.windowTitle()}'")
        
        # 测试直接翻译调用
        print("\n🧪 直接翻译测试:")
        direct_compact = QCoreApplication.translate("main_window", "Compact Mode(&M)")
        print(f"  Direct translate 'Compact Mode(&M)': '{direct_compact}'")
        
        direct_tools = QCoreApplication.translate("main_window", "Tools(&T)")
        print(f"  Direct translate 'Tools(&T)': '{direct_tools}'")
        
        # 测试手动设置
        print("\n🔧 手动设置测试:")
        if hasattr(main_window, 'compact_mode_action'):
            main_window.compact_mode_action.setText(direct_compact)
            print(f"  手动设置后 Compact Mode Action: '{main_window.compact_mode_action.text()}'")
        
        if hasattr(main_window, 'tools_menu'):
            main_window.tools_menu.setTitle(direct_tools)
            print(f"  手动设置后 Tools Menu: '{main_window.tools_menu.title()}'")
        
        main_window.close()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔧 调试UI翻译更新")
    print("=" * 60)
    
    success = test_translation_update()
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 调试完成")
        
        print("\n💡 分析:")
        print("1. 检查 _update_ui_translations 是否被正确调用")
        print("2. 检查翻译是否正确加载")
        print("3. 检查UI元素是否正确更新")
        print("4. 检查是否需要在特定时机调用翻译更新")
        
    else:
        print("❌ 调试失败")

if __name__ == "__main__":
    main()
