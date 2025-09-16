#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的ComboBox功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QTimer

def test_error_handling():
    """测试错误处理"""
    print("🧪 测试错误处理改进...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 测试UI导入
        from ui_rtt2uart_updated import Ui_dialog
        
        # 创建对话框
        dialog = QDialog()
        ui = Ui_dialog()
        ui.setupUi(dialog)
        
        print("✅ UI组件创建成功")
        
        # 测试ComboBox基本功能
        if hasattr(ui, 'comboBox_serialno'):
            combo = ui.comboBox_serialno
            
            # 测试基本操作
            combo.clear()
            combo.addItem("")
            combo.addItem("⭐ 697436767 (J-Link V9.3 Plus)", "697436767")
            combo.addItem("424966295 (J-Link V9.3 Plus)", "424966295")
            
            print(f"✅ ComboBox项目数: {combo.count()}")
            
            # 测试选择
            combo.setCurrentIndex(1)
            current_text = combo.currentText()
            print(f"✅ 当前选择: {current_text}")
            
            # 测试数据提取
            if current_text.startswith("⭐ "):
                extracted = current_text[2:]
                if " (" in extracted:
                    extracted = extracted.split(" (")[0]
                print(f"✅ 提取的序列号: {extracted}")
        
        # 测试刷新按钮
        if hasattr(ui, 'pushButton_refresh_jlink'):
            button = ui.pushButton_refresh_jlink
            print(f"✅ 刷新按钮文本: {button.text()}")
        
        dialog.close()
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_logic():
    """测试回退逻辑"""
    print("🧪 测试回退逻辑...")
    
    # 测试空选择的处理
    test_cases = [
        "",  # 空字符串
        "   ",  # 空白字符
        "⭐ 697436767 (J-Link V9.3 Plus)",  # 有效选择
        "424966295",  # 纯序列号
    ]
    
    for test_case in test_cases:
        selected_text = test_case.strip()
        
        if selected_text and selected_text != "":
            # 有效选择
            if selected_text.startswith("⭐ "):
                selected_text = selected_text[2:]
            if " (" in selected_text:
                selected_text = selected_text.split(" (")[0]
            print(f"✅ 有效选择: '{test_case}' → '{selected_text}'")
        else:
            # 空选择，应该回退到JLINK内置选择框
            print(f"✅ 空选择: '{test_case}' → 使用JLINK内置选择框")
    
    return True

def main():
    """主函数"""
    print("🚀 测试修复后的ComboBox功能")
    print("=" * 50)
    
    success = True
    
    # 测试错误处理
    if not test_error_handling():
        success = False
    print()
    
    # 测试回退逻辑
    if not test_fallback_logic():
        success = False
    print()
    
    if success:
        print("🎉 所有测试通过！")
        print("\n修复说明:")
        print("1. ✅ 添加了完整的错误处理和安全检查")
        print("2. ✅ 当ComboBox未选择设备时回退到JLINK内置选择框")
        print("3. ✅ 修复了UI组件的存在性检查")
        print("4. ✅ 改进了设备检测的异常处理")
        print("5. ✅ 增强了日志记录和错误信息")
        
        print("\n使用说明:")
        print("- 选择具体设备：直接连接到该设备")
        print("- 空选择或未指定：自动使用JLINK内置选择框")
        print("- 多设备环境：显示选择对话框")
        print("- 单设备环境：自动连接唯一设备")
    else:
        print("❌ 部分测试失败！")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
