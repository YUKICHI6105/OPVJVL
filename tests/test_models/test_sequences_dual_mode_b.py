"""2素子同時測定(モードB)シーケンスのテスト。"""
from __future__ import annotations

import pytest
from models.instruments.mock.bm9_mock import BM9Mock
from models.instruments.mock.keithley2612b_mock import Keithley2612BMock
from models.measurement.config import ChannelConfig, DualBConfig
from models.measurement.result import ChannelPoint
from models.measurement.sequences import run_dual_b_sequence


def test_run_dual_b_sequence_both_enabled():
    """両チャンネルとも有効な場合のモードB掃引を検証。"""
    # chA: 3点, chB: 2点
    ch_a = ChannelConfig(
        enabled=True,
        device_mode="太陽電池",
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,  # 0.0, 0.1, 0.2 (3点)
        iteration=1,
    )
    ch_b = ChannelConfig(
        enabled=True,
        device_mode="太陽電池",
        v_min=0.5,
        v_max=0.6,
        v_step=0.1,  # 0.5, 0.6 (2点)
        iteration=1,
        hold_at_end="last_value",
    )
    config = DualBConfig(connection="MOCK", use_mock=True, channel_a=ch_a, channel_b=ch_b)

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()

    is_aborted = lambda: False
    points = list(run_dual_b_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    # ループ回数は max(3, 2) = 3 回
    # 各ループで有効な測定点が生成される。
    # ループ0: A (0.0V), B (0.5V) -> 2点
    # ループ1: A (0.1V), B (0.6V) -> 2点
    # ループ2: A (0.2V) (Bは点数が終了したためスキップ) -> 1点
    # 合計: 5点
    assert len(points) == 5

    ch_a_points = [p for p in points if p.channel == "A"]
    ch_b_points = [p for p in points if p.channel == "B"]

    assert len(ch_a_points) == 3
    assert len(ch_b_points) == 2

    assert ch_a_points[0].voltage == 0.0
    assert ch_a_points[2].voltage == 0.2
    assert ch_b_points[0].voltage == 0.5
    assert ch_b_points[1].voltage == 0.6

    for p in points:
        assert isinstance(p, ChannelPoint)


def test_run_dual_b_sequence_one_channel():
    """片方のチャンネルのみ有効な場合の動作。"""
    ch_a = ChannelConfig(
        enabled=True,
        device_mode="太陽電池",
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,
        iteration=1,
    )
    ch_b = ChannelConfig(enabled=False)  # 無効
    config = DualBConfig(connection="MOCK", use_mock=True, channel_a=ch_a, channel_b=ch_b)

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()

    is_aborted = lambda: False
    points = list(run_dual_b_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    assert len(points) == 3
    for p in points:
        assert p.channel == "A"


def test_run_dual_b_sequence_with_bm9():
    """モードBで一方のチャンネルで輝度計を使用する場合を検証。"""
    ch_a = ChannelConfig(
        enabled=True,
        device_mode="発光素子",
        v_min=0.0,
        v_max=0.1,
        v_step=0.1,
        iteration=1,
    )
    ch_b = ChannelConfig(enabled=True, device_mode="太陽電池", v_min=0.0, v_max=0.1, v_step=0.1, iteration=1)
    config = DualBConfig(connection="MOCK", use_mock=True, channel_a=ch_a, channel_b=ch_b)

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()
    bm9 = BM9Mock(connection="MOCK", k=10.0)
    bm9.connect()

    is_aborted = lambda: False
    points = list(
        run_dual_b_sequence(smu, config, is_aborted, sleep_fn=lambda x: None, luminance_meter=bm9)
    )

    ch_a_points = [p for p in points if p.channel == "A"]
    ch_b_points = [p for p in points if p.channel == "B"]

    assert len(ch_a_points) == 2
    assert len(ch_b_points) == 2

    # A (発光素子) には輝度データが含まれ、B (太陽電池) には含まれない (None)
    for p in ch_a_points:
        assert p.luminance is not None
    for p in ch_b_points:
        assert p.luminance is None
