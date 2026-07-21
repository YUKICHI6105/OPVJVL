"""測定シーケンスのジェネレータ関数群。

要件定義書_基本設計書.md B-4節の擬似コードを本実装に落とし込んだもの。
Qt非依存であり、Worker(QThread)側がこれらのジェネレータをラップして
シグナル化する。``sleep_fn``を注入可能にすることでテスト時に実待機を
スキップできる。

各シーケンスは``try/finally``で必ず出力をOFFにし(B-7節エラーハンドリング
方針)、``is_aborted()``をループ内で毎回チェックして協調的中断を行う。
"""
from __future__ import annotations

import time
from typing import Callable, Iterator, Optional, Union

import numpy as np

from ..instruments.base import AbstractLuminanceMeter, AbstractSourceMeter
from .config import DualAConfig, DualBConfig, JVLConfig, OPVConfig
from .result import ChannelPoint, IVLPoint, IVPoint


def _interruptible_sleep(
    total_seconds: float,
    sleep_fn: Callable[[float], None],
    is_aborted: Callable[[], bool],
    chunk_seconds: float = 0.1,
) -> None:
    """``total_seconds``の待機を``chunk_seconds``単位に分割して行う。

    測定点間の遅延待機(delay_time)を一度の``sleep_fn``呼び出しで行うと、
    待機中は``is_aborted()``を確認できず中断要求への応答が最大delay_time秒
    遅れてしまう。本関数は待機を小刻みに分割し、チャンクの合間に毎回
    ``is_aborted()``を確認することで中断応答時間を``chunk_seconds``程度に
    抑える。中断を検知した場合は残り時間を待たずに即座に打ち切る
    (呼び出し側は本関数から戻った後に改めて``is_aborted()``を確認し、
    中断ならその回の測定・yieldを行わずbreakすること)。
    """
    remaining = total_seconds
    # 浮動小数点誤差でremainingがわずかに残り続けるのを防ぐための微小しきい値。
    while remaining > 1e-9 and not is_aborted():
        step = chunk_seconds if remaining > chunk_seconds else remaining
        sleep_fn(step)
        remaining -= step


def run_opv_sequence(
    smu: AbstractSourceMeter,
    config: OPVConfig,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Iterator[IVPoint]:
    """OPVモード(太陽電池JV/IV特性測定)シーケンス。B-4-1節。"""
    channel = config.channel if config.device_type == "keithley2612b" else "default"
    smu.reset()
    smu.configure_source_voltage(channel, config.compliance_current, config.nplc)
    voltage_list = config.build_voltage_list()
    smu.set_output(channel, True)
    try:
        for i, v in enumerate(voltage_list):
            if is_aborted():
                break
            smu.set_voltage(channel, float(v))
            _interruptible_sleep(config.delay_time, sleep_fn, is_aborted)
            if is_aborted():
                break
            current = smu.measure_current(channel)
            yield IVPoint(index=i, voltage=float(v), current=current)
    finally:
        smu.set_output(channel, False)


def run_jvl_sequence(
    smu: AbstractSourceMeter,
    config: JVLConfig,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
    luminance_meter: Optional[AbstractLuminanceMeter] = None,
) -> Iterator[Union[IVPoint, IVLPoint]]:
    """JVLモード(発光素子IV-輝度測定/暗IV測定共通)シーケンス。B-4-2節。

    ``config.use_luminance``がFalseの場合は暗IV測定として扱い、
    ``run_opv_sequence``と同じ``IVPoint``のみを生成する。
    """
    channel = config.channel if config.device_type == "keithley2612b" else "default"
    smu.reset()
    smu.configure_source_voltage(channel, config.compliance_current, config.nplc)
    voltage_list = config.build_voltage_list()
    smu.set_output(channel, True)
    try:
        for i, v in enumerate(voltage_list):
            if is_aborted():
                break
            smu.set_voltage(channel, float(v))
            _interruptible_sleep(config.delay_time, sleep_fn, is_aborted)
            if is_aborted():
                break
            current = smu.measure_current(channel)
            if luminance_meter is not None and hasattr(luminance_meter, "update_reference_current"):
                luminance_meter.update_reference_current(current)
            if config.use_luminance and luminance_meter is not None:
                # 既存コードKeithley2400_JVL.pyの単位換算(*100)を踏襲
                luminance = luminance_meter.get_luminance() * 100
                yield IVLPoint(
                    index=i, voltage=float(v), current=current, luminance=luminance
                )
            else:
                yield IVPoint(index=i, voltage=float(v), current=current)
    finally:
        smu.set_output(channel, False)


def run_dual_a_sequence(
    smu: AbstractSourceMeter,
    config: DualAConfig,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
    luminance_meter: Optional[AbstractLuminanceMeter] = None,
) -> Iterator[Union[IVPoint, IVLPoint]]:
    """モードA(2ch低ノイズ計測)シーケンス。B-4-3節。

    smuaで電圧を掃引・印加し、smubを0V固定の仮想接地電流計として使用する。
    ``OPV_measurement_ver2.py``踏襲で、2chの単純平均ではなくsmubの測定電流
    のみを採用する。
    """
    smu.reset()
    smu.configure_source_voltage("smua", config.compliance_current, config.nplc)
    smu.configure_source_voltage("smub", config.compliance_current, config.nplc)
    voltage_list = config.build_voltage_list()
    smu.set_output("smua", True)
    smu.set_output("smub", True)
    try:
        for i, v in enumerate(voltage_list):
            if is_aborted():
                break
            smu.set_voltage("smua", float(v))
            smu.set_voltage("smub", 0.0)
            _interruptible_sleep(config.delay_time, sleep_fn, is_aborted)
            if is_aborted():
                break
            # smubを仮想接地電流計として使用。符号反転は既存コード踏襲
            current = -1.0 * smu.measure_current("smub")
            if luminance_meter is not None and hasattr(luminance_meter, "update_reference_current"):
                luminance_meter.update_reference_current(current)
            if config.device_mode == "発光素子" and luminance_meter is not None:
                yield IVLPoint(
                    index=i,
                    voltage=float(v),
                    current=current,
                    luminance=luminance_meter.get_luminance() * 100,
                )
            else:
                yield IVPoint(index=i, voltage=float(v), current=current)
    finally:
        smu.set_output("smua", False)
        smu.set_output("smub", False)


def run_contact_check_hold_sequence(
    smu: AbstractSourceMeter,
    channel: str,
    compliance_current: float,
    nplc: float,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
    poll_interval: float = 0.2,
) -> Iterator[IVPoint]:
    """接触確認(OPV式)シーケンス。0Vを保持し続け、電流を継続的に測定する。

    本測定Configには依存しない軽量なシーケンス。``is_aborted()``がTrueになる
    (=ユーザーが接触確認ボタンをOFFにする)まで無期限にループするため、
    総点数は不定であり、進捗バーには使わない想定。
    """
    smu.reset()
    smu.configure_source_voltage(channel, compliance_current, nplc)
    smu.set_output(channel, True)
    try:
        while not is_aborted():
            smu.set_voltage(channel, 0.0)
            current = smu.measure_current(channel)
            yield IVPoint(index=0, voltage=0.0, current=current)
            sleep_fn(poll_interval)
    finally:
        smu.set_output(channel, False)


def run_contact_check_ramp_sequence(
    smu: AbstractSourceMeter,
    channel: str,
    compliance_current: float,
    nplc: float,
    threshold_current: float,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
    v_step: float = 0.05,
    v_max: float = 20.0,
    delay: float = 0.05,
    poll_interval: float = 0.2,
) -> Iterator[IVPoint]:
    """接触確認(JVL式)シーケンス。0Vから電圧を徐々に上げ、電流が閾値に達したら
    その電圧で出力を維持し続け、``is_aborted()``がTrueになる(=ユーザーが
    停止ボタンを押す)まで電流を測定し続ける。閾値に達する前に``v_max``
    (安全上限電圧)に達した場合は、素子保護のため出力を停止する。
    """
    smu.reset()
    smu.configure_source_voltage(channel, compliance_current, nplc)
    smu.set_output(channel, True)
    voltage = 0.0
    try:
        threshold_reached = False
        while not is_aborted() and voltage <= v_max:
            smu.set_voltage(channel, voltage)
            sleep_fn(delay)
            current = smu.measure_current(channel)
            yield IVPoint(index=0, voltage=voltage, current=current)
            if abs(current) >= threshold_current:
                threshold_reached = True
                break
            voltage += v_step

        # 目標電流に到達した場合のみ、その電圧で出力を維持したまま
        # ユーザーが停止するまで電流を読み続ける(v_max到達時は保護のため
        # 保持せず、finallyで即座に出力を停止する)。
        while threshold_reached and not is_aborted():
            current = smu.measure_current(channel)
            yield IVPoint(index=0, voltage=voltage, current=current)
            sleep_fn(poll_interval)
    finally:
        smu.set_output(channel, False)


def _hold_voltage(voltage_list: np.ndarray, hold_at_end: str) -> float:
    """掃引点数を使い切った後にチャンネルへ設定する保持電圧を返す。"""
    if hold_at_end == "last_value" and len(voltage_list) > 0:
        return float(voltage_list[-1])
    return 0.0


def run_dual_b_sequence(
    smu: AbstractSourceMeter,
    config: DualBConfig,
    is_aborted: Callable[[], bool],
    sleep_fn: Callable[[float], None] = time.sleep,
    luminance_meter: Optional[AbstractLuminanceMeter] = None,
) -> Iterator[ChannelPoint]:
    """モードB(2素子同時計測)のロックステップ制御シーケンス。B-4-4節。

    チャンネルA・チャンネルBを単一ループ内で交互制御する。掃引点数が
    異なる場合、短い方は掃引終了後``hold_at_end``に従って保持電圧を
    設定するが、測定・emitはその回スキップする(無駄なデータ点を
    記録しない)。
    """
    chan_a = config.channel_a
    chan_b = config.channel_b
    va_list = chan_a.build_voltage_list() if chan_a.enabled else np.array([])
    vb_list = chan_b.build_voltage_list() if chan_b.enabled else np.array([])
    n = max(len(va_list), len(vb_list))

    # 他シーケンス(OPV/JVL/モードA)と同様、出力ONの前に必ず機器を初期化し、
    # チャンネルごとのコンプライアンス電流・NPLCを設定する(素子保護のため必須)。
    smu.reset()
    if chan_a.enabled:
        smu.configure_source_voltage("smua", chan_a.compliance_current, chan_a.nplc)
    if chan_b.enabled:
        smu.configure_source_voltage("smub", chan_b.compliance_current, chan_b.nplc)

    if chan_a.enabled:
        smu.set_output("smua", True)
    if chan_b.enabled:
        smu.set_output("smub", True)

    try:
        for i in range(n):
            if is_aborted():
                break

            if chan_a.enabled:
                if i < len(va_list):
                    smu.set_voltage("smua", float(va_list[i]))
                else:
                    smu.set_voltage("smua", _hold_voltage(va_list, chan_a.hold_at_end))

            if chan_b.enabled:
                if i < len(vb_list):
                    smu.set_voltage("smub", float(vb_list[i]))
                else:
                    smu.set_voltage("smub", _hold_voltage(vb_list, chan_b.hold_at_end))

            _interruptible_sleep(
                max(chan_a.delay_time, chan_b.delay_time), sleep_fn, is_aborted
            )
            if is_aborted():
                break

            if chan_a.enabled and i < len(va_list):
                current_a = smu.measure_current("smua")
                if luminance_meter is not None and hasattr(luminance_meter, "update_reference_current"):
                    luminance_meter.update_reference_current(current_a)
                luminance_a = (
                    luminance_meter.get_luminance() * 100
                    if chan_a.device_mode == "発光素子" and luminance_meter is not None
                    else None
                )
                yield ChannelPoint(
                    channel="A",
                    index=i,
                    voltage=float(va_list[i]),
                    current=current_a,
                    luminance=luminance_a,
                )

            if chan_b.enabled and i < len(vb_list):
                current_b = smu.measure_current("smub")
                if luminance_meter is not None and hasattr(luminance_meter, "update_reference_current"):
                    luminance_meter.update_reference_current(current_b)
                luminance_b = (
                    luminance_meter.get_luminance() * 100
                    if chan_b.device_mode == "発光素子" and luminance_meter is not None
                    else None
                )
                yield ChannelPoint(
                    channel="B",
                    index=i,
                    voltage=float(vb_list[i]),
                    current=current_b,
                    luminance=luminance_b,
                )
    finally:
        smu.set_output("smua", False)
        smu.set_output("smub", False)
