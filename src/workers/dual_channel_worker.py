"""モードB(2素子同時計測)専用のWorkerインフラ層。

要件定義書_基本設計書.md B-1節・B-4-5節・B-7節に対応する。
``measurement/sequences.py``の``run_dual_b_sequence``が生成する
``ChannelPoint``(``channel``属性が``"A"``または``"B"``)を、チャンネル
ごとに別シグナルへ振り分ける。Qt依存はこの層に閉じ込める。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

from models.instruments.base import AbstractLuminanceMeter, AbstractSourceMeter
from models.measurement.config import ChannelConfig
from qtcompat import QThread, pyqtSignal
from utils.logger import get_logger

logger = get_logger("dual_channel_worker")


class DualChannelWorker(QThread):
    """モードB(2素子同時計測)の測定シーケンスをQThread上で実行するWorker。

    ``point.channel``が``"A"``なら``point_measured_a``、``"B"``なら
    ``point_measured_b``へ振り分けてemitする。それ以外の責務は
    ``MeasurementWorker``と同様(B-7節: 例外の全捕捉・機器のclose保証)。

    ``finished_ok``の第4引数``aborted``は、``request_stop()``による
    協調的中断で終了した場合にTrueとなる(正常完了との区別)。
    ``csv_save_fn``には中断有無を渡し、メタ情報(サイドカーJSON)へ
    記録できるようにする。
    """

    point_measured_a = pyqtSignal(object)
    point_measured_b = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(list, str, str, bool)  # points, csv_a, csv_b, aborted
    error = pyqtSignal(str)
    contact_check_reading = pyqtSignal(str, float, float)
    contact_check_finished = pyqtSignal()

    def __init__(
        self,
        make_iterator: Callable[[Callable[[], bool]], object],
        smu: AbstractSourceMeter,
        total_points: int,
        luminance_meter: Optional[AbstractLuminanceMeter] = None,
        csv_save_fn: Optional[Callable[[list, list, bool], "tuple[str, str]"]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._make_iterator = make_iterator
        self._smu = smu
        self._total_points = total_points
        self._luminance_meter = luminance_meter
        self._csv_save_fn = csv_save_fn
        self._abort_requested = False
        self._aborted_channels: set[str] = set()
        self._pending_lock = threading.Lock()
        self._pending_channel: Optional[tuple[str, ChannelConfig, Optional[AbstractLuminanceMeter]]] = None
        self._accepting_channels = True
        self._measurement_channels: set[str] = set()
        self._contact_request = None
        self._contact_state = None
        self._contact_stop_requested = False

    def reserve_measurement_channels(self, channels: set[str]) -> None:
        self._measurement_channels.update(channels)

    def request_contact_check(self, channel, device_mode, compliance, nplc, threshold, v_max) -> bool:
        with self._pending_lock:
            if (not self._accepting_channels or self._abort_requested
                    or channel in self._measurement_channels or self._contact_request is not None):
                return False
            self._contact_request = (channel, device_mode, compliance, nplc, threshold, v_max)
            self._contact_stop_requested = False
            return True

    def request_stop_contact_check(self) -> None:
        with self._pending_lock:
            self._contact_stop_requested = True

    def _finish_contact_check(self) -> None:
        if self._contact_state is not None:
            self._smu.set_output(self._contact_state["source"], False)
        with self._pending_lock:
            existed = self._contact_request is not None
            self._contact_request = None
            self._contact_state = None
            self._contact_stop_requested = False
        if existed:
            self.contact_check_finished.emit()

    def service_contact_check(self) -> None:
        """測定スレッド内で空きチャネルを処理する。SMU全体のresetは行わない。"""
        with self._pending_lock:
            request = self._contact_request
            stop = self._contact_stop_requested
        if request is None:
            return
        if stop:
            self._finish_contact_check()
            return
        channel, mode, compliance, nplc, threshold, v_max = request
        source = "smua" if channel == "A" else "smub"
        now = time.monotonic()
        if self._contact_state is None:
            self._smu.configure_source_voltage(source, compliance, nplc)
            self._smu.set_voltage(source, 0.0)
            self._smu.set_output(source, True)
            self._contact_state = {"source": source, "voltage": 0.0,
                                   "due": time.monotonic() + 0.05, "holding": mode != "発光素子"}
            return
        state = self._contact_state
        if now < state["due"]:
            return
        current = self._smu.measure_current(source)
        self.contact_check_reading.emit(channel, state["voltage"], current)
        if not state["holding"] and abs(current) >= threshold:
            state["holding"] = True
        if state["holding"]:
            state["due"] = time.monotonic() + 0.2
        else:
            voltage = round(state["voltage"] + 0.05, 10)
            if voltage > v_max:
                self._finish_contact_check()
                return
            state["voltage"] = voltage
            self._smu.set_voltage(source, voltage)
            state["due"] = time.monotonic() + 0.05

    def request_add_channel(
        self, channel: str, config: ChannelConfig,
        luminance_meter: Optional[AbstractLuminanceMeter] = None,
    ) -> bool:
        """空きチャンネルの開始要求を測定スレッドへ安全に渡す。"""
        with self._pending_lock:
            if (self._abort_requested or channel in self._aborted_channels
                    or not self._accepting_channels or self._pending_channel is not None
                    or (self._contact_request is not None and self._contact_request[0] == channel)):
                return False
            self._measurement_channels.add(channel)
            self._pending_channel = (channel, config, luminance_meter)
            self._total_points += len(config.build_voltage_list())
            return True

    def take_pending_channel(self) -> Optional[tuple[str, ChannelConfig]]:
        with self._pending_lock:
            pending = self._pending_channel
            self._pending_channel = None
        if pending is None:
            return None
        channel, config, meter = pending
        if meter is not None:
            try:
                meter.connect()
            except Exception:
                meter.close()
                raise
            self._luminance_meter = meter
        return channel, config

    def get_luminance_meter(self) -> Optional[AbstractLuminanceMeter]:
        return self._luminance_meter

    def finish_if_no_pending(self) -> bool:
        """最後の測定点と追加要求の競合を防いで受付を終了する。"""
        with self._pending_lock:
            if self._pending_channel is not None:
                return False
            self._accepting_channels = False
            return True

    def request_stop(self) -> None:
        """協調的中断フラグを立てる。``QThread.terminate()``は絶対に使わない。"""
        with self._pending_lock:
            self._abort_requested = True
            self._aborted_channels.update(("A", "B"))
            self._accepting_channels = False

    def request_stop_channel(self, channel: str) -> bool:
        """指定チャンネルだけを停止し、もう一方の掃引は継続する。"""
        if channel not in ("A", "B"):
            return False
        with self._pending_lock:
            if (self._abort_requested or not self._accepting_channels
                    or channel in self._aborted_channels):
                return False
            self._aborted_channels.add(channel)
            return True

    def is_channel_aborted(self, channel: str) -> bool:
        with self._pending_lock:
            return channel in self._aborted_channels

    @property
    def aborted_channels(self) -> frozenset[str]:
        with self._pending_lock:
            return frozenset(self._aborted_channels)

    def _is_aborted(self) -> bool:
        return self._abort_requested

    def run(self) -> None:
        points: List[object] = []
        points_a: List[object] = []
        points_b: List[object] = []
        try:
            self._smu.connect()
            if self._luminance_meter is not None:
                self._luminance_meter.connect()

            iterator = self._make_iterator(self._is_aborted)
            for point in iterator:
                points.append(point)
                if point.channel == "A":
                    points_a.append(point)
                    self.point_measured_a.emit(point)
                else:
                    points_b.append(point)
                    self.point_measured_b.emit(point)
                self.progress.emit(len(points), self._total_points)
        except Exception as exc:  # noqa: BLE001 - B-7節: 未捕捉例外でスレッドを落とさない
            logger.error("DualChannelWorker error: %s", exc)
            self.error.emit(str(exc))
            return
        finally:
            with self._pending_lock:
                self._accepting_channels = False
            try:
                self._finish_contact_check()
            finally:
                self._close_instruments()

        aborted = self._abort_requested or bool(self.aborted_channels)
        csv_path_a = ""
        csv_path_b = ""
        if self._csv_save_fn is not None:
            try:
                csv_path_a, csv_path_b = self._csv_save_fn(points_a, points_b, aborted)
            except Exception as exc:  # noqa: BLE001
                # CSV保存失敗はメモリ上の測定結果を失わせない(B-7節)。
                # finished_okは空パスで発火し、別途errorで通知する。
                logger.error("DualChannelWorker CSV save failed: %s", exc)
                self.error.emit(f"CSV保存に失敗しました: {exc}")

        logger.info(
            "DualChannelWorker finished: points=%d, aborted=%s", len(points), aborted
        )
        self.finished_ok.emit(points, csv_path_a, csv_path_b, aborted)

    def _close_instruments(self) -> None:
        try:
            try:
                self._smu.set_output("smua", False)
            except Exception:
                pass
            try:
                self._smu.set_output("smub", False)
            except Exception:
                pass
        finally:
            try:
                self._smu.close()
            except Exception:  # noqa: BLE001
                pass
        if self._luminance_meter is not None:
            try:
                self._luminance_meter.close()
            except Exception:  # noqa: BLE001
                pass
