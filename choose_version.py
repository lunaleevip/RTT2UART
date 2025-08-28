#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RTT2UART 版本选择器
让用户选择使用原版本还是重构版本
"""

import sys
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class VersionChooser(QDialog):
    """版本选择对话框"""
    
    def __init__(self):
        super().__init__()
        self.choice = None
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("RTT2UART - 版本选择")
        self.setWindowIcon(QIcon(":/Jlink_ICON.ico") if QIcon(":/Jlink_ICON.ico").isNull() == False else QIcon())
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        # 标题
        title = QLabel("选择 RTT2UART 版本")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 20px;")
        layout.addWidget(title)
        
        # 版本卡片容器
        cards_layout = QHBoxLayout()
        
        # 原版本卡片
        original_card = self.create_version_card(
            "原版本",
            "保持原有的窗口结构和体验",
            [
                "✓ 熟悉的界面布局",
                "✓ 原有的功能特性", 
                "✓ 已优化的性能",
                "⚠ 加载体验一般"
            ],
            "#4CAF50",
            "original"
        )
        
        # 重构版本卡片
        new_card = self.create_version_card(
            "重构版本",
            "全新的用户体验和界面设计",
            [
                "✨ 优雅的连接对话框",
                "✨ 统一的主窗口界面",
                "✨ 完整的菜单和状态栏",
                "✨ 更佳的用户体验"
            ],
            "#2196F3",
            "new"
        )
        
        cards_layout.addWidget(original_card)
        cards_layout.addWidget(new_card)
        layout.addLayout(cards_layout)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 应用样式
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 4px;
                border: 1px solid #ddd;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
        """)
    
    def create_version_card(self, title, description, features, color, choice_key):
        """创建版本卡片"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {color};
                border-radius: 10px;
                background-color: white;
                margin: 10px;
            }}
            QFrame:hover {{
                background-color: {color}15;
            }}
        """)
        card.setFixedSize(220, 260)
        
        layout = QVBoxLayout()
        
        # 标题
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"""
            font-size: 16px; 
            font-weight: bold; 
            color: {color}; 
            margin: 10px;
        """)
        layout.addWidget(title_label)
        
        # 描述
        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(desc_label)
        
        # 特性列表
        for feature in features:
            feature_label = QLabel(feature)
            feature_label.setStyleSheet("margin: 2px 10px; color: #333;")
            layout.addWidget(feature_label)
        
        layout.addStretch()
        
        # 选择按钮
        choose_btn = QPushButton("选择此版本")
        choose_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                margin: 10px;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """)
        choose_btn.clicked.connect(lambda: self.choose_version(choice_key))
        layout.addWidget(choose_btn)
        
        card.setLayout(layout)
        return card
    
    def choose_version(self, choice):
        """选择版本"""
        self.choice = choice
        self.accept()
    
    def get_choice(self):
        """获取选择结果"""
        return self.choice

def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 显示选择对话框
    chooser = VersionChooser()
    if chooser.exec() != QDialog.Accepted:
        return 0
    
    choice = chooser.get_choice()
    if not choice:
        return 0
    
    try:
        if choice == "original":
            print("🔄 启动原版本...")
            import main_window
            from main_window import MainWindow
            
            # 创建主窗口
            main_win = MainWindow()
            main_win.show()
            
        elif choice == "new":
            print("🚀 启动重构版本...")
            from new_main_window import RTTMainWindow
            
            # 创建重构版主窗口
            main_win = RTTMainWindow()
            main_win.show()
        
        return app.exec()
        
    except Exception as e:
        print(f"💥 启动失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 显示错误对话框
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("启动失败")
        msg.setText(f"程序启动失败: {e}")
        msg.setDetailedText(traceback.format_exc())
        msg.exec()
        
        return 1

if __name__ == "__main__":
    sys.exit(main())

