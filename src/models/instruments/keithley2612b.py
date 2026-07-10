"""Keithley 2612B 実機ドライバ。

PyVISA + TSP(Lua)コマンドでKeithley 2612Bを制御する。サードパーティの
``keithley2600``パッケージには依存せず、TSPコマンドを直接送受信する自前
実装とする(要件定義書 A-3節の合意事項)。移植元は
``OPVJVL2/instruments.py``の``Keithley2612B``。
"""
from __future__ import annotations

from typing import Optional

try:
    import pyvisa
except ImportError:
    pyvisa = None

from models.instruments.base import AbstractSourceMeter, InstrumentError


class Keithley2612B(AbstractSourceMeter):
    """PyVISA + TSPコマンドでKeithley 2612Bを制御するクラス。"""

    channels: tuple[str, ...] = ("smua", "smub")

    def __init__(self, resource_name: str, visa_library: str = "@ivi"):
        self.resource_name = resource_name
        self.visa_library = visa_library
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._inst: Optional[pyvisa.resources.MessageBasedResource] = None

    def connect(self, timeout_ms: int = 30000) -> str:
        if pyvisa is None:
            raise InstrumentError("pyvisa がインストールされていないため、Keithley2612B 実機は使用できません。")
        try:
            self._rm = pyvisa.ResourceManager(self.visa_library)
            self._inst = self._rm.open_resource(self.resource_name)
            self._inst.timeout = timeout_ms
            self._inst.write_termination = "\n"
            self._inst.read_termination = "\n"
            self._inst.write("*IDN?")
            return self._inst.read().strip()
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithley2612Bへの接続に失敗しました: {e}") from e

    def close(self) -> None:
        if self._inst is not None:
            try:
                self._inst.close()
            except pyvisa.errors.VisaIOError:
                pass
            self._inst = None
        if self._rm is not None:
            try:
                self._rm.close()
            except pyvisa.errors.VisaIOError:
                pass
            self._rm = None

    def _require_connection(self) -> None:
        if self._inst is None:
            raise InstrumentError(
                "Keithley2612Bが接続されていません。connect()を先に呼んでください。"
            )

    # ------------------------------------------------------------------
    # 低レベルTSP通信
    # ------------------------------------------------------------------
    def _write(self, tsp_command: str) -> None:
        self._require_connection()
        try:
            self._inst.write(tsp_command)
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithley2612Bへの書き込みに失敗しました: {e}") from e

    def _query(self, tsp_expression: str) -> str:
        # TSPには通常のSCPIクエリ相当がないため、print()経由で値を読み出す。
        self._require_connection()
        try:
            self._inst.write(f"print({tsp_expression})")
            return self._inst.read().strip()
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithley2612Bからの読み取りに失敗しました: {e}") from e

    @staticmethod
    def _validate_channel(channel: str) -> None:
        if channel not in ("smua", "smub"):
            raise ValueError(f"不正なチャンネル指定です: {channel!r} (smua/smubのみ)")

    # ------------------------------------------------------------------
    # AbstractSourceMeter 実装
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self._write("reset()")

    def configure_source_voltage(
        self,
        channel: str,
        compliance_current: float,
        nplc: float,
        auto_range: bool = True,
    ) -> None:
        self._validate_channel(channel)
        self._write(f"{channel}.source.func = {channel}.OUTPUT_DCVOLTS")
        self._write(f"{channel}.source.limiti = {compliance_current}")
        self._write(f"{channel}.measure.nplc = {nplc}")
        auto_state = "AUTORANGE_ON" if auto_range else "AUTORANGE_OFF"
        self._write(f"{channel}.measure.autorangei = {channel}.{auto_state}")
        self.set_output(channel, False)

    def set_output(self, channel: str, on: bool) -> None:
        self._validate_channel(channel)
        state = f"{channel}.OUTPUT_ON" if on else f"{channel}.OUTPUT_OFF"
        self._write(f"{channel}.source.output = {state}")

    def set_voltage(self, channel: str, voltage: float) -> None:
        self._validate_channel(channel)
        self._write(f"{channel}.source.levelv = {voltage}")

    def measure_current(self, channel: str) -> float:
        self._validate_channel(channel)
        result = self._query(f"{channel}.measure.i()")
        try:
            return float(result)
        except ValueError as e:
            raise InstrumentError(f"電流測定値のパースに失敗しました: {result!r}") from e

    def measure_voltage(self, channel: str) -> float:
        self._validate_channel(channel)
        result = self._query(f"{channel}.measure.v()")
        try:
            return float(result)
        except ValueError as e:
            raise InstrumentError(f"電圧測定値のパースに失敗しました: {result!r}") from e
