#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT 跨平台构建脚本
支持在非 macOS 系统上为 macOS 构建应用程序
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import json

def check_cross_build_environment():
    """检查跨平台构建环境"""
    print("🌍 检查跨平台构建环境...")
    
    current_os = platform.system()
    print(f"✅ 当前系统：{current_os}")
    
    # 检查 Python 版本
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print(f"❌ Python 版本过低：{python_version.major}.{python_version.minor}")
        print("💡 需要 Python 3.8 或更高版本")
        return False
    
    print(f"✅ Python 版本：{python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 检查必要的文件
    required_files = [
        'main_window.py',
        'rtt2uart.py', 
        'ui_rtt2uart.py',
        'resources_rc.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("❌ 缺少必要文件：")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    print("✅ 核心文件检查完成")
    
    return True

def install_cross_dependencies():
    """安装跨平台构建依赖"""
    print("📦 安装跨平台构建依赖...")
    
    # 检查并安装 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller 已安装：{PyInstaller.__version__}")
    except ImportError:
        print("📥 安装 PyInstaller...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller>=6.0.0'], check=True)
    
    # 安装其他必要依赖
    dependencies = [
        'pylink-square>=1.2.0',
        'pyserial>=3.5',
        'PySide6>=6.7.0',
        'qdarkstyle>=3.0.0'
    ]
    
    print("📥 检查项目依赖...")
    for dep in dependencies:
        module_name = dep.split('>=')[0].replace('-', '_')
        try:
            __import__(module_name)
            print(f"✅ {dep.split('>=')[0]} 已安装")
        except ImportError:
            print(f"📥 安装 {dep}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
    
    return True

def create_cross_macos_spec():
    """创建跨平台 macOS 构建配置"""
    print("📝 创建跨平台 macOS 构建配置...")
    
    spec_content = """# -*- mode: python ; coding: utf-8 -*-
# XexunRTT 跨平台 macOS 构建配置

import sys
from pathlib import Path

# 数据文件配置
datas = []

# 检查并添加存在的数据文件
data_files = [
    ('xexunrtt.qm', '.'),
    ('qt_zh_CN.qm', '.'),
    ('JLinkCommandFile.jlink', '.'),
    ('JLinkDevicesBuildIn.xml', '.'),
    ('cmd.txt', '.'),
    ('config.ini', '.'),
]

for src, dst in data_files:
    if Path(src).exists():
        datas.append((src, dst))
    else:
        print(f"⚠️ 数据文件不存在，跳过：{src}")

# 检查图片目录
if Path('picture').exists():
    datas.append(('picture', 'picture'))

# 隐式导入
hiddenimports = [
    'xml.etree.ElementTree',
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtPrintSupport',
    'pylink',
    'serial',
    'serial.tools.list_ports',
    'logging',
    'logging.handlers',
    'configparser',
    'threading',
    'queue',
    'time',
    'datetime',
    'json',
    'os',
    'sys',
    'pathlib',
    'qdarkstyle',
]

# 排除的模块（减少包大小）
excludes = [
    'tkinter',
    'unittest',
    'test',
    'email',
    'http',
    'urllib',
    'pydoc',
    'sqlite3',
    'asyncio',
    'multiprocessing',
    'subprocess',
    'distutils',
    'lib2to3',
    'setuptools',
    'pip',
]

a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XexunRTT'
)

# 注意：BUNDLE 仅在 macOS 上可用
# 在其他平台上构建时，注释掉 BUNDLE 部分
import platform
if platform.system() == 'Darwin':
    app = BUNDLE(
        coll,
        name='XexunRTT.app',
        bundle_identifier='com.xexun.rtt2uart',
        version='2.1.3',
        info_plist={
            'CFBundleName': 'XexunRTT',
            'CFBundleDisplayName': 'XexunRTT - J-Link RTT Viewer',
            'CFBundleIdentifier': 'com.xexun.rtt2uart',
            'CFBundleVersion': '2.1.3',
            'CFBundleShortVersionString': '2.1.3',
            'CFBundleInfoDictionaryVersion': '6.0',
            'CFBundleExecutable': 'XexunRTT',
            'CFBundlePackageType': 'APPL',
            'CFBundleSignature': 'XRTT',
            'LSMinimumSystemVersion': '10.13.0',
            'LSApplicationCategoryType': 'public.app-category.developer-tools',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
            'NSHumanReadableCopyright': '© 2025 Xexun Technology',
            'CFBundleDocumentTypes': [
                {
                    'CFBundleTypeExtensions': ['log', 'txt'],
                    'CFBundleTypeName': 'Log Files',
                    'CFBundleTypeRole': 'Viewer',
                    'LSHandlerRank': 'Alternate'
                }
            ]
        },
    )
else:
    # 在非 macOS 系统上，只生成基本的目录结构
    pass
"""
    
    spec_file = Path('XexunRTT_cross_macOS.spec')
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ 创建跨平台 spec 文件：{spec_file}")
    return spec_file

def build_cross_macos():
    """跨平台构建 macOS 应用程序"""
    print("🚀 开始跨平台构建 macOS 应用程序...")
    print("⚠️ 注意：生成的应用程序需要在 macOS 系统上运行")
    
    spec_file = create_cross_macos_spec()
    
    # PyInstaller 构建命令
    # 注意：使用 .spec 文件时不能同时使用 --windowed 等选项
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',              # 清理缓存
        '--noconfirm',          # 不询问覆盖
        '--distpath=dist_macos', # 指定输出目录
        str(spec_file)
    ]
    
    print("🔨 执行构建命令...")
    print("命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ 跨平台构建成功!")
        
        # 检查生成的应用结构
        dist_path = Path('dist_macos')
        
        # 首先检查是否生成了 .app 结构（仅在 macOS 上）
        app_structure = dist_path / 'XexunRTT.app'
        if app_structure.exists():
            print(f"📱 生成的应用结构：{app_structure}")
            return app_structure
        
        # 检查是否生成了普通目录结构
        exe_path = dist_path / 'XexunRTT' / 'XexunRTT.exe'  # Windows 构建
        if exe_path.exists():
            print(f"📁 生成的可执行文件：{exe_path}")
            print("💡 需要在 macOS 系统上重新打包为 .app 格式")
            return exe_path
        
        # 检查 Unix 可执行文件
        exe_path_unix = dist_path / 'XexunRTT' / 'XexunRTT'  # Unix 构建
        if exe_path_unix.exists():
            print(f"📁 生成的可执行文件：{exe_path_unix}")
            print("💡 需要在 macOS 系统上重新打包为 .app 格式")
            return exe_path_unix
        
        # 检查是否有目录结构
        app_dir = dist_path / 'XexunRTT'
        if app_dir.exists():
            print(f"📁 生成的应用目录：{app_dir}")
            print("💡 需要在 macOS 系统上重新打包为 .app 格式")
            return app_dir
        
        print("❌ 未找到生成的文件")
        return None
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败：{e}")
        return None
    except Exception as e:
        print(f"❌ 构建过程中出现错误：{e}")
        return None

def create_macos_package_script():
    """创建 macOS 打包脚本"""
    print("📜 创建 macOS 打包脚本...")
    
    script_content = """#!/bin/bash
# macOS 应用程序打包脚本
# 在 macOS 系统上运行此脚本来完成最终打包

echo "🍎 macOS 应用程序打包脚本"
echo "================================"

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
</dict>
</plist>
EOF

# 设置可执行权限
echo "🔧 设置可执行权限..."
chmod +x "$APP_DIR/Contents/MacOS/XexunRTT"

# 复制图标（如果存在）
if [ -f "Jlink_ICON.ico" ]; then
    echo "🎨 转换并复制图标..."
    sips -s format icns Jlink_ICON.ico --out "$APP_DIR/Contents/Resources/XexunRTT.icns" 2>/dev/null || echo "⚠️ 图标转换失败，使用默认图标"
fi

echo "✅ 应用程序包创建完成：$APP_DIR"

# 创建 DMG（可选）
read -p "是否创建 DMG 安装包? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 创建 DMG 安装包..."
    
    DMG_NAME="XexunRTT_macOS_v2.1.3.dmg"
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
"""
    
    script_file = Path('package_macos.sh')
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # 设置可执行权限（如果在 Unix 系统上）
    if platform.system() in ['Linux', 'Darwin']:
        os.chmod(script_file, 0o755)
    
    print(f"✅ 创建 macOS 打包脚本：{script_file}")
    return script_file

def create_cross_build_guide():
    """创建跨平台构建指南"""
    print("📚 创建跨平台构建指南...")
    
    guide_content = """# XexunRTT macOS 跨平台构建指南

## 🌍 概述

此指南帮助您在 Windows 或 Linux 系统上为 macOS 构建 XexunRTT 应用程序。

## 🏗️ 构建流程

### 第一步：跨平台构建（在任何系统上）

1. **准备环境**
   ```bash
   python -m pip install pyinstaller>=6.0.0
   python -m pip install -r requirements.txt
   ```

2. **执行跨平台构建**
   ```bash
   python build_cross_platform.py
   ```

3. **检查输出**
   - 构建完成后会在 `dist_macos/` 目录生成文件
   - 文件结构可能不是完整的 .app 格式

### 第二步：最终打包（需要在 macOS 上）

1. **传输文件到 macOS**
   - 将整个 `dist_macos/` 目录复制到 macOS 系统
   - 同时复制 `package_macos.sh` 脚本

2. **在 macOS 上完成打包**
   ```bash
   chmod +x package_macos.sh
   ./package_macos.sh
   ```

3. **获得最终应用**
   - 生成 `XexunRTT.app` 应用程序包
   - 可选择创建 DMG 安装包

## 🔧 替代方案

### 方案一：使用 GitHub Actions

创建 `.github/workflows/build-macos.yml`：

```yaml
name: Build macOS App

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: macos-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller>=6.0.0
    
    - name: Build macOS app
      run: python build_macos.py
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: XexunRTT-macOS
        path: dist/
```

### 方案二：使用 Docker（实验性）

```dockerfile
# Dockerfile.macos
FROM sickcodes/docker-osx:auto

# 安装构建依赖
RUN brew install python@3.11

# 复制源代码
COPY . /app
WORKDIR /app

# 构建应用
RUN python build_macos.py
```

### 方案三：云构建服务

- **CircleCI**：支持 macOS 构建环境
- **Travis CI**：提供 macOS 虚拟机
- **Azure DevOps**：有 macOS 代理

## 📋 注意事项

### 跨平台限制
- PyInstaller 的 BUNDLE 功能仅在 macOS 上可用
- 某些 macOS 特定的库可能在其他平台上不可用
- 生成的应用程序包需要在 macOS 上进行最终整理

### 依赖问题
- J-Link 驱动在不同平台上的表现可能不同
- PySide6 的某些模块可能有平台特定的要求
- 确保所有依赖项支持 macOS

### 测试建议
- 在构建完成后，务必在真实的 macOS 设备上测试
- 测试不同版本的 macOS（10.13+）
- 验证 J-Link 连接和 RTT 功能

## 🛠️ 故障排除

### 构建失败
1. 检查 Python 版本是否兼容
2. 确保所有依赖项已正确安装
3. 查看 PyInstaller 详细错误信息

### 应用无法运行
1. 检查 Info.plist 配置
2. 验证可执行文件权限
3. 确保所有依赖库已包含

### 权限问题
1. 在 macOS 上设置正确的可执行权限
2. 处理 Gatekeeper 安全警告
3. 考虑代码签名（付费开发者账户）

## 📞 获取帮助

如果遇到问题，请：
1. 查看构建日志中的详细错误信息
2. 在 GitHub Issues 中搜索类似问题
3. 提供完整的错误日志和系统信息

---

© 2025 Xexun Technology
"""
    
    guide_file = Path('macOS_Build_Guide.md')
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print(f"✅ 创建构建指南：{guide_file}")
    return guide_file

def main():
    """主函数"""
    print("🌍 XexunRTT 跨平台 macOS 构建工具")
    print("=" * 50)
    
    current_os = platform.system()
    print(f"当前系统：{current_os}")
    
    if current_os == 'Darwin':
        print("💡 检测到 macOS 系统，建议使用 build_macos.py 进行原生构建")
        choice = input("是否继续跨平台构建？(y/n): ").lower()
        if choice != 'y':
            print("🔄 请运行：python build_macos.py")
            return True
    
    try:
        # 1. 检查环境
        if not check_cross_build_environment():
            return False
        
        # 2. 安装依赖
        if not install_cross_dependencies():
            return False
        
        # 3. 清理构建目录
        dist_path = Path('dist_macos')
        if dist_path.exists():
            print(f"🧹 清理目录：{dist_path}")
            shutil.rmtree(dist_path, ignore_errors=True)
        
        # 4. 跨平台构建
        build_output = build_cross_macos()
        if not build_output:
            return False
        
        # 5. 创建打包脚本
        script_path = create_macos_package_script()
        
        # 6. 创建构建指南
        guide_path = create_cross_build_guide()
        
        # 7. 显示总结
        print("\n" + "=" * 50)
        print("🎉 跨平台构建完成!")
        print("-" * 50)
        print(f"📁 构建输出：{build_output}")
        print(f"📜 打包脚本：{script_path}")
        print(f"📚 构建指南：{guide_path}")
        
        print("\n🔄 下一步操作：")
        print("1. 将 dist_macos/ 目录传输到 macOS 系统")
        print("2. 将 package_macos.sh 脚本传输到 macOS 系统")
        print("3. 在 macOS 上运行：./package_macos.sh")
        print("4. 获得最终的 XexunRTT.app 应用程序")
        
        print("\n⚠️ 重要提醒：")
        print("- 生成的文件需要在 macOS 上进行最终打包")
        print("- 确保目标 macOS 系统已安装 J-Link 驱动")
        print("- 首次运行需要在安全设置中允许应用程序")
        
        return True
        
    except KeyboardInterrupt:
        print("\n❌ 构建被用户取消")
        return False
    except Exception as e:
        print(f"❌ 构建过程中出现错误：{e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
