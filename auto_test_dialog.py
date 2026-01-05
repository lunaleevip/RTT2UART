from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from PySide6.QtCore import QCoreApplication

from config_manager import config_manager


@dataclass
class AutoTestRule:
    enabled: bool = False
    trigger_type: str = "text"  # "text" | "interval"
    trigger_text: str = ""
    interval_sec: int = 1
    action_type: str = "send"  # "send" | "restart"
    action_text: str = ""

    # runtime
    last_fire_ts: float = 0.0
    next_fire_ts: float = 0.0
    status: str = "Disabled"

    def to_config(self) -> Dict[str, Any]:
        d = asdict(self)
        # strip runtime fields
        for k in ("last_fire_ts", "next_fire_ts", "status"):
            d.pop(k, None)
        return d


class AutoTestEngine(QObject):
    rule_status_changed = Signal(int, str)

    def __init__(self, main_window):
        super().__init__(main_window)
        self._main_window = main_window
        self._rules: List[AutoTestRule] = [AutoTestRule() for _ in range(3)]
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(1000)

        self._load_from_config()

    def _load_from_config(self):
        raw = config_manager.get_auto_test_rules()
        rules: List[AutoTestRule] = []
        for i in range(3):
            r = AutoTestRule()
            if i < len(raw) and isinstance(raw[i], dict):
                d = raw[i]
                try:
                    r.enabled = bool(d.get("enabled", False))
                    r.trigger_type = str(d.get("trigger_type", "text") or "text")
                    r.trigger_text = str(d.get("trigger_text", "") or "")
                    r.interval_sec = int(d.get("interval_sec", 1) or 1)
                    r.action_type = str(d.get("action_type", "send") or "send")
                    r.action_text = str(d.get("action_text", "") or "")
                except Exception:
                    pass
            rules.append(r)
        self.set_rules(rules, persist=False)

    def set_rules(self, rules: List[AutoTestRule], persist: bool = True):
        # normalize to 3
        self._rules = []
        for i in range(3):
            self._rules.append(rules[i] if i < len(rules) else AutoTestRule())
        self._rearm_all()
        self._publish_all_status()
        if persist:
            try:
                config_manager.set_auto_test_rules([r.to_config() for r in self._rules])
                config_manager.save_config()
            except Exception:
                pass

    def get_rules(self) -> List[AutoTestRule]:
        return list(self._rules)

    def _rearm_all(self):
        now = time.time()
        for i, r in enumerate(self._rules):
            if not r.enabled:
                r.status = QCoreApplication.translate("autotest", "Disabled")
                r.next_fire_ts = 0.0
                continue
            if r.trigger_type == "interval":
                sec = max(1, int(r.interval_sec or 1))
                r.next_fire_ts = now + sec
                r.status = QCoreApplication.translate("autotest", "Waiting")
            else:
                r.next_fire_ts = 0.0
                r.status = QCoreApplication.translate("autotest", "Waiting")

    def _publish_all_status(self):
        for i, r in enumerate(self._rules):
            self.rule_status_changed.emit(i, r.status)

    def on_new_text(self, _tab_index: int, text: str):
        # Called from Worker when new text arrives (already line-framed).
        if not text:
            return
        now = time.time()
        for i, r in enumerate(self._rules):
            if not r.enabled:
                continue
            if r.trigger_type != "text":
                continue
            kw = (r.trigger_text or "").strip()
            if not kw:
                continue
            # rate limit: 1s
            if (now - float(r.last_fire_ts or 0.0)) < 1.0:
                continue
            if kw in text:
                self._fire(i, reason="text")

    def _on_tick(self):
        now = time.time()
        for i, r in enumerate(self._rules):
            if not r.enabled:
                continue
            if r.trigger_type != "interval":
                continue
            sec = max(1, int(r.interval_sec or 1))
            if r.next_fire_ts <= 0.0:
                r.next_fire_ts = now + sec
            if now >= r.next_fire_ts:
                self._fire(i, reason="interval")
                r.next_fire_ts = now + sec
            else:
                remain = int(r.next_fire_ts - now + 0.999)
                r.status = QCoreApplication.translate("autotest", "Next in %ds") % remain
                self.rule_status_changed.emit(i, r.status)

    def _fire(self, idx: int, reason: str):
        try:
            r = self._rules[idx]
        except Exception:
            return
        now = time.time()
        r.last_fire_ts = now
        r.status = QCoreApplication.translate("autotest", "Triggered")
        self.rule_status_changed.emit(idx, r.status)

        try:
            if r.action_type == "restart":
                # F9 behavior
                if hasattr(self._main_window, "restart_app_execute"):
                    self._main_window.restart_app_execute()
                return

            # send command
            cmd = (r.action_text or "").strip()
            if not cmd:
                r.status = QCoreApplication.translate("autotest", "Error: empty command")
                self.rule_status_changed.emit(idx, r.status)
                return

            # Reuse existing send pipeline: fill cmd_buffer then send.
            try:
                if hasattr(self._main_window, "ui") and hasattr(self._main_window.ui, "cmd_buffer"):
                    self._main_window.ui.cmd_buffer.setCurrentText(cmd)
                if hasattr(self._main_window, "on_pushButton_clicked"):
                    self._main_window.on_pushButton_clicked()
            except Exception as e:
                r.status = QCoreApplication.translate("autotest", "Error: %s") % str(e)
                self.rule_status_changed.emit(idx, r.status)
        finally:
            # keep waiting state for text trigger; interval will update on next tick
            if r.enabled and r.trigger_type == "text":
                r.status = QCoreApplication.translate("autotest", "Waiting")
                self.rule_status_changed.emit(idx, r.status)


class AutoTestDialog(QDialog):
    def __init__(self, main_window, engine: AutoTestEngine):
        super().__init__(main_window)
        self._main_window = main_window
        self._engine = engine

        self.setWindowTitle(QCoreApplication.translate("autotest", "Auto Test"))
        self.setModal(False)

        root = QVBoxLayout(self)
        grid = QGridLayout()
        root.addLayout(grid)

        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Enable")), 0, 0)
        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Trigger")), 0, 1)
        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Param")), 0, 2)
        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Action")), 0, 3)
        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Command")), 0, 4)
        grid.addWidget(QLabel(QCoreApplication.translate("autotest", "Status")), 0, 5)

        self._rows: List[Dict[str, Any]] = []
        rules = self._engine.get_rules()
        for i in range(3):
            row: Dict[str, Any] = {}
            r = rules[i] if i < len(rules) else AutoTestRule()

            chk = QCheckBox()
            chk.setChecked(bool(r.enabled))
            row["chk"] = chk

            combo_trig = QComboBox()
            combo_trig.addItem(QCoreApplication.translate("autotest", "Text"), "text")
            combo_trig.addItem(QCoreApplication.translate("autotest", "Interval(s)"), "interval")
            combo_trig.setCurrentIndex(0 if r.trigger_type != "interval" else 1)
            row["combo_trig"] = combo_trig

            edit_kw = QLineEdit()
            edit_kw.setText(r.trigger_text or "")
            spin_sec = QSpinBox()
            spin_sec.setRange(1, 3600)
            spin_sec.setValue(max(1, int(r.interval_sec or 1)))
            row["edit_kw"] = edit_kw
            row["spin_sec"] = spin_sec

            param_box = QWidget()
            param_lay = QHBoxLayout(param_box)
            param_lay.setContentsMargins(0, 0, 0, 0)
            param_lay.addWidget(edit_kw)
            param_lay.addWidget(spin_sec)
            row["param_box"] = param_box

            combo_act = QComboBox()
            combo_act.addItem(QCoreApplication.translate("autotest", "Send Command"), "send")
            combo_act.addItem(QCoreApplication.translate("autotest", "Restart (F9)"), "restart")
            combo_act.setCurrentIndex(0 if r.action_type != "restart" else 1)
            row["combo_act"] = combo_act

            edit_cmd = QLineEdit()
            edit_cmd.setText(r.action_text or "")
            row["edit_cmd"] = edit_cmd

            lab_status = QLabel(r.status or QCoreApplication.translate("autotest", "Disabled"))
            row["lab_status"] = lab_status

            grid.addWidget(chk, i + 1, 0)
            grid.addWidget(combo_trig, i + 1, 1)
            grid.addWidget(param_box, i + 1, 2)
            grid.addWidget(combo_act, i + 1, 3)
            grid.addWidget(edit_cmd, i + 1, 4)
            grid.addWidget(lab_status, i + 1, 5)

            self._rows.append(row)

            def _bind(idx: int):
                chk.stateChanged.connect(lambda _v: self._apply_ui_to_engine())
                combo_trig.currentIndexChanged.connect(lambda _v: self._on_row_mode_changed(idx))
                edit_kw.editingFinished.connect(self._apply_ui_to_engine)
                spin_sec.valueChanged.connect(lambda _v: self._apply_ui_to_engine())
                combo_act.currentIndexChanged.connect(lambda _v: self._on_action_changed(idx))
                edit_cmd.editingFinished.connect(self._apply_ui_to_engine)

            _bind(i)

            self._on_row_mode_changed(i)
            self._on_action_changed(i)

        btn_row = QHBoxLayout()
        root.addLayout(btn_row)
        btn_row.addStretch(1)
        btn_close = QPushButton(QCoreApplication.translate("autotest", "Close"))
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        self._engine.rule_status_changed.connect(self._on_rule_status)
        self._apply_ui_to_engine()

    def _on_rule_status(self, idx: int, status: str):
        try:
            self._rows[idx]["lab_status"].setText(status)
        except Exception:
            pass

    def _on_row_mode_changed(self, idx: int):
        try:
            row = self._rows[idx]
            mode = str(row["combo_trig"].currentData() or "text")
            is_interval = (mode == "interval")
            row["edit_kw"].setVisible(not is_interval)
            row["spin_sec"].setVisible(is_interval)
        except Exception:
            pass
        self._apply_ui_to_engine()

    def _on_action_changed(self, idx: int):
        try:
            row = self._rows[idx]
            act = str(row["combo_act"].currentData() or "send")
            row["edit_cmd"].setEnabled(act != "restart")
        except Exception:
            pass
        self._apply_ui_to_engine()

    def _apply_ui_to_engine(self):
        rules: List[AutoTestRule] = []
        for row in self._rows:
            r = AutoTestRule()
            r.enabled = bool(row["chk"].isChecked())
            r.trigger_type = str(row["combo_trig"].currentData() or "text")
            r.trigger_text = str(row["edit_kw"].text() or "")
            r.interval_sec = int(row["spin_sec"].value())
            r.action_type = str(row["combo_act"].currentData() or "send")
            r.action_text = str(row["edit_cmd"].text() or "")
            rules.append(r)
        self._engine.set_rules(rules, persist=True)


