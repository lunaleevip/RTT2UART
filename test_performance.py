#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的性能测试启动脚本
"""

import sys
import os
from PySide6.QtWidgets import QApplication

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from performance_test import PerformanceTestWidget

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用图标和名称
    app.setApplicationName("RTT性能测试工具")
    
    # 创建测试窗口
    test_widget = PerformanceTestWidget()
    test_widget.log_message("独立性能测试模式启动")
    test_widget.log_message("警告：此模式无法连接到主程序，仅用于界面测试")
    test_widget.show()
    
    sys.exit(app.exec())
