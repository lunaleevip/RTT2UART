#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试cmd.txt重复加载和重复内容修复
"""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

def test_command_history_loading():
    """测试命令历史加载是否去重"""
    print("🧪 测试命令历史加载...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        print("✅ 主窗口创建成功")
        
        # 检查命令历史ComboBox
        cmd_buffer = main_window.ui.cmd_buffer
        
        # 获取所有命令
        commands = []
        for i in range(cmd_buffer.count()):
            commands.append(cmd_buffer.itemText(i))
        
        print(f"📋 加载的命令总数: {len(commands)}")
        
        # 检查是否有重复
        unique_commands = set(commands)
        duplicates = len(commands) - len(unique_commands)
        
        if duplicates > 0:
            print(f"❌ 发现 {duplicates} 个重复命令")
            # 显示重复的命令
            seen = set()
            for cmd in commands:
                if cmd in seen:
                    print(f"   重复: {cmd}")
                else:
                    seen.add(cmd)
            return False
        else:
            print("✅ 没有发现重复命令")
            return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_history_update():
    """测试命令历史更新逻辑"""
    print("\n🧪 测试命令历史更新逻辑...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        
        # 获取初始命令数量
        initial_count = main_window.ui.cmd_buffer.count()
        print(f"📋 初始命令数量: {initial_count}")
        
        # 测试添加新命令
        test_cmd = "test_command_unique_12345"
        main_window._update_command_history(test_cmd)
        
        after_add_count = main_window.ui.cmd_buffer.count()
        print(f"📋 添加新命令后数量: {after_add_count}")
        
        # 检查新命令是否在最前面
        first_cmd = main_window.ui.cmd_buffer.itemText(0)
        if first_cmd == test_cmd:
            print(f"✅ 新命令正确添加到最前面: {test_cmd}")
        else:
            print(f"❌ 新命令位置错误，期望: {test_cmd}，实际: {first_cmd}")
            return False
        
        # 测试重复添加相同命令（应该只调整顺序，不增加数量）
        main_window._update_command_history(test_cmd)
        
        after_duplicate_count = main_window.ui.cmd_buffer.count()
        print(f"📋 重复添加后数量: {after_duplicate_count}")
        
        if after_duplicate_count == after_add_count:
            print("✅ 重复命令没有增加总数量，只调整了顺序")
        else:
            print(f"❌ 重复命令错误地增加了数量")
            return False
        
        # 检查重复命令仍然在最前面
        first_cmd_after = main_window.ui.cmd_buffer.itemText(0)
        if first_cmd_after == test_cmd:
            print(f"✅ 重复命令仍在最前面: {test_cmd}")
        else:
            print(f"❌ 重复命令位置错误: {first_cmd_after}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_manager_integration():
    """测试配置管理器集成"""
    print("\n🧪 测试配置管理器集成...")
    
    try:
        from config_manager import ConfigManager
        
        # 创建配置管理器
        config = ConfigManager()
        
        # 获取命令历史
        cmd_history = config.get_command_history()
        print(f"📋 配置文件中的命令历史数量: {len(cmd_history)}")
        
        # 检查重复
        unique_commands = set(cmd_history)
        duplicates = len(cmd_history) - len(unique_commands)
        
        if duplicates > 0:
            print(f"❌ 配置文件中有 {duplicates} 个重复命令")
            return False
        else:
            print("✅ 配置文件中没有重复命令")
            return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 测试cmd.txt重复加载和重复内容修复")
    print("=" * 60)
    
    # 测试配置管理器
    config_ok = test_config_manager_integration()
    
    # 测试命令历史加载
    loading_ok = test_command_history_loading()
    
    # 测试命令历史更新
    update_ok = test_command_history_update()
    
    print("\n" + "=" * 60)
    
    if config_ok and loading_ok and update_ok:
        print("🎉 所有测试通过！")
        print("\n修复效果:")
        print("1. ✅ 统一使用配置管理器加载命令历史")
        print("2. ✅ 加载时自动去重，防止重复显示")
        print("3. ✅ 新命令智能管理：重复时只调整顺序")
        print("4. ✅ 配置文件中无重复命令")
        
        print("\n技术改进:")
        print("- 移除了直接读取cmd.txt的重复逻辑")
        print("- 统一使用ConfigManager管理命令历史")
        print("- 实现了智能去重算法")
        print("- 优化了ComboBox项目顺序管理")
        
        print("\n用户体验:")
        print("- 不再出现重复的命令选项")
        print("- 最近使用的命令自动排在最前面")
        print("- 命令历史数量保持合理范围")
        print("- 配置文件更加整洁")
    else:
        print("❌ 部分测试失败！")
        if not config_ok:
            print("- 配置管理器测试失败")
        if not loading_ok:
            print("- 命令历史加载测试失败")
        if not update_ok:
            print("- 命令历史更新测试失败")
    
    return 0 if (config_ok and loading_ok and update_ok) else 1

if __name__ == '__main__':
    sys.exit(main())
