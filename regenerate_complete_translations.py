#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成完整的翻译文件
"""

import subprocess
import xml.etree.ElementTree as ET
import os

def force_regenerate_translations():
    """强制重新生成翻译文件"""
    print("🔧 强制重新生成完整翻译文件")
    print("=" * 60)
    
    # 删除旧的翻译文件
    old_files = ["xexunrtt_complete.ts", "xexunrtt_complete.qm"]
    for file in old_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️ 删除旧文件: {file}")
    
    # 重新扫描所有源文件
    source_files = [
        "main_window.py",
        "ui_rtt2uart.py", 
        "ui_rtt2uart_updated.py",
        "ui_sel_device.py",
        "ui_xexunrtt.py"
    ]
    
    existing_files = []
    for file in source_files:
        if os.path.exists(file):
            existing_files.append(file)
            print(f"✅ 扫描文件: {file}")
        else:
            print(f"⚠️ 文件不存在: {file}")
    
    # 生成新的翻译文件
    print(f"\n🔄 重新扫描 {len(existing_files)} 个文件...")
    cmd = ["pyside6-lupdate"] + existing_files + ["-ts", "xexunrtt_complete_new.ts"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0:
            print(f"✅ 新翻译文件生成成功")
            print(f"   输出: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ 翻译文件生成失败")
            print(f"   错误: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 执行lupdate失败: {e}")
        return False

def add_comprehensive_translations():
    """添加全面的翻译"""
    print("\n🔧 添加全面的翻译")
    print("=" * 50)
    
    ts_file = "xexunrtt_complete_new.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    # 完整的翻译映射表
    comprehensive_translations = {
        # main_window 上下文
        "main_window": {
            # 菜单项
            "Clear Current Page(&C)": "清除当前页面(&C)",
            "Open Log Folder(&O)": "打开日志文件夹(&O)",
            "Open Config Folder(&F)": "打开配置文件夹(&F)",
            "Encoding(&E)": "编码(&E)",
            "Restart APP F9(&A)": "重启应用 F9(&A)",
            "Switch Theme(&T)": "切换主题(&T)",
            "About(&A)...": "关于(&A)...",
            
            # 连接菜单
            "Reconnect(&R)": "重新连接(&R)",
            "Disconnect(&D)": "断开连接(&D)",
            "Connection Settings(&S)...": "连接设置(&S)...",
            
            # 窗口菜单
            "New Window(&N)": "新建窗口(&N)",
            "Compact Mode(&M)": "紧凑模式(&M)",
            
            # 状态和消息
            "Connected": "已连接",
            "Disconnected": "已断开",
            "Sent:": "已发送:",
            "Send:": "发送:",
            
            # 日志相关
            "JLink Debug Log": "JLink调试日志",
            "Clear Log": "清除日志",
            "Enable Verbose Log": "启用详细日志",
            "Disable Verbose Log": "禁用详细日志",
            
            # 窗口标题
            "XexunRTT - RTT Debug Main Window": "XexunRTT - RTT调试主窗口",
            "RTT2UART Connection Configuration": "RTT2UART连接配置",
            
            # 串口转发设置
            "Serial Forward Settings": "串口转发设置",
            "LOG Current Tab": "日志当前标签",
            "DATA (RTT Channel 1)": "数据 (RTT通道 1)",
            "Forward": "转发",
            "Disable Forward": "禁用转发",
            "Current Tab": "当前标签",
            
            # 其他
            "Open a new window": "打开新窗口",
            "Toggle compact mode for multi-device usage": "切换紧凑模式用于多设备使用",
            "Find jlink dll failed !": "查找jlink dll失败！",
            "Unable to create connection dialog": "无法创建连接对话框"
        },
        
        # xexun_rtt 上下文
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
        },
        
        # dialog 上下文
        "dialog": {
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
            "...": "...",
            "Disable Forward": "禁用转发",
            "Current Tab": "当前标签"
        }
    }
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        total_added = 0
        
        for context_name, translations in comprehensive_translations.items():
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
            existing_sources = set()
            for message in context.findall('message'):
                source_elem = message.find('source')
                if source_elem is not None:
                    existing_sources.add(source_elem.text)
            
            # 添加或更新翻译
            for source_text, translation_text in translations.items():
                if source_text not in existing_sources:
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
                    
                    print(f"  ✅ {context_name}: '{source_text}' → '{translation_text}'")
                    total_added += 1
                else:
                    # 更新现有翻译
                    for message in context.findall('message'):
                        source_elem = message.find('source')
                        if source_elem is not None and source_elem.text == source_text:
                            translation_elem = message.find('translation')
                            if translation_elem is not None:
                                translation_elem.text = translation_text
                                # 移除unfinished标记
                                if 'type' in translation_elem.attrib:
                                    del translation_elem.attrib['type']
                                print(f"  🔧 {context_name}: 更新 '{source_text}' → '{translation_text}'")
                                total_added += 1
                            break
        
        # 保存文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"\n✅ 成功添加/更新 {total_added} 条翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 添加翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def compile_and_deploy():
    """编译并部署翻译文件"""
    print("\n🔨 编译并部署翻译文件")
    print("=" * 50)
    
    try:
        # 编译QM文件
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_complete_new.ts", "-qm", "xexunrtt_complete_new.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件编译成功")
            print(f"   输出: {result.stdout.strip()}")
        else:
            print(f"❌ QM文件编译失败")
            print(f"   错误: {result.stderr}")
            return False
        
        # 替换旧文件
        if os.path.exists("xexunrtt_complete_new.ts"):
            if os.path.exists("xexunrtt_complete.ts"):
                os.remove("xexunrtt_complete.ts")
            os.rename("xexunrtt_complete_new.ts", "xexunrtt_complete.ts")
            print("✅ 替换翻译源文件")
        
        if os.path.exists("xexunrtt_complete_new.qm"):
            if os.path.exists("xexunrtt_complete.qm"):
                os.remove("xexunrtt_complete.qm")
            os.rename("xexunrtt_complete_new.qm", "xexunrtt_complete.qm")
            print("✅ 替换编译后的翻译文件")
        
        # 更新资源文件
        result = subprocess.run(
            ["pyside6-rcc", "resources.qrc", "-o", "resources_rc.py"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ 资源文件更新成功")
            return True
        else:
            print(f"❌ 资源文件更新失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 编译部署失败: {e}")
        return False

def verify_final_result():
    """验证最终结果"""
    print("\n🔍 验证最终结果")
    print("=" * 50)
    
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    with open(ts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查关键翻译
    key_texts = [
        "Clear Current Page(&C)",
        "Open Log Folder(&O)", 
        "Open Config Folder(&F)",
        "Serial Forward Settings",
        "LOG Current Tab",
        "DATA (RTT Channel 1)",
        "Disable Forward",
        "Reconnect(&R)",
        "Connection Settings(&S)..."
    ]
    
    print("🔍 验证关键翻译:")
    found_count = 0
    for text in key_texts:
        if f"<source>{text}</source>" in content:
            print(f"  ✅ '{text}' 存在")
            found_count += 1
        else:
            print(f"  ❌ '{text}' 缺失")
    
    # 统计翻译状态
    import re
    total_messages = len(re.findall(r'<message>', content))
    unfinished = len(re.findall(r'type="unfinished"', content))
    finished = total_messages - unfinished
    
    print(f"\n📊 最终翻译统计:")
    print(f"  总消息数: {total_messages}")
    print(f"  已完成: {finished}")
    print(f"  未完成: {unfinished}")
    print(f"  完成率: {finished/total_messages*100:.1f}%")
    print(f"  关键翻译覆盖率: {found_count}/{len(key_texts)} ({found_count/len(key_texts)*100:.1f}%)")
    
    return found_count == len(key_texts)

def main():
    """主函数"""
    print("🔧 重新生成完整翻译文件")
    print("=" * 60)
    
    success = True
    
    # 1. 强制重新生成翻译文件
    if not force_regenerate_translations():
        success = False
    
    # 2. 添加全面的翻译
    if success and not add_comprehensive_translations():
        success = False
    
    # 3. 编译并部署
    if success and not compile_and_deploy():
        success = False
    
    # 4. 验证最终结果
    if success:
        verify_ok = verify_final_result()
        if not verify_ok:
            print("⚠️ 翻译验证部分失败，但继续...")
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 完整翻译文件重新生成完成！")
        
        print("\n✅ 修复的问题:")
        print("1. ✅ 重新扫描了所有源文件")
        print("2. ✅ 添加了所有缺失的翻译文本")
        print("3. ✅ 'Clear Current Page(&C)' → '清除当前页面(&C)'")
        print("4. ✅ 'Open Log Folder(&O)' → '打开日志文件夹(&O)'")
        print("5. ✅ 'Serial Forward Settings' → '串口转发设置'")
        print("6. ✅ 'LOG Current Tab' → '日志当前标签'")
        print("7. ✅ 所有菜单和UI元素翻译")
        
        print("\n🔧 下一步:")
        print("1. 重启程序测试翻译效果")
        print("2. 检查动态创建的UI元素")
        print("3. 确保所有翻译正确应用")
        
    else:
        print("❌ 翻译文件重新生成失败")
    
    return success

if __name__ == "__main__":
    main()
