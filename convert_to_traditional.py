#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简体中文翻译文件转换为繁体中文

使用 OpenCC 将 xexunrtt_complete.ts 中的简体中文翻译转换为繁体中文
"""

import re
from opencc import OpenCC

def convert_ts_to_traditional(input_file, output_file):
    """将翻译文件中的简体中文转换为繁体中文"""
    
    # 创建简体到繁体的转换器
    cc = OpenCC('s2twp')  # s2twp: Simplified Chinese to Traditional Chinese (Taiwan standard with phrases)
    
    print(f"读取文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 正则表达式匹配 <translation> 标签中的内容
    def replace_translation(match):
        """替换翻译内容"""
        opening_tag = match.group(1)
        translation_text = match.group(2)
        closing_tag = match.group(3)
        
        # 转换为繁体中文
        traditional_text = cc.convert(translation_text)
        
        return f"{opening_tag}{traditional_text}{closing_tag}"
    
    print("转换简体中文到繁体中文...")
    # 匹配 <translation>内容</translation> 或 <translation type="...">内容</translation>
    pattern = r'(<translation[^>]*>)(.*?)(</translation>)'
    new_content = re.sub(pattern, replace_translation, content, flags=re.DOTALL)
    
    # 同时转换 <source> 标签中的中文（如果有的话）
    def replace_source(match):
        """替换源文本（如果包含中文）"""
        opening_tag = match.group(1)
        source_text = match.group(2)
        closing_tag = match.group(3)
        
        # 只转换包含中文的源文本
        if any('\u4e00' <= char <= '\u9fff' for char in source_text):
            traditional_text = cc.convert(source_text)
            return f"{opening_tag}{traditional_text}{closing_tag}"
        else:
            return match.group(0)
    
    pattern_source = r'(<source>)(.*?)(</source>)'
    new_content = re.sub(pattern_source, replace_source, new_content, flags=re.DOTALL)
    
    # 更新语言标记
    new_content = new_content.replace(
        '<TS version="2.1" language="zh_CN">',
        '<TS version="2.1" language="zh_TW">'
    )
    
    print(f"保存繁体文件: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("[OK] 转换完成!")
    print()
    print("[STATS] 统计信息:")
    
    # 统计翻译数量
    translation_count = len(re.findall(r'<translation[^>]*>.*?</translation>', new_content, re.DOTALL))
    print(f"   翻译条目数: {translation_count}")
    
    # 统计包含中文的翻译
    chinese_translations = [m for m in re.finditer(r'<translation[^>]*>(.*?)</translation>', new_content, re.DOTALL)
                           if any('\u4e00' <= char <= '\u9fff' for char in m.group(1))]
    print(f"   包含中文的翻译: {len(chinese_translations)}")
    
    print()
    print("[NEXT] 下一步:")
    print(f"   1. 检查生成的文件: {output_file}")
    print(f"   2. 编译为 .qm 文件:")
    print(f"      pyside6-lrelease {output_file} -qm {output_file.replace('.ts', '.qm')}")
    print(f"   3. 测试繁体中文界面")

if __name__ == '__main__':
    try:
        convert_ts_to_traditional('xexunrtt_complete.ts', 'xexunrtt_zh_TW.ts')
    except Exception as e:
        print(f"[ERROR] 转换失败: {e}")
        import traceback
        traceback.print_exc()

