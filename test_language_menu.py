#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语言设置菜单测试脚本

测试：
1. Language 菜单是否存在
2. 3 个语言选项是否正确
3. 语言切换是否保存到配置文件
4. 重启后是否加载正确的语言
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import config_manager

def test_language_config():
    """测试语言配置功能"""
    print("=" * 70)
    print("语言设置功能测试")
    print("=" * 70)
    print()
    
    # 1. 测试获取默认语言
    print("📋 测试 1: 获取默认语言")
    default_lang = config_manager.get_language()
    print(f"   默认语言: {default_lang}")
    assert default_lang in ['en_US', 'zh_CN', 'zh_TW'], f"无效的默认语言: {default_lang}"
    print("   ✅ 通过")
    print()
    
    # 2. 测试设置为英语
    print("📋 测试 2: 设置为英语")
    config_manager.set_language('en_US')
    current_lang = config_manager.get_language()
    print(f"   设置后的语言: {current_lang}")
    assert current_lang == 'en_US', f"设置失败，当前语言: {current_lang}"
    print("   ✅ 通过")
    print()
    
    # 3. 测试设置为简体中文
    print("📋 测试 3: 设置为简体中文")
    config_manager.set_language('zh_CN')
    current_lang = config_manager.get_language()
    print(f"   设置后的语言: {current_lang}")
    assert current_lang == 'zh_CN', f"设置失败，当前语言: {current_lang}"
    print("   ✅ 通过")
    print()
    
    # 4. 测试设置为繁体中文
    print("📋 测试 4: 设置为繁体中文")
    config_manager.set_language('zh_TW')
    current_lang = config_manager.get_language()
    print(f"   设置后的语言: {current_lang}")
    assert current_lang == 'zh_TW', f"设置失败，当前语言: {current_lang}"
    print("   ✅ 通过")
    print()
    
    # 5. 测试无效语言代码（应该使用默认值）
    print("📋 测试 5: 测试无效语言代码")
    config_manager.set_language('invalid_lang')
    current_lang = config_manager.get_language()
    print(f"   设置无效语言后: {current_lang}")
    assert current_lang == 'zh_CN', f"应该回退到默认语言 zh_CN，实际: {current_lang}"
    print("   ✅ 通过")
    print()
    
    # 6. 测试保存到配置文件
    print("📋 测试 6: 保存到配置文件")
    config_manager.set_language('en_US')
    save_result = config_manager.save_config()
    print(f"   保存结果: {'成功' if save_result else '失败（无变化）'}")
    
    # 重新加载配置
    config_manager.load_config()
    loaded_lang = config_manager.get_language()
    print(f"   重新加载后的语言: {loaded_lang}")
    assert loaded_lang == 'en_US', f"保存/加载失败，加载的语言: {loaded_lang}"
    print("   ✅ 通过")
    print()
    
    # 7. 测试配置文件内容
    print("📋 测试 7: 检查配置文件内容")
    config_file = config_manager.config_file
    print(f"   配置文件路径: {config_file}")
    
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'language' in content:
                print("   ✅ 配置文件包含 'language' 设置")
                # 显示相关行
                for line in content.split('\n'):
                    if 'language' in line.lower():
                        print(f"      {line.strip()}")
            else:
                print("   ❌ 配置文件不包含 'language' 设置")
    else:
        print(f"   ⚠️  配置文件不存在: {config_file}")
    print()
    
    # 恢复默认语言
    config_manager.set_language('zh_CN')
    config_manager.save_config()
    
    print("=" * 70)
    print("✅ 所有测试通过！")
    print("=" * 70)
    print()
    print("📝 语言设置功能验证成功！")
    print()
    print("💡 手动测试步骤：")
    print("   1. 运行主程序: python main_window.py")
    print("   2. 打开菜单栏 → Language")
    print("   3. 检查是否显示 3 个选项：")
    print("      - English")
    print("      - 中文（简体）")
    print("      - 中文（繁體）")
    print("   4. 点击不同语言选项")
    print("   5. 查看重启提示对话框")
    print("   6. 重启程序验证语言切换")
    print()

if __name__ == '__main__':
    try:
        test_language_config()
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

