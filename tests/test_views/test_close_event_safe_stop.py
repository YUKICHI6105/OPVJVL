"""review.md項目3のテスト: MainWindow.closeEvent が実行中の測定を安全停止すること。"""
from __future__ import annotations

from views.main_window import MainWindow


def test_close_event_calls_stop_and_wait_on_all_viewmodels(qtbot, monkeypatch, tmp_path):
    """closeEvent実行時に、全ViewModelのstop_and_wait系APIが呼ばれること。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    calls = []
    monkeypatch.setattr(
        window.opv_tab.viewModel, "stop_and_wait", lambda: calls.append("opv")
    )
    monkeypatch.setattr(
        window.jvl_tab.viewModel, "stop_and_wait", lambda: calls.append("jvl")
    )
    monkeypatch.setattr(
        window.dual_channel_tab.viewModel,
        "stop_and_wait_a",
        lambda: calls.append("dual_a"),
    )
    monkeypatch.setattr(
        window.dual_channel_tab.viewModel,
        "stop_and_wait_b",
        lambda: calls.append("dual_b"),
    )

    window._stop_running_measurements()

    assert set(calls) == {"opv", "jvl", "dual_a", "dual_b"}
    window.close()


def test_stop_and_wait_is_noop_when_not_running(qtbot):
    """未実行のViewModelでstop_and_waitを呼んでも例外にならない(workerがNoneの場合)。"""
    from views.opv_tab import OPVTab

    tab = OPVTab()
    qtbot.addWidget(tab)
    # 例外が出ないことのみを検証する
    tab.viewModel.stop_and_wait(timeout_ms=10)
