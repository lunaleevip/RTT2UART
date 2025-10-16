#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能修复翻译文件 - 自动填充常见的未完成翻译
"""

import xml.etree.ElementTree as ET
import subprocess
import os

# 常见翻译映射表（工具提示等不需要翻译的内容）
COMMON_TRANSLATIONS = {
    "F1": "F1",
    "F2": "F2",
    "F3": "F3",
    "F4": "F4",
    "F5": "F5",
    "F6": "F6",
    "F7": "F7",
    "F8": "F8",
    "F9": "F9",
    "60": "60",  # 默认超时秒数
    "1": "1",
    "2": "2",
    "...": "...",
    "↻": "↻",  # 刷新按钮符号
}

def fix_unfinished_translations():
    """修复未完成的翻译"""
    print("🔧 智能修复翻译文件")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        total_fixed = 0
        
        # 遍历所有上下文
        for context in root.findall('context'):
            context_name_elem = context.find('name')
            context_name = context_name_elem.text if context_name_elem is not None else "Unknown"
            
            # 遍历所有消息
            for message in context.findall('message'):
                source_elem = message.find('source')
                translation_elem = message.find('translation')
                
                if source_elem is not None and translation_elem is not None:
                    source_text = source_elem.text
                    translation_text = translation_elem.text
                    
                    # 检查是否有 type="unfinished" 标记
                    if 'type' in translation_elem.attrib:
                        attr_type = translation_elem.attrib['type']
                        
                        if attr_type == 'unfinished':
                            # 情况1: 如果已有翻译内容，直接移除unfinished标记
                            if translation_text and translation_text.strip():
                                del translation_elem.attrib['type']
                                print(f"✅ {context_name}: 移除unfinished标记 '{source_text}' → '{translation_text}'")
                                total_fixed += 1
                            
                            # 情况2: 如果是常见的不需要翻译的内容（如F1-F9等）
                            elif source_text in COMMON_TRANSLATIONS:
                                translation_elem.text = COMMON_TRANSLATIONS[source_text]
                                del translation_elem.attrib['type']
                                print(f"✅ {context_name}: 自动填充 '{source_text}' → '{COMMON_TRANSLATIONS[source_text]}'")
                                total_fixed += 1
                            
                            # 情况3: 空翻译，保持unfinished标记，但给出警告
                            else:
                                print(f"⚠️ {context_name}: 需要人工翻译 '{source_text}'")
        
        # 保存文件
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"\n✅ 成功修复 {total_fixed} 条翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 修复翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def recompile_translations():
    """重新编译翻译文件"""
    print("\n🔨 重新编译翻译文件")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["pyside6-lrelease", "xexunrtt_complete.ts", "-qm", "xexunrtt_complete.qm"],
            capture_output=True, text=True, encoding='utf-8'
        )
        
        if result.returncode == 0:
            print("✅ QM文件编译成功")
            print(f"   {result.stdout.strip()}")
            return True
        else:
            print(f"❌ QM文件编译失败")
            print(f"   错误: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 编译失败: {e}")
        return False

def verify_translations():
    """验证翻译状态"""
    print("\n🔍 验证翻译状态")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    with open(ts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    import re
    total_messages = len(re.findall(r'<message>', content))
    unfinished = len(re.findall(r'type="unfinished"', content))
    vanished = len(re.findall(r'type="vanished"', content))
    finished = total_messages - unfinished - vanished
    
    print(f"📊 翻译统计:")
    print(f"  总消息数: {total_messages}")
    print(f"  已完成: {finished}")
    print(f"  未完成: {unfinished}")
    print(f"  已废弃: {vanished}")
    print(f"  完成率: {finished/(total_messages-vanished)*100:.1f}%")
    
    if unfinished > 0:
        print(f"\n⚠️ 仍有 {unfinished} 条未完成的翻译（可能需要人工处理）")
    else:
        print(f"\n✅ 所有翻译已完成！")
    
    return unfinished == 0

def main():
    """主函数"""
    print("🔧 智能修复翻译文件")
    print("=" * 60)
    
    success = True
    
    # 1. 修复未完成的翻译
    if not fix_unfinished_translations():
        success = False
    
    # 2. 重新编译
    if success and not recompile_translations():
        success = False
    
    # 3. 验证结果
    if success:
        verify_translations()
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 翻译文件修复完成！")
        print("\n💡 提示:")
        print("每次修改UI文件后运行 'pyside6-lupdate' 都会重新标记UI翻译为unfinished")
        print("这时只需运行此脚本即可自动修复")
        print("\n🔧 下一步:")
        print("1. 重启程序测试翻译效果")
        print("2. 如需提交，运行: git add xexunrtt_complete.ts xexunrtt_complete.qm")
    else:
        print("❌ 翻译文件修复失败")
    
    return success

if __name__ == "__main__":
    main()

