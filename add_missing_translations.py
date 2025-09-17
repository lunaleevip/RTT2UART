#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加缺失的翻译条目
"""

import xml.etree.ElementTree as ET
import subprocess

def add_missing_translations():
    """添加缺失的翻译条目"""
    ts_file = "xexunrtt_en.ts"
    
    # 需要添加的翻译
    missing_translations = {
        "Sent:": "已发送:",
        "Send:": "发送:",
    }
    
    try:
        # 解析XML
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        # 找到main_window context
        main_window_context = None
        for context in root.findall('context'):
            name_elem = context.find('name')
            if name_elem is not None and name_elem.text == 'main_window':
                main_window_context = context
                break
        
        if main_window_context is None:
            print("❌ 找不到main_window context")
            return False
        
        # 检查哪些翻译缺失
        existing_sources = set()
        for message in main_window_context.findall('message'):
            source_elem = message.find('source')
            if source_elem is not None:
                existing_sources.add(source_elem.text)
        
        added_count = 0
        for source_text, translation_text in missing_translations.items():
            if source_text not in existing_sources:
                # 创建新的message元素
                message_elem = ET.SubElement(main_window_context, 'message')
                
                # 添加location元素 (可选)
                location_elem = ET.SubElement(message_elem, 'location')
                location_elem.set('filename', 'main_window.py')
                location_elem.set('line', '2156')  # 大致行号
                
                # 添加source元素
                source_elem = ET.SubElement(message_elem, 'source')
                source_elem.text = source_text
                
                # 添加translation元素
                translation_elem = ET.SubElement(message_elem, 'translation')
                translation_elem.text = translation_text
                
                print(f"✅ 添加翻译: '{source_text}' → '{translation_text}'")
                added_count += 1
            else:
                print(f"ℹ️ 翻译已存在: '{source_text}'")
        
        if added_count > 0:
            # 保存文件
            tree.write(ts_file, encoding='utf-8', xml_declaration=True)
            print(f"✅ 成功添加 {added_count} 条翻译到 {ts_file}")
        else:
            print("ℹ️ 没有需要添加的翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 添加翻译失败: {e}")
        return False

def compile_qm():
    """编译QM文件"""
    try:
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_en.ts", "-qm", "xexunrtt_en.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件编译成功")
            return True
        else:
            print(f"❌ QM文件编译失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 编译QM文件出错: {e}")
        return False

def update_resources():
    """更新资源文件"""
    try:
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
        print(f"❌ 更新资源文件出错: {e}")
        return False

def verify_translations():
    """验证翻译"""
    ts_file = "xexunrtt_en.ts"
    
    try:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键翻译
        key_translations = ["Sent:", "Compact Mode(&M)"]
        
        print("🔍 验证关键翻译:")
        for key in key_translations:
            if key in content:
                print(f"  ✅ '{key}' 存在于翻译文件中")
            else:
                print(f"  ❌ '{key}' 不存在于翻译文件中")
        
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
        
    except Exception as e:
        print(f"❌ 验证翻译失败: {e}")

def main():
    """主函数"""
    print("🔧 添加缺失的翻译条目")
    print("=" * 50)
    
    # 添加缺失的翻译
    if add_missing_translations():
        print("\n📋 验证翻译文件:")
        verify_translations()
        
        print("\n🔨 编译QM文件:")
        if compile_qm():
            print("\n📦 更新资源文件:")
            if update_resources():
                print("\n🎉 所有操作完成！")
                return True
    
    print("❌ 操作失败")
    return False

if __name__ == "__main__":
    main()
