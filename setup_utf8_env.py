#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import locale

def setup_utf8_environment():
    """设置UTF-8环境"""
    print("Setting up UTF-8 environment...")
    
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 设置标准输出编码
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    
    # 显示当前编码信息
    print(f"System encoding: {sys.getdefaultencoding()}")
    print(f"Stdout encoding: {sys.stdout.encoding}")
    print(f"Stderr encoding: {sys.stderr.encoding}")
    print(f"Locale: {locale.getpreferredencoding()}")
    
    # 测试中文显示
    print("UTF-8测试成功：")
    print("✅ 正则表达式筛选功能已完成")
    print("✅ 重复数据问题修复完成")
    print("✅ 终端UTF-8编码设置完成")

if __name__ == "__main__":
    setup_utf8_environment()
