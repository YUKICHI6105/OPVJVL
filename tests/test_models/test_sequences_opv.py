"""OPV測定シーケンスのテスト。"""
from __future__ import annotations

import pytest
from opvjvl.models.instruments.mock.keithley2400_mock import Keithley2400Mock
from opvjvl.models.measurement.config import OPVConfig
from opvjvl.models.measurement.sequences import run_opv_sequence


def test_run_opv_sequence_success():
    """OPV測定シーケンスが正常に最後まで実行されることを検証。"""
    config = OPVConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=-0.1,
        v_max=0.1,
        v_step=0.1,  # -0.1, 0.0, 0.1 の3点
        iteration=2,  # 各点2回繰り返しなので、計6点
        compliance_current=0.02,
        nplc=1.0,
        delay_time=0.5,
    )

    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    is_aborted = lambda: False
    sleep_calls = []
    sleep_fn = lambda x: sleep_calls.append(x)

    points = list(run_opv_sequence(smu, config, is_aborted, sleep_fn=sleep_fn))

    # 点数の検証 (3 * 2 = 6点)
    assert len(points) == 6
    assert points[0].index == 0
    assert points[0].voltage == -0.1
    assert points[5].index == 5
    assert points[5].voltage == pytest.approx(0.1)

    # sleep関数の呼び出し回数
    assert len(sleep_calls) == 6
    assert sleep_calls[0] == 0.5

    # 測定完了後、出力がOFFになっていることを検証
    assert smu.connected
    assert smu.output_calls[-1] == ("default", False)


def test_run_opv_sequence_aborted():
    """OPV測定シーケンスが途中で中断された場合、安全に出力がOFFになることを検証。"""
    config = OPVConfig(
        device_type="keithley2400",
        connection="MOCK",
        use_mock=True,
        v_min=-0.1,
        v_max=0.5,
        v_step=0.1,  # -0.1, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5 (7点)
        iteration=1,
    )

    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    # 3点目 (index=2) の後に中断フラグを立てる
    call_count = 0

    def is_aborted():
        nonlocal call_count
        call_count += 1
        return call_count > 3

    points = list(run_opv_sequence(smu, config, is_aborted, sleep_fn=lambda x: None))

    # 3点のみ測定されていること
    assert len(points) == 3
    # 中断後、出力がOFFになっていること
    assert smu.output_calls[-1] == ("default", False)
