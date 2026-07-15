"""review.md項目4のテスト: メニュー再編・F5/Escショートカット・ボタンラベル。"""
from __future__ import annotations

from views.main_window import MainWindow


def test_menu_bar_has_new_three_menu_structure(qtbot, monkeypatch, tmp_path):
    """メニューバーが「ファイル/設定/ヘルプ」の3メニュー構成になっていること。

    旧「測定」「表示」メニューは廃止され、バージョン情報アクションも削除される。
    「ファイル」メニューには「データを開く」が追加される。
    """
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    menu_bar = window.menuBar()
    menu_titles = [action.text() for action in menu_bar.actions()]
    assert len(menu_titles) == 3
    assert menu_titles[0] == "ファイル(&F)"
    assert menu_titles[1] == "設定(&S)"
    assert menu_titles[2] == "ヘルプ(&H)"

    # 旧メニュー/バージョン情報が残っていないこと
    assert not hasattr(window, "actionAbout")
    assert not hasattr(window, "menuMeasurement")
    assert not hasattr(window, "menuView")

    # ファイルメニューに「データを開く」が追加されていること
    assert hasattr(window, "actionOpenData")
    assert window.actionOpenData.text() == "データを開く...(&O)"
    assert window.actionOpenData.shortcut().toString() == "Ctrl+O"

    # 設定メニューへ機器設定・表示設定が統合されていること(objectNameは維持)
    assert window.actionDeviceSettings.objectName() == "actionDeviceSettings"
    assert window.actionDeviceSettings.text() == "測定の設定...(&M)"
    assert window.actionDisplaySettings.text() == "表示の設定...(&D)"

    window.close()


def test_f5_and_esc_shortcuts_registered(qtbot, monkeypatch, tmp_path):
    """F5/EscのQShortcutが登録され、F5相当の呼び出しで開始ボタンclickに到達すること。

    開始ボタンが無効な場合は何もしない(排他ロック中の誤操作防止)ことも検証する。
    """
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._startShortcut.key().toString() == "F5"
    assert window._stopShortcut.key().toString() == "Esc"

    clicked = []
    window.opv_tab.opv_startButton.clicked.connect(lambda: clicked.append("start"))

    # 表示中(OPVタブ)の開始ボタンが有効な場合、F5相当のハンドラ呼び出しでclickへ到達する
    assert window.mainTabWidget.currentWidget() is window.opv_tab
    assert window.opv_tab.opv_startButton.isEnabled()
    window._on_menu_start_measurement()
    assert clicked == ["start"]

    # 開始ボタンが無効(排他ロック中)なら何もしない
    clicked.clear()
    window.opv_tab.opv_startButton.setEnabled(False)
    window._on_menu_start_measurement()
    assert clicked == []

    window.close()


def test_start_stop_buttons_show_shortcut_hint(qtbot, monkeypatch, tmp_path):
    """全タブの開始/中断ボタンのテキストに (F5)/(Esc) が含まれること。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    start_buttons = [
        window.opv_tab.opv_startButton,
        window.jvl_tab.jvl_startButton,
        window.dual_channel_tab.dual_a_startButton,
        window.dual_channel_tab.dual_b_startButton,
    ]
    stop_buttons = [
        window.opv_tab.opv_stopButton,
        window.jvl_tab.jvl_stopButton,
        window.dual_channel_tab.dual_a_stopButton,
        window.dual_channel_tab.dual_b_stopButton,
    ]
    for button in start_buttons:
        assert "(F5)" in button.text()
        assert "開始" in button.text()  # QSS配色セレクタ(text*="開始")の一致確認
    for button in stop_buttons:
        assert "(Esc)" in button.text()
        assert "中断" in button.text()  # QSS配色セレクタ(text*="中断")の一致確認

    window.close()


def test_open_data_menu_shows_error_for_invalid_file(qtbot, monkeypatch, tmp_path):
    """データを開くで、有効なデータが1点も読み込めないCSVはエラーダイアログのみ表示する。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("not,valid,csv\nfoo,bar,baz\n", encoding="utf-8")

    monkeypatch.setattr(
        "views.main_window.QtWidgets.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(bad_csv), "CSV Files (*.csv)"),
    )
    warnings = []
    monkeypatch.setattr(
        "views.main_window.QtWidgets.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )

    window._on_menu_open_data()
    assert len(warnings) == 1
    assert window._data_viewer_dialogs == []

    window.close()


def test_open_data_menu_opens_viewer_for_valid_file(qtbot, monkeypatch, tmp_path):
    """有効なCSVでは DataViewerDialog が開かれ、参照リストに保持される。"""
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    window = MainWindow()
    qtbot.addWidget(window)

    good_csv = tmp_path / "good.csv"
    good_csv.write_text(
        "voltage [V],current [A]\n0.0,0.001\n0.1,0.002\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        "views.main_window.QtWidgets.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(good_csv), "CSV Files (*.csv)"),
    )

    window._on_menu_open_data()
    assert len(window._data_viewer_dialogs) == 1
    dialog = window._data_viewer_dialogs[0]
    qtbot.addWidget(dialog)
    dialog.close()
    assert window._data_viewer_dialogs == []

    window.close()
