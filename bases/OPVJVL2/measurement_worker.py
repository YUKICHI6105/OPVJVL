"""
measurement_worker.py
JVL(電流密度-電圧-輝度)測定を別スレッドで実行するワーカー。

GUIスレッドをブロックしないよう、測定ループはQThread上で実行し、
1点測定するごとにシグナルでGUI側へ結果を通知してリアルタイムプロット
更新に使う。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from bases.OPVJVL2.instruments import Keithley2612B, BM9, InstrumentError


@dataclass
class MeasurementConfig:
    # Keithley接続
    keithley_resource: str
    visa_library: str = "@ivi"

    # 掃引条件
    v_min: float = -0.1
    v_max: float = 1.1
    v_step: float = 0.02
    iteration: int = 5  # 各電圧での繰り返し測定回数(過渡電流モニター用)

    # タイミング
    integration_nplc: float = 0.5   # 積分時間(NPLC)
    delay_time: float = 0.5         # 電圧設定後、測定までの待機時間 [s]

    # チャンネル構成
    #   "single": smuaのみで電圧掃引・電流測定(OPV_measurement.py相当)
    #   "dual"  : smuaで電圧掃引、smubを0V固定して電流測定(ver2相当)
    channel_mode: str = "single"

    # 輝度計(BM9)
    use_luminance: bool = False
    bm9_port: Optional[str] = None

    # 保存
    sample_name: str = "sample"
    save_dir: str = "."

    def build_voltage_list(self) -> np.ndarray:
        base = np.arange(self.v_min, self.v_max + self.v_step, self.v_step)
        repeated = np.repeat(base, self.iteration)
        return repeated


@dataclass
class MeasurementPoint:
    index: int
    voltage: float
    current: float
    luminance: Optional[float] = None


class MeasurementWorker(QThread):
    """
    JVL測定を実行するワーカースレッド。

    Signals
    -------
    point_measured(object)  : MeasurementPointが1点測定されるたびに発火
    progress(int, int)      : (現在の点番号, 全点数)
    finished_ok(str)        : 正常終了。引数は保存先CSVパス
    error(str)              : 例外発生時のエラーメッセージ
    log(str)                : ログ用テキスト(GUIのログ欄に流す)
    """

    point_measured = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, config: MeasurementConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._abort_requested = False

    def request_abort(self):
        """外部から測定の中断を要求する。"""
        self._abort_requested = True

    def run(self):
        cfg = self.config
        keithley: Optional[Keithley2612B] = None
        bm9: Optional[BM9] = None

        try:
            self.log.emit("Keithleyに接続しています...")
            keithley = Keithley2612B(cfg.keithley_resource, cfg.visa_library)
            idn = keithley.connect()
            self.log.emit(f"接続成功: {idn}")

            keithley.set_integration_time("smua", cfg.integration_nplc)
            keithley.set_source_function_voltage("smua")
            if cfg.channel_mode == "dual":
                keithley.set_integration_time("smub", cfg.integration_nplc)
                keithley.set_source_function_voltage("smub")

            if cfg.use_luminance:
                if not cfg.bm9_port:
                    raise InstrumentError("輝度測定が有効ですが、BM9のポートが指定されていません。")
                self.log.emit("BM9に接続しています...")
                bm9 = BM9(cfg.bm9_port)
                bm9.connect()
                self.log.emit("BM9接続成功")

            voltage_list = cfg.build_voltage_list()
            n_points = len(voltage_list)
            est_min = n_points * (cfg.delay_time + cfg.integration_nplc / 60.0) / 60.0
            self.log.emit(f"測定点数: {n_points}, 推定所要時間: 約{est_min:.1f}分")

            results: list[MeasurementPoint] = []

            keithley.set_output("smua", True)
            if cfg.channel_mode == "dual":
                keithley.set_output("smub", True)

            for i, voltage in enumerate(voltage_list):
                if self._abort_requested:
                    self.log.emit("ユーザーにより測定が中断されました。")
                    break

                voltage = float(voltage)
                keithley.set_voltage("smua", voltage)
                if cfg.channel_mode == "dual":
                    keithley.set_voltage("smub", 0.0)

                time.sleep(cfg.delay_time)

                if cfg.channel_mode == "dual":
                    current = -1.0 * keithley.measure_current("smub")
                else:
                    current = keithley.measure_current("smua")

                luminance = None
                if cfg.use_luminance and bm9 is not None:
                    luminance = bm9.get_luminance()

                point = MeasurementPoint(index=i, voltage=voltage, current=current, luminance=luminance)
                results.append(point)

                self.point_measured.emit(point)
                self.progress.emit(i + 1, n_points)

            keithley.set_output("smua", False)
            if cfg.channel_mode == "dual":
                keithley.set_output("smub", False)

            csv_path = self._save_results(results)
            self.finished_ok.emit(csv_path)

        except InstrumentError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"予期しないエラーが発生しました: {e}")
        finally:
            if keithley is not None:
                try:
                    keithley.close()
                except Exception:
                    pass
            if bm9 is not None:
                try:
                    bm9.close()
                except Exception:
                    pass

    def _save_results(self, results: list[MeasurementPoint]) -> str:
        import os
        import pandas as pd

        cfg = self.config
        data = {
            "voltage [V]": [p.voltage for p in results],
            "current [A]": [p.current for p in results],
        }
        if cfg.use_luminance:
            data["luminance [cd/m2]"] = [p.luminance for p in results]

        df = pd.DataFrame(data)
        os.makedirs(cfg.save_dir, exist_ok=True)
        csv_path = os.path.join(cfg.save_dir, f"{cfg.sample_name}_JVL_measurement_data.csv")
        df.to_csv(csv_path, index=False)
        self.log.emit(f"保存しました: {csv_path}")
        return csv_path
