#!/bin/bash
# 简单的 DMG 打包脚本
# 直接使用 dist/XexunRTT.app 创建 DMG

echo "📦 XexunRTT DMG 打包脚本"
echo "================================"

# 从 version.py 读取版本号
VERSION=$(python3 -c "from version import VERSION; print(VERSION)" 2>/dev/null || echo "3.0.0")
echo "📦 版本: v${VERSION}"

# 检查是否在 macOS 上运行
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ 此脚本需要在 macOS 系统上运行"
    exit 1
fi

# 检查 app 是否存在
if [ ! -d "dist/XexunRTT.app" ]; then
    echo "❌ 未找到 dist/XexunRTT.app"
    echo "💡 请先运行: python3 build.py"
    exit 1
fi

echo "✅ 找到应用程序包: dist/XexunRTT.app"

# 显示 app 大小
APP_SIZE=$(du -sh dist/XexunRTT.app | cut -f1)
echo "📏 应用程序大小: ${APP_SIZE}"

# 创建输出目录
mkdir -p dist_macos_final

# DMG 文件名
DMG_NAME="XexunRTT_macOS_v${VERSION}.dmg"
DMG_TEMP_DIR="dist_macos_final/dmg_temp"

echo "📁 准备 DMG 临时目录..."
# 清理旧的临时目录
rm -rf "$DMG_TEMP_DIR"
mkdir -p "$DMG_TEMP_DIR"

# 复制 app 到临时目录（使用 ditto 保留符号链接）
echo "📋 复制应用程序..."
ditto "dist/XexunRTT.app" "$DMG_TEMP_DIR/XexunRTT.app"

# 创建 Applications 文件夹的符号链接，方便拖拽安装
echo "🔗 创建 Applications 链接..."
ln -s /Applications "$DMG_TEMP_DIR/Applications"

# 删除旧的 DMG
if [ -f "dist_macos_final/$DMG_NAME" ]; then
    echo "🗑️  删除旧的 DMG 文件..."
    rm "dist_macos_final/$DMG_NAME"
fi

# 创建 DMG
echo "🔨 创建 DMG 文件..."
hdiutil create \
    -volname "XexunRTT v${VERSION}" \
    -srcfolder "$DMG_TEMP_DIR" \
    -ov \
    -format UDZO \
    "dist_macos_final/$DMG_NAME"

# 清理临时目录
echo "🧹 清理临时文件..."
rm -rf "$DMG_TEMP_DIR"

# 显示结果
if [ -f "dist_macos_final/$DMG_NAME" ]; then
    DMG_SIZE=$(du -sh "dist_macos_final/$DMG_NAME" | cut -f1)
    echo ""
    echo "============================================"
    echo "✅ DMG 创建成功！"
    echo "============================================"
    echo "📦 文件: dist_macos_final/$DMG_NAME"
    echo "📏 大小: ${DMG_SIZE}"
    echo "🎯 版本: v${VERSION}"
    echo "============================================"
else
    echo "❌ DMG 创建失败"
    exit 1
fi

