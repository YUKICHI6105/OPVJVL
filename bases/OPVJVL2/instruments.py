"""
instruments.py
JVL測定システムで使用する測定器の制御クラス群。

- Keithley2612B : PyVISA + TSP(Lua)コマンドでKeithley 2612Bを制御する。
                   keithley2600パッケージへの依存をなくし、PyVISAのみで完結させる。
- BM9           : TOPCON BM9輝度計のシリアル通信制御(InstrumentsControl.pyから移植・整理)。

いずれも「使えない状態(未接続・エラー)」をなるべく例外として明示し、
GUI側でエラーダイアログとして表示しやすいようにしている。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import pyvisa
import serial


# ---------------------------------------------------------------------------
# Keithley 2612B (PyVISA + TSP)
# ---------------------------------------------------------------------------

class InstrumentError(Exception):
    """測定器関連の例外の基底クラス。"""


class Keithley2612B:
    """
    PyVISA + TSPコマンドでKeithley 2612Bを制御するクラス。

    TSP(Test Script Processor)は Keithley 26xx シリーズ独自の Lua ベースの
    コマンド体系で、元の keithley2600 パッケージも内部的にはこの方式で
    通信している。SCPI互換モードより機器本来の機能(smua/smub, 積分時間
    設定など)に直接アクセスしやすいため、こちらを採用する。

    使用例:
        k = Keithley2612B("USB0::0x05E6::0x2612::4043586::INSTR")
        k.connect()
        k.set_integration_time("smua", 0.5)
        k.set_output("smua", True)
        k.set_voltage("smua", 1.0)
        i = k.measure_current("smua")
        k.set_output("smua", False)
        k.close()
    """

    def __init__(self, resource_name: str, visa_library: str = "@ivi"):
        """
        Parameters
        ----------
        resource_name : VISAリソース文字列 (例 "USB0::0x05E6::0x2612::4043586::INSTR")
        visa_library   : pyvisaのバックエンド指定。Windowsで従来のvisa64.dllを
                          使う場合は "C:\\WINDOWS\\system32\\visa64.dll" を指定する。
                          省略時はpyvisa-py等の自動検出("@ivi")。
        """
        self.resource_name = resource_name
        self.visa_library = visa_library
        self._rm: Optional[pyvisa.ResourceManager] = None
        self._inst: Optional[pyvisa.resources.MessageBasedResource] = None

    # -- 接続管理 -----------------------------------------------------------

    def connect(self, timeout_ms: int = 30000):
        try:
            self._rm = pyvisa.ResourceManager(self.visa_library)
            self._inst = self._rm.open_resource(self.resource_name)
            self._inst.timeout = timeout_ms
            self._inst.write_termination = "\n"
            self._inst.read_termination = "\n"
            # 機器がTSPモードで待ち受けているか簡易確認
            self._inst.write("*IDN?")
            idn = self._inst.read()
            return idn.strip()
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithleyへの接続に失敗しました: {e}") from e

    def close(self):
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception:
                pass
            self._rm = None

    def _require_connection(self):
        if self._inst is None:
            raise InstrumentError("Keithleyが接続されていません。connect()を先に呼んでください。")

    # -- 低レベルTSP通信 -----------------------------------------------------

    def _write(self, tsp_command: str):
        self._require_connection()
        try:
            self._inst.write(tsp_command)
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithleyへの書き込みに失敗しました: {e}") from e

    def _query(self, tsp_expression: str) -> str:
        """TSPの print() 経由で値を取得する。"""
        self._require_connection()
        try:
            self._inst.write(f"print({tsp_expression})")
            return self._inst.read().strip()
        except pyvisa.errors.VisaIOError as e:
            raise InstrumentError(f"Keithleyからの読み取りに失敗しました: {e}") from e

    # -- 高レベルAPI ----------------------------------------------------------

    def set_integration_time(self, channel: str, nplc: float):
        """
        積分時間の設定。

        Parameters
        ----------
        channel : "smua" or "smub"
        nplc    : NPLC値。元コードのintegration_timeは秒指定のように見えるが、
                  keithley2600のset_integration_timeは実際にはNPLC(電源周波数の
                  周期数, 通常0.001〜25)を渡す仕様。元コードの0.5はNPLC=0.5相当
                  として扱う。
        """
        self._validate_channel(channel)
        self._write(f"{channel}.measure.nplc = {nplc}")

    def set_output(self, channel: str, on: bool):
        self._validate_channel(channel)
        state = f"{channel}.OUTPUT_ON" if on else f"{channel}.OUTPUT_OFF"
        self._write(f"{channel}.source.output = {state}")

    def set_source_function_voltage(self, channel: str):
        self._validate_channel(channel)
        self._write(f"{channel}.source.func = {channel}.OUTPUT_DCVOLTS")

    def set_voltage(self, channel: str, voltage: float):
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

    def reset(self):
        self._write("reset()")

    @staticmethod
    def _validate_channel(channel: str):
        if channel not in ("smua", "smub"):
            raise InstrumentError(f"不正なチャンネル指定です: {channel!r} (smua/smubのみ)")

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
    InstrumentsControl.py のロジックをそのまま踏襲しつつ、接続/切断エラーを
    InstrumentErrorとして扱うようにした。
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
# VISAリソース一覧取得(GUIの接続先ドロップダウン用ヘルパー)
# ---------------------------------------------------------------------------

def list_visa_resources(visa_library: str = "@ivi") -> list[str]:
    try:
        rm = pyvisa.ResourceManager(visa_library)
        resources = list(rm.list_resources())
        rm.close()
        return resources
    except Exception:
        return []


def list_serial_ports() -> list[str]:
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []
