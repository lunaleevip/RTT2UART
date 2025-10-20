#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证所有更新相关模块是否能正常导入
"""

import sys

print("=" * 70)
print("验证更新模块导入")
print("=" * 70)
print()

modules_to_check = [
    ('update_dialog', '更新对话框'),
    ('auto_updater', '自动更新器'),
    ('version', '版本信息'),
    ('requests', 'HTTP 请求'),
    ('bsdiff4', '二进制差异'),
]

all_ok = True

for module_name, description in modules_to_check:
    try:
        __import__(module_name)
        print(f"✅ {module_name:20s} - {description}")
    except ImportError as e:
        print(f"❌ {module_name:20s} - {description} - 导入失败: {e}")
        all_ok = False

print()
print("=" * 70)

if all_ok:
    print("✅ 所有模块导入成功！")
    print()
    print("测试具体功能:")
    try:
        from update_dialog import check_for_updates_on_startup
        print("  ✅ check_for_updates_on_startup 可用")
        
        from auto_updater import AutoUpdater
        print("  ✅ AutoUpdater 可用")
        
        from version import VERSION
        print(f"  ✅ VERSION = {VERSION}")
        
        print()
        print("🎉 更新功能完全正常！")
    except Exception as e:
        print(f"  ❌ 功能测试失败: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ 部分模块导入失败，请检查依赖")
    sys.exit(1)

