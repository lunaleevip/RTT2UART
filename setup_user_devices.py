#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速设置用户自定义设备列表
"""

import os
import sys
import shutil

def get_config_dir():
    """获取配置目录"""
    if sys.platform == "darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/XexunRTT")
    elif sys.platform == "win32":  # Windows
        return os.path.expanduser("~/AppData/Roaming/XexunRTT")
    else:  # Linux
        return os.path.expanduser("~/.config/XexunRTT")

def setup_user_devices():
    """设置用户自定义设备列表"""
    
    # 获取配置目录
    config_dir = get_config_dir()
    user_devices_file = os.path.join(config_dir, 'JLinkDevices.xml')
    example_file = 'JLinkDevices_user_example.xml'
    
    print("=" * 60)
    print("  XexunRTT - 用户自定义设备设置")
    print("=" * 60)
    print()
    
    # 检查示例文件是否存在
    if not os.path.exists(example_file):
        print(f"❌ 示例文件不存在: {example_file}")
        print(f"   请确保在项目根目录运行此脚本")
        return False
    
    # 创建配置目录
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
        print(f"✅ 创建配置目录: {config_dir}")
    else:
        print(f"📁 配置目录: {config_dir}")
    
    # 检查是否已存在用户设备文件
    if os.path.exists(user_devices_file):
        print(f"⚠  用户设备文件已存在: {user_devices_file}")
        
        # 统计现有设备数量
        try:
            with open(user_devices_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                device_count = content.count('<DeviceInfo') + content.count('<ChipInfo')
                print(f"   当前包含约 {device_count} 个自定义设备")
        except:
            pass
        
        # 询问是否覆盖
        choice = input("\n是否覆盖为示例文件? (y/N): ").strip().lower()
        if choice != 'y':
            print("\n✅ 保留现有文件，未做修改")
            print(f"\n提示: 您可以手动编辑文件添加设备:")
            print(f"      {user_devices_file}")
            return True
    
    # 复制示例文件
    try:
        shutil.copy2(example_file, user_devices_file)
        print(f"\n✅ 已复制示例文件到:")
        print(f"   {user_devices_file}")
        
        # 统计示例设备数量
        with open(user_devices_file, 'r', encoding='utf-8') as f:
            content = f.read()
            device_count = content.count('<DeviceInfo') + content.count('<ChipInfo')
            print(f"\n📝 示例文件包含 {device_count} 个设备示例")
        
        print(f"\n" + "=" * 60)
        print("  后续步骤:")
        print("=" * 60)
        print(f"1. 编辑文件添加您的自定义设备:")
        print(f"   {user_devices_file}")
        print(f"")
        print(f"2. 参考示例格式定义设备属性:")
        print(f"   - Name: 设备名称（唯一）")
        print(f"   - WorkRAMStartAddr: RAM起始地址")
        print(f"   - WorkRAMSize: RAM大小")
        print(f"   - Core: 核心类型")
        print(f"")
        print(f"3. 保存文件后重启程序")
        print(f"")
        print(f"4. 查看日志确认设备已加载:")
        print(f"   👤 Found user-defined device database")
        print(f"   ✅ Database merge complete: Added X devices")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 复制文件失败: {e}")
        return False

if __name__ == '__main__':
    success = setup_user_devices()
    input("\n按回车键退出...")
    sys.exit(0 if success else 1)

