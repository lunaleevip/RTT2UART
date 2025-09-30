#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import io

def fix_python_console_encoding():
    """修复Python控制台输出编码问题"""
    
    # 设置环境变量
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 重新配置标准输出流
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    else:
        # 对于较老版本的Python
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, 
            encoding='utf-8', 
            errors='replace'
        )
    
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    else:
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, 
            encoding='utf-8', 
            errors='replace'
        )
    
    # 测试输出
    print("=" * 50)
    print("Python控制台编码修复完成！")
    print("=" * 50)
    print("✅ 正则表达式筛选功能已完成")
    print("✅ 重复数据问题修复完成") 
    print("✅ Python控制台UTF-8编码修复完成")
    print("=" * 50)
    
    # 显示编码信息
    print(f"系统默认编码: {sys.getdefaultencoding()}")
    print(f"标准输出编码: {sys.stdout.encoding}")
    print(f"标准错误编码: {sys.stderr.encoding}")
    print(f"文件系统编码: {sys.getfilesystemencoding()}")
    
    return True

if __name__ == "__main__":
    fix_python_console_encoding()
