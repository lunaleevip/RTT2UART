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
    
    def __init__(self, parent=None, tab_index: int = -1, config_manager=None, disable_content_limit=False):
        super().__init__(parent)
        
        # 标签页索引和配置管理器
        self.tab_index = tab_index  # -1表示普通标签页，0表示ALL标签页，1-15表示通道标签页
        self.config_manager = config_manager
        
        # 是否禁用内容限制（用于回放窗口）
        self.disable_content_limit = disable_content_limit
        
        # 行数上限：始终保留最后N行（由配置控制）
        if (not self.disable_content_limit) and self.config_manager:
            try:
                max_lines = int(self.config_manager.get_max_log_size())
                if max_lines > 0:
                    self.document().setMaximumBlockCount(max_lines)
                    logger.info(f"[UI] MaximumBlockCount set to {max_lines} lines")
            except Exception as e:
                logger.debug(f"[UI] Failed to set MaximumBlockCount: {e}")
        
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
        
        # 不再需要通道前缀正则表达式，由Worker类处理
        
        # 初始化ANSI处理器
        self._init_ansi_processor()
        
    def update_config_manager(self, config_manager):
        """更新配置管理器引用"""
        self.config_manager = config_manager
        
    def update_tab_index(self, tab_index: int):
        """更新标签页索引"""
        self.tab_index = tab_index
        
    def _init_ansi_processor(self):
        """初始化ANSI处理器 - 支持颜色代码处理"""
        # 预编译正则表达式 - 用于ANSI颜色代码检测和提取
        self._ansi_regex = re.compile(r'\x1B\[[0-9;]*[mJ]')
        self._ansi_color_regex = re.compile(r'\x1B\[([0-9;]*)m')
        
        # 初始化颜色和格式缓存
        self._color_cache = {}
        self._format_cache = {}
        
    def _get_cached_format(self, fg_color=None, bg_color=None, bold=False):
        """获取缓存的文本格式对象

        Args:
            fg_color: 前景色 (QColor)
            bg_color: 背景色 (QColor)
            bold: 是否粗体

        Returns:
            QTextCharFormat对象
        """
        # 创建缓存键 - 使用可哈希的值
        fg_key = (fg_color.red(), fg_color.green(), fg_color.blue()) if fg_color else None
        bg_key = (bg_color.red(), bg_color.green(), bg_color.blue()) if bg_color else None
        key = (fg_key, bg_key, bold)

        # 检查缓存
        if key in self._format_cache:
            return self._format_cache[key]

        # 创建新的格式对象
        format_obj = QTextCharFormat()

        # 设置前景色
        if fg_color:
            format_obj.setForeground(fg_color)

        # 设置背景色
        if bg_color:
            format_obj.setBackground(bg_color)

        # 设置粗体
        if bold:
            format_obj.setFontWeight(QFont.Bold)

        # 缓存格式对象
        self._format_cache[key] = format_obj

        return format_obj
        
    def _parse_ansi_fast(self, text):
        """解析ANSI颜色代码

        Args:
            text: 包含ANSI颜色代码的文本

        Returns:
            分段文本列表，每个元素包含文本和对应的格式
        """
        segments = []

        # 检查是否包含清屏命令
        if '\x1B[2J' in text:
            # 只在 TAB 1-TAB16 执行清屏操作
            if 1 <= self.tab_index <= 16:
                self.clear_content()
            # 移除清屏命令
            text = text.replace('\x1B[2J', '')

        # 如果不包含任何ANSI代码，直接返回文本
        if '\x1B[' not in text:
            if text:
                segments.append({
                    'text': text,
                    'format': None
                })
            return segments

        # 当前格式状态
        current_fg = None
        current_bg = None
        current_bold = False

        # 遍历ANSI颜色代码
        last_end = 0
        for match in self._ansi_color_regex.finditer(text):
            start, end = match.span()

            # 获取匹配的代码部分
            code_str = match.group(1)

            # 提取代码前的普通文本
            if start > last_end:
                plain_text = text[last_end:start]
                if plain_text:
                    format_obj = self._get_cached_format(current_fg, current_bg, current_bold)
                    segments.append({
                        'text': plain_text,
                        'format': format_obj
                    })

            # 处理ANSI代码
            codes = code_str.split(';')
            i = 0
            while i < len(codes):
                code = codes[i]
                if not code:
                    i += 1
                    continue

                try:
                    code_num = int(code)

                    # 重置所有属性
                    if code_num == 0:
                        current_fg = None
                        current_bg = None
                        current_bold = False
                    # 粗体
                    elif code_num == 1:
                        current_bold = True
                    # 前景色设置 - 标准颜色代码 (30-37)
                    elif 30 <= code_num <= 37:
                        # 标准颜色映射
                        color_map = {
                            30: QColor(0, 0, 0),      # 黑色
                            31: QColor(255, 0, 0),    # 红色
                            32: QColor(0, 255, 0),    # 绿色
                            33: QColor(255, 255, 0),  # 黄色
                            34: QColor(0, 0, 255),    # 蓝色
                            35: QColor(255, 0, 255),  # 洋红色
                            36: QColor(0, 255, 255),  # 青色
                            37: QColor(255, 255, 255) # 白色
                        }
                        current_fg = color_map[code_num]
                    # 前景色设置 - 亮颜色代码 (90-97)
                    elif 90 <= code_num <= 97:
                        # 亮颜色映射
                        color_map = {
                            90: QColor(128, 128, 128),    # 亮黑色
                            91: QColor(255, 100, 100),    # 亮红色
                            92: QColor(100, 255, 100),    # 亮绿色
                            93: QColor(255, 255, 100),    # 亮黄色
                            94: QColor(100, 100, 255),    # 亮蓝色
                            95: QColor(255, 100, 255),    # 亮洋红色
                            96: QColor(100, 255, 255),    # 亮青色
                            97: QColor(255, 255, 255)     # 亮白色
                        }
                        current_fg = color_map[code_num]
                    # 前景色设置 - 24位真彩色 (38;2;R;G;B)
                    elif code_num == 38 and i + 4 < len(codes) and codes[i+1] == '2':
                        try:
                            r = int(codes[i+2])
                            g = int(codes[i+3])
                            b = int(codes[i+4])
                            current_fg = QColor(r, g, b)
                            # 跳过已处理的代码
                            i += 4
                        except (ValueError, IndexError):
                            pass
                    # 背景色设置 - 标准颜色代码 (40-47)
                    elif 40 <= code_num <= 47:
                        # 标准背景色映射
                        color_map = {
                            40: QColor(0, 0, 0),      # 黑色背景
                            41: QColor(255, 0, 0),    # 红色背景
                            42: QColor(0, 255, 0),    # 绿色背景
                            43: QColor(255, 255, 0),  # 黄色背景
                            44: QColor(0, 0, 255),    # 蓝色背景
                            45: QColor(255, 0, 255),  # 洋红色背景
                            46: QColor(0, 255, 255),  # 青色背景
                            47: QColor(255, 255, 255) # 白色背景
                        }
                        current_bg = color_map[code_num]
                    # 背景色设置 - 亮颜色代码 (100-107)
                    elif 100 <= code_num <= 107:
                        # 亮背景色映射
                        color_map = {
                            100: QColor(128, 128, 128),    # 亮黑色背景
                            101: QColor(255, 100, 100),    # 亮红色背景
                            102: QColor(100, 255, 100),    # 亮绿色背景
                            103: QColor(255, 255, 100),    # 亮黄色背景
                            104: QColor(100, 100, 255),    # 亮蓝色背景
                            105: QColor(255, 100, 255),    # 亮洋红色背景
                            106: QColor(100, 255, 255),    # 亮青色背景
                            107: QColor(255, 255, 255)     # 亮白色背景
                        }
                        current_bg = color_map[code_num]
                    # 背景色设置 - 24位真彩色 (48;2;R;G;B)
                    elif code_num == 48 and i + 4 < len(codes) and codes[i+1] == '2':
                        try:
                            r = int(codes[i+2])
                            g = int(codes[i+3])
                            b = int(codes[i+4])
                            current_bg = QColor(r, g, b)
                            # 跳过已处理的代码
                            i += 4
                        except (ValueError, IndexError):
                            pass
                except ValueError:
                    pass
                
                i += 1

            last_end = end

        # 添加最后一段文本
        if last_end < len(text):
            remaining_text = text[last_end:]
            if remaining_text:
                format_obj = self._get_cached_format(current_fg, current_bg, current_bold)
                segments.append({
                    'text': remaining_text,
                    'format': format_obj
                })

        return segments
        
    def _extract_channel_index(self, text: str) -> int:
        """已废弃的通道索引提取方法
        
        所有通道处理逻辑已移至Worker类
        """
        return 0  # 返回默认通道
        
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
        """批量处理待处理的文本 - 支持ANSI颜色代码"""
        if not self._pending_texts:
            return
            
        start_time = time.time()
        
        # 合并所有待处理文本
        combined_text = ''.join(self._pending_texts)
        self._pending_texts.clear()
        
        # 解析ANSI颜色代码并应用格式
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.beginEditBlock()
        
        # 无ANSI快速路径
        if '\x1B[' not in combined_text:
            cursor.setCharFormat(QTextCharFormat())
            cursor.insertText(combined_text)
        else:
            # 解析ANSI颜色代码
            segments = self._parse_ansi_fast(combined_text)
            
            # 应用每个分段的格式和文本（减少重复setCharFormat）
            last_format = None
            for segment in segments:
                text = segment['text']
                format_obj = segment['format']
                
                if format_obj is not None:
                    if format_obj is not last_format:
                        cursor.setCharFormat(format_obj)
                        last_format = format_obj
                else:
                    if last_format is not None:
                        cursor.setCharFormat(QTextCharFormat())
                        last_format = None
                
                # 插入文本
                cursor.insertText(text)
        
        cursor.endEditBlock()
                
        self.setTextCursor(cursor)
        
        # 达到MAXLINE时清理前1/3行（仅UI；若锁定则延后）
        self._maybe_trim_max_lines()
        
        # 性能监控
        elapsed = (time.time() - start_time) * 1000
        self._update_count += 1
        
        if elapsed > 20:  # 超过20ms记录警告
            now_ts = time.time()
            last_ts = getattr(self, '_ansi_warn_last_ts', 0.0)
            if (now_ts - last_ts) > 2.0:
                print(f"[ANSI] 批处理耗时: {elapsed:.1f}ms, 数据量: {len(combined_text)}字节")
                self._ansi_warn_last_ts = now_ts
        
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
        # 对于回放窗口，只有在明确调用时才清空内容
        # 但不阻止显式的清空操作
        self.clear()
        # 清理MAXLINE状态，避免清空后立即触发裁剪循环
        try:
            self._pending_maxline_trim = False
            self._last_maxline_trim_ts = 0.0
        except Exception:
            pass
        # 清理部分缓存以释放内存
        # if len(self._format_cache) > 100:
        #     self._format_cache.clear()

    def _maybe_trim_max_lines(self):
        """达到MAXLINE时清理前1/3行（锁定时延后）"""
        try:
            doc = self.document()
            max_blocks = int(doc.maximumBlockCount()) if doc else 0
            if max_blocks <= 0:
                return
            if doc.blockCount() < max_blocks:
                return
            # 冷却：避免连续触发导致卡顿
            now_ts = time.time()
            last_ts = float(getattr(self, '_last_maxline_trim_ts', 0.0) or 0.0)
            if (now_ts - last_ts) < 2.0:
                return
            if bool(getattr(self, '_v_scroll_locked', False)):
                self._pending_maxline_trim = True
                try:
                    logger.warning(f"[MAXLINE] Defer trim while scroll locked (blocks={doc.blockCount()}, max={max_blocks})")
                except Exception:
                    pass
                return
            self._trim_max_lines_ui(max_blocks)
        except Exception:
            pass

    def _trim_max_lines_ui(self, max_blocks: int):
        """实际执行清理（仅UI）"""
        try:
            lines_to_remove = max(1, int(max_blocks) // 3)
            trim_cursor = self.textCursor()
            trim_cursor.beginEditBlock()
            trim_cursor.movePosition(QTextCursor.Start)
            for _ in range(lines_to_remove):
                trim_cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor)
            trim_cursor.removeSelectedText()
            trim_cursor.endEditBlock()
            self._pending_maxline_trim = False
            self._last_maxline_trim_ts = time.time()
            try:
                logger.warning(f"[MAXLINE] Trimmed top {lines_to_remove} lines (max={max_blocks})")
            except Exception:
                pass
        except Exception:
            pass

    def apply_pending_maxline_trim(self):
        """解除锁定后执行延后的MAXLINE清理"""
        try:
            if not getattr(self, '_pending_maxline_trim', False):
                return
            if bool(getattr(self, '_v_scroll_locked', False)):
                return
            doc = self.document()
            max_blocks = int(doc.maximumBlockCount()) if doc else 0
            if max_blocks <= 0:
                return
            self._trim_max_lines_ui(max_blocks)
        except Exception:
            pass
    
    def append_text(self, text):
        """添加文本的安全方法，支持禁用内容限制"""
        # 获取当前文档
        doc = self.document()
        
        # 保存滚动位置
        v_scrollbar = self.verticalScrollBar()
        at_bottom = (v_scrollbar.value() >= v_scrollbar.maximum() - 2)
        
        # 插入文本到末尾
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        
        # 恢复滚动位置
        if at_bottom:
            self.moveCursor(QTextCursor.End)
        
        # 对于回放窗口，不进行内容限制检查
        # 只有非回放窗口才需要检查行数限制
        if not self.disable_content_limit and self.config_manager:
            # 如果文档已设置最大行数，由 Qt 自动裁剪
            if doc.maximumBlockCount() <= 0:
                # 获取最大日志行数限制
                max_lines = self.config_manager.get_max_log_size()
                if max_lines > 0:
                    # 检查当前行数
                    block = doc.firstBlock()
                    line_count = 0
                    while block.isValid():
                        line_count += block.lineCount()
                        block = block.next()
                    
                    # 如果超过限制，只保留最后max_lines行
                    if line_count > max_lines:
                        # 计算需要删除的行数
                        lines_to_remove = line_count - max_lines
                        
                        # 删除多余的行
                        cursor = self.textCursor()
                        cursor.movePosition(QTextCursor.Start)
                        
                        # 移动到需要保留的第一行
                        current_line = 0
                        block = doc.firstBlock()
                        while block.isValid() and current_line < lines_to_remove:
                            current_line += block.lineCount()
                            if current_line < lines_to_remove:
                                block = block.next()
                            else:
                                break
                        
                        if block.isValid():
                            # 从文档开始选择到要保留的第一行
                            cursor.setPosition(block.position())
                            cursor.movePosition(QTextCursor.Start, QTextCursor.KeepAnchor)
                            cursor.removeSelectedText()
    
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
