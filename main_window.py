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

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

# pylink支持的最大速率是12000kHz（Release v0.7.0开始支持15000及以上速率）
speed_list = [5, 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 750,
              900, 1000, 1334, 1600, 2000, 2667, 3200, 4000, 4800, 5334, 6000, 8000, 9600, 12000,
              15000, 20000, 25000, 30000, 40000, 50000]

baudrate_list = [50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
                 9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600]

MAX_TAB_SIZE = 24
MAX_TEXT_LENGTH = (int)(2e6) #缓存 2MB 的数据
VERSION = "1.0.2"

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
            if ok and new_text:
                self.setTabText(index, new_text)

class XexunRTTWindow(QWidget):
    def __init__(self, main):
        super(XexunRTTWindow, self).__init__()
        self.main = main
        self.ui = Ui_xexun_rtt()
        self.ui.setupUi(self)
        
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
        
        for i in range(MAX_TAB_SIZE):
            page = QWidget()
            text_edit = QTextEdit(page)  # 在页面上创建 QTextEdit 实例
            text_edit.setReadOnly(True)
            text_edit.setWordWrapMode(QTextOption.NoWrap)  # 禁用自动换行
            text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示垂直滚动条
            text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # 始终显示水平滚动条
            layout = QVBoxLayout(page)  # 创建布局管理器
            layout.addWidget(text_edit)  # 将 QTextEdit 添加到布局中
            
            if i == 0:
                self.ui.tem_switch.addTab(page, QCoreApplication.translate("main_window", "All"))  # 将页面添加到 tabWidget 中
            elif i < 17:
                self.ui.tem_switch.addTab(page, '{}'.format(i - 1))  # 将页面添加到 tabWidget 中
            else:
                self.ui.tem_switch.addTab(page, QCoreApplication.translate("main_window", "filter"))
                
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
        self.light_stylesheet = ""
        self.dark_stylesheet = qdarkstyle.load_stylesheet()
        
        self.ui.light_checkbox.stateChanged.connect(self.set_style)
        self.set_style()
        
        # 创建定时器并连接到槽函数
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_periodic_task)
        self.timer.start(100)  # 每100毫秒（0.1秒）执行一次
        
    def resizeEvent(self, event):
        # 当窗口大小变化时更新布局大小
        self.ui.layoutWidget.setGeometry(QRect(0, 0, self.width(), self.height()))

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
            if log_directory and os.listdir(log_directory):
                os.startfile(log_directory)
            else:
                shutil.rmtree(log_directory)
        self.main.close()

    @Slot(int)
    def switchPage(self, index):
        self.main.switchPage(index)


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
            self.ui.tem_switch.setCurrentIndex(2);#输入指令成功后，自动切换到应答界面
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
        
    def on_cmd_buffer_activated(self, index):
        text = self.ui.cmd_buffer.currentText()
        if text:  # 如果文本不为空
            self.ui.pushButton.click()  # 触发 QPushButton 的点击事件

    def update_periodic_task(self):
        
        title = QCoreApplication.translate("main_window", u"XexunRTT Main Ver:") + VERSION
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
            if self.jlink._library._path is not None:
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
                elif sys.platform.startswith('linux'):
                    jlink_env = {}
                    cmd = 'JLinkExe -CommandFile JLinkCommandFile.jlink'
                elif sys.platform.startswith('darwin'):
                    jlink_env = {}
                    cmd = 'JLinkExe -CommandFile JLinkCommandFile.jlink'

        except Exception as e:
            logging.error(f'can not export devices xml file, error info: {e}')

    def closeEvent(self, e):
        if self.rtt2uart is not None and self.start_state == True:
            self.rtt2uart.stop()
        if self.xexunrtt is not None:
            self.xexunrtt.close()
        # 保存当前配置
        with open(self.setting_file_path, 'wb') as f:
            pickle.dump(self.settings, f)
        
        # 等待其他线程结束
        for thread in threading.enumerate():
            if thread != threading.current_thread():
                if not is_dummy_thread(thread):
                    thread.join()
        super().closeEvent(e)
        
        e.accept()

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

                self.rtt2uart.start()
                
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
                    

                self.rtt2uart.stop()
                #self.show()

                self.start_state = False
                self.ui.pushButton_Start.setText(QCoreApplication.translate("main_window", "Start"))
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

                text_edit.insertPlainText(self.worker.buffers[index])
                self.worker.buffers[index] = ""

                text_length = len(text_edit.toPlainText())
                if text_length > MAX_TEXT_LENGTH:
                    # 截取文本长度
                    new_text = text_edit.toPlainText()[(MAX_TEXT_LENGTH/2):]
                    text_edit.clear()
                    text_edit.insertPlainText(new_text)

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
        # 获取当前选定的页面索引
        index = self.xexunrtt.ui.tem_switch.currentIndex()
        # 刷新文本框
        self.switchPage(index)
   

class Worker(QObject):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.byte_buffer = [bytearray() for _ in range(16)]  # 创建MAX_TAB_SIZE个缓冲区
        self.buffers = [""] * MAX_TAB_SIZE  # 创建MAX_TAB_SIZE个缓冲区

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

            buffer = self.buffers[index+1]
            buffer0 = self.buffers[0]
        
            self.buffers[index+1] += data
            
            self.buffers[0] +=  "%02u> " % index
            self.buffers[0] += data
            # 在主线程中执行操作

            with open(self.parent.rtt2uart.rtt_log_filename + '_' + str(index) + '.log', 'a') as page_log_file:
                page_log_file.write(data);

            # 将buffer分割成行
            lines = data.split('\n')

            for line in lines:
                for i in range(17 , MAX_TAB_SIZE):
                    tagText = self.parent.xexunrtt.ui.tem_switch.tabText(i)
                    search_word = tagText
                    buffer = self.buffers[i]
                    if search_word != QCoreApplication.translate("main_window", "filter") and search_word in line:
                        new_path = replace_special_characters(search_word)
                        with open(self.parent.rtt2uart.rtt_log_filename + '_' + new_path + '.log', 'a') as search_log_file:
                            search_log_file.write(line + '\n');
                            self.buffers[i] += line + '\n'

            self.finished.emit()

def replace_special_characters(path, replacement='_'):
    # 定义需要替换的特殊字符的正则表达式模式
    pattern = r'[<>:"/\\|?*]'

    # 使用指定的替换字符替换特殊字符
    new_path = re.sub(pattern, replacement, path)

    return new_path

def is_dummy_thread(thread):
    return thread.name.startswith('Dummy')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 加载并安装翻译文件
    translator = QTranslator()
    # 加载内置翻译文件
    if translator.load(QLocale.system(), ":/xexunrtt.qm"):
        # 如果成功加载翻译文件，则安装翻译器
        QCoreApplication.installTranslator(translator)
    else:
        # 加载失败时进行错误处理
        print("Failed to load translation file.")

    # 加载 Qt 内置翻译文件
    qt_translator = QTranslator()
    if qt_translator.load(QLocale.system(), ":/qt_zh_CN.qm"):
        QCoreApplication.installTranslator(qt_translator)
    else:
        print("Failed to load Qt translation file.")
    
    window = MainWindow()
    #window.setWindowTitle("RTT2UART Control Panel V2.0.0")
    window.show()

    sys.exit(app.exec())
