"""JVLモード(発光素子IV-輝度測定/暗IV測定共通)タブのViewModel。

要件定義書_基本設計書.md A-4-3節・B-1節に対応する。
"""
from __future__ import annotations

import functools
from typing import Optional

from models.instruments import registry
from models.measurement import csv_writer
from models.measurement.config import JVLConfig
from models.measurement.sequences import run_jvl_sequence
from qtcompat import QObject, pyqtSignal
from viewmodels import base_viewmodel as bvm
from viewmodels.device_discovery import list_serial_ports, list_visa_resources
from workers.measurement_worker import MeasurementWorker


class JVLViewModel(QObject):
    """JVLタブ用ViewModel。輝度計測ONならBM9(またはモック)を生成して渡す。"""

    running_changed = pyqtSignal(bool)
    progress = pyqtSignal(int)
    point_measured = pyqtSignal(object)
    log_appended = pyqtSignal(str)
    error_appended = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_ok = pyqtSignal(list, str, bool)  # points, csv_path, aborted

    def __init__(self, parent=None) -> None:
        # MVVMの依存方向を守るため、ViewModelはViewを一切参照しない。
        # シグナルの結線はView側(JVLTab._bind_viewmodel)の責務とする。
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

    def refresh_bm9_ports(self) -> list[str]:
        return list_serial_ports()

    # ------------------------------------------------------------------
    # 測定開始/中断
    # ------------------------------------------------------------------
    def start_measurement(self, config: JVLConfig) -> None:
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
        if config.use_luminance and (not config.bm9_port or not config.bm9_port.strip()):
            self.error.emit("輝度計測を使用する場合はBM9接続ポートを入力してください。")
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

        self.log_appended.emit(
            f"{bvm.mock_log_prefix(config.use_mock)}測定を開始します"
            f" ({config.device_type}, {config.connection}, 輝度計測={config.use_luminance})"
        )

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

        self.running_changed.emit(True)
        worker.start()

    def stop_measurement(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()

    def stop_and_wait(self, timeout_ms: int = 3000) -> None:
        """アプリ終了時(MainWindow.closeEvent)専用の同期的停止API(review.md項目3)。

        実行中のworkerへ協調的中断を要求し、``QThread.wait()``で猶予を与えることで、
        workerの``finally``節(機器の出力OFF・close())が走り切る時間を確保する。
        タイムアウトしても例外は出さず終了処理を継続させる。
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.request_stop()
            worker.wait(timeout_ms)

    # ------------------------------------------------------------------
    # Workerシグナルハンドラ
    # ------------------------------------------------------------------
    def _on_point_measured(self, point) -> None:
        self.point_measured.emit(point)
        luminance = getattr(point, "luminance", None)
        message = f"V={point.voltage:.4f} V, I={point.current:.6e} A"
        if luminance is not None:
            message += f", L={luminance:.4f} cd/m2"
        self.log_appended.emit(message)

    def _on_progress(self, current: int, total: int) -> None:
        self.progress.emit(current)

    def _on_finished_ok(self, points: list, csv_path: str, aborted: bool) -> None:
        # 中断(ユーザーによるstop)と正常完了を明確に区別して表示する
        if aborted:
            message = f"測定中断: {len(points)}点で停止しました。"
        else:
            message = f"測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        self.log_appended.emit(message)
        self.finished_ok.emit(points, csv_path, aborted)
        self._reset_running_state()

    def _on_error(self, message: str) -> None:
        self.error_appended.emit(message)
        self.error.emit(message)
        self._reset_running_state()

    def _reset_running_state(self) -> None:
        self.running_changed.emit(False)
        self._worker = None
