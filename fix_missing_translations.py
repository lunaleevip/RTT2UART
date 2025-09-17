#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复缺失的翻译
"""

import xml.etree.ElementTree as ET
import subprocess

def fix_translations():
    """修复翻译文件中缺失的翻译"""
    ts_file = "xexunrtt_en.ts"
    
    # 补充翻译映射
    additional_translations = {
        "ALL window displays summary data from all channels and doesn't support clear operation.\nPlease switch to specific RTT channel (0-15) to clear.": 
        "ALL窗口显示所有通道的汇总数据，不支持清屏操作。\n请切换到具体的RTT通道（0-15）进行清屏。",
        
        "{} - {}": "{} - {}",
        
        # 确保这些翻译正确
        "Compact Mode(&M)": "紧凑模式(&M)",
        "Sent:": "已发送:",
        "Send:": "发送:",
    }
    
    try:
        # 解析XML
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        updated_count = 0
        
        # 遍历所有message
        for context in root.findall('context'):
            for message in context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    
                    # 检查是否在补充翻译中
                    if source_text in additional_translations:
                        translation_elem.text = additional_translations[source_text]
                        # 移除unfinished属性
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                        updated_count += 1
                        print(f"更新翻译: '{source_text}' -> '{additional_translations[source_text]}'")
        
        # 保存文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"✅ 更新了 {updated_count} 条翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新翻译失败: {e}")
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

def check_translation_status():
    """检查翻译状态"""
    ts_file = "xexunrtt_en.ts"
    
    try:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 统计
        import re
        total_messages = len(re.findall(r'<message>', content))
        unfinished = len(re.findall(r'type="unfinished"', content))
        finished = total_messages - unfinished
        
        print(f"📊 翻译状态:")
        print(f"   总消息数: {total_messages}")
        print(f"   已完成: {finished}")
        print(f"   未完成: {unfinished}")
        
        if unfinished > 0:
            print(f"\n⚠️ 未完成的翻译:")
            # 找出未完成的翻译
            unfinished_matches = re.finditer(
                r'<source>(.*?)</source>\s*<translation type="unfinished"',
                content, re.DOTALL
            )
            
            for i, match in enumerate(unfinished_matches):
                if i < 5:  # 只显示前5个
                    source_text = match.group(1).strip()
                    print(f"   {i+1}. '{source_text}'")
        
    except Exception as e:
        print(f"❌ 检查翻译状态失败: {e}")

def main():
    """主函数"""
    print("🔧 修复缺失的翻译...")
    
    # 检查当前状态
    print("1. 检查当前翻译状态:")
    check_translation_status()
    
    # 修复翻译
    print("\n2. 修复翻译:")
    if fix_translations():
        print("✅ 翻译修复成功")
        
        # 重新检查
        print("\n3. 重新检查翻译状态:")
        check_translation_status()
        
        # 编译QM文件
        print("\n4. 编译QM文件:")
        if compile_qm():
            print("✅ 所有操作完成")
        else:
            print("❌ QM编译失败")
    else:
        print("❌ 翻译修复失败")

if __name__ == "__main__":
    main()
