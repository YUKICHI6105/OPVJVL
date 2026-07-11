"""アプリケーションのメインウィンドウ(View層)。

`resources/ui/main_window.ui`(Qt Designer作成済み、現在は未使用。参照や
将来の巻き戻しのため残置)はロードせず、B-6-2節のオブジェクト階層に従い
Pythonコードでウィジェットツリーを直接構築する。
OPV/JVL/2ch活用の各タブをコードで構築して挿入する。
業務ロジックは持たない(B-6-1節: ハイブリッド方式)。
"""
from __future__ import annotations

import os

from qtcompat import QAction, QtCore, QtGui, QtWidgets, enum_value, qt_exec
from utils import device_settings, persistence, win32_utils
from utils.logger import get_logger
from utils.paths import get_log_dir
from views import plot_buffer, theme
from views.dialogs import DeviceSettingsDialog, DisplaySettingsDialog
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab
from views.opv_tab import OPVTab

_DEVICE_TYPE_BY_INDEX = {0: "keithley2400", 1: "keithley2612b"}

logger = get_logger("main_window")


def _get_widget_value(widget):
    """ウィジェット種別に応じて永続化用の値を取り出す。"""
    if isinstance(widget, QtWidgets.QDoubleSpinBox):
        return widget.value()
    if isinstance(widget, QtWidgets.QSpinBox):
        return widget.value()
    if isinstance(widget, QtWidgets.QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QtWidgets.QComboBox):
        return widget.currentText()
    if isinstance(widget, QtWidgets.QLineEdit):
        return widget.text()
    raise TypeError(f"永続化に未対応のウィジェット型です: {type(widget).__name__}")


def _set_widget_value(widget, value) -> None:
    """ウィジェット種別に応じて永続化された値を復元する。型不一致は握り潰さず変換する。"""
    if isinstance(widget, QtWidgets.QDoubleSpinBox):
        widget.setValue(float(value))
    elif isinstance(widget, QtWidgets.QSpinBox):
        widget.setValue(int(value))
    elif isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, QtWidgets.QComboBox):
        widget.setCurrentText(str(value))
    elif isinstance(widget, QtWidgets.QLineEdit):
        widget.setText(str(value))
    else:
        raise TypeError(f"永続化に未対応のウィジェット型です: {type(widget).__name__}")


class MainWindow(QtWidgets.QMainWindow):
    """3つのタブを持つメインウィンドウ(B-6-2節の階層をPythonコードで構築)。"""

    def __init__(self, parent=None, developer_mode: bool = False):
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle("太陽電池と発光素子計測プログラム")
        self.resize(1200, 800)

        self.developer_mode = developer_mode
        self.device_settings = device_settings.load_device_settings()

        self._build_central_widget()
        self._apply_device_settings(self.device_settings)
        self._restore_measurement_settings()
        self._build_menu_bar()
        self._connect_running_signals()
        self.setStatusBar(QtWidgets.QStatusBar(self))

    # ------------------------------------------------------------------
    # 測定パラメータの永続化(EQEのpersistence.py/settings_controller.py踏襲)
    # ------------------------------------------------------------------
    def _persistent_widgets(self) -> dict:
        """全タブ+共通保存設定パネルの永続化対象ウィジェット対応表を返す。"""
        widgets = {
            "shared_sample_name": self.sharedSampleNameEdit,
            "shared_save_dir": self.sharedSaveDirEdit,
        }
        widgets.update(self.opv_tab.persistent_widgets())
        widgets.update(self.jvl_tab.persistent_widgets())
        widgets.update(self.dual_channel_tab.persistent_widgets())
        return widgets

    def _restore_measurement_settings(self) -> None:
        """settings.jsonから前回の測定パラメータ・グラフ表示設定をUIへ復元する。"""
        settings = persistence.load_settings()
        for key, widget in self._persistent_widgets().items():
            if key not in settings:
                continue
            try:
                _set_widget_value(widget, settings[key])
            except (TypeError, ValueError) as e:
                # 破損した値が1つあっても他のキーの復元は続行する
                logger.warning("設定キー %s の復元に失敗しました: %s", key, e)

        # グラフ表示スタイル(EQEの「表示の設定」から移植)の復元と適用
        self._graph_style = {
            key: settings.get(key, default)
            for key, default in theme.GRAPH_STYLE_DEFAULTS.items()
        }
        try:
            self._apply_graph_style()
        except (TypeError, ValueError) as e:
            logger.warning("グラフ表示設定の復元に失敗したためデフォルト値を使用します: %s", e)
            self._graph_style = dict(theme.GRAPH_STYLE_DEFAULTS)
            self._apply_graph_style()

    def _collect_measurement_settings(self) -> dict:
        """現在のUI入力値・グラフ表示設定を永続化用の辞書として収集する。"""
        settings = {
            key: _get_widget_value(widget)
            for key, widget in self._persistent_widgets().items()
        }
        settings.update(self._graph_style)
        return settings

    def closeEvent(self, event) -> None:  # noqa: N802 - Qtの命名規則
        """終了時に測定パラメータをsettings.jsonへ保存する(EQEパターン)。"""
        try:
            persistence.save_settings(self._collect_measurement_settings())
            logger.info("測定パラメータをsettings.jsonへ保存しました。")
        except Exception as e:  # noqa: BLE001 - 保存失敗で終了を妨げない
            logger.error("終了時の設定保存に失敗しました: %s", e)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        centralWidget = QtWidgets.QWidget(objectName="centralWidget")
        centralLayout = QtWidgets.QVBoxLayout(centralWidget)
        centralLayout.setObjectName("centralLayout")
        centralLayout.setContentsMargins(0, 0, 0, 0)

        self.sharedSaveGroupBox = self._build_shared_save_group()
        # 各タブの設定カラム(views/theme.py の SETTINGS_PANEL_WIDTH)と横幅を揃え、
        # 右側に空のストレッチを添えることで「左半分の設定カラム内に収まる」よう
        # 左詰めで配置する(review.md指摘#1: 左半分からはみ出す問題への対応)。
        sharedSaveRow = QtWidgets.QHBoxLayout()
        sharedSaveRow.setObjectName("sharedSaveRow")
        sharedSaveRow.addWidget(self.sharedSaveGroupBox)
        sharedSaveRow.addStretch(1)
        centralLayout.addLayout(sharedSaveRow, 0)

        self.opv_tab = OPVTab(
            sample_name_edit=self.sharedSampleNameEdit,
            save_dir_edit=self.sharedSaveDirEdit,
        )
        self.jvl_tab = JVLTab(
            sample_name_edit=self.sharedSampleNameEdit,
            save_dir_edit=self.sharedSaveDirEdit,
        )
        # 2ch活用モードは、モードBのみチャンネルA/Bの素子が異なるため
        # 共通保存設定パネルを流用しない(モードAのサンプル名/保存先のみ流用)。
        self.dual_channel_tab = DualChannelTab(
            sample_name_edit=self.sharedSampleNameEdit,
            save_dir_edit=self.sharedSaveDirEdit,
        )

        self.mainTabWidget = QtWidgets.QTabWidget(objectName="mainTabWidget")
        self.mainTabWidget.addTab(self.opv_tab, "OPVモード")
        self.mainTabWidget.addTab(self.jvl_tab, "JVLモード")
        self.mainTabWidget.addTab(self.dual_channel_tab, "2ch活用モード")

        # 共通保存設定パネルは、「2ch活用モードタブ」が表示中かつその内部モードが
        # 「モードB」の間だけ非表示にする(モードBはチャンネルA/Bそれぞれ別の素子を
        # 計測するため、保存先・サンプル名をタブ内でローカルに個別入力する運用のため)。
        # OPV/JVLタブ表示中や2ch活用モードAの間は、常に共通保存設定パネルを表示する。
        self.mainTabWidget.currentChanged.connect(self._update_shared_panel_visibility)
        self.dual_channel_tab.dual_modeSelectCombo.currentIndexChanged.connect(
            self._update_shared_panel_visibility
        )
        self._update_shared_panel_visibility()

        centralLayout.addWidget(self.mainTabWidget, 1)
        self.setCentralWidget(centralWidget)

    def _update_shared_panel_visibility(self, *_args) -> None:
        """2ch活用モードタブがモードB表示中の場合のみ、共通保存設定パネルを隠す。"""
        is_dual_tab_active = self.mainTabWidget.currentWidget() is self.dual_channel_tab
        is_mode_b = self.dual_channel_tab.dual_modeSelectCombo.currentIndex() == 1
        self.sharedSaveGroupBox.setVisible(not (is_dual_tab_active and is_mode_b))

    def _build_shared_save_group(self) -> QtWidgets.QGroupBox:
        """タブ横断で共有する「共通保存設定」パネル(サンプル名/保存先)。

        EQEプロジェクト(`views/main_window.py`のinit_ui())のレイアウトに倣い、
        `mainTabWidget`より外側(上)に配置することで、タブを切り替えても
        サンプル名・保存先の入力値が維持されるようにする。
        「サンプル名」「保存先」を縦2行のフォームで並べ(review.md指摘#2)、
        横幅は各タブの設定カラム(`theme.SETTINGS_PANEL_*`)に揃えて
        左側の設定カラム内に収める。縦方向のサイズポリシーはMaximumにして、
        ウィンドウ拡大時にタブ側(グラフ等)へ余剰スペースが割り当てられるようにする。
        """
        sharedSaveGroupBox = QtWidgets.QGroupBox("共通保存設定", objectName="sharedSaveGroupBox")
        size_policy_fixed = enum_value(QtWidgets.QSizePolicy, "Maximum")
        size_policy_preferred = enum_value(QtWidgets.QSizePolicy, "Preferred")
        sharedSaveGroupBox.setSizePolicy(size_policy_preferred, size_policy_fixed)
        sharedSaveGroupBox.setMinimumWidth(theme.SETTINGS_PANEL_MIN_WIDTH)
        sharedSaveGroupBox.setMaximumWidth(theme.SETTINGS_PANEL_MAX_WIDTH)

        sharedSaveFormLayout = QtWidgets.QFormLayout(sharedSaveGroupBox)
        sharedSaveFormLayout.setObjectName("sharedSaveFormLayout")

        # 1行目: サンプル名
        self.sharedSampleNameEdit = QtWidgets.QLineEdit(objectName="sharedSampleNameEdit")
        sharedSaveFormLayout.addRow("サンプル名:", self.sharedSampleNameEdit)

        # 2行目: 保存先 + 参照ボタン
        self.sharedSaveDirEdit = QtWidgets.QLineEdit(objectName="sharedSaveDirEdit")
        self.sharedBrowseSaveDirButton = QtWidgets.QPushButton(
            "参照...", objectName="sharedBrowseSaveDirButton"
        )
        self.sharedBrowseSaveDirButton.clicked.connect(self._on_browse_shared_save_dir)
        sharedSaveDirRow = QtWidgets.QHBoxLayout()
        sharedSaveDirRow.setObjectName("sharedSaveDirRow")
        sharedSaveDirRow.addWidget(self.sharedSaveDirEdit)
        sharedSaveDirRow.addWidget(self.sharedBrowseSaveDirButton)
        sharedSaveFormLayout.addRow("保存先:", sharedSaveDirRow)

        return sharedSaveGroupBox

    # ------------------------------------------------------------------
    # 機器設定(接続先ポート等)の適用・永続化
    # ------------------------------------------------------------------
    def _apply_device_settings(self, settings: dict) -> None:
        """機器設定ダイアログで確定した設定値(またはロード直後の設定値)を各タブへ反映する。

        開発者モードでない場合は、settings.jsonに過去保存された use_mock=True が
        残っていても、実機のつもりが誤ってモックのままだったという事故を防ぐため
        必ずFalseとして扱う(self.developer_modeとの論理積を取る)。
        """
        self.opv_tab.apply_device_settings(
            _DEVICE_TYPE_BY_INDEX.get(settings.get("opv_device_type_index", 0), "keithley2400"),
            settings.get("opv_connection", ""),
            settings.get("opv_channel", "smua"),
            self.developer_mode and settings.get("opv_use_mock", False),
        )
        self.jvl_tab.apply_device_settings(
            _DEVICE_TYPE_BY_INDEX.get(settings.get("jvl_device_type_index", 0), "keithley2400"),
            settings.get("jvl_connection", ""),
            settings.get("jvl_bm9_port", ""),
            settings.get("jvl_channel", "smua"),
            self.developer_mode and settings.get("jvl_use_mock", False),
        )
        self.dual_channel_tab.apply_device_settings_mode_a(
            settings.get("dual_a_connection", ""),
            settings.get("dual_a_bm9_port", ""),
            self.developer_mode and settings.get("dual_a_use_mock", False),
        )
        self.dual_channel_tab.apply_device_settings_mode_b(
            settings.get("dual_b_connection", ""),
            settings.get("dual_b_bm9_port", ""),
            self.developer_mode and settings.get("dual_b_use_mock", False),
        )

    def _open_device_settings_dialog(self) -> None:
        dialog = DeviceSettingsDialog(self, self.device_settings, self.developer_mode)
        accepted = enum_value(QtWidgets.QDialog, "Accepted")
        if qt_exec(dialog) == accepted:
            self.device_settings = dialog.get_settings()
            self._apply_device_settings(self.device_settings)
            device_settings.save_device_settings(self.device_settings)

    def _connect_running_signals(self) -> None:
        """いずれかの測定が実行中の間は「機器設定」メニュー項目を無効化する。

        測定実行中に接続先(COM/VISAポート)が変更されてしまうことを防ぐため、
        各タブのViewModelが公開する running_changed 系シグナルを購読し、いずれか
        1つでもTrueになったら無効化、全てFalseに戻ったら有効化する。
        """
        self._running_flags = {
            "opv": False,
            "jvl": False,
            "dual_a": False,
            "dual_b": False,
        }
        self.opv_tab.viewModel.running_changed.connect(
            lambda running: self._on_any_running_changed("opv", running)
        )
        self.jvl_tab.viewModel.running_changed.connect(
            lambda running: self._on_any_running_changed("jvl", running)
        )
        self.dual_channel_tab.viewModel.running_changed_a.connect(
            lambda running: self._on_any_running_changed("dual_a", running)
        )
        self.dual_channel_tab.viewModel.running_changed_b.connect(
            lambda running: self._on_any_running_changed("dual_b", running)
        )

    def _on_any_running_changed(self, key: str, running: bool) -> None:
        self._running_flags[key] = running
        any_running = any(self._running_flags.values())
        self.actionDeviceSettings.setEnabled(not any_running)

        # 測定中はWindowsのスリープ・ディスプレイ消灯を防止し、
        # 全測定の終了・中断で通常状態へ復帰する(EQEのprevent_sleep踏襲)
        if any_running != getattr(self, "_sleep_prevented", False):
            self._sleep_prevented = any_running
            win32_utils.prevent_sleep(any_running)

    def _on_browse_shared_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.sharedSaveDirEdit.setText(directory)

    def _build_menu_bar(self) -> None:
        """メニューバーを構築する。

        EQEプロジェクト(``EQE/src/views/main_window.py`` の ``create_menu_bar``)の
        メニュー構成から、OPVJVLに適用可能な項目を移植した:
        終了(Ctrl+Q) / 測定開始(F5)・測定中断(Esc) / グラフ表示の設定(Ctrl+D) /
        ログファイルの表示・エクスポート / バージョン情報。
        EQE固有の機能(EQE計算、テーマ切替、公式ドキュメント、
        リアルタイムログコンソール等)は移植対象外。
        """
        menuBar = self.menuBar()
        menuBar.setObjectName("menuBar")

        # --- ファイル メニュー ---
        menuFile = menuBar.addMenu("ファイル(&F)")
        menuFile.setObjectName("menuFile")
        self.actionExit = QAction("終了(&X)", self)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.actionExit.setStatusTip("アプリケーションを終了します")
        self.actionExit.triggered.connect(self.close)
        menuFile.addAction(self.actionExit)

        # --- 測定 メニュー ---
        menuMeasurement = menuBar.addMenu("測定(&M)")
        menuMeasurement.setObjectName("menuMeasurement")

        self.actionStartMeasurement = QAction("測定開始(現在のタブ)(&S)", self)
        self.actionStartMeasurement.setObjectName("actionStartMeasurement")
        self.actionStartMeasurement.setShortcut(QtGui.QKeySequence("F5"))
        self.actionStartMeasurement.setStatusTip("表示中のタブの測定を開始します")
        self.actionStartMeasurement.triggered.connect(self._on_menu_start_measurement)
        menuMeasurement.addAction(self.actionStartMeasurement)

        self.actionStopMeasurement = QAction("測定中断(&T)", self)
        self.actionStopMeasurement.setObjectName("actionStopMeasurement")
        self.actionStopMeasurement.setShortcut(QtGui.QKeySequence("Esc"))
        self.actionStopMeasurement.setStatusTip("表示中のタブの測定を中断します")
        self.actionStopMeasurement.triggered.connect(self._on_menu_stop_measurement)
        menuMeasurement.addAction(self.actionStopMeasurement)

        menuMeasurement.addSeparator()

        self.actionDeviceSettings = QAction("機器設定...(&D)", self)
        self.actionDeviceSettings.setObjectName("actionDeviceSettings")
        self.actionDeviceSettings.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        self.actionDeviceSettings.triggered.connect(self._open_device_settings_dialog)
        menuMeasurement.addAction(self.actionDeviceSettings)

        # --- 表示 メニュー ---
        menuView = menuBar.addMenu("表示(&V)")
        menuView.setObjectName("menuView")
        self.actionDisplaySettings = QAction("グラフ表示の設定...(&D)", self)
        self.actionDisplaySettings.setObjectName("actionDisplaySettings")
        self.actionDisplaySettings.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self.actionDisplaySettings.setStatusTip("グラフの線幅・シンボル・フォント等を設定します")
        self.actionDisplaySettings.triggered.connect(self._open_display_settings_dialog)
        menuView.addAction(self.actionDisplaySettings)

        # --- ヘルプ メニュー ---
        menuHelp = menuBar.addMenu("ヘルプ(&H)")
        menuHelp.setObjectName("menuHelp")

        self.actionShowLogFile = QAction("ログファイルを表示(&L)", self)
        self.actionShowLogFile.setObjectName("actionShowLogFile")
        self.actionShowLogFile.triggered.connect(self._show_log_file)
        menuHelp.addAction(self.actionShowLogFile)

        self.actionExportLogFile = QAction("ログファイルのエクスポート...(&E)", self)
        self.actionExportLogFile.setObjectName("actionExportLogFile")
        self.actionExportLogFile.triggered.connect(self._export_log_file)
        menuHelp.addAction(self.actionExportLogFile)

        menuHelp.addSeparator()

        self.actionAbout = QAction("バージョン情報(&A)", self)
        self.actionAbout.setObjectName("actionAbout")
        self.actionAbout.triggered.connect(self._show_about)
        menuHelp.addAction(self.actionAbout)

    # ------------------------------------------------------------------
    # メニューアクションのハンドラ(EQEから移植した項目)
    # ------------------------------------------------------------------
    def _current_run_buttons(self):
        """表示中のタブ(2ch活用モードは選択中モード)の開始/中断ボタンを返す。"""
        current = self.mainTabWidget.currentWidget()
        if current is self.opv_tab:
            return self.opv_tab.opv_startButton, self.opv_tab.opv_stopButton
        if current is self.jvl_tab:
            return self.jvl_tab.jvl_startButton, self.jvl_tab.jvl_stopButton
        if self.dual_channel_tab.dual_modeSelectCombo.currentIndex() == 0:
            return (
                self.dual_channel_tab.dual_a_startButton,
                self.dual_channel_tab.dual_a_stopButton,
            )
        return (
            self.dual_channel_tab.dual_b_startButton,
            self.dual_channel_tab.dual_b_stopButton,
        )

    def _on_menu_start_measurement(self) -> None:
        """メニュー/F5から表示中タブの測定を開始する(実行中は何もしない)。"""
        start_button, _stop_button = self._current_run_buttons()
        if start_button.isEnabled():
            start_button.click()

    def _on_menu_stop_measurement(self) -> None:
        """メニュー/Escから表示中タブの測定を中断する(停止中は何もしない)。"""
        _start_button, stop_button = self._current_run_buttons()
        if stop_button.isEnabled():
            stop_button.click()

    def _all_plot_widgets(self) -> list:
        """全タブの全プロットウィジェット(グラフ表示設定の適用対象)を返す。"""
        widgets = []
        for tab in (self.opv_tab, self.jvl_tab, self.dual_channel_tab):
            widgets.extend(tab.plot_widgets())
        return widgets

    def _apply_graph_style(self) -> None:
        """現在のグラフ表示設定を全プロットへ適用する。"""
        plot_buffer.apply_graph_style(self._all_plot_widgets(), self._graph_style)

    def _open_display_settings_dialog(self) -> None:
        """「グラフ表示の設定」ダイアログ(EQEのDisplaySettingsDialog移植)を開く。"""
        dialog = DisplaySettingsDialog(self, dict(self._graph_style))
        accepted = enum_value(QtWidgets.QDialog, "Accepted")
        if qt_exec(dialog) == accepted:
            self._graph_style = dialog.get_settings()
            self._apply_graph_style()
            # 次回起動に備えて即時保存する(EQEのsettings_controller踏襲)
            persistence.save_settings(dict(self._graph_style))
            logger.info("グラフ表示設定を更新しました: %s", self._graph_style)

    def _log_file_path(self) -> str:
        return os.path.join(get_log_dir(), "opvjvl_software.log")

    def _show_log_file(self) -> None:
        """ログファイルをOS既定のアプリケーションで開く(EQEのshow_log_file移植)。"""
        log_path = self._log_file_path()
        if os.path.exists(log_path):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(log_path))
        else:
            QtWidgets.QMessageBox.information(
                self, "情報", f"ログファイルが見つかりません。\nパス: {log_path}"
            )

    def _export_log_file(self) -> None:
        """ログファイルを任意の場所へコピー保存する(EQEのexport_log_file移植)。"""
        import shutil

        log_path = self._log_file_path()
        if not os.path.exists(log_path):
            QtWidgets.QMessageBox.information(
                self, "情報", "ログファイルがまだ存在しないか作成されていません。"
            )
            return

        suggested_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(suggested_dir):
            suggested_dir = os.path.expanduser("~")

        dest_path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "ログファイルのエクスポート",
            os.path.join(suggested_dir, "opvjvl_software_export.log"),
            "Log Files (*.log);;All Files (*)",
        )
        if not dest_path:
            return
        try:
            shutil.copy2(log_path, dest_path)
            QtWidgets.QMessageBox.information(
                self, "成功", f"ログファイルを正常に書き出しました:\n{dest_path}"
            )
        except OSError as e:
            QtWidgets.QMessageBox.critical(
                self, "エラー", f"ログファイルの書き出しに失敗しました:\n{e}"
            )

    def _show_about(self) -> None:
        """バージョン情報ダイアログを表示する。"""
        QtWidgets.QMessageBox.about(
            self,
            "バージョン情報",
            "<h3>太陽電池と発光素子計測プログラム (OPVJVL)</h3>"
            "<p>太陽電池(OPV)のJV測定および発光素子のJVL測定ソフトウェア</p>"
            "<p>Ishii &amp; Fukagawa Lab (Chiba University)</p>",
        )
