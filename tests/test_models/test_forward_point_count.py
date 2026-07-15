"""``forward_point_count()``(review.md項目2)の単体テスト。

``OPVConfig``/``ChannelConfig``双方について、``hysteresis``の有無・``iteration``の
組み合わせで、``build_voltage_list()``のうち往路に属する点数を正しく返すことを検証する。
"""
from __future__ import annotations

from models.measurement.config import ChannelConfig, OPVConfig


def test_opv_config_forward_point_count_without_hysteresis():
    """hysteresis=False時は全体が往路なので、全点数と一致すること。"""
    config = OPVConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1)  # 往路: 0.0, 0.1, 0.2
    assert config.forward_point_count() == len(config.build_voltage_list()) == 3


def test_opv_config_forward_point_count_with_hysteresis():
    """hysteresis=True時は往路のみの点数(復路を含まない)を返すこと。"""
    config = OPVConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1, hysteresis=True)
    # 往路: 0.0, 0.1, 0.2 (3点) 復路: 0.1, 0.0 (2点、折り返し点非重複)
    assert config.forward_point_count() == 3
    assert len(config.build_voltage_list()) == 5


def test_opv_config_forward_point_count_with_hysteresis_and_iteration():
    """iteration>1では往路点数もiteration倍されること。"""
    config = OPVConfig(v_min=0.0, v_max=0.1, v_step=0.1, iteration=2, hysteresis=True)
    # 往路(0.0, 0.1)を2回ずつ = 4点。復路(0.0)を2回 = 2点。全体6点。
    assert config.forward_point_count() == 4
    assert len(config.build_voltage_list()) == 6


def test_channel_config_forward_point_count_without_hysteresis():
    config = ChannelConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1)
    assert config.forward_point_count() == len(config.build_voltage_list()) == 3


def test_channel_config_forward_point_count_with_hysteresis():
    config = ChannelConfig(v_min=0.0, v_max=0.2, v_step=0.1, iteration=1, hysteresis=True)
    assert config.forward_point_count() == 3
    assert len(config.build_voltage_list()) == 5


def test_channel_config_forward_point_count_with_hysteresis_and_iteration():
    config = ChannelConfig(v_min=0.0, v_max=0.1, v_step=0.1, iteration=2, hysteresis=True)
    assert config.forward_point_count() == 4
    assert len(config.build_voltage_list()) == 6
