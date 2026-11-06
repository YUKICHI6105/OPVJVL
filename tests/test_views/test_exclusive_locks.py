"""機器共有ベースの測定排他制御(MainWindow._update_start_button_locks)のテスト。

OPV⇔JVL、2chモードA⇔Bは常に相互排他。OPV/JVLの機器選択が2612Bの場合のみ
OPV/JVL群⇔2ch群も相互排他になり、2400選択時(既定値)は並行実行を許可する。
"""
from __future__ import annotations

from views.main_window import MainWindow


def _buttons(window):
    return (
        window.opv_tab.opv_startButton,
        window.jvl_tab.jvl_startButton,
        window.dual_channel_tab.dual_a_startButton,
        window.dual_channel_tab.dual_b_startButton,
    )


def test_jvl_contact_check_locks_opv_start_and_contact_buttons(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    vm = window.jvl_tab.viewModel
    try:
        vm.start_contact_check("keithley2400", "mock", "smua", True, 0.02, 1, 0.001, 5)
        assert not window.opv_tab.opv_startButton.isEnabled()
        assert not window.opv_tab.opv_contactCheckButton.isEnabled()
        assert window.jvl_tab.jvl_contactCheckButton.isEnabled()
        # 他タブの状態通知でも共有機器のロックを解除しない。
        window.opv_tab.viewModel.contact_check_running_changed.emit(False)
        assert not window.opv_tab.opv_startButton.isEnabled()
        assert not window.opv_tab.opv_contactCheckButton.isEnabled()
    finally:
        worker = vm._contact_worker
        vm.stop_contact_check()
        if worker is not None:
            worker.wait(3000)
        qtbot.waitUntil(lambda: not window._running_flags["jvl"], timeout=5000)
        window.close()


def test_channel_start_buttons_share_mode_b_lock(qtbot, monkeypatch, tmp_path):
    from models.measurement.config import ChannelConfig, DualBConfig
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    tab = window.dual_channel_tab
    buttons = (tab.dual_chA_startButton, tab.dual_chB_startButton, tab.dual_b_startButton)
    assert all(button.isEnabled() for button in buttons)
    tab.viewModel.running_changed_b.emit(True)
    assert all(not button.isEnabled() for button in buttons)
    tab.viewModel.running_changed_b.emit(False)
    assert all(button.isEnabled() for button in buttons)
    tab._active_mode_b_config = DualBConfig(
        channel_a=ChannelConfig(enabled=True),
        channel_b=ChannelConfig(enabled=False),
    )
    tab._mode_b_reserved_channels = {"A": True, "B": False}
    tab.viewModel.running_changed_b.emit(True)
    assert tab.dual_chA_startButton.isEnabled()
    assert tab.dual_chA_startButton.text() == "このチャネルを中断"
    assert tab.dual_chB_startButton.isEnabled()
    assert not tab.dual_b_startButton.isEnabled()
    tab._mode_b_reserved_channels["B"] = True
    window._update_start_button_locks()
    assert tab.dual_chB_startButton.isEnabled()
    tab._mode_b_stopped_channels["A"] = True
    tab._update_mode_b_channel_buttons(True)
    window._update_start_button_locks()
    assert not tab.dual_chA_startButton.isEnabled()
    assert tab.dual_chA_startButton.text() == "中断済み"
    tab.viewModel.running_changed_b.emit(False)
    tab.viewModel.running_changed_a.emit(True)
    assert all(not button.isEnabled() for button in buttons)
    tab.viewModel.running_changed_a.emit(False)
    window.close()


def test_opv_jvl_always_mutually_exclusive(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    opv_btn, jvl_btn, dual_a_btn, dual_b_btn = _buttons(window)

    window.opv_tab.viewModel.running_changed.emit(True)
    assert not jvl_btn.isEnabled()
    assert jvl_btn.toolTip() != ""
    # 2400選択(既定値)なので2ch群は並行実行可能
    assert dual_a_btn.isEnabled()
    assert dual_b_btn.isEnabled()

    window.opv_tab.viewModel.running_changed.emit(False)
    assert jvl_btn.isEnabled()
    assert jvl_btn.toolTip() == ""
    window.close()


def test_dual_mode_a_b_always_mutually_exclusive(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    opv_btn, jvl_btn, dual_a_btn, dual_b_btn = _buttons(window)

    window.dual_channel_tab.viewModel.running_changed_a.emit(True)
    assert not dual_b_btn.isEnabled()
    assert opv_btn.isEnabled()
    assert jvl_btn.isEnabled()

    window.dual_channel_tab.viewModel.running_changed_a.emit(False)
    assert dual_b_btn.isEnabled()
    window.close()


def test_2612b_selection_cross_locks_opvjvl_and_dual_groups(qtbot, monkeypatch, tmp_path):
    """OPV/JVLの機器選択が2612B(index==1)の場合、OPV/JVL群⇔2ch群が相互排他になる。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    opv_btn, jvl_btn, dual_a_btn, dual_b_btn = _buttons(window)

    window.device_settings["opvjvl_device_type_index"] = 1
    window._update_start_button_locks()

    window.opv_tab.viewModel.running_changed.emit(True)
    assert not dual_a_btn.isEnabled()
    assert not dual_b_btn.isEnabled()
    assert dual_a_btn.toolTip() != ""

    window.opv_tab.viewModel.running_changed.emit(False)
    assert dual_a_btn.isEnabled()
    assert dual_b_btn.isEnabled()

    window.dual_channel_tab.viewModel.running_changed_b.emit(True)
    assert not opv_btn.isEnabled()
    assert not jvl_btn.isEnabled()
    window.dual_channel_tab.viewModel.running_changed_b.emit(False)
    window.close()


def test_2400_selection_allows_parallel_execution(qtbot, monkeypatch, tmp_path):
    """OPV/JVLの機器選択が2400(既定値, index==0)の場合、2ch群との排他は発生しない。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)
    opv_btn, jvl_btn, dual_a_btn, dual_b_btn = _buttons(window)

    assert window.device_settings.get("opvjvl_device_type_index", 0) == 0

    window.opv_tab.viewModel.running_changed.emit(True)
    window.dual_channel_tab.viewModel.running_changed_a.emit(True)
    assert dual_a_btn.isEnabled() is False  # 自分自身が実行中なので無効(排他とは無関係)
    assert not dual_b_btn.isEnabled()  # モードA実行中との相互排他(常時)
    # OPVとモードAは機器が異なるため、互いの排他ロックは発生しない
    assert opv_btn.toolTip() == "" or "共有" not in opv_btn.toolTip()

    window.opv_tab.viewModel.running_changed.emit(False)
    window.dual_channel_tab.viewModel.running_changed_a.emit(False)
    window.close()
