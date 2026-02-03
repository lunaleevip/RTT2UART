#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
使用INI格式保存和加载应用程序设置
"""

import os
import configparser
import json
import logging
from typing import Any, List, Dict, Optional
from PySide6.QtCore import QCoreApplication

logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器，使用INI格式保存设置"""
    
    def __init__(self, config_dir: str = None):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录，默认为用户目录下的应用配置文件夹
        """
        if config_dir is None:
            # 使用用户目录下的应用配置文件夹
            import sys
            if sys.platform == "darwin":  # macOS
                config_dir = os.path.expanduser("~/Library/Application Support/XexunRTT")
            elif sys.platform == "win32":  # Windows
                config_dir = os.path.expanduser("~/AppData/Roaming/XexunRTT")
            else:  # Linux
                config_dir = os.path.expanduser("~/.config/XexunRTT")
        
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, "config.ini")
        self.cmd_file = os.path.join(config_dir, "cmd.txt")
        
        # 创建配置解析器
        self.config = configparser.ConfigParser()
        self.config.optionxform = str  # 保持键名大小写
        
        # 🔑 用于脏数据检测的快照
        self._last_saved_snapshot = None
        
        # 设置默认值
        self._set_defaults()
        
        # 加载现有配置
        self.load_config()
        
        # 尝试从APP内部迁移配置文件（如果存在）
        self._migrate_from_app_bundle()
    
    def _set_defaults(self):
        """设置默认配置值"""
        # JLink连接设置
        self.config['Connection'] = {
            'device_list': '[]',  # JSON格式的设备列表
            'device_index': '0',
            'interface': '0',  # 0:JTAG, 1:SWD, 2:cJTAG, 3:FINE
            'speed': '0',      # 速度索引
            'connection_type': 'USB',  # USB, TCP/IP, Existing
            'serial_number': '',
            'ip_address': '',
            'auto_reconnect': 'true',
            'auto_reconnect_on_no_data': 'false',  # 无数据自动重连开关
            'auto_reconnect_timeout': '60',  # 无数据自动重连超时时间（秒）
            'preferred_jlink_serials': '[]',  # JSON格式的偏好JLINK序列号列表
            'last_jlink_serial': '',         # 上次使用的JLINK序列号
            'auto_select_jlink': 'false'     # 是否自动选择上次使用的JLINK
        }
        
        # 串口设置
        self.config['Serial'] = {
            'port_index': '0',
            'baudrate': '16',  # 波特率索引
            'port_name': '',   # 实际选中的端口名
            'reset_target': 'false'
        }
        
        # 串口转发设置
        self.config['SerialForward'] = {
            'enabled': 'false',
            'mode': 'LOG',     # LOG 或 DATA
            'target_tab': '-1' # 转发目标TAB索引
        }

        # Watch/Memory/FrameBuffer panel settings
        # NOTE: recent expressions are stored as JSON list
        self.config['WatchPanel'] = {
            'elf_path': '',
            'recent_exprs': '[]',
            'mem_addr': '0x20000000',
            'mem_size': '256',
            'fb_addr': '',
            'fb_w': '0',
            'fb_h': '0',
            'fb_fmt': 'MonoLSB',
            'fb_auto': 'false',
        }

        # Auto test rules (max 3): JSON list of rule objects
        # rule fields:
        # - enabled: bool
        # - trigger_type: "text" | "interval"
        # - trigger_text: str
        # - interval_sec: int
        # - action_type: "send" | "restart"
        # - action_text: str
        self.config['AutoTest'] = {
            'rules': '[]'
        }
        
        # Restart 设置
        self.config['Restart'] = {
            'method': 'SFR',  # SFR 或 RESET_PIN
            'format_ram': 'false'  # 重启前是否格式化RAM
        }
        
        # UI界面设置
        self.config['UI'] = {
            'light_mode': 'false',
            'fontsize': '9',
            'lock_horizontal': 'true',
            'lock_vertical': 'false',
            'window_geometry': '',  # 主窗口几何信息
            'dialog_geometry': '',  # 连接对话框几何信息
            'dpi_scale': 'auto',    # DPI缩放设置: auto或具体数值(0.1-5.0)
            'regex_filter': 'false', # 正则表达式筛选开关，默认关闭
            'language': 'zh_CN'     # 界面语言: en_US, zh_CN, zh_TW
        }
        
        # 文本编码设置（读取/写入日志与显示）
        self.config['Encoding'] = {
            'text_encoding': 'gbk'  # 默认GBK
        }
        
        # 过滤器设置 (支持多个过滤器) - 只设置section，不初始化具体值
        # 🔑 修复：不要清空 Filters section，让 load_config() 加载已保存的值
        if 'Filters' not in self.config:
            self.config['Filters'] = {}
        
        # 日志设置
        self.config['Logging'] = {
            'auto_save': 'true',
            'log_format': 'txt',
            'max_lines': '10000',  # UI最大行数
            'auto_delete_empty': 'true',
            'log_split': 'true',  # 日志拆分，默认开启
            'last_log_directory': ''  # 上次使用的日志目录
        }
        
        # 性能清理设置
        self.config['Performance'] = {
            'clean_trigger_ms': '50',      # 触发清理的UI耗时阈值（毫秒）
            'warning_trigger_ms': '100',   # 触发警告的UI耗时阈值（毫秒）
            'clean_ratio_denominator': '10'  # 清理比例分母（1/N）
        }
        
        # 自动重置设置（JSON 列表字符串）
        self.config['Autoreset'] = {
            'reset_msg': json.dumps(["JLink connection failed after open"], ensure_ascii=False)
        }
        
        # 初始化通道颜色配置
        if 'ChannelColors' not in self.config:
            self.config['ChannelColors'] = {}
        # 设置默认的16个通道颜色（循环使用基本颜色）
        default_fg_colors = [
            'FFFFFF', 'FF0000', '00FF00', 'FFFF00',  # 白、红、绿、黄
            '0000FF', 'FF00FF', '00FFFF', 'FF8000',  # 蓝、洋红、青、橙
            '000000', '000000', '000000', '000000',  # 黑底系列
            '000000', '000000', '000000', '000000'   # 黑底系列
        ]
        default_bg_colors = [
            '000000', '000000', '000000', '000000',  # 黑底系列
            '000000', '000000', '000000', '000000',  # 黑底系列
            'FFFFFF', 'FF0000', '00FF00', 'FFFF00',  # 白、红、绿、黄
            '0000FF', 'FF00FF', '00FFFF', 'FF8000'   # 蓝、洋红、青、橙
        ]
        
        # 检查是否需要初始化前景色数组
        if 'fgcolors' not in self.config['ChannelColors']:
            # 将颜色数组转换为逗号分隔的字符串
            self.config['ChannelColors']['fgcolors'] = ','.join(default_fg_colors)
        
        # 检查是否需要初始化背景色数组
        if 'bgcolors' not in self.config['ChannelColors']:
            self.config['ChannelColors']['bgcolors'] = ','.join(default_bg_colors)
    
    def load_config(self):
        """从INI文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                logger.debug(f"配置文件加载成功: {self.config_file}")
                # 兼容旧配置：max_log_size -> max_lines
                try:
                    if self.config.has_section('Logging'):
                        if (not self.config.has_option('Logging', 'max_lines') 
                            and self.config.has_option('Logging', 'max_log_size')):
                            old_value = self.config.get('Logging', 'max_log_size', fallback='10000')
                            self.config.set('Logging', 'max_lines', str(old_value))
                            logger.info(f"迁移配置: Logging.max_log_size -> max_lines = {old_value}")
                except Exception as e:
                    logger.debug(f"配置迁移失败: {e}")
            except Exception as e:
                logger.debug(f"配置文件加载失败: {e}")
                # 使用默认设置
                pass
        else:
            logger.debug(f"配置文件不存在，使用默认设置: {self.config_file}")
        
        # 🔑 加载后创建快照，用于脏数据检测
        self._last_saved_snapshot = self._create_config_snapshot()
    
    def _safe_getint(self, section: str, option: str, fallback: int) -> int:
        """安全地获取整数配置值，如果转换失败则返回默认值并修复配置"""
        try:
            return self.config.getint(section, option, fallback=fallback)
        except ValueError as e:
            logger.debug(f"配置项 [{section}] {option} 值无效: {e}，使用默认值 {fallback}")
            self.config.set(section, option, str(fallback))
            return fallback
    
    def _safe_getboolean(self, section: str, option: str, fallback: bool) -> bool:
        """安全地获取布尔配置值，如果转换失败则返回默认值并修复配置"""
        try:
            return self.config.getboolean(section, option, fallback=fallback)
        except ValueError as e:
            logger.debug(f"配置项 [{section}] {option} 值无效: {e}，使用默认值 {fallback}")
            self.config.set(section, option, str(fallback).lower())
            return fallback
    
    def _safe_get(self, section: str, option: str, fallback: str) -> str:
        """安全地获取字符串配置值，如果获取失败则返回默认值并修复配置"""
        try:
            return self.config.get(section, option, fallback=fallback)
        except Exception as e:
            logger.debug(f"配置项 [{section}] {option} 值无效: {e}，使用默认值 {fallback}")
            self.config.set(section, option, str(fallback))
            return fallback
    
    def _create_config_snapshot(self) -> str:
        """创建当前配置的快照（用于脏数据检测）"""
        import io
        snapshot = io.StringIO()
        self.config.write(snapshot)
        return snapshot.getvalue()
    
    def save_config(self, force: bool = False):
        """
        保存配置到INI文件
        
        Args:
            force: 是否强制保存，忽略脏数据检测
        
        Returns:
            True if saved, False if no changes or error
        """
        try:
            # 🔧 调试日志已禁用 - 筛选器问题已解决
            # 如需重新启用，将 DEBUG_CONFIG_SAVE 设置为 True
            DEBUG_CONFIG_SAVE = False
            
            if DEBUG_CONFIG_SAVE:
                import traceback
                import logging
                debug_logger = logging.getLogger(__name__)
                
                call_stack = traceback.extract_stack()
                caller_info = []
                # 获取最近的5个调用层级（排除当前函数）
                for frame in call_stack[-6:-1]:
                    caller_info.append(f"{frame.filename}:{frame.lineno} in {frame.name}")
                
                debug_logger.info("=" * 40)
                debug_logger.info("[CONFIG SAVE] save_config() 被调用")
                debug_logger.info(f"[CONFIG SAVE] 调用栈:")
                for i, caller in enumerate(caller_info, 1):
                    debug_logger.info(f"[CONFIG SAVE]   {i}. {caller}")
                
                # 打印当前所有筛选值
                debug_logger.info(f"[CONFIG SAVE] 当前配置中的筛选值:")
                for i in range(17, 33):
                    filter_key = f'filter_{i}'
                    if self.config.has_option('Filters', filter_key):
                        filter_value = self.config.get('Filters', filter_key)
                        if filter_value:
                            debug_logger.info(f"[CONFIG SAVE]   filter_{i} = '{filter_value}'")
            
            # 🔑 脏数据检测：只有在配置真正改变时才写入文件
            if not force:
                current_snapshot = self._create_config_snapshot()
                if self._last_saved_snapshot is not None and current_snapshot == self._last_saved_snapshot:
                    # 配置未改变，跳过保存
                    if DEBUG_CONFIG_SAVE:
                        import logging
                        debug_logger = logging.getLogger(__name__)
                        debug_logger.info("[CONFIG SAVE] 配置未改变，跳过保存")
                        debug_logger.info("=" * 40)
                    return False
            
            # 配置已改变或强制保存，写入文件
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            
            # 更新快照
            self._last_saved_snapshot = self._create_config_snapshot()
            
            if DEBUG_CONFIG_SAVE:
                import logging
                debug_logger = logging.getLogger(__name__)
                debug_logger.info(f"[CONFIG SAVE] 配置保存成功: {self.config_file}")
                debug_logger.info("=" * 40)
            
            return True
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
            return False

    # ===========================================
    # 编码设置相关方法
    # ===========================================
    def get_text_encoding(self) -> str:
        """获取当前文本编码（用于解码RTT、写日志、发送指令）"""
        enc = self.config.get('Encoding', 'text_encoding', fallback='gbk')
        return (enc or 'gbk').lower()

    def set_text_encoding(self, encoding_name: str):
        """设置文本编码并保存到配置（不立即保存文件，由调用方决定）"""
        if not encoding_name:
            encoding_name = 'gbk'
        self.config.set('Encoding', 'text_encoding', encoding_name.lower())
    
    # ===========================================
    # 重启设置相关方法
    # ===========================================
    def get_restart_method(self) -> str:
        try:
            m = self.config.get('Restart', 'method', fallback='SFR').upper()
            return 'RESET_PIN' if m == 'RESET_PIN' else 'SFR'
        except Exception:
            return 'SFR'

    def set_restart_method(self, method: str):
        try:
            m = (method or 'SFR').upper()
            if m not in ('SFR', 'RESET_PIN'):
                m = 'SFR'
            self.config.set('Restart', 'method', m)
        except Exception:
            pass
    
    def get_format_ram_on_restart(self) -> bool:
        """获取重启前是否格式化RAM设置"""
        return self._safe_getboolean('Restart', 'format_ram', False)
    
    def set_format_ram_on_restart(self, enabled: bool):
        """设置重启前是否格式化RAM"""
        self.config.set('Restart', 'format_ram', str(enabled).lower())
    
    # ===========================================
    # 连接设置相关方法
    # ===========================================
    
    def get_device_list(self) -> List[str]:
        """获取设备列表"""
        try:
            device_list_str = self.config.get('Connection', 'device_list', fallback='[]')
            return json.loads(device_list_str)
        except:
            return []
    
    def set_device_list(self, devices: List[str]):
        """设置设备列表"""
        self.config.set('Connection', 'device_list', json.dumps(devices, ensure_ascii=False))
    
    def get_device_index(self) -> int:
        """获取当前选中的设备索引"""
        return self._safe_getint('Connection', 'device_index', 0)
    
    def set_device_index(self, index: int):
        """设置当前选中的设备索引"""
        self.config.set('Connection', 'device_index', str(index))
    
    def get_interface(self) -> int:
        """获取接口类型索引"""
        return self._safe_getint('Connection', 'interface', 0)
    
    def set_interface(self, interface: int):
        """设置接口类型索引"""
        self.config.set('Connection', 'interface', str(interface))
    
    def get_speed(self) -> int:
        """获取速度值（kHz）"""
        return self._safe_getint('Connection', 'speed', 4000)
    
    def set_speed(self, speed: int):
        """设置速度值（kHz）"""
        self.config.set('Connection', 'speed', str(speed))
    
    def get_connection_type(self) -> str:
        """获取连接类型"""
        return self.config.get('Connection', 'connection_type', fallback='USB')
    
    def set_connection_type(self, conn_type: str):
        """设置连接类型"""
        self.config.set('Connection', 'connection_type', conn_type)
    
    def get_serial_number(self) -> str:
        """获取序列号"""
        return self.config.get('Connection', 'serial_number', fallback='')
    
    def set_serial_number(self, serial_no: str):
        """设置序列号"""
        self.config.set('Connection', 'serial_number', serial_no)
    
    def get_ip_address(self) -> str:
        """获取IP地址"""
        return self.config.get('Connection', 'ip_address', fallback='')
    
    def set_ip_address(self, ip: str):
        """设置IP地址"""
        self.config.set('Connection', 'ip_address', ip)
    
    def get_preferred_jlink_serials(self) -> List[str]:
        """获取偏好的JLINK序列号列表"""
        try:
            serials_json = self.config.get('Connection', 'preferred_jlink_serials', fallback='[]')
            return json.loads(serials_json)
        except (json.JSONDecodeError, ValueError):
            return []
    
    def set_preferred_jlink_serials(self, serials: List[str]):
        """设置偏好的JLINK序列号列表"""
        self.config.set('Connection', 'preferred_jlink_serials', json.dumps(serials))
    
    def add_preferred_jlink_serial(self, serial: str):
        """添加偏好的JLINK序列号"""
        serials = self.get_preferred_jlink_serials()
        if serial and serial not in serials:
            serials.insert(0, serial)  # 新的序列号放在最前面
            # 限制最多保存10个序列号
            if len(serials) > 10:
                serials = serials[:10]
            self.set_preferred_jlink_serials(serials)
    
    def get_last_jlink_serial(self) -> str:
        """获取上次使用的JLINK序列号"""
        return self.config.get('Connection', 'last_jlink_serial', fallback='')
    
    def set_last_jlink_serial(self, serial: str):
        """设置上次使用的JLINK序列号"""
        self.config.set('Connection', 'last_jlink_serial', serial)
    
    def get_auto_select_jlink(self) -> bool:
        """获取是否自动选择JLINK"""
        return self.config.getboolean('Connection', 'auto_select_jlink', fallback=False)
    
    def set_auto_select_jlink(self, auto_select: bool):
        """设置是否自动选择JLINK"""
        self.config.set('Connection', 'auto_select_jlink', str(auto_select).lower())
    
    def get_auto_reconnect(self) -> bool:
        """获取自动重连设置"""
        return self._safe_getboolean('Connection', 'auto_reconnect', True)
    
    def set_auto_reconnect(self, enabled: bool):
        """设置自动重连"""
        self.config.set('Connection', 'auto_reconnect', str(enabled).lower())
    
    def get_auto_reconnect_on_no_data(self) -> bool:
        """获取无数据自动重连设置"""
        return self._safe_getboolean('Connection', 'auto_reconnect_on_no_data', False)
    
    def set_auto_reconnect_on_no_data(self, enabled: bool):
        """设置无数据自动重连"""
        self.config.set('Connection', 'auto_reconnect_on_no_data', str(enabled).lower())
    
    def get_auto_reconnect_timeout(self) -> int:
        """获取自动重连超时时间（秒）"""
        return self._safe_getint('Connection', 'auto_reconnect_timeout', 60)
    
    def set_auto_reconnect_timeout(self, timeout: int):
        """设置自动重连超时时间（秒）"""
        self.config.set('Connection', 'auto_reconnect_timeout', str(timeout))
    
    def get_rtt_control_block_mode(self) -> str:
        """获取RTT Control Block模式: 'auto', 'address', 'search_range'"""
        return self.config.get('Connection', 'rtt_control_block_mode', fallback='auto')
    
    def set_rtt_control_block_mode(self, mode: str):
        """设置RTT Control Block模式"""
        self.config.set('Connection', 'rtt_control_block_mode', mode)
    
    def get_rtt_address(self) -> str:
        """获取RTT Control Block地址（Address模式）"""
        return self.config.get('Connection', 'rtt_address', fallback='')
    
    def set_rtt_address(self, address: str):
        """设置RTT Control Block地址（Address模式）"""
        self.config.set('Connection', 'rtt_address', address)
    
    def get_rtt_search_range(self) -> str:
        """获取RTT Control Block搜索范围（Search Range模式）"""
        return self.config.get('Connection', 'rtt_search_range', fallback='')
    
    def set_rtt_search_range(self, search_range: str):
        """设置RTT Control Block搜索范围（Search Range模式）"""
        self.config.set('Connection', 'rtt_search_range', search_range)
    
    # ===========================================
    # 串口设置相关方法
    # ===========================================
    
    def get_port_index(self) -> int:
        """获取串口索引"""
        return self._safe_getint('Serial', 'port_index', 0)
    
    def set_port_index(self, index: int):
        """设置串口索引"""
        self.config.set('Serial', 'port_index', str(index))
    
    def get_baudrate(self) -> int:
        """获取波特率值"""
        return self._safe_getint('Serial', 'baudrate', 115200)
    
    def set_baudrate(self, baudrate: int):
        """设置波特率值"""
        self.config.set('Serial', 'baudrate', str(baudrate))
    
    def get_port_name(self) -> str:
        """获取端口名"""
        return self.config.get('Serial', 'port_name', fallback='')
    
    def set_port_name(self, port_name: str):
        """设置端口名"""
        self.config.set('Serial', 'port_name', port_name)
    
    def get_reset_target(self) -> bool:
        """获取重置目标设置"""
        return self._safe_getboolean('Serial', 'reset_target', False)
    
    def set_reset_target(self, enabled: bool):
        """设置重置目标"""
        self.config.set('Serial', 'reset_target', str(enabled).lower())
    
    # ===========================================
    # 串口转发设置相关方法
    # ===========================================
    
    def get_serial_forward_enabled(self) -> bool:
        """获取串口转发是否启用"""
        return self._safe_getboolean('SerialForward', 'enabled', False)
    
    def set_serial_forward_enabled(self, enabled: bool):
        """设置串口转发启用状态"""
        self.config.set('SerialForward', 'enabled', str(enabled).lower())
    
    def get_serial_forward_mode(self) -> str:
        """获取串口转发模式"""
        return self.config.get('SerialForward', 'mode', fallback='LOG')
    
    def set_serial_forward_mode(self, mode: str):
        """设置串口转发模式"""
        self.config.set('SerialForward', 'mode', mode)
    
    def get_serial_forward_target_tab(self) -> int:
        """获取串口转发目标TAB"""
        return self._safe_getint('SerialForward', 'target_tab', -1)
    
    def set_serial_forward_target_tab(self, tab: int):
        """设置串口转发目标TAB"""
        self.config.set('SerialForward', 'target_tab', str(tab))

    # ===========================================
    # Watch/Memory/FrameBuffer panel settings
    # ===========================================

    def get_watch_elf_path(self) -> str:
        return self._safe_get('WatchPanel', 'elf_path', '')

    def set_watch_elf_path(self, path: str):
        self.config.set('WatchPanel', 'elf_path', path or '')

    def get_watch_recent_exprs(self) -> List[str]:
        try:
            raw = self.config.get('WatchPanel', 'recent_exprs', fallback='[]')
            arr = json.loads(raw)
            if isinstance(arr, list):
                out: List[str] = []
                for x in arr:
                    if isinstance(x, str) and x.strip():
                        out.append(x.strip())
                return out
        except Exception:
            return []
        return []

    def set_watch_recent_exprs(self, exprs: List[str]):
        try:
            arr = [x for x in exprs if isinstance(x, str) and x.strip()]
            self.config.set('WatchPanel', 'recent_exprs', json.dumps(arr[:10], ensure_ascii=False))
        except Exception:
            self.config.set('WatchPanel', 'recent_exprs', '[]')

    def get_watch_mem_addr(self) -> str:
        return self._safe_get('WatchPanel', 'mem_addr', '0x20000000')

    def set_watch_mem_addr(self, addr_text: str):
        self.config.set('WatchPanel', 'mem_addr', addr_text or '')

    def get_watch_mem_size(self) -> int:
        return self._safe_getint('WatchPanel', 'mem_size', 256)

    def set_watch_mem_size(self, size: int):
        try:
            self.config.set('WatchPanel', 'mem_size', str(int(size)))
        except Exception:
            self.config.set('WatchPanel', 'mem_size', '256')

    def get_watch_fb_addr(self) -> str:
        return self._safe_get('WatchPanel', 'fb_addr', '')

    def set_watch_fb_addr(self, addr_text: str):
        self.config.set('WatchPanel', 'fb_addr', addr_text or '')

    def get_watch_fb_w(self) -> int:
        return self._safe_getint('WatchPanel', 'fb_w', 0)

    def set_watch_fb_w(self, w: int):
        try:
            self.config.set('WatchPanel', 'fb_w', str(int(w)))
        except Exception:
            self.config.set('WatchPanel', 'fb_w', '0')

    def get_watch_fb_h(self) -> int:
        return self._safe_getint('WatchPanel', 'fb_h', 0)

    def set_watch_fb_h(self, h: int):
        try:
            self.config.set('WatchPanel', 'fb_h', str(int(h)))
        except Exception:
            self.config.set('WatchPanel', 'fb_h', '0')

    def get_watch_fb_fmt(self) -> str:
        return self._safe_get('WatchPanel', 'fb_fmt', 'MonoLSB')

    def set_watch_fb_fmt(self, fmt: str):
        self.config.set('WatchPanel', 'fb_fmt', fmt or 'MonoLSB')

    def get_watch_fb_auto(self) -> bool:
        return self._safe_getboolean('WatchPanel', 'fb_auto', False)

    def set_watch_fb_auto(self, enabled: bool):
        self.config.set('WatchPanel', 'fb_auto', str(bool(enabled)).lower())

    # ===========================================
    # Auto Test
    # ===========================================

    def get_auto_test_rules(self) -> List[Dict[str, Any]]:
        """Return up to 3 auto-test rules."""
        try:
            raw = self.config.get('AutoTest', 'rules', fallback='[]')
            arr = json.loads(raw)
            if not isinstance(arr, list):
                return []
            out: List[Dict[str, Any]] = []
            for item in arr[:3]:
                if isinstance(item, dict):
                    out.append(item)
            return out
        except Exception:
            return []

    def set_auto_test_rules(self, rules: List[Dict[str, Any]]):
        """Persist up to 3 auto-test rules as JSON."""
        try:
            arr = []
            for r in (rules or [])[:3]:
                if isinstance(r, dict):
                    arr.append(r)
            self.config.set('AutoTest', 'rules', json.dumps(arr, ensure_ascii=False))
        except Exception:
            self.config.set('AutoTest', 'rules', '[]')
    
    # ===========================================
    # UI设置相关方法
    # ===========================================
    
    def get_light_mode(self) -> bool:
        """获取浅色模式设置"""
        return self._safe_getboolean('UI', 'light_mode', False)
    
    def set_light_mode(self, enabled: bool):
        """设置浅色模式"""
        self.config.set('UI', 'light_mode', str(enabled).lower())
    
    def get_fontsize(self) -> int:
        """获取字体大小"""
        return self._safe_getint('UI', 'fontsize', 9)
    
    def set_fontsize(self, size: int):
        """设置字体大小"""
        self.config.set('UI', 'fontsize', str(size))
    
    def get_fontfamily(self) -> str:
        """获取字体名称（优先使用支持CJK的等宽字体）"""
        import sys
        from PySide6.QtGui import QFontDatabase
        
        # 定义优先字体列表：SimSun -> Consolas -> Courier New
        if sys.platform == "darwin":
            preferred_fonts = ["SimSun", "Consolas", "Courier New", "Monaco", "Menlo"]
        else:
            preferred_fonts = ["SimSun", "Consolas", "Courier New"]
        
        # 检查系统中是否有优先字体
        font_db = QFontDatabase()
        system_fonts = set(font_db.families())
        
        for font in preferred_fonts:
            if font in system_fonts:
                default_font = font
                break
        else:
            # 如果没有找到任何优先字体，使用最后的备选
            default_font = "Courier New" if sys.platform != "darwin" else "Monaco"
        
        return self._safe_get('UI', 'fontfamily', default_font)
    
    def set_fontfamily(self, font: str):
        """设置字体名称"""
        self.config.set('UI', 'fontfamily', font)
    
    def get_dpi_scale(self) -> str:
        """获取DPI缩放设置"""
        return self._safe_get('UI', 'dpi_scale', 'auto')
    
    def set_dpi_scale(self, scale):
        """设置DPI缩放"""
        # 验证输入值
        if scale == 'auto':
            self.config.set('UI', 'dpi_scale', str(scale))
        else:
            try:
                scale_value = float(scale)
                if 0.1 <= scale_value <= 5.0:
                    self.config.set('UI', 'dpi_scale', str(scale))
                else:
                    raise ValueError(f"DPI缩放值超出范围: {scale}，应为0.1-5.0之间的数值")
            except ValueError as e:
                if "could not convert" in str(e):
                    raise ValueError(f"DPI缩放值无效: {scale}，应为'auto'或0.1-5.0之间的数值")
                else:
                    raise e
    
    def get_lock_horizontal(self) -> bool:
        """获取水平锁定设置"""
        return self._safe_getboolean('UI', 'lock_horizontal', True)
    
    def set_lock_horizontal(self, enabled: bool):
        """设置水平锁定"""
        self.config.set('UI', 'lock_horizontal', str(enabled).lower())
    
    def get_lock_vertical(self) -> bool:
        """获取垂直锁定设置"""
        return self._safe_getboolean('UI', 'lock_vertical', False)
    
    def set_lock_vertical(self, enabled: bool):
        """设置垂直锁定"""
        self.config.set('UI', 'lock_vertical', str(enabled).lower())
    
    def get_regex_filter(self) -> bool:
        """获取全局正则表达式筛选开关设置（向后兼容）"""
        return self._safe_getboolean('UI', 'regex_filter', False)
    
    def set_regex_filter(self, enabled: bool):
        """设置全局正则表达式筛选开关（向后兼容）"""
        self.config.set('UI', 'regex_filter', str(enabled).lower())
    
    def get_language(self) -> str:
        """获取界面语言设置"""
        return self.config.get('UI', 'language', fallback='zh_CN')
    
    def set_language(self, language: str):
        """设置界面语言
        
        Args:
            language: 语言代码，支持 'en_US', 'zh_CN', 'zh_TW'
        """
        valid_languages = ['en_US', 'zh_CN', 'zh_TW']
        if language in valid_languages:
            self.config.set('UI', 'language', language)
        else:
            logger.debug(f"Warning: Invalid language '{language}', using default 'zh_CN'")
            self.config.set('UI', 'language', 'zh_CN')
    
    # ===========================================
    # 标签页颜色配置相关方法
    # ===========================================
    def get_channel_color(self, channel_index):
        """获取指定通道的颜色配置"""
        if 'ChannelColors' in self.config:
            # 尝试获取前景色数组
            if 'fgcolors' in self.config['ChannelColors']:
                fg_colors = self.config['ChannelColors']['fgcolors'].split(',')
                if channel_index < len(fg_colors):
                    fg_color = fg_colors[channel_index]
                else:
                    fg_color = 'FFFFFF'  # 默认前景色
            else:
                fg_color = 'FFFFFF'  # 默认前景色
                
            # 尝试获取背景色数组
            if 'bgcolors' in self.config['ChannelColors']:
                bg_colors = self.config['ChannelColors']['bgcolors'].split(',')
                if channel_index < len(bg_colors):
                    bg_color = bg_colors[channel_index]
                else:
                    bg_color = '000000'  # 默认背景色
            else:
                bg_color = '000000'  # 默认背景色
                
            return (fg_color, bg_color)
        # 返回默认颜色
        return ('FFFFFF', '000000')

    def set_channel_color(self, channel_index, fg_color, bg_color):
        """设置指定通道的颜色配置"""
        if 'ChannelColors' not in self.config:
            self.config['ChannelColors'] = {}
            
        # 确保前景色数组存在
        if 'fgcolors' not in self.config['ChannelColors']:
            # 创建默认的前景色数组
            default_fg_colors = ['FFFFFF'] * 16
            self.config['ChannelColors']['fgcolors'] = ','.join(default_fg_colors)
        
        # 确保背景色数组存在
        if 'bgcolors' not in self.config['ChannelColors']:
            # 创建默认的背景色数组
            default_bg_colors = ['000000'] * 16
            self.config['ChannelColors']['bgcolors'] = ','.join(default_bg_colors)
        
        # 更新前景色
        fg_colors = self.config['ChannelColors']['fgcolors'].split(',')
        # 确保数组足够大
        while len(fg_colors) <= channel_index:
            fg_colors.append('FFFFFF')  # 添加默认颜色
        fg_colors[channel_index] = fg_color
        self.config['ChannelColors']['fgcolors'] = ','.join(fg_colors)
        
        # 更新背景色
        bg_colors = self.config['ChannelColors']['bgcolors'].split(',')
        # 确保数组足够大
        while len(bg_colors) <= channel_index:
            bg_colors.append('000000')  # 添加默认颜色
        bg_colors[channel_index] = bg_color
        self.config['ChannelColors']['bgcolors'] = ','.join(bg_colors)
    
    def get_tab_regex_filter(self, tab_index: int) -> bool:
        """获取指定TAB的正则表达式筛选开关设置"""
        key = f'regex_filter_{tab_index}'
        return self._safe_getboolean('TabRegex', key, False)
    
    def set_tab_regex_filter(self, tab_index: int, enabled: bool):
        """设置指定TAB的正则表达式筛选开关"""
        if not self.config.has_section('TabRegex'):
            self.config.add_section('TabRegex')
        key = f'regex_filter_{tab_index}'
        self.config.set('TabRegex', key, str(enabled).lower())
    
    # ===========================================
    # 过滤器相关方法
    # ===========================================
    
    def get_filter(self, filter_index: int) -> str:
        """获取指定过滤器的内容"""
        key = f'filter_{filter_index}'
        return self.config.get('Filters', key, fallback='')
    
    def set_filter(self, filter_index: int, content: str):
        """设置指定过滤器的内容"""
        # 🔧 调试日志已禁用 - 筛选器问题已解决
        # 如需重新启用，将 DEBUG_FILTER_SET 设置为 True
        DEBUG_FILTER_SET = False
        
        if DEBUG_FILTER_SET:
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            
            # 打印调用栈和修改信息
            call_stack = traceback.extract_stack()
            caller_info = []
            # 获取最近的3个调用层级（排除当前函数）
            for frame in call_stack[-4:-1]:
                caller_info.append(f"{frame.filename}:{frame.lineno} in {frame.name}")
            
            logger.info("=" * 40)
            logger.info(f"[FILTER SET] set_filter({filter_index}, '{content}')")
            logger.info(f"[FILTER SET] 调用栈:")
            for i, caller in enumerate(caller_info, 1):
                logger.info(f"[FILTER SET]   {i}. {caller}")
            
            key = f'filter_{filter_index}'
            
            # 记录修改前的值
            old_value = self.config.get('Filters', key, fallback='<不存在>')
            logger.info(f"[FILTER SET] 修改前: filter_{filter_index} = '{old_value}'")
        
        key = f'filter_{filter_index}'
        self.config.set('Filters', key, content)
        
        if DEBUG_FILTER_SET:
            logger.info(f"[FILTER SET] 修改后: filter_{filter_index} = '{content}'")
            logger.info("=" * 40)
    
    def get_all_filters(self) -> Dict[int, str]:
        """获取所有过滤器设置"""
        filters = {}
        for key, value in self.config.items('Filters'):
            if key.startswith('filter_'):
                try:
                    index = int(key.replace('filter_', ''))
                    filters[index] = value
                except ValueError:
                    continue
        return filters
    
    # ===========================================
    # 命令历史相关方法
    # ===========================================
    
    def get_command_history(self) -> List[str]:
        """从CMD.txt文件读取命令历史"""
        if not os.path.exists(self.cmd_file):
            return []
        
        try:
            # 优先尝试UTF-8编码
            with open(self.cmd_file, 'r', encoding='utf-8') as f:
                commands = []
                for line in f:
                    line = line.strip()
                    if line:  # 忽略空行
                        commands.append(line)
                return commands
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试GBK（兼容旧文件）
            try:
                with open(self.cmd_file, 'r', encoding='gbk') as f:
                    commands = []
                    for line in f:
                        line = line.strip()
                        if line:  # 忽略空行
                            commands.append(line)
                    # 读取成功后，立即转换为UTF-8格式保存
                    self._convert_cmd_file_to_utf8(commands)
                    return commands
            except Exception as e:
                logger.debug(f"读取命令历史失败 (GBK): {e}")
                return []
        except Exception as e:
            logger.debug(f"读取命令历史失败: {e}")
            return []
    
    def add_command_to_history(self, command: str):
        """添加命令到历史记录"""
        if not command.strip():
            return
        
        try:
            # 读取现有命令
            existing_commands = self.get_command_history()
            
            # 避免重复添加相同命令
            if command in existing_commands:
                existing_commands.remove(command)
            
            # 将新命令添加到最前面
            existing_commands.insert(0, command)
            
            # 限制历史记录数量（保留最近100条）
            existing_commands = existing_commands[:100]
            
            # 写回文件，使用UTF-8编码
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.cmd_file, 'w', encoding='utf-8') as f:
                for cmd in existing_commands:
                    f.write(cmd + '\n')
            
            logger.debug(f"命令已添加到历史记录: {command}")
            
        except Exception as e:
            logger.debug(f"保存命令历史失败: {e}")
    
    def _convert_cmd_file_to_utf8(self, commands: List[str]):
        """将命令历史文件从GBK转换为UTF-8编码"""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.cmd_file, 'w', encoding='utf-8') as f:
                for cmd in commands:
                    f.write(cmd + '\n')
            logger.debug(f"命令历史文件已转换为UTF-8编码: {self.cmd_file}")
        except Exception as e:
            logger.debug(f"转换命令历史文件编码失败: {e}")
    
    def clear_command_history(self):
        """清空命令历史"""
        try:
            # 创建空的UTF-8编码文件
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.cmd_file, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
            logger.debug("命令历史已清空")
        except Exception as e:
            logger.debug(f"清空命令历史失败: {e}")
    
    # ===========================================
    # 查找历史相关方法
    # ===========================================
    
    def get_search_history(self) -> List[str]:
        """获取查找历史记录"""
        try:
            history_str = self.config.get('Find', 'search_history', fallback='[]')
            return json.loads(history_str)
        except:
            return []
    
    def add_search_to_history(self, search_text: str):
        """添加查找内容到历史记录"""
        if not search_text.strip():
            return
        
        try:
            # 读取现有历史
            existing_history = self.get_search_history()
            
            # 避免重复添加相同内容
            if search_text in existing_history:
                existing_history.remove(search_text)
            
            # 将新内容添加到最前面
            existing_history.insert(0, search_text)
            
            # 限制历史记录数量（保留最近10条）
            existing_history = existing_history[:10]
            
            # 保存到配置
            if not self.config.has_section('Find'):
                self.config.add_section('Find')
            self.config.set('Find', 'search_history', json.dumps(existing_history, ensure_ascii=False))
            
        except Exception as e:
            logger.debug(f"保存查找历史失败: {e}")
    
    def clear_search_history(self):
        """清空查找历史"""
        try:
            if not self.config.has_section('Find'):
                self.config.add_section('Find')
            self.config.set('Find', 'search_history', '[]')
            logger.debug("查找历史已清空")
        except Exception as e:
            logger.debug(f"清空查找历史失败: {e}")
    
    def get_max_log_size(self) -> int:
        """获取最大日志行数"""
        # 优先读取新键 max_lines，兼容旧键 max_log_size
        if self.config.has_option('Logging', 'max_lines'):
            return self._safe_getint('Logging', 'max_lines', 10000)
        return self._safe_getint('Logging', 'max_log_size', 10000)
    
    def set_max_log_size(self, max_lines: int):
        """设置最大日志行数"""
        self.config.set('Logging', 'max_lines', str(max_lines))
    
    def get_log_split(self) -> bool:
        """获取日志拆分设置"""
        return self._safe_getboolean('Logging', 'log_split', True)
    
    def set_log_split(self, enabled: bool):
        """设置日志拆分"""
        self.config.set('Logging', 'log_split', str(enabled).lower())
    
    # get_last_log_directory 方法已移除 - 不再使用上次日志目录功能
    
    # set_last_log_directory 方法已移除 - 不再使用上次日志目录功能
    
    def get_clean_trigger_ms(self) -> int:
        """获取触发清理的UI耗时阈值（毫秒）"""
        return self._safe_getint('Performance', 'clean_trigger_ms', 50)
    
    def set_clean_trigger_ms(self, ms: int):
        """设置触发清理的UI耗时阈值（毫秒）"""
        self.config.set('Performance', 'clean_trigger_ms', str(ms))
    
    def get_warning_trigger_ms(self) -> int:
        """获取触发警告的UI耗时阈值（毫秒）"""
        return self._safe_getint('Performance', 'warning_trigger_ms', 100)
    
    def set_warning_trigger_ms(self, ms: int):
        """设置触发警告的UI耗时阈值（毫秒）"""
        self.config.set('Performance', 'warning_trigger_ms', str(ms))
    
    def get_clean_ratio_denominator(self) -> int:
        """获取清理比例分母（清理 1/N）"""
        return self._safe_getint('Performance', 'clean_ratio_denominator', 10)
    
    def set_clean_ratio_denominator(self, denominator: int):
        """设置清理比例分母（清理 1/N）"""
        if denominator <= 0:
            denominator = 10  # 防止除零错误
        self.config.set('Performance', 'clean_ratio_denominator', str(denominator))
    
    # ===========================================
    # 迁移和兼容性方法
    # ===========================================
    
    def migrate_from_pickle(self, pickle_file_path: str):
        """从旧的pickle格式配置文件迁移设置"""
        if not os.path.exists(pickle_file_path):
            return False
        
        try:
            import pickle
            with open(pickle_file_path, 'rb') as f:
                old_settings = pickle.load(f)
            
            logger.debug("开始从pickle格式迁移配置...")
            
            # 迁移各项设置
            if 'device' in old_settings:
                self.set_device_list(old_settings.get('device', []))
            
            if 'device_index' in old_settings:
                self.set_device_index(old_settings.get('device_index', 0))
            
            if 'interface' in old_settings:
                self.set_interface(old_settings.get('interface', 0))
            
            if 'speed' in old_settings:
                self.set_speed(old_settings.get('speed', 0))
            
            if 'port' in old_settings:
                self.set_port_index(old_settings.get('port', 0))
            
            if 'buadrate' in old_settings:  # 注意：原来的拼写错误
                self.set_baudrate(old_settings.get('buadrate', 16))
            
            if 'lock_h' in old_settings:
                self.set_lock_horizontal(bool(old_settings.get('lock_h', 1)))
            
            if 'lock_v' in old_settings:
                self.set_lock_vertical(bool(old_settings.get('lock_v', 0)))
            
            if 'light_mode' in old_settings:
                self.set_light_mode(bool(old_settings.get('light_mode', 0)))
            
            if 'fontsize' in old_settings:
                self.set_fontsize(old_settings.get('fontsize', 9))
            
            if 'serial_forward_tab' in old_settings:
                self.set_serial_forward_target_tab(old_settings.get('serial_forward_tab', -1))
            
            if 'serial_forward_mode' in old_settings:
                self.set_serial_forward_mode(old_settings.get('serial_forward_mode', 'LOG'))
            
            # 迁移过滤器设置
            if 'filter' in old_settings:
                filters = old_settings.get('filter', [])
                for i, filter_content in enumerate(filters):
                    if filter_content is not None:
                        self.set_filter(i + 17, str(filter_content))  # 过滤器从索引17开始
            
            # 迁移命令历史
            if 'cmd' in old_settings:
                commands = old_settings.get('cmd', [])
                for cmd in commands:
                    if cmd:
                        self.add_command_to_history(str(cmd))
            
            # 保存迁移后的配置
            self.save_config()
            
            logger.debug("配置迁移完成")
            return True
            
        except Exception as e:
            logger.debug(f"配置迁移失败: {e}")
            return False
    
    def _migrate_from_app_bundle(self):
        """从APP内部迁移配置文件到用户目录"""
        try:
            import sys
            if getattr(sys, 'frozen', False):  # 如果是打包的APP
                # 获取APP内部资源路径
                if sys.platform == "darwin":  # macOS
                    app_bundle_path = os.path.dirname(sys.executable)
                    # 在macOS APP中，可执行文件在Contents/MacOS/目录下
                    app_bundle_path = os.path.dirname(os.path.dirname(os.path.dirname(app_bundle_path)))
                    app_config_file = os.path.join(app_bundle_path, "Resources", "config.ini")
                    app_cmd_file = os.path.join(app_bundle_path, "Resources", "cmd.txt")
                else:
                    # Windows/Linux
                    app_bundle_path = os.path.dirname(sys.executable)
                    app_config_file = os.path.join(app_bundle_path, "config.ini")
                    app_cmd_file = os.path.join(app_bundle_path, "cmd.txt")
                
                # 迁移配置文件
                if os.path.exists(app_config_file) and not os.path.exists(self.config_file):
                    logger.debug(f"从APP内部迁移配置文件: {app_config_file} -> {self.config_file}")
                    os.makedirs(self.config_dir, exist_ok=True)
                    import shutil
                    shutil.copy2(app_config_file, self.config_file)
                    # 重新加载配置
                    self.load_config()
                
                # 迁移命令历史文件
                if os.path.exists(app_cmd_file) and not os.path.exists(self.cmd_file):
                    logger.debug(f"从APP内部迁移命令历史: {app_cmd_file} -> {self.cmd_file}")
                    os.makedirs(self.config_dir, exist_ok=True)
                    import shutil
                    shutil.copy2(app_cmd_file, self.cmd_file)
                    
        except Exception as e:
            logger.debug(f"配置文件迁移失败: {e}")


# 全局配置管理器实例
config_manager = ConfigManager()
