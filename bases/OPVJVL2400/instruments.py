"""
instruments.py
OPV / JVL 測定システムで使用する測定器の制御クラス群。

- Keithley2400 : シリアル通信(SCPI over RS-232)でKeithley 2400を制御する。
                  ベースコード(InstrumentsControl.py)のロジックをそのまま踏襲。
- BM9          : TOPCON BM9輝度計のシリアル通信制御。

いずれも接続・通信エラーを InstrumentError として明示し、
GUI側でエラーダイアログとして表示しやすいようにしている。
"""

from __future__ import annotations

import time
from typing import Optional

import serial


class InstrumentError(Exception):
    """測定器関連の例外の基底クラス。"""


# ---------------------------------------------------------------------------
# Keithley 2400 (シリアル / SCPI)
# ---------------------------------------------------------------------------

class Keithley2400:
    """
    シリアル通信(RS-232, SCPI)でKeithley 2400を制御するクラス。
    ベースコード(InstrumentsControl.py)のロジックをそのまま踏襲している。
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> str:
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
            raise InstrumentError(f"Keithley2400への接続に失敗しました ({self.port}): {e}") from e

        try:
            idn = self.query("*IDN?")
            return idn
        except Exception as e:
            raise InstrumentError(f"Keithley2400からの*IDN?応答取得に失敗しました: {e}") from e

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def _require_connection(self):
        if self.ser is None or not self.ser.is_open:
            raise InstrumentError("Keithley2400が接続されていません。connect()を先に呼んでください。")

    # ========= 基本I/O =========
    def write(self, msg: str) -> None:
        self._require_connection()
        try:
            self.ser.write((msg + "\n").encode("ascii"))
        except serial.SerialException as e:
            raise InstrumentError(f"Keithley2400への書き込みに失敗しました: {e}") from e

    def read(self) -> str:
        self._require_connection()
        try:
            data = self.ser.readline().decode("ascii").strip()
        except serial.SerialException as e:
            raise InstrumentError(f"Keithley2400からの読み取りに失敗しました: {e}") from e
        if not data:
            raise InstrumentError("Keithley2400からの応答がありません(タイムアウト)。")
        return data

    def query(self, msg: str) -> str:
        self._require_connection()
        self.ser.reset_input_buffer()
        self.write(msg)
        return self.read()

    # ========= 基本操作 =========
    def reset(self):
        self.write("*RST")
        time.sleep(1.0)

    def clear_status(self):
        self.write("*CLS")

    # ========= ソース設定 =========
    def configure_source_voltage(self, compliance_current: float = 0.02, nplc: float = 1.0,
                                  auto_range: bool = True, current_range: float = 1e-3):
        self.write("SOUR:FUNC VOLT")
        self.write("SENS:FUNC 'CURR'")
        self.write(f"SENS:CURR:PROT {compliance_current}")
        self.write(f"SENS:CURR:NPLC {nplc}")
        if auto_range:
            self.write("SENS:CURR:RANG:AUTO ON")
        else:
            self.write("SENS:CURR:RANG:AUTO OFF")
            self.write(f"SENS:CURR:RANG {current_range}")
        self.output_off()

    def configure_source_current(self, nplc: float = 1.0, auto_range: bool = True, voltage_range: float = 20):
        self.write("SOUR:FUNC CURR")
        self.write("SENS:FUNC 'VOLT'")
        self.write(f"SENS:VOLT:NPLC {nplc}")
        if auto_range:
            self.write("SENS:VOLT:RANG:AUTO ON")
        else:
            self.write("SENS:VOLT:RANG:AUTO OFF")
            self.write(f"SENS:VOLT:RANG {voltage_range}")
        self.output_off()

    # ========= 出力制御 =========
    def output_on(self):
        self.write("OUTP ON")

    def output_off(self):
        self.write("OUTP OFF")

    # ========= ソースレベル設定 =========
    def set_voltage(self, voltage: float):
        self.write(f"SOUR:VOLT {voltage}")

    def set_current(self, current: float):
        self.write(f"SOUR:CURR {current}")

    # ========= 測定 =========
    def measure_current(self) -> float:
        resp = self.query("MEAS:CURR?")
        try:
            second = resp.split(",")[1]
            return float(second)
        except Exception as e:
            raise InstrumentError(f"電流測定値のパースに失敗しました: {resp!r}") from e

    def measure_voltage(self) -> float:
        resp = self.query("MEAS:VOLT?")
        try:
            first = resp.split(",")[0]
            return float(first)
        except Exception as e:
            raise InstrumentError(f"電圧測定値のパースに失敗しました: {resp!r}") from e

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ---------------------------------------------------------------------------
# TOPCON BM9 輝度計
# ---------------------------------------------------------------------------

class BM9:
    """
    TOPCON BM9 輝度計のシリアル通信制御。
    """

    def __init__(self, port: str):
        self.port = port
        self.ser: Optional[serial.Serial] = None

    def connect(self):
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

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None

    def _require_connection(self):
        if self.ser is None or not self.ser.is_open:
            raise InstrumentError("BM9が接続されていません。connect()を先に呼んでください。")

    def _read(self) -> str:
        self._require_connection()
        data = self.ser.read_until(b"\r")
        if not data:
            raise InstrumentError("BM9からの応答がありません(タイムアウト)。")
        return data.decode("ascii").replace("\r", "")

    def _write(self, msg: str):
        self._require_connection()
        self.ser.write(f"{msg}\r".encode("ascii"))

    def get_luminance(self) -> float:
        self._write("DBR0ST")
        line = self._read().split()
        try:
            return float(line[0])
        except (IndexError, ValueError) as e:
            raise InstrumentError(f"輝度値のパースに失敗しました: {line!r}") from e

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ---------------------------------------------------------------------------
# シリアルポート一覧取得(GUIのポート選択ドロップダウン用ヘルパー)
# ---------------------------------------------------------------------------

def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []
