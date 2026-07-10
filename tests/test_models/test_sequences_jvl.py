"""JVL測定シーケンスのテスト。"""
from __future__ import annotations

import pytest
from opvjvl.models.instruments.mock.bm9_mock import BM9Mock
from opvjvl.models.instruments.mock.keithley2400_mock import Keithley2400Mock
from opvjvl.models.measurement.config import JVLConfig
from opvjvl.models.measurement.result import IVLPoint, IVPoint
from opvjvl.models.measurement.sequences import run_jvl_sequence


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
