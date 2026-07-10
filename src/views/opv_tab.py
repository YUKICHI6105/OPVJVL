"""OPVモード(太陽電池 JV/IV特性測定)タブのView。

B-6-2節「OPVタブ（opv_tab.ui）階層」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。
"""
from __future__ import annotations

import pyqtgraph as pg

from qtcompat import Qt, QtWidgets, enum_value
from models.measurement.config import OPVConfig
from viewmodels.opv_viewmodel import OPVViewModel
from views.plot_buffer import PlotBuffer
from views.widgets.no_scroll_spinbox import NoScrollDoubleSpinBox, NoScrollSpinBox


class OPVTab(QtWidgets.QWidget):
    """OPVモードタブ(OPVTabForm相当)。"""

    def __init__(
        self,
        parent=None,
        viewModel: OPVViewModel = None,
        sample_name_edit: QtWidgets.QLineEdit = None,
        save_dir_edit: QtWidgets.QLineEdit = None,
    ):
        super().__init__(parent)
        self.setObjectName("OPVTabForm")
        self._plot_buffer = None
        self._external_sample_name_edit = sample_name_edit
        self._external_save_dir_edit = save_dir_edit
        # 機器設定(機器選択・接続先)は「機器設定」ダイアログ(MainWindowのメニューバー経由)
        # から `apply_device_settings()` によって注入される。タブ内には入力欄を持たない。
        self._device_type = "keithley2400"
        self._connection = ""
        self._channel = "smua"
        self._use_mock = False
        self._build_ui()

        # ViewModelの保持と結線(結線はView側の責務。__init__から一度だけ行う)
        self.viewModel = viewModel or OPVViewModel()
        self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """ViewModelとの結線を行う。__init__から一度だけ呼ぶこと(二重結線防止)。"""
        self.opv_startButton.clicked.connect(self._on_start_clicked)
        self.opv_stopButton.clicked.connect(self._on_stop_clicked)

        # ViewModelからのシグナル購読
        self.viewModel.running_changed.connect(self._on_running_changed)
        self.viewModel.progress.connect(self.opv_progressBar.setValue)
        self.viewModel.point_measured.connect(self._on_point_measured)
        self.viewModel.log_appended.connect(self._append_log)
        self.viewModel.error_appended.connect(self._append_error_log)
        self.viewModel.error.connect(self._show_warning)
        self.viewModel.finished_ok.connect(self._on_finished_ok)

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
        opv_splitter.setSizes([420, 780])

    def _build_settings_panel(self) -> QtWidgets.QScrollArea:
        opv_settingsScrollArea = QtWidgets.QScrollArea(objectName="opv_settingsScrollArea")
        opv_settingsScrollArea.setWidgetResizable(True)
        opv_settingsScrollArea.setMinimumWidth(340)

        opv_settingsContainer = QtWidgets.QWidget(objectName="opv_settingsContainer")
        opv_settingsLayout = QtWidgets.QVBoxLayout(opv_settingsContainer)
        opv_settingsLayout.setObjectName("opv_settingsLayout")

        opv_settingsLayout.addWidget(self._build_measurement_group())
        opv_settingsLayout.addWidget(self._build_save_run_group())
        opv_settingsLayout.addStretch()

        opv_settingsScrollArea.setWidget(opv_settingsContainer)
        return opv_settingsScrollArea

    def _build_measurement_group(self) -> QtWidgets.QGroupBox:
        """接続設定・電圧掃引・タイミング/コンプライアンスを1つのGroupBoxに統合。"""
        opv_measurementGroupBox = QtWidgets.QGroupBox("測定設定", objectName="opv_measurementGroupBox")
        opv_measurementFormLayout = QtWidgets.QFormLayout(opv_measurementGroupBox)
        opv_measurementFormLayout.setObjectName("opv_measurementFormLayout")

        # 電圧掃引(Vmin/Vmax/Vstepを1行)
        self.opv_vMinSpin = NoScrollDoubleSpinBox(objectName="opv_vMinSpin")
        self.opv_vMinSpin.setRange(-20.0, 20.0)
        self.opv_vMinSpin.setDecimals(3)
        self.opv_vMinSpin.setSingleStep(0.01)
        self.opv_vMinSpin.setValue(-0.1)
        self.opv_vMinSpin.setMaximumWidth(80)

        self.opv_vMaxSpin = NoScrollDoubleSpinBox(objectName="opv_vMaxSpin")
        self.opv_vMaxSpin.setRange(-20.0, 20.0)
        self.opv_vMaxSpin.setDecimals(3)
        self.opv_vMaxSpin.setSingleStep(0.01)
        self.opv_vMaxSpin.setValue(1.1)
        self.opv_vMaxSpin.setMaximumWidth(80)

        self.opv_vStepSpin = NoScrollDoubleSpinBox(objectName="opv_vStepSpin")
        self.opv_vStepSpin.setRange(0.001, 10.0)
        self.opv_vStepSpin.setDecimals(3)
        self.opv_vStepSpin.setSingleStep(0.01)
        self.opv_vStepSpin.setValue(0.02)
        self.opv_vStepSpin.setMaximumWidth(80)

        opv_sweepRow = QtWidgets.QHBoxLayout()
        opv_sweepRow.setObjectName("opv_sweepRow")
        opv_sweepRow.addWidget(QtWidgets.QLabel("開始:"))
        opv_sweepRow.addWidget(self.opv_vMinSpin)
        opv_sweepRow.addWidget(QtWidgets.QLabel("終了:"))
        opv_sweepRow.addWidget(self.opv_vMaxSpin)
        opv_sweepRow.addWidget(QtWidgets.QLabel("ステップ:"))
        opv_sweepRow.addWidget(self.opv_vStepSpin)
        opv_measurementFormLayout.addRow("電圧掃引 (V):", opv_sweepRow)

        # 繰り返し回数 / NPLC(1行に統合)
        self.opv_iterationSpin = NoScrollSpinBox(objectName="opv_iterationSpin")
        self.opv_iterationSpin.setRange(1, 1000)
        self.opv_iterationSpin.setValue(3)
        self.opv_iterationSpin.setMaximumWidth(80)

        self.opv_nplcSpin = NoScrollDoubleSpinBox(objectName="opv_nplcSpin")
        self.opv_nplcSpin.setRange(0.01, 10.0)
        self.opv_nplcSpin.setDecimals(2)
        self.opv_nplcSpin.setSingleStep(0.1)
        self.opv_nplcSpin.setValue(1.0)
        self.opv_nplcSpin.setMaximumWidth(80)

        opv_iterationNplcRow = QtWidgets.QHBoxLayout()
        opv_iterationNplcRow.setObjectName("opv_iterationNplcRow")
        opv_iterationNplcRow.addWidget(QtWidgets.QLabel("繰り返し:"))
        opv_iterationNplcRow.addWidget(self.opv_iterationSpin)
        opv_iterationNplcRow.addWidget(QtWidgets.QLabel("NPLC:"))
        opv_iterationNplcRow.addWidget(self.opv_nplcSpin)
        opv_measurementFormLayout.addRow(opv_iterationNplcRow)

        # 遅延 / コンプライアンス(1行に統合)
        self.opv_delaySpin = NoScrollDoubleSpinBox(objectName="opv_delaySpin")
        self.opv_delaySpin.setRange(0.0, 60.0)
        self.opv_delaySpin.setDecimals(2)
        self.opv_delaySpin.setSingleStep(0.1)
        self.opv_delaySpin.setValue(1.0)
        self.opv_delaySpin.setMaximumWidth(80)

        self.opv_complianceSpin = NoScrollDoubleSpinBox(objectName="opv_complianceSpin")
        self.opv_complianceSpin.setRange(0.0001, 1.0)
        self.opv_complianceSpin.setDecimals(4)
        self.opv_complianceSpin.setSingleStep(0.001)
        self.opv_complianceSpin.setValue(0.02)
        self.opv_complianceSpin.setMaximumWidth(80)

        opv_delayComplianceRow = QtWidgets.QHBoxLayout()
        opv_delayComplianceRow.setObjectName("opv_delayComplianceRow")
        opv_delayComplianceRow.addWidget(QtWidgets.QLabel("遅延[s]:"))
        opv_delayComplianceRow.addWidget(self.opv_delaySpin)
        opv_delayComplianceRow.addWidget(QtWidgets.QLabel("コンプライアンス[A]:"))
        opv_delayComplianceRow.addWidget(self.opv_complianceSpin)
        opv_measurementFormLayout.addRow(opv_delayComplianceRow)

        return opv_measurementGroupBox

    def _build_save_run_group(self) -> QtWidgets.QGroupBox:
        """保存設定と実行ボタンを1つのGroupBoxに統合。"""
        opv_saveRunGroupBox = QtWidgets.QGroupBox("保存・実行", objectName="opv_saveRunGroupBox")
        opv_saveRunLayout = QtWidgets.QVBoxLayout(opv_saveRunGroupBox)
        opv_saveRunLayout.setObjectName("opv_saveRunLayout")

        opv_saveFormLayout = QtWidgets.QFormLayout()
        opv_saveFormLayout.setObjectName("opv_saveFormLayout")

        if self._external_sample_name_edit is not None:
            # 共通保存設定パネル(MainWindow側)のウィジェットをそのまま参照する。
            # タブ内には重複表示しない。
            self.opv_sampleNameEdit = self._external_sample_name_edit
        else:
            self.opv_sampleNameEdit = QtWidgets.QLineEdit(objectName="opv_sampleNameEdit")
            opv_saveFormLayout.addRow("サンプル名:", self.opv_sampleNameEdit)

        if self._external_save_dir_edit is not None:
            self.opv_saveDirEdit = self._external_save_dir_edit
        else:
            self.opv_saveDirEdit = QtWidgets.QLineEdit(objectName="opv_saveDirEdit")
            self.opv_browseSaveDirButton = QtWidgets.QPushButton(
                "参照...", objectName="opv_browseSaveDirButton"
            )
            self.opv_browseSaveDirButton.clicked.connect(self._on_browse_save_dir)

            opv_saveDirRow = QtWidgets.QHBoxLayout()
            opv_saveDirRow.setObjectName("opv_saveDirRow")
            opv_saveDirRow.addWidget(self.opv_saveDirEdit)
            opv_saveDirRow.addWidget(self.opv_browseSaveDirButton)
            opv_saveFormLayout.addRow("保存先:", opv_saveDirRow)

        opv_saveRunLayout.addLayout(opv_saveFormLayout)

        self.opv_startButton = QtWidgets.QPushButton("測定開始", objectName="opv_startButton")
        self.opv_stopButton = QtWidgets.QPushButton("中断", objectName="opv_stopButton")
        self.opv_stopButton.setEnabled(False)

        opv_runRow = QtWidgets.QHBoxLayout()
        opv_runRow.setObjectName("opv_runRow")
        opv_runRow.addWidget(self.opv_startButton)
        opv_runRow.addWidget(self.opv_stopButton)
        opv_saveRunLayout.addLayout(opv_runRow)

        return opv_saveRunGroupBox

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
    # UI値からのConfig構築
    # ------------------------------------------------------------------
    def apply_device_settings(
        self, device_type: str, connection: str, channel: str = "smua", use_mock: bool = False
    ) -> None:
        """機器設定ダイアログ(``DeviceSettingsDialog``)で確定した設定値を適用する。"""
        self._device_type = device_type
        self._connection = connection
        self._channel = channel
        self._use_mock = use_mock

    def _build_config(self) -> OPVConfig:
        return OPVConfig(
            device_type=self._device_type,
            connection=self._connection,
            use_mock=self._use_mock,
            v_min=self.opv_vMinSpin.value(),
            v_max=self.opv_vMaxSpin.value(),
            v_step=self.opv_vStepSpin.value(),
            iteration=self.opv_iterationSpin.value(),
            compliance_current=self.opv_complianceSpin.value(),
            nplc=self.opv_nplcSpin.value(),
            delay_time=self.opv_delaySpin.value(),
            sample_name=self.opv_sampleNameEdit.text().strip() or "sample",
            save_dir=self.opv_saveDirEdit.text().strip() or ".",
            channel=self._channel,
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        config = self._build_config()
        total_points = len(config.build_voltage_list())
        self.opv_progressBar.setMaximum(max(total_points, 1))
        self.opv_progressBar.setValue(0)
        self._plot_buffer = PlotBuffer(self.opv_plotWidget)
        self.viewModel.start_measurement(config)

    def _on_stop_clicked(self) -> None:
        self.viewModel.stop_measurement()

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ
    # ------------------------------------------------------------------
    def _on_running_changed(self, running: bool) -> None:
        self.opv_startButton.setEnabled(not running)
        self.opv_stopButton.setEnabled(running)

    def _on_point_measured(self, point) -> None:
        if self._plot_buffer is not None:
            self._plot_buffer.add_point(point.voltage, point.current)

    def _append_log(self, message: str) -> None:
        self.opv_logTextEdit.append(message)

    def _append_error_log(self, message: str) -> None:
        self.opv_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok(self, points: list, csv_path: str) -> None:
        pass

    def _on_browse_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.opv_saveDirEdit.setText(directory)
