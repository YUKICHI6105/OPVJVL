"""DualChannelViewModel の動作検証テスト。"""
from __future__ import annotations

import pytest
from qtcompat import QtWidgets
from viewmodels.dual_channel_viewmodel import DualChannelViewModel
from views.dual_channel_tab import DualChannelTab


def test_dual_channel_viewmodel_init(qtbot):
    """初期状態の検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    # モードA初期値
    assert tab.dual_a_startButton.isEnabled()
    assert not tab.dual_a_stopButton.isEnabled()

    # モードB初期値
    assert tab.dual_b_startButton.isEnabled()
    assert not tab.dual_b_stopButton.isEnabled()


def test_dual_channel_mode_b_mutual_exclusion(qtbot):
    """モードBにおいて、チャンネルAとBで同時に「発光素子」を選択できない排他制御の検証。"""
    tab = DualChannelTab()
    qtbot.addWidget(tab)

    vm = tab.viewModel

    # 初期状態 (チャンネルA: 太陽電池, チャンネルB: 太陽電池)
    assert tab.dual_chA_deviceModeCombo.currentText() == "太陽電池"
    assert tab.dual_chB_deviceModeCombo.currentText() == "太陽電池"

    # チャンネルAを「発光素子」にする
    tab.dual_chA_deviceModeCombo.setCurrentText("発光素子")

    # 排他制御により、チャンネルBの「発光素子」は選択不可、または「太陽電池」に強制され、コンボボックス項目から消えるか無効になる
    # 設計書によると「発光素子モード選択肢を無効化（disable）し太陽電池モードのみ選択可能にする」
    assert tab.dual_chB_deviceModeCombo.currentText() == "太陽電池"
    
    model = tab.dual_chB_deviceModeCombo.model()
    for index in range(tab.dual_chB_deviceModeCombo.count()):
        if tab.dual_chB_deviceModeCombo.itemText(index) == "発光素子":
            item = model.item(index)
            assert not item.isEnabled()

    # チャンネルAを「太陽電池」に戻す
    tab.dual_chA_deviceModeCombo.setCurrentText("太陽電池")
    for index in range(tab.dual_chB_deviceModeCombo.count()):
        if tab.dual_chB_deviceModeCombo.itemText(index) == "発光素子":
            item = model.item(index)
            assert item.isEnabled()

