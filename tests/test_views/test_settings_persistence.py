"""MainWindow経由の測定パラメータ保存・復元(GUIラウンドトリップ)のテスト。"""
from __future__ import annotations

from views.main_window import MainWindow


def test_main_window_saves_on_close_and_restores_on_next_launch(qtbot, monkeypatch, tmp_path):
    """終了時にUI値がsettings.jsonへ保存され、次回起動時に復元されることを検証。"""
    settings_path = tmp_path / "settings.json"
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(settings_path))

    # 1回目の起動: 値を変更して閉じる
    window1 = MainWindow()
    qtbot.addWidget(window1)
    window1.opv_tab.opv_vMinSpin.setValue(-0.25)
    window1.jvl_tab.jvl_useLuminanceCheckBox.setChecked(False)
    window1.dual_channel_tab.dual_chA_sampleNameEdit.setText("chA-sample")
    window1.sharedSampleNameEdit.setText("shared-dev")
    window1.close()  # closeEvent -> save_settings

    assert settings_path.exists()

    # 2回目の起動: 前回値が復元される
    window2 = MainWindow()
    qtbot.addWidget(window2)
    assert window2.opv_tab.opv_vMinSpin.value() == -0.25
    assert window2.jvl_tab.jvl_useLuminanceCheckBox.isChecked() is False
    assert window2.dual_channel_tab.dual_chA_sampleNameEdit.text() == "chA-sample"
    assert window2.sharedSampleNameEdit.text() == "shared-dev"
    window2.close()


def test_main_window_launches_with_defaults_when_no_settings(qtbot, monkeypatch, tmp_path):
    """settings.jsonが無い初回起動ではウィジェットのデフォルト値のままであることを検証。"""
    settings_path = tmp_path / "settings.json"
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(settings_path))

    window = MainWindow()
    qtbot.addWidget(window)
    assert window.opv_tab.opv_vMinSpin.value() == -0.1
    assert window.jvl_tab.jvl_vMaxSpin.value() == 1.9
    assert window.jvl_tab.jvl_useLuminanceCheckBox.isChecked() is True
    window.close()


def test_running_state_toggles_prevent_sleep(qtbot, monkeypatch, tmp_path):
    """測定中スリープ防止ON、全測定終了でOFFになることを検証(win32 APIはモック化)。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))

    from views import main_window as mw_mod

    calls = []
    monkeypatch.setattr(mw_mod.win32_utils, "prevent_sleep", calls.append)

    window = MainWindow()
    qtbot.addWidget(window)

    # OPV測定開始 → スリープ防止ON
    window.opv_tab.viewModel.running_changed.emit(True)
    assert calls == [True]

    # 並行してJVLも開始 → 既にONなので再呼び出しされない
    window.jvl_tab.viewModel.running_changed.emit(True)
    assert calls == [True]

    # OPVのみ終了 → JVLが動作中なのでOFFにならない
    window.opv_tab.viewModel.running_changed.emit(False)
    assert calls == [True]

    # 全て終了 → スリープ防止OFF
    window.jvl_tab.viewModel.running_changed.emit(False)
    assert calls == [True, False]
    window.close()
