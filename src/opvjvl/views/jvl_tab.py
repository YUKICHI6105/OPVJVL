"""JVLモード(発光素子 IV-輝度測定 / 暗IV測定共通)タブのView。

B-6-2節「JVLタブ（jvl_tab.ui）」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。業務ロジックは持たない。
OPVタブと同一構成に加え、輝度計(BM9)グループと2ページ構成のプロットタブを持つ。
"""
from __future__ import annotations

import pyqtgraph as pg

from opvjvl.qtcompat import Qt, QtWidgets, enum_value


class JVLTab(QtWidgets.QWidget):
    """JVLモードタブ(JVLTabForm相当)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("JVLTabForm")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        jvl_rootLayout = QtWidgets.QHBoxLayout(self)
        jvl_rootLayout.setObjectName("jvl_rootLayout")

        jvl_splitter = QtWidgets.QSplitter(objectName="jvl_splitter")
        jvl_splitter.setOrientation(enum_value(Qt, "Horizontal"))
        jvl_rootLayout.addWidget(jvl_splitter)

        jvl_splitter.addWidget(self._build_settings_panel())
        jvl_splitter.addWidget(self._build_display_panel())

    def _build_settings_panel(self) -> QtWidgets.QScrollArea:
        jvl_settingsScrollArea = QtWidgets.QScrollArea(objectName="jvl_settingsScrollArea")
        jvl_settingsScrollArea.setWidgetResizable(True)

        jvl_settingsContainer = QtWidgets.QWidget(objectName="jvl_settingsContainer")
        jvl_settingsLayout = QtWidgets.QVBoxLayout(jvl_settingsContainer)
        jvl_settingsLayout.setObjectName("jvl_settingsLayout")

        jvl_settingsLayout.addWidget(self._build_connection_group())
        jvl_settingsLayout.addWidget(self._build_sweep_group())
        jvl_settingsLayout.addWidget(self._build_timing_group())
        jvl_settingsLayout.addWidget(self._build_luminance_group())
        jvl_settingsLayout.addWidget(self._build_save_group())
        jvl_settingsLayout.addWidget(self._build_run_group())
        jvl_settingsLayout.addStretch()

        jvl_settingsScrollArea.setWidget(jvl_settingsContainer)
        return jvl_settingsScrollArea

    def _build_connection_group(self) -> QtWidgets.QGroupBox:
        jvl_connectionGroupBox = QtWidgets.QGroupBox("接続設定", objectName="jvl_connectionGroupBox")
        jvl_connectionFormLayout = QtWidgets.QFormLayout(jvl_connectionGroupBox)
        jvl_connectionFormLayout.setObjectName("jvl_connectionFormLayout")

        self.jvl_deviceTypeCombo = QtWidgets.QComboBox(objectName="jvl_deviceTypeCombo")
        self.jvl_deviceTypeCombo.addItems(["Keithley2400", "Keithley2612B(単チャンネル運用)"])
        jvl_connectionFormLayout.addRow("機器選択:", self.jvl_deviceTypeCombo)

        self.jvl_useMockCheckBox = QtWidgets.QCheckBox(objectName="jvl_useMockCheckBox")
        jvl_connectionFormLayout.addRow("モック使用:", self.jvl_useMockCheckBox)

        self.jvl_connectionCombo = QtWidgets.QComboBox(objectName="jvl_connectionCombo")
        self.jvl_connectionCombo.setEditable(True)
        self.jvl_connectionCombo.addItem("COM5")

        self.jvl_refreshDevicesButton = QtWidgets.QPushButton("再検索", objectName="jvl_refreshDevicesButton")

        jvl_connectionRow = QtWidgets.QHBoxLayout()
        jvl_connectionRow.addWidget(self.jvl_connectionCombo)
        jvl_connectionRow.addWidget(self.jvl_refreshDevicesButton)
        jvl_connectionFormLayout.addRow("接続先(COM/VISA):", jvl_connectionRow)

        return jvl_connectionGroupBox

    def _build_sweep_group(self) -> QtWidgets.QGroupBox:
        jvl_sweepGroupBox = QtWidgets.QGroupBox("電圧掃引条件", objectName="jvl_sweepGroupBox")
        jvl_sweepFormLayout = QtWidgets.QFormLayout(jvl_sweepGroupBox)
        jvl_sweepFormLayout.setObjectName("jvl_sweepFormLayout")

        self.jvl_vMinSpin = QtWidgets.QDoubleSpinBox(objectName="jvl_vMinSpin")
        self.jvl_vMinSpin.setRange(-20.0, 20.0)
        self.jvl_vMinSpin.setDecimals(3)
        self.jvl_vMinSpin.setSingleStep(0.1)
        self.jvl_vMinSpin.setValue(-1.0)
        self.jvl_vMinSpin.setSuffix(" V")
        jvl_sweepFormLayout.addRow("Vmin:", self.jvl_vMinSpin)

        self.jvl_vMaxSpin = QtWidgets.QDoubleSpinBox(objectName="jvl_vMaxSpin")
        self.jvl_vMaxSpin.setRange(-20.0, 20.0)
        self.jvl_vMaxSpin.setDecimals(3)
        self.jvl_vMaxSpin.setSingleStep(0.1)
        self.jvl_vMaxSpin.setValue(1.9)
        self.jvl_vMaxSpin.setSuffix(" V")
        jvl_sweepFormLayout.addRow("Vmax:", self.jvl_vMaxSpin)

        self.jvl_vStepSpin = QtWidgets.QDoubleSpinBox(objectName="jvl_vStepSpin")
        self.jvl_vStepSpin.setRange(0.001, 10.0)
        self.jvl_vStepSpin.setDecimals(3)
        self.jvl_vStepSpin.setSingleStep(0.01)
        self.jvl_vStepSpin.setValue(0.1)
        self.jvl_vStepSpin.setSuffix(" V")
        jvl_sweepFormLayout.addRow("Vstep:", self.jvl_vStepSpin)

        self.jvl_iterationSpin = QtWidgets.QSpinBox(objectName="jvl_iterationSpin")
        self.jvl_iterationSpin.setRange(1, 1000)
        self.jvl_iterationSpin.setValue(3)
        jvl_sweepFormLayout.addRow("繰り返し回数:", self.jvl_iterationSpin)

        return jvl_sweepGroupBox

    def _build_timing_group(self) -> QtWidgets.QGroupBox:
        jvl_timingGroupBox = QtWidgets.QGroupBox(
            "タイミング/コンプライアンス", objectName="jvl_timingGroupBox"
        )
        jvl_timingFormLayout = QtWidgets.QFormLayout(jvl_timingGroupBox)
        jvl_timingFormLayout.setObjectName("jvl_timingFormLayout")

        self.jvl_nplcSpin = QtWidgets.QDoubleSpinBox(objectName="jvl_nplcSpin")
        self.jvl_nplcSpin.setRange(0.01, 10.0)
        self.jvl_nplcSpin.setDecimals(2)
        self.jvl_nplcSpin.setSingleStep(0.1)
        self.jvl_nplcSpin.setValue(1.0)
        jvl_timingFormLayout.addRow("積分時間(NPLC):", self.jvl_nplcSpin)

        self.jvl_delaySpin = QtWidgets.QDoubleSpinBox(objectName="jvl_delaySpin")
        self.jvl_delaySpin.setRange(0.0, 60.0)
        self.jvl_delaySpin.setDecimals(2)
        self.jvl_delaySpin.setSingleStep(0.1)
        self.jvl_delaySpin.setValue(1.0)
        self.jvl_delaySpin.setSuffix(" s")
        jvl_timingFormLayout.addRow("遅延時間[s]:", self.jvl_delaySpin)

        self.jvl_complianceSpin = QtWidgets.QDoubleSpinBox(objectName="jvl_complianceSpin")
        self.jvl_complianceSpin.setRange(0.0001, 1.0)
        self.jvl_complianceSpin.setDecimals(4)
        self.jvl_complianceSpin.setSingleStep(0.001)
        self.jvl_complianceSpin.setValue(0.02)
        self.jvl_complianceSpin.setSuffix(" A")
        jvl_timingFormLayout.addRow("コンプライアンス電流[A]:", self.jvl_complianceSpin)

        return jvl_timingGroupBox

    def _build_luminance_group(self) -> QtWidgets.QGroupBox:
        jvl_luminanceGroupBox = QtWidgets.QGroupBox("輝度計(BM9)", objectName="jvl_luminanceGroupBox")
        jvl_luminanceLayout = QtWidgets.QVBoxLayout(jvl_luminanceGroupBox)
        jvl_luminanceLayout.setObjectName("jvl_luminanceLayout")

        self.jvl_useLuminanceCheckBox = QtWidgets.QCheckBox(
            "BM9で輝度も測定する(OFFで暗IV測定)", objectName="jvl_useLuminanceCheckBox"
        )
        self.jvl_useLuminanceCheckBox.setChecked(True)
        jvl_luminanceLayout.addWidget(self.jvl_useLuminanceCheckBox)

        jvl_luminanceFormLayout = QtWidgets.QFormLayout()
        jvl_luminanceFormLayout.setObjectName("jvl_luminanceFormLayout")

        self.jvl_bm9PortCombo = QtWidgets.QComboBox(objectName="jvl_bm9PortCombo")
        self.jvl_bm9PortCombo.setEditable(True)
        self.jvl_bm9PortCombo.addItem("COM4")

        self.jvl_refreshBm9PortsButton = QtWidgets.QPushButton(
            "再検索", objectName="jvl_refreshBm9PortsButton"
        )

        jvl_bm9PortRow = QtWidgets.QHBoxLayout()
        jvl_bm9PortRow.addWidget(self.jvl_bm9PortCombo)
        jvl_bm9PortRow.addWidget(self.jvl_refreshBm9PortsButton)
        jvl_luminanceFormLayout.addRow("ポート:", jvl_bm9PortRow)

        jvl_luminanceLayout.addLayout(jvl_luminanceFormLayout)

        self.jvl_useLuminanceCheckBox.toggled.connect(self._on_use_luminance_toggled)
        self._on_use_luminance_toggled(self.jvl_useLuminanceCheckBox.isChecked())

        return jvl_luminanceGroupBox

    def _build_save_group(self) -> QtWidgets.QGroupBox:
        jvl_saveGroupBox = QtWidgets.QGroupBox("保存", objectName="jvl_saveGroupBox")
        jvl_saveFormLayout = QtWidgets.QFormLayout(jvl_saveGroupBox)
        jvl_saveFormLayout.setObjectName("jvl_saveFormLayout")

        self.jvl_sampleNameEdit = QtWidgets.QLineEdit(objectName="jvl_sampleNameEdit")
        jvl_saveFormLayout.addRow("サンプル名:", self.jvl_sampleNameEdit)

        self.jvl_saveDirEdit = QtWidgets.QLineEdit(objectName="jvl_saveDirEdit")
        self.jvl_browseSaveDirButton = QtWidgets.QPushButton("参照...", objectName="jvl_browseSaveDirButton")
        self.jvl_browseSaveDirButton.clicked.connect(self._on_browse_save_dir)

        jvl_saveDirRow = QtWidgets.QHBoxLayout()
        jvl_saveDirRow.addWidget(self.jvl_saveDirEdit)
        jvl_saveDirRow.addWidget(self.jvl_browseSaveDirButton)
        jvl_saveFormLayout.addRow("保存先:", jvl_saveDirRow)

        return jvl_saveGroupBox

    def _build_run_group(self) -> QtWidgets.QGroupBox:
        jvl_runGroupBox = QtWidgets.QGroupBox("実行", objectName="jvl_runGroupBox")
        jvl_runLayout = QtWidgets.QHBoxLayout(jvl_runGroupBox)
        jvl_runLayout.setObjectName("jvl_runLayout")

        self.jvl_startButton = QtWidgets.QPushButton("測定開始", objectName="jvl_startButton")
        self.jvl_stopButton = QtWidgets.QPushButton("中断", objectName="jvl_stopButton")
        self.jvl_stopButton.setEnabled(False)

        jvl_runLayout.addWidget(self.jvl_startButton)
        jvl_runLayout.addWidget(self.jvl_stopButton)

        return jvl_runGroupBox

    def _build_display_panel(self) -> QtWidgets.QWidget:
        jvl_displayPanel = QtWidgets.QWidget(objectName="jvl_displayPanel")
        jvl_displayLayout = QtWidgets.QVBoxLayout(jvl_displayPanel)
        jvl_displayLayout.setObjectName("jvl_displayLayout")

        self.jvl_progressBar = QtWidgets.QProgressBar(objectName="jvl_progressBar")
        self.jvl_progressBar.setValue(0)
        jvl_displayLayout.addWidget(self.jvl_progressBar)

        self.jvl_plotTabWidget = QtWidgets.QTabWidget(objectName="jvl_plotTabWidget")

        self.jvl_ivPlotWidget = pg.PlotWidget()
        self.jvl_ivPlotWidget.setObjectName("jvl_ivPlotWidget")
        self.jvl_ivPlotWidget.setLabel("bottom", "Voltage", units="V")
        self.jvl_ivPlotWidget.setLabel("left", "Current", units="A")
        self.jvl_ivPlotWidget.showGrid(x=True, y=True, alpha=0.2)
        self.jvl_plotTabWidget.addTab(self.jvl_ivPlotWidget, "I-V")

        self.jvl_ivlPlotWidget = pg.PlotWidget()
        self.jvl_ivlPlotWidget.setObjectName("jvl_ivlPlotWidget")
        self.jvl_ivlPlotWidget.setLabel("bottom", "Voltage", units="V")
        self.jvl_ivlPlotWidget.setLabel("left", "Current", units="A")
        self.jvl_ivlPlotWidget.showGrid(x=True, y=True, alpha=0.2)
        self._setup_luminance_axis(self.jvl_ivlPlotWidget)
        self.jvl_plotTabWidget.addTab(self.jvl_ivlPlotWidget, "I-V-L")

        jvl_displayLayout.addWidget(self.jvl_plotTabWidget)

        jvl_logGroupBox = QtWidgets.QGroupBox("ログ", objectName="jvl_logGroupBox")
        jvl_logLayout = QtWidgets.QVBoxLayout(jvl_logGroupBox)
        jvl_logLayout.setObjectName("jvl_logLayout")

        self.jvl_logTextEdit = QtWidgets.QTextEdit(objectName="jvl_logTextEdit")
        self.jvl_logTextEdit.setReadOnly(True)
        jvl_logLayout.addWidget(self.jvl_logTextEdit)

        jvl_displayLayout.addWidget(jvl_logGroupBox)

        return jvl_displayPanel

    def _setup_luminance_axis(self, plot_widget: pg.PlotWidget) -> None:
        """I-V-Lグラフの右軸に輝度用ViewBoxを重ねる(既存main_gui.pyのパターン踏襲)。

        実際のデータプロットはViewModel/Worker側の役割であり、ここでは
        右軸ViewBoxの土台(表示制御)のみを用意する。
        """
        luminance_viewbox = pg.ViewBox()
        plot_widget.scene().addItem(luminance_viewbox)
        plot_widget.getAxis("right").linkToView(luminance_viewbox)
        luminance_viewbox.setXLink(plot_widget)
        plot_widget.showAxis("right")
        plot_widget.getAxis("right").setLabel("Luminance", units="cd/m2")
        plot_widget.luminance_viewbox = luminance_viewbox

        def _sync_luminance_viewbox() -> None:
            luminance_viewbox.setGeometry(plot_widget.getViewBox().sceneBoundingRect())

        _sync_luminance_viewbox()
        plot_widget.getViewBox().sigResized.connect(_sync_luminance_viewbox)

    # ------------------------------------------------------------------
    # View内に閉じた表示制御(ロジックは持たない単純なスロット)
    # ------------------------------------------------------------------
    def _on_use_luminance_toggled(self, checked: bool) -> None:
        self.jvl_bm9PortCombo.setEnabled(checked)
        self.jvl_refreshBm9PortsButton.setEnabled(checked)

    def _on_browse_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.jvl_saveDirEdit.setText(directory)
