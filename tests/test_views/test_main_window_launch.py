"""MainWindow の起動・レイアウト確認テスト。"""
from __future__ import annotations

import pytest
from views.main_window import MainWindow


def test_main_window_launch(qtbot):
    """MainWindow が正常に起動し、3つのタブが存在することを検証。"""
    window = MainWindow()
    qtbot.addWidget(window)

    # タブ数の検証
    assert window.mainTabWidget.count() == 3

    # 各タブのテキストの検証
    assert window.mainTabWidget.tabText(0) == "OPVモード"
    assert window.mainTabWidget.tabText(1) == "JVLモード"
    assert window.mainTabWidget.tabText(2) == "2ch活用モード"

    # メインウィンドウの基本プロパティ
    assert window.windowTitle() == "太陽電池と発光素子計測プログラム"
