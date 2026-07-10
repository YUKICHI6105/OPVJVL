"""Keithley2400Mock クラスの動作検証テスト。"""
from __future__ import annotations

import pytest
from models.instruments.base import InstrumentError
from models.instruments.mock.keithley2400_mock import Keithley2400Mock


def test_keithley2400_mock_basic_flow():
    """接続、リセット、設定、出力、測定の一連の基本動作を確認。"""
    mock = Keithley2400Mock(connection="MOCK")

    # 初期状態
    assert not mock.connected
    assert mock.connect_calls == 0

    # 接続
    idn = mock.connect()
    assert mock.connected
    assert mock.connect_calls == 1
    assert "Keithley2400Mock" in idn

    # リセット
    mock.reset()
    assert mock.reset_calls == 1

    # 電圧設定と測定
    mock.set_output("default", True)
    mock.set_voltage("default", 0.5)

    v = mock.measure_voltage("default")
    assert abs(v - 0.5) < 1e-4  # 設定電圧がノイズを伴って返る

    # クローズ
    mock.close()
    assert not mock.connected
    assert mock.close_calls == 1


def test_keithley2400_mock_diode_equation():
    """ダイオード方程式に基づく擬似電流の応答を検証。"""
    # ノイズを排除して予測可能にする
    mock = Keithley2400Mock(connection="MOCK", I0=1e-10, n=1.5, I_L=0.0, noise_std=0.0)
    mock.connect()
    mock.set_output("default", True)

    # 0V印加時はほぼ0A (ノイズ0)
    mock.set_voltage("default", 0.0)
    assert mock.measure_current("default") == 0.0

    # 順バイアスで電流が流れる
    mock.set_voltage("default", 0.8)
    i_forward = mock.measure_current("default")
    assert i_forward > 0.0

    # 逆バイアスで電流はほぼ0（逆飽和電流に微小ノイズ）
    mock.set_voltage("default", -0.5)
    i_reverse = mock.measure_current("default")
    assert i_reverse < 0.0
    assert abs(i_reverse) < 1e-9


def test_keithley2400_mock_compliance():
    """コンプライアンス電流でのクリッピングを検証。"""
    mock = Keithley2400Mock(
        connection="MOCK", I0=1e-10, n=1.5, I_L=0.0, noise_std=0.0, compliance_current=0.01
    )
    mock.connect()
    mock.set_output("default", True)

    # 十分高い電圧を印加して電流がコンプライアンスを超えるようにする
    mock.set_voltage("default", 2.0)
    i = mock.measure_current("default")
    # コンプライアンス制限 (0.01 A) でクリップされること
    assert abs(i) == pytest.approx(0.01)


def test_keithley2400_mock_connect_failure():
    """故障注入オプションによる接続失敗を検証。"""
    mock = Keithley2400Mock(connection="MOCK", simulate_connect_failure=True)
    with pytest.raises(InstrumentError) as excinfo:
        mock.connect()
    assert "simulated connection failure" in str(excinfo.value)
    assert not mock.connected


def test_keithley2400_mock_fail_after_n_points():
    """故障注入オプションによる測定中の失敗を検証。"""
    mock = Keithley2400Mock(connection="MOCK", fail_after_n_points=2)
    mock.connect()
    mock.set_output("default", True)

    # 1点目: 成功
    mock.set_voltage("default", 0.1)
    mock.measure_current("default")

    # 2点目: 成功
    mock.set_voltage("default", 0.2)
    mock.measure_current("default")

    # 3点目: 失敗するはず
    mock.set_voltage("default", 0.3)
    with pytest.raises(InstrumentError) as excinfo:
        mock.measure_current("default")
    assert "simulated failure after" in str(excinfo.value)
