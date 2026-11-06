"""2ch活用モード(モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測)タブのView。

B-6-2節「2ch活用モードタブ（dual_channel_tab.ui）」のウィジェットツリー・
objectName命名規則に厳密に従い、Pythonコードでウィジェットツリーを構築する。
"""
from __future__ import annotations

import os
from typing import Optional

import pyqtgraph as pg

from qtcompat import QtWidgets
from models.measurement.config import ChannelConfig, DualAConfig, DualBConfig
from models.measurement.csv_writer import (
    dual_a_csv_filename,
    dual_b_csv_filename,
    save_points_csv,
    validate_dual_b_filenames,
)
from viewmodels.dual_channel_viewmodel import DualChannelViewModel
from views import tab_layout
from views.luminance_confirm import confirm_luminance_use
from views.notify_sound import dismiss_completion_alarm, play_completion_sound
from views.plot_buffer import (
    DualAxisPlotBuffer,
    PlotBuffer,
    install_auto_range_menu,
    set_iv_axis_labels,
    setup_luminance_axis,
)
from views.progress_bar import set_measurement_completed
from views.save_confirm import confirm_overwrite, ensure_save_dir
from views.tab_layout import make_double_spin as _make_double_spin
from views.widgets.no_scroll_combobox import NoScrollComboBox

DEVICE_MODE_ITEMS = ["太陽電池", "発光素子"]
_DEVICE_TYPE_2612B = "keithley2612b"


class DualChannelTab(QtWidgets.QWidget):
    """2ch活用モードタブ(DualChannelTabForm相当)。"""

    def __init__(
        self,
        parent=None,
        viewModel: DualChannelViewModel = None,
        sample_name_edit: QtWidgets.QLineEdit = None,
        save_dir_edit: QtWidgets.QLineEdit = None,
    ):
        super().__init__(parent)
        self.setObjectName("DualChannelTabForm")
        self._updating_exclusivity = False

        self._plot_buffer_a = None
        self._plot_buffer_b_cha = None
        self._plot_buffer_b_chb = None

        # 最後に完了/中断した測定結果(「別名保存」用)
        self._last_result_a = None  # (points, device_mode, use_luminance)
        self._last_result_b = None  # {"A": (points, device_mode, use_luminance), "B": (...)}
        self._active_forward_point_count_a = None
        self._last_forward_point_count_a = None
        self._active_mode_a_use_luminance = False
        self._active_forward_point_count_b = {"A": None, "B": None}
        self._last_forward_point_count_b = {"A": None, "B": None}
        self._active_mode_b_config: Optional[DualBConfig] = None
        self._mode_b_reserved_channels = {"A": False, "B": False}
        self._mode_b_stopped_channels = {"A": False, "B": False}

        # 機器設定(接続先・輝度計ポート)は「機器設定」ダイアログ(MainWindowのメニュー
        # バー経由)から `apply_device_settings_mode_a`/`_mode_b` によって注入される。
        # タブ内には入力欄を持たない。
        self._dual_a_connection = ""
        self._dual_a_bm9_port = ""
        self._dual_a_use_mock = False
        self._dual_b_connection = ""
        self._dual_b_bm9_port = ""
        self._dual_b_use_mock = False

        # 接触確認の実行中フラグ(本測定用running_changedと接触確認用ボタンの
        # enabled制御を分離するため、Viewが自身の状態として保持する)
        self._contact_check_running_a = False
        self._contact_check_running_b = False
        # モードBの接触確認は物理SMU1台をchA/chBで共有するため、現在動作中の
        # チャンネル("chA"/"chB")をViewで追跡し、ボタン表示・enabled制御に使う。
        self._contact_check_active_prefix_b: Optional[str] = None

        # 共通保存設定パネル(MainWindow側)のウィジェット参照。
        # モードAのサンプル名/保存先にのみ流用する。
        # モードBは保存先・チャンネルA/Bのサンプル名を全てタブ内にローカル生成する
        # (チャンネルA/Bで別々の素子を同時計測するため、共通パネルとは独立させる)。
        self._external_sample_name_edit = sample_name_edit
        self._external_save_dir_edit = save_dir_edit

        self._build_ui()

        # ViewModelの保持と結線(結線はView側の責務。__init__から一度だけ行う)
        self.viewModel = viewModel or DualChannelViewModel()
        self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """ViewModelとの結線を行う。__init__から一度だけ呼ぶこと(二重結線防止)。"""
        self.dual_a_startButton.clicked.connect(self._on_mode_a_start_clicked)
        self.dual_a_stopButton.clicked.connect(self._on_mode_a_stop_clicked)
        self.dual_b_startButton.clicked.connect(lambda: self._on_mode_b_start_clicked())
        self.dual_chA_startButton.clicked.connect(lambda: self._on_mode_b_channel_button_clicked("A"))
        self.dual_chB_startButton.clicked.connect(lambda: self._on_mode_b_channel_button_clicked("B"))
        self.dual_b_stopButton.clicked.connect(self._on_mode_b_stop_clicked)

        # ViewModelからのシグナル購読
        # モードA
        self.viewModel.running_changed_a.connect(self._on_running_changed_a)
        self.viewModel.progress_a.connect(self.dual_a_progressBar.setValue)
        self.viewModel.point_measured_a.connect(self._on_point_measured_a)
        self.viewModel.log_appended_a.connect(self._append_log_a)
        self.viewModel.error_appended_a.connect(self._append_error_log_a)
        self.viewModel.error_a.connect(self._show_warning_a)
        self.viewModel.finished_ok_a.connect(self._on_finished_ok_a)

        # モードB
        self.viewModel.running_changed_b.connect(self._on_running_changed_b)
        self.viewModel.progress_b.connect(self.dual_b_progressBar.setValue)
        self.viewModel.point_measured_b_cha.connect(self._on_point_measured_b_cha)
        self.viewModel.point_measured_b_chb.connect(self._on_point_measured_b_chb)
        self.viewModel.log_appended_b.connect(self._append_log_b)
        self.viewModel.error_appended_b.connect(self._append_error_log_b)
        self.viewModel.error_b.connect(self._show_warning_b)
        self.viewModel.finished_ok_b.connect(self._on_finished_ok_b)

        # 接触確認 モードA
        self.dual_a_contactCheckButton.clicked.connect(self._on_mode_a_contact_check_clicked)
        self.viewModel.contact_check_running_changed_a.connect(
            self._on_contact_check_running_changed_a
        )
        self.viewModel.contact_check_reading_a.connect(self._on_contact_check_reading_a)

        # 接触確認 モードB(チャンネルA/B)
        self.dual_chA_contactCheckButton.clicked.connect(
            lambda: self._on_channel_contact_check_clicked("chA")
        )
        self.dual_chB_contactCheckButton.clicked.connect(
            lambda: self._on_channel_contact_check_clicked("chB")
        )
        self.viewModel.contact_check_running_changed_b.connect(
            self._on_contact_check_running_changed_b
        )
        self.viewModel.contact_check_reading_b.connect(self._on_contact_check_reading_b)

    # ------------------------------------------------------------------
    # UI構築(ルート)
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        dual_rootLayout = QtWidgets.QVBoxLayout(self)
        dual_rootLayout.setObjectName("dual_rootLayout")
        # 2ch活用モードだけは「タブ直下のルート → モードページ」と入れ子が1段深く、
        # 既定余白(9px)がモードページ側の余白(4px)へ上乗せされるため、設定欄の
        # 実効幅がOPV/JVLタブより18px狭くなっていた。ここでは余白を持たせず、
        # 幅の基準をモードページ側(build_settings_column)へ一本化する。
        dual_rootLayout.setContentsMargins(0, 0, 0, 0)

        dual_modeSelectRow = QtWidgets.QHBoxLayout()
        dual_modeSelectRow.setObjectName("dual_modeSelectRow")
        dual_modeSelectRow.addWidget(QtWidgets.QLabel("動作モード:"))

        self.dual_modeSelectCombo = QtWidgets.QComboBox(objectName="dual_modeSelectCombo")
        self.dual_modeSelectCombo.addItems(
            ["モードA: 2ch低ノイズ計測", "モードB: 2素子同時計測"]
        )
        dual_modeSelectRow.addWidget(self.dual_modeSelectCombo)
        dual_modeSelectRow.addStretch()
        dual_rootLayout.addLayout(dual_modeSelectRow)

        self.dual_modeStack = QtWidgets.QStackedWidget(objectName="dual_modeStack")
        self.dual_modeStack.addWidget(self._build_mode_a_page())
        self.dual_modeStack.addWidget(self._build_mode_b_page())
        dual_rootLayout.addWidget(self.dual_modeStack)

        # 表示パネル(進捗+グラフ)とログは、モードA/Bをそれぞれ
        # QStackedWidgetへ積み、MainWindow右カラム(displayStack)/
        # 左カラムの「ログ」グループ(logStack)へ渡す(review.md指摘#1)。
        self._displayStack = QtWidgets.QStackedWidget(objectName="dual_displayStack")
        self._displayStack.addWidget(self._dual_a_display_panel)
        self._displayStack.addWidget(self._dual_b_display_panel)

        self._logStack = QtWidgets.QStackedWidget(objectName="dual_logStack")
        self._logStack.addWidget(self.dual_a_logTextEdit)
        self._logStack.addWidget(self.dual_b_logTextEdit)

        self.dual_modeSelectCombo.currentIndexChanged.connect(self.dual_modeStack.setCurrentIndex)
        self.dual_modeSelectCombo.currentIndexChanged.connect(self._displayStack.setCurrentIndex)
        self.dual_modeSelectCombo.currentIndexChanged.connect(self._logStack.setCurrentIndex)

    def display_panel(self) -> QtWidgets.QWidget:
        """MainWindow右カラム(displayStack)に積む表示パネル。

        モードA/Bそれぞれの表示パネル(進捗バー+グラフ)を収めた
        QStackedWidgetを返し、``dual_modeSelectCombo``に同期させる。
        """
        return self._displayStack

    def log_widget(self) -> QtWidgets.QWidget:
        """MainWindow左カラムの「ログ」グループ(logStack)に積むログ表示。

        モードA/Bそれぞれのログを収めたQStackedWidgetを返し、
        ``dual_modeSelectCombo``に同期させる。
        """
        return self._logStack

    # ------------------------------------------------------------------
    # モードA
    # ------------------------------------------------------------------
    def _build_mode_a_page(self) -> QtWidgets.QWidget:
        """モードAページ。共通レイアウトビルダー(views/tab_layout.py)で構築する。

        左右分割はメインウィンドウ直下のQSplitterが担うため(review.md指摘#1)、
        このページ自身は設定カラムの中身だけを持つ。表示パネル/ログは
        ``_build_ui()``でQStackedWidgetへ積まれ、MainWindowへ渡される。
        """
        dual_modeAPage = QtWidgets.QWidget(objectName="dual_modeAPage")

        settings_groups = self._build_mode_a_settings_groups()

        # 表示パネル側のウィジェット
        self.dual_a_progressBar = QtWidgets.QProgressBar(objectName="dual_a_progressBar")
        self.dual_a_progressBar.setValue(0)
        self.dual_a_plotWidget = pg.PlotWidget()
        self.dual_a_plotWidget.setObjectName("dual_a_plotWidget")
        set_iv_axis_labels(self.dual_a_plotWidget)
        install_auto_range_menu(self.dual_a_plotWidget)
        self.dual_a_logTextEdit = QtWidgets.QTextEdit(objectName="dual_a_logTextEdit")
        self.dual_a_logTextEdit.setReadOnly(True)

        tab_layout.build_settings_column(dual_modeAPage, "dual_a", settings_groups=settings_groups)
        self._dual_a_display_panel = tab_layout.build_display_panel(
            "dual_a", self.dual_a_plotWidget, self.dual_a_progressBar
        )
        return dual_modeAPage

    def _build_mode_a_settings_groups(self) -> list:
        """モードAの設定カラムに積むグループ群(測定設定/保存・実行)を構築する。"""
        # 測定設定(接続・計測対象・掃引・タイミング・輝度計をまとめて1つのGroupBoxに集約)
        dual_a_measurementGroupBox = QtWidgets.QGroupBox(
            "測定設定", objectName="dual_a_measurementGroupBox"
        )
        dual_a_measurementFormLayout = QtWidgets.QFormLayout(dual_a_measurementGroupBox)

        self.dual_a_deviceModeCombo = NoScrollComboBox(objectName="dual_a_deviceModeCombo")
        self.dual_a_deviceModeCombo.addItems(DEVICE_MODE_ITEMS)
        self.dual_a_hysteresisCheckBox = QtWidgets.QCheckBox(
            "ヒステリシス測定", objectName="dual_a_hysteresisCheckBox"
        )
        self.dual_a_hysteresisCheckBox.setToolTip("往復掃引")
        dual_a_deviceModeRow = QtWidgets.QHBoxLayout()
        dual_a_deviceModeRow.setObjectName("dual_a_deviceModeRow")
        dual_a_deviceModeRow.addWidget(self.dual_a_deviceModeCombo)
        dual_a_deviceModeRow.addWidget(self.dual_a_hysteresisCheckBox)
        dual_a_measurementFormLayout.addRow("計測対象:", dual_a_deviceModeRow)

        self.dual_a_vMinSpin = _make_double_spin("dual_a_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, "")
        self.dual_a_vMaxSpin = _make_double_spin("dual_a_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, "")
        self.dual_a_vStepSpin = _make_double_spin("dual_a_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, "")
        dual_a_measurementFormLayout.addRow(tab_layout.labeled_fields("dual_a_sweepRow", [
            ("開始 [V]", self.dual_a_vMinSpin), ("終了 [V]", self.dual_a_vMaxSpin),
            ("ステップ [V]", self.dual_a_vStepSpin),
        ]))

        self.dual_a_iterationSpin = tab_layout.make_iteration_spin("dual_a_iterationSpin")
        # NPLC上限25.0はKeithley2612Bの仕様上限。初期値25.0はベースコード
        # (bases/keithley2600/OPV_measurement_ver2.py)の積分時間0.5秒
        # (50Hzで25NPLC相当)に合わせる。
        self.dual_a_nplcSpin = _make_double_spin("dual_a_nplcSpin", 0.01, 25.0, 2, 0.1, 25.0)
        self.dual_a_delaySpin = _make_double_spin("dual_a_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, "")
        self.dual_a_complianceSpin = _make_double_spin(
            "dual_a_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02, ""
        )
        dual_a_measurementFormLayout.addRow(tab_layout.labeled_fields("dual_a_timingRow", [
            ("各電圧の回数", self.dual_a_iterationSpin), ("NPLC", self.dual_a_nplcSpin),
            ("遅延 [s]", self.dual_a_delaySpin), ("電流上限 [A]", self.dual_a_complianceSpin),
        ]))

        # 保存・実行
        dual_a_saveRunGroupBox = QtWidgets.QGroupBox("保存・実行", objectName="dual_a_saveRunGroupBox")
        dual_a_saveRunFormLayout = QtWidgets.QFormLayout(dual_a_saveRunGroupBox)

        if self._external_sample_name_edit is not None:
            # 共通保存設定パネル(MainWindow側)のウィジェットをそのまま参照する。
            # タブ内には重複表示しない。
            self.dual_a_sampleNameEdit = self._external_sample_name_edit
        else:
            self.dual_a_sampleNameEdit = QtWidgets.QLineEdit(objectName="dual_a_sampleNameEdit")
            dual_a_saveRunFormLayout.addRow("サンプル名:", self.dual_a_sampleNameEdit)

        if self._external_save_dir_edit is not None:
            self.dual_a_saveDirEdit = self._external_save_dir_edit
        else:
            self.dual_a_saveDirEdit = QtWidgets.QLineEdit(objectName="dual_a_saveDirEdit")
            self.dual_a_browseSaveDirButton = QtWidgets.QPushButton(
                "参照...", objectName="dual_a_browseSaveDirButton"
            )
            self.dual_a_browseSaveDirButton.clicked.connect(self._on_browse_mode_a_save_dir)
            dual_a_saveDirRow = QtWidgets.QHBoxLayout()
            dual_a_saveDirRow.setObjectName("dual_a_saveDirRow")
            dual_a_saveDirRow.addWidget(self.dual_a_saveDirEdit)
            dual_a_saveDirRow.addWidget(self.dual_a_browseSaveDirButton)
            dual_a_saveRunFormLayout.addRow("保存先:", dual_a_saveDirRow)

        dual_a_saveRunFormLayout.addRow(tab_layout.filename_preview(
            "dual_a", self.dual_a_sampleNameEdit,
            lambda name: dual_a_csv_filename(name, self.dual_a_deviceModeCombo.currentText()),
            self.dual_a_deviceModeCombo,
        ))
        dual_a_runRow = QtWidgets.QHBoxLayout()
        dual_a_runRow.setObjectName("dual_a_runRow")
        # ショートカット(F5/Esc)をボタンのラベルに明記する(review.md項目4)。
        self.dual_a_startButton = QtWidgets.QPushButton("測定開始 (F5)", objectName="dual_a_startButton")
        self.dual_a_stopButton = QtWidgets.QPushButton("中断 (Esc)", objectName="dual_a_stopButton")
        self.dual_a_stopButton.setEnabled(False)
        dual_a_runRow.addWidget(self.dual_a_startButton)
        dual_a_runRow.addWidget(self.dual_a_stopButton)
        dual_a_saveRunFormLayout.addRow(dual_a_runRow)

        # 接触確認(deviceModeに応じてOPV式/JVL式を自動切替。JVL式は電流閾値到達後
        # その電圧を維持し続け、停止ボタンで止めるまで保持する。v_maxは素子保護の
        # ための安全上限電圧)
        self.dual_a_contactCheckThresholdSpin = _make_double_spin(
            "dual_a_contactCheckThresholdSpin", 0.0001, 1.0, 4, 0.0001, 0.001, "A"
        )
        self.dual_a_contactCheckVMaxSpin = _make_double_spin(
            "dual_a_contactCheckVMaxSpin", 0.1, 20.0, 2, 0.1, 5.0, "V"
        )
        self.dual_a_contactCheckButton = QtWidgets.QPushButton(
            "接触確認", objectName="dual_a_contactCheckButton"
        )
        self.dual_a_contactCheckReadingLabel = QtWidgets.QLabel(
            "電流: -", objectName="dual_a_contactCheckReadingLabel"
        )
        dual_a_contactCheckRow = QtWidgets.QHBoxLayout()
        dual_a_contactCheckRow.setObjectName("dual_a_contactCheckRow")
        dual_a_contactCheckRow.addWidget(QtWidgets.QLabel("電流閾値[A]:"))
        dual_a_contactCheckRow.addWidget(self.dual_a_contactCheckThresholdSpin)
        dual_a_contactCheckRow.addWidget(QtWidgets.QLabel("最大電圧[V]:"))
        dual_a_contactCheckRow.addWidget(self.dual_a_contactCheckVMaxSpin)
        dual_a_saveRunFormLayout.addRow("接触確認:", dual_a_contactCheckRow)
        dual_a_saveRunFormLayout.addRow(self.dual_a_contactCheckButton)
        dual_a_saveRunFormLayout.addRow(self.dual_a_contactCheckReadingLabel)

        return [dual_a_measurementGroupBox, dual_a_saveRunGroupBox]

    # ------------------------------------------------------------------
    # モードB
    # ------------------------------------------------------------------
    def _build_mode_b_page(self) -> QtWidgets.QWidget:
        """モードBページ。共通レイアウトビルダー(views/tab_layout.py)で
        他タブ・モードAと同一のコードパスで設定カラムを構築する
        (左右分割はメインウィンドウ直下のQSplitterが担う。review.md指摘#1)。
        共通保存先、チャンネルA/Bの設定と個別開始、同時開始・中断を配置する。
        """
        dual_modeBPage = QtWidgets.QWidget(objectName="dual_modeBPage")

        settings_groups = self._build_mode_b_settings_groups()

        # 表示パネル側のウィジェット(チャンネルA/Bのプロットタブ)
        self.dual_b_progressBar = QtWidgets.QProgressBar(objectName="dual_b_progressBar")
        self.dual_b_progressBar.setValue(0)
        self.dual_b_displayTabWidget = QtWidgets.QTabWidget(objectName="dual_b_displayTabWidget")
        self.dual_chA_plotWidget = pg.PlotWidget()
        self.dual_chA_plotWidget.setObjectName("dual_chA_plotWidget")
        set_iv_axis_labels(self.dual_chA_plotWidget)
        install_auto_range_menu(self.dual_chA_plotWidget)
        self.dual_b_displayTabWidget.addTab(self.dual_chA_plotWidget, "チャンネルA")
        self.dual_chB_plotWidget = pg.PlotWidget()
        self.dual_chB_plotWidget.setObjectName("dual_chB_plotWidget")
        set_iv_axis_labels(self.dual_chB_plotWidget)
        install_auto_range_menu(self.dual_chB_plotWidget)
        self.dual_b_displayTabWidget.addTab(self.dual_chB_plotWidget, "チャンネルB")
        self.dual_b_logTextEdit = QtWidgets.QTextEdit(objectName="dual_b_logTextEdit")
        self.dual_b_logTextEdit.setReadOnly(True)

        tab_layout.build_settings_column(
            dual_modeBPage, "dual_b", settings_groups=settings_groups[:-1], footer=settings_groups[-1]
        )
        self._dual_b_display_panel = tab_layout.build_display_panel(
            "dual_b", self.dual_b_displayTabWidget, self.dual_b_progressBar
        )
        return dual_modeBPage

    def _build_mode_b_settings_groups(self) -> list:
        """モードBの設定カラムに積むグループ群(共通設定/チャンネルA/B/実行)を構築する。"""
        # 共通設定(保存先をまとめて1つのGroupBoxに集約。接続先/BM9ポートは
        # 「機器設定」ダイアログへ移動済み)
        dual_b_commonGroupBox = QtWidgets.QGroupBox(
            "保存先（チャンネルA・B共通）", objectName="dual_b_connectionGroupBox"
        )
        dual_b_commonFormLayout = QtWidgets.QFormLayout(dual_b_commonGroupBox)
        # モードBの保存先はチャンネルA/B共通の1つの保存先だが、共通保存設定パネル
        # (MainWindow側)とは独立させ、常にタブ内にローカル生成する。
        self.dual_b_saveDirEdit = QtWidgets.QLineEdit(objectName="dual_b_saveDirEdit")
        self.dual_b_browseSaveDirButton = QtWidgets.QPushButton(
            "参照...", objectName="dual_b_browseSaveDirButton"
        )
        self.dual_b_browseSaveDirButton.clicked.connect(self._on_browse_mode_b_save_dir)
        dual_b_saveDirRow = QtWidgets.QHBoxLayout()
        dual_b_saveDirRow.setObjectName("dual_b_saveDirRow")
        dual_b_saveDirRow.addWidget(self.dual_b_saveDirEdit)
        dual_b_saveDirRow.addWidget(self.dual_b_browseSaveDirButton)
        dual_b_commonFormLayout.addRow("保存先:", dual_b_saveDirRow)

        # チャンネルA/B(設定カラムの幅に収まるよう、横並びではなく縦に積む)
        (
            self.dual_chA_startButton,
            self.dual_chA_deviceModeCombo,
            self.dual_chA_vMinSpin,
            self.dual_chA_vMaxSpin,
            self.dual_chA_vStepSpin,
            self.dual_chA_iterationSpin,
            self.dual_chA_nplcSpin,
            self.dual_chA_delaySpin,
            self.dual_chA_complianceSpin,
            self.dual_chA_sampleNameEdit,
            self.dual_chA_hysteresisCheckBox,
            self.dual_chA_contactCheckThresholdSpin,
            self.dual_chA_contactCheckVMaxSpin,
            self.dual_chA_contactCheckButton,
            self.dual_chA_contactCheckReadingLabel,
            channelAGroupBox,
        ) = self._build_channel_group("chA", "チャンネルA (smua)")
        (
            self.dual_chB_startButton,
            self.dual_chB_deviceModeCombo,
            self.dual_chB_vMinSpin,
            self.dual_chB_vMaxSpin,
            self.dual_chB_vStepSpin,
            self.dual_chB_iterationSpin,
            self.dual_chB_nplcSpin,
            self.dual_chB_delaySpin,
            self.dual_chB_complianceSpin,
            self.dual_chB_sampleNameEdit,
            self.dual_chB_hysteresisCheckBox,
            self.dual_chB_contactCheckThresholdSpin,
            self.dual_chB_contactCheckVMaxSpin,
            self.dual_chB_contactCheckButton,
            self.dual_chB_contactCheckReadingLabel,
            channelBGroupBox,
        ) = self._build_channel_group("chB", "チャンネルB (smub)")

        # モードB発光素子排他制御の配線
        self.dual_chA_deviceModeCombo.currentTextChanged.connect(
            lambda text: self._on_channel_device_mode_changed("A", text)
        )
        self.dual_chB_deviceModeCombo.currentTextChanged.connect(
            lambda text: self._on_channel_device_mode_changed("B", text)
        )

        # 実行
        dual_b_runGroupBox = QtWidgets.QGroupBox("実行", objectName="dual_b_runGroupBox")
        dual_b_runLayout = QtWidgets.QVBoxLayout(dual_b_runGroupBox)
        dual_b_buttonRow = QtWidgets.QHBoxLayout()
        dual_b_buttonRow.setObjectName("dual_b_buttonRow")
        # ショートカット(F5/Esc)をボタンのラベルに明記する(review.md項目4)。
        self.dual_b_startButton = QtWidgets.QPushButton("A・B同時測定開始 (F5)", objectName="dual_b_startButton")
        self.dual_b_stopButton = QtWidgets.QPushButton("中断 (Esc)", objectName="dual_b_stopButton")
        self.dual_b_stopButton.setEnabled(False)
        dual_b_buttonRow.addWidget(self.dual_b_startButton)
        dual_b_buttonRow.addWidget(self.dual_b_stopButton)
        dual_b_runLayout.addLayout(dual_b_buttonRow)

        return [dual_b_commonGroupBox, channelAGroupBox, channelBGroupBox, dual_b_runGroupBox]

    def plot_widgets(self) -> list:
        """このタブが保有する全プロットウィジェット(グラフ表示設定の適用対象)。"""
        return [self.dual_a_plotWidget, self.dual_chA_plotWidget, self.dual_chB_plotWidget]

    def _build_channel_group(self, ch_prefix: str, title: str):
        """チャンネルA/B共通の設定グループを構築する(`dual_chA_*`/`dual_chB_*`)。"""
        group_box_object_name = "dual_channelAGroupBox" if ch_prefix == "chA" else "dual_channelBGroupBox"
        group_box = QtWidgets.QGroupBox(title, objectName=group_box_object_name)
        form_layout = QtWidgets.QFormLayout(group_box)
        form_layout.setObjectName(f"dual_{ch_prefix}_formLayout")
        start_button = QtWidgets.QPushButton(
            "このチャネルを測定開始", objectName=f"dual_{ch_prefix}_startButton"
        )
        contact_check_button = QtWidgets.QPushButton(
            "接触確認", objectName=f"dual_{ch_prefix}_contactCheckButton"
        )
        action_row = QtWidgets.QHBoxLayout()
        action_row.setObjectName(f"dual_{ch_prefix}_actionRow")
        action_row.addWidget(start_button)
        action_row.addWidget(contact_check_button)

        device_mode_combo = NoScrollComboBox(objectName=f"dual_{ch_prefix}_deviceModeCombo")
        device_mode_combo.addItems(DEVICE_MODE_ITEMS)
        hysteresis_checkbox = QtWidgets.QCheckBox(
            "ヒステリシス測定", objectName=f"dual_{ch_prefix}_hysteresisCheckBox"
        )
        hysteresis_checkbox.setToolTip("往復掃引")
        device_mode_row = QtWidgets.QHBoxLayout()
        device_mode_row.setObjectName(f"dual_{ch_prefix}_deviceModeRow")
        device_mode_row.addWidget(device_mode_combo)
        device_mode_row.addWidget(hysteresis_checkbox)
        form_layout.addRow("計測対象:", device_mode_row)

        v_min_spin = _make_double_spin(f"dual_{ch_prefix}_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, "")
        v_max_spin = _make_double_spin(f"dual_{ch_prefix}_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, "")
        v_step_spin = _make_double_spin(f"dual_{ch_prefix}_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, "")
        form_layout.addRow(tab_layout.labeled_fields(f"dual_{ch_prefix}_sweepRow", [
            ("開始 [V]", v_min_spin), ("終了 [V]", v_max_spin), ("ステップ [V]", v_step_spin),
        ]))

        iteration_spin = tab_layout.make_iteration_spin(f"dual_{ch_prefix}_iterationSpin")

        # NPLC上限25.0はKeithley2612Bの仕様上限(初期値は1.0のまま)。
        nplc_spin = _make_double_spin(f"dual_{ch_prefix}_nplcSpin", 0.01, 25.0, 2, 0.1, 1.0)
        delay_spin = _make_double_spin(f"dual_{ch_prefix}_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, "")
        compliance_spin = _make_double_spin(
            f"dual_{ch_prefix}_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02, ""
        )
        form_layout.addRow(tab_layout.labeled_fields(f"dual_{ch_prefix}_timingRow", [
            ("各電圧の回数", iteration_spin), ("NPLC", nplc_spin),
            ("遅延 [s]", delay_spin), ("電流上限 [A]", compliance_spin),
        ]))

        sample_name_edit = QtWidgets.QLineEdit(objectName=f"dual_{ch_prefix}_sampleNameEdit")
        form_layout.addRow("サンプル名:", sample_name_edit)
        form_layout.addRow(tab_layout.filename_preview(
            f"dual_{ch_prefix}", sample_name_edit,
            lambda name: dual_b_csv_filename(name, ch_prefix[-1], device_mode_combo.currentText()),
            device_mode_combo,
        ))

        # 接触確認(チャンネルのdevice_modeに応じてOPV式/JVL式を自動切替。
        # モードBの物理SMUは1台共有のため、チャンネルA/Bの接触確認は
        # ViewModel側で相互排他される)
        contact_check_threshold_spin = _make_double_spin(
            f"dual_{ch_prefix}_contactCheckThresholdSpin", 0.0001, 1.0, 4, 0.0001, 0.001, "A"
        )
        contact_check_v_max_spin = _make_double_spin(
            f"dual_{ch_prefix}_contactCheckVMaxSpin", 0.1, 20.0, 2, 0.1, 5.0, "V"
        )
        contact_check_reading_label = QtWidgets.QLabel(
            "電流: -", objectName=f"dual_{ch_prefix}_contactCheckReadingLabel"
        )
        contact_check_row = QtWidgets.QHBoxLayout()
        contact_check_row.setObjectName(f"dual_{ch_prefix}_contactCheckRow")
        contact_check_row.addWidget(QtWidgets.QLabel("電流閾値[A]:"))
        contact_check_row.addWidget(contact_check_threshold_spin)
        contact_check_row.addWidget(QtWidgets.QLabel("最大電圧[V]:"))
        contact_check_row.addWidget(contact_check_v_max_spin)
        form_layout.addRow("接触確認:", contact_check_row)
        form_layout.addRow(action_row)
        form_layout.addRow(contact_check_reading_label)

        return (
            start_button,
            device_mode_combo,
            v_min_spin,
            v_max_spin,
            v_step_spin,
            iteration_spin,
            nplc_spin,
            delay_spin,
            compliance_spin,
            sample_name_edit,
            hysteresis_checkbox,
            contact_check_threshold_spin,
            contact_check_v_max_spin,
            contact_check_button,
            contact_check_reading_label,
            group_box,
        )

    # ------------------------------------------------------------------
    # UI値からのConfig構築
    # ------------------------------------------------------------------
    def apply_device_settings_mode_a(
        self, connection: str, bm9_port: str, use_mock: bool = False
    ) -> None:
        """機器設定ダイアログ(``DeviceSettingsDialog``)で確定した設定値をモードAへ適用する。"""
        self._dual_a_connection = connection
        self._dual_a_bm9_port = bm9_port
        self._dual_a_use_mock = use_mock

    def apply_device_settings_mode_b(
        self, connection: str, bm9_port: str, use_mock: bool = False
    ) -> None:
        """機器設定ダイアログ(``DeviceSettingsDialog``)で確定した設定値をモードBへ適用する。"""
        self._dual_b_connection = connection
        self._dual_b_bm9_port = bm9_port
        self._dual_b_use_mock = use_mock

    def _build_mode_a_config(self) -> DualAConfig:
        device_mode = self.dual_a_deviceModeCombo.currentText()
        use_luminance = device_mode == "発光素子"
        bm9_port = self._dual_a_bm9_port if use_luminance else None
        return DualAConfig(
            device_type=_DEVICE_TYPE_2612B,
            connection=self._dual_a_connection,
            use_mock=self._dual_a_use_mock,
            v_min=self.dual_a_vMinSpin.value(),
            v_max=self.dual_a_vMaxSpin.value(),
            v_step=self.dual_a_vStepSpin.value(),
            iteration=self.dual_a_iterationSpin.value(),
            compliance_current=self.dual_a_complianceSpin.value(),
            nplc=self.dual_a_nplcSpin.value(),
            delay_time=self.dual_a_delaySpin.value(),
            sample_name=self.dual_a_sampleNameEdit.text().strip() or "sample",
            save_dir=self.dual_a_saveDirEdit.text().strip() or ".",
            device_mode=device_mode,
            use_luminance=use_luminance,
            bm9_port=bm9_port,
            hysteresis=self.dual_a_hysteresisCheckBox.isChecked(),
        )

    def _build_channel_config(self, prefix: str) -> ChannelConfig:
        device_mode_combo = getattr(self, f"dual_{prefix}_deviceModeCombo")
        v_min_spin = getattr(self, f"dual_{prefix}_vMinSpin")
        v_max_spin = getattr(self, f"dual_{prefix}_vMaxSpin")
        v_step_spin = getattr(self, f"dual_{prefix}_vStepSpin")
        iteration_spin = getattr(self, f"dual_{prefix}_iterationSpin")
        nplc_spin = getattr(self, f"dual_{prefix}_nplcSpin")
        delay_spin = getattr(self, f"dual_{prefix}_delaySpin")
        compliance_spin = getattr(self, f"dual_{prefix}_complianceSpin")
        sample_name_edit = getattr(self, f"dual_{prefix}_sampleNameEdit")
        hysteresis_checkbox = getattr(self, f"dual_{prefix}_hysteresisCheckBox")

        return ChannelConfig(
            enabled=True,
            device_mode=device_mode_combo.currentText(),
            v_min=v_min_spin.value(),
            v_max=v_max_spin.value(),
            v_step=v_step_spin.value(),
            iteration=iteration_spin.value(),
            nplc=nplc_spin.value(),
            delay_time=delay_spin.value(),
            compliance_current=compliance_spin.value(),
            sample_name=sample_name_edit.text().strip() or "sample",
            hysteresis=hysteresis_checkbox.isChecked(),
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_mode_a_start_clicked(self) -> None:
        if not ensure_save_dir(self, self.dual_a_saveDirEdit):
            return
        config = self._build_mode_a_config()
        planned_path = os.path.join(
            config.save_dir, dual_a_csv_filename(config.sample_name, config.device_mode)
        )
        if not confirm_overwrite(self, [planned_path]):
            return
        if config.use_luminance:
            decision = confirm_luminance_use(self, config.bm9_port, config.use_mock)
            if decision is None:
                return
            if not decision:
                config.use_luminance = False
                config.bm9_port = None
                self._append_log_a("BM9を使用せず、電流のみ測定します。")
        self._active_mode_a_use_luminance = config.use_luminance
        total_points = len(config.build_voltage_list())
        dismiss_completion_alarm()
        set_measurement_completed(self.dual_a_progressBar, False)
        self.dual_a_progressBar.setMaximum(max(total_points, 1))
        self.dual_a_progressBar.setValue(0)
        reverse_from_index = config.forward_point_count() if config.hysteresis else None
        self._active_forward_point_count_a = reverse_from_index
        if config.use_luminance:
            setup_luminance_axis(self.dual_a_plotWidget)
            self._plot_buffer_a = DualAxisPlotBuffer(
                self.dual_a_plotWidget, reverse_from_index=reverse_from_index
            )
        else:
            self._plot_buffer_a = PlotBuffer(
                self.dual_a_plotWidget, reverse_from_index=reverse_from_index
            )
        self.viewModel.start_mode_a(config)

    def _on_mode_a_stop_clicked(self) -> None:
        if self._contact_check_running_a:
            self.viewModel.stop_contact_check_a()
        else:
            self.viewModel.stop_mode_a()

    def _on_mode_a_contact_check_clicked(self) -> None:
        if self._contact_check_running_a:
            self.viewModel.stop_contact_check_a()
        else:
            self.viewModel.start_contact_check_a(
                self.dual_a_deviceModeCombo.currentText(),
                self._dual_a_connection,
                self._dual_a_use_mock,
                self.dual_a_complianceSpin.value(),
                self.dual_a_nplcSpin.value(),
                self.dual_a_contactCheckThresholdSpin.value(),
                self.dual_a_contactCheckVMaxSpin.value(),
            )

    def _on_mode_b_channel_button_clicked(self, channel: str) -> None:
        if self.viewModel.mode_b_is_running() and self._mode_b_reserved_channels[channel]:
            if not self._mode_b_stopped_channels[channel] and self.viewModel.stop_mode_b_channel(channel):
                self._mode_b_stopped_channels[channel] = True
                self._update_mode_b_channel_buttons(True)
            return
        self._on_mode_b_start_clicked(channel)

    def _on_mode_b_start_clicked(self, channel: Optional[str] = None) -> None:
        """指定チャネルのみ、またはA・Bを同時に測定する。"""
        joining = self.viewModel.mode_b_is_running()
        if joining and channel is None:
            return
        if not ensure_save_dir(self, self.dual_b_saveDirEdit):
            return
        chan_a = self._build_channel_config("chA")
        chan_b = self._build_channel_config("chB")
        chan_a.enabled = channel in (None, "A")
        chan_b.enabled = channel in (None, "B")
        try:
            validate_dual_b_filenames(chan_a, chan_b, self.dual_b_saveDirEdit.text().strip() or ".")
        except ValueError as exc:
            self._show_warning_b(str(exc))
            return

        led_channel = None
        if chan_a.enabled and chan_a.device_mode == "発光素子":
            led_channel = "A"
        elif chan_b.enabled and chan_b.device_mode == "発光素子":
            led_channel = "B"

        wants_bm9 = led_channel is not None
        bm9_port = self._dual_b_bm9_port if wants_bm9 else None

        save_dir = self.dual_b_saveDirEdit.text().strip() or "."
        planned_paths = []
        if chan_a.enabled:
            planned_paths.append(
                os.path.join(save_dir, dual_b_csv_filename(chan_a.sample_name, "A", chan_a.device_mode))
            )
        if chan_b.enabled:
            planned_paths.append(
                os.path.join(save_dir, dual_b_csv_filename(chan_b.sample_name, "B", chan_b.device_mode))
            )
        if not confirm_overwrite(self, planned_paths):
            return
        if wants_bm9:
            decision = confirm_luminance_use(self, bm9_port, self._dual_b_use_mock)
            if decision is None:
                return
            if not decision:
                bm9_port = None
                self._append_log_b("BM9を使用せず、電流のみ測定します。")

        config = DualBConfig(
            connection=self._dual_b_connection,
            use_mock=self._dual_b_use_mock,
            channel_a=chan_a,
            channel_b=chan_b,
            bm9_port=bm9_port,
            save_dir=save_dir,
        )
        if joining:
            if not self.viewModel.start_mode_b(config):
                return
            self._mode_b_reserved_channels[channel] = True
            self._update_mode_b_channel_buttons(True)
            selected_channel = chan_a if channel == "A" else chan_b
            self.dual_b_progressBar.setMaximum(
                self.dual_b_progressBar.maximum()
                + len(selected_channel.build_voltage_list())
            )
            self._active_forward_point_count_b[channel] = (
                selected_channel.forward_point_count() if selected_channel.hysteresis else None
            )
            selected_plot = self.dual_chA_plotWidget if channel == "A" else self.dual_chB_plotWidget
            use_luminance = bool(bm9_port)
            reverse_index = self._active_forward_point_count_b[channel]
            if use_luminance:
                setup_luminance_axis(selected_plot)
                buffer = DualAxisPlotBuffer(selected_plot, reverse_from_index=reverse_index)
            else:
                buffer = PlotBuffer(selected_plot, reverse_from_index=reverse_index)
            if channel == "A":
                self._plot_buffer_b_cha = buffer
            else:
                self._plot_buffer_b_chb = buffer
            return
        self._active_mode_b_config = config
        self._mode_b_reserved_channels = {"A": chan_a.enabled, "B": chan_b.enabled}
        self._mode_b_stopped_channels = {"A": False, "B": False}

        va_len = len(chan_a.build_voltage_list()) if chan_a.enabled else 0
        vb_len = len(chan_b.build_voltage_list()) if chan_b.enabled else 0
        total_points = va_len + vb_len
        dismiss_completion_alarm()
        set_measurement_completed(self.dual_b_progressBar, False)
        self.dual_b_progressBar.setMaximum(max(total_points, 1))
        self.dual_b_progressBar.setValue(0)

        # review.md指摘#6: 発光素子計測かつBM9使用のチャンネルは輝度も描画する
        # (DualAxisPlotBuffer)。それ以外は電流のみのPlotBuffer。
        uses_luminance_a = led_channel == "A" and bool(bm9_port)
        uses_luminance_b = led_channel == "B" and bool(bm9_port)

        reverse_from_index_a = chan_a.forward_point_count() if chan_a.hysteresis else None
        reverse_from_index_b = chan_b.forward_point_count() if chan_b.hysteresis else None
        self._active_forward_point_count_b = {"A": reverse_from_index_a, "B": reverse_from_index_b}

        if chan_a.enabled and uses_luminance_a:
            setup_luminance_axis(self.dual_chA_plotWidget)
            self._plot_buffer_b_cha = DualAxisPlotBuffer(
                self.dual_chA_plotWidget, reverse_from_index=reverse_from_index_a
            )
        elif chan_a.enabled:
            self._plot_buffer_b_cha = PlotBuffer(
                self.dual_chA_plotWidget, reverse_from_index=reverse_from_index_a
            )
        else:
            self._plot_buffer_b_cha = None

        if chan_b.enabled and uses_luminance_b:
            setup_luminance_axis(self.dual_chB_plotWidget)
            self._plot_buffer_b_chb = DualAxisPlotBuffer(
                self.dual_chB_plotWidget, reverse_from_index=reverse_from_index_b
            )
        elif chan_b.enabled:
            self._plot_buffer_b_chb = PlotBuffer(
                self.dual_chB_plotWidget, reverse_from_index=reverse_from_index_b
            )
        else:
            self._plot_buffer_b_chb = None

        self.viewModel.start_mode_b(config)

    def _on_mode_b_stop_clicked(self) -> None:
        if self._contact_check_running_b:
            self.viewModel.stop_contact_check_b()
        else:
            self.viewModel.stop_mode_b()

    def _on_channel_contact_check_clicked(self, prefix: str) -> None:
        """モードB: チャンネルA/B共通の接触確認ボタンハンドラ(`prefix`は"chA"/"chB")。"""
        if self._contact_check_active_prefix_b == prefix:
            self.viewModel.stop_contact_check_b()
            return
        if self._contact_check_active_prefix_b is not None:
            return  # 他方のチャンネルが接触確認中(同一スロットのため多重起動しない)

        target_channel = "smua" if prefix == "chA" else "smub"
        device_mode_combo = getattr(self, f"dual_{prefix}_deviceModeCombo")
        nplc_spin = getattr(self, f"dual_{prefix}_nplcSpin")
        compliance_spin = getattr(self, f"dual_{prefix}_complianceSpin")
        threshold_spin = getattr(self, f"dual_{prefix}_contactCheckThresholdSpin")
        v_max_spin = getattr(self, f"dual_{prefix}_contactCheckVMaxSpin")
        self._contact_check_active_prefix_b = prefix
        self.viewModel.start_contact_check_b(
            target_channel,
            device_mode_combo.currentText(),
            self._dual_b_connection,
            self._dual_b_use_mock,
            compliance_spin.value(),
            nplc_spin.value(),
            threshold_spin.value(),
            v_max_spin.value(),
        )

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ (モードA)
    # ------------------------------------------------------------------
    def _on_running_changed_a(self, running: bool) -> None:
        self.dual_a_startButton.setEnabled(not running)
        self.dual_a_stopButton.setEnabled(running)
        self.dual_a_deviceModeCombo.setEnabled(not running)
        self.dual_a_hysteresisCheckBox.setEnabled(not running)
        self.dual_modeSelectCombo.setEnabled(not running)
        # running_changed_aは本測定と接触確認の両方から発火される共有シグナル
        # (MainWindow側のクロスタブ排他ロックが流用するため)。接触確認ボタン
        # 自体は自身の状態(_contact_check_running_a)でのみ制御する。
        if not self._contact_check_running_a:
            self.dual_a_contactCheckButton.setEnabled(not running)

    def _on_progress_changed_a(self, current: int, total: int) -> None:
        self.dual_a_progressBar.setMaximum(max(total, 1))
        self.dual_a_progressBar.setValue(current)


    def _on_point_measured_a(self, point) -> None:
        if self._plot_buffer_a is None:
            return
        if isinstance(self._plot_buffer_a, DualAxisPlotBuffer):
            luminance = getattr(point, "luminance", None)
            self._plot_buffer_a.add_point(point.voltage, point.current, luminance)
        else:
            self._plot_buffer_a.add_point(point.voltage, point.current)

    def _append_log_a(self, message: str) -> None:
        self.dual_a_logTextEdit.append(message)

    def _append_error_log_a(self, message: str) -> None:
        self.dual_a_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning_a(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok_a(self, points: list, csv_path: str, aborted: bool) -> None:
        self._last_forward_point_count_a = self._active_forward_point_count_a
        self._last_result_a = (
            points, self.dual_a_deviceModeCombo.currentText(), self._active_mode_a_use_luminance
        )
        set_measurement_completed(self.dual_a_progressBar, not aborted)
        play_completion_sound("aborted" if aborted else "success", self)

    def _on_contact_check_running_changed_a(self, running: bool) -> None:
        self._contact_check_running_a = running
        self.dual_a_contactCheckButton.setText("接触確認を停止" if running else "接触確認")
        self.dual_a_contactCheckButton.setEnabled(True)
        if not running:
            self.dual_a_contactCheckReadingLabel.setText("電流: -")
        self.dual_a_startButton.setEnabled(not running)

    def _on_contact_check_reading_a(self, voltage: float, current: float) -> None:
        self.dual_a_contactCheckReadingLabel.setText(f"電流: {current:.6e} A (V={voltage:.3f})")

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ (モードB)
    # ------------------------------------------------------------------
    def _on_running_changed_b(self, running: bool) -> None:
        self.dual_b_startButton.setEnabled(not running)
        active = self._active_mode_b_config if running else None
        self._update_mode_b_channel_buttons(running)
        self.dual_b_stopButton.setEnabled(running)
        self.dual_modeSelectCombo.setEnabled(not running)
        self.dual_b_saveDirEdit.setEnabled(not running)

        # チャンネル設定コントロールの制御
        for prefix in ["chA", "chB"]:
            channel = "A" if prefix == "chA" else "B"
            editable = not running or bool(active and not self._mode_b_reserved_channels[channel])
            for field in ("deviceModeCombo", "vMinSpin", "vMaxSpin", "vStepSpin",
                          "iterationSpin", "nplcSpin", "delaySpin", "complianceSpin",
                          "sampleNameEdit", "hysteresisCheckBox"):
                getattr(self, f"dual_{prefix}_{field}").setEnabled(editable)

        # running_changed_bは本測定と接触確認(chA/chB共有スロット)の両方から
        # 発火される共有シグナル。接触確認ボタン自体は自身の状態
        # (_contact_check_running_b)でのみ制御する。
        if not self._contact_check_running_b:
            self.dual_chA_contactCheckButton.setEnabled(not running)
            self.dual_chB_contactCheckButton.setEnabled(not running)
        if not running:
            self._active_mode_b_config = None
            self._mode_b_reserved_channels = {"A": False, "B": False}
            self._mode_b_stopped_channels = {"A": False, "B": False}

    def _update_mode_b_channel_buttons(self, running: bool) -> None:
        for channel, button in (("A", self.dual_chA_startButton),
                                ("B", self.dual_chB_startButton)):
            reserved = running and self._mode_b_reserved_channels[channel]
            stopped = reserved and self._mode_b_stopped_channels[channel]
            button.setText("中断済み" if stopped else "このチャネルを中断" if reserved
                           else "このチャネルを測定開始")
            button.setEnabled(not stopped and (
                reserved or not running or self._active_mode_b_config is not None
            ))

    def _on_progress_changed_b(self, current: int, total: int) -> None:
        self.dual_b_progressBar.setMaximum(max(total, 1))
        self.dual_b_progressBar.setValue(current)


    def _on_point_measured_b_cha(self, point) -> None:
        if self._plot_buffer_b_cha is None:
            return
        if isinstance(self._plot_buffer_b_cha, DualAxisPlotBuffer):
            luminance = getattr(point, "luminance", None)
            self._plot_buffer_b_cha.add_point(point.voltage, point.current, luminance)
        else:
            self._plot_buffer_b_cha.add_point(point.voltage, point.current)

    def _on_point_measured_b_chb(self, point) -> None:
        if self._plot_buffer_b_chb is None:
            return
        if isinstance(self._plot_buffer_b_chb, DualAxisPlotBuffer):
            luminance = getattr(point, "luminance", None)
            self._plot_buffer_b_chb.add_point(point.voltage, point.current, luminance)
        else:
            self._plot_buffer_b_chb.add_point(point.voltage, point.current)

    def _append_log_b(self, message: str) -> None:
        self.dual_b_logTextEdit.append(message)

    def _append_error_log_b(self, message: str) -> None:
        self.dual_b_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning_b(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok_b(
        self, points: list, csv_path_a: str, csv_path_b: str, aborted: bool
    ) -> None:
        self._last_forward_point_count_b = self._active_forward_point_count_b.copy()
        set_measurement_completed(self.dual_b_progressBar, not aborted)
        play_completion_sound("aborted" if aborted else "success", self)
        chan_a_points = [p for p in points if p.channel == "A"]
        chan_b_points = [p for p in points if p.channel == "B"]

        active = self._active_mode_b_config
        device_mode_a = active.channel_a.device_mode if active else self.dual_chA_deviceModeCombo.currentText()
        device_mode_b = active.channel_b.device_mode if active else self.dual_chB_deviceModeCombo.currentText()
        led_channel = None
        if active and active.channel_a.enabled and device_mode_a == "発光素子":
            led_channel = "A"
        elif active and active.channel_b.enabled and device_mode_b == "発光素子":
            led_channel = "B"
        use_luminance_a = led_channel == "A" and bool(active.bm9_port)
        use_luminance_b = led_channel == "B" and bool(active.bm9_port)
        self._last_result_b = {
            "A": (chan_a_points, device_mode_a, use_luminance_a),
            "B": (chan_b_points, device_mode_b, use_luminance_b),
        }

    def _on_contact_check_running_changed_b(self, running: bool) -> None:
        self._contact_check_running_b = running
        active_prefix = self._contact_check_active_prefix_b
        for prefix in ("chA", "chB"):
            button = getattr(self, f"dual_{prefix}_contactCheckButton")
            if running and prefix == active_prefix:
                button.setText("接触確認を停止")
                button.setEnabled(True)
            else:
                button.setText("接触確認")
                # 動作中は非アクティブ側を無効化し、同一スロットの多重起動を防ぐ
                button.setEnabled(not running)
        if not running:
            self.dual_chA_contactCheckReadingLabel.setText("電流: -")
            self.dual_chB_contactCheckReadingLabel.setText("電流: -")
            self._contact_check_active_prefix_b = None
        self.dual_b_startButton.setEnabled(not running)
        self.dual_chA_startButton.setEnabled(not running)
        self.dual_chB_startButton.setEnabled(not running)

    def _on_contact_check_reading_b(self, channel: str, voltage: float, current: float) -> None:
        prefix = "chA" if channel == "A" else "chB"
        label = getattr(self, f"dual_{prefix}_contactCheckReadingLabel")
        label.setText(f"電流: {current:.6e} A (V={voltage:.3f})")

    # ------------------------------------------------------------------
    # 設定の永続化(MainWindowが起動時restore/終了時saveに使用)
    # ------------------------------------------------------------------
    def persistent_widgets(self) -> dict:
        """永続化対象の設定キーとウィジェットの対応表を返す。

        キー名は ``utils.persistence.MEASUREMENT_SETTINGS_DEFAULTS`` と一致させる。
        """
        widgets = {
            # モードA
            "dual_a_device_mode": self.dual_a_deviceModeCombo,
            "dual_a_v_min": self.dual_a_vMinSpin,
            "dual_a_v_max": self.dual_a_vMaxSpin,
            "dual_a_v_step": self.dual_a_vStepSpin,
            "dual_a_iteration": self.dual_a_iterationSpin,
            "dual_a_nplc": self.dual_a_nplcSpin,
            "dual_a_delay": self.dual_a_delaySpin,
            "dual_a_compliance": self.dual_a_complianceSpin,
            "dual_a_hysteresis": self.dual_a_hysteresisCheckBox,
            "dual_a_contact_check_threshold": self.dual_a_contactCheckThresholdSpin,
            "dual_a_contact_check_v_max": self.dual_a_contactCheckVMaxSpin,
            # モードB(共通)
            "dual_b_save_dir": self.dual_b_saveDirEdit,
        }
        for prefix in ("chA", "chB"):
            widgets.update({
                f"dual_{prefix}_device_mode": getattr(self, f"dual_{prefix}_deviceModeCombo"),
                f"dual_{prefix}_v_min": getattr(self, f"dual_{prefix}_vMinSpin"),
                f"dual_{prefix}_v_max": getattr(self, f"dual_{prefix}_vMaxSpin"),
                f"dual_{prefix}_v_step": getattr(self, f"dual_{prefix}_vStepSpin"),
                f"dual_{prefix}_iteration": getattr(self, f"dual_{prefix}_iterationSpin"),
                f"dual_{prefix}_nplc": getattr(self, f"dual_{prefix}_nplcSpin"),
                f"dual_{prefix}_delay": getattr(self, f"dual_{prefix}_delaySpin"),
                f"dual_{prefix}_compliance": getattr(self, f"dual_{prefix}_complianceSpin"),
                f"dual_{prefix}_sample_name": getattr(self, f"dual_{prefix}_sampleNameEdit"),
                f"dual_{prefix}_hysteresis": getattr(self, f"dual_{prefix}_hysteresisCheckBox"),
                f"dual_{prefix}_contact_check_threshold": getattr(
                    self, f"dual_{prefix}_contactCheckThresholdSpin"
                ),
                f"dual_{prefix}_contact_check_v_max": getattr(
                    self, f"dual_{prefix}_contactCheckVMaxSpin"
                ),
            })
        return widgets

    # ------------------------------------------------------------------
    # View内に閉じた表示制御
    # ------------------------------------------------------------------
    def _on_channel_device_mode_changed(self, changed_channel: str, text: str) -> None:
        """モードB: 発光素子モードを選択できるチャンネルを最大1つに制限する。"""
        if self._updating_exclusivity:
            return
        self._updating_exclusivity = True
        try:
            other_combo = (
                self.dual_chB_deviceModeCombo
                if changed_channel == "A"
                else self.dual_chA_deviceModeCombo
            )
            if text == "発光素子":
                if other_combo.currentText() == "発光素子":
                    other_combo.setCurrentText("太陽電池")
                self._set_combo_item_enabled(other_combo, "発光素子", False)
            else:
                self._set_combo_item_enabled(other_combo, "発光素子", True)
        finally:
            self._updating_exclusivity = False

    @staticmethod
    def _set_combo_item_enabled(combo: QtWidgets.QComboBox, text: str, enabled: bool) -> None:
        model = combo.model()
        index = combo.findText(text)
        if index >= 0:
            item = model.item(index)
            if item is not None:
                item.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 別名保存(ファイルメニュー「測定データを別名保存...」/Ctrl+S)
    # ------------------------------------------------------------------
    def save_last_result_as(self, parent=None) -> None:
        """表示中モード(モードA/B)の最後の測定結果を任意のファイル名でCSV保存する。

        モードBは表示中のチャンネルタブ(``dual_b_displayTabWidget``)の
        結果のみを保存対象とする(チャンネルA/Bは別々の素子のため)。
        """
        if self.dual_modeSelectCombo.currentIndex() == 0:
            self._save_mode_a_result_as(parent)
        else:
            self._save_mode_b_result_as(parent)

    def _save_mode_a_result_as(self, parent=None) -> None:
        if not self._last_result_a:
            QtWidgets.QMessageBox.information(
                parent or self, "情報", "保存できる測定結果がありません。"
            )
            return
        points, device_mode, include_luminance = self._last_result_a
        sample_name = self.dual_a_sampleNameEdit.text().strip() or "sample"
        save_dir = self.dual_a_saveDirEdit.text().strip() or "."
        default_path = os.path.join(save_dir, dual_a_csv_filename(sample_name, device_mode))
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            parent or self, "測定データを別名保存", default_path, "CSV Files (*.csv)"
        )
        if not path:
            return
        save_points_csv(points, path, include_luminance, self._last_forward_point_count_a)
        self._append_log_a(f"測定データを保存しました: {path}")

    def _save_mode_b_result_as(self, parent=None) -> None:
        channel = "A" if self.dual_b_displayTabWidget.currentIndex() == 0 else "B"
        prefix = "chA" if channel == "A" else "chB"
        result = self._last_result_b.get(channel) if self._last_result_b else None
        if not result or not result[0]:
            QtWidgets.QMessageBox.information(
                parent or self, "情報", "保存できる測定結果がありません。"
            )
            return
        points, device_mode, use_luminance = result
        sample_name_edit = getattr(self, f"dual_{prefix}_sampleNameEdit")
        sample_name = sample_name_edit.text().strip() or "sample"
        save_dir = self.dual_b_saveDirEdit.text().strip() or "."
        default_path = os.path.join(
            save_dir, dual_b_csv_filename(sample_name, channel, device_mode)
        )
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            parent or self, "測定データを別名保存", default_path, "CSV Files (*.csv)"
        )
        if not path:
            return
        save_points_csv(points, path, use_luminance, self._last_forward_point_count_b[channel])
        self._append_log_b(f"測定データを保存しました: {path}")

    def _on_browse_mode_a_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_a_saveDirEdit.setText(directory)

    def _on_browse_mode_b_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_b_saveDirEdit.setText(directory)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # 輝度用ViewBox(luminance_viewbox)を持つプロットのみ、右軸ViewBoxの
        # 位置をJVLタブと同様に同期する(review.md指摘#6)。
        for plot_widget in (self.dual_a_plotWidget, self.dual_chA_plotWidget, self.dual_chB_plotWidget):
            luminance_viewbox = getattr(plot_widget, "luminance_viewbox", None)
            if luminance_viewbox is not None:
                luminance_viewbox.setGeometry(plot_widget.getViewBox().sceneBoundingRect())
