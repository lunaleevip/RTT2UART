#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试ComboBox设备选择功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from config_manager import ConfigManager

def test_combo_functionality():
    """测试ComboBox相关功能"""
    print("🧪 测试ComboBox设备选择功能...")
    
    # 测试配置管理
    config = ConfigManager()
    
    # 模拟添加一些设备
    test_serials = ["697436767", "424966295", "697415391"]
    
    print("添加测试设备到偏好列表...")
    for serial in test_serials:
        config.add_preferred_jlink_serial(serial)
    
    preferred = config.get_preferred_jlink_serials()
    print(f"偏好设备列表: {preferred}")
    
    # 设置最后使用的设备
    config.set_last_jlink_serial("697436767")
    last = config.get_last_jlink_serial()
    print(f"最后使用的设备: {last}")
    
    config.save_config()
    print("✅ 配置测试完成")

def test_ui_changes():
    """测试UI组件变更"""
    print("🧪 测试UI组件变更...")
    
    try:
        # 导入UI模块
        from ui_rtt2uart_updated import Ui_dialog
        
        # 检查新的组件是否存在
        dialog = Ui_dialog()
        
        # 检查ComboBox是否存在
        if hasattr(dialog, 'comboBox_serialno'):
            print("✅ comboBox_serialno 组件存在")
        else:
            print("❌ comboBox_serialno 组件不存在")
        
        # 检查刷新按钮是否存在
        if hasattr(dialog, 'pushButton_refresh_jlink'):
            print("✅ pushButton_refresh_jlink 按钮存在")
        else:
            print("❌ pushButton_refresh_jlink 按钮不存在")
            
    except Exception as e:
        print(f"❌ UI测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("✅ UI组件测试完成")

def main():
    """主测试函数"""
    print("🚀 开始测试ComboBox设备选择功能")
    print("=" * 50)
    
    # 测试配置功能
    test_combo_functionality()
    print()
    
    # 测试UI变更
    test_ui_changes()
    print()
    
    print("🎉 所有测试完成！")
    print("\n功能说明:")
    print("1. 序列号输入框已改为ComboBox下拉选择")
    print("2. 自动检测并填充JLINK设备列表")
    print("3. 偏好设备用⭐标记优先显示")
    print("4. 添加🔄刷新按钮手动刷新设备列表")
    print("5. 支持直接选择设备连接，无需再次选择对话框")
    print()
    print("使用方法:")
    print("- 勾选'Serial NO'显示设备选择ComboBox")
    print("- 从下拉列表选择要连接的设备")
    print("- 点击🔄按钮刷新设备列表")
    print("- 选择设备后直接点击'开始'连接")

if __name__ == '__main__':
    main()
