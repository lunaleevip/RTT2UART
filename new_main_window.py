#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构后的主窗口
更好的用户体验和窗口管理
"""

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
import os
import pickle
import pylink
import serial.tools.list_ports
import psutil
import threading
import logging

# 设置日志
logger = logging.getLogger(__name__)

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

# 导入原有的常量和工具类
from main_window import (
    speed_list, baudrate_list, MAX_TAB_SIZE, MAX_TEXT_LENGTH,
    Worker, PythonHighlighter, DeviceTableModel, DeviceSelectDialog,
    EditableTabBar, replace_special_characters, is_dummy_thread
)
from rtt2uart import rtt_to_serial as RTT2UART

class ConnectionDialog(QDialog):
    """连接配置对话框"""
    
    # 定义信号
    connection_established = Signal(dict)  # 连接建立信号，传递配置参数
    
    def __init__(self, parent=None):
        super(ConnectionDialog, self).__init__(parent)
        self.ui = Ui_dialog()
        self.ui.setupUi(self)
        
        self.setWindowTitle("RTT2UART - 连接配置")
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        self.setModal(True)  # 设置为模态对话框
        
        # 去掉Qt.ApplicationModal，使用普通模态
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        # 初始化属性
        self.setting_file_path = os.path.join(os.getcwd(), "settings")
        self.target_device = None
        self.connect_type = None
        self.jlink = None
        
        # 初始化界面
        self._init_ui()
        self._load_settings()
        self._connect_signals()
        self._init_jlink()
        
        # 美化界面
        self._apply_styling()
    
    def _init_ui(self):
        """初始化界面元素"""
        # 默认选项设置
        self.ui.checkBox__auto.setChecked(True)
        self.ui.radioButton_usb.setChecked(True)
        self.usb_selete_slot()
        
        # 添加接口选项
        interfaces = ["JTAG", "SWD", "cJTAG", "FINE"]
        for interface in interfaces:
            self.ui.comboBox_Interface.addItem(interface)
        
        # 添加速度选项
        for speed in speed_list:
            self.ui.comboBox_Speed.addItem(f"{speed} kHz")
        
        # 添加波特率选项
        for baudrate in baudrate_list:
            self.ui.comboBox_baudrate.addItem(str(baudrate))
        
        # 扫描串口
        self.port_scan()
        
        # 设置按钮文本
        self.ui.pushButton_Start.setText("连接并启动")
        
    def _apply_styling(self):
        """应用样式美化"""
        style = """
        QDialog {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #cccccc;
            border-radius: 8px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
        }
        QComboBox {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 4px;
            background-color: white;
        }
        QComboBox:focus {
            border: 2px solid #4CAF50;
        }
        """
        self.setStyleSheet(style)
    
    def _load_settings(self):
        """加载设置"""
        self.settings = {
            'device': [], 'device_index': 0, 'interface': 0,
            'speed': 0, 'port': 0, 'buadrate': 0, 
            'lock_h': 1, 'lock_v': 0, 'light_mode': 0, 
            'fontsize': 9, 'filter': [None] * (MAX_TAB_SIZE - 17), 
            'cmd': []
        }
        
        if os.path.exists(self.setting_file_path):
            try:
                with open(self.setting_file_path, 'rb') as f:
                    self.settings = pickle.load(f)
                self._apply_settings()
            except Exception:
                pass  # 如果加载失败，使用默认设置
    
    def _apply_settings(self):
        """应用已保存的设置"""
        if len(self.settings['device']):
            self.ui.comboBox_Device.addItems(self.settings['device'])
            self.target_device = self.settings['device'][self.settings['device_index']]
        
        self.ui.comboBox_Device.setCurrentIndex(self.settings['device_index'])
        self.ui.comboBox_Interface.setCurrentIndex(self.settings['interface'])
        self.ui.comboBox_Speed.setCurrentIndex(self.settings['speed'])
        self.ui.comboBox_Port.setCurrentIndex(self.settings['port'])
        self.ui.comboBox_baudrate.setCurrentIndex(self.settings['buadrate'])
    
    def _connect_signals(self):
        """连接信号槽"""
        self.ui.pushButton_Start.clicked.connect(self.on_connect)
        self.ui.pushButton_DeviceSelete.clicked.connect(self.target_device_selete)
        self.ui.pushButton_PortScan.clicked.connect(self.port_scan)
        
        # 单选按钮信号
        self.ui.radioButton_usb.clicked.connect(self.usb_selete_slot)
        self.ui.radioButton_tcp.clicked.connect(self.tcp_selete_slot)
        self.ui.radioButton_existing.clicked.connect(self.existing_session_selete_slot)
        
        # 下拉框信号
        self.ui.comboBox_Device.currentIndexChanged.connect(self.device_change_slot)
        self.ui.comboBox_Interface.currentIndexChanged.connect(self.interface_change_slot)
    
    def _init_jlink(self):
        """初始化JLink"""
        try:
            self.jlink = pylink.JLink()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"JLink初始化失败: {e}")
    
    def on_connect(self):
        """连接按钮点击事件"""
        if not self._validate_settings():
            return
        
        # 收集配置参数
        config = self._get_connection_config()
        
        # 尝试建立连接
        if self._test_connection(config):
            # 保存设置
            self._save_settings()
            
            # 发送连接成功信号并关闭对话框
            self.connection_established.emit(config)
            self.accept()
        else:
            QMessageBox.warning(self, "连接失败", "无法建立JLink连接，请检查设备和配置")
    
    def _validate_settings(self):
        """验证设置"""
        if not self.target_device:
            QMessageBox.warning(self, "警告", "请选择目标设备")
            return False
        
        if self.ui.comboBox_Port.currentText() == "":
            QMessageBox.warning(self, "警告", "请选择串口")
            return False
        
        return True
    
    def _get_connection_config(self):
        """获取连接配置"""
        # 确定连接接口类型
        interface_text = self.ui.comboBox_Interface.currentText()
        if interface_text == 'JTAG':
            device_interface = pylink.enums.JLinkInterfaces.JTAG
        elif interface_text == 'SWD':
            device_interface = pylink.enums.JLinkInterfaces.SWD
        elif interface_text == 'cJTAG':
            device_interface = None
        elif interface_text == 'FINE':
            device_interface = pylink.enums.JLinkInterfaces.FINE
        else:
            device_interface = pylink.enums.JLinkInterfaces.SWD
        
        # 确定连接类型和参数
        if self.ui.radioButton_usb.isChecked():
            connect_type = 'USB'
            connect_para = self.ui.lineEdit_usb.text() if self.ui.lineEdit_usb.text() else None
        elif self.ui.radioButton_tcp.isChecked():
            connect_type = 'TCP'
            connect_para = self.ui.lineEdit_tcp.text()
        else:
            connect_type = 'EXISTING'
            connect_para = None
        
        return {
            'jlink': self.jlink,
            'connect_type': connect_type,
            'connect_para': connect_para,
            'device': self.target_device,
            'port': self.ui.comboBox_Port.currentText(),
            'baudrate': int(self.ui.comboBox_baudrate.currentText()),
            'interface': device_interface,
            'speed': speed_list[self.ui.comboBox_Speed.currentIndex()],
            'reset': self.ui.checkBox_resettarget.isChecked(),
            'settings': self.settings.copy()
        }
    
    def _test_connection(self, config):
        """测试连接"""
        try:
            # 这里可以添加实际的连接测试逻辑
            # 暂时返回True，实际使用时应该测试JLink连接
            return True
        except Exception:
            return False
    
    def _save_settings(self):
        """保存设置"""
        try:
            with open(self.setting_file_path, 'wb') as f:
                pickle.dump(self.settings, f)
        except Exception:
            pass
    
    # 以下是从原MainWindow移植的方法
    def usb_selete_slot(self):
        """USB选择槽"""
        self.ui.label_usb.setEnabled(True)
        self.ui.lineEdit_usb.setEnabled(True)
        self.ui.label_tcp.setEnabled(False)
        self.ui.lineEdit_tcp.setEnabled(False)
        self.ui.checkBox__auto.setEnabled(False)
        self.ui.checkBox_resettarget.setEnabled(True)
        self.connect_type = 'USB'
    
    def tcp_selete_slot(self):
        """TCP选择槽"""
        self.ui.label_usb.setEnabled(False)
        self.ui.lineEdit_usb.setEnabled(False)
        self.ui.label_tcp.setEnabled(True)
        self.ui.lineEdit_tcp.setEnabled(True)
        self.ui.checkBox__auto.setEnabled(False)
        self.ui.checkBox_resettarget.setEnabled(True)
        self.connect_type = 'TCP'
    
    def existing_session_selete_slot(self):
        """现有会话选择槽"""
        self.ui.label_usb.setEnabled(False)
        self.ui.lineEdit_usb.setEnabled(False)
        self.ui.label_tcp.setEnabled(False)
        self.ui.lineEdit_tcp.setEnabled(False)
        self.ui.checkBox__auto.setEnabled(True)
        self.ui.checkBox_resettarget.setEnabled(False)
        self.ui.checkBox_resettarget.setChecked(False)
        self.connect_type = 'EXISTING'
    
    def port_scan(self):
        """扫描串口"""
        self.ui.comboBox_Port.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ui.comboBox_Port.addItem(port.device)
    
    def target_device_selete(self):
        """目标设备选择"""
        device_ui = DeviceSelectDialog()
        if device_ui.exec() == QDialog.Accepted:
            self.target_device = device_ui.get_target_device()
            
            if self.target_device and self.target_device not in self.settings['device']:
                self.settings['device'].insert(0, self.target_device)
                self.ui.comboBox_Device.insertItem(0, self.target_device)
                self.ui.comboBox_Device.setCurrentIndex(0)
                self.settings['device_index'] = 0
    
    def device_change_slot(self, index):
        """设备改变槽"""
        self.settings['device_index'] = index
        if index < len(self.settings['device']):
            self.target_device = self.settings['device'][index]
    
    def interface_change_slot(self, index):
        """接口改变槽"""
        self.settings['interface'] = index


class RTTMainWindow(QMainWindow):
    """重构后的主窗口"""
    
    def __init__(self):
        super(RTTMainWindow, self).__init__()
        
        # 基本设置
        self.setWindowTitle("RTT2UART - 调试工具")
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico"))
        
        # 状态管理
        self.rtt2uart = None
        self.start_state = False
        self.connection_config = None
        
        # 创建中央widget和布局
        self._create_ui()
        self._create_menu_bar()
        self._create_status_bar()
        self._create_worker()
        
        # 连接信号
        self._connect_signals()
        
        # 应用样式
        self._apply_styling()
        
        # 显示连接对话框
        self._show_connection_dialog()
    
    def _create_ui(self):
        """创建用户界面"""
        # 创建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建RTT窗口UI
        rtt_widget = QWidget()
        self.rtt_ui = Ui_xexun_rtt()
        self.rtt_ui.setupUi(rtt_widget)
        
        # 创建JLink日志显示区域
        self._create_jlink_log_area()
        
        # 创建分割器来分割RTT区域和JLink日志区域
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(rtt_widget)
        splitter.addWidget(self.jlink_log_widget)
        
        # 设置分割比例 (RTT区域占70%，JLink日志占30%)
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
        
        # 初始化RTT相关组件
        self._init_rtt_components()
    
    def _create_jlink_log_area(self):
        """创建JLink日志显示区域"""
        # 创建JLink日志widget
        self.jlink_log_widget = QWidget()
        layout = QVBoxLayout(self.jlink_log_widget)
        
        # 创建标题和控制按钮
        header_layout = QHBoxLayout()
        
        # JLink日志标题
        title_label = QLabel("JLink 调试日志")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title_label)
        
        # 添加弹簧
        header_layout.addStretch()
        
        # 清除日志按钮
        self.clear_jlink_log_btn = QPushButton("清除日志")
        self.clear_jlink_log_btn.setMaximumWidth(80)
        self.clear_jlink_log_btn.clicked.connect(self.clear_jlink_log)
        header_layout.addWidget(self.clear_jlink_log_btn)
        
        # 启用/禁用JLink日志按钮
        self.toggle_jlink_log_btn = QPushButton("启用详细日志")
        self.toggle_jlink_log_btn.setMaximumWidth(100)
        self.toggle_jlink_log_btn.setCheckable(True)
        self.toggle_jlink_log_btn.clicked.connect(self.toggle_jlink_verbose_log)
        header_layout.addWidget(self.toggle_jlink_log_btn)
        
        layout.addLayout(header_layout)
        
        # 创建JLink日志文本框
        self.jlink_log_text = QTextEdit()
        self.jlink_log_text.setReadOnly(True)
        self.jlink_log_text.setMaximumHeight(200)
        self.jlink_log_text.setFont(QFont("Consolas", 9))
        self.jlink_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3e3e3e;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        
        layout.addWidget(self.jlink_log_text)
        
        # 初始化JLink日志捕获
        self.jlink_verbose_logging = False
        self._setup_jlink_logging()
    
    def _setup_jlink_logging(self):
        """设置JLink日志捕获"""
        # 创建自定义日志处理器来捕获JLink日志
        self.jlink_log_handler = JLinkLogHandler(self.jlink_log_text)
        
        # 设置JLink库的日志级别
        jlink_logger = logging.getLogger('pylink')
        jlink_logger.setLevel(logging.DEBUG)
        jlink_logger.addHandler(self.jlink_log_handler)
    
    def clear_jlink_log(self):
        """清除JLink日志"""
        self.jlink_log_text.clear()
    
    def toggle_jlink_verbose_log(self, enabled):
        """切换JLink详细日志"""
        self.jlink_verbose_logging = enabled
        if enabled:
            self.toggle_jlink_log_btn.setText("禁用详细日志")
            # 启用更详细的JLink日志
            if hasattr(self, 'connection_config') and self.connection_config:
                jlink = self.connection_config.get('jlink')
                if jlink:
                    try:
                        # 设置JLink为详细模式
                        jlink.set_log_file("jlink_debug.log")
                        self.append_jlink_log("JLink 详细日志已启用")
                    except Exception as e:
                        self.append_jlink_log(f"启用详细日志失败: {e}")
        else:
            self.toggle_jlink_log_btn.setText("启用详细日志")
            self.append_jlink_log("JLink 详细日志已禁用")
    
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
    
    def _init_rtt_components(self):
        """初始化RTT相关组件"""
        # 创建自定义标签栏
        self.rtt_ui.tem_switch.setTabBar(EditableTabBar())
        
        # 初始化高亮器
        self.highlighter = {}
        
        # 为每个标签页创建高亮器
        for i in range(MAX_TAB_SIZE):
            widget = self.rtt_ui.tem_switch.widget(i)
            if widget:
                text_edit = widget.findChild(QTextEdit)
                if text_edit:
                    self.highlighter[i] = PythonHighlighter(text_edit.document())
        
        # 设置标签文本
        self.tabText = [""] * MAX_TAB_SIZE
        for i in range(17, MAX_TAB_SIZE):
            self.rtt_ui.tem_switch.setTabText(i, "filter")
            self.tabText[i] = "filter"
        
        # 连接RTT UI信号
        self.rtt_ui.tem_switch.currentChanged.connect(self.switchPage)
        self.rtt_ui.pushButton.clicked.connect(self.on_send_command)
        self.rtt_ui.clear.clicked.connect(self.on_clear_clicked)
        self.rtt_ui.openfolder.clicked.connect(self.on_openfolder_clicked)
        
        # 初始化定时器和更新标志
        self.page_dirty_flags = [False] * MAX_TAB_SIZE
        
        # 创建更新定时器
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_periodic_task)
        self.update_timer.start(500)  # 500ms更新一次
        
        # 设置样式
        self._setup_dark_light_theme()
    
    def _setup_dark_light_theme(self):
        """设置暗色/亮色主题"""
        try:
            from PySide6.QtGui import QPalette
            palette = QPalette()
            palette.ID = 'light'
            self.light_stylesheet = qdarkstyle._load_stylesheet(qt_api='pyside6', palette=palette)
            self.dark_stylesheet = qdarkstyle.load_stylesheet_pyside6()
            
            self.rtt_ui.light_checkbox.stateChanged.connect(self.set_style)
            self.set_style()
        except:
            pass  # 如果样式加载失败，使用默认样式
    
    def set_style(self):
        """设置样式"""
        try:
            if self.rtt_ui.light_checkbox.isChecked():
                self.setStyleSheet(self.light_stylesheet)
            else:
                self.setStyleSheet(self.dark_stylesheet)
        except:
            pass
    
    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 连接菜单
        connect_menu = menubar.addMenu("连接")
        
        reconnect_action = QAction("重新连接", self)
        reconnect_action.setShortcut("F2")
        reconnect_action.triggered.connect(self._show_connection_dialog)
        connect_menu.addAction(reconnect_action)
        
        disconnect_action = QAction("断开连接", self)
        disconnect_action.triggered.connect(self.stop_rtt)
        connect_menu.addAction(disconnect_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu("工具")
        
        performance_action = QAction("性能监控", self)
        performance_action.triggered.connect(self.show_performance_monitor)
        tools_menu.addAction(performance_action)
        
        device_restart_action = QAction("重启设备", self)
        device_restart_action.setShortcut("F9")
        device_restart_action.triggered.connect(self.device_restart)
        tools_menu.addAction(device_restart_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        """创建状态栏"""
        self.status_bar = self.statusBar()
        
        # 连接状态标签
        self.status_connection = QLabel("未连接")
        self.status_bar.addPermanentWidget(self.status_connection)
        
        # 数据统计标签
        self.status_data = QLabel("读取: 0 | 写入: 0")
        self.status_bar.addPermanentWidget(self.status_data)
    
    def _create_worker(self):
        """创建工作线程"""
        self.worker = Worker(self)
        self.worker.moveToThread(QApplication.instance().thread())
        self.worker.finished.connect(self.handleBufferUpdate)
        self.worker.start_flush_timer()
    
    def _connect_signals(self):
        """连接信号槽"""
        # 窗口关闭信号
        pass
    
    def _apply_styling(self):
        """应用主窗口样式"""
        # 设置窗口大小和位置
        self.resize(1200, 800)
        self.showMaximized()
    
    def _show_connection_dialog(self):
        """显示连接对话框"""
        dialog = ConnectionDialog(self)
        dialog.connection_established.connect(self.on_connection_established)
        
        if dialog.exec() != QDialog.Accepted:
            # 如果用户取消连接，且当前没有活动连接，则关闭程序
            if not self.start_state:
                self.close()
    
    @Slot(dict)
    def on_connection_established(self, config):
        """连接建立成功"""
        self.connection_config = config
        self.start_rtt()
        
        # 更新状态栏
        device_name = config.get('device', '未知设备')
        port_name = config.get('port', '未知端口')
        self.status_connection.setText(f"已连接: {device_name} -> {port_name}")
    
    def start_rtt(self):
        """启动RTT连接"""
        if not self.connection_config:
            return
        
        try:
            config = self.connection_config
            
            # 在JLink日志中记录连接开始
            self.append_jlink_log(f"开始连接到设备: {config['device']}")
            self.append_jlink_log(f"连接类型: {config['connect_type']}")
            self.append_jlink_log(f"串口: {config['port']}, 波特率: {config['baudrate']}")
            
            self.rtt2uart = RTT2UART(
                main=self,
                jlink=config['jlink'],
                connect_inf=config['connect_type'],
                connect_para=config['connect_para'],
                device=config['device'],
                port=config['port'],
                baudrate=config['baudrate'],
                interface=config['interface'],
                speed=config['speed'],
                reset=config['reset']
            )
            
            # 设置JLink日志回调
            self.rtt2uart.set_jlink_log_callback(self.append_jlink_log)
            
            self.rtt2uart.start()
            self.start_state = True
            
            # 更新UI
            self.status_connection.setText(f"运行中: {config['device']} -> {config['port']}")
            self.append_jlink_log("RTT连接启动成功")
            
        except Exception as e:
            self.append_jlink_log(f"RTT启动失败: {e}")
            QMessageBox.critical(self, "启动失败", f"RTT启动失败: {e}")
    
    def stop_rtt(self):
        """停止RTT连接"""
        if self.rtt2uart and self.start_state:
            try:
                self.rtt2uart.stop()
                self.start_state = False
                self.status_connection.setText("已断开")
                
                # 等待一段时间确保资源完全释放
                import time
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error stopping RTT: {e}")
                self.start_state = False
                self.status_connection.setText("停止时出错")
    
    def addToBuffer(self, index, string):
        """添加数据到缓冲区"""
        if hasattr(self, 'worker'):
            self.worker.addToBuffer(index, string)
    
    def switchPage(self, index):
        """切换页面"""
        if not hasattr(self, 'worker') or len(self.worker.buffers[index]) <= 0:
            return
        
        current_page_widget = self.rtt_ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            text_edit = current_page_widget.findChild(QTextEdit)
            if text_edit:
                font = QFont("新宋体", self.rtt_ui.fontsize_box.value())
                text_edit.setFont(font)
                
                # 记录滚动条位置
                vscroll = text_edit.verticalScrollBar().value()
                hscroll = text_edit.horizontalScrollBar().value()
                
                # 更新文本
                cursor = text_edit.textCursor()
                cursor.movePosition(QTextCursor.End)
                text_edit.setTextCursor(cursor)
                text_edit.setCursorWidth(0)
                
                # 设置高亮关键词
                if index >= 17:
                    if index in self.highlighter:
                        self.highlighter[index].setKeywords([self.rtt_ui.tem_switch.tabText(index)])
                    if self.tabText[index] != self.rtt_ui.tem_switch.tabText(index):
                        self.tabText[index] = self.rtt_ui.tem_switch.tabText(index)
                        text_edit.clear()
                elif index != 2:
                    keywords = []
                    for i in range(MAX_TAB_SIZE):
                        if i >= 17:
                            keywords.append(self.rtt_ui.tem_switch.tabText(i))
                    if index in self.highlighter:
                        self.highlighter[index].setKeywords(keywords)
                
                text_edit.insertPlainText(self.worker.buffers[index])
                self.worker.buffers[index] = ""
                
                # 标记页面已更新
                if hasattr(self, 'page_dirty_flags'):
                    self.page_dirty_flags[index] = False
                
                # 检查文本长度并清理
                text_length = len(text_edit.toPlainText())
                if text_length > MAX_TEXT_LENGTH:
                    new_text = text_edit.toPlainText()[int(MAX_TEXT_LENGTH/2):]
                    text_edit.clear()
                    text_edit.insertPlainText(new_text)
                
                # 恢复滚动条位置
                if self.rtt_ui.LockV_checkBox.isChecked():
                    text_edit.verticalScrollBar().setValue(vscroll)
                if self.rtt_ui.LockH_checkBox.isChecked():
                    text_edit.horizontalScrollBar().setValue(hscroll)
    
    @Slot()
    def handleBufferUpdate(self):
        """处理缓冲区更新"""
        current_index = self.rtt_ui.tem_switch.currentIndex()
        
        # 优先更新当前显示的页面
        if hasattr(self, 'page_dirty_flags') and self.page_dirty_flags[current_index]:
            self.switchPage(current_index)
        
        # 批量更新其他有变化的页面（限制每次最多更新3个）
        updated_count = 0
        for i in range(MAX_TAB_SIZE):
            if (hasattr(self, 'page_dirty_flags') and 
                i != current_index and 
                self.page_dirty_flags[i] and 
                updated_count < 3):
                self.switchPage(i)
                updated_count += 1
    
    def update_periodic_task(self):
        """定期更新任务"""
        if not self.rtt2uart:
            return
        
        # 更新数据统计
        read_bytes = self.rtt2uart.read_bytes0 + self.rtt2uart.read_bytes1
        write_bytes = self.rtt2uart.write_bytes0
        self.status_data.setText(f"读取: {read_bytes} | 写入: {write_bytes}")
    
    def on_send_command(self):
        """发送命令"""
        if not self.rtt2uart or not self.start_state:
            QMessageBox.warning(self, "警告", "请先建立RTT连接")
            return
        
        current_text = self.rtt_ui.cmd_buffer.currentText()
        if not current_text:
            return
        
        try:
            utf8_data = current_text + '\n'
            gbk_data = utf8_data.encode('gbk', errors='ignore')
            
            bytes_written = self.connection_config['jlink'].rtt_write(0, gbk_data)
            self.rtt2uart.write_bytes0 = bytes_written
            
            if bytes_written == len(gbk_data):
                self.rtt_ui.cmd_buffer.clearEditText()
                sent_msg = f"发送: {utf8_data[:-1]}"
                self.rtt_ui.sent.setText(sent_msg)
                self.rtt_ui.tem_switch.setCurrentIndex(2)  # 切换到应答界面
                
                # 添加到历史记录
                if current_text not in [self.rtt_ui.cmd_buffer.itemText(i) for i in range(self.rtt_ui.cmd_buffer.count())]:
                    self.rtt_ui.cmd_buffer.addItem(current_text)
            
        except Exception as e:
            QMessageBox.warning(self, "发送失败", f"命令发送失败: {e}")
    
    def on_clear_clicked(self):
        """清除按钮点击"""
        index = self.rtt_ui.tem_switch.currentIndex()
        current_page_widget = self.rtt_ui.tem_switch.widget(index)
        if isinstance(current_page_widget, QWidget):
            text_edit = current_page_widget.findChild(QTextEdit)
            if text_edit:
                text_edit.clear()
    
    def on_openfolder_clicked(self):
        """打开文件夹按钮点击"""
        if self.rtt2uart and hasattr(self.rtt2uart, 'log_directory'):
            try:
                os.startfile(self.rtt2uart.log_directory)
            except:
                pass
    
    def show_performance_monitor(self):
        """显示性能监控"""
        try:
            import subprocess
            subprocess.Popen([sys.executable, "performance_monitor.py"])
        except Exception as e:
            QMessageBox.information(self, "信息", f"无法启动性能监控: {e}")
    
    def device_restart(self):
        """重启设备"""
        if self.rtt2uart and self.start_state:
            try:
                # 这里可以添加设备重启逻辑
                QMessageBox.information(self, "信息", "设备重启功能暂未实现")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"设备重启失败: {e}")
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于 RTT2UART", 
                         "RTT2UART 调试工具\n\n"
                         "版本: 优化版\n"
                         "基于 SEGGER RTT 技术\n"
                         "支持实时双向通信")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            if self.rtt2uart and self.start_state:
                reply = QMessageBox.question(self, "确认关闭", 
                                           "RTT连接仍在运行，确定要关闭程序吗？",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
                if reply == QMessageBox.No:
                    event.ignore()
                    return
                
                # 停止RTT连接
                self.stop_rtt()
            
            # 停止更新定时器
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            
            # 停止工作线程
            if hasattr(self, 'worker'):
                try:
                    if hasattr(self.worker, 'buffer_flush_timer') and self.worker.buffer_flush_timer:
                        self.worker.buffer_flush_timer.stop()
                except:
                    pass
            
            # 保存设置
            if hasattr(self, 'connection_config') and self.connection_config:
                try:
                    setting_file_path = os.path.join(os.getcwd(), "settings")
                    with open(setting_file_path, 'wb') as f:
                        pickle.dump(self.connection_config['settings'], f)
                except Exception as e:
                    logger.warning(f"Failed to save settings: {e}")
            
            # 清理资源
            try:
                for i in range(MAX_TAB_SIZE):
                    current_page_widget = self.rtt_ui.tem_switch.widget(i)
                    if isinstance(current_page_widget, QWidget):
                        text_edit = current_page_widget.findChild(QTextEdit)
                        if text_edit:
                            text_edit.clear()
            except Exception as e:
                logger.warning(f"Error clearing text edits: {e}")
            
            # 等待所有线程结束
            import threading
            import time
            
            # 给线程一些时间来清理
            time.sleep(0.3)
            
            # 检查并等待非主线程结束
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.is_alive():
                    if hasattr(thread, 'name') and not thread.name.startswith('Dummy'):
                        try:
                            thread.join(timeout=1.0)
                        except:
                            pass
            
            event.accept()
            
        except Exception as e:
            logger.error(f"Error during close event: {e}")
            event.accept()  # 即使出错也要关闭窗口


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 加载翻译文件
    translator = QTranslator()
    translation_loaded = False
    
    # 首先尝试从资源文件加载
    if translator.load(QLocale.system(), ":/xexunrtt.qm"):
        QCoreApplication.installTranslator(translator)
        translation_loaded = True
        print("Translation loaded from resources.")
    # 如果资源文件加载失败，尝试从当前目录加载
    elif translator.load("xexunrtt.qm"):
        QCoreApplication.installTranslator(translator)
        translation_loaded = True
        print("Translation loaded from current directory.")
    else:
        print("Failed to load translation file.")
    
    # 加载 Qt 内置翻译文件
    qt_translator = QTranslator()
    qt_translation_loaded = False
    
    # 首先尝试从资源文件加载
    if qt_translator.load(QLocale.system(), ":/qt_zh_CN.qm"):
        QCoreApplication.installTranslator(qt_translator)
        qt_translation_loaded = True
        print("Qt translation loaded from resources.")
    # 如果资源文件加载失败，尝试从当前目录加载
    elif qt_translator.load("qt_zh_CN.qm"):
        QCoreApplication.installTranslator(qt_translator)
        qt_translation_loaded = True
        print("Qt translation loaded from current directory.")
    else:
        print("Failed to load Qt translation file.")
    
    # 创建并显示主窗口
    window = RTTMainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
