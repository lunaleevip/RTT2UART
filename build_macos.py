#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT macOS 打包构建脚本
创建适用于 macOS 的应用程序包
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
import json

def check_macos_environment():
    """检查 macOS 构建环境"""
    print("🍎 检查 macOS 构建环境...")
    
    # 检查操作系统
    if platform.system() != 'Darwin':
        print("❌ 错误：此脚本需要在 macOS 系统上运行")
        print("💡 如果您在其他系统上，请参考跨平台构建说明")
        return False
    
    print(f"✅ 操作系统：macOS {platform.mac_ver()[0]}")
    print(f"✅ 架构：{platform.machine()}")
    
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
        'resources_rc.py',
        'Jlink_ICON.ico'
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

def install_macos_dependencies():
    """安装 macOS 构建依赖"""
    print("📦 安装 macOS 构建依赖...")
    
    # 检查并安装 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller 已安装：{PyInstaller.__version__}")
    except ImportError:
        print("📥 安装 PyInstaller...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller>=6.0.0'], check=True)
    
    # 检查并安装其他依赖
    dependencies = [
        'pylink-square>=1.2.0',
        'pyserial>=3.5',
        'PySide6>=6.7.0',
        'qdarkstyle>=3.0.0'
    ]
    
    print("📥 检查项目依赖...")
    for dep in dependencies:
        try:
            subprocess.run([sys.executable, '-c', f"import {dep.split('>=')[0].replace('-', '_')}"], 
                         check=True, capture_output=True)
            print(f"✅ {dep.split('>=')[0]} 已安装")
        except (subprocess.CalledProcessError, ImportError):
            print(f"📥 安装 {dep}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
    
    return True

def clean_build_directories():
    """清理构建目录"""
    print("🧹 清理之前的构建...")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            print(f"🗑️ 删除目录：{dir_name}")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # 删除之前的 spec 文件
    spec_files = list(Path('.').glob('*.spec'))
    for spec_file in spec_files:
        if 'macos' in spec_file.name.lower():
            print(f"🗑️ 删除旧的 spec 文件：{spec_file}")
            spec_file.unlink()

def create_macos_icon():
    """创建 macOS 应用图标（.icns）"""
    print("🎨 创建 macOS 应用图标...")
    
    # 检查是否有原始图标
    ico_file = Path('Jlink_ICON.ico')
    icns_file = Path('XexunRTT.icns')
    
    if ico_file.exists() and not icns_file.exists():
        try:
            # 尝试使用 sips 命令转换图标（macOS 内置工具）
            subprocess.run([
                'sips', '-s', 'format', 'icns', 
                str(ico_file), '--out', str(icns_file)
            ], check=True, capture_output=True)
            print(f"✅ 成功转换图标：{icns_file}")
            return str(icns_file)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ 无法转换图标，将使用默认图标")
            # 创建一个简单的图标占位符
            return None
    elif icns_file.exists():
        print(f"✅ 使用现有图标：{icns_file}")
        return str(icns_file)
    else:
        print("⚠️ 未找到图标文件，将使用默认图标")
        return None

def create_macos_spec():
    """创建 macOS 专用的 PyInstaller spec 文件"""
    print("📝 创建 macOS 构建配置...")
    
    icon_path = create_macos_icon()
    icon_option = f"icon='{icon_path}'," if icon_path else ""
    
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
# XexunRTT macOS 构建配置

import sys
from pathlib import Path

# 数据文件配置
datas = [
    ('xexunrtt.qm', '.'),
    ('qt_zh_CN.qm', '.'),
    ('JLinkCommandFile.jlink', '.'),
    ('JLinkDevicesBuildIn.xml', '.'),
    ('cmd.txt', '.'),
    ('config.ini', '.'),
    ('picture', 'picture'),
    ('new_window.sh', '.'),  # 多开脚本
]

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
    'distutils',
    'lib2to3',
    'setuptools',
    'pip',
    # Qt模块优化
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtDataVisualization',
    'PySide6.QtVirtualKeyboard',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DExtras',
    'PySide6.QtCharts',
    'PySide6.QtSpatialAudio',
    'PySide6.QtTextToSpeech',
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtBluetooth',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtLocation',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSerialBus',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtStateMachine',
    'PySide6.QtUiTools',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtXml',
    'PySide6.QtXmlPatterns',
]

# macOS 特定的二进制文件
binaries = []

a = Analysis(
    ['main_window.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
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
    upx=True,  # 使用 UPX 压缩
    console=False,  # macOS GUI 应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_option}
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='XexunRTT'
)

# 创建 macOS 应用程序包
app = BUNDLE(
    coll,
    name='XexunRTT.app',
    {icon_option}
    bundle_identifier='com.xexun.rtt2uart',
    version='2.1.0',
    info_plist={{
        'CFBundleName': 'XexunRTT',
        'CFBundleDisplayName': 'XexunRTT - J-Link RTT Viewer',
        'CFBundleIdentifier': 'com.xexun.rtt2uart',
        'CFBundleVersion': '2.1.0',
        'CFBundleShortVersionString': '2.1.0',
        'CFBundleInfoDictionaryVersion': '6.0',
        'CFBundleExecutable': 'XexunRTT',
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': 'XRTT',
        'LSMinimumSystemVersion': '10.13.0',
        'LSApplicationCategoryType': 'public.app-category.developer-tools',
        'NSHighResolutionCapable': True,  # 启用高分辨率支持，确保清晰显示
        'NSRequiresAquaSystemAppearance': False,
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSUIElement': False,  # 确保应用在Dock中显示
        'NSSupportsAutomaticTermination': False,  # 支持多开
        'NSSupportsSuddenTermination': False,  # 支持多开
        'NSDocumentTypes': [
            {{
                'CFBundleTypeExtensions': ['log', 'txt'],
                'CFBundleTypeName': 'Log Files',
                'CFBundleTypeRole': 'Editor',
                'LSTypeIsPackage': False
            }}
        ],
        'NSHumanReadableCopyright': '© 2025 Xexun Technology',
        'CFBundleDocumentTypes': [
            {{
                'CFBundleTypeExtensions': ['log', 'txt'],
                'CFBundleTypeName': 'Log Files',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate'
            }}
        ]
    }},
)
"""
    
    spec_file = Path('XexunRTT_macOS.spec')
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ 创建 spec 文件：{spec_file}")
    return spec_file

def build_macos_app():
    """构建 macOS 应用程序"""
    print("🚀 开始构建 macOS 应用程序...")
    
    spec_file = create_macos_spec()
    
    # PyInstaller 构建命令
    # 注意：使用 .spec 文件时不能同时使用 --windowed 等选项
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',              # 清理缓存
        '--noconfirm',          # 不询问覆盖
        str(spec_file)
    ]
    
    print("🔨 执行构建命令...")
    print("命令:", ' '.join(cmd))
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("-" * 60)
        print("✅ macOS 应用构建成功!")
        
        # 检查生成的应用
        app_path = Path('dist/XexunRTT.app')
        if app_path.exists():
            print(f"📱 生成的应用程序：{app_path}")
            
            # 获取应用大小
            try:
                result = subprocess.run(['du', '-sh', str(app_path)], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    size = result.stdout.split()[0]
                    print(f"📏 应用大小：{size}")
            except:
                pass
            
            return app_path
        else:
            print("❌ 未找到生成的应用程序")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 构建失败：{e}")
        return None
    except Exception as e:
        print(f"❌ 构建过程中出现错误：{e}")
        return None

def create_dmg_installer(app_path):
    """创建 macOS DMG 安装包"""
    print("📦 创建 DMG 安装包...")
    
    if not app_path or not app_path.exists():
        print("❌ 应用程序不存在，无法创建 DMG")
        return None
    
    dmg_name = "XexunRTT_macOS_v2.1.0.dmg"
    dmg_path = Path('dist') / dmg_name
    
    # 删除已存在的 DMG
    if dmg_path.exists():
        dmg_path.unlink()
    
    try:
        # 创建临时 DMG 目录
        temp_dmg_dir = Path('dist/dmg_temp')
        if temp_dmg_dir.exists():
            shutil.rmtree(temp_dmg_dir)
        temp_dmg_dir.mkdir(parents=True)
        
        # 复制应用到临时目录
        shutil.copytree(app_path, temp_dmg_dir / 'XexunRTT.app')
        
        # 创建应用程序文件夹的符号链接
        subprocess.run(['ln', '-sf', '/Applications', str(temp_dmg_dir / 'Applications')], check=True)
        
        # 创建 DMG
        cmd = [
            'hdiutil', 'create',
            '-volname', 'XexunRTT',
            '-srcfolder', str(temp_dmg_dir),
            '-ov', '-format', 'UDZO',
            str(dmg_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # 清理临时目录
        shutil.rmtree(temp_dmg_dir)
        
        print(f"✅ DMG 安装包创建成功：{dmg_path}")
        
        # 获取 DMG 大小
        try:
            result = subprocess.run(['ls', '-lh', str(dmg_path)], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                size = result.stdout.split()[4]
                print(f"📏 DMG 大小：{size}")
        except:
            pass
        
        return dmg_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 创建 DMG 失败：{e}")
        return None
    except Exception as e:
        print(f"❌ 创建 DMG 时出现错误：{e}")
        return None

def create_macos_readme():
    """创建 macOS 特定的说明文档"""
    print("📖 创建 macOS 说明文档...")
    
    readme_content = """# XexunRTT for macOS

## 🍎 macOS 版本说明

这是 XexunRTT (J-Link RTT Viewer) 的 macOS 版本，专为 macOS 系统优化。

## 📋 系统要求

- **操作系统**：macOS 10.13 (High Sierra) 或更高版本
- **架构**：Intel x64 或 Apple Silicon (M1/M2)
- **内存**：建议 4GB 或以上
- **存储空间**：约 500MB 可用空间

## 🚀 安装方法

### 方法 1：使用 DMG 安装包
1. 下载 `XexunRTT_macOS_v1.0.5.dmg`
2. 双击打开 DMG 文件
3. 将 `XexunRTT.app` 拖拽到 `Applications` 文件夹
4. 从启动台或应用程序文件夹启动

### 方法 2：直接使用应用程序
1. 下载并解压应用程序包
2. 将 `XexunRTT.app` 移动到应用程序文件夹（可选）
3. 双击启动应用程序

## 🔒 安全性说明

### Gatekeeper 警告
首次运行时，macOS 可能显示安全警告：

```
"XexunRTT.app" cannot be opened because it is from an unidentified developer.
```

**解决方法：**
1. 在 Finder 中右键点击 `XexunRTT.app`
2. 选择"打开"
3. 在弹出的对话框中点击"打开"
4. 或者在"系统偏好设置" > "安全性与隐私" > "通用"中允许应用运行

### 权限说明
应用程序需要以下权限：
- **USB 设备访问**：连接 J-Link 调试器
- **网络访问**：串口转发功能（如需要）
- **文件系统访问**：保存日志文件

## 🔌 J-Link 驱动安装

### 自动检测
应用程序会自动检测 J-Link 驱动，如果未安装会提示下载。

### 手动安装
1. 访问 SEGGER 官网：https://www.segger.com/downloads/jlink/
2. 下载适合 macOS 的 J-Link Software Pack
3. 安装 dmg 包中的驱动程序
4. 重启应用程序

## 🎯 功能特性

- ✅ **RTT 查看器**：实时查看 RTT 输出
- ✅ **多终端支持**：支持多个 RTT 通道
- ✅ **串口转发**：RTT 数据转发到虚拟串口
- ✅ **日志保存**：自动保存 RTT 日志
- ✅ **命令发送**：向目标设备发送命令
- ✅ **ANSI 颜色**：支持彩色文本显示
- ✅ **查找功能**：Ctrl+F 查找文本
- ✅ **深色主题**：支持 macOS 深色模式

## 🛠️ 故障排除

### 无法连接 J-Link
1. 确认 J-Link 驱动已正确安装
2. 检查 USB 连接
3. 尝试重新插拔 J-Link 设备
4. 检查设备是否被其他应用占用

### 应用崩溃
1. 检查 macOS 版本是否支持
2. 重新安装应用程序
3. 查看控制台日志获取详细错误信息

### 权限问题
1. 在"系统偏好设置" > "安全性与隐私"中检查权限
2. 尝试使用管理员权限运行
3. 重新安装应用程序

## 📝 更新日志

### v1.0.5 (macOS 版本)
- ✅ 适配 macOS 系统
- ✅ 支持 Apple Silicon (M1/M2)
- ✅ 优化界面显示
- ✅ 修复 macOS 特定问题
- ✅ 添加 DMG 安装包

## 🔗 相关链接

- **项目主页**：https://github.com/xexun/RTT2UART
- **SEGGER J-Link**：https://www.segger.com/products/debug-probes/j-link/
- **技术支持**：support@xexun.com

## 📞 技术支持

如遇到问题，请联系：
- **邮箱**：support@xexun.com
- **问题反馈**：GitHub Issues
- **QQ群**：[待补充]

---

© 2025 Xexun Technology. All rights reserved.
"""
    
    readme_file = Path('dist/README_macOS.md')
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✅ 创建说明文档：{readme_file}")
    return readme_file

def main():
    """主函数"""
    print("🍎 XexunRTT macOS 构建工具")
    print("=" * 50)
    
    try:
        # 1. 检查环境
        if not check_macos_environment():
            return False
        
        # 2. 安装依赖
        if not install_macos_dependencies():
            return False
        
        # 3. 清理构建目录
        clean_build_directories()
        
        # 4. 构建应用程序
        app_path = build_macos_app()
        if not app_path:
            return False
        
        # 5. 创建 DMG 安装包
        dmg_path = create_dmg_installer(app_path)
        
        # 6. 创建说明文档
        readme_path = create_macos_readme()
        
        # 7. 显示总结
        print("\n" + "=" * 50)
        print("🎉 macOS 构建完成!")
        print("-" * 50)
        print(f"📱 应用程序：{app_path}")
        if dmg_path:
            print(f"📦 安装包：{dmg_path}")
        print(f"📖 说明文档：{readme_path}")
        
        print("\n🚀 使用方法：")
        print("1. 双击运行 XexunRTT.app")
        if dmg_path:
            print("2. 或使用 DMG 安装包进行分发")
        print("3. 首次运行时允许在安全设置中打开")
        
        print("\n⚠️ 注意事项：")
        print("- 需要安装 J-Link 驱动")
        print("- 首次运行需要在安全设置中允许")
        print("- 确保目标设备支持 RTT 功能")
        
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
