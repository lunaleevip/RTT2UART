# -*- coding: utf-8 -*-
"""
UI 常量配置文件
集中管理所有 UI 相关的硬编码常量
"""

# ============================================================================
# 窗口尺寸配置
# ============================================================================
class WindowSize:
    """窗口尺寸常量"""
    # 主窗口
    MAIN_WINDOW_BASE_WIDTH = 1200
    MAIN_WINDOW_BASE_HEIGHT = 800
    MAIN_WINDOW_MIN_WIDTH = 200
    MAIN_WINDOW_MIN_HEIGHT = 150
    
    # MDI 子窗口
    MDI_WINDOW_DEFAULT_WIDTH = 800
    MDI_WINDOW_DEFAULT_HEIGHT = 600
    
    # 对话框
    CONNECTION_DIALOG_WIDTH = 700
    CONNECTION_DIALOG_HEIGHT = 500
    DEVICE_DIALOG_WIDTH = 400
    DEVICE_DIALOG_HEIGHT = 150
    FIND_DIALOG_WIDTH = 500
    FIND_DIALOG_HEIGHT = 350
    
    # 紧凑模式
    COMPACT_MODE_WIDTH = 400
    COMPACT_MODE_NORMAL_WIDTH = 800
    COMPACT_MODE_NORMAL_HEIGHT = 600


# ============================================================================
# 布局尺寸配置
# ============================================================================
class LayoutSize:
    """布局尺寸常量"""
    # 按钮区域
    BUTTON_AREA_HEIGHT = 70
    
    # JLink 日志区域
    JLINK_LOG_MIN_HEIGHT = 80      # 最小高度（约4行数据）
    JLINK_LOG_MAX_HEIGHT = 400     # 最大高度
    JLINK_LOG_DEFAULT_HEIGHT = 150 # 默认高度
    
    # 底部容器（按钮区 + JLink日志区）
    BOTTOM_CONTAINER_HEIGHT = BUTTON_AREA_HEIGHT + JLINK_LOG_DEFAULT_HEIGHT  # 220px
    
    # 菜单栏、状态栏等额外空间
    MENUBAR_STATUSBAR_HEIGHT = 100
    
    # 表格列宽
    TABLE_COLUMN_WIDTH_MANUFACTURER = 100


# ============================================================================
# 定时器配置
# ============================================================================
class TimerInterval:
    """定时器间隔常量（单位：毫秒）"""
    # UI 更新
    MDI_WINDOW_UPDATE = 100        # MDI 窗口更新间隔
    BUFFER_FLUSH = 500             # 缓冲区刷新间隔（优化：增加间隔减少CPU占用）
    DELAYED_INIT = 100             # 延迟初始化
    
    # 状态检查
    DATA_CHECK = 5000              # 数据检查间隔（5秒）
    STATUS_UPDATE = 1000           # 状态更新间隔（1秒）
    JLINK_LOG_TAIL = 500           # JLink 日志拉取间隔
    
    # 延迟操作
    DELAYED_DISPLAY = 1000         # 延迟显示
    DELAYED_FONT_REFRESH = 100     # 延迟字体刷新
    AUTO_RECONNECT = 1000          # 自动重连延迟
    FORCE_QUIT = 2000              # 强制退出延迟
    
    # 状态栏消息显示时间
    STATUSBAR_MESSAGE_SHORT = 2000  # 短消息（2秒）
    STATUSBAR_MESSAGE_LONG = 3000   # 长消息（3秒）


# ============================================================================
# 缓冲区配置
# ============================================================================
class BufferConfig:
    """缓冲区配置常量"""
    # 文本缓冲
    MAX_TEXT_CHARS = 3000          # 最大字符数
    MAX_BLOCKS = 1000              # 最大文本块数
    BLOCK_CLEANUP_COUNT = 100      # 清理时保留的块数
    
    # 日志缓冲
    MAX_LOG_BUFFERS = 100          # 最大同时缓冲的文件数量
    
    # 内存缓冲（Worker）
    INITIAL_CAPACITY = 100 * 1024  # 初始容量 100KB
    MAX_CAPACITY = 6400 * 1024     # 最大容量 6.4MB
    MEMORY_WARNING_THRESHOLD = 0.8 # 内存警告阈值（800KB）
    
    # UI 性能警告阈值
    UI_WARNING_THRESHOLD_MS = 100  # UI 操作超过 100ms 发出警告


# ============================================================================
# 串口配置
# ============================================================================
class SerialConfig:
    """串口配置常量"""
    # JLink 速率列表（kHz）
    SPEED_LIST = [
        5, 10, 20, 30, 50, 100, 200, 300, 400, 500, 600, 750,
        900, 1000, 1334, 1600, 2000, 2667, 3200, 4000, 4800, 5334, 6000, 8000, 9600, 12000,
        15000, 20000, 25000, 30000, 40000, 50000
    ]
    
    # 波特率列表
    BAUDRATE_LIST = [
        50, 75, 110, 134, 150, 200, 300, 600, 1200, 1800, 2400, 4800,
        9600, 19200, 38400, 57600, 115200, 230400, 460800, 500000, 576000, 921600
    ]
    
    # 默认值
    DEFAULT_SPEED = 4000
    DEFAULT_BAUDRATE = 115200
    DEFAULT_BAUDRATE_INDEX = 16  # 115200 在列表中的索引


# ============================================================================
# RTT 地址配置
# ============================================================================
class RTTAddress:
    """RTT 地址配置常量"""
    # 默认地址
    DEFAULT_ADDRESS_STM32 = '0x20000000'
    DEFAULT_ADDRESS_EXAMPLE = '0x10000000 0x1000, 0x20000000 0x1000'
    
    # Windows 文件访问权限
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000


# ============================================================================
# 清理配置
# ============================================================================
class CleanupConfig:
    """清理配置常量"""
    # 最大条目数
    MAX_ITEMS = 100
    
    # RAM 清理进度计算基数
    RAM_PROGRESS_BASE = 100


# ============================================================================
# 颜色配置（ANSI 转 HTML）
# ============================================================================
class ColorConfig:
    """颜色配置常量"""
    # ANSI 黄色转 HTML（深黄色）
    ANSI_YELLOW_HTML = '#808000'

