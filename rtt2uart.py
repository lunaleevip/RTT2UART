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
            if self._connect_inf != 'EXISTING' and self.jlink.connected() == False:
                # 加载jlinkARM.dll
                if self._connect_inf == 'USB':
                    self.jlink.open(serial_no=self._connect_para)
                else:
                    self.jlink.open(ip_addr=self._connect_para)

                # 设置连接速率
                if self.jlink.set_speed(self._speed) == False:
                    logger.error('Set speed failed', exc_info=True)
                    raise Exception("Set jlink speed failed")

                # 设置连接接口为SWD
                if self.jlink.set_tif(self._interface) == False:
                    logger.error('Set interface failed', exc_info=True)
                    raise Exception("Set jlink interface failed")

                try:
                    if self._reset == True:
                        # 复位一下目标芯片，复位后不要停止芯片，保证后续操作的稳定性
                        self.jlink.reset(halt=False)

                    # 连接目标芯片
                    self.jlink.connect(self.device)
                    # 启动RTT，对于RTT的任何操作都需要在RTT启动后进行
                    self.jlink.rtt_start()

                except pylink.errors.JLinkException:
                    logger.error('Connect target failed', exc_info=True)
                    raise
        except pylink.errors.JLinkException as errors:
            logger.error('Open jlink failed', exc_info=True)
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

        self.thread_switch = False
        if self.rtt_thread:
            self.rtt_thread.join(0.5)

        if self.rtt2uart:
            self.rtt2uart.join(0.5)
            
        if self._connect_inf == 'USB':
            try:
                if self.jlink.connected() == True:
                    # 使用完后停止RTT
                    self.jlink.rtt_stop()
                    # 释放之前加载的jlinkARM.dll
                    self.jlink.close()
            except pylink.errors.JLinkException:
                logger.error('Disconnect target failed', exc_info=True)
                pass

        try:
            if self.serial.isOpen() == True:
                self.serial.close()
        except:
            logger.error('Close serial failed', exc_info=True)
            pass
        # 打包文件为ZIP压缩包
        #zip_folder(os.path.join(self.log_directory), os.path.join(str(self.log_directory) + '.zip'))
        # 删除文件夹
        #shutil.rmtree(self.log_directory)


    def rtt_thread_exec(self):
        # 打开日志文件，如果不存在将自动创建
        with open(self.rtt_log_filename, 'ab') as log_file:
            while self.thread_switch:
                try:
                    rtt_recv_log = []
                    while True:
                        recv_log = self.jlink.rtt_read(0, 1024)
                        if not recv_log:
                            break
                        else:
                            rtt_recv_log += recv_log

                    self.read_bytes0 += len(rtt_recv_log)
                    rtt_log_len = len(rtt_recv_log)
                
                    if rtt_log_len:
                        # 将接收到的数据写入日志文件
                        log_bytes = bytearray(rtt_recv_log);
                        log_file.write(log_bytes)

                        skip_next_byte = False
                        temp_buff = bytearray()
                    
                        for i in range(rtt_log_len):
                            if skip_next_byte:
                                self.tem = chr(log_bytes[i])
                                skip_next_byte = False
                                continue
                        
                            if log_bytes[i] == 255:
                                skip_next_byte = True
                                self.insert_char(self.tem, temp_buff)
                                temp_buff.clear()
                                continue
                        
                            temp_buff.append(log_bytes[i])
                        
                        if len(temp_buff):
                            self.insert_char(self.tem, temp_buff)
                    
                except Exception as e:
                    print("Error:", e)
                    pass

    def rtt2uart_exec(self):
        # 打开日志文件，如果不存在将自动创建
        with open(self.rtt_data_filename, 'ab') as data_file:
            while self.thread_switch:
                try:
                    rtt_recv_data = self.jlink.rtt_read(1, 1024)
                    self.read_bytes1 += len(rtt_recv_data)

                    if len(rtt_recv_data):
                        # 将接收到的数据写入数据文件
                        data_file.write(bytes(rtt_recv_data))
                        
                        if self.serial.isOpen():
                            try:
                                self.serial.write(bytes(rtt_recv_data))
                            except Exception as e:
                                print("Error:", e)
                                self.serial.close()
                except Exception as e:
                    print("Error:", e)


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


if __name__ == "__main__":
    serial_name = input("请输入虚拟串口对中的串口名字，如COM26：")

    if '' == serial_name:
        serial_name = 'COM26'

    test = rtt_to_serial(0, 'AMAPH1KK-KBR', serial_name, 115200)
    test.start()
