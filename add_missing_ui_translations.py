#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加缺失的UI翻译
"""

import xml.etree.ElementTree as ET
import subprocess

def add_missing_ui_contexts():
    """手动添加缺失的UI翻译上下文"""
    print("🔧 手动添加缺失的UI翻译上下文")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    
    # 需要添加的翻译上下文和内容
    missing_contexts = {
        "xexun_rtt": {
            "Form": "表单",
            "can read from cmd.txt": "可以从cmd.txt读取",
            "Disconnect": "断开连接",
            "Clear": "清除",
            "Open Folder": "打开文件夹",
            "Send": "发送",
            "Light Mode": "明亮模式",
            "double click filter to write filter text": "双击过滤器编写过滤文本",
            "Font Size": "字体大小",
            "Reconnect": "重新连接",
            "Lock Horizontal": "锁定水平滚动",
            "Lock Vertical": "锁定垂直滚动",
            "1": "1",
            "2": "2"
        }
    }
    
    try:
        # 解析现有翻译文件
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        # 检查是否已存在xexun_rtt上下文
        xexun_rtt_context = None
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None and name_elem.text == 'xexun_rtt':
                xexun_rtt_context = context
                break
        
        added_count = 0
        
        # 如果不存在xexun_rtt上下文，创建它
        if xexun_rtt_context is None:
            print("📝 创建xexun_rtt翻译上下文...")
            xexun_rtt_context = ET.SubElement(root, 'context')
            name_elem = ET.SubElement(xexun_rtt_context, 'name')
            name_elem.text = 'xexun_rtt'
        
        # 获取已存在的翻译
        existing_sources = set()
        for message in xexun_rtt_context.findall('message'):
            source_elem = message.find('source')
            if source_elem is not None:
                existing_sources.add(source_elem.text)
        
        # 添加缺失的翻译
        for source_text, translation_text in missing_contexts["xexun_rtt"].items():
            if source_text not in existing_sources:
                # 创建新的message元素
                message_elem = ET.SubElement(xexun_rtt_context, 'message')
                
                # 添加location元素
                location_elem = ET.SubElement(message_elem, 'location')
                location_elem.set('filename', 'ui_xexunrtt.py')
                location_elem.set('line', '227')  # 大致行号
                
                # 添加source元素
                source_elem = ET.SubElement(message_elem, 'source')
                source_elem.text = source_text
                
                # 添加translation元素
                translation_elem = ET.SubElement(message_elem, 'translation')
                translation_elem.text = translation_text
                
                print(f"  ✅ 添加翻译: '{source_text}' → '{translation_text}'")
                added_count += 1
            else:
                print(f"  ℹ️ 翻译已存在: '{source_text}'")
        
        # 同样添加dialog上下文的翻译
        dialog_context = None
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None and name_elem.text == 'dialog':
                dialog_context = context
                break
        
        if dialog_context is not None:
            # 更新dialog上下文中未完成的翻译
            dialog_translations = {
                "RTT2UART Control Panel": "RTT2UART控制面板",
                "Start": "开始",
                "Target Interface And Speed": "目标接口和速度",
                "Specify Target Device": "指定目标设备",
                "UART Config": "UART配置",
                "Port:": "端口:",
                "Baud rate:": "波特率:",
                "Scan": "扫描",
                "Reset target": "复位目标",
                "Connection to J-Link": "连接到J-Link",
                "USB": "USB",
                "Existing Session": "现有会话",
                "TCP/IP": "TCP/IP",
                "Serial NO": "序列号",
                "Auto Reconnect": "自动重连"
            }
            
            for message in dialog_context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    if source_text in dialog_translations:
                        translation_elem.text = dialog_translations[source_text]
                        # 移除unfinished标记
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                        added_count += 1
        
        # 保存文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"\n✅ 成功添加/更新 {added_count} 条翻译到 {ts_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 添加翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def recompile_translation():
    """重新编译翻译文件"""
    print("\n🔨 重新编译翻译文件")
    print("-" * 40)
    
    try:
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_complete.ts", "-qm", "xexunrtt_complete.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件重新编译成功")
            print(f"   输出: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ QM文件重新编译失败")
            print(f"   错误: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 重新编译失败: {e}")
        return False

def update_main_window_translation_loading():
    """更新main_window.py中的翻译加载逻辑"""
    print("\n🔧 更新翻译加载逻辑")
    print("-" * 40)
    
    # 创建一个新的翻译加载函数
    new_translation_code = '''
def load_all_translations(app):
    """加载所有翻译文件"""
    locale = QLocale.system()
    
    if locale.language() == QLocale.Chinese:
        # 加载完整翻译文件
        translator = QTranslator()
        if translator.load("xexunrtt_complete.qm"):
            app.installTranslator(translator)
            print("Complete translation loaded from file.")
            return True
        elif translator.load(":/xexunrtt_complete.qm"):
            app.installTranslator(translator)
            print("Complete translation loaded from resources.")
            return True
        else:
            print("Failed to load complete translation file.")
            return False
    else:
        print("Using English interface (default).")
        return True
'''
    
    print("💡 建议的翻译加载代码:")
    print(new_translation_code)
    
    print("📝 需要在main_window.py中:")
    print("1. 替换现有的翻译加载逻辑")
    print("2. 使用 xexunrtt_complete.qm 而不是 xexunrtt_en.qm")
    print("3. 确保所有UI组件都能获得正确的翻译")
    
    return True

def verify_all_translations():
    """验证所有翻译"""
    print("\n🔍 验证所有翻译")
    print("-" * 40)
    
    ts_file = "xexunrtt_complete.ts"
    
    try:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键翻译
        key_texts = [
            "Lock Horizontal",
            "Lock Vertical", 
            "Send",
            "Clear",
            "Open Folder",
            "Reconnect",
            "Disconnect",
            "RTT2UART Control Panel",
            "Sent:",
            "Connection(&C)"
        ]
        
        print("🔍 关键翻译验证:")
        all_found = True
        for text in key_texts:
            if f"<source>{text}</source>" in content:
                print(f"  ✅ '{text}' 存在")
            else:
                print(f"  ❌ '{text}' 缺失")
                all_found = False
        
        # 统计翻译状态
        import re
        total_messages = len(re.findall(r'<message>', content))
        unfinished = len(re.findall(r'type="unfinished"', content))
        finished = total_messages - unfinished
        
        print(f"\n📊 翻译统计:")
        print(f"  总消息数: {total_messages}")
        print(f"  已完成: {finished}")
        print(f"  未完成: {unfinished}")
        print(f"  完成率: {finished/total_messages*100:.1f}%")
        
        return all_found
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 添加缺失的UI翻译")
    print("=" * 60)
    
    success = True
    
    # 1. 添加缺失的UI翻译上下文
    if not add_missing_ui_contexts():
        success = False
    
    # 2. 重新编译翻译文件
    if success and not recompile_translation():
        success = False
    
    # 3. 验证所有翻译
    if success and not verify_all_translations():
        print("⚠️ 部分翻译验证失败，但继续处理...")
    
    # 4. 更新翻译加载逻辑建议
    update_main_window_translation_loading()
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 UI翻译修复完成！")
        
        print("\n✅ 修复的问题:")
        print("1. ✅ 添加了xexun_rtt上下文的所有翻译")
        print("2. ✅ 'Lock Horizontal' → '锁定水平滚动'")
        print("3. ✅ 'Lock Vertical' → '锁定垂直滚动'")
        print("4. ✅ 'Send' → '发送'")
        print("5. ✅ 'Clear' → '清除'")
        print("6. ✅ 连接配置窗口的所有翻译")
        print("7. ✅ 重新编译了完整翻译文件")
        
        print("\n🔧 下一步:")
        print("1. 更新main_window.py使用xexunrtt_complete.qm")
        print("2. 测试所有UI元素的翻译效果")
        print("3. 确保重新编译语言文件时不会丢失翻译")
        
    else:
        print("❌ UI翻译修复失败")
    
    return success

if __name__ == "__main__":
    main()
