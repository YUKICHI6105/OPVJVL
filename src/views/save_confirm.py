"""測定開始前の「上書き保存」確認ダイアログ(共有ヘルパー)。

各タブの開始クリックハンドラは、ViewModelのstart呼び出し前に本モジュールの
``confirm_overwrite`` を呼び、保存予定のCSVパスが既に存在する場合のみ
確認ダイアログを表示する。Qt依存のためView層に置く(csv_writerはQt非依存を維持)。
"""
from __future__ import annotations

import os
from typing import Sequence

from qtcompat import QtWidgets, enum_value


def confirm_overwrite(parent, paths: Sequence[str]) -> bool:
    """保存予定パスのうち既存のものがあれば上書き確認ダイアログを表示する。

    既存のパスが1つも無ければダイアログを出さずTrueを返す。
    ダイアログで「はい」が選ばれればTrue(上書きして続行)、
    「キャンセル」またはダイアログを閉じた場合はFalse(開始しない)を返す。
    """
    existing = [p for p in paths if p and os.path.exists(p)]
    if not existing:
        return True

    file_list = "\n".join(existing)
    message = f"同名のファイルが存在します。上書きしますか?\n\n{file_list}"
    yes_button = enum_value(QtWidgets.QMessageBox, "Yes")
    cancel_button = enum_value(QtWidgets.QMessageBox, "Cancel")
    result = QtWidgets.QMessageBox.question(
        parent,
        "上書き確認",
        message,
        yes_button | cancel_button,
        cancel_button,
    )
    return result == yes_button
