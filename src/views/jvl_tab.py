"""JVLモード(発光素子 IV-輝度測定 / 暗IV測定共通)タブのView。

B-6-2節「JVLタブ（jvl_tab.ui）」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。
OPVタブと同一構成に加え、輝度計(BM9)グループと2ページ構成のプロットタブを持つ。
"""
from __future__ import annotations

import pyqtgraph as pg

from qtcompat import Qt, QtWidgets, enum_value
from models.measurement.config import JVLConfig
from viewmodels.jvl_viewmodel import JVLViewModel
from views.plot_buffer import PlotBuffer, DualAxisPlotBuffer
from views.widgets.no_scroll_spinbox import NoScrollDoubleSpinBox, NoScrollSpinBox


class JVLTab(QtWidgets.QWidget):
    """JVLモードタブ(JVLTabForm相当)。"""

    def __init__(
        self,
        parent=None,
        viewModel: JVLViewModel = None,
        sample_name_edit: QtWidgets.QLineEdit = None,
        save_dir_edit: QtWidgets.QLineEdit = None,
    ):
        super().__init__(parent)
        self.setObjectName("JVLTabForm")
        self._iv_plot_buffer = None
        self._ivl_plot_buffer = None
        self._external_sample_name_edit = sample_name_edit
        self._external_save_dir_edit = save_dir_edit
        # 機器設定(機器選択・接続先・輝度計ポート)は「機器設定」ダイアログ
        # (MainWindowのメニューバー経由)から `apply_device_settings()` によって
        # 注入される。タブ内には入力欄を持たない。
        self._device_type = "keithley2400"
        self._connection = ""
        self._bm9_port = ""
        self._channel = "smua"
        self._use_mock = False
        self._build_ui()

        # ViewModelの保持と結線(結線はView側の責務。__init__から一度だけ行う)
        self.viewModel = viewModel or JVLViewModel()
        self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """ViewModelとの結線を行う。__init__から一度だけ呼ぶこと(二重結線防止)。"""
        self.jvl_startButton.clicked.connect(self._on_start_clicked)
        self.jvl_stopButton.clicked.connect(self._on_stop_clicked)

        # ViewModelからのシグナル購読
        self.viewModel.running_changed.connect(self._on_running_changed)
        self.viewModel.progress.connect(self.jvl_progressBar.setValue)
        self.viewModel.point_measured.connect(self._on_point_measured)
        self.viewModel.log_appended.connect(self._append_log)
        self.viewModel.error_appended.connect(self._append_error_log)
        self.viewModel.error.connect(self._show_warning)
        self.viewModel.finished_ok.connect(self._on_finished_ok)

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

        jvl_settingsLayout.addWidget(self._build_measurement_group())
        jvl_settingsLayout.addWidget(self._build_save_run_group())
        jvl_settingsLayout.addStretch()

        jvl_settingsScrollArea.setWidget(jvl_settingsContainer)
        return jvl_settingsScrollArea

    def _build_measurement_group(self) -> QtWidgets.QGroupBox:
        """接続設定・電圧掃引・タイミング/コンプライアンス・輝度計設定を1つのGroupBoxに統合。"""
        jvl_measurementGroupBox = QtWidgets.QGroupBox("測定設定", objectName="jvl_measurementGroupBox")
        jvl_measurementFormLayout = QtWidgets.QFormLayout(jvl_measurementGroupBox)
        jvl_measurementFormLayout.setObjectName("jvl_measurementFormLayout")

        # 電圧掃引(Vmin/Vmax/Vstepを1行)
        self.jvl_vMinSpin = NoScrollDoubleSpinBox(objectName="jvl_vMinSpin")
        self.jvl_vMinSpin.setRange(-20.0, 20.0)
        self.jvl_vMinSpin.setDecimals(3)
        self.jvl_vMinSpin.setSingleStep(0.1)
        self.jvl_vMinSpin.setValue(-1.0)
        self.jvl_vMinSpin.setMaximumWidth(80)

        self.jvl_vMaxSpin = NoScrollDoubleSpinBox(objectName="jvl_vMaxSpin")
        self.jvl_vMaxSpin.setRange(-20.0, 20.0)
        self.jvl_vMaxSpin.setDecimals(3)
        self.jvl_vMaxSpin.setSingleStep(0.1)
        self.jvl_vMaxSpin.setValue(1.9)
        self.jvl_vMaxSpin.setMaximumWidth(80)

        self.jvl_vStepSpin = NoScrollDoubleSpinBox(objectName="jvl_vStepSpin")
        self.jvl_vStepSpin.setRange(0.001, 10.0)
        self.jvl_vStepSpin.setDecimals(3)
        self.jvl_vStepSpin.setSingleStep(0.01)
        self.jvl_vStepSpin.setValue(0.1)
        self.jvl_vStepSpin.setMaximumWidth(80)

        jvl_sweepRow = QtWidgets.QHBoxLayout()
        jvl_sweepRow.setObjectName("jvl_sweepRow")
        jvl_sweepRow.addWidget(QtWidgets.QLabel("開始:"))
        jvl_sweepRow.addWidget(self.jvl_vMinSpin)
        jvl_sweepRow.addWidget(QtWidgets.QLabel("終了:"))
        jvl_sweepRow.addWidget(self.jvl_vMaxSpin)
        jvl_sweepRow.addWidget(QtWidgets.QLabel("ステップ:"))
        jvl_sweepRow.addWidget(self.jvl_vStepSpin)
        jvl_measurementFormLayout.addRow("電圧掃引 (V):", jvl_sweepRow)

        # 繰り返し回数 / NPLC(1行に統合)
        self.jvl_iterationSpin = NoScrollSpinBox(objectName="jvl_iterationSpin")
        self.jvl_iterationSpin.setRange(1, 1000)
        self.jvl_iterationSpin.setValue(3)
        self.jvl_iterationSpin.setMaximumWidth(80)

        self.jvl_nplcSpin = NoScrollDoubleSpinBox(objectName="jvl_nplcSpin")
        self.jvl_nplcSpin.setRange(0.01, 10.0)
        self.jvl_nplcSpin.setDecimals(2)
        self.jvl_nplcSpin.setSingleStep(0.1)
        self.jvl_nplcSpin.setValue(1.0)
        self.jvl_nplcSpin.setMaximumWidth(80)

        jvl_iterationNplcRow = QtWidgets.QHBoxLayout()
        jvl_iterationNplcRow.setObjectName("jvl_iterationNplcRow")
        jvl_iterationNplcRow.addWidget(QtWidgets.QLabel("繰り返し:"))
        jvl_iterationNplcRow.addWidget(self.jvl_iterationSpin)
        jvl_iterationNplcRow.addWidget(QtWidgets.QLabel("NPLC:"))
        jvl_iterationNplcRow.addWidget(self.jvl_nplcSpin)
        jvl_measurementFormLayout.addRow(jvl_iterationNplcRow)

        # 遅延 / コンプライアンス(1行に統合)
        self.jvl_delaySpin = NoScrollDoubleSpinBox(objectName="jvl_delaySpin")
        self.jvl_delaySpin.setRange(0.0, 60.0)
        self.jvl_delaySpin.setDecimals(2)
        self.jvl_delaySpin.setSingleStep(0.1)
        self.jvl_delaySpin.setValue(1.0)
        self.jvl_delaySpin.setMaximumWidth(80)

        self.jvl_complianceSpin = NoScrollDoubleSpinBox(objectName="jvl_complianceSpin")
        self.jvl_complianceSpin.setRange(0.0001, 1.0)
        self.jvl_complianceSpin.setDecimals(4)
        self.jvl_complianceSpin.setSingleStep(0.001)
        self.jvl_complianceSpin.setValue(0.02)
        self.jvl_complianceSpin.setMaximumWidth(80)

        jvl_delayComplianceRow = QtWidgets.QHBoxLayout()
        jvl_delayComplianceRow.setObjectName("jvl_delayComplianceRow")
        jvl_delayComplianceRow.addWidget(QtWidgets.QLabel("遅延[s]:"))
        jvl_delayComplianceRow.addWidget(self.jvl_delaySpin)
        jvl_delayComplianceRow.addWidget(QtWidgets.QLabel("コンプライアンス[A]:"))
        jvl_delayComplianceRow.addWidget(self.jvl_complianceSpin)
        jvl_measurementFormLayout.addRow(jvl_delayComplianceRow)

        # 輝度計(BM9)設定(測定設定グループ内に統合。BM9ポート自体は「機器設定」
        # ダイアログへ移動済みのため、輝度計測有無のチェックボックスのみ残す)
        self.jvl_useLuminanceCheckBox = QtWidgets.QCheckBox(
            "BM9で輝度も測定する(OFFで暗IV測定)", objectName="jvl_useLuminanceCheckBox"
        )
        self.jvl_useLuminanceCheckBox.setChecked(True)
        jvl_measurementFormLayout.addRow("輝度計(BM9):", self.jvl_useLuminanceCheckBox)

        return jvl_measurementGroupBox

    def _build_save_run_group(self) -> QtWidgets.QGroupBox:
        """保存設定と実行ボタンを1つのGroupBoxに統合。"""
        jvl_saveRunGroupBox = QtWidgets.QGroupBox("保存・実行", objectName="jvl_saveRunGroupBox")
        jvl_saveRunLayout = QtWidgets.QVBoxLayout(jvl_saveRunGroupBox)
        jvl_saveRunLayout.setObjectName("jvl_saveRunLayout")

        jvl_saveFormLayout = QtWidgets.QFormLayout()
        jvl_saveFormLayout.setObjectName("jvl_saveFormLayout")

        if self._external_sample_name_edit is not None:
            # 共通保存設定パネル(MainWindow側)のウィジェットをそのまま参照する。
            # タブ内には重複表示しない。
            self.jvl_sampleNameEdit = self._external_sample_name_edit
        else:
            self.jvl_sampleNameEdit = QtWidgets.QLineEdit(objectName="jvl_sampleNameEdit")
            jvl_saveFormLayout.addRow("サンプル名:", self.jvl_sampleNameEdit)

        if self._external_save_dir_edit is not None:
            self.jvl_saveDirEdit = self._external_save_dir_edit
        else:
            self.jvl_saveDirEdit = QtWidgets.QLineEdit(objectName="jvl_saveDirEdit")
            self.jvl_browseSaveDirButton = QtWidgets.QPushButton(
                "参照...", objectName="jvl_browseSaveDirButton"
            )
            self.jvl_browseSaveDirButton.clicked.connect(self._on_browse_save_dir)

            jvl_saveDirRow = QtWidgets.QHBoxLayout()
            jvl_saveDirRow.setObjectName("jvl_saveDirRow")
            jvl_saveDirRow.addWidget(self.jvl_saveDirEdit)
            jvl_saveDirRow.addWidget(self.jvl_browseSaveDirButton)
            jvl_saveFormLayout.addRow("保存先:", jvl_saveDirRow)

        jvl_saveRunLayout.addLayout(jvl_saveFormLayout)

        self.jvl_startButton = QtWidgets.QPushButton("測定開始", objectName="jvl_startButton")
        self.jvl_stopButton = QtWidgets.QPushButton("中断", objectName="jvl_stopButton")
        self.jvl_stopButton.setEnabled(False)

        jvl_runRow = QtWidgets.QHBoxLayout()
        jvl_runRow.setObjectName("jvl_runRow")
        jvl_runRow.addWidget(self.jvl_startButton)
        jvl_runRow.addWidget(self.jvl_stopButton)
        jvl_saveRunLayout.addLayout(jvl_runRow)

        return jvl_saveRunGroupBox

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
    # UI値からのConfig構築
    # ------------------------------------------------------------------
    def apply_device_settings(
        self,
        device_type: str,
        connection: str,
        bm9_port: str,
        channel: str = "smua",
        use_mock: bool = False,
    ) -> None:
        """機器設定ダイアログ(``DeviceSettingsDialog``)で確定した設定値を適用する。"""
        self._device_type = device_type
        self._connection = connection
        self._bm9_port = bm9_port
        self._channel = channel
        self._use_mock = use_mock

    def _build_config(self) -> JVLConfig:
        use_luminance = self.jvl_useLuminanceCheckBox.isChecked()
        bm9_port = self._bm9_port if use_luminance else None
        return JVLConfig(
            device_type=self._device_type,
            connection=self._connection,
            use_mock=self._use_mock,
            v_min=self.jvl_vMinSpin.value(),
            v_max=self.jvl_vMaxSpin.value(),
            v_step=self.jvl_vStepSpin.value(),
            iteration=self.jvl_iterationSpin.value(),
            compliance_current=self.jvl_complianceSpin.value(),
            nplc=self.jvl_nplcSpin.value(),
            delay_time=self.jvl_delaySpin.value(),
            sample_name=self.jvl_sampleNameEdit.text().strip() or "sample",
            save_dir=self.jvl_saveDirEdit.text().strip() or ".",
            use_luminance=use_luminance,
            bm9_port=bm9_port,
            channel=self._channel,
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        config = self._build_config()
        total_points = len(config.build_voltage_list())
        self.jvl_progressBar.setMaximum(max(total_points, 1))
        self.jvl_progressBar.setValue(0)
        self._iv_plot_buffer = PlotBuffer(self.jvl_ivPlotWidget)
        self._ivl_plot_buffer = DualAxisPlotBuffer(self.jvl_ivlPlotWidget)
        self.viewModel.start_measurement(config)

    def _on_stop_clicked(self) -> None:
        self.viewModel.stop_measurement()

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ
    # ------------------------------------------------------------------
    def _on_running_changed(self, running: bool) -> None:
        self.jvl_startButton.setEnabled(not running)
        self.jvl_stopButton.setEnabled(running)
        self.jvl_useLuminanceCheckBox.setEnabled(not running)

    def _on_point_measured(self, point) -> None:
        luminance = getattr(point, "luminance", None)
        if self._iv_plot_buffer is not None:
            self._iv_plot_buffer.add_point(point.voltage, point.current)
        if self._ivl_plot_buffer is not None:
            self._ivl_plot_buffer.add_point(point.voltage, point.current, luminance)

    def _append_log(self, message: str) -> None:
        self.jvl_logTextEdit.append(message)

    def _append_error_log(self, message: str) -> None:
        self.jvl_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok(self, points: list, csv_path: str) -> None:
        pass

    def _on_browse_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.jvl_saveDirEdit.setText(directory)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # I-V-Lグラフの右軸ViewBoxの位置同期
        if hasattr(self, "jvl_ivlPlotWidget") and hasattr(self.jvl_ivlPlotWidget, "luminance_viewbox"):
            self.jvl_ivlPlotWidget.luminance_viewbox.setGeometry(
                self.jvl_ivlPlotWidget.getViewBox().sceneBoundingRect()
            )
