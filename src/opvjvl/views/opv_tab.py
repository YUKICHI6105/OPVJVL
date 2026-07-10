"""OPVモード(太陽電池 JV/IV特性測定)タブのView。

B-6-2節「OPVタブ（opv_tab.ui）階層」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。業務ロジックは持たない。
"""
from __future__ import annotations

import pyqtgraph as pg

from opvjvl.qtcompat import Qt, QtWidgets, enum_value


class OPVTab(QtWidgets.QWidget):
    """OPVモードタブ(OPVTabForm相当)。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("OPVTabForm")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        opv_rootLayout = QtWidgets.QHBoxLayout(self)
        opv_rootLayout.setObjectName("opv_rootLayout")

        opv_splitter = QtWidgets.QSplitter(objectName="opv_splitter")
        opv_splitter.setOrientation(enum_value(Qt, "Horizontal"))
        opv_rootLayout.addWidget(opv_splitter)

        opv_splitter.addWidget(self._build_settings_panel())
        opv_splitter.addWidget(self._build_display_panel())

    def _build_settings_panel(self) -> QtWidgets.QScrollArea:
        opv_settingsScrollArea = QtWidgets.QScrollArea(objectName="opv_settingsScrollArea")
        opv_settingsScrollArea.setWidgetResizable(True)

        opv_settingsContainer = QtWidgets.QWidget(objectName="opv_settingsContainer")
        opv_settingsLayout = QtWidgets.QVBoxLayout(opv_settingsContainer)
        opv_settingsLayout.setObjectName("opv_settingsLayout")

        opv_settingsLayout.addWidget(self._build_connection_group())
        opv_settingsLayout.addWidget(self._build_sweep_group())
        opv_settingsLayout.addWidget(self._build_timing_group())
        opv_settingsLayout.addWidget(self._build_save_group())
        opv_settingsLayout.addWidget(self._build_run_group())
        opv_settingsLayout.addStretch()

        opv_settingsScrollArea.setWidget(opv_settingsContainer)
        return opv_settingsScrollArea

    def _build_connection_group(self) -> QtWidgets.QGroupBox:
        opv_connectionGroupBox = QtWidgets.QGroupBox("接続設定", objectName="opv_connectionGroupBox")
        opv_connectionFormLayout = QtWidgets.QFormLayout(opv_connectionGroupBox)
        opv_connectionFormLayout.setObjectName("opv_connectionFormLayout")

        self.opv_deviceTypeCombo = QtWidgets.QComboBox(objectName="opv_deviceTypeCombo")
        self.opv_deviceTypeCombo.addItems(["Keithley2400", "Keithley2612B(単チャンネル運用)"])
        opv_connectionFormLayout.addRow("機器選択:", self.opv_deviceTypeCombo)

        self.opv_useMockCheckBox = QtWidgets.QCheckBox(objectName="opv_useMockCheckBox")
        opv_connectionFormLayout.addRow("モック使用:", self.opv_useMockCheckBox)

        self.opv_connectionCombo = QtWidgets.QComboBox(objectName="opv_connectionCombo")
        self.opv_connectionCombo.setEditable(True)
        self.opv_connectionCombo.addItem("COM5")

        self.opv_refreshDevicesButton = QtWidgets.QPushButton("再検索", objectName="opv_refreshDevicesButton")

        opv_connectionRow = QtWidgets.QHBoxLayout()
        opv_connectionRow.addWidget(self.opv_connectionCombo)
        opv_connectionRow.addWidget(self.opv_refreshDevicesButton)
        opv_connectionFormLayout.addRow("接続先(COM/VISA):", opv_connectionRow)

        return opv_connectionGroupBox

    def _build_sweep_group(self) -> QtWidgets.QGroupBox:
        opv_sweepGroupBox = QtWidgets.QGroupBox("電圧掃引条件", objectName="opv_sweepGroupBox")
        opv_sweepFormLayout = QtWidgets.QFormLayout(opv_sweepGroupBox)
        opv_sweepFormLayout.setObjectName("opv_sweepFormLayout")

        self.opv_vMinSpin = QtWidgets.QDoubleSpinBox(objectName="opv_vMinSpin")
        self.opv_vMinSpin.setRange(-20.0, 20.0)
        self.opv_vMinSpin.setDecimals(3)
        self.opv_vMinSpin.setSingleStep(0.01)
        self.opv_vMinSpin.setValue(-0.1)
        self.opv_vMinSpin.setSuffix(" V")
        opv_sweepFormLayout.addRow("Vmin:", self.opv_vMinSpin)

        self.opv_vMaxSpin = QtWidgets.QDoubleSpinBox(objectName="opv_vMaxSpin")
        self.opv_vMaxSpin.setRange(-20.0, 20.0)
        self.opv_vMaxSpin.setDecimals(3)
        self.opv_vMaxSpin.setSingleStep(0.01)
        self.opv_vMaxSpin.setValue(1.1)
        self.opv_vMaxSpin.setSuffix(" V")
        opv_sweepFormLayout.addRow("Vmax:", self.opv_vMaxSpin)

        self.opv_vStepSpin = QtWidgets.QDoubleSpinBox(objectName="opv_vStepSpin")
        self.opv_vStepSpin.setRange(0.001, 10.0)
        self.opv_vStepSpin.setDecimals(3)
        self.opv_vStepSpin.setSingleStep(0.01)
        self.opv_vStepSpin.setValue(0.02)
        self.opv_vStepSpin.setSuffix(" V")
        opv_sweepFormLayout.addRow("Vstep:", self.opv_vStepSpin)

        self.opv_iterationSpin = QtWidgets.QSpinBox(objectName="opv_iterationSpin")
        self.opv_iterationSpin.setRange(1, 1000)
        self.opv_iterationSpin.setValue(3)
        opv_sweepFormLayout.addRow("繰り返し回数:", self.opv_iterationSpin)

        return opv_sweepGroupBox

    def _build_timing_group(self) -> QtWidgets.QGroupBox:
        opv_timingGroupBox = QtWidgets.QGroupBox(
            "タイミング/コンプライアンス", objectName="opv_timingGroupBox"
        )
        opv_timingFormLayout = QtWidgets.QFormLayout(opv_timingGroupBox)
        opv_timingFormLayout.setObjectName("opv_timingFormLayout")

        self.opv_nplcSpin = QtWidgets.QDoubleSpinBox(objectName="opv_nplcSpin")
        self.opv_nplcSpin.setRange(0.01, 10.0)
        self.opv_nplcSpin.setDecimals(2)
        self.opv_nplcSpin.setSingleStep(0.1)
        self.opv_nplcSpin.setValue(1.0)
        opv_timingFormLayout.addRow("積分時間(NPLC):", self.opv_nplcSpin)

        self.opv_delaySpin = QtWidgets.QDoubleSpinBox(objectName="opv_delaySpin")
        self.opv_delaySpin.setRange(0.0, 60.0)
        self.opv_delaySpin.setDecimals(2)
        self.opv_delaySpin.setSingleStep(0.1)
        self.opv_delaySpin.setValue(1.0)
        self.opv_delaySpin.setSuffix(" s")
        opv_timingFormLayout.addRow("遅延時間[s]:", self.opv_delaySpin)

        self.opv_complianceSpin = QtWidgets.QDoubleSpinBox(objectName="opv_complianceSpin")
        self.opv_complianceSpin.setRange(0.0001, 1.0)
        self.opv_complianceSpin.setDecimals(4)
        self.opv_complianceSpin.setSingleStep(0.001)
        self.opv_complianceSpin.setValue(0.02)
        self.opv_complianceSpin.setSuffix(" A")
        opv_timingFormLayout.addRow("コンプライアンス電流[A]:", self.opv_complianceSpin)

        return opv_timingGroupBox

    def _build_save_group(self) -> QtWidgets.QGroupBox:
        opv_saveGroupBox = QtWidgets.QGroupBox("保存", objectName="opv_saveGroupBox")
        opv_saveFormLayout = QtWidgets.QFormLayout(opv_saveGroupBox)
        opv_saveFormLayout.setObjectName("opv_saveFormLayout")

        self.opv_sampleNameEdit = QtWidgets.QLineEdit(objectName="opv_sampleNameEdit")
        opv_saveFormLayout.addRow("サンプル名:", self.opv_sampleNameEdit)

        self.opv_saveDirEdit = QtWidgets.QLineEdit(objectName="opv_saveDirEdit")
        self.opv_browseSaveDirButton = QtWidgets.QPushButton("参照...", objectName="opv_browseSaveDirButton")
        self.opv_browseSaveDirButton.clicked.connect(self._on_browse_save_dir)

        opv_saveDirRow = QtWidgets.QHBoxLayout()
        opv_saveDirRow.addWidget(self.opv_saveDirEdit)
        opv_saveDirRow.addWidget(self.opv_browseSaveDirButton)
        opv_saveFormLayout.addRow("保存先:", opv_saveDirRow)

        return opv_saveGroupBox

    def _build_run_group(self) -> QtWidgets.QGroupBox:
        opv_runGroupBox = QtWidgets.QGroupBox("実行", objectName="opv_runGroupBox")
        opv_runLayout = QtWidgets.QHBoxLayout(opv_runGroupBox)
        opv_runLayout.setObjectName("opv_runLayout")

        self.opv_startButton = QtWidgets.QPushButton("測定開始", objectName="opv_startButton")
        self.opv_stopButton = QtWidgets.QPushButton("中断", objectName="opv_stopButton")
        self.opv_stopButton.setEnabled(False)

        opv_runLayout.addWidget(self.opv_startButton)
        opv_runLayout.addWidget(self.opv_stopButton)

        return opv_runGroupBox

    def _build_display_panel(self) -> QtWidgets.QWidget:
        opv_displayPanel = QtWidgets.QWidget(objectName="opv_displayPanel")
        opv_displayLayout = QtWidgets.QVBoxLayout(opv_displayPanel)
        opv_displayLayout.setObjectName("opv_displayLayout")

        self.opv_progressBar = QtWidgets.QProgressBar(objectName="opv_progressBar")
        self.opv_progressBar.setValue(0)
        opv_displayLayout.addWidget(self.opv_progressBar)

        self.opv_plotWidget = pg.PlotWidget()
        self.opv_plotWidget.setObjectName("opv_plotWidget")
        opv_displayLayout.addWidget(self.opv_plotWidget)

        opv_logGroupBox = QtWidgets.QGroupBox("ログ", objectName="opv_logGroupBox")
        opv_logLayout = QtWidgets.QVBoxLayout(opv_logGroupBox)
        opv_logLayout.setObjectName("opv_logLayout")

        self.opv_logTextEdit = QtWidgets.QTextEdit(objectName="opv_logTextEdit")
        self.opv_logTextEdit.setReadOnly(True)
        opv_logLayout.addWidget(self.opv_logTextEdit)

        opv_displayLayout.addWidget(opv_logGroupBox)

        return opv_displayPanel

    # ------------------------------------------------------------------
    # View内に閉じた表示制御(ロジックは持たない単純なスロット)
    # ------------------------------------------------------------------
    def _on_browse_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.opv_saveDirEdit.setText(directory)
