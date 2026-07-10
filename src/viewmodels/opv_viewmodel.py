"""OPVモード(太陽電池 JV/IV特性測定)タブのViewModel。

要件定義書_基本設計書.md A-4-2節・B-1節に対応する。
"""
from __future__ import annotations

import functools
from typing import Optional

from models.instruments import registry
from models.measurement import csv_writer
from models.measurement.config import OPVConfig
from models.measurement.sequences import run_opv_sequence
from qtcompat import QObject, pyqtSignal
from viewmodels import base_viewmodel as bvm
from viewmodels.device_discovery import list_serial_ports, list_visa_resources
from workers.measurement_worker import MeasurementWorker


class OPVViewModel(QObject):
    """OPVタブ用ViewModel。輝度計は使用しない。"""

    running_changed = pyqtSignal(bool)
    progress = pyqtSignal(int)
    point_measured = pyqtSignal(object)
    log_appended = pyqtSignal(str)
    error_appended = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_ok = pyqtSignal(list, str)

    def __init__(self, parent=None) -> None:
        # MVVMの依存方向を守るため、ViewModelはViewを一切参照しない。
        # シグナルの結線はView側(OPVTab._bind_viewmodel)の責務とする。
        super().__init__(parent)
        self._worker: Optional[MeasurementWorker] = None

    # ------------------------------------------------------------------
    # 機器一覧の再検索
    # ------------------------------------------------------------------
    def refresh_devices(self, device_type: str) -> list[str]:
        if device_type == "keithley2612b":
            return list_visa_resources()
        else:
            return list_serial_ports()

    # ------------------------------------------------------------------
    # 測定開始/中断
    # ------------------------------------------------------------------
    def start_measurement(self, config: OPVConfig) -> None:
        if self._worker is not None and self._worker.isRunning():
            return  # 二重起動防止(B-7節)

        if config.v_max <= config.v_min:
            self.error.emit(f"Vmax({config.v_max})はVmin({config.v_min})より大きい値にしてください。")
            return
        if config.v_step <= 0:
            self.error.emit("Vstepは0より大きい値にしてください。")
            return
        if config.iteration < 1:
            self.error.emit("繰り返し回数は1回以上にしてください。")
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

        self.log_appended.emit(
            f"{bvm.mock_log_prefix(config.use_mock)}測定を開始します"
            f" ({config.device_type}, {config.connection})"
        )

        worker = MeasurementWorker(
            make_iterator, smu, total_points, csv_save_fn=csv_save_fn
        )
        worker.point_measured.connect(self._on_point_measured)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_finished_ok)
        worker.error.connect(self._on_error)
        self._worker = worker

        self.running_changed.emit(True)
        worker.start()

    def stop_measurement(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    # ------------------------------------------------------------------
    # Workerシグナルハンドラ
    # ------------------------------------------------------------------
    def _on_point_measured(self, point) -> None:
        self.point_measured.emit(point)
        self.log_appended.emit(
            f"V={point.voltage:.4f} V, I={point.current:.6e} A"
        )

    def _on_progress(self, current: int, total: int) -> None:
        self.progress.emit(current)

    def _on_finished_ok(self, points: list, csv_path: str) -> None:
        message = f"測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        self.log_appended.emit(message)
        self.finished_ok.emit(points, csv_path)
        self._reset_running_state()

    def _on_error(self, message: str) -> None:
        self.error_appended.emit(message)
        self.error.emit(message)
        self._reset_running_state()

    def _reset_running_state(self) -> None:
        self.running_changed.emit(False)
        self._worker = None
