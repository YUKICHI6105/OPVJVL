"""TOPCON BM9 輝度計 実機ドライバ。

RS-232シリアル(2400bps, ODD parity, 7bit, stop1)で通信する。コマンドは
``"DBR0ST"``のみ。移植元は``keithley2400/InstrumentsControl.py``の``BM9``。

読み取りタイムアウトは5秒の有限値とする(移植元の``timeout=None``とは
異なる意図的な変更)。BM9の通信不良が度々発生するため、応答が5秒間ない
場合は``InstrumentError``を送出し、測定をハングさせない(通信不良の検知を
優先する)。
"""
from __future__ import annotations

from typing import Optional

import serial

from models.instruments.base import AbstractLuminanceMeter, InstrumentError


class BM9(AbstractLuminanceMeter):
    """RS-232でTOPCON BM9輝度計を制御するクラス。"""

    def __init__(self, port: str):
        self.port = port
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> None:
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=2400,
                timeout=5,
                parity=serial.PARITY_ODD,
                bytesize=serial.SEVENBITS,
                stopbits=serial.STOPBITS_ONE,
            )
        except serial.SerialException as e:
            raise InstrumentError(f"BM9への接続に失敗しました ({self.port}): {e}") from e

    def close(self) -> None:
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def _require_connection(self) -> None:
        if self.ser is None or not self.ser.is_open:
            raise InstrumentError("BM9が接続されていません。connect()を先に呼んでください。")

    def _write(self, msg: str) -> None:
        self._require_connection()
        try:
            self.ser.write(f"{msg}\r".encode("ascii"))
        except serial.SerialException as e:
            raise InstrumentError(f"BM9への書き込みに失敗しました: {e}") from e

    def _read(self) -> str:
        self._require_connection()
        try:
            data = self.ser.read_until(b"\r")
        except serial.SerialException as e:
            raise InstrumentError(f"BM9からの読み取りに失敗しました: {e}") from e
        if not data:
            raise InstrumentError("BM9からの応答がありません(タイムアウト)。")
        return data.decode("ascii").replace("\r", "")

    def get_luminance(self) -> float:
        self._write("DBR0ST")
        line = self._read().split()
        try:
            return float(line[0])
        except (IndexError, ValueError) as e:
            raise InstrumentError(f"輝度値のパースに失敗しました: {line!r}") from e
