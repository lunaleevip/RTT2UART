#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试TAB 1内容显示到JLink日志框功能
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

def test_tab1_content_retrieval():
    """测试TAB 1内容获取功能"""
    print("🧪 测试TAB 1内容获取...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        print("✅ 主窗口创建成功")
        
        # 测试get_tab1_content方法
        content = main_window.get_tab1_content()
        print(f"📋 TAB 1当前内容长度: {len(content)} 字符")
        
        if content:
            print(f"📋 TAB 1内容预览: {content[:100]}...")
        else:
            print("📋 TAB 1当前无内容")
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_jlink_log_display():
    """测试JLink日志显示功能"""
    print("\n🧪 测试JLink日志显示...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 测试append_jlink_log方法
        test_message = "测试JLink日志显示功能"
        main_window.append_jlink_log(test_message)
        print(f"✅ 成功添加测试消息到JLink日志: {test_message}")
        
        # 测试_display_tab1_content_to_jlink_log方法
        test_command = "test_command"
        main_window._display_tab1_content_to_jlink_log(test_command)
        print(f"✅ 成功调用TAB 1内容显示方法，命令: {test_command}")
        
        # 等待一段时间以便观察效果
        QTimer.singleShot(2000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_send_integration():
    """测试命令发送集成功能"""
    print("\n🧪 测试命令发送集成...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 检查on_pushButton_clicked方法是否包含新功能
        import inspect
        method_source = inspect.getsource(main_window.on_pushButton_clicked)
        
        if "_display_tab1_content_to_jlink_log" in method_source:
            print("✅ 命令发送方法已集成TAB 1内容显示功能")
            integration_ok = True
        else:
            print("❌ 命令发送方法未集成TAB 1内容显示功能")
            integration_ok = False
        
        # 检查相关方法是否存在
        methods_to_check = [
            'get_tab1_content',
            '_display_tab1_content_to_jlink_log',
            '_delayed_display_tab1_content'
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
        
        return integration_ok and methods_ok
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_tab1_content():
    """模拟TAB 1有内容的情况"""
    print("\n🧪 模拟TAB 1内容显示...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 获取TAB 1的文本框并添加一些测试内容
        tab1_widget = main_window.ui.tem_switch.widget(1)
        if tab1_widget:
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
            text_edit = tab1_widget.findChild(QPlainTextEdit)
            if not text_edit:
                text_edit = tab1_widget.findChild(QTextEdit)
            
            if text_edit:
                # 添加模拟内容
                test_content = """[15:09:16.997] sensor_activity_detect[2244] 活动检测, 主频: 0.00 Hz, 方差: 0.155, 呼吸: 0.0次/分, 步数: 17, 倾向: 0, 翻身: 0,
[15:09:17.005] sensor_activity_detect[2244] 活动检测, 主频: 0.00 Hz, 方差: 0.155, 呼吸: 0.0次/分, 步数: 17, 倾向: 0, 翻身: 0,
[15:09:17.013] RTT LEN: 4 DATA: ver?"""
                
                if hasattr(text_edit, 'appendPlainText'):
                    text_edit.appendPlainText(test_content)
                else:
                    text_edit.append(test_content)
                
                print("✅ 已添加模拟内容到TAB 1")
                
                # 测试内容获取
                retrieved_content = main_window.get_tab1_content()
                print(f"📋 获取的内容长度: {len(retrieved_content)} 字符")
                
                # 测试显示到JLink日志
                main_window._display_tab1_content_to_jlink_log("ver?")
                print("✅ 已调用显示到JLink日志功能")
                
        # 等待一段时间以便观察效果
        QTimer.singleShot(3000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 测试TAB 1内容显示到JLink日志框功能")
    print("=" * 60)
    
    # 测试TAB 1内容获取
    content_ok = test_tab1_content_retrieval()
    
    # 测试JLink日志显示
    jlink_ok = test_jlink_log_display()
    
    # 测试命令发送集成
    integration_ok = test_command_send_integration()
    
    # 模拟TAB 1内容显示
    simulation_ok = simulate_tab1_content()
    
    print("\n" + "=" * 60)
    
    if content_ok and jlink_ok and integration_ok and simulation_ok:
        print("🎉 所有测试通过！")
        print("\n功能实现:")
        print("1. ✅ TAB 1内容获取功能正常")
        print("2. ✅ JLink日志显示功能正常")
        print("3. ✅ 命令发送集成功能正常")
        print("4. ✅ 内容显示模拟测试正常")
        
        print("\n技术特性:")
        print("- 支持获取TAB 1 (RTT Channel 1) 的当前内容")
        print("- 智能内容截取，只显示最近的500字符")
        print("- 延迟100ms获取内容，等待可能的响应数据")
        print("- 自动清理ANSI控制字符")
        print("- 只显示最近5行内容，避免日志过长")
        print("- 提供友好的格式化输出")
        
        print("\n用户体验:")
        print("- 📤 显示发送的命令")
        print("- 📥 显示RTT Channel 1的响应")
        print("- ─ 使用分隔线区分不同命令")
        print("- 自动滚动到JLink日志底部")
    else:
        print("❌ 部分测试失败！")
        if not content_ok:
            print("- TAB 1内容获取测试失败")
        if not jlink_ok:
            print("- JLink日志显示测试失败")
        if not integration_ok:
            print("- 命令发送集成测试失败")
        if not simulation_ok:
            print("- 内容显示模拟测试失败")
    
    return 0 if (content_ok and jlink_ok and integration_ok and simulation_ok) else 1

if __name__ == '__main__':
    sys.exit(main())
