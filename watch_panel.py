from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from PySide6.QtCore import QCoreApplication, QTimer, Qt, QByteArray
from PySide6.QtGui import QAction, QFont, QGuiApplication, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCompleter,
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QCheckBox,
)
from PySide6.QtCore import QStringListModel

from map_parser import parse_segger_map, lookup_symbol
from watch_dwarf import DwarfIndex, TypeDesc, DwarfVariable

logger = logging.getLogger(__name__)

class _InlineInputLineEdit(QLineEdit):
    """Inline input editor used as the last row in the watch tree."""
    def __init__(self, dock: "WatchDock"):
        super().__init__(dock.tree_watch)
        self._dock = dock
        self.setPlaceholderText(QCoreApplication.translate("watch", "Type expression here, press Enter"))
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(int(self.sizeHint().height()) + 2)
        self.setCompleter(dock._completer)
        self.textEdited.connect(dock._on_expr_text_edited)
        self.returnPressed.connect(lambda: dock._submit_inline_expr(self.text().strip()))

    def keyPressEvent(self, event):
        # If completer popup is visible, Enter should accept completion, not submit.
        try:
            comp = self.completer()
            if comp is not None and comp.popup() is not None and comp.popup().isVisible():
                key = int(event.key())
                if key in (int(Qt.Key_Return), int(Qt.Key_Enter)):
                    super().keyPressEvent(event)
                    return
        except Exception:
            pass
        super().keyPressEvent(event)


@dataclass
class WatchItemModel:
    expr: str
    addr: int
    typ: Optional[TypeDesc]
    size: int
    # bitfield (optional)
    bit_size: Optional[int] = None
    bit_lsb: Optional[int] = None
    storage_bytes: Optional[int] = None
    computed: bool = False


def _parse_int(text: str) -> Optional[int]:
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    try:
        if t.lower().startswith("0x"):
            return int(t, 16)
        return int(t, 10)
    except Exception:
        return None


def _format_hex_dump(addr: int, data: bytes, width: int = 16) -> str:
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        asc_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{addr + i:08X}  {hex_part:<{width*3}}  {asc_part}")
    return "\n".join(lines)


class WatchDock(QDockWidget):
    def __init__(self, main_window):
        super().__init__(QCoreApplication.translate("watch", "Watch / Memory"), main_window)
        self.main_window = main_window

        self.map_path: Optional[str] = None
        self.elf_path: Optional[str] = None
        self._map_symbols: Dict[str, object] = {}
        self._dwarf: Optional[DwarfIndex] = None

        self._watch_items: Dict[str, WatchItemModel] = {}

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_all)

        # Log rate limit: key -> last_ts
        self._log_rate: Dict[str, float] = {}
        self._log_rate_default_sec = 5.0

        # Memory dump auto refresh is enabled only after a manual Load
        self._memory_auto_enabled = False
        self._watch_enabled = False

        # Symbol completer (MAP + DWARF)
        self._symbol_model = QStringListModel(self)
        self._completer = QCompleter(self._symbol_model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._all_symbol_names: List[str] = []

        root = QWidget(self)
        self.setWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # File selection + refresh interval
        top = QFrame(root)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(6)

        self.label_status = QLabel(QCoreApplication.translate("watch", "Select ELF to enable."))
        self.label_status.setWordWrap(True)
        self.label_status.setVisible(False)

        self.text_log = QPlainTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setMaximumBlockCount(200)
        self.text_log.setMaximumHeight(90)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.edit_map = QLineEdit()
        self.edit_map.setReadOnly(True)
        btn_map = QPushButton(QCoreApplication.translate("watch", "Select..."))
        btn_map.clicked.connect(self._select_map)
        row_map = QHBoxLayout()
        row_map.addWidget(self.edit_map, 1)
        row_map.addWidget(btn_map)
        w_map = QWidget()
        w_map.setLayout(row_map)
        # 先暂时隐藏 MAP 行，因为暂时不需要使用 MAP
        w_map.setVisible(False)
        #form.addRow(QCoreApplication.translate("watch", "MAP"), w_map)

        self.edit_elf = QLineEdit()
        self.edit_elf.setReadOnly(True)
        btn_elf = QPushButton(QCoreApplication.translate("watch", "Select..."))
        btn_elf.clicked.connect(self._select_elf)
        row_elf = QHBoxLayout()
        row_elf.addWidget(self.edit_elf, 1)
        row_elf.addWidget(btn_elf)
        w_elf = QWidget()
        w_elf.setLayout(row_elf)
        form.addRow(QCoreApplication.translate("watch", "ELF"), w_elf)

        row_refresh = QHBoxLayout()
        self.combo_refresh = QComboBox()
        self.combo_refresh.addItem(QCoreApplication.translate("watch", "Off"), 0)
        self.combo_refresh.addItem("1s", 1)
        self.combo_refresh.addItem("2s", 2)
        self.combo_refresh.addItem("5s", 5)
        self.combo_refresh.addItem("10s", 10)
        self.combo_refresh.currentIndexChanged.connect(self._on_refresh_interval_changed)
        row_refresh.addWidget(QLabel(QCoreApplication.translate("watch", "Refresh")))
        row_refresh.addWidget(self.combo_refresh)
        row_refresh.addStretch(1)
        btn_reload = QPushButton(QCoreApplication.translate("watch", "Reload Symbols"))
        btn_reload.clicked.connect(self._reload_symbols)
        row_refresh.addWidget(btn_reload)

        btn_refresh_now = QPushButton(QCoreApplication.translate("watch", "Refresh Now"))
        btn_refresh_now.clicked.connect(self._refresh_now)
        row_refresh.addWidget(btn_refresh_now)

        top_layout.addLayout(form)
        top_layout.addLayout(row_refresh)
        top_layout.addWidget(self.label_status)
        top_layout.addWidget(self.text_log)
        outer.addWidget(top)

        splitter = QSplitter(Qt.Vertical, root)
        outer.addWidget(splitter, 1)

        # Watch area
        watch_box = QWidget()
        watch_layout = QVBoxLayout(watch_box)
        watch_layout.setContentsMargins(6, 6, 6, 6)
        watch_layout.setSpacing(6)

        add_row = QHBoxLayout()
        self.edit_expr = QLineEdit()
        self.edit_expr.setPlaceholderText(QCoreApplication.translate("watch", "Expression / symbol name"))
        self.edit_expr.setCompleter(self._completer)
        self.edit_expr.returnPressed.connect(lambda: self._add_watch())
        self.edit_expr.textEdited.connect(self._on_expr_text_edited)
        btn_add = QPushButton(QCoreApplication.translate("watch", "Add"))
        # QPushButton.clicked emits a bool argument; avoid it being treated as expr parameter.
        btn_add.clicked.connect(lambda _checked=False: self._add_watch())
        add_row.addWidget(self.edit_expr, 1)
        add_row.addWidget(btn_add)
        add_row_widget = QWidget()
        add_row_widget.setLayout(add_row)
        # Hide the top input row; use inline input row in tree instead
        add_row_widget.setVisible(False)
        watch_layout.addWidget(add_row_widget)

        # Keep original input for fallback shortcuts, but it's hidden.

        self.tree_watch = QTreeWidget()
        self.tree_watch.setHeaderLabels([
            QCoreApplication.translate("watch", "Expression"),
            QCoreApplication.translate("watch", "Value"),
        ])
        self.tree_watch.setColumnWidth(0, 260)
        self.tree_watch.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree_watch.setContextMenuPolicy(Qt.ActionsContextMenu)
        # act_del = QAction(QCoreApplication.translate("watch", "Remove"), self.tree_watch)
        # act_del.triggered.connect(self._remove_selected)
        # self.tree_watch.addAction(act_del)

        act_add_to_watch = QAction(QCoreApplication.translate("watch", "Add to Watch"), self.tree_watch)
        act_add_to_watch.triggered.connect(self._add_selected_to_watch)
        self.tree_watch.addAction(act_add_to_watch)

        act_refresh_one = QAction(QCoreApplication.translate("watch", "Refresh"), self.tree_watch)
        act_refresh_one.triggered.connect(self._refresh_selected_only)
        self.tree_watch.addAction(act_refresh_one)

        act_view_mem = QAction(QCoreApplication.translate("watch", "View Memory"), self.tree_watch)
        act_view_mem.triggered.connect(self._view_memory_for_selected)
        self.tree_watch.addAction(act_view_mem)

        # Delete key to remove selected symbol
        act_del_key = QAction(QCoreApplication.translate("watch", "Remove"), self.tree_watch)
        act_del_key.setShortcut(Qt.Key_Delete)
        act_del_key.setShortcutContext(Qt.WidgetShortcut)
        act_del_key.triggered.connect(self._remove_selected)
        self.tree_watch.addAction(act_del_key)

        watch_layout.addWidget(self.tree_watch, 1)

        # Inline input row (always last). New items are inserted before it (do NOT move it).
        self._input_item: Optional[QTreeWidgetItem] = None
        self._inline_input: Optional[QLineEdit] = None
        self._create_input_row()
        self.tree_watch.itemClicked.connect(self._on_tree_item_clicked)

        splitter.addWidget(watch_box)

        # Bottom area: Memory Dump + Frame Buffer (tabs)
        bottom_tabs = QTabWidget()
        splitter.addWidget(bottom_tabs)

        # --- Memory Dump tab ---
        mem_box = QWidget()
        mem_layout = QVBoxLayout(mem_box)
        mem_layout.setContentsMargins(6, 6, 6, 6)
        mem_layout.setSpacing(6)

        mem_row = QHBoxLayout()
        self.edit_addr = QLineEdit("0x20000000")
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 4096 * 16)
        self.spin_size.setValue(256)
        btn_load = QPushButton(QCoreApplication.translate("watch", "Load"))
        btn_load.clicked.connect(self.load_memory_dump)
        mem_row.addWidget(QLabel(QCoreApplication.translate("watch", "Address")))
        mem_row.addWidget(self.edit_addr)
        mem_row.addWidget(QLabel(QCoreApplication.translate("watch", "Size")))
        mem_row.addWidget(self.spin_size)
        mem_row.addWidget(btn_load)
        mem_layout.addLayout(mem_row)

        self.text_dump = QPlainTextEdit()
        self.text_dump.setReadOnly(True)
        self.text_dump.setLineWrapMode(QPlainTextEdit.NoWrap)
        mem_layout.addWidget(self.text_dump, 1)

        bottom_tabs.addTab(mem_box, QCoreApplication.translate("watch", "Memory Dump"))

        # --- Frame Buffer tab ---
        fb_box = QWidget()
        fb_layout = QVBoxLayout(fb_box)
        fb_layout.setContentsMargins(6, 6, 6, 6)
        fb_layout.setSpacing(6)

        self.fb_edit_addr = QLineEdit()
        self.fb_edit_addr.setPlaceholderText("0x20000000")
        self.fb_spin_w = QSpinBox()
        self.fb_spin_w.setRange(0, 8192)
        self.fb_spin_w.setValue(0)
        self.fb_spin_h = QSpinBox()
        self.fb_spin_h.setRange(0, 8192)
        self.fb_spin_h.setValue(0)
        self.fb_combo_fmt = QComboBox()
        self.fb_combo_fmt.addItem("ARGB32", "ARGB32")
        self.fb_combo_fmt.addItem("RGB32", "RGB32")
        self.fb_combo_fmt.addItem("RGB565", "RGB565")
        self.fb_combo_fmt.addItem("RGB888", "RGB888")
        self.fb_combo_fmt.addItem("Mono LSB", "MonoLSB")
        self.fb_combo_fmt.addItem("Mono MSB", "MonoMSB")

        self.fb_check_auto = QCheckBox(QCoreApplication.translate("watch", "Auto refresh"))
        btn_fb_load = QPushButton(QCoreApplication.translate("watch", "Load"))
        btn_fb_load.clicked.connect(self.load_frame_buffer)

        # Row 1: Address / Width / Height / Load
        fb_row1 = QHBoxLayout()
        fb_row1.addWidget(QLabel(QCoreApplication.translate("watch", "Address")))
        fb_row1.addWidget(self.fb_edit_addr, 1)
        fb_row1.addWidget(QLabel(QCoreApplication.translate("watch", "Width")))
        fb_row1.addWidget(self.fb_spin_w)
        fb_row1.addWidget(QLabel(QCoreApplication.translate("watch", "Height")))
        fb_row1.addWidget(self.fb_spin_h)
        fb_row1.addWidget(btn_fb_load)
        fb_layout.addLayout(fb_row1)

        # Row 2: Format / Auto refresh / Refresh Now / Zoom tools
        fb_row2 = QHBoxLayout()
        self.fb_btn_refresh = QPushButton(QCoreApplication.translate("watch", "Refresh Now"))
        self.fb_btn_refresh.clicked.connect(self.load_frame_buffer)
        self.fb_btn_zoom_out = QPushButton("-")
        self.fb_btn_zoom_out.clicked.connect(lambda: self._fb_set_zoom(self._fb_zoom / 1.25))
        self.fb_btn_zoom_in = QPushButton("+")
        self.fb_btn_zoom_in.clicked.connect(lambda: self._fb_set_zoom(self._fb_zoom * 1.25))
        self.fb_btn_zoom_1 = QPushButton("1:1")
        self.fb_btn_zoom_1.clicked.connect(lambda: self._fb_set_zoom(1.0))
        self.fb_btn_fit = QPushButton(QCoreApplication.translate("watch", "Fit"))
        self.fb_btn_fit.clicked.connect(self._fb_fit_to_view)

        fb_row2.addWidget(QLabel(QCoreApplication.translate("watch", "Format")))
        fb_row2.addWidget(self.fb_combo_fmt)
        fb_row2.addWidget(self.fb_check_auto)
        fb_row2.addWidget(self.fb_btn_refresh)
        fb_row2.addStretch(1)
        fb_row2.addWidget(self.fb_btn_zoom_out)
        fb_row2.addWidget(self.fb_btn_zoom_in)
        fb_row2.addWidget(self.fb_btn_zoom_1)
        fb_row2.addWidget(self.fb_btn_fit)
        fb_layout.addLayout(fb_row2)

        self._fb_zoom = 1.0
        self._fb_last_qimage: Optional[QImage] = None
        self._fb_last_bytes: Optional[bytes] = None
        self._fb_job_id = 0

        self.fb_label = QLabel(QCoreApplication.translate("watch", "No address specified"))
        self.fb_label.setAlignment(Qt.AlignCenter)
        self.fb_label.setMinimumHeight(120)
        self.fb_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fb_label.setFocusPolicy(Qt.StrongFocus)
        self.fb_label.setContextMenuPolicy(Qt.ActionsContextMenu)

        act_copy_fb = QAction(QCoreApplication.translate("watch", "Copy Image"), self.fb_label)
        act_copy_fb.setShortcut(QKeySequence.Copy)
        act_copy_fb.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        act_copy_fb.triggered.connect(self._fb_copy_to_clipboard)
        self.fb_label.addAction(act_copy_fb)

        self.fb_scroll = QScrollArea()
        self.fb_scroll.setWidgetResizable(True)
        self.fb_scroll.setWidget(self.fb_label)
        fb_layout.addWidget(self.fb_scroll, 1)

        bottom_tabs.addTab(fb_box, QCoreApplication.translate("watch", "Frame Buffer"))
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._set_watch_enabled(False)
        self._log_ui("Watch/Memory dock initialized.")
        self._apply_app_font()

        # Follow main window font settings (if available)
        try:
            if hasattr(self.main_window, "ui") and hasattr(self.main_window.ui, "font_combo"):
                self.main_window.ui.font_combo.currentTextChanged.connect(lambda _t: self._apply_app_font())
            if hasattr(self.main_window, "ui") and hasattr(self.main_window.ui, "fontsize_box"):
                self.main_window.ui.fontsize_box.valueChanged.connect(lambda _v: self._apply_app_font())
        except Exception:
            pass

    def _apply_app_font(self):
        """Apply the same monospace font as main window's configured font."""
        try:
            font_name = None
            font_size = None
            if hasattr(self.main_window, "_current_font_name") and self.main_window._current_font_name:
                font_name = self.main_window._current_font_name
            if hasattr(self.main_window, "_current_font_size") and self.main_window._current_font_size:
                font_size = int(self.main_window._current_font_size)

            if font_name is None and hasattr(self.main_window, "ui") and hasattr(self.main_window.ui, "font_combo"):
                font_name = self.main_window.ui.font_combo.currentText()
            if font_size is None and hasattr(self.main_window, "ui") and hasattr(self.main_window.ui, "fontsize_box"):
                font_size = int(self.main_window.ui.fontsize_box.value())

            if not font_name:
                font_name = "Consolas"
            if not font_size:
                font_size = 10

            font = QFont(font_name, font_size)
            font.setFixedPitch(True)
            font.setStyleHint(QFont.TypeWriter)
            font.setStyleStrategy(QFont.PreferDefault)
            font.setKerning(False)

            # Apply to watch widgets + dumps/log
            self.edit_expr.setFont(font)
            self.tree_watch.setFont(font)
            self.text_dump.setFont(font)
            self.text_log.setFont(font)
            try:
                self.fb_edit_addr.setFont(font)
            except Exception:
                pass
        except Exception as e:
            self._log_ui(f"Apply font failed: {e}", "warning", rate_key="apply-font-failed", rate_sec=10.0)

    def _set_watch_enabled(self, enabled: bool):
        """Enable/disable Watch area only. Memory dump must always be usable without MAP/ELF."""
        self._watch_enabled = bool(enabled)
        self.edit_expr.setEnabled(bool(enabled))
        self.tree_watch.setEnabled(bool(enabled))

        # Memory dump controls always enabled
        self.edit_addr.setEnabled(True)
        self.spin_size.setEnabled(True)
        self.text_dump.setEnabled(True)
        try:
            self.fb_edit_addr.setEnabled(True)
            self.fb_spin_w.setEnabled(True)
            self.fb_spin_h.setEnabled(True)
            self.fb_combo_fmt.setEnabled(True)
            self.fb_check_auto.setEnabled(True)
            self.fb_btn_refresh.setEnabled(True)
        except Exception:
            pass

        if not enabled:
            self.tree_watch.clear()
            # Keep memory dump usable; only hint for Watch area
            # self._log_ui("Watch disabled (ELF not selected). Memory dump is available.")

    def _should_log(self, key: str, interval_sec: Optional[float] = None) -> bool:
        try:
            import time
            now = time.time()
            sec = float(interval_sec if interval_sec is not None else self._log_rate_default_sec)
            last = self._log_rate.get(key, 0.0)
            if now - last >= sec:
                self._log_rate[key] = now
                return True
            return False
        except Exception:
            return True

    def _log_ui(self, msg: str, level: str = "info", rate_key: Optional[str] = None, rate_sec: Optional[float] = None):
        """Write to python logger + dock log box."""
        if rate_key is not None and not self._should_log(rate_key, rate_sec):
            return

        try:
            if level == "error":
                logger.error(msg)
            elif level == "warning":
                logger.warning(msg)
            else:
                logger.info(msg)
        except Exception:
            pass

        try:
            self.text_log.appendPlainText(msg)
        except Exception:
            pass

        try:
            # also show latest status (one-line)
            self.label_status.setText(msg)
        except Exception:
            pass

    def _select_map(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("watch", "Select MAP file"),
            "",
            "MAP (*.map);;All (*.*)",
        )
        if path:
            self.map_path = path
            self.edit_map.setText(path)
            self._log_ui(f"MAP selected: {path}")
            self._try_enable()

    def _select_elf(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            QCoreApplication.translate("watch", "Select ELF file"),
            "",
            "ELF (*.elf *.out *.axf);;All (*.*)",
        )
        if path:
            self.elf_path = path
            self.edit_elf.setText(path)
            self._log_ui(f"ELF selected: {path}")
            self._try_enable()

    def _try_enable(self):
        # ELF is required; MAP is optional (enhances static/global symbol resolution)
        if self.elf_path:
            ok = self._reload_symbols()
            self._set_watch_enabled(bool(ok))
        else:
            self._set_watch_enabled(False)

    def _reload_symbols(self) -> bool:
        if not self.elf_path:
            self._log_ui("Reload skipped: ELF not selected.", "warning")
            return False
        # MAP optional
        self._map_symbols = {}
        if self.map_path:
            try:
                self._map_symbols = parse_segger_map(self.map_path)
            except Exception as e:
                self._log_ui(f"MAP parse failed: {e}", "error")
                QMessageBox.warning(self, QCoreApplication.translate("watch", "Error"), str(e))
                return False
        try:
            self._dwarf = DwarfIndex(self.elf_path)
            # DwarfIndex may still work in ELF-only/symtab-only mode
            if self._dwarf.variables:
                self._log_ui("DWARF loaded OK.")
            else:
                self._log_ui("ELF loaded (symtab-only mode).")
        except Exception as e:
            # ELF解析失败时降级：仅MAP可用（无类型、无ELF符号）
            self._dwarf = None
            self._log_ui(f"ELF parse failed, MAP-only mode. Error: {e}", "warning")
            QMessageBox.warning(
                self,
                QCoreApplication.translate("watch", "DWARF Parse Failed"),
                QCoreApplication.translate(
                    "watch",
                    "ELF DWARF parsing failed, Watch will run in MAP-only mode.\n\n"
                    "Struct field expansion will be unavailable.\n\nError: %s"
                ) % str(e),
            )

        # Update symbol completer list (MAP + DWARF)
        try:
            names = set(self._map_symbols.keys()) if self._map_symbols else set()
            if self._dwarf is not None:
                names.update(self._dwarf.variables.keys())
                # Also include symtab symbols for ELF-only usage
                try:
                    names.update(self._dwarf.symtab_symbols.keys())
                except Exception:
                    pass
            # Filter out empty names and sort for stable UI
            name_list = sorted([n for n in names if isinstance(n, str) and n.strip()])
            self._all_symbol_names = name_list
            self._symbol_model.setStringList(name_list)
            self._log_ui(
                f"Symbols loaded: MAP={len(self._map_symbols)}; DWARF={'OK' if (self._dwarf is not None and bool(self._dwarf.variables)) else 'OFF'}; Total={len(name_list)}"
            )
        except Exception:
            self._symbol_model.setStringList([])
            self._all_symbol_names = []
            self._log_ui("Failed to build symbol completer list.", "warning")

        # Re-resolve existing watch items
        existing = list(self._watch_items.keys())
        self._watch_items.clear()
        self.tree_watch.clear()
        self._create_input_row()
        for expr in existing:
            self._add_watch(expr)
        return True

    def _create_input_row(self):
        """Create (or recreate) the inline input row at the bottom of the tree."""
        # Recreate every time after clear() to avoid stale widgets
        self._input_item = QTreeWidgetItem(["", ""])
        self._input_item.setData(0, Qt.UserRole, {"kind": "input"})
        self._input_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        try:
            self._input_item.setSizeHint(0, self.tree_watch.fontMetrics().height() * 2)
        except Exception:
            pass
        self.tree_watch.addTopLevelItem(self._input_item)

        self._inline_input = _InlineInputLineEdit(self)
        self.tree_watch.setItemWidget(self._input_item, 0, self._inline_input)
        self._input_item.setText(1, "")

    def _insert_before_input_row(self, item: QTreeWidgetItem):
        """Insert a top-level item before the inline input row."""
        try:
            if self._input_item is not None:
                idx = self.tree_watch.indexOfTopLevelItem(self._input_item)
                if idx >= 0:
                    self.tree_watch.insertTopLevelItem(idx, item)
                    return
        except Exception:
            pass
        self.tree_watch.addTopLevelItem(item)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        try:
            meta = item.data(0, Qt.UserRole)
            if isinstance(meta, dict) and meta.get("kind") == "input":
                if self._inline_input is not None:
                    self._inline_input.setFocus()
                    self._inline_input.selectAll()
        except Exception:
            pass

    def _submit_inline_expr(self, expr: str):
        """Submit expression from inline input."""
        if not expr:
            return
        self._add_watch(expr)
        # Defer clear to next event loop tick: prevents completer/return key handling from restoring text.
        def _clear_later():
            try:
                ed = getattr(self, "_inline_input", None)
                if ed is None:
                    return
                ed.blockSignals(True)
                ed.setText("")
                ed.blockSignals(False)
                ed.setFocus()
                ed.selectAll()
                # Restore global symbol list in completer after submit
                self._symbol_model.setStringList(self._all_symbol_names)
            except Exception:
                return
        try:
            QTimer.singleShot(0, _clear_later)
        except Exception:
            _clear_later()

    def _on_expr_text_edited(self, text: str):
        # Dynamic completion: base symbol list or member/index list based on current expression.
        try:
            candidates = self._build_completion_candidates(text)
            if candidates is None:
                return
            self._symbol_model.setStringList(candidates)
        except Exception:
            # Keep previous completer list if anything goes wrong
            return

    def _build_completion_candidates(self, text: str) -> Optional[List[str]]:
        s = (text or "").strip()
        if not s:
            self._symbol_model.setStringList(self._all_symbol_names)
            return self._all_symbol_names

        # If no member/index syntax, show global symbol list
        if ("." not in s) and ("[" not in s) and ("->" not in s):
            self._symbol_model.setStringList(self._all_symbol_names)
            return self._all_symbol_names

        info = self._parse_expression_for_completion(s)
        if info is None:
            return self._all_symbol_names
        base, completed_steps, mode, prefix, prefix_expr = info

        # Need DWARF types to suggest members
        if self._dwarf is None:
            return self._all_symbol_names

        dv = self._dwarf.lookup(base)
        if dv is None or dv.typ is None:
            return self._all_symbol_names

        cur_typ: Optional[TypeDesc] = dv.typ
        # Walk completed steps to current type
        for kind, val in completed_steps:
            t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
            if t0 is None:
                return self._all_symbol_names
            if kind == "member":
                # pointer-to-struct: treat as target type for completion
                if t0.kind == "pointer" and t0.target is not None:
                    cur_typ = t0.target
                    t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
                    if t0 is None:
                        return self._all_symbol_names
                if t0.kind != "struct":
                    return self._all_symbol_names
                mem = next((m for m in t0.members if m.name == str(val)), None)
                if mem is None:
                    return self._all_symbol_names
                cur_typ = mem.typ
            elif kind == "index":
                idx = int(val)
                if t0.kind == "array" and t0.target is not None:
                    cur_typ = t0.target
                elif t0.kind == "pointer" and t0.target is not None:
                    cur_typ = t0.target
                else:
                    return self._all_symbol_names
            else:
                return self._all_symbol_names

        if mode == "member":
            t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
            if t0 is None:
                return self._all_symbol_names
            if t0.kind == "pointer" and t0.target is not None:
                t0 = self._unwrap_typedef(t0.target) or t0.target
            if t0 is None or t0.kind != "struct":
                return self._all_symbol_names
            pref = (prefix or "")
            mem_names = [m.name for m in t0.members if m.name]
            if pref:
                mem_names = [m for m in mem_names if m.lower().startswith(pref.lower())]
            # Build full-expression candidates
            base_expr = prefix_expr
            return [f"{base_expr}{m}" for m in sorted(mem_names)]

        if mode == "index":
            t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
            if t0 is None:
                return self._all_symbol_names
            # Suggest 0..15 by default
            pref_d = (prefix or "")
            sugg = [str(i) for i in range(16)]
            if pref_d:
                sugg = [x for x in sugg if x.startswith(pref_d)]
            return [f"{prefix_expr}{d}]" for d in sugg]

        return self._all_symbol_names

    def _parse_expression_for_completion(
        self, expr: str
    ) -> Optional[Tuple[str, List[Tuple[str, Union[str, int]]], str, str, str]]:
        """
        Parse expression allowing incomplete last token.
        Returns:
          base, completed_steps, mode('member'|'index'|'none'), prefix, prefix_expr
        prefix_expr is the expression prefix up to where completion should append.
        """
        s = (expr or "").strip()
        if not s:
            return None
        s = s.replace("->", ".")
        i = 0
        n = len(s)

        def read_ident_partial(pos: int) -> Tuple[str, int]:
            j = pos
            while j < n and (s[j].isalnum() or s[j] in ("_", "$")):
                j += 1
            return s[pos:j], j

        # base ident
        if i >= n or not (s[i].isalpha() or s[i] == "_"):
            return None
        base, i = read_ident_partial(i)
        if not base:
            return None

        steps: List[Tuple[str, Union[str, int]]] = []
        mode = "none"
        prefix = ""
        prefix_expr = base

        while i < n:
            if s[i] == ".":
                i += 1
                if i >= n:
                    mode = "member"
                    prefix = ""
                    prefix_expr = s
                    break
                if not (s[i].isalpha() or s[i] == "_"):
                    mode = "member"
                    prefix = ""
                    prefix_expr = s[:i]
                    break
                ident, j = read_ident_partial(i)
                # If ident ends at end or before another delimiter, it may be complete or partial.
                if j == n:
                    mode = "member"
                    prefix = ident
                    prefix_expr = s[:i]  # up to start of ident
                    break
                if j < n and s[j] in (".", "["):
                    # complete member
                    steps.append(("member", ident))
                    prefix_expr = s[:j]
                    i = j
                    continue
                # unknown char -> treat as partial member
                mode = "member"
                prefix = ident
                prefix_expr = s[:i]
                break

            if s[i] == "[":
                i += 1
                # digits optional
                j = i
                while j < n and s[j].isdigit():
                    j += 1
                digits = s[i:j]
                if j >= n:
                    mode = "index"
                    prefix = digits
                    prefix_expr = s[:i]  # up to start digits
                    break
                if s[j] != "]":
                    mode = "index"
                    prefix = digits
                    prefix_expr = s[:i]
                    break
                # Have closing ]
                if digits:
                    steps.append(("index", int(digits)))
                prefix_expr = s[: j + 1]
                i = j + 1
                continue

            # unexpected char
            break

        return base, steps, mode, prefix, prefix_expr

    def _is_target_connected(self) -> bool:
        """Check target connectivity; used to stop refresh timer when disconnected."""
        try:
            session = self.main_window._get_active_device_session()
            if not session or not getattr(session, "is_connected", False) or not session.rtt2uart:
                return False
            jlink = session.rtt2uart.jlink
            lock = getattr(session.rtt2uart, "_jlink_lock", None)
            if not jlink:
                return False
            if lock:
                with lock:
                    return bool(jlink.connected())
            return bool(jlink.connected())
        except Exception:
            return False

    def _refresh_now(self):
        # Manual refresh: refresh watch values (if enabled) + always refresh memory dump once
        if not self._is_target_connected():
            self._refresh_timer.stop()
            self._log_ui("Refresh skipped: Target is not connected.", "warning", rate_key="refresh-not-connected", rate_sec=5.0)
            return
        try:
            if self._watch_enabled:
                for i in range(self.tree_watch.topLevelItemCount()):
                    item = self.tree_watch.topLevelItem(i)
                    meta = item.data(0, Qt.UserRole)
                    if isinstance(meta, dict) and meta.get("kind") == "root":
                        key = meta.get("name")
                        if isinstance(key, str) and key in self._watch_items:
                            self._refresh_item(item, self._watch_items[key])
            # Always refresh memory dump on manual refresh; also enables auto refresh
            self.load_memory_dump(manual=True)
            # Manual refresh for framebuffer too
            try:
                self.load_frame_buffer()
            except Exception:
                pass
        except Exception as e:
            self._log_ui(f"Refresh Now failed: {e}", "warning", rate_key="refresh-now-failed", rate_sec=3.0)

    def _fb_set_zoom(self, zoom: float):
        try:
            z = float(zoom)
            if z < 0.05:
                z = 0.05
            if z > 20.0:
                z = 20.0
            self._fb_zoom = z
            self._fb_update_pixmap()
        except Exception:
            pass

    def _fb_fit_to_view(self):
        try:
            img = self._fb_last_qimage
            if img is None or img.isNull():
                return
            viewport = self.fb_scroll.viewport().size()
            if viewport.width() <= 0 or viewport.height() <= 0:
                return
            zx = viewport.width() / max(1, img.width())
            zy = viewport.height() / max(1, img.height())
            self._fb_set_zoom(min(zx, zy))
        except Exception:
            pass

    def _fb_update_pixmap(self):
        try:
            img = self._fb_last_qimage
            if img is None or img.isNull():
                return
            pm = QPixmap.fromImage(img)
            if float(getattr(self, "_fb_zoom", 1.0)) != 1.0:
                pm = pm.scaled(
                    int(max(1, img.width() * float(self._fb_zoom))),
                    int(max(1, img.height() * float(self._fb_zoom))),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
            self.fb_label.setPixmap(pm)
            self.fb_label.setText("")
        except Exception as e:
            self.fb_label.setPixmap(QPixmap())
            self.fb_label.setText(str(e))

    def _fb_copy_to_clipboard(self):
        try:
            # Copy the actually rendered display result at 1:1:
            # temporarily force zoom=1.0, render pixmap, copy, then restore zoom.
            pm = None
            try:
                prev_zoom = float(getattr(self, "_fb_zoom", 1.0))
                self._fb_zoom = 1.0
                self._fb_update_pixmap()
                pm0 = self.fb_label.pixmap()
                if pm0 is not None and not pm0.isNull():
                    pm = QPixmap(pm0)  # detach
            except Exception:
                pm = None
            finally:
                try:
                    self._fb_zoom = prev_zoom
                    self._fb_update_pixmap()
                except Exception:
                    pass

            if pm is not None and not pm.isNull():
                QGuiApplication.clipboard().setPixmap(pm)
                return

            # Fallback: copy raw 1:1 image if available
            img = getattr(self, "_fb_last_qimage", None)
            if img is not None and not img.isNull():
                QGuiApplication.clipboard().setImage(img.convertToFormat(QImage.Format_ARGB32))
        except Exception:
            pass

    def load_frame_buffer(self):
        """Read framebuffer from target memory and render into an image (non-blocking)."""
        try:
            self._fb_job_id = int(getattr(self, "_fb_job_id", 0)) + 1
            job_id = int(self._fb_job_id)

            addr = _parse_int(self.fb_edit_addr.text())
            w = int(self.fb_spin_w.value())
            h = int(self.fb_spin_h.value())
            fmt = str(self.fb_combo_fmt.currentData() or "ARGB32")

            if addr is None or addr <= 0:
                self.fb_label.setPixmap(QPixmap())
                self.fb_label.setText(QCoreApplication.translate("watch", "No address specified"))
                return
            if w <= 0 or h <= 0:
                self.fb_label.setPixmap(QPixmap())
                self.fb_label.setText(QCoreApplication.translate("watch", "Invalid size"))
                return

            jlink, jlink_lock = self._get_active_jlink()
            if not jlink:
                self.fb_label.setPixmap(QPixmap())
                self.fb_label.setText(QCoreApplication.translate("watch", "No active JLink"))
                return

            self.fb_label.setPixmap(QPixmap())
            self.fb_label.setText(QCoreApplication.translate("watch", "Loading..."))

            import threading

            def _worker():
                try:
                    # Many framebuffers use 4-byte aligned stride per line. Auto-align to improve correctness.
                    if fmt in ("ARGB32", "RGB32"):
                        stride = w * 4
                    elif fmt == "RGB565":
                        stride = w * 2
                    elif fmt == "RGB888":
                        stride = w * 3
                    elif fmt in ("MonoLSB", "MonoMSB"):
                        stride = (w + 7) // 8
                    else:
                        stride = w * 4
                    stride = int(((int(stride) + 3) // 4) * 4)  # 4-byte aligned
                    n = int(stride) * int(h)

                    if jlink_lock:
                        with jlink_lock:
                            raw = bytes(jlink.memory_read8(int(addr), int(n)))
                    else:
                        raw = bytes(jlink.memory_read8(int(addr), int(n)))

                    def _apply():
                        if int(getattr(self, "_fb_job_id", 0)) != int(job_id):
                            return
                        self._fb_last_bytes = raw
                        self._fb_last_meta = {
                            "addr": int(addr),
                            "w": int(w),
                            "h": int(h),
                            "fmt": str(fmt),
                            "stride": int(stride),
                        }
                        self._fb_last_qimage = self._fb_decode_image(raw, w, h, fmt, stride)
                        self._fb_update_pixmap()

                    # Ensure UI update is posted to GUI thread (worker thread may have no event loop)
                    QTimer.singleShot(0, self, _apply)
                except Exception as e:
                    def _err():
                        if int(getattr(self, "_fb_job_id", 0)) != int(job_id):
                            return
                        self.fb_label.setPixmap(QPixmap())
                        self.fb_label.setText(str(e))
                    QTimer.singleShot(0, self, _err)

            threading.Thread(target=_worker, daemon=True, name="framebuffer_loader").start()
        except Exception as e:
            self.fb_label.setPixmap(QPixmap())
            self.fb_label.setText(str(e))

    def _fb_decode_image(self, raw: bytes, w: int, h: int, fmt: str, stride: int) -> QImage:
        """Decode raw framebuffer bytes into QImage."""
        try:
            if fmt == "ARGB32":
                ba = QByteArray(raw)
                img = QImage(ba, w, h, int(stride), QImage.Format_ARGB32)
                return img.copy()
            if fmt == "RGB32":
                ba = QByteArray(raw)
                img = QImage(ba, w, h, int(stride), QImage.Format_RGB32)
                return img.copy()
            if fmt == "RGB888":
                if int(stride) == w * 3:
                    ba = QByteArray(raw)
                    img = QImage(ba, w, h, int(stride), QImage.Format_RGB888)
                    return img.copy()
                # Strip per-line padding
                out = bytearray(w * h * 3)
                for y in range(h):
                    src0 = y * int(stride)
                    src1 = src0 + (w * 3)
                    dst0 = y * (w * 3)
                    out[dst0: dst0 + (w * 3)] = raw[src0:src1]
                ba = QByteArray(bytes(out))
                img = QImage(ba, w, h, w * 3, QImage.Format_RGB888)
                return img.copy()
            if fmt == "RGB565":
                mv = memoryview(raw)
                out = bytearray(w * h * 3)
                oi = 0
                row_bytes = w * 2
                for y in range(h):
                    base = y * int(stride)
                    for x in range(0, row_bytes, 2):
                        i = base + x
                        v = mv[i] | (mv[i + 1] << 8)
                        r = (v >> 11) & 0x1F
                        g = (v >> 5) & 0x3F
                        b = v & 0x1F
                        out[oi] = (r << 3) | (r >> 2)
                        out[oi + 1] = (g << 2) | (g >> 4)
                        out[oi + 2] = (b << 3) | (b >> 2)
                        oi += 3
                ba = QByteArray(bytes(out))
                img = QImage(ba, w, h, w * 3, QImage.Format_RGB888)
                return img.copy()
            if fmt == "MonoLSB":
                ba = QByteArray(raw)
                img = QImage(ba, w, h, int(stride), QImage.Format_MonoLSB)
                return img.copy()
            if fmt == "MonoMSB":
                ba = QByteArray(raw)
                img = QImage(ba, w, h, int(stride), QImage.Format_Mono)
                return img.copy()
        except Exception:
            pass
        return QImage()

    def _on_refresh_interval_changed(self):
        sec = int(self.combo_refresh.currentData() or 0)
        if sec <= 0:
            self._refresh_timer.stop()
            self._log_ui("Refresh interval: Off")
        else:
            # If disconnected, don't start timer
            if not self._is_target_connected():
                self._refresh_timer.stop()
                self._log_ui("Refresh interval set, but target not connected. Timer not started.", "warning", rate_key="timer-not-started", rate_sec=5.0)
                return
            self._refresh_timer.start(sec * 1000)
            self._log_ui(f"Refresh interval: {sec}s")

    def _get_active_jlink(self):
        try:
            session = self.main_window._get_active_device_session()
            if session and session.rtt2uart and session.rtt2uart.jlink:
                return session.rtt2uart.jlink, getattr(session.rtt2uart, "_jlink_lock", None)
        except Exception:
            return None, None
        return None, None

    def _add_watch(self, expr: Optional[str] = None):
        if expr is None:
            expr = self.edit_expr.text().strip()
        if not expr:
            return
        self.edit_expr.clear()
        # Allow ELF-only mode (MAP optional). Require at least one source of symbols.
        if not self._map_symbols and self._dwarf is None:
            QMessageBox.information(
                self,
                QCoreApplication.translate("watch", "Watch"),
                QCoreApplication.translate("watch", "Please select ELF (and optional MAP), then click Reload Symbols."),
            )
            self._log_ui("Add failed: symbols not loaded (Reload Symbols first).", "warning")
            return

        name = expr.strip()
        self._log_ui(f"Add watch: {name}")

        # De-dup: if already exists, just refresh the existing row (do not add a new item)
        if name in self._watch_items:
            try:
                existing_item = self._find_top_level_item_by_expr(name)
                if existing_item is not None:
                    self._refresh_item(existing_item, self._watch_items[name])
                    existing_item.setSelected(True)
                    self.tree_watch.scrollToItem(existing_item)
                else:
                    # Fallback: refresh via model only
                    self._log_ui(f"Refresh existing (no tree item found): {name}", rate_key=f"refresh-exist:{name}", rate_sec=2.0)
                return
            except Exception as e:
                self._log_ui(f"Refresh existing failed: {e}", "warning", rate_key="refresh-exist-failed", rate_sec=2.0)
                return

        # Computed expression support (e.g. 3+4, (float)3.14*44, sym.member*20)
        # Heuristic: contains arithmetic/bitwise operators (excluding '.' and brackets used by member/index paths)
        if re.search(r"(<<|>>|[+\-*/%&|^])", name):
            if self._try_add_computed_expression(name):
                return

        # Expression support: a.b.c, a.b[3], etc.
        if any(x in name for x in (".", "[", "]", "->")):
            resolved = self._resolve_expression(name)
            if resolved is not None:
                r_addr, r_typ, r_size, r_bit = resolved
                model = WatchItemModel(
                    expr=name,
                    addr=int(r_addr),
                    typ=r_typ,
                    size=int(r_size),
                    bit_size=(r_bit.get("bit_size") if r_bit else None),
                    bit_lsb=(r_bit.get("bit_lsb") if r_bit else None),
                    storage_bytes=(r_bit.get("storage_bytes") if r_bit else None),
                )
                self._watch_items[name] = model
                root = QTreeWidgetItem([name, ""])
                root.setData(
                    0,
                    Qt.UserRole,
                    {
                        "kind": "root",
                        "name": name,
                        "addr": int(r_addr),
                        "typ": r_typ,
                        "size": int(r_size),
                        "bit_size": model.bit_size,
                        "bit_lsb": model.bit_lsb,
                        "storage_bytes": model.storage_bytes,
                    },
                )
                self._insert_before_input_row(root)
                # Default collapsed for newly inserted expressions
                root.setExpanded(False)
                self._populate_children(root, r_typ, depth=0, max_depth=3)
                self._refresh_item(root, model)
                self._log_ui(f"Added: {name} @0x{int(r_addr):08X} size=0x{int(r_size):X} type={'DWARF' if r_typ else 'MAP'}")
                return

        ms = lookup_symbol(self._map_symbols, name) if self._map_symbols else None
        dv: Optional[DwarfVariable] = self._dwarf.lookup(name) if self._dwarf is not None else None
        elf_sym = self._dwarf.lookup_symbol_addr(name) if (dv is None and self._dwarf is not None) else None

        if dv is not None:
            addr = dv.address
            typ = dv.typ
            size = typ.size or (ms.size if ms else 0)
        elif elf_sym is not None:
            addr = int(elf_sym[0])
            typ = None
            size = int(elf_sym[1] or (ms.size if ms else 0))
        elif ms is not None:
            addr = ms.address
            typ = None
            size = ms.size
        else:
            # Add placeholder
            item = QTreeWidgetItem([name, QCoreApplication.translate("watch", "symbol not found")])
            self._insert_before_input_row(item)
            self._log_ui(f"Add failed: symbol not found: {name}", "warning")
            return

        if addr == 0:
            item = QTreeWidgetItem([name, QCoreApplication.translate("watch", "address is 0 (not placed)")] )
            self._insert_before_input_row(item)
            self._log_ui(f"Add failed: address is 0 for {name}", "warning")
            return

        model = WatchItemModel(expr=name, addr=addr, typ=typ, size=size)
        self._watch_items[name] = model
        root = QTreeWidgetItem([name, ""])
        # Store full model on the tree item to support recursive refresh/expand
        root.setData(0, Qt.UserRole, {"kind": "root", "name": name, "addr": int(addr), "typ": typ, "size": int(size)})
        self._insert_before_input_row(root)
        # Default collapsed for newly inserted expressions
        root.setExpanded(False)
        self._populate_children(root, typ, depth=0, max_depth=3)
        self._refresh_item(root, model)
        self._log_ui(f"Added: {name} @0x{addr:08X} size=0x{size:X} type={'DWARF' if typ else 'MAP'}")

    def _find_top_level_item_by_expr(self, expr: str) -> Optional[QTreeWidgetItem]:
        """Find existing top-level watch item by its expression string."""
        try:
            for i in range(self.tree_watch.topLevelItemCount()):
                it = self.tree_watch.topLevelItem(i)
                meta = it.data(0, Qt.UserRole)
                if isinstance(meta, dict) and meta.get("kind") == "root" and meta.get("name") == expr:
                    return it
                # Fallback: compare display text
                if (it.text(0) or "") == expr:
                    return it
        except Exception:
            return None
        return None

    def _parse_expression(self, expr: str) -> Optional[Tuple[str, List[Tuple[str, Union[str, int]]]]]:
        """
        Parse expression like:
          base.member1.member2
          base.member[3]
        Returns (base, steps) where steps are:
          ("member", "name") or ("index", 3)
        """
        s = (expr or "").strip()
        if not s:
            return None
        # Normalize "->" to "." (we'll handle pointer deref automatically when needed)
        s = s.replace("->", ".")
        i = 0
        n = len(s)

        def read_ident(pos: int) -> Tuple[Optional[str], int]:
            if pos >= n:
                return None, pos
            # allow leading underscore
            if not (s[pos].isalpha() or s[pos] == "_"):
                return None, pos
            j = pos + 1
            while j < n and (s[j].isalnum() or s[j] in ("_", "$")):
                j += 1
            return s[pos:j], j

        base, i2 = read_ident(i)
        if not base:
            return None
        i = i2
        steps: List[Tuple[str, Union[str, int]]] = []

        while i < n:
            if s[i] == ".":
                ident, j = read_ident(i + 1)
                if not ident:
                    return None
                steps.append(("member", ident))
                i = j
                continue
            if s[i] == "[":
                j = i + 1
                k = j
                while k < n and s[k].isdigit():
                    k += 1
                if k == j:
                    return None
                if k >= n or s[k] != "]":
                    return None
                idx = int(s[j:k], 10)
                steps.append(("index", idx))
                i = k + 1
                continue
            # unsupported token
            return None
        return base, steps

    def _resolve_expression(self, expr: str) -> Optional[Tuple[int, Optional[TypeDesc], int, Optional[Dict[str, int]]]]:
        """
        Resolve expression to (addr, typ, size, bitfield_meta).
        Requires DWARF type information for member/index traversal.
        """
        parsed = self._parse_expression(expr)
        if not parsed:
            return None
        base, steps = parsed
        if self._dwarf is None:
            self._log_ui("Expression resolve failed: no ELF/DWARF loaded.", "warning", rate_key="expr-no-dwarf", rate_sec=3.0)
            return None

        dv = self._dwarf.lookup(base)
        if dv is None:
            # fallback to MAP/ELF symtab base symbol only (no traversal)
            return None

        cur_addr = int(dv.address)
        cur_typ: Optional[TypeDesc] = dv.typ
        bit_meta: Optional[Dict[str, int]] = None

        for kind, val in steps:
            t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
            if t0 is None:
                return None

            if kind == "member":
                mname = str(val)
                # If current is pointer-to-struct, dereference to struct address automatically
                if t0.kind == "pointer" and t0.target is not None:
                    # Need connection to read pointer value
                    if not self._is_target_connected():
                        self._log_ui("Expression requires target connection to dereference pointer.", "warning", rate_key="expr-need-conn", rate_sec=3.0)
                        return None
                    jlink, lock = self._get_active_jlink()
                    if not jlink:
                        return None
                    if lock:
                        with lock:
                            cur_addr = int(self._read_ptr_value(jlink, cur_addr, int(t0.size or 4)))
                    else:
                        cur_addr = int(self._read_ptr_value(jlink, cur_addr, int(t0.size or 4)))
                    cur_typ = t0.target
                    t0 = self._unwrap_typedef(cur_typ) if cur_typ else None
                    if t0 is None:
                        return None

                if t0.kind != "struct":
                    return None
                mem = next((m for m in t0.members if m.name == mname), None)
                if mem is None:
                    return None
                cur_addr = int(cur_addr + int(mem.offset))
                cur_typ = mem.typ
                # Capture bitfield meta if present for final leaf
                if getattr(mem, "bit_size", None) is not None and getattr(mem, "bit_lsb", None) is not None:
                    bit_meta = {
                        "bit_size": int(getattr(mem, "bit_size") or 0),
                        "bit_lsb": int(getattr(mem, "bit_lsb") or 0),
                        "storage_bytes": int(getattr(mem, "storage_bytes") or 1),
                    }
                else:
                    bit_meta = None
                continue

            if kind == "index":
                idx = int(val)
                # array or pointer indexing
                if t0.kind == "array" and t0.target is not None:
                    stride = int(t0.target.size or 1)
                    cur_addr = int(cur_addr + idx * stride)
                    cur_typ = t0.target
                    bit_meta = None
                    continue
                if t0.kind == "pointer" and t0.target is not None:
                    if not self._is_target_connected():
                        self._log_ui("Expression requires target connection to dereference pointer.", "warning", rate_key="expr-need-conn", rate_sec=3.0)
                        return None
                    jlink, lock = self._get_active_jlink()
                    if not jlink:
                        return None
                    if lock:
                        with lock:
                            base_ptr = int(self._read_ptr_value(jlink, cur_addr, int(t0.size or 4)))
                    else:
                        base_ptr = int(self._read_ptr_value(jlink, cur_addr, int(t0.size or 4)))
                    stride = int(t0.target.size or 1)
                    cur_addr = int(base_ptr + idx * stride)
                    cur_typ = t0.target
                    bit_meta = None
                    continue
                return None

        size = int(getattr(self._unwrap_typedef(cur_typ) if cur_typ else None, "size", 0) or 0)
        if size <= 0:
            size = 4
        return cur_addr, cur_typ, size, bit_meta

    # ---------------- Computed expression support ----------------
    _CE_TOKEN_RE = re.compile(
        r"\s*(?:(0x[0-9A-Fa-f]+)|(\d+\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_\$]*)|(<<|>>|[+\-*/%&|^()\\[\\].]))"
    )

    def _try_add_computed_expression(self, expr: str) -> bool:
        # Reject if it is a pure member/index path (we already handle those)
        if any(x in expr for x in (".", "[", "]", "->")) and not re.search(r"(<<|>>|[+\-*/%&|^])", expr):
            return False

        # Validate parse (do not require connection at add-time)
        try:
            _ = self._eval_computed_expression(expr, allow_no_jlink=True)
        except Exception:
            return False

        model = WatchItemModel(expr=expr, addr=0, typ=None, size=0, computed=True)
        self._watch_items[expr] = model
        root = QTreeWidgetItem([expr, ""])
        root.setData(0, Qt.UserRole, {"kind": "root", "name": expr, "addr": 0, "typ": None, "size": 0, "computed": True})
        self._insert_before_input_row(root)
        self._refresh_item(root, model)
        return True

    def _ce_tokenize(self, s: str) -> List[str]:
        out: List[str] = []
        i = 0
        while i < len(s):
            m = self._CE_TOKEN_RE.match(s, i)
            if not m:
                raise ValueError(f"Invalid token near: {s[i:i+16]}")
            tok = m.group(1) or m.group(2) or m.group(3) or m.group(4)
            out.append(tok)
            i = m.end()
        return out

    def _eval_computed_expression(self, expr: str, allow_no_jlink: bool = False) -> Union[int, float]:
        tokens = self._ce_tokenize(expr.replace("->", "."))
        self._ce_tok = tokens
        self._ce_pos = 0
        v = self._ce_parse_expr()
        if self._ce_pos != len(self._ce_tok):
            raise ValueError("Unexpected tokens at end")
        return v

    def _ce_peek(self) -> Optional[str]:
        return self._ce_tok[self._ce_pos] if self._ce_pos < len(self._ce_tok) else None

    def _ce_eat(self, t: str) -> bool:
        if self._ce_peek() == t:
            self._ce_pos += 1
            return True
        return False

    def _ce_expect(self, t: str):
        if not self._ce_eat(t):
            raise ValueError(f"Expected '{t}'")

    # Precedence: | ^ & << >> + - * / %
    def _ce_parse_expr(self) -> Union[int, float]:
        return self._ce_parse_bitor()

    def _ce_parse_bitor(self):
        v = self._ce_parse_bitxor()
        while self._ce_eat("|"):
            v2 = self._ce_parse_bitxor()
            v = int(v) | int(v2)
        return v

    def _ce_parse_bitxor(self):
        v = self._ce_parse_bitand()
        while self._ce_eat("^"):
            v2 = self._ce_parse_bitand()
            v = int(v) ^ int(v2)
        return v

    def _ce_parse_bitand(self):
        v = self._ce_parse_shift()
        while self._ce_eat("&"):
            v2 = self._ce_parse_shift()
            v = int(v) & int(v2)
        return v

    def _ce_parse_shift(self):
        v = self._ce_parse_add()
        while True:
            if self._ce_eat("<<"):
                v2 = self._ce_parse_add()
                v = int(v) << int(v2)
                continue
            if self._ce_eat(">>"):
                v2 = self._ce_parse_add()
                v = int(v) >> int(v2)
                continue
            break
        return v

    def _ce_parse_add(self):
        v = self._ce_parse_mul()
        while True:
            if self._ce_eat("+"):
                v2 = self._ce_parse_mul()
                v = v + v2
                continue
            if self._ce_eat("-"):
                v2 = self._ce_parse_mul()
                v = v - v2
                continue
            break
        return v

    def _ce_parse_mul(self):
        v = self._ce_parse_unary()
        while True:
            if self._ce_eat("*"):
                v2 = self._ce_parse_unary()
                v = v * v2
                continue
            if self._ce_eat("/"):
                v2 = self._ce_parse_unary()
                v = v / v2
                continue
            if self._ce_eat("%"):
                v2 = self._ce_parse_unary()
                v = int(v) % int(v2)
                continue
            break
        return v

    def _ce_parse_unary(self):
        if self._ce_eat("+"):
            return +self._ce_parse_unary()
        if self._ce_eat("-"):
            return -self._ce_parse_unary()
        # C-style cast: (type)unary
        if self._ce_peek() == "(":
            save = self._ce_pos
            self._ce_pos += 1
            tname = self._ce_peek()
            if tname and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tname):
                self._ce_pos += 1
                if self._ce_eat(")"):
                    v = self._ce_parse_unary()
                    return self._ce_apply_cast(tname, v)
            self._ce_pos = save
        return self._ce_parse_primary()

    def _ce_apply_cast(self, tname: str, v: Union[int, float]) -> Union[int, float]:
        t = (tname or "").lower()
        if t in ("float", "double"):
            return float(v)
        if "int" in t or t.endswith("_t") or t in ("char", "short", "long"):
            return int(v)
        return v

    def _ce_parse_primary(self):
        tok = self._ce_peek()
        if tok is None:
            raise ValueError("Unexpected end")
        if tok == "(":
            self._ce_pos += 1
            v = self._ce_parse_expr()
            self._ce_expect(")")
            return v
        if tok.startswith("0x"):
            self._ce_pos += 1
            return int(tok, 16)
        if re.match(r"^\\d+\\.\\d+$", tok):
            self._ce_pos += 1
            return float(tok)
        if re.match(r"^\\d+$", tok):
            self._ce_pos += 1
            return int(tok, 10)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_\\$]*$", tok):
            self._ce_pos += 1
            parts = [tok]
            while True:
                if self._ce_eat("."):
                    ident = self._ce_peek()
                    if not ident or not re.match(r"^[A-Za-z_][A-Za-z0-9_\\$]*$", ident):
                        raise ValueError("Expected member name after '.'")
                    self._ce_pos += 1
                    parts.append(".")
                    parts.append(ident)
                    continue
                if self._ce_eat("["):
                    idx_val = self._ce_parse_expr()
                    self._ce_expect("]")
                    parts.append("[")
                    parts.append(str(int(idx_val)))
                    parts.append("]")
                    continue
                break
            sym_expr = "".join(parts)
            return self._read_symbol_as_number(sym_expr)
        raise ValueError(f"Unexpected token: {tok}")

    def _read_symbol_as_number(self, sym_expr: str) -> Union[int, float]:
        # Resolve address/type (supports bitfield via _resolve_expression)
        resolved = self._resolve_expression(sym_expr) if any(x in sym_expr for x in (".", "[", "]", "->")) else None
        if resolved is not None:
            addr, typ, _size, bit = resolved
            jlink, lock = self._get_active_jlink()
            if not jlink:
                raise ValueError("No active JLink")
            if bit:
                if lock:
                    with lock:
                        return int(self._read_bitfield(jlink, int(addr), int(bit["bit_lsb"]), int(bit["bit_size"]), int(bit["storage_bytes"])))
                return int(self._read_bitfield(jlink, int(addr), int(bit["bit_lsb"]), int(bit["bit_size"]), int(bit["storage_bytes"])))
            t0 = self._unwrap_typedef(typ) if typ else None
            if t0 and t0.kind == "pointer":
                if lock:
                    with lock:
                        return int(self._read_ptr_value(jlink, int(addr), int(t0.size or 4)))
                return int(self._read_ptr_value(jlink, int(addr), int(t0.size or 4)))
            n = int(getattr(t0, "size", 4) or 4) if t0 else 4
            n = max(1, min(n, 8))
            if lock:
                with lock:
                    raw = bytes(jlink.memory_read8(int(addr), n))
            else:
                raw = bytes(jlink.memory_read8(int(addr), n))
            return int.from_bytes(raw, "little", signed=False)

        # Fallback: top-level symbol only (MAP/ELF symtab)
        ms = lookup_symbol(self._map_symbols, sym_expr) if self._map_symbols else None
        dv = self._dwarf.lookup(sym_expr) if self._dwarf is not None else None
        elf_sym = self._dwarf.lookup_symbol_addr(sym_expr) if (dv is None and self._dwarf is not None) else None
        if dv is None and ms is None and elf_sym is None:
            raise ValueError("symbol not found")
        addr = int(dv.address) if dv is not None else (int(elf_sym[0]) if elf_sym is not None else int(ms.address))
        typ = dv.typ if dv is not None else None
        jlink, lock = self._get_active_jlink()
        if not jlink:
            raise ValueError("No active JLink")
        t0 = self._unwrap_typedef(typ) if typ else None
        if t0 and t0.kind == "pointer":
            if lock:
                with lock:
                    return int(self._read_ptr_value(jlink, addr, int(t0.size or 4)))
            return int(self._read_ptr_value(jlink, addr, int(t0.size or 4)))
        n = int(getattr(t0, "size", 4) or 4) if t0 else 4
        n = max(1, min(n, 8))
        if lock:
            with lock:
                raw = bytes(jlink.memory_read8(addr, n))
        else:
            raw = bytes(jlink.memory_read8(addr, n))
        return int.from_bytes(raw, "little", signed=False)

    def _unwrap_typedef(self, typ: Optional[TypeDesc]) -> Optional[TypeDesc]:
        t = typ
        seen = 0
        while t is not None and t.kind == "typedef" and t.target is not None and seen < 16:
            t = t.target
            seen += 1
        return t

    def _as_struct_type(self, typ: Optional[TypeDesc]) -> Optional[TypeDesc]:
        """Return underlying struct type for struct / typedef-to-struct."""
        t = self._unwrap_typedef(typ)
        if t is not None and t.kind == "struct":
            return t
        return None

    def _as_ptr_to_struct_type(self, typ: Optional[TypeDesc]) -> Optional[Tuple[TypeDesc, TypeDesc]]:
        """Return (pointer_type, struct_type) for pointer-to-struct / pointer-to-typedef-to-struct."""
        t = self._unwrap_typedef(typ)
        if t is None or t.kind != "pointer" or t.target is None:
            return None
        target = self._unwrap_typedef(t.target)
        if target is not None and target.kind == "struct":
            return t, target
        return None

    def _populate_children(self, root_item: QTreeWidgetItem, typ: Optional[TypeDesc], depth: int, max_depth: int):
        root_item.takeChildren()
        if not typ:
            return
        if depth >= max_depth:
            return

        # struct / typedef-to-struct
        st = self._as_struct_type(typ)
        if st is not None:
            for m in st.members[:128]:
                child = QTreeWidgetItem([m.name, ""])
                child.setData(
                    0,
                    Qt.UserRole,
                    {
                        "kind": "member",
                        "offset": int(m.offset),
                        "typ": m.typ,
                        "bit_size": getattr(m, "bit_size", None),
                        "bit_lsb": getattr(m, "bit_lsb", None),
                        "storage_bytes": getattr(m, "storage_bytes", None),
                    },
                )
                root_item.addChild(child)
                self._populate_children(child, m.typ, depth + 1, max_depth)
            return

        # pointer-to-struct / pointer-to-typedef-to-struct
        pts = self._as_ptr_to_struct_type(typ)
        if pts is not None:
            _pt, st2 = pts
            for m in st2.members[:128]:
                child = QTreeWidgetItem([m.name, ""])
                child.setData(
                    0,
                    Qt.UserRole,
                    {
                        "kind": "member",
                        "offset": int(m.offset),
                        "typ": m.typ,
                        "bit_size": getattr(m, "bit_size", None),
                        "bit_lsb": getattr(m, "bit_lsb", None),
                        "storage_bytes": getattr(m, "storage_bytes", None),
                    },
                )
                root_item.addChild(child)
                self._populate_children(child, m.typ, depth + 1, max_depth)
            return

        # array
        t0 = self._unwrap_typedef(typ)
        if t0 and t0.kind == "array" and t0.target and t0.count:
            # Show first up to 16 items
            count = min(int(t0.count), 16)
            stride = t0.target.size or 1
            for i in range(count):
                child = QTreeWidgetItem([f"[{i}]", ""])
                child.setData(0, Qt.UserRole, {"kind": "index", "offset": int(i * stride), "typ": t0.target})
                root_item.addChild(child)
                self._populate_children(child, t0.target, depth + 1, max_depth)
            return
        return

    def _remove_selected(self):
        it = self.tree_watch.currentItem()
        if not it:
            return
        # Remove top-level only
        while it.parent():
            it = it.parent()
        key = it.data(0, Qt.UserRole)
        if isinstance(key, str) and key in self._watch_items:
            del self._watch_items[key]
        idx = self.tree_watch.indexOfTopLevelItem(it)
        if idx >= 0:
            self.tree_watch.takeTopLevelItem(idx)

    def _refresh_selected_only(self):
        """Context menu: refresh only the selected entry (top-level), not all."""
        it = self.tree_watch.currentItem()
        if not it:
            return
        # Refresh top-level only
        while it.parent():
            it = it.parent()
        meta = it.data(0, Qt.UserRole)
        expr = None
        if isinstance(meta, dict) and meta.get("kind") == "root":
            expr = meta.get("name")
        if not expr:
            expr = it.text(0)
        if not expr:
            return
        if expr not in self._watch_items:
            return
        self._refresh_item(it, self._watch_items[expr])

    def _add_selected_to_watch(self):
        """Context menu: add selected member/index node as a standalone Watch item."""
        it = self.tree_watch.currentItem()
        if not it:
            return
        expr = self._get_expression_for_item(it)
        if not expr:
            return
        # Avoid duplicates
        if expr in self._watch_items:
            self._log_ui(f"Already exists: {expr}", rate_key=f"add-to-watch-exists:{expr}", rate_sec=2.0)
            return
        self._add_watch(expr)

    # NOTE: inline embedded input row was removed; we use the original top input box.

    def _get_expression_for_item(self, item: QTreeWidgetItem) -> Optional[str]:
        """Build a full expression path for a tree node (root/member/index)."""
        if item is None:
            return None
        # Find root
        root = item
        while root.parent():
            root = root.parent()
        rmeta = root.data(0, Qt.UserRole)
        if not isinstance(rmeta, dict) or rmeta.get("kind") != "root":
            return None
        base_expr = str(rmeta.get("name") or root.text(0) or "").strip()
        if not base_expr:
            return None
        if item is root:
            return base_expr

        # Collect segments from item -> root (excluding root)
        segs: List[str] = []
        cur = item
        while cur is not None and cur is not root:
            seg = (cur.text(0) or "").strip()
            if seg:
                segs.append(seg)
            cur = cur.parent()
        segs.reverse()

        expr = base_expr
        for seg in segs:
            if seg.startswith("[") and seg.endswith("]"):
                expr += seg
            else:
                expr += "." + seg
        return expr

    def _view_memory_for_selected(self):
        """Context menu: fill memory dump address/size from selected watch node and load."""
        it = self.tree_watch.currentItem()
        if not it:
            return
        if not self._is_target_connected():
            self._log_ui("View Memory failed: Target is not connected.", "warning", rate_key="view-mem-not-connected", rate_sec=5.0)
            return

        addr, size = self._get_effective_address_and_size(it)
        if addr is None:
            self._log_ui("View Memory failed: Cannot resolve address.", "warning", rate_key="view-mem-no-addr", rate_sec=3.0)
            return

        try:
            self.edit_addr.setText(f"0x{int(addr):08X}")
            if size and int(size) > 0:
                self.spin_size.setValue(min(int(size), self.spin_size.maximum()))
            self.load_memory_dump(manual=True)
        except Exception as e:
            self._log_ui(f"View Memory failed: {e}", "warning", rate_key="view-mem-failed", rate_sec=3.0)

    def _get_effective_address_and_size(self, item: QTreeWidgetItem) -> Tuple[Optional[int], Optional[int]]:
        """Resolve current selected node to an absolute memory address and suggested size."""
        # Find top-level root
        root = item
        while root.parent():
            root = root.parent()
        rmeta = root.data(0, Qt.UserRole)
        if not isinstance(rmeta, dict) or rmeta.get("kind") != "root":
            return None, None
        if rmeta.get("computed"):
            return None, None

        base_var_addr = int(rmeta.get("addr") or 0)
        root_typ = rmeta.get("typ")
        if base_var_addr == 0:
            return None, None

        jlink, lock = self._get_active_jlink()
        if not jlink:
            return None, None

        # Compute base address for children:
        # - struct: base is the variable address
        # - pointer-to-struct: base is the dereferenced pointer value
        base_addr = None
        try:
            t0 = self._unwrap_typedef(root_typ) if root_typ else None
            if t0 is not None and t0.kind == "struct":
                base_addr = base_var_addr
            elif t0 is not None and t0.kind == "pointer":
                pts = self._as_ptr_to_struct_type(t0)
                if pts is not None:
                    if lock:
                        with lock:
                            base_addr = self._read_ptr_value(jlink, base_var_addr, int(t0.size or 4))
                    else:
                        base_addr = self._read_ptr_value(jlink, base_var_addr, int(t0.size or 4))
                else:
                    # Normal pointer: use pointed value as address (dereference once)
                    if lock:
                        with lock:
                            base_addr = self._read_ptr_value(jlink, base_var_addr, int(t0.size or 4))
                    else:
                        base_addr = self._read_ptr_value(jlink, base_var_addr, int(t0.size or 4))
            elif t0 is not None and t0.kind == "array":
                base_addr = base_var_addr
            else:
                base_addr = base_var_addr
        except Exception:
            base_addr = base_var_addr

        # Walk down from root to selected item accumulating offsets
        off = 0
        cur = item
        while cur is not None and cur is not root:
            cmeta = cur.data(0, Qt.UserRole)
            if isinstance(cmeta, dict) and cmeta.get("kind") in ("member", "index"):
                off += int(cmeta.get("offset") or 0)
            cur = cur.parent()

        addr = (int(base_addr) + int(off)) if base_addr is not None else None

        # Suggested size: prefer type size from selected node meta (member/index) or root type
        size = None
        try:
            cmeta = item.data(0, Qt.UserRole)
            ctyp = None
            if isinstance(cmeta, dict):
                ctyp = cmeta.get("typ")
            if ctyp is None and item is root:
                ctyp = root_typ
            tsel = self._unwrap_typedef(ctyp) if ctyp else None
            if tsel is not None:
                if getattr(tsel, "size", 0):
                    size = int(tsel.size)
                elif tsel.kind == "pointer":
                    size = int(tsel.size or 4)
        except Exception:
            size = None

        # Fallback: keep current spinbox if unknown, otherwise default 256
        if not size:
            try:
                size = int(self.spin_size.value() or 256)
            except Exception:
                size = 256
        return addr, size

    def refresh_all(self):
        # Stop timer when disconnected to avoid useless refresh/log spam
        if not self._is_target_connected():
            if self._refresh_timer.isActive():
                self._refresh_timer.stop()
            self._log_ui("Auto refresh stopped: Target is not connected.", "warning", rate_key="auto-refresh-stopped", rate_sec=10.0)
            return
        # If not connected, avoid spamming; UI will show errors on items
        # Refresh watch values
        if self._watch_enabled:
            for i in range(self.tree_watch.topLevelItemCount()):
                item = self.tree_watch.topLevelItem(i)
                meta = item.data(0, Qt.UserRole)
                if isinstance(meta, dict) and meta.get("kind") == "root":
                    key = meta.get("name")
                    if isinstance(key, str) and key in self._watch_items:
                        self._refresh_item(item, self._watch_items[key])
        # Memory dump auto refresh (if enabled interval)
        if self._memory_auto_enabled and self.combo_refresh.currentData() and int(self.combo_refresh.currentData()) > 0:
            self.load_memory_dump(manual=False)

        # Frame buffer auto refresh (independent from MAP/ELF)
        try:
            if hasattr(self, "fb_check_auto") and self.fb_check_auto.isChecked():
                self.load_frame_buffer()
        except Exception:
            pass

    def _read_ptr_value(self, jlink, addr: int, ptr_size: int) -> int:
        psz = int(ptr_size or 4)
        raw = bytes(jlink.memory_read8(int(addr), min(psz, 8)))
        return int.from_bytes(raw[:min(psz, 8)], "little", signed=False)

    def _read_bytes(self, jlink, addr: int, size: int) -> bytes:
        n = int(size or 0)
        if n <= 0:
            return b""
        return bytes(jlink.memory_read8(int(addr), n))

    def _read_bitfield(self, jlink, addr: int, bit_lsb: int, bit_size: int, storage_bytes: int) -> int:
        n = int(storage_bytes or 1)
        if n <= 0:
            n = 1
        raw = bytes(jlink.memory_read8(int(addr), n))
        base = int.from_bytes(raw, "little", signed=False)
        shift = int(bit_lsb)
        bsz = int(bit_size)
        if bsz <= 0:
            return 0
        if bsz >= 64:
            mask = (2**64) - 1
        else:
            mask = (1 << bsz) - 1
        return (base >> shift) & mask

    def _format_byte_preview(self, data: bytes, max_len: int = 32) -> str:
        if not data:
            return ""
        head = data[: int(max_len)]
        hex_part = " ".join(f"{b:02X}" for b in head)
        if len(data) > max_len:
            return f"{hex_part} ..."
        return hex_part

    def _try_format_char_array(self, jlink, addr: int, typ: TypeDesc) -> Optional[str]:
        """If typ is char/uint8-like array, return printable string preview."""
        try:
            t0 = self._unwrap_typedef(typ)
            if not t0 or t0.kind != "array" or not t0.target or not t0.count:
                return None
            tgt = self._unwrap_typedef(t0.target)
            if not tgt or tgt.kind != "base":
                return None
            if (tgt.size or 0) != 1:
                return None
            name = (tgt.name or "").lower()
            if "char" not in name and "int8" not in name and "uint8" not in name and "signed char" not in name and "unsigned char" not in name:
                return None
            data = self._read_bytes(jlink, addr, int(t0.count))
            if not data:
                return None
            if b"\x00" in data:
                data = data.split(b"\x00", 1)[0]
            # Keep it short; avoid huge strings
            data = data[:64]
            try:
                s = data.decode("utf-8", errors="ignore")
            except Exception:
                s = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
            return f"\"{s}\""
        except Exception:
            return None

    def _refresh_tree(self, item: QTreeWidgetItem, jlink, lock, addr: int, typ: Optional[TypeDesc], size_fallback: int):
        """Recursively refresh a node and its children. addr is the node address (or pointer variable address)."""
        t0 = self._unwrap_typedef(typ) if typ else None

        # Determine base address for children (struct base or dereferenced pointer base)
        child_base = None
        if t0 is not None and t0.kind == "struct":
            item.setText(1, "<struct>")
            child_base = int(addr)
        elif t0 is not None and t0.kind == "pointer":
            pts = self._as_ptr_to_struct_type(t0)
            if pts is not None:
                # pointer-to-struct: display pointer value, use it as base for children
                ptr_val = self._read_ptr_value(jlink, int(addr), int(t0.size or 4))
                item.setText(1, f"0x{ptr_val:08X}" if ptr_val else "NULL")
                child_base = int(ptr_val) if ptr_val else 0
            else:
                # normal pointer
                item.setText(1, self._read_scalar_hex(jlink, int(addr), int(t0.size or 4)))
                child_base = None
        elif t0 is not None and t0.kind == "array":
            # For arrays, children are at base+offset
            child_base = int(addr)
            # Prefer string preview for char/uint8 arrays
            s = None
            try:
                s = self._try_format_char_array(jlink, int(addr), t0)
            except Exception:
                s = None
            if s:
                item.setText(1, s)
            else:
                # preview first bytes
                preview_len = min(int(t0.size or 16) or 16, 32)
                data = self._read_bytes(jlink, int(addr), max(preview_len, 1))
                item.setText(1, self._format_byte_preview(data, max_len=32))
        else:
            # scalar/unknown
            item.setText(1, self._read_value(jlink, int(addr), typ, size_fallback))
            child_base = None

        # Refresh children if any
        if item.childCount() <= 0:
            return
        for ci in range(item.childCount()):
            ch = item.child(ci)
            cmeta = ch.data(0, Qt.UserRole)
            if not isinstance(cmeta, dict):
                continue
            if cmeta.get("kind") in ("member", "index"):
                off = int(cmeta.get("offset") or 0)
                ctyp = cmeta.get("typ")
                if child_base is None:
                    ch.setText(1, "NULL")
                    continue
                caddr = int(child_base) + off
                bsz = cmeta.get("bit_size")
                blsb = cmeta.get("bit_lsb")
                sbytes = cmeta.get("storage_bytes")
                if bsz is not None and blsb is not None:
                    try:
                        val = self._read_bitfield(jlink, caddr, int(blsb), int(bsz), int(sbytes or 1))
                        ch.setText(1, str(val))
                    except Exception:
                        self._refresh_tree(ch, jlink, lock, caddr, ctyp, getattr(ctyp, "size", 0) if ctyp else 4)
                else:
                    self._refresh_tree(ch, jlink, lock, caddr, ctyp, getattr(ctyp, "size", 0) if ctyp else 4)

    def _refresh_item(self, item: QTreeWidgetItem, model: WatchItemModel):
        jlink, lock = self._get_active_jlink()
        if not jlink:
            item.setText(1, QCoreApplication.translate("watch", "No active JLink"))
            return
        try:
            if getattr(model, "computed", False):
                def _read_ce():
                    v = self._eval_computed_expression(model.expr)
                    if isinstance(v, float):
                        item.setText(1, f"{v:g}")
                    else:
                        item.setText(1, str(int(v)))
                if lock:
                    with lock:
                        _read_ce()
                else:
                    _read_ce()
                return

            # Bitfield leaf expression: show extracted bits
            meta = item.data(0, Qt.UserRole)
            if isinstance(meta, dict) and meta.get("kind") == "root":
                bsz = meta.get("bit_size")
                blsb = meta.get("bit_lsb")
                sbytes = meta.get("storage_bytes")
                if bsz is not None and blsb is not None:
                    def _read_bf():
                        v = self._read_bitfield(jlink, int(model.addr), int(blsb), int(bsz), int(sbytes or 1))
                        item.setText(1, str(v))
                    if lock:
                        with lock:
                            _read_bf()
                    else:
                        _read_bf()
                    return

            if lock:
                with lock:
                    self._refresh_tree(item, jlink, lock, int(model.addr), model.typ, int(model.size or 4))
            else:
                self._refresh_tree(item, jlink, lock, int(model.addr), model.typ, int(model.size or 4))
        except Exception as e:
            item.setText(1, str(e))
            emsg = str(e)
            if "Target is not connected" in emsg:
                # Rate limit hard to avoid console spam
                self._log_ui(
                    f"Read failed: {model.expr} @0x{model.addr:08X}: {emsg}",
                    "warning",
                    rate_key="target-not-connected",
                    rate_sec=10.0,
                )
            else:
                self._log_ui(
                    f"Read failed: {model.expr} @0x{model.addr:08X}: {emsg}",
                    "warning",
                    rate_key=f"read-failed:{model.expr}",
                    rate_sec=3.0,
                )

    def _read_value(self, jlink, addr: int, typ: Optional[TypeDesc], size_fallback: int = 4) -> str:
        # Base types only for now; for unknown, show hex bytes.
        if typ and typ.kind in ("base", "typedef", "enum"):
            size = typ.size or size_fallback
            return self._read_scalar_hex(jlink, addr, size)
        if typ and typ.kind == "pointer":
            size = typ.size or 4
            return self._read_scalar_hex(jlink, addr, size)
        if typ and typ.kind == "array":
            # show first 16 bytes
            data = bytes(jlink.memory_read8(addr, min(16, typ.size or 16)))
            return " ".join(f"{b:02X}" for b in data)
        if typ and typ.kind == "struct":
            return "<struct>"
        # Unknown: use fallback size up to 16
        size = size_fallback if size_fallback > 0 else 4
        data = bytes(jlink.memory_read8(addr, min(16, size)))
        return " ".join(f"{b:02X}" for b in data)

    def _read_scalar_hex(self, jlink, addr: int, size: int) -> str:
        size = int(size)
        if size <= 0:
            size = 4
        data = bytes(jlink.memory_read8(addr, min(size, 8)))
        val = int.from_bytes(data[:min(size, 8)], "little", signed=False)
        return f"0x{val:0{min(size, 8)*2}X}"

    def load_memory_dump(self, manual: bool = True):
        jlink, lock = self._get_active_jlink()
        if not jlink:
            self.text_dump.setPlainText(QCoreApplication.translate("watch", "No active JLink"))
            self._log_ui("Memory dump load failed: no active JLink.", "warning", rate_key="mem-no-jlink", rate_sec=10.0)
            return
        addr = _parse_int(self.edit_addr.text())
        if addr is None:
            self.text_dump.setPlainText(QCoreApplication.translate("watch", "Invalid address"))
            self._log_ui("Memory dump load failed: invalid address.", "warning", rate_key="mem-bad-addr", rate_sec=5.0)
            return
        size = int(self.spin_size.value())
        try:
            if lock:
                with lock:
                    data = bytes(jlink.memory_read8(addr, size))
            else:
                data = bytes(jlink.memory_read8(addr, size))
            self.text_dump.setPlainText(_format_hex_dump(addr, data))
            self._log_ui(f"Memory dump loaded: 0x{addr:08X} size={size}")
            # Enable auto refresh only after a manual load
            if manual:
                self._memory_auto_enabled = True
        except Exception as e:
            self.text_dump.setPlainText(str(e))
            emsg = str(e)
            if "Target is not connected" in emsg:
                self._log_ui(
                    f"Memory dump read failed: 0x{addr:08X} size={size}: {emsg}",
                    "warning",
                    rate_key="mem-target-not-connected",
                    rate_sec=10.0,
                )
            else:
                self._log_ui(
                    f"Memory dump read failed: 0x{addr:08X} size={size}: {emsg}",
                    "warning",
                    rate_key="mem-read-failed",
                    rate_sec=3.0,
                )


