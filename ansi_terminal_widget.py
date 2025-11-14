#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高性能ANSI终端显示组件
支持高效的彩色文本渲染，专门优化大量数据流的显示性能
"""

import re
import time
import logging
from collections import deque

# 获取logger实例
logger = logging.getLogger(__name__)
from PySide6.QtWidgets import QTextEdit, QWidget, QVBoxLayout
from PySide6.QtCore import QTimer, Signal, QThread, QObject
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QKeySequence


class FastAnsiTextEdit(QTextEdit):
    """
    高性能ANSI文本编辑器
    - 批量处理ANSI序列
    - 缓存格式化对象
    - 优化文本插入性能
    - 支持ALT键纵向选择
    - 支持通道特定颜色显示（在ALL标签页中）
    """
    
    def __init__(self, parent=None, tab_index: int = -1, config_manager=None):
        super().__init__(parent)
        
        # 标签页索引和配置管理器
        self.tab_index = tab_index  # -1表示普通标签页，0表示ALL标签页，1-15表示通道标签页
        self.config_manager = config_manager
        
        # 性能优化设置
        self.setUndoRedoEnabled(False)
        self.document().setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.WidgetWidth)  # 根据窗口宽度自动换行
        self.setReadOnly(True)
        
        # 启用文本选择功能（包括ALT块选取）
        from PySide6.QtCore import Qt
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        
        # ALT纵向选择支持
        self.column_select_mode = False
        self.column_select_start = None
        self.column_select_cursor_start = None
        self.column_select_ranges = None  # 保存选择范围(起始行列，结束行列)
        
        # 🎯 最大化显示设置
        from PySide6.QtWidgets import QSizePolicy
        from PySide6.QtCore import Qt
        
        # 设置大小策略为扩展，确保充分利用可用空间
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 设置滚动条策略 - 始终显示
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
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
        
        # 初始化通道前缀正则表达式
        import re
        # 匹配常见的通道前缀格式：[CH0], CH1:, [0], 0:, [Channel 2], etc.
        # 增强版正则，支持更多格式包括日志格式如 "[02]" 或 "02[" 等
        self._channel_prefix_regex = re.compile(r'^\[(?:CH|Channel)?(\d{1,2})\]|^(?:CH|Channel)?(\d{1,2}):|^\[(\d{1,2})\]|^(\d{1,2})\[', re.IGNORECASE)
        
        # 初始化ANSI处理器
        self._init_ansi_processor()
        
    def update_config_manager(self, config_manager):
        """更新配置管理器引用"""
        self.config_manager = config_manager
        
    def update_tab_index(self, tab_index: int):
        """更新标签页索引"""
        self.tab_index = tab_index
        
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
        
        # 背景色映射 - 统一使用明亮黄色高亮
        self._ansi_bg_colors = {
            40: QColor(0, 0, 0),        # 黑色背景
            41: QColor(205, 0, 0),      # 红色背景
            42: QColor(0, 205, 0),      # 绿色背景
            43: QColor(255, 255, 0),    # 🎨 明亮黄色背景 - 统一高亮颜色
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
        
        # 将字体信息也加入缓存键，确保不同字体生成不同的格式缓存
        # 获取当前字体信息作为键的一部分
        font = self.font()
        font_key = (font.family(), font.pointSize())
        
        key = (fg_key, bg_key, bold, font_key)
        
        if key not in self._format_cache:
            fmt = QTextCharFormat()
            
            if fg_color:
                fmt.setForeground(fg_color)
            if bg_color:
                fmt.setBackground(bg_color)
            if bold:
                fmt.setFontWeight(QFont.Bold)
                
            # 使用当前文本编辑器的字体设置
            fmt.setFont(font)
            
            self._format_cache[key] = fmt
            
        return self._format_cache[key]
        
    def _parse_ansi_fast(self, text):
        """快速解析ANSI序列
        在ALL标签页中，根据通道前缀使用不同的颜色配置
        """
        segments = []
        current_fg = None
        current_bg = None
        current_bold = False
        
        # 如果是ALL标签页（索引为0）且有配置管理器，需要根据通道前缀应用不同颜色
        is_all_tab = self.tab_index == 0 and self.config_manager is not None
        # logger.info(f"[颜色调试] 当前tab_index={self.tab_index}，config_manager={self.config_manager is not None}，is_all_tab={is_all_tab}")
        
        if is_all_tab:
            # 1. 先删除所有原本的颜色标签（ANSI序列）
            text_without_ansi = self._ansi_regex.sub('', text)
            
            # 2. 按行分割文本，逐行处理
            lines = text_without_ansi.split('\n')
            for line_idx, line in enumerate(lines):
                # 去除每行末尾可能存在的\r字符，避免多余的换行
                line = line.rstrip('\r')
                # 为每行单独处理通道信息
                current_is_channel_line = False
                current_channel_fg = None
                current_channel_bg = None
                
                if line:  # 只处理非空行
                    # 3. 查找通道前缀
                    channel_idx = self._extract_channel_index(line)
                    # logger.info(f"[颜色调试] 行{line_idx}：文本='{line[:50]}...'，提取到通道索引={channel_idx}")
                    
                    # 标记是否为有效的通道行
                    current_is_channel_line = 0 <= channel_idx <= 15
                    # logger.info(f"[颜色调试] 行{line_idx}：是否为有效通道行={current_is_channel_line}")
                    
                    # 如果是有效的通道行，获取通道颜色
                    if current_is_channel_line:
                        try:
                            # 从配置获取颜色
                            fg_hex, bg_hex = self.config_manager.get_channel_color(channel_idx)
                            # logger.info(f"[颜色调试] 行{line_idx}：通道{channel_idx}的颜色配置 - 前景色={fg_hex}，背景色={bg_hex}")
                            
                            # 创建QColor对象
                            current_channel_fg = QColor(f"#{fg_hex}")
                            current_channel_bg = QColor(f"#{bg_hex}")
                            # logger.info(f"[颜色调试] 行{line_idx}：成功创建通道{channel_idx}的颜色对象")
                        except Exception as e:
                            # 配置获取失败时使用默认颜色
                            # logger.info(f"[颜色调试] 行{line_idx}：获取通道{channel_idx}颜色配置失败 - {str(e)}")
                            current_is_channel_line = False
                    
                    # 4. 给每行添加当前通道的颜色标签
                    if current_is_channel_line:
                        # 使用通道特定颜色
                        # logger.info(f"[颜色调试] 行{line_idx}：应用通道{channel_idx}的颜色")
                        segments.append({
                            'text': line,
                            'format': self._get_cached_format(current_channel_fg, current_channel_bg, False)
                        })
                    else:
                        # 使用默认颜色
                        # logger.info(f"[颜色调试] 行{line_idx}：应用默认颜色")
                        segments.append({
                            'text': line,
                            'format': self._get_cached_format(current_fg, current_bg, current_bold)
                        })
                
                # 添加换行符（除了最后一行）
                if line_idx < len(lines) - 1:
                    # 如果是通道行，确保换行符也使用通道颜色
                    if line and current_is_channel_line and current_channel_fg is not None:
                        segments.append({
                            'text': '\n',
                            'format': self._get_cached_format(current_channel_fg, current_channel_bg, False)
                        })
                    else:
                        segments.append({
                            'text': '\n',
                            'format': self._get_cached_format(current_fg, current_bg, current_bold)
                        })
        else:
            # 普通标签页，使用原始的ANSI解析逻辑
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
        
    def _extract_channel_index(self, text: str) -> int:
        """从文本中提取通道索引
        
        Args:
            text: 输入文本
        
        Returns:
            通道索引（0-15），如果未找到或超出范围则返回-1
        """
        # logger.info(f"[颜色调试] 提取通道索引：输入文本='{text[:50]}...'")
        # 1. 首先尝试匹配日志格式中的通道标识，支持多种格式
        # 如 "0x11:11:08:45:721[0x64096852]]" 或 "[8043965]" 或 "ascu_list-receive [80]"
        import re
        
        # 增强版正则表达式，支持更多格式
        # 匹配：[0xXX], [XX], [XXXXXXXX]等格式
        hex_match = re.search(r'\[(0x[0-9A-Fa-f]+)\]|\[(\d+)\]', text)
        if hex_match:
            channel_str = hex_match.group(1) or hex_match.group(2)
            try:
                if channel_str.startswith('0x'):
                    # 十六进制转换
                    channel_idx = int(channel_str, 16)
                    # 对于长十六进制数，提取第一个字节作为通道号
                    if channel_idx > 255:
                        channel_idx = (channel_idx >> 24) & 0xFF  # 提取第一个字节
                else:
                    # 十进制转换
                    channel_idx = int(channel_str)
                    # 对于长十进制数，提取高位作为通道号或直接取模16
                    if channel_idx > 1000:
                        # 尝试从长数字中提取通道信息
                        # 方法1：取第一个数字
                        first_digit = int(str(channel_idx)[0])
                        if 0 <= first_digit <= 15:
                            return first_digit
                        # 方法2：直接取模16
                        return channel_idx % 16
                
                # 检查范围并映射到0-15
                # 例如：通道80映射到0，通道81映射到1，以此类推
                if 80 <= channel_idx <= 95:
                    return channel_idx - 80
                elif 0 <= channel_idx <= 15:
                    return channel_idx
            except ValueError:
                pass
        
        # 2. 尝试原始的通道前缀匹配
        match = self._channel_prefix_regex.match(text.strip())
        if match:
            # 提取数字部分（可能在任何一个捕获组中）
            for i in range(1, 5):  # 检查所有捕获组
                channel_str = match.group(i)
                if channel_str:
                    try:
                        channel_idx = int(channel_str)
                        # 检查范围
                        if 0 <= channel_idx <= 15:
                            return channel_idx
                    except ValueError:
                        continue
        
        # 3. 新增：匹配格式如 "00>"、"07>"、"15>" 这样的通道前缀
        # 这里使用re.match确保只匹配行首
        new_prefix_match = re.match(r'^(\d{1,2})>', text.strip())
        if new_prefix_match:
            channel_str = new_prefix_match.group(1)
            try:
                channel_idx = int(channel_str)
                # 检查范围
                if 0 <= channel_idx <= 15:
                    # logger.info(f"[颜色调试] 成功匹配新格式通道前缀：{channel_str}>")
                    return channel_idx
            except ValueError:
                pass
        
        # 4. 特殊处理：检查文本是否以数字开头，后跟空格或其他分隔符
        # 例如："02 [8043965]" 这样的格式
        parts = text.strip().split()
        if parts and parts[0].isdigit():
            try:
                channel_idx = int(parts[0])
                if 0 <= channel_idx <= 15:
                    # 进一步验证：检查是否包含其他标识符
                    # 例如，确保它不是行号等
                    if len(parts[0]) <= 2 and (len(parts) > 1 and (parts[1].startswith('[') or parts[1].startswith(':'))):
                        return channel_idx
            except ValueError:
                pass
                
        return -1
        
    def append_ansi_text(self, text, force_flush=False, on_complete=None):
        """添加ANSI文本 - 支持批处理
        
        Args:
            text: 要添加的文本
            force_flush: 是否立即刷新
            on_complete: 完成后的回调函数
        """
        self._pending_texts.append(text)
        
        # 保存回调函数
        if on_complete:
            if not hasattr(self, '_pending_callbacks'):
                self._pending_callbacks = []
            self._pending_callbacks.append(on_complete)
        
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
        
        # 调用所有待处理的回调函数
        if hasattr(self, '_pending_callbacks') and self._pending_callbacks:
            for callback in self._pending_callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"[ANSI] 回调函数执行失败: {e}")
            self._pending_callbacks.clear()
            
    def clear_content(self):
        """清空内容 - 同时清理缓存"""
        self.clear()
        # 清理部分缓存以释放内存
        if len(self._format_cache) > 100:
            self._format_cache.clear()
    
    def clear_format_cache(self):
        """清除格式缓存，确保新字体设置能够应用到所有新添加的文本"""
        self._format_cache.clear()
        logger.info(f"[FONT UPDATE] Cleared format cache for text edit")
    
    # ==================== ALT纵向选择功能 ====================
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        from PySide6.QtCore import Qt
        # 🔧 修复：右键点击时，如果存在ALT选择块区，不清除选区
        if event.button() == Qt.RightButton:
            if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
                # 右键点击且有ALT选择块区，不处理，让contextMenuEvent处理
                # 不调用父类方法，避免清除选区
                event.accept()
                return
        
        # 检查是否按住ALT键
        if event.modifiers() & Qt.AltModifier:
            self.column_select_mode = True
            # 记录起始位置
            self.column_select_start = event.pos()
            cursor = self.cursorForPosition(event.pos())
            self.column_select_cursor_start = cursor
            # 清除现有选择
            cursor.clearSelection()
            self.setTextCursor(cursor)
            event.accept()
        else:
            self.column_select_mode = False
            # 🔧 清除纵向选择的高亮（但右键点击时已在上面的检查中处理）
            self._clearColumnSelection()
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.column_select_mode and self.column_select_start:
            # 执行纵向选择
            self._updateColumnSelection(event.pos())
            event.accept()
        else:
            # 普通拖动选择时清除纵向选择高亮
            if hasattr(self, '_column_selection_data') and event.buttons():
                self._clearColumnSelection()
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        from PySide6.QtCore import Qt
        # 🔧 修复：右键释放时，如果存在ALT选择块区，不清除选区
        if event.button() == Qt.RightButton:
            if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
                # 右键释放且有ALT选择块区，不处理，让contextMenuEvent处理
                # 不调用父类方法，避免清除选区
                event.accept()
                return
        
        if self.column_select_mode:
            self.column_select_mode = False
            # 保存选择信息以便复制
            self._saveColumnSelection()
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def contextMenuEvent(self, event):
        """🔧 修复：右键菜单事件 - 使用Qt默认菜单，保持ALT选择块区不被清除"""
        # 创建Qt标准上下文菜单
        menu = self.createStandardContextMenu()
        
        # 如果有ALT选择块区，修改复制动作的行为
        if hasattr(self, '_column_selection_data') and self._column_selection_data and self.column_select_ranges:
            # 找到复制动作并替换其行为
            from PySide6.QtGui import QKeySequence
            copy_shortcut = QKeySequence(QKeySequence.Copy).toString()
            for action in menu.actions():
                # 检查是否是复制动作（通过快捷键或文本）
                action_shortcut = action.shortcut().toString() if action.shortcut() else ""
                action_text = action.text().lower()
                if copy_shortcut and action_shortcut == copy_shortcut:
                    # 断开原有的连接，连接新的复制方法
                    try:
                        action.triggered.disconnect()
                    except:
                        pass  # 如果没有连接，忽略错误
                    action.triggered.connect(self._copyColumnSelection)
                    # 🔧 修复：确保复制动作是启用的
                    action.setEnabled(True)
                    break
                elif 'copy' in action_text or '复制' in action_text:
                    # 也检查文本中包含copy或复制
                    try:
                        action.triggered.disconnect()
                    except:
                        pass
                    action.triggered.connect(self._copyColumnSelection)
                    # 🔧 修复：确保复制动作是启用的
                    action.setEnabled(True)
                    break
        
        # 显示菜单
        menu.exec_(event.globalPos())
        event.accept()
    
    def keyPressEvent(self, event):
        """键盘事件 - 支持Ctrl+C复制纵向选择的文本"""
        from PySide6.QtCore import Qt
        if event.matches(QKeySequence.Copy) and self.column_select_ranges:
            self._copyColumnSelection()
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def _saveColumnSelection(self):
        """保存纵向选择的文本数据"""
        if not self.column_select_ranges:
            return
        
        start_line, start_col, end_line, end_col = self.column_select_ranges
        
        # 提取纵向选择的文本
        selected_text = []
        document = self.document()
        
        for line_num in range(start_line, end_line + 1):
            block = document.findBlockByNumber(line_num)
            if not block.isValid():
                continue
            
            block_text = block.text()
            block_length = len(block_text)
            
            # 提取本行的选中部分
            line_start_col = min(start_col, block_length)
            line_end_col = min(end_col, block_length)
            
            if line_start_col < line_end_col:
                selected_text.append(block_text[line_start_col:line_end_col])
            else:
                selected_text.append('')
        
        # 保存选择数据
        self._column_selection_data = '\n'.join(selected_text)
    
    def _copyColumnSelection(self):
        """复制纵向选择的文本到剪贴板"""
        if not hasattr(self, '_column_selection_data'):
            return
        
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = self._column_selection_data
        clipboard.setText(text)
    
    def _applyColumnHighlight(self):
        """应用纵向选择的高亮"""
        if not self.column_select_ranges:
            return
        
        start_line, start_col, end_line, end_col = self.column_select_ranges
        
        # 创建纵向选择
        extra_selections = []
        document = self.document()
        
        for line_num in range(start_line, end_line + 1):
            block = document.findBlockByNumber(line_num)
            if not block.isValid():
                continue
            
            block_text = block.text()
            block_length = len(block_text)
            
            # 计算本行的选择范围
            line_start_col = min(start_col, block_length)
            line_end_col = min(end_col, block_length)
            
            if line_start_col < line_end_col:
                # 创建选区
                selection = QTextEdit.ExtraSelection()
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + line_start_col)
                cursor.setPosition(block.position() + line_end_col, QTextCursor.KeepAnchor)
                
                # 设置选区样式
                selection.cursor = cursor
                selection.format.setBackground(self.palette().highlight())
                selection.format.setForeground(self.palette().highlightedText())
                
                extra_selections.append(selection)
        
        # 应用选区
        self.setExtraSelections(extra_selections)
    
    def _clearColumnSelection(self):
        """清除纵向选择的高亮"""
        self.column_select_ranges = None
        if hasattr(self, '_column_selection_data'):
            delattr(self, '_column_selection_data')
        self.setExtraSelections([])
    
    def paintEvent(self, event):
        """重写绘制事件以保持纵向选择高亮"""
        super().paintEvent(event)
        
        if self.column_select_ranges:
            self._applyColumnHighlight()
    
    def _updateColumnSelection(self, end_pos):
        """更新纵向选择"""
        if not self.column_select_cursor_start:
            return
        
        # 获取起始和结束光标位置
        start_cursor = self.column_select_cursor_start
        end_cursor = self.cursorForPosition(end_pos)
        
        # 获取起始和结束的行号和列号
        start_block = start_cursor.block()
        end_block = end_cursor.block()
        
        start_line = start_block.blockNumber()
        end_line = end_block.blockNumber()
        
        start_col = start_cursor.positionInBlock()
        end_col = end_cursor.positionInBlock()
        
        # 确保起始行小于结束行
        if start_line > end_line:
            start_line, end_line = end_line, start_line
            start_col, end_col = end_col, start_col
        
        # 确保起始列小于结束列
        if start_col > end_col:
            start_col, end_col = end_col, start_col
        
        # 保存选择范围用于后续重新应用
        self.column_select_ranges = (start_line, start_col, end_line, end_col)
        
        # 应用高亮
        self._applyColumnHighlight()


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
        """设置内部文本编辑器的字体，并清除格式缓存以确保新字体生效"""
        result = self.text_edit.setFont(font)
        # 清除格式缓存，确保新字体设置能够应用到所有新添加的文本
        if hasattr(self.text_edit, 'clear_format_cache'):
            self.text_edit.clear_format_cache()
        return result
        
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
