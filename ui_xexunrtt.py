# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'xexunrtt.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
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
from PySide6.QtWidgets import (QApplication, QComboBox, QGridLayout, QLabel,
    QPushButton, QSizePolicy, QTabWidget, QWidget)

class Ui_xexun_rtt(object):
    def setupUi(self, xexun_rtt):
        if not xexun_rtt.objectName():
            xexun_rtt.setObjectName(u"xexun_rtt")
        xexun_rtt.resize(924, 508)
        self.widget = QWidget(xexun_rtt)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(0, 0, 811, 421))
        self.gridLayout = QGridLayout(self.widget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.cmd_buffer = QComboBox(self.widget)
        self.cmd_buffer.setObjectName(u"cmd_buffer")
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cmd_buffer.sizePolicy().hasHeightForWidth())
        self.cmd_buffer.setSizePolicy(sizePolicy)
        self.cmd_buffer.setMaximumSize(QSize(16777215, 26))
        font = QFont()
        font.setFamilies([u"\u65b0\u5b8b\u4f53"])
        self.cmd_buffer.setFont(font)
        self.cmd_buffer.setEditable(True)

        self.gridLayout.addWidget(self.cmd_buffer, 1, 0, 1, 1)

        self.pushButton = QPushButton(self.widget)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setEnabled(True)
        self.pushButton.setMaximumSize(QSize(80, 26))

        self.gridLayout.addWidget(self.pushButton, 1, 1, 1, 1)

        self.tem_switch = QTabWidget(self.widget)
        self.tem_switch.setObjectName(u"tem_switch")
        self.tem_switch.setMinimumSize(QSize(100, 200))
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.tem_switch.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.tem_switch.addTab(self.tab_2, "")

        self.gridLayout.addWidget(self.tem_switch, 0, 0, 1, 2)

        self.status = QLabel(self.widget)
        self.status.setObjectName(u"status")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.status.sizePolicy().hasHeightForWidth())
        self.status.setSizePolicy(sizePolicy1)
        self.status.setMinimumSize(QSize(200, 26))
        self.status.setMaximumSize(QSize(16777215, 26))

        self.gridLayout.addWidget(self.status, 2, 0, 1, 2)


        self.retranslateUi(xexun_rtt)

        self.pushButton.setDefault(True)
        self.tem_switch.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(xexun_rtt)
    # setupUi

    def retranslateUi(self, xexun_rtt):
        xexun_rtt.setWindowTitle(QCoreApplication.translate("xexun_rtt", u"Form", None))
        self.pushButton.setText(QCoreApplication.translate("xexun_rtt", u"Enter", None))
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab), QCoreApplication.translate("xexun_rtt", u"1", None))
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab_2), QCoreApplication.translate("xexun_rtt", u"2", None))
        self.status.setText("")
    # retranslateUi

