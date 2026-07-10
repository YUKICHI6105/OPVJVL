"""2ch活用モード(モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測)タブのView。

B-6-2節「2ch活用モードタブ（dual_channel_tab.ui）」のウィジェットツリー・
objectName命名規則に厳密に従い、Pythonコードでウィジェットツリーを構築する。
"""
from __future__ import annotations

import pyqtgraph as pg

from qtcompat import Qt, QtWidgets, enum_value
from models.measurement.config import ChannelConfig, DualAConfig, DualBConfig
from viewmodels.dual_channel_viewmodel import DualChannelViewModel
from views.plot_buffer import PlotBuffer
from views.widgets.no_scroll_spinbox import NoScrollDoubleSpinBox, NoScrollSpinBox

DEVICE_MODE_ITEMS = ["太陽電池", "発光素子"]
_DEVICE_TYPE_2612B = "keithley2612b"


def _make_double_spin(
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    value: float,
    suffix: str = "",
) -> QtWidgets.QDoubleSpinBox:
    spin = NoScrollDoubleSpinBox(objectName=object_name)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    spin.setMaximumWidth(80)
    return spin


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

        # 機器設定(接続先・輝度計ポート)は「機器設定」ダイアログ(MainWindowのメニュー
        # バー経由)から `apply_device_settings_mode_a`/`_mode_b` によって注入される。
        # タブ内には入力欄を持たない。
        self._dual_a_connection = ""
        self._dual_a_bm9_port = ""
        self._dual_a_use_mock = False
        self._dual_b_connection = ""
        self._dual_b_bm9_port = ""
        self._dual_b_use_mock = False

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
        self.dual_b_startButton.clicked.connect(self._on_mode_b_start_clicked)
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

    # ------------------------------------------------------------------
    # UI構築(ルート)
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        dual_rootLayout = QtWidgets.QVBoxLayout(self)
        dual_rootLayout.setObjectName("dual_rootLayout")

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

        self.dual_modeSelectCombo.currentIndexChanged.connect(self.dual_modeStack.setCurrentIndex)

    # ------------------------------------------------------------------
    # モードA
    # ------------------------------------------------------------------
    def _build_mode_a_page(self) -> QtWidgets.QWidget:
        dual_modeAPage = QtWidgets.QWidget(objectName="dual_modeAPage")
        dual_a_pageLayout = QtWidgets.QVBoxLayout(dual_modeAPage)

        dual_a_splitter = QtWidgets.QSplitter(objectName="dual_a_splitter")
        dual_a_splitter.setOrientation(enum_value(Qt, "Horizontal"))
        dual_a_pageLayout.addWidget(dual_a_splitter)

        dual_a_splitter.addWidget(self._build_mode_a_settings_panel())
        dual_a_splitter.addWidget(self._build_mode_a_display_panel())

        return dual_modeAPage

    def _build_mode_a_settings_panel(self) -> QtWidgets.QScrollArea:
        dual_a_settingsScrollArea = QtWidgets.QScrollArea(objectName="dual_a_settingsScrollArea")
        dual_a_settingsScrollArea.setWidgetResizable(True)

        dual_a_settingsContainer = QtWidgets.QWidget(objectName="dual_a_settingsContainer")
        dual_a_settingsLayout = QtWidgets.QVBoxLayout(dual_a_settingsContainer)
        dual_a_settingsLayout.setObjectName("dual_a_settingsLayout")

        # 測定設定(接続・計測対象・掃引・タイミング・輝度計をまとめて1つのGroupBoxに集約)
        dual_a_measurementGroupBox = QtWidgets.QGroupBox(
            "測定設定", objectName="dual_a_measurementGroupBox"
        )
        dual_a_measurementFormLayout = QtWidgets.QFormLayout(dual_a_measurementGroupBox)

        self.dual_a_deviceModeCombo = QtWidgets.QComboBox(objectName="dual_a_deviceModeCombo")
        self.dual_a_deviceModeCombo.addItems(DEVICE_MODE_ITEMS)
        dual_a_measurementFormLayout.addRow("計測対象:", self.dual_a_deviceModeCombo)

        self.dual_a_vMinSpin = _make_double_spin("dual_a_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, "")
        self.dual_a_vMaxSpin = _make_double_spin("dual_a_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, "")
        self.dual_a_vStepSpin = _make_double_spin("dual_a_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, "")
        dual_a_sweepRow = QtWidgets.QHBoxLayout()
        dual_a_sweepRow.setObjectName("dual_a_sweepRow")
        dual_a_sweepRow.addWidget(self.dual_a_vMinSpin)
        dual_a_sweepRow.addWidget(self.dual_a_vMaxSpin)
        dual_a_sweepRow.addWidget(self.dual_a_vStepSpin)
        dual_a_measurementFormLayout.addRow("電圧掃引(Vmin/Vmax/Vstep):", dual_a_sweepRow)

        self.dual_a_iterationSpin = NoScrollSpinBox(objectName="dual_a_iterationSpin")
        self.dual_a_iterationSpin.setRange(1, 1000)
        self.dual_a_iterationSpin.setValue(3)
        self.dual_a_iterationSpin.setMaximumWidth(80)
        self.dual_a_nplcSpin = _make_double_spin("dual_a_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)
        dual_a_iterationNplcRow = QtWidgets.QHBoxLayout()
        dual_a_iterationNplcRow.setObjectName("dual_a_iterationNplcRow")
        dual_a_iterationNplcRow.addWidget(self.dual_a_iterationSpin)
        dual_a_iterationNplcRow.addWidget(self.dual_a_nplcSpin)
        dual_a_measurementFormLayout.addRow("繰り返し回数/積分時間(NPLC):", dual_a_iterationNplcRow)

        self.dual_a_delaySpin = _make_double_spin("dual_a_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, "")
        self.dual_a_complianceSpin = _make_double_spin(
            "dual_a_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02, ""
        )
        dual_a_delayComplianceRow = QtWidgets.QHBoxLayout()
        dual_a_delayComplianceRow.setObjectName("dual_a_delayComplianceRow")
        dual_a_delayComplianceRow.addWidget(self.dual_a_delaySpin)
        dual_a_delayComplianceRow.addWidget(self.dual_a_complianceSpin)
        dual_a_measurementFormLayout.addRow("遅延時間[s]/コンプライアンス電流[A]:", dual_a_delayComplianceRow)

        dual_a_settingsLayout.addWidget(dual_a_measurementGroupBox)

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

        dual_a_runRow = QtWidgets.QHBoxLayout()
        dual_a_runRow.setObjectName("dual_a_runRow")
        self.dual_a_startButton = QtWidgets.QPushButton("測定開始", objectName="dual_a_startButton")
        self.dual_a_stopButton = QtWidgets.QPushButton("中断", objectName="dual_a_stopButton")
        self.dual_a_stopButton.setEnabled(False)
        dual_a_runRow.addWidget(self.dual_a_startButton)
        dual_a_runRow.addWidget(self.dual_a_stopButton)
        dual_a_saveRunFormLayout.addRow(dual_a_runRow)

        dual_a_settingsLayout.addWidget(dual_a_saveRunGroupBox)

        dual_a_settingsLayout.addStretch()

        dual_a_settingsScrollArea.setWidget(dual_a_settingsContainer)

        return dual_a_settingsScrollArea

    def _build_mode_a_display_panel(self) -> QtWidgets.QWidget:
        dual_a_displayPanel = QtWidgets.QWidget(objectName="dual_a_displayPanel")
        dual_a_displayLayout = QtWidgets.QVBoxLayout(dual_a_displayPanel)
        dual_a_displayLayout.setObjectName("dual_a_displayLayout")

        self.dual_a_progressBar = QtWidgets.QProgressBar(objectName="dual_a_progressBar")
        dual_a_displayLayout.addWidget(self.dual_a_progressBar)

        self.dual_a_plotWidget = pg.PlotWidget()
        self.dual_a_plotWidget.setObjectName("dual_a_plotWidget")
        dual_a_displayLayout.addWidget(self.dual_a_plotWidget)

        self.dual_a_logTextEdit = QtWidgets.QTextEdit(objectName="dual_a_logTextEdit")
        self.dual_a_logTextEdit.setReadOnly(True)
        dual_a_displayLayout.addWidget(self.dual_a_logTextEdit)

        return dual_a_displayPanel

    # ------------------------------------------------------------------
    # モードB
    # ------------------------------------------------------------------
    def _build_mode_b_page(self) -> QtWidgets.QWidget:
        dual_modeBPage = QtWidgets.QWidget(objectName="dual_modeBPage")
        dual_b_rootLayout = QtWidgets.QVBoxLayout(dual_modeBPage)
        dual_b_rootLayout.setObjectName("dual_b_rootLayout")

        # 共通設定(保存先をまとめて1つのGroupBoxに集約。接続先/BM9ポートは
        # 「機器設定」ダイアログへ移動済み)
        dual_b_commonGroupBox = QtWidgets.QGroupBox(
            "共通設定(BM9 / 保存)", objectName="dual_b_connectionGroupBox"
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

        dual_b_rootLayout.addWidget(dual_b_commonGroupBox)

        # チャンネルA/B
        dual_b_channelsSplitter = QtWidgets.QSplitter(objectName="dual_b_channelsSplitter")
        dual_b_channelsSplitter.setOrientation(enum_value(Qt, "Horizontal"))
        (
            self.dual_chA_enableCheckBox,
            self.dual_chA_deviceModeCombo,
            self.dual_chA_vMinSpin,
            self.dual_chA_vMaxSpin,
            self.dual_chA_vStepSpin,
            self.dual_chA_iterationSpin,
            self.dual_chA_nplcSpin,
            self.dual_chA_delaySpin,
            self.dual_chA_luminanceGroupBox,
            self.dual_chA_useBm9CheckBox,
            self.dual_chA_sampleNameEdit,
            channelAGroupBox,
        ) = self._build_channel_group("chA", "チャンネルA (smua)")
        (
            self.dual_chB_enableCheckBox,
            self.dual_chB_deviceModeCombo,
            self.dual_chB_vMinSpin,
            self.dual_chB_vMaxSpin,
            self.dual_chB_vStepSpin,
            self.dual_chB_iterationSpin,
            self.dual_chB_nplcSpin,
            self.dual_chB_delaySpin,
            self.dual_chB_luminanceGroupBox,
            self.dual_chB_useBm9CheckBox,
            self.dual_chB_sampleNameEdit,
            channelBGroupBox,
        ) = self._build_channel_group("chB", "チャンネルB (smub)")
        dual_b_channelsSplitter.addWidget(channelAGroupBox)
        dual_b_channelsSplitter.addWidget(channelBGroupBox)
        dual_b_rootLayout.addWidget(dual_b_channelsSplitter)

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
        self.dual_b_startButton = QtWidgets.QPushButton("測定開始", objectName="dual_b_startButton")
        self.dual_b_stopButton = QtWidgets.QPushButton("中断", objectName="dual_b_stopButton")
        self.dual_b_stopButton.setEnabled(False)
        dual_b_buttonRow.addWidget(self.dual_b_startButton)
        dual_b_buttonRow.addWidget(self.dual_b_stopButton)
        dual_b_runLayout.addLayout(dual_b_buttonRow)
        self.dual_b_progressBar = QtWidgets.QProgressBar(objectName="dual_b_progressBar")
        dual_b_runLayout.addWidget(self.dual_b_progressBar)
        dual_b_rootLayout.addWidget(dual_b_runGroupBox)

        # 表示(チャンネルA/Bのプロットタブ + 共通ログ)
        self.dual_b_displayTabWidget = QtWidgets.QTabWidget(objectName="dual_b_displayTabWidget")
        self.dual_chA_plotWidget = pg.PlotWidget()
        self.dual_chA_plotWidget.setObjectName("dual_chA_plotWidget")
        self.dual_b_displayTabWidget.addTab(self.dual_chA_plotWidget, "チャンネルA")
        self.dual_chB_plotWidget = pg.PlotWidget()
        self.dual_chB_plotWidget.setObjectName("dual_chB_plotWidget")
        self.dual_b_displayTabWidget.addTab(self.dual_chB_plotWidget, "チャンネルB")
        dual_b_rootLayout.addWidget(self.dual_b_displayTabWidget)

        self.dual_b_logTextEdit = QtWidgets.QTextEdit(objectName="dual_b_logTextEdit")
        self.dual_b_logTextEdit.setReadOnly(True)
        dual_b_rootLayout.addWidget(self.dual_b_logTextEdit)

        return dual_modeBPage

    def _build_channel_group(self, ch_prefix: str, title: str):
        """チャンネルA/B共通の設定グループを構築する(`dual_chA_*`/`dual_chB_*`)。"""
        group_box_object_name = "dual_channelAGroupBox" if ch_prefix == "chA" else "dual_channelBGroupBox"
        group_box = QtWidgets.QGroupBox(title, objectName=group_box_object_name)
        form_layout = QtWidgets.QFormLayout(group_box)
        form_layout.setObjectName(f"dual_{ch_prefix}_formLayout")

        enable_checkbox = QtWidgets.QCheckBox("有効", objectName=f"dual_{ch_prefix}_enableCheckBox")
        form_layout.addRow(enable_checkbox)

        device_mode_combo = QtWidgets.QComboBox(objectName=f"dual_{ch_prefix}_deviceModeCombo")
        device_mode_combo.addItems(DEVICE_MODE_ITEMS)
        form_layout.addRow("計測対象:", device_mode_combo)

        v_min_spin = _make_double_spin(f"dual_{ch_prefix}_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, "")
        v_max_spin = _make_double_spin(f"dual_{ch_prefix}_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, "")
        v_step_spin = _make_double_spin(f"dual_{ch_prefix}_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, "")
        sweep_row = QtWidgets.QHBoxLayout()
        sweep_row.setObjectName(f"dual_{ch_prefix}_sweepRow")
        sweep_row.addWidget(v_min_spin)
        sweep_row.addWidget(v_max_spin)
        sweep_row.addWidget(v_step_spin)
        form_layout.addRow("電圧掃引 (V):", sweep_row)

        iteration_spin = NoScrollSpinBox(objectName=f"dual_{ch_prefix}_iterationSpin")
        iteration_spin.setRange(1, 1000)
        iteration_spin.setValue(3)
        iteration_spin.setMaximumWidth(80)

        nplc_spin = _make_double_spin(f"dual_{ch_prefix}_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)
        delay_spin = _make_double_spin(f"dual_{ch_prefix}_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, "")
        timing_row = QtWidgets.QHBoxLayout()
        timing_row.setObjectName(f"dual_{ch_prefix}_timingRow")
        timing_row.addWidget(iteration_spin)
        timing_row.addWidget(nplc_spin)
        timing_row.addWidget(delay_spin)
        form_layout.addRow("繰り返し回数/NPLC/遅延[s]:", timing_row)

        # 輝度計測(BM9共有): ネストしたGroupBoxではなく、通常のQWidget行として組み込む。
        # `dual_{ch_prefix}_luminanceGroupBox`という属性名・setVisible等の呼び出しは維持する。
        luminance_group_box = QtWidgets.QWidget(objectName=f"dual_{ch_prefix}_luminanceGroupBox")
        luminance_layout = QtWidgets.QHBoxLayout(luminance_group_box)
        luminance_layout.setContentsMargins(0, 0, 0, 0)
        use_bm9_checkbox = QtWidgets.QCheckBox(
            "BM9を使用する", objectName=f"dual_{ch_prefix}_useBm9CheckBox"
        )
        luminance_layout.addWidget(use_bm9_checkbox)
        form_layout.addRow("輝度計測:", luminance_group_box)

        sample_name_edit = QtWidgets.QLineEdit(objectName=f"dual_{ch_prefix}_sampleNameEdit")
        form_layout.addRow("サンプル名:", sample_name_edit)

        return (
            enable_checkbox,
            device_mode_combo,
            v_min_spin,
            v_max_spin,
            v_step_spin,
            iteration_spin,
            nplc_spin,
            delay_spin,
            luminance_group_box,
            use_bm9_checkbox,
            sample_name_edit,
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
        )

    def _build_channel_config(self, prefix: str) -> ChannelConfig:
        enable_checkbox = getattr(self, f"dual_{prefix}_enableCheckBox")
        device_mode_combo = getattr(self, f"dual_{prefix}_deviceModeCombo")
        v_min_spin = getattr(self, f"dual_{prefix}_vMinSpin")
        v_max_spin = getattr(self, f"dual_{prefix}_vMaxSpin")
        v_step_spin = getattr(self, f"dual_{prefix}_vStepSpin")
        iteration_spin = getattr(self, f"dual_{prefix}_iterationSpin")
        nplc_spin = getattr(self, f"dual_{prefix}_nplcSpin")
        delay_spin = getattr(self, f"dual_{prefix}_delaySpin")
        sample_name_edit = getattr(self, f"dual_{prefix}_sampleNameEdit")

        return ChannelConfig(
            enabled=enable_checkbox.isChecked(),
            device_mode=device_mode_combo.currentText(),
            v_min=v_min_spin.value(),
            v_max=v_max_spin.value(),
            v_step=v_step_spin.value(),
            iteration=iteration_spin.value(),
            nplc=nplc_spin.value(),
            delay_time=delay_spin.value(),
            sample_name=sample_name_edit.text().strip() or "sample",
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_mode_a_start_clicked(self) -> None:
        config = self._build_mode_a_config()
        total_points = len(config.build_voltage_list())
        self.dual_a_progressBar.setMaximum(max(total_points, 1))
        self.dual_a_progressBar.setValue(0)
        self._plot_buffer_a = PlotBuffer(self.dual_a_plotWidget)
        self.viewModel.start_mode_a(config)

    def _on_mode_a_stop_clicked(self) -> None:
        self.viewModel.stop_mode_a()

    def _on_mode_b_start_clicked(self) -> None:
        chan_a = self._build_channel_config("chA")
        chan_b = self._build_channel_config("chB")

        led_channel = None
        if chan_a.enabled and chan_a.device_mode == "発光素子":
            led_channel = "A"
        elif chan_b.enabled and chan_b.device_mode == "発光素子":
            led_channel = "B"

        bm9_port = None
        if led_channel == "A" and self.dual_chA_useBm9CheckBox.isChecked():
            bm9_port = self._dual_b_bm9_port
        elif led_channel == "B" and self.dual_chB_useBm9CheckBox.isChecked():
            bm9_port = self._dual_b_bm9_port

        config = DualBConfig(
            connection=self._dual_b_connection,
            use_mock=self._dual_b_use_mock,
            channel_a=chan_a,
            channel_b=chan_b,
            bm9_port=bm9_port,
            save_dir=self.dual_b_saveDirEdit.text().strip() or ".",
        )

        va_len = len(chan_a.build_voltage_list()) if chan_a.enabled else 0
        vb_len = len(chan_b.build_voltage_list()) if chan_b.enabled else 0
        total_points = va_len + vb_len
        self.dual_b_progressBar.setMaximum(max(total_points, 1))
        self.dual_b_progressBar.setValue(0)

        self._plot_buffer_b_cha = (
            PlotBuffer(self.dual_chA_plotWidget) if chan_a.enabled else None
        )
        self._plot_buffer_b_chb = (
            PlotBuffer(self.dual_chB_plotWidget) if chan_b.enabled else None
        )

        self.viewModel.start_mode_b(config)

    def _on_mode_b_stop_clicked(self) -> None:
        self.viewModel.stop_mode_b()

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ (モードA)
    # ------------------------------------------------------------------
    def _on_running_changed_a(self, running: bool) -> None:
        self.dual_a_startButton.setEnabled(not running)
        self.dual_a_stopButton.setEnabled(running)
        self.dual_a_deviceModeCombo.setEnabled(not running)
        self.dual_modeSelectCombo.setEnabled(not running)

    def _on_progress_changed_a(self, current: int, total: int) -> None:
        self.dual_a_progressBar.setMaximum(max(total, 1))
        self.dual_a_progressBar.setValue(current)


    def _on_point_measured_a(self, point) -> None:
        if self._plot_buffer_a is not None:
            self._plot_buffer_a.add_point(point.voltage, point.current)

    def _append_log_a(self, message: str) -> None:
        self.dual_a_logTextEdit.append(message)

    def _append_error_log_a(self, message: str) -> None:
        self.dual_a_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning_a(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok_a(self, points: list, csv_path: str) -> None:
        pass

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ (モードB)
    # ------------------------------------------------------------------
    def _on_running_changed_b(self, running: bool) -> None:
        self.dual_b_startButton.setEnabled(not running)
        self.dual_b_stopButton.setEnabled(running)
        self.dual_modeSelectCombo.setEnabled(not running)

        # チャンネル設定コントロールの制御
        for prefix in ["chA", "chB"]:
            getattr(self, f"dual_{prefix}_enableCheckBox").setEnabled(not running)
            getattr(self, f"dual_{prefix}_deviceModeCombo").setEnabled(not running)
            getattr(self, f"dual_{prefix}_vMinSpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_vMaxSpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_vStepSpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_iterationSpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_nplcSpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_delaySpin").setEnabled(not running)
            getattr(self, f"dual_{prefix}_useBm9CheckBox").setEnabled(not running)
            getattr(self, f"dual_{prefix}_sampleNameEdit").setEnabled(not running)

    def _on_progress_changed_b(self, current: int, total: int) -> None:
        self.dual_b_progressBar.setMaximum(max(total, 1))
        self.dual_b_progressBar.setValue(current)


    def _on_point_measured_b_cha(self, point) -> None:
        if self._plot_buffer_b_cha is not None:
            self._plot_buffer_b_cha.add_point(point.voltage, point.current)

    def _on_point_measured_b_chb(self, point) -> None:
        if self._plot_buffer_b_chb is not None:
            self._plot_buffer_b_chb.add_point(point.voltage, point.current)

    def _append_log_b(self, message: str) -> None:
        self.dual_b_logTextEdit.append(message)

    def _append_error_log_b(self, message: str) -> None:
        self.dual_b_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning_b(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok_b(self, points: list, csv_path_a: str, csv_path_b: str) -> None:
        pass

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

    def _on_browse_mode_a_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_a_saveDirEdit.setText(directory)

    def _on_browse_mode_b_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_b_saveDirEdit.setText(directory)
