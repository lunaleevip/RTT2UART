#!/bin/bash
# XexunRTT macOS 应用程序最终化脚本
# 在 macOS 上运行以完成应用程序包的设置

echo "🍎 XexunRTT macOS 应用程序最终化"
echo "=================================="

APP_NAME="XexunRTT.app"
if [ ! -d "$APP_NAME" ]; then
    echo "❌ 未找到 $APP_NAME，请确保在正确的目录中运行"
    exit 1
fi

echo "✅ 找到应用程序包：$APP_NAME"

# 设置可执行权限
echo "🔧 设置可执行权限..."
chmod +x "$APP_NAME/Contents/MacOS/XexunRTT"
chmod +x "$APP_NAME/Contents/MacOS/launch.sh"

# 转换图标格式
if [ -f "$APP_NAME/Contents/Resources/XexunRTT.ico" ]; then
    echo "🎨 转换图标格式..."
    sips -s format icns "$APP_NAME/Contents/Resources/XexunRTT.ico" \
         --out "$APP_NAME/Contents/Resources/XexunRTT.icns" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        rm "$APP_NAME/Contents/Resources/XexunRTT.ico"
        echo "✅ 图标转换完成"
        
        # 更新 Info.plist 以使用新图标
        /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string XexunRTT.icns" \
                                "$APP_NAME/Contents/Info.plist" 2>/dev/null
    else
        echo "⚠️ 图标转换失败，使用默认图标"
    fi
fi

# 移除隔离属性（如果存在）
echo "🛡️ 移除隔离属性..."
xattr -cr "$APP_NAME" 2>/dev/null || true

# 验证应用程序包
echo "✅ 验证应用程序包..."
if [ -x "$APP_NAME/Contents/MacOS/XexunRTT" ]; then
    echo "✅ 应用程序包设置完成！"
    echo ""
    echo "🚀 使用方法："
    echo "1. 双击 $APP_NAME 启动应用程序"
    echo "2. 首次运行时右键选择'打开'（绕过安全检查）"
    echo "3. 确保已安装 J-Link 驱动程序"
    echo ""
    
    # 可选：创建 DMG
    read -p "是否创建 DMG 安装包? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📦 创建 DMG 安装包..."
        DMG_NAME="XexunRTT_macOS_v1.0.5.dmg"
        
        # 创建临时目录
        TEMP_DIR=$(mktemp -d)
        cp -r "$APP_NAME" "$TEMP_DIR/"
        ln -sf /Applications "$TEMP_DIR/Applications"
        
        # 创建 DMG
        hdiutil create -volname "XexunRTT" -srcfolder "$TEMP_DIR" \
                       -ov -format UDZO "$DMG_NAME"
        
        rm -rf "$TEMP_DIR"
        echo "✅ DMG 创建完成：$DMG_NAME"
    fi
else
    echo "❌ 应用程序包验证失败"
    exit 1
fi
