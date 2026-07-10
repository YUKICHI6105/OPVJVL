"""TOPCON BM9 輝度計のモッククラス。

要件定義書_基本設計書.md A-6節に基づく。既定では直近に
``update_reference_current`` で登録された電流値から簡易な輝度モデル
``L = k * max(I, 0)`` を計算する。``luminance_fn`` を注入すれば任意の
モデルに差し替え可能(GUI結合テストでの厳密な期待値検証用)。実機ドライバ
とは独立に、``AbstractLuminanceMeter`` のみに依存する。serial/pyvisaは
importしない。time.sleepも使用しない。
"""
from __future__ import annotations

from typing import Callable

from models.instruments.base import AbstractLuminanceMeter, InstrumentError


class BM9Mock(AbstractLuminanceMeter):
    """TOPCON BM9 と同一インタフェースを持つ擬似輝度計モック。"""

    def __init__(
        self,
        connection: str,
        luminance_fn: Callable[[], float] | None = None,
        simulate_connect_failure: bool = False,
        k: float = 1e6,
    ) -> None:
        self.connection = connection
        self.luminance_fn = luminance_fn
        self.simulate_connect_failure = simulate_connect_failure
        self.k = k

        self._reference_current = 0.0
        self.connected = False
        self.connect_calls = 0
        self.close_calls = 0

    def update_reference_current(self, current: float) -> None:
        """ソースメータモック等から直近の測定電流を受け取り、既定輝度モデルに反映する。"""
        self._reference_current = current

    # -- AbstractLuminanceMeter実装 --------------------------------------

    def connect(self) -> None:
        self.connect_calls += 1
        if self.simulate_connect_failure:
            raise InstrumentError("BM9Mock: simulated connection failure")
        self.connected = True

    def close(self) -> None:
        self.close_calls += 1
        self.connected = False

    def get_luminance(self) -> float:
        if self.luminance_fn is not None:
            return float(self.luminance_fn())
        return self.k * max(self._reference_current, 0.0)
