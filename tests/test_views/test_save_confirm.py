"""上書き確認・保存先確認ダイアログ(views/save_confirm.py)の単体テスト。"""
from __future__ import annotations

import os

from qtcompat import QtWidgets, enum_value
from views.save_confirm import confirm_overwrite, ensure_save_dir


def test_no_existing_paths_skips_dialog(tmp_path, monkeypatch):
    """存在するパスが1つも無ければダイアログを出さずTrueを返す。"""
    calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *a, **kw: calls.append(1)
    )

    missing_path = str(tmp_path / "not_exists.csv")
    assert confirm_overwrite(None, [missing_path]) is True
    assert calls == []


def test_existing_path_shows_dialog_and_respects_yes(tmp_path, monkeypatch):
    """既存パスがあればダイアログを表示し、「はい」でTrueを返す。"""
    existing = tmp_path / "already_there.csv"
    existing.write_text("dummy", encoding="utf-8")

    yes_value = enum_value(QtWidgets.QMessageBox, "Yes")
    calls = []

    def fake_warning(*args, **kwargs):
        calls.append(args)
        return yes_value

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)

    assert confirm_overwrite(None, [str(existing)]) is True
    assert len(calls) == 1


def test_existing_path_cancel_returns_false(tmp_path, monkeypatch):
    """既存パスがあり「キャンセル」を選ぶとFalseを返す。"""
    existing = tmp_path / "already_there.csv"
    existing.write_text("dummy", encoding="utf-8")

    cancel_value = enum_value(QtWidgets.QMessageBox, "Cancel")
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *a, **kw: cancel_value
    )

    assert confirm_overwrite(None, [str(existing)]) is False


def test_mixed_existing_and_missing_paths(tmp_path, monkeypatch):
    """一部のみ存在する場合、存在するパスのみダイアログに含まれる想定で動作する。"""
    existing = tmp_path / "exists.csv"
    existing.write_text("dummy", encoding="utf-8")
    missing = str(tmp_path / "missing.csv")

    yes_value = enum_value(QtWidgets.QMessageBox, "Yes")
    captured = {}

    def fake_warning(parent, title, message, *args, **kwargs):
        captured["message"] = message
        return yes_value

    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)

    assert confirm_overwrite(None, [str(existing), missing]) is True
    assert os.path.basename(str(existing)) in captured["message"]
    assert os.path.basename(missing) not in captured["message"]


# ----------------------------------------------------------------------
# review.md項目3: ensure_save_dir
# ----------------------------------------------------------------------
def test_ensure_save_dir_returns_true_when_already_filled(qtbot):
    """入力済みならダイアログを出さず即Trueを返す。"""
    edit = QtWidgets.QLineEdit("C:/existing_dir")
    qtbot.addWidget(edit)
    assert ensure_save_dir(None, edit) is True
    assert edit.text() == "C:/existing_dir"


def test_ensure_save_dir_empty_and_selected(tmp_path, qtbot, monkeypatch):
    """空欄でディレクトリを選択した場合、setTextしてTrueを返す。"""
    edit = QtWidgets.QLineEdit("")
    qtbot.addWidget(edit)
    selected_dir = str(tmp_path)

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **kw: selected_dir
    )

    assert ensure_save_dir(None, edit) is True
    assert edit.text() == selected_dir


def test_ensure_save_dir_empty_and_cancelled(qtbot, monkeypatch):
    """空欄でキャンセルした場合、情報ダイアログを出しFalseを返す。"""
    edit = QtWidgets.QLineEdit("")
    qtbot.addWidget(edit)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **kw: "")

    info_calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "information", lambda *a, **kw: info_calls.append(a)
    )

    assert ensure_save_dir(None, edit) is False
    assert edit.text() == ""
    assert len(info_calls) == 1


def test_ensure_save_dir_whitespace_only_treated_as_empty(qtbot, monkeypatch):
    """空白のみのテキストは空欄扱いとしてダイアログを開く。"""
    edit = QtWidgets.QLineEdit("   ")
    qtbot.addWidget(edit)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory", lambda *a, **kw: "")
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *a, **kw: None)

    assert ensure_save_dir(None, edit) is False
