"""ViewModel-View間シグナル結線の回帰テスト。

過去の不具合: ViewModelの``__init__``とViewの``__init__``の双方が
``_bind_viewmodel()``を呼んでいたため、VM→Viewの全シグナルが二重結線され、
ログの2重表示・エラーダイアログの2回表示・プロットへの2重追加が発生していた。
本テストは「シグナル1回のemitに対しViewの反応がちょうど1回」であることを
検証し、二重結線の再発を防ぐ。
"""
from __future__ import annotations

from qtcompat import QtWidgets
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab
from views.opv_tab import OPVTab


def test_opv_log_signal_bound_once(qtbot):
    tab = OPVTab()
    qtbot.addWidget(tab)

    tab.viewModel.log_appended.emit("PING_OPV")
    assert tab.opv_logTextEdit.toPlainText().count("PING_OPV") == 1

    tab.viewModel.error_appended.emit("ERR_OPV")
    assert tab.opv_logTextEdit.toPlainText().count("ERR_OPV") == 1


def test_opv_error_dialog_shown_once(qtbot, monkeypatch):
    tab = OPVTab()
    qtbot.addWidget(tab)

    calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: calls.append(1)
    )
    tab.viewModel.error.emit("validation error")
    assert len(calls) == 1


def test_jvl_log_signal_bound_once(qtbot):
    tab = JVLTab()
    qtbot.addWidget(tab)

    tab.viewModel.log_appended.emit("PING_JVL")
    assert tab.jvl_logTextEdit.toPlainText().count("PING_JVL") == 1


def test_jvl_error_dialog_shown_once(qtbot, monkeypatch):
    tab = JVLTab()
    qtbot.addWidget(tab)

    calls = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: calls.append(1)
    )
    tab.viewModel.error.emit("validation error")
    assert len(calls) == 1


def test_dual_channel_log_signals_bound_once(qtbot):
    tab = DualChannelTab()
    qtbot.addWidget(tab)

    tab.viewModel.log_appended_a.emit("PING_DUAL_A")
    assert tab.dual_a_logTextEdit.toPlainText().count("PING_DUAL_A") == 1

    tab.viewModel.log_appended_b.emit("PING_DUAL_B")
    assert tab.dual_b_logTextEdit.toPlainText().count("PING_DUAL_B") == 1


def test_running_changed_toggles_buttons_once(qtbot):
    """running_changedの結線が機能していること(結線漏れの検出)。"""
    tab = OPVTab()
    qtbot.addWidget(tab)

    tab.viewModel.running_changed.emit(True)
    assert not tab.opv_startButton.isEnabled()
    assert tab.opv_stopButton.isEnabled()

    tab.viewModel.running_changed.emit(False)
    assert tab.opv_startButton.isEnabled()
    assert not tab.opv_stopButton.isEnabled()
