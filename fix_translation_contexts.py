#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复翻译上下文问题
"""

import subprocess
import xml.etree.ElementTree as ET
import os

def generate_complete_translations():
    """生成包含所有上下文的完整翻译文件"""
    print("🔧 生成包含所有上下文的完整翻译文件")
    print("=" * 60)
    
    # 所有需要扫描的文件
    source_files = [
        "main_window.py",
        "ui_rtt2uart.py", 
        "ui_rtt2uart_updated.py",
        "ui_sel_device.py",
        "ui_xexunrtt.py"
    ]
    
    # 检查文件是否存在
    existing_files = []
    for file in source_files:
        if os.path.exists(file):
            existing_files.append(file)
            print(f"✅ 找到文件: {file}")
        else:
            print(f"⚠️ 文件不存在: {file}")
    
    if not existing_files:
        print("❌ 没有找到任何源文件")
        return False
    
    # 生成翻译文件
    print(f"\n🔄 扫描 {len(existing_files)} 个文件生成翻译...")
    cmd = ["pyside6-lupdate"] + existing_files + ["-ts", "xexunrtt_complete.ts"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print(f"✅ 翻译文件生成成功")
            print(f"   输出: {result.stdout.strip()}")
        else:
            print(f"❌ 翻译文件生成失败")
            print(f"   错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 执行lupdate失败: {e}")
        return False
    
    return True

def analyze_translation_contexts():
    """分析翻译上下文"""
    print("\n🔍 分析翻译上下文")
    print("-" * 40)
    
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        contexts = {}
        total_messages = 0
        
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None:
                context_name = name_elem.text
                messages = context.findall('message')
                contexts[context_name] = len(messages)
                total_messages += len(messages)
        
        print(f"📊 翻译上下文统计:")
        for context_name, count in contexts.items():
            print(f"  - {context_name}: {count} 条消息")
        
        print(f"\n📋 总计: {total_messages} 条翻译消息")
        
        # 检查关键翻译
        print(f"\n🔍 检查关键翻译:")
        key_texts = {
            "RTT2UART Connection Configuration": "连接配置",
            "Lock Horizontal": "锁定水平滚动",
            "Lock Vertical": "锁定垂直滚动", 
            "Send": "发送",
            "Sent:": "已发送:",
            "Clear": "清除",
            "Open Folder": "打开文件夹",
            "Reconnect": "重新连接",
            "Disconnect": "断开连接"
        }
        
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for english, chinese in key_texts.items():
            if f"<source>{english}</source>" in content:
                print(f"  ✅ '{english}' 存在于翻译文件中")
            else:
                print(f"  ❌ '{english}' 不存在于翻译文件中")
        
        return True
        
    except Exception as e:
        print(f"❌ 分析翻译文件失败: {e}")
        return False

def populate_translations():
    """填充翻译内容"""
    print("\n🔧 填充翻译内容")
    print("-" * 40)
    
    ts_file = "xexunrtt_complete.ts"
    
    # 翻译映射表
    translations = {
        # dialog 上下文
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
        "Auto Reconnect": "自动重连",
        
        # xexun_rtt 上下文
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
        
        # main_window 上下文
        "RTT2UART Connection Configuration": "RTT2UART连接配置",
        "Sent:": "已发送:",
        "Send:": "发送:",
        "JLink Debug Log": "JLink调试日志",
        "Clear Log": "清除日志",
        "Connected": "已连接",
        "Disconnected": "已断开",
        "Connection(&C)": "连接(&C)",
        "Window(&W)": "窗口(&W)",
        "Tools(&T)": "工具(&T)",
        "Help(&H)": "帮助(&H)",
        "Compact Mode(&M)": "紧凑模式(&M)",
        "XexunRTT - RTT Debug Main Window": "XexunRTT - RTT调试主窗口"
    }
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        updated_count = 0
        
        for context in root.findall('context'):
            for message in context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    if source_text in translations:
                        # 更新翻译
                        translation_elem.text = translations[source_text]
                        # 移除unfinished标记
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                        updated_count += 1
        
        # 保存更新的文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"✅ 已更新 {updated_count} 条翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 填充翻译失败: {e}")
        return False

def compile_qm_file():
    """编译QM文件"""
    print("\n🔨 编译QM文件")
    print("-" * 40)
    
    try:
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_complete.ts", "-qm", "xexunrtt_complete.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件编译成功")
            print(f"   输出: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ QM文件编译失败")
            print(f"   错误: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 编译QM文件失败: {e}")
        return False

def update_resources():
    """更新资源文件"""
    print("\n📦 更新资源文件")
    print("-" * 40)
    
    # 读取现有资源文件
    qrc_file = "resources.qrc"
    if not os.path.exists(qrc_file):
        print(f"❌ 资源文件不存在: {qrc_file}")
        return False
    
    try:
        with open(qrc_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查是否已包含完整翻译文件
        if "xexunrtt_complete.qm" not in content:
            # 在现有翻译文件后添加新的翻译文件
            if "xexunrtt_en.qm" in content:
                content = content.replace(
                    "<file>./xexunrtt_en.qm</file>",
                    "<file>./xexunrtt_en.qm</file>\n        <file>./xexunrtt_complete.qm</file>"
                )
            else:
                # 在</qresource>前添加
                content = content.replace(
                    "</qresource>",
                    "        <file>./xexunrtt_complete.qm</file>\n    </qresource>"
                )
            
            with open(qrc_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ 已添加完整翻译文件到资源")
        else:
            print("ℹ️ 完整翻译文件已在资源中")
        
        # 重新编译资源
        result = subprocess.run(
            ["pyside6-rcc", qrc_file, "-o", "resources_rc.py"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ 资源文件编译成功")
            return True
        else:
            print(f"❌ 资源文件编译失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 更新资源文件失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 修复翻译上下文问题")
    print("=" * 60)
    
    success = True
    
    # 1. 生成完整翻译文件
    if not generate_complete_translations():
        success = False
    
    # 2. 分析翻译上下文
    if success and not analyze_translation_contexts():
        success = False
    
    # 3. 填充翻译内容
    if success and not populate_translations():
        success = False
    
    # 4. 编译QM文件
    if success and not compile_qm_file():
        success = False
    
    # 5. 更新资源文件
    if success and not update_resources():
        success = False
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 翻译上下文修复完成！")
        
        print("\n✅ 修复的问题:")
        print("1. ✅ 扫描了所有UI文件，包含多个翻译上下文")
        print("2. ✅ 'dialog'上下文 - 连接配置窗口翻译")
        print("3. ✅ 'xexun_rtt'上下文 - Lock滚动条、Send按钮翻译")
        print("4. ✅ 'main_window'上下文 - 主窗口翻译")
        print("5. ✅ 生成了完整的翻译文件 xexunrtt_complete.qm")
        print("6. ✅ 更新了资源文件")
        
        print("\n💡 使用方法:")
        print("1. 将main_window.py中的翻译加载改为使用xexunrtt_complete.qm")
        print("2. 或者创建一个统一的翻译管理系统")
        print("3. 确保所有UI组件都能正确加载对应上下文的翻译")
        
    else:
        print("❌ 翻译上下文修复失败")
    
    return success

if __name__ == "__main__":
    main()
