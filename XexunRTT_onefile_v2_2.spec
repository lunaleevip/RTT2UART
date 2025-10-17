# -*- mode: python ; coding: utf-8 -*-

# XexunRTT 单文件版本构建配置（版本号自动从version.py读取）

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path.cwd()))

# 从version.py读取版本信息
try:
    from version import VERSION, VERSION_NAME
    print(f"Building {VERSION_NAME} v{VERSION}")
except ImportError:
    VERSION = "2.3"
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

# 分析配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=pywin32_binaries,
    datas=[
        ('xexunrtt_complete.qm', '.'),
        ('qt_zh_CN.qm', '.'),
        ('JLinkCommandFile.jlink', '.'),
        ('JLinkDevicesBuildIn.xml', '.'),
        ('cmd.txt', '.'),
        ('picture', 'picture'),
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
        'dis',  # Python 反汇编模块，inspect依赖
        'inspect',  # 代码检查模块
        'opcode',  # dis模块依赖
        # Windows COM 自动化（用于复用资源管理器窗口）
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        'win32api',
        'win32con',
        'itertools',
        'typing',
        'base64',  # PySide6/shiboken6依赖
        'binascii',  # base64依赖
        'struct',  # 二进制数据处理
        
        # PySide6 子模块
        'PySide6.QtCore.QTimer',
        'PySide6.QtCore.QThread',
        'PySide6.QtCore.QObject',
        'PySide6.QtCore.Signal',
        'PySide6.QtCore.Slot',
        'PySide6.QtCore.QCoreApplication',
        'PySide6.QtCore.QTranslator',
        'PySide6.QtCore.QLocale',
        'PySide6.QtCore.QSettings',
        'PySide6.QtCore.QStandardPaths',
        'PySide6.QtCore.QDir',
        'PySide6.QtCore.QFile',
        'PySide6.QtCore.QIODevice',
        'PySide6.QtCore.QTextStream',
        'PySide6.QtCore.QUrl',
        'PySide6.QtCore.QMimeData',
        'PySide6.QtCore.QByteArray',
        'PySide6.QtCore.QRegularExpression',
        
        # GUI 模块
        'PySide6.QtGui.QFont',
        'PySide6.QtGui.QFontMetrics',
        'PySide6.QtGui.QPixmap',
        'PySide6.QtGui.QIcon',
        'PySide6.QtGui.QPalette',
        'PySide6.QtGui.QColor',
        'PySide6.QtGui.QPainter',
        'PySide6.QtGui.QBrush',
        'PySide6.QtGui.QPen',
        'PySide6.QtGui.QTextCursor',
        'PySide6.QtGui.QTextDocument',
        'PySide6.QtGui.QTextCharFormat',
        'PySide6.QtGui.QSyntaxHighlighter',
        'PySide6.QtGui.QKeySequence',
        'PySide6.QtGui.QAction',
        'PySide6.QtGui.QShortcut',
        'PySide6.QtGui.QClipboard',
        'PySide6.QtGui.QDesktopServices',
        'PySide6.QtGui.QScreen',
        'PySide6.QtGui.QGuiApplication',
        
        # Widgets 模块
        'PySide6.QtWidgets.QApplication',
        'PySide6.QtWidgets.QMainWindow',
        'PySide6.QtWidgets.QWidget',
        'PySide6.QtWidgets.QDialog',
        'PySide6.QtWidgets.QVBoxLayout',
        'PySide6.QtWidgets.QHBoxLayout',
        'PySide6.QtWidgets.QGridLayout',
        'PySide6.QtWidgets.QFormLayout',
        'PySide6.QtWidgets.QStackedLayout',
        'PySide6.QtWidgets.QLabel',
        'PySide6.QtWidgets.QPushButton',
        'PySide6.QtWidgets.QLineEdit',
        'PySide6.QtWidgets.QTextEdit',
        'PySide6.QtWidgets.QPlainTextEdit',
        'PySide6.QtWidgets.QComboBox',
        'PySide6.QtWidgets.QCheckBox',
        'PySide6.QtWidgets.QRadioButton',
        'PySide6.QtWidgets.QSpinBox',
        'PySide6.QtWidgets.QDoubleSpinBox',
        'PySide6.QtWidgets.QSlider',
        'PySide6.QtWidgets.QProgressBar',
        'PySide6.QtWidgets.QTabWidget',
        'PySide6.QtWidgets.QTabBar',
        'PySide6.QtWidgets.QListWidget',
        'PySide6.QtWidgets.QTreeWidget',
        'PySide6.QtWidgets.QTableWidget',
        'PySide6.QtWidgets.QScrollArea',
        'PySide6.QtWidgets.QScrollBar',
        'PySide6.QtWidgets.QSplitter',
        'PySide6.QtWidgets.QGroupBox',
        'PySide6.QtWidgets.QFrame',
        'PySide6.QtWidgets.QMenuBar',
        'PySide6.QtWidgets.QMenu',
        'PySide6.QtWidgets.QToolBar',
        'PySide6.QtWidgets.QStatusBar',
        'PySide6.QtWidgets.QMessageBox',
        'PySide6.QtWidgets.QInputDialog',
        'PySide6.QtWidgets.QFileDialog',
        'PySide6.QtWidgets.QColorDialog',
        'PySide6.QtWidgets.QFontDialog',
        'PySide6.QtWidgets.QProgressDialog',
        'PySide6.QtWidgets.QSizePolicy',
        'PySide6.QtWidgets.QSpacerItem',
        'PySide6.QtWidgets.QSystemTrayIcon',
        'PySide6.QtWidgets.QGraphicsView',
        'PySide6.QtWidgets.QGraphicsScene',
        'PySide6.QtWidgets.QGraphicsItem',
        
        # 第三方模块
        'qdarkstyle',
        'qdarkstyle.dark',
        'qdarkstyle.light',
        'qdarkstyle.palette',
        
        # 自定义模块
        'config_manager',
        'rtt2uart',
        'ansi_terminal_widget',
        'performance_monitor',
        'ui_xexunrtt',
        'resources_rc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 不要排除dis和inspect相关模块
        # 'dis', 'inspect',  # 注释掉，确保这些模块被包含
        # 排除不需要的模块以减小文件大小
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
        'pdb',
        'profile',
        'cProfile',
        'pstats',
        'trace',
        # 'dis',  # ❌ 不要排除dis模块，inspect依赖它
        'py_compile',
        'compileall',
        'pickletools',
        'xmlrpc',
        'http.server',
        'wsgiref',
        'email',
        'mailbox',
        'mimetypes',
        # 'base64',  # ❌ 不要排除，PySide6/shiboken6依赖它
        'binhex',
        # 'binascii',  # ❌ 不要排除，base64依赖它
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
        'mimetypes',
        'chunk',
        'colorsys',
        'imghdr',
        'sndhdr',
        'sunau',
        'wave',
        'audioop',
        'aifc',
        'chunk',
        'sunau',
        'wave',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# 生成PYZ文件
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 生成单文件EXE
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=f'{VERSION_NAME}_v{VERSION}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Jlink_ICON.ico',
    version=f'version_info_v{VERSION}.txt'
)
