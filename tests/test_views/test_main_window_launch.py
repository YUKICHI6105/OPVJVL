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


def test_log_panel_is_fixed_height_and_settings_take_extra_space(qtbot):
    """縦の余剰スペースがログではなく設定タブへ回ることを検証。

    以前はログがstretch=1で余剰を全て吸っていたため、ウィンドウを高くするほど
    ログだけが伸び、設定欄は項目の多いタブでも狭いままだった。
    """
    from qtcompat import QtWidgets
    from views import theme

    window = MainWindow()
    qtbot.addWidget(window)

    log_group = window.findChild(QtWidgets.QGroupBox, "logGroupBox")
    left_column = window.findChild(QtWidgets.QWidget, "leftColumnWidget")
    left_layout = left_column.layout()

    assert log_group.height() == theme.LOG_PANEL_HEIGHT
    assert log_group.minimumHeight() == log_group.maximumHeight()
    assert left_layout.stretch(left_layout.indexOf(log_group)) == 0
    assert left_layout.stretch(left_layout.indexOf(window.mainTabWidget)) == 1
