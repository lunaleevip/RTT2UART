# -*- mode: python ; coding: utf-8 -*-
# XexunRTT macOS 构建配置

import sys
from pathlib import Path

# 从 version.py 读取版本信息
try:
    import sys
    sys.path.insert(0, str(Path.cwd()))
    from version import VERSION
except ImportError:
    VERSION = "3.0.0"  # 默认版本

# 数据文件配置
datas = [
    ('lang/xexunrtt_zh_CN.qm', 'lang'),
    ('lang/xexunrtt_zh_TW.qm', 'lang'),
    ('qt_zh_CN.qm', '.'),
    ('qt_zh_TW.qm', '.'),
    ('ui', 'ui'),  # UI文件目录
    ('JLinkCommandFile.jlink', '.'),
    ('JLinkDevicesBuildIn.xml', '.'),
    ('cmd.txt', '.'),
    ('config.ini', '.'),
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
    'resources_rc',  # 包含资源文件
    'requests',  # HTTP 请求库
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
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,  # 最高级别优化
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
    strip=True,  # 移除符号表减小体积
    upx=True,  # 使用 UPX 压缩
    console=False,  # macOS GUI 应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='XexunRTT.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,  # 移除符号表减小体积
    upx=True,
    upx_exclude=[],
    name='XexunRTT'
)

# 创建 macOS 应用程序包
app = BUNDLE(
    coll,
    name='XexunRTT.app',
    icon='XexunRTT.icns',
    bundle_identifier='com.xexun.rtt2uart',
    version=VERSION,
    info_plist={
        'CFBundleName': 'XexunRTT',
        'CFBundleDisplayName': 'XexunRTT - J-Link RTT Viewer',
        'CFBundleIdentifier': 'com.xexun.rtt2uart',
        'CFBundleVersion': VERSION,
        'CFBundleShortVersionString': VERSION,
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
            {
                'CFBundleTypeExtensions': ['log', 'txt'],
                'CFBundleTypeName': 'Log Files',
                'CFBundleTypeRole': 'Editor',
                'LSTypeIsPackage': False
            }
        ],
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
