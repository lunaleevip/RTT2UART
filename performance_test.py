#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT性能测试脚本
用于测试大量数据写入时的性能瓶颈
"""

import sys
import random
import time
import threading
import psutil
import os
from datetime import datetime
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

class PerformanceMonitor(QObject):
    """性能监控器"""
    
    # 定义信号
    performance_updated = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.monitoring = False
        self.start_time = None
        self.data_written = 0
        self.lines_written = 0
        
    def start_monitoring(self):
        """开始性能监控"""
        self.monitoring = True
        self.start_time = time.time()
        self.data_written = 0
        self.lines_written = 0
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        
    def add_data(self, data_size, line_count=1):
        """记录数据写入"""
        self.data_written += data_size
        self.lines_written += line_count
        
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            # 获取系统性能信息
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            
            # 计算运行时间和数据速率
            elapsed_time = time.time() - self.start_time if self.start_time else 0
            data_rate = self.data_written / elapsed_time if elapsed_time > 0 else 0
            line_rate = self.lines_written / elapsed_time if elapsed_time > 0 else 0
            
            # 发送性能数据
            perf_data = {
                'elapsed_time': elapsed_time,
                'cpu_percent': cpu_percent,
                'memory_percent': memory_info.percent,
                'process_memory_mb': process_memory.rss / 1024 / 1024,
                'data_written_mb': self.data_written / 1024 / 1024,
                'lines_written': self.lines_written,
                'data_rate_kbps': data_rate / 1024,
                'line_rate_per_sec': line_rate
            }
            
            self.performance_updated.emit(perf_data)
            time.sleep(0.5)  # 每500ms更新一次


class DataGenerator(QObject):
    """随机数据生成器"""
    
    # 进度信号
    progress_updated = Signal(int)
    data_generated = Signal(list)
    
    def __init__(self):
        super().__init__()
    
    @staticmethod
    def generate_random_text(length=80):
        """生成随机文本行"""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "
        return ''.join(random.choice(chars) for _ in range(length))
    
    def generate_test_data(self, lines=10000):
        """生成测试数据（带进度更新）"""
        data = []
        batch_size = 100  # 每100行更新一次进度
        
        for i in range(lines):
            # 随机生成不同长度的行
            line_length = random.randint(50, 120)
            line = f"[{i:05d}] {self.generate_random_text(line_length)}"
            data.append(line)
            
            # 更新进度
            if (i + 1) % batch_size == 0 or i == lines - 1:
                progress = int((i + 1) * 100 / lines)
                self.progress_updated.emit(progress)
                
                # 让界面有机会更新
                QApplication.processEvents()
        
        self.data_generated.emit(data)
        return data


class PerformanceTestWidget(QWidget):
    """性能测试主界面"""
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.test_running = False
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.write_test_data)
        
        # 性能监控器
        self.perf_monitor = PerformanceMonitor()
        self.perf_monitor.performance_updated.connect(self.update_performance_display)
        
        # 测试数据
        self.test_data_pool = []
        self.current_data_index = 0
        
        # 数据生成器
        self.data_generator = DataGenerator()
        self.data_generator.progress_updated.connect(self.update_progress)
        self.data_generator.data_generated.connect(self.on_data_generated)
        
        self.init_ui()
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 如果测试正在运行，先停止测试
        if self.test_running:
            self.log_message("检测到窗口关闭，正在停止性能测试...")
            self.stop_test()
        
        # 停止性能监控
        if hasattr(self, 'perf_monitor'):
            self.perf_monitor.stop_monitoring()
        
        self.log_message("性能测试工具已安全关闭")
        
        # 调用父类的关闭事件
        super().closeEvent(event)
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("RTT性能测试工具")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QVBoxLayout()
        
        # 控制面板
        control_group = QGroupBox("测试控制")
        control_layout = QGridLayout()
        
        # 数据准备
        self.prep_button = QPushButton("1. 准备测试数据 (10000行)")
        self.prep_button.clicked.connect(self.prepare_test_data)
        control_layout.addWidget(self.prep_button, 0, 0)
        
        # 进度条和状态
        prep_widget = QWidget()
        prep_layout = QVBoxLayout(prep_widget)
        prep_layout.setContentsMargins(0, 0, 0, 0)
        
        self.prep_status = QLabel("未准备")
        prep_layout.addWidget(self.prep_status)
        
        self.prep_progress = QProgressBar()
        self.prep_progress.setVisible(False)
        self.prep_progress.setRange(0, 100)
        prep_layout.addWidget(self.prep_progress)
        
        control_layout.addWidget(prep_widget, 0, 1)
        
        # 填充数据
        fill_widget = QWidget()
        fill_layout = QHBoxLayout(fill_widget)
        fill_layout.setContentsMargins(0, 0, 0, 0)
        
        self.fill_button = QPushButton("2. 填充所有页面")
        self.fill_button.clicked.connect(self.fill_all_pages)
        self.fill_button.setEnabled(False)
        fill_layout.addWidget(self.fill_button)
        
        self.fill_fast_button = QPushButton("🚀 极速填充")
        self.fill_fast_button.clicked.connect(self.fill_all_pages_fast)
        self.fill_fast_button.setEnabled(False)
        self.fill_fast_button.setToolTip("超高速批量填充，跳过UI更新")
        fill_layout.addWidget(self.fill_fast_button)
        
        control_layout.addWidget(fill_widget, 1, 0)
        
        self.fill_status = QLabel("未填充")
        control_layout.addWidget(self.fill_status, 1, 1)
        
        # 诊断按钮
        self.diag_button = QPushButton("🔍 诊断连接状态")
        self.diag_button.clicked.connect(self.diagnose_connection)
        control_layout.addWidget(self.diag_button, 2, 0, 1, 2)
        
        # 测试参数
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("写入间隔(ms):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 1000)  # 降低最小间隔测试高频写入
        self.interval_spin.setValue(100)
        param_layout.addWidget(self.interval_spin)
        
        param_layout.addWidget(QLabel("每次行数:"))
        self.lines_spin = QSpinBox()
        self.lines_spin.setRange(1, 50)  # 增加批量大小选项
        self.lines_spin.setValue(5)     # 提高默认值
        param_layout.addWidget(self.lines_spin)
        
        # 高性能模式开关
        self.turbo_mode = QCheckBox("🚀 Turbo模式")
        self.turbo_mode.setToolTip("启用批量写入和减少UI更新")
        self.turbo_mode.setChecked(True)  # 默认启用
        param_layout.addWidget(self.turbo_mode)
        
        control_layout.addLayout(param_layout, 2, 0, 1, 2)
        
        # 开始/停止测试
        self.start_button = QPushButton("3. 开始性能测试")
        self.start_button.clicked.connect(self.toggle_test)
        self.start_button.setEnabled(False)
        control_layout.addWidget(self.start_button, 3, 0)
        
        self.test_status = QLabel("未开始")
        control_layout.addWidget(self.test_status, 3, 1)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 性能显示
        perf_group = QGroupBox("性能监控")
        perf_layout = QGridLayout()
        
        self.perf_labels = {}
        metrics = [
            ('elapsed_time', '运行时间(s)'),
            ('cpu_percent', 'CPU使用率(%)'),
            ('memory_percent', '系统内存(%)'),
            ('process_memory_mb', '进程内存(MB)'),
            ('data_written_mb', '已写数据(MB)'),
            ('lines_written', '已写行数'),
            ('data_rate_kbps', '数据速率(KB/s)'),
            ('line_rate_per_sec', '行速率(行/s)')
        ]
        
        for i, (key, label) in enumerate(metrics):
            perf_layout.addWidget(QLabel(label), i // 2, (i % 2) * 2)
            value_label = QLabel("0")
            value_label.setStyleSheet("font-weight: bold; color: blue;")
            self.perf_labels[key] = value_label
            perf_layout.addWidget(value_label, i // 2, (i % 2) * 2 + 1)
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        # 日志显示
        log_group = QGroupBox("测试日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
        
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"[{timestamp}] {message}")
        
        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def prepare_test_data(self):
        """准备测试数据"""
        self.log_message("开始生成测试数据...")
        
        # 显示进度条
        self.prep_progress.setVisible(True)
        self.prep_progress.setValue(0)
        self.prep_button.setEnabled(False)
        self.prep_status.setText("生成中...")
        
        # 在线程中生成数据，避免界面卡顿
        def generate_data():
            self.data_generator.generate_test_data(10000)
            
        threading.Thread(target=generate_data, daemon=True).start()
    
    def update_progress(self, progress):
        """更新进度条"""
        self.prep_progress.setValue(progress)
        self.prep_status.setText(f"生成中... {progress}%")
        
    def on_data_generated(self, data):
        """数据生成完成"""
        self.test_data_pool = data
        self.prep_progress.setVisible(False)
        self.prep_status.setText(f"已准备 {len(self.test_data_pool)} 行")
        self.fill_button.setEnabled(True)
        self.fill_fast_button.setEnabled(True)
        self.prep_button.setEnabled(True)
        self.log_message(f"测试数据生成完成，共 {len(self.test_data_pool)} 行")
    
    def diagnose_connection(self):
        """诊断当前连接状态"""
        self.log_message("=== 🔍 开始诊断连接状态 ===")
        
        if not self.main_window:
            self.log_message("❌ 未连接到主窗口")
            return
        
        self.log_message("✅ 已连接到主窗口")
        
        # 检查connection_dialog
        if hasattr(self.main_window, 'connection_dialog'):
            if self.main_window.connection_dialog:
                self.log_message("✅ 找到connection_dialog对象")
                
                # 检查worker对象
                if hasattr(self.main_window.connection_dialog, 'worker'):
                    worker = self.main_window.connection_dialog.worker
                    self.log_message("✅ 找到worker对象")
                    
                    # 检查worker的缓冲区
                    if hasattr(worker, 'buffers'):
                        buffer_count = len(worker.buffers)
                        self.log_message(f"✅ worker有 {buffer_count} 个缓冲区")
                        
                        # 检查缓冲区内容
                        total_data = sum(len(buf) for buf in worker.buffers)
                        self.log_message(f"📊 当前缓冲区总数据量: {total_data} 字符")
                        
                        # 显示各通道数据量
                        for i, buf in enumerate(worker.buffers):
                            if len(buf) > 0:
                                self.log_message(f"  通道 {i}: {len(buf)} 字符")
                    else:
                        self.log_message("❌ worker没有buffers属性")
                else:
                    self.log_message("❌ connection_dialog没有worker对象")
            else:
                self.log_message("❌ connection_dialog为None")
        else:
            self.log_message("❌ 主窗口没有connection_dialog属性")
        
        # 检查RTT连接状态
        if (hasattr(self.main_window, 'connection_dialog') and 
            self.main_window.connection_dialog and 
            hasattr(self.main_window.connection_dialog, 'start_state')):
            
            is_connected = self.main_window.connection_dialog.start_state
            if is_connected:
                self.log_message("✅ RTT连接状态: 已连接")
            else:
                self.log_message("⚠️ RTT连接状态: 未连接")
                self.log_message("💡 建议: 请先在连接对话框中启动RTT连接")
        
        # 检查tabs状态
        if hasattr(self.main_window, 'ui') and hasattr(self.main_window.ui, 'tem_switch'):
            tab_count = self.main_window.ui.tem_switch.count()
            current_tab = self.main_window.ui.tem_switch.currentIndex()
            self.log_message(f"📋 标签页信息: 共 {tab_count} 个，当前第 {current_tab} 个")
        
        self.log_message("=== 🔍 诊断完成 ===")
        
    def fill_all_pages(self):
        """填充所有页面"""
        if not self.main_window:
            self.log_message("错误：未连接到主窗口")
            return
            
        if not self.test_data_pool:
            self.log_message("错误：请先准备测试数据")
            return
            
        self.log_message("开始填充所有页面...")
        self.fill_button.setEnabled(False)
        self.fill_status.setText("填充中...")
        
        try:
            # worker对象在ConnectionDialog中，通过connection_dialog访问
            worker = None
            if hasattr(self.main_window, 'connection_dialog') and self.main_window.connection_dialog:
                if hasattr(self.main_window.connection_dialog, 'worker'):
                    worker = self.main_window.connection_dialog.worker
                    self.log_message("找到ConnectionDialog中的worker对象")
            
            # 如果还没找到，尝试直接在主窗口中查找
            if not worker and hasattr(self.main_window, 'worker'):
                worker = self.main_window.worker
                self.log_message("找到主窗口中的worker对象")
            
            if worker:
                # 🚀 优化：批量填充数据到所有通道 (0-15)
                self.log_message("开始高速批量填充...")
                
                for channel in range(16):
                    # 每个通道填充1000行随机数据
                    channel_data = random.sample(self.test_data_pool, min(1000, len(self.test_data_pool)))
                    
                    # 🚀 性能优化：批量合并数据，减少函数调用
                    batch_data = '\n'.join(channel_data) + '\n'
                    batch_bytes = batch_data.encode('utf-8')
                    
                    # 一次性写入整个批次
                    worker.addToBuffer(channel, batch_bytes)
                    
                    self.log_message(f"通道 {channel} 批量填充完成，{len(channel_data)} 行")
                    
                    # 🚀 优化：减少UI更新频率，每4个通道更新一次
                    if (channel + 1) % 4 == 0:
                        QApplication.processEvents()
                
                self.fill_status.setText("填充完成")
                self.start_button.setEnabled(True)
                self.log_message("所有页面填充完成")
                
            else:
                self.log_message("错误：未找到worker对象")
                self.log_message("提示：请确保已启动RTT连接")
                
        except Exception as e:
            self.log_message(f"填充过程出错：{str(e)}")
            
        finally:
            self.fill_button.setEnabled(True)
            self.fill_fast_button.setEnabled(True)
    
    def fill_all_pages_fast(self):
        """🚀 极速填充所有页面（最大性能模式）"""
        if not self.main_window:
            self.log_message("错误：未连接到主窗口")
            return
            
        if not self.test_data_pool:
            self.log_message("错误：请先准备测试数据")
            return
            
        self.log_message("开始极速填充模式...")
        self.fill_button.setEnabled(False)
        self.fill_fast_button.setEnabled(False)
        self.fill_status.setText("极速填充中...")
        
        start_time = time.time()
        
        try:
            # 获取worker对象
            worker = None
            if hasattr(self.main_window, 'connection_dialog') and self.main_window.connection_dialog:
                if hasattr(self.main_window.connection_dialog, 'worker'):
                    worker = self.main_window.connection_dialog.worker
                    self.log_message("找到worker对象，开始极速模式")
            
            if not worker and hasattr(self.main_window, 'worker'):
                worker = self.main_window.worker
            
            if worker:
                # 🚀 极速模式：直接操作buffers，绕过addToBuffer的开销
                self.log_message("🚀 启用直接缓冲区写入模式")
                
                # 暂时禁用UI更新
                if hasattr(self.main_window, 'page_dirty_flags'):
                    original_flags = self.main_window.page_dirty_flags.copy()
                
                for channel in range(16):
                    # 每个通道填充1000行随机数据
                    channel_data = random.sample(self.test_data_pool, min(1000, len(self.test_data_pool)))
                    
                    # 🚀 极速：直接写入到worker的buffers
                    if hasattr(worker, 'buffers'):
                        batch_text = '\n'.join(channel_data) + '\n'
                        
                        # 直接添加到缓冲区（跳过addToBuffer的处理开销）
                        if len(worker.buffers) > channel + 1:
                            worker.buffers[channel + 1] += batch_text
                            
                        # 同时更新ALL通道（channel 0）
                        if len(worker.buffers) > 0:
                            formatted_batch = '\n'.join([f"{channel:02d}> {line}" for line in channel_data]) + '\n'
                            worker.buffers[0] += formatted_batch
                    
                    # 极速模式：每8个通道才更新一次日志
                    if (channel + 1) % 8 == 0:
                        self.log_message(f"极速填充进度: {channel + 1}/16 通道")
                
                elapsed = time.time() - start_time
                total_lines = 16 * 1000
                lines_per_sec = total_lines / elapsed if elapsed > 0 else 0
                
                self.fill_status.setText("极速填充完成")
                self.start_button.setEnabled(True)
                self.log_message(f"🚀 极速填充完成！")
                self.log_message(f"📊 性能: {total_lines} 行 / {elapsed:.2f}秒 = {lines_per_sec:.0f} 行/秒")
                
                # 强制更新所有页面
                if hasattr(self.main_window, 'page_dirty_flags'):
                    for i in range(len(self.main_window.page_dirty_flags)):
                        self.main_window.page_dirty_flags[i] = True
                
                # 强制刷新当前显示的页面
                QApplication.processEvents()
                
            else:
                self.log_message("错误：未找到worker对象")
                
        except Exception as e:
            self.log_message(f"极速填充出错：{str(e)}")
            
        finally:
            self.fill_button.setEnabled(True)
            self.fill_fast_button.setEnabled(True)
            
    def toggle_test(self):
        """开始/停止测试"""
        if not self.test_running:
            self.start_test()
        else:
            self.stop_test()
            
    def start_test(self):
        """开始性能测试"""
        if not self.main_window or not self.test_data_pool:
            self.log_message("错误：请先准备数据并填充页面")
            return
            
        self.test_running = True
        self.start_button.setText("停止测试")
        self.test_status.setText("测试中...")
        self.current_data_index = 0
        
        # 开始性能监控
        self.perf_monitor.start_monitoring()
        
        # 设置定时器
        interval = self.interval_spin.value()
        self.test_timer.start(interval)
        
        self.log_message(f"性能测试开始，间隔：{interval}ms")
        
    def stop_test(self):
        """停止性能测试"""
        self.test_running = False
        self.test_timer.stop()
        self.perf_monitor.stop_monitoring()
        
        self.start_button.setText("3. 开始性能测试")
        self.test_status.setText("已停止")
        
        self.log_message("性能测试停止")
        
    def write_test_data(self):
        """写入测试数据（优化版本）"""
        if not self.test_running or not self.main_window:
            return
            
        try:
            # 获取worker对象
            worker = None
            if hasattr(self.main_window, 'connection_dialog') and self.main_window.connection_dialog:
                if hasattr(self.main_window.connection_dialog, 'worker'):
                    worker = self.main_window.connection_dialog.worker
            
            if not worker and hasattr(self.main_window, 'worker'):
                worker = self.main_window.worker
            
            if not worker:
                self.log_message("警告：worker对象不可用，停止测试")
                self.stop_test()
                return
                
            lines_count = self.lines_spin.value()
            
            # 随机选择写入的通道 (0-15 或者 ALL)
            channels_to_write = []
            
            # 30% 概率写入 ALL 通道，70% 概率写入随机单个通道
            if random.random() < 0.3:
                channels_to_write = list(range(16))  # 写入所有通道
            else:
                channels_to_write = [random.randint(0, 15)]  # 随机单个通道
            
            total_data_size = 0
            total_lines = 0
            
            # 🚀 Turbo模式：选择最优写入策略
            if self.turbo_mode.isChecked():
                # Turbo模式：批量写入，减少函数调用
                for channel in channels_to_write:
                    batch_lines = []
                    for _ in range(lines_count):
                        if self.current_data_index >= len(self.test_data_pool):
                            self.current_data_index = 0
                        batch_lines.append(self.test_data_pool[self.current_data_index])
                        self.current_data_index += 1
                    
                    if batch_lines:
                        batch_data = '\n'.join(batch_lines) + '\n'
                        batch_bytes = batch_data.encode('utf-8')
                        worker.addToBuffer(channel, batch_bytes)
                        
                        total_data_size += len(batch_bytes)
                        total_lines += len(batch_lines)
            else:
                # 标准模式：逐行写入，更接近真实RTT行为
                for channel in channels_to_write:
                    for _ in range(lines_count):
                        if self.current_data_index >= len(self.test_data_pool):
                            self.current_data_index = 0
                            
                        data_line = self.test_data_pool[self.current_data_index] + '\n'
                        self.current_data_index += 1
                        
                        data_bytes = data_line.encode('utf-8')
                        worker.addToBuffer(channel, data_bytes)
                        
                        total_data_size += len(data_bytes)
                        total_lines += 1
            
            # 更新性能统计
            self.perf_monitor.add_data(total_data_size, total_lines)
            
        except Exception as e:
            self.log_message(f"写入数据时出错：{str(e)}")
            self.stop_test()
            
    def update_performance_display(self, perf_data):
        """更新性能显示"""
        for key, value in perf_data.items():
            if key in self.perf_labels:
                if isinstance(value, float):
                    if key == 'elapsed_time':
                        self.perf_labels[key].setText(f"{value:.1f}")
                    elif 'rate' in key or 'percent' in key:
                        self.perf_labels[key].setText(f"{value:.2f}")
                    else:
                        self.perf_labels[key].setText(f"{value:.1f}")
                else:
                    self.perf_labels[key].setText(str(value))
        
        # 瓶颈分析和警告
        self._analyze_bottlenecks(perf_data)
    
    def _analyze_bottlenecks(self, perf_data):
        """分析性能瓶颈并给出建议"""
        warnings = []
        
        # CPU使用率检查
        if perf_data.get('cpu_percent', 0) > 80:
            warnings.append("⚠️ CPU使用率过高，可能影响性能")
        
        # 内存使用检查  
        if perf_data.get('memory_percent', 0) > 85:
            warnings.append("⚠️ 系统内存不足，可能导致卡顿")
            
        if perf_data.get('process_memory_mb', 0) > 500:
            warnings.append("⚠️ 进程内存占用过高，建议重启程序")
        
        # 🚀 更新的数据处理速率检查（适应优化后的性能）
        line_rate = perf_data.get('line_rate_per_sec', 0)
        if line_rate > 1000:
            warnings.append("🚀 数据处理速度超强")
        elif line_rate > 500:
            warnings.append("✅ 数据处理速度优秀")
        elif line_rate > 100:
            warnings.append("⚡ 数据处理速度良好")
        elif line_rate > 50:
            warnings.append("📊 数据处理速度一般")
        elif line_rate > 10:
            warnings.append("⚠️ 数据处理速度较慢")
        else:
            warnings.append("🚨 数据处理速度严重不足")
        
        # 显示最新的警告信息
        if warnings:
            latest_warning = warnings[-1]
            if hasattr(self, '_last_warning') and self._last_warning != latest_warning:
                self.log_message(latest_warning)
            self._last_warning = latest_warning


def show_performance_test(main_window=None):
    """显示性能测试窗口"""
    test_widget = PerformanceTestWidget(main_window)
    test_widget.show()
    return test_widget


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 独立运行测试
    test_widget = PerformanceTestWidget()
    test_widget.show()
    
    sys.exit(app.exec())
