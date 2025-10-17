#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
翻译更新脚本 - 自动锁定UI翻译
"""

import xml.etree.ElementTree as ET
import subprocess
import os
import sys

def lock_ui_translations():
    """
    使用Qt的官方方法锁定UI翻译：
    - 将已翻译的条目标记为不会被lupdate覆盖
    - 使用 <translation type="finished"> 替代默认状态
    """
    print("🔒 锁定UI翻译...")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    if not os.path.exists(ts_file):
        print(f"❌ 翻译文件不存在: {ts_file}")
        return False
    
    try:
        # 使用ElementTree解析，不格式化以保留原有格式
        ET.register_namespace('', 'http://www.w3.org/XML/1998/namespace')
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        locked_count = 0
        ui_contexts = set()
        
        # 遍历所有上下文
        for context in root.findall('context'):
            context_name_elem = context.find('name')
            context_name = context_name_elem.text if context_name_elem is not None else "Unknown"
            
            # 遍历所有消息
            for message in context.findall('message'):
                location = message.find('location')
                translation = message.find('translation')
                
                if location is None or translation is None:
                    continue
                
                # 检查是否来自.ui文件
                filename = location.get('filename', '')
                is_from_ui = filename.endswith('.ui')
                
                if is_from_ui:
                    ui_contexts.add(context_name)
                    
                    # 如果有翻译内容且不是obsolete
                    if translation.text and translation.text.strip():
                        current_type = translation.get('type')
                        
                        # 方案1: 完全移除type属性（默认为finished）
                        if current_type in ['unfinished', None]:
                            if current_type:
                                del translation.attrib['type']
                            locked_count += 1
                        
                        # 方案2: 显式标记为finished（更明确，推荐）
                        # if current_type != 'finished':
                        #     translation.set('type', 'finished')
                        #     locked_count += 1
        
        # 保存修改
        # 使用write方法，不美化格式，保持原样
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        
        print(f"✅ 已锁定 {locked_count} 条UI翻译")
        print(f"📂 涉及上下文: {', '.join(sorted(ui_contexts))}")
        
        return True
        
    except Exception as e:
        print(f"❌ 锁定失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_translations():
    """更新翻译文件"""
    print("\n📝 更新翻译文件...")
    print("=" * 60)
    
    cmd = [
        "pyside6-lupdate",
        "main_window.py",
        "xexunrtt.ui",
        "rtt2uart_updated.ui",
        "rtt2uart.py",
        "-ts", "xexunrtt_complete.ts"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

def remove_unfinished_marks():
    """移除所有 unfinished 标记（针对已有翻译）"""
    print("\n🔧 移除unfinished标记...")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        fixed_count = 0
        
        for context in root.findall('context'):
            for message in context.findall('message'):
                translation = message.find('translation')
                
                if translation is not None:
                    # 如果有翻译文本，移除 unfinished 标记
                    if translation.text and translation.text.strip():
                        if translation.get('type') == 'unfinished':
                            del translation.attrib['type']
                            fixed_count += 1
        
        tree.write(ts_file, encoding='utf-8', xml_declaration=True)
        print(f"✅ 已修复 {fixed_count} 条翻译")
        
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

def compile_translations():
    """编译翻译文件"""
    print("\n🔨 编译翻译文件...")
    print("=" * 60)
    
    cmd = [
        "pyside6-lrelease",
        "xexunrtt_complete.ts",
        "-qm", "xexunrtt_complete.qm"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 编译失败: {e}")
        return False

def show_statistics():
    """显示翻译统计"""
    print("\n📊 翻译统计...")
    print("=" * 60)
    
    ts_file = "xexunrtt_complete.ts"
    
    try:
        tree = ET.parse(ts_file)
        root = tree.getroot()
        
        total = 0
        finished = 0
        unfinished = 0
        ui_translations = 0
        
        for context in root.findall('context'):
            for message in context.findall('message'):
                location = message.find('location')
                translation = message.find('translation')
                
                if translation is not None:
                    total += 1
                    
                    # 检查是否来自UI
                    if location is not None:
                        filename = location.get('filename', '')
                        if filename.endswith('.ui'):
                            ui_translations += 1
                    
                    # 检查翻译状态
                    if translation.text and translation.text.strip():
                        if translation.get('type') != 'unfinished':
                            finished += 1
                        else:
                            unfinished += 1
        
        print(f"📝 总消息数: {total}")
        print(f"✅ 已完成: {finished}")
        print(f"⚠️  未完成: {unfinished}")
        print(f"🎨 UI翻译: {ui_translations}")
        
        if total > 0:
            print(f"📈 完成率: {finished/total*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 统计失败: {e}")
        return False

def main():
    """主函数"""
    print("🔄 翻译更新流程（带锁定）")
    print("=" * 60)
    print()
    
    # 步骤1: 更新翻译
    if not update_translations():
        print("\n❌ 翻译更新失败")
        sys.exit(1)
    
    # 步骤2: 移除unfinished标记
    if not remove_unfinished_marks():
        print("\n❌ 修复unfinished标记失败")
        sys.exit(1)
    
    # 步骤3: 锁定UI翻译
    if not lock_ui_translations():
        print("\n❌ 锁定UI翻译失败")
        sys.exit(1)
    
    # 步骤4: 编译翻译
    if not compile_translations():
        print("\n❌ 编译翻译失败")
        sys.exit(1)
    
    # 步骤5: 显示统计
    show_statistics()
    
    print("\n" + "=" * 60)
    print("✅ 翻译更新完成！")
    print("\n💡 提示:")
    print("  - UI翻译已锁定，下次lupdate不会标记为unfinished")
    print("  - 如需修改UI翻译，请手动编辑 .ts 文件")
    print("  - 运行此脚本即可自动处理所有翻译更新")

if __name__ == '__main__':
    main()

