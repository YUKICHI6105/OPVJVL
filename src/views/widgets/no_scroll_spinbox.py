"""マウスホイールでの誤操作を防止し、増減ボタンを非表示にしたスピンボックス。

QAbstractSpinBoxは標準でカーソルが乗っている状態でのホイールスクロールに
反応して値を変更してしまうため、QScrollArea内に配置すると、ユーザーが
パネル全体をスクロールしようとした際に意図せず値が変化してしまう問題がある。
本モジュールのクラスはwheelEventを無効化し、ホイール入力を親ウィジェット
(QScrollArea)へ伝播させることでこれを防止する。

また、狭い幅で数値を並べる測定設定パネルでは右側の上下矢印ボタンが
邪魔になり、ユーザーは基本的に直接数値を入力するため、
``setButtonSymbols(NoButtons)``でボタン自体を非表示にする。
"""
from __future__ import annotations

from qtcompat import QtWidgets, enum_value

_NO_BUTTONS = enum_value(QtWidgets.QAbstractSpinBox, "NoButtons")


class NoScrollDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """ホイールスクロールで値が変化せず、増減ボタンも表示しないQDoubleSpinBox。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(_NO_BUTTONS)

    def wheelEvent(self, event) -> None:
        event.ignore()


class NoScrollSpinBox(QtWidgets.QSpinBox):
    """ホイールスクロールで値が変化せず、増減ボタンも表示しないQSpinBox。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(_NO_BUTTONS)

    def wheelEvent(self, event) -> None:
        event.ignore()
