"""
main_gui.py
JVL(電流密度-電圧-輝度)測定 統合GUI

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

from bases.OPVJVL2.instruments import list_visa_resources, list_serial_ports
from bases.OPVJVL2.measurement_worker import MeasurementWorker, MeasurementConfig, MeasurementPoint


# ---------------------------------------------------------------------------
# 配色トークン(計装機器の操作パネルを意識した、視認性重視のダークテーマ)
# ---------------------------------------------------------------------------
COLOR_BG = "#12161C"
COLOR_PANEL = "#1A2028"
COLOR_PANEL_BORDER = "#2A323D"
COLOR_TEXT = "#E7ECF2"
COLOR_TEXT_DIM = "#8B98A8"
COLOR_ACCENT_J = "#4FD1C5"    # 電流(青緑)
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
    border: 1px solid {COLOR_ACCENT_J};
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
    border: 1px solid {COLOR_ACCENT_J};
    color: {COLOR_ACCENT_J};
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
    background-color: {COLOR_ACCENT_J};
    border-radius: 3px;
}}
QLabel#sectionLabel {{
    color: {COLOR_ACCENT_V};
    font-weight: 700;
    letter-spacing: 2px;
}}
QCheckBox {{
    spacing: 8px;
}}
"""


class JVLMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JVL Measurement — OPV Characterization")
        self.resize(1180, 720)

        self.worker: MeasurementWorker | None = None

        self._build_ui()
        self._refresh_device_lists()

    # -- UI構築 --------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_control_panel(), stretch=0)
        root.addWidget(self._build_display_panel(), stretch=1)

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(340)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        title = QLabel("J–V–L MEASUREMENT")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        layout.addWidget(self._build_connection_group())
        layout.addWidget(self._build_sweep_group())
        layout.addWidget(self._build_timing_group())
        layout.addWidget(self._build_luminance_group())
        layout.addWidget(self._build_save_group())
        layout.addWidget(self._build_run_group())
        layout.addStretch(1)

        return panel

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("接続")
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.keithley_combo = QComboBox()
        self.keithley_combo.setEditable(True)
        refresh_btn = QPushButton("再検索")
        refresh_btn.clicked.connect(self._refresh_device_lists)
        row.addWidget(self.keithley_combo, stretch=1)
        row.addWidget(refresh_btn, stretch=0)
        form.addRow("Keithley VISA:", row)

        self.channel_mode_combo = QComboBox()
        self.channel_mode_combo.addItem("smua単独 (single)", "single")
        self.channel_mode_combo.addItem("smua掃引 + smub=0V測定 (dual)", "dual")
        form.addRow("チャンネル構成:", self.channel_mode_combo)

        return box

    def _build_sweep_group(self) -> QGroupBox:
        box = QGroupBox("電圧掃引条件")
        form = QFormLayout(box)

        self.vmin_spin = self._make_spin(-10, 10, -0.1, 3, " V")
        self.vmax_spin = self._make_spin(-10, 10, 1.1, 3, " V")
        self.vstep_spin = self._make_spin(0.001, 5, 0.02, 3, " V")
        self.iteration_spin = QSpinBox()
        self.iteration_spin.setRange(1, 100)
        self.iteration_spin.setValue(5)

        form.addRow("Vmin:", self.vmin_spin)
        form.addRow("Vmax:", self.vmax_spin)
        form.addRow("Vstep:", self.vstep_spin)
        form.addRow("繰り返し回数:", self.iteration_spin)

        return box

    def _build_timing_group(self) -> QGroupBox:
        box = QGroupBox("タイミング")
        form = QFormLayout(box)

        self.nplc_spin = self._make_spin(0.001, 25, 0.5, 3, " NPLC")
        self.delay_spin = self._make_spin(0, 60, 0.5, 3, " s")

        form.addRow("積分時間:", self.nplc_spin)
        form.addRow("ディレイ時間:", self.delay_spin)

        return box

    def _build_luminance_group(self) -> QGroupBox:
        box = QGroupBox("輝度計 (BM9)")
        layout = QVBoxLayout(box)

        self.use_bm9_checkbox = QCheckBox("BM9で輝度も測定する")
        self.use_bm9_checkbox.stateChanged.connect(self._on_bm9_toggled)
        layout.addWidget(self.use_bm9_checkbox)

        form = QFormLayout()
        self.bm9_combo = QComboBox()
        self.bm9_combo.setEditable(True)
        self.bm9_combo.setEnabled(False)
        form.addRow("ポート:", self.bm9_combo)
        layout.addLayout(form)

        return box

    def _build_save_group(self) -> QGroupBox:
        box = QGroupBox("保存")
        form = QFormLayout(box)

        self.sample_name_edit = QLineEdit("sample")
        form.addRow("サンプル名:", self.sample_name_edit)

        row = QHBoxLayout()
        self.save_dir_edit = QLineEdit(os.getcwd())
        browse_btn = QPushButton("参照...")
        browse_btn.clicked.connect(self._browse_save_dir)
        row.addWidget(self.save_dir_edit, stretch=1)
        row.addWidget(browse_btn, stretch=0)
        form.addRow("保存先:", row)

        return box

    def _build_run_group(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.start_btn = QPushButton("測定開始")
        self.start_btn.setObjectName("startButton")
        self.start_btn.clicked.connect(self._start_measurement)

        self.stop_btn = QPushButton("中断")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_measurement)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)
        return widget

    def _build_display_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("待機中")
        layout.addWidget(self.progress_bar)

        tabs = QTabWidget()

        pg.setConfigOption("background", COLOR_PANEL)
        pg.setConfigOption("foreground", COLOR_TEXT)

        # J-V グラフ
        self.jv_plot = pg.PlotWidget()
        self.jv_plot.setLabel("bottom", "Voltage", units="V")
        self.jv_plot.setLabel("left", "Current", units="A")
        self.jv_plot.showGrid(x=True, y=True, alpha=0.2)
        self.jv_curve = self.jv_plot.plot([], [], pen=pg.mkPen(COLOR_ACCENT_J, width=2),
                                           symbol="o", symbolSize=5,
                                           symbolBrush=COLOR_ACCENT_J, symbolPen=None)
        tabs.addTab(self.jv_plot, "J–V")

        # J-V-L グラフ(輝度は右軸に重ねる)
        self.jvl_plot = pg.PlotWidget()
        self.jvl_plot.setLabel("bottom", "Voltage", units="V")
        self.jvl_plot.setLabel("left", "Current", units="A", color=COLOR_ACCENT_J)
        self.jvl_plot.showGrid(x=True, y=True, alpha=0.2)
        self.jvl_curve = self.jvl_plot.plot([], [], pen=pg.mkPen(COLOR_ACCENT_J, width=2), name="Current")

        self.lum_viewbox = pg.ViewBox()
        self.jvl_plot.scene().addItem(self.lum_viewbox)
        self.jvl_plot.getAxis("right").linkToView(self.lum_viewbox)
        self.lum_viewbox.setXLink(self.jvl_plot)
        self.jvl_plot.showAxis("right")
        self.jvl_plot.getAxis("right").setLabel("Luminance", units="cd/m2", color=COLOR_ACCENT_L)
        self.lum_curve = pg.PlotCurveItem(pen=pg.mkPen(COLOR_ACCENT_L, width=2))
        self.lum_viewbox.addItem(self.lum_curve)
        self._sync_luminance_viewbox()
        self.jvl_plot.getViewBox().sigResized.connect(self._sync_luminance_viewbox)

        tabs.addTab(self.jvl_plot, "J–V–L")

        layout.addWidget(tabs, stretch=1)

        log_box = QGroupBox("ログ")
        log_layout = QVBoxLayout(log_box)
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(140)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_box)

        return panel

    def _sync_luminance_viewbox(self):
        self.lum_viewbox.setGeometry(self.jvl_plot.getViewBox().sceneBoundingRect())

    @staticmethod
    def _make_spin(lo, hi, default, decimals, suffix) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setSingleStep(10 ** (-decimals + 1))
        spin.setValue(default)
        spin.setSuffix(suffix)
        return spin

    # -- イベントハンドラ ------------------------------------------------------

    def _refresh_device_lists(self):
        self.keithley_combo.clear()
        resources = list_visa_resources()
        if resources:
            self.keithley_combo.addItems(resources)
        else:
            self.keithley_combo.addItem("USB0::0x05E6::0x2612::4043586::INSTR")

        self.bm9_combo.clear()
        ports = list_serial_ports()
        if ports:
            self.bm9_combo.addItems(ports)
        else:
            self.bm9_combo.addItem("COM3")

    def _on_bm9_toggled(self, state):
        self.bm9_combo.setEnabled(bool(state))

    def _browse_save_dir(self):
        path = QFileDialog.getExistingDirectory(self, "保存先フォルダを選択", self.save_dir_edit.text())
        if path:
            self.save_dir_edit.setText(path)

    def _append_log(self, text: str):
        self.log_text.appendPlainText(text)

    def _start_measurement(self):
        try:
            config = MeasurementConfig(
                keithley_resource=self.keithley_combo.currentText().strip(),
                v_min=self.vmin_spin.value(),
                v_max=self.vmax_spin.value(),
                v_step=self.vstep_spin.value(),
                iteration=self.iteration_spin.value(),
                integration_nplc=self.nplc_spin.value(),
                delay_time=self.delay_spin.value(),
                channel_mode=self.channel_mode_combo.currentData(),
                use_luminance=self.use_bm9_checkbox.isChecked(),
                bm9_port=self.bm9_combo.currentText().strip() if self.use_bm9_checkbox.isChecked() else None,
                sample_name=self.sample_name_edit.text().strip() or "sample",
                save_dir=self.save_dir_edit.text().strip() or os.getcwd(),
            )
        except Exception as e:
            QMessageBox.warning(self, "設定エラー", f"設定値が不正です: {e}")
            return

        if config.v_step <= 0 or config.v_max < config.v_min:
            QMessageBox.warning(self, "設定エラー", "電圧掃引条件が不正です(Vstep>0、Vmax>=Vminを確認してください)。")
            return

        self.jv_curve.setData([], [])
        self.lum_curve.setData([], [])
        self._v_history: list[float] = []
        self._i_history: list[float] = []
        self._l_history: list[float] = []

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("測定中... %p%")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_config_widgets_enabled(False)

        self.worker = MeasurementWorker(config)
        self.worker.point_measured.connect(self._on_point_measured)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.error.connect(self._on_error)
        self.worker.finished_ok.connect(self._on_finished_ok)
        self.worker.start()

    def _stop_measurement(self):
        if self.worker is not None:
            self.worker.request_abort()
            self.stop_btn.setEnabled(False)

    def _set_config_widgets_enabled(self, enabled: bool):
        for w in (self.keithley_combo, self.channel_mode_combo,
                  self.vmin_spin, self.vmax_spin, self.vstep_spin, self.iteration_spin,
                  self.nplc_spin, self.delay_spin,
                  self.use_bm9_checkbox, self.bm9_combo,
                  self.sample_name_edit, self.save_dir_edit):
            w.setEnabled(enabled)
        if enabled:
            self.bm9_combo.setEnabled(self.use_bm9_checkbox.isChecked())

    def _on_point_measured(self, point: MeasurementPoint):
        self._v_history.append(point.voltage)
        self._i_history.append(point.current)
        self.jv_curve.setData(self._v_history, self._i_history)
        self.jvl_curve.setData(self._v_history, self._i_history)

        if point.luminance is not None:
            self._l_history.append(point.luminance)
            self.lum_curve.setData(self._v_history, self._l_history)

    def _on_progress(self, current: int, total: int):
        pct = int(100 * current / total) if total else 0
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"測定中... {current}/{total} ({pct}%)")

    def _on_error(self, message: str):
        self._append_log(f"[ERROR] {message}")
        QMessageBox.critical(self, "測定エラー", message)
        self._finish_ui_reset()

    def _on_finished_ok(self, csv_path: str):
        self.progress_bar.setFormat("完了")
        self._append_log(f"測定完了。保存先: {csv_path}")
        self._finish_ui_reset()

    def _finish_ui_reset(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._set_config_widgets_enabled(True)
        self.worker = None


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE_SHEET)
    window = JVLMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
