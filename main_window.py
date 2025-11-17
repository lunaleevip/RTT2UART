#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XexunRTT Main Window Module
RTT2UART主窗口模块
"""

# 标准库导入
import sys
import os
import io
import re
import time
import pickle
import logging
import subprocess
import threading
import shutil
import ctypes.util as ctypes_util
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

# ==================== 配置日志（必须在所有其他导入之前） ====================
# 创建日志目录
log_dir = Path.home() / "AppData" / "Local" / "XexunRTT" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "xexunrtt.log"

# 配置日志处理器
log_handlers = [
    logging.FileHandler(log_file, encoding='utf-8', mode='w'),
]

# 如果是开发环境，也输出到控制台
if not getattr(sys, 'frozen', False):
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.WARN,  # INFO 级别以查看更新日志
    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s',
    handlers=log_handlers,
    force=True  # 强制重新配置
)

logger = logging.getLogger(__name__)

# ==================== 配置全局异常处理器 ====================
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """全局异常处理器 - 将所有未捕获的异常记录到日志"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 允许Ctrl+C正常工作
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))

# 设置全局异常处理器
sys.excepthook = global_exception_handler

logger.info("=" * 70)
logger.info("XexunRTT Starting...")
logger.info(f"Log file: {log_file}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
logger.info("=" * 70)
# ==================== 日志配置完成 ====================

# 第三方库导入（在类定义之前）
import serial
import serial.tools.list_ports
import pylink
import psutil
import qdarkstyle

# PySide6导入
from PySide6.QtCore import (
    Qt, QObject, QTimer, QThread, Signal, QCoreApplication,
    QTranslator, QLocale, QRegularExpression, QSettings, QSize, QPoint,
    QRect, Slot, QSortFilterProxyModel, QAbstractItemModel, QModelIndex
)
from PySide6 import QtCore
from PySide6.QtGui import (
    QFont, QIcon, QAction, QTextCharFormat, QColor, QTextCursor,
    QSyntaxHighlighter, QPalette, QKeySequence, QActionGroup, QTextOption
)
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QTextEdit, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QMessageBox, QFileDialog, QTabWidget,
    QSplitter, QFrame, QMenu, QHeaderView, QAbstractItemView,
    QSizePolicy, QButtonGroup, QListWidget, QListWidgetItem, QTabBar,
    QPlainTextEdit, QMdiArea, QMdiSubWindow, QTableWidget, QTableWidgetItem,
    QDialogButtonBox
)
from PySide6.QtNetwork import QLocalSocket, QLocalServer

# ========== 设备会话管理 ==========
class DeviceSession:
    """设备会话 - 管理单个设备的连接和数据"""
    
    def __init__(self, device_info, session_id=None):
        """
        初始化设备会话
        
        Args:
            device_info: 设备信息字典 {'serial': '...', 'product_name': '...', 'connection': 'USB', 'index': 0}
            session_id: 会话ID（可选）
        """
        if session_id is None:
            import uuid
            self.session_id = str(uuid.uuid4())[:8]
        else:
            self.session_id = session_id
        
        self.device_info = device_info
        self.device_serial = device_info.get('serial', 'Unknown')
        self.device_name = device_info.get('product_name', b'Unknown').decode() if isinstance(device_info.get('product_name'), bytes) else device_info.get('product_name', 'Unknown')
        self.device_index = device_info.get('index', None)  # 设备索引（用于显示）
        
        # 连接相关
        self.connection_dialog = None  # 连接对话框实例
        self.rtt2uart = None  # RTT连接实例
        self.is_connected = False
        
        # MDI子窗口
        self.mdi_window = None
        
        # 日志缓冲区（使用字典格式，与主窗口保持一致）
        self.log_buffers = {}
        self.log_buffer_locks = {}  # 每个文件路径对应一个锁
        
        # 筛选器设置（17-31通道）
        self.filters = {}
        
        logger.info(f"DeviceSession created: {self.session_id} for device {self.device_serial}")
    
    def get_display_name(self):
        """获取显示名称"""
        # 显示连接类型_索引号 序列号（例如：USB_1 69668156）
        connection_type = self.device_info.get('connection', 'USB')
        # 如果有索引，显示索引号；否则不显示索引号
        if self.device_index is not None:
            return f"{connection_type}_{self.device_index} {self.device_serial}"
        else:
            # 没有索引时，只显示连接类型和序列号
            return f"{connection_type} {self.device_serial}"
    
    def connect(self):
        """连接设备"""
        # 连接逻辑将在后续实现
        pass
    
    def disconnect(self):
        """断开设备连接"""
        if self.rtt2uart:
            try:
                # 异步停止RTT,不阻塞UI
                from PySide6.QtCore import QTimer
                rtt_obj = self.rtt2uart
                QTimer.singleShot(0, lambda: rtt_obj.stop())
            except Exception as e:
                logger.error(f"Failed to stop RTT: {e}")
        self.is_connected = False
    
    def cleanup(self):
        """清理资源"""
        self.disconnect()
        
        # 关闭MDI窗口
        if self.mdi_window:
            try:
                self.mdi_window.close()
                self.mdi_window = None
            except Exception as e:
                logger.error(f"Failed to close MDI window: {e}")
        
        logger.info(f"DeviceSession cleaned up: {self.session_id}")


class DeviceSessionManager:
    """设备会话管理器 - 管理所有设备会话"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.sessions = []  # 所有设备会话列表
        self.active_session = None  # 当前激活的会话
        self.session_lock = threading.Lock()
        logger.info("DeviceSessionManager initialized")
    
    def add_session(self, session):
        """添加设备会话"""
        with self.session_lock:
            if session not in self.sessions:
                self.sessions.append(session)
                logger.info(f"✅ Session added: {session.session_id}")
    
    def remove_session(self, session):
        """移除设备会话"""
        with self.session_lock:
            if session in self.sessions:
                session.cleanup()
                self.sessions.remove(session)
                if session == self.active_session:
                    # 如果移除的是当前激活会话，切换到第一个会话
                    self.active_session = self.sessions[0] if self.sessions else None
                logger.info(f"✅ Session removed: {session.session_id}")
    
    def set_active_session(self, session):
        """设置当前激活的会话"""
        with self.session_lock:
            self.active_session = session
            logger.info(f"Active session: {session.session_id if session else 'None'}")
    
    def get_active_session(self):
        """获取当前激活的会话"""
        with self.session_lock:
            return self.active_session
    
    def get_all_sessions(self):
        """获取所有会话"""
        with self.session_lock:
            return self.sessions.copy()
    
    def get_session_count(self):
        """获取会话数量"""
        with self.session_lock:
            return len(self.sessions)
    
    def cleanup_all(self):
        """清理所有会话"""
        with self.session_lock:
            for session in self.sessions[:]:
                session.cleanup()
            self.sessions.clear()
            self.active_session = None
            logger.info("All sessions cleaned up")

# 全局设备会话管理器
session_manager = DeviceSessionManager()

# 项目模块导入
from ui import Ui_RTTMainWindow, Ui_ConnectionDialog, Ui_Dialog
from rtt2uart import ansi_processor, rtt_to_serial
from config_manager import config_manager
from ui_constants import (
    WindowSize, LayoutSize, TimerInterval, BufferConfig,
    SerialConfig, RTTAddress, CleanupConfig, ColorConfig
)
#from performance_test import show_performance_test
import resources_rc

# 自动更新模块 - 必须在 try-except 外先导入以确保 PyInstaller 能识别
import update_dialog  # 先导入模块本身
import auto_updater   # 确保 auto_updater 也被导入

try:
    from update_dialog import check_for_updates_on_startup
    UPDATE_AVAILABLE = True
    logger.info("Auto update module loaded successfully")
except ImportError as e:
    UPDATE_AVAILABLE = False
    logger.error(f"❌ Failed to load auto update module: {e}")
    import traceback
    logger.error(f"Traceback:\n{traceback.format_exc()}")


# 修复Python控制台编码问题 - 确保UTF-8输出正常显示
def fix_console_encoding():
    """修复控制台编码，防止中文乱码"""
    try:
        # 设置环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        # 重新配置标准输出流
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        else:
            # 对于较老版本的Python
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, 
                encoding='utf-8', 
                errors='replace'
            )
        
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, 
                encoding='utf-8', 
                errors='replace'
            )
    except Exception as e:
        # 如果编码设置失败，至少记录错误
        logger.debug(f"Warning: Failed to set console encoding: {e}")

# 立即修复编码问题
fix_console_encoding()


# DPI检测和调整功能
def get_system_dpi():
    """获取系统DPI缩放比例"""
    try:
        if sys.platform == "darwin":  # macOS
            # 使用Qt获取屏幕DPI
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            screen = app.primaryScreen()
            if screen:
                # 获取物理DPI和逻辑DPI
                physical_dpi = screen.physicalDotsPerInch()
                logical_dpi = screen.logicalDotsPerInch()
                device_pixel_ratio = screen.devicePixelRatio()
                
                # 计算缩放比例
                scale_factor = device_pixel_ratio
                
                logger.info(f"macOS DPI Info:")
                logger.info(f"   Physical DPI: {physical_dpi:.1f}")
                logger.info(f"   Logical DPI: {logical_dpi:.1f}")
                logger.info(f"   Device Pixel Ratio: {device_pixel_ratio:.1f}")
                logger.info(f"   Scale Factor: {scale_factor:.1f}")
                
                return scale_factor
        else:
            # Windows/Linux
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            screen = app.primaryScreen()
            if screen:
                physical_dpi = screen.physicalDotsPerInch()
                logical_dpi = screen.logicalDotsPerInch()
                scale_factor = logical_dpi / 96.0  # 96是标准DPI
                
                logger.info(f"System DPI Info:")
                logger.info(f"   Physical DPI: {physical_dpi:.1f}")
                logger.info(f"   Logical DPI: {logical_dpi:.1f}")
                logger.info(f"   Scale Factor: {scale_factor:.1f}")
                
                return scale_factor
    except Exception as e:
        logger.warning(f"Failed to get DPI: {e}")
        return 1.0
    
    return 1.0

def get_dpi_scale_factor(manual_dpi=None):
    """获取DPI缩放因子，支持手动设置或自动检测"""
    if manual_dpi is not None and manual_dpi != "auto":
        try:
            dpi_value = float(manual_dpi)
            if 0.1 <= dpi_value <= 5.0:  # 限制范围在0.1到5.0之间
                logger.info(f"Using manual DPI setting: {dpi_value:.2f}")
                return dpi_value
            else:
                logger.warning(f"DPI value out of range (0.1-5.0): {dpi_value}, using auto detection")
        except ValueError:
            logger.warning(f"Invalid DPI value: {manual_dpi}, using auto detection")
    
    # 自动检测系统DPI
    return get_system_dpi()

def get_adaptive_font_size(base_size, dpi_scale):
    """根据DPI缩放调整字体大小"""
    if dpi_scale <= 0.5:
        # DPI很小，需要放大字体
        return int(base_size * 1.5)
    elif dpi_scale <= 0.8:
        # DPI较小，稍微放大字体
        return int(base_size * 1.2)
    elif dpi_scale <= 1.0:
        # 标准DPI，使用原始字体大小
        return base_size
    elif dpi_scale <= 1.5:
        # DPI较大，稍微缩小字体
        return int(base_size * 0.9)
    elif dpi_scale <= 2.0:
        # DPI很大，进一步缩小字体
        return int(base_size * 0.8)
    else:
        # DPI非常大，大幅缩小字体
        return int(base_size * 0.7)

def get_adaptive_window_size(base_width, base_height, dpi_scale):
    """根据DPI缩放调整窗口大小"""
    if dpi_scale <= 0.5:
        # DPI很小，需要放大窗口
        return int(base_width * 1.5), int(base_height * 1.5)
    elif dpi_scale <= 0.8:
        # DPI较小，稍微放大窗口
        return int(base_width * 1.2), int(base_height * 1.2)
    elif dpi_scale <= 1.0:
        # 标准DPI，使用原始大小
        return base_width, base_height
    elif dpi_scale <= 1.5:
        # DPI较大，稍微缩小窗口
        return int(base_width * 0.9), int(base_height * 0.9)
    elif dpi_scale <= 2.0:
        # DPI很大，进一步缩小窗口
        return int(base_width * 0.8), int(base_height * 0.8)
    else:
        # DPI非常大，大幅缩小窗口
        return int(base_width * 0.7), int(base_height * 0.7)


class JLinkLogHandler(logging.Handler):
    """自定义JLink日志处理器，将日志输出到GUI - 统一使用回调函数"""
    
    def __init__(self, log_callback):
        super().__init__()
        self.log_callback = log_callback
        self.setLevel(logging.DEBUG)
        
        # 设置日志格式
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        self.setFormatter(formatter)
    
    def emit(self, record):
        """发送日志记录到GUI"""
        try:
            msg = self.format(record)
            # 使用QTimer确保在主线程中更新GUI
            QTimer.singleShot(0, lambda: self._append_to_gui(msg))
        except Exception:
            pass
    
    def _append_to_gui(self, message):
        """在GUI中添加消息 - 通过回调函数统一处理"""
        try:
            if self.log_callback:
                self.log_callback(message)
        except Exception:
            pass

# 日志已在文件开头配置

# pylink支持的最大速率是12000kHz（Release v0.7.0开始支持15000及以上速率）
speed_list = SerialConfig.SPEED_LIST

baudrate_list = SerialConfig.BAUDRATE_LIST

MAX_TAB_SIZE = 32

def get_speed_index_from_value(speed_value):
    """根据速度值获取索引"""
    try:
        return speed_list.index(speed_value)
    except ValueError:
        # 如果找不到精确匹配，返回最接近的索引
        closest_index = 0
        min_diff = abs(speed_list[0] - speed_value)
        for i, speed in enumerate(speed_list):
            diff = abs(speed - speed_value)
            if diff < min_diff:
                min_diff = diff
                closest_index = i
        return closest_index

def get_baudrate_index_from_value(baudrate_value):
    """根据波特率值获取索引"""
    try:
        return baudrate_list.index(baudrate_value)
    except ValueError:
        # 如果找不到精确匹配，返回最接近的索引
        closest_index = 0
        min_diff = abs(baudrate_list[0] - baudrate_value)
        for i, baudrate in enumerate(baudrate_list):
            diff = abs(baudrate - baudrate_value)
            if diff < min_diff:
                min_diff = diff
                closest_index = i
        return closest_index
MAX_UI_TEXT_LENGTH = 1024 * 1024  # 1MB UI文本限制
MAX_TEXT_LENGTH = (int)(8e6) #缓存 8MB 的数据

class DeviceTableModel(QtCore.QAbstractTableModel):
    def __init__(self, device_list, header):
        super(DeviceTableModel, self).__init__()

        self.device_list = device_list
        self.header = header

    def rowCount(self, parent):
        return len(self.device_list)

    def columnCount(self, parent):
        return len(self.header)

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != QtCore.Qt.DisplayRole:
            return None

        return self.device_list[index.row()][index.column()]

        return None
    def headerData(self, col, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.header[col]
        return None


class DeviceSelectDialog(QDialog):
    def __init__(self, parent=None):
        super(DeviceSelectDialog, self).__init__(parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/xexunrtt.ico"))
        self.setWindowModality(Qt.ApplicationModal)
        
        # 应用父窗口的主题样式
        if parent and hasattr(parent, 'styleSheet'):
            current_stylesheet = parent.styleSheet()
            if current_stylesheet:
                self.setStyleSheet(current_stylesheet)
        
        # 设置窗口标志以避免在任务栏Aero Peek中显示
        current_flags = self.windowFlags()
        new_flags = current_flags | Qt.Tool
        # 确保保留关闭按钮和系统菜单
        new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(new_flags)
        
        # 设置对话框标题和标签文本（支持国际化）
        self.setWindowTitle(QCoreApplication.translate("main_window", "Target Device Settings"))
        self.ui.label.setText(QCoreApplication.translate("main_window", "Selected Device:"))
        self.ui.lineEdit_filter.setPlaceholderText(QCoreApplication.translate("main_window", "Filter"))
        
		#创建筛选模型
        self.proxy_model = QSortFilterProxyModel()
		#连接文本框设置筛选条件
        self.ui.lineEdit_filter.textChanged.connect(self.set_filter)
        
        self._target = None

        filepath = self.get_jlink_devices_list_file()
        if filepath != '':
            self.devices_list = self.parse_jlink_devices_list_file(filepath)

        if len(self.devices_list):
            # 从 header_data 中取出数据，放入到模型中
            header_data = [
                QCoreApplication.translate("main_window", "Manufacturer"),
                QCoreApplication.translate("main_window", "Device"),
                QCoreApplication.translate("main_window", "Core"),
                QCoreApplication.translate("main_window", "NumCores"),
                QCoreApplication.translate("main_window", "Flash Size"),
                QCoreApplication.translate("main_window", "RAM Size")
            ]

            model = DeviceTableModel(self.devices_list, header_data)

            self.proxy_model.setSourceModel(model)
            self.ui.tableView.setModel(self.proxy_model)
            #self.ui.tableView.setSortingEnabled(True)  # 开启排序
            # set font
            # font = QFont("Courier New", 9)
            # self.ui.tableView.setFont(font)
            # set column width to fit contents (set font first!)
            # Disable auto-resizing
            self.ui.tableView.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
            self.ui.tableView.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
			
            # Set fixed column widths (adjust the values based on your needs)
            self.ui.tableView.setColumnWidth(0, 100)  # Manufacturer
            self.ui.tableView.setColumnWidth(1, 280)  # Device
            self.ui.tableView.setColumnWidth(2, 140)  # Core
            self.ui.tableView.setColumnWidth(3, 70)  # NumCores
            self.ui.tableView.setColumnWidth(4, 70)  # Flash Size
            self.ui.tableView.setColumnWidth(5, 70)  # RAM Size
            self.ui.tableView.setSelectionBehavior(
                QAbstractItemView.SelectRows)

            self.ui.tableView.clicked.connect(self.refresh_selected_device)
            # 在设备选择对话框中连接到双击事件
            self.ui.tableView.doubleClicked.connect(self.accept)
            
        # 📋 修复：连接对话框按钮的信号
        self.ui.buttonBox.accepted.connect(self.accept)
        self.ui.buttonBox.rejected.connect(self.reject)
            
    def get_jlink_devices_list_file(self):
        """获取JLink设备数据库文件路径
        
        优先级：
        1. JLink安装目录（从pylink库获取）
        2. 本地项目目录
        3. 打包后的资源目录
        """
        
        # 1. 优先从JLink安装目录读取（通过pylink库）
        try:
            import pylink
            # 尝试通过pylink获取JLink安装路径
            jlink_lib_path = pylink.library.Library().dll_path()
            if jlink_lib_path:
                jlink_dir = os.path.dirname(jlink_lib_path)
                jlink_xml = os.path.join(jlink_dir, 'JLinkDevicesBuildIn.xml')
                if os.path.exists(jlink_xml):
                    logger.info(f"Using JLink device database from installation: {jlink_xml}")
                    return jlink_xml
        except Exception as e:
            logger.debug(f"Could not locate JLink installation directory: {e}")
        
        # 2. 开发环境：从当前目录读取
        if os.path.exists('JLinkDevicesBuildIn.xml'):
            local_path = os.path.abspath('JLinkDevicesBuildIn.xml')
            logger.info(f"Using local device database: {local_path}")
            return local_path
        
        # 3. 打包后环境：从资源目录读取
        try:
            # PyInstaller会将资源文件解压到sys._MEIPASS目录
            if hasattr(sys, '_MEIPASS'):
                resource_path = os.path.join(sys._MEIPASS, 'JLinkDevicesBuildIn.xml')
                if os.path.exists(resource_path):
                    logger.info(f"Using packaged device database: {resource_path}")
                    return resource_path
            
            # 尝试从当前可执行文件目录读取
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            exe_resource_path = os.path.join(exe_dir, 'JLinkDevicesBuildIn.xml')
            if os.path.exists(exe_resource_path):
                logger.info(f"Using device database from exe directory: {exe_resource_path}")
                return exe_resource_path
                
        except Exception as e:
            logger.warning(f"Failed to locate JLinkDevicesBuildIn.xml from resources: {e}")
        
        # 如果都找不到，抛出异常
        raise Exception(QCoreApplication.translate("main_window", "Can not find device database !"))
    
    def _device_database_exists(self):
        """检查设备数据库文件是否存在"""
        try:
            self.get_jlink_devices_list_file()
            return True
        except Exception:
            return False
    
    def _get_jlink_command_file_path(self):
        """获取JLinkCommandFile.jlink文件路径"""
        
        # 开发环境：优先从当前目录读取
        if os.path.exists('JLinkCommandFile.jlink'):
            return os.path.abspath('JLinkCommandFile.jlink')
        
        # 打包后环境：从资源目录读取
        try:
            # PyInstaller会将资源文件解压到sys._MEIPASS目录
            if hasattr(sys, '_MEIPASS'):
                resource_path = os.path.join(sys._MEIPASS, 'JLinkCommandFile.jlink')
                if os.path.exists(resource_path):
                    return resource_path
            
            # 尝试从当前可执行文件目录读取
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            exe_resource_path = os.path.join(exe_dir, 'JLinkCommandFile.jlink')
            if os.path.exists(exe_resource_path):
                return exe_resource_path
                
        except Exception as e:
            logger.warning(f"Failed to locate JLinkCommandFile.jlink from resources: {e}")
        
        # 如果都找不到，返回默认路径（向后兼容）
        return 'JLinkCommandFile.jlink'

    def parse_jlink_devices_list_file(self, path):
        """解析JLink设备数据库文件"""
        try:
            # 尝试使用UTF-8编码打开文件
            with open(path, 'r', encoding='utf-8') as parsefile:
                tree = ET.ElementTree(file=parsefile)
        except UnicodeDecodeError:
            # 如果UTF-8失败，尝试使用系统默认编码
            try:
                with open(path, 'r', encoding='gbk') as parsefile:
                    tree = ET.ElementTree(file=parsefile)
            except UnicodeDecodeError:
                # 最后尝试使用ISO-8859-1编码
                with open(path, 'r', encoding='iso-8859-1') as parsefile:
                    tree = ET.ElementTree(file=parsefile)
        except Exception as e:
            logger.error(f"Failed to open JLinkDevicesBuildIn.xml: {e}")
            raise Exception(QCoreApplication.translate("main_window", "Failed to parse device database file!"))

        jlink_devices_list = []

        for VendorInfo in tree.findall('VendorInfo'):
            for DeviceInfo in VendorInfo.findall('DeviceInfo'):
                device_item = []

                # get Manufacturer
                device_item.append(VendorInfo.attrib['Name'])
                # get Device
                device_item.append(DeviceInfo.attrib['Name'])
                # get Core
                device_item.append(DeviceInfo.attrib['Core'])
                # get NumCores
                # now fix 1
                device_item.append('1')
                # get Flash Size
                flash_size = 0
                for FlashBankInfo in DeviceInfo.findall('FlashBankInfo'):
                    flash_size += int(FlashBankInfo.attrib['Size'], 16)

                flash_size = flash_size // 1024
                if flash_size < 1024:
                    device_item.append(str(flash_size)+' KB')
                else:
                    flash_size = flash_size // 1024
                    device_item.append(str(flash_size)+' MB')
                # get RAM Size
                ram_size = 0
                if 'WorkRAMSize' in DeviceInfo.attrib.keys():
                    ram_size += int(DeviceInfo.attrib['WorkRAMSize'], 16)

                device_item.append(str(ram_size//1024)+' KB')

                # add item to list
                jlink_devices_list.append(device_item)

        parsefile.close()

        return jlink_devices_list

    def refresh_selected_device(self):
        proxy_index = self.ui.tableView.currentIndex()
        source_index = self.proxy_model.mapToSource(proxy_index)
        self._target = self.devices_list[source_index.row()][1]
        self.ui.label_sel_dev.setText(self._target)


    def get_target_device(self):
        return self._target

    def set_filter(self, text):
        self.proxy_model.setFilterKeyColumn(1) #只对 Device 列进行筛选
        self.proxy_model.setFilterFixedString(text) #设置筛选的文本
        
        # 筛选后将滚动条滚动到顶部
        if hasattr(self.ui, 'tableView'):
            self.ui.tableView.scrollToTop()

    # 在设备选择对话框类中添加一个方法来处理确定按钮的操作
    def accept(self):
        self.refresh_selected_device()
        super().accept()  # 调用父类的accept()以正确设置对话框结果

class FilterEditDialog(QDialog):
    """筛选文本编辑对话框，支持正则表达式"""
    def __init__(self, parent=None, current_text="", current_regex_state=False):
        super().__init__(parent)
        self.setWindowTitle(QCoreApplication.translate("main_window", "Edit Filter Text"))
        self.setModal(True)
        self.resize(400, 150)
        
        # 创建布局
        layout = QVBoxLayout(self)
        
        # 文本输入标签和输入框
        text_label = QLabel(QCoreApplication.translate("main_window", "Filter Text:"))
        layout.addWidget(text_label)
        
        self.text_edit = QLineEdit(current_text)
        self.text_edit.setPlaceholderText(QCoreApplication.translate("main_window", "Enter filter text..."))
        layout.addWidget(self.text_edit)
        
        # 正则表达式复选框
        self.regex_checkbox = QCheckBox(QCoreApplication.translate("main_window", "Enable Regular Expression"))
        self.regex_checkbox.setChecked(current_regex_state)
        self.regex_checkbox.setToolTip(QCoreApplication.translate("main_window", "Use regular expression for pattern matching"))
        layout.addWidget(self.regex_checkbox)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton(QCoreApplication.translate("main_window", "OK"))
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton(QCoreApplication.translate("main_window", "Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 设置焦点到文本输入框
        self.text_edit.setFocus()
        self.text_edit.selectAll()
    
    def get_filter_text(self):
        """获取筛选文本"""
        return self.text_edit.text().strip()
    
    def is_regex_enabled(self):
        """获取正则表达式状态"""
        return self.regex_checkbox.isChecked()

class ColumnSelectTextEdit(QTextEdit):
    """支持ALT键纵向选择文本的QTextEdit"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.column_select_mode = False
        self.column_select_start = None
        self.column_select_cursor_start = None
        self.column_select_ranges = None  # 保存选择范围(起始行列，结束行列)
        
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        from PySide6.QtCore import Qt
        # 🔧 修复：右键点击时，如果存在ALT选择块区，不清除选区
        if event.button() == Qt.RightButton:
            if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
                # 右键点击且有ALT选择块区，不处理，让contextMenuEvent处理
                # 不调用父类方法，避免清除选区
                event.accept()
                return
        
        # 检查是否按住ALT键
        if event.modifiers() & Qt.AltModifier:
            self.column_select_mode = True
            # 记录起始位置
            self.column_select_start = event.pos()
            cursor = self.cursorForPosition(event.pos())
            self.column_select_cursor_start = cursor
            # 清除现有选择
            cursor.clearSelection()
            self.setTextCursor(cursor)
            event.accept()
        else:
            self.column_select_mode = False
            # 🔧 清除纵向选择的高亮（但右键点击时已在上面的检查中处理）
            self._clearColumnSelection()
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.column_select_mode and self.column_select_start:
            # 执行纵向选择
            self._updateColumnSelection(event.pos())
            event.accept()
        else:
            # 🔧 普通拖动选择时清除纵向选择高亮
            if hasattr(self, '_column_selection_data') and event.buttons():
                self._clearColumnSelection()
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        from PySide6.QtCore import Qt
        # 🔧 修复：右键释放时，如果存在ALT选择块区，不清除选区
        if event.button() == Qt.RightButton:
            if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
                # 右键释放且有ALT选择块区，不处理，让contextMenuEvent处理
                # 不调用父类方法，避免清除选区
                event.accept()
                return
        
        if self.column_select_mode:
            self.column_select_mode = False
            # 保存选择信息以便复制
            self._saveColumnSelection()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event):
        """🔧 修复：右键菜单事件 - 使用Qt默认菜单，保持ALT选择块区不被清除"""
        # 创建Qt标准上下文菜单
        menu = self.createStandardContextMenu()
        
        # 如果有ALT选择块区，修改复制动作的行为
        if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
            # 找到复制动作并替换其行为
            copy_shortcut = QKeySequence(QKeySequence.Copy).toString()
            for action in menu.actions():
                # 检查是否是复制动作（通过快捷键或文本）
                action_shortcut = action.shortcut().toString() if action.shortcut() else ""
                action_text = action.text().lower()
                if copy_shortcut and action_shortcut == copy_shortcut:
                    # 断开原有的连接，连接新的复制方法
                    try:
                        action.triggered.disconnect()
                    except:
                        pass  # 如果没有连接，忽略错误
                    action.triggered.connect(self._copyColumnSelection)
                    # 🔧 修复：确保复制动作是启用的
                    action.setEnabled(True)
                    break
                elif 'copy' in action_text or '复制' in action_text:
                    # 也检查文本中包含copy或复制
                    try:
                        action.triggered.disconnect()
                    except:
                        pass
                    action.triggered.connect(self._copyColumnSelection)
                    # 🔧 修复：确保复制动作是启用的
                    action.setEnabled(True)
                    break
        
        # 显示菜单
        menu.exec_(event.globalPos())
        event.accept()
    
    def keyPressEvent(self, event):
        """键盘事件 - 支持Ctrl+C复制纵向选择的文本"""
        if event.matches(QKeySequence.Copy) and hasattr(self, '_column_selection_data'):
            # 复制纵向选择的文本
            self._copyColumnSelection()
            event.accept()
        else:
            # 🔧 其他键盘操作（方向键等）时清除纵向选择高亮
            # 因为文本编辑器是只读的，主要是方向键和PageUp/Down会改变视图
            from PySide6.QtCore import Qt
            if event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, 
                              Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown]:
                if hasattr(self, '_column_selection_data'):
                    self._clearColumnSelection()
            super().keyPressEvent(event)
    
    def _saveColumnSelection(self):
        """保存纵向选择的数据"""
        if not self.column_select_ranges:
            return
        
        start_line, start_col, end_line, end_col = self.column_select_ranges
        
        # 收集每行选中的文本
        selected_texts = []
        document = self.document()
        
        for line_num in range(start_line, end_line + 1):
            block = document.findBlockByNumber(line_num)
            if not block.isValid():
                continue
            
            block_text = block.text()
            block_length = len(block_text)
            
            # 计算本行的选择范围
            line_start_col = min(start_col, block_length)
            line_end_col = min(end_col, block_length)
            
            if line_start_col < line_end_col:
                selected_text = block_text[line_start_col:line_end_col]
                selected_texts.append(selected_text)
        
        # 保存选择数据（用于复制）
        self._column_selection_data = selected_texts
        
        # 重新应用高亮以确保显示
        self._applyColumnHighlight()
    
    def _copyColumnSelection(self):
        """复制纵向选择的文本到剪贴板"""
        if not hasattr(self, '_column_selection_data') or not self._column_selection_data:
            return
        
        # 将每行文本用换行符连接
        text = '\n'.join(self._column_selection_data)
        
        # 复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
    
    def _applyColumnHighlight(self):
        """应用纵向选择的高亮"""
        if not self.column_select_ranges:
            return
        
        start_line, start_col, end_line, end_col = self.column_select_ranges
        
        # 创建纵向选择
        extra_selections = []
        document = self.document()
        
        for line_num in range(start_line, end_line + 1):
            block = document.findBlockByNumber(line_num)
            if not block.isValid():
                continue
            
            block_text = block.text()
            block_length = len(block_text)
            
            # 计算本行的选择范围
            line_start_col = min(start_col, block_length)
            line_end_col = min(end_col, block_length)
            
            if line_start_col < line_end_col:
                # 创建选区
                selection = QTextEdit.ExtraSelection()
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + line_start_col)
                cursor.setPosition(block.position() + line_end_col, QTextCursor.KeepAnchor)
                
                # 设置选区样式
                selection.cursor = cursor
                selection.format.setBackground(self.palette().highlight())
                selection.format.setForeground(self.palette().highlightedText())
                
                extra_selections.append(selection)
        
        # 应用选区
        self.setExtraSelections(extra_selections)
    
    def _clearColumnSelection(self):
        """清除纵向选择的高亮"""
        # 清除ExtraSelections高亮
        self.setExtraSelections([])
        # 清除保存的选择数据
        if hasattr(self, '_column_selection_data'):
            delattr(self, '_column_selection_data')
        if hasattr(self, '_column_selections'):
            delattr(self, '_column_selections')
        # 清除选择范围
        self.column_select_ranges = None
    
    def focusOutEvent(self, event):
        """失去焦点事件"""
        # 不再自动清除选择，保持选中状态
        super().focusOutEvent(event)
    
    def paintEvent(self, event):
        """重绘事件 - 保持纵向选择高亮"""
        super().paintEvent(event)
        # 如果有保存的选择范围，始终重新应用高亮（保持选中状态直到下次选择）
        if self.column_select_ranges:
            self._applyColumnHighlight()
    
    def _updateColumnSelection(self, end_pos):
        """更新纵向选择"""
        if not self.column_select_cursor_start:
            return
        
        # 获取起始和结束光标位置
        start_cursor = self.column_select_cursor_start
        end_cursor = self.cursorForPosition(end_pos)
        
        # 获取起始和结束的行号和列号
        start_block = start_cursor.block()
        end_block = end_cursor.block()
        
        start_line = start_block.blockNumber()
        end_line = end_block.blockNumber()
        
        start_col = start_cursor.positionInBlock()
        end_col = end_cursor.positionInBlock()
        
        # 确保起始行小于结束行
        if start_line > end_line:
            start_line, end_line = end_line, start_line
            start_col, end_col = end_col, start_col
        
        # 确保起始列小于结束列
        if start_col > end_col:
            start_col, end_col = end_col, start_col
        
        # 保存选择范围用于后续重新应用
        self.column_select_ranges = (start_line, start_col, end_line, end_col)
        
        # 应用高亮
        self._applyColumnHighlight()


class EditableTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None  # 将在主窗口中设置
        self.drag_start_pos = None  # 拖动起始位置
        self.is_dragging = False  # 是否正在拖动
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件，鼠标中键点击清空筛选"""
        if event.button() == Qt.LeftButton:
            # 记录左键按下位置，用于拖动检测
            self.drag_start_pos = event.pos()
            self.is_dragging = False
        
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.pos())
            # 中键点击TAB
            if index >= 17:  # 只处理Filters标签
                # 中键清除筛选TAB
                # 清空该标签页
                # 找到当前的DeviceMdiWindow实例
                tab_widget = self.parent()
                mdi_window = None
                if tab_widget:
                    # tab_widget.parent() 是 DeviceMdiWindow
                    # 因为 tab_widget 是直接添加到 DeviceMdiWindow 的布局中的
                    mdi_window = tab_widget.parent()
                    
                    # 如果 parent 是 QWidget，可能需要再往上找
                    if mdi_window and not isinstance(mdi_window, DeviceMdiWindow):
                        # 可能是 QMdiSubWindow，获取其 widget
                        if hasattr(mdi_window, 'widget'):
                            mdi_window = mdi_window.widget()
                    
                    pass
                
                if mdi_window and isinstance(mdi_window, DeviceMdiWindow):
                    old_text = self.tabText(index)
                    pass
                    
                    # 保存当前标签页索引
                    current_index = tab_widget.currentIndex()
                    # 切换到目标标签页
                    tab_widget.setCurrentIndex(index)
                    
                    # 清空该TAB的文本编辑器
                    if index < len(mdi_window.text_edits):
                        mdi_window.text_edits[index].clear()
                        pass
                    
                    # 清空Worker的缓冲区
                    if mdi_window.device_session and mdi_window.device_session.connection_dialog:
                        worker = getattr(mdi_window.device_session.connection_dialog, 'worker', None)
                        if worker and index < len(worker.colored_buffers):
                            worker.colored_buffers[index].clear()
                            worker.colored_buffer_lengths[index] = 0
                            mdi_window.last_display_lengths[index] = 0
                            pass
                    
                    # 🔑 先保存空字符串到配置（MDI架构：使用当前设备会话的配置）
                    # 必须在 update_filter_tab_display() 之前更新配置，否则判断逻辑会读取到旧值
                    if mdi_window.device_session and mdi_window.device_session.connection_dialog:
                        mdi_window.device_session.connection_dialog.config.set_filter(index, "")
                        pass
                    
                    # 重置标签文本为"+"
                    self.setTabText(index, "+")
                    pass
                    
                    # 更新筛选TAB显示（隐藏多余的空TAB）
                    pass
                    mdi_window.update_filter_tab_display()
                    
                    # 保存配置到文件
                    if mdi_window.device_session and mdi_window.device_session.connection_dialog:
                        mdi_window.device_session.connection_dialog.config.save_config()
                        pass
                    
                    # 恢复原来的标签页（如果不是同一个）
                    if current_index != index:
                        tab_widget.setCurrentIndex(current_index)
                    
                    pass
                else:
                    logger.warning(f"mdi_window无效或不是DeviceMdiWindow实例")
                event.accept()
                return
            else:
                pass
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，实现拖动切换标签"""
        if event.buttons() & Qt.LeftButton and self.drag_start_pos is not None:
            # 检测是否开始拖动
            if not self.is_dragging:
                # 计算移动距离
                delta = event.pos() - self.drag_start_pos
                if abs(delta.x()) > 5 or abs(delta.y()) > 5:  # 移动超过5像素才算拖动
                    self.is_dragging = True
            
            if self.is_dragging:
                # 获取当前鼠标位置下的标签索引
                index = self.tabAt(event.pos())
                if index >= 0:
                    # 切换到该标签
                    if self.parent():
                        self.parent().setCurrentIndex(index)
                event.accept()
                return
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = None
            self.is_dragging = False
        super().mouseReleaseEvent(event)
    
    # 移除 tabSizeHint 重写，恢复原来的自适应行为
    # def tabSizeHint(self, index):
    #     """重写标签大小提示，让当前标签优先完整显示"""
    #     # 获取原始大小提示
    #     size = super().tabSizeHint(index)
    #     
    #     # 如果是当前标签，保持完整宽度
    #     if index == self.currentIndex():
    #         return size
    #     
    #     # 非当前标签，缩小到最小宽度（显示省略号）
    #     # 设置最小宽度为字体宽度的3倍（足够显示1-2个字符+省略号）
    #     from PySide6.QtGui import QFontMetrics
    #     fm = QFontMetrics(self.font())
    #     min_width = fm.averageCharWidth() * 4  # 4个字符宽度
    #     
    #     # 返回最小宽度和原始宽度的较小值
    #     size.setWidth(min(size.width(), max(min_width, 40)))
    #     return size
    
    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.pos())
        
        # 处理ALL标签页（索引为0）的颜色配置
        if index == 0:
            # 找到当前的DeviceMdiWindow实例
            tab_widget = self.parent()
            mdi_window = None
            if tab_widget:
                # tab_widget.parent() 是 DeviceMdiWindow
                mdi_window = tab_widget.parent()
                
                # 如果 parent 是 QWidget，可能需要再往上找
                if mdi_window and not isinstance(mdi_window, DeviceMdiWindow):
                    # 可能是 QMdiSubWindow，获取其 widget
                    if hasattr(mdi_window, 'widget'):
                        mdi_window = mdi_window.widget()
            
            if mdi_window and isinstance(mdi_window, DeviceMdiWindow):
                # 导入颜色配置对话框
                from color_config_dialog import ColorConfigDialog
                
                # 从设备会话中获取配置管理器
                config_manager = None
                if hasattr(mdi_window, 'device_session') and mdi_window.device_session and hasattr(mdi_window.device_session, 'connection_dialog') and mdi_window.device_session.connection_dialog:
                    config_manager = mdi_window.device_session.connection_dialog.config
                
                # 确保配置管理器存在
                if not config_manager:
                    logger.error("无法获取配置管理器，无法打开颜色配置对话框")
                    return
                
                # 显示颜色配置对话框
                dialog = ColorConfigDialog(config_manager, parent=mdi_window.main_window)
                if dialog.exec() == QDialog.Accepted:
                    # 颜色配置已保存，清空ALL标签页数据以重新加载颜色设置
                    # 准备清空ALL标签页(TAB[0])的数据
                    if index < len(mdi_window.text_edits):
                        # 清空文本编辑器
                        mdi_window.text_edits[index].clear()
                        pass
                        
                        # 清空Worker的缓冲区
                        if mdi_window.device_session and mdi_window.device_session.connection_dialog:
                            worker = getattr(mdi_window.device_session.connection_dialog, 'worker', None)
                            if worker and index < len(worker.colored_buffers):
                                worker.colored_buffers[index].clear()
                                worker.colored_buffer_lengths[index] = 0
                                mdi_window.last_display_lengths[index] = 0
                                pass
                    
                    # 记录日志
                    pass
            
            return
        if index >= 17:
            old_text = self.tabText(index)
            
            # 找到当前的DeviceMdiWindow实例（MDI架构）
            tab_widget = self.parent()
            mdi_window = None
            if tab_widget:
                # tab_widget.parent() 是 DeviceMdiWindow
                # 因为 tab_widget 是直接添加到 DeviceMdiWindow 的布局中的
                mdi_window = tab_widget.parent()
                
                # 如果 parent 是 QWidget，可能需要再往上找
                if mdi_window and not isinstance(mdi_window, DeviceMdiWindow):
                    # 可能是 QMdiSubWindow，获取其 widget
                    if hasattr(mdi_window, 'widget'):
                        mdi_window = mdi_window.widget()
                
                pass
            
            # 如果是"+"符号,传递空字符串给对话框
            # 如果筛选内容本身就是"+",则传递"+"
            dialog_text = old_text
            if old_text == "+":
                # 检查配置中的实际内容（MDI架构：使用当前设备会话的配置）
                actual_filter = ""
                if mdi_window and mdi_window.device_session and mdi_window.device_session.connection_dialog:
                    actual_filter = mdi_window.device_session.connection_dialog.config.get_filter(index)
                # 如果配置中是空的或也是"+",传空字符串;否则传实际内容
                if not actual_filter or actual_filter == "+":
                    dialog_text = ""
                else:
                    dialog_text = actual_filter
            
            # 获取当前TAB的正则表达式状态（MDI架构）
            current_regex_state = False
            if mdi_window and mdi_window.device_session and mdi_window.device_session.connection_dialog:
                current_regex_state = mdi_window.device_session.connection_dialog.config.get_tab_regex_filter(index)
            
            # 显示自定义对话框
            dialog = FilterEditDialog(self, dialog_text, current_regex_state)
            if dialog.exec() == QDialog.Accepted:
                new_text = dialog.get_filter_text()
                regex_enabled = dialog.is_regex_enabled()
                
                # 更新TAB文本和tooltip
                tab_widget = self.parent()
                if new_text:
                    self.setTabText(index, new_text)
                    # 设置tooltip显示完整内容
                    if tab_widget:
                        tab_widget.setTabToolTip(index, new_text)
                    # 更新TAB筛选文本
                else:
                    self.setTabText(index, "+")  # 清空时显示"+"
                    # 设置tooltip提示双击编辑
                    if tab_widget:
                        from PySide6.QtCore import QCoreApplication
                        tab_widget.setTabToolTip(index, QCoreApplication.translate("main_window", "Double-click to edit filter"))
                    # 清空TAB筛选文本
                
                # 找到当前的DeviceMdiWindow实例
                mdi_window = None
                if tab_widget:
                    # tab_widget.parent() 是 DeviceMdiWindow
                    # 因为 tab_widget 是直接添加到 DeviceMdiWindow 的布局中的
                    mdi_window = tab_widget.parent()
                    
                    # 如果 parent 是 QWidget，可能需要再往上找
                    if mdi_window and not isinstance(mdi_window, DeviceMdiWindow):
                        # 可能是 QMdiSubWindow，获取其 widget
                        if hasattr(mdi_window, 'widget'):
                            mdi_window = mdi_window.widget()
                    
                    pass
                
                # 如果清空了筛选文本，同时清空该TAB的数据
                if not new_text:
                    # 准备清空TAB[{index}]的数据
                    if mdi_window and isinstance(mdi_window, DeviceMdiWindow):
                        pass
                        if index < len(mdi_window.text_edits):
                            pass
                            # 清空文本编辑器
                            mdi_window.text_edits[index].clear()
                            pass
                            
                            # 清空Worker的缓冲区
                            if mdi_window.device_session and mdi_window.device_session.connection_dialog:
                                worker = getattr(mdi_window.device_session.connection_dialog, 'worker', None)
                                if worker and index < len(worker.colored_buffers):
                                    worker.colored_buffers[index].clear()
                                    worker.colored_buffer_lengths[index] = 0
                                    mdi_window.last_display_lengths[index] = 0
                                    pass
                        else:
                            logger.warning(f"TAB索引{index}超出范围！text_edits总数: {len(mdi_window.text_edits)}")
                    else:
                        logger.warning(f"  ✗ mdi_window无效或不是DeviceMdiWindow实例")
                
                # 🔑 先保存过滤器设置和正则表达式状态（MDI架构：使用当前设备会话的配置）
                # 必须在 update_filter_tab_display() 之前更新配置，否则判断逻辑会读取到旧值
                if mdi_window and mdi_window.device_session and mdi_window.device_session.connection_dialog:
                    config = mdi_window.device_session.connection_dialog.config
                    
                    # 🔑 架构改进：config对象在UI初始化时已包含所有筛选值
                    # 只需要更新当前TAB的值即可
                    if new_text:
                        config.set_filter(index, new_text)
                        # 更新配置中的筛选值
                    else:
                        config.set_filter(index, "")
                        # 更新配置中的筛选值为空
                    
                    # 🔧 修改：为单个TAB保存正则表达式状态
                    config.set_tab_regex_filter(index, regex_enabled)
                    pass
                
                # 更新筛选TAB显示（隐藏多余的空TAB）
                if mdi_window and isinstance(mdi_window, DeviceMdiWindow):
                    pass
                    mdi_window.update_filter_tab_display()
                
                # 保存配置到文件
                if mdi_window and mdi_window.device_session and mdi_window.device_session.connection_dialog:
                    config = mdi_window.device_session.connection_dialog.config
                    config.save_config()
                    pass

class DeviceMdiWindow(QWidget):
    """设备MDI子窗口内容 - 每个设备有自己的32个日志TAB"""
    def __init__(self, device_session, parent=None):
        super(DeviceMdiWindow, self).__init__(parent)
        
        self.device_session = device_session
        self.main_window = parent  # 保存主窗口引用以访问配置
        self.mdi_sub_window = None  # 将在添加到MDI区域时设置
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建32个日志TAB
        from PySide6.QtWidgets import QTabWidget
        from ansi_terminal_widget import FastAnsiTextEdit
        
        self.tab_widget = QTabWidget()
        
        # 使用可编辑的TAB栏
        editable_tab_bar = EditableTabBar()
        editable_tab_bar.main_window = parent  # 设置主窗口引用
        self.tab_widget.setTabBar(editable_tab_bar)
        
        # 初始化32个TAB - 使用FastAnsiTextEdit支持ANSI颜色
        # TAB标签: ALL, 0-15, +筛选(17-31)
        self.text_edits = []  # 保存所有text_edit引用
        for i in range(MAX_TAB_SIZE):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            
            # 使用FastAnsiTextEdit代替普通QTextEdit，传递标签页索引和配置管理器
            # 获取配置管理器引用
            config_manager = None
            if hasattr(device_session, 'connection_dialog') and device_session.connection_dialog:
                config_manager = device_session.connection_dialog.config
                
            # 创建FastAnsiTextEdit实例，传递标签页索引和配置管理器
            # 注意：i=0是ALL标签页，i=1-16是通道0-15，i>16是筛选标签页
            text_edit = FastAnsiTextEdit(tab_index=i, config_manager=config_manager)
            text_edit.setReadOnly(True)
            text_edit.setLineWrapMode(QTextEdit.NoWrap)
            
            # 应用主窗口的字体设置
            if parent and hasattr(parent, 'ui'):
                try:
                    if hasattr(parent.ui, 'font_combo'):
                        font_name = parent.ui.font_combo.currentText()
                    else:
                        font_name = "Consolas"
                    font_size = parent.ui.fontsize_box.value() if hasattr(parent.ui, 'fontsize_box') else 10
                    
                    font = QFont(font_name, font_size)
                    font.setFixedPitch(True)
                    font.setStyleHint(QFont.TypeWriter)
                    text_edit.setFont(font)
                except:
                    pass
            
            page_layout.addWidget(text_edit)
            
            # 设置TAB标签名称
            if i == 0:
                tab_name = self.tr("ALL")
            elif i <= 16:
                tab_name = str(i - 1)  # 1-16显示为0-15
            else:
                # 筛选TAB (17-31)：初始只显示一个"+"，有内容时显示内容
                tab_name = "+"  # 初始都显示为"+"
            
            self.tab_widget.addTab(page, tab_name)
            
            # 筛选TAB初始时先隐藏（除了第一个）
            if i > 17:
                self.tab_widget.setTabVisible(i, False)
            
            self.text_edits.append(text_edit)
        
        layout.addWidget(self.tab_widget)
        
        # 创建定时器定期从Worker缓冲区更新UI
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_from_worker)
        self.update_timer.start(TimerInterval.MDI_WINDOW_UPDATE)
        
        # 记录上次显示的长度，用于增量更新
        self.last_display_lengths = [0] * MAX_TAB_SIZE
        
        # 🔧 修复：监听TAB切换事件，切换时强制刷新当前TAB内容
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # 🔧 修复：记录每个TAB上次更新的时间，用于低频率刷新非激活TAB
        self.last_tab_update_times = [0.0] * MAX_TAB_SIZE
        self.inactive_tab_update_interval = 3.0  # 非激活TAB更新间隔：3秒
        self.last_inactive_gap_check_times = [0.0] * MAX_TAB_SIZE  # 非激活TAB数据丢失检测时间
        self.inactive_gap_check_interval = 6.0  # 非激活TAB数据丢失检测间隔：6秒
        
        # 为每个text_edit添加滚动条锁定属性和位置保存
        # 安装滚动条监听器
        for i, text_edit in enumerate(self.text_edits):
            # 在text_edit对象上添加自定义属性
            text_edit._channel_idx = i  # 通道索引
            text_edit._v_scroll_locked = False  # 垂直滚动条锁定状态
            text_edit._saved_h_pos = 0  # 保存的水平滚动条位置
            text_edit._saved_v_pos = 0  # 保存的垂直滚动条位置
            text_edit._user_scrolling = False  # 标记用户是否正在拖动滑块
            text_edit._wheel_scrolling = False  # 标记用户是否正在使用滚轮
            text_edit._wheel_delta = 0  # 记录滚轮滚动方向（正数=向下，负数=向上）
            
            v_scrollbar = text_edit.verticalScrollBar()
            h_scrollbar = text_edit.horizontalScrollBar()
            
            # 监听用户手动操作滚动条（按下和释放滑块、滑块移动）
            v_scrollbar.sliderPressed.connect(lambda te=text_edit: self._on_slider_pressed(te))
            v_scrollbar.sliderReleased.connect(lambda te=text_edit: self._on_slider_released(te))
            v_scrollbar.sliderMoved.connect(lambda value, te=text_edit: self._on_slider_moved(te, value))
            
            # 安装事件过滤器来检测鼠标滚轮事件
            # 需要同时在text_edit和其viewport上安装，因为滚轮事件可能发生在viewport上
            text_edit.installEventFilter(self)
            text_edit.viewport().installEventFilter(self)
            
            # 垂直滚动条监听：检测用户操作并更新锁定状态
            v_scrollbar.valueChanged.connect(lambda value, te=text_edit: self._on_vertical_scroll_changed(te, value))
            
            # 水平滚动条监听：保存用户设置的位置
            h_scrollbar.valueChanged.connect(lambda value, te=text_edit: self._on_horizontal_scroll_changed(te, value))
            
            pass
        
        # 设置窗口大小
        self.resize(WindowSize.MDI_WINDOW_DEFAULT_WIDTH, WindowSize.MDI_WINDOW_DEFAULT_HEIGHT)
        
        # 从配置加载筛选文本并设置tooltip
        if parent and hasattr(parent, 'connection_dialog') and parent.connection_dialog:
            for i in range(17, MAX_TAB_SIZE):
                filter_content = parent.connection_dialog.config.get_filter(i)
                if filter_content:
                    self.tab_widget.setTabText(i, filter_content)
                    # 设置tooltip显示完整的筛选内容
                    self.tab_widget.setTabToolTip(i, filter_content)
                    logger.debug(f"  Filter[{i}] loaded: '{filter_content}'")
                else:
                    # 空内容时设置tooltip提示双击编辑
                    from PySide6.QtCore import QCoreApplication
                    self.tab_widget.setTabToolTip(i, QCoreApplication.translate("main_window", "Double-click to edit filter"))
        self.tab_widget.setTabToolTip(0, QCoreApplication.translate("main_window", "Double-click to edit colorsetting"))
        # 初始化筛选TAB显示（隐藏多余的空筛选TAB）
        self.update_filter_tab_display()
        
        pass
    
    def eventFilter(self, obj, event):
        """事件过滤器：检测鼠标滚轮事件并记录滚动方向"""
        try:
            from PySide6.QtCore import QEvent
            # 检测鼠标滚轮事件
            if event.type() == QEvent.Type.Wheel:
                # 找到对应的text_edit对象
                text_edit = None
                if hasattr(obj, '_wheel_scrolling'):
                    # obj本身就是text_edit
                    text_edit = obj
                else:
                    # obj可能是viewport，需要找到父text_edit
                    parent = obj.parent()
                    if parent and hasattr(parent, '_wheel_scrolling'):
                        text_edit = parent
                
                if text_edit:
                    text_edit._wheel_scrolling = True
                    # angleDelta().y() < 0 表示向上滚（内容向下移动，远离底部）
                    # angleDelta().y() > 0 表示向下滚（内容向上移动，接近底部）
                    text_edit._wheel_delta = event.angleDelta().y()
                    pass
        except Exception as e:
            logger.error(f"Error in event filter: {e}", exc_info=True)
        
        # 继续传递事件
        return super().eventFilter(obj, event)
    
    def _on_slider_pressed(self, text_edit):
        """用户按下滚动条滑块时的处理"""
        text_edit._user_scrolling = True
        pass
    
    def _on_slider_released(self, text_edit):
        """用户释放滚动条滑块时的处理"""
        text_edit._user_scrolling = False
        pass
    
    def _on_slider_moved(self, text_edit, value):
        """用户拖动滚动条滑块时的处理（包括鼠标滚轮）"""
        # 标记用户正在操作，并立即更新锁定状态
        text_edit._user_scrolling = True
        pass
    
    def _on_vertical_scroll_changed(self, text_edit, value):
        """垂直滚动条位置变化时的处理 - 智能锁定
        拖动滑块或使用滚轮时都会更新锁定状态
        """
        try:
            channel_idx = text_edit._channel_idx
            
            # 只处理当前激活的TAB
            current_tab = self.tab_widget.currentIndex()
            if channel_idx != current_tab:
                return
            
            # 始终保存当前位置
            text_edit._saved_v_pos = value
            
            scrollbar = text_edit.verticalScrollBar()
            
            # 判断是否是用户操作：
            # 1. 拖动滑块：_user_scrolling=True AND isSliderDown()=True
            # 2. 使用滚轮：_wheel_scrolling=True
            is_dragging = text_edit._user_scrolling and scrollbar.isSliderDown()
            is_wheeling = text_edit._wheel_scrolling
            is_user_action = is_dragging or is_wheeling
            
            # 只有用户操作时才更新锁定状态
            if not is_user_action:
                return
            
            # 更新锁定状态的逻辑：
            old_state = text_edit._v_scroll_locked
            
            if is_wheeling:
                # 滚轮操作：根据滚动方向判断
                # wheel_delta > 0: 向上滚（内容向下移动，远离底部）→ 锁定
                # wheel_delta < 0: 向下滚（内容向上移动，接近底部）→ 检查是否到底部
                
                # 检查是否在底部
                at_bottom = (scrollbar.value() >= scrollbar.maximum() - 2)
                
                if text_edit._wheel_delta > 0:
                    # 向上滚动：锁定
                    text_edit._v_scroll_locked = True
                    if old_state != text_edit._v_scroll_locked:
                        logger.info(f"🔒 Channel {channel_idx} scroll lock changed by WHEEL: LOCKED=True (向上滚动, delta={text_edit._wheel_delta})")
                elif text_edit._wheel_delta < 0:
                    # 向下滚动：只有到达底部时才解锁
                    if at_bottom:
                        text_edit._v_scroll_locked = False
                        if old_state != text_edit._v_scroll_locked:
                            logger.info(f"🔒 Channel {channel_idx} scroll lock changed by WHEEL: LOCKED=False (向下滚动到底部, delta={text_edit._wheel_delta}, value={value}, max={scrollbar.maximum()})")
                    # 如果没到底部，保持当前锁定状态不变
                
                # 重置滚轮标志
                text_edit._wheel_scrolling = False
                text_edit._wheel_delta = 0
            elif is_dragging:
                # 拖动滑块：实时更新锁定状态（立即生效，不等松开鼠标）
                # 检查是否在底部
                at_bottom = (scrollbar.value() >= scrollbar.maximum() - 2)
                new_lock_state = not at_bottom
                
                # 立即更新锁定状态（每次拖动都更新，确保即使新数据到来也能正确判断）
                text_edit._v_scroll_locked = new_lock_state
                
                # 只在状态真正改变时记录日志
                if old_state != new_lock_state:
                    logger.info(f"🔒 Channel {channel_idx} scroll lock changed by DRAG: LOCKED={text_edit._v_scroll_locked} (at_bottom={at_bottom}, value={value}, max={scrollbar.maximum()})")
            
        except Exception as e:
            logger.error(f"Error in scroll changed handler: {e}", exc_info=True)
    
    def _on_horizontal_scroll_changed(self, text_edit, value):
        """水平滚动条位置变化时的处理 - 保存用户设置的位置"""
        try:
            # 保存当前位置到text_edit对象（所有TAB都保存，不只是当前激活的）
            text_edit._saved_h_pos = value
            # logger.debug(f"↔️ Channel {text_edit._channel_idx} H-scroll position saved: {value}")
            
        except Exception as e:
            logger.error(f"Error in horizontal scroll handler: {e}", exc_info=True)
    
    def _on_tab_changed(self, index):
        """TAB切换事件处理 - 检查并强制刷新当前TAB内容"""
        try:
            if index < 0 or index >= MAX_TAB_SIZE:
                return
            
            if not self.device_session.connection_dialog:
                return
            
            worker = getattr(self.device_session.connection_dialog, 'worker', None)
            if not worker:
                return
            
            # 检查当前TAB的显示长度是否远小于Worker缓冲区长度
            current_length = worker.colored_buffer_lengths[index]
            last_length = self.last_display_lengths[index]
            
            # 如果缓冲区有数据但显示长度远小于缓冲区长度，说明有大量数据丢失
            # 阈值：如果差距超过1KB，强制刷新
            gap_threshold = 1024
            if current_length > last_length + gap_threshold:
                logger.warning(f"🔧 TAB[{index}]切换检测到数据丢失: last_display={last_length}, buffer={current_length}, gap={current_length - last_length}, 强制刷新")
                
                # 强制刷新当前TAB的内容
                self._force_refresh_tab(index)
        except Exception as e:
            logger.error(f"Error in tab changed handler: {e}", exc_info=True)
    
    def _force_refresh_tab(self, channel):
        """强制刷新指定TAB的内容 - 从Worker缓冲区重新加载所有数据"""
        try:
            if not self.device_session.connection_dialog:
                return
            
            worker = getattr(self.device_session.connection_dialog, 'worker', None)
            if not worker:
                return
            
            if channel < 0 or channel >= MAX_TAB_SIZE or channel >= len(self.text_edits):
                return
            
            # 获取彩色缓冲区的当前长度
            current_length = worker.colored_buffer_lengths[channel]
            last_length = self.last_display_lengths[channel]
            
            if current_length <= last_length:
                # 没有新数据，不需要刷新
                return
            
            # 提取所有未显示的数据
            colored_data = ''.join(worker.colored_buffers[channel])
            missing_data = colored_data[last_length:]
            
            if not missing_data:
                return
            
            text_edit = self.text_edits[channel]
            
            # 获取滚动条
            v_scrollbar = text_edit.verticalScrollBar()
            h_scrollbar = text_edit.horizontalScrollBar()
            
            # 保存当前滚动条位置
            vscroll = v_scrollbar.value()
            hscroll = h_scrollbar.value()
            was_at_bottom = (vscroll >= v_scrollbar.maximum() - 2)
            
            # 🔧 修复重影问题：如果缺失数据量很大（超过1MB），说明可能已经丢失了大量数据
            # 此时应该清空显示并重新加载所有数据，避免文本重叠
            if len(missing_data) > 1024 * 1024:  # 1MB阈值
                logger.warning(f"🔧 TAB[{channel}] Missing data too large ({len(missing_data)//1024}KB), clearing and reloading all data")
                # 清空显示
                text_edit.clear()
                # 重新加载所有数据
                all_data = colored_data
                last_length = 0
            else:
                all_data = missing_data
            
            # 插入数据（使用正确的光标位置，避免重叠）
            if hasattr(text_edit, '_parse_ansi_fast'):
                # 检查数据中是否包含清屏序列，如果有则先清屏
                if '\x1B[2J' in all_data:
                    text_edit.clear_content()
                    # 重置已显示长度
                    self.last_display_lengths[channel] = 0
                    # 更新数据为清屏序列之后的部分
                    all_data = all_data.split('\x1B[2J')[-1]
                
                # 使用FastAnsiTextEdit的解析方法
                segments = text_edit._parse_ansi_fast(all_data)
                cursor = text_edit.textCursor()
                cursor.movePosition(QTextCursor.End)
                for segment in segments:
                    if segment['text']:
                        cursor.insertText(segment['text'], segment['format'])
                text_edit.setTextCursor(cursor)
            else:
                # 降级处理：使用普通追加
                cursor = text_edit.textCursor()
                cursor.movePosition(QTextCursor.End)
                text_edit.setTextCursor(cursor)
                text_edit.insertPlainText(all_data)
            
            # 恢复滚动条位置
            v_scrollbar.blockSignals(True)
            h_scrollbar.blockSignals(True)
            
            try:
                # 如果之前滚动条在底部，或者用户没有锁定滚动条，则滚动到底部
                if was_at_bottom or not text_edit._v_scroll_locked:
                    v_scrollbar.setValue(v_scrollbar.maximum())
                    text_edit._v_scroll_locked = False
                else:
                    # 保持原位置
                    v_scrollbar.setValue(vscroll)
                
                # 水平滚动条：永远锁定，使用保存的位置
                h_scrollbar.setValue(hscroll)
            finally:
                v_scrollbar.blockSignals(False)
                h_scrollbar.blockSignals(False)
            
            # 更新已显示长度
            self.last_display_lengths[channel] = current_length
            
            # 更新时间戳
            self.last_tab_update_times[channel] = time.time()
            
            logger.info(f"✅ TAB[{channel}]强制刷新完成: 补充了 {len(missing_data)} 字节数据")
            
        except Exception as e:
            logger.error(f"Failed to force refresh tab {channel}: {e}", exc_info=True)
    
    def _update_from_worker(self):
        """从Worker缓冲区更新UI - 使用ANSI文本显示，智能滚动条控制"""
        try:
            if not self.device_session.connection_dialog:
                logger.info(f"[UPDATE] No connection_dialog for session {self.device_session.session_id}")
                return
            
            worker = getattr(self.device_session.connection_dialog, 'worker', None)
            if not worker:
                logger.info(f"[UPDATE] No worker for session {self.device_session.session_id}")
                return
            
            # 检查是否有任何新数据
            has_new_data = False
            for ch in range(MAX_TAB_SIZE):
                if worker.colored_buffer_lengths[ch] > self.last_display_lengths[ch]:
                    has_new_data = True
                    break
            
            # if has_new_data:
            #     logger.info(f"[UPDATE] Found new data for session {self.device_session.session_id}")
            
            # 获取当前激活的TAB索引
            current_tab = self.tab_widget.currentIndex()
            current_time = time.time()
            
            # 遍历所有通道，检查是否有新数据
            for channel in range(MAX_TAB_SIZE):
                # 获取彩色缓冲区的当前长度
                current_length = worker.colored_buffer_lengths[channel]
                last_length = self.last_display_lengths[channel]
                
                # 🔧 修复：对于非激活TAB，降低更新频率（1秒一次）
                is_active_tab = (channel == current_tab)
                if not is_active_tab:
                    # 检查是否需要更新（距离上次更新超过1秒）
                    time_since_last_update = current_time - self.last_tab_update_times[channel]
                    if time_since_last_update < self.inactive_tab_update_interval:
                        # 跳过本次更新，但继续检查缓冲区裁剪（这是关键问题，必须立即处理）
                        if current_length < last_length:
                            trimmed_length = last_length - current_length
                            logger.warning(f"🔧 [CH{channel}] Inactive TAB buffer trimmed: last_display={last_length}, current={current_length}, trimmed={trimmed_length} bytes, resetting to 0")
                            self.last_display_lengths[channel] = 0
                            last_length = 0
                        
                        # 🔧 修复：非激活TAB的数据丢失检测也应该有频率限制（5秒一次）
                        time_since_last_gap_check = current_time - self.last_inactive_gap_check_times[channel]
                        if time_since_last_gap_check >= self.inactive_gap_check_interval:
                            # 只有超过5秒才检查数据丢失
                            if current_length > last_length + 1024:
                                logger.warning(f"🔧 [CH{channel}] Inactive TAB data gap detected: gap={current_length - last_length}, forcing refresh")
                                self._force_refresh_tab(channel)
                            # 更新数据丢失检测时间戳
                            self.last_inactive_gap_check_times[channel] = current_time
                        continue
                    # 更新非激活TAB的时间戳
                    self.last_tab_update_times[channel] = current_time
                    # 正常更新时也重置数据丢失检测时间戳
                    self.last_inactive_gap_check_times[channel] = current_time
                
                # 🔧 修复：如果current < last，说明缓冲区被裁剪了，需要调整last_display_lengths
                if current_length < last_length:
                    # 计算被裁剪的长度
                    trimmed_length = last_length - current_length
                    logger.warning(f"🔧 [CH{channel}] Buffer trimmed detected: last_display={last_length}, current={current_length}, trimmed={trimmed_length} bytes, resetting to 0")
                    self.last_display_lengths[channel] = 0
                    last_length = 0
                
                # 🔧 修复：如果数据丢失超过阈值，强制刷新（激活和非激活TAB都需要）
                if current_length > last_length + 1024:
                    tab_type = "Current" if is_active_tab else "Inactive"
                    logger.warning(f"🔧 [CH{channel}] {tab_type} TAB data gap detected: gap={current_length - last_length}, forcing refresh")
                    self._force_refresh_tab(channel)
                    continue
                
                if current_length > last_length:
                    # 有新数据，提取增量部分
                    colored_data = ''.join(worker.colored_buffers[channel])
                    new_data = colored_data[last_length:]
                    
                    if new_data and channel < len(self.text_edits):
                        text_edit = self.text_edits[channel]
                        
                        # 获取滚动条
                        v_scrollbar = text_edit.verticalScrollBar()
                        h_scrollbar = text_edit.horizontalScrollBar()
                        
                        # 完全按照旧代码switchPage的方式（8284-8285行）：
                        # 在添加数据前保存当前滚动条位置
                        vscroll = v_scrollbar.value()
                        hscroll = h_scrollbar.value()
                        
                        # 使用同步方式插入ANSI文本（参考旧代码的_insert_ansi_text_fast方法）
                        # 不使用FastAnsiTextEdit的批处理机制，确保滚动条恢复时机正确
                        if hasattr(text_edit, '_parse_ansi_fast'):
                            # 使用FastAnsiTextEdit的解析方法，但同步插入
                            segments = text_edit._parse_ansi_fast(new_data)
                            cursor = text_edit.textCursor()
                            cursor.movePosition(QTextCursor.End)
                            for segment in segments:
                                if segment['text']:
                                    cursor.insertText(segment['text'], segment['format'])
                            text_edit.setTextCursor(cursor)
                        else:
                            # 降级处理：使用普通追加
                            cursor = text_edit.textCursor()
                            cursor.movePosition(QTextCursor.End)
                            text_edit.setTextCursor(cursor)
                            text_edit.insertPlainText(new_data)
                        
                        # 完全按照旧代码switchPage方法的逻辑（8507-8511行）：
                        # 关键：阻塞信号，避免setValue触发_on_vertical_scroll_changed改变锁定状态
                        # 只有用户手动拖动滚动条时才应该改变锁定状态
                        v_scrollbar.blockSignals(True)
                        h_scrollbar.blockSignals(True)
                        
                        try:
                            # 垂直滚动条：根据锁定状态决定是否恢复位置
                            if text_edit._v_scroll_locked:
                                # 锁定状态：恢复到保存的位置
                                v_scrollbar.setValue(vscroll)
                                # logger.info(f"🔒 Channel {channel} V-scroll LOCKED: set {vscroll}, actual={v_scrollbar.value()}, max={v_scrollbar.maximum()}")
                            else:
                                # 未锁定状态：滚动到底部
                                v_scrollbar.setValue(v_scrollbar.maximum())
                                # logger.info(f"🔓 Channel {channel} V-scroll UNLOCKED: set {v_scrollbar.maximum()}, actual={v_scrollbar.value()}")
                                
                                # 关键：确保解锁状态不被意外改变
                                # 因为设置完后可能还有新数据到来，导致maximum变化
                                # 所以需要确保_v_scroll_locked保持为False
                                text_edit._v_scroll_locked = False
                            
                            # 水平滚动条：永远锁定，使用保存的位置
                            h_scrollbar.setValue(hscroll)
                            # logger.debug(f"↔️ Channel {channel} H-scroll: set {hscroll}, actual={h_scrollbar.value()}, max={h_scrollbar.maximum()}")
                        finally:
                            # 恢复信号
                            v_scrollbar.blockSignals(False)
                            h_scrollbar.blockSignals(False)
                        
                        # 更新已显示长度
                        self.last_display_lengths[channel] = current_length
                        
                        # 更新TAB的时间戳（激活和非激活TAB都更新）
                        self.last_tab_update_times[channel] = current_time
        except Exception as e:
            logger.error(f"Failed to update from worker: {e}", exc_info=True)
    
    def update_filter_tab_display(self):
        """更新筛选TAB的显示
        规则：
        - 如果筛选TAB有内容，显示该内容
        - 动态显示空"+"TAB：
          * 如果所有可见的筛选TAB都有内容，显示一个新的"+"（未超上限）
          * 如果有空"+"TAB，只显示一个
        """
        try:
            # 统计有内容的筛选TAB和空TAB
            tabs_with_content = []
            empty_tabs = []
            
            logger.info("=" * 60)
            logger.info("🔍 开始更新筛选TAB显示")
            
            # 获取配置对象
            config = None
            if self.device_session and self.device_session.connection_dialog:
                config = self.device_session.connection_dialog.config
            
            for i in range(17, MAX_TAB_SIZE):
                tab_text = self.tab_widget.tabText(i)
                is_visible = self.tab_widget.isTabVisible(i)
                
                # 判断是否有内容：优先检查配置，其次检查TAB文本
                has_content = False
                if config:
                    filter_content = config.get_filter(i)
                    has_content = filter_content and filter_content.strip() and filter_content != "+"
                
                # 如果配置中没有内容，再检查TAB文本
                if not has_content:
                    has_content = tab_text and tab_text != "+" and tab_text.strip()
                
                # logger.info(f"  TAB[{i}]: text='{tab_text}', visible={is_visible}, has_content={has_content}")
                
                if has_content:
                    tabs_with_content.append(i)
                else:
                    empty_tabs.append(i)
            
            logger.info(f"📊 统计: {len(tabs_with_content)}个有内容, {len(empty_tabs)}个空TAB")
            logger.info(f"  有内容的TAB: {tabs_with_content}")
            logger.info(f"  空TAB: {empty_tabs}")
            
            # 先将所有有内容的TAB设为可见,并更新tooltip
            for i in tabs_with_content:
                self.tab_widget.setTabVisible(i, True)
                # 更新tooltip显示完整内容
                tab_text = self.tab_widget.tabText(i)
                self.tab_widget.setTabToolTip(i, tab_text)
                logger.info(f"  ✓ 设置TAB[{i}]可见（有内容）")
            
            # 决定需要显示多少个空"+"TAB
            # 规则：始终只显示一个空"+"TAB
            empty_tab_to_show_count = 1 if empty_tabs else 0
            logger.info(f"📌 需要显示 {empty_tab_to_show_count} 个空'+'TAB")
            
            # 应用空TAB的显示规则
            shown_empty_count = 0
            for i in empty_tabs:
                if shown_empty_count < empty_tab_to_show_count:
                    # 显示这个空TAB
                    self.tab_widget.setTabText(i, "+")
                    # 设置tooltip提示双击编辑
                    from PySide6.QtCore import QCoreApplication
                    self.tab_widget.setTabToolTip(i, QCoreApplication.translate("main_window", "Double-click to edit filter"))
                    self.tab_widget.setTabVisible(i, True)
                    shown_empty_count += 1
                    # logger.info(f"  ✓ 设置TAB[{i}]可见（空'+'）")
                else:
                    # 隐藏这个空TAB
                    self.tab_widget.setTabVisible(i, False)
                    # logger.info(f"  ✗ 隐藏TAB[{i}]")
            
            logger.info(f"✅ 筛选TAB更新完成: {len(tabs_with_content)}个有内容, {shown_empty_count}个空'+'可见")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Failed to update filter tab display: {e}", exc_info=True)
    
    def closeEvent(self, event):
        """窗口关闭事件 - 断开设备并注销对象"""
        logger.info(f"DeviceMdiWindow closing for session: {self.device_session.session_id}")
        
        # 停止更新定时器
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        # 断开设备连接
        try:
            if self.device_session.is_connected:
                logger.info(f"Disconnecting device: {self.device_session.device_serial}")
                self.device_session.disconnect()
        except Exception as e:
            logger.error(f"Failed to disconnect device: {e}", exc_info=True)
        
        # 通知主窗口关闭此设备会话并注销对象
        # DeviceMdiWindow是QWidget，通过mdi_sub_window获取QMdiArea
        if hasattr(self, 'mdi_sub_window') and self.mdi_sub_window:
            mdi_area = self.mdi_sub_window.mdiArea()
            if mdi_area:
                main_window = mdi_area.parent()
                while main_window and not isinstance(main_window, RTTMainWindow):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, '_on_mdi_window_closed'):
                    main_window._on_mdi_window_closed(self.device_session)
        
        event.accept()


class RTTMainWindow(QMainWindow):
    def __init__(self):
        super(RTTMainWindow, self).__init__()
        
        # 保存当前进程PID,用于进程冲突检测
        import os
        self.main_process_pid = os.getpid()
        
        # 主窗口标识（用于日志文件夹等）
        self.window_id = "main"
        
        # 设备会话管理
        self.device_sessions = []  # 所有设备会话列表
        self.current_session = None  # 当前激活的设备会话
        
        self.connection_dialog = None
        self._is_closing = False  # 标记主窗口是否正在关闭
        self._filters_loaded = False  # 🔑 标记filter是否已加载到UI
        self._ui_initialization_complete = False  # 🔑 标记UI初始化是否完成
        
        # 🔑 当前字体和字号的临时变量（用于检测变化并触发全局刷新）
        self._current_font_name = None  # 当前应用的字体名称
        self._current_font_size = None  # 当前应用的字号
        
        # 获取DPI缩放比例（支持手动设置或自动检测）
        manual_dpi = config_manager.get_dpi_scale()
        self.dpi_scale = get_dpi_scale_factor(manual_dpi)
        logger.info(f"Current DPI scale: {self.dpi_scale:.2f}")
        
        # 设置主窗口属性
        self.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT - RTT Debug Main Window"))
        self.setWindowIcon(QIcon(":/xexunrtt.ico"))
        
        # 根据DPI调整窗口大小
        base_width, base_height = WindowSize.MAIN_WINDOW_BASE_WIDTH, WindowSize.MAIN_WINDOW_BASE_HEIGHT
        adaptive_width, adaptive_height = get_adaptive_window_size(base_width, base_height, self.dpi_scale)
        self.resize(adaptive_width, adaptive_height)
        logger.info(f"Window size adjusted to: {adaptive_width}x{adaptive_height}")
        
        # 设置最小窗口尺寸 - 允许极小窗口以便多设备同时使用
        min_width = WindowSize.MAIN_WINDOW_MIN_WIDTH
        min_height = WindowSize.MAIN_WINDOW_MIN_HEIGHT
        self.setMinimumSize(min_width, min_height)
        logger.info(f"Minimum window size set to: {min_width}x{min_height}")
        
        # 紧凑模式状态
        self.compact_mode = False
        
        # 添加右键菜单支持紧凑模式
        #self.setContextMenuPolicy(Qt.CustomContextMenu)
        #self.customContextMenuRequested.connect(self._show_context_menu)
        
        # 设置 UI（xexunrtt.ui 现在是 QMainWindow 类型）
        self.ui = Ui_RTTMainWindow()
        self.ui.setupUi(self)
        
        # 从 UI 文件获取已创建的部件
        # UI 文件中已经包含了 mdi_area, main_splitter, button_command_area, jlink_log_area 等
        # 我们需要获取这些引用并进行额外配置
        
        # 从 UI 文件获取已创建的部件引用
        self.main_splitter = self.ui.main_splitter
        self.mdi_area = self.ui.mdi_area
        
        # 配置 MDI 区域
        from PySide6.QtGui import QBrush, QColor
        self.mdi_area.setViewMode(QMdiArea.ViewMode.SubWindowView)
        self.mdi_area.setActivationOrder(QMdiArea.WindowOrder.ActivationHistoryOrder)
        self.mdi_area.setBackground(QBrush(QColor(53, 53, 53)))
        
        # 禁用自动调整子窗口大小选项，允许手动调整
        self.mdi_area.setOption(QMdiArea.AreaOption.DontMaximizeSubWindowOnActivation, True)
        
        # 连接 MDI 子窗口激活信号，用于同步暂停/恢复状态等
        self.mdi_area.subWindowActivated.connect(self._on_mdi_subwindow_activated)
        
        # 设置 MDI 区域样式
        # 只设置背景色,不覆盖子窗口的原生样式
        self.mdi_area.setStyleSheet("""
            QMdiArea {
                background-color: #353535;
            }
        """)
        
        
        # 配置分割器样式和行为
        self.main_splitter.setHandleWidth(3)  # 设置分割线宽度为 3 像素
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #555555;
                height: 3px;
            }
            QSplitter::handle:hover {
                background-color: #777777;
            }
            QSplitter::handle:pressed {
                background-color: #999999;
            }
        """)
        
        # 设置可折叠性
        self.main_splitter.setCollapsible(0, False)  # MDI区域不可折叠
        self.main_splitter.setCollapsible(1, True)   # 底部容器可折叠（允许完全隐藏）
        
        # 监听分割器大小变化，自动隐藏/显示JLink日志区
        self.main_splitter.splitterMoved.connect(self._on_splitter_moved)
        
        # 设置按钮区固定高度
        if hasattr(self.ui, 'button_command_area'):
            self.ui.button_command_area.setFixedHeight(LayoutSize.BUTTON_AREA_HEIGHT)
        
        # 配置JLink日志区域（UI文件中已创建）
        if hasattr(self.ui, 'jlink_log_area'):
            self.jlink_log_widget = self.ui.jlink_log_area
            self.jlink_log_text = self.ui.jlink_log_text
            
            # 设置高度限制
            self.jlink_log_min_height = LayoutSize.JLINK_LOG_MIN_HEIGHT
            self.jlink_log_max_height = LayoutSize.JLINK_LOG_MAX_HEIGHT
            self.jlink_log_widget.setMinimumHeight(0)  # 允许完全隐藏
            self.jlink_log_widget.setMaximumHeight(self.jlink_log_max_height)
        
        # 限制底部容器的最大高度（按钮区 + JLink日志区）
        if hasattr(self.ui, 'bottom_container'):
            max_bottom_height = LayoutSize.BUTTON_AREA_HEIGHT + self.jlink_log_max_height
            self.ui.bottom_container.setMaximumHeight(max_bottom_height)
            logger.debug(f"Bottom container max height set to {max_bottom_height}px")
            
            # 连接UI文件中的按钮信号
            if hasattr(self.ui, 'clear_jlink_log_btn'):
                self.clear_jlink_log_btn = self.ui.clear_jlink_log_btn
                self.clear_jlink_log_btn.clicked.connect(self.clear_jlink_log)
            
            if hasattr(self.ui, 'toggle_jlink_log_btn'):
                self.toggle_jlink_log_btn = self.ui.toggle_jlink_log_btn
                self.toggle_jlink_log_btn.clicked.connect(self.toggle_jlink_verbose_log)
            
            # 初始化JLink日志捕获
            self.jlink_verbose_logging = False
            self._setup_jlink_logging()
            
            # 设置初始样式
            QTimer.singleShot(0, self._update_jlink_log_style)
        
        # 初始化JLink日志区的初始大小（延迟设置，等待窗口显示后）
        QTimer.singleShot(TimerInterval.DELAYED_INIT, self._init_splitter_sizes)
        
        # 创建菜单栏和状态栏（UI文件已创建menubar和statusbar，先清空菜单栏再创建自定义菜单以避免重复）
        # 清空现有菜单栏
        self.menuBar().clear()
        # 创建自定义菜单
        self._create_menu_bar()
        self._create_status_bar()
        
        # 隐藏并从布局中移除 tem_switch（MDI 架构中不再使用）
        if hasattr(self.ui, 'tem_switch'):
            self.ui.tem_switch.setVisible(False)
            self.ui.tem_switch.setParent(None)
        
        # 初始化时禁用RTT相关功能，直到连接成功
        self._set_rtt_controls_enabled(False)
        
        # 不再创建原有的UI，改为动态创建设备窗口
        # self.ui = Ui_xexun_rtt()
        # self.ui.setupUi(self.central_widget)
        
        # 自动重连相关变量
        self.manual_disconnect = False  # 是否为手动断开
        self.last_data_time = 0  # 上次收到数据的时间戳
        self.data_check_timer = QTimer(self)  # 数据检查定时器
        self.data_check_timer.timeout.connect(self._check_data_timeout)
        
        # 立即创建连接对话框以便加载配置
        self.connection_dialog = ConnectionDialog(self)
        self._main_connection_dialog = self.connection_dialog  # 保存主连接对话框引用
        # 连接成功信号
        self.connection_dialog.connection_established.connect(self.on_connection_established)
        
        # 从配置恢复格式化RAM设置（在 connection_dialog 创建后）
        try:
            format_ram_enabled = self.connection_dialog.config.get_format_ram_on_restart()
            self.action_format_ram.setChecked(format_ram_enabled)
        except Exception as e:
            logger.debug(f"Failed to load format_ram config: {e}")
        
        # 命令历史导航
        self.command_history_index = -1  # 当前历史命令索引，-1表示未选择历史命令
        self.current_input_text = ""     # 保存当前输入的文本
        # 连接断开信号
        self.connection_dialog.connection_disconnected.connect(self.on_connection_disconnected)
        
        # 在connection_dialog初始化后加载命令历史
        self.populateComboBox()
        
        # 串口转发设置已移动到连接对话框中
        
        # QMainWindow默认就有最大化按钮，不需要额外设置
        # 向 tabWidget 中添加页面并连接信号

        # 创建动作并设置快捷键
        self.action1 = QAction(self)
        self.action1.setShortcut(QKeySequence("F1"))

        self.action2 = QAction(self)
        self.action2.setShortcut(QKeySequence("F2"))

        self.action3 = QAction(self)
        self.action3.setShortcut(QKeySequence("F3"))

        self.action4 = QAction(self)
        self.action4.setShortcut(QKeySequence("F4"))

        # F5和F6快捷键已移除（滚动条锁定改为智能自动控制）
        # self.action5 = QAction(self)
        # self.action5.setShortcut(QKeySequence("F5"))
        # 
        # self.action6 = QAction(self)
        # self.action6.setShortcut(QKeySequence("F6"))

        self.action7 = QAction(self)
        self.action7.setShortcut(QKeySequence("F7"))
        


                
        self.action9 = QAction(self)
        self.action9.setShortcut(QKeySequence("F9"))
                
        # 添加CTRL+F查找功能
        self.find_action = QAction(self)
        self.find_action.setShortcut(QKeySequence("Ctrl+F"))
        self.find_action.triggered.connect(self.show_find_dialog)
        
        # 添加强制退出快捷键
        self.force_quit_action = QAction(self)
        self.force_quit_action.setShortcut(QKeySequence("Ctrl+Alt+Q"))
        self.force_quit_action.triggered.connect(self._force_quit)
                
        #self.actionenter = QAction(self)
        #self.actionenter.setShortcut(QKeySequence(Qt.Key_Return, Qt.Key_Enter))

        # 将动作添加到主窗口
        self.addAction(self.action1)
        self.addAction(self.action2)
        self.addAction(self.action3)
        self.addAction(self.action4)
        # self.addAction(self.action5)  # F5已移除
        # self.addAction(self.action6)  # F6已移除
        self.addAction(self.action7)

        self.addAction(self.action9)
        self.addAction(self.find_action)
        self.addAction(self.force_quit_action)
        #self.addAction(self.actionenter)

        # 连接动作的触发事件
        self.action1.triggered.connect(self.on_openfolder_clicked)
        self.action2.triggered.connect(self.on_re_connect_clicked)
        self.action3.triggered.connect(self.on_dis_connect_clicked)
        self.action4.triggered.connect(self.on_clear_clicked)
        # self.action5.triggered.connect(self.toggle_lock_v_checkbox)  # F5已移除，现在用于暂停/恢复刷新
        # self.action6.triggered.connect(self.toggle_lock_h_checkbox)  # F6已移除
        self.action7.triggered.connect(self.toggle_style_checkbox)
        
        # F5/F6 暂停/恢复刷新（通过UI单选按钮控制，这里只添加快捷键）
        self.pause_refresh_action = QAction(QCoreApplication.translate("main_window", "Pause Refresh"), self)
        self.pause_refresh_action.setShortcut(QKeySequence("F5"))
        self.pause_refresh_action.triggered.connect(self.pause_ui_refresh)
        self.addAction(self.pause_refresh_action)
        
        self.resume_refresh_action = QAction(QCoreApplication.translate("main_window", "Resume Refresh"), self)
        self.resume_refresh_action.setShortcut(QKeySequence("F6"))
        self.resume_refresh_action.triggered.connect(self.resume_ui_refresh)
        self.addAction(self.resume_refresh_action)

        # 重定向 F9 到统一的执行逻辑（根据子菜单选择）
        self.action9.triggered.connect(self.restart_app_execute)
        #self.actionenter.triggered.connect(self.on_pushButton_clicked)

        # ========== 旧代码已删除：tem_switch 初始化 ==========
        # MDI 架构中，每个设备都有自己的 DeviceMdiWindow，不再需要主窗口的 tem_switch
        # tabText 和 highlighter 也移到了 DeviceMdiWindow 中
        # ====================================================
        self.ui.pushButton.clicked.connect(self.on_pushButton_clicked)
        self.ui.dis_connect.clicked.connect(self.on_dis_connect_clicked)
        self.ui.re_connect.clicked.connect(self.on_re_connect_clicked)
        self.ui.clear.clicked.connect(self.on_clear_clicked)
        
        # 连接暂停/恢复刷新单选按钮
        if hasattr(self.ui, 'radioButton_pause_refresh'):
            self.ui.radioButton_pause_refresh.toggled.connect(lambda checked: self.pause_ui_refresh() if checked else None)
        if hasattr(self.ui, 'radioButton_resume_refresh'):
            self.ui.radioButton_resume_refresh.toggled.connect(lambda checked: self.resume_ui_refresh() if checked else None)

        # JLink 文件日志跟随显示
        self.jlink_log_file_path = None
        self.jlink_log_tail_timer = None
        self.jlink_log_tail_offset = 0
        self.ui.openfolder.clicked.connect(self.on_openfolder_clicked)
        
        # 初始化编码下拉框（ui_xexunrtt.py中已有 encoder 组合框）
        if hasattr(self.ui, 'encoder'):
            self._init_encoding_combo()
            self.ui.encoder.currentTextChanged.connect(self._on_encoding_changed)
        self.ui.cmd_buffer.activated.connect(self.on_pushButton_clicked)
        
        # 为ComboBox安装事件过滤器以支持上下方向键导航命令历史
        self.ui.cmd_buffer.installEventFilter(self)

        # 设置默认样式
        palette = QPalette()
        palette.ID = 'light'
        self.light_stylesheet = qdarkstyle._load_stylesheet(qt_api='pyside6', palette=palette)
        self.dark_stylesheet = qdarkstyle.load_stylesheet_pyside6()
        
        self.ui.light_checkbox.stateChanged.connect(self.set_style)
        
        # 初始化字体选择ComboBox
        if hasattr(self.ui, 'font_combo'):
            self._init_font_combo()
            self.ui.font_combo.currentTextChanged.connect(self.on_font_changed)
        
        self.ui.fontsize_box.valueChanged.connect(self.on_fontsize_changed)
        
        
        # 连接自动重连控件的信号
        if hasattr(self.ui, 'auto_reconnect_checkbox'):
            self.ui.auto_reconnect_checkbox.stateChanged.connect(self._on_auto_reconnect_changed)
            # 从配置加载自动重连设置
            auto_reconnect_enabled = self.connection_dialog.config.get_auto_reconnect_on_no_data()
            self.ui.auto_reconnect_checkbox.setChecked(auto_reconnect_enabled)
        
        if hasattr(self.ui, 'reconnect_timeout_edit'):
            self.ui.reconnect_timeout_edit.textChanged.connect(self._on_reconnect_timeout_changed)
            # 从配置加载超时设置
            timeout = self.connection_dialog.config.get_auto_reconnect_timeout()
            self.ui.reconnect_timeout_edit.setText(str(timeout))
        
        # 连接重启APP按钮
        if hasattr(self.ui, 'restart_app_button'):
            self.ui.restart_app_button.clicked.connect(self.restart_app_execute)
        
        # 隐藏新建窗口按钮（已被设备TAB栏的"+"按钮替代）
        if hasattr(self.ui, 'new_window_button'):
            self.ui.new_window_button.hide()
        
        # 隐藏紧缩模式复选框（功能已废弃）
        if hasattr(self.ui, 'compact_mode_checkbox'):
            self.ui.compact_mode_checkbox.hide()
        
        # 隐藏水平和垂直滚动条锁定复选框（改为智能自动锁定）
        if hasattr(self.ui, 'LockH_checkBox'):
            self.ui.LockH_checkBox.hide()
        if hasattr(self.ui, 'LockV_checkBox'):
            self.ui.LockV_checkBox.hide()
        
        # 连接紧缩模式复选框 (F11) - 已屏蔽
        # if hasattr(self.ui, 'compact_mode_checkbox'):
        #     self.ui.compact_mode_checkbox.stateChanged.connect(self._on_compact_mode_checkbox_changed)
        #     # 创建F11快捷键
        #     self.action11 = QAction(self)
        #     self.action11.setShortcut(QKeySequence("F11"))
        #     self.action11.triggered.connect(self._toggle_compact_mode_via_f11)
        #     self.addAction(self.action11)
        #     # 同步初始状态
        #     self.ui.compact_mode_checkbox.setChecked(self.compact_mode)
        
        # 创建F8快捷键用于切换自动重连
        self.action8 = QAction(self)
        self.action8.setShortcut(QKeySequence("F8"))
        self.action8.triggered.connect(self._toggle_auto_reconnect)
        self.addAction(self.action8)
        
        self.set_style()
        
        # 创建定时器并连接到槽函数
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_periodic_task)
        self.timer.start(TimerInterval.STATUS_UPDATE)
        
        # 数据更新标志，用于智能刷新
        self.page_dirty_flags = [False] * MAX_TAB_SIZE
        
        # 立即加载并应用保存的配置
        self._apply_saved_settings()
        
        # 🔄 自动更新检查（延迟5秒，不影响启动速度）
        if UPDATE_AVAILABLE:
            check_for_updates_on_startup(self)
            logger.info("Auto update check scheduled")
        else:
            logger.warning("Auto update module not available")
    
    # 串口转发功能已移动到连接对话框中
    
    # 串口转发相关方法已移动到连接对话框中
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 连接菜单
        self.connection_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Connection(&C)"))
        
        # 重新连接动作
        reconnect_action = QAction(QCoreApplication.translate("main_window", "Reconnect(&R)"), self)
        reconnect_action.triggered.connect(self.on_re_connect_clicked)
        self.connection_menu.addAction(reconnect_action)
        
        # 断开连接动作
        disconnect_action = QAction(QCoreApplication.translate("main_window", "Disconnect(&D)"), self)
        disconnect_action.triggered.connect(self.on_dis_connect_clicked)
        self.connection_menu.addAction(disconnect_action)
        
        # self.connection_menu.addSeparator()
        
        # # 连接设置动作
        # settings_action = QAction(QCoreApplication.translate("main_window", "Connection Settings(&S)..."), self)
        # settings_action.triggered.connect(self._show_connection_settings)
        # self.connection_menu.addAction(settings_action)
        
        # 窗口菜单
        self.window_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Window(&W)"))
        
        # 水平分割窗口
        split_horizontal_action = QAction(QCoreApplication.translate("main_window", "Split Horizontal"), self)
        split_horizontal_action.triggered.connect(lambda: self._split_layout('horizontal'))
        self.window_menu.addAction(split_horizontal_action)
        
        # 垂直分割窗口
        split_vertical_action = QAction(QCoreApplication.translate("main_window", "Split Vertical"), self)
        split_vertical_action.triggered.connect(lambda: self._split_layout('vertical'))
        self.window_menu.addAction(split_vertical_action)
        
        self.window_menu.addSeparator()
        
        # 紧凑模式切换动作
        # 紧缩模式 - 已屏蔽
        # self.compact_mode_action = QAction(QCoreApplication.translate("main_window", "Compact Mode(&M)"), self)
        # self.compact_mode_action.setCheckable(True)
        # self.compact_mode_action.setChecked(False)
        # self.compact_mode_action.setShortcut(QKeySequence("Ctrl+M"))
        # self.compact_mode_action.setStatusTip(QCoreApplication.translate("main_window", "Toggle compact mode for multi-device usage"))
        # self.compact_mode_action.triggered.connect(self._toggle_compact_mode)
        # self.window_menu.addAction(self.compact_mode_action)
        # 
        # self.window_menu.addSeparator()
        
        # MDI窗口列表将在这里动态添加
        # 连接窗口菜单的aboutToShow信号以动态更新窗口列表
        self.window_menu.aboutToShow.connect(self._update_window_menu)
        
        # 工具菜单
        self.tools_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Tools(&T)"))
        
        # 清除日志动作
        clear_action = QAction(QCoreApplication.translate("main_window", "Clear Current Page(&C)"), self)
        clear_action.triggered.connect(self.on_clear_clicked)
        self.tools_menu.addAction(clear_action)
        
        # 打开日志文件夹动作
        open_folder_action = QAction(QCoreApplication.translate("main_window", "Open Log Folder(&O)"), self)
        open_folder_action.triggered.connect(self.on_openfolder_clicked)
        self.tools_menu.addAction(open_folder_action)
        
        # 打开配置文件夹动作
        open_config_folder_action = QAction(QCoreApplication.translate("main_window", "Open Config Folder(&F)"), self)
        open_config_folder_action.triggered.connect(self.on_open_config_folder_clicked)
        self.tools_menu.addAction(open_config_folder_action)
        
        self.tools_menu.addSeparator()
        
        # RTT Chain Info 动作
        self.rtt_info_action = QAction(QCoreApplication.translate("main_window", "RTT Chain Info(&I)"), self)
        self.rtt_info_action.triggered.connect(self.show_rtt_chain_info)
        self.rtt_info_action.setEnabled(False)  # 默认禁用，连接后启用
        self.tools_menu.addAction(self.rtt_info_action)
        
        self.tools_menu.addSeparator()
        
        # 编码设置子菜单（仅在断开时可切换）
        self.encoding_menu = self.tools_menu.addMenu(QCoreApplication.translate("main_window", "Encoding(&E)"))
        self._build_encoding_submenu()
        
        # 重启 APP 子菜单（选择方式），执行通过F9
        restart_menu = self.tools_menu.addMenu(QCoreApplication.translate("main_window", "Restart APP F9(&A)"))
        self.action_restart_sfr = QAction(QCoreApplication.translate("main_window", "via SFR access"), self)
        self.action_restart_pin = QAction(QCoreApplication.translate("main_window", "via reset pin"), self)
        self.action_restart_sfr.setCheckable(True)
        self.action_restart_pin.setCheckable(True)
        self.restart_group = QActionGroup(self)
        self.restart_group.setExclusive(True)
        self.restart_group.addAction(self.action_restart_sfr)
        self.restart_group.addAction(self.action_restart_pin)
        # 从配置恢复默认方式
        try:
            default_method = self.connection_dialog.config.get_restart_method() if self.connection_dialog else 'SFR'
        except Exception:
            default_method = 'SFR'
        self.action_restart_sfr.setChecked(default_method == 'SFR')
        self.action_restart_pin.setChecked(default_method == 'RESET_PIN')
        restart_menu.addAction(self.action_restart_sfr)
        restart_menu.addAction(self.action_restart_pin)
        
        # 添加分隔符
        restart_menu.addSeparator()
        
        # 格式化RAM选项
        self.action_format_ram = QAction(QCoreApplication.translate("main_window", "Format RAM before restart"), self)
        self.action_format_ram.setCheckable(True)
        # 注意：初始状态将在 connection_dialog 创建后设置
        self.action_format_ram.setChecked(False)  # 默认不勾选
        # 连接信号保存配置
        self.action_format_ram.toggled.connect(self._on_format_ram_toggled)
        restart_menu.addAction(self.action_format_ram)
        
        # F9 触发执行由全局 action9 负责（避免重复快捷键冲突）
        
        # 样式切换动作
        style_action = QAction(QCoreApplication.translate("main_window", "Switch Theme(&T)"), self)
        style_action.triggered.connect(self.toggle_style_checkbox)
        self.tools_menu.addAction(style_action)
        
        # tools_menu.addSeparator()
        
        # 性能测试动作
        # perf_test_action = QAction(QCoreApplication.translate("main_window", "性能测试(&P)..."), self)
        # perf_test_action.triggered.connect(self.show_performance_test)
        # tools_menu.addAction(perf_test_action)
        
        # 注释掉Turbo模式菜单（功能保留，界面隐藏）
        # tools_menu.addSeparator()
        # 
        # # 🚀 Turbo模式切换
        # self.turbo_mode_action = QAction(QCoreApplication.translate("main_window", "🚀 Turbo模式(&T)"), self)
        # self.turbo_mode_action.setCheckable(True)
        # self.turbo_mode_action.setChecked(True)  # 默认启用
        # self.turbo_mode_action.triggered.connect(self.toggle_turbo_mode)
        # tools_menu.addAction(self.turbo_mode_action)
        
        # Language 菜单（固定不翻译）
        self.language_menu = menubar.addMenu("Language(&L)")
        
        # 创建语言动作组（用于单选）
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)
        
        # 当前语言设置（使用全局 config_manager）
        current_language = config_manager.get_language()
        
        # English
        self.action_en = QAction("English", self)
        self.action_en.setCheckable(True)
        self.action_en.setData("en_US")
        if current_language == "en_US":
            self.action_en.setChecked(True)
        self.action_en.triggered.connect(lambda: self._change_language("en_US"))
        self.language_action_group.addAction(self.action_en)
        self.language_menu.addAction(self.action_en)
        
        # 中文（简体）
        self.action_zh_cn = QAction("中文（简体）", self)
        self.action_zh_cn.setCheckable(True)
        self.action_zh_cn.setData("zh_CN")
        if current_language == "zh_CN":
            self.action_zh_cn.setChecked(True)
        self.action_zh_cn.triggered.connect(lambda: self._change_language("zh_CN"))
        self.language_action_group.addAction(self.action_zh_cn)
        self.language_menu.addAction(self.action_zh_cn)
        
        # 中文（繁体）
        self.action_zh_tw = QAction("中文（繁體）", self)
        self.action_zh_tw.setCheckable(True)
        self.action_zh_tw.setData("zh_TW")
        if current_language == "zh_TW":
            self.action_zh_tw.setChecked(True)
        self.action_zh_tw.triggered.connect(lambda: self._change_language("zh_TW"))
        self.language_action_group.addAction(self.action_zh_tw)
        self.language_menu.addAction(self.action_zh_tw)
        
        # 帮助菜单
        self.help_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Help(&H)"))
        
        # 关于动作
        about_action = QAction(QCoreApplication.translate("main_window", "About(&A)..."), self)
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action)
        
        # ========== 在菜单栏右侧添加设备TAB栏 ========== (已完全屏蔽)
        # self._create_device_tab_bar(menubar)
    
    def _create_device_tab_bar(self, menubar):
        """在菜单栏右侧创建设备TAB栏 - 已完全屏蔽"""
        pass
        # # 创建一个容器widget来放置TAB栏，设置主窗口为父对象
        # self.device_tab_container = QWidget(self)
        # device_tab_layout = QHBoxLayout(self.device_tab_container)
        # device_tab_layout.setContentsMargins(5, 0, 5, 0)
        # device_tab_layout.setSpacing(5)
        # 
        # # 创建设备TAB栏，设置容器为父对象
        # self.device_tab_bar = QTabBar(self.device_tab_container)
        # self.device_tab_bar.setTabsClosable(True)  # 允许关闭TAB
        # self.device_tab_bar.setMovable(True)  # 允许拖动TAB
        # self.device_tab_bar.setExpanding(False)  # 不自动扩展
        # self.device_tab_bar.setDrawBase(False)  # 不绘制底部线条
        # 
        # # 设置TAB栏的大小策略为最小化
        # self.device_tab_bar.setSizePolicy(
        #     QSizePolicy.Minimum,  # 水平方向最小化
        #     QSizePolicy.Fixed     # 垂直方向固定
        # )
        # 
        # # 连接信号
        # self.device_tab_bar.currentChanged.connect(self._on_device_tab_changed)
        # self.device_tab_bar.tabCloseRequested.connect(self._on_device_tab_close_requested)
        # 
        # # 添加"+"按钮用于新建设备连接，设置容器为父对象
        # self.add_device_btn = QPushButton("+", self.device_tab_container)
        # self.add_device_btn.setFixedSize(30, 25)
        # self.add_device_btn.setToolTip(QCoreApplication.translate("main_window", "Connect New Device"))
        # self.add_device_btn.clicked.connect(self._connect_new_device)
        # self.add_device_btn.setStyleSheet("""
        #     QPushButton {
        #         font-size: 16px;
        #         font-weight: bold;
        #         border: 1px solid #555;
        #         border-radius: 3px;
        #         background-color: #2d2d30;
        #         color: #ffffff;
        #     }
        #     QPushButton:hover {
        #         background-color: #3e3e42;
        #     }
        #     QPushButton:pressed {
        #         background-color: #007acc;
        #     }
        # """)
        # 
        # device_tab_layout.addWidget(self.device_tab_bar)
        # device_tab_layout.addWidget(self.add_device_btn)
        # device_tab_layout.addStretch()  # 添加弹性空间，让TAB栏靠左
        # 
        # # 设置容器的大小策略
        # self.device_tab_container.setSizePolicy(
        #     QSizePolicy.Minimum,  # 水平方向最小化
        #     QSizePolicy.Fixed     # 垂直方向固定
        # )
        # 
        # # 将容器添加到菜单栏右侧（暂时隐藏）
        # menubar.setCornerWidget(self.device_tab_container, Qt.TopRightCorner)
        # self.device_tab_container.setVisible(False)  # 暂时屏蔽设备TAB栏
        # 
        # logger.info(f"Device tab bar created in menu bar (hidden), parent: {self.device_tab_bar.parent()}")
    
    def _on_device_tab_changed(self, index):
        """设备TAB切换事件 - 激活对应的MDI窗口"""
        if index < 0 or index >= len(self.device_sessions):
            return
        
        # 获取对应的设备会话
        session = self.device_sessions[index]
        self.current_session = session
        session_manager.set_active_session(session)
        
        # 切换主窗口的connection_dialog引用到该设备的dialog
        if session.connection_dialog:
            self.connection_dialog = session.connection_dialog
        
        # 激活对应的MDI窗口
        if session.mdi_window:
            self.mdi_area.setActiveSubWindow(session.mdi_window)
        
        logger.info(f"Switched to device session: {session.session_id}")
    
    def _on_device_tab_close_requested(self, index):
        """设备TAB关闭请求"""
        if index < 0 or index >= len(self.device_sessions):
            return
        
        session = self.device_sessions[index]
        
        # 确认关闭
        reply = QMessageBox.question(
            self,
            QCoreApplication.translate("main_window", "Close Device"),
            QCoreApplication.translate("main_window", 
                "Are you sure you want to close device {}?\n\nAll unsaved data will be lost.").format(session.get_display_name()),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._close_device_session(index)
    
    def _on_mdi_window_closed(self, device_session):
        """MDI窗口关闭事件"""
        try:
            # 找到对应的会话索引
            for i, session in enumerate(self.device_sessions):
                if session.session_id == device_session.session_id:
                    self._close_device_session(i)
                    break
        except Exception as e:
            logger.error(f"Failed to handle MDI window close: {e}", exc_info=True)
    
    def _connect_new_device(self):
        """连接新设备"""
        try:
            # 创建新的连接对话框用于选择设备
            from main_window import ConnectionDialog
            
            # 创建临时连接对话框
            temp_dialog = ConnectionDialog(self)
            temp_dialog.setWindowTitle(QCoreApplication.translate("main_window", "Connect New Device"))
            
            # 连接信号，当连接成功时创建新的设备会话
            def on_new_device_connected():
                try:
                    if not temp_dialog.rtt2uart:
                        return
                    
                    # 获取设备信息
                    rtt = temp_dialog.rtt2uart
                    device_serial = getattr(rtt, '_connect_para', 'Unknown')
                    
                    # 检查是否已经存在该设备的会话
                    for session in self.device_sessions:
                        if session.device_serial == device_serial:
                            QMessageBox.information(
                                self,
                                QCoreApplication.translate("main_window", "Device Already Connected"),
                                QCoreApplication.translate("main_window", 
                                    "This device is already connected.\n\nDevice: {}").format(device_serial)
                            )
                            return
                    
                    # 创建新的设备会话
                    # 查找设备索引
                    device_index = None
                    if hasattr(temp_dialog, 'available_jlinks'):
                        for idx, dev in enumerate(temp_dialog.available_jlinks):
                            if dev.get('serial') == device_serial:
                                device_index = idx
                                logger.info(f"Found device index: {device_index} for serial {device_serial}")
                                break
                        if device_index is None:
                            logger.warning(f"Device index not found for serial {device_serial}, will display without index")
                    
                    device_info = {
                        'serial': device_serial,
                        'product_name': getattr(rtt, 'device_info', 'Unknown'),
                        'connection': 'USB',
                        'index': device_index
                    }
                    
                    session = DeviceSession(device_info)
                    session.rtt2uart = rtt
                    session.connection_dialog = temp_dialog
                    session.is_connected = True
                    
                    # 创建MDI子窗口内容
                    mdi_content = DeviceMdiWindow(session, self)
                    
                    # 创建MDI子窗口并添加内容
                    from PySide6.QtCore import Qt
                    mdi_sub_window = self.mdi_area.addSubWindow(mdi_content)
                    mdi_sub_window.setWindowTitle(f"{session.get_display_name()}")
                    mdi_sub_window.setWindowIcon(QIcon(":/xexunrtt.ico"))
                    
                    # 显式设置窗口标志以确保可以调整大小
                    flags = mdi_sub_window.windowFlags()
                    logger.info(f"[MDI] Original window flags: {flags}")
                    # 确保没有设置固定大小相关的标志
                    mdi_sub_window.setWindowFlags(
                        Qt.WindowType.SubWindow |
                        Qt.WindowType.WindowTitleHint |
                        Qt.WindowType.WindowSystemMenuHint |
                        Qt.WindowType.WindowMinMaxButtonsHint
                    )
                    logger.info(f"[MDI] New window flags: {mdi_sub_window.windowFlags()}")
                    
                    # 设置大小
                    mdi_sub_window.resize(800, 600)
                    logger.info(f"[MDI] Window size: {mdi_sub_window.size()}")
                    
                    # 确保窗口状态是正常的（非最大化）
                    mdi_sub_window.setWindowState(Qt.WindowState.WindowNoState)
                    logger.info(f"[MDI] Window state: {mdi_sub_window.windowState()}")
                    
                    # 保存引用
                    session.mdi_window = mdi_content
                    mdi_content.mdi_sub_window = mdi_sub_window
                    
                    # 连接关闭信号
                    mdi_sub_window.destroyed.connect(lambda: self._on_mdi_window_closed(session))
                    
                    # 显示窗口（使用showNormal确保正常状态）
                    mdi_sub_window.showNormal()
                    logger.info(f"[MDI] Window shown, isVisible: {mdi_sub_window.isVisible()}, state: {mdi_sub_window.windowState()}")
                    
                    # 延迟设置窗口状态，确保窗口框架已经完全初始化
                    from PySide6.QtCore import QTimer
                    def ensure_normal_state():
                        if mdi_sub_window.windowState() != Qt.WindowState.WindowNoState:
                            logger.info(f"[MDI] Forcing window to normal state, current: {mdi_sub_window.windowState()}")
                            mdi_sub_window.setWindowState(Qt.WindowState.WindowNoState)
                            mdi_sub_window.resize(800, 600)
                    QTimer.singleShot(100, ensure_normal_state)
                    
                    # 添加到会话列表
                    self.device_sessions.append(session)
                    session_manager.add_session(session)
                    
                    # 设置为当前会话
                    self.current_session = session
                    session_manager.set_active_session(session)
                    
                    tab_name = session.get_display_name()
                    logger.info(f"✅ New device session created with MDI window: {tab_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to create new device session: {e}", exc_info=True)
            
            temp_dialog.connection_established.connect(on_new_device_connected)
            temp_dialog.show()
            
            logger.info("Connect new device requested")
            
        except Exception as e:
            logger.error(f"Failed to connect new device: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                QCoreApplication.translate("main_window", "Error"),
                QCoreApplication.translate("main_window", "Failed to connect new device: {}").format(str(e))
            )
    
    def _get_active_device_session(self):
        """获取当前激活的设备会话（基于激活的MDI窗口）"""
        try:
            active_mdi_sub = self.mdi_area.activeSubWindow()
            if active_mdi_sub:
                # 获取MDI子窗口的内容widget（DeviceMdiWindow）
                content_widget = active_mdi_sub.widget()
                if content_widget and isinstance(content_widget, DeviceMdiWindow):
                    logger.debug(f"[GET_ACTIVE] Found active session: {content_widget.device_session.session_id}")
                    return content_widget.device_session
            logger.debug("[GET_ACTIVE] No active MDI window found")
            return None
        except Exception as e:
            logger.error(f"Failed to get active device session: {e}")
            return None
    
    def _get_active_mdi_window(self):
        """获取当前激活的 MDI 窗口"""
        try:
            active_mdi_sub = self.mdi_area.activeSubWindow()
            if active_mdi_sub:
                content_widget = active_mdi_sub.widget()
                if content_widget and isinstance(content_widget, DeviceMdiWindow):
                    return content_widget
            return None
        except Exception as e:
            logger.error(f"Failed to get active MDI window: {e}")
            return None
    
    def _switch_to_session(self, session):
        """切换UI到指定的设备会话"""
        try:
            if not session:
                logger.warning("Cannot switch to None session")
                return
            
            logger.info(f"Switching UI to session: {session.session_id} (device: {session.device_serial})")
            
            # 1. 切换connection_dialog引用
            if session.connection_dialog:
                self.connection_dialog = session.connection_dialog
                
                # 2. 切换Worker引用，这样UI会显示对应设备的日志
                if hasattr(session.connection_dialog, 'worker') and session.connection_dialog.worker:
                    # 保存当前worker的引用（如果需要）
                    if hasattr(self, '_current_worker'):
                        old_worker = self._current_worker
                    
                    # 切换到新设备的worker
                    self._current_worker = session.connection_dialog.worker
                    
                    # 刷新UI显示该设备的日志
                    self._refresh_ui_from_worker(session.connection_dialog.worker)
            
            # 3. 更新连接状态显示
            if session.is_connected:
                self.connection_status_label.setText(
                    QCoreApplication.translate("main_window", "Connected: %s") % session.get_display_name()
                )
                self._set_rtt_controls_enabled(True)
            else:
                self.connection_status_label.setText(
                    QCoreApplication.translate("main_window", "Disconnected")
                )
                self._set_rtt_controls_enabled(False)
            
            # 4. 更新状态栏
            self.update_status_bar()
            
            logger.info(f"✅ Switched to session: {session.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to switch session: {e}", exc_info=True)
    
    # ========== 旧代码已删除：_refresh_ui_from_worker 方法 ==========
    # MDI 架构中，每个 DeviceMdiWindow 有自己的 _update_from_worker 方法
    # ====================================================
    # def _refresh_ui_from_worker(self, worker):
    #     # 此方法已废弃
    #     pass
    
    # ========== 旧代码已删除：_clear_all_logs 方法 ==========
    # MDI 架构中，清除日志由 on_clear_clicked 方法处理，操作当前 MDI 窗口
    # ====================================================
    # def _clear_all_logs(self):
    #     # 此方法已废弃
    #     pass
    
    def _close_device_session(self, index):
        """关闭设备会话"""
        if index < 0 or index >= len(self.device_sessions):
            return
        
        session = self.device_sessions[index]
        
        # 断开连接并清理
        session.cleanup()
        
        # 安全关闭该会话的ConnectionDialog
        if hasattr(session, 'connection_dialog') and session.connection_dialog:
            try:
                # 检查QObject是否仍然有效
                if hasattr(session.connection_dialog, 'isValid') and session.connection_dialog.isValid():
                    session.connection_dialog.close()
                    session.connection_dialog.deleteLater()
                else:
                    # 对于不支持isValid的对象，我们仍然尝试deleteLater来确保资源被释放
                    session.connection_dialog.deleteLater()
                # 清除引用
                session.connection_dialog = None
            except Exception as e:
                logger.warning(f"Connection dialog already deleted or invalid: {e}")
                # 确保引用被清除
                if hasattr(session, 'connection_dialog'):
                    session.connection_dialog = None
        
        # 从列表中移除
        self.device_sessions.pop(index)
        session_manager.remove_session(session)
        
        # 如果还有其他会话，切换到第一个
        if self.device_sessions:
            self.current_session = self.device_sessions[0]
            # 激活第一个设备的MDI窗口
            if self.current_session.mdi_window:
                self.mdi_area.setActiveSubWindow(self.current_session.mdi_window.mdi_sub_window)
            
            # 如果只剩一个窗口，先设置默认大小再最大化
            remaining_windows = self.mdi_area.subWindowList()
            if len(remaining_windows) == 1:
                remaining_windows[0].resize(WindowSize.MDI_WINDOW_DEFAULT_WIDTH, WindowSize.MDI_WINDOW_DEFAULT_HEIGHT)
                remaining_windows[0].showMaximized()
                logger.info(f"Only one MDI window remaining, set to default size (800x600) then maximized")
            else:
                #水平排列所有窗口
                pass
        else:
            self.current_session = None
            # 恢复到主连接对话框
            if hasattr(self, '_main_connection_dialog'):
                self.connection_dialog = self._main_connection_dialog
        
        logger.info(f"Device session closed: {session.session_id}")
    
    def _create_device_session_from_connection(self, session):
        """从已有session创建MDI窗口"""
        try:
            if not session:
                logger.warning("No session provided")
                return
            
            # 创建MDI子窗口内容
            mdi_content = DeviceMdiWindow(session, self)
            
            # 先获取当前窗口数量(在添加新窗口之前)
            current_window_count = len(self.mdi_area.subWindowList())
            
            # 创建MDI子窗口并添加内容
            from PySide6.QtCore import Qt, QTimer
            mdi_sub_window = self.mdi_area.addSubWindow(mdi_content)
            mdi_sub_window.setWindowTitle(f"{session.get_display_name()}")
            mdi_sub_window.setWindowIcon(QIcon(":/xexunrtt.ico"))
            
            # 保存引用
            session.mdi_window = mdi_content
            mdi_content.mdi_sub_window = mdi_sub_window
            
            # 连接关闭信号
            mdi_sub_window.destroyed.connect(lambda: self._on_mdi_window_closed(session))
            
            # 注意: 不要手动设置 windowFlags,使用 QMdiSubWindow 的默认标志
            # 默认标志已经包含了所有必要的功能(标题栏、调整大小、最小化/最大化/关闭按钮)
            logger.info(f"MDI window created with default flags: {mdi_sub_window.windowFlags()}")
            
            # 为子窗口设置一个简单的边框样式,但不影响标题栏
            mdi_sub_window.setStyleSheet("""
                QMdiSubWindow {
                    border: 1px solid #555555;
                }
            """)
            
            if current_window_count == 0:
                # 第一个窗口：先设置默认大小,再最大化image.png
                mdi_sub_window.resize(WindowSize.MDI_WINDOW_DEFAULT_WIDTH, WindowSize.MDI_WINDOW_DEFAULT_HEIGHT)
                mdi_sub_window.show()
                mdi_sub_window.showMaximized()
                logger.info(f"First MDI window, set to default size (800x600) then maximized")
            else:
                # 多个窗口：恢复所有窗口为正常大小，然后平铺
                # 恢复第一个窗口
                all_windows = self.mdi_area.subWindowList()
                for win in all_windows:
                    if win.isMaximized():
                        win.showNormal()
                        win.resize(WindowSize.MDI_WINDOW_DEFAULT_WIDTH, WindowSize.MDI_WINDOW_DEFAULT_HEIGHT)
                
                # 设置新窗口的大小和位置
                mdi_sub_window.resize(WindowSize.MDI_WINDOW_DEFAULT_WIDTH, WindowSize.MDI_WINDOW_DEFAULT_HEIGHT)
                mdi_sub_window.move(20, 20)
                mdi_sub_window.show()
                # 平铺所有窗口
                self.mdi_area.tileSubWindows()
                logger.info(f"Multiple MDI windows ({current_window_count + 1}), tiling all windows")
            
            # 添加到会话列表
            self.device_sessions.append(session)
            session_manager.add_session(session)
            
            # 设置为当前会话
            self.current_session = session
            session_manager.set_active_session(session)
            
            logger.info(f"✅ Device session created with MDI window: {session.get_display_name()}")
            self.append_jlink_log(QCoreApplication.translate("main_window", "Device %s connected successfully") % session.get_display_name())
            
            # 启用 RTT Chain Info 菜单
            if hasattr(self, 'rtt_info_action'):
                self.rtt_info_action.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Failed to create device session: {e}", exc_info=True)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        
        # 连接状态标签
        self.connection_status_label = QLabel(QCoreApplication.translate("main_window", "Disconnected"))
        self.status_bar.addWidget(self.connection_status_label)
        
        # 注释掉Turbo模式状态标签（功能保留，界面隐藏）
        # # 🚀 Turbo模式状态标签
        # self.turbo_status_label = QLabel("🚀 Turbo: ON")
        # self.turbo_status_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        # self.status_bar.addPermanentWidget(self.turbo_status_label)
        
        # 数据统计标签
        self.data_stats_label = QLabel(QCoreApplication.translate("main_window", "Read: 0 | Write: 0"))
        self.status_bar.addPermanentWidget(self.data_stats_label)
    
    def _show_connection_settings(self):
        """显示连接设置对话框"""
        self.show_connection_dialog()
    
    def _update_window_menu(self):
        """动态更新窗口菜单中的MDI窗口列表"""
        try:
            # 移除之前动态添加的窗口列表项
            # 找到最后一个分隔符之后的所有action并移除
            actions = self.window_menu.actions()
            last_separator_index = -1
            
            # 找到最后一个分隔符的位置
            for i, action in enumerate(actions):
                if action.isSeparator():
                    last_separator_index = i
            
            # 移除最后一个分隔符之后的所有action
            if last_separator_index >= 0:
                actions_to_remove = actions[last_separator_index + 1:]
                for action in actions_to_remove:
                    self.window_menu.removeAction(action)
            
            # 获取所有MDI子窗口
            sub_windows = self.mdi_area.subWindowList()
            if sub_windows:
                # 创建ActionGroup实现单选
                if not hasattr(self, 'window_action_group'):
                    self.window_action_group = QActionGroup(self)
                    self.window_action_group.setExclusive(True)
                else:
                    # 清空旧的actions
                    for action in self.window_action_group.actions():
                        self.window_action_group.removeAction(action)
                
                # 添加窗口列表
                for i, sub_window in enumerate(sub_windows):
                    # sub_window是QMdiSubWindow，需要获取其内部的DeviceMdiWindow
                    mdi_content = sub_window.widget()
                    if isinstance(mdi_content, DeviceMdiWindow):
                        # 创建窗口切换动作
                        window_title = sub_window.windowTitle()
                        action = QAction(f"{i+1}. {window_title}", self)
                        action.setCheckable(True)
                        
                        # 标记当前激活的窗口
                        if sub_window == self.mdi_area.activeSubWindow():
                            action.setChecked(True)
                        
                        # 保存窗口引用到action的data中（保存QMdiSubWindow）
                        action.setData(sub_window)
                        
                        # 添加到ActionGroup实现单选
                        self.window_action_group.addAction(action)
                        
                        # 连接切换信号（传递QMdiSubWindow）
                        action.triggered.connect(lambda checked, w=sub_window: self._activate_mdi_window(w))
                        
                        # 添加到菜单
                        self.window_menu.addAction(action)
                        
                        # 添加快捷键（前9个窗口）
                        if i < 9:
                            action.setShortcut(QKeySequence(f"Ctrl+{i+1}"))
            
        except Exception as e:
            logger.error(f"Failed to update window menu: {e}", exc_info=True)
    
    def _activate_mdi_window(self, mdi_sub_window):
        """激活指定的MDI窗口"""
        try:
            if mdi_sub_window:
                # mdi_sub_window是QMdiSubWindow包装器
                self.mdi_area.setActiveSubWindow(mdi_sub_window)
                mdi_sub_window.raise_()
                mdi_sub_window.activateWindow()
                
                # 获取内部的DeviceMdiWindow来更新会话
                mdi_content = mdi_sub_window.widget()
                if isinstance(mdi_content, DeviceMdiWindow):
                    self.current_session = mdi_content.device_session
                    session_manager.set_active_session(mdi_content.device_session)
                    logger.info(f"Activated MDI window for session: {mdi_content.device_session.session_id}")
        except Exception as e:
            logger.error(f"Failed to activate MDI window: {e}", exc_info=True)
    
    def _new_window(self):
        """新建窗口 - 重定向到连接新设备"""
        self._connect_new_device()
    
    def _count_jlink_usb_devices(self):
        """统计JLink USB设备数量"""
        try:
            import pylink
            jlink = pylink.JLink()
            num_devices = jlink.num_connected_emulators()
            return num_devices
        except Exception as e:
            logger.warning(f"Failed to count JLink devices: {e}")
            return 0
    
    # ========== 旧的MDI架构方法（已废弃） ==========
    # def _update_instance_tabs(self):
    #     """更新实例TAB栏"""
    #     # 更新窗口菜单中的实例列表
    #     self._update_instances_menu()
    # 
    # def _update_instances_menu(self):
    #     """更新实例菜单"""
    #     pass
    # 
    # def _focus_tab_window(self, tab_window):
    #     """聚焦到指定TAB窗口"""
    #     pass
    
    def _split_layout(self, orientation):
        """分割布局显示多个MDI设备窗口"""
        try:
            if len(self.device_sessions) < 2:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self,
                    QCoreApplication.translate("main_window", "Split Layout"),
                    QCoreApplication.translate("main_window", 
                        "Need at least 2 connected devices to split.\n\nPlease connect another device first."))
                return
            
            # 使用MDI区域的平铺功能
            if orientation == 'horizontal':
                self.mdi_area.tileSubWindows()
                logger.info("MDI layout: Tiled (Horizontal)")
            else:
                # 垂直平铺（通过调整窗口位置实现）
                sub_windows = self.mdi_area.subWindowList()
                if sub_windows:
                    mdi_height = self.mdi_area.height()
                    window_height = mdi_height // len(sub_windows)
                    mdi_width = self.mdi_area.width()
                    
                    for i, window in enumerate(sub_windows):
                        window.showNormal()
                        window.setGeometry(0, i * window_height, mdi_width, window_height)
                
                logger.info("MDI layout: Vertical")
            
            logger.info(f"Split layout applied: {orientation}, {len(self.device_sessions)} devices")
            
        except Exception as e:
            logger.error(f"Failed to apply split layout: {e}", exc_info=True)
        
        # # 旧代码（已禁用）
        # try:
        #     all_tab_windows = []  # instance_manager.get_all_tab_windows()
            
        #     if len(all_tab_windows) < 2:
        #         from PySide6.QtWidgets import QMessageBox
        #         QMessageBox.information(self,
        #             QCoreApplication.translate("main_window", "Split Layout"),
        #             QCoreApplication.translate("main_window", 
        #                 "Need at least 2 windows to split.\n\nPlease create a new window first (F10)."))
        #         return
            
        #     # 创建分割窗口
        #     split_window = QMainWindow()
        #     split_window.setWindowTitle(QCoreApplication.translate("main_window", "Split View"))
        #     split_window.setWindowIcon(QIcon(":/xexunrtt.ico"))
            
        #     # 创建中心部件和分割器
        #     central_widget = QWidget()
        #     split_window.setCentralWidget(central_widget)
        #     layout = QVBoxLayout(central_widget)
        #     layout.setContentsMargins(0, 0, 0, 0)
            
        #     # 创建分割器
        #     if orientation == 'horizontal':
        #         splitter = QSplitter(Qt.Horizontal)
        #     else:
        #         splitter = QSplitter(Qt.Vertical)
            
        #     # 将所有TAB窗口嵌入到分割器中（最多4个）
        #     for tab_window in all_tab_windows[:4]:
        #         # 创建容器widget来嵌入TAB窗口的内容
        #         container = QWidget()
        #         container_layout = QVBoxLayout(container)
        #         container_layout.setContentsMargins(2, 2, 2, 2)
                
        #         # 添加标题标签
        #         title_label = QLabel(tab_window.windowTitle())
        #         title_label.setStyleSheet("font-weight: bold; padding: 5px; background-color: #2d2d30; color: white;")
        #         container_layout.addWidget(title_label)
                
        #         # 创建TAB widget的克隆视图（只读）
        #         tab_clone = QTabWidget()
        #         for i, original_tab in enumerate(tab_window.log_tabs):
        #             clone_tab = QPlainTextEdit()
        #             clone_tab.setReadOnly(True)
        #             clone_tab.setPlainText(original_tab.toPlainText())
        #             tab_clone.addTab(clone_tab, f"CH{i}")
                
        #         container_layout.addWidget(tab_clone)
        #         splitter.addWidget(container)
            
        #     layout.addWidget(splitter)
            
        #     # 设置窗口大小和显示
        #     if orientation == 'horizontal':
        #         split_window.resize(1600, 600)
        #     else:
        #         split_window.resize(800, 1200)
            
        #     split_window.show()
            
        #     # 保存分割窗口引用
        #     if not hasattr(self, 'split_windows'):
        #         self.split_windows = []
        #     self.split_windows.append(split_window)
            
        #     logger.info(f"Created {orientation} split layout with {len(all_tab_windows[:4])} windows")
            
        # except Exception as e:
        #     logger.error(f"Failed to create split layout: {e}")
        #     import traceback
        #     traceback.print_exc()
        #     from PySide6.QtWidgets import QMessageBox
        #     QMessageBox.warning(self,
        #         QCoreApplication.translate("main_window", "Error"),
        #         QCoreApplication.translate("main_window", "Failed to create split layout:\n{}").format(e))
    
    def _remove_split(self):
        """移除所有分割窗口"""
        if hasattr(self, 'split_windows'):
            for window in self.split_windows:
                try:
                    window.close()
                except:
                    pass
            self.split_windows.clear()
            logger.info("Removed all split windows")
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self,
                QCoreApplication.translate("main_window", "Remove Split"),
                QCoreApplication.translate("main_window", "No split windows to remove."))
    
    def _on_compact_mode_checkbox_changed(self, state):
        """复选框状态改变时的处理"""
        # Qt.Checked = 2, Qt.Unchecked = 0
        should_enable = (state == 2)  # Qt.Checked
        logger.info(f"[COMPACT MODE] Checkbox changed: state={state}, should_enable={should_enable}, current={self.compact_mode}")
        # 只有当状态真正不同时才切换
        if self.compact_mode != should_enable:
            # 直接设置为目标状态
            self.compact_mode = should_enable
            logger.info(f"[COMPACT MODE] Setting compact_mode to: {self.compact_mode}")
            self._apply_compact_mode_state()
        else:
            logger.info(f"[COMPACT MODE] State unchanged, skipping (both are {self.compact_mode})")
    
    def _toggle_compact_mode_via_f11(self):
        """通过F11快捷键切换紧缩模式"""
        self.compact_mode = not self.compact_mode
        self._apply_compact_mode_state()
    
    def _toggle_compact_mode(self):
        """切换紧凑模式（菜单和其他地方调用）"""
        self.compact_mode = not self.compact_mode
        self._apply_compact_mode_state()
    
    def _apply_compact_mode_state(self):
        """应用紧凑模式状态到UI"""
        logger.info(f"[COMPACT MODE] Applying state: compact_mode={self.compact_mode}")
        
        if self.compact_mode:
            # 进入紧凑模式
            logger.info("Entering compact mode for multi-device usage")
            
            # 保存当前窗口状态
            self._normal_geometry = self.geometry()
            self._normal_menu_visible = self.menuBar().isVisible()
            self._normal_status_visible = self.statusBar().isVisible()
            
            # 隐藏菜单栏和状态栏
            self.menuBar().setVisible(False)
            self.statusBar().setVisible(False)
            
            # 隐藏JLink日志区域
            if hasattr(self, 'jlink_log_widget'):
                self._normal_jlink_log_visible = self.jlink_log_widget.isVisible()
                self.jlink_log_widget.setVisible(False)
            
            # 设置为紧凑尺寸 - 更合理的尺寸
            compact_width = 400
            compact_height = 250
            self.resize(compact_width, compact_height)
            
            # 设置窗口标题显示紧凑模式
            original_title = self.windowTitle()
            compact_mode_text = QCoreApplication.translate("main_window", " - Compact Mode")
            if compact_mode_text not in original_title:
                self.setWindowTitle(original_title + QCoreApplication.translate("main_window", " - Compact Mode"))
            
            # 设置窗口始终置顶（紧凑模式特性）
            try:
                current_flags = self.windowFlags()
                # 确保保留关闭按钮和其他必要的窗口控件
                new_flags = current_flags | Qt.WindowStaysOnTopHint
                # 明确保留窗口系统菜单和关闭按钮
                new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
                self.setWindowFlags(new_flags)
                self.show()  # 重新显示以应用新的窗口标志
                logger.info("Window set to stay on top in compact mode with close button enabled")
            except Exception as ex:
                logger.warning(f"Failed to set window stay-on-top: {ex}")
                
        else:
            # 退出紧凑模式
            logger.info("Exiting compact mode")
            
            # 取消置顶
            try:
                current_flags = self.windowFlags()
                new_flags = current_flags & ~Qt.WindowStaysOnTopHint
                # 确保保留关闭按钮和其他必要的窗口控件
                new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
                self.setWindowFlags(new_flags)
                self.show()  # 重新显示以应用新的窗口标志
                logger.info("Window stay-on-top flag removed with close button enabled")
            except Exception as ex:
                logger.warning(f"Failed to clear window stay-on-top: {ex}")
            
            # 恢复菜单栏和状态栏
            if hasattr(self, '_normal_menu_visible'):
                self.menuBar().setVisible(self._normal_menu_visible)
            else:
                self.menuBar().setVisible(True)
                
            if hasattr(self, '_normal_status_visible'):
                self.statusBar().setVisible(self._normal_status_visible)
            else:
                self.statusBar().setVisible(True)
            
            # 恢复JLink日志区域
            if hasattr(self, 'jlink_log_widget'):
                if hasattr(self, '_normal_jlink_log_visible'):
                    self.jlink_log_widget.setVisible(self._normal_jlink_log_visible)
                else:
                    self.jlink_log_widget.setVisible(True)
            
            # 恢复窗口几何
            if hasattr(self, '_normal_geometry'):
                self.setGeometry(self._normal_geometry)
            else:
                # 默认恢复尺寸
                normal_width = 800
                normal_height = 600
                self.resize(normal_width, normal_height)
            
            # 恢复原始窗口标题
            current_title = self.windowTitle()
            compact_mode_check = QCoreApplication.translate("main_window", " - Compact Mode")
            if compact_mode_check in current_title:
                compact_mode_text = QCoreApplication.translate("main_window", " - Compact Mode")
                self.setWindowTitle(current_title.replace(compact_mode_text, ""))
        
        # 同步所有UI元素状态（阻止信号循环）
        # 1. 更新菜单项
        # if hasattr(self, 'compact_mode_action'):
        #     self.compact_mode_action.blockSignals(True)
        #     self.compact_mode_action.setChecked(self.compact_mode)
        #     self.compact_mode_action.blockSignals(False)
        
        # 2. 更新UI复选框 - 已屏蔽
        # if hasattr(self.ui, 'compact_mode_checkbox'):
        #     self.ui.compact_mode_checkbox.blockSignals(True)
        #     self.ui.compact_mode_checkbox.setChecked(self.compact_mode)
        #     self.ui.compact_mode_checkbox.blockSignals(False)
    
    # def _show_context_menu(self, position):
    #     """显示右键菜单"""
    #     context_menu = QMenu(self)
        
    #     # 紧凑模式选项 - 根据当前状态显示不同文本
    #     if self.compact_mode:
    #         compact_action = context_menu.addAction("🔍 恢复正常模式 (Ctrl+M)")
    #         compact_action.setToolTip("退出紧凑模式，恢复完整界面")
    #     else:
    #         compact_action = context_menu.addAction("📱 切换到紧凑模式 (Ctrl+M)")
    #         compact_action.setToolTip("进入紧凑模式，适合多窗口使用")
        
    #     compact_action.triggered.connect(self._toggle_compact_mode)
        
    #     context_menu.addSeparator()
        
    #     # 窗口管理
    #     window_menu = context_menu.addMenu("🪟 窗口管理")
        
    #     # 新建窗口
    #     new_window_action = window_menu.addAction("新建窗口 (Ctrl+N)")
    #     new_window_action.triggered.connect(self._new_window)
        
    #     # 最小化窗口
    #     minimize_action = window_menu.addAction("最小化窗口")
    #     minimize_action.triggered.connect(self.showMinimized)
        
    #     # 最大化/还原
    #     if self.isMaximized():
    #         maximize_action = window_menu.addAction("还原窗口")
    #         maximize_action.triggered.connect(self.showNormal)
    #     else:
    #         maximize_action = window_menu.addAction("最大化窗口")
    #         maximize_action.triggered.connect(self.showMaximized)
        
    #     context_menu.addSeparator()
        
    #     # 连接管理
    #     connection_menu = context_menu.addMenu("🔗 连接管理")
        
    #     # 连接设置
    #     settings_action = connection_menu.addAction("连接设置...")
    #     settings_action.triggered.connect(self._show_connection_settings)
        
    #     # 重新连接
    #     if hasattr(self, 'connection_dialog') and self.connection_dialog:
    #         if self.connection_dialog.start_state:
    #             reconnect_action = connection_menu.addAction("断开连接")
    #             reconnect_action.triggered.connect(self.on_dis_connect_clicked)
    #         else:
    #             reconnect_action = connection_menu.addAction("重新连接")
    #             reconnect_action.triggered.connect(self.on_re_connect_clicked)
        
    #     context_menu.addSeparator()
        
    #     # 程序控制
    #     program_menu = context_menu.addMenu("⚙️ 程序控制")
        
    #     # 正常退出
    #     quit_action = program_menu.addAction("退出程序")
    #     quit_action.triggered.connect(self.close)
        
    #     # 强制退出
    #     force_quit_action = program_menu.addAction("强制退出 (Ctrl+Alt+Q)")
    #     force_quit_action.triggered.connect(self._force_quit)
    #     force_quit_action.setToolTip("用于程序无响应时的紧急退出")
        
    #     # 显示菜单
    #     context_menu.exec(self.mapToGlobal(position))
    
    def _force_quit(self):
        """强制退出程序 - 用于紧急情况"""
        logger.info("Force quit triggered by user (Ctrl+Alt+Q)")
        
        try:
            # 立即清除窗口置顶标志
            if self.compact_mode:
                current_flags = self.windowFlags()
                new_flags = current_flags & ~Qt.WindowStaysOnTopHint
                # 确保保留关闭按钮
                new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
                self.setWindowFlags(new_flags)
            
            # 强制关闭所有子窗口
            for widget in QApplication.allWidgets():
                if widget != self:
                    try:
                        widget.close()
                    except:
                        pass
            
            # 强制退出应用程序
            QApplication.quit()
            
        except Exception as e:
            logger.error(f"Error in force quit: {e}")
            # 如果以上方法都失败，使用系统退出
            import sys
            sys.exit(0)
    
    def _change_language(self, language: str):
        """切换界面语言
        
        Args:
            language: 语言代码 ('en_US', 'zh_CN', 'zh_TW')
        """
        # 获取当前语言
        current_language = config_manager.get_language()
        
        # 语言名称映射
        language_names = {
            'en_US': 'English',
            'zh_CN': '中文（简体）',
            'zh_TW': '中文（繁體）'
        }
        
        # 如果语言没有变化，显示提示后返回
        if current_language == language:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Information)
            
            # 根据当前语言显示不同的标题和提示文本
            if language == 'en_US':
                msg.setWindowTitle("Language")
                msg.setText(f"Current language is already {language_names[language]}")
            elif language == 'zh_CN':
                msg.setWindowTitle("语言")
                msg.setText(f"当前语言已经是{language_names[language]}")
            else:  # zh_TW
                msg.setWindowTitle("語言")
                msg.setText(f"目前語言已經是{language_names[language]}")
            
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec()
            return
        
        # 保存语言设置（使用全局 config_manager）
        config_manager.set_language(language)
        config_manager.save_config()
        
        # 显示重启提示
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        
        # 根据目标语言显示不同的标题和提示文本
        if language == 'en_US':
            msg.setWindowTitle("Language")
            msg.setText(f"Language changed to {language_names[language]}")
            msg.setInformativeText("Please restart the application for the changes to take effect.")
        elif language == 'zh_CN':
            msg.setWindowTitle("语言")
            msg.setText(f"语言已切换到{language_names[language]}")
            msg.setInformativeText("请重启应用程序使更改生效。")
        else:  # zh_TW
            msg.setWindowTitle("語言")
            msg.setText(f"語言已切換到{language_names[language]}")
            msg.setInformativeText("請重啟應用程式使更改生效。")
        
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    def _show_about(self):
        """显示关于对话框"""
        try:
            from version import VERSION, VERSION_NAME, BUILD_TIME
            
            about_text = QCoreApplication.translate(
                "main_window",
                "%s v%s\n\nRTT Debug Tool\n\nBased on PySide6\n\nBuilt: %s"
            ) % (VERSION_NAME, VERSION, BUILD_TIME)
            
            QMessageBox.about(
                self,
                QCoreApplication.translate("main_window", "About %s") % VERSION_NAME,
                about_text
            )
        except ImportError:
            # 如果version.py不存在，使用默认信息
            QMessageBox.about(
                self,
                         QCoreApplication.translate("main_window", "About XexunRTT"),
                QCoreApplication.translate(
                    "main_window",
                    "XexunRTT v2.2\n\nRTT Debug Tool\n\nBased on PySide6"
                )
            )

    def _build_encoding_submenu(self):
        """构建编码设置子菜单"""
        try:
            if not hasattr(self, 'encoding_menu') or self.encoding_menu is None:
                return
            self.encoding_menu.clear()
            # 可选编码列表
            self._encoding_list = ['GBK', 'UTF-8', 'UTF-8-SIG', 'GB2312', 'BIG5', 'ISO-8859-1']
            self.encoding_action_group = QActionGroup(self)
            self.encoding_action_group.setExclusive(True)
            current = 'gbk'
            try:
                if self.connection_dialog:
                    current = self.connection_dialog.config.get_text_encoding()
            except Exception:
                pass
            for enc in self._encoding_list:
                action = QAction(enc, self)
                action.setCheckable(True)
                action.setChecked(enc.lower() == current.lower())
                action.triggered.connect(lambda checked, e=enc: self._on_encoding_selected(e))
                self.encoding_action_group.addAction(action)
                self.encoding_menu.addAction(action)
            # MDI架构：初始根据是否有活动连接设置可用性
            has_active_connection = bool(self._get_active_device_session())
            self._set_encoding_menu_enabled(not has_active_connection)
        except Exception:
            pass

    def _refresh_encoding_menu_checks(self):
        try:
            current = self.connection_dialog.config.get_text_encoding() if self.connection_dialog else 'gbk'
            if hasattr(self, 'encoding_action_group'):
                for act in self.encoding_action_group.actions():
                    act.setChecked(act.text().lower() == current.lower())
        except Exception:
            pass

    def _set_encoding_menu_enabled(self, enabled: bool):
        try:
            if hasattr(self, 'encoding_menu') and self.encoding_menu is not None:
                self.encoding_menu.setEnabled(enabled)
        except Exception:
            pass

    def _on_encoding_selected(self, enc: str):
        """🔧 修复：选择编码 - 允许连接时切换，但提示需要重新连接才生效"""
        try:
            # 设置编码
            if self.connection_dialog:
                self.connection_dialog.config.set_text_encoding(enc)
                self.connection_dialog.config.save_config()
            
            # 同步 UI 旧控件（如存在）
            if hasattr(self, 'ui') and hasattr(self.ui, 'encoder'):
                idx = self.ui.encoder.findText(enc, Qt.MatchFixedString)
                if idx >= 0:
                    self.ui.encoder.setCurrentIndex(idx)
            
            # 检查是否有活动连接
            if self._get_active_device_session():
                # 连接时切换编码，提示需要重新连接
                QMessageBox.information(
                    self, 
                    QCoreApplication.translate("main_window", "Info"), 
                    QCoreApplication.translate("main_window", "Encoding switched to: %s\n\nPlease reconnect for the new encoding to take effect.") % enc
                )
            else:
                self.statusBar().showMessage(QCoreApplication.translate("main_window", "Encoding switched to: %s") % enc, 2000)
        except Exception:
            pass
    
    # def show_performance_test(self):
    #     """显示性能测试窗口"""
    #     try:
    #         self.perf_test_widget = show_performance_test(self)
    #         self.perf_test_widget.log_message(QCoreApplication.translate("main_window", "Performance test tool started"))
    #         self.perf_test_widget.log_message(QCoreApplication.translate("main_window", "Note: Please ensure device is connected and RTT debugging is started"))
    #     except Exception as e:
    #         QMessageBox.warning(self, QCoreApplication.translate("main_window", "Error"), QCoreApplication.translate("main_window", "Failed to start performance test: {}").format(str(e)))
    
    # def toggle_turbo_mode(self):
    #     """切换Turbo模式（隐藏UI，功能保留）"""
    #     # 注释掉UI相关代码，但保留核心功能
    #     # enabled = self.turbo_mode_action.isChecked()
        
    #     # 由于UI已隐藏，这里可以通过其他方式控制，暂时保持启用状态
    #     enabled = True
        
    #     # 应用到ConnectionDialog的worker
    #     if self.connection_dialog and hasattr(self.connection_dialog, 'worker'):
    #         self.connection_dialog.worker.set_turbo_mode(enabled)
            
        # 注释掉状态消息和状态栏更新（UI已隐藏）
        # # 显示状态消息
        # status = "启用" if enabled else "禁用"
        # self.append_jlink_log(f"🚀 Turbo模式已{status}")
        # 
        # # 更新状态栏
        # if hasattr(self, 'turbo_status_label'):
        #     self.turbo_status_label.setText(f"🚀 Turbo: {'ON' if enabled else 'OFF'}")
        #     # 更新颜色
        #     color = "#00AA00" if enabled else "#AA0000"
        #     self.turbo_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        # 
        # # 使用append_jlink_log而不是log_message
        # if hasattr(self, 'append_jlink_log'):
        #     self.append_jlink_log(f"Turbo模式已{status}，{'批量处理数据以提升性能' if enabled else '逐行处理数据以保持精确性'}")
    
    def show_connection_dialog(self):
        """显示连接配置对话框"""
        # 连接对话框已在初始化时创建，直接显示即可
        
        # 在显示前确保串口转发选择框内容是最新的
        # （TAB在主窗口初始化后才会准备好，所以这里需要更新）
        if hasattr(self.connection_dialog, '_update_serial_forward_combo'):
            self.connection_dialog._update_serial_forward_combo()
        
        # 显示对话框
        self.connection_dialog.show()
        self.connection_dialog.raise_()
        self.connection_dialog.activateWindow()
        
        # 将对话框居中显示在主窗口中
        self._center_dialog_on_parent(self.connection_dialog)
        
        self.connection_dialog.raise_()
        self.connection_dialog.activateWindow()
    
    def _center_dialog_on_parent(self, dialog):
        """将对话框居中显示在父窗口中"""
        if not dialog or not self:
            return
        
        # 获取主窗口的几何信息
        parent_geometry = self.geometry()
        parent_x = parent_geometry.x()
        parent_y = parent_geometry.y()
        parent_width = parent_geometry.width()
        parent_height = parent_geometry.height()
        
        # 获取对话框的大小
        dialog_width = dialog.width()
        dialog_height = dialog.height()
        
        # 计算居中位置
        center_x = parent_x + (parent_width - dialog_width) // 2
        center_y = parent_y + (parent_height - dialog_height) // 2
        
        # 设置对话框位置
        dialog.move(center_x, center_y)
    
    def on_connection_established(self):
        """连接建立成功后的处理"""
        # 启用RTT相关功能
        self._set_rtt_controls_enabled(True)
        # 🔧 修复：连接中允许切换编码（切换后提示需要重新连接）
        # self._set_encoding_menu_enabled(False)  # 不再禁用编码菜单
        
        # 启动自动重连监控（如果已启用）
        self.manual_disconnect = False  # 清除手动断开标记
        if hasattr(self.ui, 'auto_reconnect_checkbox') and self.ui.auto_reconnect_checkbox.isChecked():
            self.last_data_time = time.time()
            self.data_check_timer.start(TimerInterval.DATA_CHECK)
            logger.info("Auto reconnect monitoring started")
        
        # 创建设备会话并添加MDI窗口
        if not self.connection_dialog or not self.connection_dialog.rtt2uart:
            logger.warning("No active connection to create session from")
            return
        
        # 获取当前连接的设备信息
        rtt = self.connection_dialog.rtt2uart
        device_serial = getattr(rtt, '_connect_para', 'Unknown')
        
        # 查找设备索引
        device_index = None
        if hasattr(self.connection_dialog, 'available_jlinks'):
            logger.debug(f"Searching for device {device_serial} in available_jlinks: {self.connection_dialog.available_jlinks}")
            for idx, dev in enumerate(self.connection_dialog.available_jlinks):
                dev_serial = dev.get('serial', '')
                logger.debug(f"  Comparing: '{dev_serial}' == '{device_serial}' ? {dev_serial == device_serial}")
                if dev_serial == device_serial:
                    device_index = idx
                    logger.info(f"Found device index: {device_index} for serial {device_serial}")
                    break
            if device_index is None:
                logger.warning(f"Device index not found for serial {device_serial}, will display without index")
        
        device_info = {
            'serial': device_serial,
            'product_name': getattr(rtt, 'device_info', 'Unknown'),
            'connection': 'USB',
            'index': device_index
        }
        
        # 创建新的设备会话
        session = DeviceSession(device_info=device_info)
        session.rtt2uart = rtt
        session.connection_dialog = self.connection_dialog
        session.is_connected = True
        
        # 添加到会话管理器
        session_manager.add_session(session)
        self.device_sessions.append(session)
        
        # 创建MDI子窗口并添加内容
        self._create_device_session_from_connection(session)
        
        # 设置为当前会话
        self.current_session = session
        session_manager.set_active_session(session)
        
        # 应用保存的设置
        self._apply_saved_settings()
        
        # 更新状态显示（MDI架构：会自动显示活动设备的状态）
        self.update_status_bar()
        
        # 显示成功消息
        self.statusBar().showMessage(QCoreApplication.translate("main_window", "RTT connection established successfully"), 3000)
    
    def flush_all_log_buffers(self):
        """刷新所有设备会话中的日志缓冲区
        
        用于连接断开时确保所有缓存数据都被保存，防止数据丢失
        """
        try:
            total_flushed = 0
            total_bytes = 0
            
            # 遍历所有设备会话
            for session in self.device_sessions:
                # 检查会话是否有worker并且worker有flush_all_log_buffers方法
                if hasattr(session, 'worker') and session.worker and hasattr(session.worker, 'flush_all_log_buffers'):
                    # 调用worker的flush_all_log_buffers方法
                    try:
                        session.worker.flush_all_log_buffers()
                        total_flushed += 1
                    except Exception as e:
                        logger.error(f"Failed to flush log buffers for session {session.device_id}: {e}")
            
            if total_flushed > 0:
                logger.info(f"Successfully triggered flush for {total_flushed} device sessions")
                
        except Exception as e:
            logger.error(f"Error in RTTMainWindow.flush_all_log_buffers: {e}")
    
    def on_connection_disconnected(self):
        """连接断开后的处理"""
        # 禁用RTT相关功能
        self._set_rtt_controls_enabled(False)
        # 🔧 修复：编码菜单现在始终可用，不需要重新启用
        # self._set_encoding_menu_enabled(True)
        
        # 🔄 连接断开时立即刷新所有日志缓冲区，确保所有缓存数据都被保存
        self.flush_all_log_buffers()
        
        # 更新状态显示
        self.update_status_bar()
        
        # 显示断开消息
        self.statusBar().showMessage(QCoreApplication.translate("main_window", "RTT connection disconnected"), 3000)
    
    def _set_rtt_controls_enabled(self, enabled):
        """设置RTT相关控件的启用状态"""
        # RTT相关的UI控件在连接成功前应该被禁用
        if hasattr(self, 'ui'):
            # 发送命令相关控件
            if hasattr(self.ui, 'pushButton'):
                self.ui.pushButton.setEnabled(enabled)
            # if hasattr(self.ui, 'cmd_buffer'):
            #     self.ui.cmd_buffer.setEnabled(enabled)
            
            # # 清除按钮
            # if hasattr(self.ui, 'clear'):
            #     self.ui.clear.setEnabled(enabled)
            
            # # 打开文件夹按钮
            # if hasattr(self.ui, 'openfolder'):
            #     self.ui.openfolder.setEnabled(enabled)
    
    def _apply_saved_settings(self):
        """应用保存的设置"""
        if not self.connection_dialog:
            return
            
        try:
            settings = self.connection_dialog.settings
            # 注意：滚动条锁定功能已移至DeviceMdiWindow，不再使用LockH/LockV复选框
            self.ui.light_checkbox.setChecked(settings['light_mode'])
            self.ui.fontsize_box.setValue(settings['fontsize'])
            
            # 加载字体设置
            if hasattr(self.ui, 'font_combo'):
                saved_font = self.connection_dialog.config.get_fontfamily()
                index = self.ui.font_combo.findText(saved_font)
                if index >= 0:
                    self.ui.font_combo.setCurrentIndex(index)
                # 🔑 初始化当前字体变量（避免首次加载时触发不必要的刷新）
                self._current_font_name = saved_font
            
            # 🔑 初始化当前字号变量
            self._current_font_size = settings['fontsize']
            
            # 命令历史已在populateComboBox()中加载，这里只需要同步到settings
            cmd_history = self.connection_dialog.config.get_command_history()
            # 使用集合去重，保持顺序
            unique_commands = []
            seen = set()
            for cmd in cmd_history:
                if cmd and cmd not in seen:
                    unique_commands.append(cmd)
                    seen.add(cmd)
            
            # 同步更新settings以保持兼容性（不重复添加到UI）
            settings['cmd'] = unique_commands
            
            logger.debug(f"Command history synced to settings: {len(unique_commands)} items")
            
            # 🔑 关键修复：只在程序启动时加载筛选值，连接时不要重新加载
            # 避免F4清空后重新连接导致筛选值被清空
            if not self._filters_loaded:
                # 从配置管理器加载筛选器设置
                # 🔑 关键改进：确保config对象中始终包含所有筛选值（即使是空值）
                # MDI 架构：筛选器在 DeviceMdiWindow 创建时从配置加载
                # 这里只需要确保 config 对象中有筛选器数据
                logger.info("📥 Loading filters from config (MDI architecture)")
                for i in range(17, MAX_TAB_SIZE):
                    # 优先从INI配置加载筛选器
                    filter_content = self.connection_dialog.config.get_filter(i)
                    if not filter_content and i - 17 < len(settings['filter']) and settings['filter'][i-17]:
                        # 兼容旧格式：从settings加载，并同步到config对象
                        filter_text = settings['filter'][i-17]
                        self.connection_dialog.config.set_filter(i, filter_text)
                        logger.debug(f"  Filter[{i}] loaded from settings and synced: '{filter_text}'")
                    elif not filter_content:
                        # 没有配置值，确保config对象中有空字符串占位
                        self.connection_dialog.config.set_filter(i, "")
                
                # 🔑 标记：filter已经加载，UI初始化完成
                self._filters_loaded = True
                logger.info("UI initialization completed, all filters synced to config object, config saving is now safe")
            else:
                # MDI 架构：重连时，筛选器已经在 DeviceMdiWindow 中
                logger.info("🔄 Reconnecting: filters managed by DeviceMdiWindow (MDI architecture)")
                self._filters_loaded = True
            
            # 🔑 标记：UI初始化完成，现在可以安全保存配置
            self._ui_initialization_complete = True
                    
            # 应用样式
            self.set_style()
        except Exception as e:
            logger.warning(f'Failed to apply saved settings: {e}')
    
    def _create_default_tab_window(self):
        """创建默认的第一个TAB窗口（已废弃，新架构不需要）"""
        pass
    
    def _init_splitter_sizes(self):
        """初始化分割器大小"""
        try:
            # 获取窗口总高度
            total_height = self.height()
            
            # 计算各部分的初始高度
            # MDI区域：占据大部分空间
            # 底部容器：按钮区 + JLink日志区
            button_height = LayoutSize.BUTTON_AREA_HEIGHT
            jlink_log_height = LayoutSize.JLINK_LOG_DEFAULT_HEIGHT
            bottom_height = LayoutSize.BOTTOM_CONTAINER_HEIGHT
            # 减去菜单栏、状态栏、分割条等额外空间
            mdi_height = total_height - bottom_height - LayoutSize.MENUBAR_STATUSBAR_HEIGHT
            
            # 设置分割器大小（只有2个部件：MDI区域和底部容器）
            self.main_splitter.setSizes([mdi_height, bottom_height])
            
            logger.info(f"Splitter initialized: MDI={mdi_height}px, Bottom={bottom_height}px (Button={button_height}px + JLink={jlink_log_height}px)")
        except Exception as e:
            logger.error(f"Failed to initialize splitter sizes: {e}", exc_info=True)
    
    def _on_splitter_moved(self, pos, index):
        """分割器移动事件 - 自动隐藏/显示JLink日志区
        
        注意：最大高度限制已通过 bottom_container.setMaximumHeight() 设置，
        Qt 会自动限制分割线的可拖动范围，无需在此处理
        """
        try:
            # 获取底部容器的当前高度
            sizes = self.main_splitter.sizes()
            if len(sizes) >= 2:
                bottom_height = sizes[1]  # 底部容器高度（按钮区 + JLink日志区）
                
                # 计算JLink日志区的实际高度（底部容器高度 - 按钮区高度）
                button_height = LayoutSize.BUTTON_AREA_HEIGHT
                jlink_height = bottom_height - button_height
                
                # 如果JLink区域小于最小高度，自动隐藏
                if jlink_height < self.jlink_log_min_height:
                    if self.jlink_log_widget.isVisible():
                        self.jlink_log_widget.setVisible(False)
                        logger.info(f"JLink log hidden (height={jlink_height}px < {self.jlink_log_min_height}px)")
                else:
                    # 确保显示
                    if not self.jlink_log_widget.isVisible():
                        self.jlink_log_widget.setVisible(True)
                        logger.info(f"JLink log shown (height={jlink_height}px)")
        except Exception as e:
            logger.error(f"Failed to handle splitter move: {e}", exc_info=True)
    
    def _setup_jlink_logging(self):
        """设置JLink日志捕获 - 统一使用 append_jlink_log 回调"""
        # 创建自定义日志处理器来捕获JLink日志，使用统一的回调函数
        self.jlink_log_handler = JLinkLogHandler(self.append_jlink_log)
        
        # 设置JLink库的日志级别 - 默认只显示WARNING及以上级别的日志
        jlink_logger = logging.getLogger('pylink')
        jlink_logger.setLevel(logging.WARNING)  # 改为WARNING级别，减少调试信息
        jlink_logger.addHandler(self.jlink_log_handler)
        
        # 防止日志传播到根日志器，避免在控制台重复输出
        jlink_logger.propagate = False
    
    def clear_jlink_log(self):
        """清除JLink日志"""
        self.jlink_log_text.clear()
    
    def toggle_jlink_verbose_log(self, enabled):
        """切换JLink详细日志"""
        self.jlink_verbose_logging = enabled
        jlink_logger = logging.getLogger('pylink')
        
        if enabled:
            self.toggle_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Disable Verbose Log"))
            # 启用详细的JLink日志 - 设置为DEBUG级别
            jlink_logger.setLevel(logging.DEBUG)
            self.append_jlink_log(QCoreApplication.translate("main_window", "JLink verbose logging enabled - will show all debug information"))
            
            # 启用JLink文件日志到当前目录
            self.enable_jlink_file_logging()
        else:
            self.toggle_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Enable Verbose Log"))
            # 禁用详细日志 - 恢复为WARNING级别
            jlink_logger.setLevel(logging.WARNING)
            self.append_jlink_log(QCoreApplication.translate("main_window", "JLink verbose logging disabled - only showing warnings and errors"))
            
            # 禁用JLink文件日志
            self.disable_jlink_file_logging()
    
    def enable_jlink_file_logging(self):
        """启用JLink文件日志"""
        try:
            import os
            # 使用当前工作目录，文件名为JLINK_DEBUG.TXT
            log_file_path = os.path.join(os.getcwd(), "JLINK_DEBUG.TXT")
            
            # MDI架构：为所有已连接的设备会话启用文件日志
            enabled_count = 0
            for session in session_manager.get_all_sessions():
                if session.rtt2uart and hasattr(session.rtt2uart, 'jlink'):
                    try:
                        session.rtt2uart.jlink.set_log_file(log_file_path)
                        enabled_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to enable file logging for session {session.session_id}: {e}")
            
            if enabled_count > 0:
                self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging enabled: %s") % log_file_path)
                self._start_jlink_log_tailer(log_file_path)
            else:
                # 如果还没有连接，标记需要在连接时启用
                self.pending_jlink_log_file = log_file_path
                self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging will be enabled on next connection: %s") % log_file_path)
                
        except Exception as e:
            self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to setup file logging: %s") % str(e))
    
    def disable_jlink_file_logging(self):
        """禁用JLink文件日志"""
        try:
            # 清除待启用的日志文件标记
            if hasattr(self, 'pending_jlink_log_file'):
                delattr(self, 'pending_jlink_log_file')
            
            # MDI架构：为所有已连接的设备会话禁用文件日志
            disabled_count = 0
            for session in session_manager.get_all_sessions():
                if session.rtt2uart and hasattr(session.rtt2uart, 'jlink'):
                    try:
                        # 通过设置空字符串来禁用文件日志
                        session.rtt2uart.jlink.set_log_file("")
                        disabled_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to disable file logging for session {session.session_id}: {e}")
            
            if disabled_count > 0:
                self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging disabled"))
                self._stop_jlink_log_tailer()
                    
        except Exception as e:
            self.append_jlink_log(QCoreApplication.translate("main_window", "Error disabling file logging: %s") % str(e))
    
    def append_jlink_log(self, message):
        """添加JLink日志消息 - 统一的日志显示方法"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        
        # 在GUI线程中更新文本（兼容 QPlainTextEdit）
        if hasattr(self.jlink_log_text, 'appendPlainText'):
            self.jlink_log_text.appendPlainText(formatted_message)
        else:
            self.jlink_log_text.append(formatted_message)
        
        # 自动滚动到底部
        scrollbar = self.jlink_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # 限制日志行数，避免内存占用过多
        document = self.jlink_log_text.document()
        if document.blockCount() > 1000:
            cursor = self.jlink_log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)
            cursor.removeSelectedText()
    
    def get_tab1_content(self, full_content=False):
        """获取TAB 1 (RTT Channel 1) 的当前内容
        
        Args:
            full_content (bool): 如果为True，返回完整内容；如果为False，返回截取的内容
        """
        try:
            # TAB 1对应索引2（索引0是ALL页面，索引1是RTT Channel 0，索引2是RTT Channel 1）
            tab_index = 2
            
            # MDI 架构：从当前活动的 MDI 窗口获取 TAB 1 的内容
            mdi_window = self._get_active_mdi_window()
            if not mdi_window or not hasattr(mdi_window, 'text_edits') or len(mdi_window.text_edits) <= tab_index:
                return ""
            
            tab1_widget = mdi_window.text_edits[tab_index].parent()
            
            # 查找文本框
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
            text_edit = tab1_widget.findChild(QPlainTextEdit)
            if not text_edit:
                text_edit = tab1_widget.findChild(QTextEdit)
            
            if text_edit:
                # 获取文本内容
                if hasattr(text_edit, 'toPlainText'):
                    content = text_edit.toPlainText()
                else:
                    content = text_edit.toHtml()
                
                # 如果要求完整内容，直接返回
                if full_content:
                    return content
                
                # 返回最近的内容（增加字符数限制，确保内容完整）
                max_chars = 3000  # 进一步增加到3000字符
                if len(content) > max_chars:
                    # 获取最后的内容，并尝试从完整行开始
                    recent_content = content[-max_chars:]
                    # 找到第一个换行符，从那里开始
                    first_newline = recent_content.find('\n')
                    if first_newline != -1:
                        recent_content = recent_content[first_newline + 1:]
                    return recent_content
                else:
                    return content
            
            return ""
            
        except Exception as e:
            logger.error(f"Failed to get TAB 1 content: {e}")
            return ""
    
    def _display_tab1_content_to_jlink_log(self, command):
        """将TAB 1的内容显示到JLink日志框中"""
        try:
            # 延迟一小段时间，等待可能的响应数据
            QTimer.singleShot(1000, lambda: self._delayed_display_tab1_content(command))
            
        except Exception as e:
            logger.error(f"Failed to display TAB 1 content to JLink log: {e}")
    
    def _delayed_display_tab1_content(self, command):
        """延迟显示TAB 1内容（等待响应数据）"""
        try:
            # 获取TAB 1的当前内容（使用更大的截取范围）
            tab1_content = self.get_tab1_content()
            
            if tab1_content.strip():
                # 分割内容为行
                lines = tab1_content.strip().split('\n')
                
                # 智能显示逻辑：根据内容长度调整显示行数
                total_lines = len(lines)
                if total_lines <= 10:
                    # 少量内容，全部显示
                    max_lines = total_lines
                elif total_lines <= 30:
                    # 中等内容，显示最近20行
                    max_lines = 20
                else:
                    # 大量内容，显示最近30行
                    max_lines = 30
                
                recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
                
                # 添加到JLink日志
                msg = QCoreApplication.translate('main_window', 'Command sent: %1')
                sent_msg = msg.arg(command)
                self.append_jlink_log(sent_msg)
                msg = QCoreApplication.translate('main_window', 'RTT Channel 1 Response:')
                self.append_jlink_log(msg)
                
                # 如果内容被截取，显示省略提示
                if len(lines) > max_lines:
                    skipped_lines = len(lines) - max_lines
                    self.append_jlink_log(f"   ... ({QCoreApplication.translate('main_window', 'Skipped first')} {skipped_lines} {QCoreApplication.translate('main_window', 'lines')}) ...")
                
                # 统计显示的有效行数
                valid_line_count = 0
                for line in recent_lines:
                    line = line.strip()
                    if line:  # 只显示非空行
                        # 清理ANSI控制字符（如果有的话）
                        import re
                        clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                        # 限制单行长度，避免过长的行
                        if len(clean_line) > 120:
                            clean_line = clean_line[:117] + "..."
                        self.append_jlink_log(f"   {clean_line}")
                        valid_line_count += 1
                
                # 显示统计信息
                if len(lines) > max_lines:
                    # 使用标准的翻译字符串格式
                    msg = QCoreApplication.translate('main_window', '   Showing recent %1 lines / Total %2 lines')
                    sent_msg = msg.arg(valid_line_count).arg(len(lines))
                    self.append_jlink_log(sent_msg)
                else:
                    # 使用正确的Qt字符串格式化方式
                    msg = QCoreApplication.translate('main_window', '   Total %1 lines')
                    sent_msg = msg.arg(valid_line_count)
                    self.append_jlink_log(sent_msg)
                
                self.append_jlink_log("─" * 50)  # 分隔线
            else:
                # 如果没有内容，显示提示信息
                msg = QCoreApplication.translate('main_window', 'Command sent: %1')
                sent_msg = msg.arg(command)
                self.append_jlink_log(sent_msg)
                
                sent_msg = QCoreApplication.translate('main_window', 'RTT Channel 1: No response data')
                self.append_jlink_log(sent_msg)
                self.append_jlink_log("─" * 50)  # 分隔线
                
        except Exception as e:
            logger.error(f"Failed to delayed display TAB 1 content: {e}")

    def eventFilter(self, obj, event):
        """事件过滤器：处理ComboBox的键盘事件和鼠标滚轮事件"""
        if obj == self.ui.cmd_buffer:
            # 处理键盘事件
            if event.type() == event.Type.KeyPress:
                key = event.key()
                
                # 处理上方向键
                if key == Qt.Key_Up:
                    self._navigate_command_history_up()
                    return True  # 消费事件
                    
                # 处理下方向键
                elif key == Qt.Key_Down:
                    self._navigate_command_history_down()
                    return True  # 消费事件
                    
                # 处理其他按键时保存当前输入
                elif key not in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
                    # 如果当前不在历史导航模式，保存输入文本
                    if self.command_history_index == -1:
                        # 延迟保存，让按键先被处理
                        QTimer.singleShot(0, self._save_current_input)
            
            # 🔧 修复：处理鼠标滚轮事件，在ComboBox上滚动时导航命令历史
            elif event.type() == event.Type.Wheel:
                from PySide6.QtCore import QEvent
                wheel_delta = event.angleDelta().y()
                if wheel_delta > 0:
                    # 向上滚动：显示更早的命令
                    self._navigate_command_history_up()
                elif wheel_delta < 0:
                    # 向下滚动：显示更新的命令
                    self._navigate_command_history_down()
                return True  # 消费事件，阻止ComboBox的默认滚轮行为
        
        # 调用父类的事件过滤器
        return super().eventFilter(obj, event)
    
    def _save_current_input(self):
        """保存当前输入的文本"""
        if self.command_history_index == -1:
            self.current_input_text = self.ui.cmd_buffer.currentText()
    
    def _navigate_command_history_up(self):
        """向上导航命令历史"""
        try:
            # 获取命令历史
            history_count = self.ui.cmd_buffer.count()
            if history_count == 0:
                return
            
            # 如果当前不在历史导航模式，保存当前输入并开始导航
            if self.command_history_index == -1:
                self.current_input_text = self.ui.cmd_buffer.currentText()
                self.command_history_index = 0
            else:
                # 向上移动（更早的命令）
                self.command_history_index = min(self.command_history_index + 1, history_count - 1)
            
            # 🔧 修复：阻止信号传播，避免触发activated信号更新"已发送"区域
            self.ui.cmd_buffer.blockSignals(True)
            try:
                # 设置ComboBox显示历史命令（只更新输入框，不触发信号）
                self.ui.cmd_buffer.setCurrentIndex(self.command_history_index)
                # 选中文本，便于继续输入时替换
                line_edit = self.ui.cmd_buffer.lineEdit()
                if line_edit:
                    line_edit.selectAll()
            finally:
                self.ui.cmd_buffer.blockSignals(False)
            
            logger.debug(f"Navigate to history command [{self.command_history_index}]: {self.ui.cmd_buffer.currentText()}")
            
        except Exception as e:
            logger.error(f"Failed to navigate up command history: {e}")
    
    def _navigate_command_history_down(self):
        """向下导航命令历史"""
        try:
            # 如果不在历史导航模式，不处理
            if self.command_history_index == -1:
                return
            
            # 向下移动（更新的命令）
            self.command_history_index -= 1
            
            # 🔧 修复：阻止信号传播，避免触发activated信号更新"已发送"区域
            self.ui.cmd_buffer.blockSignals(True)
            try:
                if self.command_history_index < 0:
                    # 回到当前输入
                    self.command_history_index = -1
                    self.ui.cmd_buffer.setCurrentText(self.current_input_text)
                    logger.debug(f"Return to current input: {self.current_input_text}")
                else:
                    # 设置ComboBox显示历史命令（只更新输入框，不触发信号）
                    self.ui.cmd_buffer.setCurrentIndex(self.command_history_index)
                    logger.debug(f"Navigate to history command [{self.command_history_index}]: {self.ui.cmd_buffer.currentText()}")
                
                # 选中文本，便于继续输入时替换
                line_edit = self.ui.cmd_buffer.lineEdit()
                if line_edit:
                    line_edit.selectAll()
            finally:
                self.ui.cmd_buffer.blockSignals(False)
            
        except Exception as e:
            logger.error(f"Failed to navigate down command history: {e}")
    
    def _reset_command_history_navigation(self):
        """重置命令历史导航状态"""
        self.command_history_index = -1
        self.current_input_text = ""

    def _start_jlink_log_tailer(self, log_file_path):
        """启动定时器，实时读取 JLINK_DEBUG.TXT 的增量内容并显示到窗口。"""
        try:
            self.jlink_log_file_path = log_file_path
            # 初始化偏移
            try:
                self.jlink_log_tail_offset = os.path.getsize(log_file_path)
            except Exception:
                self.jlink_log_tail_offset = 0
            if self.jlink_log_tail_timer is None:
                self.jlink_log_tail_timer = QTimer(self)
                self.jlink_log_tail_timer.timeout.connect(self._poll_jlink_log_tail)
            self.jlink_log_tail_timer.start(TimerInterval.JLINK_LOG_TAIL)
        except Exception as e:
            self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to start log tailer: %s") % str(e))

    def _stop_jlink_log_tailer(self):
        try:
            if self.jlink_log_tail_timer is not None:
                self.jlink_log_tail_timer.stop()
        except Exception:
            pass

    def _poll_jlink_log_tail(self):
        try:
            if not self.jlink_log_file_path:
                return
            path = self.jlink_log_file_path
            if not os.path.exists(path):
                return
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self.jlink_log_tail_offset)
                data = f.read()
                if data:
                    # 控制插入量，避免卡顿
                    if len(data) > 32768:
                        data = data[-32768:]
                    if hasattr(self.jlink_log_text, 'appendPlainText'):
                        self.jlink_log_text.appendPlainText(data)
                    else:
                        self.jlink_log_text.append(data)
                    self.jlink_log_tail_offset = f.tell()
        except Exception:
            pass
    
    def _handle_connection_lost(self):
        """处理JLink连接丢失事件 - 不退出程序，保持界面可用"""
        try:
            self.append_jlink_log(QCoreApplication.translate("main_window", "WARNING: JLink connection lost"))
            
            # 更新连接状态显示
            if self.connection_dialog:
                # 重置连接状态
                self.connection_dialog.start_state = False
                self.connection_dialog.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
                
                # 发送连接断开信号
                self.connection_dialog.connection_disconnected.emit()
                
                # 🔄 立即更新状态栏显示
                self.update_status_bar()
                
                self.append_jlink_log(QCoreApplication.translate("main_window", "Connection state reset, you can:"))
                self.append_jlink_log(QCoreApplication.translate("main_window", "   1. Check hardware connection"))
                self.append_jlink_log(QCoreApplication.translate("main_window", "   2. Click Start button to reconnect"))
                self.append_jlink_log(QCoreApplication.translate("main_window", "   3. Check logs for details"))
                
                # 🎯 显示用户友好的重连提示
                try:
                    from PySide6.QtWidgets import QMessageBox
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle(QCoreApplication.translate("main_window", "JLink Connection Lost"))
                    msg.setText(QCoreApplication.translate("main_window", "JLink connection has been lost"))
                    msg.setInformativeText(QCoreApplication.translate("main_window", "Program will continue running, you can reconnect anytime.\n\nSuggested actions:\n1. Check hardware connection\n2. Click Start button to reconnect"))
                    msg.setStandardButtons(QMessageBox.Ok)
                    msg.setDefaultButton(QMessageBox.Ok)
                    
                    # 使用非阻塞方式显示对话框
                    msg.show()
                    
                except Exception as msg_e:
                    logger.warning(f"Failed to show reconnection dialog: {msg_e}")
            
        except Exception as e:
            self.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error handling connection loss')}: {e}")
            logger.error(f"Error in _handle_connection_lost: {e}")
            
            # 🛡️ 确保即使处理连接丢失时出错，程序也不会退出
            try:
                self.append_jlink_log(QCoreApplication.translate("main_window", "Attempting to recover normal state..."))
                if self.connection_dialog:
                    self.connection_dialog.start_state = False
                    self.update_status_bar()
            except Exception:
                pass  # 静默处理恢复错误
        
    def resizeEvent(self, event):
        # 当窗口大小变化时更新布局大小
        # 由于现在使用了分割器布局，让Qt自动处理大小调整
        super().resizeEvent(event)

    def closeEvent(self, e):
        """程序关闭事件处理 - 断开所有设备并确保所有资源被正确清理"""
        logger.info("Starting program shutdown process...")
        
        # 设置关闭标志，防止在关闭时显示连接对话框
        self._is_closing = True
        
        # 断开所有设备并清理所有MDI窗口
        try:
            # 获取所有MDI子窗口
            sub_windows = self.mdi_area.subWindowList()
            for sub_window in sub_windows:
                try:
                    # sub_window是QMdiSubWindow，需要获取其内部的DeviceMdiWindow
                    mdi_content = sub_window.widget()
                    if isinstance(mdi_content, DeviceMdiWindow):
                        # 断开设备连接
                        if mdi_content.device_session.is_connected:
                            logger.info(f"Disconnecting device: {mdi_content.device_session.device_serial}")
                            mdi_content.device_session.disconnect()
                    
                    # 关闭MDI窗口
                    sub_window.close()
                except Exception as mdi_e:
                    logger.error(f"Failed to close MDI window: {mdi_e}", exc_info=True)
            
            logger.info(f"Closed {len(sub_windows)} MDI window(s)")
        except Exception as ex:
            logger.error(f"Error closing MDI windows: {ex}", exc_info=True)
        
        # 清理所有设备会话
        try:
            session_manager.cleanup_all()
            logger.info("All device sessions cleaned up")
        except Exception as ex:
            logger.error(f"Error cleaning up device sessions: {ex}", exc_info=True)
        
        # 如果处于紧凑模式，先清除窗口置顶标志，确保能正常关闭
        if self.compact_mode:
            try:
                current_flags = self.windowFlags()
                new_flags = current_flags & ~Qt.WindowStaysOnTopHint
                # 确保保留关闭按钮
                new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
                self.setWindowFlags(new_flags)
                logger.info("Cleared window stay-on-top flag for clean shutdown")
            except Exception as ex:
                logger.warning(f"Error clearing window flags: {ex}")
        
        try:
            # 注意：在MDI架构中，所有设备的RTT连接已在上面的循环中断开
            # 不再需要单独处理 self.connection_dialog.rtt2uart
            
            # 1. 停止所有定时器
            self._stop_all_timers()
            
            # 2. 强制终止所有工作线程
            self._force_terminate_threads()
            
            # 3. 清理UI资源
            self._cleanup_ui_resources()
            
            # 4. 清理日志目录
            self._cleanup_log_directories()
            
            # 5. 关闭连接对话框
            if self.connection_dialog:
                self.connection_dialog.hide()
                self.connection_dialog.close()
            
            # 7. 强制终止所有子进程
            self._force_terminate_child_processes()
            
            # 8. 强制退出应用程序
            self._force_quit_application()
            
        except Exception as ex:
            logger.error(f"Error closing program: {ex}")
        finally:
            # 确保窗口关闭
            e.accept()
            logger.info("Program shutdown process completed")
    
    def _stop_all_timers(self):
        """停止所有定时器"""
        try:
            # 停止主窗口的定时器
            if hasattr(self, 'update_timer') and self.update_timer:
                self.update_timer.stop()
            
            # 停止连接对话框中的定时器
            if self.connection_dialog and hasattr(self.connection_dialog, 'worker'):
                worker = self.connection_dialog.worker
                if hasattr(worker, 'buffer_flush_timer') and worker.buffer_flush_timer:
                    worker.buffer_flush_timer.stop()
                    logger.info("Buffer refresh timer stopped")
            
            logger.info("All timers stopped")
        except Exception as e:
            logger.error(f"Error stopping timers: {e}")
    
    def _force_terminate_threads(self):
        """强制终止所有线程"""
        try:
            import time
            
            # 给线程一些时间自然结束（缩短等待时间）
            time.sleep(0.1)
            
            # 检查并强制终止仍在运行的线程
            active_threads = []
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    if not is_dummy_thread(thread):
                        active_threads.append(thread)
                        logger.warning(f"Active thread found: {thread.name} (daemon={thread.daemon})")
            
            if active_threads:
                logger.warning(f"Found {len(active_threads)} active thread(s), attempting to terminate...")
                
                for thread in active_threads:
                    try:
                        # 检查线程是否已经是daemon
                        is_daemon = thread.daemon
                        
                        # 尝试优雅地停止线程（缩短超时时间）
                        thread.join(timeout=0.2)
                        
                        if thread.is_alive():
                            logger.warning(f"Thread {thread.name} failed to stop gracefully (daemon={is_daemon})")
                        else:
                            logger.info(f"Thread {thread.name} stopped successfully")
                    except Exception as e:
                        logger.error(f"Error terminating thread {thread.name}: {e}")
            
            logger.info("Thread cleanup completed")
        except Exception as e:
            logger.error(f"Error force terminating threads: {e}")
    
    def _cleanup_ui_resources(self):
        """清理UI资源"""
        try:
            # MDI 架构：MDI 窗口在关闭时会自动清理
            # 这里只需要清理主窗口的资源
            
            # 清理JLink日志
            if hasattr(self, 'jlink_log_text'):
                self.jlink_log_text.clear()
            
            logger.info("UI resource cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning UI resources: {e}")
    
    def _cleanup_log_directories(self):
        """清理日志目录 - MDI架构：清理所有设备会话的日志目录"""
        try:
            # MDI架构：清理所有设备会话的日志目录
            for session in session_manager.get_all_sessions():
                if session.rtt2uart and session.rtt2uart.log_directory:
                    log_directory = session.rtt2uart.log_directory
                    if log_directory and os.path.exists(log_directory):
                        if not os.listdir(log_directory):
                            shutil.rmtree(log_directory)
                            logger.info(f"Deleted empty log directory: {log_directory}")
            
        except Exception as e:
            logger.error(f"Error cleaning log directories: {e}")
    
    def _force_terminate_child_processes(self):
        """强制终止所有子进程"""
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            
            if children:
                logger.info(f"Found {len(children)} child processes, starting cleanup...")
                
                for child in children:
                    try:
                        logger.info(f"Terminating child process: PID={child.pid}, Name={child.name()}")
                        child.terminate()
                        child.wait(timeout=2)
                        
                        if child.is_running():
                            logger.warning(f"Force killing child process: PID={child.pid}")
                            child.kill()
                            child.wait(timeout=1)
                            
                    except psutil.NoSuchProcess:
                        # 进程已经不存在
                        pass
                    except Exception as e:
                        logger.error(f"Error terminating child process: {e}")
                
                logger.info("Child process cleanup completed")
            
        except Exception as e:
            logger.error(f"Error force terminating child processes: {e}")
    
    
    def _force_quit_application(self):
        """强制退出应用程序 - 确保进程完全终止"""
        try:
            logger.info("Force quitting application...")
            
            # 1. 先尝试终止所有子进程
            try:
                current_process = psutil.Process()
                children = current_process.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                    except:
                        pass
            except:
                pass
            
            # 2. 获取应用程序实例并退出
            app = QApplication.instance()
            if app:
                # 处理所有待处理事件
                app.processEvents()
                
                # 设置退出代码并立即退出
                app.quit()
                
                # 如果quit()不起作用，延迟强制退出
                QTimer.singleShot(TimerInterval.FORCE_QUIT, lambda: os._exit(0))
            else:
                # 没有应用实例，直接退出
                os._exit(0)
            
        except Exception as e:
            logger.error(f"Error force quitting application: {e}")
            # 最后的手段：直接退出进程
            try:
                os._exit(0)
            except:
                sys.exit(0)

    # ========== 旧代码已删除：switchPage 方法 ==========
    # MDI 架构中，每个 DeviceMdiWindow 有自己的标签页切换逻辑
    # 不再需要主窗口的 switchPage 方法
    # ====================================================
    # @Slot(int)
    # def switchPage(self, index):
    #     # 此方法已废弃，MDI 架构中由 DeviceMdiWindow 处理标签页切换
    #     pass


    @Slot()
    def handleBufferUpdate(self):
        # 更新数据时间戳（用于自动重连监控）
        self._update_data_timestamp()
        
        # MDI 架构：字体更新由 DeviceMdiWindow 处理
        # 这里不需要刷新，因为字体已经在 _update_all_tabs_font 中更新了
        pass
        
    def on_pushButton_clicked(self):
        current_text = self.ui.cmd_buffer.currentText()
        # 发送指令：界面读取的命令文本 + 换行
        cmd_text = current_text + '\n'
        # 发送前按所选编码转换
        try:
            enc = self.connection_dialog.config.get_text_encoding() if self.connection_dialog else 'gbk'
        except Exception:
            enc = 'gbk'
        out_bytes = cmd_text.encode(enc, errors='ignore')
        
        # MDI 架构：使用当前活动设备的 session
        session = self._get_active_device_session()
        if session and session.rtt2uart and session.rtt2uart.jlink:
            bytes_written = session.rtt2uart.jlink.rtt_write(0, out_bytes)
            session.rtt2uart.write_bytes0 = bytes_written
        else:
            bytes_written = 0
            logger.warning("No active device session for sending command")
            
        # 检查发送是否成功
        if(bytes_written == len(out_bytes)):
            # 🔧 修复：正确清空ComboBox输入框
            try:
                self.ui.cmd_buffer.clearEditText()
                self.ui.cmd_buffer.setCurrentText("")  # 确保输入框完全清空
                logger.debug(f"Command sent successfully, input cleared: {current_text}")
            except Exception as e:
                logger.error(f"Failed to clear input box: {e}")
            
            # 重置命令历史导航状态
            self._reset_command_history_navigation()
                
            # 使用格式化字符串确保翻译能被正确提取
            sent_msg = QCoreApplication.translate("main_window", "Sent:\t%s") % cmd_text[:len(cmd_text) - 1]
            self.ui.sent.setText(sent_msg)
            
            # MDI 架构：在当前活动的 MDI 窗口中设置高亮
            mdi_window = self._get_active_mdi_window()
            if mdi_window and hasattr(mdi_window, 'text_edits') and len(mdi_window.text_edits) > 2:
                # 在 channel 2 (应答界面) 设置高亮关键字
                # 注意：MDI 架构中每个设备有自己的高亮器
                pass  # TODO: 实现 MDI 窗口的高亮功能
                    
            # 📋 新功能：命令发送成功后，将TAB 1的输出内容展示到JLink日志框
            #self._display_tab1_content_to_jlink_log(current_text)
                    
            # 智能命令历史管理：防止重复，只调整顺序
            self._update_command_history(current_text)
            
            self.ui.cmd_buffer.clearEditText()
            self.ui.cmd_buffer.setCurrentText("")  # 确保输入框完全清空
        else:
            # 发送失败的处理
            logger.warning(f"Command send failed: expected {len(out_bytes)} bytes, actually sent {bytes_written} bytes")
            self.ui.sent.setText(QCoreApplication.translate("main_window", "Send Failed"))

    def on_dis_connect_clicked(self):
        """F3 - 断开当前激活设备的连接"""
        try:
            # 获取当前激活的设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("No active device session to disconnect")
                return
            
            logger.info(f"Disconnecting device: {session.get_display_name()}")
            self.append_jlink_log(QCoreApplication.translate("main_window", "Disconnecting device: %s") % session.get_display_name())
            
            # 标记为手动断开，停止自动重连定时器
            self.manual_disconnect = True
            if hasattr(self, 'data_check_timer'):
                self.data_check_timer.stop()
                logger.info("Auto reconnect timer stopped due to manual disconnect")
            
            # 断开该设备的连接
            if session.rtt2uart:
                try:
                    session.rtt2uart.stop()
                    logger.info(f"RTT stopped for device: {session.get_display_name()}")
                    self.append_jlink_log(QCoreApplication.translate("main_window", "RTT stopped for device: %s") % session.get_display_name())
                except Exception as e:
                    logger.error(f"Failed to stop RTT: {e}")
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to stop RTT: %s") % str(e))
            
            session.is_connected = False
            logger.info(f"Device disconnected: {session.get_display_name()}")
            self.append_jlink_log(QCoreApplication.translate("main_window", "Device disconnected: %s") % session.get_display_name())
            
            # 检查是否还有其他连接的设备，如果没有则禁用 RTT Chain Info 菜单
            if hasattr(self, 'rtt_info_action'):
                has_connected = any(s.is_connected for s in self.device_sessions if s.rtt2uart)
                self.rtt_info_action.setEnabled(has_connected)
            
        except Exception as e:
            logger.error(f"Failed to disconnect device: {e}", exc_info=True)

    def on_re_connect_clicked(self):
        """F2 - 多设备管理入口：选择设备进行连接或重新连接"""
        try:
            # 重新连接时清除手动断开标记
            self.manual_disconnect = False
            
            # 创建新的连接对话框用于选择设备
            from main_window import ConnectionDialog
            
            # 创建临时连接对话框
            temp_dialog = ConnectionDialog(self)
            temp_dialog.setWindowTitle(QCoreApplication.translate("main_window", "Select Device to Connect"))
            
            # 🔑 关键修复：只在重连同一设备时重用 JLink 对象
            # 不同设备需要不同的 JLink 对象，因为 pylink 不支持一个 JLink 对象同时连接多个设备
            # 注意：这个检查必须在用户选择设备之前进行，所以我们先不做任何操作
            # 实际的 JLink 对象重用会在 on_device_selected() 回调中处理
            
            def on_device_selected():
                try:
                    if not temp_dialog.rtt2uart:
                        return
                    
                    rtt = temp_dialog.rtt2uart
                    device_serial = getattr(rtt, '_connect_para', 'Unknown')
                    
                    # 检查该设备是否已经存在会话
                    existing_session = None
                    for session in self.device_sessions:
                        if session.device_serial == device_serial:
                            existing_session = session
                            break
                    
                    if existing_session:
                        # 设备已存在，重新连接
                        logger.info(f"Device {device_serial} exists, reconnecting...")
                        self.append_jlink_log(QCoreApplication.translate("main_window", "Device %s exists, reconnecting...") % device_serial)
                        
                        # 注意：JLink 对象重用已经在 ConnectionDialog.start() 中处理了
                        # 保存旧的字节计数
                        old_read_bytes0 = 0
                        old_read_bytes1 = 0
                        old_write_bytes0 = 0
                        if existing_session.rtt2uart:
                            old_read_bytes0 = existing_session.rtt2uart.read_bytes0
                            old_read_bytes1 = existing_session.rtt2uart.read_bytes1
                            old_write_bytes0 = existing_session.rtt2uart.write_bytes0
                            logger.info(f"保存旧字节计数: read0={old_read_bytes0}, read1={old_read_bytes1}, write0={old_write_bytes0}")
                        
                        # 先断开旧连接
                        if existing_session.rtt2uart and existing_session.is_connected:
                            try:
                                logger.info(f"Stopping old RTT connection for device {device_serial}")
                                existing_session.rtt2uart.stop()
                                # 注意：不关闭 JLink，因为新的 rtt2uart 会重用它
                                logger.info(f"Old RTT stopped, JLink will be reused")
                            except Exception as e:
                                logger.error(f"Failed to stop old RTT: {e}")
                        
                        # 更新会话的连接信息
                        existing_session.rtt2uart = rtt
                        existing_session.connection_dialog = temp_dialog
                        existing_session.is_connected = True
                        
                        # 恢复字节计数
                        rtt.read_bytes0 = old_read_bytes0
                        rtt.read_bytes1 = old_read_bytes1
                        rtt.write_bytes0 = old_write_bytes0
                        logger.info(f"✅ 恢复字节计数: read0={old_read_bytes0}, read1={old_read_bytes1}, write0={old_write_bytes0}")
                        self.append_jlink_log(QCoreApplication.translate("main_window", "Restored byte count: %s bytes") % old_read_bytes0)
                        
                        # 不清空buffer,保持累计
                        logger.info(f"✅ Keeping existing buffers for device {device_serial}")
                        self.append_jlink_log(QCoreApplication.translate("main_window", "Reconnecting without clearing data"))
                        
                        # 重置UI显示偏移量,确保新数据立即显示
                        if existing_session.mdi_window:
                            # 获取旧worker的colored_buffer长度作为新的起点
                            old_worker = getattr(existing_session.connection_dialog, 'worker', None) if existing_session.connection_dialog else None
                            if old_worker:
                                for ch in range(len(existing_session.mdi_window.last_display_lengths)):
                                    # 设置为当前buffer长度,这样新数据会立即显示
                                    existing_session.mdi_window.last_display_lengths[ch] = old_worker.colored_buffer_lengths[ch]
                                logger.info(f"✅ Reset UI display offsets to current buffer lengths: {existing_session.mdi_window.last_display_lengths[:3]}")
                                self.append_jlink_log(QCoreApplication.translate("main_window", "Reset UI display offsets"))
                        
                        # 启动RTT数据读取
                        try:
                            rtt.start()
                            logger.info(f"✅ RTT data reading started for device {device_serial}")
                            self.append_jlink_log(QCoreApplication.translate("main_window", "RTT data reading started for device %s") % device_serial)
                        except Exception as e:
                            logger.error(f"Failed to start RTT: {e}", exc_info=True)
                            self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to start RTT: %s") % str(e))
                        
                        # 重新启动MDI窗口的更新定时器
                        if existing_session.mdi_window:
                            if hasattr(existing_session.mdi_window, 'update_timer'):
                                existing_session.mdi_window.update_timer.start(TimerInterval.MDI_WINDOW_UPDATE)
                                logger.info(f"✅ MDI window update timer restarted for device {device_serial}")
                        
                        # 激活该设备的MDI窗口(保持原有大小,不改变窗口状态)
                        if existing_session.mdi_window and existing_session.mdi_window.mdi_sub_window:
                            self.mdi_area.setActiveSubWindow(existing_session.mdi_window.mdi_sub_window)
                            logger.info("Reconnected: Activated existing MDI window without changing size")
                        
                        # 设置为当前会话
                        self.current_session = existing_session
                        session_manager.set_active_session(existing_session)
                        
                        # 启用 RTT Chain Info 菜单
                        if hasattr(self, 'rtt_info_action'):
                            self.rtt_info_action.setEnabled(True)
                        
                        logger.info(f"✅ Device {device_serial} reconnected")
                        return
                    else:
                        # 新设备，创建新会话和MDI窗口
                        # 查找设备索引
                        device_index = None
                        if hasattr(temp_dialog, 'available_jlinks'):
                            for idx, dev in enumerate(temp_dialog.available_jlinks):
                                if dev.get('serial') == device_serial:
                                    device_index = idx
                                    logger.info(f"Found device index: {device_index} for serial {device_serial}")
                                    break
                            if device_index is None:
                                logger.warning(f"Device index not found for serial {device_serial}, will display without index")
                        
                        device_info = {
                            'serial': device_serial,
                            'product_name': getattr(rtt, 'device_info', 'Unknown'),
                            'connection': 'USB',
                            'index': device_index
                        }
                        
                        session = DeviceSession(device_info)
                        session.rtt2uart = rtt
                        session.connection_dialog = temp_dialog
                        session.is_connected = True
                        
                        # 创建MDI子窗口并添加内容(包含单窗口最大化逻辑)
                        self._create_device_session_from_connection(session)
                        
                        # 设置为当前会话
                        self.current_session = session
                        session_manager.set_active_session(session)
                        self.connection_dialog = temp_dialog
                        
                        logger.info(f"✅ New device {device_serial} connected with MDI window")
                        
                except Exception as e:
                    logger.error(f"Failed to handle device selection: {e}", exc_info=True)
            
            temp_dialog.connection_established.connect(on_device_selected)
            temp_dialog.show()
            temp_dialog.raise_()
            temp_dialog.activateWindow()
            
            logger.info("F2 - Device selection dialog opened")
            
        except Exception as e:
            logger.error(f"Failed to open device selection: {e}", exc_info=True)
    
    def _on_auto_reconnect_changed(self, state):
        """自动重连复选框状态改变"""
        enabled = (state == Qt.CheckState.Checked.value) if hasattr(Qt.CheckState, 'Checked') else (state == 2)
        logger.debug(f"[AUTO-RECONNECT] State changed: state={state}, enabled={enabled}")
        
        # 保存到配置（🔑 只在UI初始化完成后保存）
        if self.connection_dialog and self._ui_initialization_complete:
            self.connection_dialog.config.set_auto_reconnect_on_no_data(enabled)
            self.connection_dialog.config.save_config()
            logger.debug("[AUTO-RECONNECT] Configuration saved to connection dialog")
        
        # MDI架构：获取活动设备会话并检查连接状态
        session = self._get_active_device_session()
        session_connected = False
        
        if session:
            session_connected = hasattr(session, 'is_connected') and session.is_connected
            logger.debug(f"[AUTO-RECONNECT] Active session: connected={session_connected}")
        else:
            logger.debug("[AUTO-RECONNECT] No active device session")
        
        # 根据启用状态和连接状态启动或停止监控定时器
        if enabled and session and session_connected:
            # 初始化last_data_time
            self.last_data_time = time.time()
            logger.debug(f"[AUTO-RECONNECT] Initialized last_data_time: {self.last_data_time:.2f}")
            # 启动定时器，使用DATA_CHECK间隔
            self.data_check_timer.start(TimerInterval.DATA_CHECK)
            logger.info("[AUTO-RECONNECT] Auto-reconnect monitoring enabled")
            # 显示启动状态到JLink日志
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto-reconnect monitoring started"))
        else:
            # 停止定时器
            self.data_check_timer.stop()
            logger.info(f"[AUTO-RECONNECT] Auto-reconnect monitoring disabled: enabled={enabled}, session_connected={session_connected}")
            # 显示停止状态到JLink日志
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto-reconnect monitoring stopped"))
    
    def _on_reconnect_timeout_changed(self, text):
        """超时时间文本框改变"""
        try:
            timeout = int(text)
            if timeout > 0:
                # 保存到配置（🔑 只在UI初始化完成后保存）
                if self.connection_dialog and self._ui_initialization_complete:
                    self.connection_dialog.config.set_auto_reconnect_timeout(timeout)
                    self.connection_dialog.config.save_config()
        except ValueError:
            pass  # 忽略无效输入
    
    def _toggle_auto_reconnect(self):
        """F8快捷键切换自动重连"""
        if hasattr(self.ui, 'auto_reconnect_checkbox'):
            current_state = self.ui.auto_reconnect_checkbox.isChecked()
            self.ui.auto_reconnect_checkbox.setChecked(not current_state)
    
    def _check_data_timeout(self):
        """检查数据超时并执行自动重连"""
        # 跳过手动断开的情况，但不要停止定时器
        if self.manual_disconnect:
            logger.debug("[AUTO-RECONNECT] Skipping timeout check: manual disconnect active")
            return
        
        # 获取活动设备会话
        session = self._get_active_device_session()
        if not session:
            logger.debug("[AUTO-RECONNECT] Skipping timeout check: no active device session")
            return
        
        # 获取RTT对象并检查连接状态
        rtt_obj = session.rtt2uart if hasattr(session, 'rtt2uart') else None
        session_connected = hasattr(session, 'is_connected') and session.is_connected
        rtt_connected = hasattr(rtt_obj, 'is_connected') and rtt_obj.is_connected if rtt_obj else False
        
        # 获取超时设置
        try:
            timeout = int(self.ui.reconnect_timeout_edit.text())
        except:
            timeout = 60
        
        # 检查是否超时
        current_time = time.time()
        time_since_last_data = current_time - self.last_data_time if self.last_data_time > 0 else 0
        
        # 增加详细调试日志
        logger.debug(f"[AUTO-RECONNECT] Timeout check: session_connected={session_connected}, "
                   f"rtt_connected={rtt_connected}, last_data_time={self.last_data_time:.2f}, "
                   f"current={current_time:.2f}, elapsed={time_since_last_data:.2f}s, timeout={timeout}s")
        
        # 重连条件：
        # 1. 有数据时间戳
        # 2. 无数据时间超过设置的超时时间
        should_reconnect = False
        reconnect_reason = ""
        
        if self.last_data_time > 0 and time_since_last_data > timeout:
            should_reconnect = True
            reconnect_reason = f"No data received for {timeout} seconds"
        
        if should_reconnect:
            logger.warning(f"[AUTO-RECONNECT] {reconnect_reason}, auto reconnecting...")
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "No data timeout, automatically reconnecting..."))
            
            # 重置时间戳，避免重复触发
            self.last_data_time = current_time
            
            # 执行自动重连
            try:
                self._perform_auto_reconnect()
                logger.info("[AUTO-RECONNECT] Reconnection process initiated")
            except Exception as e:
                logger.error(f"[AUTO-RECONNECT] Failed to initiate reconnection: {e}")
    
    def _perform_auto_reconnect(self):
        """执行自动重连（不重置文件夹）- MDI架构：针对活动设备会话"""
        logger.info("[AUTO-RECONNECT] Starting auto-reconnection process")
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("[AUTO-RECONNECT] Cannot reconnect: no active device session")
                return
            
            # 检查rtt2uart属性
            if not hasattr(session, 'rtt2uart') or not session.rtt2uart:
                logger.warning("[AUTO-RECONNECT] Cannot reconnect: session missing rtt2uart object")
                return
            
            # 使用rtt2uart的重启方法，不会重置日志文件夹
            rtt_obj = session.rtt2uart
            logger.debug("[AUTO-RECONNECT] Got RTT object, proceeding with reconnection")
            
            # 停止RTT连接
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Stopping RTT connection for reconnection..."))
            
            try:
                rtt_obj.stop(keep_folder=True)  # 保留日志文件夹
                logger.info("[AUTO-RECONNECT] RTT connection stopped successfully")
            except Exception as stop_error:
                logger.error(f"[AUTO-RECONNECT] Failed to stop RTT connection: {stop_error}")
                if hasattr(self, 'append_jlink_log'):
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to stop RTT connection: %s") % str(stop_error))
                # 即使停止失败，仍然尝试启动，可能会恢复连接
            
            # 等待停止完成后重新启动
            delay = TimerInterval.AUTO_RECONNECT
            logger.info(f"[AUTO-RECONNECT] Waiting {delay}ms before starting reconnection")
            QTimer.singleShot(delay, self._auto_reconnect_start)
            
        except Exception as e:
            logger.error(f"[AUTO-RECONNECT] Reconnection process failed: {e}", exc_info=True)
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect process failed: %s") % str(e))
    
    def _auto_reconnect_start(self):
        """自动重连 - 启动连接 - MDI架构：针对活动设备会话"""
        logger.info("[AUTO-RECONNECT] Attempting to restart RTT connection")
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("[AUTO-RECONNECT] Cannot restart: no active device session")
                return
            
            # 检查rtt2uart属性
            if not hasattr(session, 'rtt2uart') or not session.rtt2uart:
                logger.warning("[AUTO-RECONNECT] Cannot restart: session missing rtt2uart object")
                return
            
            # 重新启动RTT连接
            rtt_obj = session.rtt2uart
            logger.debug("[AUTO-RECONNECT] Got RTT object for restart")
            
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Restarting RTT connection..."))
            
            # 尝试启动RTT连接
            try:
                rtt_obj.start()
                logger.info("[AUTO-RECONNECT] RTT connection restarted successfully")
                
                # 重置数据时间戳
                self.last_data_time = time.time()
                logger.debug(f"[AUTO-RECONNECT] Reset last_data_time: {self.last_data_time:.2f}")
                
                # 确保定时器仍然运行
                if not self.data_check_timer.isActive():
                    self.data_check_timer.start(TimerInterval.DATA_CHECK)
                    logger.debug("[AUTO-RECONNECT] Re-started data check timer")
                
                # 显示完成消息
                logger.info("[AUTO-RECONNECT] Auto-reconnection completed successfully")
                if hasattr(self, 'append_jlink_log'):
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect completed successfully"))
                    
            except Exception as start_error:
                logger.error(f"[AUTO-RECONNECT] Failed to start RTT connection: {start_error}", exc_info=True)
                if hasattr(self, 'append_jlink_log'):
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to restart RTT connection: %s") % str(start_error))
                # 即使启动失败，也尝试重新初始化时间戳和定时器，为下次重连做准备
                self.last_data_time = time.time()
                if not self.data_check_timer.isActive():
                    self.data_check_timer.start(TimerInterval.DATA_CHECK)
                    
        except Exception as e:
            logger.error(f"[AUTO-RECONNECT] Reconnection startup process failed: {e}", exc_info=True)
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect startup process failed: %s") % str(e))
    
    def _update_data_timestamp(self):
        """更新数据时间戳（在收到数据时调用）"""
        current_time = time.time()
        previous_time = self.last_data_time
        
        # 只在第一次或超过5秒没更新时记录日志（避免日志刷屏）
        if previous_time == 0:
            logger.info("[AUTO-RECONNECT] Initial data timestamp set")
        elif (current_time - previous_time) > 5:
            logger.debug(f"[AUTO-RECONNECT] Data timestamp updated: {previous_time:.2f} -> {current_time:.2f}")
        
        # 检查数据接收是否恢复
        if hasattr(self, 'is_auto_reconnect_enabled') and self.is_auto_reconnect_enabled():
            # 检查上次数据接收是否已经超时
            timeout = self._get_auto_reconnect_timeout()
            if timeout > 0 and (previous_time > 0) and (current_time - previous_time) > timeout:
                logger.info("[AUTO-RECONNECT] Data reception restored after potential timeout")
        
        self.last_data_time = current_time

    def _on_mdi_subwindow_activated(self, sub_window):
        """MDI 子窗口激活时的回调 - 同步暂停/恢复状态等"""
        if not sub_window:
            return
        
        try:
            # 获取激活的设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart:
                return
            
            # 同步暂停/恢复刷新状态
            is_paused = session.rtt2uart.ui_refresh_paused
            
            # 更新UI单选按钮状态
            if hasattr(self.ui, 'radioButton_pause_refresh') and hasattr(self.ui, 'radioButton_resume_refresh'):
                if is_paused:
                    self.ui.radioButton_pause_refresh.setChecked(True)
                else:
                    self.ui.radioButton_resume_refresh.setChecked(True)
            
            logger.debug(f"MDI window activated: {session.get_display_name()}, paused={is_paused}")
            
        except Exception as e:
            logger.error(f"Failed to sync state on MDI activation: {e}", exc_info=True)
    
    def pause_ui_refresh(self):
        """F5 暂停UI刷新 - 在rtt2uart中暂停数据处理"""
        try:
            # 获取当前激活的设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("No active device session to pause refresh")
                return
            
            # 设置rtt2uart的暂停标志
            if session.rtt2uart:
                session.rtt2uart.ui_refresh_paused = True
                logger.info(QCoreApplication.translate("main_window", "Device %s UI refresh paused") % session.get_display_name())
                self.statusBar().showMessage(
                    QCoreApplication.translate("main_window", "UI refresh paused - Device %s") % session.get_display_name(), 
                    3000
                )
                
                # 更新UI单选按钮状态
                if hasattr(self.ui, 'radioButton_pause_refresh'):
                    self.ui.radioButton_pause_refresh.setChecked(True)
            else:
                logger.warning("No RTT connection to pause")
                
        except Exception as e:
            logger.error(f"Failed to pause UI refresh: {e}", exc_info=True)
    
    def resume_ui_refresh(self):
        """F6 恢复UI刷新 - 在rtt2uart中恢复数据处理"""
        try:
            # 获取当前激活的设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("No active device session to resume refresh")
                return
            
            # 恢复rtt2uart的刷新并处理暂停期间的数据
            if session.rtt2uart:
                # 先清除暂停标志，这样flush_paused_data处理的数据会正常发送
                session.rtt2uart.ui_refresh_paused = False
                
                # 一次性处理暂停期间积累的所有数据（仅在非关闭状态下）
                if not self._is_closing:
                    session.rtt2uart.flush_paused_data()
                else:
                    # 关闭时直接清空，不处理
                    session.rtt2uart.clear_paused_data()
                
                logger.info(QCoreApplication.translate("main_window", "Device %s UI refresh resumed") % session.get_display_name())
                self.statusBar().showMessage(
                    QCoreApplication.translate("main_window", "UI refresh resumed - Device %s") % session.get_display_name(), 
                    3000
                )
                
                # 更新UI单选按钮状态
                if hasattr(self.ui, 'radioButton_resume_refresh'):
                    self.ui.radioButton_resume_refresh.setChecked(True)
            else:
                logger.warning("No RTT connection to resume")
                
        except Exception as e:
            logger.error(f"Failed to resume UI refresh: {e}", exc_info=True)
    
    def on_clear_clicked(self):
        """F4清空当前TAB - 操作当前激活的MDI设备窗口"""
        try:
            # 获取当前激活的设备会话
            session = self._get_active_device_session()
            if not session or not session.mdi_window:
                logger.warning("No active device session to clear")
                return
            
            mdi_window = session.mdi_window
            current_index = mdi_window.tab_widget.currentIndex()
            logger.debug(f"Clearing TAB {current_index} for device {session.get_display_name()}")
            
            # 1. 清空UI显示
            if current_index < len(mdi_window.text_edits):
                text_edit = mdi_window.text_edits[current_index]
                text_edit.clear()
                logger.debug(f"Cleared TAB {current_index} UI display")
            else:
                logger.warning(f"TAB {current_index} text editor not found")
                return
            
            # 2. 清空数据缓冲区
            if session.connection_dialog and hasattr(session.connection_dialog, 'worker') and session.connection_dialog.worker:
                worker = session.connection_dialog.worker
                try:
                    # 清空主缓冲区
                    if current_index < len(worker.buffers):
                        if hasattr(worker.buffers[current_index], 'clear'):
                            worker.buffers[current_index].clear()
                        else:
                            worker.buffers[current_index] = []
                        worker.buffer_lengths[current_index] = 0
                        
                    # 清空彩色缓冲区
                    if hasattr(worker, 'colored_buffers') and current_index < len(worker.colored_buffers):
                        if hasattr(worker.colored_buffers[current_index], 'clear'):
                            worker.colored_buffers[current_index].clear()
                        else:
                            worker.colored_buffers[current_index] = []
                        worker.colored_buffer_lengths[current_index] = 0
                        
                    # 清空HTML缓冲区
                    if hasattr(worker, 'html_buffers') and current_index < len(worker.html_buffers):
                        worker.html_buffers[current_index] = ""
                        
                    # 重置显示长度
                    if hasattr(worker, 'display_lengths') and current_index < len(worker.display_lengths):
                        worker.display_lengths[current_index] = 0
                        
                    # 重置MDI窗口的显示长度
                    if hasattr(mdi_window, 'last_display_lengths') and current_index < len(mdi_window.last_display_lengths):
                        mdi_window.last_display_lengths[current_index] = 0
                        
                    logger.debug(f"Cleared TAB {current_index} data buffer")
                    
                except Exception as e:
                    logger.error(f"Failed to clear TAB {current_index} data buffer: {e}")
            else:
                logger.warning("Cannot access Worker, only cleared UI display")
                
            logger.info(f"TAB {current_index} clear completed for device {session.get_display_name()}")
            
        except Exception as e:
            logger.error(f"Failed to clear TAB: {e}", exc_info=True)

    def on_openfolder_clicked(self):
        """打开日志文件夹 - 复用同一个窗口跳转到新文件夹 - MDI架构：打开活动设备的日志目录"""
        try:
            import pathlib
            import subprocess
            
            # MDI架构：获取活动设备会话的日志目录
            session = self._get_active_device_session()
            if session and session.rtt2uart:
                target_dir = str(session.rtt2uart.log_directory)  # 🔑 确保转换为字符串
            else:
                # 在断开状态下打开默认的日志目录
                desktop_path = pathlib.Path.home() / "Desktop/XexunRTT_Log"
                if desktop_path.exists():
                    target_dir = str(desktop_path)
                else:
                    # 如果日志目录不存在，打开桌面
                    target_dir = str(pathlib.Path.home() / "Desktop")
            
            # Windows: 尝试复用已有的资源管理器窗口
            if sys.platform == "win32":
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("Shell.Application")
                    
                    # 初始化窗口ID跟踪
                    if not hasattr(self, '_my_explorer_window_id'):
                        self._my_explorer_window_id = None
                    
                    # 遍历所有打开的资源管理器窗口
                    windows = shell.Windows()
                    navigated = False
                    my_window = None
                    
                    # 🔑 尝试找到由本程序打开的窗口
                    if self._my_explorer_window_id is not None:
                        logger.debug(f"[F1] Looking for tracked window (HWND={self._my_explorer_window_id})")
                        logger.debug(f"[F1] Found {len(windows)} explorer windows")
                        for window in windows:
                            try:
                                # 通过HWND(窗口句柄)来识别窗口
                                if hasattr(window, 'HWND'):
                                    current_hwnd = window.HWND
                                    logger.debug(f"[F1] Checking window HWND={current_hwnd}")
                                    if current_hwnd == self._my_explorer_window_id:
                                        my_window = window
                                        logger.debug(f"[F1] Found matching window!")
                                        break
                            except Exception as e:
                                logger.debug(f"[F1] Error checking window: {e}")
                                continue
                        
                        if not my_window:
                            logger.warning(f"[F1] Tracked window (HWND={self._my_explorer_window_id}) not found in {len(windows)} windows, will open new one")
                            self._my_explorer_window_id = None
                    
                    # 如果找到了我们的窗口，复用它
                    if my_window:
                        try:
                            my_window.Navigate(target_dir)
                            
                            # 🔑 强制激活窗口到前台
                            try:
                                import win32gui
                                import win32con
                                hwnd = self._my_explorer_window_id
                                
                                # 如果窗口最小化，先还原
                                if win32gui.IsIconic(hwnd):
                                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                
                                # 激活窗口到前台
                                win32gui.SetForegroundWindow(hwnd)
                                logger.debug(f"[F1] Activated window to foreground (HWND={hwnd})")
                            except Exception as e:
                                logger.warning(f"[F1] Failed to activate window: {e}")
                                # 尝试使用COM属性作为备选
                                try:
                                    my_window.Visible = True
                                except:
                                    pass
                            
                            navigated = True
                            logger.info(f"Reused tracked window (HWND={self._my_explorer_window_id}), navigated to: {target_dir}")
                            return
                        except Exception as e:
                            logger.warning(f"Tracked window is invalid: {e}, will open new one")
                            self._my_explorer_window_id = None
                    
                    # 如果没找到我们的窗口，打开新窗口并记录其ID
                    if not navigated:
                        logger.info("Opening new explorer window and tracking it")
                        os.startfile(target_dir)
                        
                        # 等待窗口打开
                        import time
                        time.sleep(0.5)
                        
                        # 尝试找到新打开的窗口
                        windows = shell.Windows()
                        logger.debug(f"[F1] After opening, found {len(windows)} windows, looking for: {target_dir}")
                        
                        # 先记录所有窗口的最新HWND，选择最新的（通常是最后一个）
                        latest_hwnd = None
                        target_path_normalized = target_dir.replace('\\', '/').lower()
                        
                        for window in windows:
                            try:
                                current_folder = window.LocationURL
                                current_hwnd = window.HWND if hasattr(window, 'HWND') else None
                                logger.debug(f"[F1] Window HWND={current_hwnd}, LocationURL={current_folder}")
                                
                                # 检查是否是我们刚打开的文件夹
                                if current_folder and target_path_normalized in current_folder.lower():
                                    latest_hwnd = current_hwnd
                                    logger.debug(f"[F1] Found matching window! HWND={latest_hwnd}")
                            except Exception as e:
                                logger.debug(f"[F1] Error checking window: {e}")
                                continue
                        
                        if latest_hwnd:
                            self._my_explorer_window_id = latest_hwnd
                            logger.info(f"[F1] Tracked new window (HWND={self._my_explorer_window_id})")
                        else:
                            logger.warning(f"[F1] Failed to find newly opened window for: {target_dir}")
                        
                except ImportError:
                    # 如果没有 win32com，回退到普通方式
                    logger.warning("win32com not available, using fallback method")
                    os.startfile(target_dir)
                except Exception as e:
                    logger.warning(f"Failed to use COM automation: {e}, using fallback")
                    os.startfile(target_dir)
            
            # macOS - Finder 默认只打开一个窗口，自动复用
            elif sys.platform == "darwin":
                subprocess.run(["open", target_dir])
                logger.info(f"Opened/navigated folder (macOS): {target_dir}")
            
            # Linux - 大多数文件管理器会复用窗口
            else:
                subprocess.run(["xdg-open", target_dir])
                logger.info(f"Opened/navigated folder (Linux): {target_dir}")
            
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")
            # 显示错误消息
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Error"), QCoreApplication.translate("main_window", "Cannot open folder:\n{}").format(e))

    def on_open_config_folder_clicked(self):
        """Open config folder - cross-platform compatible version"""
        try:
            import pathlib
            import subprocess
            
            # Get config directory path
            config_dir_path = pathlib.Path(config_manager.config_dir)
            target_dir = str(config_dir_path)
            
            # Ensure config directory exists
            if not config_dir_path.exists():
                config_dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created config directory: {target_dir}")
            
            # Cross-platform open folder
            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", target_dir])
            elif sys.platform == "win32":  # Windows
                os.startfile(target_dir)
            else:  # Linux
                subprocess.run(["xdg-open", target_dir])
                
            logger.info(f"Opened config folder: {target_dir}")
            
        except Exception as e:
            logger.error(f"Failed to open config folder: {e}")
            # Show error message
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Error"), QCoreApplication.translate("main_window", "Cannot open config folder:\n{}").format(e))

    def show_rtt_chain_info(self):
        """显示 RTT 通道信息对话框 - 使用表格显示"""
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart:
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("main_window", "No Connection"),
                    QCoreApplication.translate("main_window", "Please connect to a device first.")
                )
                return
            
            rtt2uart = session.rtt2uart
            
            # 检查 JLink 连接和 RTT 状态
            if not hasattr(rtt2uart, 'jlink') or not rtt2uart.jlink:
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("main_window", "No JLink Connection"),
                    QCoreApplication.translate("main_window", "JLink is not connected.")
                )
                return
            
            # 检查 JLink 是否真正打开
            try:
                if not rtt2uart.jlink.opened():
                    QMessageBox.warning(
                        self,
                        QCoreApplication.translate("main_window", "JLink Not Open"),
                        QCoreApplication.translate("main_window", "JLink DLL is not open. Please connect to device first.")
                    )
                    return
            except Exception as e:
                logger.warning(f"Failed to check JLink open status: {e}")
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("main_window", "JLink Not Ready"),
                    QCoreApplication.translate("main_window", "JLink is not ready. Please connect to device first.")
                )
                return
            
            # 获取 RTT 通道信息
            try:
                # 读取真实的 RTT 控制块信息
                num_up_buffers = rtt2uart.jlink.rtt_get_num_up_buffers()
                num_down_buffers = rtt2uart.jlink.rtt_get_num_down_buffers()
                
                logger.info(f"RTT Info: {num_up_buffers} up buffers, {num_down_buffers} down buffers")
                
                # 创建对话框
                dialog = QDialog(self)
                dialog.setWindowTitle(QCoreApplication.translate("main_window", "RTT Channel Description"))
                dialog.setMinimumWidth(500)
                
                layout = QVBoxLayout(dialog)
                
                # Up channels 标签和表格
                up_label = QLabel(QCoreApplication.translate("main_window", "Up channels:"))
                up_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
                layout.addWidget(up_label)
                
                up_table = QTableWidget(num_up_buffers, 4)
                up_table.setHorizontalHeaderLabels([
                    QCoreApplication.translate("main_window", "Id"),
                    QCoreApplication.translate("main_window", "Name"),
                    QCoreApplication.translate("main_window", "Size"),
                    QCoreApplication.translate("main_window", "Mode")
                ])
                up_table.horizontalHeader().setStretchLastSection(True)
                up_table.setEditTriggers(QTableWidget.NoEditTriggers)
                up_table.setSelectionBehavior(QTableWidget.SelectRows)
                
                # 填充 Up channels 数据
                for i in range(num_up_buffers):
                    try:
                        buf_info = rtt2uart.jlink.rtt_get_buf_descriptor(i, True)
                        name = buf_info.name.decode('utf-8') if isinstance(buf_info.name, bytes) else str(buf_info.name)
                        size = buf_info.SizeOfBuffer
                        flags = buf_info.Flags
                        
                        # 解析并翻译模式标志
                        if flags == 0:
                            mode = QCoreApplication.translate("main_window", "Non-blocking, skip")
                        elif flags == 1:
                            mode = QCoreApplication.translate("main_window", "Non-blocking, trim")
                        elif flags == 2:
                            mode = QCoreApplication.translate("main_window", "Blocking")
                        else:
                            mode = QCoreApplication.translate("main_window", "Mode %s") % flags
                        
                        up_table.setItem(i, 0, QTableWidgetItem(f"#{i}"))
                        up_table.setItem(i, 1, QTableWidgetItem(name))
                        up_table.setItem(i, 2, QTableWidgetItem(str(size)))
                        up_table.setItem(i, 3, QTableWidgetItem(mode))
                        
                        logger.debug(f"Up buffer {i}: name={name}, size={size}, flags={flags}")
                    except Exception as e:
                        logger.warning(f"Failed to get up buffer {i} info: {e}")
                        up_table.setItem(i, 0, QTableWidgetItem(f"#{i}"))
                        up_table.setItem(i, 1, QTableWidgetItem("-"))
                        up_table.setItem(i, 2, QTableWidgetItem("-"))
                        up_table.setItem(i, 3, QTableWidgetItem("-"))
                
                up_table.resizeColumnsToContents()
                # 设置表格高度自适应行数
                up_table_height = up_table.horizontalHeader().height() + 2  # 表头高度 + 边框
                for i in range(num_up_buffers):
                    up_table_height += up_table.rowHeight(i)
                up_table.setFixedHeight(up_table_height)
                layout.addWidget(up_table)
                
                # Down channels 标签和表格
                down_label = QLabel(QCoreApplication.translate("main_window", "Down channels:"))
                down_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
                layout.addWidget(down_label)
                
                down_table = QTableWidget(num_down_buffers, 4)
                down_table.setHorizontalHeaderLabels([
                    QCoreApplication.translate("main_window", "Id"),
                    QCoreApplication.translate("main_window", "Name"),
                    QCoreApplication.translate("main_window", "Size"),
                    QCoreApplication.translate("main_window", "Mode")
                ])
                down_table.horizontalHeader().setStretchLastSection(True)
                down_table.setEditTriggers(QTableWidget.NoEditTriggers)
                down_table.setSelectionBehavior(QTableWidget.SelectRows)
                
                # 填充 Down channels 数据
                for i in range(num_down_buffers):
                    try:
                        buf_info = rtt2uart.jlink.rtt_get_buf_descriptor(i, False)
                        name = buf_info.name.decode('utf-8') if isinstance(buf_info.name, bytes) else str(buf_info.name)
                        size = buf_info.SizeOfBuffer
                        flags = buf_info.Flags
                        
                        # 解析并翻译模式标志
                        if flags == 0:
                            mode = QCoreApplication.translate("main_window", "Non-blocking, skip")
                        elif flags == 1:
                            mode = QCoreApplication.translate("main_window", "Non-blocking, trim")
                        elif flags == 2:
                            mode = QCoreApplication.translate("main_window", "Blocking")
                        else:
                            mode = QCoreApplication.translate("main_window", "Mode %s") % flags
                        
                        down_table.setItem(i, 0, QTableWidgetItem(f"#{i}"))
                        down_table.setItem(i, 1, QTableWidgetItem(name))
                        down_table.setItem(i, 2, QTableWidgetItem(str(size)))
                        down_table.setItem(i, 3, QTableWidgetItem(mode))
                        
                        logger.debug(f"Down buffer {i}: name={name}, size={size}, flags={flags}")
                    except Exception as e:
                        logger.warning(f"Failed to get down buffer {i} info: {e}")
                        down_table.setItem(i, 0, QTableWidgetItem(f"#{i}"))
                        down_table.setItem(i, 1, QTableWidgetItem("-"))
                        down_table.setItem(i, 2, QTableWidgetItem("-"))
                        down_table.setItem(i, 3, QTableWidgetItem("-"))
                
                down_table.resizeColumnsToContents()
                # 设置表格高度自适应行数
                down_table_height = down_table.horizontalHeader().height() + 2  # 表头高度 + 边框
                for i in range(num_down_buffers):
                    down_table_height += down_table.rowHeight(i)
                down_table.setFixedHeight(down_table_height)
                layout.addWidget(down_table)
                
                # 添加确定按钮
                button_box = QDialogButtonBox(QDialogButtonBox.Ok)
                button_box.accepted.connect(dialog.accept)
                layout.addWidget(button_box)
                
                # 调整对话框大小以适应内容
                dialog.adjustSize()
                
                # 显示对话框
                dialog.exec()
                
            except Exception as e:
                logger.error(f"Failed to get RTT channel info: {e}")
                QMessageBox.warning(
                    self,
                    QCoreApplication.translate("main_window", "Error"),
                    QCoreApplication.translate("main_window", "Failed to get RTT channel information:\n%s") % str(e)
                )
                
        except Exception as e:
            logger.error(f"Error showing RTT chain info: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                QCoreApplication.translate("main_window", "Error"),
                QCoreApplication.translate("main_window", "Failed to show RTT channel information:\n%s") % str(e)
            )

    def populateComboBox(self):
        """统一从配置管理器加载命令历史，避免重复加载"""
        try:
            # 清空现有项目，防止重复加载
            self.ui.cmd_buffer.clear()
            
            # 统一使用配置管理器加载命令历史
            if hasattr(self, 'connection_dialog') and self.connection_dialog:
                cmd_history = self.connection_dialog.config.get_command_history()
                
                if cmd_history:
                    # 使用集合去重，保持顺序
                    unique_commands = []
                    seen = set()
                    for cmd in cmd_history:
                        if cmd and cmd not in seen:
                            unique_commands.append(cmd)
                            seen.add(cmd)
                    
                    # 添加去重后的命令到ComboBox
                    for cmd in unique_commands:
                        self.ui.cmd_buffer.addItem(cmd)
                    
                    logger.debug(f"Loaded {len(unique_commands)} unique command history from config manager")
                else:
                    logger.debug("No command history in config manager")
            else:
                logger.debug("Connection dialog not initialized, skip loading command history")
                
        except Exception as e:
            logger.error(f"Error loading command history: {e}")
    
    def _update_command_history(self, command: str):
        """智能更新命令历史：防止重复插入，只调整顺序"""
        if not command or not command.strip():
            return
        
        try:
            # 检查命令是否已存在于ComboBox中
            existing_index = -1
            for i in range(self.ui.cmd_buffer.count()):
                if self.ui.cmd_buffer.itemText(i) == command:
                    existing_index = i
                    break
            
            if existing_index >= 0:
                # 如果命令已存在，移除旧位置的项目
                self.ui.cmd_buffer.removeItem(existing_index)
                logger.debug(f"Remove duplicate command: {command}")
            
            # 将命令插入到最前面（索引0）
            self.ui.cmd_buffer.insertItem(0, command)
            
            # 同步更新配置管理器
            if self.connection_dialog:
                # 更新settings中的cmd列表（保持兼容性）
                if hasattr(self.connection_dialog, 'settings') and 'cmd' in self.connection_dialog.settings:
                    if command in self.connection_dialog.settings['cmd']:
                        self.connection_dialog.settings['cmd'].remove(command)
                    self.connection_dialog.settings['cmd'].insert(0, command)
                
                # 保存到配置文件
                self.connection_dialog.config.add_command_to_history(command)
            
            # 限制ComboBox项目数量，避免过多
            max_items = CleanupConfig.MAX_ITEMS
            while self.ui.cmd_buffer.count() > max_items:
                self.ui.cmd_buffer.removeItem(self.ui.cmd_buffer.count() - 1)
            
            logger.debug(f"Command history updated: {command} (Total: {self.ui.cmd_buffer.count()})")
                    
        except Exception as e:
            logger.error(f"Failed to update command history: {e}")
    
    def _convert_cmd_file_to_utf8(self):
        """将cmd.txt文件转换为UTF-8编码"""
        try:
            # 先读取所有内容
            commands = []
            with open('cmd.txt', 'r', encoding='gbk') as file:
                for line in file:
                    commands.append(line.rstrip('\n\r'))
            
            # 用UTF-8编码重新写入
            with open('cmd.txt', 'w', encoding='utf-8') as file:
                for cmd in commands:
                    file.write(cmd + '\n')
            
            logger.info("cmd.txt file converted to UTF-8 encoding")
            
        except Exception as e:
            logger.error(f"Failed to convert cmd.txt encoding: {e}")

    def _init_encoding_combo(self):
        """初始化编码选择框并与配置同步"""
        try:
            self.ui.encoder.clear()
            # 常用编码集合
            encodings = [
                'gbk', 'utf-8', 'utf-8-sig', 'gb2312', 'big5', 'iso-8859-1'
            ]
            for enc in encodings:
                self.ui.encoder.addItem(enc)
            # 从配置恢复
            current = self.connection_dialog.config.get_text_encoding() if self.connection_dialog else 'gbk'
            idx = self.ui.encoder.findText(current, Qt.MatchFixedString)
            if idx >= 0:
                self.ui.encoder.setCurrentIndex(idx)
        except Exception:
            pass

    def _on_encoding_changed(self, enc: str):
        """用户切换编码时保存配置"""
        try:
            if self.connection_dialog:
                self.connection_dialog.config.set_text_encoding(enc)
                self.connection_dialog.config.save_config()
        except Exception:
            pass

    def set_style(self):
        # 根据复选框状态设置样式
        stylesheet = self.light_stylesheet if self.ui.light_checkbox.isChecked() else self.dark_stylesheet
        self.setStyleSheet(stylesheet)
        if self.connection_dialog:
            self.connection_dialog.settings['light_mode'] = self.ui.light_checkbox.isChecked()
            # 同步保存到INI配置（只在UI初始化完成后保存）
            if self._ui_initialization_complete:
                self.connection_dialog.config.set_light_mode(self.ui.light_checkbox.isChecked())
                self.connection_dialog.config.save_config()
        
        # 更新JLink日志区域的样式
        self._update_jlink_log_style()
    
    def _init_font_combo(self):
        """初始化字体选择下拉框，列出常用等宽字体"""
        # 预定义常用等宽字体列表，避免获取系统所有字体的性能开销
        common_monospace_fonts = [
            "Consolas", "Courier New", "SimSun", "Monaco", "Menlo",
            "Cascadia Code", "DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono",
            "JetBrains Mono", "Fira Code", "Source Code Pro", "Sarasa Mono SC",
            "等距更纱黑体 SC", "Fixedsys"
        ]
        
        # 填充字体下拉框，并为每个项设置对应的字体样式
        self.ui.font_combo.clear()
        
        # 字体对象缓存，避免重复创建
        self._font_cache = {}
        
        for font_name in common_monospace_fonts:
            self.ui.font_combo.addItem(font_name)
            # 为该项设置对应的字体，让用户直观看到字体效果
            item_index = self.ui.font_combo.count() - 1
            if font_name not in self._font_cache:
                self._font_cache[font_name] = QFont(font_name, 10)
            self.ui.font_combo.setItemData(item_index, self._font_cache[font_name], Qt.FontRole)
        
        logger.info(f"[FONT] Initialized with {len(common_monospace_fonts)} common monospace fonts")
        
        # 从配置加载保存的字体
        if self.connection_dialog:
            saved_font = self.connection_dialog.config.get_fontfamily()
            # 查找匹配的字体
            index = self.ui.font_combo.findText(saved_font)
            if index >= 0:
                self.ui.font_combo.setCurrentIndex(index)
                logger.info(f"[FONT] Loaded saved font: {saved_font}")
            else:
                # 如果保存的字体不存在，使用默认字体：SimSun -> Consolas -> Courier New
                default_fonts = ["SimSun", "Consolas", "Courier New"]
                selected_font = None
                
                for default_font in default_fonts:
                    index = self.ui.font_combo.findText(default_font)
                    if index >= 0:
                        selected_font = default_font
                        self.ui.font_combo.setCurrentIndex(index)
                        logger.info(f"[FONT] Using default font: {default_font}")
                        break
                
                # 如果所有默认字体都不存在，使用第一个字体
                if not selected_font and common_monospace_fonts:
                    self.ui.font_combo.setCurrentIndex(0)
                    logger.info(f"[FONT] No default font found, using: {common_monospace_fonts[0]}")
    
    def on_font_changed(self, font_name):
        """字体变更时的处理 - 检测变化并全局刷新"""
        if not font_name:
            return
            
        # 🔑 检测字体是否真的改变了
        if self._current_font_name == font_name:
            logger.info(f"[FONT] Font unchanged: {font_name}, skipping refresh")
            return
        
        logger.info(f"[FONT] Font changed from '{self._current_font_name}' to '{font_name}' - forcing全局刷新")
        
        # 保存到配置（只在UI初始化完成后保存）
        if self.connection_dialog and self._ui_initialization_complete:
            self.connection_dialog.config.set_fontfamily(font_name)
            self.connection_dialog.config.save_config()
        
        # 🔑 全局更新：遍历所有TAB并强制刷新已有文本的字体
        self._update_all_tabs_font()
        
        # 更新当前字体变量
        self._current_font_name = font_name
    
    def _update_all_tabs_font(self):
        """全局更新所有TAB的字体 - 优化性能版本"""
        try:
            # 获取字体设置
            font_name = self.ui.font_combo.currentText() if hasattr(self.ui, 'font_combo') else "Consolas"
            font_size = self.ui.fontsize_box.value()
            
            # 构建缓存键
            font_cache_key = f"{font_name}_{font_size}"
            
            # 字体对象缓存检查
            if not hasattr(self, '_font_cache'):
                self._font_cache = {}
            
            # 如果缓存中没有此字体配置，创建并缓存
            if font_cache_key not in self._font_cache:
                # 创建字体对象 - 使用更严格的等宽字体设置
                font = QFont(font_name, font_size)
                font.setFixedPitch(True)
                font.setStyleHint(QFont.TypeWriter)  # 使用TypeWriter而不是Monospace
                font.setStyleStrategy(QFont.PreferDefault)
                font.setKerning(False)  # 禁用字距调整
                self._font_cache[font_cache_key] = font
            
            # 从缓存获取字体对象
            font = self._font_cache[font_cache_key]
            
            # 跟踪更新计数
            updated_count = 0
            
            # 批量处理所有文本编辑控件
            all_text_edits = []
            
            # 收集所有需要更新的文本编辑控件
            for session in session_manager.get_all_sessions():
                if session.mdi_window:
                    all_text_edits.extend([te for te in session.mdi_window.text_edits if te])
            
            # 批量更新 - 避免在循环中处理事件
            for text_edit in all_text_edits:
                # 1. 设置控件字体
                text_edit.setFont(font)
                
                # 2. 设置文档默认字体（对新增内容生效）
                text_edit.document().setDefaultFont(font)
                
                # 3. 清除格式缓存（如果是FastAnsiTextEdit实例）
                # 这是关键修复：确保新数据使用新字体而不是缓存的旧格式
                # 性能优化：只在必要时清除缓存
                if hasattr(text_edit, 'clear_format_cache') and hasattr(text_edit, '_format_cache'):
                    # 如果缓存为空或字体没有变化，就不需要清除缓存
                    if text_edit._format_cache:  # 只在缓存非空时执行
                        try:
                            text_edit.clear_format_cache()
                            logger.info(f"[FONT UPDATE] Cleared format cache for text edit")
                        except Exception as e:
                            logger.warning(f"Failed to clear format cache: {e}")
                
                # 3. 使用更高效的方式更新现有文本格式
                cursor = QTextCursor(text_edit.document())
                cursor.movePosition(QTextCursor.Start)
                cursor.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
                
                # 创建格式对象
                char_format = QTextCharFormat()
                char_format.setFont(font)
                
                # 使用批量编辑 - 只更新字体属性而不覆盖颜色等其他格式
                cursor.beginEditBlock()
                # 不使用setCharFormat直接设置，而是逐个字符或段落更新字体
                # 这样可以保留现有的颜色格式
                document = text_edit.document()
                block = document.begin()
                while block.isValid():
                    # 遍历块中的每个字符
                    fragment_cursor = QTextCursor(block)
                    fragment_cursor.movePosition(QTextCursor.StartOfBlock)
                    while not fragment_cursor.atBlockEnd():
                        # 选择当前字符
                        fragment_cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
                        # 获取现有格式
                        current_format = fragment_cursor.charFormat()
                        # 只更新字体，保留其他格式（如颜色）
                        current_format.setFont(font)
                        fragment_cursor.setCharFormat(current_format)
                    block = block.next()
                cursor.endEditBlock()
                
                updated_count += 1
            
            # 一次性处理所有待处理事件
            QApplication.processEvents()
            
            # 触发所有文本编辑控件更新
            for text_edit in all_text_edits:
                text_edit.updateGeometry()
                text_edit.viewport().update()
            
            logger.info(f"[FONT] Updated font for {updated_count} text edits to: {font_name} {font_size}pt")
            
            # 延迟刷新一次 - 但避免过度刷新
            if updated_count > 0:
                QTimer.singleShot(100, lambda: self._delayed_font_refresh_all())
                
        except Exception as e:
            logger.warning(f"Failed to update all tabs font: {e}")
    
    def _delayed_font_refresh(self):
        """延迟刷新字体 - 用于某些系统的兼容性（向后兼容）"""
        self._delayed_font_refresh_all()
    
    def _delayed_font_refresh_all(self):
        """延迟刷新所有TAB的字体 - 优化版本，减少不必要的操作"""
        try:
            # 收集所有需要延迟刷新的文本编辑控件
            delayed_refresh_edits = []
            
            # 遍历所有设备会话的MDI窗口
            for session in session_manager.get_all_sessions():
                if session.mdi_window:
                    delayed_refresh_edits.extend([te for te in session.mdi_window.text_edits if te])
            
            # 批量处理延迟刷新
            for text_edit in delayed_refresh_edits:
                # 只需要标记文档为脏并触发更新，避免过多的重绘操作
                doc = text_edit.document()
                doc.markContentsDirty(0, doc.characterCount())
                text_edit.update()  # 使用update而非repaint，让Qt优化刷新过程
            
            # 一次性处理所有待处理事件
            QApplication.processEvents()
            
            logger.info(f"[FONT] Delayed font refresh completed for {len(delayed_refresh_edits)} text edits")
        except Exception as e:
            logger.info(f"Delayed font refresh error: {e}")
    
    def _update_current_tab_font(self):
        """更新当前TAB的字体（MDI架构） - 优化版本"""
        try:
            # MDI架构：获取当前活动的MDI窗口
            mdi_window = self._get_active_mdi_window()
            if not mdi_window:
                return
            
            current_index = mdi_window.tab_widget.currentIndex()
            if current_index < len(mdi_window.text_edits):
                text_edit = mdi_window.text_edits[current_index]
                if text_edit:
                    # 获取字体设置
                    font_name = self.ui.font_combo.currentText() if hasattr(self.ui, 'font_combo') else "Consolas"
                    font_size = self.ui.fontsize_box.value()
                    
                    # 构建缓存键并使用字体缓存
                    font_cache_key = f"{font_name}_{font_size}"
                    
                    if not hasattr(self, '_font_cache'):
                        self._font_cache = {}
                    
                    # 从缓存获取或创建字体对象
                    if font_cache_key not in self._font_cache:
                        font = QFont(font_name, font_size)
                        font.setFixedPitch(True)
                        font.setStyleHint(QFont.TypeWriter)  # 使用更严格的等宽字体设置
                        font.setKerning(False)  # 禁用字距调整
                        self._font_cache[font_cache_key] = font
                    
                    # 应用字体
                    font = self._font_cache[font_cache_key]
                    text_edit.setFont(font)
                    text_edit.document().setDefaultFont(font)
                    
                    # 只更新当前可见的文本
                    text_edit.update()
        except Exception as e:
            logger.warning(f"Failed to update current tab font: {e}")
    
    def on_fontsize_changed(self):
        """字体大小变更时的处理 - 检测变化并全局刷新"""
        font_size = self.ui.fontsize_box.value()
        
        # 🔑 检测字号是否真的改变了
        if self._current_font_size == font_size:
            logger.info(f"[FONT] Font size unchanged: {font_size}pt, skipping refresh")
            return
        
        logger.info(f"[FONT] Font size changed from {self._current_font_size}pt to {font_size}pt - forcing全局刷新")
        
        if self.connection_dialog:
            self.connection_dialog.settings['fontsize'] = font_size
            # 同步保存到INI配置（🔑 只在UI初始化完成后保存）
            if self._ui_initialization_complete:
                self.connection_dialog.config.set_fontsize(font_size)
                self.connection_dialog.config.save_config()
        
        # 🔑 全局更新：遍历所有TAB并强制刷新已有文本的字号
        self._update_all_tabs_font()
        
        # 更新当前字号变量
        self._current_font_size = font_size
    
    def on_lock_h_changed(self):
        """水平滚动条锁定状态改变时保存配置"""
        if self.connection_dialog:
            # 🔧 BUG修复：同时更新settings字典和配置文件
            self.connection_dialog.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
            # 只在UI初始化完成后保存
            if self._ui_initialization_complete:
                self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
                self.connection_dialog.config.save_config()
                logger.debug(f"[SAVE] Horizontal scrollbar lock state saved: {self.ui.LockH_checkBox.isChecked()}")
    
    # 注意：垂直滚动条锁定功能已移至DeviceMdiWindow，此方法已废弃
    def on_lock_v_changed(self):
        pass
    
    
    def _update_jlink_log_style(self):
        """更新JLink日志区域的样式以匹配当前主题"""
        if not hasattr(self, 'jlink_log_text'):
            return
            
        # 主窗口不再有light_checkbox，默认使用深色主题
        is_light_mode = False
        
        if is_light_mode:
            # 浅色主题样式
            jlink_log_style = """
                QTextEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #c0c0c0;
                    font-family: 'Consolas', 'Monaco', monospace;
                    selection-background-color: #3399ff;
                }
            """
        else:
            # 深色主题样式
            jlink_log_style = """
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3e3e3e;
                    font-family: 'Consolas', 'Monaco', monospace;
                    selection-background-color: #264f78;
                }
            """
        
        self.jlink_log_text.setStyleSheet(jlink_log_style)
        
    def on_cmd_buffer_activated(self, index):
        text = self.ui.cmd_buffer.currentText()
        if text:  # 如果文本不为空
            self.ui.pushButton.click()  # 触发 QPushButton 的点击事件

    def update_status_bar(self):
        """更新状态栏信息 - MDI架构：显示活动设备的状态"""
        if not hasattr(self, 'status_bar'):
            return
        
        # MDI架构：获取活动设备会话
        session = self._get_active_device_session()
        
        # 更新连接状态
        if session and session.rtt2uart and session.is_connected:
            # 显示设备连接信息：USB_X_SN格式
            device_info = getattr(session.rtt2uart, 'device_info', 'Unknown')
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected: %s") % device_info)
        else:
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "Disconnected"))
        
        # 更新数据统计
        readed = 0
        writed = 0
        if session and session.rtt2uart:
            readed = session.rtt2uart.read_bytes0 + session.rtt2uart.read_bytes1
            writed = session.rtt2uart.write_bytes0
        
        self.data_stats_label.setText(
            QCoreApplication.translate("main_window", "Read: {} | Write: {}").format(readed, writed)
        )
        
        # 更新窗口标题
        self.update_window_title()
    
    def update_window_title(self):
        """更新窗口标题，显示连接状态、当前标签页、读写字节数"""
        title_parts = []
        try:
            from version import VERSION, VERSION_NAME, BUILD_TIME
            title_parts.append(VERSION_NAME + " v" + VERSION)
        except Exception as e:
            pass

        # 获取当前激活的设备会话
        active_session = self._get_active_device_session()
        
        # 1. 连接状态和设备信息
        if active_session and active_session.is_connected and active_session.rtt2uart:
            device_info = getattr(active_session.rtt2uart, 'device_info', 'Unknown')
            title_parts.append(QCoreApplication.translate("main_window", "Connected: %s") % device_info)
        else:
            title_parts.append(QCoreApplication.translate("main_window", "Disconnected"))
        
        # 2. 读写字节统计 - 使用当前session的rtt2uart
        readed = 0
        writed = 0
        if active_session and active_session.rtt2uart:
            readed = active_session.rtt2uart.read_bytes0 + active_session.rtt2uart.read_bytes1
            writed = active_session.rtt2uart.write_bytes0
        
        title_parts.append(QCoreApplication.translate("main_window", "Read: %10d bytes") % readed)
        title_parts.append(QCoreApplication.translate("main_window", "Write: %4d bytes") % writed)

        # 3. 当前激活的设备窗口和标签页名称
        if active_session and active_session.mdi_window:
            # 获取设备名称
            #device_name = active_session.get_display_name()
            # 获取当前标签页名称
            current_index = active_session.mdi_window.tab_widget.currentIndex()
            current_tab_name = active_session.mdi_window.tab_widget.tabText(current_index)
            title_parts.append(f"{current_tab_name}")
                
        # 组合标题
        title = " | ".join(title_parts)
        self.setWindowTitle(title)
    
    def update_periodic_task(self):
        
        # title = QCoreApplication.translate("main_window", u"XexunRTT")
        # title += "\t"
        
        # if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
        #     title += QCoreApplication.translate("main_window", u"status:Started")
        # else:
        #     title += QCoreApplication.translate("main_window", u"status:Stoped")

        # title += "\t"
        
        # readed = 0
        # writed = 0
        # if self.connection_dialog and self.connection_dialog.rtt2uart is not None:
        #     readed = self.connection_dialog.rtt2uart.read_bytes0 + self.connection_dialog.rtt2uart.read_bytes1
        #     writed = self.connection_dialog.rtt2uart.write_bytes0
        
        # title += QCoreApplication.translate("main_window", u"Readed:") + "%8u" % readed
        # title += "\t"
        # title += QCoreApplication.translate("main_window", u"Writed:") + "%4u" % writed
        # title += " "
        
        # self.setWindowTitle(title)
        
        # 更新状态栏
        self.update_status_bar()
        
        # 定时任务不应该保存配置，只更新显示信息
        # 配置保存应该在用户实际修改设置时进行
        
        # ========== 旧代码已删除：_ensure_correct_tooltips 调用 ==========
        # MDI 架构中不再需要
        # ====================================================
    
    # ========== 旧代码已删除：_ensure_correct_tooltips 方法 ==========
    # MDI 架构中，工具提示由 DeviceMdiWindow 管理
    # ====================================================
    # def _ensure_correct_tooltips(self):
    #     # 此方法已废弃
    #     pass


    def toggle_lock_h_checkbox(self):
        self.ui.LockH_checkBox.setChecked(not self.ui.LockH_checkBox.isChecked())
        if self.connection_dialog:
            self.connection_dialog.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
            # 同步保存到INI配置（只在UI初始化完成后保存）
            if self._ui_initialization_complete:
                self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
                self.connection_dialog.config.save_config()
    
    # 注意：垂直滚动条锁定功能已移至DeviceMdiWindow，此方法已废弃
    def toggle_lock_v_checkbox(self):
        pass
    def toggle_style_checkbox(self):
        self.ui.light_checkbox.setChecked(not self.ui.light_checkbox.isChecked())
        self.set_style()
        
    def device_restart(self):
        # 与 F9 行为保持一致：根据子菜单选择执行重启
        self.restart_app_execute()

    def _on_format_ram_toggled(self, checked):
        """格式化RAM选项切换时保存配置"""
        try:
            if self.connection_dialog:
                self.connection_dialog.config.set_format_ram_on_restart(checked)
                self.connection_dialog.config.save_config()
        except Exception as e:
            logger.error(f"Failed to save format RAM config: {e}")
    
    def _get_device_ram_info(self, session=None):
        """从JLink设备配置中获取RAM地址和大小
        
        Args:
            session: 可选的设备会话对象，在MDI架构中使用
            
        Returns:
            tuple: (ram_start_addr, ram_size) 或 (None, None) 如果获取失败
        """
        try:
            # 优先使用传入的session获取设备信息（MDI架构）
            device_name = None
            
            if session and hasattr(session, 'connection_dialog') and session.connection_dialog:
                device_name = session.connection_dialog.target_device
                if not device_name:
                    try:
                        device_name = session.connection_dialog.ui.comboBox_Device.currentText()
                    except:
                        pass
            # 如果没有session或获取失败，回退到全局connection_dialog
            elif self.connection_dialog:
                device_name = self.connection_dialog.target_device
                if not device_name:
                    try:
                        device_name = self.connection_dialog.ui.comboBox_Device.currentText()
                    except:
                        pass
            
            if not device_name:
                logger.warning("No device name available for RAM info lookup")
                return None, None
            
            logger.info(f"Looking up RAM info for device: {device_name}")
            
            # 解析JLink设备数据库文件
            import xml.etree.ElementTree as ET
            # 获取XML文件路径
            try:
                # 尝试从connection_dialog获取（如果可用）
                if hasattr(self, 'connection_dialog') and self.connection_dialog and hasattr(self.connection_dialog, 'get_jlink_devices_list_file'):
                    xml_path = self.connection_dialog.get_jlink_devices_list_file()
                else:
                    raise AttributeError("Neither self nor connection_dialog has get_jlink_devices_list_file method")
                
                if not xml_path:
                    raise ValueError("get_jlink_devices_list_file returned empty path")
                    
            except (AttributeError, ValueError) as e:
                logger.error(f"Failed to get device list file path: {e}")
                # 不再使用硬编码路径，让错误能够被检测到
                return None, None
            
            try:
                with open(xml_path, 'r', encoding='utf-8') as f:
                    tree = ET.ElementTree(file=f)
            except UnicodeDecodeError:
                with open(xml_path, 'r', encoding='iso-8859-1') as f:
                    tree = ET.ElementTree(file=f)
            
            # 查找设备信息
            for VendorInfo in tree.findall('VendorInfo'):
                for DeviceInfo in VendorInfo.findall('DeviceInfo'):
                    if DeviceInfo.attrib.get('Name') == device_name:
                        # 获取RAM起始地址和大小
                        ram_start = DeviceInfo.attrib.get('WorkRAMStartAddr')
                        ram_size = DeviceInfo.attrib.get('WorkRAMSize')
                        
                        if ram_start and ram_size:
                            # 转换为整数
                            ram_start_addr = int(ram_start, 16)
                            ram_size_bytes = int(ram_size, 16)
                            logger.info(f"Found RAM info for {device_name}: addr=0x{ram_start_addr:08X}, size={ram_size_bytes} bytes")
                            return ram_start_addr, ram_size_bytes
                        else:
                            logger.warning(f"Device {device_name} found but no RAM info (WorkRAMStartAddr={ram_start}, WorkRAMSize={ram_size})")
                            return None, None
                    
                    # 检查别名
                    for AliasInfo in DeviceInfo.findall('AliasInfo'):
                        if AliasInfo.attrib.get('Name') == device_name:
                            ram_start = DeviceInfo.attrib.get('WorkRAMStartAddr')
                            ram_size = DeviceInfo.attrib.get('WorkRAMSize')
                            
                            if ram_start and ram_size:
                                ram_start_addr = int(ram_start, 16)
                                ram_size_bytes = int(ram_size, 16)
                                logger.info(f"Found RAM info for {device_name} (via alias): addr=0x{ram_start_addr:08X}, size={ram_size_bytes} bytes")
                                return ram_start_addr, ram_size_bytes
                            else:
                                logger.warning(f"Device {device_name} found via alias but no RAM info")
                                return None, None
            
            logger.warning(f"Device {device_name} not found in JLink device database")
            return None, None
            
        except Exception as e:
            logger.error(f"Failed to get device RAM info: {e}")
            return None, None
    
    def _format_ram(self):
        """格式化RAM（清零）
        
        Returns:
            bool: 成功启动格式化线程返回True，失败返回False
        """
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart or not session.is_connected:
                return False
            
            # 获取RAM信息（传递session以适配MDI架构）
            ram_start, ram_size = self._get_device_ram_info(session)
            
            if ram_start is None or ram_size is None:
                device_name = session.connection_dialog.target_device if session.connection_dialog else "Unknown"
                self.append_jlink_log(QCoreApplication.translate("main_window", "⚠ Cannot get RAM info for device '%s', skipping RAM format") % device_name)
                return False
            
            # 创建并启动格式化线程
            format_thread = RamFormatThread(self, session, ram_start, ram_size)
            format_thread.log_signal.connect(self.append_jlink_log)
            format_thread.start()
            
            # 禁用格式化按钮以防止重复点击
            if hasattr(self, 'action_format_ram'):
                self.action_format_ram.setEnabled(False)
            
            # 连接线程完成信号
            def on_format_finished(success):
                # 重新启用格式化按钮
                if hasattr(self, 'action_format_ram'):
                    self.action_format_ram.setEnabled(True)
                # 通知重启操作格式化已完成
                if hasattr(self, '_format_ram_finished'):
                    self._format_ram_finished(success)
            
            # 连接自定义的format_finished信号而不是默认的finished信号
            format_thread.format_finished.connect(on_format_finished)
            
            return True
            
        except Exception as e:
            error_msg = QCoreApplication.translate("main_window", "RAM format error: %s") % str(e)
            self.append_jlink_log(error_msg)
            logger.error(f"RAM format error: {e}")
            return False

    def restart_app_via_sfr(self):
        """通过SFR访问触发固件重启（需保持连接）"""
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart or not session.is_connected:
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please connect first, then restart app"))
                return
            jlink = session.rtt2uart.jlink
            try:
                # Cortex-M: AIRCR.SYSRESETREQ = 1 -> 写 0x05FA0004 到 0xE000ED0C
                try:
                    jlink.halt()
                except Exception:
                    pass
                # pylink API: memory_write32(addr, List[int])
                jlink.memory_write32(0xE000ED0C, [0x05FA0004])
                self.append_jlink_log(QCoreApplication.translate("main_window", "Restart via SFR (AIRCR.SYSRESETREQ) sent by memory_write32"))
            except Exception as e:
                QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "SFR restart failed: %s") % str(e))
        except Exception as e:
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), str(e))

    def restart_app_via_reset_pin(self):
        """通过硬件复位引脚重启（若调试器支持）"""
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart or not session.is_connected:
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please connect first, then restart app"))
                return
            jlink = session.rtt2uart.jlink
            try:
                jlink.reset(halt=False)
                self.append_jlink_log(QCoreApplication.translate("main_window", "Restart via reset pin executed"))
            except Exception as e:
                QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "Reset pin restart failed: %s") % str(e))
        except Exception as e:
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), str(e))

    def restart_app_execute(self):
        """F9 - 重启当前激活设备的APP"""
        try:
            # 获取当前激活的设备会话
            session = self._get_active_device_session()
            if not session:
                logger.warning("No active device session to restart")
                return
            
            # MDI架构：若未连接，则先自动连接，待连接成功后再执行
            if not session.is_connected:
                if session.connection_dialog:
                    # 连接成功后回调一次，再断开信号
                    def _once():
                        try:
                            session.connection_dialog.connection_established.disconnect(_once)
                        except Exception:
                            pass
                        # 确保在事件循环返回后执行，避免与连接建立时序冲突
                        QTimer.singleShot(0, self.restart_app_execute)
                    try:
                        session.connection_dialog.connection_established.connect(_once)
                    except Exception:
                        pass
                    # 静默启动连接
                    session.connection_dialog.start()
                    return
                else:
                    QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Unable to create connection dialog"))
                    return

            # 已连接：按选择执行
            selected_sfr = hasattr(self, 'action_restart_sfr') and self.action_restart_sfr.isChecked()
            # 保存选择到配置
            try:
                if session.connection_dialog:
                    session.connection_dialog.config.set_restart_method('SFR' if selected_sfr else 'RESET_PIN')
                    session.connection_dialog.config.save_config()
            except Exception:
                pass
            
            # 检查是否需要格式化RAM
            format_ram_enabled = hasattr(self, 'action_format_ram') and self.action_format_ram.isChecked()
            if format_ram_enabled:
                self.append_jlink_log(QCoreApplication.translate("main_window", "--- Format RAM before restart ---"))
                
                # 设置格式化完成后的回调函数
                def on_format_ram_finished(success):
                    # 即使格式化失败也尝试执行重启操作
                    self._execute_restart(selected_sfr)
                    # 移除回调引用以避免内存泄漏
                    if hasattr(self, '_format_ram_finished'):
                        delattr(self, '_format_ram_finished')
                
                # 存储回调函数引用
                self._format_ram_finished = on_format_ram_finished
                
                # 启动异步RAM格式化
                self._format_ram()
            else:
                # 不需要格式化RAM，直接执行重启
                self._execute_restart(selected_sfr)
                
        except Exception as e:
            logger.error(f"Restart app error: {e}")
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "Restart app error: %s") % str(e))
    
    def _execute_restart(self, use_sfr=True):
        """执行设备重启操作
        
        Args:
            use_sfr (bool): True使用SFR方式重启，False使用复位引脚方式重启
        """
        try:
            if use_sfr:
                self.restart_app_via_sfr()
            else:
                self.restart_app_via_reset_pin()
        except Exception as e:
            logger.error(f"Execute restart error: {e}")
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "Restart execution error: %s") % str(e))
    
    def restart_app_via_reset_pin(self):
        """通过硬件复位引脚重启（若调试器支持）"""
        try:
            # MDI架构：获取活动设备会话
            session = self._get_active_device_session()
            if not session or not session.rtt2uart or not session.is_connected:
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please connect first, then restart app"))
                return
            jlink = session.rtt2uart.jlink
            try:
                # 尝试使用J-Link API触发复位
                jlink.reset()
                self.append_jlink_log(QCoreApplication.translate("main_window", "Reset pin triggered, device should restart"))
                logger.info(f"Restart executed for device: {session.get_display_name()}")
            except Exception as e:
                QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "Reset pin restart failed: %s") % str(e))
                logger.error(f"Failed to restart device: {e}", exc_info=True)
        except Exception as e:
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), str(e))
            logger.error(f"Failed to restart device: {e}", exc_info=True)

    def show_find_dialog(self):
        """Show find dialog"""
        try:
            # Get current active MDI window
            active_mdi_sub = self.mdi_area.activeSubWindow()
            if not active_mdi_sub:
                logger.warning("No active MDI window for find dialog")
                return
            
            # Get DeviceMdiWindow content
            mdi_window = active_mdi_sub.widget()
            if not mdi_window or not isinstance(mdi_window, DeviceMdiWindow):
                logger.warning("Active MDI window is not a DeviceMdiWindow")
                return
            
            # Get current active TAB in the MDI window
            current_index = mdi_window.tab_widget.currentIndex()
            if current_index < 0 or current_index >= len(mdi_window.text_edits):
                logger.warning(f"Invalid tab index: {current_index}")
                return
            
            # Get the text editor for current tab
            text_edit = mdi_window.text_edits[current_index]
            if not text_edit:
                logger.warning(f"No text editor found for tab {current_index}")
                return
                
            # Get selected text (if single line)
            cursor = text_edit.textCursor()
            selected_text = cursor.selectedText()
            initial_text = ""
            
            # Only use selected text if it's a single line (no line breaks)
            if selected_text and '\n' not in selected_text and '\r' not in selected_text:
                # QTextCursor uses U+2029 (paragraph separator) for line breaks
                if '\u2029' not in selected_text:
                    initial_text = selected_text.strip()
            
            # logger.info(f"Opening find dialog for tab {current_index}, initial_text: '{initial_text}'")
                
            # Create and show find dialog
            if not hasattr(self, 'find_dialog') or not self.find_dialog:
                self.find_dialog = FindDialog(self, text_edit)
            else:
                self.find_dialog.set_text_edit(text_edit)
            
            # Set initial search text if available
            if initial_text:
                self.find_dialog.set_search_text(initial_text)
                
            self.find_dialog.show()
            self.find_dialog.raise_()
            self.find_dialog.activateWindow()
            
        except Exception as e:
            logger.error(f"Failed to show find dialog: {e}", exc_info=True)


class RamFormatThread(QThread):
    """RAM格式化工作线程，在后台执行RAM清零操作"""
    log_signal = Signal(str)
    format_finished = Signal(bool)  # 自定义信号，用于传递格式化结果
    
    def __init__(self, parent, session, ram_start, ram_size):
        super().__init__(parent)
        self.session = session
        self.ram_start = ram_start
        self.ram_size = ram_size
        # Use global logger instead of parent logger
        global logger
        self.logger = logger
        
    def run(self):
        """线程运行函数，执行实际的RAM格式化操作"""
        try:
            jlink = self.session.rtt2uart.jlink
            
            # 获取设备名称用于日志显示
            device_name = "Unknown"
            if hasattr(self.session, 'connection_dialog') and self.session.connection_dialog:
                device_name = self.session.connection_dialog.target_device or "Unknown"
                if not device_name:
                    try:
                        device_name = self.session.connection_dialog.ui.comboBox_Device.currentText()
                    except:
                        pass
            
            self.log_signal.emit(QCoreApplication.translate("main_window", "Starting RAM format: 0x%08X, size: %d bytes") % (self.ram_start, self.ram_size))
            
            # 分块清除RAM（每次4KB）
            block_size = 4096
            total_blocks = (self.ram_size + block_size - 1) // block_size
            cleared_size = 0
            success = True
            
            try:
                jlink.halt()
            except Exception:
                pass
            
            for i in range(total_blocks):
                offset = i * block_size
                current_addr = self.ram_start + offset
                current_size = min(block_size, self.ram_size - offset)
                
                try:
                    # 创建全零数据块
                    zero_data = [0] * (current_size // 4)  # memory_write32需要32位数据
                    jlink.memory_write32(current_addr, zero_data)
                    cleared_size += current_size
                    
                    # 每清除1/4进度输出一次日志
                    if (i + 1) % (max(1, total_blocks // 4)) == 0 or i == total_blocks - 1:
                        progress = (cleared_size * 100) // self.ram_size
                        self.log_signal.emit(QCoreApplication.translate("main_window", "RAM format progress: %d%%") % progress)
                    
                except Exception as e:
                    # 遇到错误时显示警告并完成操作
                    error_msg = QCoreApplication.translate("main_window", "⚠ RAM format failed at 0x%08X: %s\nCleared %d/%d bytes") % (current_addr, str(e), cleared_size, self.ram_size)
                    self.log_signal.emit(error_msg)
                    self.logger.warning(f"RAM format failed at 0x{current_addr:08X}: {e}")
                    success = cleared_size > 0  # 如果清除了部分内存，仍然返回True
                    break
            
            if success:
                self.log_signal.emit(QCoreApplication.translate("main_window", "✓ RAM format completed: %d bytes cleared") % cleared_size)
            
            # 线程完成时发出自定义信号
            self.format_finished.emit(success)
            
        except Exception as e:
            error_msg = QCoreApplication.translate("main_window", "RAM format error: %s") % str(e)
            self.log_signal.emit(error_msg)
            self.logger.error(f"RAM format error: {e}")
            self.format_finished.emit(False)

class FindDialog(QDialog):
    """Find Dialog"""
    
    def __init__(self, parent=None, text_edit=None):
        super().__init__(parent)
        self.text_edit = text_edit
        self.last_search_text = ""
        self.last_position = 0
        self.highlights = []
        self.find_all_window = None
        
        self.setWindowTitle(QCoreApplication.translate("FindDialog", "Find"))
        self.setModal(False)
        self.resize(450, 140)
        
        # Set window flags to avoid Aero Peek display in taskbar
        current_flags = self.windowFlags()
        new_flags = current_flags | Qt.Tool
        # Ensure close button and system menu are preserved
        new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(new_flags)
        
        # Create UI
        self.setup_ui()
        
        # Connect signals
        self.setup_connections()
        
        # Load search history
        self.load_search_history()
        
    def setup_ui(self):
        """Setup UI"""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QCheckBox, QLabel
        
        layout = QVBoxLayout(self)
        
        # Search input combo box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel(QCoreApplication.translate("FindDialog", "Find:")))
        self.search_input = QComboBox()
        self.search_input.setEditable(True)
        self.search_input.setMaxCount(10)  # Maximum 10 items in history
        self.search_input.lineEdit().setPlaceholderText(QCoreApplication.translate("FindDialog", "Enter text to find..."))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.case_sensitive = QCheckBox(QCoreApplication.translate("FindDialog", "Case Sensitive"))
        self.whole_word = QCheckBox(QCoreApplication.translate("FindDialog", "Whole Words"))
        self.regex_mode = QCheckBox(QCoreApplication.translate("FindDialog", "Regular Expression"))
        options_layout.addWidget(self.case_sensitive)
        options_layout.addWidget(self.whole_word)
        options_layout.addWidget(self.regex_mode)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.find_next_btn = QPushButton(QCoreApplication.translate("FindDialog", "Find Next"))
        self.find_prev_btn = QPushButton(QCoreApplication.translate("FindDialog", "Find Previous"))
        self.find_all_btn = QPushButton(QCoreApplication.translate("FindDialog", "Find All"))
        self.count_btn = QPushButton(QCoreApplication.translate("FindDialog", "Count"))
        self.highlight_all_btn = QPushButton(QCoreApplication.translate("FindDialog", "Highlight All"))
        self.clear_highlight_btn = QPushButton(QCoreApplication.translate("FindDialog", "Clear Highlight"))
        self.close_btn = QPushButton(QCoreApplication.translate("FindDialog", "Close"))
        
        button_layout.addWidget(self.find_next_btn)
        button_layout.addWidget(self.find_prev_btn)
        button_layout.addWidget(self.find_all_btn)
        button_layout.addWidget(self.count_btn)
        button_layout.addWidget(self.highlight_all_btn)
        button_layout.addWidget(self.clear_highlight_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
        # Count result label (bottom left)
        count_layout = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        count_layout.addWidget(self.count_label)
        count_layout.addStretch()
        layout.addLayout(count_layout)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.search_input.lineEdit().textChanged.connect(self.on_search_text_changed)
        self.search_input.lineEdit().returnPressed.connect(self.find_next)
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_all_btn.clicked.connect(self.find_all)
        self.count_btn.clicked.connect(self.count_matches)
        self.highlight_all_btn.clicked.connect(self.highlight_all)
        self.clear_highlight_btn.clicked.connect(self.clear_highlights)
        self.close_btn.clicked.connect(self.close)
    
    def load_search_history(self):
        """Load search history from config"""
        try:
            from config_manager import config_manager
            history = config_manager.get_search_history()
            self.search_input.clear()
            self.search_input.addItems(history)
            self.search_input.setCurrentText("")
        except Exception as e:
            logger.debug(f"Failed to load search history: {e}")
    
    def save_search_to_history(self, search_text: str):
        """Save search text to history"""
        if not search_text.strip():
            return
        try:
            from config_manager import config_manager
            config_manager.add_search_to_history(search_text)
            config_manager.save_config()
            # Reload history in combo box
            self.load_search_history()
            self.search_input.setCurrentText(search_text)
        except Exception as e:
            logger.debug(f"Failed to save search history: {e}")
        
    def set_text_edit(self, text_edit):
        """Set text editor to search"""
        self.text_edit = text_edit
        self.clear_highlights()
    
    def set_search_text(self, text):
        """Set initial search text"""
        if text:
            self.search_input.setCurrentText(text)
            # Select all text for easy replacement
            self.search_input.lineEdit().selectAll()
        
    def on_search_text_changed(self):
        """Handle search text changed"""
        if self.search_input.currentText() != self.last_search_text:
            self.last_position = 0
            self.clear_highlights()
            
    def find_next(self):
        """Find next occurrence"""
        search_text = self.search_input.currentText()
        if search_text:
            self.save_search_to_history(search_text)
        self.find_text(forward=True)
        
    def find_previous(self):
        """Find previous occurrence"""
        search_text = self.search_input.currentText()
        if search_text:
            self.save_search_to_history(search_text)
        self.find_text(forward=False)
        
    def find_text(self, forward=True):
        """Find text with optional regex support"""
        if not self.text_edit or not self.search_input.currentText():
            # logger.debug("find_text: No text_edit or search text")
            return False
            
        search_text = self.search_input.currentText()
        # logger.info(f"find_text: Searching for '{search_text}', forward={forward}")
        
        # Get search options
        from PySide6.QtGui import QTextDocument
        from PySide6.QtCore import QRegularExpression
        
        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindBackward
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindWholeWords
            
        # Get current cursor position
        cursor = self.text_edit.textCursor()
        # logger.debug(f"find_text: Current cursor position: {cursor.position()}")
        
        # If new search text, start from beginning/end
        if search_text != self.last_search_text:
            if forward:
                cursor.movePosition(cursor.MoveOperation.Start)
            else:
                cursor.movePosition(cursor.MoveOperation.End)
            self.last_search_text = search_text
            # logger.debug(f"find_text: New search, cursor moved to: {cursor.position()}")
            
        # Execute search (regex or plain text)
        if self.regex_mode.isChecked():
            # Regex search
            pattern_options = QRegularExpression.PatternOption.NoPatternOption
            if not self.case_sensitive.isChecked():
                pattern_options = QRegularExpression.PatternOption.CaseInsensitiveOption
            regex = QRegularExpression(search_text, pattern_options)
            found_cursor = self.text_edit.document().find(regex, cursor, flags)
        else:
            # Plain text search
            found_cursor = self.text_edit.document().find(search_text, cursor, flags)
        
        # logger.debug(f"find_text: First search result: isNull={found_cursor.isNull()}")
        
        if not found_cursor.isNull():
            # Found, select and scroll to position
            # logger.info(f"find_text: Found at position {found_cursor.position()}")
            self.text_edit.setTextCursor(found_cursor)
            self.text_edit.ensureCursorVisible()
            return True
        else:
            # Not found, search from the other end
            # logger.debug("find_text: Not found, wrapping search")
            if forward:
                cursor.movePosition(cursor.MoveOperation.Start)
            else:
                cursor.movePosition(cursor.MoveOperation.End)
            
            if self.regex_mode.isChecked():
                pattern_options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_sensitive.isChecked():
                    pattern_options = QRegularExpression.PatternOption.CaseInsensitiveOption
                regex = QRegularExpression(search_text, pattern_options)
                found_cursor = self.text_edit.document().find(regex, cursor, flags)
            else:
                found_cursor = self.text_edit.document().find(search_text, cursor, flags)
            
            # logger.debug(f"find_text: Wrapped search result: isNull={found_cursor.isNull()}")
            
            if not found_cursor.isNull():
                # logger.info(f"find_text: Found (wrapped) at position {found_cursor.position()}")
                self.text_edit.setTextCursor(found_cursor)
                self.text_edit.ensureCursorVisible()
                return True
        
        # logger.warning(f"find_text: '{search_text}' not found")
        return False
        
    def find_all(self):
        """Find all occurrences and show results window"""
        if not self.text_edit or not self.search_input.currentText():
            return
        
        search_text = self.search_input.currentText()
        self.save_search_to_history(search_text)
        
        # Find all matches
        matches = []
        from PySide6.QtGui import QTextDocument
        from PySide6.QtCore import QRegularExpression
        
        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindWholeWords
        
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        
        line_num = 1
        current_position = 0
        
        while True:
            if self.regex_mode.isChecked():
                # Regex search
                pattern_options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_sensitive.isChecked():
                    pattern_options = QRegularExpression.PatternOption.CaseInsensitiveOption
                regex = QRegularExpression(search_text, pattern_options)
                cursor = self.text_edit.document().find(regex, cursor, flags)
            else:
                # Plain text search
                cursor = self.text_edit.document().find(search_text, cursor, flags)
            
            if cursor.isNull():
                break
            
            # Get line number and context
            block = cursor.block()
            line_number = block.blockNumber() + 1
            line_text = block.text()
            match_position = cursor.selectionStart()
            
            matches.append({
                'line': line_number,
                'text': line_text,
                'position': match_position,
                'cursor': cursor
            })
        
        # Show results window
        if matches:
            if not self.find_all_window or not self.find_all_window.isVisible():
                self.find_all_window = FindAllResultsWindow(self, self.text_edit, matches, search_text)
                self.find_all_window.show()
            else:
                self.find_all_window.update_results(matches, search_text)
                self.find_all_window.raise_()
                self.find_all_window.activateWindow()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, 
                QCoreApplication.translate("FindDialog", "Find All"),
                QCoreApplication.translate("FindDialog", "No matches found."))
        
    def highlight_all(self):
        """Highlight all matching text"""
        if not self.text_edit or not self.search_input.currentText():
            # logger.debug("highlight_all: No text_edit or search text")
            return
            
        search_text = self.search_input.currentText()
        # logger.info(f"highlight_all: Highlighting '{search_text}'")
        self.save_search_to_history(search_text)
        self.clear_highlights()
        
        # Get search options
        from PySide6.QtGui import QTextDocument, QTextCharFormat, QColor
        from PySide6.QtCore import QRegularExpression
        
        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindWholeWords
            
        # Create highlight format - bright yellow background + black text for better contrast
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor(255, 255, 0, 160))  # Bright yellow background
        highlight_format.setForeground(QColor(0, 0, 0))           # Black text
        
        # Find all matches
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        
        extra_selections = []
        match_count = 0
        while True:
            if self.regex_mode.isChecked():
                # Regex search
                pattern_options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_sensitive.isChecked():
                    pattern_options = QRegularExpression.PatternOption.CaseInsensitiveOption
                regex = QRegularExpression(search_text, pattern_options)
                cursor = self.text_edit.document().find(regex, cursor, flags)
            else:
                # Plain text search
                cursor = self.text_edit.document().find(search_text, cursor, flags)
            
            if cursor.isNull():
                break
                
            match_count += 1
            # Create selection area
            from PySide6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight_format
            extra_selections.append(selection)
            
        # Apply highlights
        # logger.info(f"highlight_all: Found {match_count} matches, applying highlights")
        self.text_edit.setExtraSelections(extra_selections)
        self.highlights = extra_selections
        
    def clear_highlights(self):
        """清除所有高亮"""
        # logger.info("clear_highlights: Clearing all highlights")
        if self.text_edit:
            self.text_edit.setExtraSelections([])
        self.highlights = []
    
    def count_matches(self):
        """统计匹配数量并显示在左下角"""
        if not self.text_edit:
            return
            
        search_text = self.search_input.currentText()
        if not search_text:
            self.count_label.setText(QCoreApplication.translate("FindDialog", "Please enter search text"))
            return
        
        # Build search flags
        from PySide6.QtGui import QTextDocument
        from PySide6.QtCore import QRegularExpression
        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_word.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        
        # Count matches
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        
        count = 0
        while True:
            if self.regex_mode.isChecked():
                # Regex search
                pattern_options = QRegularExpression.PatternOption.NoPatternOption
                if not self.case_sensitive.isChecked():
                    pattern_options = QRegularExpression.PatternOption.CaseInsensitiveOption
                regex = QRegularExpression(search_text, pattern_options)
                cursor = self.text_edit.document().find(regex, cursor, flags)
            else:
                # Plain text search
                cursor = self.text_edit.document().find(search_text, cursor, flags)
            
            if cursor.isNull():
                break
            count += 1
        
        # Display result
        if count == 0:
            self.count_label.setText(QCoreApplication.translate("FindDialog", "No matches found"))
        elif count == 1:
            self.count_label.setText(QCoreApplication.translate("FindDialog", "Found 1 match"))
        else:
            self.count_label.setText(QCoreApplication.translate("FindDialog", "Found %n matches", "", count))
        
    def showEvent(self, event):
        """Handle dialog show event"""
        super().showEvent(event)
        self.search_input.setFocus()
        # Text is already selected if set_search_text was called
        # Otherwise select all existing text
        if not self.search_input.lineEdit().selectedText():
            self.search_input.lineEdit().selectAll()
        
    def closeEvent(self, event):
        """Handle dialog close event"""
        self.clear_highlights()
        super().closeEvent(event)


class FindAllResultsWindow(QDialog):
    """Find All Results Window - displays all search results in a list"""
    
    def __init__(self, parent=None, text_edit=None, matches=None, search_text=""):
        super().__init__(parent)
        self.text_edit = text_edit
        self.matches = matches or []
        self.search_text = search_text
        
        self.setWindowTitle(QCoreApplication.translate("FindAllResultsWindow", "Find All Results"))
        self.setModal(False)
        self.resize(WindowSize.CONNECTION_DIALOG_WIDTH, WindowSize.CONNECTION_DIALOG_HEIGHT)
        
        # Set window flags to stay on top but allow resizing and dragging
        current_flags = self.windowFlags()
        new_flags = current_flags | Qt.Tool
        # Ensure close button and system menu are preserved
        new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(new_flags)
        
        # Create UI
        self.setup_ui()
        
        # Populate results
        self.populate_results()
    
    def setup_ui(self):
        """Setup UI"""
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QAbstractItemView
        
        layout = QVBoxLayout(self)
        
        # Results info label
        self.info_label = QLabel()
        layout.addWidget(self.info_label)
        
        # Results list
        self.results_list = QListWidget()
        # Enable extended selection (Ctrl+Click for multiple, Shift+Click for range)
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results_list.itemDoubleClicked.connect(self.on_result_double_clicked)
        layout.addWidget(self.results_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.copy_btn = QPushButton(QCoreApplication.translate("FindAllResultsWindow", "Copy Selected"))
        self.copy_all_btn = QPushButton(QCoreApplication.translate("FindAllResultsWindow", "Copy All"))
        self.close_btn = QPushButton(QCoreApplication.translate("FindAllResultsWindow", "Close"))
        
        self.copy_btn.clicked.connect(self.copy_selected)
        self.copy_all_btn.clicked.connect(self.copy_all)
        self.close_btn.clicked.connect(self.close)
        
        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(self.copy_all_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
    
    def populate_results(self):
        """Populate results list"""
        self.results_list.clear()
        
        # Update info label
        count = len(self.matches)
        self.info_label.setText(
            QCoreApplication.translate("FindAllResultsWindow", "Found {0} match(es) for '{1}'").format(count, self.search_text)
        )
        
        # Add results to list
        for match in self.matches:
            line_num = match['line']
            line_text = match['text'].strip()
            # Limit line text length for display
            if len(line_text) > 2048:
                line_text = line_text[:2048] + "..."
            
            item_text = f"Line {line_num}: {line_text}"
            self.results_list.addItem(item_text)
    
    def on_result_double_clicked(self, item):
        """Handle result item double-click - jump to position in text"""
        row = self.results_list.row(item)
        if 0 <= row < len(self.matches):
            match = self.matches[row]
            
            # Create cursor at match position
            cursor = self.text_edit.textCursor()
            cursor.setPosition(match['position'])
            
            # Select the matched text
            block = cursor.block()
            block_start = block.position()
            match_start_in_block = match['position'] - block_start
            
            # Try to select the search text length
            cursor.setPosition(match['position'])
            cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(self.search_text))
            
            # Set cursor and ensure visible
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()
            self.text_edit.setFocus()
    
    def copy_selected(self):
        """Copy selected results to clipboard"""
        selected_items = self.results_list.selectedItems()
        if selected_items:
            # Collect all selected item texts
            selected_texts = [item.text() for item in selected_items]
            
            from PySide6.QtGui import QClipboard
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(selected_texts))
    
    def copy_all(self):
        """Copy all results to clipboard"""
        all_text = []
        for i in range(self.results_list.count()):
            all_text.append(self.results_list.item(i).text())
        
        if all_text:
            from PySide6.QtGui import QClipboard
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText("\n".join(all_text))
    
    def update_results(self, matches, search_text):
        """Update results with new search"""
        self.matches = matches
        self.search_text = search_text
        self.populate_results()


class ConnectionDialog(QDialog):
    # 定义信号
    connection_established = Signal()
    connection_disconnected = Signal()
    
    def __init__(self, parent=None):
        super(ConnectionDialog, self).__init__(parent)
        
        # 导入需要的模块
        from PySide6.QtCore import QTimer
        
        # 注意：不再需要垃圾回收，因为我们直接重用已存在的 JLink 对象
        # 这样可以避免不必要的卡顿
        
        # 🚫 暂时禁用进程冲突检测,因为它会阻塞UI响应
        # 用户可以通过日志查看"JLink already open"错误并手动处理
        # 如需启用,取消下面的注释:
        # import threading
        # threading.Thread(target=self._check_and_handle_jlink_conflicts, daemon=True).start()
        
        self.ui = Ui_ConnectionDialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/xexunrtt.ico"))
        self.setWindowTitle(QCoreApplication.translate("main_window", "Connection Configuration"))
        self.setWindowModality(Qt.ApplicationModal)
        
        # 设置窗口标志以避免在任务栏Aero Peek中显示
        # Tool窗口不会在任务栏显示预览，但保持可访问性
        current_flags = self.windowFlags()
        new_flags = current_flags | Qt.Tool
        # 确保保留关闭按钮和系统菜单
        new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(new_flags)
        
        logger.info("ConnectionDialog window flags set to prevent Aero Peek display")
        
        # 使用新的配置管理器
        self.config = config_manager
        
        # 异步迁移旧配置(不阻塞UI)
        def migrate_old_config():
            old_settings_file = os.path.join(os.getcwd(), "settings")
            if os.path.exists(old_settings_file):
                if self.config.migrate_from_pickle(old_settings_file):
                    try:
                        os.remove(old_settings_file)
                        logger.debug("旧配置文件已删除")
                    except:
                        pass
        QTimer.singleShot(0, migrate_old_config)

        self.start_state = False
        self.target_device = None
        self.rtt2uart = None
        self.connect_type = None
        
        # 根据配置设置默认值
        self.ui.checkBox__auto.setChecked(self.config.get_auto_reconnect())
        
        # 设置连接类型
        conn_type = self.config.get_connection_type()
        if conn_type == 'USB':
            self.ui.radioButton_usb.setChecked(True)
            self.usb_selete_slot()
        elif conn_type == 'TCP/IP':
            self.ui.radioButton_tcpip.setChecked(True)
        elif conn_type == 'Existing':
            self.ui.radioButton_existing.setChecked(True)

        self.ui.comboBox_Interface.addItem("JTAG")
        self.ui.comboBox_Interface.addItem("SWD")
        self.ui.comboBox_Interface.addItem("cJTAG")
        self.ui.comboBox_Interface.addItem("FINE")

        for i in range(len(speed_list)):
            self.ui.comboBox_Speed.addItem(str(speed_list[i]) + " kHz")

        for i in range(len(baudrate_list)):
            self.ui.comboBox_baudrate.addItem(str(baudrate_list[i]))

        # 异步扫描串口，避免阻塞 UI
        QTimer.singleShot(0, self.port_scan)

        # 兼容性：保留settings字典结构用于现有代码
        self.settings = {
            'device': self.config.get_device_list(),
            'device_index': self.config.get_device_index(),
            'interface': self.config.get_interface(),
            'speed': get_speed_index_from_value(self.config.get_speed()),  # 转换为索引
            'port': self.config.get_port_index(),
            'buadrate': get_baudrate_index_from_value(self.config.get_baudrate()),  # 转换为索引
            'lock_h': int(self.config.get_lock_horizontal()),
            'lock_v': int(self.config.get_lock_vertical()),
            'light_mode': int(self.config.get_light_mode()),
            'fontsize': self.config.get_fontsize(),
            'filter': [self.config.get_filter(i) if self.config.get_filter(i) else None for i in range(17, 33)],
            'cmd': self.config.get_command_history(),
            'serial_forward_tab': self.config.get_serial_forward_target_tab(),
            'serial_forward_mode': self.config.get_serial_forward_mode()
        }

        # 主窗口引用（由父窗口传入）
        self.main_window = parent
        
        # 初始化串口转发设置（UI文件中已定义控件）
        self._setup_serial_forward_controls()
        
        self.worker = Worker(self)
        self.worker.moveToThread(QApplication.instance().thread())  # 将Worker对象移动到GUI线程

        # 连接信号和槽
        self.worker.finished.connect(self.handleBufferUpdate)
        self.ui.addToBuffer = self.worker.addToBuffer
        
        # 启动Worker的日志刷新定时器
        self.worker.start_flush_timer()
        

        # 应用从INI配置加载的设置到UI控件
        self._load_ui_settings()
        
        # 根据配置文件中的实际值设置UI控件
        self._apply_config_to_ui()

        # 信号-槽
        self.ui.pushButton_Start.clicked.connect(self.start)
        self.ui.pushButton_scan.clicked.connect(self.port_scan)
        self.ui.pushButton_Selete_Device.clicked.connect(
            self.target_device_selete)
        self.ui.comboBox_Device.currentIndexChanged.connect(
            self.device_change_slot)
        self.ui.comboBox_Interface.currentIndexChanged.connect(
            self.interface_change_slot)
        self.ui.comboBox_Speed.currentIndexChanged.connect(
            self.speed_change_slot)
        self.ui.comboBox_Port.currentIndexChanged.connect(
            self.port_change_slot)
        self.ui.comboBox_baudrate.currentIndexChanged.connect(
            self.buadrate_change_slot)
        self.ui.checkBox_serialno.stateChanged.connect(
            self.serial_no_change_slot)
        # 安全地连接ComboBox信号
        if hasattr(self.ui, 'comboBox_serialno'):
            self.ui.comboBox_serialno.currentTextChanged.connect(
                self.serial_no_text_changed_slot)
        if hasattr(self.ui, 'pushButton_refresh_jlink'):
            self.ui.pushButton_refresh_jlink.clicked.connect(
                self._refresh_jlink_devices)
        self.ui.checkBox_resettarget.stateChanged.connect(
            self.reset_target_change_slot)
        self.ui.checkBox_log_split.stateChanged.connect(
            self.log_split_change_slot)
        self.ui.radioButton_usb.clicked.connect(self.usb_selete_slot)
        self.ui.radioButton_existing.clicked.connect(
            self.existing_session_selete_slot)
        
        # RTT Control Block 信号连接
        self.ui.radioButton_AutoDetection.clicked.connect(self.rtt_control_block_mode_changed)
        self.ui.radioButton_Address.clicked.connect(self.rtt_control_block_mode_changed)
        self.ui.radioButton_SearchRange.clicked.connect(self.rtt_control_block_mode_changed)
        self.ui.lineEdit_RTTAddress.textChanged.connect(self.rtt_control_block_address_changed)

        # 🔑 关键修复：每个物理 JLink 设备需要独立的 JLink() 对象实例
        # 但是，pylink 库不允许多个 JLink() 对象同时调用 open()
        # 解决方案：
        # 1. 如果是重连同一设备（相同序列号），重用该设备的 JLink 对象
        # 2. 如果是连接新设备，检查是否已有其他设备的 JLink 对象打开
        #    - 如果有，先关闭它，然后创建新的 JLink 对象
        #    - 如果没有，直接创建新的 JLink 对象
        
        self.jlink = None
        self.target_device_serial = None  # 将在 start() 中设置
        
        try:
            # 暂时创建一个 JLink 对象用于设备检测
            # 真正的连接会在 start() 中处理
            self.jlink = pylink.JLink()
            logger.info("Created new JLink object in ConnectionDialog.__init__ for device detection")
        except:
            logger.error('Find jlink dll failed', exc_info=True)
            raise Exception(QCoreApplication.translate("main_window", "Find jlink dll failed !"))
        
        # 初始化JLINK设备选择相关属性
        self.available_jlinks = []
        self.selected_jlink_serial = None
        
        # 检测可用的JLINK设备
        self._detect_jlink_devices()
        
        # 🔑 如果检测到多个设备，自动启用序列号选择功能
        if len(self.available_jlinks) > 1:
            if hasattr(self.ui, 'checkBox_serialno'):
                self.ui.checkBox_serialno.setChecked(True)
                logger.info(f"[AUTO] Detected {len(self.available_jlinks)} devices on dialog open, auto-enabled serial number selection")
                
                # 显示 ComboBox 和刷新按钮
                if hasattr(self.ui, 'comboBox_serialno'):
                    self.ui.comboBox_serialno.setVisible(True)
                if hasattr(self.ui, 'pushButton_refresh_jlink'):
                    self.ui.pushButton_refresh_jlink.setVisible(True)
                
                # 延迟自动打开下拉框，让用户选择设备
                if hasattr(self.ui, 'comboBox_serialno'):
                    # 延迟更长时间，确保对话框完全显示后再打开下拉框
                    QTimer.singleShot(300, lambda: self.ui.comboBox_serialno.showPopup() if hasattr(self.ui, 'comboBox_serialno') else None)
                    logger.info(f"[AUTO] Will open device selection dropdown after dialog is fully shown")
                
                # 🔑 初始状态：如果没有选择设备，禁用开始按钮
                if hasattr(self.ui, 'pushButton_Start'):
                    self.ui.pushButton_Start.setEnabled(False)
                    logger.info(f"[AUTO] Start button disabled initially: multiple devices, no selection")

        try:
            # 导出器件列表文件
            if self.jlink._library._path is not None and not self._device_database_exists():
                path_env = os.path.dirname(self.jlink._library._path)
                env = os.environ

                if self.jlink._library._windows or self.jlink._library._cygwin:
                    jlink_env = {'PATH': path_env}
                    env.update(jlink_env)

                    # 获取JLinkCommandFile.jlink的正确路径
                    jlink_cmd_file = self._get_jlink_command_file_path()
                    cmd = f'JLink.exe -CommandFile "{jlink_cmd_file}"'

                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                    subprocess.run(cmd, check=True, startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    subprocess.kill()

                elif sys.platform.startswith('linux'):
                    jlink_env = {}
                    jlink_cmd_file = self._get_jlink_command_file_path()
                    cmd = f'JLinkExe -CommandFile "{jlink_cmd_file}"'
                elif sys.platform.startswith('darwin'):
                    jlink_env = {}
                    jlink_cmd_file = self._get_jlink_command_file_path()
                    cmd = f'JLinkExe -CommandFile "{jlink_cmd_file}"'

        except Exception as e:
            logging.error(f'can not export devices xml file, error info: {e}')

    def closeEvent(self, e):
        try:
            # 检查主窗口是否正在关闭，如果是则直接关闭不做其他操作
            if self.main_window and self.main_window._is_closing:
                super().closeEvent(e)
                e.accept()
                return
                
            # 🚨 强制刷新所有缓冲区到文件（确保数据不丢失）
            # 注意: 这里保持同步执行,虽然可能稍慢,但能确保数据完整性
            if hasattr(self, 'worker') and hasattr(self.worker, 'force_flush_all_buffers'):
                try:
                    logger.info("ConnectionDialog closed, force refreshing all TAB buffers...")
                    self.worker.force_flush_all_buffers()
                except Exception as ex:
                    logger.error(f"Error force flushing ConnectionDialog buffers: {ex}")
            
            # 停止RTT连接(会自动关闭JLink)
            if self.rtt2uart is not None:
                try:
                    self.rtt2uart.stop()
                    # 清理rtt2uart对象引用
                    self.rtt2uart = None
                    logger.info("RTT2UART object cleaned up in closeEvent")
                except Exception as ex:
                    logger.error(f"Error stopping RTT: {ex}")
            
            # 清理JLink对象引用(不需要再次关闭,rtt2uart.stop()已经处理)
            if hasattr(self, 'jlink') and self.jlink is not None:
                try:
                    # 只删除引用,不再调用close()(避免重复关闭导致access violation)
                    del self.jlink
                    self.jlink = None
                    logger.info("JLink object reference cleaned up in closeEvent")
                except Exception as ex:
                    logger.warning(f"Error cleaning up JLink reference: {ex}")
            
            # 关闭RTT窗口
            # 主窗口由父窗口管理，不需要在这里关闭
            # if self.main_window is not None:
            #     try:
            #         self.main_window.close()
            #     except Exception as ex:
            #         logger.error(f"Error closing RTT main window: {ex}")
            
            # 停止工作线程
            if hasattr(self, 'worker'):
                try:
                    if hasattr(self.worker, 'buffer_flush_timer') and self.worker.buffer_flush_timer:
                        self.worker.buffer_flush_timer.stop()
                except:
                    pass
            
            # 保存当前配置
            try:
                # 保存当前UI设置到INI配置
                self._save_ui_settings()
                self.config.save_config()
            except Exception as ex:
                logger.warning(f"Failed to save settings: {ex}")
            
            # 等待其他线程结束，增加超时处理
            import time
            time.sleep(0.2)  # 给线程时间清理
            
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    if not is_dummy_thread(thread):
                        try:
                            thread.join(timeout=1.0)  # 增加超时
                        except:
                            pass
            
            super().closeEvent(e)
            e.accept()
            
        except Exception as ex:
            logger.error(f"Error during close event: {ex}")
            e.accept()  # 即使出错也要关闭窗口
    
    def _setup_serial_forward_controls(self):
        """初始化串口转发设置控件（控件已在UI文件中定义）"""
        # 创建按钮组确保互斥选择
        self.serial_forward_mode_group = QButtonGroup(self)
        self.serial_forward_mode_group.addButton(self.ui.radioButton_LOG)
        self.serial_forward_mode_group.addButton(self.ui.radioButton_DATA)
        
        # 初始化选择框内容
        self._update_serial_forward_combo()
        
        # 恢复保存的设置（只在初始化时执行）
        self._restore_saved_forward_settings()
        
        # 连接信号
        self.ui.comboBox_SerialForward.currentIndexChanged.connect(self._on_serial_forward_changed)
        self.ui.radioButton_LOG.toggled.connect(self._on_forward_mode_changed)
        self.ui.radioButton_DATA.toggled.connect(self._on_forward_mode_changed)
    
    def _load_ui_settings(self):
        """加载并应用UI设置"""
        # 应用设备列表
        device_list = self.config.get_device_list()
        if device_list:
            self.ui.comboBox_Device.addItems(device_list)
            device_index = self.config.get_device_index()
            if device_index < len(device_list):
                self.target_device = device_list[device_index]
                self.ui.comboBox_Device.setCurrentIndex(device_index)
        
        # 应用接口设置
        self.ui.comboBox_Interface.setCurrentIndex(self.config.get_interface())
        
        # 应用速度设置
        self.ui.comboBox_Speed.setCurrentIndex(self.config.get_speed())
        
        # 应用串口设置
        self.ui.comboBox_Port.setCurrentIndex(self.config.get_port_index())
        self.ui.comboBox_baudrate.setCurrentIndex(self.config.get_baudrate())
        
        # 应用其他设置
        self.ui.checkBox_resettarget.setChecked(self.config.get_reset_target())
        self.ui.checkBox_log_split.setChecked(self.config.get_log_split())
        
        # 应用序列号设置
        self.ui.comboBox_serialno.setCurrentText(self.config.get_serial_number())
        self.ui.lineEdit_ip.setText(self.config.get_ip_address())
        
        # 应用RTT Control Block设置
        rtt_mode = self.config.get_rtt_control_block_mode()
        
        if rtt_mode == 'address':
            self.ui.radioButton_Address.setChecked(True)
            rtt_address = self.config.get_rtt_address()
            if rtt_address:
                self.ui.lineEdit_RTTAddress.setText(rtt_address)
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "Example: 0x20000000"))
        elif rtt_mode == 'search_range':
            self.ui.radioButton_SearchRange.setChecked(True)
            rtt_range = self.config.get_rtt_search_range()
            if rtt_range:
                self.ui.lineEdit_RTTAddress.setText(rtt_range)
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "Syntax: <RangeStart [hex]> <RangeSize>, ..."))
        else:  # 'auto' or default
            self.ui.radioButton_AutoDetection.setChecked(True)
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "JLink automatically detects the RTT control block"))
        
        # 初始化设备列表
        self._initialize_device_combo()
        
        # 如果没有保存的设置，使用合理的默认值
        if not device_list:
            self.ui.comboBox_Interface.setCurrentIndex(1)  # SWD
            self.ui.comboBox_Speed.setCurrentIndex(19)     # 合适的速度
            self.ui.comboBox_baudrate.setCurrentIndex(SerialConfig.DEFAULT_BAUDRATE_INDEX)
            
            # 保存默认设置
            self.config.set_interface(1)
            self.config.set_speed(SerialConfig.DEFAULT_SPEED)
            self.config.set_baudrate(SerialConfig.DEFAULT_BAUDRATE)
    
    def _apply_config_to_ui(self):
        """根据配置文件中的实际值设置UI控件"""
        try:
            # 设置速度选择框
            speed_value = self.config.get_speed()
            speed_index = get_speed_index_from_value(speed_value)
            if speed_index < self.ui.comboBox_Speed.count():
                self.ui.comboBox_Speed.setCurrentIndex(speed_index)
            
            # 设置波特率选择框
            baudrate_value = self.config.get_baudrate()
            baudrate_index = get_baudrate_index_from_value(baudrate_value)
            if baudrate_index < self.ui.comboBox_baudrate.count():
                self.ui.comboBox_baudrate.setCurrentIndex(baudrate_index)
            
            # 设置接口选择框
            interface_index = self.config.get_interface()
            if interface_index < self.ui.comboBox_Interface.count():
                self.ui.comboBox_Interface.setCurrentIndex(interface_index)
            
            # 设置端口选择框
            port_index = self.config.get_port_index()
            if port_index < self.ui.comboBox_Port.count():
                self.ui.comboBox_Port.setCurrentIndex(port_index)
                
        except Exception as e:
            logger.debug(f"应用配置到UI时出错: {e}")
    
    def _save_ui_settings(self):
        """保存当前UI设置到配置"""
        try:
            # 保存设备设置
            if hasattr(self, 'target_device') and self.target_device:
                current_devices = [self.ui.comboBox_Device.itemText(i) for i in range(self.ui.comboBox_Device.count())]
                self.config.set_device_list(current_devices)
                self.config.set_device_index(self.ui.comboBox_Device.currentIndex())
            
            # 保存接口和速度设置
            self.config.set_interface(self.ui.comboBox_Interface.currentIndex())
            self.config.set_speed(speed_list[self.ui.comboBox_Speed.currentIndex()])
            
            # 保存串口设置
            self.config.set_port_index(self.ui.comboBox_Port.currentIndex())
            self.config.set_baudrate(baudrate_list[self.ui.comboBox_baudrate.currentIndex()])
            self.config.set_reset_target(self.ui.checkBox_resettarget.isChecked())
            self.config.set_log_split(self.ui.checkBox_log_split.isChecked())
            
            # 保存连接类型
            if self.ui.radioButton_usb.isChecked():
                self.config.set_connection_type('USB')
            elif self.ui.radioButton_tcpip.isChecked():
                self.config.set_connection_type('TCP/IP')
            elif self.ui.radioButton_existing.isChecked():
                self.config.set_connection_type('Existing')
            
            # 保存序列号和IP设置
            self.config.set_serial_number(self.ui.comboBox_serialno.currentText())
            self.config.set_ip_address(self.ui.lineEdit_ip.text())
            self.config.set_auto_reconnect(self.ui.checkBox__auto.isChecked())
            
            # 保存当前选中的端口名
            current_port_text = self.ui.comboBox_Port.currentText()
            if " - " in current_port_text:
                port_name = current_port_text.split(" - ")[0]
            else:
                port_name = current_port_text
            self.config.set_port_name(port_name)
            
            # 保存串口转发设置
            if hasattr(self.ui, 'comboBox_SerialForward'):
                self.config.set_serial_forward_target_tab(
                    self.ui.comboBox_SerialForward.itemData(self.ui.comboBox_SerialForward.currentIndex()) or -1
                )
                
                if hasattr(self.ui, 'radioButton_LOG') and self.ui.radioButton_LOG.isChecked():
                    self.config.set_serial_forward_mode('LOG')
                elif hasattr(self.ui, 'radioButton_DATA') and self.ui.radioButton_DATA.isChecked():
                    self.config.set_serial_forward_mode('DATA')
            
            # 如果有主窗口，保存主窗口的UI设置
            if self.main_window:
                self._save_main_window_settings()
            
        except Exception as e:
            logger.warning(f"Failed to save UI settings: {e}")
    
    def _save_main_window_settings(self):
        """保存主窗口的UI设置"""
        try:
            if hasattr(self.main_window.ui, 'light_checkbox'):
                self.config.set_light_mode(self.main_window.ui.light_checkbox.isChecked())
            
            if hasattr(self.main_window.ui, 'fontsize_box'):
                self.config.set_fontsize(self.main_window.ui.fontsize_box.value())
            
            # 注意：滚动条锁定功能已移至DeviceMdiWindow，不再保存LockH/LockV状态
            
            # 保存过滤器设置
            # 🔑 修复：必须保存所有filter的状态，包括空值和默认"filter"文本
            # 否则配置文件中的旧filter值不会被清除
            # MDI 架构：筛选器保存由 DeviceMdiWindow 管理
            # 这里只需要确保 config 对象中的筛选器数据已经同步
            # 筛选器在 DeviceMdiWindow 中编辑时会实时更新到 config 对象
            if hasattr(self.main_window, '_filters_loaded') and self.main_window._filters_loaded:
                # 筛选器已经在 config 对象中，无需额外操作
                pass
            
            # 保存命令历史
            if hasattr(self.main_window.ui, 'cmd_buffer'):
                commands = []
                for i in range(self.main_window.ui.cmd_buffer.count()):
                    cmd_text = self.main_window.ui.cmd_buffer.itemText(i)
                    if cmd_text.strip():
                        commands.append(cmd_text)
                # 命令历史通过config_manager单独管理，这里不需要特别处理
                
        except Exception as e:
            logger.warning(f"Failed to save main window settings: {e}")
    
    def _update_serial_forward_combo(self):
        """更新串口转发选择框的内容"""
        if not hasattr(self.ui, 'comboBox_SerialForward'):
            return
        
        # 检查主窗口的TAB是否已经初始化完成
        # MDI 架构：检查当前活动的设备会话是否有 MDI 窗口
        tab_ready = False
        active_session = None
        if self.main_window:
            active_session = self.main_window._get_active_device_session()
            if active_session and active_session.mdi_window:
                tab_ready = True
            
        # 临时断开信号连接，避免在更新过程中触发不必要的事件
        # 使用blockSignals更安全的方式
        self.ui.comboBox_SerialForward.blockSignals(True)
        
        # 清空现有选项
        self.ui.comboBox_SerialForward.clear()
        
        # 添加禁用选项
        self.ui.comboBox_SerialForward.addItem(QCoreApplication.translate("dialog", "Disable Forward"), -1)
        
        # 根据选中的模式添加不同的选项
        if hasattr(self.ui, 'radioButton_LOG') and self.ui.radioButton_LOG.isChecked():
            # LOG模式：显示所有TAB页面
            self.ui.comboBox_SerialForward.addItem(QCoreApplication.translate("dialog", "Current Tab"), 'current_tab')
            
            # MDI 架构：从当前活动的设备会话获取 TAB 列表
            if tab_ready and active_session and active_session.mdi_window:
                mdi_window = active_session.mdi_window
                for i in range(MAX_TAB_SIZE):
                    tab_text = mdi_window.tab_widget.tabText(i)

                    # 根据索引构建显示文本
                    if i == 0:
                        # ALL页面（索引0）
                        display_text = QCoreApplication.translate('dialog', '%s (%s)') % (tab_text, QCoreApplication.translate('dialog', 'All Data'))
                    elif i < 17:
                        # RTT通道（索引1-16），显示"通道 0"到"通道 15"
                        # tab_text应该是"0"到"15"
                        display_text = QCoreApplication.translate('dialog', 'Channel %s') % tab_text
                    else:
                        # 筛选标签页（索引17+）
                        filter_translated = QCoreApplication.translate("main_window", "filter")
                        if tab_text == "filter" or tab_text == filter_translated or tab_text == "+":
                            display_text = QCoreApplication.translate('dialog', 'Filter %s: (%s)') % (i-16, QCoreApplication.translate('dialog', 'Not Set'))
                        else:
                            display_text = QCoreApplication.translate('dialog', 'Filter %s: %s') % (i-16, tab_text)
                    
                    self.ui.comboBox_SerialForward.addItem(display_text, i)
        
        elif hasattr(self.ui, 'radioButton_DATA') and self.ui.radioButton_DATA.isChecked():
            # DATA模式：只显示RTT信道1
            self.ui.comboBox_SerialForward.addItem(QCoreApplication.translate("dialog", "RTT Channel 1 (Raw Data)"), 'rtt_channel_1')
        
        # 恢复保存的设置（只在初始化时执行，不在每次更新时重置）
        # 这里不再重置单选框状态，避免用户选择被覆盖
        # if 'serial_forward_mode' in self.settings:
        #     forward_mode = self.settings['serial_forward_mode']
        #     if forward_mode == 'DATA' and hasattr(self, 'radioButton_DATA'):
        #         self.radioButton_DATA.setChecked(True)
        #     elif hasattr(self, 'radioButton_LOG'):
        #         self.radioButton_LOG.setChecked(True)
        
        # 不在这里恢复选择框的选中项，避免覆盖用户的当前选择
        # 选择框的恢复由_restore_saved_forward_settings方法处理
        
        # 重新启用信号
        self.ui.comboBox_SerialForward.blockSignals(False)
    
    def _restore_saved_forward_settings(self):
        """恢复保存的转发设置（只在初始化时调用）"""
        # 恢复单选框状态
        if 'serial_forward_mode' in self.settings:
            forward_mode = self.settings['serial_forward_mode']
            if forward_mode == 'DATA' and hasattr(self.ui, 'radioButton_DATA'):
                self.ui.radioButton_DATA.setChecked(True)
            elif hasattr(self.ui, 'radioButton_LOG'):
                self.ui.radioButton_LOG.setChecked(True)
        
        # 重新更新选择框内容以匹配单选框状态
        self._update_serial_forward_combo()
        
        # 恢复选择框的选中项
        if 'serial_forward_tab' in self.settings:
            forward_tab = self.settings['serial_forward_tab']
            for i in range(self.ui.comboBox_SerialForward.count()):
                if self.ui.comboBox_SerialForward.itemData(i) == forward_tab:
                    self.ui.comboBox_SerialForward.setCurrentIndex(i)
                    break
    
    def _on_forward_mode_changed(self):
        """转发模式发生变化时的处理"""
        # 添加调试信息
        mode = 'DATA' if (hasattr(self.ui, 'radioButton_DATA') and self.ui.radioButton_DATA.isChecked()) else 'LOG'
        logger.debug(f'Forward mode changed to: {mode}')
        
        # 更新选择框内容
        self._update_serial_forward_combo()
        
        # 应用新的转发设置
        self._on_serial_forward_changed(self.ui.comboBox_SerialForward.currentIndex())
    
    def _on_serial_forward_changed(self, index):
        """串口转发选择发生变化时的处理"""
        if not hasattr(self.ui, 'comboBox_SerialForward'):
            return
            
        selected_tab = self.ui.comboBox_SerialForward.itemData(index)
        
        # 获取转发模式
        forward_mode = 'LOG' if (hasattr(self.ui, 'radioButton_LOG') and self.ui.radioButton_LOG.isChecked()) else 'DATA'
        
        # 更新串口转发设置
        if self.rtt2uart:
            self.rtt2uart.set_serial_forward_config(selected_tab, forward_mode)
        
        # 保存设置
        self.settings['serial_forward_tab'] = selected_tab
        self.settings['serial_forward_mode'] = forward_mode
        
        # 同步保存到INI配置
        self.config.set_serial_forward_target_tab(selected_tab)
        self.config.set_serial_forward_mode(forward_mode)
        
        # 显示状态信息
        if selected_tab == -1:
            self.ui.status.setText(QCoreApplication.translate("dialog", "Forward Disabled"))
        else:
            tab_name = self.ui.comboBox_SerialForward.currentText()
            mode_text = QCoreApplication.translate("dialog", "LOG Mode") if forward_mode == 'LOG' else QCoreApplication.translate("dialog", "DATA Mode")
            self.ui.status.setText(QCoreApplication.translate("dialog", "{} - {}").format(mode_text, tab_name))

    def port_scan(self):
        port_list = list(serial.tools.list_ports.comports())
        self.ui.comboBox_Port.clear()
        port_list.sort()
        for port in port_list:
            try:
                # 不实际打开串口，只是列出可用的串口
                # 避免与其他程序冲突或阻塞
                
                # 获取友好名称并截取前20个字符
                description = port.description if hasattr(port, 'description') else ""
                if description:
                    # 移除重复的端口名信息，并截取有用部分
                    description = description.replace(f"({port.device})", "").strip()
                    if len(description) > 20:
                        description = description[:20] + "..."
                    display_text = f"{port.device} - {description}"
                else:
                    display_text = port.device
                
                self.ui.comboBox_Port.addItem(display_text)
            except Exception as e:
                logger.warning(f'Error adding port {port.device}: {e}')
                pass
    
    def get_selected_port_name(self):
        """从显示文本中提取实际的端口名"""
        display_text = self.ui.comboBox_Port.currentText()
        if " - " in display_text:
            return display_text.split(" - ")[0]
        return display_text

    def start(self):
        if self.start_state == False:
            logger.debug('click start button')
            try:
                device_interface = None
                # USB或者TCP/IP方式接入需要选择配置
                if not self.ui.radioButton_existing.isChecked():
                    if self.target_device is not None:
                        selete_interface = self.ui.comboBox_Interface.currentText()
                        if (selete_interface == 'JTAG'):
                            device_interface = pylink.enums.JLinkInterfaces.JTAG
                        elif (selete_interface == 'SWD'):
                            device_interface = pylink.enums.JLinkInterfaces.SWD
                        elif (selete_interface == 'cJTAG'):
                            device_interface = None
                        elif (selete_interface == 'FINE'):
                            device_interface = pylink.enums.JLinkInterfaces.FINE
                        else:
                            device_interface = pylink.enums.JLinkInterfaces.SWD

                        # 启动后不能再进行配置
                        self.ui.comboBox_Device.setEnabled(False)
                        self.ui.pushButton_Selete_Device.setEnabled(False)
                        self.ui.comboBox_Interface.setEnabled(False)
                        self.ui.comboBox_Speed.setEnabled(False)
                        self.ui.comboBox_Port.setEnabled(False)
                        self.ui.comboBox_baudrate.setEnabled(False)
                        self.ui.pushButton_scan.setEnabled(False)
                       

                    else:
                        raise Exception(QCoreApplication.translate("main_window", "Please selete the target device !"))
                    
                # 获取接入方式的参数
                if self.ui.radioButton_usb.isChecked():
                    if self.ui.checkBox_serialno.isChecked():
                        # 从ComboBox获取选择的设备序列号
                        selected_text = self.ui.comboBox_serialno.currentText().strip()
                        
                        # 检查是否有有效选择
                        if selected_text and selected_text != "":
                            # 提取实际的序列号（去除⭐标记和编号）
                            if selected_text.startswith("⭐#"):
                                # 格式: ⭐#0 序列号
                                selected_text = selected_text.split(" ", 1)[1] if " " in selected_text else ""
                            elif selected_text.startswith("#"):
                                # 格式: #0 序列号
                                selected_text = selected_text.split(" ", 1)[1] if " " in selected_text else ""
                            
                            connect_para = selected_text
                            
                            # 保存选择到配置
                            self.config.set_last_jlink_serial(connect_para)
                            self.config.add_preferred_jlink_serial(connect_para)
                            self.config.save_config()
                        else:
                            # 当ComboBox未选择设备时，回退到原有的JLINK内置选择框
                            logger.info("ComboBox device not selected, using JLINK built-in selector")
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "No device serial number specified, using JLINK built-in device selector"))
                            
                            if len(self.available_jlinks) > 1:
                                if not self._select_jlink_device():
                                    # 用户取消选择，停止连接
                                    return
                                connect_para = self.selected_jlink_serial
                            elif len(self.available_jlinks) == 1:
                                self.selected_jlink_serial = self.available_jlinks[0]['serial']
                                connect_para = self.selected_jlink_serial
                            else:
                                # 没有检测到设备，使用空参数让JLINK自动选择
                                connect_para = None
                    else:
                        # 未勾选序列号选项，使用原有逻辑
                        if len(self.available_jlinks) > 1:
                            if not self._select_jlink_device():
                                # 用户取消选择，停止连接
                                return
                        elif len(self.available_jlinks) == 1:
                            self.selected_jlink_serial = self.available_jlinks[0]['serial']
                        connect_para = self.selected_jlink_serial if hasattr(self, 'selected_jlink_serial') else None
                elif self.ui.radioButton_tcpip.isChecked():
                    connect_para = self.ui.lineEdit_ip.text()
                elif self.ui.radioButton_existing.isChecked():
                    connect_para = self.ui.checkBox__auto.isChecked()
                else:
                    connect_para = None
                    
                # 检查是否需要执行重置连接
                if self.ui.checkBox_resettarget.isChecked():
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Reset connection option detected, starting connection reset..."))
                    self.perform_connection_reset()
                    # 重置完成后取消勾选
                    self.ui.checkBox_resettarget.setChecked(False)
                    self.config.set_reset_target(False)
                    self.config.save_config()
                
                self.start_state = True
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Stop"))
                
                # 获取日志拆分配置
                log_split_enabled = self.config.get_log_split()
                # last_log_directory 功能已移除
                
                # 获取当前选择的设备索引
                device_index = self._get_current_device_index(connect_para)
                
                # 🔍 调试信息：显示设备选择详情
                combo_index = self.ui.comboBox_serialno.currentIndex()
                combo_text = self.ui.comboBox_serialno.currentText()
                logger.debug(f"[DEBUG] Device selection info:")
                logger.debug(f"   ComboBox索引: {combo_index}")
                logger.debug(f"   ComboBox文本: {combo_text}")
                logger.debug(f"   连接参数: {connect_para}")
                logger.debug(f"   计算的设备索引: {device_index}")
                logger.debug(f"   可用设备数量: {len(self.available_jlinks)}")
                if self.available_jlinks:
                    for i, dev in enumerate(self.available_jlinks):
                        marker = "=>" if i == device_index else "  "
                        logger.debug(f"   {marker} #{i}: {dev['serial']} ({dev['product_name']})")
                
                # 🔑 关键修复：在创建 rtt2uart 之前，正确处理 JLink 对象
                # 策略：
                # 1. 如果是重连同一设备（相同序列号），重用该设备的 JLink 对象
                # 2. 如果是连接不同设备，需要创建新的 JLink 对象
                #    但 pylink 不允许多个 JLink 对象同时打开，所以需要先关闭其他设备的 JLink
                
                # 检查是否是重连同一设备
                existing_session_for_same_device = None
                if hasattr(self.main_window, 'device_sessions'):
                    for session in self.main_window.device_sessions:
                        if session.device_serial == connect_para:
                            existing_session_for_same_device = session
                            break
                
                if existing_session_for_same_device:
                    # 重连同一设备，重用其 JLink 对象
                    if existing_session_for_same_device.connection_dialog and hasattr(existing_session_for_same_device.connection_dialog, 'jlink'):
                        old_jlink = existing_session_for_same_device.connection_dialog.jlink
                        # 删除临时创建的 JLink 对象
                        if hasattr(self, 'jlink') and self.jlink != old_jlink:
                            try:
                                # 不要调用 close()，因为这个 JLink 对象还没有 open()
                                del self.jlink
                            except:
                                pass
                        # 使用已存在的 JLink 对象
                        self.jlink = old_jlink
                        logger.info(f"✅ Reusing existing JLink object for same device {connect_para}")
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Reusing existing JLink connection for same device"))
                else:
                    # 连接不同设备，使用新创建的 JLink 对象（在 __init__ 中创建的）
                    # pylink 库支持多个 JLink() 对象同时存在，每个对象连接不同的物理设备
                    logger.info(f"Using new JLink object for device {connect_para}")
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Connecting new device with independent JLink connection..."))
                
                # 获取RTT Control Block配置
                rtt_cb_mode = self.config.get_rtt_control_block_mode()
                rtt_address = self.config.get_rtt_address() if rtt_cb_mode == 'address' else ''
                rtt_search_range = self.config.get_rtt_search_range() if rtt_cb_mode == 'search_range' else ''
                
                self.rtt2uart = rtt_to_serial(
                    self.worker, 
                    self.jlink, 
                    self.connect_type, 
                    connect_para, 
                    self.target_device, 
                    self.get_selected_port_name(), 
                    self.ui.comboBox_baudrate.currentText(), 
                    device_interface, 
                    speed_list[self.ui.comboBox_Speed.currentIndex()], 
                    False,  # reset
                    log_split_enabled, 
                    self.main_window.window_id, 
                    device_index,
                    rtt_cb_mode,  # RTT Control Block模式
                    rtt_address,  # RTT地址
                    rtt_search_range  # RTT搜索范围
                )  # 重置后不再需要在rtt2uart中重置

                # 🔧 在start()之前设置JLink日志回调，确保所有日志都能显示
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.rtt2uart.set_jlink_log_callback(self.main_window.append_jlink_log)
                    # 显示连接开始信息
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "开始连接设备: %s") % str(self.target_device))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "连接类型: %s") % str(self.connect_type))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "串口: %s, 波特率: %s") % (self.get_selected_port_name(), self.ui.comboBox_baudrate.currentText()))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "RTT连接启动成功"))
                    
                    # 🔍 调试信息：确认设备连接
                    device_info = f"USB_{device_index}_{connect_para}" if connect_para else f"USB_{device_index}"
                    logger.debug(f"[DEVICE] Connection confirmed: {device_info}")
                    logger.debug(f"   目标设备: {self.target_device}")
                    logger.debug(f"   连接类型: {self.connect_type}")

                self.rtt2uart.start()
                
                # last_log_directory 功能已移除，每次启动使用新的日志文件夹
                
                # 检查是否有待启用的JLink文件日志
                if hasattr(self.main_window, 'pending_jlink_log_file'):
                    try:
                        self.rtt2uart.jlink.set_log_file(self.main_window.pending_jlink_log_file)
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging enabled: %s") % self.main_window.pending_jlink_log_file)
                            # 启动跟随
                            if hasattr(self.main_window, '_start_jlink_log_tailer'):
                                self.main_window._start_jlink_log_tailer(self.main_window.pending_jlink_log_file)
                    except Exception as e:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Failed to enable file logging: %s") % str(e))
                
                # 应用串口转发设置
                if hasattr(self.ui, 'comboBox_SerialForward'):
                    selected_tab = self.ui.comboBox_SerialForward.itemData(self.ui.comboBox_SerialForward.currentIndex())
                    forward_mode = 'LOG' if (hasattr(self.ui, 'radioButton_LOG') and self.ui.radioButton_LOG.isChecked()) else 'DATA'
                    
                    if selected_tab is not None:
                        self.rtt2uart.set_serial_forward_config(selected_tab, forward_mode)
                        if hasattr(self.main_window, 'append_jlink_log'):
                            if selected_tab == -1:
                                pass
                                #self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Serial forwarding disabled"))
                            else:
                                tab_name = self.ui.comboBox_SerialForward.currentText()
                                mode_text = QCoreApplication.translate("main_window", "LOG Mode") if forward_mode == 'LOG' else QCoreApplication.translate("main_window", "DATA Mode")
                                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Serial forwarding enabled: %s - %s") % (mode_text, tab_name))
                
                # 更新串口转发选择框（在连接成功后更新TAB列表）
                self._update_serial_forward_combo()
                
                # 发送连接成功信号
                self.connection_established.emit()
                
                # 隐藏连接对话框
                self.hide()

            except Exception as errors:
                QMessageBox.critical(self, "Errors", str(errors))
                # Existing方式不需要选择配置，继续禁用，不恢复
                if self.ui.radioButton_existing.isChecked() == False:
                    # 停止后才能再次配置
                    self.ui.comboBox_Device.setEnabled(True)
                    self.ui.pushButton_Selete_Device.setEnabled(True)
                    self.ui.comboBox_Interface.setEnabled(True)
                    self.ui.comboBox_Speed.setEnabled(True)
                    self.ui.comboBox_Port.setEnabled(True)
                    self.ui.comboBox_baudrate.setEnabled(True)
                    self.ui.pushButton_scan.setEnabled(True)
                    
                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))

        else:
            logger.debug('click stop button')
            try:
                # Existing方式不需要选择配置，继续禁用，不恢复
                if self.ui.radioButton_existing.isChecked() == False:
                    # 停止后才能再次配置
                    self.ui.comboBox_Device.setEnabled(True)
                    self.ui.pushButton_Selete_Device.setEnabled(True)
                    self.ui.comboBox_Interface.setEnabled(True)
                    self.ui.comboBox_Speed.setEnabled(True)
                    self.ui.comboBox_Port.setEnabled(True)
                    self.ui.comboBox_baudrate.setEnabled(True)
                    self.ui.pushButton_scan.setEnabled(True)
                    

                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Stopping RTT connection..."))
                
                # 🚨 断开连接前强制刷新所有缓冲区到文件（确保数据不丢失）
                if hasattr(self, 'worker') and hasattr(self.worker, 'force_flush_all_buffers'):
                    try:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Saving all TAB data to files..."))
                        self.worker.force_flush_all_buffers()
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "All TAB data saved"))
                    except Exception as ex:
                        logger.error(f"断开连接时强制刷新缓冲区出错: {ex}")
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Data save error')}: {ex}")
                
                self.rtt2uart.stop()
                
                # 发送连接断开信号
                self.connection_disconnected.emit()
                
                # 🔄 立即更新主窗口状态栏显示
                if self.main_window and hasattr(self.main_window, 'update_status_bar'):
                    self.main_window.update_status_bar()
                
                # 断开连接时不自动显示连接对话框
                # 用户可以通过菜单或快捷键手动打开连接设置
                pass

                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
            except:
                logger.error('Stop rtt2uart failed', exc_info=True)
                pass
    
    # 删除了不再需要的_apply_saved_settings_to_main_window方法
    
    def get_jlink_devices_list_file(self):
        """获取JLink设备数据库文件路径，支持开发环境和打包后的资源访问"""
        # 1. 首先尝试读取开发环境中的资源文件
        try:
            # 尝试从resources_rc中获取JLinkDevicesBuildIn.xml
            import resources_rc
            
            # 检查资源文件是否存在于当前工作目录中
            current_dir = os.getcwd()
            db_file_path = os.path.join(current_dir, "JLinkDevicesBuildIn.xml")
            
            if os.path.exists(db_file_path):
                logger.info(f"Using local device database: {db_file_path}")
                return db_file_path
            
        except ImportError:
            logger.warning("resources_rc module not found, trying alternative methods")
        except Exception as e:
            logger.warning(f"Failed to locate JLinkDevicesBuildIn.xml from resources: {e}")
        
        # 如果都找不到，抛出异常
        raise Exception(QCoreApplication.translate("main_window", "Can not find device database !"))
    
    def _device_database_exists(self):
        """检查设备数据库文件是否存在"""
        try:
            self.get_jlink_devices_list_file()
            return True
        except Exception:
            return False
    
    def _check_and_handle_jlink_conflicts(self):
        """检测并处理JLink占用冲突"""
        try:
            import psutil
            import os
            
            # 获取当前进程PID和父进程PID
            current_pid = os.getpid()
            try:
                current_proc = psutil.Process(current_pid)
                parent_pid = current_proc.ppid()  # 获取父进程PID
                logger.info(f"当前进程PID: {current_pid}, 父进程PID: {parent_pid}")
            except Exception as e:
                logger.warning(f"无法获取父进程信息: {e}")
                parent_pid = None
            
            xexunrtt_processes = []
            
            # 只查找运行XexunRTT的进程(main_window.py或XexunRTT.exe)
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_pid = proc.info['pid']
                    
                    # 排除当前进程和父进程
                    if proc_pid == current_pid:
                        logger.debug(f"跳过当前进程 PID: {proc_pid}")
                        continue
                    if parent_pid and proc_pid == parent_pid:
                        logger.debug(f"跳过父进程(虚拟环境启动器) PID: {proc_pid}")
                        continue
                    
                    cmdline = proc.info['cmdline'] if proc.info['cmdline'] else []
                    cmdline_str = ' '.join(cmdline).lower()
                    
                    # 检查是否是XexunRTT相关进程
                    is_xexunrtt = False
                    if 'xexunrtt.exe' in cmdline_str or 'xexunrtt_v' in cmdline_str:
                        is_xexunrtt = True
                    elif 'python' in proc.info['name'].lower() and 'main_window.py' in cmdline_str:
                        is_xexunrtt = True
                    
                    if is_xexunrtt:
                        logger.info(f"发现XexunRTT进程 PID: {proc_pid}, 名称: {proc.info['name']}, 命令行: {cmdline_str[:100]}")
                        xexunrtt_processes.append({
                            'pid': proc_pid,
                            'name': proc.info['name'],
                            'cmdline': ' '.join(cmdline) if cmdline else 'N/A'
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if xexunrtt_processes:
                logger.warning(f"检测到 {len(xexunrtt_processes)} 个其他XexunRTT进程可能占用JLink")
                
                # 构建提示信息
                process_info = "\n".join([
                    f"PID: {p['pid']} - {p['name']}\n{QCoreApplication.translate('main_window', 'Command line')}: {p['cmdline'][:100]}..."
                    for p in xexunrtt_processes[:5]  # 最多显示5个
                ])
                
                if len(xexunrtt_processes) > 5:
                    process_info += f"\n... {QCoreApplication.translate('main_window', 'and %n more process(es)', '', len(xexunrtt_processes) - 5)}"
                
                # 显示对话框让用户选择
                from PySide6.QtWidgets import QMessageBox
                from PySide6.QtCore import Qt
                msg_box = QMessageBox(self.parent())
                msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
                msg_box.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT Process Conflict"))
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setText(QCoreApplication.translate("main_window", 
                    "Detected %n other XexunRTT process(es) running, which may occupy the JLink device.\n\n"
                    "If you encounter \"JLink already open\" error, you can choose to terminate these processes.", 
                    "", len(xexunrtt_processes)))
                msg_box.setDetailedText(process_info)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                msg_box.button(QMessageBox.StandardButton.Yes).setText(QCoreApplication.translate("main_window", "Terminate Old XexunRTT Processes"))
                msg_box.button(QMessageBox.StandardButton.No).setText(QCoreApplication.translate("main_window", "Ignore and Continue"))
                
                result = msg_box.exec()
                
                if result == QMessageBox.StandardButton.Yes:
                    # 用户选择终止进程
                    killed_count = 0
                    for proc_info in xexunrtt_processes:
                        try:
                            proc = psutil.Process(proc_info['pid'])
                            proc.terminate()  # 先尝试优雅终止
                            proc.wait(timeout=2)  # 等待2秒
                            killed_count += 1
                            logger.info(f"✅ 已终止进程 PID: {proc_info['pid']}")
                        except psutil.TimeoutExpired:
                            # 如果优雅终止失败,强制杀死
                            try:
                                proc.kill()
                                killed_count += 1
                                logger.info(f"✅ 已强制终止进程 PID: {proc_info['pid']}")
                            except Exception as e:
                                logger.error(f"❌ 无法终止进程 PID {proc_info['pid']}: {e}")
                        except Exception as e:
                            logger.error(f"❌ 终止进程失败 PID {proc_info['pid']}: {e}")
                    
                    if killed_count > 0:
                        QMessageBox.information(
                            self.parent(),
                            QCoreApplication.translate("main_window", "Process Termination Completed"),
                            QCoreApplication.translate("main_window", 
                                "Successfully terminated %n process(es).\n\n"
                                "You can now try to connect to the JLink device.", 
                                "", killed_count)
                        )
                        logger.info(f"🎯 用户选择终止进程,已清理 {killed_count} 个进程")
                else:
                    logger.info("用户选择忽略进程冲突警告")
                    
        except ImportError:
            logger.warning("psutil模块未安装,无法检测进程冲突")
        except Exception as e:
            logger.error(f"检测JLink冲突时出错: {e}", exc_info=True)

    def target_device_selete(self):
        # 传入主窗口作为parent，以便应用相同的主题样式
        device_ui = DeviceSelectDialog(self.main_window)
        result = device_ui.exec()
        
        # 📋 修复：只有用户确认选择（不是取消）且选择了有效设备时才更新
        if result == QDialog.Accepted:
            selected_device = device_ui.get_target_device()
            
            # 只有选择了有效设备才更新
            if selected_device:
                self.target_device = selected_device

                if self.target_device not in self.settings['device']:
                    self.settings['device'].append(self.target_device)
                    self.ui.comboBox_Device.addItem(self.target_device)
                
                # 选择新添加的项目
                index = self.ui.comboBox_Device.findText(self.target_device)
                if index != -1:
                    self.ui.comboBox_Device.setCurrentIndex(index)
                    # 保存设备选择到配置文件
                    self.config.set_device_list(self.settings['device'])
                    self.config.set_device_index(index)
                    self.config.save_config()
                # 刷新显示
                self.ui.comboBox_Device.update()
        # 如果用户取消或没有选择设备，保持原有的设备选择不变
        
    def device_change_slot(self, index):
        self.settings['device_index'] = index
        self.target_device = self.ui.comboBox_Device.currentText()
        # 同步保存到INI配置
        self.config.set_device_index(index)
        self.config.save_config()

    def interface_change_slot(self, index):
        self.settings['interface'] = index
        # 同步保存到INI配置
        self.config.set_interface(index)
        self.config.save_config()

    def speed_change_slot(self, index):
        self.settings['speed'] = index
        # 同步保存到INI配置
        self.config.set_speed(speed_list[index])  # 保存实际值而不是索引
        self.config.save_config()

    def port_change_slot(self, index):
        self.settings['port'] = index
        # 同步保存到INI配置
        self.config.set_port_index(index)
        self.config.save_config()

    def buadrate_change_slot(self, index):
        self.settings['buadrate'] = index
        # 同步保存到INI配置
        self.config.set_baudrate(baudrate_list[index])  # 保存实际值而不是索引
        self.config.save_config()

    def serial_no_change_slot(self):
        try:
            if self.ui.checkBox_serialno.isChecked():
                # 显示ComboBox和刷新按钮
                if hasattr(self.ui, 'comboBox_serialno'):
                    self.ui.comboBox_serialno.setVisible(True)
                if hasattr(self.ui, 'pushButton_refresh_jlink'):
                    self.ui.pushButton_refresh_jlink.setVisible(True)
                
                # 当勾选序列号时，刷新设备列表
                self._refresh_jlink_devices()
            else:
                # 隐藏ComboBox和刷新按钮
                if hasattr(self.ui, 'comboBox_serialno'):
                    self.ui.comboBox_serialno.setVisible(False)
                if hasattr(self.ui, 'pushButton_refresh_jlink'):
                    self.ui.pushButton_refresh_jlink.setVisible(False)
        except Exception as e:
            logger.error(f"Error in serial_no_change_slot: {e}")
    
    def serial_no_text_changed_slot(self, text):
        """序列号文本变更处理"""
        # 当用户选择或输入序列号时，保存选择到配置
        if text:
            self.config.set_last_jlink_serial(text)
            self.config.add_preferred_jlink_serial(text)
            self.config.save_config()
        
        # 🔑 多设备时，根据选择状态启用/禁用开始按钮
        if hasattr(self, 'available_jlinks') and len(self.available_jlinks) > 1:
            if hasattr(self.ui, 'pushButton_Start'):
                # 如果选择了空项（text为空或只包含空格），禁用开始按钮
                if not text or text.strip() == "":
                    self.ui.pushButton_Start.setEnabled(False)
                    logger.debug("[MULTI-DEVICE] Start button disabled: no device selected")
                else:
                    self.ui.pushButton_Start.setEnabled(True)
                    logger.debug(f"[MULTI-DEVICE] Start button enabled: device {text} selected")
    
    def reset_target_change_slot(self):
        """重置连接选项变更处理"""
        is_checked = self.ui.checkBox_resettarget.isChecked()
        
        # 保存设置
        self.config.set_reset_target(is_checked)
        self.config.save_config()
    
    def log_split_change_slot(self):
        """日志拆分选项变更处理"""
        is_checked = self.ui.checkBox_log_split.isChecked()
        
        # 保存设置
        self.config.set_log_split(is_checked)
        self.config.save_config()
    
    def rtt_control_block_mode_changed(self):
        """RTT Control Block模式变更处理"""
        if self.ui.radioButton_AutoDetection.isChecked():
            mode = 'auto'
            # 自动检测模式下清空文本框
            self.ui.lineEdit_RTTAddress.clear()
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "JLink automatically detects the RTT control block"))
        elif self.ui.radioButton_Address.isChecked():
            mode = 'address'
            # 读取地址模式的配置
            saved_address = self.config.get_rtt_address()
            if saved_address:
                self.ui.lineEdit_RTTAddress.setText(saved_address)
            else:
                # 如果没有保存的地址，填充示例
                self.ui.lineEdit_RTTAddress.setText(RTTAddress.DEFAULT_ADDRESS_STM32)
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "Example: 0x20000000"))
        elif self.ui.radioButton_SearchRange.isChecked():
            mode = 'search_range'
            # 读取搜索范围模式的配置
            saved_range = self.config.get_rtt_search_range()
            if saved_range:
                self.ui.lineEdit_RTTAddress.setText(saved_range)
            else:
                # 如果没有保存的范围，填充示例
                self.ui.lineEdit_RTTAddress.setText(RTTAddress.DEFAULT_ADDRESS_EXAMPLE)
            self.ui.lineEdit_RTTAddress.setPlaceholderText(
                QCoreApplication.translate("main_window", "Syntax: <RangeStart [hex]> <RangeSize>, ..."))
        else:
            mode = 'auto'
        
        # 保存设置
        self.config.set_rtt_control_block_mode(mode)
        self.config.save_config()
        logger.info(f"RTT Control Block mode changed to: {mode}")
    
    def rtt_control_block_address_changed(self, text):
        """RTT Control Block地址变更处理"""
        # 根据当前模式保存到不同的配置项
        if self.ui.radioButton_Address.isChecked():
            self.config.set_rtt_address(text)
            logger.debug(f"RTT Control Block address changed to: {text}")
        elif self.ui.radioButton_SearchRange.isChecked():
            self.config.set_rtt_search_range(text)
            logger.debug(f"RTT Control Block search range changed to: {text}")
        # Auto Detection模式不保存文本框内容
        
        self.config.save_config()
        
        # 只保存设置，不立即执行重置操作
        # 重置操作将在点击"开始"按钮时执行
    
    def detect_jlink_conflicts(self):
        """检测JLink驱动冲突"""
        try:
            import psutil
            import os
            
            current_pid = os.getpid()
            jlink_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.info['pid'] != current_pid and proc.info['name']:
                        name_lower = proc.info['name'].lower()
                        # 检测常见的JLink相关程序
                        jlink_keywords = ['jlink', 'j-link', 'jflash', 'j-flash', 'commander', 'segger']
                        if any(keyword in name_lower for keyword in jlink_keywords):
                            jlink_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'exe': proc.info.get('exe', 'Unknown')
                            })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return jlink_processes
            
        except Exception as e:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error detecting JLink conflicts')}: {e}")
            return []
    
    def force_release_jlink_driver(self):
        """强制释放JLink驱动"""
        try:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Force releasing JLink driver..."))
            
            # 1. 检测冲突进程
            conflicts = self.detect_jlink_conflicts()
            if conflicts:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Detected %d JLink-related processes:') % len(conflicts)}")
                    for proc in conflicts:
                        self.main_window.append_jlink_log(f"   - {proc['name']} (PID: {proc['pid']})")
                    self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'These programs may be occupying JLink driver'))
            
            # 2. 尝试通过Windows API强制释放驱动
            try:
                import ctypes
                from ctypes import wintypes
                
                # 定义Windows API常量
                GENERIC_READ = RTTAddress.GENERIC_READ
                GENERIC_WRITE = RTTAddress.GENERIC_WRITE
                OPEN_EXISTING = 3
                INVALID_HANDLE_VALUE = -1
                
                # 尝试打开JLink设备句柄来检测占用情况
                kernel32 = ctypes.windll.kernel32
                
                # 常见的JLink设备路径
                jlink_paths = [
                    r"\\.\JLink",
                    r"\\.\JLinkARM", 
                    r"\\.\SEGGER",
                ]
                
                for device_path in jlink_paths:
                    try:
                        handle = kernel32.CreateFileW(
                            device_path,
                            GENERIC_READ | GENERIC_WRITE,
                            0,  # 不共享
                            None,
                            OPEN_EXISTING,
                            0,
                            None
                        )
                        
                        if handle != INVALID_HANDLE_VALUE:
                            kernel32.CloseHandle(handle)
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Successfully accessed device')}: {device_path}")
                        else:
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Cannot access device')}: {device_path} ({QCoreApplication.translate('main_window', 'may be occupied')})")
                                
                    except Exception as e:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error checking device')} {device_path}: {e}")
                
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Windows API driver check failed')}: {e}")
            
            # 3. 尝试重新枚举USB设备
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'Re-enumerating USB devices...'))
                
                # 通过重新扫描串口来触发USB设备重新枚举
                import serial.tools.list_ports
                ports_before = list(serial.tools.list_ports.comports())
                
                # 等待一下让系统稳定
                import time
                time.sleep(0.5)
                
                ports_after = list(serial.tools.list_ports.comports())
                
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'USB device re-enumeration complete (found %d serial ports)') % len(ports_after)}")
                
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'USB device re-enumeration failed')}: {e}")
            
            return True
            
        except Exception as e:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Force release JLink driver failed')}: {e}")
            return False

    def perform_connection_reset(self):
        """执行强化的连接重置操作 - 解决JLink驱动抢占问题"""
        try:
            # 显示重置信息
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Starting enhanced connection reset..."))
            
            # 1. 停止当前连接（如果存在）
            if hasattr(self, 'rtt2uart') and self.rtt2uart is not None:
                try:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Stopping current RTT connection..."))
                    self.rtt2uart.stop()
                    self.rtt2uart = None
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "RTT connection stopped"))
                except Exception as e:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error stopping RTT connection')}: {e}")
            
            # 2. 强制释放JLink驱动（解决驱动抢占问题）
            if hasattr(self, 'jlink') and self.jlink is not None:
                try:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Force releasing JLink driver..."))
                    
                    # 强制断开所有连接
                    try:
                        if self.jlink.connected():
                            self.jlink.close()
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "JLink connection disconnected"))
                    except:
                        pass  # 忽略断开时的错误
                    
                    # 强制清理JLink对象
                    try:
                        del self.jlink
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "JLink object deleted"))
                    except:
                        pass
                    
                    self.jlink = None
                    
                    # 等待驱动释放
                    import time
                    time.sleep(1.0)  # 增加等待时间
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Waiting for driver release..."))
                    
                    # 强制垃圾回收
                    import gc
                    gc.collect()
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Performing garbage collection"))
                    
                    # 执行强制驱动释放
                    self.force_release_jlink_driver()
                    
                    # 重新创建JLink对象
                    try:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Recreating JLink object..."))
                        
                        self.jlink = pylink.JLink()
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "JLink object recreated successfully"))
                        
                        # 尝试打开连接验证
                        try:
                            self.jlink.open()
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "JLink driver reset successful, connection OK"))
                            # 立即关闭，等待后续正常连接流程
                            self.jlink.close()
                        except Exception as e:
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'JLink connection test failed')}: {e}")
                                self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'Hint: Other programs may still be occupying JLink'))
                                
                                # 再次检测冲突并给出具体建议
                                conflicts = self.detect_jlink_conflicts()
                                if conflicts:
                                    self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'Found following JLink-related programs running:'))
                                    for proc in conflicts:
                                        self.main_window.append_jlink_log(f"   - {proc['name']} (PID: {proc['pid']})")
                                    self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'Please close these programs and retry'))
                                else:
                                    self.main_window.append_jlink_log(QCoreApplication.translate('main_window', 'Suggest re-plugging JLink device and retry'))
                        
                    except Exception as e2:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Failed to recreate JLink object')}: {e2}")
                        self.jlink = None
                        
                except Exception as e:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error force releasing JLink driver')}: {e}")
            
            # 3. 重置串口连接（清除串口状态）
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Resetting serial port status..."))
                
                # 重新扫描串口
                self.port_scan()
                
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Serial port status reset"))
                    
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error resetting serial port status')}: {e}")
            
            # 4. 清理缓存和状态
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Cleaning cache and status..."))
                
                # 重置连接状态
                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
                
                # 🔄 更新主窗口状态栏显示
                if self.main_window and hasattr(self.main_window, 'update_status_bar'):
                    self.main_window.update_status_bar()
                
                # 清理主窗口缓存（如果存在）
                if hasattr(self.main_window, 'buffers'):
                    for i in range(len(self.main_window.buffers)):
                        try:
                            self.main_window.buffers[i].clear()
                        except Exception:
                            self.main_window.buffers[i] = []
                
                if hasattr(self.main_window, 'colored_buffers'):
                    for i in range(len(self.main_window.colored_buffers)):
                        try:
                            self.main_window.colored_buffers[i].clear()
                        except Exception:
                            self.main_window.colored_buffers[i] = []
                
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Cache and status cleaned"))
                    
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error cleaning cache')}: {e}")
            
            # 5. 强化的驱动重置完成
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Enhanced connection reset complete!"))
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "If still unable to connect, please:"))
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "   1. Close all JLink-related programs (J-Link Commander, J-Flash, etc.)"))
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "   2. Re-plug JLink device"))
                self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "   3. Then retry connection"))
            
        except Exception as e:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Connection reset failed')}: {e}")
            logger.error(f'Connection reset failed: {e}', exc_info=True)


    def _clear_main_window_ui(self):
        """清空主窗口的所有TAB显示内容 - 已禁用，保留旧数据显示"""
        # BUG2修复：新连接时保留窗口旧数据，只清除写入文件的缓冲区
        logger.debug("[INFO] Keep old window data display, only clear file write buffer")
        pass

    def _clear_all_worker_caches(self):
        """🚨 清空Worker的文件写入缓存，但保留UI显示数据"""
        if not hasattr(self, 'worker') or not self.worker:
            return
            
        try:
            worker = self.worker
            
            # BUG2修复：只清除写入文件的缓冲区，不清除UI显示缓冲区
            # 1. 清空日志文件缓冲区（关键：防止旧数据写入新文件）
            if hasattr(worker, 'log_buffers'):
                cleared_count = len(worker.log_buffers)
                worker.log_buffers.clear()
                logger.debug(f"[CLEAN] Cleared {cleared_count} log file buffers")
            
            
            # 2. BUG1修复：清空字节缓冲区和批量缓冲区，防止残余数据
            for i in range(MAX_TAB_SIZE):
                # 字节缓冲区 - 强制清除，防止残余数据
                if hasattr(worker, 'byte_buffer') and i < len(worker.byte_buffer):
                    if len(worker.byte_buffer[i]) > 0:
                        logger.debug(f"[WARNING] Clear channel {i} byte buffer residual data: {len(worker.byte_buffer[i])} bytes")
                    worker.byte_buffer[i].clear()
                
                # 批量缓冲区
                if hasattr(worker, 'batch_buffers') and i < len(worker.batch_buffers):
                    if len(worker.batch_buffers[i]) > 0:
                        logger.debug(f"[WARNING] Clear channel {i} batch buffer residual data: {len(worker.batch_buffers[i])} items")
                    worker.batch_buffers[i].clear()
                
                # BUG1修复：清空筛选TAB(17+)的buffers和colored_buffers，避免重复检测失效
                # 只清除筛选TAB，保留通道TAB(0-16)的显示数据
                if i >= 17:
                    if hasattr(worker.buffers[i], 'clear'):
                        worker.buffers[i].clear()
                    else:
                        worker.buffers[i] = []
                worker.buffer_lengths[i] = 0
                
                if hasattr(worker, 'colored_buffers') and i < len(worker.colored_buffers):
                    if hasattr(worker.colored_buffers[i], 'clear'):
                        worker.colored_buffers[i].clear()
                    else:
                        worker.colored_buffers[i] = []
                    worker.colored_buffer_lengths[i] = 0
                
                if hasattr(worker, 'display_lengths') and i < len(worker.display_lengths):
                    worker.display_lengths[i] = 0
            
            # 3. 重置性能计数器
            if hasattr(worker, 'update_counter'):
                worker.update_counter = 0
            
            # 4. 重置容量配置
            if hasattr(worker, 'buffer_capacities'):
                for i in range(MAX_TAB_SIZE):
                    worker.buffer_capacities[i] = worker.initial_capacity
                    if hasattr(worker, 'colored_buffer_capacities'):
                        worker.colored_buffer_capacities[i] = worker.initial_capacity
            
            # 注意：保留通道TAB(0-16)的buffers和colored_buffers用于UI显示
            # 清空筛选TAB(17+)以确保重复检测正常工作
            
            log_msg = QCoreApplication.translate("main_window", "File write cache cleared, channel TABs keep old data, filter TABs cleared")
            logger.debug(f"🎉 {log_msg}")
            
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(log_msg)
                
        except Exception as e:
            logger.debug(f"[ERROR] Error clearing Worker cache: {e}")
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error clearing Worker cache')}: {e}")

    def _get_current_device_index(self, connect_para):
        """获取当前连接参数对应的设备索引 - 直接使用ComboBox索引"""
        try:
            # 🔧 关键修复：直接使用ComboBox的当前选择索引，忽略空项
            current_combo_index = self.ui.comboBox_serialno.currentIndex()
            
            # 如果选择的是空项（索引0），跳过
            if current_combo_index <= 0:
                logger.debug("[WARNING] Empty item or invalid index selected, using default value 0")
                return 0
            
            # ComboBox索引需要减1，因为索引0是空项
            actual_device_index = current_combo_index - 1
            
            # 验证设备索引有效性
            if 0 <= actual_device_index < len(self.available_jlinks):
                selected_device = self.available_jlinks[actual_device_index]
                
                logger.debug(f"[SELECT] ComboBox selection: Index {current_combo_index} -> Device index {actual_device_index}")
                logger.debug(f"   Device: {selected_device['serial']} ({selected_device['product_name']})")
                logger.debug(f"   Connect param: {connect_para}")
                
                # 验证序列号是否匹配
                if selected_device['serial'] == connect_para:
                    logger.debug(f"[OK] Serial number matched, using device index: {actual_device_index} (USB_{actual_device_index})")
                    return actual_device_index
                else:
                    logger.debug(f"[WARNING] Serial number mismatch: Expected {connect_para}, Got {selected_device['serial']}")
                    logger.debug(f"   Still using ComboBox selected index: {actual_device_index}")
                    return actual_device_index
            else:
                logger.debug(f"[WARNING] Invalid device index: {actual_device_index}, Device count: {len(self.available_jlinks)}")
                
        except Exception as e:
            logger.debug(f"[ERROR] Failed to get device index: {e}")
        
        # 如果出现问题，返回0作为默认值
        logger.debug("[WARNING] Using default index: 0")
        return 0

    def _detect_jlink_devices(self):
        """检测可用的JLINK设备"""
        try:
            # 确保available_jlinks已初始化
            if not hasattr(self, 'available_jlinks'):
                self.available_jlinks = []
            else:
                self.available_jlinks.clear()
            
            # 检查jlink对象是否可用
            if not hasattr(self, 'jlink') or self.jlink is None:
                logger.warning("JLink对象未初始化，跳过设备检测")
                self.available_jlinks.append({
                    'serial': '',
                    'product_name': '自动检测 (JLink未初始化)',
                    'connection': 'USB'
                })
                return
            
            # 尝试枚举USB连接的JLink设备
            try:
                # 使用JLink的内部方法获取设备列表
                devices = self.jlink.connected_emulators()
                if devices:
                    for device in devices:
                        try:
                            # 安全地获取设备信息
                            serial_num = getattr(device, 'SerialNumber', None)
                            if serial_num:
                                # 获取产品名称并确保是字符串类型
                                product_name = getattr(device, 'acProduct', b'J-Link')
                                if isinstance(product_name, bytes):
                                    product_name = product_name.decode('utf-8', errors='ignore')
                                
                                device_info = {
                                    'serial': str(serial_num),
                                    'product_name': product_name,
                                    'connection': 'USB'
                                }
                                self.available_jlinks.append(device_info)
                                logger.info(f"Found JLink device: {device_info}")
                        except Exception as e:
                            logger.warning(f"Error processing device: {e}")
                            continue
                else:
                    logger.info("No JLink devices found")
                        
            except Exception as e:
                logger.warning(f"Could not enumerate JLink devices: {e}")
                # 如果枚举失败，添加一个默认的"自动检测"选项
                self.available_jlinks.append({
                    'serial': '',
                    'product_name': '自动检测',
                    'connection': 'USB'
                })
            
            # 如果没有找到设备，添加默认选项
            if not self.available_jlinks:
                self.available_jlinks.append({
                    'serial': '',
                    'product_name': '自动检测 (无设备)',
                    'connection': 'USB'
                })
                
        except Exception as e:
            logger.error(f"Error detecting JLink devices: {e}")
            # 确保always有一个默认选项
            self.available_jlinks = [{
                'serial': '',
                'product_name': '自动检测',
                'connection': 'USB'
            }]
    
    def _create_jlink_selection_dialog(self):
        """创建JLINK设备选择对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("main_window", "Select J-Link Device"))
        dialog.setWindowIcon(QIcon(":/xexunrtt.ico"))
        dialog.setModal(True)
        dialog.resize(WindowSize.FIND_DIALOG_WIDTH, WindowSize.FIND_DIALOG_HEIGHT)
        
        # 设置窗口标志以避免在任务栏Aero Peek中显示
        current_flags = dialog.windowFlags()
        new_flags = current_flags | Qt.Tool
        # 确保保留关闭按钮和系统菜单
        new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
        dialog.setWindowFlags(new_flags)
        
        layout = QVBoxLayout(dialog)
        
        # 说明标签
        info_label = QLabel("检测到多个 J-Link 设备，请选择要使用的设备：")
        layout.addWidget(info_label)
        
        # 设备列表
        device_list = QListWidget()
        device_list.setAlternatingRowColors(True)
        
        # 获取偏好的序列号列表
        preferred_serials = self.config.get_preferred_jlink_serials()
        last_serial = self.config.get_last_jlink_serial()
        
        # 添加设备到列表，优先显示偏好的设备
        items_added = set()
        selected_index = 0
        
        # 首先添加偏好的设备
        for preferred_serial in preferred_serials:
            for i, device in enumerate(self.available_jlinks):
                if device['serial'] == preferred_serial and device['serial'] not in items_added:
                    display_text = f"⭐ {device['product_name']}"
                    if device['serial']:
                        display_text += f" (序列号: {device['serial']})"
                    else:
                        display_text += " (自动检测)"
                    
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, device)
                    device_list.addItem(item)
                    items_added.add(device['serial'])
                    
                    # 如果是上次使用的设备，设为选中
                    if device['serial'] == last_serial:
                        selected_index = device_list.count() - 1
        
        # 然后添加其他设备
        for device in self.available_jlinks:
            if device['serial'] not in items_added:
                display_text = device['product_name']
                if device['serial']:
                    display_text += f" (序列号: {device['serial']})"
                else:
                    display_text += " (自动检测)"
                
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, device)
                device_list.addItem(item)
                items_added.add(device['serial'])
        
        # 设置默认选中项
        if device_list.count() > 0:
            device_list.setCurrentRow(selected_index)
        
        layout.addWidget(device_list)
        
        # 选项复选框
        options_layout = QHBoxLayout()
        remember_checkbox = QCheckBox("记住此设备作为偏好选择")
        remember_checkbox.setChecked(True)
        auto_select_checkbox = QCheckBox("下次自动选择上次使用的设备")
        auto_select_checkbox.setChecked(self.config.get_auto_select_jlink())
        
        options_layout.addWidget(remember_checkbox)
        options_layout.addWidget(auto_select_checkbox)
        layout.addLayout(options_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新设备列表")
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        
        refresh_btn.clicked.connect(lambda: self._refresh_device_list(device_list))
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 设置对话框属性
        dialog.device_list = device_list
        dialog.remember_checkbox = remember_checkbox
        dialog.auto_select_checkbox = auto_select_checkbox
        
        return dialog
    
    def _refresh_device_list(self, device_list_widget):
        """刷新设备列表"""
        self._detect_jlink_devices()
        device_list_widget.clear()
        
        for device in self.available_jlinks:
            display_text = device['product_name']
            if device['serial']:
                display_text += f" (序列号: {device['serial']})"
            else:
                display_text += " (自动检测)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, device)
            device_list_widget.addItem(item)
        
        if device_list_widget.count() > 0:
            device_list_widget.setCurrentRow(0)
    
    def _select_jlink_device(self):
        """选择JLINK设备"""
        if len(self.available_jlinks) <= 1:
            # 只有一个或没有设备，直接使用
            if self.available_jlinks:
                self.selected_jlink_serial = self.available_jlinks[0]['serial']
            return True
        
        # 🔧 不使用配置文件自动选择，每次都让用户手动选择
        # 设备选择是一次性的，不需要持久化到配置文件
        
        # 显示选择对话框
        dialog = self._create_jlink_selection_dialog()
        if dialog.exec() == QDialog.Accepted:
            current_item = dialog.device_list.currentItem()
            if current_item:
                device = current_item.data(Qt.UserRole)
                self.selected_jlink_serial = device['serial']
                
                # 保存选择
                if dialog.remember_checkbox.isChecked():
                    self.config.add_preferred_jlink_serial(device['serial'])
                
                self.config.set_last_jlink_serial(device['serial'])
                self.config.set_auto_select_jlink(dialog.auto_select_checkbox.isChecked())
                self.config.save_config()
                
                logger.info(f"Selected JLink device: {device}")
                return True
        
        return False
    
    def _initialize_device_combo(self):
        """初始化设备ComboBox"""
        try:
            # 检查ComboBox是否存在
            if not hasattr(self.ui, 'comboBox_serialno'):
                logger.warning("ComboBox未找到，跳过初始化")
                return
            
            # 清空现有列表
            try:
                self.ui.comboBox_serialno.clear()
            except Exception as e:
                logger.warning(f"清空ComboBox失败: {e}")
                return
            
            # 添加空选项（自动检测）
            self.ui.comboBox_serialno.addItem("")
            
            # 检测并添加设备
            self._refresh_jlink_devices()
            
            # 设置默认选择
            try:
                saved_serial = self.config.get_last_jlink_serial()
                if saved_serial:
                    index = self.ui.comboBox_serialno.findText(saved_serial)
                    if index >= 0:
                        self.ui.comboBox_serialno.setCurrentIndex(index)
            except Exception as e:
                logger.warning(f"设置默认选择失败: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing device combo: {e}")
    
    def _refresh_jlink_devices(self):
        """刷新JLINK设备列表"""
        #logger.info("🔄" * 40)
        # logger.info("[REFRESH JLINK] 用户点击刷新按钮")
        try:
            # 检查ComboBox是否存在
            if not hasattr(self.ui, 'comboBox_serialno'):
                logger.warning("ComboBox未找到，跳过设备列表刷新")
                # logger.info("🔄" * 40)
                return
            
            # 重新检测设备
            self._detect_jlink_devices()
            
            # 保存当前选择
            current_text = ""
            try:
                current_text = self.ui.comboBox_serialno.currentText()
            except Exception as e:
                logger.warning(f"获取当前选择失败: {e}")
            
            # 清空ComboBox（保留第一个空项）
            try:
                while self.ui.comboBox_serialno.count() > 1:
                    self.ui.comboBox_serialno.removeItem(1)
            except Exception as e:
                logger.warning(f"清空ComboBox失败: {e}")
                # 重新清空整个ComboBox
                self.ui.comboBox_serialno.clear()
                self.ui.comboBox_serialno.addItem("")  # 添加空项
            
            # 🔧 简化设备列表填充：不使用偏好设备，直接按检测顺序添加
            try:
                # 直接按available_jlinks的顺序添加所有设备
                for device_index, device in enumerate(self.available_jlinks):
                    serial = device.get('serial', '')
                    if serial:
                        # 不使用星标，直接显示索引和序列号
                        display_text = f"#{device_index} {serial}"
                        self.ui.comboBox_serialno.addItem(display_text, serial)
                        logger.debug(f"[ADD] Add device to ComboBox: Index {device_index} -> {display_text}")
                    else:
                        display_text = f"#{device_index} {QCoreApplication.translate('main_window', 'Auto Detect')}"
                        self.ui.comboBox_serialno.addItem(display_text, "")
                        logger.debug(f"[ADD] Add device to ComboBox: Index {device_index} -> {display_text}")
                
                # 恢复之前的选择
                if current_text:
                    index = self.ui.comboBox_serialno.findText(current_text)
                    if index >= 0:
                        self.ui.comboBox_serialno.setCurrentIndex(index)
                    else:
                        # 如果找不到完全匹配，尝试按数据匹配
                        for i in range(self.ui.comboBox_serialno.count()):
                            try:
                                item_data = self.ui.comboBox_serialno.itemData(i)
                                if item_data == current_text:
                                    self.ui.comboBox_serialno.setCurrentIndex(i)
                                    break
                            except Exception:
                                continue
                
                logger.info(f"[REFRESH JLINK] Refreshed device list: {len(self.available_jlinks)} devices found")
                #logger.info("🔄" * 40)
                
                # 🔑 多设备时自动启用序列号选择并打开下拉框
                if len(self.available_jlinks) > 1:
                    # 自动勾选序列号选择框并显示相关控件
                    if hasattr(self.ui, 'checkBox_serialno') and not self.ui.checkBox_serialno.isChecked():
                        self.ui.checkBox_serialno.setChecked(True)
                        logger.info(f"[AUTO] Multiple devices detected ({len(self.available_jlinks)}), auto-enabled serial number selection")
                        
                        # 手动显示 ComboBox 和刷新按钮（避免递归调用 serial_no_change_slot）
                        if hasattr(self.ui, 'comboBox_serialno'):
                            self.ui.comboBox_serialno.setVisible(True)
                        if hasattr(self.ui, 'pushButton_refresh_jlink'):
                            self.ui.pushButton_refresh_jlink.setVisible(True)
                    
                    # 自动打开下拉框让用户选择
                    if hasattr(self.ui, 'comboBox_serialno'):
                        # 延迟一点打开，确保UI已经更新
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(100, lambda: self.ui.comboBox_serialno.showPopup())
                        logger.info(f"[AUTO] Opening device selection dropdown for user")
                    
                    # 🔑 检查当前选择，如果是空项则禁用开始按钮
                    if hasattr(self.ui, 'comboBox_serialno') and hasattr(self.ui, 'pushButton_Start'):
                        current_text = self.ui.comboBox_serialno.currentText()
                        if not current_text or current_text.strip() == "":
                            self.ui.pushButton_Start.setEnabled(False)
                            logger.info(f"[AUTO] Start button disabled: no device selected (multiple devices available)")
                        else:
                            self.ui.pushButton_Start.setEnabled(True)
                            logger.debug(f"[AUTO] Start button enabled: device selected")
                
            except Exception as e:
                logger.error(f"Error adding devices to ComboBox: {e}")
                #logger.info("🔄" * 40)
            
        except Exception as e:
            logger.error(f"Error refreshing device list: {e}")
            #logger.info("🔄" * 40)

    def usb_selete_slot(self):
        self.connect_type = 'USB'

        self.ui.checkBox__auto.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox_serialno.setVisible(True)
        self.serial_no_change_slot()
        # 通过usb方式接入，以下功能需要选择，恢复使用
        self.ui.comboBox_Device.setEnabled(True)
        self.ui.pushButton_Selete_Device.setEnabled(True)
        self.ui.comboBox_Interface.setEnabled(True)
        self.ui.comboBox_Speed.setEnabled(True)
        self.ui.checkBox_resettarget.setEnabled(True)

    def existing_session_selete_slot(self):
        self.connect_type = 'EXISTING'

        self.ui.checkBox_serialno.setVisible(False)
        if hasattr(self.ui, 'comboBox_serialno'):
            self.ui.comboBox_serialno.setVisible(False)
        if hasattr(self.ui, 'pushButton_refresh_jlink'):
            self.ui.pushButton_refresh_jlink.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox__auto.setVisible(True)
        # 通过existing_session方式接入时，以下功能无效，禁止使用
        self.ui.comboBox_Device.setEnabled(False)
        self.ui.pushButton_Selete_Device.setEnabled(False)
        self.ui.comboBox_Interface.setEnabled(False)
        self.ui.comboBox_Speed.setEnabled(False)
        self.ui.checkBox_resettarget.setEnabled(False)
        self.ui.checkBox_resettarget.setChecked(False)

    def _auto_clean_tab_data(self, tab_index, text_edit, ui_time):
        """自动清理TAB数据：在UI耗时过高时清理1/3的数据"""
        try:
            # 🚀 性能优化：清理UI显示的数据
            if hasattr(text_edit, 'document') and text_edit.document():
                document = text_edit.document()
                current_blocks = document.blockCount()
                
                if current_blocks > BufferConfig.MAX_BLOCKS:  # 只在行数较多时才清理
                    # 🚀 使用可配置的清理比例
                    clean_ratio_denominator = 10  # 默认值（1/10）
                    try:
                        if hasattr(self, 'main_window') and self.main_window.connection_dialog and hasattr(self.main_window.connection_dialog, 'config'):
                            clean_ratio_denominator = self.main_window.connection_dialog.config.get_clean_ratio_denominator()
                    except Exception:
                        pass
                    
                    # 计算要删除的行数（1/N）
                    lines_to_remove = current_blocks // clean_ratio_denominator
                    
                    # 使用高效的批量删除
                    from PySide6.QtGui import QTextCursor
                    cursor = text_edit.textCursor()
                    cursor.movePosition(QTextCursor.Start)
                    
                    # 选择前1/3的内容
                    for _ in range(lines_to_remove):
                        cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
                    
                    # 批量删除选中的文本
                    cursor.removeSelectedText()
                    
                    logger.info(f"[CLEAN] TAB{tab_index} auto cleanup completed: removed {lines_to_remove} lines (1/{clean_ratio_denominator}), took {ui_time:.1f}ms -> remaining {document.blockCount()} lines")
            
            # 🚀 清理内部缓冲区数据：同时清理worker中的数据
            if hasattr(self, 'worker') and self.worker:
                # 获取清理比例配置
                clean_ratio_denominator = 10  # 默认值（1/10）
                try:
                    if hasattr(self, 'main_window') and self.main_window.connection_dialog and hasattr(self.main_window.connection_dialog, 'config'):
                        clean_ratio_denominator = self.main_window.connection_dialog.config.get_clean_ratio_denominator()
                except Exception:
                    pass
                
                # 计算保留比例 (1 - 1/N) = (N-1)/N
                keep_ratio = (clean_ratio_denominator - 1) / clean_ratio_denominator
                
                # 清理彩色缓冲区数据
                if hasattr(self.worker, 'colored_buffers') and tab_index < len(self.worker.colored_buffers):
                    colored_buffer = self.worker.colored_buffers[tab_index]
                    if len(colored_buffer) > 10:  # 确保有足够的数据
                        # 保留后(N-1)/N的数据
                        keep_count = int(len(colored_buffer) * keep_ratio)
                        self.worker.colored_buffers[tab_index] = colored_buffer[-keep_count:] if keep_count > 0 else []
                        
                        # 更新彩色缓冲区长度计数
                        if hasattr(self.worker, 'colored_buffer_lengths'):
                            if tab_index < len(self.worker.colored_buffer_lengths):
                                self.worker.colored_buffer_lengths[tab_index] = sum(len(chunk) for chunk in self.worker.colored_buffers[tab_index])
                
                # 清理普通缓冲区数据
                if hasattr(self.worker, 'buffers') and tab_index < len(self.worker.buffers):
                    buffer = self.worker.buffers[tab_index]
                    if len(buffer) > 10:  # 确保有足够的数据
                        # 保留后(N-1)/N的数据
                        keep_count = int(len(buffer) * keep_ratio)
                        self.worker.buffers[tab_index] = buffer[-keep_count:] if keep_count > 0 else []
                        
                        # 更新缓冲区长度计数
                        if hasattr(self.worker, 'buffer_lengths'):
                            if tab_index < len(self.worker.buffer_lengths):
                                self.worker.buffer_lengths[tab_index] = sum(len(chunk) for chunk in self.worker.buffers[tab_index])
                        
                        # 重置显示长度计数
                        if hasattr(self.worker, 'display_lengths'):
                            if tab_index < len(self.worker.display_lengths):
                                self.worker.display_lengths[tab_index] = 0
        
        except Exception as e:
            # 清理失败不影响主要功能
            logger.error(f"[CLEAN] TAB{tab_index} 自动清理失败: {e}")

    @Slot(int)
    def switchPage(self, index):
        """MDI 架构：TAB 切换和刷新由 DeviceMdiWindow 处理
        
        这个方法在旧架构中用于切换 TAB 时刷新显示。
        现在保留方法签名以兼容旧代码调用，但不执行任何操作。
        """
        pass

    def clear_current_tab(self):
        """清空当前标签页的内容 - 仅限RTT通道（0-15），不包括ALL窗口（MDI架构）
        
        MDI 架构：清空功能由主窗口的 on_clear_clicked 处理。
        这个方法保留以兼容旧代码调用。
        """
        if self.main_window:
            self.main_window.on_clear_clicked()


    def _insert_ansi_text_fast(self, text_edit, text, tab_index=None):
        """🎨 ANSI彩色文本插入 - 支持全部TAB彩色显示"""
        try:
            # 检查是否包含ANSI控制符
            if '\x1B[' not in text:
                # 纯文本，直接插入
                text_edit.insertPlainText(text)
                return
            
            # 检查是否包含清屏控制符
            if '\x1B[2J' in text:
                # 只有RTT通道（索引1-16）才允许清屏，ALL窗口（索引0）不允许
                if tab_index is not None and tab_index >= 1 and tab_index <= 16:
                    text_edit.clear()
                # 移除清屏控制符，继续处理其他ANSI代码
                text = text.replace('\x1B[2J', '')
            
            # 解析ANSI文本段落
            from rtt2uart import ansi_processor
            segments = ansi_processor.parse_ansi_text(text)
            cursor = text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            
            for segment in segments:
                text_part = segment['text']
                color = segment['color']
                background = segment['background']
                
                if not text_part:
                    continue
                
                # 创建文本格式
                format = QTextCharFormat()
                
                if color:
                    # 设置前景色
                    format.setForeground(QColor(color))
                
                if background:
                    # 设置背景色
                    format.setBackground(QColor(background))
                
                # 🔑 关键修复：使用用户选择的字体，并设置正确的等宽渲染属性
                # 获取当前文本框的字体（已经在switchPage中设置好）
                current_font = text_edit.font()
                font = QFont(current_font.family(), current_font.pointSize())
                font.setFixedPitch(True)
                font.setStyleHint(QFont.StyleHint.Monospace)  # 🔑 强制等宽渲染
                font.setKerning(False)  # 🔑 禁用字距调整
                format.setFont(font)
                
                # 插入格式化文本
                cursor.insertText(text_part, format)
            
            # 更新文本编辑器的光标位置
            text_edit.setTextCursor(cursor)
            
        except Exception as e:
            # 如果ANSI处理失败，回退到纯文本
            try:
                text_edit.insertPlainText(text)
            except Exception:
                from rtt2uart import ansi_processor
                clean_text = ansi_processor.remove_ansi_codes(text)
                text_edit.insertPlainText(clean_text)

    # _cleanup_ui_text方法已移除，使用滑动文本块机制替代


    @Slot()
    def handleBufferUpdate(self):
        # 更新数据时间戳（用于自动重连监控）
        if self.main_window and hasattr(self.main_window, '_update_data_timestamp'):
            self.main_window._update_data_timestamp()
        
        # 📈 记录刷新事件
        if hasattr(self.worker, 'refresh_count'):
            self.worker.refresh_count += 1
        
        # UI 刷新节流：限制最小刷新间隔，避免高频更新导致卡顿
        try:
            now_ms = int(time.time() * 1000)
            if hasattr(self.worker, '_last_ui_update_ms') and hasattr(self.worker, 'min_ui_update_interval_ms'):
                if now_ms - self.worker._last_ui_update_ms < self.worker.min_ui_update_interval_ms:
                    return
                self.worker._last_ui_update_ms = now_ms
        except Exception:
            pass
            
        # 智能更新：只刷新有数据变化的页面
        if not self.main_window:
            return
            
        # 使用滑动文本块机制，不需要定期清理UI文本
        
        # MDI 架构中不再使用 tem_switch，由 DeviceMdiWindow 处理
        return
            
        # current_index = self.main_window.ui.tem_switch.currentIndex()
        
        # 增加时间戳跟踪，用于限制UI更新频率
        current_time_ms = int(time.time() * 1000)
        
        # 优先更新当前显示的页面 - 添加更新间隔限制
        if self.main_window.page_dirty_flags[current_index]:
            # 检查是否需要立即更新当前页面
            if current_time_ms - self.main_window._last_ui_update_ms >= self.main_window.min_ui_update_interval_ms:
                self.switchPage(current_index)
                self.main_window.page_dirty_flags[current_index] = False
                self.main_window._last_ui_update_ms = current_time_ms
        
        # 🎨 优化：智能UI更新策略，减少不必要的刷新
        # 1. 只有在处理完当前页面且有足够时间间隔时才更新其他页面
        # 2. 实现基于重要性的更新优先级
        # 3. 批量合并小更新
        if current_time_ms - self.main_window._last_ui_update_ms >= self.main_window.min_ui_update_interval_ms:
            # 收集所有需要更新的页面
            dirty_pages = []
            for i in range(MAX_TAB_SIZE):
                if i != current_index and self.main_window.page_dirty_flags[i]:
                    # 这里可以添加更多优先级逻辑，如基于数据量、时间等
                    dirty_pages.append(i)
            
            # 智能批量更新策略
            if dirty_pages:
                # 根据系统负载动态调整更新数量
                if hasattr(self.worker, 'get_buffer_memory_usage'):
                    memory_info = self.worker.get_buffer_memory_usage()
                    utilization = memory_info.get('capacity_utilization', 0)
                    
                    # 更保守的更新策略，减少CPU占用
                    if utilization > 85:  # 非常高的利用率
                        max_updates = 1  # 只更新1个页面
                    elif utilization > 70:  # 高利用率
                        max_updates = 2  # 更新2个页面
                    elif utilization > 50:  # 中等利用率
                        max_updates = 3  # 更新3个页面
                    else:  # 低利用率
                        max_updates = 5  # 更新5个页面
                else:
                    max_updates = 3  # 默认保守策略
                
                # 限制同时更新的页面数量
                pages_to_update = min(len(dirty_pages), max_updates)
                
                # 批量更新优先级最高的页面
                for i in range(pages_to_update):
                    page_index = dirty_pages[i]
                    self.switchPage(page_index)
                    self.main_window.page_dirty_flags[page_index] = False
                
                # 更新最后UI更新时间
                self.main_window._last_ui_update_ms = current_time_ms
        
        # 清理策略：当页面过多时，标记低优先级页面为干净以避免内存积压
        # 但保留脏标记直到有足够资源更新它们
   

class Worker(QObject):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.byte_buffer = [bytearray() for _ in range(16)]  # 创建MAX_TAB_SIZE个缓冲区
        
        # 🚀 高性能分块缓冲：避免字符串 O(n^2) 级累加
        self.buffers = [[] for _ in range(MAX_TAB_SIZE)]  # 以列表分块存储
        self.colored_buffers = [[] for _ in range(MAX_TAB_SIZE)]  # 彩色数据分块
        # 为每个缓冲维护长度计数，避免每次追加都遍历求和
        self.buffer_lengths = [0] * MAX_TAB_SIZE
        self.colored_buffer_lengths = [0] * MAX_TAB_SIZE
        # 纯文本显示的已显示长度（按字节计数），用于增量提取，避免每次 join 全量
        self.display_lengths = [0] * MAX_TAB_SIZE
        
        # 🎯 成倍扩容配置 (100K->200K->400K->800K->1.6M->3.2M->6.4M)
        self.buffer_capacities = [0] * MAX_TAB_SIZE  # 当前容量
        self.colored_buffer_capacities = [0] * MAX_TAB_SIZE  # 彩色缓冲区容量
        self.initial_capacity = BufferConfig.INITIAL_CAPACITY
        self.max_capacity = BufferConfig.MAX_CAPACITY
        self.growth_factor = 2               # 扩容系数
        
        # 初始化容量记录
        for i in range(MAX_TAB_SIZE):
            self.buffer_capacities[i] = self.initial_capacity
            self.colored_buffer_capacities[i] = self.initial_capacity
        
        # 使用滑动文本块机制，QPlainTextEdit自动管理历史缓冲
        
        # 性能优化：文件I/O缓冲
        self.log_buffers = {}  # 日志文件缓冲
        # 延迟创建定时器，确保在正确的线程中
        self.buffer_flush_timer = None
        
        
        # 性能计数器
        self.update_counter = 0
        
        # 🚀 Turbo模式：批量处理缓冲
        self.batch_buffers = [bytearray() for _ in range(16)]  # 批量缓冲区
        self.batch_timers = [None for _ in range(16)]  # 每个通道的批量计时器
        self.turbo_mode = False  # 默认启用Turbo模式
        self.batch_delay = 20   # 批量延迟20ms（降低延迟，提升响应性）
        
        # 📈 性能监控变量
        self.last_refresh_time = time.time()
        self.refresh_count = 0
        self.last_log_time = time.time()
        self.log_interval = 5.0  # 每5秒记录一次性能日志
        # UI 刷新节流（ms）
        self.min_ui_update_interval_ms = 20
        self._last_ui_update_ms = 0
        # 🎨 大量积压时的"追尾显示"参数（调整阈值以减少彩色显示失败）
        self.backlog_fast_forward_threshold = 512 * 1024  # 积压超过512KB时快进（提高阈值）
        self.fast_forward_tail = 128 * 1024                # 只显示末尾128KB（增加显示内容）
        # 是否启用彩色缓冲（保持原行为=启用）
        self.enable_color_buffers = True
    
    def set_turbo_mode(self, enabled, batch_delay=20):
        """设置Turbo模式"""
        self.turbo_mode = enabled
        self.batch_delay = batch_delay
        
        # 如果禁用turbo模式，立即处理所有待处理的批量数据
        if not enabled:
            for i in range(16):
                if self.batch_timers[i] is not None:
                    self.batch_timers[i].stop()
                    self._process_batch_buffer(i)

    def start_flush_timer(self):
        """启动日志刷新定时器（增强版本）"""
        if self.buffer_flush_timer is None:
            self.buffer_flush_timer = QTimer()
            self.buffer_flush_timer.timeout.connect(self.flush_log_buffers)
            # 🚀 更频繁的刷新，确保TAB日志实时输出
            self.buffer_flush_timer.start(TimerInterval.BUFFER_FLUSH)
            
        # 🔧 立即执行一次刷新，确保启动时的数据能及时写入
        QTimer.singleShot(TimerInterval.DELAYED_INIT, self.flush_log_buffers)

    def flush_log_buffers(self):
        """定期刷新日志缓冲到文件（增强版本）"""
        try:
            # 创建字典的副本以避免运行时修改错误
            log_buffers_copy = dict(self.log_buffers)
            
            # 🚀 提高文件处理数量，确保TAB日志实时输出
            max_files_per_flush = 50  # 增加到50个文件，确保不会延迟
            processed_files = 0
            
            for filepath, content in log_buffers_copy.items():
                if content and processed_files < max_files_per_flush:
                    try:
                        # 🛡️ 检查文件路径有效性
                        import os
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        
                        # 🚀 使用更安全的文件写入方式
                        with open(filepath, 'a', encoding='utf-8', buffering=8192) as f:
                            f.write(content)
                            f.flush()  # 强制刷新到磁盘
                            
                        # 安全地清空缓冲区
                        if filepath in self.log_buffers:
                            self.log_buffers[filepath] = ""
                            
                        processed_files += 1
                        
                    except (OSError, IOError, PermissionError) as e:
                        # 🚨 文件写入失败，记录错误但不中断其他文件的处理
                        logger.error(f"Failed to write log file {filepath}: {e}")
                        # 保留缓冲区数据，下次再试
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error writing log file {filepath}: {e}")
                        continue
                        
            # 🧹 定期清理过大的缓冲区（防止内存泄漏）
            self._cleanup_oversized_buffers()
            
        except RuntimeError:
            # 如果字典在迭代过程中被修改，跳过这次刷新
            pass
        except Exception as e:
            logger.error(f"Error in flush_log_buffers: {e}")
    
    def _cleanup_oversized_buffers(self):
        """清理过大的日志缓冲区"""
        try:
            max_buffer_size = 1024 * 1024  # 1MB限制
            for filepath in list(self.log_buffers.keys()):
                if len(self.log_buffers[filepath]) > max_buffer_size:
                    # 强制写入过大的缓冲区
                    try:
                        with open(filepath, 'a', encoding='utf-8') as f:
                            f.write(self.log_buffers[filepath])
                            f.flush()
                        self.log_buffers[filepath] = ""
                        logger.warning(f"Force flushed oversized buffer for {filepath}")
                    except Exception as e:
                        # 如果写入失败，截断缓冲区避免内存耗尽
                        self.log_buffers[filepath] = self.log_buffers[filepath][-max_buffer_size//2:]
                        logger.error(f"Truncated oversized buffer for {filepath}: {e}")
        except Exception as e:
            logger.error(f"Error in _cleanup_oversized_buffers: {e}")

    def write_to_log_buffer(self, filepath, content):
        """写入日志缓冲而不是直接写文件（增强版本）
        
        Args:
            filepath: 日志文件路径
            content: 要写入的内容
            
        该方法实现了4KB批量写入的缓存机制，减少磁盘I/O操作频率。
        """
        try:
            
            # 常规缓冲写入逻辑
            if filepath not in self.log_buffers:
                self.log_buffers[filepath] = ""
            
            # 🚀 检查缓冲区大小，避免单个文件缓冲区过大
            max_single_buffer = 512 * 1024  # 512KB限制
            if len(self.log_buffers[filepath]) > max_single_buffer:
                # 立即写入到文件
                try:
                    import os
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write(self.log_buffers[filepath])
                        f.flush()
                    self.log_buffers[filepath] = ""
                except Exception as e:
                    # 写入失败，截断缓冲区
                    self.log_buffers[filepath] = self.log_buffers[filepath][-max_single_buffer//2:]
                    logger.error(f"Buffer overflow, truncated for {filepath}: {e}")
            
            self.log_buffers[filepath] += content
            
            # 🚀 批量写入机制：当缓冲区达到4KB时才写入，减少I/O操作频率
            batch_flush_threshold = 4096  # 4KB阈值，按用户要求进行批量写入
            if len(self.log_buffers[filepath]) >= batch_flush_threshold:
                try:
                    import os
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write(self.log_buffers[filepath])
                        f.flush()
                    self.log_buffers[filepath] = ""
                except Exception as e:
                    logger.error(f"Batch flush failed for {filepath}: {e}")
            
            # 🔧 检查总缓冲区数量，避免文件过多
            if len(self.log_buffers) > BufferConfig.MAX_LOG_BUFFERS:  # 限制同时缓冲的文件数量
                self._emergency_flush_oldest_buffers()
                
        except Exception as e:
            logger.error(f"Error in write_to_log_buffer for {filepath}: {e}")
    
    def flush_all_log_buffers(self):
        """刷新所有日志缓冲区，将所有缓存数据写入文件
        
        用于连接断开时确保所有数据都被保存，防止数据丢失
        """
        try:
            flushed_count = 0
            total_bytes = 0
            
            # 遍历所有日志缓冲区
            for filepath, buffer_content in list(self.log_buffers.items()):
                if buffer_content:
                    try:
                        import os
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        with open(filepath, 'a', encoding='utf-8') as f:
                            f.write(buffer_content)
                            f.flush()
                        
                        # 统计写入的数据量
                        total_bytes += len(buffer_content)
                        flushed_count += 1
                        
                        # 清空缓冲区
                        self.log_buffers[filepath] = ""
                        
                    except Exception as e:
                        logger.error(f"Failed to flush buffer for {filepath} during connection disconnect: {e}")
            
            if flushed_count > 0:
                logger.info(f"Successfully flushed {flushed_count} log buffers ({total_bytes} bytes) during connection disconnect")
                
        except Exception as e:
            logger.error(f"Error in flush_all_log_buffers: {e}")
    
    def _emergency_flush_oldest_buffers(self):
        """紧急刷新最老的缓冲区"""
        try:
            # 按文件名排序，刷新前50个文件的缓冲区
            sorted_files = sorted(self.log_buffers.keys())
            for filepath in sorted_files[:50]:
                if self.log_buffers[filepath]:
                    try:
                        import os
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        with open(filepath, 'a', encoding='utf-8') as f:
                            f.write(self.log_buffers[filepath])
                            f.flush()
                        self.log_buffers[filepath] = ""
                    except Exception as e:
                        logger.error(f"Emergency flush failed for {filepath}: {e}")
                        # 删除无法写入的缓冲区
                        del self.log_buffers[filepath]
        except Exception as e:
            logger.error(f"Error in _emergency_flush_oldest_buffers: {e}")

    def force_flush_all_buffers(self):
        """🚨 强制刷新所有日志缓冲区到文件（程序关闭时调用）"""
        logger.info("Starting to force refresh all log buffers...")
        try:
            if not self.log_buffers:
                logger.info("No log buffers to flush")
                return
                
            flushed_count = 0
            error_count = 0
            
            # 创建缓冲区副本，避免迭代过程中修改字典
            log_buffers_copy = dict(self.log_buffers)
            
            for filepath, content in log_buffers_copy.items():
                if content:  # 只处理有内容的缓冲区
                    try:
                        # 确保目录存在
                        import os
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        
                        # 强制写入文件
                        with open(filepath, 'a', encoding='utf-8', buffering=8192) as f:
                            f.write(content)
                            f.flush()  # 强制刷新到磁盘
                        
                        # 清空已刷新的缓冲区
                        if filepath in self.log_buffers:
                            self.log_buffers[filepath] = ""
                            
                        flushed_count += 1
                        logger.debug(f"✅ 强制刷新完成: {filepath}")
                        
                    except (OSError, IOError, PermissionError) as e:
                        error_count += 1
                        logger.error(f"❌ 强制刷新失败 {filepath}: {e}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"❌ 强制刷新异常 {filepath}: {e}")
            
            logger.info(f"🚨 Force refresh completed: {flushed_count} files succeeded, {error_count} files failed")
            
        except Exception as e:
            logger.error(f"强制刷新所有缓冲区时出错: {e}")
            
    def get_pending_buffer_info(self):
        """获取待刷新缓冲区信息（用于调试）"""
        try:
            if not self.log_buffers:
                return "没有待刷新的缓冲区"
                
            info_lines = []
            total_size = 0
            
            for filepath, content in self.log_buffers.items():
                if content:
                    size = len(content)
                    total_size += size
                    info_lines.append(f"  - {filepath}: {size} 字节")
            
            if info_lines:
                info_lines.insert(0, f"待刷新缓冲区 ({len(info_lines)} 个文件, 总计 {total_size} 字节):")
                return "\n".join(info_lines)
            else:
                return "所有缓冲区都已刷新"
                
        except Exception as e:
            return f"获取缓冲区信息失败: {e}"

    def write_data_to_buffer_log(self, buffer_index, data, log_suffix=""):
        """📋 统一日志写入方法：将数据直接传递给write_to_log_buffer进行处理
        
        Args:
            buffer_index: buffer索引 (0=ALL页面, 1-16=通道页面, 17+=筛选页面)
            data: 要写入的数据（应该与对应buffer内容一致）
            log_suffix: 日志文件后缀 (如果为空，使用buffer_index)
        """
        try:
            if (hasattr(self.parent, 'rtt2uart') and 
                self.parent.rtt2uart and data):
                
                # 构造日志文件路径
                if log_suffix:
                    log_filepath = f"{self.parent.rtt2uart.rtt_log_filename}_{log_suffix}.log"
                else:
                    log_filepath = f"{self.parent.rtt2uart.rtt_log_filename}_{buffer_index}.log"
                
                # 直接调用write_to_log_buffer方法，由该方法内部处理缓存和批量写入逻辑
                self.write_to_log_buffer(log_filepath, data)
                    
        except Exception as e:
            logger.error(f"Failed to write data to buffer {buffer_index} log: {e}")

    # 类级别预编译的正则表达式，避免每次调用都重新编译
    _ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    _color_replacements = [
        # 优化的ANSI颜色替换模式，使用更简单的正则表达式
        (re.compile(r'\x1B\[31m([^\x1B]*)'), r'<span style="color: red;">\1</span>'),
        (re.compile(r'\x1B\[1;31m([^\x1B]*)'), r'<span style="color: #FF0000;">\1</span>'),
        (re.compile(r'\x1B\[32m([^\x1B]*)'), r'<span style="color: green;">\1</span>'),
        (re.compile(r'\x1B\[1;32m([^\x1B]*)'), r'<span style="color: #00FF00;">\1</span>'),
        (re.compile(r'\x1B\[33m([^\x1B]*)'), r'<span style="color: #808000;">\1</span>'),
        (re.compile(r'\x1B\[1;33m([^\x1B]*)'), r'<span style="color: #FFFF00;">\1</span>'),
        (re.compile(r'\x1B\[34m([^\x1B]*)'), r'<span style="color: blue;">\1</span>'),
        (re.compile(r'\x1B\[1;34m([^\x1B]*)'), r'<span style="color: #0000FF;">\1</span>'),
        (re.compile(r'\x1B\[0m'), '</span>')  # 重置代码
    ]

    def _has_ansi_codes(self, text):
        """检查文本是否包含ANSI控制符"""
        try:
            # 使用预编译的正则表达式
            return bool(self._ansi_pattern.search(text))
        except Exception:
            return False

    def _convert_ansi_to_html(self, text):
        """将ANSI控制符转换为HTML格式 - 性能优化版本"""
        try:
            # 首先快速检查是否包含ANSI控制符
            if not self._has_ansi_codes(text):
                return text
            
            # 使用预编译的正则表达式进行颜色替换
            html_text = text
            
            # 分两步处理：先处理颜色开始标记，再处理重置标记
            for pattern, replacement in self._color_replacements:
                html_text = pattern.sub(replacement, html_text)
            
            # 移除剩余的ANSI控制符
            html_text = self._ansi_pattern.sub('', html_text)
            
            # 修复可能的未闭合标签（简单的修复）
            if '<span' in html_text and '</span>' not in html_text:
                html_text += '</span>'
            
            return html_text
            
        except Exception as e:
            # 如果转换失败，使用预编译的正则表达式返回纯文本
            return self._ansi_pattern.sub('', text)



    # _aggressive_manage_buffer_size方法已移除，使用滑动文本块机制替代

    @Slot(int, str)
    def addToBuffer(self, index, string):
        # 🚀 Turbo模式：智能批量处理
        if self.turbo_mode and len(string) < 2048:  # 增大阈值，更多数据使用批量处理
            self.batch_buffers[index] += string
            
            # 🚀 优化：如果批量缓冲区太大，立即处理避免延迟过久
            if len(self.batch_buffers[index]) > 8192:  # 增加批量处理阈值到8KB
                self._process_batch_buffer(index)
                return
            
            # 设置批量处理定时器
            if self.batch_timers[index] is not None:
                self.batch_timers[index].stop()
            else:
                self.batch_timers[index] = QTimer()
                # 🔧 修复重复问题：只连接一次信号，避免重复连接导致重复触发
                self.batch_timers[index].timeout.connect(
                    lambda idx=index: self._process_batch_buffer(idx)
                )
            
            # 增加批量处理延迟，减少处理频率
            current_delay = self.batch_delay
            # 根据缓冲区大小动态调整延迟
            if len(self.batch_buffers[index]) > 4096:
                current_delay = max(10, self.batch_delay // 2)  # 缓冲区较大时，缩短延迟
            
            self.batch_timers[index].start(current_delay)
            return
        
        # 标准模式或大数据包：直接处理
        self._process_buffer_data(index, string)
    
    def _process_batch_buffer(self, index):
        """处理批量缓冲区"""
        if len(self.batch_buffers[index]) > 0:
            batch_data = bytes(self.batch_buffers[index])
            self.batch_buffers[index].clear()
            self._process_buffer_data(index, batch_data)
            
            # 🚀 Turbo模式优化：批量处理后强制触发UI更新
            if hasattr(self.parent, 'main_window') and self.parent.main_window:
                if hasattr(self.parent.main_window, 'page_dirty_flags'):
                    # 标记相关页面需要更新
                    # MDI 架构：page_dirty_flags 已废弃
                    # 数据更新由 DeviceMdiWindow 的定时器处理
                    pass
                        
                # MDI 架构：缓冲区更新由 DeviceMdiWindow 处理
                # handleBufferUpdate 已废弃
    
    def _process_buffer_data(self, index, string):
        # 批量处理优化：减少重复操作，提高性能
        
        # 添加数据到指定索引的缓冲区
        self.byte_buffer[index] += string
        
        # 标准化行尾标记：将所有行尾标记统一为LF（\n）
        self.byte_buffer[index] = self.byte_buffer[index].replace(b'\r\n', b'\n').replace(b'\r', b'\n')

        # 找到最后一个 '\n' 的索引（只处理完整行）
        newline = self.byte_buffer[index].rfind(b'\n')
        if newline == -1:  # 如果没有找到完整行，直接返回
            return
            
        # 分割数据：只处理完整的行，剩余部分保留在byte_buffer中
        new_buffer = self.byte_buffer[index][:newline + 1]
        self.byte_buffer[index] = self.byte_buffer[index][newline + 1:]
        
        # 使用配置的编码进行解码
        try:
            enc = self.parent.config.get_text_encoding() if hasattr(self.parent, 'config') else 'gbk'
            data = new_buffer.decode(enc, errors='ignore')
        except Exception:
            enc = 'gbk'
            data = new_buffer.decode(enc, errors='ignore')

        # 修复多余换行问题
        if data.endswith('\n\n'):
            data = data.rstrip('\n') + '\n'

        # 预构建缓冲区前缀
        prefix = "%02u> " % index
        
        # 优化的ANSI处理和缓冲区管理
        try:
            # 批量处理：只在必要时进行ANSI处理
            if self._has_ansi_codes(data):
                # 只在数据包含ANSI控制符时才调用ansi_processor
                clean_data = ansi_processor.remove_ansi_codes(data)
                if clean_data.endswith('\n\n'):
                    clean_data = clean_data.rstrip('\n') + '\n'
            else:
                # 快速路径：当没有ANSI控制符时，直接使用原始数据
                clean_data = data
            
            # 批量缓冲区追加：避免重复调用
            self._append_to_buffer(index+1, clean_data)
            self._append_to_buffer(0, prefix + clean_data)
            
            # 为彩色显示保留原始ANSI文本
            if hasattr(self, 'colored_buffers'):
                self._append_to_colored_buffer(index+1, data)
                self._append_to_colored_buffer(0, prefix + data)
                    
        except Exception as e:
            # 错误处理：使用更简单的回退机制
            logger.warning(f"ANSI处理失败，使用原始数据: {e}")
            self._append_to_buffer(index+1, data)
            self._append_to_buffer(0, prefix + data)
            if hasattr(self, 'colored_buffers'):
                self._append_to_colored_buffer(index+1, data)
                self._append_to_colored_buffer(0, prefix + data)
            
        # 标记页面需要更新（延迟更新策略）
        self.update_counter += 1
        if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
            # 只在累积一定数量的更新后才标记脏标志，减少UI更新频率
            # 增加阈值，从每2次更新一次改为每3次更新一次，大数据包阈值从1KB增加到2KB
            if self.update_counter % 3 == 0 or len(data) > 2048:  # 减少UI更新频率
                self.parent.main_window.page_dirty_flags[index+1] = True
                self.parent.main_window.page_dirty_flags[0] = True
        
        # 串口转发功能：将指定TAB的数据转发到串口
            if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                # 转发单个通道的数据（index+1对应TAB索引）
                self.parent.rtt2uart.add_tab_data_for_forwarding(index+1, data)
                # 转发所有数据（TAB 0）包含通道前缀
                buffer_parts = ["%02u> " % index, data]
                self.parent.rtt2uart.add_tab_data_for_forwarding(0, ''.join(buffer_parts))

            # 📋 统一日志处理：通道数据写入对应的日志文件（使用通道号0~15）
            # 减少日志写入频率：只在数据量较大或周期性写入
            if len(clean_data) > 1024 or self.update_counter % 5 == 0:
                self.write_data_to_buffer_log(index+1, clean_data, str(index))

            # 📋 统一过滤逻辑：使用清理过的数据进行筛选，确保与页面显示一致
            if clean_data.strip():  # 只处理非空数据
                clean_lines = [line for line in clean_data.split('\n') if line.strip()]
                self.process_filter_lines(clean_lines)

            self.finished.emit()
    
    def _append_to_buffer(self, index, data):
        """🚀 智能缓冲区追加：预分配 + 成倍扩容机制 + 连续重复检查"""
        if index < len(self.buffers):
            # 防御：如果被外部代码误置为字符串，立即恢复为分块列表
            if not isinstance(self.buffers[index], list):
                self.buffers[index] = []
                self.buffer_lengths[index] = 0
            
            # 🔧 连续重复检查：只检查最后一条记录，防止完全相同的连续数据被重复添加
            # 注意：不检查最近N条，因为周期性日志（如状态报告）可能在不同时间重复，但应该被保留
            if len(self.buffers[index]) > 0:
                last_data = self.buffers[index][-1]
                if data == last_data:
                    # 检测到连续重复数据，跳过添加
                    #logger.debug(f"检测到连续重复数据，跳过添加到buffer[{index}]: {data[:50]}...")
                    return
            current_length = self.buffer_lengths[index]
            new_length = current_length + len(data)
            
            # 🚀 检查是否需要扩容
            if new_length > self.buffer_capacities[index]:
                new_capacity = self._calculate_new_capacity(self.buffer_capacities[index], new_length)
                if new_capacity > self.buffer_capacities[index] and new_capacity <= self.max_capacity:
                    # 成倍扩容
                    old_capacity = self.buffer_capacities[index]
                    self.buffer_capacities[index] = new_capacity
                    memory_info = self.get_buffer_memory_usage()
                    logger.info(f"[EXPAND] Buffer {index} expanded: {old_capacity//1024}KB -> {new_capacity//1024}KB, "
                               f"总内存: {memory_info['total_memory_mb']:.1f}MB, 利用率: {memory_info['capacity_utilization']:.1f}%")
                elif self.buffer_capacities[index] >= self.max_capacity:
                    # 已达最大容量，清理旧数据
                    trim_size = self.max_capacity // 2  # 保留3.2MB
                    # 从头部移除旧块直到长度不超过目标
                    while self.buffer_lengths[index] > trim_size and self.buffers[index]:
                        removed = self.buffers[index].pop(0)
                        rem_len = len(removed)
                        self.buffer_lengths[index] -= rem_len
                        # 调整对应显示偏移，避免因头部裁剪导致显示滞后
                        self.display_lengths[index] = max(0, self.display_lengths[index] - rem_len)
                    logger.info(f"[TRIM] Buffer {index} trimmed to {self.buffer_lengths[index]//1024}KB (max capacity reached)")
            
            # 分块追加，避免大字符串反复拷贝
            self.buffers[index].append(data)
            self.buffer_lengths[index] += len(data)
    
    def _append_to_colored_buffer(self, index, data):
        """🎨 智能彩色缓冲区追加：预分配 + 成倍扩容机制 + 连续重复检查"""
        if hasattr(self, 'colored_buffers') and index < len(self.colored_buffers):
            # 防御：如果被误置为字符串，恢复为分块列表
            if not isinstance(self.colored_buffers[index], list):
                self.colored_buffers[index] = []
                self.colored_buffer_lengths[index] = 0
            
            # 🔧 连续重复检查：只检查最后一条记录，防止完全相同的连续数据被重复添加
            # 注意：不检查最近N条，因为周期性日志（如状态报告）可能在不同时间重复，但应该被保留
            if len(self.colored_buffers[index]) > 0:
                last_data = self.colored_buffers[index][-1]
                if data == last_data:
                    # 检测到连续重复数据，跳过添加
                    return
            current_length = self.colored_buffer_lengths[index]
            new_length = current_length + len(data)
            
            # 🚀 检查是否需要扩容
            if new_length > self.colored_buffer_capacities[index]:
                new_capacity = self._calculate_new_capacity(self.colored_buffer_capacities[index], new_length)
                if new_capacity > self.colored_buffer_capacities[index] and new_capacity <= self.max_capacity:
                    # 成倍扩容
                    old_capacity = self.colored_buffer_capacities[index]
                    self.colored_buffer_capacities[index] = new_capacity
                    memory_info = self.get_buffer_memory_usage()
                    logger.info(f"[EXPAND] Colored buffer {index} expanded: {old_capacity//1024}KB -> {new_capacity//1024}KB, "
                               f"总内存: {memory_info['total_memory_mb']:.1f}MB, 利用率: {memory_info['capacity_utilization']:.1f}%")
                elif self.colored_buffer_capacities[index] >= self.max_capacity:
                    # 已达最大容量，清理旧数据
                    trim_size = self.max_capacity // 2  # 保留3.2MB
                    trimmed_length = 0
                    while self.colored_buffer_lengths[index] > trim_size and self.colored_buffers[index]:
                        removed = self.colored_buffers[index].pop(0)
                        removed_len = len(removed)
                        self.colored_buffer_lengths[index] -= removed_len
                        trimmed_length += removed_len
                    
                    # 🔧 修复：通知所有MDI窗口更新last_display_lengths，避免数据丢失
                    if trimmed_length > 0 and hasattr(self.parent, 'main_window') and self.parent.main_window:
                        self._notify_mdi_windows_buffer_trimmed(index, trimmed_length)
                    
                    logger.info(f"[TRIM] Colored buffer {index} trimmed {trimmed_length//1024}KB, now {self.colored_buffer_lengths[index]//1024}KB (max capacity reached)")
            
            # 分块追加
            self.colored_buffers[index].append(data)
            self.colored_buffer_lengths[index] += len(data)
            
            # 🔧 修复：更新数据时间戳（用于自动重连监控）
            if hasattr(self.parent, 'main_window') and self.parent.main_window:
                if hasattr(self.parent.main_window, '_update_data_timestamp'):
                    self.parent.main_window._update_data_timestamp()
            
            # 📈 性能监控：记录数据增长
            self._log_performance_metrics()
    
    def get_buffer_memory_usage(self):
        """📈 获取缓冲区内存使用情况"""
        total_size = sum(self.buffer_lengths)
        max_size = max(self.buffer_lengths) if self.buffer_lengths else 0
        colored_size = sum(self.colored_buffer_lengths) if hasattr(self, 'colored_buffer_lengths') else 0
        
        return {
            'total_buffer_size': total_size,
            'max_single_buffer': max_size,
            'colored_buffer_size': colored_size,
            'total_memory_mb': (total_size + colored_size) / (1024 * 1024),
            'total_capacity': sum(self.buffer_capacities) + sum(self.colored_buffer_capacities),
            'capacity_utilization': (total_size + colored_size) / (sum(self.buffer_capacities) + sum(self.colored_buffer_capacities)) * 100 if sum(self.buffer_capacities) > 0 else 0
        }

    def _extract_increment_from_chunks(self, chunks, last_size, max_bytes=None):
        """从分块列表中提取自 last_size 起的增量数据，并返回(new_text, current_total_size)。
        可选 max_bytes 限制返回文本的最大字节数（从尾部截取）。"""
        remaining = last_size
        total_len = 0
        out_parts = []
        for part in chunks:
            plen = len(part)
            total_len += plen
            if remaining >= plen:
                remaining -= plen
                continue
            if remaining > 0:
                out_parts.append(part[remaining:])
                remaining = 0
            else:
                out_parts.append(part)
        new_text = ''.join(out_parts)
        if max_bytes is not None and len(new_text) > max_bytes:
            new_text = new_text[-max_bytes:]
        return new_text, total_len
    
    def _calculate_new_capacity(self, current_capacity, required_size):
        """📈 计算新的缓冲区容量：成倍扩容机制"""
        new_capacity = current_capacity
        
        # 按成倍扩容直到满足需求
        while new_capacity < required_size and new_capacity < self.max_capacity:
            new_capacity *= self.growth_factor
        
        # 不超过最大容量
        return min(new_capacity, self.max_capacity)
    
    def _notify_mdi_windows_buffer_trimmed(self, buffer_index, trimmed_length):
        """通知所有MDI窗口缓冲区被裁剪，需要更新last_display_lengths"""
        try:
            if not hasattr(self.parent, 'main_window') or not self.parent.main_window:
                return
            
            main_window = self.parent.main_window
            if not hasattr(main_window, 'device_sessions'):
                return
            
            # 遍历所有设备会话，更新对应的MDI窗口
            for session in main_window.device_sessions:
                if session.connection_dialog and session.connection_dialog.worker == self:
                    # 这是当前Worker对应的会话
                    if session.mdi_window and hasattr(session.mdi_window, 'last_display_lengths'):
                        if buffer_index < len(session.mdi_window.last_display_lengths):
                            old_length = session.mdi_window.last_display_lengths[buffer_index]
                            # 调整last_display_lengths，但不能小于0
                            new_length = max(0, old_length - trimmed_length)
                            session.mdi_window.last_display_lengths[buffer_index] = new_length
                            logger.debug(f"📊 Updated MDI window last_display_lengths[{buffer_index}]: {old_length} -> {new_length} (trimmed {trimmed_length} bytes)")
        except Exception as e:
            logger.error(f"Failed to notify MDI windows of buffer trim: {e}", exc_info=True)
    
    def _log_performance_metrics(self):
        """📈 记录性能指标：刷新率和数据量"""
        current_time = time.time()
        
        # 每5秒记录一次性能日志
        if current_time - self.last_log_time >= self.log_interval:
            memory_info = self.get_buffer_memory_usage()
            
            # 计算刷新率
            time_elapsed = current_time - self.last_log_time
            refresh_rate = self.refresh_count / time_elapsed if time_elapsed > 0 else 0
            
            # 记录性能指标
            # logger.info(f"[PERF] Performance monitoring - refresh rate: {refresh_rate:.1f}Hz, "
            #            f"总数据量: {memory_info['total_memory_mb']:.1f}MB, "
            #            f"容量利用率: {memory_info['capacity_utilization']:.1f}%, "
            #            f"最大单缓冲: {memory_info['max_single_buffer']//1024:.0f}KB")
            
            # 检查性能阈值
            if memory_info['total_memory_mb'] > 0.8:  # 800KB以上
                if refresh_rate < 10:  # 刷新率低于10Hz
                    logger.warning(f"[WARN] 性能警告 - 数据量: {memory_info['total_memory_mb']:.1f}MB, 刷新率下降至: {refresh_rate:.1f}Hz")
                    
            if memory_info['total_memory_mb'] > 2.0:  # 2MB以上
                if refresh_rate < 5:  # 刷新率低于5Hz
                    logger.error(f"[CRIT] 性能严重 - 数据量: {memory_info['total_memory_mb']:.1f}MB, 刷新率严重下降至: {refresh_rate:.1f}Hz")
            
            # 重置计数器
            self.refresh_count = 0
            self.last_log_time = current_time

    def _highlight_filter_text(self, line, search_word, compiled_pattern=None, is_regex=False):
        """为筛选文本添加高亮显示
        
        Args:
            line: 要处理的文本行
            search_word: 搜索词（用于普通匹配）
            compiled_pattern: 预编译的正则表达式模式（用于正则匹配）
            is_regex: 是否使用正则表达式匹配
        """
        try:
            # 🎨 使用明亮黄色背景 + 黑色文字高亮筛选关键词 - 增强对比度
            highlight_start = '\x1B[43;30m'  # 明亮黄色背景 + 黑色文字
            highlight_end = '\x1B[0m'        # 重置所有格式
            
            if is_regex and compiled_pattern is not None:
                # 正则表达式高亮：找到所有匹配并高亮
                matches = list(compiled_pattern.finditer(line))
                if not matches:
                    return line
                
                # 从后往前替换，避免索引偏移问题
                highlighted_line = line
                for match in reversed(matches):
                    start, end = match.span()
                    matched_text = highlighted_line[start:end]
                    highlighted_line = (
                        highlighted_line[:start] + 
                        f"{highlight_start}{matched_text}{highlight_end}" + 
                        highlighted_line[end:]
                    )
                
                return highlighted_line
            else:
                # 普通字符串高亮：大小写不敏感匹配
                if not search_word or search_word.lower() not in line.lower():
                    return line
                
            # 使用正则表达式进行大小写不敏感的替换，保持原文本的大小写
                import re
            pattern = re.escape(search_word)
            highlighted_line = re.sub(pattern, f"{highlight_start}\\g<0>{highlight_end}", line, flags=re.IGNORECASE)
            
            return highlighted_line
                
        except Exception:
            # 如果高亮失败，返回原始行
            return line

    def process_filter_lines(self, lines):
        """优化的过滤处理逻辑 - 支持单个TAB独立正则表达式配置"""
        # 预编译搜索词以提高性能
        search_words = []
        
        for i in range(17, MAX_TAB_SIZE):
            try:
                # 🔑 MDI架构改进：从配置中读取筛选条件
                # Worker的parent是ConnectionDialog，直接使用self.parent.config
                if hasattr(self.parent, 'config') and self.parent.config:
                    config = self.parent.config
                    tag_text = config.get_filter(i)
                    
                    # 添加调试日志
                    # if tag_text and tag_text.strip() and tag_text != "+":
                    #     logger.info(f"[FILTER] TAB[{i}] filter: '{tag_text}'")
                    
                    # 只处理非空的筛选条件
                    if tag_text and tag_text.strip() and tag_text != "+":
                        # 检查单个TAB的正则表达式状态
                        tab_regex_enabled = config.get_tab_regex_filter(i)
                        
                        # 如果该TAB启用正则表达式，预编译正则模式
                        if tab_regex_enabled:
                            try:
                                compiled_pattern = re.compile(tag_text, re.IGNORECASE)
                                search_words.append((i, tag_text, compiled_pattern, True))  # 添加正则标记
                            except re.error:
                                # 如果正则表达式无效，回退到普通字符串匹配
                                search_words.append((i, tag_text, None, False))
                        else:
                            search_words.append((i, tag_text, None, False))
            except:
                continue
        
        # 批量处理行 - 修复重复添加问题
        for line in lines:
            if not line.strip():
                continue
            
            # 🔧 修复重复问题：为每行数据记录已匹配的TAB索引，避免同一TAB重复添加
            matched_tabs = set()  # 记录当前行已匹配的TAB索引
                
            for item in search_words:
                # 支持新格式 (i, tag_text, compiled_pattern, is_regex)
                if len(item) == 4:
                    i, search_word, compiled_pattern, is_regex = item
                    
                    # 🔧 防重复：如果该TAB已经匹配过这行数据，跳过
                    if i in matched_tabs:
                        continue
                    
                    # 根据是否启用正则表达式决定匹配方式
                    if compiled_pattern is not None and is_regex:
                        # 正则表达式匹配
                        match_found = compiled_pattern.search(line) is not None
                    else:
                        # 普通字符串匹配（大小写不敏感）
                        match_found = search_word.lower() in line.lower()
                        
                    if match_found:
                        # 🔧 记录已匹配的TAB，防止同一TAB重复添加
                        matched_tabs.add(i)
                        
                        filtered_data = line + '\n'
                        # 🔧 使用重复检测机制添加筛选数据
                        self._append_to_buffer(i, filtered_data)
                        
                        # 🎨 处理彩色筛选数据 - 保持ANSI颜色格式
                        if hasattr(self, 'colored_buffers') and len(self.colored_buffers) > i:
                            # 创建带高亮的彩色数据（传递正则表达式参数）
                            highlighted_line = self._highlight_filter_text(line, search_word, compiled_pattern, is_regex)
                            highlighted_data = highlighted_line + '\n'
                            self._append_to_colored_buffer(i, highlighted_data)
                        
                        # 标记页面需要更新
                        if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
                            self.parent.main_window.page_dirty_flags[i] = True
                        
                        # 串口转发功能：转发筛选后的数据
                        if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                            self.parent.rtt2uart.add_tab_data_for_forwarding(i, filtered_data)
                        
                        # 📋 统一日志处理：筛选数据写入对应的日志文件
                        new_path = replace_special_characters(search_word)
                        self.write_data_to_buffer_log(i, filtered_data, new_path)
                elif len(item) == 3:
                    # 兼容旧格式 (i, tag_text, compiled_pattern)
                    i, search_word, compiled_pattern = item
                    
                    # 🔧 防重复：如果该TAB已经匹配过这行数据，跳过
                    if i in matched_tabs:
                        continue
                    
                    # 根据是否有编译的正则模式决定匹配方式
                    is_regex = compiled_pattern is not None
                    if compiled_pattern is not None:
                        # 正则表达式匹配
                        match_found = compiled_pattern.search(line) is not None
                    else:
                        # 普通字符串匹配（大小写不敏感）
                        match_found = search_word.lower() in line.lower()
                        
                    if match_found:
                        # 🔧 记录已匹配的TAB，防止同一TAB重复添加
                        matched_tabs.add(i)
                        
                        filtered_data = line + '\n'
                        # 🔧 使用重复检测机制添加筛选数据
                        self._append_to_buffer(i, filtered_data)
                        
                        # 🎨 处理彩色筛选数据 - 保持ANSI颜色格式
                        if hasattr(self, 'colored_buffers') and len(self.colored_buffers) > i:
                            # 创建带高亮的彩色数据（传递正则表达式参数）
                            highlighted_line = self._highlight_filter_text(line, search_word, compiled_pattern, is_regex)
                            highlighted_data = highlighted_line + '\n'
                            self._append_to_colored_buffer(i, highlighted_data)
                        
                        # 标记页面需要更新
                        if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
                            self.parent.main_window.page_dirty_flags[i] = True
                        
                        # 串口转发功能：转发筛选后的数据
                        if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                            self.parent.rtt2uart.add_tab_data_for_forwarding(i, filtered_data)
                        
                        # 📋 统一日志处理：筛选数据写入对应的日志文件
                        new_path = replace_special_characters(search_word)
                        self.write_data_to_buffer_log(i, filtered_data, new_path)
                else:
                    # 兼容旧格式
                    i, search_word = item
                    
                    # 🔧 防重复：如果该TAB已经匹配过这行数据，跳过
                    if i in matched_tabs:
                        continue
                        
                    match_found = search_word.lower() in line.lower()
                    
                    if match_found:
                        # 🔧 记录已匹配的TAB，防止同一TAB重复添加
                        matched_tabs.add(i)
                        
                        filtered_data = line + '\n'
                        # 🔧 使用重复检测机制添加筛选数据
                        self._append_to_buffer(i, filtered_data)
                        
                        # 🎨 处理彩色筛选数据 - 保持ANSI颜色格式
                        if hasattr(self, 'colored_buffers') and len(self.colored_buffers) > i:
                            # 创建带高亮的彩色数据
                            highlighted_line = self._highlight_filter_text(line, search_word)
                            highlighted_data = highlighted_line + '\n'
                            self._append_to_colored_buffer(i, highlighted_data)
                        
                        # 标记页面需要更新
                        if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
                            self.parent.main_window.page_dirty_flags[i] = True
                        
                        # 串口转发功能：转发筛选后的数据
                        if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                            self.parent.rtt2uart.add_tab_data_for_forwarding(i, filtered_data)
                        
                        # 📋 统一日志处理：筛选数据写入对应的日志文件
                        new_path = replace_special_characters(search_word)
                        self.write_data_to_buffer_log(i, filtered_data, new_path)

def replace_special_characters(path, replacement='_'):
    # 定义需要替换的特殊字符的正则表达式模式
    pattern = r'[<>:"/\\|?*]'

    # 使用指定的替换字符替换特殊字符
    new_path = re.sub(pattern, replacement, path)

    return new_path


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.keywords = []
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor(0, 0, 0))      # 黑色文字增强对比度
        # 移除加粗以保持等宽字体对齐
        # self.keyword_format.setFontWeight(QFont.Bold)
        self.keyword_format.setBackground(QColor(255, 255, 0))  # 明亮黄色背景

        self.pattern = None
        self.main_window = None  # 用于获取当前字体设置

    def setKeywords(self, keywords):
        self.keywords = keywords
        escaped_keywords = [re.escape(keyword) for keyword in keywords]
        # 将问号进行转义
        escaped_keywords = [keyword.replace('?', r'\?') for keyword in escaped_keywords]
        self.pattern = re.compile(r'\b(?:' + '|'.join(escaped_keywords) + r')\b')

    def highlightBlock(self, text):
        # 1. 首先处理关键词高亮
        if self.pattern:
            for match in self.pattern.finditer(text):
                start_index = match.start()
                match_length = match.end() - start_index
                
                # 🔑 关键修复：动态获取当前字体并应用到高亮格式
                # 这样可以确保高亮文本使用正确的字体
                format = QTextCharFormat(self.keyword_format)
                
                # 尝试获取当前使用的字体
                if self.main_window and hasattr(self.main_window, 'ui'):
                    try:
                        if hasattr(self.main_window.ui, 'font_combo'):
                            font_name = self.main_window.ui.font_combo.currentText()
                        else:
                            font_name = "Consolas"
                        font_size = self.main_window.ui.fontsize_box.value()
                        
                        font = QFont(font_name, font_size)
                        font.setFixedPitch(True)
                        font.setStyleHint(QFont.TypeWriter)
                        font.setStyleStrategy(QFont.PreferDefault)
                        font.setKerning(False)
                        format.setFont(font)
                    except:
                        # 如果获取失败，使用文档默认字体
                        pass
                
                self.setFormat(start_index, match_length, format)
        

    


def is_dummy_thread(thread):
    return thread.name.startswith('Dummy')

if __name__ == "__main__":
    # 🔑 单实例机制 - 确保只有一个程序实例运行
    import socket
    import atexit
    
    # 使用socket实现单实例锁（比QLocalServer更可靠）
    LOCK_SOCKET = None
    LOCK_PORT = 59768  # 使用固定端口号作为锁
    
    def acquire_instance_lock():
        """获取单实例锁"""
        global LOCK_SOCKET
        try:
            LOCK_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            LOCK_SOCKET.bind(('127.0.0.1', LOCK_PORT))
            logger.info(f"✅ Single instance lock acquired on port {LOCK_PORT}")
            return True
        except OSError:
            logger.warning(f"⚠️ Another instance is already running (port {LOCK_PORT} in use)")
            return False
    
    def release_instance_lock():
        """释放单实例锁"""
        global LOCK_SOCKET
        if LOCK_SOCKET:
            try:
                LOCK_SOCKET.close()
                logger.info("Single instance lock released")
            except:
                pass
            LOCK_SOCKET = None
    
    def cleanup_zombie_processes():
        """清理僵尸进程 - 查找并终止可能遗留的XexunRTT进程"""
        try:
            current_pid = os.getpid()
            exe_name = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])
            
            # 查找所有XexunRTT相关进程
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    # 跳过当前进程
                    if proc.pid == current_pid:
                        continue
                    
                    # 检查进程名称
                    proc_name = proc.info.get('name', '')
                    proc_exe = proc.info.get('exe', '')
                    
                    # 匹配XexunRTT进程
                    if ('XexunRTT' in proc_name or 'xexunrtt' in proc_name.lower() or
                        (proc_exe and 'XexunRTT' in proc_exe)):
                        logger.warning(f"🔍 Found zombie process: PID={proc.pid}, Name={proc_name}")
                        proc.terminate()  # 先尝试优雅终止
                        proc.wait(timeout=3)  # 等待最多3秒
                        killed_count += 1
                        logger.info(f"✅ Terminated zombie process: PID={proc.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
            
            if killed_count > 0:
                logger.info(f"✅ Cleaned up {killed_count} zombie process(es)")
                time.sleep(1)  # 等待进程完全退出
        except Exception as e:
            logger.error(f"❌ Failed to cleanup zombie processes: {e}")
    
    def emergency_cleanup():
        """紧急清理函数 - 在程序异常退出时强制关闭JLink"""
        try:
            import pylink
            # 创建一个临时JLink对象尝试关闭可能遗留的连接
            temp_jlink = pylink.JLink()
            try:
                if temp_jlink.connected():
                    temp_jlink.close()
                    logger.debug("[EMERGENCY] Force closed JLink connection on exit")
            except:
                pass
        except:
            pass
        
        # 释放单实例锁
        release_instance_lock()
    
    # 注册退出处理器
    atexit.register(emergency_cleanup)
    
    # 1. 先清理可能的僵尸进程
    cleanup_zombie_processes()
    
    # 2. 尝试获取单实例锁
    if not acquire_instance_lock():
        # 如果无法获取锁，说明有其他实例在运行
        # 提示用户选择是否终止旧进程
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)
            
            # 查找XexunRTT进程
            current_pid = os.getpid()
            xexunrtt_processes = []
            
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                    try:
                        if proc.pid == current_pid:
                            continue
                        
                        proc_name = proc.info.get('name', '')
                        proc_exe = proc.info.get('exe', '')
                        
                        # 匹配XexunRTT进程或python进程运行main_window.py
                        if ('XexunRTT' in proc_name or 'xexunrtt' in proc_name.lower() or
                            (proc_exe and 'XexunRTT' in proc_exe)):
                            xexunrtt_processes.append({
                                'pid': proc.pid,
                                'name': proc_name,
                                'exe': proc_exe or 'N/A'
                            })
                        elif 'python' in proc_name.lower():
                            # 检查命令行是否包含main_window.py
                            cmdline = proc.info.get('cmdline', [])
                            if cmdline and any('main_window.py' in arg for arg in cmdline):
                                xexunrtt_processes.append({
                                    'pid': proc.pid,
                                    'name': proc_name,
                                    'exe': ' '.join(cmdline)
                                })
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except ImportError:
                pass
            
            # 构建进程信息
            if xexunrtt_processes:
                process_info = "\n".join([
                    f"PID: {p['pid']} - {p['name']}\n{QCoreApplication.translate('main_window', 'Path')}: {p['exe']}"
                    for p in xexunrtt_processes
                ])
            else:
                process_info = QCoreApplication.translate("main_window", 
                    "Unable to detect specific process information\n"
                    "The port may be occupied or process permission is insufficient")
            
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT - Already Running"))
            msg.setText(QCoreApplication.translate("main_window", "XexunRTT is already running!"))
            msg.setInformativeText(
                QCoreApplication.translate("main_window",
                    "Another instance of XexunRTT is currently running.\n\n"
                    "If you don't see the window, there might be a zombie process.\n"
                    "Please check Task Manager and terminate any XexunRTT processes manually.")
            )
            msg.setDetailedText(process_info)
            
            # 如果找到了进程,提供终止选项
            if xexunrtt_processes:
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.setDefaultButton(QMessageBox.No)
                msg.button(QMessageBox.Yes).setText(QCoreApplication.translate("main_window", "Terminate Old Processes and Start"))
                msg.button(QMessageBox.No).setText(QCoreApplication.translate("main_window", "Cancel"))
                
                result = msg.exec()
                
                if result == QMessageBox.Yes:
                    # 用户选择终止旧进程
                    killed_count = 0
                    try:
                        import psutil
                        for proc_info in xexunrtt_processes:
                            try:
                                proc = psutil.Process(proc_info['pid'])
                                proc.terminate()  # 先尝试优雅终止
                                proc.wait(timeout=3)  # 等待3秒
                                killed_count += 1
                                logger.info(f"✅ 已终止旧进程 PID: {proc_info['pid']}")
                            except psutil.TimeoutExpired:
                                # 如果优雅终止失败,强制杀死
                                try:
                                    proc.kill()
                                    killed_count += 1
                                    logger.info(f"✅ 已强制终止旧进程 PID: {proc_info['pid']}")
                                except Exception as e:
                                    logger.error(f"❌ 无法终止进程 PID {proc_info['pid']}: {e}")
                            except Exception as e:
                                logger.error(f"❌ 终止进程失败 PID {proc_info['pid']}: {e}")
                        
                        if killed_count > 0:
                            logger.info(f"🎯 已清理 {killed_count} 个旧进程,等待端口释放...")
                            time.sleep(2)  # 等待端口释放
                            
                            # 重新尝试获取锁
                            if acquire_instance_lock():
                                logger.info("成功获取单实例锁,继续启动")
                                # 继续启动程序(不退出)
                            else:
                                QMessageBox.critical(
                                    None,
                                    "启动失败",
                                    "终止旧进程后仍无法获取锁,可能端口仍被占用。\n请手动检查任务管理器。"
                                )
                                sys.exit(1)
                        else:
                            QMessageBox.warning(None, "终止失败", "无法终止任何旧进程,程序将退出。")
                            sys.exit(1)
                    except ImportError:
                        QMessageBox.warning(None, "功能不可用", "psutil模块未安装,无法自动终止进程。")
                        sys.exit(1)
                else:
                    # 用户选择取消
                    sys.exit(0)
            else:
                # 没有找到进程,只显示确定按钮
                msg.setStandardButtons(QMessageBox.Ok)
                msg.exec()
                sys.exit(1)
        except Exception as e:
            logger.error(f"处理单实例冲突时出错: {e}", exc_info=True)
            sys.exit(1)
    
    # 获取DPI设置并应用环境变量
    manual_dpi = config_manager.get_dpi_scale()
    if manual_dpi != "auto":
        try:
            dpi_value = float(manual_dpi)
            if sys.platform == "darwin":  # macOS
                # 设置Qt环境变量强制DPI缩放
                os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
                os.environ['QT_SCALE_FACTOR'] = str(dpi_value)
                os.environ['QT_SCREEN_SCALE_FACTORS'] = str(dpi_value)
                os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
                logger.debug(f"[CONFIG] Setting Qt DPI environment variables: {dpi_value}")
        except ValueError:
            pass
    
    # Check if application instance exists, create if not
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Load and install translation files
    translator = QTranslator()
    # Try to load translation files from multiple locations
    translation_loaded = False
    
    # 🔧 获取资源文件路径（支持PyInstaller打包）
    def get_resource_path(filename):
        """获取资源文件的正确路径（支持开发环境和PyInstaller打包环境）"""
        # PyInstaller打包后，资源文件在临时目录_MEIPASS中
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, filename)
        # 开发环境，资源文件在当前目录
        return filename
    
    # 🌐 根据配置文件加载对应的语言
    config_language = config_manager.get_language()
    logger.debug(f"[LANGUAGE] Configured language: {config_language}")
    
    # 根据配置的语言加载对应的翻译文件
    if config_language == 'zh_CN':
        # 简体中文
        qm_paths = [
            get_resource_path(os.path.join("lang", "xexunrtt_zh_CN.qm")),  # PyInstaller或当前目录
            os.path.join("lang", "xexunrtt_zh_CN.qm"),  # lang目录
            "xexunrtt_zh_CN.qm",  # 当前目录（备用）
            "../Resources/lang/xexunrtt_zh_CN.qm",  # Resources目录（macOS）
            ":/lang/xexunrtt_zh_CN.qm"  # Qt资源（备用）
        ]
        
        for qm_path in qm_paths:
            if translator.load(qm_path):
                QCoreApplication.installTranslator(translator)
                translation_loaded = True
                logger.debug(f"[OK] Simplified Chinese translation loaded successfully: {qm_path}")
                # Test if translation is working
                test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
                logger.debug(f"翻译测试: 'JLink Debug Log' → '{test_text}'")
                break
        
        if not translation_loaded:
            logger.debug("[WARNING] Cannot load Simplified Chinese translation file, using English interface")
    
    elif config_language == 'zh_TW':
        # 繁体中文
        qm_paths = [
            get_resource_path(os.path.join("lang", "xexunrtt_zh_TW.qm")),  # PyInstaller或当前目录
            os.path.join("lang", "xexunrtt_zh_TW.qm"),  # lang目录
            "xexunrtt_zh_TW.qm",  # 当前目录（备用）
            "../Resources/lang/xexunrtt_zh_TW.qm",  # Resources目录（macOS）
            ":/lang/xexunrtt_zh_TW.qm"  # Qt资源（备用）
        ]
        
        for qm_path in qm_paths:
            if translator.load(qm_path):
                QCoreApplication.installTranslator(translator)
                translation_loaded = True
                logger.debug(f"[OK] Traditional Chinese translation loaded successfully: {qm_path}")
                # Test if translation is working
                test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
                logger.debug(f"翻譯測試: 'JLink Debug Log' → '{test_text}'")
                break
        
        if not translation_loaded:
            logger.debug("[WARNING] Cannot load Traditional Chinese translation file, using English interface")
    elif config_language == 'en_US':
        logger.debug("[LANGUAGE] Using English interface (no translation file needed)")
    else:
        logger.debug(f"[WARNING] Unknown language '{config_language}', using English interface")

    # Load Qt built-in translation files (only for Chinese)
    qt_translator = QTranslator()
    qt_translation_loaded = False
    
    if config_language in ['zh_CN', 'zh_TW']:
        # 根据语言选择对应的Qt翻译文件
        qt_translation_file = "qt_zh_CN.qm" if config_language == 'zh_CN' else "qt_zh_TW.qm"
        
        # 尝试按优先级加载Qt翻译文件
        qt_qm_paths = [
            get_resource_path(qt_translation_file),  # PyInstaller或当前目录
            qt_translation_file,  # 当前目录（备用）
            f"../Resources/{qt_translation_file}",  # Resources目录（macOS）
            f":/{qt_translation_file}"  # Qt资源（备用）
        ]
        
        for qt_qm_path in qt_qm_paths:
            if qt_translator.load(qt_qm_path):
                QCoreApplication.installTranslator(qt_translator)
                qt_translation_loaded = True
                logger.debug(f"[OK] Qt translation loaded successfully: {qt_qm_path}")
                break
        
        if not qt_translation_loaded:
            logger.debug(f"[WARNING] Cannot load Qt translation file: {qt_translation_file}")
    
    # Create main window
    main_window = RTTMainWindow()
    
    
    # Update translations before window display
    if hasattr(main_window, '_update_ui_translations'):
        main_window._update_ui_translations()
    
    # Show main window first (maximized)
    main_window.showMaximized()
    
    # Then show connection configuration dialog
    main_window.show_connection_dialog()

    sys.exit(app.exec())
