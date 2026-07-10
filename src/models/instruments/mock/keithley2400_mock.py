"""Keithley 2400 のモッククラス。

要件定義書_基本設計書.md A-6節に基づき、ダイオード方程式
``I = I0 * (exp(V / (n*Vt)) - 1) - I_L`` に基づく擬似IV特性を生成する。
実機ドライバとは独立に、``AbstractSourceMeter`` のみに依存する。
serial/pyvisaはimportしない。time.sleepも使用しない
(待機制御は上位のシーケンス関数側でsleep_fnにより行う)。
"""
from __future__ import annotations

import numpy as np

from models.instruments.base import AbstractSourceMeter, InstrumentError

#: 室温近似の熱電圧 kT/q [V]
VT_ROOM_TEMPERATURE = 0.02585


class Keithley2400Mock(AbstractSourceMeter):
    """Keithley 2400 と同一インタフェースを持つダイオード方程式ベースのモック。

    Keithley2400は物理的に1チャンネルしかないため、``channel`` 引数は
    受け取るが内部では無視する(常に単一の内部状態を参照する)。
    """

    channels: tuple[str, ...] = ("default",)

    def __init__(
        self,
        connection: str,
        I0: float = 1e-10,
        n: float = 1.5,
        I_L: float = 0.0,
        noise_std: float = 1e-6,
        seed: int | None = None,
        compliance_current: float = 0.02,
        simulate_connect_failure: bool = False,
        fail_after_n_points: int | None = None,
    ) -> None:
        self.connection = connection
        self.I0 = I0
        self.n = n
        self.I_L = I_L
        self.noise_std = noise_std
        self.compliance_current = compliance_current
        self.simulate_connect_failure = simulate_connect_failure
        self.fail_after_n_points = fail_after_n_points

        self._rng = np.random.default_rng(seed)
        self._voltage = 0.0
        self._output_on = False
        self._measure_count = 0

        self.connected = False
        self.connect_calls = 0
        self.close_calls = 0
        self.reset_calls = 0
        self.output_calls: list[tuple[str, bool]] = []
        self.configure_calls: list[tuple[str, float, float, bool]] = []

    # -- プリセット ---------------------------------------------------

    @classmethod
    def for_opv(cls, connection: str, **kwargs) -> Keithley2400Mock:
        """太陽電池(OPV)用プリセット。光電流オフセット I_L > 0 を既定にする。"""
        kwargs.setdefault("I_L", 1e-3)
        return cls(connection, **kwargs)

    @classmethod
    def for_jvl(cls, connection: str, **kwargs) -> Keithley2400Mock:
        """発光素子(JVL)用プリセット。整流特性のみ(I_L = 0)。"""
        kwargs.setdefault("I_L", 0.0)
        return cls(connection, **kwargs)

    # -- AbstractSourceMeter実装 ---------------------------------------

    def connect(self, timeout_ms: int = 30000) -> str:
        self.connect_calls += 1
        if self.simulate_connect_failure:
            raise InstrumentError("Keithley2400Mock: simulated connection failure")
        self.connected = True
        return "MOCK,Keithley2400Mock,0,1.0"

    def close(self) -> None:
        self.close_calls += 1
        self.connected = False

    def reset(self) -> None:
        self.reset_calls += 1
        self._voltage = 0.0
        self._output_on = False

    def configure_source_voltage(
        self,
        channel: str,
        compliance_current: float,
        nplc: float,
        auto_range: bool = True,
    ) -> None:
        self.compliance_current = compliance_current
        self.configure_calls.append((channel, compliance_current, nplc, auto_range))

    def set_output(self, channel: str, on: bool) -> None:
        self._output_on = on
        self.output_calls.append((channel, on))

    def set_voltage(self, channel: str, voltage: float) -> None:
        self._voltage = voltage

    def measure_current(self, channel: str) -> float:
        self._measure_count += 1
        if (
            self.fail_after_n_points is not None
            and self._measure_count > self.fail_after_n_points
        ):
            raise InstrumentError(
                "Keithley2400Mock: simulated failure after "
                f"{self.fail_after_n_points} measurement(s)"
            )
        current = self._diode_current(self._voltage)
        current += self._rng.normal(0.0, self.noise_std)
        limit = abs(self.compliance_current)
        return float(np.clip(current, -limit, limit))

    def measure_voltage(self, channel: str) -> float:
        return self._voltage + float(self._rng.normal(0.0, self.noise_std))

    # -- 内部ヘルパ ------------------------------------------------------

    def _diode_current(self, voltage: float) -> float:
        return self.I0 * (np.exp(voltage / (self.n * VT_ROOM_TEMPERATURE)) - 1.0) - self.I_L
