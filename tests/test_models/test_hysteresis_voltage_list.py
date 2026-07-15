"""ヒステリシス測定(往復掃引)の電圧列生成(``build_voltage_list``)のテスト。

``OPVConfig``/``ChannelConfig``双方について、``hysteresis=False``で従来通りの
片道掃引になること、``hysteresis=True``で往路+復路(折り返し点非重複)を
連結した電圧列になること、iteration回の繰り返しが往復連結後に正しく
適用されることを検証する。
"""
from __future__ import annotations

import numpy as np

from models.measurement.config import ChannelConfig, OPVConfig


def test_opv_config_hysteresis_false_is_unchanged():
    """hysteresis=False(既定値)では従来通りの片道掃引になること。"""
    config = OPVConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1)  # 0.0, 0.1, 0.2
    voltages = config.build_voltage_list()
    np.testing.assert_allclose(voltages, [0.0, 0.1, 0.2])


def test_opv_config_hysteresis_true_round_trip_no_duplicate_turnaround():
    """hysteresis=Trueでは往路+復路(折り返し点Vmaxを重複させない)になること。"""
    config = OPVConfig(
        v_min=0.0, v_max=0.2, v_step=0.1, iteration=1, hysteresis=True
    )  # 往路: 0.0, 0.1, 0.2
    voltages = config.build_voltage_list()
    # 往路(0.0, 0.1, 0.2) + 復路(0.1, 0.0)  ※Vmax=0.2の重複なし
    np.testing.assert_allclose(voltages, [0.0, 0.1, 0.2, 0.1, 0.0])


def test_opv_config_hysteresis_true_with_iteration():
    """hysteresis=True かつ iteration>1 では、往復連結後の電圧列全体に対して
    各点をiteration回繰り返すこと。"""
    config = OPVConfig(
        v_min=0.0, v_max=0.1, v_step=0.1, iteration=2, hysteresis=True
    )  # 往路: 0.0, 0.1
    voltages = config.build_voltage_list()
    # 往復連結: [0.0, 0.1, 0.0] をそれぞれ2回繰り返す
    np.testing.assert_allclose(voltages, [0.0, 0.0, 0.1, 0.1, 0.0, 0.0])


def test_channel_config_hysteresis_false_is_unchanged():
    """ChannelConfigでもhysteresis=False(既定値)では片道掃引になること。"""
    config = ChannelConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1)
    voltages = config.build_voltage_list()
    np.testing.assert_allclose(voltages, [0.0, 0.1, 0.2])


def test_channel_config_hysteresis_true_round_trip_no_duplicate_turnaround():
    """ChannelConfigでもhysteresis=Trueで往復掃引(折り返し点非重複)になること。"""
    config = ChannelConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1, hysteresis=True)
    voltages = config.build_voltage_list()
    np.testing.assert_allclose(voltages, [0.0, 0.1, 0.2, 0.1, 0.0])


def test_channel_config_hysteresis_true_with_iteration():
    """ChannelConfigでもhysteresis=True かつ iteration>1 で各点がiteration回繰り返されること。"""
    config = ChannelConfig(v_min=0.0, v_max=0.1, v_step=0.1, iteration=2, hysteresis=True)
    voltages = config.build_voltage_list()
    np.testing.assert_allclose(voltages, [0.0, 0.0, 0.1, 0.1, 0.0, 0.0])
