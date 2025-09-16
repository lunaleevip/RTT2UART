#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试关闭按钮修复
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

def test_close_button_availability():
    """测试关闭按钮在紧凑模式下的可用性"""
    print("🧪 测试关闭按钮修复...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        window = RTTMainWindow()
        window.show()
        
        print("✅ 主窗口创建成功")
        
        # 检查初始状态的窗口标志
        initial_flags = window.windowFlags()
        print(f"📋 初始窗口标志: {initial_flags}")
        print(f"   SystemMenuHint: {bool(initial_flags & Qt.WindowSystemMenuHint)}")
        print(f"   CloseButtonHint: {bool(initial_flags & Qt.WindowCloseButtonHint)}")
        print(f"   StaysOnTopHint: {bool(initial_flags & Qt.WindowStaysOnTopHint)}")
        
        # 测试进入紧凑模式
        print("\n🔄 进入紧凑模式...")
        window._toggle_compact_mode()
        
        if window.compact_mode:
            compact_flags = window.windowFlags()
            print(f"📋 紧凑模式窗口标志: {compact_flags}")
            print(f"   SystemMenuHint: {bool(compact_flags & Qt.WindowSystemMenuHint)}")
            print(f"   CloseButtonHint: {bool(compact_flags & Qt.WindowCloseButtonHint)}")
            print(f"   StaysOnTopHint: {bool(compact_flags & Qt.WindowStaysOnTopHint)}")
            
            # 检查关闭按钮是否可用
            has_close_button = bool(compact_flags & Qt.WindowCloseButtonHint)
            has_system_menu = bool(compact_flags & Qt.WindowSystemMenuHint)
            is_on_top = bool(compact_flags & Qt.WindowStaysOnTopHint)
            
            if has_close_button and has_system_menu and is_on_top:
                print("✅ 紧凑模式：关闭按钮可用，窗口置顶正常")
                success_compact = True
            else:
                print("❌ 紧凑模式：关闭按钮或其他功能异常")
                success_compact = False
        else:
            print("❌ 无法进入紧凑模式")
            success_compact = False
        
        # 测试退出紧凑模式
        print("\n🔄 退出紧凑模式...")
        window._toggle_compact_mode()
        
        if not window.compact_mode:
            normal_flags = window.windowFlags()
            print(f"📋 正常模式窗口标志: {normal_flags}")
            print(f"   SystemMenuHint: {bool(normal_flags & Qt.WindowSystemMenuHint)}")
            print(f"   CloseButtonHint: {bool(normal_flags & Qt.WindowCloseButtonHint)}")
            print(f"   StaysOnTopHint: {bool(normal_flags & Qt.WindowStaysOnTopHint)}")
            
            # 检查关闭按钮是否可用
            has_close_button = bool(normal_flags & Qt.WindowCloseButtonHint)
            has_system_menu = bool(normal_flags & Qt.WindowSystemMenuHint)
            is_not_on_top = not bool(normal_flags & Qt.WindowStaysOnTopHint)
            
            if has_close_button and has_system_menu and is_not_on_top:
                print("✅ 正常模式：关闭按钮可用，窗口置顶已清除")
                success_normal = True
            else:
                print("❌ 正常模式：关闭按钮或其他功能异常")
                success_normal = False
        else:
            print("❌ 无法退出紧凑模式")
            success_normal = False
        
        # 自动关闭窗口
        QTimer.singleShot(1000, window.close)
        
        return success_compact and success_normal
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_window_flags():
    """分析窗口标志的含义"""
    print("🔍 窗口标志分析...")
    
    from PySide6.QtCore import Qt
    
    flags_info = {
        'WindowSystemMenuHint': Qt.WindowSystemMenuHint,
        'WindowCloseButtonHint': Qt.WindowCloseButtonHint, 
        'WindowStaysOnTopHint': Qt.WindowStaysOnTopHint,
        'WindowMinimizeButtonHint': Qt.WindowMinimizeButtonHint,
        'WindowMaximizeButtonHint': Qt.WindowMaximizeButtonHint,
    }
    
    print("🔧 重要窗口标志:")
    for name, flag in flags_info.items():
        print(f"   {name}: {flag}")
    
    print("\n说明:")
    print("- WindowSystemMenuHint: 启用系统菜单（包含关闭、最小化等）")
    print("- WindowCloseButtonHint: 显示关闭按钮")
    print("- WindowStaysOnTopHint: 窗口始终置顶")
    print("- 设置窗口标志时需要明确保留必要的按钮")

def main():
    """主函数"""
    print("🚀 测试关闭按钮修复")
    print("=" * 50)
    
    # 分析窗口标志
    analyze_window_flags()
    print()
    
    # 测试关闭按钮
    success = test_close_button_availability()
    print()
    
    if success:
        print("🎉 关闭按钮修复测试通过！")
        print("\n修复说明:")
        print("1. ✅ 紧凑模式下关闭按钮保持可用")
        print("2. ✅ 窗口置顶功能正常工作")
        print("3. ✅ 正常模式下所有功能恢复")
        print("4. ✅ 系统菜单（右键标题栏）保持可用")
        
        print("\n技术细节:")
        print("- 使用 WindowSystemMenuHint | WindowCloseButtonHint 确保按钮可用")
        print("- 在设置 WindowStaysOnTopHint 时保留其他标志")
        print("- 所有窗口标志操作都有错误处理")
        
        print("\n用户体验改进:")
        print("- ✅ 可以直接点击右上角 ❌ 关闭窗口")
        print("- ✅ 紧凑模式下体验与正常模式一致")
        print("- ✅ 无需依赖右键菜单或快捷键退出")
    else:
        print("❌ 关闭按钮修复测试失败！")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
