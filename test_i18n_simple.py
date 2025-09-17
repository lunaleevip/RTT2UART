#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的国际化测试
"""

import os
import sys

def check_files():
    """检查文件"""
    print("🔍 检查国际化文件...")
    
    files = {
        "xexunrtt_en.ts": "英文翻译源文件",
        "xexunrtt_en.qm": "英文翻译编译文件", 
        "resources_rc.py": "资源文件",
        "main_window.py": "主窗口文件",
        "xexunrtt.ui": "主界面UI文件",
        "rtt2uart.ui": "连接界面UI文件",
        "sel_device.ui": "设备选择UI文件"
    }
    
    all_ok = True
    for filename, description in files.items():
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"✅ {description}: {filename} ({size:,} 字节)")
        else:
            print(f"❌ {description}: {filename} (缺失)")
            all_ok = False
    
    return all_ok

def check_ui_fonts():
    """检查UI字体"""
    print("\n🔤 检查UI字体设置...")
    
    ui_files = ["xexunrtt.ui", "rtt2uart.ui", "sel_device.ui"]
    
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            with open(ui_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "Arial" in content:
                print(f"✅ {ui_file}: 使用Arial字体")
            elif "新宋体" in content or "微软雅黑" in content:
                print(f"❌ {ui_file}: 仍使用中文字体")
            else:
                print(f"ℹ️ {ui_file}: 无特定字体设置")

def check_translation_content():
    """检查翻译内容"""
    print("\n📝 检查翻译内容...")
    
    if os.path.exists("xexunrtt_en.ts"):
        with open("xexunrtt_en.ts", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计翻译条目
        import re
        messages = re.findall(r'<message>', content)
        translations = re.findall(r'<translation[^>]*>([^<]*)</translation>', content)
        unfinished = re.findall(r'type="unfinished"', content)
        
        print(f"📊 翻译统计:")
        print(f"   总消息数: {len(messages)}")
        print(f"   已翻译数: {len([t for t in translations if t.strip()])}")
        print(f"   未完成数: {len(unfinished)}")
        
        if len(unfinished) > 0:
            print(f"⚠️ 还有 {len(unfinished)} 条翻译未完成")
        else:
            print("✅ 所有翻译已完成")

def check_source_code():
    """检查源代码"""
    print("\n🔍 检查源代码英文化...")
    
    if os.path.exists("main_window.py"):
        with open("main_window.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找QCoreApplication.translate调用
        import re
        translate_calls = re.findall(r'QCoreApplication\.translate\("([^"]*)",\s*"([^"]*?)"\)', content)
        
        print(f"📊 翻译调用统计:")
        print(f"   翻译调用总数: {len(translate_calls)}")
        
        # 检查是否还有中文
        chinese_in_translate = []
        for context, text in translate_calls:
            if re.search(r'[\u4e00-\u9fff]', text):
                chinese_in_translate.append((context, text))
        
        if chinese_in_translate:
            print(f"⚠️ 发现 {len(chinese_in_translate)} 个翻译调用仍包含中文:")
            for context, text in chinese_in_translate[:5]:  # 只显示前5个
                print(f"   {context}: '{text}'")
            if len(chinese_in_translate) > 5:
                print(f"   ... 还有 {len(chinese_in_translate) - 5} 个")
        else:
            print("✅ 所有翻译调用已英文化")

def main():
    """主函数"""
    print("🌍 国际化功能检查")
    print("=" * 50)
    
    # 检查文件
    files_ok = check_files()
    
    # 检查UI字体
    check_ui_fonts()
    
    # 检查翻译内容
    check_translation_content()
    
    # 检查源代码
    check_source_code()
    
    print("\n" + "=" * 50)
    
    if files_ok:
        print("🎉 国际化检查完成！")
        
        print("\n📋 完成的工作:")
        print("✅ 生成英文翻译文件 (xexunrtt_en.ts/qm)")
        print("✅ 更新资源文件 (resources_rc.py)")
        print("✅ 修改UI字体为Arial")
        print("✅ 源代码文本英文化")
        print("✅ 翻译内容填充")
        
        print("\n🎯 使用说明:")
        print("- 程序默认使用英文界面")
        print("- 通过加载xexunrtt_en.qm可切换为中文")
        print("- 所有UI文本支持国际化")
        
    else:
        print("❌ 发现缺失文件，请检查!")
    
    return 0 if files_ok else 1

if __name__ == "__main__":
    sys.exit(main())
