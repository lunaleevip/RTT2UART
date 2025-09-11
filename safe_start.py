#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全启动脚本
带详细错误信息和恢复机制的启动脚本
"""

import sys
import os
import traceback
import time

def check_environment():
    """检查运行环境"""
    print("🔍 检查运行环境...")
    
    # 检查Python版本
    print(f"  Python版本: {sys.version}")
    
    # 检查必要文件
    required_files = [
        'main_window.py',
        'rtt2uart.py', 
        'ui_rtt2uart.py',
        'ui_sel_device.py',
        'ui_xexunrtt.py',
        'resources_rc.py'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file} - 文件缺失")
            return False
    
    return True

def start_with_error_handling():
    """带错误处理的启动"""
    print("\n🚀 启动 RTT2UART...")
    
    try:
        # 导入必要模块
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        import main_window
        
        # 创建应用程序
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 设置应用程序属性
        app.setApplicationName("RTT2UART")
        app.setApplicationVersion("优化版")
        
        print("  ✅ 应用程序初始化完成")
        
        # 创建主窗口
        main_win = main_window.RTTMainWindow()
        print("  ✅ 主窗口创建完成")
        
        # 显示窗口
        main_win.show()
        print("  ✅ 界面显示完成")
        
        print("\n🎉 程序启动成功！")
        print("💡 如果程序运行缓慢，可以使用性能监控工具:")
        print("   python performance_monitor.py")
        
        # 运行应用程序
        return app.exec()
        
    except ImportError as e:
        print(f"\n❌ 模块导入错误: {e}")
        print("💡 请确保虚拟环境已激活并安装了所有依赖")
        print("   运行: pip install -r requirements.txt")
        return 1
        
    except Exception as e:
        print(f"\n💥 启动失败: {e}")
        print("\n📋 详细错误信息:")
        traceback.print_exc()
        
        print(f"\n🔧 可能的解决方案:")
        print(f"1. 检查是否有其他RTT2UART实例在运行")
        print(f"2. 检查JLink驱动是否正确安装")
        print(f"3. 检查虚拟环境是否正确激活")
        print(f"4. 尝试重新安装依赖包")
        
        return 1

def main():
    """主函数"""
    print("🛠️  RTT2UART 安全启动器")
    print("="*50)
    
    # 检查环境
    if not check_environment():
        print("\n❌ 环境检查失败")
        return 1
    
    print("  ✅ 环境检查通过")
    
    # 尝试启动
    return start_with_error_handling()

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 用户取消启动")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 未预期的错误: {e}")
        traceback.print_exc()
        sys.exit(1)

