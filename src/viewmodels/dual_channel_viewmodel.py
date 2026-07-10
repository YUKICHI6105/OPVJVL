"""2ch活用モード(モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測)タブのViewModel。

要件定義書_基本設計書.md A-4-4節・B-1節に対応する。
"""
from __future__ import annotations

import datetime
import functools
from typing import Optional

from models.instruments import registry
from models.measurement import csv_writer
from models.measurement.config import ChannelConfig, DualAConfig, DualBConfig
from models.measurement.sequences import run_dual_a_sequence, run_dual_b_sequence
from qtcompat import QObject, pyqtSignal
from viewmodels import base_viewmodel as bvm
from workers.dual_channel_worker import DualChannelWorker
from workers.measurement_worker import MeasurementWorker

_DEVICE_TYPE_2612B = "keithley2612b"


class DualChannelViewModel(QObject):
    """2ch活用モードタブ用ViewModel。モードA/モードBを個別に扱う。"""

    # モードA用
    running_changed_a = pyqtSignal(bool)
    progress_a = pyqtSignal(int)
    point_measured_a = pyqtSignal(object)
    log_appended_a = pyqtSignal(str)
    error_appended_a = pyqtSignal(str)
    error_a = pyqtSignal(str)
    finished_ok_a = pyqtSignal(list, str, bool)  # points, csv_path, aborted

    # モードB用
    running_changed_b = pyqtSignal(bool)
    progress_b = pyqtSignal(int)
    point_measured_b_cha = pyqtSignal(object)
    point_measured_b_chb = pyqtSignal(object)
    log_appended_b = pyqtSignal(str)
    error_appended_b = pyqtSignal(str)
    error_b = pyqtSignal(str)
    finished_ok_b = pyqtSignal(list, str, str, bool)  # points, csv_path_a, csv_path_b, aborted

    def __init__(self, parent=None) -> None:
        # MVVMの依存方向を守るため、ViewModelはViewを一切参照しない。
        # シグナルの結線はView側(DualChannelTab._bind_viewmodel)の責務とする。
        super().__init__(parent)
        self._worker_a: Optional[MeasurementWorker] = None
        self._worker_b: Optional[DualChannelWorker] = None

    # ==================================================================
    # モードA(2ch低ノイズ計測)
    # ==================================================================
    def start_mode_a(self, config: DualAConfig) -> None:
        if self._worker_a is not None and self._worker_a.isRunning():
            return  # 二重起動防止(B-7節)

        if config.v_max <= config.v_min:
            self.error_a.emit(f"Vmax({config.v_max})はVmin({config.v_min})より大きい値にしてください。")
            return
        if config.v_step <= 0:
            self.error_a.emit("Vstepは0より大きい値にしてください。")
            return
        if config.iteration < 1:
            self.error_a.emit("繰り返し回数は1回以上にしてください。")
            return
        if config.use_luminance and (not config.bm9_port or not config.bm9_port.strip()):
            self.error_a.emit("輝度計測を使用する場合はBM9接続ポートを入力してください。")
            return

        preset = "jvl" if config.device_mode == "発光素子" else "opv"
        smu = registry.create_source_meter(
            config.device_type, config.connection, use_mock=config.use_mock, preset=preset
        )
        luminance_meter = None
        if config.use_luminance:
            luminance_meter = registry.create_luminance_meter(
                config.bm9_port, use_mock=config.use_mock
            )

        total_points = len(config.build_voltage_list())
        make_iterator = functools.partial(
            run_dual_a_sequence, smu, config, luminance_meter=luminance_meter
        )
        csv_save_fn = functools.partial(
            csv_writer.save_dual_a_csv,
            sample_name=config.sample_name,
            save_dir=config.save_dir,
            device_mode=config.device_mode,
            use_luminance=config.use_luminance,
        )

        self.log_appended_a.emit(
            f"{bvm.mock_log_prefix(config.use_mock)}モードA測定を開始します"
            f" ({config.connection}, 計測対象={config.device_mode})"
        )

        worker = MeasurementWorker(
            make_iterator,
            smu,
            total_points,
            luminance_meter=luminance_meter,
            csv_save_fn=csv_save_fn,
        )
        worker.point_measured.connect(self._on_mode_a_point_measured)
        worker.progress.connect(self._on_mode_a_progress)
        worker.finished_ok.connect(self._on_mode_a_finished_ok)
        worker.error.connect(self._on_mode_a_error)
        self._worker_a = worker

        self.running_changed_a.emit(True)
        worker.start()

    def stop_mode_a(self) -> None:
        if self._worker_a is not None:
            self._worker_a.request_stop()

    def _on_mode_a_point_measured(self, point) -> None:
        self.point_measured_a.emit(point)
        luminance = getattr(point, "luminance", None)
        message = f"V={point.voltage:.4f} V, I={point.current:.6e} A"
        if luminance is not None:
            message += f", L={luminance:.4f} cd/m2"
        self.log_appended_a.emit(message)

    def _on_mode_a_progress(self, current: int, total: int) -> None:
        self.progress_a.emit(current)

    def _on_mode_a_finished_ok(self, points: list, csv_path: str, aborted: bool) -> None:
        # 中断(ユーザーによるstop)と正常完了を明確に区別して表示する
        if aborted:
            message = f"モードA測定中断: {len(points)}点で停止しました。"
        else:
            message = f"モードA測定完了: {len(points)}点。"
        if csv_path:
            message += f" 保存先: {csv_path}"
        self.log_appended_a.emit(message)
        self.finished_ok_a.emit(points, csv_path, aborted)
        self._reset_mode_a_running_state()

    def _on_mode_a_error(self, message: str) -> None:
        self.error_appended_a.emit(message)
        self.error_a.emit(message)
        self._reset_mode_a_running_state()

    def _reset_mode_a_running_state(self) -> None:
        self.running_changed_a.emit(False)
        self._worker_a = None

    # ==================================================================
    # モードB(2素子同時計測)
    # ==================================================================
    def start_mode_b(self, config: DualBConfig) -> None:
        if self._worker_b is not None and self._worker_b.isRunning():
            return  # 二重起動防止(B-7節)

        chan_a = config.channel_a
        chan_b = config.channel_b

        if not chan_a.enabled and not chan_b.enabled:
            self.error_b.emit("チャンネルA・チャンネルBのうち少なくとも一方を有効にしてください。")
            return

        if (
            chan_a.enabled
            and chan_b.enabled
            and chan_a.device_mode == "発光素子"
            and chan_b.device_mode == "発光素子"
        ):
            self.error_b.emit(
                "チャンネルA・チャンネルBの両方を「発光素子」モードにすることはできません"
                "(輝度計は1台のため同時計測できません)。"
            )
            return

        if chan_a.enabled:
            if chan_a.v_max <= chan_a.v_min:
                self.error_b.emit(f"[chA] Vmax({chan_a.v_max})はVmin({chan_a.v_min})より大きい値にしてください。")
                return
            if chan_a.v_step <= 0:
                self.error_b.emit("[chA] Vstepは0より大きい値にしてください。")
                return
            if chan_a.iteration < 1:
                self.error_b.emit("[chA] 繰り返し回数は1回以上にしてください。")
                return

        if chan_b.enabled:
            if chan_b.v_max <= chan_b.v_min:
                self.error_b.emit(f"[chB] Vmax({chan_b.v_max})はVmin({chan_b.v_min})より大きい値にしてください。")
                return
            if chan_b.v_step <= 0:
                self.error_b.emit("[chB] Vstepは0より大きい値にしてください。")
                return
            if chan_b.iteration < 1:
                self.error_b.emit("[chB] 繰り返し回数は1回以上にしてください。")
                return

        led_channel = None
        if chan_a.enabled and chan_a.device_mode == "発光素子":
            led_channel = "A"
        elif chan_b.enabled and chan_b.device_mode == "発光素子":
            led_channel = "B"

        use_luminance_a = False
        use_luminance_b = False
        if led_channel == "A" and config.bm9_port:
            use_luminance_a = True
        elif led_channel == "B" and config.bm9_port:
            use_luminance_b = True

        preset = "jvl" if led_channel is not None else "opv"
        smu = registry.create_source_meter(
            _DEVICE_TYPE_2612B, config.connection, use_mock=config.use_mock, preset=preset
        )
        luminance_meter = None
        if config.bm9_port:
            luminance_meter = registry.create_luminance_meter(config.bm9_port, use_mock=config.use_mock)

        va_len = len(chan_a.build_voltage_list()) if chan_a.enabled else 0
        vb_len = len(chan_b.build_voltage_list()) if chan_b.enabled else 0
        total_points = va_len + vb_len

        make_iterator = functools.partial(
            run_dual_b_sequence, smu, config, luminance_meter=luminance_meter
        )
        csv_save_fn = functools.partial(
            self._save_mode_b_results,
            channel_a=chan_a,
            channel_b=chan_b,
            save_dir=config.save_dir,
            connection=config.connection,
            use_luminance_a=use_luminance_a,
            use_luminance_b=use_luminance_b,
        )

        self.log_appended_b.emit(
            f"{bvm.mock_log_prefix(config.use_mock)}モードB測定を開始します ({config.connection})"
        )

        worker = DualChannelWorker(
            make_iterator,
            smu,
            total_points,
            luminance_meter=luminance_meter,
            csv_save_fn=csv_save_fn,
        )
        worker.point_measured_a.connect(self._on_mode_b_point_measured_a)
        worker.point_measured_b.connect(self._on_mode_b_point_measured_b)
        worker.progress.connect(self._on_mode_b_progress)
        worker.finished_ok.connect(self._on_mode_b_finished_ok)
        worker.error.connect(self._on_mode_b_error)
        self._worker_b = worker

        self.running_changed_b.emit(True)
        worker.start()

    def stop_mode_b(self) -> None:
        if self._worker_b is not None:
            self._worker_b.request_stop()

    def _save_mode_b_results(
        self,
        points_a: list,
        points_b: list,
        aborted: bool,
        channel_a: ChannelConfig,
        channel_b: ChannelConfig,
        save_dir: str,
        connection: str,
        use_luminance_a: bool,
        use_luminance_b: bool,
    ) -> tuple[str, str]:
        path_a = ""
        path_b = ""
        if channel_a.enabled:
            path_a = csv_writer.save_dual_b_channel_csv(
                points_a,
                sample_name=channel_a.sample_name,
                save_dir=save_dir,
                channel="A",
                device_mode=channel_a.device_mode,
                use_luminance=use_luminance_a,
            )
        if channel_b.enabled:
            path_b = csv_writer.save_dual_b_channel_csv(
                points_b,
                sample_name=channel_b.sample_name,
                save_dir=save_dir,
                channel="B",
                device_mode=channel_b.device_mode,
                use_luminance=use_luminance_b,
            )

        meta_sample_name = self._combined_sample_name(channel_a, channel_b)
        csv_writer.save_dual_b_meta_json(
            sample_name=meta_sample_name,
            save_dir=save_dir,
            meta={
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "connection": connection,
                # ユーザー操作による中断で終了した測定かどうか(解析時の判断材料)
                "aborted": aborted,
                "channel_a": self._channel_meta(channel_a),
                "channel_b": self._channel_meta(channel_b),
            },
        )
        return path_a, path_b

    @staticmethod
    def _channel_meta(channel: ChannelConfig) -> dict:
        return {
            "enabled": channel.enabled,
            "device_mode": channel.device_mode,
            "v_min": channel.v_min,
            "v_max": channel.v_max,
            "v_step": channel.v_step,
            "iteration": channel.iteration,
            "nplc": channel.nplc,
            "delay_time": channel.delay_time,
            "sample_name": channel.sample_name,
        }

    @staticmethod
    def _combined_sample_name(channel_a: ChannelConfig, channel_b: ChannelConfig) -> str:
        if channel_a.enabled and channel_b.enabled:
            return f"{channel_a.sample_name}_{channel_b.sample_name}"
        if channel_a.enabled:
            return channel_a.sample_name
        return channel_b.sample_name

    def _on_mode_b_point_measured_a(self, point) -> None:
        self.point_measured_b_cha.emit(point)
        self._log_mode_b_point("A", point)

    def _on_mode_b_point_measured_b(self, point) -> None:
        self.point_measured_b_chb.emit(point)
        self._log_mode_b_point("B", point)

    def _log_mode_b_point(self, channel: str, point) -> None:
        message = f"[ch{channel}] V={point.voltage:.4f} V, I={point.current:.6e} A"
        if point.luminance is not None:
            message += f", L={point.luminance:.4f} cd/m2"
        self.log_appended_b.emit(message)

    def _on_mode_b_progress(self, current: int, total: int) -> None:
        self.progress_b.emit(current)

    def _on_mode_b_finished_ok(self, points: list, path_a: str, path_b: str, aborted: bool) -> None:
        # 中断(ユーザーによるstop)と正常完了を明確に区別して表示する
        if aborted:
            message = f"モードB測定中断: 合計{len(points)}点で停止しました。"
        else:
            message = f"モードB測定完了: 合計{len(points)}点。"
        if path_a:
            message += f" chA保存先: {path_a}"
        if path_b:
            message += f" chB保存先: {path_b}"
        self.log_appended_b.emit(message)
        self.finished_ok_b.emit(points, path_a, path_b, aborted)
        self._reset_mode_b_running_state()

    def _on_mode_b_error(self, message: str) -> None:
        self.error_appended_b.emit(message)
        self.error_b.emit(message)
        self._reset_mode_b_running_state()

    def _reset_mode_b_running_state(self) -> None:
        self.running_changed_b.emit(False)
        self._worker_b = None
