from pickle import NONE
import sys
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor
from PySide6.QtCore import *
from PySide6 import QtGui
from PySide6 import QtCore
from PySide6.QtCore import QObject
from PySide6.QtGui import QFont, QIcon, QAction
from PySide6.QtNetwork import QLocalSocket, QLocalServer
import qdarkstyle
from ui_rtt2uart_updated import Ui_dialog
from ui_sel_device import Ui_Dialog
from ui_xexunrtt import Ui_xexun_rtt
from rtt2uart import ansi_processor
import resources_rc
from contextlib import redirect_stdout
import serial.tools.list_ports
import serial
import ctypes.util as ctypes_util
import xml.etree.ElementTree as ET
import pylink
from rtt2uart import rtt_to_serial
import logging
import time
import pickle
import os
from config_manager import config_manager
import subprocess
import threading
import shutil
import re
import psutil
from performance_test import show_performance_test

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

MAX_TAB_SIZE = 24

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
    def __init__(self):
        super(DeviceSelectDialog, self).__init__()
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        self.setWindowModality(Qt.ApplicationModal)
        
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
        """获取JLink设备数据库文件路径，支持开发环境和打包后的资源访问"""
        
        # 开发环境：优先从当前目录读取
        if os.path.exists('JLinkDevicesBuildIn.xml'):
            return os.path.abspath('JLinkDevicesBuildIn.xml')
        
        # 打包后环境：从资源目录读取
        try:
            # PyInstaller会将资源文件解压到sys._MEIPASS目录
            if hasattr(sys, '_MEIPASS'):
                resource_path = os.path.join(sys._MEIPASS, 'JLinkDevicesBuildIn.xml')
                if os.path.exists(resource_path):
                    return resource_path
            
            # 尝试从当前可执行文件目录读取
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            exe_resource_path = os.path.join(exe_dir, 'JLinkDevicesBuildIn.xml')
            if os.path.exists(exe_resource_path):
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

    # 在设备选择对话框类中添加一个方法来处理确定按钮的操作
    def accept(self):
        self.refresh_selected_device()
        super().accept()  # 调用父类的accept()以正确设置对话框结果

class EditableTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None  # 将在主窗口中设置
    
    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.pos())
        if index >= 17:
            old_text = self.tabText(index)
            new_text, ok = QInputDialog.getText(self, QCoreApplication.translate("main_window", "Edit Filter Text"), QCoreApplication.translate("main_window", "Enter new text:"), QLineEdit.Normal, old_text)
            if ok:
                if new_text:
                    self.setTabText(index, new_text)
                else:
                    self.setTabText(index, QCoreApplication.translate("main_window", "filter"))
                
                # 保存过滤器设置
                if self.main_window and self.main_window.connection_dialog:
                    filter_text = new_text if new_text else QCoreApplication.translate("main_window", "filter")
                    if filter_text != QCoreApplication.translate("main_window", "filter"):
                        self.main_window.connection_dialog.config.set_filter(index, filter_text)
                        self.main_window.connection_dialog.config.save_config()

class RTTMainWindow(QMainWindow):
    def __init__(self):
        super(RTTMainWindow, self).__init__()
        self.connection_dialog = None
        self._is_closing = False  # 标记主窗口是否正在关闭
        
        # 设置主窗口属性
        self.setWindowTitle(QCoreApplication.translate("main_window", "XexunRTT - RTT调试主窗口"))
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        
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
        
        # 立即创建连接对话框以便加载配置
        self.connection_dialog = ConnectionDialog(self)
        # 连接成功信号
        self.connection_dialog.connection_established.connect(self.on_connection_established)
        # 连接断开信号
        self.connection_dialog.connection_disconnected.connect(self.on_connection_disconnected)
        
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
        #self.addAction(self.actionenter)

        # 连接动作的触发事件
        self.action1.triggered.connect(self.on_openfolder_clicked)
        self.action2.triggered.connect(self.on_re_connect_clicked)
        self.action3.triggered.connect(self.on_dis_connect_clicked)
        self.action4.triggered.connect(self.on_clear_clicked)
        self.action5.triggered.connect(self.toggle_lock_v_checkbox)
        self.action6.triggered.connect(self.toggle_lock_h_checkbox)
        self.action7.triggered.connect(self.toggle_style_checkbox)

        self.action9.triggered.connect(self.device_restart)
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
            
            # 🎨 默认使用QPlainTextEdit（高性能纯文本），必要时再回退QTextEdit
            from PySide6.QtWidgets import QPlainTextEdit
            text_edit = QPlainTextEdit(page)
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.NoWrap)  # 禁用换行，提升性能
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示水平滚动条
            text_edit.setToolTip("")  # 清除文本编辑器的工具提示
            
            # 🎯 关键性能优化设置 - 像JLink RTT Viewer一样支持大缓冲
            text_edit.document().setMaximumBlockCount(50000)  # 10000行缓冲，接近JLink RTT Viewer
            
            # 🎨 设置等宽字体，提升渲染性能
            font = QFont("新宋体", 10)
            font.setFixedPitch(True)  # 等宽字体
            text_edit.setFont(font)
            
            layout = QVBoxLayout(page)  # 创建布局管理器
            layout.addWidget(text_edit)  # 将 QPlainTextEdit 添加到布局中
            self.highlighter[i] = PythonHighlighter(text_edit.document())
            
            if i == 0:
                self.ui.tem_switch.addTab(page, QCoreApplication.translate("main_window", "All"))  # 将页面添加到 tabWidget 中
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
        self.populateComboBox()
        self.ui.cmd_buffer.enter_pressed.connect(self.on_pushButton_clicked)

        # 设置默认样式
        palette = QPalette()
        palette.ID = 'light'
        self.light_stylesheet = qdarkstyle._load_stylesheet(qt_api='pyside6', palette=palette)
        self.dark_stylesheet = qdarkstyle.load_stylesheet_pyside6()
        
        self.ui.light_checkbox.stateChanged.connect(self.set_style)
        self.ui.fontsize_box.valueChanged.connect(self.on_fontsize_changed)
        
        # 连接滚动条锁定复选框的信号
        self.ui.LockH_checkBox.stateChanged.connect(self.on_lock_h_changed)
        self.ui.LockV_checkBox.stateChanged.connect(self.on_lock_v_changed)
        
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
        connection_menu = menubar.addMenu(QCoreApplication.translate("main_window", "连接(&C)"))
        
        # 重新连接动作
        reconnect_action = QAction(QCoreApplication.translate("main_window", "重新连接(&R)"), self)
        reconnect_action.triggered.connect(self.on_re_connect_clicked)
        connection_menu.addAction(reconnect_action)
        
        # 断开连接动作
        disconnect_action = QAction(QCoreApplication.translate("main_window", "断开连接(&D)"), self)
        disconnect_action.triggered.connect(self.on_dis_connect_clicked)
        connection_menu.addAction(disconnect_action)
        
        connection_menu.addSeparator()
        
        # 连接设置动作
        settings_action = QAction(QCoreApplication.translate("main_window", "连接设置(&S)..."), self)
        settings_action.triggered.connect(self._show_connection_settings)
        connection_menu.addAction(settings_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu(QCoreApplication.translate("main_window", "工具(&T)"))
        
        # 清除日志动作
        clear_action = QAction(QCoreApplication.translate("main_window", "清除当前页面(&C)"), self)
        clear_action.triggered.connect(self.on_clear_clicked)
        tools_menu.addAction(clear_action)
        
        # 打开日志文件夹动作
        open_folder_action = QAction(QCoreApplication.translate("main_window", "打开日志文件夹(&O)"), self)
        open_folder_action.triggered.connect(self.on_openfolder_clicked)
        tools_menu.addAction(open_folder_action)
        
        tools_menu.addSeparator()
        
        # 样式切换动作
        style_action = QAction(QCoreApplication.translate("main_window", "切换主题(&T)"), self)
        style_action.triggered.connect(self.toggle_style_checkbox)
        tools_menu.addAction(style_action)
        
        tools_menu.addSeparator()
        
        # 性能测试动作
        perf_test_action = QAction(QCoreApplication.translate("main_window", "性能测试(&P)..."), self)
        perf_test_action.triggered.connect(self.show_performance_test)
        tools_menu.addAction(perf_test_action)
        
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
        help_menu = menubar.addMenu(QCoreApplication.translate("main_window", "帮助(&H)"))
        
        # 关于动作
        about_action = QAction(QCoreApplication.translate("main_window", "关于(&A)..."), self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        
        # 连接状态标签
        self.connection_status_label = QLabel(QCoreApplication.translate("main_window", "未连接"))
        self.status_bar.addWidget(self.connection_status_label)
        
        # 注释掉Turbo模式状态标签（功能保留，界面隐藏）
        # # 🚀 Turbo模式状态标签
        # self.turbo_status_label = QLabel("🚀 Turbo: ON")
        # self.turbo_status_label.setStyleSheet("color: #00AA00; font-weight: bold;")
        # self.status_bar.addPermanentWidget(self.turbo_status_label)
        
        # 数据统计标签
        self.data_stats_label = QLabel(QCoreApplication.translate("main_window", "读取: 0 | 写入: 0"))
        self.status_bar.addPermanentWidget(self.data_stats_label)
    
    def _show_connection_settings(self):
        """显示连接设置对话框"""
        self.show_connection_dialog()
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, 
                         QCoreApplication.translate("main_window", "关于 XexunRTT"),
                         QCoreApplication.translate("main_window", 
                                                   "XexunRTT v2.0\n\n"
                                                   "RTT调试工具\n\n"
                                                   "基于 PySide6 开发"))
    
    def show_performance_test(self):
        """显示性能测试窗口"""
        try:
            self.perf_test_widget = show_performance_test(self)
            self.perf_test_widget.log_message("性能测试工具已启动")
            self.perf_test_widget.log_message("注意：请确保已连接设备并开始RTT调试")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动性能测试失败：{str(e)}")
    
    def toggle_turbo_mode(self):
        """切换Turbo模式（隐藏UI，功能保留）"""
        # 注释掉UI相关代码，但保留核心功能
        # enabled = self.turbo_mode_action.isChecked()
        
        # 由于UI已隐藏，这里可以通过其他方式控制，暂时保持启用状态
        enabled = True
        
        # 应用到ConnectionDialog的worker
        if self.connection_dialog and hasattr(self.connection_dialog, 'worker'):
            self.connection_dialog.worker.set_turbo_mode(enabled)
            
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
        
        # 显示对话框
        self.connection_dialog.show()
        
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
        
        # 应用保存的设置
        self._apply_saved_settings()
        
        # 更新状态显示
        self.update_status_bar()
        
        # 显示成功消息
        self.statusBar().showMessage(QCoreApplication.translate("main_window", "RTT连接建立成功"), 3000)
    
    def on_connection_disconnected(self):
        """连接断开后的处理"""
        # 禁用RTT相关功能
        self._set_rtt_controls_enabled(False)
        
        # 更新状态显示
        self.update_status_bar()
        
        # 显示断开消息
        self.statusBar().showMessage(QCoreApplication.translate("main_window", "RTT连接已断开"), 3000)
    
    def _set_rtt_controls_enabled(self, enabled):
        """设置RTT相关控件的启用状态"""
        # RTT相关的UI控件在连接成功前应该被禁用
        if hasattr(self, 'ui'):
            # 发送命令相关控件
            if hasattr(self.ui, 'pushButton'):
                self.ui.pushButton.setEnabled(enabled)
            if hasattr(self.ui, 'cmd_buffer'):
                self.ui.cmd_buffer.setEnabled(enabled)
            
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
            self.ui.LockH_checkBox.setChecked(settings['lock_h'])
            self.ui.LockV_checkBox.setChecked(settings['lock_v'])
            self.ui.light_checkbox.setChecked(settings['light_mode'])
            self.ui.fontsize_box.setValue(settings['fontsize'])
            # 从INI配置加载命令历史
            cmd_history = self.connection_dialog.config.get_command_history()
            self.ui.cmd_buffer.addItems(cmd_history)
            # 同步更新settings以保持兼容性
            settings['cmd'] = cmd_history
            
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
        self.jlink_log_text.setFont(QFont("Consolas", 9))
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
        """处理JLink连接丢失事件"""
        try:
            self.append_jlink_log("⚠️ 处理JLink连接丢失事件...")
            
            # 更新连接状态显示
            if self.connection_dialog:
                # 重置连接状态
                self.connection_dialog.start_state = False
                self.connection_dialog.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
                
                # 发送连接断开信号
                self.connection_dialog.connection_disconnected.emit()
                
                # 🔄 立即更新状态栏显示
                self.update_status_bar()
                
                self.append_jlink_log("✅ 连接状态已重置，可以重新连接")
            
        except Exception as e:
            self.append_jlink_log(f"❌ 处理连接丢失时出错: {e}")
            logger.error(f"Error in _handle_connection_lost: {e}")
        
    def resizeEvent(self, event):
        # 当窗口大小变化时更新布局大小
        # 由于现在使用了分割器布局，让Qt自动处理大小调整
        super().resizeEvent(event)

    def closeEvent(self, e):
        """程序关闭事件处理 - 确保所有资源被正确清理"""
        logger.info("开始程序关闭流程...")
        
        # 设置关闭标志，防止在关闭时显示连接对话框
        self._is_closing = True
        
        try:
            # 1. 停止所有RTT连接
            if self.connection_dialog and self.connection_dialog.rtt2uart is not None:
                if self.connection_dialog.start_state == True:
                    logger.info("停止RTT连接...")
                    try:
                        # 正确调用stop方法而不是start方法
                        self.connection_dialog.rtt2uart.stop()
                        self.connection_dialog.start_state = False
                        
                        # 🔄 更新状态栏显示
                        self.update_status_bar()
                        
                        logger.info("RTT连接已停止")
                    except Exception as ex:
                        logger.error(f"停止RTT连接时出错: {ex}")
            
            # 2. 停止所有定时器
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
            logger.error(f"关闭程序时出错: {ex}")
        finally:
            # 确保窗口关闭
            e.accept()
            logger.info("程序关闭流程完成")
    
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
                    logger.info("缓冲刷新定时器已停止")
            
            logger.info("所有定时器已停止")
        except Exception as e:
            logger.error(f"停止定时器时出错: {e}")
    
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
                        logger.warning(f"强制终止线程: {thread.name}")
                        try:
                            # 尝试优雅地停止线程
                            thread.join(timeout=2.0)
                            if thread.is_alive():
                                logger.warning(f"线程 {thread.name} 未能优雅停止，将被强制终止")
                                # 对于Python线程，我们无法直接杀死，但可以标记为daemon
                                thread.daemon = True
                        except Exception as e:
                            logger.error(f"终止线程 {thread.name} 时出错: {e}")
            
            logger.info("线程清理完成")
        except Exception as e:
            logger.error(f"强制终止线程时出错: {e}")
    
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
            
            logger.info("UI资源清理完成")
        except Exception as e:
            logger.error(f"清理UI资源时出错: {e}")
    
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
                        logger.info(f"已删除空日志目录: {log_directory}")
            
        except Exception as e:
            logger.error(f"清理日志目录时出错: {e}")
    
    def _force_terminate_child_processes(self):
        """强制终止所有子进程"""
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            
            if children:
                logger.info(f"发现 {len(children)} 个子进程，开始清理...")
                
                for child in children:
                    try:
                        logger.info(f"终止子进程: PID={child.pid}, 名称={child.name()}")
                        child.terminate()
                        child.wait(timeout=2)
                        
                        if child.is_running():
                            logger.warning(f"强制杀死子进程: PID={child.pid}")
                            child.kill()
                            child.wait(timeout=1)
                            
                    except psutil.NoSuchProcess:
                        # 进程已经不存在
                        pass
                    except Exception as e:
                        logger.error(f"终止子进程时出错: {e}")
                
                logger.info("子进程清理完成")
            
        except Exception as e:
            logger.error(f"强制终止子进程时出错: {e}")
    
    def _force_quit_application(self):
        """强制退出应用程序"""
        try:
            # 获取应用程序实例
            app = QApplication.instance()
            if app:
                logger.info("强制退出应用程序...")
                # 设置退出代码并立即退出
                app.quit()
                # 如果quit()不起作用，使用更强制的方法
                QTimer.singleShot(1000, lambda: os._exit(0))
            
        except Exception as e:
            logger.error(f"强制退出应用程序时出错: {e}")
            # 最后的手段：直接退出进程
            os._exit(0)

    @Slot(int)
    def switchPage(self, index):
        self.connection_dialog.switchPage(index)
        
        # 更新当前标签页索引（用于串口转发）
        if self.connection_dialog and self.connection_dialog.rtt2uart:
            self.connection_dialog.rtt2uart.set_current_tab_index(index)
        
        # 每次切换页面时都确保工具提示设置正确
        self._ensure_correct_tooltips()


    @Slot()
    def handleBufferUpdate(self):
        # 获取当前选定的页面索引
        index = self.ui.tem_switch.currentIndex()
        # 刷新文本框
        self.switchPage(index)
        
    def on_pushButton_clicked(self):
        current_text = self.ui.cmd_buffer.currentText()
        utf8_data = current_text
        utf8_data += '\n'
        
        gbk_data = utf8_data.encode('gbk', errors='ignore')
        
        if self.connection_dialog:
            bytes_written = self.connection_dialog.jlink.rtt_write(0, gbk_data)
            self.connection_dialog.rtt2uart.write_bytes0 = bytes_written
        else:
            bytes_written = 0
        if(bytes_written == len(gbk_data)):
            self.ui.cmd_buffer.clearEditText()
            sent_msg = QCoreApplication.translate("main_window", u"Sent:") + "\t" + utf8_data[:len(utf8_data) - 1]
            self.ui.sent.setText(sent_msg)
            self.ui.tem_switch.setCurrentIndex(2)   #输入指令成功后，自动切换到应答界面
            current_page_widget = self.ui.tem_switch.widget(2)
            if isinstance(current_page_widget, QWidget):
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page_widget.findChild(QPlainTextEdit) or current_page_widget.findChild(QTextEdit)
                if text_edit:
                    self.highlighter[2].setKeywords([current_text])
                    
            # 检查字符串是否在 ComboBox 的列表中
            if current_text not in [self.ui.cmd_buffer.itemText(i) for i in range(self.ui.cmd_buffer.count())]:
                # 如果不在列表中，则将字符串添加到 ComboBox 中
                self.ui.cmd_buffer.addItem(current_text)
                if self.connection_dialog:
                    self.connection_dialog.settings['cmd'].append(current_text)
                    # 同步保存到CMD.txt文件
                    self.connection_dialog.config.add_command_to_history(current_text)

    def on_dis_connect_clicked(self):
        """断开连接，不显示连接对话框"""
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            self.connection_dialog.start()  # 这会切换到断开状态
        # 如果已经断开，则无操作（但快捷键仍然响应）

    def on_re_connect_clicked(self):
        """重新连接：先断开现有连接，然后显示连接对话框"""
        # 如果当前有连接，先断开
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            self.connection_dialog.start()  # 这会切换到断开状态
            
        # 显示连接对话框供用户重新连接
        if self.connection_dialog and not self._is_closing:
            self.connection_dialog.show()

    def on_clear_clicked(self):
        index = self.ui.tem_switch.currentIndex()
        current_page_widget = self.ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            from PySide6.QtWidgets import QPlainTextEdit
            text_edit = current_page_widget.findChild(QPlainTextEdit) or current_page_widget.findChild(QTextEdit)
            if text_edit:
                text_edit.clear()

    def on_openfolder_clicked(self):
        # 在连接状态下打开当前的日志目录
        if self.connection_dialog and self.connection_dialog.rtt2uart:
            os.startfile(self.connection_dialog.rtt2uart.log_directory)
        else:
            # 在断开状态下打开默认的日志目录
            import pathlib
            desktop_path = pathlib.Path.home() / "Desktop/XexunRTT_Log"
            if desktop_path.exists():
                os.startfile(str(desktop_path))
            else:
                # 如果日志目录不存在，打开桌面
                desktop = pathlib.Path.home() / "Desktop"
                os.startfile(str(desktop))

    def populateComboBox(self):
        # 读取 cmd.txt 文件并将内容添加到 QComboBox 中
        try:
            # 首先尝试UTF-8编码，失败后尝试GBK编码
            try:
                with open('cmd.txt', 'r', encoding='utf-8') as file:
                    for line in file:
                        self.ui.cmd_buffer.addItem(line.strip())  # 去除换行符并添加到 QComboBox 中
            except UnicodeDecodeError:
                # 如果UTF-8解码失败，尝试GBK编码
                with open('cmd.txt', 'r', encoding='gbk') as file:
                    for line in file:
                        self.ui.cmd_buffer.addItem(line.strip())
        except FileNotFoundError:
            print("File 'cmd.txt' not found.")
        except Exception as e:
            print("An error occurred while reading 'cmd.txt':", e)

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
    
    def on_fontsize_changed(self):
        """字体大小变更时的处理"""
        if self.connection_dialog:
            self.connection_dialog.settings['fontsize'] = self.ui.fontsize_box.value()
            # 同步保存到INI配置
            self.connection_dialog.config.set_fontsize(self.ui.fontsize_box.value())
            self.connection_dialog.config.save_config()
    
    def on_lock_h_changed(self):
        """水平滚动条锁定状态改变时保存配置"""
        if self.connection_dialog:
            self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
            self.connection_dialog.config.save_config()
    
    def on_lock_v_changed(self):
        """垂直滚动条锁定状态改变时保存配置"""
        if self.connection_dialog:
            self.connection_dialog.config.set_lock_vertical(self.ui.LockV_checkBox.isChecked())
            self.connection_dialog.config.save_config()
    
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
        if hasattr(self, 'jlink_log_widget'):
            # 更新JLink日志区域的文本
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
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "已连接"))
        else:
            self.connection_status_label.setText(QCoreApplication.translate("main_window", "未连接"))
        
        # 更新数据统计
        readed = 0
        writed = 0
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None:
            readed = self.connection_dialog.rtt2uart.read_bytes0 + self.connection_dialog.rtt2uart.read_bytes1
            writed = self.connection_dialog.rtt2uart.write_bytes0
        
        self.data_stats_label.setText(
            QCoreApplication.translate("main_window", "读取: {} | 写入: {}").format(readed, writed)
        )
    
    def update_periodic_task(self):
        
        title = QCoreApplication.translate("main_window", u"XexunRTT")
        title += "\t"
        
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            title += QCoreApplication.translate("main_window", u"status:Started")
        else:
            title += QCoreApplication.translate("main_window", u"status:Stoped")

        title += "\t"
        
        readed = 0
        writed = 0
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None:
            readed = self.connection_dialog.rtt2uart.read_bytes0 + self.connection_dialog.rtt2uart.read_bytes1
            writed = self.connection_dialog.rtt2uart.write_bytes0
        
        title += QCoreApplication.translate("main_window", u"Readed:") + "%8u" % readed
        title += "\t"
        title += QCoreApplication.translate("main_window", u"Writed:") + "%4u" % writed
        title += " "
        
        self.setWindowTitle(title)
        
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
        return
        # if self.connection_dialog.rtt2uart.jlink:
        #     try:
        #         jlink = self.connection_dialog.rtt2uart.jlink
        #         jlink.open()
        #         jlink.reset(halt=True) #实测效果不理想
        #         print("J-Link device start successfully.")
        #     except pylink.errors.JLinkException as e:
        #         print("Error resetting J-Link device:", e)


                                    
class ConnectionDialog(QDialog):
    # 定义信号
    connection_established = Signal()
    connection_disconnected = Signal()
    
    def __init__(self, parent=None):
        super(ConnectionDialog, self).__init__(parent)
        self.ui = Ui_dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        self.setWindowTitle(QCoreApplication.translate("main_window", "RTT2UART 连接配置"))
        self.setWindowModality(Qt.ApplicationModal)
        
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
        self.ui.checkBox_resettarget.stateChanged.connect(
            self.reset_target_change_slot)
        self.ui.radioButton_usb.clicked.connect(self.usb_selete_slot)
        self.ui.radioButton_existing.clicked.connect(
            self.existing_session_selete_slot)

        try:
            self.jlink = pylink.JLink()
        except:
            logger.error('Find jlink dll failed', exc_info=True)
            raise Exception(QCoreApplication.translate("main_window", "Find jlink dll failed !"))

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
        
        # 应用序列号设置
        self.ui.lineEdit_serialno.setText(self.config.get_serial_number())
        self.ui.lineEdit_ip.setText(self.config.get_ip_address())
        
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
            
            # 保存连接类型
            if self.ui.radioButton_usb.isChecked():
                self.config.set_connection_type('USB')
            elif self.ui.radioButton_tcpip.isChecked():
                self.config.set_connection_type('TCP/IP')
            elif self.ui.radioButton_existing.isChecked():
                self.config.set_connection_type('Existing')
            
            # 保存序列号和IP设置
            self.config.set_serial_number(self.ui.lineEdit_serialno.text())
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
            logger.warning(f"保存UI设置失败: {e}")
    
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
            logger.warning(f"保存主窗口设置失败: {e}")
    
    def _update_serial_forward_combo(self):
        """更新串口转发选择框的内容"""
        if not hasattr(self.ui, 'comboBox_SerialForward'):
            return
            
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
            
            if self.main_window and hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'tem_switch'):
                for i in range(MAX_TAB_SIZE):
                    tab_text = self.main_window.ui.tem_switch.tabText(i)
                    if i == 0:
                        display_text = f"{tab_text} ({QCoreApplication.translate('dialog', 'All Data')})"
                    elif i < 17:
                        display_text = f"{QCoreApplication.translate('dialog', 'Channel')} {tab_text}"
                    else:
                        # 对于筛选标签页，显示实际的筛选文本
                        if tab_text == QCoreApplication.translate("main_window", "filter"):
                            display_text = f"{QCoreApplication.translate('dialog', 'Filter')} {i-16}: ({QCoreApplication.translate('dialog', 'Not Set')})"
                        else:
                            display_text = f"{QCoreApplication.translate('dialog', 'Filter')} {i-16}: {tab_text}"
                    
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
                if self.ui.radioButton_usb.isChecked() and self.ui.checkBox_serialno.isChecked():
                    connect_para = self.ui.lineEdit_serialno.text()
                elif self.ui.radioButton_tcpip.isChecked():
                    connect_para = self.ui.lineEdit_ip.text()
                elif self.ui.radioButton_existing.isChecked():
                    connect_para = self.ui.checkBox__auto.isChecked()
                else:
                    connect_para = None
                    
                # 检查是否需要执行重置连接
                if self.ui.checkBox_resettarget.isChecked():
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("🔄 检测到重置连接选项，开始执行连接重置...")
                    self.perform_connection_reset()
                    # 重置完成后取消勾选
                    self.ui.checkBox_resettarget.setChecked(False)
                    self.config.set_reset_target(False)
                    self.config.save_config()
                
                self.start_state = True
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Stop"))
                
                self.rtt2uart = rtt_to_serial(self.worker, self.jlink, self.connect_type, connect_para, self.target_device, self.get_selected_port_name(
                ), self.ui.comboBox_baudrate.currentText(), device_interface, speed_list[self.ui.comboBox_Speed.currentIndex()], False)  # 重置后不再需要在rtt2uart中重置

                self.rtt2uart.start()
                
                # 设置JLink日志回调
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.rtt2uart.set_jlink_log_callback(self.main_window.append_jlink_log)
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Starting connection to device: %s") % str(self.target_device))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Connection type: %s") % str(self.connect_type))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Serial port: %s, Baud rate: %s") % (self.get_selected_port_name(), self.ui.comboBox_baudrate.currentText()))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "RTT connection started successfully"))
                
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
        device_ui = DeviceSelectDialog()
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
        if self.ui.checkBox_serialno.isChecked():
            self.ui.lineEdit_serialno.setVisible(True)
        else:
            self.ui.lineEdit_serialno.setVisible(False)
    
    def reset_target_change_slot(self):
        """重置连接选项变更处理"""
        is_checked = self.ui.checkBox_resettarget.isChecked()
        
        # 保存设置
        self.config.set_reset_target(is_checked)
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
                self.main_window.append_jlink_log(f"⚠️ 检测JLink冲突时出错: {e}")
            return []
    
    def force_release_jlink_driver(self):
        """强制释放JLink驱动"""
        try:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log("🔧 执行强制JLink驱动释放...")
            
            # 1. 检测冲突进程
            conflicts = self.detect_jlink_conflicts()
            if conflicts:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"🔍 检测到 {len(conflicts)} 个JLink相关进程:")
                    for proc in conflicts:
                        self.main_window.append_jlink_log(f"   - {proc['name']} (PID: {proc['pid']})")
                    self.main_window.append_jlink_log("💡 这些程序可能正在占用JLink驱动")
            
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
                                self.main_window.append_jlink_log(f"✅ 成功访问设备: {device_path}")
                        else:
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(f"⚠️ 无法访问设备: {device_path} (可能被占用)")
                                
                    except Exception as e:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(f"⚠️ 检查设备 {device_path} 时出错: {e}")
                
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"⚠️ Windows API驱动检查失败: {e}")
            
            # 3. 尝试重新枚举USB设备
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log("🔄 重新枚举USB设备...")
                
                # 通过重新扫描串口来触发USB设备重新枚举
                import serial.tools.list_ports
                ports_before = list(serial.tools.list_ports.comports())
                
                # 等待一下让系统稳定
                import time
                time.sleep(0.5)
                
                ports_after = list(serial.tools.list_ports.comports())
                
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"📊 USB设备重新枚举完成 (发现 {len(ports_after)} 个串口)")
                
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"⚠️ USB设备重新枚举失败: {e}")
            
            return True
            
        except Exception as e:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"❌ 强制释放JLink驱动失败: {e}")
            return False

    def perform_connection_reset(self):
        """执行强化的连接重置操作 - 解决JLink驱动抢占问题"""
        try:
            # 显示重置信息
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log("🔄 开始执行强化连接重置...")
            
            # 1. 停止当前连接（如果存在）
            if hasattr(self, 'rtt2uart') and self.rtt2uart is not None:
                try:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("📴 停止当前RTT连接...")
                    self.rtt2uart.stop()
                    self.rtt2uart = None
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("✅ RTT连接已停止")
                except Exception as e:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(f"⚠️ 停止RTT连接时出错: {e}")
            
            # 2. 强制释放JLink驱动（解决驱动抢占问题）
            if hasattr(self, 'jlink') and self.jlink is not None:
                try:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("🔧 强制释放JLink驱动...")
                    
                    # 强制断开所有连接
                    try:
                        if self.jlink.connected():
                            self.jlink.close()
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log("📴 JLink连接已断开")
                    except:
                        pass  # 忽略断开时的错误
                    
                    # 强制清理JLink对象
                    try:
                        del self.jlink
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log("🗑️ JLink对象已删除")
                    except:
                        pass
                    
                    self.jlink = None
                    
                    # 等待驱动释放
                    import time
                    time.sleep(1.0)  # 增加等待时间
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("⏳ 等待驱动释放...")
                    
                    # 强制垃圾回收
                    import gc
                    gc.collect()
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log("🧹 执行垃圾回收")
                    
                    # 执行强制驱动释放
                    self.force_release_jlink_driver()
                    
                    # 重新创建JLink对象
                    try:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log("🔄 重新创建JLink对象...")
                        
                        self.jlink = pylink.JLink()
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log("✅ JLink对象重新创建成功")
                        
                        # 尝试打开连接验证
                        try:
                            self.jlink.open()
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log("✅ JLink驱动重置成功，可以正常连接")
                            # 立即关闭，等待后续正常连接流程
                            self.jlink.close()
                        except Exception as e:
                            if hasattr(self.main_window, 'append_jlink_log'):
                                self.main_window.append_jlink_log(f"⚠️ JLink连接测试失败: {e}")
                                self.main_window.append_jlink_log("💡 提示: 可能仍有其他程序占用JLink")
                                
                                # 再次检测冲突并给出具体建议
                                conflicts = self.detect_jlink_conflicts()
                                if conflicts:
                                    self.main_window.append_jlink_log("🔍 发现以下JLink相关程序正在运行:")
                                    for proc in conflicts:
                                        self.main_window.append_jlink_log(f"   - {proc['name']} (PID: {proc['pid']})")
                                    self.main_window.append_jlink_log("💡 请关闭这些程序后重试连接")
                                else:
                                    self.main_window.append_jlink_log("💡 建议重新插拔JLink设备后重试")
                        
                    except Exception as e2:
                        if hasattr(self.main_window, 'append_jlink_log'):
                            self.main_window.append_jlink_log(f"❌ 重新创建JLink对象失败: {e2}")
                        self.jlink = None
                        
                except Exception as e:
                    if hasattr(self.main_window, 'append_jlink_log'):
                        self.main_window.append_jlink_log(f"⚠️ 强制释放JLink驱动时出错: {e}")
            
            # 3. 重置串口连接（清除串口状态）
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log("🔧 重置串口状态...")
                
                # 重新扫描串口
                self.port_scan()
                
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log("✅ 串口状态已重置")
                    
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"⚠️ 重置串口状态时出错: {e}")
            
            # 4. 清理缓存和状态
            try:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log("🧹 清理缓存和状态...")
                
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
                    self.main_window.append_jlink_log("✅ 缓存和状态已清理")
                    
            except Exception as e:
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.main_window.append_jlink_log(f"⚠️ 清理缓存时出错: {e}")
            
            # 5. 强化的驱动重置完成
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log("🎉 强化连接重置完成！")
                self.main_window.append_jlink_log("💡 如果仍然无法连接，请:")
                self.main_window.append_jlink_log("   1. 关闭所有JLink相关程序(J-Link Commander、J-Flash等)")
                self.main_window.append_jlink_log("   2. 重新插拔JLink设备")
                self.main_window.append_jlink_log("   3. 然后重试连接")
            
        except Exception as e:
            if hasattr(self.main_window, 'append_jlink_log'):
                self.main_window.append_jlink_log(f"❌ 连接重置失败: {e}")
            logger.error(f'Connection reset failed: {e}', exc_info=True)

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
        self.ui.lineEdit_serialno.setVisible(False)
        self.ui.lineEdit_ip.setVisible(False)
        self.ui.checkBox__auto.setVisible(True)
        # 通过existing_session方式接入时，以下功能无效，禁止使用
        self.ui.comboBox_Device.setEnabled(False)
        self.ui.pushButton_Selete_Device.setEnabled(False)
        self.ui.comboBox_Interface.setEnabled(False)
        self.ui.comboBox_Speed.setEnabled(False)
        self.ui.checkBox_resettarget.setEnabled(False)
        self.ui.checkBox_resettarget.setChecked(False)

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
            
            font = QFont("Consolas", self.main_window.ui.fontsize_box.value())  # 使用等宽字体
            font.setFixedPitch(True)
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
                        # QPlainTextEdit 直接用纯文本“增量”
                        from PySide6.QtWidgets import QPlainTextEdit
                        if isinstance(text_edit, QPlainTextEdit):
                            incremental_plain, current_total = self.worker._extract_increment_from_chunks(
                                self.worker.buffers[index],
                                self.worker.display_lengths[index],
                                max_insert_length
                            )
                            ui_start_time = time.time()
                            if incremental_plain:
                                text_edit.insertPlainText(incremental_plain)
                                self.worker.display_lengths[index] = current_total
                        else:
                            # QTextEdit 保持彩色路径
                            incremental_colored_data = ''.join(self.worker.colored_buffers[index])
                            if len(incremental_colored_data) > max_insert_length:
                                incremental_colored_data = incremental_colored_data[-max_insert_length:]
                            ui_start_time = time.time()
                            self._insert_ansi_text_fast(text_edit, incremental_colored_data, index)
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                        
                        # 📈 性能监控：UI更新结束
                        ui_time = (time.time() - ui_start_time) * 1000  # 转换为毫秒
                        if ui_time > 50:  # 大于50ms记录警告
                            data_size = len(incremental_colored_data) // 1024  # KB
                            logger.warning(f"[UI] UI更新耗时 - TAB{index}: {ui_time:.1f}ms, 数据量: {data_size}KB")
                    
                    elif len(self.worker.buffers[index]) > 0:
                        # 🚀 方案B：智能处理 — QPlainTextEdit 增量纯文本
                        from PySide6.QtWidgets import QPlainTextEdit
                        ui_start_time = time.time()
                        if isinstance(text_edit, QPlainTextEdit):
                            # 快进逻辑：积压过多时直接从尾部显示，避免显示严重滞后
                            backlog = self.worker.buffer_lengths[index] - self.worker.display_lengths[index]
                            if backlog > self.worker.backlog_fast_forward_threshold:
                                # 直接跳到尾部
                                tail_bytes = self.worker.fast_forward_tail
                                accumulated = ''.join(self.worker.buffers[index])
                                tail_text = accumulated[-tail_bytes:]
                                text_edit.insertPlainText(ansi_processor.remove_ansi_codes(tail_text))
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
                                text_edit.insertPlainText(ansi_processor.remove_ansi_codes(incremental_text))
                                self.worker.display_lengths[index] = current_total
                        else:
                            accumulated_data = ''.join(self.worker.buffers[index])
                            if len(accumulated_data) > max_insert_length:
                                display_data = accumulated_data[-max_insert_length:]
                            else:
                                display_data = accumulated_data
                            if self.worker._has_ansi_codes(display_data):
                                colored_html = self.worker._convert_ansi_to_html(display_data)
                                self._insert_ansi_text_fast(text_edit, colored_html, index)
                            else:
                                text_edit.insertPlainText(display_data)
                        
                        # 📈 性能监控：UI更新结束
                        ui_time = (time.time() - ui_start_time) * 1000  # 转换为毫秒
                        if ui_time > 50:  # 大于50ms记录警告
                            data_size = len(display_data) // 1024  # KB
                            logger.warning(f"[UI] UI更新耗时 - TAB{index}: {ui_time:.1f}ms, 数据量: {data_size}KB")
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                    
                    # 只在连接状态下清空已处理的缓冲区，断开连接后保留数据供查看
                    if hasattr(self.worker, 'colored_buffers') and is_connected:
                        self.worker.colored_buffer_lengths[index] = 0
                        self.worker.colored_buffers[index].clear()
                        
                except Exception as e:
                    # 异常处理：只在连接状态下清空缓冲区避免数据堆积
                    if hasattr(self.worker, 'colored_buffers') and is_connected:
                        try:
                            self.worker.colored_buffer_lengths[index] = 0
                            self.worker.colored_buffers[index].clear()
                        except Exception:
                            self.worker.colored_buffers[index] = []
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
                    QCoreApplication.translate("MainWindow", "提示"),
                    QCoreApplication.translate("MainWindow", "ALL窗口显示所有通道的汇总数据，不支持清屏操作。\n请切换到具体的RTT通道（0-15）进行清屏。")
                )


    def _insert_ansi_text_fast(self, text_edit, text, tab_index=None):
        """高性能ANSI文本插入 - 使用QTextCursor和QTextCharFormat"""
        try:
            # 在 QPlainTextEdit 上直接降级为纯文本，彻底避免富文本格式化开销
            try:
                from PySide6.QtWidgets import QPlainTextEdit
                if isinstance(text_edit, QPlainTextEdit):
                    clean_text = ansi_processor.remove_ansi_codes(text)
                    text_edit.insertPlainText(clean_text)
                    return
            except Exception:
                pass

            # 检查是否包含ANSI控制符
            if '\x1B[' not in text:
                # 纯文本，直接插入（最高性能）
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
                
                # 设置字体（保持等宽）
                font = QFont("Consolas", text_edit.font().pointSize())
                font.setFixedPitch(True)
                format.setFont(font)
                
                # 插入格式化文本
                cursor.insertText(text_part, format)
            
            # 更新文本编辑器的光标位置
            text_edit.setTextCursor(cursor)
            
        except Exception as e:
            # 如果ANSI处理失败，插入纯文本
            clean_text = ansi_processor.remove_ansi_codes(text)
            text_edit.insertPlainText(clean_text)

    # _cleanup_ui_text方法已移除，使用滑动文本块机制替代


    @Slot()
    def handleBufferUpdate(self):
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
        
        # 🚀 智能批量更新：根据容量利用率动态调整
        if hasattr(self.worker, 'get_buffer_memory_usage'):
            memory_info = self.worker.get_buffer_memory_usage()
            utilization = memory_info.get('capacity_utilization', 0)
            
            # 根据容量利用率调整更新策略
            if utilization > 80:  # 高利用率，减少更新
                max_updates = 1  # 只更新当前页面
            elif utilization > 60:  # 中等利用率
                max_updates = 2
            else:  # 低利用率，正常更新
                max_updates = 3
        else:
            max_updates = 3
        
        updated_count = 0
        for i in range(MAX_TAB_SIZE):
            if i != current_index and self.main_window.page_dirty_flags[i] and updated_count < max_updates:
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
        # 大量积压时的“追尾显示”参数
        self.backlog_fast_forward_threshold = 256 * 1024  # 积压超过256KB时快进
        self.fast_forward_tail = 64 * 1024                 # 只显示末尾64KB
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
            # 🚀 更频繁的刷新，避免缓冲区积累过多数据
            self.buffer_flush_timer.start(500)  # 每500ms刷新一次缓冲
            
        # 🔧 立即执行一次刷新，确保启动时的数据能及时写入
        QTimer.singleShot(100, self.flush_log_buffers)

    def flush_log_buffers(self):
        """定期刷新日志缓冲到文件（增强版本）"""
        try:
            # 创建字典的副本以避免运行时修改错误
            log_buffers_copy = dict(self.log_buffers)
            
            # 🔧 限制同时打开的文件数量，避免文件句柄耗尽
            max_files_per_flush = 10
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
            data = new_buffer.decode('gbk', errors='ignore')

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
                
                # 为UI显示创建带颜色的HTML格式文本
                if hasattr(self, 'colored_buffers'):
                    self._append_to_colored_buffer(index+1, self._convert_ansi_to_html(data))
                    self._append_to_colored_buffer(0, self._convert_ansi_to_html(''.join(buffer_parts)))
                    
            except Exception as e:
                # 如果ANSI处理失败，回退到原始文本处理
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
        """🚀 智能缓冲区追加：预分配 + 成倍扩容机制"""
        if index < len(self.buffers):
            # 防御：如果被外部代码误置为字符串，立即恢复为分块列表
            if not isinstance(self.buffers[index], list):
                self.buffers[index] = []
                self.buffer_lengths[index] = 0
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
        """🎨 智能彩色缓冲区追加：预分配 + 成倍扩容机制"""
        if hasattr(self, 'colored_buffers') and index < len(self.colored_buffers):
            # 防御：如果被误置为字符串，恢复为分块列表
            if not isinstance(self.colored_buffers[index], list):
                self.colored_buffers[index] = []
                self.colored_buffer_lengths[index] = 0
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
            logger.info(f"[PERF] 性能监控 - 刷新率: {refresh_rate:.1f}Hz, "
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
            if not search_word or search_word not in line:
                return line
            
            # 使用亮黄色背景高亮筛选关键词
            highlight_start = '\x1B[2;33m'  # 黄色背景
            highlight_end = '\x1B[0m'       # 重置
            
            # 替换所有匹配的关键词（保持大小写敏感）
            highlighted_line = line.replace(search_word, f"{highlight_start}{search_word}{highlight_end}")
            
            return highlighted_line
        except Exception:
            # 如果高亮失败，返回原始行
            return line

    def process_filter_lines(self, lines):
        """优化的过滤处理逻辑"""
        # 预编译搜索词以提高性能
        search_words = []
        for i in range(17, MAX_TAB_SIZE):
            try:
                if self.parent.main_window:
                    tag_text = self.parent.main_window.ui.tem_switch.tabText(i)
                    if tag_text != QCoreApplication.translate("main_window", "filter"):
                        search_words.append((i, tag_text))
            except:
                continue
        
        # 批量处理行
        for line in lines:
            if not line.strip():
                continue
                
            for i, search_word in search_words:
                if search_word in line:
                    filtered_data = line + '\n'
                    # 分块追加，避免大字符串反复拷贝
                    if i < len(self.buffers):
                        self.buffers[i].append(filtered_data)
                    
                    # 🎨 处理彩色筛选数据 - 保持ANSI颜色格式
                    if hasattr(self, 'colored_buffers') and len(self.colored_buffers) > i:
                        # 创建带高亮的彩色数据
                        highlighted_line = self._highlight_filter_text(line, search_word)
                        if i < len(self.colored_buffers):
                            self.colored_buffers[i].append(highlighted_line + '\n')
                    
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


from PySide6.QtCore import QRegularExpression, QRegularExpressionMatch
from PySide6.QtGui import QTextCharFormat, QSyntaxHighlighter

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.keywords = []
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(Qt.darkBlue)
        self.keyword_format.setFontWeight(QFont.Bold)
        self.keyword_format.setBackground(Qt.yellow)

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
    app = QApplication(sys.argv)
    
    # 加载并安装翻译文件
    translator = QTranslator()
    # 尝试从多个位置加载翻译文件
    translation_loaded = False
    
    # 尝试从当前目录加载（开发环境）
    if translator.load("xexunrtt.qm"):
        QCoreApplication.installTranslator(translator)
        translation_loaded = True
        print("Translation loaded from current directory.")
        # 测试翻译是否工作
        test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
        print(f"Translation test: 'JLink Debug Log' → '{test_text}'")
    # 如果当前目录加载失败，尝试从资源文件加载
    elif translator.load(QLocale.system(), ":/xexunrtt.qm"):
        QCoreApplication.installTranslator(translator)
        translation_loaded = True
        print("Translation loaded from resources.")
        # 测试翻译是否工作
        test_text = QCoreApplication.translate("main_window", "JLink Debug Log")
        print(f"Translation test: 'JLink Debug Log' → '{test_text}'")
    else:
        print("Failed to load translation file.")

    # 加载 Qt 内置翻译文件
    qt_translator = QTranslator()
    qt_translation_loaded = False
    
    # 尝试从当前目录加载（开发环境）
    if qt_translator.load("qt_zh_CN.qm"):
        QCoreApplication.installTranslator(qt_translator)
        qt_translation_loaded = True
        print("Qt translation loaded from current directory.")
    # 如果当前目录加载失败，尝试从资源文件加载
    elif qt_translator.load(QLocale.system(), ":/qt_zh_CN.qm"):
        QCoreApplication.installTranslator(qt_translator)
        qt_translation_loaded = True
        print("Qt translation loaded from resources.")
    else:
        print("Failed to load Qt translation file.")
    
    # 创建主窗口
    main_window = RTTMainWindow()
    
    # 在窗口显示前更新翻译
    if hasattr(main_window, '_update_ui_translations'):
        main_window._update_ui_translations()
    
    # 先显示主窗口（最大化）
    main_window.showMaximized()
    
    # 然后弹出连接配置对话框
    main_window.show_connection_dialog()

    sys.exit(app.exec())
