"""OPVモード(太陽電池 JV/IV特性測定)タブのViewModel。

要件定義書_基本設計書.md A-4-2節・B-1節に対応する。``OPVTab``(View)の
ウィジェットのみを唯一のコンストラクタ引数として受け取り、シグナル配線・
バリデーション・Model層(registry/sequences/csv_writer)の呼び出し・
``MeasurementWorker``の生成と後始末を行う。
"""
from __future__ import annotations

import functools
from typing import Optional

from opvjvl.models.instruments import registry
from opvjvl.models.measurement import csv_writer
from opvjvl.models.measurement.config import OPVConfig
from opvjvl.models.measurement.sequences import run_opv_sequence
from opvjvl.qtcompat import QObject
from opvjvl.viewmodels import base_viewmodel as bvm
from opvjvl.viewmodels.device_discovery import list_serial_ports, list_visa_resources
from opvjvl.workers.measurement_worker import MeasurementWorker

_DEVICE_TYPE_BY_INDEX = {0: "keithley2400", 1: "keithley2612b"}


class OPVViewModel(QObject):
    """OPVタブ用ViewModel。輝度計は使用しない。"""

    def __init__(self, opv_tab, parent=None) -> None:
        super().__init__(parent)
        self.view = opv_tab
        self._worker: Optional[MeasurementWorker] = None
        self._plot_buffer: Optional[bvm.PlotBuffer] = None

        self.view.opv_startButton.clicked.connect(self._on_start_clicked)
        self.view.opv_stopButton.clicked.connect(self._on_stop_clicked)
        self.view.opv_refreshDevicesButton.clicked.connect(self._on_refresh_devices_clicked)

    # ------------------------------------------------------------------
    # 機器一覧の再検索
    # ------------------------------------------------------------------
    def _on_refresh_devices_clicked(self) -> None:
        device_type = _DEVICE_TYPE_BY_INDEX.get(
            self.view.opv_deviceTypeCombo.currentIndex(), "keithley2400"
        )
        candidates = (
            list_visa_resources() if device_type == "keithley2612b" else list_serial_ports()
        )
        combo = self.view.opv_connectionCombo
        combo.clear()
        for candidate in candidates:
            combo.addItem(candidate)

    # ------------------------------------------------------------------
    # 設定構築
    # ------------------------------------------------------------------
    def _build_config(self) -> OPVConfig:
        view = self.view
        device_type = _DEVICE_TYPE_BY_INDEX.get(view.opv_deviceTypeCombo.currentIndex(), "keithley2400")
        return OPVConfig(
            device_type=device_type,
            connection=view.opv_connectionCombo.currentText(),
            use_mock=view.opv_useMockCheckBox.isChecked(),
            v_min=view.opv_vMinSpin.value(),
            v_max=view.opv_vMaxSpin.value(),
            v_step=view.opv_vStepSpin.value(),
            iteration=view.opv_iterationSpin.value(),
            compliance_current=view.opv_complianceSpin.value(),
            nplc=view.opv_nplcSpin.value(),
            delay_time=view.opv_delaySpin.value(),
            sample_name=view.opv_sampleNameEdit.text().strip() or "sample",
            save_dir=view.opv_saveDirEdit.text().strip() or ".",
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

        smu = registry.create_source_meter(
            config.device_type,
            config.connection,
            use_mock=config.use_mock,
            preset="opv",
        )
        total_points = len(config.build_voltage_list())
        make_iterator = functools.partial(run_opv_sequence, smu, config)
        csv_save_fn = functools.partial(
            csv_writer.save_opv_csv,
            sample_name=config.sample_name,
            save_dir=config.save_dir,
        )

        bvm.append_log(
            view.opv_logTextEdit,
            f"{bvm.mock_log_prefix(config.use_mock)}測定を開始します"
            f" ({config.device_type}, {config.connection})",
        )
        self._plot_buffer = bvm.PlotBuffer(view.opv_plotWidget)

        worker = MeasurementWorker(
            make_iterator, smu, total_points, csv_save_fn=csv_save_fn
        )
        worker.point_measured.connect(self._on_point_measured)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_finished_ok)
        worker.error.connect(self._on_error)
        self._worker = worker

        bvm.set_running_state(view.opv_startButton, view.opv_stopButton, True)
        worker.start()

    def _on_stop_clicked(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    # ------------------------------------------------------------------
    # Workerシグナルハンドラ
    # ------------------------------------------------------------------
    def _on_point_measured(self, point) -> None:
        if self._plot_buffer is not None:
            self._plot_buffer.add_point(point.voltage, point.current)
        bvm.append_log(
            self.view.opv_logTextEdit,
            f"V={point.voltage:.4f} V, I={point.current:.6e} A",
        )

    def _on_progress(self, current: int, total: int) -> None:
        self.view.opv_progressBar.setMaximum(max(total, 1))
        self.view.opv_progressBar.setValue(current)

    def _on_finished_ok(self, points: list, csv_path: str) -> None:
        message = f"測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        bvm.append_log(self.view.opv_logTextEdit, message)
        self._reset_running_state()

    def _on_error(self, message: str) -> None:
        bvm.append_error_log(self.view.opv_logTextEdit, message)
        bvm.show_critical(self.view, message)
        self._reset_running_state()

    def _reset_running_state(self) -> None:
        bvm.set_running_state(self.view.opv_startButton, self.view.opv_stopButton, False)
        self._worker = None
