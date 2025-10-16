#!/bin/bash
# 翻译文件更新脚本 - 自动修复UI翻译问题

echo "======================================"
echo "更新翻译文件"
echo "======================================"

echo ""
echo "[1/4] 提取翻译字符串..."
pyside6-lupdate -verbose main_window.py rtt2uart.py ui_xexunrtt.py ui_sel_device.py ui_rtt2uart_updated.py -ts xexunrtt_complete.ts
if [ $? -ne 0 ]; then
    echo "错误: lupdate失败"
    exit 1
fi

echo ""
echo "[2/4] 修复UI翻译（dialog context）..."
python3 fix_ui_translations.py
if [ $? -ne 0 ]; then
    echo "错误: UI翻译修复失败"
    exit 1
fi

echo ""
echo "[3/4] 添加新增翻译..."
python3 complete_all_missing_translations.py
if [ $? -ne 0 ]; then
    echo "错误: 新增翻译失败"
    exit 1
fi

echo ""
echo "[4/4] 编译翻译文件..."
pyside6-lrelease xexunrtt_complete.ts
if [ $? -ne 0 ]; then
    echo "错误: lrelease失败"
    exit 1
fi

echo ""
echo "======================================"
echo "翻译文件更新完成！"
echo "======================================"

