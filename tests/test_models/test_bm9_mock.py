"""BM9Mock クラスの動作検証テスト。"""
from __future__ import annotations

import pytest
from models.instruments.base import InstrumentError
from models.instruments.mock.bm9_mock import BM9Mock


def test_bm9_mock_basic_flow():
    """接続、測定、クローズの動作を検証。"""
    mock = BM9Mock(connection="MOCK")

    assert not mock.connected
    mock.connect()
    assert mock.connected

    # 初期状態での輝度は0
    lum = mock.get_luminance()
    assert lum == 0.0

    mock.close()
    assert not mock.connected


def test_bm9_mock_luminance_from_current():
    """電流の更新に応じた擬似輝度の算出を検証。"""
    mock = BM9Mock(connection="MOCK", k=100.0)
    mock.connect()

    # 電流 0.001 A -> 輝度は 100 * 0.001 = 0.1
    mock.update_reference_current(0.001)
    assert mock.get_luminance() == pytest.approx(0.1)

    # マイナス電流 -> 輝度は 0
    mock.update_reference_current(-0.005)
    assert mock.get_luminance() == 0.0


def test_bm9_mock_custom_fn():
    """カスタム輝度生成関数の注入を検証。"""
    call_count = 0

    def dummy_luminance_fn():
        nonlocal call_count
        call_count += 1
        return 12.3

    mock = BM9Mock(connection="MOCK", luminance_fn=dummy_luminance_fn)
    mock.connect()

    assert mock.get_luminance() == 12.3
    assert mock.get_luminance() == 12.3
    assert call_count == 2


def test_bm9_mock_connect_failure():
    """故障注入時の接続失敗を検証。"""
    mock = BM9Mock(connection="MOCK", simulate_connect_failure=True)
    with pytest.raises(InstrumentError) as excinfo:
        mock.connect()
    assert "simulated connection failure" in str(excinfo.value)
