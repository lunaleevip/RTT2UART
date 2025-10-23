#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT 完整 macOS 构建脚本
在 Windows 上尽可能完成 macOS 应用程序包的创建
"""

import os
import sys
import shutil
import subprocess
import platform
import json
import zipfile
from pathlib import Path
import tempfile

def create_app_bundle_structure(source_dir, output_dir):
    """在 Windows 上创建 macOS .app 目录结构"""
    print("📁 创建 macOS 应用程序包结构...")
    
    app_name = "XexunRTT.app"
    app_path = Path(output_dir) / app_name
    
    # 创建 .app 目录结构
    contents_dir = app_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    
    # 创建目录
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"✅ 创建目录结构：{app_path}")
    
    # 复制应用程序文件
    source_path = Path(source_dir)
    if source_path.exists():
        print("📋 复制应用程序文件...")
        
        # 复制所有文件到 MacOS 目录
        for item in source_path.rglob("*"):
            if item.is_file():
                relative_path = item.relative_to(source_path)
                target_path = macos_dir / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_path)
        
        print(f"✅ 文件复制完成：{len(list(source_path.rglob('*')))} 个文件")
    
    return app_path

def create_info_plist(app_path):
    """创建 Info.plist 文件"""
    print("📝 创建 Info.plist...")
    
    plist_content = """<?xml version="1.0" encoding="UTF-8"?>
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
    <string>2.1.3</string>
    <key>CFBundleShortVersionString</key>
    <string>2.1.3</string>
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
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>log</string>
                <string>txt</string>
            </array>
            <key>CFBundleTypeName</key>
            <string>Log Files</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSHandlerRank</key>
            <string>Alternate</string>
        </dict>
    </array>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>"""
    
    plist_path = app_path / "Contents" / "Info.plist"
    with open(plist_path, 'w', encoding='utf-8') as f:
        f.write(plist_content)
    
    print(f"✅ Info.plist 创建完成：{plist_path}")
    return plist_path

def convert_icon_to_icns(ico_path, app_path):
    """尝试创建 macOS 图标（模拟）"""
    print("🎨 处理应用程序图标...")
    
    if not Path(ico_path).exists():
        print("⚠️ 未找到图标文件，将使用默认图标")
        return None
    
    # 在 Windows 上无法真正转换为 .icns，但可以复制原文件
    # 在 macOS 上运行时会自动转换
    resources_dir = app_path / "Contents" / "Resources"
    icon_source = Path(ico_path)
    icon_target = resources_dir / "XexunRTT.ico"
    
    shutil.copy2(icon_source, icon_target)
    print(f"✅ 图标文件已复制：{icon_target}")
    print("💡 在 macOS 上运行时将自动转换为 .icns 格式")
    
    return icon_target

def create_macos_launch_script(app_path):
    """创建 macOS 启动脚本"""
    print("📜 创建 macOS 启动脚本...")
    
    script_content = '''#!/bin/bash
# XexunRTT macOS 启动脚本

# 获取应用程序包路径
APP_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENTS_PATH="$(dirname "$APP_PATH")"
MACOS_PATH="$APP_PATH"

# 设置环境变量
export DYLD_LIBRARY_PATH="$MACOS_PATH:$DYLD_LIBRARY_PATH"
export PYTHONPATH="$MACOS_PATH:$PYTHONPATH"

# 启动应用程序
cd "$MACOS_PATH"
exec "$MACOS_PATH/XexunRTT" "$@"
'''
    
    # 在 Windows 上创建，到 macOS 上会设置执行权限
    script_path = app_path / "Contents" / "MacOS" / "launch.sh"
    with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(script_content)
    
    print(f"✅ 启动脚本创建完成：{script_path}")
    return script_path

def create_macos_finalize_script(output_dir):
    """创建 macOS 最终化脚本"""
    print("🔧 创建 macOS 最终化脚本...")
    
    script_content = '''#!/bin/bash
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
    sips -s format icns "$APP_NAME/Contents/Resources/XexunRTT.ico" \\
         --out "$APP_NAME/Contents/Resources/XexunRTT.icns" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        rm "$APP_NAME/Contents/Resources/XexunRTT.ico"
        echo "✅ 图标转换完成"
        
        # 更新 Info.plist 以使用新图标
        /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string XexunRTT.icns" \\
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
        hdiutil create -volname "XexunRTT" -srcfolder "$TEMP_DIR" \\
                       -ov -format UDZO "$DMG_NAME"
        
        rm -rf "$TEMP_DIR"
        echo "✅ DMG 创建完成：$DMG_NAME"
    fi
else
    echo "❌ 应用程序包验证失败"
    exit 1
fi
'''
    
    script_path = Path(output_dir) / "finalize_macos_app.sh"
    with open(script_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(script_content)
    
    print(f"✅ 最终化脚本创建完成：{script_path}")
    return script_path

def create_complete_package(source_dir, output_dir):
    """创建完整的 macOS 分发包"""
    print("📦 创建完整的 macOS 分发包...")
    
    # 创建输出目录
    package_dir = Path(output_dir) / "XexunRTT_macOS_Package"
    package_dir.mkdir(exist_ok=True)
    
    # 1. 创建 .app 包结构
    app_path = create_app_bundle_structure(source_dir, package_dir)
    
    # 2. 创建 Info.plist
    create_info_plist(app_path)
    
    # 3. 处理图标
    convert_icon_to_icns("xexunrtt.ico", app_path)
    
    # 4. 创建启动脚本
    create_macos_launch_script(app_path)
    
    # 5. 创建最终化脚本
    finalize_script = create_macos_finalize_script(package_dir)
    
    # 6. 复制说明文档
    docs_to_copy = [
        "macOS_Quick_Start.md",
        "macOS_Build_Guide.md", 
        "README.md"
    ]
    
    for doc in docs_to_copy:
        if Path(doc).exists():
            shutil.copy2(doc, package_dir / doc)
    
    # 7. 创建说明文件
    readme_content = """# XexunRTT macOS 应用程序包

## 📦 包内容
- XexunRTT.app - macOS 应用程序（需要最终化）
- finalize_macos_app.sh - 最终化脚本
- 相关文档

## 🚀 安装步骤

### 1. 运行最终化脚本
```bash
./finalize_macos_app.sh
```

### 2. 首次运行
- 右键点击 XexunRTT.app
- 选择"打开"
- 在安全对话框中选择"打开"

### 3. 安装 J-Link 驱动
访问 https://www.segger.com/downloads/jlink/ 下载适合 macOS 的驱动

## ⚠️ 注意事项
- 此包在 Windows 上生成，需要在 macOS 上完成最终设置
- 首次运行需要绕过 macOS 安全检查
- 确保 macOS 版本 10.13 或更高

享受使用 XexunRTT！
"""
    
    with open(package_dir / "README_INSTALL.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    return package_dir

def main():
    """主函数"""
    print("🍎 XexunRTT 完整 macOS 构建工具")
    print("=" * 50)
    print("💡 在 Windows 上创建尽可能完整的 macOS 应用程序包")
    print()
    
    # 检查源目录
    source_dir = "dist_macos/XexunRTT"
    if not Path(source_dir).exists():
        print("❌ 未找到构建输出目录")
        print("💡 请先运行：python build_cross_platform.py")
        return False
    
    # 创建完整的 macOS 包
    try:
        package_dir = create_complete_package(source_dir, ".")
        
        print("\n" + "=" * 50)
        print("🎉 完整 macOS 包创建成功！")
        print("-" * 50)
        print(f"📦 包位置：{package_dir}")
        print()
        print("📋 包内容：")
        print("  ├── XexunRTT.app/ (应用程序包)")
        print("  ├── finalize_macos_app.sh (最终化脚本)")
        print("  ├── README_INSTALL.md (安装说明)")
        print("  └── 相关文档")
        print()
        print("🔄 下一步操作：")
        print("1. 将整个包传输到 macOS 系统")
        print("2. 在 macOS 上运行：./finalize_macos_app.sh")
        print("3. 完成最终的权限设置和图标转换")
        print()
        print("✨ 优势：")
        print("  ✅ 在 Windows 上完成了 90% 的工作")
        print("  ✅ 包含完整的 .app 目录结构")
        print("  ✅ 包含所有必要的元数据")
        print("  ✅ 自动化的最终化脚本")
        print("  ✅ 完整的安装说明")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建过程中出现错误：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
