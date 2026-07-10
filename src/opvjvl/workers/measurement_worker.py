"""OPV/JVL/モードA共通のWorkerインフラ層。

要件定義書_基本設計書.md B-1節・B-7節に対応する。``measurement/sequences.py``
のジェネレータ関数をQThread上で駆動し、1点ごとに``pyqtSignal``へ変換する。
Qt依存はこの層に閉じ込め、Model層(``measurement/sequences.py`` 等)は一切
importしない側から見て非依存のまま保つ。

ViewModelは``sequences.py``の関数を``functools.partial``で``smu``・
``config``・(必要なら)``luminance_meter``まで束縛し、``is_aborted``のみを
引数に取るCallableとして``make_iterator``に渡す想定。
"""
from __future__ import annotations

from typing import Callable, List, Optional

from ..models.instruments.base import AbstractLuminanceMeter, AbstractSourceMeter
from ..qtcompat import QThread, pyqtSignal


class MeasurementWorker(QThread):
    """OPV/JVL/モードAの測定シーケンスをQThread上で実行するWorker。

    ``run()``は``smu.connect()``(必要なら``luminance_meter.connect()``も)
    してからイテレータを回し、1点ごとに``point_measured``/``progress``を
    発火する。例外は``InstrumentError``に限らず全て``error``シグナルに
    変換して伝播させ(B-7節)、``finally``節で必ず機器の``close()``を呼ぶ。
    """

    point_measured = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(list, str)
    error = pyqtSignal(str)

    def __init__(
        self,
        make_iterator: Callable[[Callable[[], bool]], object],
        smu: AbstractSourceMeter,
        total_points: int,
        luminance_meter: Optional[AbstractLuminanceMeter] = None,
        csv_save_fn: Optional[Callable[[list], str]] = None,
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
        try:
            self._smu.connect()
            if self._luminance_meter is not None:
                self._luminance_meter.connect()

            iterator = self._make_iterator(self._is_aborted)
            for point in iterator:
                points.append(point)
                self.point_measured.emit(point)
                self.progress.emit(len(points), self._total_points)
        except Exception as exc:  # noqa: BLE001 - B-7節: 未捕捉例外でスレッドを落とさない
            self.error.emit(str(exc))
            return
        finally:
            self._close_instruments()

        csv_path = ""
        if self._csv_save_fn is not None:
            try:
                csv_path = self._csv_save_fn(points)
            except Exception as exc:  # noqa: BLE001
                # CSV保存失敗はメモリ上の測定結果を失わせない(B-7節)。
                # finished_okは空パスで発火し、別途errorで通知する。
                self.error.emit(f"CSV保存に失敗しました: {exc}")

        self.finished_ok.emit(points, csv_path)

    def _close_instruments(self) -> None:
        try:
            self._smu.close()
        except Exception:  # noqa: BLE001 - close失敗で後続クローズを止めない
            pass
        if self._luminance_meter is not None:
            try:
                self._luminance_meter.close()
            except Exception:  # noqa: BLE001
                pass
