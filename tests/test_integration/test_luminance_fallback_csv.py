"""BM9なしを選んだ発光素子測定のCSVに輝度列が入らないことを確認する。"""
from __future__ import annotations

import csv

import pytest

from qtcompat import QtWidgets
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab


@pytest.mark.parametrize("mode", ["jvl", "dual_a", "dual_b"])
def test_led_measurement_without_bm9_saves_current_only(mode, qtbot, tmp_path, monkeypatch):
    if mode == "jvl":
        tab = JVLTab()
        monkeypatch.setattr("views.jvl_tab.play_completion_sound", lambda *a: None)
        monkeypatch.setattr("views.jvl_tab.confirm_luminance_use", lambda *a: False)
        tab.apply_device_settings("keithley2400", "MOCK", "", use_mock=True)
        prefix = "jvl"
        tab.jvl_saveDirEdit.setText(str(tmp_path))
        tab.jvl_sampleNameEdit.setText("led_no_bm9")
        signal = tab.viewModel.finished_ok
        button = tab.jvl_startButton
        result_ready = lambda: tab._last_result is not None
    else:
        tab = DualChannelTab()
        monkeypatch.setattr("views.dual_channel_tab.play_completion_sound", lambda *a: None)
        monkeypatch.setattr("views.dual_channel_tab.confirm_luminance_use", lambda *a: False)
        if mode == "dual_a":
            tab.apply_device_settings_mode_a("MOCK", "", use_mock=True)
            tab.dual_a_deviceModeCombo.setCurrentText("発光素子")
            tab.dual_a_saveDirEdit.setText(str(tmp_path))
            tab.dual_a_sampleNameEdit.setText("led_no_bm9")
            prefix = "dual_a"
            signal = tab.viewModel.finished_ok_a
            button = tab.dual_a_startButton
            result_ready = lambda: tab._last_result_a is not None
        else:
            tab.apply_device_settings_mode_b("MOCK", "", use_mock=True)
            tab.dual_modeSelectCombo.setCurrentIndex(1)
            tab.dual_chA_deviceModeCombo.setCurrentText("発光素子")
            tab.dual_b_saveDirEdit.setText(str(tmp_path))
            tab.dual_chA_sampleNameEdit.setText("led_no_bm9")
            prefix = "dual_chA"
            signal = tab.viewModel.finished_ok_b
            button = tab.dual_chA_startButton
            result_ready = lambda: tab._last_result_b is not None

    qtbot.addWidget(tab)
    for field, value in (("vMinSpin", 0.0), ("vMaxSpin", 0.1),
                         ("vStepSpin", 0.1), ("iterationSpin", 1), ("delaySpin", 0.0)):
        getattr(tab, f"{prefix}_{field}").setValue(value)

    with qtbot.waitSignal(signal, timeout=10000):
        button.click()
    qtbot.waitUntil(result_ready, timeout=5000)

    result_path = tmp_path / "led_no_bm9_JVL_measurement_data.csv"
    with result_path.open(encoding="utf-8", newline="") as stream:
        assert next(csv.reader(stream)) == ["voltage [V]", "current [A]"]

    renamed_path = tmp_path / "renamed.csv"
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (str(renamed_path), "")
    )
    tab.save_last_result_as()
    with renamed_path.open(encoding="utf-8", newline="") as stream:
        assert next(csv.reader(stream)) == ["voltage [V]", "current [A]"]
