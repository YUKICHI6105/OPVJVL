"""測定開始前の「保存先確認」「上書き保存」確認ダイアログ(共有ヘルパー)。

各タブの開始クリックハンドラは、ViewModelのstart呼び出し前に本モジュールの
``ensure_save_dir``(review.md項目3)→``confirm_overwrite`` の順に呼び、
保存先が未指定なら指定を促し、保存予定のCSVパスが既に存在する場合のみ
上書き確認ダイアログを表示する。Qt依存のためView層に置く(csv_writerはQt非依存を維持)。
"""
from __future__ import annotations

import os
from typing import Sequence

from qtcompat import QtWidgets, enum_value


def ensure_save_dir(parent, save_dir_edit: QtWidgets.QLineEdit) -> bool:
    """保存先が空欄なら選択を促す(review.md項目3)。

    ``save_dir_edit`` のテキスト(前後空白除去後)が空の場合、
    ``QFileDialog.getExistingDirectory`` でディレクトリ選択ダイアログを開く。
    選択されればそのパスを ``save_dir_edit`` へ ``setText`` してTrueを返す。
    キャンセルされた場合は「保存先を指定してください」の情報ダイアログを出して
    Falseを返す(測定を開始しない)。

    空でなければダイアログを出さず即Trueを返す。

    Args:
        parent: ダイアログの親ウィジェット。
        save_dir_edit: 保存先ディレクトリを保持する``QLineEdit``。

    Returns:
        測定開始を続行してよければTrue、中止すべきならFalse。
    """
    if save_dir_edit.text().strip():
        return True

    directory = QtWidgets.QFileDialog.getExistingDirectory(parent, "保存先ディレクトリを選択")
    if directory:
        save_dir_edit.setText(directory)
        return True

    QtWidgets.QMessageBox.information(parent, "保存先未指定", "保存先を指定してください")
    return False


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
    # Warningタイプを使用し、Windows標準の警告音と警告アイコンを出す。
    result = QtWidgets.QMessageBox.warning(
        parent,
        "上書き確認",
        message,
        yes_button | cancel_button,
        cancel_button,
    )
    return result == yes_button
