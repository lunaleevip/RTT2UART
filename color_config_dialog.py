#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
颜色配置对话框
用于配置ALL标签页中不同通道的前景色和背景色
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QColorDialog, QGroupBox, QScrollArea,
    QWidget, QDialogButtonBox
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from config_manager import ConfigManager


class ColorConfigDialog(QDialog):
    """颜色配置对话框"""
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        """
        初始化颜色配置对话框
        
        Args:
            config_manager: 配置管理器实例
            parent: 父窗口
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("标签页颜色配置")
        self.resize(600, 500)
        
        # 存储颜色的临时变量
        self.colors = {}
        
        # 初始化UI
        self._init_ui()
        
        # 加载当前配置的颜色
        self._load_colors()
    
    def _init_ui(self):
        """初始化用户界面"""
        main_layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        
        # 创建网格布局用于放置颜色配置项
        self.color_grid = QGridLayout(scroll_content)
        
        # 为每个通道创建颜色配置项
        for i in range(16):
            group_box = QGroupBox(f"通道 {i}")
            group_layout = QGridLayout(group_box)
            
            # 前景色配置
            fg_label = QLabel("前景色:")
            fg_color_label = QLabel()
            fg_color_label.setFixedSize(40, 25)
            fg_color_label.setStyleSheet("border: 1px solid #CCCCCC;")
            fg_button = QPushButton("选择")
            fg_button.clicked.connect(lambda checked, idx=i, is_fg=True: self._select_color(idx, is_fg))
            
            # 背景色配置
            bg_label = QLabel("背景色:")
            bg_color_label = QLabel()
            bg_color_label.setFixedSize(40, 25)
            bg_color_label.setStyleSheet("border: 1px solid #CCCCCC;")
            bg_button = QPushButton("选择")
            bg_button.clicked.connect(lambda checked, idx=i, is_fg=False: self._select_color(idx, is_fg))
            
            # 添加到布局
            group_layout.addWidget(fg_label, 0, 0)
            group_layout.addWidget(fg_color_label, 0, 1)
            group_layout.addWidget(fg_button, 0, 2)
            group_layout.addWidget(bg_label, 1, 0)
            group_layout.addWidget(bg_color_label, 1, 1)
            group_layout.addWidget(bg_button, 1, 2)
            
            # 存储引用以便后续更新
            self.colors[i] = {
                'fg_label': fg_label,
                'fg_color_label': fg_color_label,
                'bg_label': bg_label,
                'bg_color_label': bg_color_label
            }
            
            # 添加到网格布局
            row = i // 2
            col = i % 2
            self.color_grid.addWidget(group_box, row, col)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # 添加按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def _load_colors(self):
        """从配置加载当前颜色设置"""
        for i in range(16):
            # 获取前景色
            fg_color_hex = self.config_manager.get_tab_foreground_color(i)
            fg_color = QColor(f"#{fg_color_hex}")
            self.colors[i]['fg_color_label'].setStyleSheet(
                f"background-color: #{fg_color_hex}; border: 1px solid #CCCCCC;"
            )
            self.colors[i]['fg_color'] = fg_color
            
            # 获取背景色
            bg_color_hex = self.config_manager.get_tab_background_color(i)
            bg_color = QColor(f"#{bg_color_hex}")
            self.colors[i]['bg_color_label'].setStyleSheet(
                f"background-color: #{bg_color_hex}; border: 1px solid #CCCCCC;"
            )
            self.colors[i]['bg_color'] = bg_color
    
    def _select_color(self, index: int, is_foreground: bool):
        """打开颜色选择对话框选择颜色
        
        Args:
            index: 通道索引
            is_foreground: 是否是前景色
        """
        # 获取当前颜色作为默认值
        if is_foreground:
            current_color = self.colors[index].get('fg_color', QColor("#FFFFFF"))
        else:
            current_color = self.colors[index].get('bg_color', QColor("#000000"))
        
        # 打开颜色对话框
        color = QColorDialog.getColor(
            current_color,
            self,
            f"选择通道 {index} 的{'前景色' if is_foreground else '背景色'}"
        )
        
        if color.isValid():
            # 更新UI显示
            color_hex = color.name().replace('#', '').upper()
            if is_foreground:
                self.colors[index]['fg_color_label'].setStyleSheet(
                    f"background-color: #{color_hex}; border: 1px solid #CCCCCC;"
                )
                self.colors[index]['fg_color'] = color
            else:
                self.colors[index]['bg_color_label'].setStyleSheet(
                    f"background-color: #{color_hex}; border: 1px solid #CCCCCC;"
                )
                self.colors[index]['bg_color'] = color
    
    def accept(self):
        """接受对话框，保存颜色配置"""
        for i in range(16):
            # 保存前景色
            fg_color = self.colors[i].get('fg_color', QColor("#FFFFFF"))
            fg_color_hex = fg_color.name().replace('#', '').upper()
            self.config_manager.set_tab_foreground_color(i, fg_color_hex)
            
            # 保存背景色
            bg_color = self.colors[i].get('bg_color', QColor("#000000"))
            bg_color_hex = bg_color.name().replace('#', '').upper()
            self.config_manager.set_tab_background_color(i, bg_color_hex)
        
        # 保存配置到文件
        self.config_manager.save_config(force=True)
        
        # 调用父类的accept方法关闭对话框
        super().accept()


if __name__ == "__main__":
    # 简单测试代码
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    config_manager = ConfigManager()
    dialog = ColorConfigDialog(config_manager)
    dialog.show()
    sys.exit(app.exec())
