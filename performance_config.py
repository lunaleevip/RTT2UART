#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT2UART 性能配置文件
可调整的性能参数，用于细致调优
"""

# GUI更新配置
class GUIConfig:
    # 主界面刷新间隔 (毫秒)
    MAIN_REFRESH_INTERVAL = 500  # 原来100ms，现在500ms
    
    # 页面批量更新限制
    MAX_PAGES_PER_UPDATE = 3  # 每次最多更新3个页面
    
    # 文本框最大长度 (字符)
    MAX_TEXT_LENGTH = 8 * 1024 * 1024  # 8MB
    
    # 文本清理阈值 (当超过此长度时进行清理)
    TEXT_CLEANUP_THRESHOLD = MAX_TEXT_LENGTH
    
    # 保留文本比例 (清理时保留的文本比例)
    TEXT_RETAIN_RATIO = 0.5


# 数据处理配置
class DataProcessingConfig:
    # RTT读取缓冲区大小
    RTT_READ_BUFFER_SIZE = 4096  # 原来1024，现在4096
    
    # 最大连续读取次数
    MAX_READ_ATTEMPTS = 5
    
    # 日志文件缓冲刷新间隔 (毫秒)
    LOG_BUFFER_FLUSH_INTERVAL = 1000  # 1秒
    
    # 字符串缓冲区大小阈值
    STRING_BUFFER_THRESHOLD = 1024
    
    # 空闲时休眠时间 (秒)
    IDLE_SLEEP_TIME = 0.001  # 1ms
    
    # 错误时休眠时间 (秒)
    ERROR_SLEEP_TIME = 0.01  # 10ms


# 内存管理配置
class MemoryConfig:
    # 启用内存管理
    ENABLE_MEMORY_MANAGEMENT = True
    
    # 内存清理间隔 (秒)
    MEMORY_CLEANUP_INTERVAL = 30
    
    # 内存使用阈值 (MB)
    MEMORY_WARNING_THRESHOLD = 500
    
    # 强制垃圾回收阈值 (MB)
    FORCE_GC_THRESHOLD = 1000


# 性能监控配置
class MonitoringConfig:
    # 启用性能监控
    ENABLE_PERFORMANCE_MONITORING = False
    
    # 监控数据采样间隔 (秒)
    SAMPLING_INTERVAL = 1
    
    # 监控历史数据保留数量
    HISTORY_DATA_POINTS = 60
    
    # 性能警告阈值
    CPU_WARNING_THRESHOLD = 20  # CPU使用率超过20%时警告
    MEMORY_WARNING_THRESHOLD = 500  # 内存使用超过500MB时警告


# 调试配置
class DebugConfig:
    # 启用调试模式
    ENABLE_DEBUG_MODE = False
    
    # 启用性能日志
    ENABLE_PERFORMANCE_LOGGING = False
    
    # 启用详细错误信息
    ENABLE_VERBOSE_ERRORS = False
    
    # 调试输出文件
    DEBUG_LOG_FILE = "debug_performance.log"


def get_optimized_config():
    """获取优化后的配置字典"""
    return {
        'gui': {
            'refresh_interval': GUIConfig.MAIN_REFRESH_INTERVAL,
            'max_pages_per_update': GUIConfig.MAX_PAGES_PER_UPDATE,
            'max_text_length': GUIConfig.MAX_TEXT_LENGTH,
            'text_retain_ratio': GUIConfig.TEXT_RETAIN_RATIO,
        },
        'data_processing': {
            'rtt_buffer_size': DataProcessingConfig.RTT_READ_BUFFER_SIZE,
            'max_read_attempts': DataProcessingConfig.MAX_READ_ATTEMPTS,
            'log_flush_interval': DataProcessingConfig.LOG_BUFFER_FLUSH_INTERVAL,
            'idle_sleep_time': DataProcessingConfig.IDLE_SLEEP_TIME,
        },
        'memory': {
            'enable_management': MemoryConfig.ENABLE_MEMORY_MANAGEMENT,
            'cleanup_interval': MemoryConfig.MEMORY_CLEANUP_INTERVAL,
            'warning_threshold': MemoryConfig.MEMORY_WARNING_THRESHOLD,
        },
        'monitoring': {
            'enable': MonitoringConfig.ENABLE_PERFORMANCE_MONITORING,
            'sampling_interval': MonitoringConfig.SAMPLING_INTERVAL,
            'cpu_threshold': MonitoringConfig.CPU_WARNING_THRESHOLD,
        },
        'debug': {
            'enable_debug': DebugConfig.ENABLE_DEBUG_MODE,
            'enable_perf_log': DebugConfig.ENABLE_PERFORMANCE_LOGGING,
            'log_file': DebugConfig.DEBUG_LOG_FILE,
        }
    }

def print_current_config():
    """打印当前配置"""
    config = get_optimized_config()
    
    print("🔧 RTT2UART 性能优化配置")
    print("="*50)
    
    print("📱 GUI配置:")
    print(f"  刷新间隔: {config['gui']['refresh_interval']}ms")
    print(f"  批量更新限制: {config['gui']['max_pages_per_update']}页")
    print(f"  文本最大长度: {config['gui']['max_text_length']//1024//1024}MB")
    
    print("\n📊 数据处理配置:")
    print(f"  RTT缓冲区: {config['data_processing']['rtt_buffer_size']}字节")
    print(f"  最大读取次数: {config['data_processing']['max_read_attempts']}")
    print(f"  日志刷新间隔: {config['data_processing']['log_flush_interval']}ms")
    
    print("\n💾 内存管理配置:")
    print(f"  启用内存管理: {config['memory']['enable_management']}")
    print(f"  清理间隔: {config['memory']['cleanup_interval']}秒")
    print(f"  警告阈值: {config['memory']['warning_threshold']}MB")
    
    print("\n📈 监控配置:")
    print(f"  启用监控: {config['monitoring']['enable']}")
    print(f"  采样间隔: {config['monitoring']['sampling_interval']}秒")
    print(f"  CPU警告阈值: {config['monitoring']['cpu_threshold']}%")
    
    print("="*50)

if __name__ == "__main__":
    print_current_config()

