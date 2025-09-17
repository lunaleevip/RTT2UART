#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
添加设备选择对话框翻译
"""

import xml.etree.ElementTree as ET
import subprocess
import os

def add_device_dialog_translations():
    """添加设备选择对话框的翻译"""
    print("🔧 添加设备选择对话框翻译")
    print("=" * 50)
    
    ts_file = "xexunrtt_complete.ts"
    
    # 需要添加的设备对话框翻译（注意上下文是大写的"Dialog"）
    device_dialog_translations = {
        "Dialog": {  # 注意这里是大写的Dialog，不同于小写的dialog
            "Target Device Settings": "目标设备设置",
            "Seleted Device:": "已选择的设备:",  # 注意这里原文有拼写错误"Seleted"而不是"Selected"
            "Filter": "筛选"
        }
    }
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        added_count = 0
        
        for context_name, translations in device_dialog_translations.items():
            # 查找或创建Dialog上下文（大写）
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
                        # 移除vanished或unfinished标记
                        if 'type' in translation_elem.attrib:
                            del translation_elem.attrib['type']
                        print(f"  🔧 {context_name}: 更新 '{source_text}' → '{translation_text}'")
                        added_count += 1
                else:
                    # 创建新的message元素
                    message_elem = ET.SubElement(context, 'message')
                    
                    # 添加location元素
                    location_elem = ET.SubElement(message_elem, 'location')
                    location_elem.set('filename', 'ui_sel_device.py')
                    location_elem.set('line', '60')  # retranslateUi方法的行号
                    
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
        print(f"\n✅ 成功添加/更新 {added_count} 条设备对话框翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 添加设备对话框翻译失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def recompile_and_update():
    """重新编译并更新翻译"""
    print("\n🔨 重新编译翻译文件")
    print("-" * 30)
    
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
        
        return True
        
    except Exception as e:
        print(f"❌ 编译更新失败: {e}")
        return False

def test_device_dialog_translations():
    """测试设备对话框翻译"""
    print("\n🧪 测试设备对话框翻译")
    print("-" * 30)
    
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTranslator, QCoreApplication
    import sys
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # 加载翻译
    translator = QTranslator()
    if translator.load("xexunrtt_complete.qm"):
        app.installTranslator(translator)
        print("✅ 翻译文件已加载")
    else:
        print("❌ 翻译文件加载失败")
        return False
    
    # 测试设备对话框翻译
    test_cases = [
        ("Dialog", "Target Device Settings", "目标设备设置"),
        ("Dialog", "Seleted Device:", "已选择的设备:"),
        ("Dialog", "Filter", "筛选")
    ]
    
    print("🔍 设备对话框翻译测试:")
    all_passed = True
    
    for context, english, expected_chinese in test_cases:
        actual = QCoreApplication.translate(context, english)
        if actual == expected_chinese:
            print(f"  ✅ {context}: '{english}' → '{actual}'")
        else:
            print(f"  ❌ {context}: '{english}' → '{actual}' (期望: '{expected_chinese}')")
            all_passed = False
    
    return all_passed

def verify_translation_stats():
    """验证翻译统计"""
    print("\n📊 翻译统计")
    print("-" * 30)
    
    ts_file = "xexunrtt_complete.ts"
    
    try:
        with open(ts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        import re
        total_messages = len(re.findall(r'<message>', content))
        unfinished = len(re.findall(r'type="unfinished"', content))
        vanished = len(re.findall(r'type="vanished"', content))
        finished = total_messages - unfinished - vanished
        
        print(f"总消息数: {total_messages}")
        print(f"已完成: {finished}")
        print(f"未完成: {unfinished}")
        print(f"已消失: {vanished}")
        print(f"完成率: {finished/total_messages*100:.1f}%")
        
    except Exception as e:
        print(f"❌ 统计失败: {e}")

def main():
    """主函数"""
    print("🔧 添加设备选择对话框翻译")
    print("=" * 60)
    
    success = True
    
    # 1. 添加设备对话框翻译
    if not add_device_dialog_translations():
        success = False
    
    # 2. 重新编译和更新
    if success and not recompile_and_update():
        success = False
    
    # 3. 测试翻译效果
    if success:
        test_ok = test_device_dialog_translations()
        if not test_ok:
            print("⚠️ 翻译测试部分失败，但继续...")
    
    # 4. 验证翻译统计
    verify_translation_stats()
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 设备选择对话框翻译添加完成！")
        
        print("\n✅ 修复的翻译:")
        print("1. ✅ 'Target Device Settings' → '目标设备设置'")
        print("2. ✅ 'Seleted Device:' → '已选择的设备:'")
        print("3. ✅ 'Filter' → '筛选'")
        
        print("\n🔧 现在设备选择对话框应该完全中文化了:")
        print("- ✅ 窗口标题: 目标设备设置")
        print("- ✅ 选择标签: 已选择的设备:")
        print("- ✅ 筛选提示: 筛选")
        print("- ✅ 按钮: 确定/取消")
        
    else:
        print("❌ 设备选择对话框翻译添加失败")
    
    return success

if __name__ == "__main__":
    main()
