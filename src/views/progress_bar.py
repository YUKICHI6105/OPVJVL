"""測定プログレスバーの完了表示を切り替える共通処理。"""
from __future__ import annotations

from qtcompat import QtWidgets


def set_measurement_completed(
    progress_bar: QtWidgets.QProgressBar, completed: bool
) -> None:
    """正常完了ならバーを満了にして、テーマの完了色を適用する。"""
    progress_bar.setProperty("measurementCompleted", completed)
    if completed:
        progress_bar.setValue(progress_bar.maximum())

    # Qtは動的プロパティの変更だけではスタイルを再評価しないため再適用する。
    style = progress_bar.style()
    style.unpolish(progress_bar)
    style.polish(progress_bar)
    progress_bar.update()
