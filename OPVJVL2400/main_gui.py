"""
main_gui.py
OPV / JVL 測定 統合GUI(タブ切り替え式)

実行方法:
    python main_gui.py
"""

from __future__ import annotations

import sys
import os

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QPushButton,
    QComboBox, QCheckBox, QFileDialog, QPlainTextEdit, QProgressBar,
    QMessageBox, QTabWidget,
)

from instruments import list_serial_ports
from measurement_worker import (
    OPVMeasurementWorker, OPVConfig, OPVPoint,
    JVLMeasurementWorker, JVLConfig, JVLPoint,
)


# ---------------------------------------------------------------------------
# 配色トークン(計装機器の操作パネルを意識した、視認性重視のダークテーマ)
# ---------------------------------------------------------------------------
COLOR_BG = "#12161C"
COLOR_PANEL = "#1A2028"
COLOR_PANEL_BORDER = "#2A323D"
COLOR_TEXT = "#E7ECF2"
COLOR_TEXT_DIM = "#8B98A8"
COLOR_ACCENT_I = "#4FD1C5"    # 電流(青緑)
COLOR_ACCENT_V = "#F2B84B"    # 電圧系ラベル(琥珀)
COLOR_ACCENT_L = "#B47EE5"    # 輝度(紫)
COLOR_DANGER = "#E0645A"
COLOR_OK = "#57C785"

STYLE_SHEET = f"""
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    background-color: {COLOR_PANEL};
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px;
    font-weight: 600;
    color: {COLOR_TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {COLOR_ACCENT_V};
    letter-spacing: 1px;
}}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background-color: #0E1217;
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    color: {COLOR_TEXT};
}}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT_I};
}}
QPushButton {{
    background-color: #23303A;
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 4px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #2C3D49;
}}
QPushButton:disabled {{
    color: {COLOR_TEXT_DIM};
    background-color: #1C232B;
}}
QPushButton#startButton {{
    background-color: #1B4A44;
    border: 1px solid {COLOR_ACCENT_I};
    color: {COLOR_ACCENT_I};
}}
QPushButton#startButton:hover {{
    background-color: #205950;
}}
QPushButton#stopButton {{
    background-color: #4A2323;
    border: 1px solid {COLOR_DANGER};
    color: {COLOR_DANGER};
}}
QPushButton#stopButton:hover {{
    background-color: #5A2A2A;
}}
QPlainTextEdit {{
    background-color: #0B0E12;
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 4px;
    color: {COLOR_TEXT_DIM};
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}}
QProgressBar {{
    background-color: #0E1217;
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 4px;
    text-align: center;
    color: {COLOR_TEXT};
}}
QProgressBar::chunk {{
    background-color: {COLOR_ACCENT_I};
    border-radius: 3px;
}}
QLabel#sectionLabel {{
    color: {COLOR_ACCENT_V};
    font-weight: 700;
    letter-spacing: 2px;
}}
QTabWidget::pane {{
    border: 1px solid {COLOR_PANEL_BORDER};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background-color: {COLOR_PANEL};
    color: {COLOR_TEXT_DIM};
    padding: 8px 20px;
    border: 1px solid {COLOR_PANEL_BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: #23303A;
    color: {COLOR_ACCENT_I};
    font-weight: 700;
}}
QCheckBox {{
    spacing: 8px;
}}
"""


def make_spin(lo, hi, default, decimals, suffix, step=None) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setDecimals(decimals)
    spin.setSingleStep(step if step is not None else 10 ** (-decimals + 1))
    spin.setValue(default)
    spin.setSuffix(suffix)
    return spin


# ---------------------------------------------------------------------------
# OPV測定タブ
# ---------------------------------------------------------------------------

class OPVTab(QWidget):
    def __init__(self, get_keithley_port, get_save_dir, log_fn, parent=None):
        super().__init__(parent)
        self.get_keithley_port = get_keithley_port
        self.get_save_dir = get_save_dir
        self.log_fn = log_fn
        self.worker: OPVMeasurementWorker | None = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(14)

        # -- 左: 設定パネル --
        panel = QWidget()
        panel.setFixedWidth(320)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        sweep_box = QGroupBox("電圧掃引条件")
        form = QFormLayout(sweep_box)
        self.vmin_spin = make_spin(-20, 20, -0.1, 3, " V")
        self.vmax_spin = make_spin(-20, 20, 1.1, 3, " V")
        self.vstep_spin = make_spin(0.001, 5, 0.02, 3, " V")
        self.iteration_spin = QSpinBox()
        self.iteration_spin.setRange(1, 100)
        self.iteration_spin.setValue(3)
        form.addRow("Vmin:", self.vmin_spin)
        form.addRow("Vmax:", self.vmax_spin)
        form.addRow("Vstep:", self.vstep_spin)
        form.addRow("繰り返し回数:", self.iteration_spin)
        layout.addWidget(sweep_box)

        timing_box = QGroupBox("タイミング / ソース設定")
        form2 = QFormLayout(timing_box)
        self.delay_spin = make_spin(0, 60, 1.0, 3, " s")
        self.nplc_spin = make_spin(0.01, 25, 1.0, 3, "")
        self.compliance_spin = make_spin(0.0001, 1.0, 0.02, 4, " A")
        self.autorange_check = QCheckBox("電流レンジ自動")
        self.autorange_check.setChecked(True)
        form2.addRow("ディレイ時間:", self.delay_spin)
        form2.addRow("NPLC:", self.nplc_spin)
        form2.addRow("コンプライアンス電流:", self.compliance_spin)
        form2.addRow("", self.autorange_check)
        layout.addWidget(timing_box)

        save_box = QGroupBox("サンプル")
        form3 = QFormLayout(save_box)
        self.sample_name_edit = QLineEdit("sample")
        form3.addRow("サンプル名:", self.sample_name_edit)
        layout.addWidget(save_box)

        run_row = QHBoxLayout()
        self.start_btn = QPushButton("測定開始")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("中断")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        run_row.addWidget(self.start_btn)
        run_row.addWidget(self.stop_btn)
        layout.addLayout(run_row)

        layout.addStretch(1)
        root.addWidget(panel, stretch=0)

        # -- 右: 表示パネル --
        display = QWidget()
        dlayout = QVBoxLayout(display)
        dlayout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("待機中")
        dlayout.addWidget(self.progress_bar)

        pg.setConfigOption("background", COLOR_PANEL)
        pg.setConfigOption("foreground", COLOR_TEXT)

        self.iv_plot = pg.PlotWidget()
        self.iv_plot.setLabel("bottom", "Voltage", units="V")
        self.iv_plot.setLabel("left", "Current", units="A")
        self.iv_plot.showGrid(x=True, y=True, alpha=0.2)
        self.iv_curve = self.iv_plot.plot([], [], pen=pg.mkPen(COLOR_ACCENT_I, width=2),
                                           symbol="o", symbolSize=5,
                                           symbolBrush=COLOR_ACCENT_I, symbolPen=None)
        dlayout.addWidget(self.iv_plot, stretch=1)

        root.addWidget(display, stretch=1)

    def set_enabled_config(self, enabled: bool):
        for w in (self.vmin_spin, self.vmax_spin, self.vstep_spin, self.iteration_spin,
                  self.delay_spin, self.nplc_spin, self.compliance_spin, self.autorange_check,
                  self.sample_name_edit):
            w.setEnabled(enabled)

    def _start(self):
        port = self.get_keithley_port()
        if not port:
            QMessageBox.warning(self, "設定エラー", "Keithley2400のCOMポートを指定してください。")
            return

        config = OPVConfig(
            keithley_port=port,
            v_min=self.vmin_spin.value(),
            v_max=self.vmax_spin.value(),
            v_step=self.vstep_spin.value(),
            iteration=self.iteration_spin.value(),
            delay_time=self.delay_spin.value(),
            nplc=self.nplc_spin.value(),
            compliance_current=self.compliance_spin.value(),
            auto_range=self.autorange_check.isChecked(),
            sample_name=self.sample_name_edit.text().strip() or "sample",
            save_dir=self.get_save_dir(),
        )

        if config.v_step <= 0 or config.v_max < config.v_min:
            QMessageBox.warning(self, "設定エラー", "電圧掃引条件が不正です(Vstep>0、Vmax>=Vmin)。")
            return

        self.iv_curve.setData([], [])
        self._v_hist, self._i_hist = [], []

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("測定中... %p%")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.set_enabled_config(False)

        self.worker = OPVMeasurementWorker(config)
        self.worker.point_measured.connect(self._on_point)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self.log_fn)
        self.worker.error.connect(self._on_error)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.start()

    def _stop(self):
        if self.worker is not None:
            self.worker.request_abort()
            self.stop_btn.setEnabled(False)

    def _on_point(self, point: OPVPoint):
        self._v_hist.append(point.voltage)
        self._i_hist.append(point.current)
        self.iv_curve.setData(self._v_hist, self._i_hist)

    def _on_progress(self, current: int, total: int):
        pct = int(100 * current / total) if total else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"測定中... {current}/{total} ({pct}%)")

    def _on_error(self, message: str):
        self.log_fn(f"[OPV][ERROR] {message}")
        QMessageBox.critical(self, "測定エラー", message)
        self._reset_ui()

    def _on_finished(self, csv_path: str):
        self.progress_bar.setFormat("完了")
        self.log_fn(f"[OPV] 測定完了。保存先: {csv_path}")
        self._reset_ui()

    def _reset_ui(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_enabled_config(True)
        self.worker = None


# ---------------------------------------------------------------------------
# JVL測定タブ
# ---------------------------------------------------------------------------

class JVLTab(QWidget):
    def __init__(self, get_keithley_port, get_save_dir, log_fn, parent=None):
        super().__init__(parent)
        self.get_keithley_port = get_keithley_port
        self.get_save_dir = get_save_dir
        self.log_fn = log_fn
        self.worker: JVLMeasurementWorker | None = None
        self._build_ui()
        self._refresh_bm9_ports()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(14)

        # -- 左: 設定パネル --
        panel = QWidget()
        panel.setFixedWidth(320)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        bm9_box = QGroupBox("輝度計 (BM9)")
        form0 = QFormLayout(bm9_box)
        row = QHBoxLayout()
        self.bm9_combo = QComboBox()
        self.bm9_combo.setEditable(True)
        refresh_btn = QPushButton("再検索")
        refresh_btn.clicked.connect(self._refresh_bm9_ports)
        row.addWidget(self.bm9_combo, stretch=1)
        row.addWidget(refresh_btn, stretch=0)
        form0.addRow("BM9ポート:", row)
        self.lum_scale_spin = make_spin(0.001, 10000, 100.0, 3, " 倍")
        form0.addRow("輝度倍率:", self.lum_scale_spin)
        layout.addWidget(bm9_box)

        sweep_box = QGroupBox("電圧掃引条件")
        form = QFormLayout(sweep_box)
        self.vmin_spin = make_spin(-20, 20, -1.0, 3, " V")
        self.vmax_spin = make_spin(-20, 20, 1.2, 3, " V")
        self.vstep_spin = make_spin(0.001, 5, 0.1, 3, " V")
        self.iteration_spin = QSpinBox()
        self.iteration_spin.setRange(1, 100)
        self.iteration_spin.setValue(3)
        form.addRow("Vmin:", self.vmin_spin)
        form.addRow("Vmax:", self.vmax_spin)
        form.addRow("Vstep:", self.vstep_spin)
        form.addRow("繰り返し回数:", self.iteration_spin)
        layout.addWidget(sweep_box)

        limit_box = QGroupBox("早期終了条件")
        form_limit = QFormLayout(limit_box)
        self.current_limit_spin = make_spin(0.000001, 10, 0.001, 6, " A", step=0.0001)
        form_limit.addRow("電流上限 |I|:", self.current_limit_spin)
        note = QLabel("上限到達時 or Vmax到達時のいずれか早い方で終了\n(それまでのデータは保存されます)")
        note.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 11px;")
        note.setWordWrap(True)
        form_limit.addRow(note)
        layout.addWidget(limit_box)

        timing_box = QGroupBox("タイミング / ソース設定")
        form2 = QFormLayout(timing_box)
        self.delay_spin = make_spin(0, 60, 1.0, 3, " s")
        self.nplc_spin = make_spin(0.01, 25, 1.0, 3, "")
        self.compliance_spin = make_spin(0.0001, 1.0, 0.02, 4, " A")
        self.autorange_check = QCheckBox("電流レンジ自動")
        self.autorange_check.setChecked(True)
        form2.addRow("ディレイ時間:", self.delay_spin)
        form2.addRow("NPLC:", self.nplc_spin)
        form2.addRow("コンプライアンス電流:", self.compliance_spin)
        form2.addRow("", self.autorange_check)
        layout.addWidget(timing_box)

        save_box = QGroupBox("サンプル")
        form3 = QFormLayout(save_box)
        self.sample_name_edit = QLineEdit("sample")
        form3.addRow("サンプル名:", self.sample_name_edit)
        layout.addWidget(save_box)

        run_row = QHBoxLayout()
        self.start_btn = QPushButton("測定開始")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("中断")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        run_row.addWidget(self.start_btn)
        run_row.addWidget(self.stop_btn)
        layout.addLayout(run_row)

        layout.addStretch(1)
        root.addWidget(panel, stretch=0)

        # -- 右: 表示パネル --
        display = QWidget()
        dlayout = QVBoxLayout(display)
        dlayout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("待機中")
        dlayout.addWidget(self.progress_bar)

        tabs = QTabWidget()

        pg.setConfigOption("background", COLOR_PANEL)
        pg.setConfigOption("foreground", COLOR_TEXT)

        self.iv_plot = pg.PlotWidget()
        self.iv_plot.setLabel("bottom", "Voltage", units="V")
        self.iv_plot.setLabel("left", "|Current|", units="A")
        self.iv_plot.showGrid(x=True, y=True, alpha=0.2)
        self.iv_plot.setLogMode(y=True)
        self.iv_curve = self.iv_plot.plot([], [], pen=pg.mkPen(COLOR_ACCENT_I, width=2),
                                           symbol="o", symbolSize=5,
                                           symbolBrush=COLOR_ACCENT_I, symbolPen=None)
        tabs.addTab(self.iv_plot, "I–V (log)")

        self.lv_plot = pg.PlotWidget()
        self.lv_plot.setLabel("bottom", "Voltage", units="V")
        self.lv_plot.setLabel("left", "|Luminance|", units="cd/m2")
        self.lv_plot.showGrid(x=True, y=True, alpha=0.2)
        self.lv_plot.setLogMode(y=True)
        self.lv_curve = self.lv_plot.plot([], [], pen=pg.mkPen(COLOR_ACCENT_L, width=2),
                                           symbol="o", symbolSize=5,
                                           symbolBrush=COLOR_ACCENT_L, symbolPen=None)
        tabs.addTab(self.lv_plot, "L–V (log)")

        dlayout.addWidget(tabs, stretch=1)
        root.addWidget(display, stretch=1)

    def _refresh_bm9_ports(self):
        current = self.bm9_combo.currentText()
        self.bm9_combo.clear()
        ports = list_serial_ports()
        if ports:
            self.bm9_combo.addItems(ports)
        else:
            self.bm9_combo.addItem("COM4")
        if current:
            idx = self.bm9_combo.findText(current)
            if idx >= 0:
                self.bm9_combo.setCurrentIndex(idx)
            else:
                self.bm9_combo.setCurrentText(current)

    def set_enabled_config(self, enabled: bool):
        for w in (self.bm9_combo, self.lum_scale_spin,
                  self.vmin_spin, self.vmax_spin, self.vstep_spin, self.iteration_spin,
                  self.current_limit_spin,
                  self.delay_spin, self.nplc_spin, self.compliance_spin, self.autorange_check,
                  self.sample_name_edit):
            w.setEnabled(enabled)

    def _start(self):
        port = self.get_keithley_port()
        if not port:
            QMessageBox.warning(self, "設定エラー", "Keithley2400のCOMポートを指定してください。")
            return
        bm9_port = self.bm9_combo.currentText().strip()
        if not bm9_port:
            QMessageBox.warning(self, "設定エラー", "BM9のCOMポートを指定してください。")
            return

        config = JVLConfig(
            keithley_port=port,
            bm9_port=bm9_port,
            v_min=self.vmin_spin.value(),
            v_max=self.vmax_spin.value(),
            v_step=self.vstep_spin.value(),
            iteration=self.iteration_spin.value(),
            delay_time=self.delay_spin.value(),
            nplc=self.nplc_spin.value(),
            compliance_current=self.compliance_spin.value(),
            auto_range=self.autorange_check.isChecked(),
            current_limit=self.current_limit_spin.value(),
            luminance_scale=self.lum_scale_spin.value(),
            sample_name=self.sample_name_edit.text().strip() or "sample",
            save_dir=self.get_save_dir(),
        )

        if config.v_step <= 0 or config.v_max < config.v_min:
            QMessageBox.warning(self, "設定エラー", "電圧掃引条件が不正です(Vstep>0、Vmax>=Vmin)。")
            return

        self.iv_curve.setData([], [])
        self.lv_curve.setData([], [])
        self._v_hist, self._i_hist, self._l_hist = [], [], []

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("測定中... %p%")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.set_enabled_config(False)

        self.worker = JVLMeasurementWorker(config)
        self.worker.point_measured.connect(self._on_point)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self.log_fn)
        self.worker.error.connect(self._on_error)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.start()

    def _stop(self):
        if self.worker is not None:
            self.worker.request_abort()
            self.stop_btn.setEnabled(False)

    def _on_point(self, point: JVLPoint):
        self._v_hist.append(point.voltage)
        self._i_hist.append(abs(point.current))
        self._l_hist.append(abs(point.luminance))
        # logモードでは0や負値がプロットされないため、有効な点のみ渡される
        self.iv_curve.setData(self._v_hist, self._i_hist)
        self.lv_curve.setData(self._v_hist, self._l_hist)

    def _on_progress(self, current: int, total: int):
        pct = int(100 * current / total) if total else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"測定中... {current}/{total} ({pct}%)")

    def _on_error(self, message: str):
        self.log_fn(f"[JVL][ERROR] {message}")
        QMessageBox.critical(self, "測定エラー", message)
        self._reset_ui()

    def _on_finished(self, csv_path: str):
        self.progress_bar.setFormat("完了")
        self.log_fn(f"[JVL] 測定完了。保存先: {csv_path}")
        self._reset_ui()

    def _reset_ui(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.set_enabled_config(True)
        self.worker = None


# ---------------------------------------------------------------------------
# メインウィンドウ
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OPV / JVL Measurement")
        self.resize(1220, 760)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # -- 共通設定バー(Keithleyポート + 保存先) --
        common_box = QGroupBox("共通設定")
        common_layout = QHBoxLayout(common_box)

        common_layout.addWidget(QLabel("Keithley2400 ポート:"))
        self.keithley_combo = QComboBox()
        self.keithley_combo.setEditable(True)
        self.keithley_combo.setMinimumWidth(120)
        common_layout.addWidget(self.keithley_combo)
        refresh_btn = QPushButton("再検索")
        refresh_btn.clicked.connect(self._refresh_keithley_ports)
        common_layout.addWidget(refresh_btn)

        common_layout.addSpacing(24)
        common_layout.addWidget(QLabel("保存先フォルダ:"))
        self.save_dir_edit = QLineEdit(os.getcwd())
        common_layout.addWidget(self.save_dir_edit, stretch=1)
        browse_btn = QPushButton("参照...")
        browse_btn.clicked.connect(self._browse_save_dir)
        common_layout.addWidget(browse_btn)

        root.addWidget(common_box)

        # -- タブ(OPV / JVL) --
        self.tabs = QTabWidget()
        self.opv_tab = OPVTab(self._get_keithley_port, self._get_save_dir, self._append_log)
        self.jvl_tab = JVLTab(self._get_keithley_port, self._get_save_dir, self._append_log)
        self.tabs.addTab(self.opv_tab, "OPV 測定")
        self.tabs.addTab(self.jvl_tab, "JVL 測定")
        root.addWidget(self.tabs, stretch=1)

        # -- 共通ログ --
        log_box = QGroupBox("ログ")
        log_layout = QVBoxLayout(log_box)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(140)
        log_layout.addWidget(self.log_text)
        root.addWidget(log_box)

        self._refresh_keithley_ports()

    def _refresh_keithley_ports(self):
        current = self.keithley_combo.currentText()
        self.keithley_combo.clear()
        ports = list_serial_ports()
        if ports:
            self.keithley_combo.addItems(ports)
        else:
            self.keithley_combo.addItem("COM5")
        if current:
            idx = self.keithley_combo.findText(current)
            if idx >= 0:
                self.keithley_combo.setCurrentIndex(idx)
            else:
                self.keithley_combo.setCurrentText(current)

    def _browse_save_dir(self):
        path = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択", self.save_dir_edit.text())
        if path:
            self.save_dir_edit.setText(path)

    def _get_keithley_port(self) -> str:
        return self.keithley_combo.currentText().strip()

    def _get_save_dir(self) -> str:
        return self.save_dir_edit.text().strip() or os.getcwd()

    def _append_log(self, text: str):
        self.log_text.appendPlainText(text)

    def closeEvent(self, event):
        # 測定中のワーカーがあれば中断を要求してから終了
        for tab in (self.opv_tab, self.jvl_tab):
            if tab.worker is not None and tab.worker.isRunning():
                tab.worker.request_abort()
                tab.worker.wait(3000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
