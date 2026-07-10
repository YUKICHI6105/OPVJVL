"""Keithley 2400 実機ドライバ。

RS-232シリアル(9600bps, 8N1)経由でSCPIコマンドを送受信する。移植元は
``keithley2400/InstrumentsControl.py``。Keithley2400は物理的に1チャンネル
しか持たないため、``AbstractSourceMeter``のメソッドが要求する``channel``
引数は受け取るが内部では使用しない。
"""
from __future__ import annotations

import time
from typing import Optional

import serial

from models.instruments.base import AbstractSourceMeter, InstrumentError


class Keithley2400(AbstractSourceMeter):
    """RS-232 + SCPIでKeithley 2400を制御するクラス。"""

    channels: tuple[str, ...] = ("default",)

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self, timeout_ms: int = 30000) -> str:
        self.timeout = timeout_ms / 1000.0
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except serial.SerialException as e:
            raise InstrumentError(
                f"Keithley2400への接続に失敗しました ({self.port}): {e}"
            ) from e

        try:
            return self._query("*IDN?")
        except InstrumentError:
            raise
        except Exception as e:
            raise InstrumentError(f"*IDN?応答の取得に失敗しました: {e}") from e

    def close(self) -> None:
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    # ------------------------------------------------------------------
    # 基本I/O
    # ------------------------------------------------------------------
    def _require_connection(self) -> None:
        if self.ser is None or not self.ser.is_open:
            raise InstrumentError(
                "Keithley2400が接続されていません。connect()を先に呼んでください。"
            )

    def _write(self, msg: str) -> None:
        self._require_connection()
        try:
            self.ser.write((msg + "\n").encode("ascii"))
        except serial.SerialException as e:
            raise InstrumentError(f"Keithley2400への書き込みに失敗しました: {e}") from e

    def _read(self) -> str:
        self._require_connection()
        try:
            data = self.ser.readline().decode("ascii").strip()
        except serial.SerialException as e:
            raise InstrumentError(f"Keithley2400からの読み取りに失敗しました: {e}") from e
        if not data:
            raise InstrumentError("Keithley2400からの応答がありません(タイムアウト)。")
        return data

    def _query(self, msg: str) -> str:
        self._require_connection()
        self.ser.reset_input_buffer()
        self._write(msg)
        return self._read()

    # ------------------------------------------------------------------
    # AbstractSourceMeter 実装
    # ------------------------------------------------------------------
    def reset(self) -> None:
        # A-4-2のシーケンス(reset -> clear_status)をここに集約し、
        # 抽象基底クラスに独立したclear_status()を増やさずに済ませる。
        self._write("*RST")
        time.sleep(1.0)
        self._write("*CLS")

    def configure_source_voltage(
        self,
        channel: str,
        compliance_current: float,
        nplc: float,
        auto_range: bool = True,
    ) -> None:
        self._write("SOUR:FUNC VOLT")
        self._write("SOUR:VOLT:MODE FIX")
        self._write("SENS:FUNC 'CURR:DC'")
        self._write(f"SENS:CURR:PROT {compliance_current}")
        self._write(f"SENS:CURR:NPLC {nplc}")
        if auto_range:
            self._write("SENS:CURR:RANG:AUTO ON")
        else:
            self._write("SENS:CURR:RANG:AUTO OFF")
        self.set_output(channel, False)

    def set_output(self, channel: str, on: bool) -> None:
        self._write("OUTP ON" if on else "OUTP OFF")

    def set_voltage(self, channel: str, voltage: float) -> None:
        self._write(f"SOUR:VOLT {voltage}")

    def measure_current(self, channel: str) -> float:
        resp = self._query("MEAS:CURR?")
        try:
            return float(resp.split(",")[1])
        except (IndexError, ValueError) as e:
            raise InstrumentError(f"電流測定値のパースに失敗しました: {resp!r}") from e

    def measure_voltage(self, channel: str) -> float:
        resp = self._query("MEAS:VOLT?")
        try:
            return float(resp.split(",")[0])
        except (IndexError, ValueError) as e:
            raise InstrumentError(f"電圧測定値のパースに失敗しました: {resp!r}") from e
