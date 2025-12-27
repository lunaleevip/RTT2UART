# -*- mode: python ; coding: utf-8 -*-

# XexunRTT 调试版本构建配置（带控制台窗口）

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path.cwd()))

# 从version.py读取版本信息
try:
    from version import VERSION, VERSION_NAME
    print(f"Building {VERSION_NAME} v{VERSION} (Debug)")
except ImportError:
    VERSION = "2.4"
    VERSION_NAME = "XexunRTT"
    print(f"Warning: Could not import version.py, using default version {VERSION}")

# 收集 pywin32 DLL 文件（仅Windows）
import sys
pywin32_binaries = []
if sys.platform == 'win32':
    try:
        import win32api
        import os
        # 获取 pywin32 DLL 路径
        win32api_path = os.path.dirname(win32api.__file__)
        pywin32_dll_path = os.path.join(os.path.dirname(win32api_path), 'pywin32_system32')
        
        # 添加必要的 DLL 文件 - 根据Python版本自动检测
        if os.path.exists(pywin32_dll_path):
            # 获取Python版本号（如 313 for Python 3.13）
            py_ver = f"{sys.version_info.major}{sys.version_info.minor}"
            dll_files = [f'pythoncom{py_ver}.dll', f'pywintypes{py_ver}.dll']
            
            for dll in dll_files:
                dll_path = os.path.join(pywin32_dll_path, dll)
                if os.path.exists(dll_path):
                    pywin32_binaries.append((dll_path, '.'))
                    print(f"Adding pywin32 DLL: {dll}")
                else:
                    print(f"Warning: pywin32 DLL not found: {dll_path}")
    except Exception as e:
        print(f"Warning: Could not locate pywin32 DLLs: {e}")

# 从正式版 spec 导入所有配置
# NOTE: keep debug build aligned with onefile win spec filename in repo
import importlib.util
spec_path = Path.cwd() / "XexunRTT_onefile_win.spec"
spec = importlib.util.spec_from_file_location("base_spec", spec_path)

# 直接使用相同的 Analysis 配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=pywin32_binaries,
    datas=[
        ('lang/xexunrtt_zh_CN.qm', 'lang'),
        ('lang/xexunrtt_zh_TW.qm', 'lang'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('ui/*.ui', 'ui'),
    ],
    hiddenimports=[
        # 核心模块
        'xml.etree.ElementTree',
        'PySide6.QtCore',
        'PySide6.QtGui', 
        'PySide6.QtWidgets',
        'pylink',
        'serial',
        'serial.tools.list_ports',
        'logging',
        'configparser',
        'json',
        're',
        'threading',
        'queue',
        'time',
        'datetime',
        'os',
        'sys',
        'pathlib',
        'platform',
        'subprocess',
        'shutil',
        'tempfile',
        'io',
        'collections',
        'functools',
        'dis',
        'inspect',
        'opcode',
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        'win32api',
        'win32con',
        'itertools',
        'typing',
        'base64',
        'binascii',
        'struct',
        
        # 自动更新依赖
        'bsdiff4',
        'requests',
        'urllib3',
        'charset_normalizer',
        'certifi',
        'idna',
        
        # email 模块及其子模块
        'email',
        'email.mime',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.parser',
        'email.message',
        'email.utils',
        'email.encoders',
        'email.header',
        'email.charset',
        'email.errors',
        'email.generator',
        'email.policy',
        'email.contentmanager',
        'email._parseaddr',
        'email._policybase',
        'email._encoded_words',
        'email._header_value_parser',
        
        # PySide6 子模块（简化版）
        'PySide6.QtCore.QTimer',
        'PySide6.QtCore.QThread',
        'PySide6.QtWidgets.QApplication',
        'PySide6.QtWidgets.QMainWindow',
        
        # 第三方模块
        'qdarkstyle',

        # Watch / Memory (lazy-imported) + pyelftools
        'watch_panel',
        'watch_dwarf',
        'map_parser',
        'elftools',
        'elftools.elf.elffile',
        'elftools.dwarf.die',
        'elftools.dwarf.dwarfinfo',
        'elftools.dwarf.descriptions',
        'elftools.construct',
        # stdlib (required by pyelftools in some code paths)
        'pdb',
        
        # 自定义模块
        'config_manager',
        'rtt2uart',
        'ansi_terminal_widget',
        'performance_monitor',
        'ui',
        'ui.ui_xexunrtt',
        'ui.ui_rtt2uart_updated',
        'ui.ui_sel_device',
        'ui_constants',
        'resources_rc',
        'auto_updater',
        'update_dialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'tensorflow',
        'torch',
        'sklearn',
        'jupyter',
        'notebook',
        'IPython',
        'sphinx',
        'pytest',
        'unittest',
        'doctest',
        'profile',
        'cProfile',
        'pstats',
        'trace',
        'py_compile',
        'compileall',
        'pickletools',
        'xmlrpc',
        'http.server',
        'wsgiref',
        'mailbox',
        'binhex',
        'quopri',
        'uu',
        'html',
        'xml.dom',
        'xml.sax',
        'xml.parsers.expat',
        'sqlite3',
        'dbm',
        'csv',
        'netrc',
        'xdrlib',
        'plistlib',
        'calendar',
        'mailcap',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 生成PYZ文件
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 生成单文件EXE - 🔧 调试版本启用控制台
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f'{VERSION_NAME}_v{VERSION}_debug',  # 添加 _debug 后缀
    debug=True,  # 启用调试模式
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用 UPX 压缩，便于调试
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 🔑 启用控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='xexunrtt.ico',
    version=f'version_info_v{VERSION}.txt'
)

