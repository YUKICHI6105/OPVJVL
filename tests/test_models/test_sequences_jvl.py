"""JVL測定シーケンスのテスト。"""
from __future__ import annotations

import pytest
from models.instruments.mock.bm9_mock import BM9Mock
from models.instruments.mock.keithley2400_mock import Keithley2400Mock
from models.instruments.mock.keithley2612b_mock import Keithley2612BMock
from models.measurement.config import JVLConfig
from models.measurement.result import IVLPoint, IVPoint
from models.measurement.sequences import run_jvl_sequence


def test_run_jvl_sequence_with_luminance():
    """輝度測定ありのJVLシーケンス動作を検証。"""
    config = JVLConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,  # 0.0, 0.1, 0.2 (3点)
        iteration=1,
        use_luminance=True,
    )

    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()
    bm9 = BM9Mock(connection="MOCK", k=100.0)
    bm9.connect()

    is_aborted = lambda: False
    points = list(
        run_jvl_sequence(smu, config, is_aborted, sleep_fn=lambda x: None, luminance_meter=bm9)
    )

    assert len(points) == 3
    for p in points:
        assert isinstance(p, IVLPoint)
        # 輝度が None でないこと
        assert p.luminance is not None


def test_run_jvl_sequence_without_luminance():
    """輝度測定なしのJVLシーケンス（暗IV用途など）を検証。"""
    config = JVLConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,
        iteration=1,
        use_luminance=False,
    )

    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    is_aborted = lambda: False
    points = list(run_jvl_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    assert len(points) == 3
    for p in points:
        # 輝度なしなので IVPoint または luminance=None になる
        if isinstance(p, IVLPoint):
            assert p.luminance is None
        else:
            assert isinstance(p, IVPoint)


def test_run_jvl_sequence_keithley2612b_uses_configured_channel():
    """2612B選択時、config.channelで指定したチャンネル(smub)が実際に使われることを検証。

    修正前は "default" 固定で smu.set_voltage("default", ...) 等を呼んでおり、
    Keithley2612B/Keithley2612BMockの_validate_channelが "default" を拒否して
    ValueError: 不正なチャンネル指定です: 'default' (smua/smubのみ) を送出していた。
    """
    config = JVLConfig(
        device_type="keithley2612b",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,  # 0.0, 0.1, 0.2 (3点)
        iteration=1,
        use_luminance=False,
        channel="smub",
    )

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()

    def is_aborted():
        return False

    points = list(run_jvl_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    assert len(points) == 3
    assert all(call[0] == "smub" for call in smu.configure_calls)
    assert all(call[0] == "smub" for call in smu.output_calls)
    assert smu.output_calls[-1] == ("smub", False)
    assert all(call[0] != "smua" for call in smu.configure_calls)
    assert all(call[0] != "smua" for call in smu.output_calls)


def test_run_jvl_sequence_keithley2400_always_uses_default_channel():
    """Keithley2400選択時は、channelフィールドの値に関わらず"default"が使われること。"""
    config = JVLConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,
        iteration=1,
        use_luminance=False,
        channel="smub",
    )

    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    def is_aborted():
        return False

    points = list(run_jvl_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    assert len(points) == 3
    assert smu.output_calls[-1] == ("default", False)
