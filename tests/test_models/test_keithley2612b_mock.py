"""Keithley2612BMock クラスの動作検証テスト。"""
from __future__ import annotations

import pytest
from models.instruments.base import InstrumentError
from models.instruments.mock.keithley2612b_mock import Keithley2612BMock


def test_keithley2612b_mock_basic_flow():
    """接続、リセット、設定、出力、測定の一連の動作を確認。"""
    mock = Keithley2612BMock(connection="MOCK")

    assert not mock.connected
    mock.connect()
    assert mock.connected

    mock.reset()
    assert mock.reset_calls == 1

    # チャンネルA、Bの独立した設定と測定
    mock.set_output("smua", True)
    mock.set_output("smub", True)
    mock.set_voltage("smua", 0.5)
    mock.set_voltage("smub", -0.2)

    v_a = mock.measure_voltage("smua")
    v_b = mock.measure_voltage("smub")

    assert abs(v_a - 0.5) < 1e-4
    assert abs(v_b - (-0.2)) < 1e-4

    mock.close()
    assert not mock.connected


def test_keithley2612b_mock_invalid_channel():
    """不正なチャンネル名が渡された際に ValueError を送出するか検証。"""
    mock = Keithley2612BMock(connection="MOCK")
    mock.connect()

    with pytest.raises(ValueError) as excinfo:
        mock.set_output("invalid_channel", True)
    assert "不正なチャンネル指定です" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        mock.set_voltage("default", 0.5)
    assert "不正なチャンネル指定です" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        mock.measure_current("smuc")
    assert "不正なチャンネル指定です" in str(excinfo.value)


def test_keithley2612b_mock_diode_equation():
    """ダイオード方程式に基づく擬似電流の応答をチャンネルごとに検証。"""
    mock = Keithley2612BMock(connection="MOCK", I0=1e-10, n=1.5, I_L=0.0, noise_std=0.0)
    mock.connect()
    mock.set_output("smua", True)
    mock.set_output("smub", True)

    # チャンネルAに順バイアス、Bに逆バイアス
    mock.set_voltage("smua", 0.8)
    mock.set_voltage("smub", -0.5)

    i_a = mock.measure_current("smua")
    i_b = mock.measure_current("smub")

    assert i_a > 0.0
    assert i_b < 0.0
    assert abs(i_b) < 1e-9


def test_keithley2612b_mock_compliance():
    """コンプライアンス制限でのクリッピングを検証。"""
    mock = Keithley2612BMock(
        connection="MOCK", I0=1e-10, n=1.5, I_L=0.0, noise_std=0.0, compliance_current=0.005
    )
    mock.connect()
    mock.set_output("smua", True)

    mock.set_voltage("smua", 2.0)
    i = mock.measure_current("smua")
    assert abs(i) == pytest.approx(0.005)


def test_keithley2612b_mock_connect_failure():
    """故障注入時の接続失敗を検証。"""
    mock = Keithley2612BMock(connection="MOCK", simulate_connect_failure=True)
    with pytest.raises(InstrumentError):
        mock.connect()
