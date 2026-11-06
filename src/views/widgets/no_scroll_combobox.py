"""ホイール操作による選択の変更を防ぐコンボボックス。"""
from qtcompat import QtWidgets


class NoScrollComboBox(QtWidgets.QComboBox):
    """ホイール入力は親のスクロール領域へ伝播させる。"""

    def wheelEvent(self, event) -> None:
        event.ignore()
