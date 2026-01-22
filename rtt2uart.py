import logging
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
class rtt_to_serial():
    def __init__(self, worker, jlink, connect_inf='USB', connect_para=None, device=None, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False, log_split=True, window_id=None, jlink_index=None, rtt_cb_mode='auto', rtt_address='', rtt_search_range='', skip_rtt_block_detection=False):
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
        self._skip_rtt_block_detection = skip_rtt_block_detection  # 跳过RTT块识别（用于F9重启）
        
        self.worker = worker
        
        # 串口参数
        self.port = port
        self.baudrate = baudrate

        self.jlink = jlink
        
        self.read_bytes0 = 0
        self.read_bytes1 = 0
        self.write_bytes0 = 0
        # JLink 入口数据时间戳（NO DATA 判定用）
        self.last_jlink_data_time = 0.0

        # 线程
        self._write_lock = threading.Lock()
        # JLink API lock: pylink is not thread-safe; Watch/Memory + RTT thread may call JLink concurrently.
        self._jlink_lock = threading.RLock()
        # JLink hang guard
        self._jlink_hung = False
        self._jlink_hung_ts = 0.0
        # 启动/重连期间暂停读线程，避免 "DLL is not open" 噪音
        self._suspend_rtt_reads = False

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
        
        # RTT数据处理器功能已移至Worker类中
        
        # UI刷新暂停标志（用于暂停/恢复刷新功能）
        self.ui_refresh_paused = False
        # 暂停原因：None / 'manual' / 'auto'
        # - manual: 用户手动F5或UI按钮触发，必须手动F6恢复
        # - auto: 文本选择触发，鼠标松开后5秒自动恢复
        self.ui_refresh_pause_reason = None
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
        self.rtt_log_filename = os.path.join(log_directory, "rtt_log.raw")
        self.rtt_data_filename = os.path.join(log_directory, "rtt_data.bin")
        self.rtt_log_prefix = os.path.join(log_directory, "rtt_log")


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
                cb = self.jlink_log_callback
                # 🛡️ 线程安全：如果回调绑定到 Qt QObject（主窗口），必须投递到GUI线程执行
                try:
                    target = getattr(cb, "__self__", None)
                    if target is not None and isinstance(target, QObject) and hasattr(target, "_append_jlink_log_queued"):
                        # 如果当前线程不是目标QObject线程，使用QueuedConnection投递
                        if QThread.currentThread() != target.thread():
                            QMetaObject.invokeMethod(
                                target,
                                "_append_jlink_log_queued",
                                Qt.QueuedConnection,
                                Q_ARG(str, str(message)),
                            )
                            return
                except Exception:
                    pass

                cb(message)
            except RuntimeError:
                # 程序退出时GUI对象可能已被删除，忽略此错误
                pass

    def _call_jlink_with_timeout(self, desc: str, fn, timeout_sec: float = 5.0):
        """Run a JLink call with a hard timeout to avoid infinite hangs (device busy, driver issues, etc.)."""
        # 强制超时上限 5 秒
        try:
            timeout_sec = float(timeout_sec)
        except Exception:
            timeout_sec = 5.0
        timeout_sec = 5.0 if timeout_sec <= 0 else min(timeout_sec, 5.0)
        result = {"exc": None}

        def _runner():
            try:
                with self._jlink_lock:
                    fn()
            except Exception as e:
                result["exc"] = e

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join(float(timeout_sec))

        if t.is_alive():
            try:
                self._force_disconnect_after_timeout(desc, timeout_sec)
            except Exception:
                pass
            raise TimeoutError(f"{desc} timeout after {timeout_sec:.1f}s")
        if result["exc"] is not None:
            raise result["exc"]
        return True
    
    def _force_disconnect_after_timeout(self, desc: str, timeout_sec: float):
        """JLink 调用超时后的强制断开处理"""
        if getattr(self, "_jlink_hung", False):
            return
        self._jlink_hung = True
        self._jlink_hung_ts = time.time()
        try:
            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink call timeout (%s, %.1fs). Forcing disconnect.") % (desc, timeout_sec))
        except Exception:
            pass
        # 立即停止线程，避免继续阻塞
        self.thread_switch = False
        # 通知主窗口并进入安全停止流程（跳过JLink关闭）
        try:
            self._auto_stop_on_connection_lost()
        except Exception:
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
                    self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
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
                        self._call_jlink_with_timeout(
                            "jlink.open(usb)",
                            lambda: self.jlink.open(self._connect_para),
                            5.0,
                        )
                    else:
                        self._call_jlink_with_timeout("jlink.open()", lambda: self.jlink.open(), 5.0)
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink reopened successfully"))
                except pylink.errors.JLinkException as e:
                    error_msg = str(e)
                    # 检测到"already open"错误时，先关闭再重试
                    if "already open" in error_msg.lower() or "is open" in error_msg.lower():
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already open, closing and retrying..."))
                        import time
                        # 尝试关闭
                        try:
                            self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
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
                            self._call_jlink_with_timeout(
                                "jlink.open(usb)",
                                lambda: self.jlink.open(self._connect_para),
                                5.0,
                            )
                        else:
                            self._call_jlink_with_timeout("jlink.open()", lambda: self.jlink.open(), 5.0)
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
                self._call_jlink_with_timeout(
                    "jlink.connect(...)",
                    lambda: self.jlink.connect(self.device),
                    5.0,
                )
                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Target device reconnected: %s") % str(self.device))
                
                # 重新启动RTT
                self._call_jlink_with_timeout("jlink.rtt_start()", lambda: self.jlink.rtt_start(), 5.0)
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
            
            # 安全清理RTT连接状态（若已判定 JLink 卡死，则跳过 close）
            try:
                if getattr(self, "_jlink_hung", False):
                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is unresponsive, skip close()"))
                else:
                    if hasattr(self, 'jlink') and self.jlink:
                        try:
                            if self.jlink.connected():
                                self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection safely disconnected"))
                        except Exception:
                            pass  # 忽略断开时的错误
            except Exception:
                pass
            
            # 通知主窗口连接已断开
            if hasattr(self.worker, '_handle_connection_lost'):
                try:
                    # 使用Qt的信号机制安全地通知主线程
                    from PySide6.QtCore import QMetaObject, Qt
                    QMetaObject.invokeMethod(
                        self.worker, 
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
                self.worker.addToBuffer(tem_num, string)
            
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
                            enc = self.worker.config.get_text_encoding() if hasattr(self, 'main') and hasattr(self.worker, 'config') else 'gbk'
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
                            enc = self.worker.config.get_text_encoding() if hasattr(self, 'main') and hasattr(self.worker, 'config') else 'gbk'
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
        # 重置JLink卡死标记
        self._jlink_hung = False
        # 启动/重连期间暂停读线程
        self._suspend_rtt_reads = True
        # 初始化首次数据到达标记
        self._first_data_received = False
        # 记录设备连接信息
        if self.jlink_log_callback:
            self.jlink_log_callback(QCoreApplication.translate("rtt2uart", "Connecting device: %s") % self.device_info)
        try:
            if self._connect_inf != 'EXISTING':
                # 🔑 启动时清理：先检查并关闭任何可能残留的连接
                try:
                    with self._jlink_lock:
                        _is_opened0 = self.jlink.opened()
                    if _is_opened0:
                        logger.warning("Found existing JLink connection at startup, closing it first...")
                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Found existing JLink connection, closing it first..."))
                        try:
                            self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
                            import time
                            time.sleep(0.5)  # 等待关闭完成
                            logger.info("Closed existing JLink connection at startup")
                        except Exception as cleanup_e:
                            logger.warning(f"Failed to close existing JLink connection: {cleanup_e}")
                except Exception as check_e:
                    # 如果检查失败，可能是未打开，继续正常流程
                    logger.debug(f"Cannot check JLink status at startup: {check_e}")
                
                # 🔑 关键修复：检查 JLink 对象是否已经打开，以及是否连接到同一设备
                # 如果连接到不同设备，需要先 close() 再重新 open()
                is_opened = False
                need_reopen = False
                try:
                    with self._jlink_lock:
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
                        self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
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
                                self._call_jlink_with_timeout(
                                    "jlink.open(serial_no=...)",
                                    lambda: self.jlink.open(serial_no=self._connect_para),
                                    5.0,
                                )
                            else:
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting JLink via USB (Auto-detect)"))
                                self._call_jlink_with_timeout("jlink.open()", lambda: self.jlink.open(), 5.0)
                        else:
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Connecting JLink via TCP/IP (%s)") % self._connect_para)
                            self._call_jlink_with_timeout(
                                "jlink.open(ip_addr=...)",
                                lambda: self.jlink.open(ip_addr=self._connect_para),
                                5.0,
                            )
                        
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
                                
                                # 第一步：检查当前状态
                                is_opened = False
                                try:
                                    with self._jlink_lock:
                                        is_opened = self.jlink.opened()
                                    logger.debug(f"JLink opened status before close: {is_opened}")
                                except Exception as check_before_e:
                                    logger.debug(f"Cannot check JLink status before close: {check_before_e}")
                                    # 如果无法检查状态，假设是打开的
                                    is_opened = True
                                
                                # 第二步：如果已打开，尝试关闭
                                if is_opened:
                                    try:
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Closing existing JLink connection..."))
                                        self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
                                        time.sleep(0.5)  # 增加等待时间，确保DLL层面完全关闭
                                        logger.debug("JLink close() called, waiting for DLL to release")
                                    except Exception as close_e:
                                        logger.warning(f"Failed to close JLink: {close_e}")
                                        # 即使关闭失败，也继续尝试清理
                                
                                # 第三步：验证是否真的关闭了
                                max_verify_attempts = 5
                                verify_attempt = 0
                                still_opened = True
                                
                                while verify_attempt < max_verify_attempts and still_opened:
                                    try:
                                        with self._jlink_lock:
                                            still_opened = self.jlink.opened()
                                        if not still_opened:
                                            logger.debug(f"JLink confirmed closed after {verify_attempt + 1} verification attempt(s)")
                                            break
                                        else:
                                            logger.debug(f"JLink still opened after close, attempt {verify_attempt + 1}/{max_verify_attempts}")
                                            verify_attempt += 1
                                            if verify_attempt < max_verify_attempts:
                                                time.sleep(0.3)  # 等待更长时间
                                    except Exception as verify_e:
                                        # 如果检查状态失败，可能是已经关闭了（某些情况下opened()会抛出异常）
                                        logger.debug(f"Cannot verify JLink status (may be closed): {verify_e}")
                                        still_opened = False
                                        break
                                
                                # 第四步：如果仍然打开，强制重新创建 JLink 对象
                                if still_opened:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink still open, recreating JLink object..."))
                                    try:
                                        # 尝试最后一次强制关闭
                                        try:
                                            self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
                                        except:
                                            pass
                                        
                                        # 删除旧对象并强制垃圾回收
                                        old_jlink = self.jlink
                                        self.jlink = None
                                        del old_jlink
                                        import gc
                                        gc.collect()
                                        time.sleep(1.0)  # 增加等待时间，确保DLL层面完全释放
                                        
                                        # 创建新的 JLink 对象
                                        self.jlink = pylink.JLink()
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink object recreated"))
                                        logger.info("JLink object recreated after failed close")
                                        
                                        # 🔑 关键修复：检查新对象是否也认为已打开（DLL层面可能仍保持状态）
                                        time.sleep(0.5)  # 等待新对象初始化
                                        try:
                                            with self._jlink_lock:
                                                new_is_opened = self.jlink.opened()
                                            if new_is_opened:
                                                logger.warning("New JLink object also reports as opened, attempting to close it...")
                                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "New JLink object reports as opened, closing it..."))
                                                try:
                                                    self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
                                                    time.sleep(1.0)  # 等待关闭完成
                                                    # 再次验证
                                                    with self._jlink_lock:
                                                        still_opened_after_new_close = self.jlink.opened()
                                                    if still_opened_after_new_close:
                                                        logger.error("JLink still reports as opened after closing new object - DLL may be locked by another process")
                                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "Warning: JLink DLL may be locked by another process"))
                                                    else:
                                                        logger.info("Successfully closed new JLink object")
                                                except Exception as new_close_e:
                                                    logger.warning(f"Failed to close new JLink object: {new_close_e}")
                                        except Exception as check_new_e:
                                            logger.debug(f"Cannot check new JLink object status: {check_new_e}")
                                        
                                        # 再次等待，确保可以安全打开
                                        time.sleep(0.5)
                                    except Exception as recreate_e:
                                        logger.error(f"Failed to recreate JLink object: {recreate_e}")
                                        raise Exception(f"Failed to recreate JLink object: {recreate_e}")
                                
                                # 第五步：重试打开
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "Retrying JLink connection..."))
                                if self._connect_inf == 'USB':
                                    if self._connect_para:
                                        self._call_jlink_with_timeout(
                                            "jlink.open(serial_no=...)",
                                            lambda: self.jlink.open(serial_no=self._connect_para),
                                            5.0,
                                        )
                                    else:
                                        self._call_jlink_with_timeout("jlink.open()", lambda: self.jlink.open(), 5.0)
                                else:
                                    self._call_jlink_with_timeout(
                                        "jlink.open(ip_addr=...)",
                                        lambda: self.jlink.open(ip_addr=self._connect_para),
                                        5.0,
                                    )
                                
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
                                error_msg = str(retry_e)
                                # 如果是 "already open" 错误，提供更详细的提示
                                if "already open" in error_msg.lower() or "is open" in error_msg.lower():
                                    detailed_msg = QCoreApplication.translate("rtt2uart", "Failed to reopen JLink: J-Link is already open.\n\nPossible causes:\n1. Another process is using JLink (check Task Manager)\n2. Previous session did not close properly\n3. JLink DLL is locked\n\nPlease:\n- Close all other applications using JLink\n- Wait a few seconds and try again\n- Restart the application if problem persists")
                                    self._log_to_gui(detailed_msg)
                                    logger.error(f"Failed to reopen JLink after retry: {error_msg}", exc_info=True)
                                    raise Exception(f"Failed to reopen JLink: {error_msg}. Please check if another process is using JLink.")
                                else:
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Failed to reopen JLink: %s") % str(retry_e))
                                    logger.error(f"Failed to reopen JLink: {error_msg}", exc_info=True)
                                    raise Exception(f"Failed to reopen JLink: {error_msg}")
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
                        with self._jlink_lock:
                            already_connected_to_target = bool(self.jlink.connected())
                        if already_connected_to_target:
                            # JLink 已连接，检查是否连接到同一设备
                            # 注意：pylink 库没有直接的方法获取当前连接的设备名称
                            # 我们假设如果 JLink 已打开且已连接，就是连接到同一设备
                            logger.info(f'JLink is already connected to a target device')
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink is already connected to target device"))
                            already_connected_to_target = True
                    except Exception as e:
                        logger.debug(f'Failed to check JLink connected status: {e}')
                
                # 移除了在connect()前的额外连接检查，让后续的connect()方法正常执行
                # 这样可以避免在实际尝试连接之前就抛出异常

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
                        try:
                            self._call_jlink_with_timeout(
                                "jlink.connect(...)",
                                lambda: self.jlink.connect(self.device),
                                5.0,
                            )
                        except pylink.errors.JLinkException as e:
                            # 真实硬件偶发报“Emulator connection error”，做一次快速重试
                            if "emulator connection error" in str(e).lower():
                                logger.warning("Emulator connection error, retrying connect...")
                                self._log_to_gui(QCoreApplication.translate("rtt2uart", "JLink connection error, retrying..."))
                                import time
                                time.sleep(0.3)
                                self._call_jlink_with_timeout(
                                    "jlink.connect(retry)",
                                    lambda: self.jlink.connect(self.device),
                                    5.0,
                                )
                            else:
                                raise
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
                                    self._call_jlink_with_timeout(
                                        "jlink.rtt_start(address)",
                                        lambda: self.jlink.rtt_start(address),
                                        5.0,
                                    )
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
                                self._call_jlink_with_timeout(
                                    "jlink.rtt_start(block_address=...)",
                                    lambda: self.jlink.rtt_start(block_address=cb_addr),
                                    5.0,
                                )
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
                        # 如果设置了跳过RTT块识别，直接使用JLink自动检测
                        if self._skip_rtt_block_detection:
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Skipping RTT block detection, using JLink auto-detection..."))
                            self._call_jlink_with_timeout("jlink.rtt_start()", lambda: self.jlink.rtt_start(), 5.0)
                        else:
                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Searching for RTT Control Block in memory..."))
                            
                            cb_addr = None
                            try:
                                # 尝试从设备配置获取RAM信息
                                ram_start = None
                                ram_size = None
                                
                                # 尝试从worker获取主窗口引用，然后获取RAM信息
                                if hasattr(self.worker, 'parent') and hasattr(self.worker.parent, 'main_window'):
                                    try:
                                        # 获取当前session
                                        session = None
                                        if hasattr(self.worker.parent.main_window, '_get_active_device_session'):
                                            session = self.worker.parent.main_window._get_active_device_session()
                                        
                                        if session:
                                            ram_start, ram_size = self.worker.parent.main_window._get_device_ram_info(session)
                                    except Exception as e:
                                        logger.debug(f"Failed to get RAM info from device config: {e}")
                                
                                # 如果无法获取RAM信息，使用默认值
                                if ram_start is None or ram_size is None:
                                    # 默认RAM范围: 0x20000000 - 0x20040000 (256KB)
                                    ram_start = 0x20000000
                                    ram_size = 0x40000  # 256KB
                                    logger.warning(f"Using default RAM range: 0x{ram_start:08X} - 0x{ram_start + ram_size:08X}")
                                else:
                                    logger.info(f"Using device RAM range: 0x{ram_start:08X} - 0x{ram_start + ram_size:08X}")
                                
                                search_chunk = 0x1000  # 每次搜索 4KB
                                
                                # RTT 控制块的标识符 "SEGGER RTT"
                                rtt_id = b"SEGGER RTT"
                                
                                # 搜索第一个RTT块（用于立即启动）
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
                                            logger.info(f"Found first RTT Control Block at 0x{cb_addr:08X}")
                                            self._log_to_gui(QCoreApplication.translate("rtt2uart", "Found RTT Control Block at address: 0x%08X") % cb_addr)
                                            
                                            # 如果session存在，添加到RTT块列表
                                            if hasattr(self.worker, 'parent') and hasattr(self.worker.parent, 'main_window'):
                                                try:
                                                    session = self.worker.parent.main_window._get_active_device_session()
                                                    if session:
                                                        if cb_addr not in session.rtt_block_list:
                                                            session.rtt_block_list.append(cb_addr)
                                                        if session.current_rtt_block is None:
                                                            session.current_rtt_block = cb_addr
                                                except Exception as e:
                                                    logger.debug(f"Failed to update session RTT block list: {e}")
                                            
                                            break
                                    except Exception as e:
                                        # 某些内存区域可能不可读，跳过
                                        pass
                                
                                if not cb_addr:
                                    # 搜索失败，尝试使用JLink自动检测作为回退
                                    logger.warning(f"RTT Control Block not found in RAM: 0x{ram_start:08X} - 0x{ram_start + ram_size:08X}, trying JLink auto-detection...")
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT Control Block not found in memory (0x%08X - 0x%08X), trying JLink auto-detection...") % (ram_start, ram_start + ram_size))
                                    try:
                                        # 尝试使用JLink自动检测
                                        self._call_jlink_with_timeout("jlink.rtt_start()", lambda: self.jlink.rtt_start(), 5.0)
                                        logger.info("JLink auto-detection succeeded")
                                        self._log_to_gui(QCoreApplication.translate("rtt2uart", "RTT started using JLink auto-detection"))
                                    except Exception as auto_e:
                                        # 自动检测也失败，抛出错误
                                        error_msg = QCoreApplication.translate("rtt2uart", "RTT Control Block not found in memory (0x%08X - 0x%08X) and JLink auto-detection failed: %s") % (ram_start, ram_start + ram_size, str(auto_e))
                                        self._log_to_gui(error_msg)
                                        logger.error(f"RTT Control Block not found and auto-detection failed: {auto_e}")
                                        raise Exception(error_msg)
                                else:
                                    # 使用找到的地址启动 RTT
                                    self._log_to_gui(QCoreApplication.translate("rtt2uart", "Starting RTT with Control Block at 0x%08X") % cb_addr)
                                    self._call_jlink_with_timeout(
                                        "jlink.rtt_start(block_address=...)",
                                        lambda: self.jlink.rtt_start(block_address=cb_addr),
                                        5.0,
                                    )
                                    
                                    # 后台搜索将继续在ConnectionDialog中启动
                                    
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
                            with self._jlink_lock:
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
                                        with self._jlink_lock:
                                            buf_info = self.jlink.rtt_get_buf_descriptor(i, True)
                                        try:
                                            if isinstance(buf_info.name, (bytes, bytearray)):
                                                name = bytes(buf_info.name).decode('utf-8', errors='replace')
                                            else:
                                                name = str(buf_info.name)
                                        except Exception:
                                            name = "-"
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
                                        with self._jlink_lock:
                                            buf_info = self.jlink.rtt_get_buf_descriptor(i, False)
                                        try:
                                            if isinstance(buf_info.name, (bytes, bytearray)):
                                                name = bytes(buf_info.name).decode('utf-8', errors='replace')
                                            else:
                                                name = str(buf_info.name)
                                        except Exception:
                                            name = "-"
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

        # Open serial only when forwarding is enabled.
        # If no serial port exists (or configured port is invalid), do not fail app startup.
        if self.serial_forward_tab != -1:  # -1 means forwarding disabled
            if not self.port:
                logger.warning(QCoreApplication.translate("rtt2uart", "Serial forwarding enabled but no COM port selected; disabling forwarding"))
                self.serial_forward_tab = -1
            else:
                try:
                    if self.serial.isOpen() == False:
                        # Configure and open serial port
                        self.serial.port = self.port
                        self.serial.baudrate = self.baudrate
                        self.serial.timeout = 3
                        self.serial.write_timeout = 3
                        self.serial.open()
                        logger.info(f'串口转发已启用，串口 {self.port} 打开成功')
                except Exception as e:
                    # Disable forwarding if open fails (e.g. no serial devices on the system)
                    logger.warning(QCoreApplication.translate("rtt2uart", "Failed to open COM port %s: %s; disabling forwarding") % (str(self.port), str(e)), exc_info=True)
                    self.serial_forward_tab = -1
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
        # 读线程已就绪，恢复读取
        self._suspend_rtt_reads = False
        
        
    def stop(self, keep_folder=False, fast=False):
        """停止RTT服务
        
        Args:
            keep_folder: 如果为True，保留日志文件夹（用于自动重连）；如果为False，清理空文件夹
            fast: If True, force-stop threads quickly and skip blocking J-Link/serial close.
        """
        if fast:
            logger.warning(QCoreApplication.translate("rtt2uart", "stop rtt2uart (fast) - Force stopping RTT threads for app exit"))
        else:
            logger.debug(QCoreApplication.translate("rtt2uart", "stop rtt2uart - Starting to stop RTT service"))

        # 清空暂停缓冲区（如果有），避免关闭时卡住
        self.clear_paused_data()
        
        # 设置停止标志
        self.thread_switch = False
        logger.debug(QCoreApplication.translate("rtt2uart", "Thread stop flag set"))

        # Fast stop is for application exit: do not wait/join, do not touch J-Link/serial here
        # (may block for seconds). Process exit will end daemon threads.
        if fast:
            return

        # 强制停止线程，增加更严格的超时处理
        self._force_stop_threads(fast=False)
        
        # 改进的 JLink 关闭逻辑
        if self._connect_inf != 'EXISTING':
            self._safe_close_jlink()

        # 关闭串口
        self._safe_close_serial()
        
        # 检查并删除空的日志文件夹（除非需要保留）
        if not keep_folder:
            self._cleanup_empty_log_folder()
        
        logger.debug(QCoreApplication.translate("rtt2uart", "RTT service stop completed"))
    
    def _force_stop_threads(self, fast: bool = False):
        """强制停止所有RTT线程"""
        import time
        
        threads_to_stop = [
            ('RTT读取线程', self.rtt_thread),
            ('RTT2UART线程', self.rtt2uart)
        ]

        # Fast path: keep joins extremely short to avoid blocking UI during app exit.
        join1 = 0.05 if fast else 0.5
        join2 = 0.05 if fast else 0.3
        final_sleep = 0.0 if fast else 0.2
        
        for thread_name, thread in threads_to_stop:
            if thread and thread.is_alive():
                logger.info(f"正在停止{thread_name}...")
                
                # 第一次尝试：优雅停止,减少超时时间避免长时间卡住
                try:
                    thread.join(timeout=join1)
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
                    thread.join(timeout=join2)
                    
                    if thread.is_alive():
                        logger.warning(f"{thread_name}仍在运行，将在主程序退出时被强制终止")
                    else:
                        logger.info(f"{thread_name}已强制停止")
                        
                except Exception as e:
                    logger.error(f"强制停止{thread_name}时出错: {e}")
        
        # 给线程一些时间完成清理
        try:
            if final_sleep > 0:
                time.sleep(final_sleep)
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
                        self._call_jlink_with_timeout("jlink.close()", lambda: self.jlink.close(), 5.0)
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
            enc = self.worker.config.get_text_encoding() if hasattr(self.worker, 'config') else 'gbk'
        except Exception:
            enc = 'gbk'
        with open(self.rtt_log_filename, 'ab') as log_file:
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

                    # 启动/重连期间暂停读取，避免DLL未打开的噪音
                    if getattr(self, '_suspend_rtt_reads', False):
                        time.sleep(0.1)
                        continue

                    # JLink 未打开时跳过读取
                    try:
                        with self._jlink_lock:
                            opened = self.jlink.opened()
                        if not opened:
                            time.sleep(0.1)
                            continue
                    except Exception:
                        time.sleep(0.1)
                        continue

                    # 启动/重连期间暂停读取，避免DLL未打开的噪音
                    if getattr(self, '_suspend_rtt_reads', False):
                        time.sleep(0.1)
                        continue

                    # JLink 未打开时跳过读取
                    try:
                        with self._jlink_lock:
                            opened = self.jlink.opened()
                        if not opened:
                            time.sleep(0.1)
                            continue
                    except Exception:
                        time.sleep(0.1)
                        continue
                    
                    # 减少连接状态检查频率，避免过多警告
                    connection_check_counter += 1
                    if connection_check_counter >= connection_check_interval:
                        connection_check_counter = 0
                        try:
                            with self._jlink_lock:
                                is_conn = self.jlink.connected()
                            if not is_conn:
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
                            with self._jlink_lock:
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
                            if "dll is not open" in str(e).lower():
                                time.sleep(0.1)
                                break
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

                    if len(rtt_recv_log) > 0:
                        self.last_jlink_data_time = time.time()
                    self.read_bytes0 += len(rtt_recv_log)
                    rtt_log_len = len(rtt_recv_log)
                    
                    # 首次数据到达时间戳记录
                    if not self._first_data_received and rtt_log_len > 0:
                        self._first_data_received = True
                        from datetime import datetime
                        first_data_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                        logger.info(f"⏱️ 首次数据到达时间: {first_data_time} (接收 {rtt_log_len} 字节)")

                    # 处理原始RTT数据以解析通道信息（使用新的process_byte函数）
                    if rtt_log_len > 0:
                        has_data = True
                        # 确保内部状态已初始化
                        if not hasattr(self, '_processing_channel'):
                            self._processing_channel = '0'  # 默认通道0
                        # 直接使用process_byte函数处理整个数据块
                        # process_byte函数内部会逐字节处理并正确识别通道分隔符
                        log_file.write(rtt_recv_log)
                        log_file.flush()
                        # 使用主窗口的worker实例处理数据
                        if hasattr(self.worker, 'process_bytes'):
                            self.worker.process_bytes(rtt_recv_log)
                    
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
                        with self._jlink_lock:
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
                            with self._jlink_lock:
                                is_conn = self.jlink.connected()
                            if not is_conn:
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
                        with self._jlink_lock:
                            rtt_recv_data = self.jlink.rtt_read(1, _RTT_READ_BUFFER_SIZE)
                        if len(rtt_recv_data) > 0:
                            self.last_jlink_data_time = time.time()
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
                        if "dll is not open" in str(e).lower():
                            time.sleep(0.1)
                            continue
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



