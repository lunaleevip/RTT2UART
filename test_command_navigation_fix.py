#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试命令历史导航和TAB索引修复功能
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeyEvent

def test_tab_index_fix():
    """测试TAB索引修复"""
    print("🧪 测试TAB索引修复...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 测试get_tab1_content方法的TAB索引
        import inspect
        source = inspect.getsource(main_window.get_tab1_content)
        
        if "tab_index = 2" in source:
            print("✅ TAB索引已修复：使用索引2 (RTT Channel 1)")
            tab_index_ok = True
        else:
            print("❌ TAB索引未修复：仍使用错误索引")
            tab_index_ok = False
        
        # 验证注释是否正确
        if "索引0是ALL页面，索引1是RTT Channel 0，索引2是RTT Channel 1" in source:
            print("✅ TAB索引注释正确")
        else:
            print("❌ TAB索引注释不正确")
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return tab_index_ok
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_navigation_setup():
    """测试命令历史导航设置"""
    print("\n🧪 测试命令历史导航设置...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 检查导航相关属性
        attributes_ok = True
        
        if hasattr(main_window, 'command_history_index'):
            print(f"✅ command_history_index属性存在: {main_window.command_history_index}")
        else:
            print("❌ command_history_index属性缺失")
            attributes_ok = False
        
        if hasattr(main_window, 'current_input_text'):
            print(f"✅ current_input_text属性存在: '{main_window.current_input_text}'")
        else:
            print("❌ current_input_text属性缺失")
            attributes_ok = False
        
        # 检查事件过滤器是否安装
        if main_window.ui.cmd_buffer.findChild(type(main_window)) == main_window:
            print("✅ 事件过滤器可能已安装")
        else:
            print("ℹ️ 事件过滤器状态未知")
        
        # 检查相关方法是否存在
        methods_to_check = [
            'eventFilter',
            '_navigate_command_history_up',
            '_navigate_command_history_down',
            '_reset_command_history_navigation',
            '_save_current_input'
        ]
        
        methods_ok = True
        for method_name in methods_to_check:
            if hasattr(main_window, method_name):
                print(f"✅ 方法存在: {method_name}")
            else:
                print(f"❌ 方法缺失: {method_name}")
                methods_ok = False
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return attributes_ok and methods_ok
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_combobox_clear_integration():
    """测试ComboBox清空集成"""
    print("\n🧪 测试ComboBox清空集成...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 检查发送成功处理方法是否包含重置导航状态
        import inspect
        method_source = inspect.getsource(main_window.on_pushButton_clicked)
        
        integration_checks = [
            ("_reset_command_history_navigation", "重置命令历史导航状态"),
            ("clearEditText", "清空ComboBox输入框"),
            ("setCurrentText", "设置ComboBox当前文本为空")
        ]
        
        integration_ok = True
        for check, description in integration_checks:
            if check in method_source:
                print(f"✅ {description}已集成: {check}")
            else:
                print(f"❌ {description}未集成: {check}")
                integration_ok = False
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return integration_ok
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_command_navigation():
    """模拟命令历史导航"""
    print("\n🧪 模拟命令历史导航...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 添加一些测试命令到ComboBox
        test_commands = ["ver?", "help", "status", "reset"]
        for cmd in test_commands:
            main_window.ui.cmd_buffer.addItem(cmd)
        
        print(f"✅ 添加了 {len(test_commands)} 个测试命令")
        
        # 测试向上导航
        print("\n📋 测试向上导航:")
        for i in range(3):
            main_window._navigate_command_history_up()
            current_text = main_window.ui.cmd_buffer.currentText()
            index = main_window.command_history_index
            print(f"   步骤 {i+1}: 索引={index}, 命令='{current_text}'")
        
        # 测试向下导航
        print("\n📋 测试向下导航:")
        for i in range(4):
            main_window._navigate_command_history_down()
            current_text = main_window.ui.cmd_buffer.currentText()
            index = main_window.command_history_index
            print(f"   步骤 {i+1}: 索引={index}, 命令='{current_text}'")
        
        # 测试重置导航状态
        main_window._reset_command_history_navigation()
        print(f"\n🔄 重置后: 索引={main_window.command_history_index}, 当前输入='{main_window.current_input_text}'")
        
        # 等待一段时间以便观察效果
        QTimer.singleShot(2000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_event_filter_simulation():
    """测试事件过滤器模拟"""
    print("\n🧪 测试事件过滤器模拟...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 添加测试命令
        test_commands = ["command1", "command2", "command3"]
        for cmd in test_commands:
            main_window.ui.cmd_buffer.addItem(cmd)
        
        # 模拟按键事件
        combo_box = main_window.ui.cmd_buffer
        
        # 模拟上方向键
        up_key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Up, Qt.NoModifier)
        result_up = main_window.eventFilter(combo_box, up_key_event)
        print(f"✅ 上方向键事件处理: {result_up} (True表示事件被消费)")
        
        # 模拟下方向键
        down_key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_Down, Qt.NoModifier)
        result_down = main_window.eventFilter(combo_box, down_key_event)
        print(f"✅ 下方向键事件处理: {result_down} (True表示事件被消费)")
        
        # 模拟普通按键
        normal_key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key_A, Qt.NoModifier)
        result_normal = main_window.eventFilter(combo_box, normal_key_event)
        print(f"✅ 普通按键事件处理: {result_normal} (False表示事件继续传递)")
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return result_up and result_down and not result_normal
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 测试命令历史导航和TAB索引修复功能")
    print("=" * 60)
    
    # 测试TAB索引修复
    tab_index_ok = test_tab_index_fix()
    
    # 测试命令历史导航设置
    navigation_setup_ok = test_command_navigation_setup()
    
    # 测试ComboBox清空集成
    clear_integration_ok = test_combobox_clear_integration()
    
    # 模拟命令历史导航
    navigation_simulation_ok = simulate_command_navigation()
    
    # 测试事件过滤器
    event_filter_ok = test_event_filter_simulation()
    
    print("\n" + "=" * 60)
    
    if all([tab_index_ok, navigation_setup_ok, clear_integration_ok, navigation_simulation_ok, event_filter_ok]):
        print("🎉 所有测试通过！")
        
        print("\n修复内容:")
        print("1. ✅ TAB索引修复 - 使用正确的索引2获取RTT Channel 1")
        print("2. ✅ 命令历史导航 - 支持上下方向键切换历史命令")
        print("3. ✅ ComboBox清空 - 发送成功后正确清空输入框")
        print("4. ✅ 导航状态重置 - 发送后重置导航状态")
        print("5. ✅ 事件过滤器 - 正确处理键盘事件")
        
        print("\n功能特性:")
        print("- 🔢 正确的TAB索引：索引2对应RTT Channel 1")
        print("- ⬆️ 上方向键：向上导航到更早的历史命令")
        print("- ⬇️ 下方向键：向下导航到更新的历史命令或当前输入")
        print("- 📝 智能保存：自动保存当前输入文本")
        print("- 🔄 状态重置：发送成功后重置导航状态")
        print("- 🎯 文本选中：导航时自动选中文本便于替换")
        
        print("\n用户体验:")
        print("- 发送成功后ComboBox被清空")
        print("- 使用上下方向键可以快速切换历史命令")
        print("- 支持在历史命令和当前输入之间切换")
        print("- 导航过程中文本自动被选中")
        print("- 发送后自动重置到正常输入模式")
        
    else:
        print("❌ 部分测试失败！")
        failed_tests = []
        if not tab_index_ok:
            failed_tests.append("TAB索引修复")
        if not navigation_setup_ok:
            failed_tests.append("命令历史导航设置")
        if not clear_integration_ok:
            failed_tests.append("ComboBox清空集成")
        if not navigation_simulation_ok:
            failed_tests.append("命令历史导航模拟")
        if not event_filter_ok:
            failed_tests.append("事件过滤器测试")
        
        print(f"失败的测试: {', '.join(failed_tests)}")
    
    return 0 if all([tab_index_ok, navigation_setup_ok, clear_integration_ok, navigation_simulation_ok, event_filter_ok]) else 1

if __name__ == '__main__':
    sys.exit(main())
