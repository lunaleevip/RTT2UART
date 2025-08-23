from pickle import NONE
import sys
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6 import QtGui
from PySide6 import QtCore
from PySide6.QtCore import QObject
from PySide6.QtGui import QFont, QIcon, QAction
from PySide6.QtNetwork import QLocalSocket, QLocalServer
import qdarkstyle
from ui_rtt2uart import Ui_dialog
from ui_sel_device import Ui_Dialog
from ui_xexunrtt import Ui_xexun_rtt
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

class XexunRTTWindow(QWidget):
    def __init__(self, main):
        super(XexunRTTWindow, self).__init__()
        self.main = main
        
        # 先设置原有的UI
        self.ui = Ui_xexun_rtt()
        self.ui.setupUi(self)
        
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
        
        # 清除原有布局并设置新布局
        if self.layout():
            QWidget().setLayout(self.layout())
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        
        # 设置窗口标志以显示最大化按钮
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
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
            
            text_edit = QTextEdit(page)  # 在页面上创建 QTextEdit 实例
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.NoWrap)  # 禁用自动换行
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示水平滚动条
            text_edit.setToolTip("")  # 清除文本编辑器的工具提示
            
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
        self.timer.start(500)  # 每500毫秒（0.5秒）执行一次，降低CPU使用率
        
        # 数据更新标志，用于智能刷新
        self.page_dirty_flags = [False] * MAX_TAB_SIZE
    
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
            if hasattr(self.main, 'rtt2uart') and self.main.rtt2uart and hasattr(self.main.rtt2uart, 'jlink'):
                try:
                    self.main.rtt2uart.jlink.set_log_file("jlink_debug.log")
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
        if self.main.rtt2uart is not None and self.main.start_state == True:
            self.main.start()

        for i in range(MAX_TAB_SIZE):
            current_page_widget = self.ui.tem_switch.widget(i)
            if isinstance(current_page_widget, QWidget):
                text_edit = current_page_widget.findChild(QTextEdit)
                if text_edit:
                    text_edit.clear()

        if self.main.rtt2uart and self.main.rtt2uart.log_directory:
            log_directory = self.main.rtt2uart.log_directory
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
        self.main.close()

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
        self.main.switchPage(index)
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
        
        bytes_written = self.main.jlink.rtt_write(0, gbk_data)
        self.main.rtt2uart.write_bytes0 = bytes_written
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
                self.main.settings['cmd'].append(current_text)

    def on_dis_connect_clicked(self):
        if self.main.rtt2uart is not None and self.main.start_state == True:
            self.main.start()

    def on_re_connect_clicked(self):
        if self.main.rtt2uart is not None and self.main.start_state == True:
            self.main.start()
            
        self.main.show()

    def on_clear_clicked(self):
        index = self.ui.tem_switch.currentIndex()
        current_page_widget = self.ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            text_edit = current_page_widget.findChild(QTextEdit)
            if text_edit:
                text_edit.clear()

    def on_openfolder_clicked(self):
        os.startfile(self.main.rtt2uart.log_directory)

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
        self.main.settings['light_mode'] = self.ui.light_checkbox.isChecked()
        
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

    def update_periodic_task(self):
        
        title = QCoreApplication.translate("main_window", u"XexunRTT")
        title += "\t"
        
        if self.main.rtt2uart is not None and self.main.start_state == True:
            title += QCoreApplication.translate("main_window", u"status:Started")
        else:
            title += QCoreApplication.translate("main_window", u"status:Stoped")

        title += "\t"
        
        readed = 0
        writed = 0
        if self.main.rtt2uart is not None:
            readed = self.main.rtt2uart.read_bytes0 + self.main.rtt2uart.read_bytes1
            writed = self.main.rtt2uart.write_bytes0
        
        title += QCoreApplication.translate("main_window", u"Readed:") + "%8u" % readed
        title += "\t"
        title += QCoreApplication.translate("main_window", u"Writed:") + "%4u" % writed
        title += " "
        
        self.setWindowTitle(title)
        
        self.main.settings['fontsize'] = self.ui.fontsize_box.value()
            
        for i in range(17 , MAX_TAB_SIZE):
            tagText = self.ui.tem_switch.tabText(i)
            self.main.settings['filter'][i-17] = tagText
            
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
        self.main.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
    def toggle_lock_v_checkbox(self):
        self.ui.LockV_checkBox.setChecked(not self.ui.LockV_checkBox.isChecked())
        self.main.settings['lock_v'] = self.ui.LockV_checkBox.isChecked()
    def toggle_style_checkbox(self):
        self.ui.light_checkbox.setChecked(not self.ui.light_checkbox.isChecked())
        self.set_style()
        
    def device_restart(self):
        return
        # if self.main.rtt2uart.jlink:
        #     try:
        #         jlink = self.main.rtt2uart.jlink
        #         jlink.open()
        #         jlink.reset(halt=True) #实测效果不理想
        #         print("J-Link device start successfully.")
        #     except pylink.errors.JLinkException as e:
        #         print("Error resetting J-Link device:", e)
                                    
class MainWindow(QDialog):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_dialog()
        self.ui.setupUi(self)

        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
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
                         'speed': 0, 'port': 0, 'buadrate': 0, 'lock_h':1, 'lock_v':0, 'light_mode':0, 'fontsize':9, 'filter':[None] * (MAX_TAB_SIZE - 17), 'cmd':[]}

        self.xexunrtt = XexunRTTWindow(self)
        self.xexunrtt.showMaximized()
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
            
            self.xexunrtt.ui.LockH_checkBox.setChecked(self.settings['lock_h'])
            self.xexunrtt.ui.LockV_checkBox.setChecked(self.settings['lock_v'])
            self.xexunrtt.ui.light_checkbox.setChecked(self.settings['light_mode'])
            self.xexunrtt.ui.fontsize_box.setValue(self.settings['fontsize'])
            self.xexunrtt.ui.cmd_buffer.addItems(self.settings['cmd'])
            
            for i in range(17 , MAX_TAB_SIZE):
                    tagText = self.xexunrtt.ui.tem_switch.tabText(i)
                    if self.settings['filter'][i-17]:
                        self.xexunrtt.ui.tem_switch.setTabText(i, self.settings['filter'][i-17])

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
            # 停止RTT连接
            if self.rtt2uart is not None and self.start_state == True:
                try:
                    self.rtt2uart.stop()
                except Exception as ex:
                    logger.error(f"Error stopping RTT: {ex}")
            
            # 关闭RTT窗口
            if self.xexunrtt is not None:
                try:
                    self.xexunrtt.close()
                except Exception as ex:
                    logger.error(f"Error closing RTT window: {ex}")
            
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

    def port_scan(self):
        port_list = list(serial.tools.list_ports.comports())
        self.ui.comboBox_Port.clear()
        port_list.sort()
        for port in port_list:
            try:
                s = serial.Serial(port[0])
                s.close()
                self.ui.comboBox_Port.addItem(port[0])
            except (OSError, serial.SerialException):
                pass

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
                
                self.rtt2uart = rtt_to_serial(self.ui, self.jlink, self.connect_type, connect_para, self.target_device, self.ui.comboBox_Port.currentText(
                ), self.ui.comboBox_baudrate.currentText(), device_interface, speed_list[self.ui.comboBox_Speed.currentIndex()], self.ui.checkBox_resettarget.isChecked())

                # 设置JLink日志回调
                if hasattr(self.xexunrtt, 'append_jlink_log'):
                    self.rtt2uart.set_jlink_log_callback(self.xexunrtt.append_jlink_log)
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "Starting connection to device: %s") % str(self.target_device))
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "Connection type: %s") % str(self.connect_type))
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "Serial port: %s, Baud rate: %s") % (self.ui.comboBox_Port.currentText(), self.ui.comboBox_baudrate.currentText()))

                self.rtt2uart.start()
                
                if hasattr(self.xexunrtt, 'append_jlink_log'):
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "RTT connection started successfully"))
                
                self.hide()
                #self.xexunrtt.show()

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
                    

                if hasattr(self.xexunrtt, 'append_jlink_log'):
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "Stopping RTT connection..."))
                
                self.rtt2uart.stop()
                #self.show()

                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
                
                if hasattr(self.xexunrtt, 'append_jlink_log'):
                    self.xexunrtt.append_jlink_log(QCoreApplication.translate("main_window", "RTT connection stopped"))
            except:
                logger.error('Stop rtt2uart failed', exc_info=True)
                pass

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
        if len(self.worker.buffers[index]) <= 0:
            return
        
        current_page_widget = self.xexunrtt.ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            text_edit = current_page_widget.findChild(QTextEdit)
            font = QFont("新宋体", self.xexunrtt.ui.fontsize_box.value())  # 设置字体
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
                    self.xexunrtt.highlighter[index].setKeywords([self.xexunrtt.ui.tem_switch.tabText(index)])
                    if self.xexunrtt.tabText[index] != self.xexunrtt.ui.tem_switch.tabText(index):
                        self.xexunrtt.tabText[index] = self.xexunrtt.ui.tem_switch.tabText(index)
                        text_edit.clear()
                elif index != 2:
                    keywords = []
                    for i in range(MAX_TAB_SIZE):
                        if i >= 17:
                            keywords.append(self.xexunrtt.ui.tem_switch.tabText(i))
                    self.xexunrtt.highlighter[index].setKeywords(keywords)
                    
                text_edit.insertPlainText(self.worker.buffers[index])
                self.worker.buffers[index] = ""
                # 标记页面需要更新
                if hasattr(self, 'xexunrtt') and hasattr(self.xexunrtt, 'page_dirty_flags'):
                    self.xexunrtt.page_dirty_flags[index] = True

                text_length = len(text_edit.toPlainText())
                if text_length > MAX_TEXT_LENGTH:
                    # 截取文本长度
                    new_text = text_edit.toPlainText()[(int)(MAX_TEXT_LENGTH/2):]
                    text_edit.clear()
                    text_edit.insertPlainText(new_text)
                    #print("new_text_length:" + str(len(new_text)) + ", old_len:" + str(text_length))

                # 恢复滚动条的值
                if self.xexunrtt.ui.LockV_checkBox.isChecked():
                    text_edit.verticalScrollBar().setValue(vscroll)

                if self.xexunrtt.ui.LockH_checkBox.isChecked():
                    text_edit.horizontalScrollBar().setValue(hscroll)
            else:
                print("No QTextEdit found on page:", index)
        else:
            print("Invalid page index or widget type:", index)


    @Slot()
    def handleBufferUpdate(self):
        # 智能更新：只刷新有数据变化的页面
        current_index = self.xexunrtt.ui.tem_switch.currentIndex()
        
        # 优先更新当前显示的页面
        if self.xexunrtt.page_dirty_flags[current_index]:
            self.switchPage(current_index)
            self.xexunrtt.page_dirty_flags[current_index] = False
        
        # 批量更新其他有变化的页面（限制每次最多更新3个）
        updated_count = 0
        for i in range(MAX_TAB_SIZE):
            if i != current_index and self.xexunrtt.page_dirty_flags[i] and updated_count < 3:
                self.switchPage(i)
                self.xexunrtt.page_dirty_flags[i] = False
                updated_count += 1
   

class Worker(QObject):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.byte_buffer = [bytearray() for _ in range(16)]  # 创建MAX_TAB_SIZE个缓冲区
        self.buffers = [""] * MAX_TAB_SIZE  # 创建MAX_TAB_SIZE个缓冲区
        
        # 性能优化：文件I/O缓冲
        self.log_buffers = {}  # 日志文件缓冲
        # 延迟创建定时器，确保在正确的线程中
        self.buffer_flush_timer = None

    def start_flush_timer(self):
        """启动日志刷新定时器"""
        if self.buffer_flush_timer is None:
            self.buffer_flush_timer = QTimer()
            self.buffer_flush_timer.timeout.connect(self.flush_log_buffers)
            self.buffer_flush_timer.start(1000)  # 每秒刷新一次缓冲

    def flush_log_buffers(self):
        """定期刷新日志缓冲到文件"""
        for filepath, content in self.log_buffers.items():
            if content:
                try:
                    with open(filepath, 'a', encoding='utf-8') as f:
                        f.write(content)
                    self.log_buffers[filepath] = ""
                except Exception:
                    pass

    def write_to_log_buffer(self, filepath, content):
        """写入日志缓冲而不是直接写文件"""
        if filepath not in self.log_buffers:
            self.log_buffers[filepath] = ""
        self.log_buffers[filepath] += content

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
            
            self.buffers[index+1] += data
            self.buffers[0] += ''.join(buffer_parts)
            
            # 标记页面需要更新
            if hasattr(self.parent, 'xexunrtt') and hasattr(self.parent.xexunrtt, 'page_dirty_flags'):
                self.parent.xexunrtt.page_dirty_flags[index+1] = True
                self.parent.xexunrtt.page_dirty_flags[0] = True

            # 优化：使用缓冲写入日志
            log_filepath = self.parent.rtt2uart.rtt_log_filename + '_' + str(index) + '.log'
            self.write_to_log_buffer(log_filepath, data)

            # 优化过滤逻辑：减少嵌套循环
            if data.strip():  # 只处理非空数据
                lines = [line for line in data.split('\n') if line.strip()]
                self.process_filter_lines(lines)

            self.finished.emit()

    def process_filter_lines(self, lines):
        """优化的过滤处理逻辑"""
        # 预编译搜索词以提高性能
        search_words = []
        for i in range(17, MAX_TAB_SIZE):
            try:
                tag_text = self.parent.xexunrtt.ui.tem_switch.tabText(i)
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
                    self.buffers[i] += line + '\n'
                    # 标记页面需要更新
                    if hasattr(self.parent, 'xexunrtt') and hasattr(self.parent.xexunrtt, 'page_dirty_flags'):
                        self.parent.xexunrtt.page_dirty_flags[i] = True
                    
                    # 缓冲写入搜索日志
                    new_path = replace_special_characters(search_word)
                    search_log_filepath = self.parent.rtt2uart.rtt_log_filename + '_' + new_path + '.log'
                    self.write_to_log_buffer(search_log_filepath, line + '\n')

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
        if not self.pattern:
            return

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
    
    window = MainWindow()
    #window.setWindowTitle("RTT2UART Control Panel V2.0.0")
    
    # 在窗口显示前更新翻译
    if hasattr(window, '_update_ui_translations'):
        window._update_ui_translations()
    
    window.show()

    sys.exit(app.exec())
