"""タブ切り替えの動作検証テスト。"""
from __future__ import annotations

import pytest
from views.main_window import MainWindow


def test_tab_switching(qtbot):
    """タブ切り替えが正しく反映されることを検証。"""
    window = MainWindow()
    qtbot.addWidget(window)

    # 初期選択タブ (OPV)
    assert window.mainTabWidget.currentIndex() == 0

    # JVLタブに切り替え
    window.mainTabWidget.setCurrentIndex(1)
    assert window.mainTabWidget.currentIndex() == 1

    # 2ch活用タブに切り替え
    window.mainTabWidget.setCurrentIndex(2)
    assert window.mainTabWidget.currentIndex() == 2
