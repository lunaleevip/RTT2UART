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
import pickle
import os
import subprocess
import threading
import shutil
import re
import psutil

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
            
    def get_jlink_devices_list_file(self):
        if os.path.exists(r'JLinkDevicesBuildIn.xml') == True:
            return os.path.abspath('JLinkDevicesBuildIn.xml')
        else:
            raise Exception(QCoreApplication.translate("main_window", "Can not find device database !"))

    def parse_jlink_devices_list_file(self, path):
        parsefile = open(path, 'r')

        tree = ET.ElementTree(file=parsefile)

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
        self.close()

class EditableTabBar(QTabBar):
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
        self.ui.tem_switch.setTabBar(EditableTabBar())  # 使用自定义的可编辑标签栏
        
        # 清除整个TabWidget的工具提示
        self.ui.tem_switch.setToolTip("")
        
        self.tabText = [None] * MAX_TAB_SIZE
        self.highlighter = [PythonHighlighter] * MAX_TAB_SIZE
        for i in range(MAX_TAB_SIZE):
            page = QWidget()
            page.setToolTip("")  # 清除页面的工具提示
            
            # 🎨 智能双模式：QTextEdit支持ANSI颜色 + 性能优化
            text_edit = QTextEdit(page)  # 使用QTextEdit支持HTML格式化
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.NoWrap)  # 禁用换行，提升性能
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示水平滚动条
            text_edit.setToolTip("")  # 清除文本编辑器的工具提示
            
            # 🎯 关键性能优化设置 - 像JLink RTT Viewer一样支持大缓冲
            text_edit.document().setMaximumBlockCount(10000)  # 10000行缓冲，接近JLink RTT Viewer
            
            # 🎨 设置等宽字体，提升渲染性能
            font = QFont("新宋体", 10)
            font.setFixedPitch(True)  # 等宽字体
            text_edit.setFont(font)
            
            layout = QVBoxLayout(page)  # 创建布局管理器
            layout.addWidget(text_edit)  # 将 QTextEdit 添加到布局中
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
        self.set_style()
        
        # 创建定时器并连接到槽函数
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_periodic_task)
        self.timer.start(1000)  # 每1000毫秒（1秒）执行一次，进一步降低更新频率
        
        # 数据更新标志，用于智能刷新
        self.page_dirty_flags = [False] * MAX_TAB_SIZE
    
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
    
    def show_connection_dialog(self):
        """显示连接配置对话框"""
        if not self.connection_dialog:
            self.connection_dialog = ConnectionDialog(self)  # 设置主窗口为父窗口
            # 连接成功信号
            self.connection_dialog.connection_established.connect(self.on_connection_established)
            # 连接断开信号
            self.connection_dialog.connection_disconnected.connect(self.on_connection_disconnected)
        
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
            self.ui.cmd_buffer.addItems(settings['cmd'])
            
            for i in range(17, MAX_TAB_SIZE):
                if settings['filter'][i-17]:
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
        
        # 创建JLink日志文本框
        self.jlink_log_text = QTextEdit()
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
            
            # 可选：同时启用JLink的文件日志
            if hasattr(self.connection_dialog, 'rtt2uart') and self.connection_dialog.rtt2uart and hasattr(self.connection_dialog.rtt2uart, 'jlink'):
                try:
                    self.connection_dialog.rtt2uart.jlink.set_log_file("jlink_debug.log")
                    self.append_jlink_log(QCoreApplication.translate("main_window", "JLink file logging enabled: jlink_debug.log"))
                except Exception as e:
                    self.append_jlink_log(QCoreApplication.translate("main_window", "Failed to enable file logging: %s") % str(e))
        else:
            self.toggle_jlink_log_btn.setText(QCoreApplication.translate("main_window", "Enable Verbose Log"))
            # 禁用详细日志 - 恢复为WARNING级别
            jlink_logger.setLevel(logging.WARNING)
            self.append_jlink_log(QCoreApplication.translate("main_window", "JLink verbose logging disabled - only showing warnings and errors"))
    
    def append_jlink_log(self, message):
        """添加JLink日志消息"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        
        # 在GUI线程中更新文本
        self.jlink_log_text.append(formatted_message)
        
        # 自动滚动到底部
        scrollbar = self.jlink_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def resizeEvent(self, event):
        # 当窗口大小变化时更新布局大小
        # 由于现在使用了分割器布局，让Qt自动处理大小调整
        super().resizeEvent(event)

    def closeEvent(self, e):
        # 设置关闭标志，防止在关闭时显示连接对话框
        self._is_closing = True
        
        # 隐藏连接对话框，防止闪现
        if self.connection_dialog:
            self.connection_dialog.hide()
        
        if self.connection_dialog and self.connection_dialog.rtt2uart is not None and self.connection_dialog.start_state == True:
            self.connection_dialog.start()

        for i in range(MAX_TAB_SIZE):
            current_page_widget = self.ui.tem_switch.widget(i)
            if isinstance(current_page_widget, QWidget):
                text_edit = current_page_widget.findChild(QTextEdit)
                if text_edit:
                    text_edit.clear()

        if self.connection_dialog.rtt2uart and self.connection_dialog.rtt2uart.log_directory:
            log_directory = self.connection_dialog.rtt2uart.log_directory
            # 注释掉自动打开文件夹功能，避免关闭程序时弹出文件夹
            # if log_directory and os.listdir(log_directory):
            #     os.startfile(log_directory)
            # else:
            #     shutil.rmtree(log_directory)
            
            # 只清理空的日志目录，不自动打开
            try:
                if log_directory and os.path.exists(log_directory) and not os.listdir(log_directory):
                    shutil.rmtree(log_directory)
            except:
                pass
        self.connection_dialog.close()

        # 获取当前进程的所有子进程
        current_process = psutil.Process()
        children = current_process.children(recursive=True)

        # 关闭所有子进程
        for child in children:
            try:
                child.terminate()  # 发送 SIGTERM 信号终止子进程
                child.wait(timeout=1)  # 等待子进程退出
                if child.is_running():
                    # 如果子进程未能正常退出，发送 SIGKILL 信号强制终止子进程
                    child.kill()
                    child.wait()
            except psutil.NoSuchProcess:
                # 如果子进程已经退出，会抛出 NoSuchProcess 异常，忽略该异常
                pass

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
                text_edit = current_page_widget.findChild(QTextEdit)
                if text_edit:
                    self.highlighter[2].setKeywords([current_text])
                    
            # 检查字符串是否在 ComboBox 的列表中
            if current_text not in [self.ui.cmd_buffer.itemText(i) for i in range(self.ui.cmd_buffer.count())]:
                # 如果不在列表中，则将字符串添加到 ComboBox 中
                self.ui.cmd_buffer.addItem(current_text)
                if self.connection_dialog:
                    self.connection_dialog.settings['cmd'].append(current_text)

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
            text_edit = current_page_widget.findChild(QTextEdit)
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
            with open('cmd.txt', 'r', encoding='gbk') as file:
                for line in file:
                    self.ui.cmd_buffer.addItem(line.strip())  # 去除换行符并添加到 QComboBox 中
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
        
        # 更新JLink日志区域的样式
        self._update_jlink_log_style()
    
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
        
        if self.connection_dialog:
            self.connection_dialog.settings['fontsize'] = self.ui.fontsize_box.value()
                
            for i in range(17 , MAX_TAB_SIZE):
                tagText = self.ui.tem_switch.tabText(i)
                self.connection_dialog.settings['filter'][i-17] = tagText
            
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
                    # 查找页面中的QTextEdit并清除其工具提示
                    text_edit = page_widget.findChild(QTextEdit)
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
    def toggle_lock_v_checkbox(self):
        self.ui.LockV_checkBox.setChecked(not self.ui.LockV_checkBox.isChecked())
        if self.connection_dialog:
            self.connection_dialog.settings['lock_v'] = self.ui.LockV_checkBox.isChecked()
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
        
        self.setting_file_path = os.path.join(os.getcwd(), "settings")

        self.start_state = False
        self.target_device = None
        self.rtt2uart = None
        self.connect_type = None
        # 默认Existing Session方式接入使能Auto reconnect
        self.ui.checkBox__auto.setChecked(True)
        # 默认选择'USB'方式接入
        self.ui.radioButton_usb.setChecked(True)
        self.usb_selete_slot()

        self.ui.comboBox_Interface.addItem("JTAG")
        self.ui.comboBox_Interface.addItem("SWD")
        self.ui.comboBox_Interface.addItem("cJTAG")
        self.ui.comboBox_Interface.addItem("FINE")

        for i in range(len(speed_list)):
            self.ui.comboBox_Speed.addItem(str(speed_list[i]) + " kHz")

        for i in range(len(baudrate_list)):
            self.ui.comboBox_baudrate.addItem(str(baudrate_list[i]))

        self.port_scan()

        self.settings = {'device': [], 'device_index': 0, 'interface': 0,
                         'speed': 0, 'port': 0, 'buadrate': 0, 'lock_h':1, 'lock_v':0, 'light_mode':0, 'fontsize':9, 'filter':[None] * (MAX_TAB_SIZE - 17), 'cmd':[], 'serial_forward_tab': -1, 'serial_forward_mode': 'LOG'}

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
        

        # 检查是否存在上次配置，存在则加载
        if os.path.exists(self.setting_file_path) == True:
            with open(self.setting_file_path, 'rb') as f:
                self.settings = pickle.load(f)

            f.close()

            # 应用上次配置
            if len(self.settings['device']):
                self.ui.comboBox_Device.addItems(self.settings['device'])
                self.target_device = self.settings['device'][self.settings['device_index']]
            self.ui.comboBox_Device.setCurrentIndex(
                self.settings['device_index'])
            self.ui.comboBox_Interface.setCurrentIndex(
                self.settings['interface'])
            self.ui.comboBox_Speed.setCurrentIndex(self.settings['speed'])
            self.ui.comboBox_Port.setCurrentIndex(self.settings['port'])
            self.ui.comboBox_baudrate.setCurrentIndex(
                self.settings['buadrate'])
            
            # 这些设置将在主窗口创建后应用
            # self.main_window.ui.LockH_checkBox.setChecked(self.settings['lock_h'])
            # self.main_window.ui.LockV_checkBox.setChecked(self.settings['lock_v'])
            # self.main_window.ui.light_checkbox.setChecked(self.settings['light_mode'])
            # self.main_window.ui.fontsize_box.setValue(self.settings['fontsize'])
            # self.main_window.ui.cmd_buffer.addItems(self.settings['cmd'])
            # 
            # for i in range(17 , MAX_TAB_SIZE):
            #         tagText = self.main_window.ui.tem_switch.tabText(i)
            #         if self.settings['filter'][i-17]:
            #             self.main_window.ui.tem_switch.setTabText(i, self.settings['filter'][i-17])

        else:
            logger.info('Setting file not exist', exc_info=True)
            self.ui.comboBox_Interface.setCurrentIndex(1)
            self.settings['interface'] = 1
            self.ui.comboBox_Speed.setCurrentIndex(19)
            self.settings['speed'] = 19
            self.ui.comboBox_baudrate.setCurrentIndex(16)
            self.settings['buadrate'] = 16

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
            if self.jlink._library._path is not None and os.path.exists(r'JLinkDevicesBuildIn.xml') == False:
                path_env = os.path.dirname(self.jlink._library._path)
                env = os.environ

                if self.jlink._library._windows or self.jlink._library._cygwin:
                    jlink_env = {'PATH': path_env}
                    env.update(jlink_env)

                    cmd = 'JLink.exe -CommandFile JLinkCommandFile.jlink'

                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE

                    subprocess.run(cmd, check=True, startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    subprocess.kill()

                elif sys.platform.startswith('linux'):
                    jlink_env = {}
                    cmd = 'JLinkExe -CommandFile JLinkCommandFile.jlink'
                elif sys.platform.startswith('darwin'):
                    jlink_env = {}
                    cmd = 'JLinkExe -CommandFile JLinkCommandFile.jlink'

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
                with open(self.setting_file_path, 'wb') as f:
                    pickle.dump(self.settings, f)
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
                    
                self.start_state = True
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Stop"))
                
                self.rtt2uart = rtt_to_serial(self.ui, self.jlink, self.connect_type, connect_para, self.target_device, self.get_selected_port_name(
                ), self.ui.comboBox_baudrate.currentText(), device_interface, speed_list[self.ui.comboBox_Speed.currentIndex()], self.ui.checkBox_resettarget.isChecked())

                self.rtt2uart.start()
                
                # 设置JLink日志回调
                if hasattr(self.main_window, 'append_jlink_log'):
                    self.rtt2uart.set_jlink_log_callback(self.main_window.append_jlink_log)
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Starting connection to device: %s") % str(self.target_device))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Connection type: %s") % str(self.connect_type))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "Serial port: %s, Baud rate: %s") % (self.get_selected_port_name(), self.ui.comboBox_baudrate.currentText()))
                    self.main_window.append_jlink_log(QCoreApplication.translate("main_window", "RTT connection started successfully"))
                
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
                
                # 断开连接时不自动显示连接对话框
                # 用户可以通过菜单或快捷键手动打开连接设置
                pass

                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
            except:
                logger.error('Stop rtt2uart failed', exc_info=True)
                pass
    
    # 删除了不再需要的_apply_saved_settings_to_main_window方法

    def target_device_selete(self):
        device_ui = DeviceSelectDialog()
        device_ui.exec()
        self.target_device = device_ui.get_target_device()

        if self.target_device and self.target_device not in self.settings['device']:
            self.settings['device'].append(self.target_device)
            self.ui.comboBox_Device.addItem(self.target_device)
        
        # 选择新添加的项目
        index = self.ui.comboBox_Device.findText(self.target_device)
        if index != -1:
            self.ui.comboBox_Device.setCurrentIndex(index)
        # 刷新显示
        self.ui.comboBox_Device.update()
        
    def device_change_slot(self, index):
        self.settings['device_index'] = index
        self.target_device = self.ui.comboBox_Device.currentText()

    def interface_change_slot(self, index):
        self.settings['interface'] = index

    def speed_change_slot(self, index):
        self.settings['speed'] = index

    def port_change_slot(self, index):
        self.settings['port'] = index

    def buadrate_change_slot(self, index):
        self.settings['buadrate'] = index

    def serial_no_change_slot(self):
        if self.ui.checkBox_serialno.isChecked():
            self.ui.lineEdit_serialno.setVisible(True)
        else:
            self.ui.lineEdit_serialno.setVisible(False)

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
        if len(self.worker.buffers[index]) <= 0:
            return
        
        if not self.main_window:
            return
            
        current_page_widget = self.main_window.ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            # 优先使用QTextEdit支持ANSI颜色显示
            text_edit = current_page_widget.findChild(QTextEdit)
            if not text_edit:
                from PySide6.QtWidgets import QPlainTextEdit
                text_edit = current_page_widget.findChild(QPlainTextEdit)  # 后备方案
            
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
                        text_edit.clear()
                elif index != 2:
                    keywords = []
                    for i in range(MAX_TAB_SIZE):
                        if i >= 17:
                            keywords.append(self.main_window.ui.tem_switch.tabText(i))
                    self.main_window.highlighter[index].setKeywords(keywords)
                    
                # 🎨 智能ANSI颜色支持 + 高性能文本处理
                try:
                    max_insert_length = 16384  # 16KB单次插入限制
                    
                    # 检查是否有ANSI彩色数据
                    has_colored_data = (hasattr(self.worker, 'colored_buffers') and 
                                      self.worker.colored_buffers[index])
                    
                    if has_colored_data and len(self.worker.colored_buffers[index]) > 0:
                        # 🚀 方案A：高性能ANSI彩色显示（使用QTextCursor+QTextCharFormat）
                        colored_data = self.worker.colored_buffers[index]
                        if len(colored_data) > max_insert_length:
                            colored_data = colored_data[-max_insert_length:]
                        
                        # 使用高性能原生Qt格式化，传入tab索引用于清屏控制
                        self._insert_ansi_text_fast(text_edit, colored_data, index)
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                    
                    elif self.worker.buffers[index]:
                        # 🚀 方案B：高性能纯文本显示（使用QPlainTextEdit模式）
                        data_to_insert = self.worker.buffers[index]
                        if len(data_to_insert) > max_insert_length:
                            data_to_insert = data_to_insert[-max_insert_length:]
                        
                        # 使用QTextEdit的高性能纯文本插入
                        text_edit.insertPlainText(data_to_insert)
                        
                        # 自动滚动到底部
                        text_edit.verticalScrollBar().setValue(
                            text_edit.verticalScrollBar().maximum())
                    
                    # 清空已处理的缓冲区
                    if hasattr(self.worker, 'colored_buffers'):
                        self.worker.colored_buffers[index] = ""
                        
                except Exception as e:
                    # 异常处理：清空缓冲区避免数据堆积
                    if hasattr(self.worker, 'colored_buffers'):
                        self.worker.colored_buffers[index] = ""
                    print(f"文本更新异常: {e}")  # 调试信息
                
                # 清空当前缓冲区（数据已经显示）
                self.worker.buffers[index] = ""
                # 标记页面需要更新
                if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'page_dirty_flags'):
                    self.main_window.page_dirty_flags[index] = True

                # 激进的文本长度管理：每次都检查并严格控制
                text_length = len(text_edit.toPlainText())
                max_allowed_length = MAX_UI_TEXT_LENGTH  # 1MB限制，更激进
                
                if text_length > max_allowed_length:
                    # 激进截取：只保留最新的50%数据
                    cursor = text_edit.textCursor()
                    cursor.movePosition(QTextCursor.MoveOperation.Start)
                    
                    # 删除前50%的内容
                    chars_to_remove = int(text_length * 0.5)
                    cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, chars_to_remove)
                    cursor.removeSelectedText()
                    
                    # 移动到文档末尾
                    cursor.movePosition(QTextCursor.MoveOperation.End)
                    text_edit.setTextCursor(cursor)
                    
                    print(f"Text truncated: {text_length} -> {len(text_edit.toPlainText())} chars")

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
                # 优先使用QTextEdit支持ANSI颜色显示
                text_edit = current_page_widget.findChild(QTextEdit)
                if not text_edit:
                    from PySide6.QtWidgets import QPlainTextEdit
                    text_edit = current_page_widget.findChild(QPlainTextEdit)  # 后备方案
                
                if text_edit and hasattr(text_edit, 'clear'):
                    text_edit.clear()
                # 同时清空对应的缓冲区
                if hasattr(self, 'worker') and self.worker:
                    if current_index < len(self.worker.buffers):
                        self.worker.buffers[current_index] = ""
                    if hasattr(self.worker, 'colored_buffers') and current_index < len(self.worker.colored_buffers):
                        self.worker.colored_buffers[current_index] = ""

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

    def _cleanup_ui_text(self):
        """定期清理UI文本内容，防止无限累积"""
        max_ui_text_length = MAX_UI_TEXT_LENGTH  # 1MB UI文本限制
        
        for i in range(MAX_TAB_SIZE):
            try:
                text_edit = self.main_window.ui.tem_switch.widget(i)
                if hasattr(text_edit, 'toPlainText'):
                    text_length = len(text_edit.toPlainText())
                    if text_length > max_ui_text_length:
                        # 激进清理：只保留最新的25%数据
                        cursor = text_edit.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.Start)
                        
                        # 删除前75%的内容
                        chars_to_remove = int(text_length * 0.75)
                        cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor, chars_to_remove)
                        cursor.removeSelectedText()
                        
                        # 移动到文档末尾
                        cursor.movePosition(QTextCursor.MoveOperation.End)
                        text_edit.setTextCursor(cursor)
                        
                        print(f"UI cleanup: TAB {i} text truncated from {text_length} to {len(text_edit.toPlainText())} chars")
            except Exception as e:
                # 忽略清理过程中的错误
                pass


    @Slot()
    def handleBufferUpdate(self):
        # 智能更新：只刷新有数据变化的页面
        if not self.main_window:
            return
            
        # 定期清理UI文本内容，防止无限累积
        if not hasattr(self, 'cleanup_counter'):
            self.cleanup_counter = 0
        self.cleanup_counter += 1
        
        # 每10次更新执行一次UI清理
        if self.cleanup_counter % 10 == 0:
            self._cleanup_ui_text()
            
        current_index = self.main_window.ui.tem_switch.currentIndex()
        
        # 优先更新当前显示的页面
        if self.main_window.page_dirty_flags[current_index]:
            self.switchPage(current_index)
            self.main_window.page_dirty_flags[current_index] = False
        
        # 批量更新其他有变化的页面（限制每次最多更新3个）
        updated_count = 0
        for i in range(MAX_TAB_SIZE):
            if i != current_index and self.main_window.page_dirty_flags[i] and updated_count < 3:
                self.switchPage(i)
                self.main_window.page_dirty_flags[i] = False
                updated_count += 1
   

class Worker(QObject):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.byte_buffer = [bytearray() for _ in range(16)]  # 创建MAX_TAB_SIZE个缓冲区
        
        # 智能缓冲区管理
        self.buffers = [""] * MAX_TAB_SIZE  # 创建MAX_TAB_SIZE个缓冲区
        self.colored_buffers = [""] * MAX_TAB_SIZE  # 创建带颜色的缓冲区
        
        # 缓冲区大小限制（QPlainTextEdit自动管理，无需手动历史缓冲）
        self.MAX_DISPLAY_BUFFER_SIZE = MAX_UI_TEXT_LENGTH  # 1MB显示缓冲区
        
        # 性能优化：文件I/O缓冲
        self.log_buffers = {}  # 日志文件缓冲
        # 延迟创建定时器，确保在正确的线程中
        self.buffer_flush_timer = None
        
        # 性能计数器
        self.update_counter = 0

    def start_flush_timer(self):
        """启动日志刷新定时器"""
        if self.buffer_flush_timer is None:
            self.buffer_flush_timer = QTimer()
            self.buffer_flush_timer.timeout.connect(self.flush_log_buffers)
            self.buffer_flush_timer.start(1000)  # 每秒刷新一次缓冲

    def flush_log_buffers(self):
        """定期刷新日志缓冲到文件（线程安全版本）"""
        try:
            # 创建字典的副本以避免运行时修改错误
            log_buffers_copy = dict(self.log_buffers)
            for filepath, content in log_buffers_copy.items():
                if content:
                    try:
                        with open(filepath, 'a', encoding='utf-8') as f:
                            f.write(content)
                        # 安全地清空缓冲区
                        if filepath in self.log_buffers:
                            self.log_buffers[filepath] = ""
                    except Exception:
                        pass
        except RuntimeError:
            # 如果字典在迭代过程中被修改，跳过这次刷新
            pass

    def write_to_log_buffer(self, filepath, content):
        """写入日志缓冲而不是直接写文件"""
        if filepath not in self.log_buffers:
            self.log_buffers[filepath] = ""
        self.log_buffers[filepath] += content



    def _aggressive_manage_buffer_size(self, index):
        """激进的缓冲区大小管理：立即限制大小"""
        max_buffer_size = 8192  # 8KB限制，更激进
        
        # 检查普通缓冲区
        if len(self.buffers[index]) > max_buffer_size:
            # 只保留最新的数据
            self.buffers[index] = self.buffers[index][-max_buffer_size:]
            
        # 检查彩色缓冲区
        if hasattr(self, 'colored_buffers') and len(self.colored_buffers[index]) > max_buffer_size:
            self.colored_buffers[index] = self.colored_buffers[index][-max_buffer_size:]

    @Slot(int, str)
    def addToBuffer(self, index, string):
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
                
                # 存储纯文本到buffers（用于日志和转发）
                self.buffers[index+1] += clean_data
                self.buffers[0] += ''.join(clean_buffer_parts)
                
                # 为UI显示创建带颜色的HTML格式文本
                if hasattr(self, 'colored_buffers'):
                    self.colored_buffers[index+1] += self._convert_ansi_to_html(data)
                    self.colored_buffers[0] += self._convert_ansi_to_html(''.join(buffer_parts))
                    
            except Exception as e:
                # 如果ANSI处理失败，回退到原始文本处理
                self.buffers[index+1] += data
                self.buffers[0] += ''.join(buffer_parts)
                if hasattr(self, 'colored_buffers'):
                    self.colored_buffers[index+1] += data
                    self.colored_buffers[0] += ''.join(buffer_parts)
            
            # 激进的缓冲区大小管理：立即限制缓冲区大小
            self._aggressive_manage_buffer_size(index+1)
            self._aggressive_manage_buffer_size(0)
            
            # 标记页面需要更新（降低更新频率）
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

            # 优化：使用缓冲写入日志
            log_filepath = self.parent.rtt2uart.rtt_log_filename + '_' + str(index) + '.log'
            self.write_to_log_buffer(log_filepath, data)

            # 优化过滤逻辑：减少嵌套循环
            if data.strip():  # 只处理非空数据
                lines = [line for line in data.split('\n') if line.strip()]
                self.process_filter_lines(lines)

            self.finished.emit()

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
                    self.buffers[i] += filtered_data
                    
                    # 🎨 处理彩色筛选数据 - 保持ANSI颜色格式
                    if hasattr(self, 'colored_buffers') and len(self.colored_buffers) > i:
                        # 创建带高亮的彩色数据
                        highlighted_line = self._highlight_filter_text(line, search_word)
                        self.colored_buffers[i] += highlighted_line + '\n'
                    
                    # 标记页面需要更新
                    if hasattr(self.parent, 'main_window') and self.parent.main_window and hasattr(self.parent.main_window, 'page_dirty_flags'):
                        self.parent.main_window.page_dirty_flags[i] = True
                    
                    # 串口转发功能：转发筛选后的数据
                    if hasattr(self.parent, 'rtt2uart') and self.parent.rtt2uart:
                        self.parent.rtt2uart.add_tab_data_for_forwarding(i, filtered_data)
                    
                    # 缓冲写入搜索日志（移除ANSI后保存）
                    new_path = replace_special_characters(search_word)
                    search_log_filepath = self.parent.rtt2uart.rtt_log_filename + '_' + new_path + '.log'
                    # 写入日志时移除ANSI控制符
                    clean_line = ansi_processor.remove_ansi_codes(line)
                    self.write_to_log_buffer(search_log_filepath, clean_line + '\n')

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
