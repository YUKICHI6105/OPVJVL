"""Keithley2400._read()のCR/LF終端検出に関するテスト。

実機の応答終端はRS-232設定に依存しCRのみの場合があり、``ser.readline()``
(LF待ち)だとタイムアウト満了までブロックしてしまう不具合があった。
本テストは実シリアルを開かず、``ser``属性にフェイクを差し込んで
CR終端/LF終端/CRLF終端/応答なし(タイムアウト)の各パターンを検証する。
"""
from __future__ import annotations

import pytest
from models.instruments.base import InstrumentError
from models.instruments.keithley2400 import Keithley2400


class _FakeSerial:
    """``read(1)``がバイト列を1バイトずつ返すフェイクシリアル。

    末尾に達したら(タイムアウトを模して)空バイト列を返し続ける。
    """

    def __init__(self, response: bytes):
        self._buf = bytearray(response)
        self.is_open = True

    def read(self, size: int = 1) -> bytes:
        assert size == 1
        if not self._buf:
            return b""
        return bytes([self._buf.pop(0)])


def _make_smu(response: bytes) -> Keithley2400:
    smu = Keithley2400(port="COM99")
    smu.ser = _FakeSerial(response)
    return smu


def test_read_cr_terminated_response():
    """CRのみで終端される実機応答を即座に確定できること。"""
    smu = _make_smu(b"+1.23456E-03\r")
    assert smu._read() == "+1.23456E-03"


def test_read_lf_terminated_response():
    """従来通りLF終端の応答も読めること。"""
    smu = _make_smu(b"+1.23456E-03\n")
    assert smu._read() == "+1.23456E-03"


def test_read_crlf_terminated_response():
    """CRLF終端の応答で、CR/LFいずれもデータとして取り込まれないこと。"""
    smu = _make_smu(b"+1.23456E-03\r\n")
    assert smu._read() == "+1.23456E-03"


def test_read_skips_leading_terminator_from_previous_response():
    """先頭に残っていた前回応答の終端文字を読み飛ばして本文を返すこと。"""
    smu = _make_smu(b"\n+9.99000E-04\r")
    assert smu._read() == "+9.99000E-04"


def test_read_empty_response_raises_instrument_error():
    """応答が全く得られずタイムアウトした場合はInstrumentErrorを送出すること。"""
    smu = _make_smu(b"")
    with pytest.raises(InstrumentError):
        smu._read()


def test_read_terminator_only_raises_instrument_error():
    """終端文字のみでデータ本体がない場合もInstrumentErrorとなること。"""
    smu = _make_smu(b"\r")
    with pytest.raises(InstrumentError):
        smu._read()
