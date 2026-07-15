"""機器抽象化の基底クラス群。

要件定義書_基本設計書.md B-2節に対応する。Keithley2400 / Keithley2612B を
機種非依存に扱うための ``AbstractSourceMeter`` と、TOPCON BM9 輝度計を扱う
``AbstractLuminanceMeter`` を定義する。実機ドライバ・モッククラスは双方とも
これらの抽象基底クラスを継承し、上位層(measurement/sequences.py, workers,
viewmodels)は具象クラスを意識せずに扱える。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class InstrumentError(Exception):
    """測定器関連の例外の基底クラス。"""


class AbstractSourceMeter(ABC):
    """Keithley 2400 / 2612B を機種非依存に扱うための共通インタフェース。

    Keithley2400は物理的に1チャンネルしか持たないため、channel引数には
    常に ``"default"`` を渡す(実装側は引数を受け取るが内部では無視してよい)。
    Keithley2612Bはchannelに ``"smua"`` または ``"smub"`` を渡す。
    """

    #: このインスタンスが公開するチャンネル名の一覧
    channels: tuple[str, ...] = ()

    @abstractmethod
    def connect(self, timeout_ms: int = 30000) -> str:
        """機器に接続し、``*IDN?`` 相当の識別文字列を返す。失敗時は ``InstrumentError``。"""

    @abstractmethod
    def close(self) -> None:
        """機器との接続を閉じる。"""

    @abstractmethod
    def reset(self) -> None:
        """機器を初期状態にリセットする。"""

    @abstractmethod
    def configure_source_voltage(
        self,
        channel: str,
        compliance_current: float,
        nplc: float,
    ) -> None:
        """電圧ソースモードを設定する。電流レンジは常にオートレンジとする。"""

    @abstractmethod
    def set_output(self, channel: str, on: bool) -> None:
        """指定チャンネルの出力をON/OFFする。"""

    @abstractmethod
    def set_voltage(self, channel: str, voltage: float) -> None:
        """指定チャンネルの出力電圧を設定する。"""

    @abstractmethod
    def measure_current(self, channel: str) -> float:
        """指定チャンネルの電流を測定して返す [A]。"""

    @abstractmethod
    def measure_voltage(self, channel: str) -> float:
        """指定チャンネルの電圧を測定して返す [V]。"""

    def __enter__(self) -> "AbstractSourceMeter":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class AbstractLuminanceMeter(ABC):
    """TOPCON BM9 等の輝度計を機種非依存に扱うための共通インタフェース。"""

    @abstractmethod
    def connect(self) -> None:
        """機器に接続する。失敗時は ``InstrumentError``。"""

    @abstractmethod
    def close(self) -> None:
        """機器との接続を閉じる。"""

    @abstractmethod
    def get_luminance(self) -> float:
        """輝度を測定して返す [cd/m2]。"""

    def __enter__(self) -> "AbstractLuminanceMeter":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
