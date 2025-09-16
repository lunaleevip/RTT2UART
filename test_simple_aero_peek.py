#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的Aero Peek修复测试
"""

import sys
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt

def test_dialog_flags():
    """测试对话框标志设置"""
    print("🧪 测试对话框窗口标志...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        # 直接导入对话框类进行测试
        from main_window import ConnectionDialog, DeviceSelectDialog, FindDialog
        
        # 创建对话框实例
        connection_dialog = ConnectionDialog()
        device_dialog = DeviceSelectDialog()
        find_dialog = FindDialog()
        
        # 检查标志
        dialogs = [
            ("ConnectionDialog", connection_dialog),
            ("DeviceSelectDialog", device_dialog), 
            ("FindDialog", find_dialog)
        ]
        
        all_correct = True
        
        for name, dialog in dialogs:
            flags = dialog.windowFlags()
            has_tool = bool(flags & Qt.Tool)
            has_close = bool(flags & Qt.WindowCloseButtonHint)
            has_system = bool(flags & Qt.WindowSystemMenuHint)
            
            print(f"📋 {name}:")
            print(f"   Tool (防Aero Peek): {has_tool}")
            print(f"   CloseButtonHint: {has_close}")
            print(f"   SystemMenuHint: {has_system}")
            
            # 检查是否正确设置
            if not (has_tool and has_close and has_system):
                print(f"   ❌ 标志设置不正确")
                all_correct = False
            else:
                print(f"   ✅ 标志设置正确")
            print()
        
        return all_correct
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 简单Aero Peek修复测试")
    print("=" * 40)
    
    success = test_dialog_flags()
    
    if success:
        print("🎉 所有对话框标志设置正确！")
        print("\n修复效果:")
        print("- ✅ 所有对话框都设置了Tool标志")
        print("- ✅ 所有对话框都保留了关闭按钮")
        print("- ✅ 所有对话框都保留了系统菜单")
        print("- ✅ 对话框不会在任务栏Aero Peek中显示")
    else:
        print("❌ 部分对话框标志设置不正确")
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
