"""2ch活用モード(モードA: 2ch低ノイズ計測 / モードB: 2素子同時計測)タブのView。

B-6-2節「2ch活用モードタブ（dual_channel_tab.ui）」のウィジェットツリー・
objectName命名規則に厳密に従い、Pythonコードでウィジェットツリーを構築する。
業務ロジックは持たないが、以下のView内表示制御のみ持つ(要件に明記されたもの):
  - dual_modeSelectComboの選択に応じたdual_modeStackのページ切替
  - モードBでのチャンネルA/B発光素子モードの排他制御(コンボ項目の有効/無効)
  - モードAでの計測対象モードに応じた輝度計グループの表示/非表示
"""
from __future__ import annotations

import pyqtgraph as pg

from opvjvl.qtcompat import Qt, QtWidgets, enum_value

DEVICE_MODE_ITEMS = ["太陽電池", "発光素子"]


def _make_double_spin(
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    value: float,
    suffix: str = "",
) -> QtWidgets.QDoubleSpinBox:
    spin = QtWidgets.QDoubleSpinBox(objectName=object_name)
    spin.setRange(minimum, maximum)
    spin.setDecimals(decimals)
    spin.setSingleStep(step)
    spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    return spin


class DualChannelTab(QtWidgets.QWidget):
    """2ch活用モードタブ(DualChannelTabForm相当)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DualChannelTabForm")
        self._updating_exclusivity = False
        self._build_ui()

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

        # 接続設定
        dual_a_connectionGroupBox = QtWidgets.QGroupBox("接続設定", objectName="dual_a_connectionGroupBox")
        dual_a_connectionFormLayout = QtWidgets.QFormLayout(dual_a_connectionGroupBox)
        self.dual_a_useMockCheckBox = QtWidgets.QCheckBox(objectName="dual_a_useMockCheckBox")
        dual_a_connectionFormLayout.addRow("モック使用:", self.dual_a_useMockCheckBox)
        self.dual_a_connectionCombo = QtWidgets.QComboBox(objectName="dual_a_connectionCombo")
        self.dual_a_connectionCombo.setEditable(True)
        dual_a_connectionFormLayout.addRow("接続先(VISA):", self.dual_a_connectionCombo)
        dual_a_settingsLayout.addWidget(dual_a_connectionGroupBox)

        # 計測対象
        dual_a_deviceModeGroupBox = QtWidgets.QGroupBox("計測対象", objectName="dual_a_deviceModeGroupBox")
        dual_a_deviceModeFormLayout = QtWidgets.QFormLayout(dual_a_deviceModeGroupBox)
        self.dual_a_deviceModeCombo = QtWidgets.QComboBox(objectName="dual_a_deviceModeCombo")
        self.dual_a_deviceModeCombo.addItems(DEVICE_MODE_ITEMS)
        dual_a_deviceModeFormLayout.addRow("計測対象:", self.dual_a_deviceModeCombo)
        dual_a_settingsLayout.addWidget(dual_a_deviceModeGroupBox)

        # 電圧掃引条件
        dual_a_sweepGroupBox = QtWidgets.QGroupBox("電圧掃引条件", objectName="dual_a_sweepGroupBox")
        dual_a_sweepFormLayout = QtWidgets.QFormLayout(dual_a_sweepGroupBox)
        self.dual_a_vMinSpin = _make_double_spin("dual_a_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, " V")
        dual_a_sweepFormLayout.addRow("Vmin:", self.dual_a_vMinSpin)
        self.dual_a_vMaxSpin = _make_double_spin("dual_a_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, " V")
        dual_a_sweepFormLayout.addRow("Vmax:", self.dual_a_vMaxSpin)
        self.dual_a_vStepSpin = _make_double_spin("dual_a_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, " V")
        dual_a_sweepFormLayout.addRow("Vstep:", self.dual_a_vStepSpin)
        self.dual_a_iterationSpin = QtWidgets.QSpinBox(objectName="dual_a_iterationSpin")
        self.dual_a_iterationSpin.setRange(1, 1000)
        self.dual_a_iterationSpin.setValue(3)
        dual_a_sweepFormLayout.addRow("繰り返し回数:", self.dual_a_iterationSpin)
        dual_a_settingsLayout.addWidget(dual_a_sweepGroupBox)

        # タイミング/コンプライアンス
        dual_a_timingGroupBox = QtWidgets.QGroupBox(
            "タイミング/コンプライアンス", objectName="dual_a_timingGroupBox"
        )
        dual_a_timingFormLayout = QtWidgets.QFormLayout(dual_a_timingGroupBox)
        self.dual_a_nplcSpin = _make_double_spin("dual_a_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)
        dual_a_timingFormLayout.addRow("積分時間(NPLC):", self.dual_a_nplcSpin)
        self.dual_a_delaySpin = _make_double_spin("dual_a_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, " s")
        dual_a_timingFormLayout.addRow("遅延時間[s]:", self.dual_a_delaySpin)
        self.dual_a_complianceSpin = _make_double_spin(
            "dual_a_complianceSpin", 0.0001, 1.0, 4, 0.001, 0.02, " A"
        )
        dual_a_timingFormLayout.addRow("コンプライアンス電流[A]:", self.dual_a_complianceSpin)
        dual_a_settingsLayout.addWidget(dual_a_timingGroupBox)

        # 輝度計(発光素子選択時のみ表示)
        self.dual_a_luminanceGroupBox = QtWidgets.QGroupBox(
            "輝度計(BM9)", objectName="dual_a_luminanceGroupBox"
        )
        dual_a_luminanceFormLayout = QtWidgets.QFormLayout(self.dual_a_luminanceGroupBox)
        self.dual_a_bm9PortCombo = QtWidgets.QComboBox(objectName="dual_a_bm9PortCombo")
        self.dual_a_bm9PortCombo.setEditable(True)
        self.dual_a_bm9PortCombo.addItem("COM4")
        dual_a_luminanceFormLayout.addRow("ポート:", self.dual_a_bm9PortCombo)
        dual_a_settingsLayout.addWidget(self.dual_a_luminanceGroupBox)

        # 保存
        dual_a_saveGroupBox = QtWidgets.QGroupBox("保存", objectName="dual_a_saveGroupBox")
        dual_a_saveFormLayout = QtWidgets.QFormLayout(dual_a_saveGroupBox)
        self.dual_a_sampleNameEdit = QtWidgets.QLineEdit(objectName="dual_a_sampleNameEdit")
        dual_a_saveFormLayout.addRow("サンプル名:", self.dual_a_sampleNameEdit)
        self.dual_a_saveDirEdit = QtWidgets.QLineEdit(objectName="dual_a_saveDirEdit")
        self.dual_a_browseSaveDirButton = QtWidgets.QPushButton(
            "参照...", objectName="dual_a_browseSaveDirButton"
        )
        self.dual_a_browseSaveDirButton.clicked.connect(self._on_browse_mode_a_save_dir)
        dual_a_saveDirRow = QtWidgets.QHBoxLayout()
        dual_a_saveDirRow.addWidget(self.dual_a_saveDirEdit)
        dual_a_saveDirRow.addWidget(self.dual_a_browseSaveDirButton)
        dual_a_saveFormLayout.addRow("保存先:", dual_a_saveDirRow)
        dual_a_settingsLayout.addWidget(dual_a_saveGroupBox)

        # 実行
        dual_a_runGroupBox = QtWidgets.QGroupBox("実行", objectName="dual_a_runGroupBox")
        dual_a_runLayout = QtWidgets.QHBoxLayout(dual_a_runGroupBox)
        self.dual_a_startButton = QtWidgets.QPushButton("測定開始", objectName="dual_a_startButton")
        self.dual_a_stopButton = QtWidgets.QPushButton("中断", objectName="dual_a_stopButton")
        self.dual_a_stopButton.setEnabled(False)
        dual_a_runLayout.addWidget(self.dual_a_startButton)
        dual_a_runLayout.addWidget(self.dual_a_stopButton)
        dual_a_settingsLayout.addWidget(dual_a_runGroupBox)

        dual_a_settingsLayout.addStretch()

        dual_a_settingsScrollArea.setWidget(dual_a_settingsContainer)

        self.dual_a_deviceModeCombo.currentTextChanged.connect(self._on_mode_a_device_mode_changed)
        self._on_mode_a_device_mode_changed(self.dual_a_deviceModeCombo.currentText())

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

        # 接続設定(2612B共通)
        dual_b_connectionGroupBox = QtWidgets.QGroupBox(
            "接続設定(2612B共通)", objectName="dual_b_connectionGroupBox"
        )
        dual_b_connectionFormLayout = QtWidgets.QFormLayout(dual_b_connectionGroupBox)
        self.dual_b_useMockCheckBox = QtWidgets.QCheckBox(objectName="dual_b_useMockCheckBox")
        dual_b_connectionFormLayout.addRow("モック使用:", self.dual_b_useMockCheckBox)
        self.dual_b_connectionCombo = QtWidgets.QComboBox(objectName="dual_b_connectionCombo")
        self.dual_b_connectionCombo.setEditable(True)
        dual_b_connectionFormLayout.addRow("接続先(VISA):", self.dual_b_connectionCombo)
        dual_b_rootLayout.addWidget(dual_b_connectionGroupBox)

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

        # 輝度計(BM9)ポート(チャンネル横断で1つのみ)
        dual_b_bm9GroupBox = QtWidgets.QGroupBox("輝度計(BM9)ポート", objectName="dual_b_bm9GroupBox")
        dual_b_bm9FormLayout = QtWidgets.QFormLayout(dual_b_bm9GroupBox)
        self.dual_b_bm9PortCombo = QtWidgets.QComboBox(objectName="dual_b_bm9PortCombo")
        self.dual_b_bm9PortCombo.setEditable(True)
        self.dual_b_bm9PortCombo.addItem("COM4")
        dual_b_bm9FormLayout.addRow("ポート:", self.dual_b_bm9PortCombo)
        dual_b_rootLayout.addWidget(dual_b_bm9GroupBox)

        # 保存
        dual_b_saveGroupBox = QtWidgets.QGroupBox("保存", objectName="dual_b_saveGroupBox")
        dual_b_saveFormLayout = QtWidgets.QFormLayout(dual_b_saveGroupBox)
        self.dual_b_saveDirEdit = QtWidgets.QLineEdit(objectName="dual_b_saveDirEdit")
        self.dual_b_browseSaveDirButton = QtWidgets.QPushButton(
            "参照...", objectName="dual_b_browseSaveDirButton"
        )
        self.dual_b_browseSaveDirButton.clicked.connect(self._on_browse_mode_b_save_dir)
        dual_b_saveDirRow = QtWidgets.QHBoxLayout()
        dual_b_saveDirRow.addWidget(self.dual_b_saveDirEdit)
        dual_b_saveDirRow.addWidget(self.dual_b_browseSaveDirButton)
        dual_b_saveFormLayout.addRow("保存先:", dual_b_saveDirRow)
        dual_b_rootLayout.addWidget(dual_b_saveGroupBox)

        # 実行
        dual_b_runGroupBox = QtWidgets.QGroupBox("実行", objectName="dual_b_runGroupBox")
        dual_b_runLayout = QtWidgets.QVBoxLayout(dual_b_runGroupBox)
        dual_b_buttonRow = QtWidgets.QHBoxLayout()
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

        v_min_spin = _make_double_spin(f"dual_{ch_prefix}_vMinSpin", -20.0, 20.0, 3, 0.01, -0.1, " V")
        v_max_spin = _make_double_spin(f"dual_{ch_prefix}_vMaxSpin", -20.0, 20.0, 3, 0.01, 1.1, " V")
        v_step_spin = _make_double_spin(f"dual_{ch_prefix}_vStepSpin", 0.001, 10.0, 3, 0.01, 0.02, " V")
        sweep_row = QtWidgets.QHBoxLayout()
        sweep_row.addWidget(v_min_spin)
        sweep_row.addWidget(v_max_spin)
        sweep_row.addWidget(v_step_spin)
        form_layout.addRow("Vmin/Vmax/Vstep:", sweep_row)

        iteration_spin = QtWidgets.QSpinBox(objectName=f"dual_{ch_prefix}_iterationSpin")
        iteration_spin.setRange(1, 1000)
        iteration_spin.setValue(3)
        form_layout.addRow("繰り返し回数:", iteration_spin)

        nplc_spin = _make_double_spin(f"dual_{ch_prefix}_nplcSpin", 0.01, 10.0, 2, 0.1, 1.0)
        delay_spin = _make_double_spin(f"dual_{ch_prefix}_delaySpin", 0.0, 60.0, 2, 0.1, 1.0, " s")
        timing_row = QtWidgets.QHBoxLayout()
        timing_row.addWidget(nplc_spin)
        timing_row.addWidget(delay_spin)
        form_layout.addRow("NPLC/遅延:", timing_row)

        luminance_group_box = QtWidgets.QGroupBox(
            "輝度計測(BM9共有)", objectName=f"dual_{ch_prefix}_luminanceGroupBox"
        )
        luminance_layout = QtWidgets.QVBoxLayout(luminance_group_box)
        use_bm9_checkbox = QtWidgets.QCheckBox(
            "BM9を使用する", objectName=f"dual_{ch_prefix}_useBm9CheckBox"
        )
        luminance_layout.addWidget(use_bm9_checkbox)
        form_layout.addRow(luminance_group_box)

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
    # View内に閉じた表示制御(ロジックは持たない単純なスロット)
    # ------------------------------------------------------------------
    def _on_mode_a_device_mode_changed(self, text: str) -> None:
        """モードA: 計測対象が「発光素子」の場合のみ輝度計グループを表示する。"""
        self.dual_a_luminanceGroupBox.setVisible(text == "発光素子")

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
        for index in range(combo.count()):
            if combo.itemText(index) == text:
                item = model.item(index)
                if item is not None:
                    item.setEnabled(enabled)
                break

    def _on_browse_mode_a_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_a_saveDirEdit.setText(directory)

    def _on_browse_mode_b_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.dual_b_saveDirEdit.setText(directory)
