#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT2UART 性能监控工具
实时监控程序性能指标，帮助诊断性能问题
"""

import time
import psutil
import threading
from collections import deque
import sys

class PerformanceMonitor:
    def __init__(self, process_name="python.exe"):
        self.process_name = process_name
        self.process = None
        self.monitoring = False
        
        # 性能数据缓存 (最近60个数据点)
        self.cpu_history = deque(maxlen=60)
        self.memory_history = deque(maxlen=60)
        self.io_history = deque(maxlen=60)
        
        # 监控线程
        self.monitor_thread = None
        
    def find_target_process(self):
        """查找目标进程"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'main_window.py' in ' '.join(proc.info['cmdline'] or []):
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def start_monitoring(self):
        """开始监控"""
        self.process = self.find_target_process()
        if not self.process:
            print("❌ 未找到RTT2UART进程，请先启动主程序")
            return False
            
        print(f"✅ 找到目标进程: PID {self.process.pid}")
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        return True
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                if not self.process or not self.process.is_running():
                    print("⚠️  目标进程已退出")
                    break
                
                # 获取性能数据
                cpu_percent = self.process.cpu_percent()
                memory_info = self.process.memory_info()
                io_counters = self.process.io_counters()
                
                # 存储历史数据
                self.cpu_history.append(cpu_percent)
                self.memory_history.append(memory_info.rss / 1024 / 1024)  # MB
                self.io_history.append(io_counters.read_bytes + io_counters.write_bytes)
                
                time.sleep(1)  # 每秒采样一次
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print("⚠️  无法访问进程信息")
                break
            except Exception as e:
                print(f"⚠️  监控错误: {e}")
                time.sleep(1)
    
    def get_current_stats(self):
        """获取当前性能统计"""
        if not self.cpu_history:
            return None
            
        stats = {
            'cpu_current': self.cpu_history[-1] if self.cpu_history else 0,
            'cpu_avg': sum(self.cpu_history) / len(self.cpu_history),
            'cpu_max': max(self.cpu_history),
            'memory_current': self.memory_history[-1] if self.memory_history else 0,
            'memory_max': max(self.memory_history) if self.memory_history else 0,
            'io_current': self.io_history[-1] if self.io_history else 0,
        }
        return stats
    
    def print_performance_report(self):
        """打印性能报告"""
        stats = self.get_current_stats()
        if not stats:
            print("📊 暂无性能数据")
            return
            
        print("\n" + "="*50)
        print("📊 RTT2UART 性能报告")
        print("="*50)
        print(f"🖥️  CPU 使用率:")
        print(f"   当前: {stats['cpu_current']:.1f}%")
        print(f"   平均: {stats['cpu_avg']:.1f}%")
        print(f"   峰值: {stats['cpu_max']:.1f}%")
        
        print(f"\n💾 内存使用:")
        print(f"   当前: {stats['memory_current']:.1f} MB")
        print(f"   峰值: {stats['memory_max']:.1f} MB")
        
        print(f"\n💽 I/O 累计: {stats['io_current'] / 1024 / 1024:.1f} MB")
        
        # 性能评估
        print(f"\n📈 性能评估:")
        if stats['cpu_avg'] > 20:
            print("   ⚠️  CPU使用率较高，建议优化")
        elif stats['cpu_avg'] > 10:
            print("   🟡 CPU使用率中等")
        else:
            print("   ✅ CPU使用率良好")
            
        if stats['memory_current'] > 500:
            print("   ⚠️  内存使用较多，建议检查内存泄漏")
        elif stats['memory_current'] > 200:
            print("   🟡 内存使用中等")
        else:
            print("   ✅ 内存使用良好")
            
        print("="*50)

def main():
    """主函数"""
    print("🔍 RTT2UART 性能监控工具")
    print("按 Ctrl+C 停止监控\n")
    
    monitor = PerformanceMonitor()
    
    if not monitor.start_monitoring():
        return
    
    try:
        while True:
            time.sleep(5)  # 每5秒显示一次报告
            monitor.print_performance_report()
            
    except KeyboardInterrupt:
        print("\n🛑 停止监控...")
        monitor.stop_monitoring()
        
        # 显示最终报告
        print("\n📋 最终性能报告:")
        monitor.print_performance_report()

if __name__ == "__main__":
    main()

