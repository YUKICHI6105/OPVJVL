"""接触確認シーケンス(hold/ramp)のテスト。"""
from __future__ import annotations

from models.instruments.mock.keithley2400_mock import Keithley2400Mock
from models.measurement.sequences import (
    run_contact_check_hold_sequence,
    run_contact_check_ramp_sequence,
)


def test_run_contact_check_hold_sequence_loops_until_aborted():
    """holdシーケンスは is_aborted() がTrueになるまでループし続けることを検証。"""
    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    counter = {"n": 0}

    def is_aborted():
        return counter["n"] >= 5

    def sleep_fn(_seconds):
        counter["n"] += 1

    points = list(
        run_contact_check_hold_sequence(
            smu, "default", 0.02, 1.0, is_aborted, sleep_fn=sleep_fn, poll_interval=0.1
        )
    )

    # sleep_fnが5回呼ばれるまでの間、毎回yieldされる(5点)
    assert len(points) == 5
    assert all(p.voltage == 0.0 for p in points)

    # 出力ON→測定→OFFの順で呼ばれ、最終的にOFFになっていること
    assert smu.output_calls[0] == ("default", True)
    assert smu.output_calls[-1] == ("default", False)


def test_run_contact_check_hold_sequence_stops_immediately_when_already_aborted():
    """開始時点で既にis_aborted()がTrueなら1点もyieldせず出力をOFFにすること。"""
    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    points = list(
        run_contact_check_hold_sequence(
            smu, "default", 0.02, 1.0, lambda: True, sleep_fn=lambda x: None
        )
    )

    assert points == []
    assert smu.output_calls[-1] == ("default", False)


def test_run_contact_check_ramp_sequence_holds_after_threshold_until_aborted():
    """rampシーケンスは電流が閾値に達した後、その電圧を維持し続け、
    is_aborted()がTrueになるまで(=停止ボタンが押されるまで)電流を
    測定し続けることを検証する。"""
    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    # 電圧に応じて単調増加する電流を返すようmeasure_currentを差し替える
    def measure_current(channel):
        return smu._voltage * 1e-3  # 電圧[V] * 1mA/V

    smu.measure_current = measure_current

    counter = {"n": 0}

    def is_aborted():
        # 閾値到達(V=5、6点目)より後、保持フェーズに入ってから3回読み取った
        # 時点で停止する。
        counter["n"] += 1
        return counter["n"] > 9

    points = list(
        run_contact_check_ramp_sequence(
            smu,
            "default",
            0.02,
            1.0,
            threshold_current=5e-3,  # 5mA
            is_aborted=is_aborted,
            sleep_fn=lambda x: None,
            v_step=1.0,
            v_max=20.0,
            delay=0.0,
            poll_interval=0.0,
        )
    )

    # V=0,1,2,3,4,5 の6点で5mA(閾値)に到達し、以降は保持フェーズとして
    # V=5のまま追加で読み取りを続ける(is_abortedがTrueになるまで)。
    assert len(points) == 9
    assert all(p.voltage == 5.0 for p in points[5:])
    assert points[-1].current >= 5e-3
    # 保持フェーズ終了(=停止ボタン押下相当)で出力がOFFになること
    assert smu.output_calls[-1] == ("default", False)


def test_run_contact_check_ramp_sequence_stops_at_v_max():
    """電流が閾値に達しない場合、v_maxに達した時点で停止することを検証。"""
    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()

    # 常に電流0を返す(閾値に到達しない)
    smu.measure_current = lambda channel: 0.0

    points = list(
        run_contact_check_ramp_sequence(
            smu,
            "default",
            0.02,
            1.0,
            threshold_current=1e-3,
            is_aborted=lambda: False,
            sleep_fn=lambda x: None,
            v_step=5.0,
            v_max=10.0,
            delay=0.0,
        )
    )

    # V=0,5,10 の3点でv_maxに達し、次のループでvoltage(15) > v_max(10)となり終了
    assert len(points) == 3
    assert points[-1].voltage == 10.0
    assert smu.output_calls[-1] == ("default", False)


def test_run_contact_check_ramp_sequence_manual_abort():
    """手動でis_aborted()がTrueになった場合、途中で停止すること。"""
    smu = Keithley2400Mock(connection="MOCK")
    smu.connect()
    smu.measure_current = lambda channel: 0.0

    counter = {"n": 0}

    def is_aborted():
        counter["n"] += 1
        return counter["n"] > 2

    points = list(
        run_contact_check_ramp_sequence(
            smu,
            "default",
            0.02,
            1.0,
            threshold_current=1.0,  # 到達しない大きな値
            is_aborted=is_aborted,
            sleep_fn=lambda x: None,
            v_step=1.0,
            v_max=100.0,
            delay=0.0,
        )
    )

    assert len(points) == 2
    assert smu.output_calls[-1] == ("default", False)
