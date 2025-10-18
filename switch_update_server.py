#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新服务器切换工具
方便在测试和生产环境之间切换
"""

import sys
from pathlib import Path

CONFIG_FILE = Path("update_config.ini")

# 预设服务器
SERVERS = {
    "test": "http://127.0.0.1:8888",
    "production": "https://your-domain.com/xexunrtt/updates",
}


def show_current():
    """显示当前配置"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            for line in content.split('\n'):
                if line.strip().startswith('server='):
                    server = line.split('=', 1)[1].strip()
                    print(f"当前服务器: {server}")
                    
                    # 判断是哪个模式
                    if server == SERVERS['test']:
                        print("模式: 🧪 测试模式")
                    elif server == SERVERS['production']:
                        print("模式: 🚀 生产模式")
                    else:
                        print("模式: ⚙️  自定义")
                    return
    
    print("当前服务器: (未配置，将使用默认生产服务器)")
    print("模式: 🚀 生产模式 (默认)")


def switch_to_test():
    """切换到测试服务器"""
    content = f"""# XexunRTT 更新服务器配置
# 当前模式: 测试模式
# 服务器地址
server={SERVERS['test']}

# 说明:
# - 测试模式使用本地服务器 (127.0.0.1:8888)
# - 需要先运行 test_update_local.py 启动测试服务器
# - 切换到生产模式请运行: python switch_update_server.py production
"""
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 已切换到测试模式")
    print(f"   服务器: {SERVERS['test']}")
    print()
    print("📝 下一步:")
    print("   1. 运行 python test_update_local.py 启动测试服务器")
    print("   2. 运行主程序测试更新")


def switch_to_production():
    """切换到生产服务器"""
    content = f"""# XexunRTT 更新服务器配置
# 当前模式: 生产模式
# 服务器地址
server={SERVERS['production']}

# 说明:
# - 生产模式使用正式服务器
# - 确保服务器上已部署更新文件
# - 切换到测试模式请运行: python switch_update_server.py test
"""
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 已切换到生产模式")
    print(f"   服务器: {SERVERS['production']}")
    print()
    print("⚠️  注意:")
    print("   确保生产服务器上已部署更新文件")


def switch_to_custom(server_url):
    """切换到自定义服务器"""
    content = f"""# XexunRTT 更新服务器配置
# 当前模式: 自定义
# 服务器地址
server={server_url}

# 说明:
# - 使用自定义服务器地址
# - 切换到测试模式: python switch_update_server.py test
# - 切换到生产模式: python switch_update_server.py production
"""
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 已切换到自定义服务器")
    print(f"   服务器: {server_url}")


def remove_config():
    """删除配置文件"""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print("✅ 已删除配置文件")
        print("   将使用默认生产服务器")
    else:
        print("ℹ️  配置文件不存在")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("=" * 60)
        print("XexunRTT 更新服务器切换工具")
        print("=" * 60)
        print()
        show_current()
        print()
        print("使用方法:")
        print("  python switch_update_server.py test        - 切换到测试模式")
        print("  python switch_update_server.py production  - 切换到生产模式")
        print("  python switch_update_server.py custom <URL> - 使用自定义URL")
        print("  python switch_update_server.py remove      - 删除配置(使用默认)")
        print("  python switch_update_server.py show        - 显示当前配置")
        print()
        return 0
    
    command = sys.argv[1].lower()
    
    if command == 'test':
        switch_to_test()
    elif command == 'production' or command == 'prod':
        switch_to_production()
    elif command == 'custom':
        if len(sys.argv) < 3:
            print("❌ 错误: 请提供自定义服务器URL")
            print("   用法: python switch_update_server.py custom <URL>")
            return 1
        switch_to_custom(sys.argv[2])
    elif command == 'remove' or command == 'delete':
        remove_config()
    elif command == 'show':
        show_current()
    else:
        print(f"❌ 未知命令: {command}")
        print("   运行 'python switch_update_server.py' 查看帮助")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

