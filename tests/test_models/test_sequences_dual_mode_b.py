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


class _EventRecordingMock(Keithley2612BMock):
    """reset/configure/output の呼び出し順序を検証するためのモック拡張。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list = []

    def reset(self) -> None:
        self.events.append(("reset",))
        super().reset()

    def configure_source_voltage(self, channel, compliance_current, nplc, auto_range=True):
        self.events.append(("configure", channel, compliance_current, nplc))
        super().configure_source_voltage(channel, compliance_current, nplc, auto_range)

    def set_output(self, channel, on) -> None:
        self.events.append(("output", channel, on))
        super().set_output(channel, on)


def test_run_dual_b_sequence_resets_and_configures_before_output_on():
    """出力ON前にreset→configure(コンプライアンス/NPLC反映)が行われることを検証。

    過去の不具合: run_dual_b_sequence が reset() も configure_source_voltage() も
    呼ばずに出力ONしており、ChannelConfig.compliance_current / nplc が
    一切反映されていなかった(素子破壊リスク)。
    """
    ch_a = ChannelConfig(
        enabled=True, v_min=0.0, v_max=0.1, v_step=0.1, iteration=1,
        compliance_current=0.005, nplc=2.0,
    )
    ch_b = ChannelConfig(
        enabled=True, v_min=0.0, v_max=0.1, v_step=0.1, iteration=1,
        compliance_current=0.010, nplc=0.5,
    )
    config = DualBConfig(connection="MOCK", use_mock=True, channel_a=ch_a, channel_b=ch_b)

    smu = _EventRecordingMock(connection="MOCK")
    smu.connect()
    list(run_dual_b_sequence(smu, config, lambda: False, sleep_fn=lambda x: None))

    # resetが1回呼ばれ、チャンネルごとのコンプライアンス/NPLCが設定されている
    assert smu.reset_calls == 1
    assert ("configure", "smua", 0.005, 2.0) in smu.events
    assert ("configure", "smub", 0.010, 0.5) in smu.events

    # 呼び出し順序: reset → configure(全チャンネル) → 出力ON
    idx_reset = smu.events.index(("reset",))
    idx_conf_a = smu.events.index(("configure", "smua", 0.005, 2.0))
    idx_conf_b = smu.events.index(("configure", "smub", 0.010, 0.5))
    idx_on_a = smu.events.index(("output", "smua", True))
    idx_on_b = smu.events.index(("output", "smub", True))
    assert idx_reset < idx_conf_a < idx_on_a
    assert idx_reset < idx_conf_b < idx_on_b

    # 終了時は両チャンネルとも出力OFF
    assert smu.events[-2:] == [("output", "smua", False), ("output", "smub", False)]


def test_run_dual_b_sequence_configures_only_enabled_channels():
    """無効チャンネルにはconfigure/出力ONを行わないことを検証。"""
    ch_a = ChannelConfig(
        enabled=True, v_min=0.0, v_max=0.1, v_step=0.1, iteration=1,
        compliance_current=0.003, nplc=1.0,
    )
    ch_b = ChannelConfig(enabled=False)
    config = DualBConfig(connection="MOCK", use_mock=True, channel_a=ch_a, channel_b=ch_b)

    smu = _EventRecordingMock(connection="MOCK")
    smu.connect()
    list(run_dual_b_sequence(smu, config, lambda: False, sleep_fn=lambda x: None))

    assert smu.reset_calls == 1
    configured_channels = [e[1] for e in smu.events if e[0] == "configure"]
    assert configured_channels == ["smua"]
    assert ("output", "smub", True) not in smu.events
