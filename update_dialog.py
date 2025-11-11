#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
更新对话框 - 集成到主程序
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import logging

from auto_updater import AutoUpdater

logger = logging.getLogger(__name__)


class UpdateThread(QThread):
    """更新下载线程"""
    
    progress = Signal(int, int, str)  # current, total, status
    finished = Signal(bool)  # success
    error = Signal(str)  # error message
    
    def __init__(self, updater: AutoUpdater, update_info: dict):
        super().__init__()
        self.updater = updater
        self.update_info = update_info
    
    def run(self):
        """执行更新"""
        try:
            success = self.updater.download_and_apply_update(
                self.update_info,
                progress_callback=self._on_progress
            )
            self.finished.emit(success)
        except Exception as e:
            logger.error(f"Update thread error: {e}")
            self.error.emit(str(e))
    
    def _on_progress(self, current, total, status):
        """进度回调"""
        self.progress.emit(current, total, status)


class UpdateDialog(QDialog):
    """更新对话框"""
    
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.updater = AutoUpdater()
        self.update_thread = None
        
        self.setWindowTitle(self.tr("Software Update"))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 检查是否有完整性警告
        has_integrity_warning = self.update_info.get('integrity_warning', False)
        is_repair = self.update_info.get('is_repair', False)
        
        # 标题
        if is_repair:
            title_text = "⚠️ 文件完整性警告"
            title_color = "#cc0000"
        elif has_integrity_warning:
            title_text = "⚠️ 检测到文件异常"
            title_color = "#ff6600"
        else:
            title_text = "发现新版本!"
            title_color = "#000000"
        
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {title_color};")
        layout.addWidget(title_label)
        
        # 如果有完整性警告，显示警告信息
        if has_integrity_warning:
            warning_text = QLabel()
            if is_repair:
                warning_text.setText(
                    "⚠️ 检测到当前程序文件的完整性校验失败！\n"
                    "文件可能已被修改、损坏或感染病毒。\n"
                    "强烈建议立即修复以确保程序安全运行。"
                )
            else:
                warning_text.setText(
                    "⚠️ 当前文件的哈希值与服务器记录不匹配！\n"
                    "文件可能已被篡改或损坏。\n"
                    "建议更新到最新版本以确保安全。"
                )
            warning_text.setStyleSheet("""
                QLabel {
                    background-color: #fff3cd;
                    border: 2px solid #ff6600;
                    border-radius: 4px;
                    padding: 10px;
                    color: #856404;
                    font-weight: bold;
                }
            """)
            warning_text.setWordWrap(True)
            layout.addWidget(warning_text)
        
        # 版本信息
        version_layout = QHBoxLayout()
        version_layout.addWidget(QLabel("当前版本:"))
        version_layout.addWidget(QLabel(self.updater.current_version))
        version_layout.addStretch()
        version_layout.addWidget(QLabel("最新版本:"))
        new_version_label = QLabel(self.update_info['version'])
        new_version_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        version_layout.addWidget(new_version_label)
        layout.addLayout(version_layout)
        
        # 更新类型和大小
        info_layout = QHBoxLayout()
        
        if self.update_info['update_type'] == 'patch':
            update_type_text = "增量更新 (仅下载差异部分)"
            size_text = f"下载大小: {self._format_size(self.update_info['patch_size'])}"
            
            # 计算节省的流量
            full_size = self.update_info['size']
            patch_size = self.update_info['patch_size']
            saved_ratio = (1 - patch_size / full_size) * 100
            
            info_label = QLabel(f"{update_type_text}\n{size_text}\n节省流量: {saved_ratio:.1f}%")
            info_label.setStyleSheet("color: #009900; padding: 5px;")
        else:
            update_type_text = self.tr("Full Update")
            size_text = f"下载大小: {self._format_size(self.update_info['size'])}"
            info_label = QLabel(f"{update_type_text}\n{size_text}")
            info_label.setStyleSheet("color: #666666; padding: 5px;")
        
        layout.addWidget(info_label)
        
        # 更新说明
        layout.addWidget(QLabel("更新内容:"))
        
        release_notes = QTextEdit()
        release_notes.setReadOnly(True)
        release_notes.setPlainText(self.update_info.get('release_notes', '暂无更新说明'))
        release_notes.setMaximumHeight(150)
        layout.addWidget(release_notes)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.update_button = QPushButton(self.tr("Update Now"))
        self.update_button.clicked.connect(self._start_update)
        self.update_button.setStyleSheet("""
            QPushButton {
                background-color: #0066cc;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        button_layout.addWidget(self.update_button)
        
        self.cancel_button = QPushButton(self.tr("Remind Later"))
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #cccccc;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _start_update(self):
        """开始更新"""
        # 禁用按钮
        self.update_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        
        # 显示进度
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("准备下载...")
        
        # 创建并启动更新线程
        self.update_thread = UpdateThread(self.updater, self.update_info)
        self.update_thread.progress.connect(self._on_progress)
        self.update_thread.finished.connect(self._on_finished)
        self.update_thread.error.connect(self._on_error)
        self.update_thread.start()
    
    def _on_progress(self, current: int, total: int, status: str):
        """更新进度"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(status)
    
    def _on_finished(self, success: bool):
        """更新完成"""
        if success:
            QMessageBox.information(
                self,
                self.tr("Update Successful"),
                "更新已完成!\n\n程序将自动重启以应用更新。",
                QMessageBox.Ok
            )
            # 接受对话框,主程序会处理重启
            self.accept()
        else:
            QMessageBox.critical(
                self,
                self.tr("Update Failed"),
                "更新过程中发生错误,请稍后重试。",
                QMessageBox.Ok
            )
            # 重新启用按钮
            self.update_button.setEnabled(True)
            self.cancel_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setVisible(False)
    
    def _on_error(self, error: str):
        """更新错误"""
        QMessageBox.critical(
            self,
            self.tr("Update Failed"),
            f"更新过程中发生错误:\n\n{error}",
            QMessageBox.Ok
        )
        # 重新启用按钮
        self.update_button.setEnabled(True)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setVisible(False)
    
    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def closeEvent(self, event):
        """关闭对话框"""
        if self.update_thread and self.update_thread.isRunning():
            reply = QMessageBox.question(
                self,
                self.tr("Confirm"),
                "更新正在进行中,确定要取消吗?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.update_thread.terminate()
                self.update_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# 集成到主程序的示例代码
def check_for_updates_on_startup(main_window):
    """
    在主程序启动时检查更新
    将此函数添加到 main_window.py 的初始化中
    """
    try:
        from PySide6.QtCore import QTimer
        
        def do_check():
            updater = AutoUpdater()
            update_info = updater.check_for_updates()
            
            if update_info:
                logger.info(f"Found update: {update_info['version']}")
                
                # 显示更新对话框
                dialog = UpdateDialog(update_info, main_window)
                if dialog.exec() == QDialog.Accepted:
                    # 用户确认更新并且更新成功
                    # Windows下更新脚本会自动重启程序
                    # 这里可以关闭主程序
                    import sys
                    sys.exit(0)
            else:
                logger.info("No update available")
        
        # 延迟5秒检查,避免影响启动速度
        QTimer.singleShot(5000, do_check)
        
    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")

