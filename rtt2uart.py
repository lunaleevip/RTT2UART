import logging
try:
    # 优先使用性能配置
    from performance_config import DataProcessingConfig as _DPConf
    _RTT_READ_BUFFER_SIZE = getattr(_DPConf, 'RTT_READ_BUFFER_SIZE', 4096)
except Exception:
    _RTT_READ_BUFFER_SIZE = 4096
import pylink
import time
import serial
import threading
import socket
import os
import datetime
import zipfile
import re
from pathlib import Path
import shutil
import json
from PySide6.QtCore import QCoreApplication

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

from config_manager import config_manager

def _get_autoreset_patterns():
    """从 config.ini 的 [Autoreset] 读取 reset_msg(JSON数组)，无配置则使用默认。"""
    try:
        cfg = config_manager.config
        raw = cfg.get('Autoreset', 'reset_msg', fallback='["JLink connection failed after open"]')  #不能修改此处，这是JLINK返回的
        arr = json.loads(raw)
        return [s for s in arr if isinstance(s, str) and s.strip()]
    except Exception as e:
        logger.warning(QCoreApplication.translate("rtt2uart", "读取自动重置配置失败: %s") % str(e))
        return [QCoreApplication.translate("rtt2uart", "JLink connection failed after open")]


class AnsiProcessor:
    """ANSI控制符处理器"""
    
    def __init__(self):
        # ANSI控制符正则表达式（字符串版本）
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        # ANSI控制符正则表达式（bytes版本）
        self.ansi_escape_bytes = re.compile(rb'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        # 颜色映射表
        self.color_map = {
            # 普通颜色 (2;XXm)
            '\x1B[2;30m': '#808080',  # 黑色
            '\x1B[2;31m': '#800000',  # 红色
            '\x1B[2;32m': '#008000',  # 绿色
            '\x1B[2;33m': '#808000',  # 黄色
            '\x1B[2;34m': '#000080',  # 蓝色
            '\x1B[2;35m': '#800080',  # 洋红
            '\x1B[2;36m': '#008080',  # 青色
            '\x1B[2;37m': '#C0C0C0',  # 白色
            
            # 亮色 (1;XXm)
            '\x1B[1;30m': '#808080',  # 亮黑色
            '\x1B[1;31m': '#FF0000',  # 亮红色
            '\x1B[1;32m': '#00FF00',  # 亮绿色
            '\x1B[1;33m': '#FFFF00',  # 亮黄色
            '\x1B[1;34m': '#0000FF',  # 亮蓝色
            '\x1B[1;35m': '#FF00FF',  # 亮洋红
            '\x1B[1;36m': '#00FFFF',  # 亮青色
            '\x1B[1;37m': '#FFFFFF',  # 亮白色
            
            # 标准背景色 (40-47m) - 统一使用明亮黄色高亮
            '\x1B[40m': 'bg:#000000',     # 黑色背景
            '\x1B[41m': 'bg:#800000',     # 红色背景
            '\x1B[42m': 'bg:#008000',     # 绿色背景
            '\x1B[43m': 'bg:#FFFF00',     # 明亮黄色背景 - 统一高亮颜色
            '\x1B[44m': 'bg:#000080',     # 蓝色背景
            '\x1B[45m': 'bg:#800080',     # 洋红背景
            '\x1B[46m': 'bg:#008080',     # 青色背景
            '\x1B[47m': 'bg:#C0C0C0',     # 白色背景
            
            # 复合颜色代码 - 背景色+前景色组合（增强对比度）
            '\x1B[43;30m': 'bg:#FFFF00;color:#000000',  # 黄色背景 + 黑色文字
            
            # 背景色 (24;XXm 和 4;XXm) - 保持兼容性
            '\x1B[24;40m': 'bg:#000000',  # 黑色背景
            '\x1B[24;41m': 'bg:#800000',  # 红色背景
            '\x1B[24;42m': 'bg:#008000',  # 绿色背景
            '\x1B[24;43m': 'bg:#FFFF00',  # 明亮黄色背景 - 统一高亮颜色
            '\x1B[24;44m': 'bg:#000080',  # 蓝色背景
            '\x1B[24;45m': 'bg:#800080',  # 洋红背景
            '\x1B[24;46m': 'bg:#008080',  # 青色背景
            '\x1B[24;47m': 'bg:#C0C0C0',  # 白色背景
            
            '\x1B[4;40m': 'bg:#000000',   # 亮黑色背景
            '\x1B[4;41m': 'bg:#FF0000',   # 亮红色背景
            '\x1B[4;42m': 'bg:#00FF00',   # 亮绿色背景
            '\x1B[4;43m': 'bg:#FFFF00',   # 明亮黄色背景 - 统一高亮颜色
            '\x1B[4;44m': 'bg:#0000FF',   # 亮蓝色背景
            '\x1B[4;45m': 'bg:#FF00FF',   # 亮洋红背景
            '\x1B[4;46m': 'bg:#00FFFF',   # 亮青色背景
            '\x1B[4;47m': 'bg:#FFFFFF',   # 亮白色背景
            
            # 控制符
            '\x1B[0m': 'reset',      # 重置
            '\x1B[2J': 'clear',      # 清屏
        }
    
    def remove_ansi_codes(self, text):
        """从文本中删除所有ANSI控制符（用于日志文件）"""
        if isinstance(text, bytes):
            # 直接在bytes上操作，然后解码
            clean_bytes = self.ansi_escape_bytes.sub(b'', text)
            # 动态编码在使用处处理，这里尽量原样返回可打印字符
            try:
                return clean_bytes.decode('gbk', errors='ignore')
            except Exception:
                return clean_bytes.decode('utf-8', errors='ignore')
        else:
            # 字符串操作
            return self.ansi_escape.sub('', text)
    
    def parse_ansi_text(self, text):
        """解析ANSI文本，返回带格式信息的文本段列表"""
        if isinstance(text, bytes):
            # 优先按 GBK，失败退回 UTF-8
            try:
                text = text.decode('gbk', errors='ignore')
            except Exception:
                text = text.decode('utf-8', errors='ignore')
        
        segments = []
        current_color = None
        current_bg = None
        
        # 分割文本，保留ANSI控制符
        parts = self.ansi_escape.split(text)
        ansi_codes = self.ansi_escape.findall(text)
        
        i = 0
        for part in parts:
            if part:  # 非空文本段
                segments.append({
                    'text': part,
                    'color': current_color,
                    'background': current_bg
                })
            
            # 处理对应的ANSI控制符
            if i < len(ansi_codes):
                code = ansi_codes[i]
                if code in self.color_map:
                    color_value = self.color_map[code]
                    if color_value == 'reset':
                        current_color = None
                        current_bg = None
                    elif color_value == 'clear':
                        # 清屏命令，可以在这里处理
                        pass
                    elif ';' in color_value:
                        # 处理复合颜色代码（如：bg:#FFFF00;color:#000000）
                        parts = color_value.split(';')
                        for part in parts:
                            if part.startswith('bg:'):
                                current_bg = part[3:]  # 移除 'bg:' 前缀
                            elif part.startswith('color:'):
                                current_color = part[6:]  # 移除 'color:' 前缀
                            else:
                                current_color = part
                    elif color_value.startswith('bg:'):
                        current_bg = color_value[3:]
                    else:
                        current_color = color_value
                i += 1
        
        return segments


# 创建全局ANSI处理器实例
ansi_processor = AnsiProcessor()

def zip_folder(folder_path, zip_file_path):
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))


class rtt_to_serial():
    def __init__(self, main, jlink, connect_inf='USB', connect_para=None, device=None, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False, log_split=True, window_id=None, jlink_index=None):
        # jlink接入方式
        self._connect_inf = connect_inf
        # jlink接入参数
        self._connect_para = connect_para
        # 目标芯片名字
        self.device = device
        # 调试口
        self._interface = interface
        # 连接速率
        self._speed = speed
        # 复位标志
        self._reset = reset
        
        self.main = main
        
        # 串口参数
        self.port = port
        self.baudrate = baudrate

        self.jlink = jlink
        
        self.read_bytes0 = 0
        self.read_bytes1 = 0
        self.write_bytes0 = 0

        # 线程
        self._write_lock = threading.Lock()

        try:
            self.serial = serial.Serial()
        except:
            logger.error(QCoreApplication.translate("rtt2uart", "创建串口对象失败"), exc_info=True)
            raise

        self.rtt_thread = None
        self.rtt2uart = None
        
        self.tem = '0'
        
        # JLink日志回调函数
        self.jlink_log_callback = None
        
        # 记录连接信息到日志
        if self.jlink_log_callback:
            self.jlink_log_callback(QCoreApplication.translate("rtt2uart", "Device connection info: %s") % self.device_info)
        
        # 串口转发设置
        self.serial_forward_tab = -1  # -1表示禁用转发
        self.serial_forward_mode = 'LOG'  # 'LOG' 或 'DATA'
        self.serial_forward_buffer = {}  # 存储各个TAB的数据缓冲
        self.current_tab_index = 0  # 当前显示的标签页索引
        
        # 设置日志文件名
        log_directory = None
        
        # 生成JLINK连接编号和文件夹名
        if jlink_index is not None:
            # 使用传入的实际设备索引
            actual_jlink_index = jlink_index
        else:
            # 兼容旧版本，如果没有传入索引则使用0
            actual_jlink_index = 0
        
        # 保存设备连接信息，用于日志显示
        self.device_info = f"USB_{actual_jlink_index}_{connect_para}" if connect_para else f"USB_{actual_jlink_index}"
        self.jlink_index = actual_jlink_index
        self.connect_serial = connect_para
        
        # 生成文件夹名：USB_索引_序列号_时间戳
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        if connect_para:
            # 有连接参数（序列号）时，格式：USB_0_69741391_20250916165124
            folder_name = f"USB_{actual_jlink_index}_{connect_para}_{timestamp}"
        else:
            # 没有连接参数时，格式：USB_0_20250916165124
            folder_name = f"USB_{actual_jlink_index}_{timestamp}"
        
        if log_split:
            # 日志拆分模式：每次连接使用新的日志目录
            desktop_path = Path.home() / "Desktop/XexunRTT_Log"
            log_directory = desktop_path / folder_name
            # 确保日志文件夹存在，如果不存在则创建
            log_directory.mkdir(parents=True, exist_ok=True)
        else:
            # 非拆分模式：使用启动时的默认文件夹
            # 每个窗口使用独立的日志文件夹（通过window_id区分）
            desktop_path = Path.home() / "Desktop/XexunRTT_Log"
            if window_id:
                # 使用窗口ID确保不同窗口使用不同文件夹
                log_directory = desktop_path / f"{folder_name}_{window_id}"
            else:
                # 兼容旧版本
                log_directory = desktop_path / folder_name
            
            # 确保日志文件夹存在
            log_directory.mkdir(parents=True, exist_ok=True)
            
        self.log_directory = log_directory
        self.rtt_log_filename = os.path.join(log_directory, "rtt_log.log")
        self.rtt_data_filename = os.path.join(log_directory, "rtt_data.log")


    def __del__(self):
        logger.debug(QCoreApplication.translate("rtt2uart", "关闭应用"))
        self.stop()
    
    def set_jlink_log_callback(self, callback):
        """设置JLink日志回调函数"""
        self.jlink_log_callback = callback
    
    def _log_to_gui(self, message):
        """将消息发送到GUI日志"""
        if self.jlink_log_callback:
            self.jlink_log_callback(message)
    
    def _auto_reset_jlink_connection(self):
        """自动重置JLink连接"""
        try:
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting auto reset JLink connection..."))
            
            # 1. 关闭RTT
            try:
                if hasattr(self.jlink, 'rtt_stop'):
                    self.jlink.rtt_stop()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT stopped"))
            except Exception as e:
                logger.warning(f"Failed to stop RTT during reset: {e}")
            
            # 2. 断开目标连接
            try:
                if hasattr(self.jlink, 'close'):
                    self.jlink.close()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection closed"))
            except Exception as e:
                logger.warning(f"Failed to close JLink during reset: {e}")
            
            # 3. 等待一段时间
            import time
            time.sleep(1.0)
            
            # 4. 重新创建JLink对象
            try:
                self.jlink = pylink.JLink()
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink object recreated"))
            except Exception as e:
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to recreate JLink object: %s") % str(e))
                return False
            
            # 5. 重新连接
            try:
                # 重新打开JLink
                if self._connect_inf == 'USB':
                    self.jlink.open(self._connect_para)
                else:
                    self.jlink.open()
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink reopened successfully"))
                
                # 重新设置速率
                self.jlink.set_speed(self._speed)
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink speed reset: %s kHz") % str(self._speed))
                
                # 重新设置接口
                self.jlink.set_tif(self._interface)
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink interface reset: %s") % str(self._interface))
                
                # 重新连接目标
                self.jlink.connect(self.device)
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Target device reconnected: %s") % str(self.device))
                
                # 重新启动RTT
                self.jlink.rtt_start()
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT restarted successfully"))
                
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset completed!"))
                return True
                
            except Exception as e:
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink reconnection failed: %s") % str(e))
                return False
                
        except Exception as e:
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset process error: %s") % str(e))
            logger.error(f"Error in _auto_reset_jlink_connection: {e}")
            return False
    
    def _auto_stop_on_connection_lost(self):
        """连接丢失时自动停止RTT功能 - 增强异常保护，防止程序退出"""
        try:
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost, safely stopping RTT..."))
            
            # 设置线程停止标志
            self.thread_switch = False
            
            # 安全清理RTT连接状态
            try:
                if hasattr(self, 'jlink') and self.jlink:
                    try:
                        if self.jlink.connected():
                            self.jlink.close()
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection safely disconnected"))
                    except Exception:
                        pass  # 忽略断开时的错误
            except Exception:
                pass
            
            # 通知主窗口连接已断开
            if hasattr(self.main, '_handle_connection_lost'):
                try:
                    # 使用Qt的信号机制安全地通知主线程
                    from PySide6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(
                        self.main, 
                        "_handle_connection_lost", 
                        Qt.QueuedConnection
                    )
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Main window notified of connection loss"))
                except Exception as e:
                    logger.warning(f"Failed to notify main window of connection loss: {e}")
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to notify main window: %s") % str(e))
            
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT function safely stopped, program continues"))
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "You can click Start button anytime to reconnect"))
            
        except Exception as e:
            # 强化异常保护 - 绝对不能让这个方法导致程序崩溃
            try:
                logger.error(f"Error in _auto_stop_on_connection_lost: {e}")
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Error stopping RTT: %s") % str(e))
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Program will continue, please reset connection manually"))
                
                # 确保线程停止标志被设置
                self.thread_switch = False
                
            except Exception:
                # 最后的保护层 - 静默处理所有异常
                pass
    
    def set_serial_forward_config(self, tab_index, mode='LOG'):
        """设置串口转发的配置"""
        old_tab_index = self.serial_forward_tab
        self.serial_forward_tab = tab_index
        self.serial_forward_mode = mode
        
        # 动态管理串口状态
        if tab_index == -1:
            # 禁用转发，关闭串口
            if hasattr(self, 'serial') and self.serial and self.serial.isOpen():
                try:
                    self.serial.close()
                    logger.info(QCoreApplication.translate("rtt2uart", "Serial forwarding disabled, port closed"))
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Serial forwarding disabled, COM port closed"))
                except Exception as e:
                    logger.error(QCoreApplication.translate("rtt2uart", "Failed to close serial port: %s") % str(e))
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to close COM port: %s") % str(e))
            else:
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Serial forwarding disabled"))
        else:
            # 启用转发，打开串口（如果还没打开）
            if hasattr(self, 'serial') and self.serial and not self.serial.isOpen():
                try:
                    # 设置串口参数并打开串口
                    self.serial.port = self.port
                    self.serial.baudrate = self.baudrate
                    self.serial.timeout = 3
                    self.serial.write_timeout = 3
                    self.serial.open()
                    logger.info(f'串口转发已启用，串口 {self.port} 打开成功')
                except Exception as e:
                    logger.error(QCoreApplication.translate("rtt2uart", "Failed to open serial port: %s") % str(e))
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to open COM port %s: %s") % (self.port, str(e)))
                    return
            
            mode_text = QCoreApplication.translate("rtt2uart", "LOG Mode") if mode == 'LOG' else QCoreApplication.translate("rtt2uart", "DATA Mode")
            if self.serial and self.serial.isOpen():
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Serial forwarding enabled: %s - %s (COM: %s)") % (mode_text, str(tab_index), self.port))
            else:
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Serial forwarding enabled: %s - %s (COM port failed)") % (mode_text, str(tab_index)))
    
    def set_current_tab_index(self, tab_index):
        """设置当前显示的标签页索引"""
        self.current_tab_index = tab_index
    
    # 保持向后兼容
    def set_serial_forward_tab(self, tab_index):
        """保持向后兼容的方法"""
        self.set_serial_forward_config(tab_index, 'LOG')
    
    def add_tab_data_for_forwarding(self, tab_index, data):
        """为TAB添加数据用于串口转发"""
        if self.serial_forward_tab == -1:
            return  # 转发已禁用
        
        should_forward = False
        
        if self.serial_forward_mode == 'LOG':
            # LOG模式：根据选中的TAB转发
            if self.serial_forward_tab == 'current_tab':
                # 转发当前标签页
                should_forward = (tab_index == self.current_tab_index)
                # 添加调试信息
                if tab_index <= 1:  # Only show debug info for first few tabs to avoid excessive logs
                    logger.debug(f'Current tab forwarding check: tab_index={tab_index}, current_tab_index={self.current_tab_index}, should_forward={should_forward}')
            elif isinstance(self.serial_forward_tab, int):
                # 转发指定的TAB
                should_forward = (tab_index == self.serial_forward_tab)
        
        elif self.serial_forward_mode == 'DATA':
            # DATA模式：不在这里转发，原始数据由add_raw_rtt_data_for_forwarding处理
            # 避免重复转发处理后的LOG数据
            should_forward = False
        
        if should_forward:
            # 将数据转发到串口
            if self.serial.isOpen():
                try:
                    # 将字符串转换为字节
                    if isinstance(data, str):
                        try:
                            enc = self.main.config.get_text_encoding() if hasattr(self, 'main') and hasattr(self.main, 'config') else 'gbk'
                        except Exception:
                            enc = 'gbk'
                        data_bytes = data.encode(enc, errors='ignore')
                    else:
                        data_bytes = bytes(data)
                    
                    self.serial.write(data_bytes)
                    # # 添加详细的调试信息
                    # logger.debug(f'Forwarded {len(data_bytes)} bytes from TAB {tab_index} to serial port (mode: {self.serial_forward_mode}, forward_tab: {self.serial_forward_tab}, current_tab: {self.current_tab_index})')
                    # # 显示部分数据内容用于调试
                    # preview = data[:50] if len(str(data)) > 50 else str(data)
                    # logger.debug(f'Forwarded data preview: {repr(preview)}')
                except Exception as e:
                    logger.error(f"Serial forward error: {e}")
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Serial forward error: %s") % str(e))
    
    def add_raw_rtt_data_for_forwarding(self, channel, data):
        """为RTT原始数据添加转发功能（DATA模式专用）"""
        logger.debug(f'add_raw_rtt_data_for_forwarding called: channel={channel}, data_len={len(data) if data else 0}, mode={self.serial_forward_mode}, tab={self.serial_forward_tab}')
        if (self.serial_forward_mode == 'DATA' and 
            self.serial_forward_tab == 'rtt_channel_1' and 
            channel == 1):
            logger.debug('add_raw_rtt_data_for_forwarding: conditions met, proceeding with forwarding')
            
            if self.serial.isOpen():
                try:
                    # RTT原始数据直接转发
                    if isinstance(data, (list, bytearray)):
                        data_bytes = bytes(data)
                    elif isinstance(data, str):
                        try:
                            enc = self.main.config.get_text_encoding() if hasattr(self, 'main') and hasattr(self.main, 'config') else 'gbk'
                        except Exception:
                            enc = 'gbk'
                        data_bytes = data.encode(enc, errors='ignore')
                    else:
                        data_bytes = data
                    
                    self.serial.write(data_bytes)
                    logger.debug(f'Forwarded {len(data_bytes)} raw bytes from RTT channel {channel} to serial port')
                except Exception as e:
                    logger.error(f"Raw RTT data forward error: {e}")
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Raw RTT data forward error: %s") % str(e))

    def start(self):
        logger.debug(QCoreApplication.translate("rtt2uart", "启动RTT2UART"))
        # 记录设备连接信息
        if self.jlink_log_callback:
            self.jlink_log_callback(QCoreApplication.translate("rtt2uart", "Connecting device: %s") % self.device_info)
        try:
            if self._connect_inf != 'EXISTING':
                # 检查并确保 JLink 连接状态
                try:
                    is_connected = self.jlink.connected()
                except pylink.errors.JLinkException:
                    # 如果检查连接状态失败，假设未连接
                    is_connected = False
                    logger.warning('Failed to check JLink connection status, assuming disconnected')
                
                if not is_connected:
                    # 加载jlinkARM.dll
                    try:
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Opening JLink connection..."))
                        if self._connect_inf == 'USB':
                            if self._connect_para:
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting JLink via USB (Serial: %s)") % self._connect_para)
                                self.jlink.open(serial_no=self._connect_para)
                            else:
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting JLink via USB (Auto-detect)"))
                                self.jlink.open()
                        else:
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting JLink via TCP/IP (%s)") % self._connect_para)
                            self.jlink.open(ip_addr=self._connect_para)
                        
                        # 短暂等待连接稳定
                        import time
                        time.sleep(0.1)
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection established"))
                        
                    except pylink.errors.JLinkException as e:
                        error_msg = f"Failed to open JLink: {e}"
                        self._log_to_gui(error_msg)
                        logger.error(error_msg, exc_info=True)
                        raise Exception(error_msg)

                # 再次检查连接状态（按配置判定是否需要自动重置并重试一次）
                try:
                    if not self.jlink.connected():
                        # 断开后，根据配置决定是否自动重置
                        auto_patterns = _get_autoreset_patterns()
                        err_msg = "JLink connection failed after open"
                        if any(p in err_msg for p in auto_patterns):
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection failed after open, trying auto reset..."))
                            if self._auto_reset_jlink_connection():
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink auto reset succeeded, continue starting..."))
                            else:
                                raise Exception(err_msg)
                        else:
                            raise Exception(err_msg)
                except pylink.errors.JLinkException:
                    # 验证异常，根据配置决定是否自动重置
                    auto_patterns = _get_autoreset_patterns()
                    err_msg = "JLink connection verification failed"
                    if any(p in err_msg for p in auto_patterns):
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink verification failed, trying auto reset..."))
                        if self._auto_reset_jlink_connection():
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink auto reset succeeded, continue starting..."))
                        else:
                            raise Exception(err_msg)
                    else:
                        raise Exception(err_msg)

                # 设置连接速率
                try:
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Setting JLink speed: %s kHz") % self._speed)
                    if self.jlink.set_speed(self._speed) == False:
                        error_msg = "Set jlink speed failed"
                        self._log_to_gui(error_msg)
                        logger.error('Set speed failed', exc_info=True)
                        raise Exception(error_msg)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink speed set successfully: %s kHz") % self._speed)
                except pylink.errors.JLinkException as e:
                    error_msg = f"Set jlink speed failed: {e}"
                    self._log_to_gui(error_msg)
                    logger.error(f'Set speed failed with exception: {e}', exc_info=True)
                    raise Exception(error_msg)

                # 设置连接接口
                try:
                    interface_name = "SWD" if self._interface == pylink.enums.JLinkInterfaces.SWD else "JTAG"
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Setting JLink interface: %s") % interface_name)
                    if self.jlink.set_tif(self._interface) == False:
                        error_msg = "Set jlink interface failed"
                        self._log_to_gui(error_msg)
                        logger.error('Set interface failed', exc_info=True)
                        raise Exception(error_msg)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink interface set successfully: %s") % interface_name)
                except pylink.errors.JLinkException as e:
                    error_msg = f"Set jlink interface failed: {e}"
                    self._log_to_gui(error_msg)
                    logger.error(f'Set interface failed with exception: {e}', exc_info=True)
                    raise Exception(error_msg)

                try:
                    if self._reset == True:
                        # 只执行目标芯片复位（连接重置已在主窗口中完成）
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Resetting target chip..."))
                        self.jlink.reset(halt=False)
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Target chip reset completed"))
                        
                        # 等待目标芯片稳定
                        import time
                        time.sleep(0.3)
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Waiting for target stabilization..."))

                    # 连接目标芯片
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting to target device: %s") % self.device)
                    self.jlink.connect(self.device)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Target device connected successfully: %s") % self.device)
                    
                    # 启动RTT，对于RTT的任何操作都需要在RTT启动后进行
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting RTT..."))
                    self.jlink.rtt_start()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT started successfully"))
                    
                    # 修复首次启动问题：RTT启动后需要清理缓冲区并等待稳定
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Initializing RTT buffers..."))
                    self._initialize_rtt_buffers()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT buffers initialized"))

                except pylink.errors.JLinkException as e:
                    error_msg = f"Connect target failed: {e}"
                    self._log_to_gui(error_msg)
                    logger.error(f'Connect target failed: {e}', exc_info=True)
                    raise Exception(error_msg)
        except pylink.errors.JLinkException as errors:
            logger.error(f'Open jlink failed: {errors}', exc_info=True)
            raise Exception(f"Open jlink failed: {errors}")
        except Exception as e:
            logger.error(f'Start RTT failed: {e}', exc_info=True)
            raise

        # 修复：只有启用串口转发时才打开串口
        if self.serial_forward_tab != -1:  # -1表示禁用转发
            try:
                if self.serial.isOpen() == False:
                    # 设置串口参数并打开串口
                    self.serial.port = self.port
                    self.serial.baudrate = self.baudrate
                    self.serial.timeout = 3
                    self.serial.write_timeout = 3
                    self.serial.open()
                    logger.info(f'串口转发已启用，串口 {self.port} 打开成功')
            except:
                logger.error('Open serial failed', exc_info=True)
                raise
        else:
            logger.info(QCoreApplication.translate("rtt2uart", "Serial forwarding disabled, skipping port open"))
        
        self.thread_switch = True
        self.rtt_thread = threading.Thread(target=self.rtt_thread_exec)
        self.rtt_thread.setDaemon(True)
        self.rtt_thread.name = 'rtt_thread'
        self.rtt_thread.start()
        
        self.rtt2uart = threading.Thread(target=self.rtt2uart_exec)
        self.rtt2uart.setDaemon(True)
        self.rtt2uart.name = 'rtt2uart'
        self.rtt2uart.start()
        
        
    def stop(self):
        logger.debug(QCoreApplication.translate("rtt2uart", "stop rtt2uart - Starting to stop RTT service"))

        # 设置停止标志
        self.thread_switch = False
        logger.debug(QCoreApplication.translate("rtt2uart", "Thread stop flag set"))
        
        # 强制停止线程，增加更严格的超时处理
        self._force_stop_threads()
        
        # 改进的 JLink 关闭逻辑
        if self._connect_inf != 'EXISTING':
            self._safe_close_jlink()

        # 关闭串口
        self._safe_close_serial()
        
        # 检查并删除空的日志文件夹
        self._cleanup_empty_log_folder()
        
        logger.debug(QCoreApplication.translate("rtt2uart", "RTT service stop completed"))
    
    def _force_stop_threads(self):
        """强制停止所有RTT线程"""
        import time
        
        threads_to_stop = [
            ('RTT读取线程', self.rtt_thread),
            ('RTT2UART线程', self.rtt2uart)
        ]
        
        for thread_name, thread in threads_to_stop:
            if thread and thread.is_alive():
                logger.info(f"正在停止{thread_name}...")
                
                # 第一次尝试：优雅停止
                try:
                    thread.join(timeout=2.0)
                    if not thread.is_alive():
                        logger.info(f"{thread_name}已优雅停止")
                        continue
                except Exception as e:
                    logger.error(f"优雅停止{thread_name}时出错: {e}")
                
                # 第二次尝试：强制停止
                logger.warning(f"{thread_name}未能优雅停止，尝试强制停止...")
                try:
                    # 设置为守护线程，这样主程序退出时会强制终止
                    thread.daemon = True
                    
                    # 再次尝试join，但时间更短
                    thread.join(timeout=1.0)
                    
                    if thread.is_alive():
                        logger.error(f"{thread_name}仍在运行，将在主程序退出时被强制终止")
                    else:
                        logger.info(f"{thread_name}已强制停止")
                        
                except Exception as e:
                    logger.error(f"强制停止{thread_name}时出错: {e}")
        
        # 给线程一些时间完成清理
        time.sleep(0.2)

    def _safe_close_jlink(self):
        """安全关闭 JLink 连接"""
        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Closing JLink connection..."))
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 检查连接状态
                is_connected = False
                try:
                    is_connected = self.jlink.connected()
                except pylink.errors.JLinkException:
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Cannot check JLink connection status (retry %s)") % (retry_count + 1))
                    logger.warning(f'Cannot check JLink connection status on retry {retry_count + 1}')
                    is_connected = False
                
                if is_connected:
                    try:
                        # 停止RTT
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Stopping RTT..."))
                        self.jlink.rtt_stop()
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT stopped"))
                        logger.debug('RTT stopped successfully')
                    except pylink.errors.JLinkException as e:
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to stop RTT: %s") % str(e))
                        logger.warning(f'Failed to stop RTT: {e}')
                    
                    try:
                        # 关闭JLink连接
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Closing JLink..."))
                        self.jlink.close()
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection closed"))
                        logger.debug('JLink closed successfully')
                        break  # 成功关闭，退出循环
                    except pylink.errors.JLinkException as e:
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to close JLink (attempt %s): %s") % (retry_count + 1, str(e)))
                        logger.warning(f'Failed to close JLink on attempt {retry_count + 1}: {e}')
                        retry_count += 1
                        if retry_count < max_retries:
                            import time
                            time.sleep(0.2)  # 短暂等待后重试
                        continue
                else:
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink already disconnected"))
                    logger.debug('JLink already disconnected')
                    break
                    
            except Exception as e:
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Unexpected error while closing JLink (attempt %s): %s") % (retry_count + 1, str(e)))
                logger.error(f'Unexpected error during JLink close on attempt {retry_count + 1}: {e}')
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(0.2)
                continue
        
        if retry_count >= max_retries:
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Maximum retry attempts reached, JLink close failed"))
            logger.error('Failed to close JLink after maximum retries')

    def _safe_close_serial(self):
        """安全关闭串口连接"""
        try:
            if hasattr(self, 'serial') and self.serial and self.serial.isOpen():
                self.serial.close()
                logger.debug('Serial port closed successfully')
        except Exception as e:
            logger.error(f'Close serial failed: {e}', exc_info=True)

    def _cleanup_empty_log_folder(self):
        """检查并删除空的日志文件夹"""
        try:
            if hasattr(self, 'log_directory') and self.log_directory:
                import os
                import shutil
                from pathlib import Path
                
                log_path = Path(self.log_directory)
                if log_path.exists() and log_path.is_dir():
                    # 计算文件夹的实际大小
                    total_size = 0
                    file_count = 0
                    
                    for file_path in log_path.rglob('*'):
                        if file_path.is_file():
                            file_count += 1
                            total_size += file_path.stat().st_size
                    
                    # 如果文件夹为空或者总大小为0KB，则删除
                    if file_count == 0 or total_size == 0:
                        shutil.rmtree(str(log_path))
                        logger.info(f'Deleted empty log folder: {log_path}')
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Deleted empty log folder: %s") % str(log_path))
                    else:
                        logger.debug(f'Log folder kept: {log_path} (size: {total_size} bytes, files: {file_count})')
                        
        except Exception as e:
            logger.error(f'Failed to cleanup log folder: {e}', exc_info=True)

    def rtt_thread_exec(self):
        # 新连接修复：初始化buffer写入偏移量，避免旧数据写入新日志
        # 如果buffers中已有数据（保留的旧数据），从当前位置开始写入，而不是从头开始
        if hasattr(self.main, 'buffers') and len(self.main.buffers) > 0:
            all_chunks = self.main.buffers[0]
            current_buffer_length = sum(len(part) for part in all_chunks)
            self._last_buffer_size = current_buffer_length
            logger.info(f"初始化日志写入偏移: {current_buffer_length} 字节（跳过旧数据）")
        else:
            self._last_buffer_size = 0
        
        # 打开日志文件，如果不存在将自动创建
        # 文本日志使用可配置编码
        try:
            enc = self.main.config.get_text_encoding() if hasattr(self.main, 'config') else 'gbk'
        except Exception:
            enc = 'gbk'
        with open(self.rtt_log_filename, 'a', encoding=enc, buffering=8192) as log_file:
            # 性能优化：添加短暂延迟避免过度占用CPU
            import time
            
            # 连接状态检查优化：减少检查频率
            connection_check_counter = 0
            connection_check_interval = 100  # 每100次循环检查一次连接状态
            last_connection_warning_time = 0
            last_rtt_read_warning_time = 0  # RTT读取警告时间
            connection_warning_interval = 5.0  # 连接警告最少间隔5秒
            rtt_read_warning_interval = 2.0  # RTT读取警告最少间隔2秒
            
            while self.thread_switch:
                try:
                    # 减少连接状态检查频率，避免过多警告
                    connection_check_counter += 1
                    if connection_check_counter >= connection_check_interval:
                        connection_check_counter = 0
                        try:
                            if not self.jlink.connected():
                                current_time = time.time()
                                # 限制警告频率，避免日志刷屏
                                if current_time - last_connection_warning_time > connection_warning_interval:
                                    logger.warning('JLink connection lost in RTT thread')
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost in RTT thread"))
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost detected, auto stopping RTT"))
                                    last_connection_warning_time = current_time
                                
                                # 连接丢失时自动停止RTT功能
                                self._auto_stop_on_connection_lost()
                                break  # 退出循环
                        except pylink.errors.JLinkException as e:
                            current_time = time.time()
                            if current_time - last_connection_warning_time > connection_warning_interval:
                                logger.warning('Cannot check JLink status in RTT thread')
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Cannot check JLink status in RTT thread"))
                                last_connection_warning_time = current_time
                            
                            # 检查是否是连接丢失错误
                            if "connection has been lost" in str(e).lower():
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost, auto stopping RTT"))
                                self._auto_stop_on_connection_lost()
                                break  # 退出循环
                            
                            time.sleep(0.5)
                            continue
                    
                    # 使用 bytearray 累积数据，避免 list 拼接与后续多次拷贝
                    rtt_recv_log = bytearray()
                    # 优化：一次性读取更多数据，减少系统调用
                    max_read_attempts = 5
                    for _ in range(max_read_attempts):
                        try:
                            recv_log = self.jlink.rtt_read(0, 4096)
                            if not recv_log:
                                break
                            else:
                                # recv_log 是 list[int] 或 bytes，统一扩展到 bytearray
                                if isinstance(recv_log, (bytes, bytearray)):
                                    rtt_recv_log.extend(recv_log)
                                else:
                                    rtt_recv_log.extend(bytearray(recv_log))
                        except pylink.errors.JLinkException as e:
                            current_time = time.time()
                            if current_time - last_rtt_read_warning_time > rtt_read_warning_interval:
                                logger.warning(QCoreApplication.translate("rtt2uart", "RTT读取失败: %s") % str(e))
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT read failed: %s") % str(e))
                                last_rtt_read_warning_time = current_time
                            
                            # 检查是否是连接丢失错误，如果是则自动停止
                            if "connection has been lost" in str(e).lower():
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT read detected JLink connection lost, auto stopping RTT"))
                                self._auto_stop_on_connection_lost()
                                return  # 退出整个线程函数
                            
                            break

                    self.read_bytes0 += len(rtt_recv_log)
                    rtt_log_len = len(rtt_recv_log)

                    # 写入ALL页面的日志数据（包含通道前缀，与ALL标签页内容一致）
                    if hasattr(self.main, 'buffers') and len(self.main.buffers) > 0:
                        try:
                            # 兼容分块缓冲结构：self.main.buffers[0] 为 List[str]
                            all_chunks = self.main.buffers[0]

                            # 计算总长度并基于上次长度取增量
                            def _extract_increment(chunks, last_size):
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
                                return ''.join(out_parts), total_len

                            last_size = getattr(self, '_last_buffer_size', 0)
                            new_data, current_total_size = _extract_increment(all_chunks, last_size)

                            if new_data.strip():
                                try:
                                    # ALL页面的buffer已经是清理过的纯文本，直接写入
                                    log_file.write(new_data)
                                    log_file.flush()
                                except Exception as e:
                                    logger.error(f"Failed to write ALL buffer data: {e}")

                            self._last_buffer_size = current_total_size
                        except Exception as e:
                            logger.error(f"ALL buffer incremental write failed: {e}")
                    else:
                        # 首次运行时初始化
                        if not hasattr(self, '_last_buffer_size'):
                            self._last_buffer_size = 0

                    # 处理原始RTT数据以解析通道信息（零拷贝分帧优化）
                    if not hasattr(self, '_pending_chunk_buf'):
                        self._pending_chunk_buf = bytearray()
                    temp_buff = self._pending_chunk_buf
                    # 分隔符 0xFF；分段形式：<payload> 0xFF <chan> <payload> 0xFF <chan> ...
                    parts = bytes(rtt_recv_log).split(b'\xff')
                    # 第一段是延续的 payload
                    if parts:
                        temp_buff.extend(parts[0])
                        # 处理后续每一段：先发出上一通道数据，再切换通道并附加该段剩余
                        for seg in parts[1:]:
                            if len(temp_buff) > 0:
                                try:
                                    # 传递 bytes，避免主线程把 bytearray 当作 str 处理
                                    self.insert_char(self.tem, bytes(temp_buff))
                                finally:
                                    temp_buff.clear()
                            if not seg:
                                continue
                            # 切换通道
                            self.tem = chr(seg[0])
                            if len(seg) > 1:
                                temp_buff.extend(seg[1:])
                    # 循环结束后，temp_buff 保留未完整结束的一段，等待下一批拼接
                    else:
                        # 没有数据时短暂休眠，避免过度占用CPU
                        time.sleep(0.001)  # 1ms
                    
                except pylink.errors.JLinkException as e:
                    logger.error(f"JLink error in RTT thread: {e}")
                    time.sleep(0.1)  # JLink错误时较长休眠
                except Exception as e:
                    logger.error(f"Unexpected error in RTT thread: {e}")
                    time.sleep(0.01)  # 发生错误时稍长休眠

    def _initialize_rtt_buffers(self):
        """初始化RTT缓冲区，清理首次启动时的垃圾数据"""
        import time
        
        try:
            # 等待RTT完全稳定
            time.sleep(0.5)
            
            # 清理RTT Channel 0 和 Channel 1 的缓冲区
            # 多次读取直到缓冲区清空，丢弃这些初始垃圾数据
            for channel in [0, 1]:
                cleared_bytes = 0
                max_clear_attempts = 10
                
                for attempt in range(max_clear_attempts):
                    try:
                        # 读取并丢弃垃圾数据
                        garbage_data = self.jlink.rtt_read(channel, 4096)
                        if not garbage_data or len(garbage_data) == 0:
                            break  # 缓冲区已空
                        
                        cleared_bytes += len(garbage_data)
                        
                        # 检查是否全是空字节
                        if isinstance(garbage_data, (list, tuple)):
                            null_count = sum(1 for b in garbage_data if b == 0)
                        else:
                            null_count = garbage_data.count(0) if hasattr(garbage_data, 'count') else 0
                        
                        # 如果读取到的数据超过50%是空字节，认为是垃圾数据
                        if len(garbage_data) > 0:
                            null_percentage = (null_count / len(garbage_data)) * 100
                            if null_percentage > 50:
                                logger.debug(QCoreApplication.translate("rtt2uart", "清理RTT Channel %d垃圾数据: %d字节 (%.1f%%空字节)") % (channel, len(garbage_data), null_percentage))
                        
                        # 短暂等待，避免过快读取
                        time.sleep(0.01)
                        
                    except pylink.errors.JLinkException as e:
                        # RTT读取错误，可能缓冲区已空或RTT未就绪
                        logger.debug(f"RTT Channel {channel} clear attempt {attempt+1} failed: {e}")
                        break
                
                if cleared_bytes > 0:
                    logger.info(QCoreApplication.translate("rtt2uart", "RTT Channel %d初始化完成，清理了%d字节垃圾数据") % (channel, cleared_bytes))
            
            # 最后再等待一小段时间，确保RTT完全稳定
            time.sleep(0.2)
            
        except Exception as e:
            logger.warning(QCoreApplication.translate("rtt2uart", "RTT缓冲区初始化警告: %s") % str(e))
            # 即使初始化失败，也继续执行，不影响正常功能

    def _filter_rtt_data(self, raw_data):
        """过滤RTT原始数据，仅在首次启动时过滤明显的垃圾数据，保持RAW数据完整性"""
        if not raw_data:
            return b''
        
        # 将数据转换为bytes
        if isinstance(raw_data, (list, tuple)):
            data_bytes = bytes(raw_data)
        elif isinstance(raw_data, (bytes, bytearray)):
            data_bytes = bytes(raw_data)
        else:
            return b''
        
        total_bytes = len(data_bytes)
        if total_bytes == 0:
            return b''
        
        # 修复：只在极端情况下过滤，保持RAW数据完整性
        # 统计空字节比例
        null_count = data_bytes.count(0)
        null_percentage = (null_count / total_bytes) * 100
        
        # 只有在以下极端情况下才丢弃数据：
        # 1. 100%都是空字节（完全无效数据）
        # 2. 超过95%是空字节且数据块较大（>1KB，明显异常）
        if null_count == total_bytes:
            # 全部是空字节，丢弃
            logger.debug(QCoreApplication.translate("rtt2uart", "丢弃全空字节数据: %d字节") % total_bytes)
            return b''
        elif null_percentage > 95 and total_bytes > 1024:
            # 超过95%空字节且数据块大于1KB，可能是异常数据
            logger.debug(QCoreApplication.translate("rtt2uart", "丢弃异常数据块: %d字节 (%.1f%%空字节)") % (total_bytes, null_percentage))
            return b''
        
        # 对于正常情况，保持RAW数据完整性，不做任何过滤
        # RAW格式需要保持所有字节的原始状态，包括0x00
        return data_bytes


    def rtt2uart_exec(self):
        # 打开日志文件，如果不存在将自动创建
        with open(self.rtt_data_filename, 'ab') as data_file:
            import time
            
            # RTT2UART线程启动时等待RTT完全就绪
            startup_wait_time = 1.0  # 等待1秒确保RTT完全启动
            logger.debug(QCoreApplication.translate("rtt2uart", "RTT2UART线程等待RTT就绪..."))
            time.sleep(startup_wait_time)
            logger.debug(QCoreApplication.translate("rtt2uart", "RTT2UART线程开始数据读取"))
            
            # 连接状态检查优化：减少检查频率
            connection_check_counter = 0
            connection_check_interval = 100  # 每100次循环检查一次连接状态
            last_connection_warning_time = 0
            connection_warning_interval = 5.0  # 连接警告最少间隔5秒
            
            while self.thread_switch:
                try:
                    # 减少连接状态检查频率，避免过多警告
                    connection_check_counter += 1
                    if connection_check_counter >= connection_check_interval:
                        connection_check_counter = 0
                        try:
                            if not self.jlink.connected():
                                current_time = time.time()
                                # 限制警告频率，避免日志刷屏
                                if current_time - last_connection_warning_time > connection_warning_interval:
                                    logger.warning('JLink connection lost in RTT2UART thread')
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost in RTT2UART thread"))
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost detected, auto stopping RTT"))
                                    last_connection_warning_time = current_time
                                
                                # 连接丢失时自动停止RTT功能
                                self._auto_stop_on_connection_lost()
                                break  # 退出循环
                        except pylink.errors.JLinkException as e:
                            current_time = time.time()
                            if current_time - last_connection_warning_time > connection_warning_interval:
                                logger.warning('Cannot check JLink status in RTT2UART thread')
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Cannot check JLink status in RTT2UART thread"))
                                last_connection_warning_time = current_time
                            
                            # 检查是否是连接丢失错误
                            if "connection has been lost" in str(e).lower():
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection lost, auto stopping RTT"))
                                self._auto_stop_on_connection_lost()
                                break  # 退出循环
                            
                            time.sleep(0.5)
                            continue
                    
                    try:
                        rtt_recv_data = self.jlink.rtt_read(1, _RTT_READ_BUFFER_SIZE)
                        self.read_bytes1 += len(rtt_recv_data)

                        if len(rtt_recv_data):
                            # rtt_data.log 保存有效的原始数据，过滤掉空字节和无效数据
                            original_size = len(rtt_recv_data)
                            filtered_data = self._filter_rtt_data(rtt_recv_data)
                            filtered_size = len(filtered_data)
                            
                            if filtered_data:  # 只有在有有效数据时才写入
                                data_file.write(filtered_data)
                                data_file.flush()  # 确保及时写入
                                
                                # 记录过滤统计（仅在实际过滤时记录）
                                if filtered_size < original_size:
                                    reduction_percent = (1 - filtered_size / original_size) * 100
                                    logger.info(QCoreApplication.translate("rtt2uart", "RTT数据过滤: 原始%d字节 → 过滤后%d字节 (减少%.1f%%)") % (original_size, filtered_size, reduction_percent))
                            
                            # 使用我们的转发逻辑而不是直接写入串口
                            # 这样可以按照UI设置进行转发
                            # logger.debug(f'RTT2UART thread: received {len(rtt_recv_data)} bytes, mode={self.serial_forward_mode}, tab={self.serial_forward_tab}')
                            if (self.serial_forward_mode == 'DATA' and 
                                self.serial_forward_tab == 'rtt_channel_1'):
                                logger.debug('RTT2UART thread: calling add_raw_rtt_data_for_forwarding')
                                self.add_raw_rtt_data_for_forwarding(1, rtt_recv_data)
                            # else:
                            #     logger.debug(f'RTT2UART thread: not forwarding - mode={self.serial_forward_mode}, tab={self.serial_forward_tab}')
                        else:
                            # 没有数据时短暂休眠
                            time.sleep(0.001)
                            
                    except pylink.errors.JLinkException as e:
                        logger.warning(f'RTT2UART read failed: {e}')
                        
                        # 检查是否是需要自动重置的错误
                        error_str = str(e).lower()
                        if ("connection has been lost" in error_str or 
                            "could not connect" in error_str or
                            "no connection" in error_str or
                            "connection failed" in error_str or
                            "device not found" in error_str):
                            
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection error detected, trying auto reset..."))
                            
                            # 尝试自动重置JLink连接
                            if self._auto_reset_jlink_connection():
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset succeeded, continuing RTT data read"))
                                continue  # 重置成功，继续循环
                            else:
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset failed, stopping RTT"))
                                self._auto_stop_on_connection_lost()
                                break  # 重置失败，退出循环
                        
                        time.sleep(1)
                        
                except pylink.errors.JLinkException as e:
                    logger.error(f"JLink error in RTT2UART thread: {e}")
                    
                    # 检查是否是需要自动重置的严重错误
                    error_str = str(e).lower()
                    if ("connection has been lost" in error_str or 
                        "could not connect" in error_str or
                        "no connection" in error_str or
                        "connection failed" in error_str):
                        
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Severe JLink connection error detected, trying auto reset..."))
                        
                        if self._auto_reset_jlink_connection():
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset succeeded"))
                            continue  # 重置成功，继续
                        else:
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection reset failed, stopping RTT"))
                            self._auto_stop_on_connection_lost()
                            break
                    
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Unexpected error in RTT2UART thread: {e}")
                    time.sleep(1)


    def insert_char(self, tem, string, new_line=False):
        if '0' <= tem <= '9':
            tem_num = int(tem)
        elif 'A' <= tem <= 'F':
            tem_num = ord(tem) - ord('A') + 10
        else:
            # 处理非法输入的情况
            tem_num = 0
        
        # DATA模式下的原始数据转发由RTT2UART线程处理
        # 这里不需要重复调用，避免数据混乱
        # if (tem_num == 1 and 
        #     self.serial_forward_mode == 'DATA' and 
        #     self.serial_forward_tab == 'rtt_channel_1'):
        #     self.add_raw_rtt_data_for_forwarding(1, string)
        
        
        self.main.addToBuffer(tem_num, string);

        # if tem == ord('1'):
        #     cursor = self.ui.textEdit.textCursor()
        #     cursor.movePosition(QTextCursor.End)
        #     if new_line:
        #         cursor.insertText('\n')
        #     cursor.insertText(string.decode('gbk'))


# if __name__ == "__main__":
#     serial_name = input("请输入虚拟串口对中的串口名字，如COM26：")

#     if '' == serial_name:
#         serial_name = 'COM26'

#     test = rtt_to_serial(0, 'AMAPH1KK-KBR', serial_name, 115200)
#     test.start()
