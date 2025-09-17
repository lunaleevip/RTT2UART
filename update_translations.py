#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新翻译文件脚本
"""

import xml.etree.ElementTree as ET
import re

# 英文到中文的翻译映射
EN_TO_ZH_MAP = {
    # 基本信息
    "Info": "信息",
    "Error": "错误", 
    "Warning": "警告",
    "Confirm": "确认",
    "Cancel": "取消",
    "OK": "确定",
    "Yes": "是",
    "No": "否",
    
    # 连接和状态
    "Connected": "已连接",
    "Disconnected": "已断开",
    "Connection(&C)": "连接(&C)",
    "Reconnect(&R)": "重新连接(&R)",
    "Disconnect(&D)": "断开连接(&D)",
    "Connection Settings(&S)...": "连接设置(&S)...",
    "Start": "开始",
    "Stop": "停止",
    "Sent:": "已发送:",
    "❌ Send Failed": "❌ 发送失败",
    
    # 窗口和界面
    "Window(&W)": "窗口(&W)",
    "New Window(&N)": "新窗口(&N)",
    "Open a new window": "打开新窗口",
    "Compact Mode(&M)": "紧凑模式(&M)",
    "Toggle compact mode for multi-device usage": "切换紧凑模式以便多设备使用",
    "XexunRTT - RTT Debug Main Window": "XexunRTT - RTT调试主窗口",
    
    # 工具菜单
    "Tools(&T)": "工具(&T)",
    "Clear Current Page(&C)": "清空当前页面(&C)",
    "Open Log Folder(&O)": "打开日志文件夹(&O)",
    "Open Config Folder(&F)": "打开配置文件夹(&F)",
    "Encoding(&E)": "编码(&E)",
    "Restart APP F9(&A)": "重启应用 F9(&A)",
    "via SFR access": "通过SFR访问",
    "via reset pin": "通过复位引脚",
    "Switch Theme(&T)": "切换主题(&T)",
    
    # 帮助菜单
    "Help(&H)": "帮助(&H)",
    "About(&A)...": "关于(&A)...",
    "About XexunRTT": "关于 XexunRTT",
    
    # 设备和数据
    "Manufacturer": "制造商",
    "Device": "设备",
    "Core": "核心",
    "NumCores": "核心数",
    "Flash Size": "Flash大小",
    "RAM Size": "RAM大小",
    "All": "全部",
    "filter": "筛选",
    "double click filter to write filter text": "双击筛选器以编写筛选文本",
    
    # 日志相关
    "JLink Debug Log": "JLink调试日志",
    "Clear Log": "清空日志",
    "Enable Verbose Log": "启用详细日志",
    "Disable Verbose Log": "禁用详细日志",
    "JLink verbose logging enabled - will show all debug information": "JLink详细日志已启用 - 将显示所有调试信息",
    "JLink verbose logging disabled - only showing warnings and errors": "JLink详细日志已禁用 - 仅显示警告和错误",
    "JLink file logging enabled: %s": "JLink文件日志已启用: %s",
    "JLink file logging disabled": "JLink文件日志已禁用",
    "Failed to enable file logging: %s": "启用文件日志失败: %s",
    "Failed to disable file logging: %s": "禁用文件日志失败: %s",
    "Failed to setup file logging: %s": "设置文件日志失败: %s",
    "Error disabling file logging: %s": "禁用文件日志时出错: %s",
    "JLink file logging will be enabled on next connection: %s": "JLink文件日志将在下次连接时启用: %s",
    "Failed to start log tailer: %s": "启动日志跟踪器失败: %s",
    
    # 转发功能
    "Disable Forward": "禁用转发",
    "Current Tab": "当前标签页",
    "RTT Channel 1 (Raw Data)": "RTT通道1 (原始数据)",
    "Forward Disabled": "转发已禁用",
    "LOG Mode": "日志模式",
    "DATA Mode": "数据模式",
    "Serial forwarding enabled: %s - %s": "串口转发已启用: %s - %s",
    "Serial forwarding disabled": "串口转发已禁用",
    
    # 状态信息
    "RTT connection established successfully": "RTT连接建立成功",
    "RTT connection disconnected": "RTT连接已断开",
    "Read: %s | Write: %s": "读取: %s | 写入: %s",
    "Read: {} | Write: {}": "读取: {} | 写入: {}",
    
    # 错误和警告消息
    "Can not find device database !": "无法找到设备数据库！",
    "Failed to parse device database file!": "解析设备数据库文件失败！",
    "Edit Filter Text": "编辑筛选文本",
    "Enter new text:": "输入新文本:",
    "Please disconnect first before switching encoding": "请先断开连接再切换编码",
    "Encoding switched to: %s": "编码已切换为: %s",
    "Cannot open folder:\\n{}": "无法打开文件夹:\\n{}",
    "Cannot open config folder:\\n{}": "无法打开配置文件夹:\\n{}",
    "Failed to start new window:\\n{}": "启动新窗口失败:\\n{}",
    "Performance test tool started": "性能测试工具已启动",
    "Note: Please ensure device is connected and RTT debugging is started": "注意: 请确保设备已连接并启动RTT调试",
    "Failed to start performance test: {}": "启动性能测试失败: {}",
    "Please connect first, then restart app": "请先连接，然后重启应用",
    "Please disconnect first, then restart app": "请先断开连接，然后重启应用",
    
    # ALL窗口相关
    "ALL window displays summary data from all channels and doesn't support clear operation.\\nPlease switch to specific RTT channel (0-15) to clear.": "ALL窗口显示所有通道的汇总数据，不支持清屏操作。\\n请切换到具体的RTT通道（0-15）进行清屏。",
    
    # 其他常用文本
    "Starting connection to device: %s": "开始连接到设备: %s",
    "Connection type: %s": "连接类型: %s", 
    "Serial port: %s, Baud rate: %s": "串口: %s，波特率: %s",
    "RTT connection started successfully": "RTT连接启动成功",
}

def update_ts_file(ts_file_path):
    """更新.ts翻译文件"""
    try:
        # 解析XML文件
        tree = ET.parse(ts_file_path)
        root = tree.getroot()
        
        # 遍历所有message元素
        for context in root.findall('context'):
            for message in context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    
                    # 查找对应的中文翻译
                    if source_text in EN_TO_ZH_MAP:
                        translation_elem.text = EN_TO_ZH_MAP[source_text]
                        # 移除unfinished属性
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                    else:
                        # 尝试模糊匹配
                        fuzzy_translation = find_fuzzy_translation(source_text)
                        if fuzzy_translation:
                            translation_elem.text = fuzzy_translation
                            if 'type' in translation_elem.attrib:
                                del translation_elem.attrib['type']
                        else:
                            print(f"No translation found for: '{source_text}'")
        
        # 保存更新后的文件
        tree.write(ts_file_path, encoding='utf-8', xml_declaration=True)
        print(f"Updated {ts_file_path}")
        return True
        
    except Exception as e:
        print(f"Error updating {ts_file_path}: {e}")
        return False

def find_fuzzy_translation(text):
    """模糊匹配翻译"""
    # 处理包含格式化字符串的文本
    if "%s" in text or "%d" in text or "{}" in text:
        # 尝试找到相似的模式
        for en_text, zh_text in EN_TO_ZH_MAP.items():
            if en_text.replace("%s", "{}").replace("%d", "{}") == text.replace("%s", "{}").replace("%d", "{}"):
                return zh_text.replace("%s", "{}").replace("%d", "{}")
    
    # 处理包含换行符的文本
    if "\\n" in text:
        clean_text = text.replace("\\n", "\n")
        if clean_text in EN_TO_ZH_MAP:
            return EN_TO_ZH_MAP[clean_text].replace("\n", "\\n")
    
    return None

def main():
    """主函数"""
    print("🔄 更新翻译文件...")
    
    ts_file = "xexunrtt_en.ts"
    if update_ts_file(ts_file):
        print("✅ 翻译文件更新成功")
        
        # 编译.qm文件
        print("📦 编译.qm文件...")
        import subprocess
        try:
            result = subprocess.run(
                ["pyside6-lrelease", ts_file, "-qm", "xexunrtt_en.qm"], 
                capture_output=True, text=True, encoding='utf-8'
            )
            if result.returncode == 0:
                print("✅ .qm文件编译成功")
            else:
                print(f"❌ .qm文件编译失败: {result.stderr}")
        except Exception as e:
            print(f"❌ 编译.qm文件时出错: {e}")
    else:
        print("❌ 翻译文件更新失败")

if __name__ == "__main__":
    main()
