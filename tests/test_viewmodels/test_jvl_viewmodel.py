"""JVLViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from qtcompat import QtWidgets
from viewmodels.jvl_viewmodel import JVLViewModel
from views.jvl_tab import JVLTab


def test_jvl_viewmodel_init(qtbot):
    """初期化時の状態検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    assert tab.jvl_startButton.isEnabled()
    assert not tab.jvl_stopButton.isEnabled()


def test_jvl_viewmodel_luminance_checkbox(qtbot):
    """輝度計チェックボックスの切り替えに伴い、Config構築時のuse_luminance/bm9_portが変化することを検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)
    tab.apply_device_settings("keithley2400", "COM5", "COM4")

    assert tab.jvl_useLuminanceCheckBox.isChecked()
    config = tab._build_config()
    assert config.use_luminance
    assert config.bm9_port == "COM4"

    tab.jvl_useLuminanceCheckBox.setChecked(False)
    config = tab._build_config()
    assert not config.use_luminance
    assert config.bm9_port is None

    tab.jvl_useLuminanceCheckBox.setChecked(True)
    config = tab._build_config()
    assert config.use_luminance
    assert config.bm9_port == "COM4"

