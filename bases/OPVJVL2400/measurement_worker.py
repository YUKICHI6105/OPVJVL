"""
measurement_worker.py
OPV測定・JVL測定を別スレッドで実行するワーカー群。

GUIスレッドをブロックしないよう測定ループはQThread上で実行し、
1点測定するごとにシグナルでGUI側へ結果を通知してリアルタイムプロット
更新に使う。

OPVMeasurementWorker : Keithley2400のみ。電圧リストを最後まで掃引する。
JVLMeasurementWorker : Keithley2400 + BM9。|電流| >= current_limit で早期終了する。
                       早期終了した場合もそれまでのデータは保存する。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from bases.OPVJVL2400.instruments import Keithley2400, BM9, InstrumentError


# ---------------------------------------------------------------------------
# 設定・測定点データクラス
# ---------------------------------------------------------------------------

@dataclass
class OPVConfig:
    keithley_port: str

    v_min: float = -0.1
    v_max: float = 1.1
    v_step: float = 0.02
    iteration: int = 3

    delay_time: float = 1.0
    nplc: float = 1.0
    compliance_current: float = 0.02
    auto_range: bool = True

    sample_name: str = "sample"
    save_dir: str = "."

    def build_voltage_list(self) -> np.ndarray:
        base = np.arange(self.v_min, self.v_max + self.v_step, self.v_step)
        return np.repeat(base, self.iteration)


@dataclass
class JVLConfig:
    keithley_port: str
    bm9_port: str

    v_min: float = -1.0
    v_max: float = 1.2
    v_step: float = 0.1
    iteration: int = 3

    delay_time: float = 1.0
    nplc: float = 1.0
    compliance_current: float = 0.02
    auto_range: bool = True

    current_limit: float = 1e-3  # |電流|がこれ以上で早期終了 [A] (デフォルト1mA)
    luminance_scale: float = 100.0  # BM9読み値に掛ける倍率

    sample_name: str = "sample"
    save_dir: str = "."

    def build_voltage_list(self) -> np.ndarray:
        base = np.arange(self.v_min, self.v_max + self.v_step, self.v_step)
        return np.repeat(base, self.iteration)


@dataclass
class OPVPoint:
    index: int
    voltage: float
    current: float


@dataclass
class JVLPoint:
    index: int
    voltage: float
    current: float
    luminance: float


# ---------------------------------------------------------------------------
# OPV測定ワーカー
# ---------------------------------------------------------------------------

class OPVMeasurementWorker(QThread):
    """
    Signals
    -------
    point_measured(object) : OPVPointが1点測定されるたびに発火
    progress(int, int)     : (現在の点番号, 全点数)
    finished_ok(str)       : 正常終了。引数は保存先CSVパス
    error(str)             : 例外発生時のエラーメッセージ
    log(str)               : ログ用テキスト
    """

    point_measured = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, config: OPVConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._abort_requested = False

    def request_abort(self):
        self._abort_requested = True

    def run(self):
        cfg = self.config
        keithley: Optional[Keithley2400] = None

        try:
            self.log.emit("[OPV] Keithley2400に接続しています...")
            keithley = Keithley2400(cfg.keithley_port)
            idn = keithley.connect()
            self.log.emit(f"[OPV] 接続成功: {idn}")

            keithley.reset()
            keithley.clear_status()
            keithley.configure_source_voltage(
                compliance_current=cfg.compliance_current,
                nplc=cfg.nplc,
                auto_range=cfg.auto_range,
            )

            voltage_list = cfg.build_voltage_list()
            n_points = len(voltage_list)
            est_min = n_points * (cfg.delay_time + cfg.nplc / 60.0) / 60.0
            self.log.emit(f"[OPV] 測定点数: {n_points}, 推定所要時間: 約{est_min:.1f}分")

            results: list[OPVPoint] = []
            keithley.output_on()

            for i, voltage in enumerate(voltage_list):
                if self._abort_requested:
                    self.log.emit("[OPV] ユーザーにより測定が中断されました。")
                    break

                voltage = float(voltage)
                keithley.set_voltage(voltage)
                time.sleep(cfg.delay_time)

                current = keithley.measure_current()

                point = OPVPoint(index=i, voltage=voltage, current=current)
                results.append(point)

                self.point_measured.emit(point)
                self.progress.emit(i + 1, n_points)

            keithley.output_off()

            csv_path = self._save_results(results)
            self.finished_ok.emit(csv_path)

        except InstrumentError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"予期しないエラーが発生しました: {e}")
        finally:
            if keithley is not None:
                try:
                    keithley.output_off()
                except Exception:
                    pass
                try:
                    keithley.close()
                except Exception:
                    pass

    def _save_results(self, results: list[OPVPoint]) -> str:
        cfg = self.config
        data = {
            "voltage [V]": [p.voltage for p in results],
            "current [A]": [p.current for p in results],
        }
        df = pd.DataFrame(data)
        os.makedirs(cfg.save_dir, exist_ok=True)
        csv_path = os.path.join(cfg.save_dir, f"{cfg.sample_name}_OPV_measurement_data.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8")
        self.log.emit(f"[OPV] 保存しました: {csv_path}")
        return csv_path


# ---------------------------------------------------------------------------
# JVL測定ワーカー
# ---------------------------------------------------------------------------

class JVLMeasurementWorker(QThread):
    """
    Signals
    -------
    point_measured(object) : JVLPointが1点測定されるたびに発火
    progress(int, int)     : (現在の点番号, 全点数)
    finished_ok(str)       : 正常終了(または早期終了・中断)。引数は保存先CSVパス
    error(str)             : 例外発生時のエラーメッセージ
    log(str)               : ログ用テキスト
    """

    point_measured = pyqtSignal(object)
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, config: JVLConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._abort_requested = False

    def request_abort(self):
        self._abort_requested = True

    def run(self):
        cfg = self.config
        keithley: Optional[Keithley2400] = None
        bm9: Optional[BM9] = None

        try:
            self.log.emit("[JVL] Keithley2400に接続しています...")
            keithley = Keithley2400(cfg.keithley_port)
            idn = keithley.connect()
            self.log.emit(f"[JVL] 接続成功: {idn}")

            self.log.emit("[JVL] BM9に接続しています...")
            bm9 = BM9(cfg.bm9_port)
            bm9.connect()
            self.log.emit("[JVL] BM9接続成功")

            keithley.reset()
            keithley.clear_status()
            keithley.configure_source_voltage(
                compliance_current=cfg.compliance_current,
                nplc=cfg.nplc,
                auto_range=cfg.auto_range,
            )

            voltage_list = cfg.build_voltage_list()
            n_points = len(voltage_list)
            est_min = n_points * (cfg.delay_time + cfg.nplc / 60.0) / 60.0
            self.log.emit(
                f"[JVL] 測定点数(最大): {n_points}, 推定所要時間(最大): 約{est_min:.1f}分, "
                f"電流上限: {cfg.current_limit * 1000:.3f} mA"
            )

            results: list[JVLPoint] = []
            stopped_early = False
            keithley.output_on()

            for i, voltage in enumerate(voltage_list):
                if self._abort_requested:
                    self.log.emit("[JVL] ユーザーにより測定が中断されました。")
                    break

                voltage = float(voltage)
                keithley.set_voltage(voltage)
                time.sleep(cfg.delay_time)

                current = keithley.measure_current()
                luminance = bm9.get_luminance() * cfg.luminance_scale

                point = JVLPoint(index=i, voltage=voltage, current=current, luminance=luminance)
                results.append(point)

                self.point_measured.emit(point)
                self.progress.emit(i + 1, n_points)

                if abs(current) >= cfg.current_limit:
                    self.log.emit(
                        f"[JVL] |電流|={abs(current)*1000:.3f} mA が上限"
                        f"{cfg.current_limit*1000:.3f} mAを超えたため測定を終了します。"
                    )
                    stopped_early = True
                    break

            keithley.output_off()

            if not stopped_early and not self._abort_requested:
                self.log.emit("[JVL] 電圧掃引が上限Vmaxまで完了しました。")

            csv_path = self._save_results(results)
            self.finished_ok.emit(csv_path)

        except InstrumentError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"予期しないエラーが発生しました: {e}")
        finally:
            if keithley is not None:
                try:
                    keithley.output_off()
                except Exception:
                    pass
                try:
                    keithley.close()
                except Exception:
                    pass
            if bm9 is not None:
                try:
                    bm9.close()
                except Exception:
                    pass

    def _save_results(self, results: list[JVLPoint]) -> str:
        """早期終了・中断の場合でも、それまでの部分データを保存する。"""
        cfg = self.config
        data = {
            "voltage [V]": [p.voltage for p in results],
            "current [A]": [p.current for p in results],
            "luminance [cd/m2]": [p.luminance for p in results],
        }
        df = pd.DataFrame(data)
        os.makedirs(cfg.save_dir, exist_ok=True)
        csv_path = os.path.join(cfg.save_dir, f"{cfg.sample_name}_JVL_measurement_data.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8")
        self.log.emit(f"[JVL] 保存しました({len(results)}点): {csv_path}")
        return csv_path
