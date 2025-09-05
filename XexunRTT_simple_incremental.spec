# -*- mode: python ; coding: utf-8 -*-

# 增量更新构建配置
# 策略：使用onedir模式，但通过自定义配置实现用户代码和库文件分离

import sys
from pathlib import Path

block_cipher = None

# 分析配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[
        # 数据文件
        ('xexunrtt.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
    ],
    hiddenimports=[
        # 必要的隐式导入
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pylink',
        'serial',
        'serial.tools.list_ports',
        'logging',
        'psutil',
        'configparser',
        'threading',
        'time',
        'datetime',
        'json',
        'xml.etree.ElementTree',
        'encodings.utf_8',
        'encodings.gbk',
        'encodings.cp936',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的模块
        'tkinter', 'unittest', 'test', 'email', 'http', 'urllib',
        'pydoc', 'doctest', 'pdb', 'profile', 'cProfile', 'pstats',
        'trace', 'timeit', 'webbrowser', 'pip', 'setuptools',
        'distutils', 'wheel', 'pytest', 'nose', 'mock',
        # 排除PySide6中不需要的大模块
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender',
        'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets', 'PySide6.QtMultimedia', 'PySide6.QtQml',
        'PySide6.QtQuick', 'PySide6.QtWebView', 'PySide6.QtXml',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,  # 使用标准archive，但后续我们会分离文件
)

# 标准PYZ配置
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# EXE配置 - 使用onedir模式
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 使用onedir模式
    name='XexunRTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='Jlink_ICON.ico',
)

# COLLECT配置
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='XexunRTT_Incremental'
)
