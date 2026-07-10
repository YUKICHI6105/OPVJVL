"""2ch低ノイズ測定(モードA)シーケンスのテスト。"""
from __future__ import annotations

import pytest
from opvjvl.models.instruments.mock.bm9_mock import BM9Mock
from opvjvl.models.instruments.mock.keithley2612b_mock import Keithley2612BMock
from opvjvl.models.measurement.config import DualAConfig
from opvjvl.models.measurement.result import IVLPoint, IVPoint
from opvjvl.models.measurement.sequences import run_dual_a_sequence


def test_run_dual_a_sequence_solar_cell():
    """モードA(太陽電池モード)の掃引を検証。"""
    config = DualAConfig(
        device_type="keithley2612b",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,  # 0.0, 0.1, 0.2 (3点)
        iteration=1,
        device_mode="太陽電池",
    )

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()

    is_aborted = lambda: False
    points = list(run_dual_a_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    assert len(points) == 3
    for p in points:
        assert isinstance(p, IVPoint)
        assert not isinstance(p, IVLPoint) or p.luminance is None

    # smua, smub 両方の出力がONになり、最終的に両方OFFになることを検証
    assert smu.output_calls[-2:] == [("smua", False), ("smub", False)]


def test_run_dual_a_sequence_led():
    """モードA(発光素子モード、輝度測定あり)の掃引を検証。"""
    config = DualAConfig(
        device_type="keithley2612b",
        connection="MOCK",
        use_mock=True,
        v_min=0.0,
        v_max=0.2,
        v_step=0.1,
        iteration=1,
        device_mode="発光素子",
    )

    smu = Keithley2612BMock(connection="MOCK")
    smu.connect()
    bm9 = BM9Mock(connection="MOCK", k=50.0)
    bm9.connect()

    is_aborted = lambda: False
    points = list(
        run_dual_a_sequence(
            smu, config, is_aborted, sleep_fn=lambda x: None, luminance_meter=bm9
        )
    )

    assert len(points) == 3
    for p in points:
        assert isinstance(p, IVLPoint)
        assert p.luminance is not None
