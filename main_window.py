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

# 第三方库导入
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
    QSizePolicy, QButtonGroup, QListWidget, QListWidgetItem, QTabBar
)
from PySide6.QtNetwork import QLocalSocket, QLocalServer

# 项目模块导入
from ui_rtt2uart_updated import Ui_ConnectionDialog
from ui_sel_device import Ui_Dialog
from ui_xexunrtt import Ui_xexun_rtt
from rtt2uart import ansi_processor, rtt_to_serial
from config_manager import config_manager
#from performance_test import show_performance_test
import resources_rc


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
        print(f"Warning: Failed to set console encoding: {e}")

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
    """自定义JLink日志处理器，将日志输出到GUI"""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
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
        """在GUI中添加消息"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_message = f"[{timestamp}] {message}"
            
            # 兼容 QPlainTextEdit 与 QTextEdit
            if hasattr(self.text_widget, 'appendPlainText'):
                self.text_widget.appendPlainText(formatted_message)
            else:
                self.text_widget.append(formatted_message)
            
            # 自动滚动到底部
            scrollbar = self.text_widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # 限制日志行数，避免内存占用过多
            document = self.text_widget.document()
            if document.blockCount() > 1000:
                cursor = self.text_widget.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)
                cursor.removeSelectedText()
        except Exception:
            pass

logging.basicConfig(level=logging.WARN,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

# pylink支持的最大速率是12000kHz（Release v0.7.0开始支持15000及以上速率）
speed_list = [5, 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 750,
              900, 1000, 1334, 1600, 2000, 2667, 3200, 4000, 4800, 5334, 6000, 8000, 9600, 12000,
              15000, 20000, 25000, 30000, 40000, 50000]

baudrate_list = [50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
                 9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600]

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

        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
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
            # 🔧 清除纵向选择的高亮
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
        if self.column_select_mode:
            self.column_select_mode = False
            # 保存选择信息以便复制
            self._saveColumnSelection()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
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
    
    def mousePressEvent(self, event):
        """处理鼠标点击事件，鼠标中键点击清空筛选"""
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.pos())
            if index >= 17:  # 只处理Filters标签
                # 清空该标签页
                if self.main_window:
                    # 保存当前标签页索引
                    current_index = self.main_window.ui.tem_switch.currentIndex()
                    # 切换到目标标签页
                    self.main_window.ui.tem_switch.setCurrentIndex(index)
                    # 执行清空操作
                    self.main_window.on_clear_clicked()
                    # 重置标签文本为"filter"
                    self.setTabText(index, QCoreApplication.translate("main_window", "filter"))
                    # 恢复原来的标签页（如果不是同一个）
                    if current_index != index:
                        self.main_window.ui.tem_switch.setCurrentIndex(current_index)
                    logger.info(f"[MIDDLE-CLICK] Cleared filter TAB {index}")
                event.accept()
                return
        super().mousePressEvent(event)
    
    def tabSizeHint(self, index):
        """重写标签大小提示，让当前标签优先完整显示"""
        # 获取原始大小提示
        size = super().tabSizeHint(index)
        
        # 如果是当前标签，保持完整宽度
        if index == self.currentIndex():
            return size
        
        # 非当前标签，缩小到最小宽度（显示省略号）
        # 设置最小宽度为字体宽度的3倍（足够显示1-2个字符+省略号）
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.font())
        min_width = fm.averageCharWidth() * 4  # 4个字符宽度
        
        # 返回最小宽度和原始宽度的较小值
        size.setWidth(min(size.width(), max(min_width, 40)))
        return size
    
    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.pos())
        if index >= 17:
            old_text = self.tabText(index)
            
            # 获取当前TAB的正则表达式状态
            current_regex_state = False
            if self.main_window and self.main_window.connection_dialog:
                current_regex_state = self.main_window.connection_dialog.config.get_tab_regex_filter(index)
            
            # 显示自定义对话框
            dialog = FilterEditDialog(self, old_text, current_regex_state)
            if dialog.exec() == QDialog.Accepted:
                new_text = dialog.get_filter_text()
                regex_enabled = dialog.is_regex_enabled()
                
                # 更新TAB文本
                if new_text:
                    self.setTabText(index, new_text)
                else:
                    self.setTabText(index, QCoreApplication.translate("main_window", "filter"))
                
                # 保存过滤器设置和正则表达式状态
                if self.main_window and self.main_window.connection_dialog:
                    # 保存筛选文本（包括空字符串）
                    if new_text:
                        self.main_window.connection_dialog.config.set_filter(index, new_text)
                    else:
                        # 用户清空了筛选，保存空字符串
                        self.main_window.connection_dialog.config.set_filter(index, "")
                    
                    # 🔧 修改：为单个TAB保存正则表达式状态
                    self.main_window.connection_dialog.config.set_tab_regex_filter(index, regex_enabled)
                    self.main_window.connection_dialog.config.save_config()
                    
                    print(f"[SAVE] TAB {index} filter='{new_text}' regex={regex_enabled}")

class RTTMainWindow(QMainWindow):
    def __init__(self):
        super(RTTMainWindow, self).__init__()
        
        # 为每个窗口生成唯一标识符，确保日志文件夹不冲突
        import uuid
        import time
        import threading
        
        # 使用UUID + 时间戳 + 线程ID确保绝对唯一性
        timestamp = str(int(time.time() * 1000000))[-8:]  # 微秒时间戳后8位
        thread_id = str(threading.get_ident())[-4:]  # 线程ID后4位
        uuid_part = str(uuid.uuid4())[:4]  # UUID前4位
        self.window_id = f"{uuid_part}{timestamp[-4:]}{thread_id}"
        
        logger.info(f"Window initialized with ID: {self.window_id}")
        
        self.connection_dialog = None
        self._is_closing = False  # 标记主窗口是否正在关闭
        
        # 获取DPI缩放比例（支持手动设置或自动检测）
        manual_dpi = config_manager.get_dpi_scale()
        self.dpi_scale = get_dpi_scale_factor(manual_dpi)
        logger.info(f"Current DPI scale: {self.dpi_scale:.2f}")
        
        # 设置主窗口属性
        self.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT - RTT Debug Main Window"))
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        
        # 根据DPI调整窗口大小
        base_width, base_height = 1200, 800
        adaptive_width, adaptive_height = get_adaptive_window_size(base_width, base_height, self.dpi_scale)
        self.resize(adaptive_width, adaptive_height)
        logger.info(f"Window size adjusted to: {adaptive_width}x{adaptive_height}")
        
        # 设置最小窗口尺寸 - 允许极小窗口以便多设备同时使用
        min_width = 200  # 极小宽度，只显示核心信息
        min_height = 150  # 极小高度
        self.setMinimumSize(min_width, min_height)
        logger.info(f"Minimum window size set to: {min_width}x{min_height}")
        
        # 紧凑模式状态
        self.compact_mode = False
        
        # 添加右键菜单支持紧凑模式
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # 创建中心部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建菜单栏和状态栏
        self._create_menu_bar()
        self._create_status_bar()
        
        # 初始化时禁用RTT相关功能，直到连接成功
        self._set_rtt_controls_enabled(False)
        
        # 先设置原有的UI
        self.ui = Ui_xexun_rtt()
        self.ui.setupUi(self.central_widget)
        
        # 自动重连相关变量
        self.manual_disconnect = False  # 是否为手动断开
        self.last_data_time = 0  # 上次收到数据的时间戳
        self.data_check_timer = QTimer(self)  # 数据检查定时器
        self.data_check_timer.timeout.connect(self._check_data_timeout)
        
        # 立即创建连接对话框以便加载配置
        self.connection_dialog = ConnectionDialog(self)
        # 连接成功信号
        self.connection_dialog.connection_established.connect(self.on_connection_established)
        
        # 命令历史导航
        self.command_history_index = -1  # 当前历史命令索引，-1表示未选择历史命令
        self.current_input_text = ""     # 保存当前输入的文本
        # 连接断开信号
        self.connection_dialog.connection_disconnected.connect(self.on_connection_disconnected)
        
        # 在connection_dialog初始化后加载命令历史
        self.populateComboBox()
        
        # 串口转发设置已移动到连接对话框中
        
        # 保存原有的layoutWidget并重新设置其父级
        original_layout_widget = self.ui.layoutWidget
        original_layout_widget.setParent(None)  # 从原有父级移除
        
        # 创建新的主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)  # 防止子部件被完全折叠
        
        # 将原有的layoutWidget添加到分割器，并确保它能够扩展
        from PySide6.QtWidgets import QSizePolicy
        original_layout_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(original_layout_widget)
        
        # 创建JLink日志区域
        self._create_jlink_log_area()
        splitter.addWidget(self.jlink_log_widget)
        
        # 设置分割比例 (RTT区域占85%，JLink日志占15%)
        splitter.setSizes([850, 150])
        splitter.setStretchFactor(0, 1)  # RTT区域可拉伸
        splitter.setStretchFactor(1, 0)  # JLink日志区域固定大小
        
        # 设置中心部件的布局
        main_layout.addWidget(splitter)
        self.central_widget.setLayout(main_layout)
        
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

        self.action5 = QAction(self)
        self.action5.setShortcut(QKeySequence("F5"))
        
        self.action6 = QAction(self)
        self.action6.setShortcut(QKeySequence("F6"))

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
        self.addAction(self.action5)
        self.addAction(self.action6)
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
        self.action5.triggered.connect(self.toggle_lock_v_checkbox)
        self.action6.triggered.connect(self.toggle_lock_h_checkbox)
        self.action7.triggered.connect(self.toggle_style_checkbox)

        # 重定向 F9 到统一的执行逻辑（根据子菜单选择）
        self.action9.triggered.connect(self.restart_app_execute)
        #self.actionenter.triggered.connect(self.on_pushButton_clicked)

        self.ui.tem_switch.clear()
        editable_tab_bar = EditableTabBar()
        editable_tab_bar.main_window = self  # 设置主窗口引用
        self.ui.tem_switch.setTabBar(editable_tab_bar)  # 使用自定义的可编辑标签栏
        
        # 清除整个TabWidget的工具提示
        self.ui.tem_switch.setToolTip("")
        
        self.tabText = [None] * MAX_TAB_SIZE
        self.highlighter = [PythonHighlighter] * MAX_TAB_SIZE
        for i in range(MAX_TAB_SIZE):
            page = QWidget()
            page.setToolTip("")  # 清除页面的工具提示
            
            # 🎨 全部TAB支持ANSI彩色显示：统一使用支持纵向选择的ColumnSelectTextEdit
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
            
            text_edit = ColumnSelectTextEdit(page)
            text_edit.setAcceptRichText(True)
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.NoWrap)  # 禁用换行，提升性能
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示水平滚动条
            text_edit.setToolTip("")  # 清除文本编辑器的工具提示
            
            # 🚀 QTextEdit性能优化设置
            text_edit.setUndoRedoEnabled(False)  # 禁用撤销重做，节省内存
            text_edit.document().setUndoRedoEnabled(False)
            text_edit.setLineWrapMode(QTextEdit.NoWrap)  # 确保不换行
            
            # 🎯 行数限制仅适用于 QPlainTextEdit（当前默认均为 QTextEdit，保留兼容）
            if isinstance(text_edit, QPlainTextEdit):
                try:
                    line_limit = 10000
                    if self.connection_dialog and hasattr(self.connection_dialog, 'config'):
                        line_limit = int(self.connection_dialog.config.get_max_log_size())
                    if line_limit <= 0:
                        line_limit = 10000
                except Exception:
                    line_limit = 10000
                text_edit.document().setMaximumBlockCount(line_limit)
            
            # 🎨 设置等宽字体，提升渲染性能
            base_font_size = 10
            adaptive_font_size = get_adaptive_font_size(base_font_size, self.dpi_scale)
            
            if sys.platform == "darwin":  # macOS
                # macOS优先使用SF Mono，然后是Menlo，最后是Monaco
                font = QFont("SF Mono", adaptive_font_size)
                if not font.exactMatch():
                    font = QFont("Menlo", adaptive_font_size)
                if not font.exactMatch():
                    font = QFont("Monaco", adaptive_font_size)
            else:
                # Windows/Linux使用Consolas或Courier New
                font = QFont("Consolas", adaptive_font_size)
                if not font.exactMatch():
                    font = QFont("Courier New", adaptive_font_size)
            font.setFixedPitch(True)  # 等宽字体
            text_edit.setFont(font)
            
            layout = QVBoxLayout(page)  # 创建布局管理器
            layout.addWidget(text_edit)  # 将 QPlainTextEdit 添加到布局中
            self.highlighter[i] = PythonHighlighter(text_edit.document())
            
            if i == 0:
                self.ui.tem_switch.addTab(page, QCoreApplication.translate("main_window", "All"))  # Add page to tabWidget
                
                # 🚀 关键修复：设置GridLayout的拉伸因子，让TAB控件完全填充可用空间
                # 设置TAB控件的大小策略为完全扩展
                self.ui.tem_switch.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                self.ui.tem_switch.setMinimumSize(0, 0)  # 移除最小尺寸限制
                
                # 🎯 极小窗口优化：设置TAB控件支持极小尺寸
                self.ui.tem_switch.setUsesScrollButtons(True)  # 当标签过多时使用滚动按钮
                self.ui.tem_switch.setElideMode(Qt.ElideRight)  # 标签文本过长时省略显示
                
                # 🔧 标签宽度自适应：当前标签优先完整显示
                tab_bar = self.ui.tem_switch.tabBar()
                if tab_bar:
                    # 设置标签不扩展填充整个空间
                    tab_bar.setExpanding(False)
                    # 设置允许滚动，让当前标签始终可见
                    tab_bar.setUsesScrollButtons(True)
                    # 设置自动调整当前标签到可见区域
                    tab_bar.setAutoHide(False)
                
                # 设置GridLayout的行拉伸因子，让第0行（TAB控件行）占据主要垂直空间
                grid_layout = self.ui.gridLayout
                if grid_layout:
                    grid_layout.setRowStretch(0, 1)  # TAB控件行，占据主要垂直空间
                    grid_layout.setRowStretch(1, 0)  # 命令输入行，固定高度
                    grid_layout.setRowStretch(2, 0)  # 控制按钮行，固定高度
                    grid_layout.setRowStretch(3, 0)  # 其他行，固定高度
            elif i < 17:
                self.ui.tem_switch.addTab(page, '{}'.format(i - 1))  # 将页面添加到 tabWidget 中
            else:
                self.ui.tem_switch.addTab(page, QCoreApplication.translate("main_window", "filter"))
                # 只为自定义filter标签页设置工具提示
                self.ui.tem_switch.setTabToolTip(i, QCoreApplication.translate("main_window", "double click filter to write filter text"))
            
            self.tabText[i] = self.ui.tem_switch.tabText(i)
                
        self.ui.tem_switch.currentChanged.connect(self.switchPage)
        self.ui.pushButton.clicked.connect(self.on_pushButton_clicked)
        self.ui.dis_connect.clicked.connect(self.on_dis_connect_clicked)
        self.ui.re_connect.clicked.connect(self.on_re_connect_clicked)
        self.ui.clear.clicked.connect(self.on_clear_clicked)

        # JLink 文件日志跟随显示
        self.jlink_log_file_path = None
        self.jlink_log_tail_timer = None
        self.jlink_log_tail_offset = 0
        self.ui.openfolder.clicked.connect(self.on_openfolder_clicked)
        self.ui.LockH_checkBox.setChecked(True)
        
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
        
        # 连接滚动条锁定复选框的信号
        self.ui.LockH_checkBox.stateChanged.connect(self.on_lock_h_changed)
        self.ui.LockV_checkBox.stateChanged.connect(self.on_lock_v_changed)
        
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
        
        # 创建F8快捷键用于切换自动重连
        self.action8 = QAction(self)
        self.action8.setShortcut(QKeySequence("F8"))
        self.action8.triggered.connect(self._toggle_auto_reconnect)
        self.addAction(self.action8)
        
        self.set_style()
        
        # 创建定时器并连接到槽函数
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_periodic_task)
        self.timer.start(1000)  # 每1000毫秒（1秒）执行一次，进一步降低更新频率
        
        # 数据更新标志，用于智能刷新
        self.page_dirty_flags = [False] * MAX_TAB_SIZE
        
        # 立即加载并应用保存的配置
        self._apply_saved_settings()
    
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
        
        self.connection_menu.addSeparator()
        
        # 连接设置动作
        settings_action = QAction(QCoreApplication.translate("main_window", "Connection Settings(&S)..."), self)
        settings_action.triggered.connect(self._show_connection_settings)
        self.connection_menu.addAction(settings_action)
        
        # 窗口菜单
        self.window_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Window(&W)"))
        
        # 新建窗口动作
        new_window_action = QAction(QCoreApplication.translate("main_window", "New Window(&N)"), self)
        new_window_action.setShortcut(QKeySequence("Ctrl+N"))
        new_window_action.setStatusTip(QCoreApplication.translate("main_window", "Open a new window"))
        new_window_action.triggered.connect(self._new_window)
        self.window_menu.addAction(new_window_action)
        
        self.window_menu.addSeparator()
        
        # 紧凑模式切换动作
        self.compact_mode_action = QAction(QCoreApplication.translate("main_window", "Compact Mode(&M)"), self)
        self.compact_mode_action.setCheckable(True)
        self.compact_mode_action.setChecked(False)
        self.compact_mode_action.setShortcut(QKeySequence("Ctrl+M"))
        self.compact_mode_action.setStatusTip(QCoreApplication.translate("main_window", "Toggle compact mode for multi-device usage"))
        self.compact_mode_action.triggered.connect(self._toggle_compact_mode)
        self.window_menu.addAction(self.compact_mode_action)
        
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
        
        # 帮助菜单
        self.help_menu = menubar.addMenu(QCoreApplication.translate("main_window", "Help(&H)"))
        
        # 关于动作
        about_action = QAction(QCoreApplication.translate("main_window", "About(&A)..."), self)
        about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(about_action)
    
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
    
    def _new_window(self):
        """新建窗口"""
        try:
            import subprocess
            import sys
            import os
            
            if getattr(sys, 'frozen', False):
                # 如果是打包的APP，启动新的APP实例
                if sys.platform == "darwin":  # macOS
                    app_path = os.path.dirname(sys.executable)
                    app_path = os.path.dirname(os.path.dirname(os.path.dirname(app_path)))
                    app_path = os.path.join(app_path, "XexunRTT.app")
                    subprocess.Popen(["open", "-n", app_path])
                else:
                    # Windows/Linux
                    subprocess.Popen([sys.executable])
            else:
                # 开发环境，启动新的Python进程
                subprocess.Popen([sys.executable, "main_window.py"])
                
            print("[OK] New window started")
        except Exception as e:
            print(f"[ERROR] Failed to start new window: {e}")
            # 显示错误消息
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Error"), QCoreApplication.translate("main_window", "Failed to start new window:\n{}").format(e))
    
    def _toggle_compact_mode(self):
        """切换紧凑模式"""
        self.compact_mode = not self.compact_mode
        
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
        
        # 更新菜单项状态
        if hasattr(self, 'compact_mode_action'):
            self.compact_mode_action.setChecked(self.compact_mode)
    
    def _show_context_menu(self, position):
        """显示右键菜单"""
        context_menu = QMenu(self)
        
        # 紧凑模式选项 - 根据当前状态显示不同文本
        if self.compact_mode:
            compact_action = context_menu.addAction("🔍 恢复正常模式 (Ctrl+M)")
            compact_action.setToolTip("退出紧凑模式，恢复完整界面")
        else:
            compact_action = context_menu.addAction("📱 切换到紧凑模式 (Ctrl+M)")
            compact_action.setToolTip("进入紧凑模式，适合多窗口使用")
        
        compact_action.triggered.connect(self._toggle_compact_mode)
        
        context_menu.addSeparator()
        
        # 窗口管理
        window_menu = context_menu.addMenu("🪟 窗口管理")
        
        # 新建窗口
        new_window_action = window_menu.addAction("新建窗口 (Ctrl+N)")
        new_window_action.triggered.connect(self._new_window)
        
        # 最小化窗口
        minimize_action = window_menu.addAction("最小化窗口")
        minimize_action.triggered.connect(self.showMinimized)
        
        # 最大化/还原
        if self.isMaximized():
            maximize_action = window_menu.addAction("还原窗口")
            maximize_action.triggered.connect(self.showNormal)
        else:
            maximize_action = window_menu.addAction("最大化窗口")
            maximize_action.triggered.connect(self.showMaximized)
        
        context_menu.addSeparator()
        
        # 连接管理
        connection_menu = context_menu.addMenu("🔗 连接管理")
        
        # 连接设置
        settings_action = connection_menu.addAction("连接设置...")
        settings_action.triggered.connect(self._show_connection_settings)
        
        # 重新连接
        if hasattr(self, 'connection_dialog') and self.connection_dialog:
            if self.connection_dialog.start_state:
                reconnect_action = connection_menu.addAction("断开连接")
                reconnect_action.triggered.connect(self.on_dis_connect_clicked)
            else:
                reconnect_action = connection_menu.addAction("重新连接")
                reconnect_action.triggered.connect(self.on_re_connect_clicked)
        
        context_menu.addSeparator()
        
        # 程序控制
        program_menu = context_menu.addMenu("⚙️ 程序控制")
        
        # 正常退出
        quit_action = program_menu.addAction("退出程序")
        quit_action.triggered.connect(self.close)
        
        # 强制退出
        force_quit_action = program_menu.addAction("强制退出 (Ctrl+Alt+Q)")
        force_quit_action.triggered.connect(self._force_quit)
        force_quit_action.setToolTip("用于程序无响应时的紧急退出")
        
        # 显示菜单
        context_menu.exec(self.mapToGlobal(position))
    
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
            # 初始根据连接状态设置可用性
            self._set_encoding_menu_enabled(not (self.connection_dialog and self.connection_dialog.start_state))
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
        """选择编码：仅在断开时允许修改"""
        try:
            if self.connection_dialog and self.connection_dialog.start_state:
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please disconnect first before switching encoding"))
                # 回退选中状态
                self._refresh_encoding_menu_checks()
                return
            if self.connection_dialog:
                self.connection_dialog.config.set_text_encoding(enc)
                self.connection_dialog.config.save_config()
            # 同步 UI 旧控件（如存在）
            if hasattr(self, 'ui') and hasattr(self.ui, 'encoder'):
                idx = self.ui.encoder.findText(enc, Qt.MatchFixedString)
                if idx >= 0:
                    self.ui.encoder.setCurrentIndex(idx)
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
        # 连接中禁止切换编码
        self._set_encoding_menu_enabled(False)
        
        # 启动自动重连监控（如果已启用）
        self.manual_disconnect = False  # 清除手动断开标记
        if hasattr(self.ui, 'auto_reconnect_checkbox') and self.ui.auto_reconnect_checkbox.isChecked():
            self.last_data_time = time.time()
            self.data_check_timer.start(5000)  # 每5秒检查一次
            logger.info("Auto reconnect monitoring started")
        
        # 更新连接状态显示，包含设备信息
        if hasattr(self, 'connection_dialog') and self.connection_dialog and hasattr(self.connection_dialog, 'rtt2uart'):
            device_info = getattr(self.connection_dialog.rtt2uart, 'device_info', 'Unknown')
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected: %s") % device_info)
        else:
                    self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected"))
        
        # 应用保存的设置
        self._apply_saved_settings()
        
        # 更新状态显示
        self.update_status_bar()
        
        # 显示成功消息
        self.statusBar().showMessage(QCoreApplication.translate("main_window", "RTT connection established successfully"), 3000)
    
    def on_connection_disconnected(self):
        """连接断开后的处理"""
        # 禁用RTT相关功能
        self._set_rtt_controls_enabled(False)
        # 断开后可切换编码
        self._set_encoding_menu_enabled(True)
        
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
            print(f"[RESTORE] Scrollbar lock settings: H={settings['lock_h']}, V={settings['lock_v']}")
            self.ui.LockH_checkBox.setChecked(settings['lock_h'])
            self.ui.LockV_checkBox.setChecked(settings['lock_v'])
            self.ui.light_checkbox.setChecked(settings['light_mode'])
            self.ui.fontsize_box.setValue(settings['fontsize'])
            
            # 加载字体设置
            if hasattr(self.ui, 'font_combo'):
                saved_font = self.connection_dialog.config.get_fontfamily()
                index = self.ui.font_combo.findText(saved_font)
                if index >= 0:
                    self.ui.font_combo.setCurrentIndex(index)
            
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
            
            # 从配置管理器加载筛选器设置
            for i in range(17, MAX_TAB_SIZE):
                # 优先从INI配置加载筛选器
                filter_content = self.connection_dialog.config.get_filter(i)
                if filter_content:
                    self.ui.tem_switch.setTabText(i, filter_content)
                elif i - 17 < len(settings['filter']) and settings['filter'][i-17]:
                    # 兼容旧格式
                    self.ui.tem_switch.setTabText(i, settings['filter'][i-17])
                    
            # 应用样式
            self.set_style()
        except Exception as e:
            logger.warning(f'Failed to apply saved settings: {e}')
    
    def _create_jlink_log_area(self):
        """创建JLink日志显示区域"""
        # 创建JLink日志widget
        self.jlink_log_widget = QWidget()
        self.jlink_log_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.jlink_log_widget.setMinimumHeight(150)
        self.jlink_log_widget.setMaximumHeight(300)
        
        layout = QVBoxLayout(self.jlink_log_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 创建标题和控制按钮
        header_layout = QHBoxLayout()
        
        # JLink日志标题
        title_label = QLabel(QCoreApplication.translate("main_window", "JLink Debug Log"))
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title_label)
        
        # 添加弹簧
        header_layout.addStretch()
        
        # 清除日志按钮
        self.clear_jlink_log_btn = QPushButton(QCoreApplication.translate("main_window", "Clear Log"))
        self.clear_jlink_log_btn.setMaximumWidth(80)
        self.clear_jlink_log_btn.clicked.connect(self.clear_jlink_log)
        header_layout.addWidget(self.clear_jlink_log_btn)
        
        # 启用/禁用JLink日志按钮
        self.toggle_jlink_log_btn = QPushButton(QCoreApplication.translate("main_window", "Enable Verbose Log"))
        self.toggle_jlink_log_btn.setMaximumWidth(120)
        self.toggle_jlink_log_btn.setCheckable(True)
        self.toggle_jlink_log_btn.clicked.connect(self.toggle_jlink_verbose_log)
        header_layout.addWidget(self.toggle_jlink_log_btn)
        
        layout.addLayout(header_layout)
        
        # 创建JLink日志文本框（使用QPlainTextEdit提高性能）
        from PySide6.QtWidgets import QPlainTextEdit
        self.jlink_log_text = QPlainTextEdit()
        self.jlink_log_text.setReadOnly(True)
        self.jlink_log_text.setMinimumHeight(120)
        self.jlink_log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 设置等宽字体
        base_font_size = 9
        adaptive_font_size = get_adaptive_font_size(base_font_size, self.dpi_scale)
        
        if sys.platform == "darwin":  # macOS
            font = QFont("SF Mono", adaptive_font_size)
            if not font.exactMatch():
                font = QFont("Menlo", adaptive_font_size)
            if not font.exactMatch():
                font = QFont("Monaco", adaptive_font_size)
        else:
            font = QFont("Consolas", adaptive_font_size)
            if not font.exactMatch():
                font = QFont("Courier New", adaptive_font_size)
        self.jlink_log_text.setFont(font)
        # 不设置固定样式表，让它跟随主题
        
        layout.addWidget(self.jlink_log_text)
        
        # 初始化JLink日志捕获
        self.jlink_verbose_logging = False
        self._setup_jlink_logging()
        
        # 设置初始样式（需要在创建完JLink日志文本框后调用）
        QTimer.singleShot(0, self._update_jlink_log_style)
    
    def _setup_jlink_logging(self):
        """设置JLink日志捕获"""
        # 创建自定义日志处理器来捕获JLink日志
        self.jlink_log_handler = JLinkLogHandler(self.jlink_log_text)
        
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
            
            # 如果已经有连接，立即启用文件日志
            if (hasattr(self.connection_dialog, 'rtt2uart') and 
                self.connection_dialog.rtt2uart and 
                hasattr(self.connection_dialog.rtt2uart, 'jlink')):
                try:
                    self.connection_dialog.rtt2uart.jlink.set_log_file(log_file_path)
                    self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging enabled: %s") % log_file_path)
                    self._start_jlink_log_tailer(log_file_path)
                except Exception as e:
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to enable file logging: %s") % str(e))
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
            
            # 如果有活动连接，禁用文件日志
            if (hasattr(self.connection_dialog, 'rtt2uart') and 
                self.connection_dialog.rtt2uart and 
                hasattr(self.connection_dialog.rtt2uart, 'jlink')):
                try:
                    # 通过设置空字符串来禁用文件日志
                    self.connection_dialog.rtt2uart.jlink.set_log_file("")
                    self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging disabled"))
                    self._stop_jlink_log_tailer()
                except Exception as e:
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to disable file logging: %s") % str(e))
                    
        except Exception as e:
            self.append_jlink_log(QCoreApplication.translate("main_window", "Error disabling file logging: %s") % str(e))
    
    def append_jlink_log(self, message):
        """添加JLink日志消息"""
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
    
    def get_tab1_content(self, full_content=False):
        """获取TAB 1 (RTT Channel 1) 的当前内容
        
        Args:
            full_content (bool): 如果为True，返回完整内容；如果为False，返回截取的内容
        """
        try:
            # TAB 1对应索引2（索引0是ALL页面，索引1是RTT Channel 0，索引2是RTT Channel 1）
            tab_index = 2
            
            # 获取TAB 1的widget
            tab1_widget = self.ui.tem_switch.widget(tab_index)
            if not tab1_widget:
                return ""
            
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
                self.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Command sent')}: {command}")
                self.append_jlink_log(f"{QCoreApplication.translate('main_window', 'RTT Channel 1 Response')}:")
                
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
                    self.append_jlink_log(f"   {QCoreApplication.translate('main_window', 'Showing recent')} {valid_line_count} {QCoreApplication.translate('main_window', 'lines')} / {QCoreApplication.translate('main_window', 'Total')} {len(lines)} {QCoreApplication.translate('main_window', 'lines')}")
                else:
                    self.append_jlink_log(f"   {QCoreApplication.translate('main_window', 'Total')} {valid_line_count} {QCoreApplication.translate('main_window', 'lines')}")
                
                self.append_jlink_log("─" * 50)  # 分隔线
            else:
                # 如果没有内容，显示提示信息
                self.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Command sent')}: {command}")
                self.append_jlink_log(f"{QCoreApplication.translate('main_window', 'RTT Channel 1: No response data')}")
                self.append_jlink_log("─" * 50)  # 分隔线
                
        except Exception as e:
            logger.error(f"Failed to delayed display TAB 1 content: {e}")

    def eventFilter(self, obj, event):
        """事件过滤器：处理ComboBox的键盘事件"""
        if obj == self.ui.cmd_buffer and event.type() == event.Type.KeyPress:
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
            
            # 设置ComboBox显示历史命令
            self.ui.cmd_buffer.setCurrentIndex(self.command_history_index)
            # 选中文本，便于继续输入时替换
            line_edit = self.ui.cmd_buffer.lineEdit()
            if line_edit:
                line_edit.selectAll()
            
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
            
            if self.command_history_index < 0:
                # 回到当前输入
                self.command_history_index = -1
                self.ui.cmd_buffer.setCurrentText(self.current_input_text)
                logger.debug(f"Return to current input: {self.current_input_text}")
            else:
                # 设置ComboBox显示历史命令
                self.ui.cmd_buffer.setCurrentIndex(self.command_history_index)
                logger.debug(f"Navigate to history command [{self.command_history_index}]: {self.ui.cmd_buffer.currentText()}")
            
            # 选中文本，便于继续输入时替换
            line_edit = self.ui.cmd_buffer.lineEdit()
            if line_edit:
                line_edit.selectAll()
            
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
            self.jlink_log_tail_timer.start(500)  # 每500ms拉一次
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
        """程序关闭事件处理 - 确保所有资源被正确清理"""
        logger.info("Starting program shutdown process...")
        
        # 设置关闭标志，防止在关闭时显示连接对话框
        self._is_closing = True
        
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
            # 1. 🚨 强制刷新所有缓冲区到文件（确保数据不丢失）
            if self.connection_dialog and hasattr(self.connection_dialog, 'worker'):
                worker = self.connection_dialog.worker
                if hasattr(worker, 'force_flush_all_buffers'):
                    try:
                        logger.info("Force refreshing all TAB buffers...")
                        worker.force_flush_all_buffers()
                    except Exception as ex:
                        logger.error(f"Error force refreshing buffers: {ex}")
            
            # 2. 停止所有RTT连接并强制关闭JLink
            if self.connection_dialog:
                # 2.1 停止RTT连接
                if self.connection_dialog.rtt2uart is not None:
                    if self.connection_dialog.start_state == True:
                        logger.info("Stopping RTT connection...")
                        try:
                            # 正确调用stop方法而不是start方法
                            self.connection_dialog.rtt2uart.stop()
                            self.connection_dialog.start_state = False
                            
                            # 🔄 更新状态栏显示
                            self.update_status_bar()
                            
                            logger.info("RTT connection stopped")
                        except Exception as ex:
                            logger.error(f"Error stopping RTT connection: {ex}")
                
                # 2.2 🔑 强制关闭JLink连接（防止遗留进程）
                if hasattr(self.connection_dialog, 'jlink') and self.connection_dialog.jlink:
                    try:
                        logger.info("Force closing JLink connection...")
                        # 尝试关闭JLink
                        if self.connection_dialog.jlink.connected():
                            self.connection_dialog.jlink.close()
                            logger.info("JLink connection force closed")
                    except Exception as ex:
                        logger.warning(f"Error force closing JLink (may already closed): {ex}")
                        # 即使失败也尝试再次关闭
                        try:
                            self.connection_dialog.jlink.close()
                        except:
                            pass
            
            # 3. 停止所有定时器
            self._stop_all_timers()
            
            # 3. 强制终止所有工作线程
            self._force_terminate_threads()
            
            # 4. 清理UI资源
            self._cleanup_ui_resources()
            
            # 5. 清理日志目录
            self._cleanup_log_directories()
            
            # 6. 关闭连接对话框
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
            
            # 给线程一些时间自然结束
            time.sleep(0.5)
            
            # 检查并强制终止仍在运行的线程
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    if not is_dummy_thread(thread):
                        logger.warning(f"Force terminating thread: {thread.name}")
                        try:
                            # 尝试优雅地停止线程
                            thread.join(timeout=2.0)
                            if thread.is_alive():
                                logger.warning(f"Thread {thread.name} failed to stop gracefully, will be force terminated")
                                # 对于Python线程，我们无法直接杀死，但可以标记为daemon
                                thread.daemon = True
                        except Exception as e:
                            logger.error(f"Error terminating thread {thread.name}: {e}")
            
            logger.info("Thread cleanup completed")
        except Exception as e:
            logger.error(f"Error force terminating threads: {e}")
    
    def _cleanup_ui_resources(self):
        """清理UI资源"""
        try:
            # 清理文本编辑器内容
            for i in range(MAX_TAB_SIZE):
                current_page_widget = self.ui.tem_switch.widget(i)
                if isinstance(current_page_widget, QWidget):
                    text_edit = current_page_widget.findChild(QTextEdit)
                    if text_edit:
                        text_edit.clear()
            
            # 清理JLink日志
            if hasattr(self, 'jlink_log_text'):
                self.jlink_log_text.clear()
            
            logger.info("UI resource cleanup completed")
        except Exception as e:
            logger.error(f"Error cleaning UI resources: {e}")
    
    def _cleanup_log_directories(self):
        """清理日志目录"""
        try:
            if (self.connection_dialog and 
                self.connection_dialog.rtt2uart and 
                self.connection_dialog.rtt2uart.log_directory):
                
                log_directory = self.connection_dialog.rtt2uart.log_directory
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
        """强制退出应用程序"""
        try:
            # 获取应用程序实例
            app = QApplication.instance()
            if app:
                logger.info("Force quitting application...")
                # 设置退出代码并立即退出
                app.quit()
                # 如果quit()不起作用，使用更强制的方法
                QTimer.singleShot(1000, lambda: os._exit(0))
            
        except Exception as e:
            logger.error(f"Error force quitting application: {e}")
            # 最后的手段：直接退出进程
            os._exit(0)

    @Slot(int)
    def switchPage(self, index):
        self.connection_dialog.switchPage(index)
        
        # 更新当前标签页索引（用于串口转发）
        if self.connection_dialog and self.connection_dialog.rtt2uart:
            self.connection_dialog.rtt2uart.set_current_tab_index(index)
        
        # 🔧 刷新标签布局，让当前标签优先显示完整
        if hasattr(self.ui, 'tem_switch'):
            tab_bar = self.ui.tem_switch.tabBar()
            if tab_bar:
                # 强制重新计算所有标签的大小
                tab_bar.update()
                # 确保当前标签在可见区域（使用Qt内置方法）
                self.ui.tem_switch.setCurrentIndex(index)
        
        # 每次切换页面时都确保工具提示设置正确
        self._ensure_correct_tooltips()


    @Slot()
    def handleBufferUpdate(self):
        # 更新数据时间戳（用于自动重连监控）
        self._update_data_timestamp()
        
        # 获取当前选定的页面索引
        index = self.ui.tem_switch.currentIndex()
        # 刷新文本框
        self.switchPage(index)
        
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
        
        if self.connection_dialog:
            bytes_written = self.connection_dialog.jlink.rtt_write(0, out_bytes)
            self.connection_dialog.rtt2uart.write_bytes0 = bytes_written
        else:
            bytes_written = 0
            
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
            
            #self.ui.tem_switch.setCurrentIndex(2)   #输入指令成功后，自动切换到应答界面
            current_page_widget = self.ui.tem_switch.widget(2)
            if isinstance(current_page_widget, QWidget):
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page_widget.findChild(QPlainTextEdit) or current_page_widget.findChild(QTextEdit)
                if text_edit:
                    self.highlighter[2].setKeywords([current_text])
                    
            # 📋 新功能：命令发送成功后，将TAB 1的输出内容展示到JLink日志框
            self._display_tab1_content_to_jlink_log(current_text)
                    
            # 智能命令历史管理：防止重复，只调整顺序
            self._update_command_history(current_text)
            
            self.ui.cmd_buffer.clearEditText()
            self.ui.cmd_buffer.setCurrentText("")  # 确保输入框完全清空
        else:
            # 发送失败的处理
            logger.warning(f"Command send failed: expected {len(out_bytes)} bytes, actually sent {bytes_written} bytes")
            self.ui.sent.setText(QCoreApplication.translate("main_window", "Send Failed"))

    def on_dis_connect_clicked(self):
        """断开连接，不显示连接对话框"""
        # 标记为手动断开，禁用自动重连
        self.manual_disconnect = True
        self.data_check_timer.stop()
        
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            self.connection_dialog.start()  # 这会切换到断开状态
        # 如果已经断开，则无操作（但快捷键仍然响应）

    def on_re_connect_clicked(self):
        """重新连接：先断开现有连接，然后显示连接对话框"""
        # 重新连接时清除手动断开标记
        self.manual_disconnect = False
        
        # 如果当前有连接，先断开
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            self.connection_dialog.start()  # 这会切换到断开状态
            
        # 显示连接对话框供用户重新连接
        if self.connection_dialog and not self._is_closing:
            self.connection_dialog.show()
            self.connection_dialog.raise_()
            self.connection_dialog.activateWindow()
    
    def _on_auto_reconnect_changed(self, state):
        """自动重连复选框状态改变"""
        enabled = (state == Qt.CheckState.Checked.value) if hasattr(Qt.CheckState, 'Checked') else (state == 2)
        
        # 保存到配置
        if self.connection_dialog:
            self.connection_dialog.config.set_auto_reconnect_on_no_data(enabled)
            self.connection_dialog.config.save_config()
        
        # 如果启用且已连接，启动监控定时器
        if enabled and self.connection_dialog and self.connection_dialog.start_state:
            self.last_data_time = time.time()
            self.data_check_timer.start(5000)  # 每5秒检查一次
            logger.info("Auto reconnect on no data enabled")
        else:
            self.data_check_timer.stop()
            logger.info("Auto reconnect on no data disabled")
    
    def _on_reconnect_timeout_changed(self, text):
        """超时时间文本框改变"""
        try:
            timeout = int(text)
            if timeout > 0:
                # 保存到配置
                if self.connection_dialog:
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
        """检查数据超时"""
        # 如果手动断开，停止检查
        if self.manual_disconnect:
            self.data_check_timer.stop()
            return
        
        # 如果未连接，停止检查
        if not self.connection_dialog or not self.connection_dialog.start_state:
            return
        
        # 获取超时设置
        try:
            timeout = int(self.ui.reconnect_timeout_edit.text())
        except:
            timeout = 60
        
        # 检查是否超时
        current_time = time.time()
        time_since_last_data = current_time - self.last_data_time if self.last_data_time > 0 else 0
        
        # 调试日志
        logger.debug(f"[AUTO-RECONNECT] Timeout check: last_data_time={self.last_data_time:.2f}, current={current_time:.2f}, elapsed={time_since_last_data:.2f}s, timeout={timeout}s")
        
        if self.last_data_time > 0 and time_since_last_data > timeout:
            logger.warning(f"No data received for {timeout} seconds, auto reconnecting...")
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "No data timeout, automatically reconnecting..."))
            
            # 重置时间戳，避免重复触发
            self.last_data_time = time.time()
            
            # 执行自动重连
            self._perform_auto_reconnect()
    
    def _perform_auto_reconnect(self):
        """执行自动重连（不重置文件夹）"""
        try:
            if not self.connection_dialog or not self.connection_dialog.rtt2uart:
                logger.warning("Cannot auto reconnect: connection_dialog or rtt2uart not available")
                return
            
            # 使用rtt2uart的重启方法，不会重置日志文件夹
            rtt_obj = self.connection_dialog.rtt2uart
            
            # 停止RTT连接
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Stopping RTT connection..."))
            rtt_obj.stop(keep_folder=True)  # 保留日志文件夹
            
            # 等待停止完成后重新启动
            QTimer.singleShot(1000, self._auto_reconnect_start)
            
        except Exception as e:
            logger.error(f"Auto reconnect failed: {e}")
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect failed: %s") % str(e))
    
    def _auto_reconnect_start(self):
        """自动重连 - 启动连接"""
        try:
            if not self.connection_dialog or not self.connection_dialog.rtt2uart:
                logger.warning("Cannot start auto reconnect: connection_dialog or rtt2uart not available")
                return
            
            # 重新启动RTT连接
            rtt_obj = self.connection_dialog.rtt2uart
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Restarting RTT connection..."))
            
            rtt_obj.start()
            
            logger.info("Auto reconnect completed")
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect completed"))
                
        except Exception as e:
            logger.error(f"Auto reconnect start failed: {e}")
            if hasattr(self, 'append_jlink_log'):
                self.append_jlink_log(QCoreApplication.translate("main_window", "Auto reconnect start failed: %s") % str(e))
    
    def _update_data_timestamp(self):
        """更新数据时间戳（在收到数据时调用）"""
        current_time = time.time()
        # 只在第一次或超过5秒没更新时记录日志（避免日志刷屏）
        if self.last_data_time == 0 or (current_time - self.last_data_time) > 5:
            logger.debug(f"[AUTO-RECONNECT] Data timestamp updated: {self.last_data_time:.2f} -> {current_time:.2f}")
        self.last_data_time = current_time

    def on_clear_clicked(self):
        """F4清空当前TAB - 完整的清空逻辑"""
        try:
            current_index = self.ui.tem_switch.currentIndex()
            logger.debug(f"Clearing TAB {current_index}")
            
            # 1. 清空UI显示
            current_page_widget = self.ui.tem_switch.widget(current_index)
            if isinstance(current_page_widget, QWidget):
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page_widget.findChild(QPlainTextEdit) or current_page_widget.findChild(QTextEdit)
                if text_edit:
                    text_edit.clear()
                    logger.debug(f"Cleared TAB {current_index} UI display")
                else:
                    logger.warning(f"TAB {current_index} text editor not found")
                    return
            else:
                logger.warning(f"TAB {current_index} is not a valid Widget")
                return
            
            # 2. 清空数据缓冲区
            if self.connection_dialog and hasattr(self.connection_dialog, 'worker') and self.connection_dialog.worker:
                worker = self.connection_dialog.worker
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
                        
                    logger.debug(f"Cleared TAB {current_index} data buffer")
                    
                except Exception as e:
                    logger.error(f"Failed to clear TAB {current_index} data buffer: {e}")
            else:
                logger.warning("Cannot access Worker, only cleared UI display")
                
            # 3. 如果是Filters标签（17+），保存清空后的filter配置
            if current_index >= 17 and self.connection_dialog and hasattr(self.connection_dialog, 'config'):
                try:
                    self.connection_dialog.config.set_filter(current_index, "")
                    self.connection_dialog.config.save_config()
                    logger.debug(f"Saved empty filter for TAB {current_index}")
                except Exception as e:
                    logger.warning(f"Failed to save filter for TAB {current_index}: {e}")
            
            # 4. 标记页面为干净状态
            if hasattr(self, 'page_dirty_flags') and current_index < len(self.page_dirty_flags):
                self.page_dirty_flags[current_index] = False
                
            logger.info(f"TAB {current_index} clear completed")
            
        except Exception as e:
            logger.error(f"Failed to clear TAB: {e}")
            # 兜底：只清空UI
            try:
                current_page_widget = self.ui.tem_switch.widget(self.ui.tem_switch.currentIndex())
                if isinstance(current_page_widget, QWidget):
                    from PySide6.QtWidgets import QPlainTextEdit
                    text_edit = current_page_widget.findChild(QPlainTextEdit) or current_page_widget.findChild(QTextEdit)
                    if text_edit:
                        text_edit.clear()
                        logger.warning("Fallback mode: only cleared UI display")
            except Exception as fallback_e:
                logger.error(f"Fallback clear also failed: {fallback_e}")

    def on_openfolder_clicked(self):
        """打开日志文件夹 - 复用同一个窗口跳转到新文件夹"""
        try:
            import pathlib
            import subprocess
            
            # 确定要打开的目录
            if self.connection_dialog and self.connection_dialog.rtt2uart:
                target_dir = self.connection_dialog.rtt2uart.log_directory
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
                if not hasattr(self, '_explorer_window_opened'):
                    self._explorer_window_opened = False
                
                if self._explorer_window_opened:
                    # 已经打开过窗口，尝试用COM接口导航到新位置
                    try:
                        import win32com.client
                        shell = win32com.client.Dispatch("Shell.Application")
                        
                        # 遍历所有打开的资源管理器窗口
                        windows = shell.Windows()
                        navigated = False
                        
                        for window in windows:
                            try:
                                # 检查是否是资源管理器窗口
                                if hasattr(window, 'Document') and window.Document:
                                    # 导航到新文件夹
                                    window.Navigate(target_dir)
                                    # 激活窗口
                                    window.Document.Application.Visible = True
                                    navigated = True
                                    logger.info(f"Reused existing window, navigated to: {target_dir}")
                                    return
                            except:
                                continue
                        
                        if not navigated:
                            # 如果没找到可用窗口（可能被关闭了），重新打开
                            logger.info("No existing window found, opening new one")
                            os.startfile(target_dir)
                            self._explorer_window_opened = True
                            
                    except ImportError:
                        # 如果没有 win32com，回退到普通方式
                        logger.warning("win32com not available, using fallback method")
                        os.startfile(target_dir)
                        self._explorer_window_opened = True
                    except Exception as e:
                        logger.warning(f"Failed to reuse window: {e}, opening new one")
                        os.startfile(target_dir)
                        self._explorer_window_opened = True
                else:
                    # 第一次打开
                    os.startfile(target_dir)
                    self._explorer_window_opened = True
                    logger.info(f"Opened new folder window: {target_dir}")
            
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
            max_items = 100
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
            # 同步保存到INI配置
            self.connection_dialog.config.set_light_mode(self.ui.light_checkbox.isChecked())
            self.connection_dialog.config.save_config()
        
        # 更新JLink日志区域的样式
        self._update_jlink_log_style()
    
    def _init_font_combo(self):
        """初始化字体选择下拉框，列出所有系统等宽字体"""
        from PySide6.QtGui import QFontDatabase
        
        # 获取系统所有字体
        font_db = QFontDatabase()
        all_fonts = sorted(font_db.families())
        
        # 常见等宽字体关键词（用于优先排序）
        monospace_keywords = [
            'mono', 'code', 'console', 'courier', 'terminal', 'fixed',
            'sarasa', '等距', 'cascadia', 'consolas', 'menlo', 'monaco',
            'dejavu', 'ubuntu', 'liberation', 'jetbrains', 'fira', 'source code'
        ]
        
        # 分类字体：可能的等宽字体 vs 其他字体
        likely_monospace = []
        other_fonts = []
        
        for font_name in all_fonts:
            # 检查是否包含等宽关键词
            font_lower = font_name.lower()
            if any(keyword in font_lower for keyword in monospace_keywords):
                likely_monospace.append(font_name)
            else:
                # 使用QFontDatabase检查是否为固定宽度字体
                if font_db.isFixedPitch(font_name):
                    likely_monospace.append(font_name)
                else:
                    other_fonts.append(font_name)
        
        # 合并列表：优先显示等宽字体
        available_fonts = likely_monospace + other_fonts
        
        # 如果没有找到任何字体，使用系统默认
        if not available_fonts:
            import sys
            default_font = "Consolas" if sys.platform == "win32" else "Monaco"
            available_fonts = [default_font]
            logger.warning(f"[FONT] No fonts found, using default: {default_font}")
        
        # 填充字体下拉框，并为每个项设置对应的字体样式
        self.ui.font_combo.clear()
        for font_name in available_fonts:
            self.ui.font_combo.addItem(font_name)
            # 🔑 关键：为该项设置对应的字体，让用户直观看到字体效果
            item_index = self.ui.font_combo.count() - 1
            font = QFont(font_name, 10)  # 使用固定大小10pt用于显示
            self.ui.font_combo.setItemData(item_index, font, Qt.FontRole)
        
        logger.info(f"[FONT] Loaded {len(available_fonts)} fonts ({len(likely_monospace)} monospace)")
        
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
                    index = self.ui.font_combo.findText(default_font, Qt.MatchFixedString)
                    if index >= 0:
                        selected_font = default_font
                        self.ui.font_combo.setCurrentIndex(index)
                        logger.info(f"[FONT] Using default font: {default_font}")
                        break
                
                # 如果所有默认字体都不存在，使用第一个字体
                if not selected_font and available_fonts:
                    self.ui.font_combo.setCurrentIndex(0)
                    logger.info(f"[FONT] No default font found, using: {available_fonts[0]}")
    
    def on_font_changed(self, font_name):
        """字体变更时的处理 - 全局生效"""
        if self.connection_dialog and font_name:
            # 保存到配置
            self.connection_dialog.config.set_fontfamily(font_name)
            self.connection_dialog.config.save_config()
            logger.info(f"[FONT] Font changed to: {font_name} - applying to all TABs")
            # 🔑 全局更新：遍历所有TAB并更新字体
            self._update_all_tabs_font()
    
    def _update_all_tabs_font(self):
        """全局更新所有TAB的字体"""
        try:
            # 获取字体设置
            if hasattr(self.ui, 'font_combo'):
                font_name = self.ui.font_combo.currentText()
            else:
                font_name = "Consolas"
            
            font_size = self.ui.fontsize_box.value()
            
            # 创建字体对象
            font = QFont(font_name, font_size)
            font.setFixedPitch(True)
            font.setStyleHint(QFont.Monospace)  # 🔑 设置字体提示为等宽
            font.setKerning(False)  # 🔑 禁用字距调整
            
            # 遍历所有TAB并更新字体
            from PySide6.QtWidgets import QPlainTextEdit
            tab_count = self.ui.tem_switch.count()
            updated_count = 0
            
            for i in range(tab_count):
                page = self.ui.tem_switch.widget(i)
                if page:
                    text_edit = page.findChild(QPlainTextEdit) or page.findChild(QTextEdit)
                    if text_edit:
                        # 设置字体
                        text_edit.setFont(font)
                        
                        # 🔑 关键：强制刷新文本显示
                        # 方法1：触发文档重新布局
                        text_edit.document().setDefaultFont(font)
                        
                        # 方法2：强制重绘
                        text_edit.update()
                        text_edit.viewport().update()
                        
                        updated_count += 1
            
            logger.info(f"[FONT] Updated font for {updated_count}/{tab_count} TABs to: {font_name} {font_size}pt")
        except Exception as e:
            logger.warning(f"Failed to update all tabs font: {e}")
    
    def _update_current_tab_font(self):
        """更新当前TAB的字体"""
        try:
            current_index = self.ui.tem_switch.currentIndex()
            current_page = self.ui.tem_switch.widget(current_index)
            if current_page:
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page.findChild(QPlainTextEdit) or current_page.findChild(QTextEdit)
                if text_edit:
                    # 获取字体名称
                    if hasattr(self.ui, 'font_combo'):
                        font_name = self.ui.font_combo.currentText()
                    else:
                        font_name = "Consolas"
                    
                    font_size = self.ui.fontsize_box.value()
                    font = QFont(font_name, font_size)
                    font.setFixedPitch(True)
                    font.setStyleHint(QFont.Monospace)  # 🔑 设置字体提示为等宽
                    font.setKerning(False)  # 🔑 禁用字距调整
                    text_edit.setFont(font)
        except Exception as e:
            logger.warning(f"Failed to update current tab font: {e}")
    
    def on_fontsize_changed(self):
        """字体大小变更时的处理 - 全局生效"""
        if self.connection_dialog:
            self.connection_dialog.settings['fontsize'] = self.ui.fontsize_box.value()
            # 同步保存到INI配置
            self.connection_dialog.config.set_fontsize(self.ui.fontsize_box.value())
            self.connection_dialog.config.save_config()
            logger.info(f"[FONT] Font size changed to: {self.ui.fontsize_box.value()}pt - applying to all TABs")
        # 🔑 全局更新：遍历所有TAB并更新字体大小
        self._update_all_tabs_font()
    
    def on_lock_h_changed(self):
        """水平滚动条锁定状态改变时保存配置"""
        if self.connection_dialog:
            # 🔧 BUG修复：同时更新settings字典和配置文件
            self.connection_dialog.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
            self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
            self.connection_dialog.config.save_config()
            print(f"[SAVE] Horizontal scrollbar lock state saved: {self.ui.LockH_checkBox.isChecked()}")
    
    def on_lock_v_changed(self):
        """垂直滚动条锁定状态改变时保存配置"""
        if self.connection_dialog:
            # 🔧 BUG修复：同时更新settings字典和配置文件
            self.connection_dialog.settings['lock_v'] = self.ui.LockV_checkBox.isChecked()
            self.connection_dialog.config.set_lock_vertical(self.ui.LockV_checkBox.isChecked())
            self.connection_dialog.config.save_config()
            print(f"[SAVE] Vertical scrollbar lock state saved: {self.ui.LockV_checkBox.isChecked()}")
    
    
    def _update_jlink_log_style(self):
        """更新JLink日志区域的样式以匹配当前主题"""
        if not hasattr(self, 'jlink_log_text'):
            return
            
        is_light_mode = self.ui.light_checkbox.isChecked()
        
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
    
    def _update_ui_translations(self):
        """更新UI元素的翻译文本"""
        # 更新窗口标题
        self.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT - RTT Debug Main Window"))
        
        # 更新菜单项
        if hasattr(self, 'connection_menu'):
            self.connection_menu.setTitle(QCoreApplication.translate("main_window", "Connection(&C)"))
        if hasattr(self, 'window_menu'):
            self.window_menu.setTitle(QCoreApplication.translate("main_window", "Window(&W)"))
        if hasattr(self, 'tools_menu'):
            self.tools_menu.setTitle(QCoreApplication.translate("main_window", "Tools(&T)"))
        if hasattr(self, 'help_menu'):
            self.help_menu.setTitle(QCoreApplication.translate("main_window", "Help(&H)"))
        
        # 更新菜单动作
        if hasattr(self, 'reconnect_action'):
            self.reconnect_action.setText(QCoreApplication.translate("main_window", "Reconnect(&R)"))
        if hasattr(self, 'disconnect_action'):
            self.disconnect_action.setText(QCoreApplication.translate("main_window", "Disconnect(&D)"))
        if hasattr(self, 'connection_settings_action'):
            self.connection_settings_action.setText(QCoreApplication.translate("main_window", "Connection Settings(&S)..."))
        if hasattr(self, 'new_window_action'):
            self.new_window_action.setText(QCoreApplication.translate("main_window", "New Window(&N)"))
        if hasattr(self, 'compact_mode_action'):
            self.compact_mode_action.setText(QCoreApplication.translate("main_window", "Compact Mode(&M)"))
        if hasattr(self, 'clear_current_page_action'):
            self.clear_current_page_action.setText(QCoreApplication.translate("main_window", "Clear Current Page(&C)"))
        if hasattr(self, 'open_log_folder_action'):
            self.open_log_folder_action.setText(QCoreApplication.translate("main_window", "Open Log Folder(&O)"))
        if hasattr(self, 'open_config_folder_action'):
            self.open_config_folder_action.setText(QCoreApplication.translate("main_window", "Open Config Folder(&F)"))
        if hasattr(self, 'encoding_menu'):
            self.encoding_menu.setTitle(QCoreApplication.translate("main_window", "Encoding(&E)"))
        if hasattr(self, 'restart_app_action'):
            self.restart_app_action.setText(QCoreApplication.translate("main_window", "Restart APP F9(&A)"))
        if hasattr(self, 'theme_menu'):
            self.theme_menu.setTitle(QCoreApplication.translate("main_window", "Switch Theme(&T)"))
        if hasattr(self, 'about_action'):
            self.about_action.setText(QCoreApplication.translate("main_window", "About(&A)..."))
        
        # 更新状态栏
        if hasattr(self, 'connection_status_label'):
            current_text = self.connection_status_label.text()
            if "Connected" in current_text or QCoreApplication.translate("main_window", "Connected") in current_text:
                # 尝试从当前文本中提取设备信息
                match = re.search(r'(USB_\d+(_\w+)?)$', current_text)
                device_info = match.group(1) if match else ""
                if device_info:
                    self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected: %s") % device_info)
                else:
                    self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected"))
            else:
                self.connection_status_label.setText(QCoreApplication.translate("main_window", "Disconnected"))
        
        # 更新JLink日志区域的文本
        if hasattr(self, 'jlink_log_widget'):
            title_label = self.jlink_log_widget.findChild(QLabel)
            if title_label:
                title_label.setText(QCoreApplication.translate("main_window", "JLink Debug Log"))
            
            if hasattr(self, 'clear_jlink_log_btn'):
                self.clear_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Clear Log"))
            
            if hasattr(self, 'toggle_jlink_log_btn'):
                if self.toggle_jlink_log_btn.isChecked():
                    self.toggle_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Disable Verbose Log"))
                else:
                    self.toggle_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Enable Verbose Log"))
        
    def on_cmd_buffer_activated(self, index):
        text = self.ui.cmd_buffer.currentText()
        if text:  # 如果文本不为空
            self.ui.pushButton.click()  # 触发 QPushButton 的点击事件

    def update_status_bar(self):
        """更新状态栏信息"""
        if not hasattr(self, 'status_bar'):
            return
            
        # 更新连接状态
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            # 显示设备连接信息：USB_X_SN格式
            device_info = getattr(self.connection_dialog.rtt2uart, 'device_info', 'Unknown')
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "Connected: %s") % device_info)
        else:
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "Disconnected"))
        
        # 更新数据统计
        readed = 0
        writed = 0
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None:
            readed = self.connection_dialog.rtt2uart.read_bytes0 + self.connection_dialog.rtt2uart.read_bytes1
            writed = self.connection_dialog.rtt2uart.write_bytes0
        
        self.data_stats_label.setText(
            QCoreApplication.translate("main_window", "Read: {} | Write: {}").format(readed, writed)
        )
    
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
        
        # 确保工具提示设置正确 - 只有filter标签页才有工具提示
        self._ensure_correct_tooltips()
    
    def _ensure_correct_tooltips(self):
        """确保工具提示设置正确 - 只有filter标签页才显示工具提示"""
        try:
            # 清除TabWidget本身的工具提示
            self.ui.tem_switch.setToolTip("")
            
            # 清除所有页面和文本编辑器的工具提示
            for i in range(MAX_TAB_SIZE):
                page_widget = self.ui.tem_switch.widget(i)
                if page_widget:
                    page_widget.setToolTip("")
                    # 查找页面中的文本编辑器并清除其工具提示
                    from PySide6.QtWidgets import QPlainTextEdit
                    text_edit = page_widget.findChild(QPlainTextEdit) or page_widget.findChild(QTextEdit)
                    if text_edit:
                        text_edit.setToolTip("")
                
                # 清除所有标签页的工具提示
                self.ui.tem_switch.setTabToolTip(i, "")
            
            # 只为filter标签页（索引>=17）设置工具提示
            for i in range(17, MAX_TAB_SIZE):
                self.ui.tem_switch.setTabToolTip(i, QCoreApplication.translate("main_window", "double click filter to write filter text"))
                
        except Exception:
            pass  # 忽略任何错误，避免影响正常功能


    def toggle_lock_h_checkbox(self):
        self.ui.LockH_checkBox.setChecked(not self.ui.LockH_checkBox.isChecked())
        if self.connection_dialog:
            self.connection_dialog.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
            # 同步保存到INI配置
            self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
            self.connection_dialog.config.save_config()
    
    def toggle_lock_v_checkbox(self):
        self.ui.LockV_checkBox.setChecked(not self.ui.LockV_checkBox.isChecked())
        if self.connection_dialog:
            self.connection_dialog.settings['lock_v'] = self.ui.LockV_checkBox.isChecked()
            # 同步保存到INI配置
            self.connection_dialog.config.set_lock_vertical(self.ui.LockV_checkBox.isChecked())
            self.connection_dialog.config.save_config()
    def toggle_style_checkbox(self):
        self.ui.light_checkbox.setChecked(not self.ui.light_checkbox.isChecked())
        self.set_style()
        
    def device_restart(self):
        # 与 F9 行为保持一致：根据子菜单选择执行重启
        self.restart_app_execute()

    def restart_app_via_sfr(self):
        """通过SFR访问触发固件重启（需保持连接）"""
        try:
            if not (self.connection_dialog and self.connection_dialog.rtt2uart and self.connection_dialog.start_state):
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please connect first, then restart app"))
                return
            jlink = self.connection_dialog.rtt2uart.jlink
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
            if not (self.connection_dialog and self.connection_dialog.rtt2uart and self.connection_dialog.start_state):
                QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Please connect first, then restart app"))
                return
            jlink = self.connection_dialog.rtt2uart.jlink
            try:
                jlink.reset(halt=False)
                self.append_jlink_log(QCoreApplication.translate("main_window", "Restart via reset pin executed"))
            except Exception as e:
                QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), QCoreApplication.translate("main_window", "Reset pin restart failed: %s") % str(e))
        except Exception as e:
            QMessageBox.warning(self, QCoreApplication.translate("main_window", "Failed"), str(e))

    def restart_app_execute(self):
        """F9 执行，根据子菜单当前选择的方式触发重启"""
        try:
            # 若未连接，则先自动连接，待连接成功后再执行
            if not (self.connection_dialog and self.connection_dialog.start_state):
                if self.connection_dialog:
                    # 连接成功后回调一次，再断开信号
                    def _once():
                        try:
                            self.connection_dialog.connection_established.disconnect(_once)
                        except Exception:
                            pass
                        # 确保在事件循环返回后执行，避免与连接建立时序冲突
                        QTimer.singleShot(0, self.restart_app_execute)
                    try:
                        self.connection_dialog.connection_established.connect(_once)
                    except Exception:
                        pass
                    # 静默启动连接
                    self.connection_dialog.start()
                    return
                else:
                    QMessageBox.information(self, QCoreApplication.translate("main_window", "Info"), QCoreApplication.translate("main_window", "Unable to create connection dialog"))
                    return

            # 已连接：按选择执行
            selected_sfr = hasattr(self, 'action_restart_sfr') and self.action_restart_sfr.isChecked()
            # 保存选择到配置
            try:
                if self.connection_dialog:
                    self.connection_dialog.config.set_restart_method('SFR' if selected_sfr else 'RESET_PIN')
                    self.connection_dialog.config.save_config()
            except Exception:
                pass
            if selected_sfr:
                self.restart_app_via_sfr()
            else:
                self.restart_app_via_reset_pin()
        except Exception:
            pass

    def show_find_dialog(self):
        """Show find dialog"""
        try:
            # Get current active TAB
            current_index = self.ui.tem_switch.currentIndex()
            current_page_widget = self.ui.tem_switch.widget(current_index)
            
            if not current_page_widget:
                return
                
            # Find text editor
            from PySide6.QtWidgets import QPlainTextEdit
            text_edit = current_page_widget.findChild(QPlainTextEdit)
            if not text_edit:
                text_edit = current_page_widget.findChild(QTextEdit)
            
            if not text_edit:
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
            logger.error(f"Failed to show find dialog: {e}")


                                    
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
        self.highlight_all_btn = QPushButton(QCoreApplication.translate("FindDialog", "Highlight All"))
        self.clear_highlight_btn = QPushButton(QCoreApplication.translate("FindDialog", "Clear Highlight"))
        self.close_btn = QPushButton(QCoreApplication.translate("FindDialog", "Close"))
        
        button_layout.addWidget(self.find_next_btn)
        button_layout.addWidget(self.find_prev_btn)
        button_layout.addWidget(self.find_all_btn)
        button_layout.addWidget(self.highlight_all_btn)
        button_layout.addWidget(self.clear_highlight_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        layout.addLayout(button_layout)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.search_input.lineEdit().textChanged.connect(self.on_search_text_changed)
        self.search_input.lineEdit().returnPressed.connect(self.find_next)
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_all_btn.clicked.connect(self.find_all)
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
            print(f"Failed to load search history: {e}")
    
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
            print(f"Failed to save search history: {e}")
        
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
            return False
            
        search_text = self.search_input.currentText()
        
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
        
        # If new search text, start from beginning/end
        if search_text != self.last_search_text:
            if forward:
                cursor.movePosition(cursor.MoveOperation.Start)
            else:
                cursor.movePosition(cursor.MoveOperation.End)
            self.last_search_text = search_text
            
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
        
        if not found_cursor.isNull():
            # Found, select and scroll to position
            self.text_edit.setTextCursor(found_cursor)
            self.text_edit.ensureCursorVisible()
            return True
        else:
            # Not found, search from the other end
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
            
            if not found_cursor.isNull():
                self.text_edit.setTextCursor(found_cursor)
                self.text_edit.ensureCursorVisible()
                return True
                
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
            return
            
        search_text = self.search_input.currentText()
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
                
            # Create selection area
            from PySide6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = highlight_format
            extra_selections.append(selection)
            
        # Apply highlights
        self.text_edit.setExtraSelections(extra_selections)
        self.highlights = extra_selections
        
    def clear_highlights(self):
        """清除所有高亮"""
        if self.text_edit:
            self.text_edit.setExtraSelections([])
        self.highlights = []
        
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
        self.resize(700, 500)
        
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
        self.ui = Ui_ConnectionDialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
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
        
        # 尝试从旧的pickle文件迁移配置
        old_settings_file = os.path.join(os.getcwd(), "settings")
        if os.path.exists(old_settings_file):
            if self.config.migrate_from_pickle(old_settings_file):
                # 迁移成功后删除旧文件
                try:
                    os.remove(old_settings_file)
                    print("旧配置文件已删除")
                except:
                    pass

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

        self.port_scan()

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

        try:
            self.jlink = pylink.JLink()
        except:
            logger.error('Find jlink dll failed', exc_info=True)
            raise Exception(QCoreApplication.translate("main_window", "Find jlink dll failed !"))
        
        # 初始化JLINK设备选择相关属性
        self.available_jlinks = []
        self.selected_jlink_serial = None
        
        # 检测可用的JLINK设备
        self._detect_jlink_devices()

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
            if hasattr(self, 'worker') and hasattr(self.worker, 'force_flush_all_buffers'):
                try:
                    logger.info("ConnectionDialog closed, force refreshing all TAB buffers...")
                    self.worker.force_flush_all_buffers()
                except Exception as ex:
                    logger.error(f"Error force flushing ConnectionDialog buffers: {ex}")
            
            # 停止RTT连接
            if self.rtt2uart is not None and self.start_state == True:
                try:
                    self.rtt2uart.stop()
                except Exception as ex:
                    logger.error(f"Error stopping RTT: {ex}")
            
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
        
        # 初始化设备列表
        self._initialize_device_combo()
        
        # 如果没有保存的设置，使用合理的默认值
        if not device_list:
            self.ui.comboBox_Interface.setCurrentIndex(1)  # SWD
            self.ui.comboBox_Speed.setCurrentIndex(19)     # 合适的速度
            self.ui.comboBox_baudrate.setCurrentIndex(16)  # 115200
            
            # 保存默认设置
            self.config.set_interface(1)
            self.config.set_speed(4000)
            self.config.set_baudrate(115200)
    
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
            print(f"应用配置到UI时出错: {e}")
    
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
            
            if hasattr(self.main_window.ui, 'LockH_checkBox'):
                self.config.set_lock_horizontal(self.main_window.ui.LockH_checkBox.isChecked())
            
            if hasattr(self.main_window.ui, 'LockV_checkBox'):
                self.config.set_lock_vertical(self.main_window.ui.LockV_checkBox.isChecked())
            
            # 保存过滤器设置
            if hasattr(self.main_window.ui, 'tem_switch'):
                for i in range(17, min(33, self.main_window.ui.tem_switch.count())):
                    tab_text = self.main_window.ui.tem_switch.tabText(i)
                    if tab_text != QCoreApplication.translate("main_window", "filter"):
                        self.config.set_filter(i, tab_text)
            
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
        # 如果TAB还没准备好，添加一个占位项，稍后会被更新
        tab_ready = False
        if (self.main_window and hasattr(self.main_window, 'ui') and 
            hasattr(self.main_window.ui, 'tem_switch')):
            tab_count = self.main_window.ui.tem_switch.count()
            tab_ready = (tab_count >= MAX_TAB_SIZE)
            if not tab_ready:
                print(f"[DEBUG] TAB not ready yet, count={tab_count}, expected={MAX_TAB_SIZE}")
            
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
            
            # 只有当TAB准备好时才添加TAB列表
            if tab_ready and self.main_window and hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'tem_switch'):
                for i in range(MAX_TAB_SIZE):
                    tab_text = self.main_window.ui.tem_switch.tabText(i)

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
                        if tab_text == "filter" or tab_text == filter_translated:
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
                print(f"[DEBUG] Device selection info:")
                print(f"   ComboBox索引: {combo_index}")
                print(f"   ComboBox文本: {combo_text}")
                print(f"   连接参数: {connect_para}")
                print(f"   计算的设备索引: {device_index}")
                print(f"   可用设备数量: {len(self.available_jlinks)}")
                if self.available_jlinks:
                    for i, dev in enumerate(self.available_jlinks):
                        marker = "=>" if i == device_index else "  "
                        print(f"   {marker} #{i}: {dev['serial']} ({dev['product_name']})")
                
                # 🚨 重大BUG修复：清空Worker缓存，防止历史数据写入新文件夹
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Cleaning Worker cache to ensure new connection uses clean data..."))
                
                self._clear_all_worker_caches()
                
                self.rtt2uart = rtt_to_serial(self.worker, self.jlink, self.connect_type, connect_para, self.target_device, self.get_selected_port_name(
                ), self.ui.comboBox_baudrate.currentText(), device_interface, speed_list[self.ui.comboBox_Speed.currentIndex()], False, log_split_enabled, self.main_window.window_id, device_index)  # 重置后不再需要在rtt2uart中重置

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
                    print(f"[DEVICE] Connection confirmed: {device_info}")
                    print(f"   目标设备: {self.target_device}")
                    print(f"   连接类型: {self.connect_type}")

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
                GENERIC_READ = 0x80000000
                GENERIC_WRITE = 0x40000000
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
        print("[INFO] Keep old window data display, only clear file write buffer")
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
                print(f"[CLEAN] Cleared {cleared_count} log file buffers")
            
            
            # 2. BUG1修复：清空字节缓冲区和批量缓冲区，防止残余数据
            for i in range(MAX_TAB_SIZE):
                # 字节缓冲区 - 强制清除，防止残余数据
                if hasattr(worker, 'byte_buffer') and i < len(worker.byte_buffer):
                    if len(worker.byte_buffer[i]) > 0:
                        print(f"[WARNING] Clear channel {i} byte buffer residual data: {len(worker.byte_buffer[i])} bytes")
                    worker.byte_buffer[i].clear()
                
                # 批量缓冲区
                if hasattr(worker, 'batch_buffers') and i < len(worker.batch_buffers):
                    if len(worker.batch_buffers[i]) > 0:
                        print(f"[WARNING] Clear channel {i} batch buffer residual data: {len(worker.batch_buffers[i])} items")
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
            print(f"🎉 {log_msg}")
            
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(log_msg)
                
        except Exception as e:
            print(f"[ERROR] Error clearing Worker cache: {e}")
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"{QCoreApplication.translate('main_window', 'Error clearing Worker cache')}: {e}")

    def _get_current_device_index(self, connect_para):
        """获取当前连接参数对应的设备索引 - 直接使用ComboBox索引"""
        try:
            # 🔧 关键修复：直接使用ComboBox的当前选择索引，忽略空项
            current_combo_index = self.ui.comboBox_serialno.currentIndex()
            
            # 如果选择的是空项（索引0），跳过
            if current_combo_index <= 0:
                print("[WARNING] Empty item or invalid index selected, using default value 0")
                return 0
            
            # ComboBox索引需要减1，因为索引0是空项
            actual_device_index = current_combo_index - 1
            
            # 验证设备索引有效性
            if 0 <= actual_device_index < len(self.available_jlinks):
                selected_device = self.available_jlinks[actual_device_index]
                
                print(f"[SELECT] ComboBox selection: Index {current_combo_index} -> Device index {actual_device_index}")
                print(f"   Device: {selected_device['serial']} ({selected_device['product_name']})")
                print(f"   Connect param: {connect_para}")
                
                # 验证序列号是否匹配
                if selected_device['serial'] == connect_para:
                    print(f"[OK] Serial number matched, using device index: {actual_device_index} (USB_{actual_device_index})")
                    return actual_device_index
                else:
                    print(f"[WARNING] Serial number mismatch: Expected {connect_para}, Got {selected_device['serial']}")
                    print(f"   Still using ComboBox selected index: {actual_device_index}")
                    return actual_device_index
            else:
                print(f"[WARNING] Invalid device index: {actual_device_index}, Device count: {len(self.available_jlinks)}")
                
        except Exception as e:
            print(f"[ERROR] Failed to get device index: {e}")
        
        # 如果出现问题，返回0作为默认值
        print("[WARNING] Using default index: 0")
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
                                device_info = {
                                    'serial': str(serial_num),
                                    'product_name': getattr(device, 'acProduct', 'J-Link'),
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
        dialog.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        dialog.setModal(True)
        dialog.resize(500, 350)
        
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
        try:
            # 检查ComboBox是否存在
            if not hasattr(self.ui, 'comboBox_serialno'):
                logger.warning("ComboBox未找到，跳过设备列表刷新")
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
                        print(f"[ADD] Add device to ComboBox: Index {device_index} -> {display_text}")
                    else:
                        display_text = f"#{device_index} {QCoreApplication.translate('main_window', 'Auto Detect')}"
                        self.ui.comboBox_serialno.addItem(display_text, "")
                        print(f"[ADD] Add device to ComboBox: Index {device_index} -> {display_text}")
                
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
                
                logger.info(f"Refreshed device list: {len(self.available_jlinks)} devices found")
                
            except Exception as e:
                logger.error(f"Error adding devices to ComboBox: {e}")
            
        except Exception as e:
            logger.error(f"Error refreshing device list: {e}")

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
                
                if current_blocks > 1000:  # 只在行数较多时才清理
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
        # 获取当前选定的页面索引并显示相应的缓冲区数据
        from PySide6.QtGui import QTextCursor
        
        # 断开连接后仍可显示缓存数据，但不清空缓存
        is_connected = hasattr(self, 'start_state') and self.start_state
            
        if len(self.worker.buffers[index]) <= 0:
            return
        
        if not self.main_window:
            return
            
        current_page_widget = self.main_window.ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            # 优先使用QPlainTextEdit（高性能），回退到QTextEdit
            from PySide6.QtWidgets import QPlainTextEdit
            text_edit = current_page_widget.findChild(QPlainTextEdit)
            if not text_edit:
                text_edit = current_page_widget.findChild(QTextEdit)
            
            # 使用等宽字体（优先使用配置的字体）
            font_name = None
            if hasattr(self.main_window.ui, 'font_combo'):
                font_name = self.main_window.ui.font_combo.currentText()
            
            if not font_name:
                # 如果没有font_combo，从配置加载
                if hasattr(self, 'config'):
                    font_name = self.config.get_fontfamily()
                else:
                    # 默认字体
                    font_name = "SF Mono" if sys.platform == "darwin" else "Consolas"
            
            font_size = self.main_window.ui.fontsize_box.value()
            font = QFont(font_name, font_size)
            font.setFixedPitch(True)
            font.setStyleHint(QFont.Monospace)  # 🔑 关键：设置字体提示为等宽
            font.setKerning(False)  # 🔑 关键：禁用字距调整，确保严格等宽
            
            if text_edit:
                text_edit.setFont(font)
                # 记录滚动条位置
                vscroll = text_edit.verticalScrollBar().value()
                hscroll = text_edit.horizontalScrollBar().value()

                # 更新文本并恢复滚动条位置
                cursor = text_edit.textCursor()
                cursor.movePosition(QTextCursor.End)
                text_edit.setTextCursor(cursor)
                text_edit.setCursorWidth(0)
                
                if index >= 17:
                    self.main_window.highlighter[index].setKeywords([self.main_window.ui.tem_switch.tabText(index)])
                    if self.main_window.tabText[index] != self.main_window.ui.tem_switch.tabText(index):
                        self.main_window.tabText[index] = self.main_window.ui.tem_switch.tabText(index)
                        # 不再自动清空筛选页面，保留历史数据
                elif index != 2:
                    keywords = []
                    for i in range(MAX_TAB_SIZE):
                        if i >= 17:
                            keywords.append(self.main_window.ui.tem_switch.tabText(i))
                    self.main_window.highlighter[index].setKeywords(keywords)
                    
                # 🎨 智能ANSI颜色支持 + 高性能文本处理
                try:
                    # 🎯 动态调整插入长度：根据缓冲区容量利用率智能限制
                    if hasattr(self.worker, 'get_buffer_memory_usage'):
                        memory_info = self.worker.get_buffer_memory_usage()
                        utilization = memory_info.get('capacity_utilization', 0)
                        
                        # 根据容量利用率调整插入长度
                        if utilization > 80:  # 高利用率
                            max_insert_length = 2048   # 2KB（更保守，降低每次插入量）
                        elif utilization > 60:  # 中等利用率
                            max_insert_length = 4096   # 4KB
                        else:  # 低利用率
                            max_insert_length = 8192   # 8KB
                    else:
                        max_insert_length = 8192  # 默认更保守
                    
                    # 检查是否有ANSI彩色数据
                    has_colored_data = (hasattr(self.worker, 'colored_buffers') and 
                                      len(self.worker.colored_buffers[index]) > 0)
                    
                    if self.worker.enable_color_buffers and has_colored_data and len(self.worker.colored_buffers[index]) > 0:
                        # 🎨 修复：TAB切换时重新渲染颜色 - 无论QPlainTextEdit还是QTextEdit都使用ANSI彩色处理
                        from PySide6.QtWidgets import QPlainTextEdit
                        
                        # 🔧 修复TAB切换重复数据问题：严格控制完全重新渲染条件
                        # 只有在真正需要时才进行完全重新渲染，避免旧数据重新出现
                        current_text_length = len(text_edit.toPlainText()) if hasattr(text_edit, 'toPlainText') else 0
                        has_display_data = hasattr(self.worker, 'display_lengths') and self.worker.display_lengths[index] > 0
                        
                        # 🔧 关键修复：严格限制完全重新渲染的条件
                        # 只有在文本编辑器完全为空且从未显示过任何数据时才完全重新渲染
                        needs_full_render = (current_text_length == 0 and  # 文本编辑器为空
                                           not has_display_data and  # 且从未显示过数据
                                           len(self.worker.colored_buffers[index]) > 0)  # 且有新数据要显示
                        
                        if isinstance(text_edit, QPlainTextEdit):
                            if needs_full_render:
                                # 🎨 完全重新渲染：只显示最新数据，避免旧数据重新出现
                                ui_start_time = time.time()
                                text_edit.clear()  # 清空当前显示
                                all_colored_data = ''.join(self.worker.colored_buffers[index])
                                
                                # 🔧 BUG1修复：display_lengths必须基于colored_buffers计算，而不是buffers
                                # 因为实际显示的是colored_buffers，长度不一致会导致增量更新时重复数据
                                total_colored_length = len(all_colored_data)
                                
                                if total_colored_length > max_insert_length:
                                    all_colored_data = all_colored_data[-max_insert_length:]
                                    # 同步更新display_lengths，基于colored_buffers的长度
                                    self.worker.display_lengths[index] = max(0, total_colored_length - max_insert_length)
                                else:
                                    # 直接使用colored_buffers的长度
                                    self.worker.display_lengths[index] = total_colored_length
                                    
                                self._insert_ansi_text_fast(text_edit, all_colored_data, index)
                            else:
                                # 🎨 增量更新：使用ANSI彩色处理而不是纯文本
                                incremental_colored, current_total = self.worker._extract_increment_from_chunks(
                                    self.worker.colored_buffers[index] if hasattr(self.worker, 'colored_buffers') else self.worker.buffers[index],
                                    self.worker.display_lengths[index],
                                    max_insert_length
                                )
                                ui_start_time = time.time()
                                if incremental_colored:
                                    self._insert_ansi_text_fast(text_edit, incremental_colored, index)
                                    self.worker.display_lengths[index] = current_total
                        else:
                            # QTextEdit 保持彩色路径
                            if needs_full_render:
                                # 🎨 完全重新渲染：只显示最新数据，避免旧数据重新出现
                                ui_start_time = time.time()
                                text_edit.clear()
                                all_colored_data = ''.join(self.worker.colored_buffers[index])
                                
                                # 🔧 BUG1修复：display_lengths必须基于colored_buffers计算，而不是buffers
                                # 因为实际显示的是colored_buffers，长度不一致会导致增量更新时重复数据
                                total_colored_length = len(all_colored_data)
                                
                                if total_colored_length > max_insert_length:
                                    all_colored_data = all_colored_data[-max_insert_length:]
                                    # 同步更新display_lengths，基于colored_buffers的长度
                                    self.worker.display_lengths[index] = max(0, total_colored_length - max_insert_length)
                                else:
                                    # 直接使用colored_buffers的长度
                                    self.worker.display_lengths[index] = total_colored_length
                                    
                                self._insert_ansi_text_fast(text_edit, all_colored_data, index)
                            else:
                                # 🔧 修复：真正的增量更新，只插入新数据而不是全部数据
                                incremental_colored, current_total = self.worker._extract_increment_from_chunks(
                                    self.worker.colored_buffers[index],
                                    self.worker.display_lengths[index],
                                    max_insert_length
                                )
                                ui_start_time = time.time()
                                if incremental_colored:
                                    self._insert_ansi_text_fast(text_edit, incremental_colored, index)
                                    self.worker.display_lengths[index] = current_total
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                        
                        # 📈 性能监控：UI更新结束
                        ui_time = (time.time() - ui_start_time) * 1000  # 转换为毫秒
                        
                        # 🚀 使用可配置的性能阈值
                        clean_trigger = 50  # 默认值
                        warning_trigger = 100  # 默认值
                        try:
                            if self.main_window.connection_dialog and hasattr(self.main_window.connection_dialog, 'config'):
                                clean_trigger = self.main_window.connection_dialog.config.get_clean_trigger_ms()
                                warning_trigger = self.main_window.connection_dialog.config.get_warning_trigger_ms()
                        except Exception:
                            pass
                        
                        if ui_time > clean_trigger:  # 使用配置的清理触发阈值
                            data_size = len(incremental_colored) // 1024 if 'incremental_colored' in locals() else 0  # KB
                            if ui_time > warning_trigger:  # 使用配置的警告触发阈值
                                logger.warning(f"[UI] UI更新耗时 - TAB{index}: {ui_time:.1f}ms, 数据量: {data_size}KB")
                            
                            # 🚀 自动清理：耗时超过阈值时清理该TAB的数据
                            self._auto_clean_tab_data(index, text_edit, ui_time)
                    
                    elif len(self.worker.buffers[index]) > 0:
                        # 🚀 方案B：智能处理 — QPlainTextEdit 增量纯文本
                        from PySide6.QtWidgets import QPlainTextEdit
                        ui_start_time = time.time()
                        if isinstance(text_edit, QPlainTextEdit):
                            # 快进逻辑：积压过多时直接从尾部显示，避免显示严重滞后
                            backlog = self.worker.buffer_lengths[index] - self.worker.display_lengths[index]
                            if backlog > self.worker.backlog_fast_forward_threshold:
                                # 🎨 快速前进模式：保持ANSI彩色显示
                                tail_bytes = self.worker.fast_forward_tail
                                accumulated = ''.join(self.worker.buffers[index])
                                tail_text = accumulated[-tail_bytes:]
                                # 使用ANSI彩色文本插入而不是纯文本
                                self._insert_ansi_text_fast(text_edit, tail_text, index)
                                self.worker.display_lengths[index] = self.worker.buffer_lengths[index]
                                ui_start_time = time.time()
                                # 自动滚动到底部
                                text_edit.verticalScrollBar().setValue(
                                    text_edit.verticalScrollBar().maximum())
                                ui_time = (time.time() - ui_start_time) * 1000
                            else:
                                incremental_text, current_total = self.worker._extract_increment_from_chunks(
                                    self.worker.buffers[index],
                                    self.worker.display_lengths[index],
                                    max_insert_length
                                )
                            if incremental_text:
                                # 🎨 增量更新：保持ANSI彩色显示
                                self._insert_ansi_text_fast(text_edit, incremental_text, index)
                                self.worker.display_lengths[index] = current_total
                        else:
                            accumulated_data = ''.join(self.worker.buffers[index])
                            if len(accumulated_data) > max_insert_length:
                                display_data = accumulated_data[-max_insert_length:]
                            else:
                                display_data = accumulated_data
                            # 🎨 统一使用ANSI文本插入方法，自动处理彩色和纯文本
                            self._insert_ansi_text_fast(text_edit, display_data, index)
                        
                        # 📈 性能监控：UI更新结束
                        ui_time = (time.time() - ui_start_time) * 1000  # 转换为毫秒
                        
                        # 🚀 使用可配置的性能阈值
                        clean_trigger = 50  # 默认值
                        warning_trigger = 100  # 默认值
                        try:
                            if self.main_window.connection_dialog and hasattr(self.main_window.connection_dialog, 'config'):
                                clean_trigger = self.main_window.connection_dialog.config.get_clean_trigger_ms()
                                warning_trigger = self.main_window.connection_dialog.config.get_warning_trigger_ms()
                        except Exception:
                            pass
                        
                        if ui_time > clean_trigger:  # 使用配置的清理触发阈值
                            data_size = len(display_data) // 1024  # KB
                            if ui_time > warning_trigger:  # 使用配置的警告触发阈值
                                logger.warning(f"[UI] UI更新耗时 - TAB{index}: {ui_time:.1f}ms, 数据量: {data_size}KB")
                            
                            # 🚀 自动清理：耗时超过阈值时清理该TAB的数据
                            self._auto_clean_tab_data(index, text_edit, ui_time)
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                    
                    # 🔧 移除TAB切换后清空缓冲区的逻辑，避免显示旧数据后再清空
                    # 注释：不再在TAB切换后清空缓冲区，让增量更新机制正常工作
                        
                except Exception as e:
                    # 🔧 异常处理：不再清空缓冲区，只记录错误
                    print(f"文本更新异常: {e}")  # 调试信息
                
                # 📋 使用正确的显示模式：累积显示全部数据
                # 只清空增量缓冲区（colored_buffers），保留累积缓冲区（buffers）
                # 这样每次显示的是完整的累积数据，而不是增量数据
                
                # 标记页面已更新，无需再次更新
                if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'page_dirty_flags'):
                    self.main_window.page_dirty_flags[index] = False

                # 使用滑动文本块机制，不需要手动清理UI文本

                # 恢复滚动条的值
                if self.main_window.ui.LockV_checkBox.isChecked():
                    text_edit.verticalScrollBar().setValue(vscroll)

                if self.main_window.ui.LockH_checkBox.isChecked():
                    text_edit.horizontalScrollBar().setValue(hscroll)
            else:
                print("No QTextEdit found on page:", index)
        else:
            print("Invalid page index or widget type:", index)

    def clear_current_tab(self):
        """清空当前标签页的内容 - 仅限RTT通道（0-15），不包括ALL窗口"""
        current_index = self.main_window.ui.tem_switch.currentIndex()
        
        # 限制清屏功能：只允许RTT通道（索引1-16，对应通道0-15），不允许ALL窗口（索引0）
        if current_index >= 1 and current_index <= 16:
            current_page_widget = self.main_window.ui.tem_switch.widget(current_index)
            if isinstance(current_page_widget, QWidget):
                # 优先使用QPlainTextEdit（高性能），回退到QTextEdit
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page_widget.findChild(QPlainTextEdit)
                if not text_edit:
                    text_edit = current_page_widget.findChild(QTextEdit)
                
                if text_edit and hasattr(text_edit, 'clear'):
                    text_edit.clear()
                # 同时清空对应的缓冲区
                if hasattr(self, 'worker') and self.worker:
                    if current_index < len(self.worker.buffers):
                        try:
                            self.worker.buffer_lengths[current_index] = 0
                            self.worker.buffers[current_index].clear()
                        except Exception:
                            self.worker.buffers[current_index] = []
                    if hasattr(self.worker, 'colored_buffers') and current_index < len(self.worker.colored_buffers):
                        try:
                            self.worker.colored_buffer_lengths[current_index] = 0
                            self.worker.colored_buffers[current_index].clear()
                        except Exception:
                            self.worker.colored_buffers[current_index] = []

                    # 清空HTML缓冲区
                    if hasattr(self.worker, 'html_buffers') and current_index < len(self.worker.html_buffers):
                        self.worker.html_buffers[current_index] = ""
        else:
            # ALL窗口或其他窗口不允许清屏
            if current_index == 0:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self.main_window, 
                    QCoreApplication.translate("MainWindow", "Info"),
                    QCoreApplication.translate("MainWindow", "ALL window displays summary data from all channels and doesn't support clear operation.\nPlease switch to specific RTT channel (0-15) to clear.")
                )


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
            
        current_index = self.main_window.ui.tem_switch.currentIndex()
        
        # 优先更新当前显示的页面
        if self.main_window.page_dirty_flags[current_index]:
            self.switchPage(current_index)
            self.main_window.page_dirty_flags[current_index] = False
        
        # 🎨 修复：确保所有TAB都能显示高亮 - 更新所有脏标记的TAB
        # 使用更积极的更新策略，确保高亮在所有TAB中都能及时显示
        if hasattr(self.worker, 'get_buffer_memory_usage'):
            memory_info = self.worker.get_buffer_memory_usage()
            utilization = memory_info.get('capacity_utilization', 0)
            
            # 根据容量利用率调整更新策略，但确保高亮显示优先级
            if utilization > 80:  # 高利用率，减少更新
                max_updates = 3  # 增加更新数量确保高亮显示
            elif utilization > 60:  # 中等利用率
                max_updates = 5
            else:  # 低利用率，正常更新
                max_updates = 8  # 更多TAB可以同时更新
        else:
            max_updates = 8
        
        updated_count = 0
        for i in range(MAX_TAB_SIZE):
            if i != current_index and self.main_window.page_dirty_flags[i] and updated_count < max_updates:
                # 🎨 为每个TAB更新内容和高亮
                self.switchPage(i)
                self.main_window.page_dirty_flags[i] = False
                updated_count += 1
   

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
        self.initial_capacity = 100 * 1024  # 初始容量 100KB
        self.max_capacity = 6400 * 1024     # 最大容量 6.4MB
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
            self.buffer_flush_timer.start(200)  # 每200ms刷新一次缓冲，提高实时性
            
        # 🔧 立即执行一次刷新，确保启动时的数据能及时写入
        QTimer.singleShot(100, self.flush_log_buffers)

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
        """写入日志缓冲而不是直接写文件（增强版本）"""
        try:
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
            
            # 🚀 实时刷新机制：当缓冲区达到一定大小时立即刷新，提高TAB日志实时性
            immediate_flush_threshold = 8192  # 8KB阈值，确保及时刷新
            if len(self.log_buffers[filepath]) >= immediate_flush_threshold:
                try:
                    import os
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write(self.log_buffers[filepath])
                        f.flush()
                    self.log_buffers[filepath] = ""
                except Exception as e:
                    logger.error(f"Immediate flush failed for {filepath}: {e}")
            
            # 🔧 检查总缓冲区数量，避免文件过多
            if len(self.log_buffers) > 100:  # 限制同时缓冲的文件数量
                self._emergency_flush_oldest_buffers()
                
        except Exception as e:
            logger.error(f"Error in write_to_log_buffer for {filepath}: {e}")
    
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
        """📋 统一日志写入方法：将数据写入指定buffer对应的日志文件
        
        Args:
            buffer_index: buffer索引 (0=ALL页面, 1-16=通道页面, 17+=筛选页面)
            data: 要写入的数据（应该与对应buffer内容一致）
            log_suffix: 日志文件后缀 (如果为空，使用buffer_index)
        """
        try:
            if (hasattr(self.parent, 'rtt2uart') and 
                self.parent.rtt2uart):
                
                # 构造日志文件路径
                if log_suffix:
                    log_filepath = f"{self.parent.rtt2uart.rtt_log_filename}_{log_suffix}.log"
                else:
                    log_filepath = f"{self.parent.rtt2uart.rtt_log_filename}_{buffer_index}.log"
                
                # 直接写入数据，确保与buffer内容一致
                if data:
                    self.write_to_log_buffer(log_filepath, data)
                    
        except Exception as e:
            logger.error(f"Failed to write data to buffer {buffer_index} log: {e}")

    def _has_ansi_codes(self, text):
        """检查文本是否包含ANSI控制符"""
        try:
            # 使用正则表达式检测ANSI控制符
            ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            return bool(ansi_pattern.search(text))
        except Exception:
            return False

    def _convert_ansi_to_html(self, text):
        """将ANSI控制符转换为HTML格式"""
        try:
            # 简化的ANSI到HTML转换
            # 这里可以根据需要扩展更多颜色支持
            
            # 移除ANSI控制符并保留纯文本（简化版本）
            # 实际项目中可以实现完整的ANSI到HTML转换
            ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            
            # 简单的颜色替换示例
            html_text = text
            
            # 改进的ANSI匹配：处理更多结束符情况
            # 红色文本  
            html_text = re.sub(r'\x1B\[31m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: red;">\1</span>', html_text)
            html_text = re.sub(r'\x1B\[1;31m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: #FF0000;">\1</span>', html_text)
            
            # 绿色文本
            html_text = re.sub(r'\x1B\[32m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: green;">\1</span>', html_text)
            html_text = re.sub(r'\x1B\[1;32m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: #00FF00;">\1</span>', html_text)
            
            # 黄色文本
            html_text = re.sub(r'\x1B\[33m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: #808000;">\1</span>', html_text)
            html_text = re.sub(r'\x1B\[1;33m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: #FFFF00;">\1</span>', html_text)
            
            # 蓝色文本
            html_text = re.sub(r'\x1B\[34m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: blue;">\1</span>', html_text)
            html_text = re.sub(r'\x1B\[1;34m([^\x1B]*?)(?:\x1B\[0m|\x1B\[\d*m|$)', r'<span style="color: #0000FF;">\1</span>', html_text)
            
            # 移除其他未处理的ANSI控制符
            html_text = ansi_pattern.sub('', html_text)
            
            return html_text
            
        except Exception as e:
            # 如果转换失败，返回移除ANSI后的纯文本
            ansi_pattern = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            return ansi_pattern.sub('', text)



    # _aggressive_manage_buffer_size方法已移除，使用滑动文本块机制替代

    @Slot(int, str)
    def addToBuffer(self, index, string):
        # 🚀 Turbo模式：智能批量处理
        if self.turbo_mode and len(string) < 1024:  # 小数据包使用批量处理
            self.batch_buffers[index] += string
            
            # 🚀 优化：如果批量缓冲区太大，立即处理避免延迟过久
            if len(self.batch_buffers[index]) > 4096:  # 4KB阈值
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
            
            self.batch_timers[index].start(self.batch_delay)
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
                    self.parent.main_window.page_dirty_flags[index + 1] = True  # 对应通道页面
                    self.parent.main_window.page_dirty_flags[0] = True  # ALL页面
                    
                    # 如果当前显示的是这些页面，立即更新
                    current_index = self.parent.main_window.ui.tem_switch.currentIndex()
                    if current_index == index + 1 or current_index == 0:
                        QTimer.singleShot(0, lambda: self.parent.switchPage(current_index))
                        
                # 🚀 强制触发缓冲区更新处理
                QTimer.singleShot(0, lambda: self.parent.handleBufferUpdate())
    
    def _process_buffer_data(self, index, string):
        # 添加数据到指定索引的缓冲区，如果超出缓冲区大小则删除最早的字符
        self.byte_buffer[index] += string

        # 找到第一个 '\n' 的索引
        newline = self.byte_buffer[index].rfind(b'\n')
        if newline != -1:  # 如果找到了 '\n'
            # 分割数据
            new_buffer = self.byte_buffer[index][:newline + 1]
            self.byte_buffer[index] = self.byte_buffer[index][newline + 1:]
            # 使用配置的编码进行解码
            try:
                enc = self.parent.config.get_text_encoding() if hasattr(self.parent, 'config') else 'gbk'
            except Exception:
                enc = 'gbk'
            data = new_buffer.decode(enc, errors='ignore')

            # 性能优化：使用列表拼接替代字符串拼接
            buffer_parts = ["%02u> " % index, data]
            
            # 重新启用ANSI处理，使用安全的错误处理
            try:
                # 处理ANSI颜色：为UI显示保留颜色，为缓冲区存储纯文本
                clean_data = ansi_processor.remove_ansi_codes(data)
                clean_buffer_parts = ["%02u> " % index, clean_data]
                
                # 🚀 智能缓冲区管理：存储纯文本到buffers（用于日志和转发）
                self._append_to_buffer(index+1, clean_data)
                self._append_to_buffer(0, ''.join(clean_buffer_parts))
                
                # 为彩色显示保留原始ANSI文本（供 QTextEdit 渲染）
                if hasattr(self, 'colored_buffers'):
                    self._append_to_colored_buffer(index+1, data)
                    self._append_to_colored_buffer(0, ''.join(buffer_parts))
                    
            except Exception as e:
                # 🔧 修复重复问题：如果ANSI处理失败，使用原始数据但避免重复添加
                logger.warning(f"ANSI处理失败，使用原始数据: {e}")
                # 只有在之前没有成功添加数据时才添加原始数据
                # 由于异常发生，之前的数据添加可能没有完成，所以这里需要添加
                self._append_to_buffer(index+1, data)
                self._append_to_buffer(0, ''.join(buffer_parts))
                if hasattr(self, 'colored_buffers'):
                    self._append_to_colored_buffer(index+1, data)
                    self._append_to_colored_buffer(0, ''.join(buffer_parts))
            
            # 使用滑动文本块机制，不需要激进的缓冲区大小限制
            
            # 标记页面需要更新（恢复原行为：当前页 + ALL）
            self.update_counter += 1
            if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
                self.parent.main_window.page_dirty_flags[index+1] = True
                self.parent.main_window.page_dirty_flags[0] = True
            
            # 串口转发功能：将指定TAB的数据转发到串口
            if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                # 转发单个通道的数据（index+1对应TAB索引）
                self.parent.rtt2uart.add_tab_data_for_forwarding(index+1, data)
                # 转发所有数据（TAB 0）包含通道前缀
                self.parent.rtt2uart.add_tab_data_for_forwarding(0, ''.join(buffer_parts))

            # 📋 统一日志处理：通道数据写入对应的日志文件（使用通道号0~15）
            self.write_data_to_buffer_log(index+1, clean_data, str(index))

            # 📋 统一过滤逻辑：使用清理过的数据进行筛选，确保与页面显示一致
            if clean_data.strip():  # 只处理非空数据
                clean_lines = [line for line in clean_data.split('\n') if line.strip()]
                self.process_filter_lines(clean_lines)

            self.finished.emit()
    
    def _append_to_buffer(self, index, data):
        """🚀 智能缓冲区追加：预分配 + 成倍扩容机制 + 重复检查"""
        if index < len(self.buffers):
            # 防御：如果被外部代码误置为字符串，立即恢复为分块列表
            if not isinstance(self.buffers[index], list):
                self.buffers[index] = []
                self.buffer_lengths[index] = 0
            
            # 🔧 增强重复检查：防止相同数据被添加（检查最近10条记录）
            if len(self.buffers[index]) > 0:
                # 检查最近的10条记录，防止非连续重复
                check_count = min(10, len(self.buffers[index]))
                recent_data = self.buffers[index][-check_count:]
                if data in recent_data:
                    # 检测到重复数据，跳过添加
                    logger.debug(f"检测到重复数据，跳过添加到buffer[{index}]: {data[:50]}...")
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
        """🎨 智能彩色缓冲区追加：预分配 + 成倍扩容机制 + 重复检查"""
        if hasattr(self, 'colored_buffers') and index < len(self.colored_buffers):
            # 防御：如果被误置为字符串，恢复为分块列表
            if not isinstance(self.colored_buffers[index], list):
                self.colored_buffers[index] = []
                self.colored_buffer_lengths[index] = 0
            
            # 🔧 增强重复检查：防止相同数据被添加（检查最近10条记录）
            if len(self.colored_buffers[index]) > 0:
                # 检查最近的10条记录，防止非连续重复
                check_count = min(10, len(self.colored_buffers[index]))
                recent_data = self.colored_buffers[index][-check_count:]
                if data in recent_data:
                    # 检测到重复数据，跳过添加
                    logger.debug(f"检测到重复彩色数据，跳过添加到colored_buffer[{index}]: {data[:50]}...")
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
                    while self.colored_buffer_lengths[index] > trim_size and self.colored_buffers[index]:
                        removed = self.colored_buffers[index].pop(0)
                        self.colored_buffer_lengths[index] -= len(removed)
                    logger.info(f"[TRIM] Colored buffer {index} trimmed to {self.colored_buffer_lengths[index]//1024}KB (max capacity reached)")
            
            # 分块追加
            self.colored_buffers[index].append(data)
            self.colored_buffer_lengths[index] += len(data)
            
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
            logger.info(f"[PERF] Performance monitoring - refresh rate: {refresh_rate:.1f}Hz, "
                       f"总数据量: {memory_info['total_memory_mb']:.1f}MB, "
                       f"容量利用率: {memory_info['capacity_utilization']:.1f}%, "
                       f"最大单缓冲: {memory_info['max_single_buffer']//1024:.0f}KB")
            
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

    def _highlight_filter_text(self, line, search_word):
        """为筛选文本添加高亮显示"""
        try:
            if not search_word or search_word.lower() not in line.lower():
                return line
            
            # 🎨 使用明亮黄色背景 + 黑色文字高亮筛选关键词 - 增强对比度
            highlight_start = '\x1B[43;30m'  # 明亮黄色背景 + 黑色文字
            highlight_end = '\x1B[0m'        # 重置所有格式
            
            # 🎨 大小写不敏感匹配和替换
            import re
            # 使用正则表达式进行大小写不敏感的替换，保持原文本的大小写
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
                if self.parent.main_window:
                    tag_text = self.parent.main_window.ui.tem_switch.tabText(i)
                    if tag_text != QCoreApplication.translate("main_window", "filter"):
                        # 🔧 修改：检查单个TAB的正则表达式状态
                        tab_regex_enabled = False
                        if hasattr(self.parent.main_window, 'connection_dialog') and self.parent.main_window.connection_dialog:
                            tab_regex_enabled = self.parent.main_window.connection_dialog.config.get_tab_regex_filter(i)
                        
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
                elif len(item) == 3:
                    # 兼容旧格式 (i, tag_text, compiled_pattern)
                    i, search_word, compiled_pattern = item
                    
                    # 🔧 防重复：如果该TAB已经匹配过这行数据，跳过
                    if i in matched_tabs:
                        continue
                    
                    # 根据是否有编译的正则模式决定匹配方式
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
                self.setFormat(start_index, match_length, self.keyword_format)
        

    


def is_dummy_thread(thread):
    return thread.name.startswith('Dummy')

if __name__ == "__main__":
    # 🔑 注册全局退出处理器，确保异常退出时也能清理JLink连接
    import atexit
    
    def emergency_cleanup():
        """紧急清理函数 - 在程序异常退出时强制关闭JLink"""
        try:
            import pylink
            # 创建一个临时JLink对象尝试关闭可能遗留的连接
            temp_jlink = pylink.JLink()
            try:
                if temp_jlink.connected():
                    temp_jlink.close()
                    print("[EMERGENCY] Force closed JLink connection on exit")
            except:
                pass
        except:
            pass
    
    # 注册退出处理器
    atexit.register(emergency_cleanup)
    
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
                print(f"[CONFIG] Setting Qt DPI environment variables: {dpi_value}")
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
    
    # Check system locale to determine which translation to load
    locale = QLocale.system()
    print(f"System locale: {locale.name()}, language: {locale.language()}, country: {locale.country()}")
    
    # 🔧 获取资源文件路径（支持PyInstaller打包）
    def get_resource_path(filename):
        """获取资源文件的正确路径（支持开发环境和PyInstaller打包环境）"""
        # PyInstaller打包后，资源文件在临时目录_MEIPASS中
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, filename)
        # 开发环境，资源文件在当前目录
        return filename
    
    # Force Chinese translation for testing, or if system is Chinese
    force_chinese = True  # 强制使用中文翻译
    if force_chinese or locale.language() == QLocale.Chinese:
        # 尝试按优先级加载翻译文件
        qm_paths = [
            get_resource_path("xexunrtt_complete.qm"),  # PyInstaller或当前目录
            "xexunrtt_complete.qm",  # 当前目录（备用）
            "../Resources/xexunrtt_complete.qm",  # Resources目录（macOS）
            ":/xexunrtt_complete.qm"  # Qt资源（备用）
        ]
        
        for qm_path in qm_paths:
            if translator.load(qm_path):
                QCoreApplication.installTranslator(translator)
                translation_loaded = True
                print(f"[OK] Chinese translation loaded successfully: {qm_path}")
                # Test if translation is working
                test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
                print(f"翻译测试: 'JLink Debug Log' → '{test_text}'")
                break
        
        if not translation_loaded:
            print("[WARNING] Cannot load Chinese translation file, using English interface")
    else:
        print("Using English interface (default).")

    # Load Qt built-in translation files
    qt_translator = QTranslator()
    qt_translation_loaded = False
    
    # 尝试按优先级加载Qt翻译文件
    qt_qm_paths = [
        get_resource_path("qt_zh_CN.qm"),  # PyInstaller或当前目录
        "qt_zh_CN.qm",  # 当前目录（备用）
        "../Resources/qt_zh_CN.qm",  # Resources目录（macOS）
        ":/qt_zh_CN.qm"  # Qt资源（备用）
    ]
    
    for qt_qm_path in qt_qm_paths:
        if qt_translator.load(qt_qm_path):
            QCoreApplication.installTranslator(qt_translator)
            qt_translation_loaded = True
            print(f"[OK] Qt translation loaded successfully: {qt_qm_path}")
            break
    
    if not qt_translation_loaded:
        print("[WARNING] Cannot load Qt translation file")
    
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
