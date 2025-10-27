#!/bin/bash
# macOS 应用程序打包脚本
# 在 macOS 系统上运行此脚本来完成最终打包

echo "🍎 macOS 应用程序打包脚本"
echo "================================"

# 从 version.py 读取版本号
VERSION=$(python3 -c "from version import VERSION; print(VERSION)" 2>/dev/null || echo "3.0.0")
echo "📦 版本: v${VERSION}"

# 检查是否在 macOS 上运行
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ 此脚本需要在 macOS 系统上运行"
    exit 1
fi

# 检查输入目录
if [ ! -d "dist_macos/XexunRTT" ]; then
    echo "❌ 未找到构建输出目录 dist_macos/XexunRTT"
    echo "💡 请先运行跨平台构建脚本"
    exit 1
fi

echo "✅ 找到构建输出目录"

# 创建 .app 目录结构
APP_NAME="XexunRTT.app"
APP_DIR="dist_macos_final/$APP_NAME"

echo "📁 创建应用程序包结构..."
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# 复制可执行文件
echo "📋 复制可执行文件..."
cp -r dist_macos/XexunRTT/* "$APP_DIR/Contents/MacOS/"

# 创建 Info.plist
echo "📝 创建 Info.plist..."
cat > "$APP_DIR/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>XexunRTT</string>
    <key>CFBundleDisplayName</key>
    <string>XexunRTT - J-Link RTT Viewer</string>
    <key>CFBundleIdentifier</key>
    <string>com.xexun.rtt2uart</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleExecutable</key>
    <string>XexunRTT</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>XRTT</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.developer-tools</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>NSHumanReadableCopyright</key>
    <string>© 2025 Xexun Technology</string>
</dict>
</plist>
EOF

# 设置可执行权限
echo "🔧 设置可执行权限..."
chmod +x "$APP_DIR/Contents/MacOS/XexunRTT"

# 复制图标（如果存在）
if [ -f "XexunRTT.icns" ]; then
    echo "🎨 复制图标..."
    cp "XexunRTT.icns" "$APP_DIR/Contents/Resources/XexunRTT.icns"
elif [ -f "xexunrtt.ico" ]; then
    echo "🎨 转换并复制图标..."
    sips -s format icns xexunrtt.ico --out "$APP_DIR/Contents/Resources/XexunRTT.icns" 2>/dev/null || echo "⚠️ 图标转换失败，使用默认图标"
fi

echo "✅ 应用程序包创建完成：$APP_DIR"

# 创建 DMG（可选）
read -p "是否创建 DMG 安装包? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 创建 DMG 安装包..."
    
    DMG_NAME="XexunRTT_macOS_v${VERSION}.dmg"
    DMG_TEMP_DIR="dist_macos_final/dmg_temp"
    
    # 创建临时目录
    mkdir -p "$DMG_TEMP_DIR"
    cp -r "$APP_DIR" "$DMG_TEMP_DIR/"
    ln -sf /Applications "$DMG_TEMP_DIR/Applications"
    
    # 创建 DMG
    hdiutil create -volname "XexunRTT" -srcfolder "$DMG_TEMP_DIR" -ov -format UDZO "dist_macos_final/$DMG_NAME"
    
    # 清理临时目录
    rm -rf "$DMG_TEMP_DIR"
    
    echo "✅ DMG 创建完成：dist_macos_final/$DMG_NAME"
fi

echo ""
echo "🎉 macOS 打包完成！"
echo "📱 应用程序：$APP_DIR"
echo ""
echo "🚀 使用方法："
echo "1. 双击运行 XexunRTT.app"
echo "2. 首次运行时在系统偏好设置中允许运行"
echo "3. 确保已安装 J-Link 驱动程序"
