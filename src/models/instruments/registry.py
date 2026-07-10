"""実機ドライバ/モッククラスを機種名から生成するファクトリ。

要件定義書_基本設計書.md B-2-3節に対応する。ViewModel層はこのファクトリ経由で
のみ機器インスタンスを生成し、実クラス/モッククラスの別を意識しない。
"""
from __future__ import annotations

from typing import Literal

from models.instruments.base import AbstractLuminanceMeter, AbstractSourceMeter
from models.instruments.bm9 import BM9
from models.instruments.keithley2400 import Keithley2400
from models.instruments.keithley2612b import Keithley2612B
from models.instruments.mock.bm9_mock import BM9Mock
from models.instruments.mock.keithley2400_mock import Keithley2400Mock
from models.instruments.mock.keithley2612b_mock import Keithley2612BMock

DeviceType = Literal["keithley2400", "keithley2612b"]

_SOURCE_METER_CLASSES: dict[DeviceType, type[AbstractSourceMeter]] = {
    "keithley2400": Keithley2400,
    "keithley2612b": Keithley2612B,
}

_SOURCE_METER_MOCK_CLASSES: dict[DeviceType, type] = {
    "keithley2400": Keithley2400Mock,
    "keithley2612b": Keithley2612BMock,
}


def create_source_meter(
    device_type: DeviceType,
    connection: str,
    use_mock: bool = False,
    preset: Literal["opv", "jvl"] = "opv",
    **kwargs,
) -> AbstractSourceMeter:
    """機種名からソースメータのインスタンスを生成する。

    ``use_mock=True``の場合、``preset``でダイオード特性のプリセット
    (光電流オフセットの有無)を切り替える。``kwargs``は各クラスの
    コンストラクタへそのまま渡される。
    """
    if use_mock:
        mock_cls = _SOURCE_METER_MOCK_CLASSES.get(device_type)
        if mock_cls is None:
            raise ValueError(f"未知の機種です: {device_type!r}")
        factory = mock_cls.for_jvl if preset == "jvl" else mock_cls.for_opv
        return factory(connection, **kwargs)

    real_cls = _SOURCE_METER_CLASSES.get(device_type)
    if real_cls is None:
        raise ValueError(f"未知の機種です: {device_type!r}")
    return real_cls(connection, **kwargs)


def create_luminance_meter(
    connection: str,
    use_mock: bool = False,
    **kwargs,
) -> AbstractLuminanceMeter:
    """TOPCON BM9(または互換モック)のインスタンスを生成する。"""
    if use_mock:
        return BM9Mock(connection, **kwargs)
    return BM9(connection, **kwargs)
