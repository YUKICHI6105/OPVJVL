"""アプリケーションのメインウィンドウ(View層)。

`resources/ui/main_window.ui`(Qt Designer作成済み、現在は未使用。参照や
将来の巻き戻しのため残置)はロードせず、B-6-2節のオブジェクト階層に従い
Pythonコードでウィジェットツリーを直接構築する。
OPV/JVL/2ch活用の各タブをコードで構築して挿入する。
業務ロジックは持たない(B-6-1節: ハイブリッド方式)。
"""
from __future__ import annotations

from qtcompat import QAction, QtGui, QtWidgets, enum_value, qt_exec
from utils import device_settings, persistence, win32_utils
from utils.logger import get_logger
from views.dialogs import DeviceSettingsDialog
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
        """settings.jsonから前回の測定パラメータをUIへ復元する。"""
        settings = persistence.load_settings()
        for key, widget in self._persistent_widgets().items():
            if key not in settings:
                continue
            try:
                _set_widget_value(widget, settings[key])
            except (TypeError, ValueError) as e:
                # 破損した値が1つあっても他のキーの復元は続行する
                logger.warning("設定キー %s の復元に失敗しました: %s", key, e)

    def _collect_measurement_settings(self) -> dict:
        """現在のUI入力値を永続化用の辞書として収集する。"""
        return {
            key: _get_widget_value(widget)
            for key, widget in self._persistent_widgets().items()
        }

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
        centralLayout.addWidget(self.sharedSaveGroupBox, 0)

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
        1行構成にして高さを最小限に抑え、グラフ表示領域を圧迫しないようにする。
        縦方向のサイズポリシーもMaximumにして、ウィンドウ拡大時に本パネルではなく
        タブ側(グラフ等)に余剰スペースが割り当てられるようにする。
        """
        sharedSaveGroupBox = QtWidgets.QGroupBox("共通保存設定", objectName="sharedSaveGroupBox")
        size_policy_fixed = enum_value(QtWidgets.QSizePolicy, "Maximum")
        size_policy_expanding = enum_value(QtWidgets.QSizePolicy, "Expanding")
        sharedSaveGroupBox.setSizePolicy(size_policy_expanding, size_policy_fixed)

        sharedSaveRowLayout = QtWidgets.QHBoxLayout(sharedSaveGroupBox)
        sharedSaveRowLayout.setObjectName("sharedSaveRowLayout")

        sharedSaveRowLayout.addWidget(QtWidgets.QLabel("サンプル名:"))
        self.sharedSampleNameEdit = QtWidgets.QLineEdit(objectName="sharedSampleNameEdit")
        sharedSaveRowLayout.addWidget(self.sharedSampleNameEdit)

        sharedSaveRowLayout.addWidget(QtWidgets.QLabel("保存先:"))
        self.sharedSaveDirEdit = QtWidgets.QLineEdit(objectName="sharedSaveDirEdit")
        sharedSaveRowLayout.addWidget(self.sharedSaveDirEdit)

        self.sharedBrowseSaveDirButton = QtWidgets.QPushButton(
            "参照...", objectName="sharedBrowseSaveDirButton"
        )
        self.sharedBrowseSaveDirButton.clicked.connect(self._on_browse_shared_save_dir)
        sharedSaveRowLayout.addWidget(self.sharedBrowseSaveDirButton)

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
        menuBar = self.menuBar()
        menuBar.setObjectName("menuBar")

        menuFile = menuBar.addMenu("ファイル(&F)")
        menuFile.setObjectName("menuFile")
        self.actionExit = QAction("終了", self)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.triggered.connect(self.close)
        menuFile.addAction(self.actionExit)

        menuMeasurement = menuBar.addMenu("測定(&M)")
        menuMeasurement.setObjectName("menuMeasurement")
        self.actionDeviceSettings = QAction("機器設定...(&D)", self)
        self.actionDeviceSettings.setObjectName("actionDeviceSettings")
        self.actionDeviceSettings.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        self.actionDeviceSettings.triggered.connect(self._open_device_settings_dialog)
        menuMeasurement.addAction(self.actionDeviceSettings)

        menuHelp = menuBar.addMenu("ヘルプ(&H)")
        menuHelp.setObjectName("menuHelp")
        self.actionAbout = QAction("バージョン情報", self)
        self.actionAbout.setObjectName("actionAbout")
        self.actionAbout.triggered.connect(self._show_about)
        menuHelp.addAction(self.actionAbout)

    def _show_about(self) -> None:
        """簡易なバージョン情報ダイアログを表示する。"""
        QtWidgets.QMessageBox.information(
            self,
            "バージョン情報",
            "太陽電池と発光素子計測プログラム\nOPVJVL",
        )
