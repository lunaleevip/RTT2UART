#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT v2.2 单文件版本构建脚本
新增筛选TAB正则表达式功能
生成单个EXE文件，便于分发和使用
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import time

def create_onefile_spec():
    """创建单文件版本的spec文件"""
    spec_content = """# -*- mode: python ; coding: utf-8 -*-

# XexunRTT v2.2 单文件版本构建配置

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path.cwd()))

# 分析配置
a = Analysis(
    ['main_window.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
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
        'itertools',
        'typing',
        'dis',
        'inspect',
        'importlib',
        'importlib.util',
        'importlib.machinery',
        'pkgutil',
        'modulefinder',
        
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
        # 'dis',  # 注释掉dis模块，因为PyInstaller需要它
        'py_compile',
        'compileall',
        'pickletools',
        'xmlrpc',
        'http.server',
        'wsgiref',
        'email',
        'mailbox',
        'mimetypes',
        'base64',
        'binhex',
        'binascii',
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
    name='XexunRTT_v2.2',
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
    version='version_info_v2_2.txt'
)
"""
    
    # 写入spec文件
    with open('XexunRTT_onefile_v2_2.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("已创建 XexunRTT_onefile_v2_2.spec")

def create_version_info():
    """创建版本信息文件"""
    version_info = """# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 2, 0, 0),
    prodvers=(2, 2, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'XexunRTT Team'),
        StringStruct(u'FileDescription', u'XexunRTT - RTT调试工具 v2.2'),
        StringStruct(u'FileVersion', u'2.2.0.0'),
        StringStruct(u'InternalName', u'XexunRTT'),
        StringStruct(u'LegalCopyright', u'Copyright © 2024 XexunRTT Team'),
        StringStruct(u'OriginalFilename', u'XexunRTT_v2.2.exe'),
        StringStruct(u'ProductName', u'XexunRTT - RTT调试工具'),
        StringStruct(u'ProductVersion', u'2.2.0.0 - 新增筛选TAB正则表达式功能')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    
    with open('version_info_v2_2.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    
    print("已创建版本信息文件 version_info_v2_2.txt")

def clean_build_dirs():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"已清理目录: {dir_name}")
            except Exception as e:
                print(f"清理目录 {dir_name} 失败: {e}")

def build_executable():
    """构建可执行文件"""
    print("开始构建 XexunRTT v2.2 单文件版本...")
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        # 运行PyInstaller
        cmd = ['pyinstaller', '--clean', 'XexunRTT_onefile_v2_2.spec']
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            build_time = time.time() - start_time
            print(f"构建成功! 耗时: {build_time:.1f}秒")
            
            # 检查生成的文件
            exe_path = Path('dist/XexunRTT_v2.2.exe')
            if exe_path.exists():
                file_size = exe_path.stat().st_size / (1024 * 1024)  # MB
                print(f"生成文件: {exe_path}")
                print(f"文件大小: {file_size:.1f} MB")
                return True
            else:
                print("未找到生成的EXE文件")
                return False
        else:
            print("构建失败!")
            print("错误输出:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"构建过程出错: {e}")
        return False

def main():
    """主函数"""
    print("XexunRTT v2.2 单文件构建工具")
    print("=" * 50)
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("需要Python 3.8或更高版本")
        return False
    
    # 检查是否安装了PyInstaller
    try:
        import PyInstaller
        print(f"PyInstaller版本: {PyInstaller.__version__}")
    except ImportError:
        print("未安装PyInstaller，请运行: pip install pyinstaller")
        return False
    
    # 检查必要文件
    required_files = [
        'main_window.py',
        'config_manager.py', 
        'rtt2uart.py',
        'xexunrtt_complete.qm',
        'Jlink_ICON.ico'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"缺少必要文件: {', '.join(missing_files)}")
        return False
    
    print("所有必要文件检查通过")
    
    # 清理旧的构建文件
    clean_build_dirs()
    
    # 创建构建文件
    create_version_info()
    create_onefile_spec()
    
    # 构建可执行文件
    success = build_executable()
    
    if success:
        print("\nXexunRTT v2.2 构建完成!")
        print("输出文件: dist/XexunRTT_v2.2.exe")
        print("\n新功能:")
        print("  • 筛选TAB支持正则表达式")
        print("  • 单个TAB独立正则配置")
        print("  • 修复TAB切换重复数据问题")
        print("  • 增加MAX_TAB_SIZE到32个")
        print("  • 完善中文翻译支持")
    else:
        print("\n构建失败，请检查错误信息")
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
