#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 email 和 requests 相关的所有依赖模块
"""

print("=" * 70)
print("检查 requests/email 依赖链")
print("=" * 70)
print()

# requests 的完整依赖链
dependencies = {
    'requests': [
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
    ],
    'urllib3': [
        'email',
        'http.client',
    ],
    'email': [
        'email.parser',
        'email.feedparser',
        'email._policybase',
        'email.header',
        'email.charset',
        'email.encoders',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'email.utils',
        'email.message',
    ],
    'email.charset': [
        'quopri',
    ],
    'email.encoders': [
        'base64',
        'quopri',
    ],
    'email.utils': [
        'calendar',  # ← email.utils 需要！
    ],
    'http.client': [
        'email.parser',
        'email.message',
    ],
}

all_ok = True
missing = []

print("🔍 检查依赖模块:")
print()

def check_module(name, indent=0):
    """递归检查模块及其依赖"""
    global all_ok, missing
    
    prefix = "  " * indent
    try:
        __import__(name)
        print(f"{prefix}✅ {name}")
        
        # 检查子依赖
        if name in dependencies:
            for dep in dependencies[name]:
                check_module(dep, indent + 1)
        
        return True
    except ImportError as e:
        print(f"{prefix}❌ {name} - {e}")
        all_ok = False
        missing.append(name)
        return False

# 从顶层开始检查
check_module('requests')

print()
print("=" * 70)

if all_ok:
    print("✅ 所有依赖模块都可用！")
    print()
    print("requests 可以正常使用")
else:
    print("❌ 缺少以下模块:")
    for mod in missing:
        print(f"  - {mod}")
    print()
    print("💡 修复方法:")
    print("   在 XexunRTT_onefile_v2_2.spec 的 excludes 中")
    print("   注释掉这些模块（不要排除它们）")
    print()
    
    import sys
    sys.exit(1)

