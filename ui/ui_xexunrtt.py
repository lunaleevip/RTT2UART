# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'xexunrtt.ui'
##
## Created by: Qt User Interface Compiler version 6.9.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QLabel, QLineEdit, QMainWindow, QMdiArea,
    QMenuBar, QPlainTextEdit, QPushButton, QRadioButton,
    QSizePolicy, QSpacerItem, QSpinBox, QSplitter,
    QStatusBar, QVBoxLayout, QWidget)

class Ui_RTTMainWindow(object):
    def setupUi(self, RTTMainWindow):
        if not RTTMainWindow.objectName():
            RTTMainWindow.setObjectName(u"RTTMainWindow")
        RTTMainWindow.resize(1200, 800)
        self.centralwidget = QWidget(RTTMainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout_main = QVBoxLayout(self.centralwidget)
        self.verticalLayout_main.setSpacing(0)
        self.verticalLayout_main.setObjectName(u"verticalLayout_main")
        self.verticalLayout_main.setContentsMargins(0, 0, 0, 0)
        self.main_splitter = QSplitter(self.centralwidget)
        self.main_splitter.setObjectName(u"main_splitter")
        self.main_splitter.setOrientation(Qt.Vertical)
        self.main_splitter.setHandleWidth(2)
        self.mdi_area = QMdiArea(self.main_splitter)
        self.mdi_area.setObjectName(u"mdi_area")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.mdi_area.sizePolicy().hasHeightForWidth())
        self.mdi_area.setSizePolicy(sizePolicy)
        self.main_splitter.addWidget(self.mdi_area)
        self.bottom_container = QWidget(self.main_splitter)
        self.bottom_container.setObjectName(u"bottom_container")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.bottom_container.sizePolicy().hasHeightForWidth())
        self.bottom_container.setSizePolicy(sizePolicy1)
        self.verticalLayout_bottom = QVBoxLayout(self.bottom_container)
        self.verticalLayout_bottom.setSpacing(0)
        self.verticalLayout_bottom.setObjectName(u"verticalLayout_bottom")
        self.verticalLayout_bottom.setContentsMargins(0, 0, 0, 0)
        self.button_command_area = QWidget(self.bottom_container)
        self.button_command_area.setObjectName(u"button_command_area")
        sizePolicy1.setHeightForWidth(self.button_command_area.sizePolicy().hasHeightForWidth())
        self.button_command_area.setSizePolicy(sizePolicy1)
        self.button_command_area.setMinimumSize(QSize(0, 70))
        self.button_command_area.setMaximumSize(QSize(16777215, 70))
        self.gridLayout = QGridLayout(self.button_command_area)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(5)
        self.gridLayout.setVerticalSpacing(5)
        self.gridLayout.setContentsMargins(5, 5, 5, 5)
        self.cmd_buffer = QComboBox(self.button_command_area)
        self.cmd_buffer.setObjectName(u"cmd_buffer")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.cmd_buffer.sizePolicy().hasHeightForWidth())
        self.cmd_buffer.setSizePolicy(sizePolicy2)
        font = QFont()
        font.setFamilies([u"Arial"])
        self.cmd_buffer.setFont(font)
        self.cmd_buffer.setEditable(True)

        self.gridLayout.addWidget(self.cmd_buffer, 0, 0, 1, 20)

        self.pushButton = QPushButton(self.button_command_area)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setMaximumSize(QSize(80, 26))
        self.pushButton.setFont(font)

        self.gridLayout.addWidget(self.pushButton, 0, 20, 1, 1)

        self.openfolder = QPushButton(self.button_command_area)
        self.openfolder.setObjectName(u"openfolder")
        self.openfolder.setFont(font)

        self.gridLayout.addWidget(self.openfolder, 1, 0, 1, 1)

        self.re_connect = QPushButton(self.button_command_area)
        self.re_connect.setObjectName(u"re_connect")
        self.re_connect.setFont(font)

        self.gridLayout.addWidget(self.re_connect, 1, 1, 1, 1)

        self.dis_connect = QPushButton(self.button_command_area)
        self.dis_connect.setObjectName(u"dis_connect")
        self.dis_connect.setFont(font)

        self.gridLayout.addWidget(self.dis_connect, 1, 2, 1, 1)

        self.clear = QPushButton(self.button_command_area)
        self.clear.setObjectName(u"clear")
        self.clear.setFont(font)

        self.gridLayout.addWidget(self.clear, 1, 3, 1, 1)

        self.radioButton_pause_refresh = QRadioButton(self.button_command_area)
        self.radioButton_pause_refresh.setObjectName(u"radioButton_pause_refresh")
        self.radioButton_pause_refresh.setFont(font)

        self.gridLayout.addWidget(self.radioButton_pause_refresh, 1, 4, 1, 1)

        self.radioButton_resume_refresh = QRadioButton(self.button_command_area)
        self.radioButton_resume_refresh.setObjectName(u"radioButton_resume_refresh")
        self.radioButton_resume_refresh.setFont(font)
        self.radioButton_resume_refresh.setChecked(True)

        self.gridLayout.addWidget(self.radioButton_resume_refresh, 1, 5, 1, 1)

        self.light_checkbox = QCheckBox(self.button_command_area)
        self.light_checkbox.setObjectName(u"light_checkbox")
        self.light_checkbox.setFont(font)

        self.gridLayout.addWidget(self.light_checkbox, 1, 6, 1, 1)

        self.auto_reconnect_checkbox = QCheckBox(self.button_command_area)
        self.auto_reconnect_checkbox.setObjectName(u"auto_reconnect_checkbox")
        self.auto_reconnect_checkbox.setFont(font)

        self.gridLayout.addWidget(self.auto_reconnect_checkbox, 1, 7, 1, 1)

        self.reconnect_timeout_edit = QLineEdit(self.button_command_area)
        self.reconnect_timeout_edit.setObjectName(u"reconnect_timeout_edit")
        self.reconnect_timeout_edit.setMaximumSize(QSize(35, 16777215))
        self.reconnect_timeout_edit.setFont(font)
        self.reconnect_timeout_edit.setAlignment(Qt.AlignCenter)

        self.gridLayout.addWidget(self.reconnect_timeout_edit, 1, 8, 1, 1)

        self.restart_app_button = QPushButton(self.button_command_area)
        self.restart_app_button.setObjectName(u"restart_app_button")
        self.restart_app_button.setFont(font)

        self.gridLayout.addWidget(self.restart_app_button, 1, 9, 1, 1)

        self.horizontalSpacer_expand = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_expand, 1, 10, 1, 1)

        self.font_combo = QComboBox(self.button_command_area)
        self.font_combo.setObjectName(u"font_combo")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.font_combo.sizePolicy().hasHeightForWidth())
        self.font_combo.setSizePolicy(sizePolicy3)
        self.font_combo.setMinimumSize(QSize(80, 20))
        self.font_combo.setFont(font)

        self.gridLayout.addWidget(self.font_combo, 1, 11, 1, 1)

        self.fontsize_box = QSpinBox(self.button_command_area)
        self.fontsize_box.setObjectName(u"fontsize_box")
        self.fontsize_box.setFont(font)
        self.fontsize_box.setMinimum(6)
        self.fontsize_box.setMaximum(24)
        self.fontsize_box.setValue(9)

        self.gridLayout.addWidget(self.fontsize_box, 1, 12, 1, 1)

        self.sent = QLabel(self.button_command_area)
        self.sent.setObjectName(u"sent")

        self.gridLayout.addWidget(self.sent, 1, 13, 1, 1)


        self.verticalLayout_bottom.addWidget(self.button_command_area)

        self.jlink_log_area = QWidget(self.bottom_container)
        self.jlink_log_area.setObjectName(u"jlink_log_area")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.jlink_log_area.sizePolicy().hasHeightForWidth())
        self.jlink_log_area.setSizePolicy(sizePolicy4)
        self.jlink_log_area.setMinimumSize(QSize(0, 0))
        self.verticalLayout_jlink = QVBoxLayout(self.jlink_log_area)
        self.verticalLayout_jlink.setSpacing(0)
        self.verticalLayout_jlink.setObjectName(u"verticalLayout_jlink")
        self.verticalLayout_jlink.setContentsMargins(0, 0, 0, 0)
        self.jlink_log_text = QPlainTextEdit(self.jlink_log_area)
        self.jlink_log_text.setObjectName(u"jlink_log_text")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.jlink_log_text.sizePolicy().hasHeightForWidth())
        self.jlink_log_text.setSizePolicy(sizePolicy5)
        font1 = QFont()
        font1.setFamilies([u"Consolas"])
        font1.setPointSize(9)
        self.jlink_log_text.setFont(font1)
        self.jlink_log_text.setReadOnly(True)

        self.verticalLayout_jlink.addWidget(self.jlink_log_text)


        self.verticalLayout_bottom.addWidget(self.jlink_log_area)

        self.main_splitter.addWidget(self.bottom_container)

        self.verticalLayout_main.addWidget(self.main_splitter)

        RTTMainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(RTTMainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1200, 21))
        RTTMainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(RTTMainWindow)
        self.statusbar.setObjectName(u"statusbar")
        RTTMainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(RTTMainWindow)

        QMetaObject.connectSlotsByName(RTTMainWindow)
    # setupUi

    def retranslateUi(self, RTTMainWindow):
        RTTMainWindow.setWindowTitle(QCoreApplication.translate("RTTMainWindow", u"XexunRTT - RTT Debug Main Window", None))
#if QT_CONFIG(tooltip)
        self.cmd_buffer.setToolTip(QCoreApplication.translate("RTTMainWindow", u"can read from cmd.txt", None))
#endif // QT_CONFIG(tooltip)
        self.pushButton.setText(QCoreApplication.translate("RTTMainWindow", u"Send", None))
#if QT_CONFIG(tooltip)
        self.openfolder.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F1", None))
#endif // QT_CONFIG(tooltip)
        self.openfolder.setText(QCoreApplication.translate("RTTMainWindow", u"Open Folder", None))
#if QT_CONFIG(tooltip)
        self.re_connect.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F2", None))
#endif // QT_CONFIG(tooltip)
        self.re_connect.setText(QCoreApplication.translate("RTTMainWindow", u"Reconnect", None))
#if QT_CONFIG(tooltip)
        self.dis_connect.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F3", None))
#endif // QT_CONFIG(tooltip)
        self.dis_connect.setText(QCoreApplication.translate("RTTMainWindow", u"Disconnect", None))
#if QT_CONFIG(tooltip)
        self.clear.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F4", None))
#endif // QT_CONFIG(tooltip)
        self.clear.setText(QCoreApplication.translate("RTTMainWindow", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.radioButton_pause_refresh.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F5", None))
#endif // QT_CONFIG(tooltip)
        self.radioButton_pause_refresh.setText(QCoreApplication.translate("RTTMainWindow", u"Pause Refresh", None))
#if QT_CONFIG(tooltip)
        self.radioButton_resume_refresh.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F6", None))
#endif // QT_CONFIG(tooltip)
        self.radioButton_resume_refresh.setText(QCoreApplication.translate("RTTMainWindow", u"Resume Refresh", None))
#if QT_CONFIG(tooltip)
        self.light_checkbox.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F7", None))
#endif // QT_CONFIG(tooltip)
        self.light_checkbox.setText(QCoreApplication.translate("RTTMainWindow", u"Light Mode", None))
#if QT_CONFIG(tooltip)
        self.auto_reconnect_checkbox.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F8", None))
#endif // QT_CONFIG(tooltip)
        self.auto_reconnect_checkbox.setText(QCoreApplication.translate("RTTMainWindow", u"Auto Reconnect", None))
        self.reconnect_timeout_edit.setText(QCoreApplication.translate("RTTMainWindow", u"60", None))
#if QT_CONFIG(tooltip)
        self.restart_app_button.setToolTip(QCoreApplication.translate("RTTMainWindow", u"F9", None))
#endif // QT_CONFIG(tooltip)
        self.restart_app_button.setText(QCoreApplication.translate("RTTMainWindow", u"Restart APP", None))
        self.sent.setText("")
        self.jlink_log_text.setPlainText("")
    # retranslateUi

