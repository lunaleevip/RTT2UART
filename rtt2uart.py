import logging
import pylink
import time
import serial
import threading
import socket
import os
import datetime
import zipfile
from pathlib import Path
import shutil

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

logging.basicConfig(level=logging.WARNING,
                    format='%(asctime)s - [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s')
logger = logging.getLogger(__name__)

def zip_folder(folder_path, zip_file_path):
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, folder_path))


class rtt_to_serial():
    def __init__(self, main, jlink, connect_inf='USB', connect_para=None, device=None, port=None, baudrate=115200, interface=pylink.enums.JLinkInterfaces.SWD, speed=12000, reset=False):
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
            logger.error('Creat serial object failed', exc_info=True)
            raise

        self.rtt_thread = None
        self.rtt2uart = None
        
        self.tem = '0'
        
        # 设置日志文件名
        log_directory=None
        
        if log_directory is None:
            # 获取桌面路径
            desktop_path = Path.home() / "Desktop/XexunRTT_Log"
            # 设置日志文件名
            log_directory = desktop_path / (str(device) + datetime.datetime.now().strftime("_%Y%m%d%H%M%S"))
            # 确保日志文件夹存在，如果不存在则创建
            log_directory.mkdir(parents=True, exist_ok=True)
            
        self.log_directory = log_directory
        self.rtt_log_filename = os.path.join(log_directory, "rtt_log.log")
        self.rtt_data_filename = os.path.join(log_directory, "rtt_data.log")


    def __del__(self):
        logger.debug('close app')
        self.stop()

    def start(self):
        logger.debug('start rtt2uart')
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
                        if self._connect_inf == 'USB':
                            self.jlink.open(serial_no=self._connect_para)
                        else:
                            self.jlink.open(ip_addr=self._connect_para)
                        
                        # 短暂等待连接稳定
                        import time
                        time.sleep(0.1)
                        
                    except pylink.errors.JLinkException as e:
                        logger.error(f'Failed to open JLink: {e}', exc_info=True)
                        raise Exception(f"Failed to open JLink: {e}")

                # 再次检查连接状态
                try:
                    if not self.jlink.connected():
                        raise Exception("JLink connection failed after open")
                except pylink.errors.JLinkException:
                    raise Exception("JLink connection verification failed")

                # 设置连接速率
                try:
                    if self.jlink.set_speed(self._speed) == False:
                        logger.error('Set speed failed', exc_info=True)
                        raise Exception("Set jlink speed failed")
                except pylink.errors.JLinkException as e:
                    logger.error(f'Set speed failed with exception: {e}', exc_info=True)
                    raise Exception(f"Set jlink speed failed: {e}")

                # 设置连接接口为SWD
                try:
                    if self.jlink.set_tif(self._interface) == False:
                        logger.error('Set interface failed', exc_info=True)
                        raise Exception("Set jlink interface failed")
                except pylink.errors.JLinkException as e:
                    logger.error(f'Set interface failed with exception: {e}', exc_info=True)
                    raise Exception(f"Set jlink interface failed: {e}")

                try:
                    if self._reset == True:
                        # 复位一下目标芯片，复位后不要停止芯片，保证后续操作的稳定性
                        self.jlink.reset(halt=False)

                    # 连接目标芯片
                    self.jlink.connect(self.device)
                    # 启动RTT，对于RTT的任何操作都需要在RTT启动后进行
                    self.jlink.rtt_start()

                except pylink.errors.JLinkException as e:
                    logger.error(f'Connect target failed: {e}', exc_info=True)
                    raise Exception(f"Connect target failed: {e}")
        except pylink.errors.JLinkException as errors:
            logger.error(f'Open jlink failed: {errors}', exc_info=True)
            raise Exception(f"Open jlink failed: {errors}")
        except Exception as e:
            logger.error(f'Start RTT failed: {e}', exc_info=True)
            raise

        try:
            if self.serial.isOpen() == False:
                # 设置串口参数并打开串口
                self.serial.port = self.port
                self.serial.baudrate = self.baudrate
                self.serial.timeout = 3
                self.serial.write_timeout = 3
                self.serial.open()
        except:
            logger.error('Open serial failed', exc_info=True)
            raise
        
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
        logger.debug('stop rtt2uart')

        # 停止线程
        self.thread_switch = False
        
        # 等待线程结束，增加超时处理
        if self.rtt_thread and self.rtt_thread.is_alive():
            self.rtt_thread.join(1.0)  # 增加超时时间
            if self.rtt_thread.is_alive():
                logger.warning('RTT thread did not stop gracefully')

        if self.rtt2uart and self.rtt2uart.is_alive():
            self.rtt2uart.join(1.0)  # 增加超时时间
            if self.rtt2uart.is_alive():
                logger.warning('RTT2UART thread did not stop gracefully')
        
        # 改进的 JLink 关闭逻辑
        if self._connect_inf != 'EXISTING':
            self._safe_close_jlink()

        # 关闭串口
        self._safe_close_serial()
        
        # 打包文件为ZIP压缩包
        #zip_folder(os.path.join(self.log_directory), os.path.join(str(self.log_directory) + '.zip'))
        # 删除文件夹
        #shutil.rmtree(self.log_directory)

    def _safe_close_jlink(self):
        """安全关闭 JLink 连接"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # 检查连接状态
                is_connected = False
                try:
                    is_connected = self.jlink.connected()
                except pylink.errors.JLinkException:
                    logger.warning(f'Cannot check JLink connection status on retry {retry_count + 1}')
                    is_connected = False
                
                if is_connected:
                    try:
                        # 停止RTT
                        self.jlink.rtt_stop()
                        logger.debug('RTT stopped successfully')
                    except pylink.errors.JLinkException as e:
                        logger.warning(f'Failed to stop RTT: {e}')
                    
                    try:
                        # 关闭JLink连接
                        self.jlink.close()
                        logger.debug('JLink closed successfully')
                        break  # 成功关闭，退出循环
                    except pylink.errors.JLinkException as e:
                        logger.warning(f'Failed to close JLink on attempt {retry_count + 1}: {e}')
                        retry_count += 1
                        if retry_count < max_retries:
                            import time
                            time.sleep(0.2)  # 短暂等待后重试
                        continue
                else:
                    logger.debug('JLink already disconnected')
                    break
                    
            except Exception as e:
                logger.error(f'Unexpected error during JLink close on attempt {retry_count + 1}: {e}')
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(0.2)
                continue
        
        if retry_count >= max_retries:
            logger.error('Failed to close JLink after maximum retries')

    def _safe_close_serial(self):
        """安全关闭串口连接"""
        try:
            if hasattr(self, 'serial') and self.serial and self.serial.isOpen():
                self.serial.close()
                logger.debug('Serial port closed successfully')
        except Exception as e:
            logger.error(f'Close serial failed: {e}', exc_info=True)


    def rtt_thread_exec(self):
        # 打开日志文件，如果不存在将自动创建
        with open(self.rtt_log_filename, 'ab') as log_file:
            # 性能优化：添加短暂延迟避免过度占用CPU
            import time
            
            while self.thread_switch:
                try:
                    # 检查JLink连接状态
                    try:
                        if not self.jlink.connected():
                            logger.warning('JLink connection lost in RTT thread')
                            time.sleep(0.1)
                            continue
                    except pylink.errors.JLinkException:
                        logger.warning('Cannot check JLink status in RTT thread')
                        time.sleep(0.1)
                        continue
                    
                    rtt_recv_log = []
                    # 优化：一次性读取更多数据，减少系统调用
                    max_read_attempts = 5
                    for _ in range(max_read_attempts):
                        try:
                            recv_log = self.jlink.rtt_read(0, 4096)  # 增加缓冲区大小
                            if not recv_log:
                                break
                            else:
                                rtt_recv_log += recv_log
                        except pylink.errors.JLinkException as e:
                            logger.warning(f'RTT read failed: {e}')
                            break

                    self.read_bytes0 += len(rtt_recv_log)
                    rtt_log_len = len(rtt_recv_log)
                
                    if rtt_log_len:
                        # 将接收到的数据写入日志文件
                        log_bytes = bytearray(rtt_recv_log)
                        log_file.write(log_bytes)
                        log_file.flush()  # 确保及时写入

                        skip_next_byte = False
                        temp_buff = bytearray()
                    
                        for i in range(rtt_log_len):
                            if skip_next_byte:
                                self.tem = chr(log_bytes[i])
                                skip_next_byte = False
                                continue
                        
                            if log_bytes[i] == 255:
                                skip_next_byte = True
                                if temp_buff:  # 只有非空时才处理
                                    self.insert_char(self.tem, temp_buff)
                                    temp_buff.clear()
                                continue
                        
                            temp_buff.append(log_bytes[i])
                        
                        if temp_buff:  # 只有非空时才处理
                            self.insert_char(self.tem, temp_buff)
                    else:
                        # 没有数据时短暂休眠，避免过度占用CPU
                        time.sleep(0.001)  # 1ms
                    
                except pylink.errors.JLinkException as e:
                    logger.error(f"JLink error in RTT thread: {e}")
                    time.sleep(0.1)  # JLink错误时较长休眠
                except Exception as e:
                    logger.error(f"Unexpected error in RTT thread: {e}")
                    time.sleep(0.01)  # 发生错误时稍长休眠

    def rtt2uart_exec(self):
        # 打开日志文件，如果不存在将自动创建
        with open(self.rtt_data_filename, 'ab') as data_file:
            import time
            
            while self.thread_switch:
                try:
                    # 检查JLink连接状态
                    try:
                        if not self.jlink.connected():
                            logger.warning('JLink connection lost in RTT2UART thread')
                            time.sleep(0.1)
                            continue
                    except pylink.errors.JLinkException:
                        logger.warning('Cannot check JLink status in RTT2UART thread')
                        time.sleep(0.1)
                        continue
                    
                    try:
                        rtt_recv_data = self.jlink.rtt_read(1, 1024)
                        self.read_bytes1 += len(rtt_recv_data)

                        if len(rtt_recv_data):
                            # 将接收到的数据写入数据文件
                            data_file.write(bytes(rtt_recv_data))
                            data_file.flush()  # 确保及时写入
                            
                            if self.serial.isOpen():
                                try:
                                    self.serial.write(bytes(rtt_recv_data))
                                except Exception as e:
                                    logger.error(f"Serial write error: {e}")
                                    try:
                                        self.serial.close()
                                    except:
                                        pass
                        else:
                            # 没有数据时短暂休眠
                            time.sleep(0.001)
                            
                    except pylink.errors.JLinkException as e:
                        logger.warning(f'RTT2UART read failed: {e}')
                        time.sleep(0.1)
                        
                except pylink.errors.JLinkException as e:
                    logger.error(f"JLink error in RTT2UART thread: {e}")
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Unexpected error in RTT2UART thread: {e}")
                    time.sleep(0.01)


    def insert_char(self, tem, string, new_line=False):
        if '0' <= tem <= '9':
            tem_num = int(tem)
        elif 'A' <= tem <= 'F':
            tem_num = ord(tem) - ord('A') + 10
        else:
            # 处理非法输入的情况
            tem_num = 0
            
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
