"""モードB(2素子同時計測)専用のWorkerインフラ層。

要件定義書_基本設計書.md B-1節・B-4-5節・B-7節に対応する。
``measurement/sequences.py``の``run_dual_b_sequence``が生成する
``ChannelPoint``(``channel``属性が``"A"``または``"B"``)を、チャンネル
ごとに別シグナルへ振り分ける。Qt依存はこの層に閉じ込める。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from models.instruments.base import AbstractLuminanceMeter, AbstractSourceMeter
from qtcompat import QThread, pyqtSignal


class DualChannelWorker(QThread):
    """モードB(2素子同時計測)の測定シーケンスをQThread上で実行するWorker。

    ``point.channel``が``"A"``なら``point_measured_a``、``"B"``なら
    ``point_measured_b``へ振り分けてemitする。それ以外の責務は
    ``MeasurementWorker``と同様(B-7節: 例外の全捕捉・機器のclose保証)。
    """

    point_measured_a = pyqtSignal(object)
    point_measured_b = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(list, str, str)
    error = pyqtSignal(str)

    def __init__(
        self,
        make_iterator: Callable[[Callable[[], bool]], object],
        smu: AbstractSourceMeter,
        total_points: int,
        luminance_meter: Optional[AbstractLuminanceMeter] = None,
        csv_save_fn: Optional[Callable[[list, list], "tuple[str, str]"]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._make_iterator = make_iterator
        self._smu = smu
        self._total_points = total_points
        self._luminance_meter = luminance_meter
        self._csv_save_fn = csv_save_fn
        self._abort_requested = False

    def request_stop(self) -> None:
        """協調的中断フラグを立てる。``QThread.terminate()``は絶対に使わない。"""
        self._abort_requested = True

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
            self.error.emit(str(exc))
            return
        finally:
            self._close_instruments()

        csv_path_a = ""
        csv_path_b = ""
        if self._csv_save_fn is not None:
            try:
                csv_path_a, csv_path_b = self._csv_save_fn(points_a, points_b)
            except Exception as exc:  # noqa: BLE001
                # CSV保存失敗はメモリ上の測定結果を失わせない(B-7節)。
                # finished_okは空パスで発火し、別途errorで通知する。
                self.error.emit(f"CSV保存に失敗しました: {exc}")

        self.finished_ok.emit(points, csv_path_a, csv_path_b)

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
