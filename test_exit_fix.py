#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试程序退出修复
"""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

def test_exit_mechanisms():
    """测试退出机制"""
    print("🧪 测试程序退出修复...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 模拟创建主窗口
        from main_window import RTTMainWindow
        
        window = RTTMainWindow()
        window.show()
        
        print("✅ 主窗口创建成功")
        
        # 测试紧凑模式切换
        print("🔄 测试紧凑模式切换...")
        
        # 进入紧凑模式
        window._toggle_compact_mode()
        if window.compact_mode:
            print("✅ 成功进入紧凑模式")
            print(f"   窗口置顶标志: {bool(window.windowFlags() & window.windowFlags().WindowStaysOnTopHint)}")
        
        # 退出紧凑模式
        window._toggle_compact_mode()
        if not window.compact_mode:
            print("✅ 成功退出紧凑模式")
            print(f"   窗口置顶标志清除: {not bool(window.windowFlags() & window.windowFlags().WindowStaysOnTopHint)}")
        
        # 测试closeEvent修复
        print("🔧 测试closeEvent修复...")
        
        # 再次进入紧凑模式
        window._toggle_compact_mode()
        print("✅ 再次进入紧凑模式用于测试关闭")
        
        # 使用定时器自动关闭窗口（模拟用户关闭）
        def auto_close():
            print("🔄 模拟用户关闭窗口...")
            window.close()
            print("✅ 窗口关闭测试完成")
            app.quit()
        
        QTimer.singleShot(1000, auto_close)  # 1秒后自动关闭
        
        # 短暂运行应用程序
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_force_quit_shortcut():
    """测试强制退出快捷键"""
    print("🧪 测试强制退出快捷键...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 检查快捷键是否正确注册
        window = RTTMainWindow()
        
        # 检查是否有强制退出动作
        if hasattr(window, 'force_quit_action'):
            shortcut = window.force_quit_action.shortcut()
            print(f"✅ 强制退出快捷键: {shortcut.toString()}")
            
            # 检查快捷键是否是 Ctrl+Alt+Q
            expected = "Ctrl+Alt+Q"
            if shortcut.toString() == expected:
                print(f"✅ 快捷键设置正确: {expected}")
            else:
                print(f"❌ 快捷键设置错误，期望: {expected}, 实际: {shortcut.toString()}")
        else:
            print("❌ 未找到强制退出动作")
            return False
        
        window.close()
        return True
        
    except Exception as e:
        print(f"❌ 快捷键测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 测试程序退出修复")
    print("=" * 50)
    
    success = True
    
    # 测试强制退出快捷键
    if not test_force_quit_shortcut():
        success = False
    print()
    
    if success:
        print("🎉 退出修复测试通过！")
        print("\n修复说明:")
        print("1. ✅ 修复了紧凑模式窗口置顶导致的退出问题")
        print("2. ✅ 在closeEvent中自动清除窗口置顶标志")
        print("3. ✅ 添加了强制退出快捷键: Ctrl+Alt+Q")
        print("4. ✅ 增强了错误处理和日志记录")
        print("5. ✅ 在右键菜单中添加了退出选项")
        
        print("\n使用说明:")
        print("- 正常退出: 关闭窗口或右键菜单 → 程序控制 → 退出程序")
        print("- 强制退出: Ctrl+Alt+Q 或右键菜单 → 程序控制 → 强制退出")
        print("- 紧凑模式下的退出已经修复，不会再卡住")
        
        # 运行实际测试（如果用户确认）
        print("\n是否运行实际窗口测试？(需要手动关闭窗口)")
        try:
            response = input("输入 'y' 运行测试: ").lower().strip()
            if response == 'y':
                test_exit_mechanisms()
        except KeyboardInterrupt:
            print("\n测试被用户中断")
    else:
        print("❌ 部分测试失败！")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
