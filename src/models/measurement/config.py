"""測定シーケンスの設定オブジェクト群。

要件定義書_基本設計書.md B-5-2節に対応する。各`*Config`は対応するシーケンス
関数(`measurement/sequences.py`)への入力パラメータをまとめたdataclass。
Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np


@dataclass
class OPVConfig:
    """OPVモード(太陽電池JV/IV特性測定)の設定。既定値はA-4-2節の表に従う。"""

    device_type: Literal["keithley2400", "keithley2612b"] = "keithley2400"
    connection: str = "COM5"
    use_mock: bool = False
    v_min: float = -0.1
    v_max: float = 1.1
    v_step: float = 0.02
    iteration: int = 3
    compliance_current: float = 0.02
    nplc: float = 1.0
    delay_time: float = 1.0
    sample_name: str = "sample"
    save_dir: str = "."
    channel: Literal["smua", "smub"] = "smua"
    hysteresis: bool = False

    def build_voltage_list(self) -> np.ndarray:
        """Vmin〜Vmaxを刻み幅Vstepで生成し、各点をiteration回繰り返す。

        既存コード`Keithley2400_OPV.py`は`np.ones`+`np.append`で同等の処理を
        行っているが、`np.repeat(base, iteration)`の方が等価かつ簡潔なため
        こちらを採用する。

        ``hysteresis=True``の場合、往路(Vmin→Vmax)に続けて復路(Vmax→Vmin)を
        連結した往復掃引の電圧列を生成する。復路は往路の反転(``base[::-1]``)
        だが、折り返し点(Vmax)が往路の末尾・復路の先頭で重複しないよう
        ``base[::-1][1:]``として先頭1点を除いてから連結する。iteration回の
        繰り返しは、往復連結後の電圧列全体に対して適用する(各点を
        iteration回連続測定する既存仕様を維持)。
        """
        # arangeは半開区間かつ浮動小数点数の丸め誤差の影響を受けやすいため、
        # v_step * 0.5 のマージンを加えることで v_max を確実に含むようにする。
        base = np.arange(self.v_min, self.v_max + self.v_step * 0.5, self.v_step)
        if self.hysteresis:
            base = np.concatenate([base, base[::-1][1:]])
        return np.repeat(base, self.iteration)


@dataclass
class JVLConfig(OPVConfig):
    """JVLモード(発光素子IV-輝度測定/暗IV測定共通)の設定。

    既定値はOPVConfigの掃引条件を`Keithley2400_JVL.py`踏襲の値で上書きする
    (A-4-3節)。
    """

    v_min: float = -1.0
    v_max: float = 1.9
    v_step: float = 0.1
    use_luminance: bool = True
    bm9_port: Optional[str] = "COM4"


@dataclass
class DualAConfig(OPVConfig):
    """モードA(2ch低ノイズ計測)の設定。"""

    device_mode: Literal["太陽電池", "発光素子"] = "太陽電池"
    use_luminance: bool = False
    bm9_port: Optional[str] = None


@dataclass
class ChannelConfig:
    """モードBにおけるチャンネル1本分(smua or smub)の掃引条件。"""

    enabled: bool = True
    device_mode: Literal["太陽電池", "発光素子"] = "太陽電池"
    v_min: float = -0.1
    v_max: float = 1.1
    v_step: float = 0.02
    iteration: int = 3
    compliance_current: float = 0.02
    nplc: float = 1.0
    delay_time: float = 1.0
    sample_name: str = "sample"
    hold_at_end: Literal["last_value", "zero"] = "last_value"
    hysteresis: bool = False

    def build_voltage_list(self) -> np.ndarray:
        """Vmin〜Vmaxを刻み幅Vstepで生成し、各点をiteration回繰り返す。

        ``hysteresis=True``の場合、``OPVConfig.build_voltage_list``と同様に
        往路(Vmin→Vmax)+復路(Vmax→Vmin、折り返し点を重複させない)を連結した
        往復掃引の電圧列を生成してからiteration回の繰り返しを適用する。
        """
        # arangeは半開区間かつ浮動小数点数の丸め誤差の影響を受けやすいため、
        # v_step * 0.5 のマージンを加えることで v_max を確実に含むようにする。
        base = np.arange(self.v_min, self.v_max + self.v_step * 0.5, self.v_step)
        if self.hysteresis:
            base = np.concatenate([base, base[::-1][1:]])
        return np.repeat(base, self.iteration)


@dataclass
class DualBConfig:
    """モードB(2素子同時計測)の設定。チャンネルA/Bそれぞれの掃引条件を持つ。"""

    connection: str = ""
    use_mock: bool = False
    channel_a: ChannelConfig = field(default_factory=ChannelConfig)
    channel_b: ChannelConfig = field(
        default_factory=lambda: ChannelConfig(enabled=False)
    )
    bm9_port: Optional[str] = None
    save_dir: str = "."
