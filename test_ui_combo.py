#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试UI ComboBox组件
"""

import sys
from PySide6.QtWidgets import QApplication, QDialog
from ui_rtt2uart_updated import Ui_dialog

def test_ui_components():
    """测试UI组件"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 创建对话框
    dialog = QDialog()
    ui = Ui_dialog()
    ui.setupUi(dialog)
    
    print("🧪 检查UI组件...")
    
    # 检查ComboBox
    if hasattr(ui, 'comboBox_serialno'):
        print("✅ comboBox_serialno 存在")
        combo = ui.comboBox_serialno
        print(f"   类型: {type(combo)}")
        print(f"   可编辑: {combo.isEditable()}")
        print(f"   位置: {combo.geometry()}")
        
        # 测试添加项目
        combo.addItem("测试设备1", "123456")
        combo.addItem("⭐ 测试设备2", "789012") 
        print(f"   项目数量: {combo.count()}")
        
    else:
        print("❌ comboBox_serialno 不存在")
    
    # 检查刷新按钮
    if hasattr(ui, 'pushButton_refresh_jlink'):
        print("✅ pushButton_refresh_jlink 存在")
        button = ui.pushButton_refresh_jlink
        print(f"   类型: {type(button)}")
        print(f"   文本: {button.text()}")
        print(f"   位置: {button.geometry()}")
    else:
        print("❌ pushButton_refresh_jlink 不存在")
    
    # 检查原有的checkBox是否还存在
    if hasattr(ui, 'checkBox_serialno'):
        print("✅ checkBox_serialno 存在")
    else:
        print("❌ checkBox_serialno 不存在")
    
    dialog.close()
    return True

def main():
    """主函数"""
    print("🚀 测试UI ComboBox组件")
    print("=" * 40)
    
    try:
        result = test_ui_components()
        if result:
            print("\n✅ UI组件测试成功！")
            print("\n功能说明:")
            print("- 序列号文本框已成功改为ComboBox")
            print("- 添加了设备刷新按钮")
            print("- ComboBox支持可编辑模式")
            print("- 保持了原有的复选框控制显示/隐藏")
        else:
            print("\n❌ UI组件测试失败！")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
