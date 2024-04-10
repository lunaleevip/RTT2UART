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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout,
    QLabel, QPushButton, QSizePolicy, QSpacerItem,
    QSpinBox, QTabWidget, QWidget)

class Ui_xexun_rtt(object):
    def setupUi(self, xexun_rtt):
        if not xexun_rtt.objectName():
            xexun_rtt.setObjectName(u"xexun_rtt")
        xexun_rtt.resize(924, 508)
        self.widget = QWidget(xexun_rtt)
        self.widget.setObjectName(u"widget")
        self.widget.setGeometry(QRect(2, 2, 497, 303))
        self.gridLayout = QGridLayout(self.widget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.pushButton = QPushButton(self.widget)
        self.pushButton.setObjectName(u"pushButton")
        self.pushButton.setEnabled(True)
        self.pushButton.setMaximumSize(QSize(80, 26))

        self.gridLayout.addWidget(self.pushButton, 1, 4, 1, 1)

        self.horizontalSpacer = QSpacerItem(10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 1, 5, 1, 1)

        self.label = QLabel(self.widget)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        self.label.setMinimumSize(QSize(50, 20))

        self.gridLayout.addWidget(self.label, 2, 0, 1, 1)

        self.fontsize_box = QSpinBox(self.widget)
        self.fontsize_box.setObjectName(u"fontsize_box")
        sizePolicy.setHeightForWidth(self.fontsize_box.sizePolicy().hasHeightForWidth())
        self.fontsize_box.setSizePolicy(sizePolicy)
        self.fontsize_box.setMinimum(6)
        self.fontsize_box.setMaximum(24)
        self.fontsize_box.setValue(9)

        self.gridLayout.addWidget(self.fontsize_box, 2, 1, 1, 1)

        self.LockV_checkBox = QCheckBox(self.widget)
        self.LockV_checkBox.setObjectName(u"LockV_checkBox")

        self.gridLayout.addWidget(self.LockV_checkBox, 2, 2, 1, 1)

        self.LockH_checkBox = QCheckBox(self.widget)
        self.LockH_checkBox.setObjectName(u"LockH_checkBox")

        self.gridLayout.addWidget(self.LockH_checkBox, 2, 3, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 3, 2, 1, 1)

        self.tem_switch = QTabWidget(self.widget)
        self.tem_switch.setObjectName(u"tem_switch")
        self.tem_switch.setMinimumSize(QSize(100, 200))
        self.tab = QWidget()
        self.tab.setObjectName(u"tab")
        self.tem_switch.addTab(self.tab, "")
        self.tab_2 = QWidget()
        self.tab_2.setObjectName(u"tab_2")
        self.tem_switch.addTab(self.tab_2, "")

        self.gridLayout.addWidget(self.tem_switch, 0, 0, 1, 6)

        self.cmd_buffer = QComboBox(self.widget)
        self.cmd_buffer.setObjectName(u"cmd_buffer")
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.cmd_buffer.sizePolicy().hasHeightForWidth())
        self.cmd_buffer.setSizePolicy(sizePolicy1)
        self.cmd_buffer.setMaximumSize(QSize(16777215, 26))
        font = QFont()
        font.setFamilies([u"\u65b0\u5b8b\u4f53"])
        self.cmd_buffer.setFont(font)
        self.cmd_buffer.setEditable(True)

        self.gridLayout.addWidget(self.cmd_buffer, 1, 0, 1, 4)


        self.retranslateUi(xexun_rtt)

        self.pushButton.setDefault(True)
        self.tem_switch.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(xexun_rtt)
    # setupUi

    def retranslateUi(self, xexun_rtt):
        xexun_rtt.setWindowTitle(QCoreApplication.translate("xexun_rtt", u"Form", None))
        self.pushButton.setText(QCoreApplication.translate("xexun_rtt", u"Enter", None))
        self.label.setText(QCoreApplication.translate("xexun_rtt", u"FontSize", None))
        self.LockV_checkBox.setText(QCoreApplication.translate("xexun_rtt", u"Lock Vertical", None))
        self.LockH_checkBox.setText(QCoreApplication.translate("xexun_rtt", u"Lock Horizontal", None))
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab), QCoreApplication.translate("xexun_rtt", u"1", None))
        self.tem_switch.setTabText(self.tem_switch.indexOf(self.tab_2), QCoreApplication.translate("xexun_rtt", u"2", None))
    # retranslateUi

