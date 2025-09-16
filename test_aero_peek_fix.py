#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试任务栏Aero Peek修复
"""

import sys
from PySide6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

def test_aero_peek_prevention():
    """测试对话框是否正确设置了防止Aero Peek显示的标志"""
    print("🧪 测试任务栏Aero Peek修复...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow, ConnectionDialog, DeviceSelectDialog, FindDialog
        
        # 测试主窗口
        main_window = RTTMainWindow()
        main_window.show()
        print("✅ 主窗口创建成功")
        
        # 检查主窗口标志（主窗口应该在任务栏显示）
        main_flags = main_window.windowFlags()
        main_has_tool = bool(main_flags & Qt.Tool)
        print(f"📋 主窗口 Tool 标志: {main_has_tool} (应该为 False)")
        
        # 测试连接对话框
        connection_dialog = ConnectionDialog(main_window)
        connection_flags = connection_dialog.windowFlags()
        connection_has_tool = bool(connection_flags & Qt.Tool)
        connection_has_close = bool(connection_flags & Qt.WindowCloseButtonHint)
        connection_has_system = bool(connection_flags & Qt.WindowSystemMenuHint)
        
        print(f"📋 连接对话框标志:")
        print(f"   Tool (防Aero Peek): {connection_has_tool} (应该为 True)")
        print(f"   CloseButtonHint: {connection_has_close} (应该为 True)")
        print(f"   SystemMenuHint: {connection_has_system} (应该为 True)")
        
        # 测试设备选择对话框
        device_dialog = DeviceSelectDialog()
        device_flags = device_dialog.windowFlags()
        device_has_tool = bool(device_flags & Qt.Tool)
        device_has_close = bool(device_flags & Qt.WindowCloseButtonHint)
        device_has_system = bool(device_flags & Qt.WindowSystemMenuHint)
        
        print(f"📋 设备选择对话框标志:")
        print(f"   Tool (防Aero Peek): {device_has_tool} (应该为 True)")
        print(f"   CloseButtonHint: {device_has_close} (应该为 True)")
        print(f"   SystemMenuHint: {device_has_system} (应该为 True)")
        
        # 测试查找对话框
        find_dialog = FindDialog(main_window)
        find_flags = find_dialog.windowFlags()
        find_has_tool = bool(find_flags & Qt.Tool)
        find_has_close = bool(find_flags & Qt.WindowCloseButtonHint)
        find_has_system = bool(find_flags & Qt.WindowSystemMenuHint)
        
        print(f"📋 查找对话框标志:")
        print(f"   Tool (防Aero Peek): {find_has_tool} (应该为 True)")
        print(f"   CloseButtonHint: {find_has_close} (应该为 True)")
        print(f"   SystemMenuHint: {find_has_system} (应该为 True)")
        
        # 检查所有对话框是否正确设置
        dialogs_correct = all([
            not main_has_tool,  # 主窗口不应该有Tool标志
            connection_has_tool and connection_has_close and connection_has_system,
            device_has_tool and device_has_close and device_has_system,
            find_has_tool and find_has_close and find_has_system
        ])
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return dialogs_correct
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_window_flags():
    """分析窗口标志的作用"""
    print("🔍 窗口标志分析...")
    
    from PySide6.QtCore import Qt
    
    print("🔧 关键窗口标志:")
    print(f"   Qt.Tool: {Qt.Tool}")
    print("   - 作用: 工具窗口，不会在任务栏显示独立图标")
    print("   - Aero Peek: 不会在任务栏预览中显示")
    print("   - 适用: 对话框、工具窗口")
    print()
    print(f"   Qt.WindowSystemMenuHint: {Qt.WindowSystemMenuHint}")
    print("   - 作用: 启用系统菜单（右键标题栏）")
    print("   - 包含: 关闭、最小化、最大化等选项")
    print()
    print(f"   Qt.WindowCloseButtonHint: {Qt.WindowCloseButtonHint}")
    print("   - 作用: 显示窗口右上角的关闭按钮")
    print("   - 用户体验: 允许直接点击关闭")

def create_demo_dialogs():
    """创建演示对话框来测试Aero Peek效果"""
    print("🎭 创建演示对话框...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建普通对话框（会在Aero Peek中显示）
    normal_dialog = QDialog()
    normal_dialog.setWindowTitle("普通对话框 - 会在Aero Peek中显示")
    normal_dialog.resize(300, 150)
    
    layout1 = QVBoxLayout(normal_dialog)
    layout1.addWidget(QLabel("这是普通对话框"))
    layout1.addWidget(QLabel("会在任务栏Aero Peek中显示"))
    close_btn1 = QPushButton("关闭")
    close_btn1.clicked.connect(normal_dialog.close)
    layout1.addWidget(close_btn1)
    
    # 创建Tool对话框（不会在Aero Peek中显示）
    tool_dialog = QDialog()
    tool_dialog.setWindowTitle("Tool对话框 - 不会在Aero Peek中显示")
    tool_dialog.resize(300, 150)
    
    # 设置Tool标志
    current_flags = tool_dialog.windowFlags()
    new_flags = current_flags | Qt.Tool
    new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
    tool_dialog.setWindowFlags(new_flags)
    
    layout2 = QVBoxLayout(tool_dialog)
    layout2.addWidget(QLabel("这是Tool对话框"))
    layout2.addWidget(QLabel("不会在任务栏Aero Peek中显示"))
    close_btn2 = QPushButton("关闭")
    close_btn2.clicked.connect(tool_dialog.close)
    layout2.addWidget(close_btn2)
    
    # 显示对话框
    normal_dialog.move(100, 100)
    tool_dialog.move(450, 100)
    
    normal_dialog.show()
    tool_dialog.show()
    
    print("📋 演示对话框已创建：")
    print("   左侧：普通对话框（会在Aero Peek中显示）")
    print("   右侧：Tool对话框（不会在Aero Peek中显示）")
    print("💡 请将鼠标悬停在任务栏上测试Aero Peek效果")
    
    return normal_dialog, tool_dialog

def main():
    """主函数"""
    print("🚀 测试任务栏Aero Peek修复")
    print("=" * 50)
    
    # 分析窗口标志
    analyze_window_flags()
    print()
    
    # 测试修复效果
    success = test_aero_peek_prevention()
    print()
    
    if success:
        print("🎉 Aero Peek修复测试通过！")
        print("\n修复说明:")
        print("1. ✅ 连接对话框设置了Tool标志，不会在Aero Peek中显示")
        print("2. ✅ 设备选择对话框设置了Tool标志")
        print("3. ✅ 查找对话框设置了Tool标志")
        print("4. ✅ 所有对话框保留了关闭按钮和系统菜单")
        print("5. ✅ 主窗口正常显示在任务栏")
        
        print("\n技术细节:")
        print("- 使用 Qt.Tool 标志防止对话框在Aero Peek中显示")
        print("- 保留 WindowSystemMenuHint 和 WindowCloseButtonHint")
        print("- 对话框仍然可以正常使用，只是不会在任务栏预览")
        
        print("\n用户体验改进:")
        print("- ✅ 任务栏Aero Peek只显示主窗口")
        print("- ✅ 敏感的连接配置信息不会暴露在预览中")
        print("- ✅ 对话框功能完全正常，包括关闭按钮")
        print("- ✅ 系统菜单（右键标题栏）保持可用")
        
    else:
        print("❌ Aero Peek修复测试失败！")
    
    # 可选：创建演示对话框
    choice = input("\n是否创建演示对话框来测试Aero Peek效果？(y/N): ")
    if choice.lower() == 'y':
        try:
            normal_dialog, tool_dialog = create_demo_dialogs()
            
            # 运行事件循环
            app = QApplication.instance()
            if app:
                print("\n按 Ctrl+C 退出演示...")
                try:
                    app.exec()
                except KeyboardInterrupt:
                    print("\n演示结束")
        except Exception as e:
            print(f"创建演示对话框失败: {e}")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
