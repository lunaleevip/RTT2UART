#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复UI翻译 - 确保dialog context的所有字符串都有中文翻译"""

import xml.etree.ElementTree as ET

# UI相关的翻译映射（dialog context）
DIALOG_TRANSLATIONS = {
    "Connection Configuration": "连接配置",
    "Start": "开始",
    "Target Interface And Speed": "目标接口和速率",
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
    "DATA (RTT Channel 1)": "DATA (RTT通道 1)",
    "Forward Content:": "转发内容:",
    # 串口转发选项
    "Disable Forward": "禁用转发",
    "Current Tab": "当前标签页",
    "All Data": "全部数据",
    "Channel": "通道",
    "Channel %s": "通道 %s",
    "%s (%s)": "%s (%s)",
    "Filter %s: (%s)": "筛选器 %s: (%s)",
    "Filter %s: %s": "筛选器 %s: %s",
    "Not Set": "未设置",
    "RTT Channel 1 (Raw Data)": "RTT通道 1 (原始数据)",
}

# xexun_rtt context的翻译（主窗口UI）
XEXUN_RTT_TRANSLATIONS = {
    "Open Folder": "打开文件夹",
    "Reconnect": "重新连接",
    "Disconnect": "断开连接",
    "Clear": "清除",
    "Send": "发送",
    "Lock Vertical": "锁定垂直",
    "Lock Horizontal": "锁定水平",
    "Light Mode": "浅色模式",
    "Font Size": "字体大小",
}

def fix_ui_translations(ts_file):
    """修复UI翻译"""
    tree = ET.parse(ts_file)
    root = tree.getroot()
    
    fixed_count = 0
    
    # 定义需要处理的context和对应的翻译字典
    contexts_to_fix = {
        'dialog': DIALOG_TRANSLATIONS,
        'xexun_rtt': XEXUN_RTT_TRANSLATIONS,
    }
    
    # 遍历所有context
    for context in root.findall('context'):
        name_elem = context.find('name')
        if name_elem is None:
            continue
            
        context_name = name_elem.text
        
        # 如果这个context需要修复
        if context_name in contexts_to_fix:
            translations = contexts_to_fix[context_name]
            
            # 遍历该context下的所有消息
            for message in context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    
                    # 检查是否需要翻译
                    if source_text in translations:
                        current_translation = translation_elem.text
                        expected_translation = translations[source_text]
                        
                        # 如果翻译不存在、为空、或被标记为unfinished/vanished
                        translation_type = translation_elem.get('type')
                        if (not current_translation or 
                            translation_type in ['unfinished', 'vanished'] or
                            current_translation != expected_translation):
                            
                            translation_elem.text = expected_translation
                            # 移除type属性（表示翻译已完成）
                            if 'type' in translation_elem.attrib:
                                del translation_elem.attrib['type']
                            
                            fixed_count += 1
                            print(f"[修复] {context_name}::{source_text} -> {expected_translation}")
    
    # 保存文件
    tree.write(ts_file, encoding='utf-8', xml_declaration=True)
    
    print(f"\n修复完成: {fixed_count} 个UI翻译")
    return fixed_count

if __name__ == '__main__':
    fix_ui_translations('xexunrtt_complete.ts')

