#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动重构版本的RTT2UART
"""

import sys
import os

# 确保当前目录在Python路径中
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

# 导入并启动新版本
try:
    from new_main_window import main
    print("🚀 启动重构版 RTT2UART...")
    print("✨ 新特性:")
    print("   - 优雅的连接对话框")
    print("   - 统一的主窗口界面") 
    print("   - 更好的用户体验")
    print("   - 完整的菜单栏和状态栏")
    print("="*50)
    
    sys.exit(main())
    
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("💡 请确保虚拟环境已激活")
    sys.exit(1)
    
except Exception as e:
    print(f"💥 启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

