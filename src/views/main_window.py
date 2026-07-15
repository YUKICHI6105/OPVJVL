"""アプリケーションのメインウィンドウ(View層)。

`resources/ui/main_window.ui`(Qt Designer作成済み、現在は未使用。参照や
将来の巻き戻しのため残置)はロードせず、B-6-2節のオブジェクト階層に従い
Pythonコードでウィジェットツリーを直接構築する。
OPV/JVL/2ch活用の各タブをコードで構築して挿入する。
業務ロジックは持たない(B-6-1節: ハイブリッド方式)。
"""
from __future__ import annotations

import os

from qtcompat import QAction, QShortcut, Qt, QtCore, QtGui, QtWidgets, enum_value, qt_exec
from utils import device_settings, persistence, win32_utils
from utils.logger import get_logger
from utils.paths import get_log_dir
from views import plot_buffer, theme
from views.data_viewer import DataViewerDialog, parse_measurement_csv
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
        # 「データを開く」で開いたDataViewerDialogをGCされないよう保持するリスト
        # (review.md項目5。複数同時に開けるため、closeされたものだけ都度取り除く)。
        self._data_viewer_dialogs: list = []

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
        """終了時に実行中の測定を安全停止し、測定パラメータをsettings.jsonへ保存する。

        review.md項目3: Ctrl+C(SIGINT)によるウィンドウクローズを含め、測定実行中に
        アプリが終了しようとした場合でも、各ViewModelへ協調的中断を要求してから
        (workerの``finally``節で機器の出力OFF等が走る猶予として``wait()``する)
        終了処理(設定保存)を進める。
        """
        self._stop_running_measurements()
        try:
            persistence.save_settings(self._collect_measurement_settings())
            logger.info("測定パラメータをsettings.jsonへ保存しました。")
        except Exception as e:  # noqa: BLE001 - 保存失敗で終了を妨げない
            logger.error("終了時の設定保存に失敗しました: %s", e)
        super().closeEvent(event)

    def _stop_running_measurements(self) -> None:
        """実行中の全測定(OPV/JVL/2chモードA/B)へ中断要求を出し、停止を待つ。

        MVVMの依存方向(ViewModelはViewを参照しない)は維持したまま、
        View(MainWindow)側からViewModelの公開APIを呼ぶ形で安全停止を行う。
        """
        try:
            self.opv_tab.viewModel.stop_and_wait()
            self.jvl_tab.viewModel.stop_and_wait()
            self.dual_channel_tab.viewModel.stop_and_wait_a()
            self.dual_channel_tab.viewModel.stop_and_wait_b()
        except Exception as e:  # noqa: BLE001 - 停止処理の失敗で終了を妨げない
            logger.error("終了時の測定安全停止に失敗しました: %s", e)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        """centralWidgetを水平QSplitterにし、レイアウトをメインウィンドウ直下へ移動する。

        review.md指摘#1: 従来は各タブ内部(views/tab_layout.pyのbuild_split_tab())で
        「左=設定+ログ / 右=グラフ」の分割を行っていたが、タブを跨いだ左右幅の
        統一・ログ領域の最大化がタブごとの実装に依存してしまっていた。
        本メソッドでは分割をメインウィンドウ直下へ引き上げ、
          左カラム: 共通保存設定パネル(上) → mainTabWidget(中、内容ぶんの高さ) →
                    「ログ」グループ(下、残り余白を全て使用)
          右カラム: displayStack(各タブの表示パネルをQStackedWidgetで切替)
        という構成にする。mainTabWidgetのcurrentChangedでログ用/表示用スタックの
        インデックスを同期する(2ch活用モードはモードA/B用のスタックをタブ側が持ち、
        dual_modeSelectComboで同期する)。
        """
        centralSplitter = QtWidgets.QSplitter(objectName="centralSplitter")
        centralSplitter.setOrientation(enum_value(Qt, "Horizontal"))
        centralSplitter.setChildrenCollapsible(False)

        # ------------------------------------------------------------------
        # 左カラム: 共通保存設定パネル + mainTabWidget + ログ(残り余白を全て使用)
        # ------------------------------------------------------------------
        leftColumnWidget = QtWidgets.QWidget(objectName="leftColumnWidget")
        leftColumnLayout = QtWidgets.QVBoxLayout(leftColumnWidget)
        leftColumnLayout.setObjectName("leftColumnLayout")
        leftColumnLayout.setContentsMargins(4, 4, 4, 4)
        leftColumnWidget.setMinimumWidth(theme.SETTINGS_PANEL_MIN_WIDTH)
        leftColumnWidget.setMaximumWidth(theme.SETTINGS_PANEL_MAX_WIDTH)

        self.sharedSaveGroupBox = self._build_shared_save_group()
        leftColumnLayout.addWidget(self.sharedSaveGroupBox, 0)

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
        # mainTabWidgetはstretch=0で「内容ぶんの高さ」に留め、
        # 残りの縦スペースは全て下の「ログ」グループへ回す。
        leftColumnLayout.addWidget(self.mainTabWidget, 0)

        logGroupBox = QtWidgets.QGroupBox("ログ", objectName="logGroupBox")
        logGroupLayout = QtWidgets.QVBoxLayout(logGroupBox)
        logGroupLayout.setObjectName("logGroupLayout")
        self.logStack = QtWidgets.QStackedWidget(objectName="logStack")
        self.logStack.addWidget(self.opv_tab.log_widget())
        self.logStack.addWidget(self.jvl_tab.log_widget())
        self.logStack.addWidget(self.dual_channel_tab.log_widget())
        logGroupLayout.addWidget(self.logStack)
        leftColumnLayout.addWidget(logGroupBox, 1)

        centralSplitter.addWidget(leftColumnWidget)

        # ------------------------------------------------------------------
        # 右カラム: 各タブの表示パネル(進捗バー+グラフ)をQStackedWidgetで切替
        # ------------------------------------------------------------------
        self.displayStack = QtWidgets.QStackedWidget(objectName="displayStack")
        self.displayStack.addWidget(self.opv_tab.display_panel())
        self.displayStack.addWidget(self.jvl_tab.display_panel())
        self.displayStack.addWidget(self.dual_channel_tab.display_panel())
        centralSplitter.addWidget(self.displayStack)

        # 左カラムは伸縮時も横幅を保持し、右カラム(表示パネル)にのみ
        # 余剰スペースを割り当てる。
        centralSplitter.setStretchFactor(0, 0)
        centralSplitter.setStretchFactor(1, 1)
        centralSplitter.setSizes(theme.DISPLAY_PANEL_STRETCH_SIZES)

        # タブ切り替えでログ/表示スタックのインデックスを同期する。
        self.mainTabWidget.currentChanged.connect(self._on_main_tab_changed)
        # 共通保存設定パネルは、「2ch活用モードタブ」が表示中かつその内部モードが
        # 「モードB」の間だけ非表示にする(モードBはチャンネルA/Bそれぞれ別の素子を
        # 計測するため、保存先・サンプル名をタブ内でローカルに個別入力する運用のため)。
        # OPV/JVLタブ表示中や2ch活用モードAの間は、常に共通保存設定パネルを表示する。
        self.dual_channel_tab.dual_modeSelectCombo.currentIndexChanged.connect(
            self._update_shared_panel_visibility
        )
        self._on_main_tab_changed(self.mainTabWidget.currentIndex())

        self.setCentralWidget(centralSplitter)

    def _on_main_tab_changed(self, index: int) -> None:
        """mainTabWidgetのタブ切り替えに、ログ用/表示用スタックのインデックスを同期する。"""
        self.logStack.setCurrentIndex(index)
        self.displayStack.setCurrentIndex(index)
        self._update_shared_panel_visibility()

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

        OPVモードとJVLモードは同一のソースメータを使うため、機器設定ダイアログでは
        opvjvl_* キーに統合されている。両タブへ同じ値を渡す(タブ側のAPIは
        従来通り個別のため、ここで同一値を配る形で橋渡しする)。
        2ch活用モードA/Bも同様にdual_*キーに統合されており、
        apply_device_settings_mode_a / _mode_b の両方へ同一値を渡す。
        """
        opvjvl_device_type = _DEVICE_TYPE_BY_INDEX.get(
            settings.get("opvjvl_device_type_index", 0), "keithley2400"
        )
        opvjvl_connection = settings.get("opvjvl_connection", "")
        opvjvl_channel = settings.get("opvjvl_channel", "smua")
        opvjvl_use_mock = self.developer_mode and settings.get("opvjvl_use_mock", False)

        self.opv_tab.apply_device_settings(
            opvjvl_device_type,
            opvjvl_connection,
            opvjvl_channel,
            opvjvl_use_mock,
        )
        self.jvl_tab.apply_device_settings(
            opvjvl_device_type,
            opvjvl_connection,
            settings.get("opvjvl_bm9_port", ""),
            opvjvl_channel,
            opvjvl_use_mock,
        )

        dual_connection = settings.get("dual_connection", "")
        dual_bm9_port = settings.get("dual_bm9_port", "")
        dual_use_mock = self.developer_mode and settings.get("dual_use_mock", False)

        self.dual_channel_tab.apply_device_settings_mode_a(
            dual_connection,
            dual_bm9_port,
            dual_use_mock,
        )
        self.dual_channel_tab.apply_device_settings_mode_b(
            dual_connection,
            dual_bm9_port,
            dual_use_mock,
        )

    def _open_device_settings_dialog(self) -> None:
        dialog = DeviceSettingsDialog(self, self.device_settings, self.developer_mode)
        accepted = enum_value(QtWidgets.QDialog, "Accepted")
        if qt_exec(dialog) == accepted:
            self.device_settings = dialog.get_settings()
            self._apply_device_settings(self.device_settings)
            device_settings.save_device_settings(self.device_settings)
            # 機器選択(2400/2612B)の変更でOPV/JVL⇔2ch群のクロスロック要否が
            # 変わるため、排他ロックを再計算する。
            self._update_start_button_locks()

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
        self._update_start_button_locks()

    def _on_any_running_changed(self, key: str, running: bool) -> None:
        self._running_flags[key] = running
        any_running = any(self._running_flags.values())
        self.actionDeviceSettings.setEnabled(not any_running)

        # 測定中はWindowsのスリープ・ディスプレイ消灯を防止し、
        # 全測定の終了・中断で通常状態へ復帰する(EQEのprevent_sleep踏襲)
        if any_running != getattr(self, "_sleep_prevented", False):
            self._sleep_prevented = any_running
            win32_utils.prevent_sleep(any_running)

        self._update_start_button_locks()

    def _update_start_button_locks(self) -> None:
        """機器共有に基づく測定の排他制御(項目3・4)。

        OPV⇔JVLは常に相互排他(同一機器共有)。2chモードA⇔Bも常に相互排他
        (同一2612B共有)。OPV/JVLの機器選択が2612Bの場合のみ、OPV/JVL群⇔
        2ch群も相互排他になる(2400選択時は物理的に別機器のため並行実行可)。

        タブ側の``_on_running_changed``系ハンドラが自タブ終了時に
        ``setEnabled(True)``した直後でも、後で実行される本メソッドが
        4ボタン全ての有効/無効を計算し直して上書きする(結線順序に依存しない)。
        """
        flags = self._running_flags
        opv_running = flags.get("opv", False)
        jvl_running = flags.get("jvl", False)
        dual_a_running = flags.get("dual_a", False)
        dual_b_running = flags.get("dual_b", False)

        opvjvl_running = opv_running or jvl_running
        dual_running = dual_a_running or dual_b_running
        # OPV/JVLの機器選択が2612B(index==1)の場合のみ、2ch群(同一2612B共有)との
        # 相互排他を追加する。2400選択時(index==0)は物理的に別機器のため対象外。
        cross_lock_enabled = self.device_settings.get("opvjvl_device_type_index", 0) == 1

        opv_locked_by = None
        if jvl_running:
            opv_locked_by = "JVLモード測定中のため開始できません(機器共有)"
        elif cross_lock_enabled and dual_running:
            opv_locked_by = "2ch活用モード測定中のため開始できません(機器共有)"

        jvl_locked_by = None
        if opv_running:
            jvl_locked_by = "OPVモード測定中のため開始できません(機器共有)"
        elif cross_lock_enabled and dual_running:
            jvl_locked_by = "2ch活用モード測定中のため開始できません(機器共有)"

        dual_a_locked_by = None
        if dual_b_running:
            dual_a_locked_by = "2ch活用モードB測定中のため開始できません(機器共有)"
        elif cross_lock_enabled and opvjvl_running:
            dual_a_locked_by = "OPV/JVLモード測定中のため開始できません(機器共有)"

        dual_b_locked_by = None
        if dual_a_running:
            dual_b_locked_by = "2ch活用モードA測定中のため開始できません(機器共有)"
        elif cross_lock_enabled and opvjvl_running:
            dual_b_locked_by = "OPV/JVLモード測定中のため開始できません(機器共有)"

        self._apply_start_button_lock(self.opv_tab.opv_startButton, opv_running, opv_locked_by)
        self._apply_start_button_lock(self.jvl_tab.jvl_startButton, jvl_running, jvl_locked_by)
        self._apply_start_button_lock(
            self.dual_channel_tab.dual_a_startButton, dual_a_running, dual_a_locked_by
        )
        self._apply_start_button_lock(
            self.dual_channel_tab.dual_b_startButton, dual_b_running, dual_b_locked_by
        )

    @staticmethod
    def _apply_start_button_lock(button, running: bool, locked_reason) -> None:
        """開始ボタン1つ分のsetEnabled/tooltipを計算し直す。"""
        button.setEnabled(not running and locked_reason is None)
        button.setToolTip(locked_reason or "")

    def _on_browse_shared_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.sharedSaveDirEdit.setText(directory)

    def _build_menu_bar(self) -> None:
        """メニューバーを構築する(review.md項目4: ファイル/設定/ヘルプの3メニュー構成)。

        従来の「測定」「表示」メニューは廃止し、「機器設定...」「グラフ表示の設定...」を
        新設の「設定」メニューへ統合、「ファイル」メニューに「データを開く...」(項目5)を
        追加、「ヘルプ」メニューから「バージョン情報」を削除した。
        測定開始(F5)/測定中断(Esc)はメニュー項目としては廃止するが、QShortcutとして
        引き続き有効にする(``_install_run_shortcuts``)。
        """
        menuBar = self.menuBar()
        menuBar.setObjectName("menuBar")

        # --- ファイル メニュー ---
        menuFile = menuBar.addMenu("ファイル(&F)")
        menuFile.setObjectName("menuFile")

        self.actionSaveResultAs = QAction("測定データを別名保存...(&S)", self)
        self.actionSaveResultAs.setObjectName("actionSaveResultAs")
        self.actionSaveResultAs.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        self.actionSaveResultAs.setStatusTip("表示中のタブの最後の測定結果を任意のファイル名で保存します")
        self.actionSaveResultAs.triggered.connect(self._on_menu_save_result_as)
        menuFile.addAction(self.actionSaveResultAs)

        self.actionOpenData = QAction("データを開く...(&O)", self)
        self.actionOpenData.setObjectName("actionOpenData")
        self.actionOpenData.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        self.actionOpenData.setStatusTip("測定CSVファイルを開いてグラフ表示します")
        self.actionOpenData.triggered.connect(self._on_menu_open_data)
        menuFile.addAction(self.actionOpenData)

        menuFile.addSeparator()

        self.actionExit = QAction("終了(&X)", self)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.actionExit.setStatusTip("アプリケーションを終了します")
        self.actionExit.triggered.connect(self.close)
        menuFile.addAction(self.actionExit)

        # --- 設定 メニュー(旧「測定」の機器設定 + 旧「表示」のグラフ表示設定) ---
        menuSettings = menuBar.addMenu("設定(&S)")
        menuSettings.setObjectName("menuSettings")

        # objectName(actionDeviceSettings)は既存の排他制御(_on_any_running_changed)
        # から参照されているため維持する。表示テキストのみ「測定の設定...」へ変更。
        self.actionDeviceSettings = QAction("測定の設定...(&M)", self)
        self.actionDeviceSettings.setObjectName("actionDeviceSettings")
        self.actionDeviceSettings.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        self.actionDeviceSettings.setStatusTip("接続先(COM/VISAポート)等の機器設定を行います")
        self.actionDeviceSettings.triggered.connect(self._open_device_settings_dialog)
        menuSettings.addAction(self.actionDeviceSettings)

        self.actionDisplaySettings = QAction("表示の設定...(&D)", self)
        self.actionDisplaySettings.setObjectName("actionDisplaySettings")
        self.actionDisplaySettings.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        self.actionDisplaySettings.setStatusTip("グラフの線幅・シンボル・フォント等を設定します")
        self.actionDisplaySettings.triggered.connect(self._open_display_settings_dialog)
        menuSettings.addAction(self.actionDisplaySettings)

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

        # 測定開始(F5)/測定中断(Esc)はメニュー項目としては廃止し、
        # QShortcutとしてのみ提供する(開始/中断ボタンのラベルにも明記済み)。
        self._install_run_shortcuts()

    def _install_run_shortcuts(self) -> None:
        """F5(測定開始)/Esc(測定中断)のQShortcutをMainWindowへ登録する(review.md項目4)。

        メニュー項目としては廃止したが、ショートカット自体は維持する要件のため、
        既存の``_on_menu_start_measurement``/``_on_menu_stop_measurement``
        (表示中タブの開始/中断ボタンをclickする実装)をそのまま流用する。
        参照はGC防止のためインスタンス変数へ保持する。
        """
        self._startShortcut = QShortcut(QtGui.QKeySequence("F5"), self)
        self._startShortcut.setObjectName("startMeasurementShortcut")
        self._startShortcut.activated.connect(self._on_menu_start_measurement)

        self._stopShortcut = QShortcut(QtGui.QKeySequence("Esc"), self)
        self._stopShortcut.setObjectName("stopMeasurementShortcut")
        self._stopShortcut.activated.connect(self._on_menu_stop_measurement)

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

    def _on_menu_save_result_as(self) -> None:
        """ファイルメニュー/Ctrl+Sから、表示中タブの最後の測定結果を別名保存する。

        2ch活用モードタブはモードA/Bいずれが表示中かをタブ側で判定する。
        """
        current = self.mainTabWidget.currentWidget()
        current.save_last_result_as(self)

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

    def _on_menu_open_data(self) -> None:
        """ファイルメニュー/Ctrl+Oから測定CSVを開き、専用ビューアで表示する(review.md項目5)。

        パース結果が0点の場合はビューアを開かずエラーダイアログを表示する。
        開いたダイアログは``self._data_viewer_dialogs``で参照保持し(GC防止)、
        複数同時に開けるようにする。
        """
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "データを開く", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        voltages, _currents, _luminances = parse_measurement_csv(path)
        if not voltages:
            QtWidgets.QMessageBox.warning(
                self,
                "エラー",
                f"CSVファイルから有効な測定データを読み込めませんでした。\nパス: {path}",
            )
            return

        dialog = DataViewerDialog(path, self)
        self._data_viewer_dialogs.append(dialog)
        dialog.finished.connect(lambda _result, d=dialog: self._on_data_viewer_closed(d))
        dialog.show()

    def _on_data_viewer_closed(self, dialog) -> None:
        """DataViewerDialogが閉じられたら参照リストから取り除き、GCを許可する。"""
        if dialog in self._data_viewer_dialogs:
            self._data_viewer_dialogs.remove(dialog)

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
