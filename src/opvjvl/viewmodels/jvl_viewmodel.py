"""JVLモード(発光素子IV-輝度測定/暗IV測定共通)タブのViewModel。

要件定義書_基本設計書.md A-4-3節・B-1節に対応する。``jvl_useLuminanceCheckBox``
がOFFの場合は暗IV測定として``run_jvl_sequence``をそのまま流用する
(A-4-3節: 新規実装不要)。プロットは``jvl_plotTabWidget``の2ページ
(``jvl_ivPlotWidget``: 電圧-電流、``jvl_ivlPlotWidget``: 電圧-電流+輝度)
の両方を更新する。
"""
from __future__ import annotations

import functools
from typing import Optional

from opvjvl.models.instruments import registry
from opvjvl.models.measurement import csv_writer
from opvjvl.models.measurement.config import JVLConfig
from opvjvl.models.measurement.sequences import run_jvl_sequence
from opvjvl.qtcompat import QObject
from opvjvl.viewmodels import base_viewmodel as bvm
from opvjvl.viewmodels.device_discovery import list_serial_ports, list_visa_resources
from opvjvl.workers.measurement_worker import MeasurementWorker

_DEVICE_TYPE_BY_INDEX = {0: "keithley2400", 1: "keithley2612b"}


class JVLViewModel(QObject):
    """JVLタブ用ViewModel。輝度計測ONならBM9(またはモック)を生成して渡す。"""

    def __init__(self, jvl_tab, parent=None) -> None:
        super().__init__(parent)
        self.view = jvl_tab
        self._worker: Optional[MeasurementWorker] = None
        self._iv_plot_buffer: Optional[bvm.PlotBuffer] = None
        self._ivl_plot_buffer: Optional[bvm.DualAxisPlotBuffer] = None

        self.view.jvl_startButton.clicked.connect(self._on_start_clicked)
        self.view.jvl_stopButton.clicked.connect(self._on_stop_clicked)
        self.view.jvl_refreshDevicesButton.clicked.connect(self._on_refresh_devices_clicked)
        self.view.jvl_refreshBm9PortsButton.clicked.connect(self._on_refresh_bm9_ports_clicked)

    # ------------------------------------------------------------------
    # 機器一覧の再検索
    # ------------------------------------------------------------------
    def _on_refresh_devices_clicked(self) -> None:
        device_type = _DEVICE_TYPE_BY_INDEX.get(
            self.view.jvl_deviceTypeCombo.currentIndex(), "keithley2400"
        )
        candidates = (
            list_visa_resources() if device_type == "keithley2612b" else list_serial_ports()
        )
        combo = self.view.jvl_connectionCombo
        combo.clear()
        for candidate in candidates:
            combo.addItem(candidate)

    def _on_refresh_bm9_ports_clicked(self) -> None:
        combo = self.view.jvl_bm9PortCombo
        combo.clear()
        for candidate in list_serial_ports():
            combo.addItem(candidate)

    # ------------------------------------------------------------------
    # 設定構築
    # ------------------------------------------------------------------
    def _build_config(self) -> JVLConfig:
        view = self.view
        device_type = _DEVICE_TYPE_BY_INDEX.get(view.jvl_deviceTypeCombo.currentIndex(), "keithley2400")
        use_luminance = view.jvl_useLuminanceCheckBox.isChecked()
        bm9_port = view.jvl_bm9PortCombo.currentText().strip() if use_luminance else None
        return JVLConfig(
            device_type=device_type,
            connection=view.jvl_connectionCombo.currentText(),
            use_mock=view.jvl_useMockCheckBox.isChecked(),
            v_min=view.jvl_vMinSpin.value(),
            v_max=view.jvl_vMaxSpin.value(),
            v_step=view.jvl_vStepSpin.value(),
            iteration=view.jvl_iterationSpin.value(),
            compliance_current=view.jvl_complianceSpin.value(),
            nplc=view.jvl_nplcSpin.value(),
            delay_time=view.jvl_delaySpin.value(),
            sample_name=view.jvl_sampleNameEdit.text().strip() or "sample",
            save_dir=view.jvl_saveDirEdit.text().strip() or ".",
            use_luminance=use_luminance,
            bm9_port=bm9_port,
        )

    # ------------------------------------------------------------------
    # 測定開始/中断
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # 二重起動防止(B-7節)

        view = self.view
        config = self._build_config()
        if not bvm.validate_voltage_range(view, config.v_min, config.v_max):
            return
        if config.use_luminance and not bvm.validate_luminance_port(view, config.bm9_port):
            return

        smu = registry.create_source_meter(
            config.device_type,
            config.connection,
            use_mock=config.use_mock,
            preset="jvl",
        )
        luminance_meter = None
        if config.use_luminance:
            luminance_meter = registry.create_luminance_meter(
                config.bm9_port, use_mock=config.use_mock
            )

        total_points = len(config.build_voltage_list())
        make_iterator = functools.partial(
            run_jvl_sequence, smu, config, luminance_meter=luminance_meter
        )
        csv_save_fn = functools.partial(
            csv_writer.save_jvl_csv,
            sample_name=config.sample_name,
            save_dir=config.save_dir,
            use_luminance=config.use_luminance,
        )

        bvm.append_log(
            view.jvl_logTextEdit,
            f"{bvm.mock_log_prefix(config.use_mock)}測定を開始します"
            f" ({config.device_type}, {config.connection}, 輝度計測={config.use_luminance})",
        )
        self._iv_plot_buffer = bvm.PlotBuffer(view.jvl_ivPlotWidget)
        self._ivl_plot_buffer = bvm.DualAxisPlotBuffer(view.jvl_ivlPlotWidget)

        worker = MeasurementWorker(
            make_iterator,
            smu,
            total_points,
            luminance_meter=luminance_meter,
            csv_save_fn=csv_save_fn,
        )
        worker.point_measured.connect(self._on_point_measured)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_finished_ok)
        worker.error.connect(self._on_error)
        self._worker = worker

        bvm.set_running_state(view.jvl_startButton, view.jvl_stopButton, True)
        worker.start()

    def _on_stop_clicked(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    # ------------------------------------------------------------------
    # Workerシグナルハンドラ
    # ------------------------------------------------------------------
    def _on_point_measured(self, point) -> None:
        luminance = getattr(point, "luminance", None)
        if self._iv_plot_buffer is not None:
            self._iv_plot_buffer.add_point(point.voltage, point.current)
        if self._ivl_plot_buffer is not None:
            self._ivl_plot_buffer.add_point(point.voltage, point.current, luminance)

        message = f"V={point.voltage:.4f} V, I={point.current:.6e} A"
        if luminance is not None:
            message += f", L={luminance:.4f} cd/m2"
        bvm.append_log(self.view.jvl_logTextEdit, message)

    def _on_progress(self, current: int, total: int) -> None:
        self.view.jvl_progressBar.setMaximum(max(total, 1))
        self.view.jvl_progressBar.setValue(current)

    def _on_finished_ok(self, points: list, csv_path: str) -> None:
        message = f"測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        bvm.append_log(self.view.jvl_logTextEdit, message)
        self._reset_running_state()

    def _on_error(self, message: str) -> None:
        bvm.append_error_log(self.view.jvl_logTextEdit, message)
        bvm.show_critical(self.view, message)
        self._reset_running_state()

    def _reset_running_state(self) -> None:
        bvm.set_running_state(self.view.jvl_startButton, self.view.jvl_stopButton, False)
        self._worker = None
