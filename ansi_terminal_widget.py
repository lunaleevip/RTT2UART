#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能ANSI终端显示组件
支持高效的彩色文本渲染，专门优化大量数据流的显示性能
"""

import re
import time
from collections import deque
from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from PySide6.QtCore import QTimer, Signal, QThread, QObject
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont


class FastAnsiTextEdit(QTextEdit):
    """
    高性能ANSI文本编辑器
    - 批量处理ANSI序列
    - 缓存格式化对象
    - 优化文本插入性能
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 性能优化设置
        self.setUndoRedoEnabled(False)
        self.document().setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setReadOnly(True)
        
        # 🎯 最大化显示设置
        from PySide6.QtWidgets import QSizePolicy
        from PySide6.QtCore import Qt
        
        # 设置大小策略为扩展，确保充分利用可用空间
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置滚动条策略 - 根据需要显示
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置最小大小，确保组件可见
        self.setMinimumSize(100, 100)
        
        # ANSI颜色映射缓存
        self._color_cache = {}
        self._format_cache = {}
        
        # 批处理缓冲区
        self._pending_texts = deque()
        self._batch_timer = QTimer()
        self._batch_timer.timeout.connect(self._flush_batch)
        self._batch_timer.setSingleShot(True)
        
        # 性能监控
        self._last_update_time = 0
        self._update_count = 0
        
        # 初始化ANSI处理器
        self._init_ansi_processor()
        
    def _init_ansi_processor(self):
        """初始化ANSI处理器"""
        # 简化的ANSI颜色映射 - 只处理常用颜色以提升性能
        self._ansi_colors = {
            # 前景色
            30: QColor(0, 0, 0),        # 黑
            31: QColor(205, 0, 0),      # 红
            32: QColor(0, 205, 0),      # 绿  
            33: QColor(205, 205, 0),    # 黄
            34: QColor(0, 0, 238),      # 蓝
            35: QColor(205, 0, 205),    # 洋红
            36: QColor(0, 205, 205),    # 青
            37: QColor(229, 229, 229),  # 白
            
            # 亮色 (90-97)
            90: QColor(127, 127, 127),  # 亮黑
            91: QColor(255, 0, 0),      # 亮红
            92: QColor(0, 255, 0),      # 亮绿
            93: QColor(255, 255, 0),    # 亮黄
            94: QColor(92, 92, 255),    # 亮蓝
            95: QColor(255, 0, 255),    # 亮洋红
            96: QColor(0, 255, 255),    # 亮青
            97: QColor(255, 255, 255),  # 亮白
        }
        
        # 背景色映射
        self._ansi_bg_colors = {
            40: QColor(0, 0, 0),        # 黑色背景
            41: QColor(205, 0, 0),      # 红色背景
            42: QColor(0, 205, 0),      # 绿色背景
            43: QColor(205, 205, 0),    # 黄色背景
            44: QColor(0, 0, 238),      # 蓝色背景
            45: QColor(205, 0, 205),    # 洋红背景
            46: QColor(0, 205, 205),    # 青色背景
            47: QColor(229, 229, 229),  # 白色背景
        }
        
        # 预编译正则表达式
        self._ansi_regex = re.compile(r'\x1B\[[0-9;]*m')
        
    def _get_cached_format(self, fg_color=None, bg_color=None, bold=False):
        """获取缓存的文本格式"""
        # 🔧 修复QColor hashable问题：将QColor转换为字符串作为键
        fg_key = fg_color.name() if fg_color else None
        bg_key = bg_color.name() if bg_color else None
        key = (fg_key, bg_key, bold)
        
        if key not in self._format_cache:
            fmt = QTextCharFormat()
            
            if fg_color:
                fmt.setForeground(fg_color)
            if bg_color:
                fmt.setBackground(bg_color)
            if bold:
                fmt.setFontWeight(QFont.Bold)
                
            # 设置等宽字体
            font = QFont("Consolas", 9)
            font.setFixedPitch(True)
            fmt.setFont(font)
            
            self._format_cache[key] = fmt
            
        return self._format_cache[key]
        
    def _parse_ansi_fast(self, text):
        """快速解析ANSI序列"""
        segments = []
        current_fg = None
        current_bg = None
        current_bold = False
        
        # 使用正则分割文本和ANSI序列
        parts = self._ansi_regex.split(text)
        ansi_codes = self._ansi_regex.findall(text)
        
        for i, part in enumerate(parts):
            if part:  # 非空文本
                segments.append({
                    'text': part,
                    'format': self._get_cached_format(current_fg, current_bg, current_bold)
                })
            
            # 处理ANSI序列
            if i < len(ansi_codes):
                code = ansi_codes[i]
                # 解析数字序列
                numbers = []
                try:
                    num_str = code[2:-1]  # 去掉\x1B[和m
                    if num_str:
                        numbers = [int(x) for x in num_str.split(';') if x.isdigit()]
                    else:
                        numbers = [0]  # 默认重置
                except:
                    continue
                    
                for num in numbers:
                    if num == 0:  # 重置
                        current_fg = None
                        current_bg = None
                        current_bold = False
                    elif num == 1:  # 加粗
                        current_bold = True
                    elif num == 22:  # 取消加粗
                        current_bold = False
                    elif 30 <= num <= 37:  # 前景色
                        current_fg = self._ansi_colors.get(num)
                    elif 40 <= num <= 47:  # 背景色
                        current_bg = self._ansi_bg_colors.get(num)
                    elif 90 <= num <= 97:  # 亮前景色
                        current_fg = self._ansi_colors.get(num)
                        
        return segments
        
    def append_ansi_text(self, text, force_flush=False):
        """添加ANSI文本 - 支持批处理"""
        self._pending_texts.append(text)
        
        if force_flush or len(self._pending_texts) > 10:
            self._flush_batch()
        else:
            # 延迟批处理，减少UI更新频率
            self._batch_timer.start(16)  # ~60fps
            
    def _flush_batch(self):
        """批量处理待处理的文本"""
        if not self._pending_texts:
            return
            
        start_time = time.time()
        
        # 合并所有待处理文本
        combined_text = ''.join(self._pending_texts)
        self._pending_texts.clear()
        
        # 快速解析ANSI
        segments = self._parse_ansi_fast(combined_text)
        
        # 批量插入文本
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        for segment in segments:
            if segment['text']:
                cursor.insertText(segment['text'], segment['format'])
                
        self.setTextCursor(cursor)
        
        # 性能监控
        elapsed = (time.time() - start_time) * 1000
        self._update_count += 1
        
        if elapsed > 20:  # 超过20ms记录警告
            print(f"[ANSI] 批处理耗时: {elapsed:.1f}ms, 数据量: {len(combined_text)}字节")
            
    def clear_content(self):
        """清空内容 - 同时清理缓存"""
        self.clear()
        # 清理部分缓存以释放内存
        if len(self._format_cache) > 100:
            self._format_cache.clear()


class OptimizedTerminalWidget(QWidget):
    """
    优化的终端组件
    - 支持多标签页
    - 自动滚动锁定
    - 性能监控
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 创建高性能文本编辑器
        self.text_edit = FastAnsiTextEdit()
        
        # 🎯 确保终端组件在TAB中最大化显示
        self.layout.addWidget(self.text_edit, 1)  # stretch=1，完全填充可用空间
        
        # 设置窗口大小策略，确保能够扩展填充
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 滚动控制
        self._scroll_locked = False
        self._auto_scroll = True
        
    def horizontalScrollBar(self):
        """访问内部文本编辑器的水平滚动条"""
        return self.text_edit.horizontalScrollBar()
        
    def verticalScrollBar(self):
        """访问内部文本编辑器的垂直滚动条"""
        return self.text_edit.verticalScrollBar()
        
    def textCursor(self):
        """访问内部文本编辑器的文本光标"""
        return self.text_edit.textCursor()
        
    def setTextCursor(self, cursor):
        """设置内部文本编辑器的文本光标"""
        return self.text_edit.setTextCursor(cursor)
        
    def setCursorWidth(self, width):
        """设置内部文本编辑器的光标宽度"""
        return self.text_edit.setCursorWidth(width)
        
    def setFont(self, font):
        """设置内部文本编辑器的字体"""
        return self.text_edit.setFont(font)
        
    def font(self):
        """获取内部文本编辑器的字体"""
        return self.text_edit.font()
        
    def insertPlainText(self, text):
        """向内部文本编辑器插入纯文本（兼容性方法）"""
        return self.text_edit.insertPlainText(text)
        
    def append_text(self, text, auto_scroll=True):
        """添加文本并控制滚动"""
        self.text_edit.append_ansi_text(text)
        
        if auto_scroll and not self._scroll_locked:
            # 自动滚动到底部
            scrollbar = self.text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
    def set_scroll_lock(self, locked):
        """设置滚动锁定"""
        self._scroll_locked = locked
        
    def clear_content(self):
        """清空内容"""
        self.text_edit.clear_content()


# 使用示例和测试代码
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QHBoxLayout
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("高性能ANSI终端测试")
            self.setGeometry(100, 100, 800, 600)
            
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            layout = QVBoxLayout(central_widget)
            
            # 添加终端组件
            self.terminal = OptimizedTerminalWidget()
            layout.addWidget(self.terminal)
            
            # 添加测试按钮
            button_layout = QHBoxLayout()
            
            test_btn = QPushButton("测试ANSI颜色")
            test_btn.clicked.connect(self.test_ansi)
            button_layout.addWidget(test_btn)
            
            stress_btn = QPushButton("压力测试")
            stress_btn.clicked.connect(self.stress_test)
            button_layout.addWidget(stress_btn)
            
            clear_btn = QPushButton("清空")
            clear_btn.clicked.connect(self.terminal.clear_content)
            button_layout.addWidget(clear_btn)
            
            layout.addLayout(button_layout)
            
        def test_ansi(self):
            """测试ANSI颜色显示"""
            test_texts = [
                "\x1B[31m红色文本\x1B[0m\n",
                "\x1B[32m绿色文本\x1B[0m\n",
                "\x1B[1;34m加粗蓝色\x1B[0m\n",
                "\x1B[43;30m黄底黑字\x1B[0m\n",
                "\x1B[91m亮红色\x1B[0m\n",
                "普通文本\n"
            ]
            
            for text in test_texts:
                self.terminal.append_text(text)
                
        def stress_test(self):
            """压力测试"""
            import random
            colors = [31, 32, 33, 34, 35, 36, 37, 91, 92, 93, 94, 95, 96, 97]
            
            for i in range(100):
                color = random.choice(colors)
                text = f"\x1B[{color}m测试行 {i+1}: 这是一行带颜色的测试文本\x1B[0m\n"
                self.terminal.append_text(text)
    
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
