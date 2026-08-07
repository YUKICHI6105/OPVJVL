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


def test_settings_column_width_is_stable_across_tabs(qtbot):
    """タブ/モードを切り替えても左の設定カラムの横幅が変わらないことを検証。

    以前は左カラムが可変幅(420〜600)で、タブごとに必要最小幅が違ううえ、
    2ch活用モードBでは共通保存設定パネルが隠れて最小幅が下がるため、
    タブを切り替えるたびに設定カラムの幅が動いていた。

    ``show()``は呼ばない(オフスクリーン環境でpyqtgraphを実描画させると
    不安定なため。conftest.py参照)。固定幅はレイアウトを確定させるだけで
    検証できる。
    """
    from qtcompat import QtWidgets
    from views import theme

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1200, 820)
    window.layout().activate()

    left_column = window.findChild(QtWidgets.QWidget, "leftColumnWidget")
    widths = []
    for tab_index in (0, 1, 2):
        window.mainTabWidget.setCurrentIndex(tab_index)
        if tab_index == 2:
            for mode_index in (0, 1):
                window.dual_channel_tab.dual_modeSelectCombo.setCurrentIndex(mode_index)
                qtbot.wait(10)
                widths.append(left_column.width())
        else:
            qtbot.wait(10)
            widths.append(left_column.width())

    assert widths == [theme.SETTINGS_PANEL_WIDTH] * len(widths)


def test_settings_scroll_areas_always_reserve_vertical_scrollbar(qtbot):
    """全タブの設定カラムが縦スクロールバーを常時表示することを検証。

    設定項目の多いタブだけ縦スクロールバーが出ると、そのぶん設定欄の実効幅が
    狭くなり、タブ切り替えのたびに入力欄の幅が変わって見える(実測で約28px)。
    常時表示にして、どのタブでも同じ幅を確保する。
    """
    from qtcompat import Qt, QtWidgets, enum_value

    always_on = enum_value(Qt, "ScrollBarAlwaysOn")
    always_off = enum_value(Qt, "ScrollBarAlwaysOff")

    window = MainWindow()
    qtbot.addWidget(window)

    for prefix in ("opv", "jvl", "dual_a", "dual_b"):
        scroll_area = window.findChild(QtWidgets.QScrollArea, f"{prefix}_settingsScrollArea")
        assert scroll_area is not None, prefix
        assert scroll_area.verticalScrollBarPolicy() == always_on, prefix
        assert scroll_area.horizontalScrollBarPolicy() == always_off, prefix
