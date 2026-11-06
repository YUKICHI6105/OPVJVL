"""BM9が使えないときの選択と測定開始条件。"""
from __future__ import annotations

import pytest

from views import luminance_confirm
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab


def test_bm9_probe_checks_response_and_closes_meter(qtbot, monkeypatch):
    meter_calls = []

    class UnresponsiveMeter:
        def connect(self):
            meter_calls.append("connect")

        def get_luminance(self):
            meter_calls.append("read")
            raise RuntimeError("BM9から応答がありません")

        def close(self):
            meter_calls.append("close")

    monkeypatch.setattr(
        luminance_confirm.registry, "create_luminance_meter", lambda *a, **k: UnresponsiveMeter()
    )
    assert "BM9から応答がありません" in luminance_confirm._unavailable_reason("COM4", False)
    assert meter_calls == ["connect", "read", "close"]


def test_missing_bm9_prompt_can_continue_or_cancel(qtbot, monkeypatch):
    def choose(label):
        def click(dialog):
            next(button for button in dialog.buttons() if button.text() == label).click()
        monkeypatch.setattr(luminance_confirm, "qt_exec", click)
        return luminance_confirm.confirm_luminance_use(None, "", False)

    assert choose("輝度なしで測定") is False
    assert choose("測定を中止") is None


def test_available_mock_bm9_can_be_selected_in_prompt(qtbot, monkeypatch):
    monkeypatch.setattr(
        luminance_confirm, "qt_exec",
        lambda dialog: next(button for button in dialog.buttons() if button.text() == "BM9を使用").click(),
    )
    assert luminance_confirm.confirm_luminance_use(None, "MOCK", True) is True


def test_available_mock_bm9_can_be_skipped_in_prompt(qtbot, monkeypatch):
    monkeypatch.setattr(
        luminance_confirm, "qt_exec",
        lambda dialog: next(
            button for button in dialog.buttons() if button.text() == "輝度なしで測定"
        ).click(),
    )
    assert luminance_confirm.confirm_luminance_use(None, "MOCK", True) is False


def test_jvl_fallback_keeps_measurement_start_and_disables_luminance(qtbot, tmp_path, monkeypatch):
    tab = JVLTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings("keithley2400", "MOCK", "", use_mock=True)
    tab.jvl_saveDirEdit.setText(str(tmp_path))
    monkeypatch.setattr("views.jvl_tab.confirm_luminance_use", lambda *a: False)
    configs = []
    monkeypatch.setattr(tab.viewModel, "start_measurement", configs.append)

    tab.jvl_startButton.click()
    assert len(configs) == 1
    assert configs[0].use_luminance is False
    assert configs[0].bm9_port is None
    assert not hasattr(tab, "jvl_useLuminanceCheckBox")


def test_mode_a_fallback_keeps_measurement_start_and_disables_luminance(qtbot, tmp_path, monkeypatch):
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings_mode_a("MOCK", "", use_mock=True)
    tab.dual_a_deviceModeCombo.setCurrentText("発光素子")
    tab.dual_a_saveDirEdit.setText(str(tmp_path))
    monkeypatch.setattr("views.dual_channel_tab.confirm_luminance_use", lambda *a: False)
    configs = []
    monkeypatch.setattr(tab.viewModel, "start_mode_a", configs.append)

    tab.dual_a_startButton.click()
    assert len(configs) == 1
    assert configs[0].device_mode == "発光素子"
    assert configs[0].use_luminance is False
    assert configs[0].bm9_port is None


@pytest.mark.parametrize("channel", ["A", "B"])
def test_mode_b_fallback_keeps_led_measurement_without_bm9(channel, qtbot, tmp_path, monkeypatch):
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings_mode_b("MOCK", "", use_mock=True)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    getattr(tab, f"dual_ch{channel}_deviceModeCombo").setCurrentText("発光素子")
    monkeypatch.setattr("views.dual_channel_tab.confirm_luminance_use", lambda *a: False)
    configs = []
    monkeypatch.setattr(tab.viewModel, "start_mode_b", configs.append)

    getattr(tab, f"dual_ch{channel}_startButton").click()
    assert len(configs) == 1
    selected = configs[0].channel_a if channel == "A" else configs[0].channel_b
    assert selected.enabled
    assert selected.device_mode == "発光素子"
    assert configs[0].bm9_port is None


def test_cancelled_bm9_prompt_does_not_start(qtbot, tmp_path, monkeypatch):
    tab = JVLTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings("keithley2400", "MOCK", "", use_mock=True)
    tab.jvl_saveDirEdit.setText(str(tmp_path))
    monkeypatch.setattr("views.jvl_tab.confirm_luminance_use", lambda *a: None)
    starts = []
    monkeypatch.setattr(tab.viewModel, "start_measurement", starts.append)
    tab.jvl_startButton.click()
    assert not starts


def test_joining_mode_b_led_can_continue_without_bm9(qtbot, tmp_path, monkeypatch):
    tab = DualChannelTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings_mode_b("MOCK", "", use_mock=True)
    tab.dual_b_saveDirEdit.setText(str(tmp_path))
    tab.dual_chB_deviceModeCombo.setCurrentText("発光素子")
    monkeypatch.setattr("views.dual_channel_tab.confirm_luminance_use", lambda *a: False)
    monkeypatch.setattr(tab.viewModel, "mode_b_is_running", lambda: True)
    configs = []
    monkeypatch.setattr(tab.viewModel, "start_mode_b", lambda config: configs.append(config) or False)

    tab.dual_chB_startButton.click()
    assert len(configs) == 1
    assert configs[0].channel_b.enabled
    assert configs[0].bm9_port is None
