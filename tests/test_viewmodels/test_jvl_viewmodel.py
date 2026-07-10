"""JVLViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from opvjvl.qtcompat import QtWidgets
from opvjvl.viewmodels.jvl_viewmodel import JVLViewModel
from opvjvl.views.jvl_tab import JVLTab


def test_jvl_viewmodel_init(qtbot):
    """初期化時の状態検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)

    vm = JVLViewModel(tab)

    assert tab.jvl_startButton.isEnabled()
    assert not tab.jvl_stopButton.isEnabled()


def test_jvl_viewmodel_luminance_checkbox(qtbot):
    """輝度計チェックボックスの切り替えに伴い、BM9ポート入力欄が有効・無効化されることを検証。"""
    tab = JVLTab()
    qtbot.addWidget(tab)

    vm = JVLViewModel(tab)

    # 初期値はTrue (有効)
    assert tab.jvl_useLuminanceCheckBox.isChecked()
    assert tab.jvl_bm9PortCombo.isEnabled()

    # チェック解除 -> 無効化される
    tab.jvl_useLuminanceCheckBox.setChecked(False)
    assert not tab.jvl_bm9PortCombo.isEnabled()

    # 再チェック -> 有効化される
    tab.jvl_useLuminanceCheckBox.setChecked(True)
    assert tab.jvl_bm9PortCombo.isEnabled()
