#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国际化处理脚本 - 将UI和输出文本改为英文
"""

import re
import os
import subprocess
from pathlib import Path

# 中英文对照字典
TRANSLATION_MAP = {
    # 菜单和按钮
    "连接": "Connection",
    "重新连接": "Reconnect", 
    "断开连接": "Disconnect",
    "连接设置": "Connection Settings",
    "窗口": "Window",
    "新窗口": "New Window",
    "紧凑模式": "Compact Mode",
    "工具": "Tools",
    "清空当前页面": "Clear Current Page",
    "打开日志文件夹": "Open Log Folder",
    "打开配置文件夹": "Open Config Folder",
    "编码": "Encoding",
    "重启应用": "Restart APP",
    "切换主题": "Switch Theme",
    "帮助": "Help",
    "关于": "About",
    
    # 状态和信息
    "已连接": "Connected",
    "已断开": "Disconnected", 
    "连接成功": "Connection established successfully",
    "连接断开": "Connection disconnected",
    "发送失败": "Send Failed",
    "发送成功": "Send Successful",
    "已发送": "Sent",
    
    # 对话框和提示
    "提示": "Info",
    "错误": "Error", 
    "警告": "Warning",
    "确认": "Confirm",
    "取消": "Cancel",
    "确定": "OK",
    "是": "Yes",
    "否": "No",
    
    # 日志和调试
    "JLink调试日志": "JLink Debug Log",
    "清空日志": "Clear Log",
    "启用详细日志": "Enable Verbose Log",
    "禁用详细日志": "Disable Verbose Log",
    "日志已启用": "Logging enabled",
    "日志已禁用": "Logging disabled",
    
    # 设备和连接
    "目标设备": "Target Device",
    "设备列表": "Device List", 
    "制造商": "Manufacturer",
    "设备": "Device",
    "核心": "Core",
    "核心数": "NumCores",
    "Flash大小": "Flash Size",
    "RAM大小": "RAM Size",
    "串口": "Serial Port",
    "波特率": "Baud Rate",
    
    # 通道和数据
    "全部": "All",
    "通道": "Channel",
    "筛选": "Filter",
    "过滤": "Filter",
    "原始数据": "Raw Data",
    "读取": "Read",
    "写入": "Write",
    "已读": "Read",
    "已写": "Written",
    
    # 文件和路径
    "打开文件夹": "Open Folder",
    "保存": "Save",
    "加载": "Load",
    "导出": "Export",
    "导入": "Import",
    
    # 其他常用词汇
    "启动": "Start",
    "停止": "Stop", 
    "暂停": "Pause",
    "继续": "Resume",
    "设置": "Settings",
    "配置": "Config",
    "选项": "Options",
    "首选项": "Preferences"
}

def find_chinese_in_file(file_path):
    """查找文件中的中文文本"""
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    chinese_texts = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                matches = chinese_pattern.findall(line)
                if matches:
                    chinese_texts.append({
                        'line': line_num,
                        'content': line.strip(),
                        'chinese': matches
                    })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return chinese_texts

def replace_chinese_in_translate_calls(content):
    """替换QCoreApplication.translate调用中的中文"""
    # 匹配QCoreApplication.translate("context", "中文")模式
    translate_pattern = r'QCoreApplication\.translate\("([^"]*)",\s*"([^"]*?)"\)'
    
    def replace_func(match):
        context = match.group(1)
        chinese_text = match.group(2)
        
        # 查找对应的英文翻译
        english_text = TRANSLATION_MAP.get(chinese_text, chinese_text)
        
        # 如果没有找到翻译，保持原文但添加注释
        if english_text == chinese_text and re.search(r'[\u4e00-\u9fff]', chinese_text):
            print(f"Warning: No translation found for: '{chinese_text}'")
            # 尝试简单的翻译
            english_text = translate_simple_chinese(chinese_text)
        
        return f'QCoreApplication.translate("{context}", "{english_text}")'
    
    return re.sub(translate_pattern, replace_func, content)

def translate_simple_chinese(text):
    """简单的中文翻译逻辑"""
    # 这里可以添加更多的翻译规则
    simple_translations = {
        "制造商": "Manufacturer",
        "设备": "Device", 
        "核心": "Core",
        "核心数": "NumCores",
        "Flash大小": "Flash Size",
        "RAM大小": "RAM Size",
        "无法找到设备数据库": "Cannot find device database",
        "解析设备数据库文件失败": "Failed to parse device database file",
        "编辑筛选文本": "Edit Filter Text",
        "输入新文本": "Enter new text",
        "双击筛选器以编写筛选文本": "Double click filter to write filter text",
        "请先断开连接，然后重启应用": "Please disconnect first, then restart app",
        "请先连接，然后重启应用": "Please connect first, then restart app",
        "切换编码为": "Encoding switched to",
        "请先断开连接再切换编码": "Please disconnect first before switching encoding",
        "RTT连接建立成功": "RTT connection established successfully",
        "RTT连接已断开": "RTT connection disconnected",
        "无法打开文件夹": "Cannot open folder",
        "无法打开配置文件夹": "Cannot open config folder",
        "启动新窗口失败": "Failed to start new window",
        "性能测试工具已启动": "Performance test tool started",
        "注意：请确保设备已连接并启动RTT调试": "Note: Please ensure device is connected and RTT debugging is started",
        "启动性能测试失败": "Failed to start performance test",
        "JLink详细日志已启用": "JLink verbose logging enabled",
        "JLink详细日志已禁用": "JLink verbose logging disabled",
        "JLink文件日志已启用": "JLink file logging enabled",
        "JLink文件日志已禁用": "JLink file logging disabled",
        "启用文件日志失败": "Failed to enable file logging",
        "禁用文件日志失败": "Failed to disable file logging",
        "设置文件日志失败": "Failed to setup file logging",
        "启动日志跟踪器失败": "Failed to start log tailer"
    }
    
    return simple_translations.get(text, text)

def update_main_window_file():
    """更新main_window.py文件"""
    file_path = "main_window.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换翻译调用中的中文
        updated_content = replace_chinese_in_translate_calls(content)
        
        # 保存更新后的文件
        with open(file_path + '.new', 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"Updated {file_path} -> {file_path}.new")
        return True
        
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False

def update_ui_files():
    """更新UI文件中的中文字体"""
    ui_files = ["xexunrtt.ui", "rtt2uart.ui", "sel_device.ui"]
    
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 替换中文字体为英文字体
                content = content.replace('<family>新宋体</family>', '<family>Arial</family>')
                content = content.replace('<family>微软雅黑</family>', '<family>Arial</family>')
                
                with open(ui_file + '.new', 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"Updated {ui_file} -> {ui_file}.new")
                
            except Exception as e:
                print(f"Error updating {ui_file}: {e}")

def generate_ts_file():
    """生成新的.ts翻译文件"""
    try:
        # 使用pylupdate5或pyside6-lupdate生成.ts文件
        cmd = ["pyside6-lupdate", "main_window.py", "ui_*.py", "-ts", "xexunrtt_en.ts"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Successfully generated xexunrtt_en.ts")
            return True
        else:
            print(f"Failed to generate .ts file: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("pyside6-lupdate not found. Please install PySide6 tools.")
        return False
    except Exception as e:
        print(f"Error generating .ts file: {e}")
        return False

def compile_qm_file():
    """编译.qm文件"""
    try:
        cmd = ["pyside6-lrelease", "xexunrtt_en.ts", "-qm", "xexunrtt_en.qm"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Successfully compiled xexunrtt_en.qm")
            return True
        else:
            print(f"Failed to compile .qm file: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("pyside6-lrelease not found. Please install PySide6 tools.")
        return False
    except Exception as e:
        print(f"Error compiling .qm file: {e}")
        return False

def analyze_current_files():
    """分析当前文件中的中文文本"""
    files_to_check = ["main_window.py", "ui_rtt2uart.py", "ui_sel_device.py", "ui_xexunrtt.py"]
    
    print("=== 分析当前文件中的中文文本 ===")
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            print(f"\n--- {file_path} ---")
            chinese_texts = find_chinese_in_file(file_path)
            
            if chinese_texts:
                for item in chinese_texts[:10]:  # 只显示前10个
                    print(f"Line {item['line']}: {item['chinese']}")
                if len(chinese_texts) > 10:
                    print(f"... and {len(chinese_texts) - 10} more")
            else:
                print("No Chinese text found")

def main():
    """主函数"""
    print("🌍 开始国际化处理...")
    
    # 1. 分析当前文件
    print("\n1. 分析当前文件...")
    analyze_current_files()
    
    # 2. 更新源代码文件
    print("\n2. 更新main_window.py...")
    if update_main_window_file():
        print("✅ main_window.py updated successfully")
    else:
        print("❌ Failed to update main_window.py")
    
    # 3. 更新UI文件
    print("\n3. 更新UI文件...")
    update_ui_files()
    
    # 4. 生成.ts文件
    print("\n4. 生成.ts翻译文件...")
    if generate_ts_file():
        print("✅ .ts file generated successfully")
    else:
        print("❌ Failed to generate .ts file")
    
    # 5. 编译.qm文件
    print("\n5. 编译.qm文件...")
    if compile_qm_file():
        print("✅ .qm file compiled successfully")
    else:
        print("❌ Failed to compile .qm file")
    
    print("\n🎉 国际化处理完成！")
    print("\n注意：")
    print("1. 请检查生成的 .new 文件")
    print("2. 如果满意，请将 .new 文件重命名替换原文件")
    print("3. 请检查生成的翻译文件")

if __name__ == "__main__":
    main()
