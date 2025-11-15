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
    def __init__(self, main, jlink, connect_inf='USB', connect_para=None, device=None, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False, log_split=True, window_id=None, jlink_index=None, rtt_cb_mode='auto', rtt_address='', rtt_search_range=''):
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
        # RTT Control Block 配置
        self._rtt_cb_mode = rtt_cb_mode  # 'auto', 'address', 'search_range'
        self._rtt_address = rtt_address
        self._rtt_search_range = rtt_search_range
        
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
        
        # UI刷新暂停标志（用于暂停/恢复刷新功能）
        self.ui_refresh_paused = False
        self.paused_data_buffer = []  # 暂停期间的数据缓冲 [(tem_num, string), ...]
        self.paused_buffer_lock = threading.Lock()  # 暂停缓冲区锁
        
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
        try:
            # 检查Python解释器是否正在关闭
            import sys
            if sys.meta_path is None:
                # Python正在关闭，避免执行可能导致错误的操作
                return
                
            logger.debug(QCoreApplication.translate("rtt2uart", "关闭应用"))
            self.stop()
        except Exception:
            # 忽略所有在析构过程中可能发生的异常
            pass
    
    def set_jlink_log_callback(self, callback):
        """设置JLink日志回调函数"""
        self.jlink_log_callback = callback
    
    def _log_to_gui(self, message):
        """将消息发送到GUI日志"""
        if self.jlink_log_callback:
            try:
                self.jlink_log_callback(message)
            except RuntimeError:
                # 程序退出时GUI对象可能已被删除，忽略此错误
                pass
    
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
                try:
                    if self._connect_inf == 'USB':
                        self.jlink.open(self._connect_para)
                    else:
                        self.jlink.open()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink reopened successfully"))
                except pylink.errors.JLinkException as e:
                    error_msg = str(e)
                    # 检测到"already open"错误时，先关闭再重试
                    if "already open" in error_msg.lower() or "is open" in error_msg.lower():
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already open, closing and retrying..."))
                        import time
                        # 尝试关闭
                        try:
                            self.jlink.close()
                            time.sleep(0.3)
                        except Exception as close_e:
                            logger.warning(f"Failed to close JLink: {close_e}")
                        
                        # 检查是否真的关闭了
                        try:
                            if self.jlink.opened():
                                # 如果仍然打开，强制重新创建 JLink 对象
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink still open, recreating JLink object..."))
                                del self.jlink
                                import gc
                                gc.collect()
                                time.sleep(0.2)
                                self.jlink = pylink.JLink()
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink object recreated"))
                        except Exception as check_e:
                            logger.debug(f"Cannot check JLink status: {check_e}")
                        
                        # 重试打开
                        if self._connect_inf == 'USB':
                            self.jlink.open(self._connect_para)
                        else:
                            self.jlink.open()
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection re-established"))
                    else:
                        raise
                
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
    
    def flush_paused_data(self):
        """恢复刷新时，一次性处理暂停期间的所有数据"""
        with self.paused_buffer_lock:
            if not self.paused_data_buffer:
                logger.info("暂停缓冲区为空，无需处理")
                return
            
            buffer_count = len(self.paused_data_buffer)
            logger.info(f"🔄 开始处理暂停期间的 {buffer_count} 条数据...")
            
            # 一次性处理所有暂停的数据
            for tem_num, string in self.paused_data_buffer:
                self.main.addToBuffer(tem_num, string)
            
            # 清空暂停缓冲区
            self.paused_data_buffer.clear()
            logger.info(f"✅ 暂停数据处理完成，已处理 {buffer_count} 条数据")
    
    def clear_paused_data(self):
        """清空暂停缓冲区（关闭时使用，不处理数据）"""
        try:
            # 使用超时避免死锁
            if self.paused_buffer_lock.acquire(timeout=0.5):
                try:
                    buffer_count = len(self.paused_data_buffer)
                    if buffer_count > 0:
                        self.paused_data_buffer.clear()
                        logger.info(f"🗑️ 已清空暂停缓冲区，丢弃 {buffer_count} 条未处理数据")
                finally:
                    self.paused_buffer_lock.release()
            else:
                logger.warning("清空暂停缓冲区超时，强制清空")
                self.paused_data_buffer.clear()
        except Exception as e:
            logger.error(f"清空暂停缓冲区时出错: {e}")
    
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
        # 初始化首次数据到达标记
        self._first_data_received = False
        # 记录设备连接信息
        if self.jlink_log_callback:
            self.jlink_log_callback(QCoreApplication.translate("rtt2uart", "Connecting device: %s") % self.device_info)
        try:
            if self._connect_inf != 'EXISTING':
                # 🔑 关键修复：检查 JLink 对象是否已经打开，以及是否连接到同一设备
                # 如果连接到不同设备，需要先 close() 再重新 open()
                is_opened = False
                need_reopen = False
                try:
                    is_opened = self.jlink.opened()
                    if is_opened:
                        # JLink 已打开，检查是否连接到同一设备
                        # 通过比较设备序列号来判断
                        current_serial = None
                        try:
                            # 尝试获取当前连接的设备序列号
                            if hasattr(self.jlink, 'serial_number'):
                                current_serial = str(self.jlink.serial_number)
                            elif hasattr(self.jlink, '_serial_no'):
                                current_serial = str(self.jlink._serial_no)
                        except:
                            pass
                        
                        target_serial = str(self._connect_para) if self._connect_para else None
                        
                        if current_serial and target_serial and current_serial != target_serial:
                            # 连接到不同设备，需要重新打开
                            logger.info(f'JLink is opened for device {current_serial}, but need to connect to {target_serial}, will reopen')
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Switching to different device, reopening JLink..."))
                            need_reopen = True
                        else:
                            # 连接到同一设备，重用连接
                            logger.info('JLink is already opened for the same device, skipping open() call')
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already open, reusing connection"))
                except Exception as e:
                    # 如果检查失败，假设未打开
                    logger.debug(f'Failed to check JLink opened status: {e}')
                    is_opened = False
                
                # 如果需要重新打开（切换设备），先关闭
                if need_reopen:
                    try:
                        logger.info('Closing JLink to switch device...')
                        self.jlink.close()
                        import time
                        time.sleep(0.3)
                        is_opened = False  # 标记为未打开，需要重新 open
                    except Exception as e:
                        logger.warning(f'Failed to close JLink: {e}')
                
                if not is_opened:
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
                        
                        # 尝试获取JLink连接详细信息
                        try:
                            # 获取设备信息
                            if hasattr(self.jlink, 'core_name'):
                                core_name = self.jlink.core_name()
                                if core_name:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Core: %s") % core_name)
                            
                            if hasattr(self.jlink, 'product_name'):
                                product = self.jlink.product_name
                                if product:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Product: %s") % product)
                            
                            if hasattr(self.jlink, 'firmware_version'):
                                fw_ver = self.jlink.firmware_version
                                if fw_ver:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Firmware: %s") % fw_ver)
                            
                            if hasattr(self.jlink, 'hardware_version'):
                                hw_ver = self.jlink.hardware_version
                                if hw_ver:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Hardware: %s") % hw_ver)
                        except Exception as e:
                            logger.debug(f"Failed to get JLink info: {e}")
                        
                    except pylink.errors.JLinkException as e:
                        error_msg = str(e)
                        logger.warning(f"JLinkException caught: {error_msg}")
                        # 🔑 检测到"already open"错误时，先关闭再重试
                        # 支持多种错误消息格式
                        if "already open" in error_msg.lower() or "is open" in error_msg.lower():
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already open, closing and retrying..."))
                            try:
                                import time
                                # 尝试关闭
                                try:
                                    self.jlink.close()
                                    time.sleep(0.3)  # 等待关闭完成
                                except Exception as close_e:
                                    logger.warning(f"Failed to close JLink: {close_e}")
                                
                                # 检查是否真的关闭了
                                try:
                                    if self.jlink.opened():
                                        # 如果仍然打开，强制重新创建 JLink 对象
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink still open, recreating JLink object..."))
                                        del self.jlink
                                        import gc
                                        gc.collect()
                                        time.sleep(0.2)
                                        self.jlink = pylink.JLink()
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink object recreated"))
                                except Exception as check_e:
                                    logger.debug(f"Cannot check JLink status: {check_e}")
                                
                                # 重试打开
                                if self._connect_inf == 'USB':
                                    if self._connect_para:
                                        self.jlink.open(serial_no=self._connect_para)
                                    else:
                                        self.jlink.open()
                                else:
                                    self.jlink.open(ip_addr=self._connect_para)
                                
                                time.sleep(0.1)
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection re-established"))
                                
                                # 重新获取JLink连接详细信息
                                try:
                                    if hasattr(self.jlink, 'core_name'):
                                        core_name = self.jlink.core_name()
                                        if core_name:
                                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Core: %s") % core_name)
                                    
                                    if hasattr(self.jlink, 'product_name'):
                                        product = self.jlink.product_name
                                        if product:
                                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Product: %s") % product)
                                    
                                    if hasattr(self.jlink, 'firmware_version'):
                                        fw_ver = self.jlink.firmware_version
                                        if fw_ver:
                                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Firmware: %s") % fw_ver)
                                    
                                    if hasattr(self.jlink, 'hardware_version'):
                                        hw_ver = self.jlink.hardware_version
                                        if hw_ver:
                                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Hardware: %s") % hw_ver)
                                except Exception as info_e:
                                    logger.debug(f"Failed to get JLink info after retry: {info_e}")
                            except Exception as retry_e:
                                error_msg = f"Failed to reopen JLink: {retry_e}"
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to reopen JLink: %s") % str(retry_e))
                                logger.error(error_msg, exc_info=True)
                                raise Exception(error_msg)
                        else:
                            error_msg = f"Failed to open JLink: {e}"
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to open JLink: %s") % str(e))
                            logger.error(error_msg, exc_info=True)
                            raise Exception(error_msg)

                # 🔑 如果 JLink 已经打开（重用的情况），检查是否已经连接到目标设备
                # 如果已连接，跳过后续的 connect() 调用，避免 "already open" 错误
                already_connected_to_target = False
                if is_opened:
                    try:
                        if self.jlink.connected():
                            # JLink 已连接，检查是否连接到同一设备
                            # 注意：pylink 库没有直接的方法获取当前连接的设备名称
                            # 我们假设如果 JLink 已打开且已连接，就是连接到同一设备
                            logger.info(f'JLink is already connected to a target device')
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already connected to target device"))
                            already_connected_to_target = True
                    except Exception as e:
                        logger.debug(f'Failed to check JLink connected status: {e}')
                
                # 再次检查连接状态（按配置判定是否需要自动重置并重试一次）
                if not already_connected_to_target:
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
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Set JLink speed failed"))
                        logger.error('Set speed failed', exc_info=True)
                        raise Exception(error_msg)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink speed set successfully: %s kHz") % self._speed)
                except pylink.errors.JLinkException as e:
                    error_msg = f"Set jlink speed failed: {e}"
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Set JLink speed failed: %s") % str(e))
                    logger.error(f'Set speed failed with exception: {e}', exc_info=True)
                    raise Exception(error_msg)

                # 设置连接接口
                try:
                    interface_name = "SWD" if self._interface == pylink.enums.JLinkInterfaces.SWD else "JTAG"
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Setting JLink interface: %s") % interface_name)
                    if self.jlink.set_tif(self._interface) == False:
                        error_msg = "Set jlink interface failed"
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Set JLink interface failed"))
                        logger.error('Set interface failed', exc_info=True)
                        raise Exception(error_msg)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink interface set successfully: %s") % interface_name)
                except pylink.errors.JLinkException as e:
                    error_msg = f"Set jlink interface failed: {e}"
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Set JLink interface failed: %s") % str(e))
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
                    # 🔑 如果 JLink 已经连接到目标设备（重用的情况），跳过 connect() 调用
                    if not already_connected_to_target:
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting to target device: %s") % self.device)
                        self.jlink.connect(self.device)
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Target device connected successfully: %s") % self.device)
                    else:
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Skipping connect, already connected to target device: %s") % self.device)
                    
                    # 启动RTT，对于RTT的任何操作都需要在RTT启动后进行
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting RTT..."))
                    
                    # 根据RTT Control Block配置启动RTT
                    if self._rtt_cb_mode == 'address' and self._rtt_address:
                        # 使用指定地址启动RTT
                        try:
                            address = int(self._rtt_address, 16)  # 转换十六进制地址
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Using RTT Control Block address: %s") % self._rtt_address)
                            
                            # 验证指定地址是否有 RTT 控制块
                            try:
                                # 读取指定地址的前 16 字节，检查是否是 "SEGGER RTT"
                                data = self.jlink.memory_read8(address, 16)
                                data_bytes = bytes(data)
                                rtt_id = b"SEGGER RTT"
                                
                                if data_bytes.startswith(rtt_id):
                                    logger.info(f"Verified RTT Control Block at 0x{address:08X}")
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Verified RTT Control Block at address: 0x%08X") % address)
                                    self.jlink.rtt_start(address)
                                else:
                                    error_msg = QCoreApplication.translate("rtt2uart", "No RTT Control Block found at specified address: 0x%08X") % address
                                    self._log_to_gui(error_msg)
                                    logger.error(f"No RTT Control Block at 0x{address:08X}, found: {data_bytes[:16]}")
                                    raise Exception(error_msg)
                            except Exception as e:
                                if "No RTT Control Block found" in str(e):
                                    raise  # 重新抛出验证失败的错误
                                # 其他错误（如内存读取失败）也应该停止
                                error_msg = QCoreApplication.translate("rtt2uart", "Failed to verify address 0x%08X: %s") % (address, str(e))
                                self._log_to_gui(error_msg)
                                logger.error(f"Failed to verify address 0x{address:08X}: {e}")
                                raise Exception(error_msg)
                                
                        except ValueError as e:
                            error_msg = QCoreApplication.translate("rtt2uart", "Invalid address format: %s") % self._rtt_address
                            self._log_to_gui(error_msg)
                            logger.error(f"Invalid address format: {self._rtt_address}")
                            raise Exception(error_msg)
                    elif self._rtt_cb_mode == 'search_range' and self._rtt_search_range:
                        # 使用搜索范围启动RTT
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Using RTT Control Block search range: %s") % self._rtt_search_range)
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Searching for RTT Control Block in memory..."))
                        
                        # 解析搜索范围并搜索控制块
                        cb_addr = None
                        try:
                            # 解析搜索范围，格式: "0x20000000 0x10000" 或 "0x20000000 0x10000, 0x30000000 0x10000"
                            ranges = self._rtt_search_range.split(',')
                            rtt_id = b"SEGGER RTT"
                            search_chunk = 0x1000  # 每次搜索 4KB
                            
                            for range_str in ranges:
                                parts = range_str.strip().split()
                                if len(parts) >= 2:
                                    try:
                                        ram_start = int(parts[0], 16) if parts[0].startswith('0x') else int(parts[0])
                                        ram_size = int(parts[1], 16) if parts[1].startswith('0x') else int(parts[1])
                                        
                                        logger.info(f"Searching range: 0x{ram_start:08X} - 0x{ram_start + ram_size:08X}")
                                        
                                        for offset in range(0, ram_size, search_chunk):
                                            try:
                                                addr = ram_start + offset
                                                data = self.jlink.memory_read8(addr, min(search_chunk, ram_size - offset))
                                                data_bytes = bytes(data)
                                                pos = data_bytes.find(rtt_id)
                                                if pos >= 0:
                                                    cb_addr = addr + pos
                                                    logger.info(f"Found RTT Control Block at 0x{cb_addr:08X}")
                                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Found RTT Control Block at address: 0x%08X") % cb_addr)
                                                    break
                                            except Exception:
                                                pass
                                        
                                        if cb_addr:
                                            break
                                    except ValueError:
                                        logger.warning(f"Invalid range format: {range_str}")
                            
                            if cb_addr:
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting RTT with Control Block at 0x%08X") % cb_addr)
                                self.jlink.rtt_start(block_address=cb_addr)
                            else:
                                error_msg = QCoreApplication.translate("rtt2uart", "RTT Control Block not found in specified range")
                                self._log_to_gui(error_msg)
                                logger.error(f"RTT Control Block not found in range: {self._rtt_search_range}")
                                raise Exception(error_msg)
                        except Exception as e:
                            if "not found in specified range" in str(e):
                                raise  # 重新抛出，不要继续
                            logger.error(f"Range search failed: {e}")
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Memory search failed: %s") % str(e))
                            raise Exception(f"Range search failed: {e}")
                    else:
                        # 自动检测模式：先搜索内存找到控制块地址
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Searching for RTT Control Block in memory..."))
                        
                        cb_addr = None
                        try:
                            # nRF52840 的 RAM 范围: 0x20000000 - 0x20040000 (256KB)
                            # TODO: 根据不同芯片调整范围
                            ram_start = 0x20000000
                            ram_size = 0x40000  # 256KB
                            search_chunk = 0x1000  # 每次搜索 4KB
                            
                            # RTT 控制块的标识符 "SEGGER RTT"
                            rtt_id = b"SEGGER RTT"
                            
                            for offset in range(0, ram_size, search_chunk):
                                try:
                                    addr = ram_start + offset
                                    # 读取内存块
                                    data = self.jlink.memory_read8(addr, min(search_chunk, ram_size - offset))
                                    
                                    # 转换为 bytes
                                    data_bytes = bytes(data)
                                    
                                    # 查找标识符
                                    pos = data_bytes.find(rtt_id)
                                    if pos >= 0:
                                        cb_addr = addr + pos
                                        logger.info(f"Found RTT Control Block at 0x{cb_addr:08X}")
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Found RTT Control Block at address: 0x%08X") % cb_addr)
                                        break
                                except Exception as e:
                                    # 某些内存区域可能不可读，跳过
                                    pass
                            
                            if not cb_addr:
                                error_msg = QCoreApplication.translate("rtt2uart", "RTT Control Block not found in memory (0x%08X - 0x%08X)") % (ram_start, ram_start + ram_size)
                                self._log_to_gui(error_msg)
                                logger.error(f"RTT Control Block not found in RAM: 0x{ram_start:08X} - 0x{ram_start + ram_size:08X}")
                                raise Exception(error_msg)
                            else:
                                # 使用找到的地址启动 RTT
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting RTT with Control Block at 0x%08X") % cb_addr)
                                self.jlink.rtt_start(block_address=cb_addr)
                                
                        except Exception as e:
                            if "not found in memory" in str(e):
                                raise  # 重新抛出，不要继续
                            logger.error(f"Memory search failed: {e}")
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Memory search failed: %s") % str(e))
                            raise Exception(f"Memory search failed: {e}")
                    
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT started successfully"))
                    
                    # 修复首次启动问题：RTT启动后需要清理缓冲区并等待稳定
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Initializing RTT buffers..."))
                    self._initialize_rtt_buffers()
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT buffers initialized"))
                    
                    # 启动延迟线程获取 RTT 通道信息
                    import threading
                    def get_rtt_info_delayed():
                        """延迟获取 RTT 通道信息"""
                        import time
                        time.sleep(2)  # 等待 2 秒让 RTT 完全初始化
                        
                        logger.info("=== get_rtt_info_delayed started ===")
                        
                        try:
                            # 获取通道信息
                            num_up = self.jlink.rtt_get_num_up_buffers()
                            num_down = self.jlink.rtt_get_num_down_buffers()
                            
                            logger.info(f"RTT channels: {num_up} up, {num_down} down")
                            
                            if num_up > 0 or num_down > 0:
                                # 收集所有要显示的信息
                                messages = []
                                
                                messages.append(QCoreApplication.translate("rtt2uart", "RTT Channel Info:"))
                                messages.append(QCoreApplication.translate("rtt2uart", "  Up channels: %d") % num_up)
                                
                                # 打印每个上行通道的详细信息
                                for i in range(num_up):
                                    try:
                                        buf_info = self.jlink.rtt_get_buf_descriptor(i, True)
                                        name = buf_info.name.decode('utf-8') if isinstance(buf_info.name, bytes) else str(buf_info.name)
                                        size = buf_info.SizeOfBuffer
                                        flags = buf_info.Flags
                                        mode_str = {0: "skip", 1: "trim", 2: "block"}.get(flags, f"mode{flags}")
                                        messages.append(QCoreApplication.translate("rtt2uart", "    #%d %s: %d bytes, %s") % (i, name, size, mode_str))
                                    except Exception as e:
                                        logger.warning(f"Failed to get up buffer {i} info: {e}")
                                
                                messages.append(QCoreApplication.translate("rtt2uart", "  Down channels: %d") % num_down)
                                
                                # 打印每个下行通道的详细信息
                                for i in range(num_down):
                                    try:
                                        buf_info = self.jlink.rtt_get_buf_descriptor(i, False)
                                        name = buf_info.name.decode('utf-8') if isinstance(buf_info.name, bytes) else str(buf_info.name)
                                        size = buf_info.SizeOfBuffer
                                        flags = buf_info.Flags
                                        mode_str = {0: "skip", 1: "trim", 2: "block"}.get(flags, f"mode{flags}")
                                        messages.append(QCoreApplication.translate("rtt2uart", "    #%d %s: %d bytes, %s") % (i, name, size, mode_str))
                                    except Exception as e:
                                        logger.warning(f"Failed to get down buffer {i} info: {e}")
                                
                                # 在主线程中显示所有消息
                                logger.info(f"Collected {len(messages)} messages, sending to GUI...")
                                for msg in messages:
                                    QTimer.singleShot(0, lambda m=msg: self._log_to_gui(m))
                                logger.info("Messages sent to GUI")
                            else:
                                logger.debug("No RTT channels found")
                                    
                        except Exception as e:
                            logger.error(f"!!! Failed to get RTT info: {e}", exc_info=True)
                            # 在主线程中显示错误
                            QTimer.singleShot(0, lambda: self._log_to_gui(f"ERROR getting RTT info: {e}"))
                            # 不影响正常流程，继续执行
                        
                        logger.info("=== get_rtt_info_delayed finished ===")
                    
                    # 启动延迟获取线程
                    logger.info("Starting rtt_info_getter thread...")
                    info_thread = threading.Thread(target=get_rtt_info_delayed, daemon=True, name="rtt_info_getter")
                    info_thread.start()
                    logger.info("rtt_info_getter thread started")

                except pylink.errors.JLinkException as e:
                    error_msg = f"Connect target failed: {e}"
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connect target failed: %s") % str(e))
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
        
        
    def stop(self, keep_folder=False):
        """停止RTT服务
        
        Args:
            keep_folder: 如果为True，保留日志文件夹（用于自动重连）；如果为False，清理空文件夹
        """
        logger.debug(QCoreApplication.translate("rtt2uart", "stop rtt2uart - Starting to stop RTT service"))

        # 清空暂停缓冲区（如果有），避免关闭时卡住
        self.clear_paused_data()
        
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
        
        # 检查并删除空的日志文件夹（除非需要保留）
        if not keep_folder:
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
                
                # 第一次尝试：优雅停止,减少超时时间避免长时间卡住
                try:
                    thread.join(timeout=0.5)  # 从2.0秒减少到0.5秒
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
                    thread.join(timeout=0.3)  # 从1.0秒减少到0.3秒
                    
                    if thread.is_alive():
                        logger.warning(f"{thread_name}仍在运行，将在主程序退出时被强制终止")
                    else:
                        logger.info(f"{thread_name}已强制停止")
                        
                except Exception as e:
                    logger.error(f"强制停止{thread_name}时出错: {e}")
        
        # 给线程一些时间完成清理
        try:
            time.sleep(0.2)
        except OSError:
            # 程序退出时可能句柄已无效，忽略此错误
            pass

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
                # 检查是否是访问冲突错误(pylink库的已知问题,不影响功能)
                error_msg = str(e).lower()
                if 'access violation' in error_msg or 'access denied' in error_msg:
                    # 访问冲突是pylink库在关闭时的已知问题,降低日志级别
                    logger.warning(f'JLink close triggered access violation (attempt {retry_count + 1}), this is a known pylink issue and can be ignored')
                    # 访问冲突通常意味着JLink已经被释放,直接退出
                    break
                else:
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Unexpected error while closing JLink (attempt %s): %s") % (retry_count + 1, str(e)))
                    logger.error(f'Unexpected error during JLink close on attempt {retry_count + 1}: {e}')
                    retry_count += 1
                    if retry_count < max_retries:
                        import time
                        try:
                            time.sleep(0.2)
                        except OSError:
                            # 程序退出时可能句柄已无效，忽略此错误
                            pass
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
        # MDI架构：重连时buffer保留旧数据继续累计显示
        # 关键：_last_buffer_size必须设置为0,否则_extract_increment会跳过旧数据
        # 这样新数据会立即显示,而不是等到超过旧buffer长度
        self._last_buffer_size = 0
        logger.info(f"初始化日志写入偏移: 0 字节（重连时继续累计显示）")
        
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
                    # 在循环开始时检查停止标志,快速响应停止请求
                    if not self.thread_switch:
                        break
                    
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
                    
                    # 优化：暂停模式下直接跳过数据获取和处理，大幅降低CPU占用
                    if self.ui_refresh_paused:
                        time.sleep(0.3)  # 暂停模式下休眠300ms
                        continue
                    
                    # 初始化数据标志，用于后续休眠策略调整
                    has_data = False
                    
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
                    
                    # 首次数据到达时间戳记录
                    if not self._first_data_received and rtt_log_len > 0:
                        self._first_data_received = True
                        from datetime import datetime
                        first_data_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        logger.info(f"⏱️ 首次数据到达时间: {first_data_time} (接收 {rtt_log_len} 字节)")

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
                            
                            # 文件写入后检查停止标志,快速响应停止请求
                            if not self.thread_switch:
                                break
                        except Exception as e:
                            logger.error(f"ALL buffer incremental write failed: {e}")
                    else:
                        # 首次运行时初始化
                        if not hasattr(self, '_last_buffer_size'):
                            self._last_buffer_size = 0

                    # 处理原始RTT数据以解析通道信息（零拷贝分帧优化）
                    if rtt_log_len > 0:
                        has_data = True
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
                    
                    # 根据是否有数据调整休眠策略
                    if not has_data and rtt_log_len == 0:
                        # 无数据时，使用更长的休眠时间
                        time.sleep(0.01)  # 10ms休眠，大幅降低CPU占用
                    else:
                        # 有数据时，短暂休眠
                        time.sleep(0.005)  # 5ms休眠
                        # 根据暂停状态调整休眠时间和数据处理策略
                        if self.ui_refresh_paused:
                            # 暂停模式下：
                            # 1. 使用更长的休眠时间
                            # 2. 不获取新数据，避免频繁添加到暂停缓冲区
                            time.sleep(0.3)  # 300ms，进一步降低暂停时CPU占用
                        else:
                            # 正常模式下短暂休眠
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
            # 极短等待，让RTT就绪（减少到50ms）
            time.sleep(0.05)
            
            # 清理RTT Channel 0 和 Channel 1 的缓冲区
            # 快速读取并丢弃初始垃圾数据，不等待
            for channel in [0, 1]:
                cleared_bytes = 0
                max_clear_attempts = 5  # 减少尝试次数
                
                for attempt in range(max_clear_attempts):
                    try:
                        # 读取并丢弃垃圾数据
                        garbage_data = self.jlink.rtt_read(channel, 4096)
                        if not garbage_data or len(garbage_data) == 0:
                            break  # 缓冲区已空
                        
                        cleared_bytes += len(garbage_data)
                        
                        # 不再等待，直接继续读取
                        
                    except pylink.errors.JLinkException as e:
                        # RTT读取错误，可能缓冲区已空或RTT未就绪
                        logger.debug(f"RTT Channel {channel} clear attempt {attempt+1} failed: {e}")
                        break
                
                if cleared_bytes > 0:
                    logger.info(QCoreApplication.translate("rtt2uart", "RTT Channel %d初始化完成，清理了%d字节垃圾数据") % (channel, cleared_bytes))
            
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
                    # 在循环开始时检查停止标志,快速响应停止请求
                    if not self.thread_switch:
                        break
                    
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
                    
                    # 优化：暂停模式下直接跳过数据获取和处理，大幅降低CPU占用
                    if self.ui_refresh_paused:
                        time.sleep(0.3)  # 暂停模式下休眠300ms
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
                            # 根据暂停状态调整休眠时间和数据处理策略
                            if self.ui_refresh_paused:
                                # 暂停模式下：
                                # 1. 使用更长的休眠时间
                                # 2. 减少数据获取频率，避免频繁操作暂停缓冲区
                                time.sleep(0.3)  # 300ms，进一步降低暂停时CPU占用
                            else:
                                # 正常模式下休眠时间优化，从1ms增加到5ms，大幅降低CPU占用
                                time.sleep(0.005)  # 5ms
                            
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
        
        # 🔄 检查UI刷新暂停标志
        if self.ui_refresh_paused:
            # 暂停时：将数据保存到暂停缓冲区，不发送给Worker
            with self.paused_buffer_lock:
                self.paused_data_buffer.append((tem_num, string))
        else:
            # 正常时：直接发送给Worker
            self.main.addToBuffer(tem_num, string)

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
