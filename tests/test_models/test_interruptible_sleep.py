"""``_interruptible_sleep``の中断即応性に関するテスト。

測定シーケンスの待機(delay_time)を0.1秒単位に分割し、チャンクの合間に
毎回is_aborted()を確認することで、待機中の中断要求に即座に応答できる
ことを検証する。
"""
from __future__ import annotations

import pytest
from models.measurement.sequences import _interruptible_sleep


def test_interruptible_sleep_runs_full_duration_when_not_aborted():
    """中断されない場合、合計待機時間がtotal_secondsと一致すること。"""
    sleep_calls = []
    _interruptible_sleep(0.5, sleep_calls.append, is_aborted=lambda: False)

    assert sum(sleep_calls) == pytest.approx(0.5)
    assert all(c <= 0.1 + 1e-9 for c in sleep_calls)


def test_interruptible_sleep_stops_early_when_aborted_mid_wait():
    """待機中にis_abortedがTrueになったら、残り時間を待たずに打ち切ること。"""
    sleep_calls = []
    call_count = 0

    def is_aborted():
        nonlocal call_count
        call_count += 1
        # 2回分のチャンク(0.2秒)を消費した後に中断要求が立つケースを模擬
        return call_count > 2

    _interruptible_sleep(10.0, sleep_calls.append, is_aborted)

    # 10秒(=100チャンク相当)を待ちきらず、中断検知までの2回で打ち切られること
    assert len(sleep_calls) == 2
    assert sum(sleep_calls) == pytest.approx(0.2)


def test_interruptible_sleep_aborted_before_first_chunk_sleeps_nothing():
    """開始時点で既に中断済みの場合、一度もsleep_fnを呼ばないこと。"""
    sleep_calls = []
    _interruptible_sleep(1.0, sleep_calls.append, is_aborted=lambda: True)

    assert sleep_calls == []


def test_interruptible_sleep_zero_duration_does_not_sleep():
    """delay_time=0.0の場合、is_abortedの追加チェックなしに即座に戻ること。"""
    sleep_calls = []
    checks = []

    def is_aborted():
        checks.append(True)
        return False

    _interruptible_sleep(0.0, sleep_calls.append, is_aborted)

    assert sleep_calls == []
