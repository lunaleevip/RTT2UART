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
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QTabWidget, QWidget)

class Ui_xexun_rtt(object):
    def setupUi(self, xexun_rtt):
        if not xexun_rtt.objectName():
            xexun_rtt.setObjectName(u"xexun_rtt")
        xexun_rtt.resize(1055, 541)
        self.layoutWidget = QWidget(xexun_rtt)
        self.layoutWidget.setObjectName(u"layoutWidget")
        self.layoutWidget.setGeometry(QRect(30, 20, 1001, 308))
        self.gridLayout = QGridLayout(self.layoutWidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_8 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_8, 2, 13, 1, 1)

        self.cmd_buffer = QComboBox(self.layoutWidget)
        self.cmd_buffer.setObjectName(u"cmd_buffer")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cmd_buffer.sizePolicy().hasHeightForWidth())
        self.cmd_buffer.setSizePolicy(sizePolicy)
        self.cmd_buffer.setMaximumSize(QSize(16777215, 26))
        font = QFont()
        font.setFamilies([u"\u65b0\u5b8b\u4f53"])
        self.cmd_buffer.setFont(font)
        self.cmd_buffer.setEditable(True)

        self.gridLayout.addWidget(self.cmd_buffer, 1, 1, 1, 19)

        self.dis_connect = QPushButton(self.layoutWidget)
        self.dis_connect.setObjectName(u"dis_connect")
        font1 = QFont()
        font1.setFamilies([u"Arial"])
        self.dis_connect.setFont(font1)

        self.gridLayout.addWidget(self.dis_connect, 2, 3, 1, 1)

        self.fontsize_box = QSpinBox(self.layoutWidget)
        self.fontsize_box.setObjectName(u"fontsize_box")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.fontsize_box.sizePolicy().hasHeightForWidth())
        self.fontsize_box.setSizePolicy(sizePolicy1)
        self.fontsize_box.setFont(font1)
        self.fontsize_box.setMinimum(6)
        self.fontsize_box.setMaximum(24)
        self.fontsize_box.setValue(9)

        self.gridLayout.addWidget(self.fontsize_box, 2, 15, 1, 1)

        self.clear = QPushButton(self.layoutWidget)
        self.clear.setObjectName(u"clear")
        self.clear.setFont(font1)

        self.gridLayout.addWidget(self.clear, 2, 4, 1, 1)

        self.openfolder = QPushButton(self.layoutWidget)
        self.openfolder.setObjectName(u"openfolder")
        self.openfolder.setFont(font1)

        self.gridLayout.addWidget(self.openfolder, 2, 1, 1, 1)

        self.horizontalSpacer_10 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_10, 2, 9, 1, 2)

        self.horizontalSpacer = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 1, 21, 1, 1)

        self.horizontalSpacer_4 = QSpacerItem(13, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_4, 2, 19, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 13, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 3, 15, 1, 1)

        self.horizontalSpacer_6 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_6, 1, 0, 1, 1)

        self.pushButton = QPushButton(self.layoutWidget)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setEnabled(True)
        self.pushButton.setMaximumSize(QSize(80, 26))
        self.pushButton.setFont(font1)
        self.pushButton.setAutoDefault(True)

        self.gridLayout.addWidget(self.pushButton, 1, 20, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_2, 2, 0, 1, 1)

        self.light_checkbox = QCheckBox(self.layoutWidget)
        self.light_checkbox.setObjectName(u"light_checkbox")
        self.light_checkbox.setFont(font1)

        self.gridLayout.addWidget(self.light_checkbox, 2, 12, 1, 1)

        self.tem_switch = QTabWidget(self.layoutWidget)
        self.tem_switch.setObjectName(u"tem_switch")
        self.tem_switch.setMinimumSize(QSize(100, 200))
        self.tem_switch.setFont(font1)
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.tem_switch.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.tem_switch.addTab(self.tab_2, "")

        self.gridLayout.addWidget(self.tem_switch, 0, 0, 1, 22)

        self.label = QLabel(self.layoutWidget)
        self.label.setObjectName(u"label")
        sizePolicy1.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy1)
        self.label.setMinimumSize(QSize(50, 20))
        self.label.setFont(font1)

        self.gridLayout.addWidget(self.label, 2, 14, 1, 1)

        self.horizontalSpacer_3 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_3, 2, 21, 1, 1)

        self.re_connect = QPushButton(self.layoutWidget)
        self.re_connect.setObjectName(u"re_connect")
        self.re_connect.setFont(font1)

        self.gridLayout.addWidget(self.re_connect, 2, 2, 1, 1)

        self.LockH_checkBox = QCheckBox(self.layoutWidget)
        self.LockH_checkBox.setObjectName(u"LockH_checkBox")
        self.LockH_checkBox.setFont(font1)

        self.gridLayout.addWidget(self.LockH_checkBox, 2, 7, 1, 1)

        self.LockV_checkBox = QCheckBox(self.layoutWidget)
        self.LockV_checkBox.setObjectName(u"LockV_checkBox")
        self.LockV_checkBox.setFont(font1)

        self.gridLayout.addWidget(self.LockV_checkBox, 2, 6, 1, 1)

        self.horizontalSpacer_9 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_9, 2, 5, 1, 1)

        self.horizontalSpacer_5 = QSpacerItem(13, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_5, 2, 16, 1, 1)

        self.sent = QLabel(self.layoutWidget)
        self.sent.setObjectName(u"sent")

        self.gridLayout.addWidget(self.sent, 2, 17, 1, 1)


        self.retranslateUi(xexun_rtt)

        self.pushButton.setDefault(True)
        self.tem_switch.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(xexun_rtt)
    # setupUi

    def retranslateUi(self, xexun_rtt):
        xexun_rtt.setWindowTitle(QCoreApplication.translate("xexun_rtt", u"Form", None))
#if QT_CONFIG(tooltip)
        self.cmd_buffer.setToolTip(QCoreApplication.translate("xexun_rtt", u"can read from cmd.txt", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.dis_connect.setToolTip(QCoreApplication.translate("xexun_rtt", u"F3", None))
#endif // QT_CONFIG(tooltip)
        self.dis_connect.setText(QCoreApplication.translate("xexun_rtt", u"Disconnect", None))
#if QT_CONFIG(tooltip)
        self.clear.setToolTip("")
#endif // QT_CONFIG(tooltip)
        self.clear.setText(QCoreApplication.translate("xexun_rtt", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.openfolder.setToolTip(QCoreApplication.translate("xexun_rtt", u"F1", None))
#endif // QT_CONFIG(tooltip)
        self.openfolder.setText(QCoreApplication.translate("xexun_rtt", u"Open Folder", None))
        self.pushButton.setText(QCoreApplication.translate("xexun_rtt", u"Send", None))
#if QT_CONFIG(tooltip)
        self.light_checkbox.setToolTip(QCoreApplication.translate("xexun_rtt", u"F7", None))
#endif // QT_CONFIG(tooltip)
        self.light_checkbox.setText(QCoreApplication.translate("xexun_rtt", u"Light Mode", None))
#if QT_CONFIG(tooltip)
        self.tem_switch.setToolTip(QCoreApplication.translate("xexun_rtt", u"double click filter to write filter text", None))
#endif // QT_CONFIG(tooltip)
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab), QCoreApplication.translate("xexun_rtt", u"1", None))
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab_2), QCoreApplication.translate("xexun_rtt", u"2", None))
        self.label.setText(QCoreApplication.translate("xexun_rtt", u"Font Size", None))
#if QT_CONFIG(tooltip)
        self.re_connect.setToolTip(QCoreApplication.translate("xexun_rtt", u"F2", None))
#endif // QT_CONFIG(tooltip)
        self.re_connect.setText(QCoreApplication.translate("xexun_rtt", u"Reconnect", None))
#if QT_CONFIG(tooltip)
        self.LockH_checkBox.setToolTip(QCoreApplication.translate("xexun_rtt", u"F6", None))
#endif // QT_CONFIG(tooltip)
        self.LockH_checkBox.setText(QCoreApplication.translate("xexun_rtt", u"Lock Horizontal", None))
#if QT_CONFIG(tooltip)
        self.LockV_checkBox.setToolTip(QCoreApplication.translate("xexun_rtt", u"F5", None))
#endif // QT_CONFIG(tooltip)
        self.LockV_checkBox.setText(QCoreApplication.translate("xexun_rtt", u"Lock Vertical", None))
        self.sent.setText("")
    # retranslateUi

