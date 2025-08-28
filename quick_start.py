#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT2UART 快速启动脚本
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox

def show_startup_info():
    """显示启动信息"""
    print("🚀 RTT2UART 快速启动")
    print("="*40)
    print("📦 可用版本:")
    print("  1. 重构版本 - 全新的用户体验")
    print("  2. 原版本   - 经典的界面风格")
    print("="*40)
    
    choice = input("请选择版本 (1=重构版, 2=原版, 回车=重构版): ").strip()
    
    if choice == "2":
        return "original"
    else:
        return "new"

def main():
    """主函数"""
    try:
        # 显示选择界面
        choice = show_startup_info()
        
        # 创建应用程序
        app = QApplication(sys.argv)
        
        if choice == "original":
            print("🔄 启动原版本...")
            try:
                from main_window import MainWindow
                window = MainWindow()
                window.show()
            except Exception as e:
                print(f"❌ 原版本启动失败: {e}")
                print("🔄 尝试启动重构版本...")
                from new_main_window import RTTMainWindow
                window = RTTMainWindow()
                window.show()
        else:
            print("✨ 启动重构版本...")
            try:
                from new_main_window import RTTMainWindow
                window = RTTMainWindow()
                window.show()
            except Exception as e:
                print(f"❌ 重构版本启动失败: {e}")
                print("🔄 尝试启动原版本...")
                from main_window import MainWindow
                window = MainWindow()
                window.show()
        
        print("🎉 程序启动成功!")
        return app.exec()
        
    except KeyboardInterrupt:
        print("\n🛑 用户取消启动")
        return 0
    except Exception as e:
        print(f"💥 启动失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

