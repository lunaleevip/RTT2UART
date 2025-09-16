#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新功能：JLINK设备预选和紧凑模式
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from config_manager import ConfigManager

def test_jlink_config():
    """测试JLINK配置功能"""
    print("🧪 测试JLINK设备配置功能...")
    
    # 创建配置管理器
    config = ConfigManager()
    
    # 测试偏好序列号功能
    test_serials = ["12345678", "87654321", "11223344"]
    
    print("添加偏好序列号...")
    for serial in test_serials:
        config.add_preferred_jlink_serial(serial)
    
    # 获取偏好序列号
    preferred = config.get_preferred_jlink_serials()
    print(f"偏好序列号列表: {preferred}")
    
    # 测试上次使用的序列号
    config.set_last_jlink_serial("12345678")
    last_serial = config.get_last_jlink_serial()
    print(f"上次使用的序列号: {last_serial}")
    
    # 测试自动选择设置
    config.set_auto_select_jlink(True)
    auto_select = config.get_auto_select_jlink()
    print(f"自动选择JLINK: {auto_select}")
    
    # 保存配置
    config.save_config()
    print("✅ JLINK配置测试完成")

def test_window_size():
    """测试窗口最小尺寸"""
    print("🧪 测试窗口最小尺寸功能...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        window = RTTMainWindow()
        
        # 测试最小尺寸
        min_size = window.minimumSize()
        print(f"最小窗口尺寸: {min_size.width()}x{min_size.height()}")
        
        # 测试紧凑模式
        print("测试紧凑模式...")
        window.compact_mode = False
        window._toggle_compact_mode()
        
        if window.compact_mode:
            print("✅ 紧凑模式激活成功")
            current_size = window.size()
            print(f"紧凑模式窗口尺寸: {current_size.width()}x{current_size.height()}")
        else:
            print("❌ 紧凑模式激活失败")
        
        # 退出紧凑模式
        window._toggle_compact_mode()
        if not window.compact_mode:
            print("✅ 退出紧凑模式成功")
        
        window.close()
        
    except Exception as e:
        print(f"❌ 窗口测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("✅ 窗口功能测试完成")

def main():
    """主测试函数"""
    print("🚀 开始测试XexunRTT v2.1新功能")
    print("=" * 50)
    
    # 测试配置功能
    test_jlink_config()
    print()
    
    # 测试窗口功能
    test_window_size()
    print()
    
    print("🎉 所有测试完成！")
    print("\n新功能说明:")
    print("1. JLINK设备预选：")
    print("   - 自动检测多个JLINK设备")
    print("   - 记住偏好的设备序列号")
    print("   - 支持自动选择上次使用的设备")
    print()
    print("2. 主窗口极小化：")
    print("   - 最小尺寸支持: 200x150")
    print("   - 紧凑模式快捷键: Ctrl+M")
    print("   - 右键菜单快速切换")
    print("   - 适合多设备同时调试")

if __name__ == '__main__':
    main()
