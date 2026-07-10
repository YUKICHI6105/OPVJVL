"""測定結果の値オブジェクト群。

要件定義書_基本設計書.md B-5-1節に対応する。1測定点を表す不変(frozen)な
dataclassを定義する。Qt非依存の純Pythonモジュールであり、pytestで直接
テストできる。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class IVPoint:
    """OPVモード(電流-電圧のみ)の1測定点。"""

    index: int
    voltage: float
    current: float


@dataclass(frozen=True)
class IVLPoint(IVPoint):
    """JVLモード等、輝度も同時測定する場合の1測定点。"""

    luminance: Optional[float] = None


@dataclass(frozen=True)
class ChannelPoint:
    """モードB(2素子同時計測)のロックステップ制御における1測定点。

    どちらのチャンネル(smua/smub)由来かを``channel``で区別する。
    """

    channel: Literal["A", "B"]
    index: int
    voltage: float
    current: float
    luminance: Optional[float] = None
