from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QCoreApplication, QTimer, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCompleter,
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
)
from PySide6.QtCore import QStringListModel

from map_parser import parse_segger_map, lookup_symbol
from watch_dwarf import DwarfIndex, TypeDesc, DwarfVariable

logger = logging.getLogger(__name__)


@dataclass
class WatchItemModel:
    expr: str
    addr: int
    typ: Optional[TypeDesc]
    size: int


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

        self.label_status = QLabel(QCoreApplication.translate("watch", "Select MAP and ELF to enable."))
        self.label_status.setWordWrap(True)

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
        form.addRow(QCoreApplication.translate("watch", "MAP"), w_map)

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
        btn_add = QPushButton(QCoreApplication.translate("watch", "Add"))
        # QPushButton.clicked emits a bool argument; avoid it being treated as expr parameter.
        btn_add.clicked.connect(lambda _checked=False: self._add_watch())
        add_row.addWidget(self.edit_expr, 1)
        add_row.addWidget(btn_add)
        watch_layout.addLayout(add_row)

        self.tree_watch = QTreeWidget()
        self.tree_watch.setHeaderLabels([
            QCoreApplication.translate("watch", "Expression"),
            QCoreApplication.translate("watch", "Value"),
        ])
        self.tree_watch.setColumnWidth(0, 260)
        self.tree_watch.setContextMenuPolicy(Qt.ActionsContextMenu)
        act_del = QAction(QCoreApplication.translate("watch", "Remove"), self.tree_watch)
        act_del.triggered.connect(self._remove_selected)
        self.tree_watch.addAction(act_del)

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

        splitter.addWidget(watch_box)

        # Memory dump area
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

        splitter.addWidget(mem_box)
        splitter.setStretchFactor(0, 2)
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

        if not enabled:
            self.tree_watch.clear()
            # Keep memory dump usable; only hint for Watch area
            self._log_ui("Watch disabled (MAP+ELF not selected). Memory dump is available.")

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
        if self.map_path and self.elf_path:
            ok = self._reload_symbols()
            self._set_watch_enabled(bool(ok))
        else:
            self._set_watch_enabled(False)

    def _reload_symbols(self) -> bool:
        if not (self.map_path and self.elf_path):
            self._log_ui("Reload skipped: MAP/ELF not selected.", "warning")
            return False
        try:
            self._map_symbols = parse_segger_map(self.map_path)
        except Exception as e:
            self._log_ui(f"MAP parse failed: {e}", "error")
            QMessageBox.warning(self, QCoreApplication.translate("watch", "Error"), str(e))
            return False
        try:
            self._dwarf = DwarfIndex(self.elf_path)
            self._log_ui("DWARF loaded OK.")
        except Exception as e:
            # DWARF解析失败时降级：仍可使用MAP符号与Memory Dump，结构体字段展开不可用
            self._dwarf = None
            self._log_ui(f"DWARF parse failed, MAP-only mode. Error: {e}", "warning")
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
            # Filter out empty names and sort for stable UI
            name_list = sorted([n for n in names if isinstance(n, str) and n.strip()])
            self._symbol_model.setStringList(name_list)
            self._log_ui(
                f"Symbols loaded: MAP={len(self._map_symbols)}; DWARF={'OK' if self._dwarf is not None else 'OFF'}; Total={len(name_list)}"
            )
        except Exception:
            self._symbol_model.setStringList([])
            self._log_ui("Failed to build symbol completer list.", "warning")

        # Re-resolve existing watch items
        existing = list(self._watch_items.keys())
        self._watch_items.clear()
        self.tree_watch.clear()
        for expr in existing:
            self._add_watch(expr)
        return True

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
        except Exception as e:
            self._log_ui(f"Refresh Now failed: {e}", "warning", rate_key="refresh-now-failed", rate_sec=3.0)

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
        # Allow MAP-only mode (DWARF may be unavailable)
        if not self._map_symbols:
            QMessageBox.information(
                self,
                QCoreApplication.translate("watch", "Watch"),
                QCoreApplication.translate("watch", "Please select MAP and ELF, then click Reload Symbols."),
            )
            self._log_ui("Add failed: symbols not loaded (Reload Symbols first).", "warning")
            return

        name = expr.strip()
        self._log_ui(f"Add watch: {name}")
        ms = lookup_symbol(self._map_symbols, name)
        dv: Optional[DwarfVariable] = self._dwarf.lookup(name) if self._dwarf is not None else None

        if dv is not None:
            addr = dv.address
            typ = dv.typ
            size = typ.size or (ms.size if ms else 0)
        elif ms is not None:
            addr = ms.address
            typ = None
            size = ms.size
        else:
            # Add placeholder
            item = QTreeWidgetItem([name, QCoreApplication.translate("watch", "symbol not found")])
            self.tree_watch.addTopLevelItem(item)
            self._log_ui(f"Add failed: symbol not found: {name}", "warning")
            return

        if addr == 0:
            item = QTreeWidgetItem([name, QCoreApplication.translate("watch", "address is 0 (not placed)")] )
            self.tree_watch.addTopLevelItem(item)
            self._log_ui(f"Add failed: address is 0 for {name}", "warning")
            return

        model = WatchItemModel(expr=name, addr=addr, typ=typ, size=size)
        self._watch_items[name] = model
        root = QTreeWidgetItem([name, ""])
        # Store full model on the tree item to support recursive refresh/expand
        root.setData(0, Qt.UserRole, {"kind": "root", "name": name, "addr": int(addr), "typ": typ, "size": int(size)})
        self.tree_watch.addTopLevelItem(root)
        root.setExpanded(True)
        self._populate_children(root, typ, depth=0, max_depth=3)
        self._refresh_item(root, model)
        self._log_ui(f"Added: {name} @0x{addr:08X} size=0x{size:X} type={'DWARF' if typ else 'MAP'}")

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
                child.setData(0, Qt.UserRole, {"kind": "member", "offset": int(m.offset), "typ": m.typ})
                root_item.addChild(child)
                self._populate_children(child, m.typ, depth + 1, max_depth)
            return

        # pointer-to-struct / pointer-to-typedef-to-struct
        pts = self._as_ptr_to_struct_type(typ)
        if pts is not None:
            _pt, st2 = pts
            for m in st2.members[:128]:
                child = QTreeWidgetItem([m.name, ""])
                child.setData(0, Qt.UserRole, {"kind": "member", "offset": int(m.offset), "typ": m.typ})
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

    def _read_ptr_value(self, jlink, addr: int, ptr_size: int) -> int:
        psz = int(ptr_size or 4)
        raw = bytes(jlink.memory_read8(int(addr), min(psz, 8)))
        return int.from_bytes(raw[:min(psz, 8)], "little", signed=False)

    def _read_bytes(self, jlink, addr: int, size: int) -> bytes:
        n = int(size or 0)
        if n <= 0:
            return b""
        return bytes(jlink.memory_read8(int(addr), n))

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
                self._refresh_tree(ch, jlink, lock, caddr, ctyp, getattr(ctyp, "size", 0) if ctyp else 4)

    def _refresh_item(self, item: QTreeWidgetItem, model: WatchItemModel):
        jlink, lock = self._get_active_jlink()
        if not jlink:
            item.setText(1, QCoreApplication.translate("watch", "No active JLink"))
            return
        try:
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


