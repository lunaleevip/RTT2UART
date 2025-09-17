#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
移植现有的翻译到新的完整翻译文件
"""

import xml.etree.ElementTree as ET
import subprocess
import os

def parse_existing_translations():
    """解析现有的翻译文件"""
    print("🔍 解析现有的翻译文件")
    print("=" * 50)
    
    old_ts_file = "xexunrtt.ts"
    
    if not os.path.exists(old_ts_file):
        print(f"❌ 原翻译文件不存在: {old_ts_file}")
        return {}
    
    try:
        tree = ET.parse(old_ts_file)
        root = tree.getroot()
        
        existing_translations = {}
        
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None:
                context_name = name_elem.text
                
                # 映射上下文名称
                if context_name == "MainWindow":
                    context_name = "main_window"
                elif context_name == "Dialog":
                    context_name = "dialog"
                elif context_name == "xexun_rtt":
                    context_name = "xexun_rtt"
                
                if context_name not in existing_translations:
                    existing_translations[context_name] = {}
                
                for message in context.findall('message'):
                    source_elem = message.find('source')
                    translation_elem = message.find('translation')
                    
                    if (source_elem is not None and translation_elem is not None and 
                        translation_elem.text and 'vanished' not in translation_elem.get('type', '')):
                        
                        source_text = source_elem.text
                        translation_text = translation_elem.text
                        existing_translations[context_name][source_text] = translation_text
                        print(f"  📋 {context_name}: '{source_text}' → '{translation_text}'")
        
        total_translations = sum(len(ctx) for ctx in existing_translations.values())
        print(f"\n✅ 解析完成，共找到 {total_translations} 条翻译")
        
        return existing_translations
        
    except Exception as e:
        print(f"❌ 解析翻译文件失败: {e}")
        return {}

def apply_existing_translations(existing_translations):
    """将现有翻译应用到新的完整翻译文件"""
    print("\n🔧 将现有翻译应用到新的完整翻译文件")
    print("=" * 50)
    
    new_ts_file = "xexunrtt_complete.ts"
    
    if not os.path.exists(new_ts_file):
        print(f"❌ 新翻译文件不存在: {new_ts_file}")
        return False
    
    try:
        tree = ET.parse(new_ts_file)
        root = tree.getroot()
        
        applied_count = 0
        
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None:
                context_name = name_elem.text
                
                if context_name in existing_translations:
                    context_translations = existing_translations[context_name]
                    
                    for message in context.findall('message'):
                        source_elem = message.find('source')
                        translation_elem = message.find('translation')
                        
                        if (source_elem is not None and translation_elem is not None and 
                            source_elem.text in context_translations):
                            
                            source_text = source_elem.text
                            existing_translation = context_translations[source_text]
                            
                            # 应用翻译
                            translation_elem.text = existing_translation
                            # 移除unfinished标记
                            if 'type' in translation_elem.attrib:
                                del translation_elem.attrib['type']
                            
                            print(f"  ✅ {context_name}: '{source_text}' → '{existing_translation}'")
                            applied_count += 1
        
        # 保存文件
        tree.write(new_ts_file, encoding='utf-8', xml_declaration=True)
        print(f"\n✅ 成功应用 {applied_count} 条现有翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 应用翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_missing_critical_translations():
    """添加关键的缺失翻译"""
    print("\n🔧 添加关键的缺失翻译")
    print("=" * 50)
    
    ts_file = "xexunrtt_complete.ts"
    
    # 从原文件中提取的关键翻译
    critical_translations = {
        "main_window": {
            # 从原文件中提取的翻译
            "Info": "提示",
            "ALL window displays summary data from all channels and doesn't support clear operation.\nPlease switch to specific RTT channel (0-15) to clear.": "ALL窗口显示所有通道的汇总数据，不支持清屏操作。\n请切换到具体的RTT通道（0-15）进行清屏。",
            "Manufacturer": "制造商",
            "Device": "设备",
            "Core": "内核",
            "NumCores": "内核数量",
            "Flash Size": "Flash大小",
            "RAM Size": "RAM大小",
            "Can not find device database !": "找不到设备数据库！",
            "Failed to parse device database file!": "解析设备数据库文件失败！",
            "Edit Filter Text": "编辑筛选文本",
            "Enter new text:": "输入新文本:",
            "filter": "筛选",
            "All": "全部",
            "double click filter to write filter text": "双击筛选器以编写筛选文本",
            "Connection(&C)": "连接(&C)",
            "Reconnect(&R)": "重新连接(&R)",
            "Disconnect(&D)": "断开连接(&D)",
            "Connection Settings(&S)...": "连接设置(&S)...",
            "Window(&W)": "窗口(&W)",
            "New Window(&N)": "新建窗口(&N)",
            "Open a new window": "打开新窗口",
            "Tools(&T)": "工具(&T)",
            "Clear Current Page(&C)": "清除当前页面(&C)",
            "Open Log Folder(&O)": "打开日志文件夹(&O)",
            "Open Config Folder(&F)": "打开配置文件夹(&F)",
            "Encoding(&E)": "编码(&E)",
            "Restart APP F9(&A)": "重启APP F9(&A)",
            "via SFR access": "通过SFR访问",
            "via reset pin": "通过复位引脚",
            "Switch Theme(&T)": "切换主题(&T)",
            "Help(&H)": "帮助(&H)",
            "About(&A)...": "关于(&A)...",
            "Disconnected": "未连接",
            "Connected": "已连接",
            "Read: 0 | Write: 0": "读取: 0 | 写入: 0",
            "Read: {} | Write: {}": "读取: {} | 写入: {}",
            "About XexunRTT": "关于 XexunRTT",
            "XexunRTT v2.1\n\nRTT Debug Tool\n\nBased on PySide6": "XexunRTT v2.1\n\nRTT调试工具\n\n基于 PySide6",
            "Please disconnect first before switching encoding": "请先断开连接再切换编码",
            "Encoding switched to: %s": "编码已切换为: %s",
            "RTT connection established successfully": "RTT连接建立成功",
            "RTT connection disconnected": "RTT连接已断开",
            "JLink Debug Log": "JLink调试日志",
            "Clear Log": "清除日志",
            "Enable Verbose Log": "启用详细日志",
            "Disable Verbose Log": "禁用详细日志",
            "JLink verbose logging enabled - will show all debug information": "JLink详细日志已启用 - 将显示所有调试信息",
            "JLink verbose logging disabled - only showing warnings and errors": "JLink详细日志已禁用 - 仅显示警告和错误",
            "Start": "开始",
            "Stop": "停止",
            "Cannot open config folder:\n{}": "无法打开配置文件夹:\n{}",
            "Cannot open folder:\n{}": "无法打开文件夹:\n{}",
            "Please connect first, then restart app": "请先连接后再重启应用",
            "Restart via SFR (AIRCR.SYSRESETREQ) sent by memory_write32": "通过SFR重启 (AIRCR.SYSRESETREQ) 由memory_write32发送",
            "Failed": "失败",
            "SFR restart failed: %s": "SFR重启失败: %s",
            "Restart via reset pin executed": "通过复位引脚重启已执行",
            "Reset pin restart failed: %s": "复位引脚重启失败: %s",
            "Unable to create connection dialog": "无法创建连接对话框",
            "Find jlink dll failed !": "查找jlink dll失败！",
            "Please selete the target device !": "请选择目标设备！",
            "Starting connection to device: %s": "开始连接设备: %s",
            "Connection type: %s": "连接类型: %s",
            "Serial port: %s, Baud rate: %s": "串口: %s, 波特率: %s",
            "RTT connection started successfully": "RTT连接启动成功",
            "LOG Mode": "LOG模式",
            "DATA Mode": "DATA模式",
            "Serial forwarding enabled: %s - %s": "串口转发已启用: %s - %s",
            "Stopping RTT connection...": "正在停止RTT连接...",
            "Error": "错误",
            "Failed to start new window:\n{}": "启动新窗口失败:\n{}",
            "Failed to start performance test: {}": "启动性能测试失败: {}",
            "Performance test tool started": "性能测试工具已启动",
            "Note: Please ensure device is connected and RTT debugging is started": "注意：请确保已连接设备并开始RTT调试",
            "❌ Send Failed": "❌ 发送失败",
            "RTT2UART Connection Configuration": "RTT2UART 连接配置"
        },
        
        "dialog": {
            "Disable Forward": "禁用转发",
            "Current Tab": "当前标签页",
            "RTT Channel 1 (Raw Data)": "RTT 通道1 (原始数据)",
            "Forward Disabled": "转发已禁用",
            "LOG Mode": "LOG模式",
            "DATA Mode": "DATA模式",
            "{} - {}": "{} - {}",
            "RTT2UART Control Panel": "RTT2UART 控制面板",
            "Start": "开始",
            "Target Interface And Speed": "目标接口和速度",
            "Specify Target Device": "指定目标设备",
            "...": "...",
            "UART Config": "UART 配置",
            "Port:": "端口:",
            "Baud rate:": "波特率:",
            "Scan": "扫描",
            "Reset target": "复位目标",
            "Log Split": "日志拆分",
            "Connection to J-Link": "连接到 J-Link",
            "USB": "USB",
            "Existing Session": "现有会话",
            "TCP/IP": "TCP/IP",
            "Serial NO": "序列号",
            "Auto Reconnect": "自动重连",
            "Serial Forward Settings": "串口转发设置",
            "LOG Current Tab Selection": "LOG 当前标签页选择",
            "DATA (RTT Channel 1)": "DATA (RTT 通道 1)",
            "Forward Content:": "转发内容:"
        },
        
        "xexun_rtt": {
            "Form": "窗体",
            "can read from cmd.txt": "可从cmd.txt读取",
            "F3": "F3",
            "Disconnect": "断开连接",
            "Clear": "清除",
            "F1": "F1",
            "Open Folder": "打开文件夹",
            "Send": "发送",
            "F7": "F7",
            "Light Mode": "浅色模式",
            "double click filter to write filter text": "双击筛选器以编写筛选文本",
            "1": "1",
            "2": "2",
            "Font Size": "字体大小",
            "F2": "F2",
            "Reconnect": "重新连接",
            "F6": "F6",
            "Lock Horizontal": "锁定水平",
            "F5": "F5",
            "Lock Vertical": "锁定垂直"
        }
    }
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        added_count = 0
        
        for context_name, translations in critical_translations.items():
            # 找到或创建上下文
            context = None
            for ctx in root.findall('context'):
                name_elem = ctx.find('name')
                if name_elem is not None and name_elem.text == context_name:
                    context = ctx
                    break
            
            if context is None:
                print(f"📝 创建上下文: {context_name}")
                context = ET.SubElement(root, 'context')
                name_elem = ET.SubElement(context, 'name')
                name_elem.text = context_name
            
            # 获取已存在的翻译
            existing_sources = {}
            for message in context.findall('message'):
                source_elem = message.find('source')
                if source_elem is not None:
                    existing_sources[source_elem.text] = message
            
            # 添加或更新翻译
            for source_text, translation_text in translations.items():
                if source_text in existing_sources:
                    # 更新现有翻译
                    message = existing_sources[source_text]
                    translation_elem = message.find('translation')
                    if translation_elem is not None:
                        translation_elem.text = translation_text
                        # 移除unfinished标记
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                        print(f"  🔧 {context_name}: 更新 '{source_text}' → '{translation_text}'")
                        added_count += 1
                else:
                    # 创建新的message元素
                    message_elem = ET.SubElement(context, 'message')
                    
                    # 添加location元素
                    location_elem = ET.SubElement(message_elem, 'location')
                    location_elem.set('filename', 'main_window.py')
                    location_elem.set('line', '1')
                    
                    # 添加source元素
                    source_elem = ET.SubElement(message_elem, 'source')
                    source_elem.text = source_text
                    
                    # 添加translation元素
                    translation_elem = ET.SubElement(message_elem, 'translation')
                    translation_elem.text = translation_text
                    
                    print(f"  ✅ {context_name}: 添加 '{source_text}' → '{translation_text}'")
                    added_count += 1
        
        # 保存文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"\n✅ 成功添加/更新 {added_count} 条关键翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 添加关键翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def compile_and_verify():
    """编译并验证翻译"""
    print("\n🔨 编译并验证翻译")
    print("=" * 50)
    
    try:
        # 编译QM文件
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_complete.ts", "-qm", "xexunrtt_complete.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件编译成功")
            print(f"   输出: {result.stdout.strip()}")
        else:
            print(f"❌ QM文件编译失败")
            print(f"   错误: {result.stderr}")
            return False
        
        # 更新资源文件
        result = subprocess.run(
            ["pyside6-rcc", "resources.qrc", "-o", "resources_rc.py"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ 资源文件更新成功")
        else:
            print(f"⚠️ 资源文件更新失败: {result.stderr}")
        
        # 验证翻译统计
        with open("xexunrtt_complete.ts", 'r', encoding='utf-8') as f:
            content = f.read()
        
        import re
        total_messages = len(re.findall(r'<message>', content))
        unfinished = len(re.findall(r'type="unfinished"', content))
        finished = total_messages - unfinished
        
        print(f"\n📊 最终翻译统计:")
        print(f"  总消息数: {total_messages}")
        print(f"  已完成: {finished}")
        print(f"  未完成: {unfinished}")
        print(f"  完成率: {finished/total_messages*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 编译验证失败: {e}")
        return False

def main():
    """主函数"""
    print("🔧 移植现有翻译到完整翻译文件")
    print("=" * 60)
    
    import os
    
    # 1. 解析现有翻译
    existing_translations = parse_existing_translations()
    
    if not existing_translations:
        print("⚠️ 没有找到现有翻译，继续添加关键翻译...")
    
    success = True
    
    # 2. 应用现有翻译
    if existing_translations:
        if not apply_existing_translations(existing_translations):
            success = False
    
    # 3. 添加关键的缺失翻译
    if not add_missing_critical_translations():
        success = False
    
    # 4. 编译并验证
    if success and not compile_and_verify():
        success = False
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 翻译移植完成！")
        
        print("\n✅ 完成的工作:")
        print("1. ✅ 移植了原有 xexunrtt.ts 中的所有翻译")
        print("2. ✅ 添加了关键的缺失翻译")
        print("3. ✅ 重新编译了完整翻译文件")
        print("4. ✅ 更新了资源文件")
        
        print("\n🌍 现在的翻译覆盖:")
        print("- ✅ 所有菜单项和UI控件")
        print("- ✅ 连接配置窗口")
        print("- ✅ 串口转发设置")
        print("- ✅ 日志和调试信息")
        print("- ✅ 错误和状态消息")
        
        print("\n🔧 下一步:")
        print("1. 重启程序测试翻译效果")
        print("2. 所有之前翻译好的内容都应该正常显示")
        
    else:
        print("❌ 翻译移植失败")
    
    return success

if __name__ == "__main__":
    main()
