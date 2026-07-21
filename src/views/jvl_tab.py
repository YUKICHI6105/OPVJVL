"""JVLモード(発光素子 IV-輝度測定 / 暗IV測定共通)タブのView。

B-6-2節「JVLタブ（jvl_tab.ui）」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。
OPVタブと同一構成に加え、輝度計(BM9)グループと2ページ構成のプロットタブを持つ。
"""
from __future__ import annotations

import os

import pyqtgraph as pg

from qtcompat import QtWidgets
from models.measurement.config import JVLConfig
from models.measurement.csv_writer import jvl_csv_filename, save_points_csv
from viewmodels.jvl_viewmodel import JVLViewModel
from views import tab_layout
from views.notify_sound import play_completion_sound
from views.plot_buffer import (
    DualAxisPlotBuffer,
    PlotBuffer,
    install_auto_range_menu,
    set_iv_axis_labels,
    setup_luminance_axis,
)
from views.save_confirm import confirm_overwrite, ensure_save_dir


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
        self._last_result = None  # (points, include_luminance) 最後に完了/中断した測定結果
        self._contact_check_running = False
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

        # 接触確認(JVL式)
        self.jvl_contactCheckButton.clicked.connect(self._on_contact_check_clicked)
        self.viewModel.contact_check_running_changed.connect(self._on_contact_check_running_changed)
        self.viewModel.contact_check_reading.connect(self._on_contact_check_reading)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """共通レイアウトビルダー(views/tab_layout.py)でタブを構築する。

        OPVタブと同一のコードパスを通すことで、レイアウト差の発生を
        構造的に防ぐ(review.md指摘#3)。JVL固有の輝度計チェックボックスは
        ``extra_rows`` フックで測定設定グループ末尾へ差し込む。左右分割は
        メインウィンドウ直下のQSplitterが担うため(review.md指摘#1)、このタブ
        自身は設定カラムの中身だけを持ち、表示パネル/ログはMainWindowへ
        ``display_panel()``/``log_widget()``経由で渡す。
        """
        # JVL固有: 輝度計(BM9)チェックボックス(BM9ポート自体は「機器設定」
        # ダイアログへ移動済みのため、輝度計測有無のチェックボックスのみ持つ)
        self.jvl_useLuminanceCheckBox = QtWidgets.QCheckBox(
            "BM9で輝度も測定する(OFFで暗IV測定)", objectName="jvl_useLuminanceCheckBox"
        )
        self.jvl_useLuminanceCheckBox.setChecked(True)

        def _add_luminance_row(form_layout: QtWidgets.QFormLayout) -> None:
            form_layout.addRow("輝度計(BM9):", self.jvl_useLuminanceCheckBox)

        # 測定設定グループ(JVL固有の初期値のみ指定。行構成はOPVと共通)
        jvl_measurementGroupBox, measurement_widgets = tab_layout.build_measurement_group(
            "jvl", v_min_default=-1.0, v_max_default=1.9, v_step_default=0.1,
            sweep_single_step=0.1, extra_rows=_add_luminance_row,
        )
        self.jvl_vMinSpin = measurement_widgets["v_min"]
        self.jvl_vMaxSpin = measurement_widgets["v_max"]
        self.jvl_vStepSpin = measurement_widgets["v_step"]
        self.jvl_iterationSpin = measurement_widgets["iteration"]
        self.jvl_nplcSpin = measurement_widgets["nplc"]
        self.jvl_delaySpin = measurement_widgets["delay"]
        self.jvl_complianceSpin = measurement_widgets["compliance"]
        self.jvl_hysteresisCheckBox = measurement_widgets["hysteresis"]

        # 保存・実行グループ
        jvl_saveRunGroupBox, save_run_widgets = tab_layout.build_save_run_group(
            "jvl",
            self._external_sample_name_edit,
            self._external_save_dir_edit,
            self._on_browse_save_dir,
        )
        self.jvl_sampleNameEdit = save_run_widgets["sample_name"]
        self.jvl_saveDirEdit = save_run_widgets["save_dir"]
        self.jvl_startButton = save_run_widgets["start"]
        self.jvl_stopButton = save_run_widgets["stop"]
        if save_run_widgets["browse"] is not None:
            self.jvl_browseSaveDirButton = save_run_widgets["browse"]

        # 接触確認(JVL式: 0Vから昇圧し、電流閾値到達後はその電圧を維持し続け、
        # 停止ボタンで止めるまで保持する。v_maxは素子保護のための安全上限電圧)
        self.jvl_contactCheckThresholdSpin = tab_layout.make_double_spin(
            "jvl_contactCheckThresholdSpin", 0.0001, 1.0, 4, 0.0001, 0.001, "A"
        )
        self.jvl_contactCheckVMaxSpin = tab_layout.make_double_spin(
            "jvl_contactCheckVMaxSpin", 0.1, 20.0, 2, 0.1, 5.0, "V"
        )
        self.jvl_contactCheckButton = QtWidgets.QPushButton(
            "接触確認", objectName="jvl_contactCheckButton"
        )
        self.jvl_contactCheckReadingLabel = QtWidgets.QLabel(
            "電流: -", objectName="jvl_contactCheckReadingLabel"
        )
        jvl_contactCheckFormLayout = QtWidgets.QFormLayout()
        jvl_contactCheckFormLayout.setObjectName("jvl_contactCheckFormLayout")
        jvl_contactCheckRow = QtWidgets.QHBoxLayout()
        jvl_contactCheckRow.setObjectName("jvl_contactCheckRow")
        jvl_contactCheckRow.addWidget(QtWidgets.QLabel("電流閾値[A]:"))
        jvl_contactCheckRow.addWidget(self.jvl_contactCheckThresholdSpin)
        jvl_contactCheckRow.addWidget(QtWidgets.QLabel("最大電圧[V]:"))
        jvl_contactCheckRow.addWidget(self.jvl_contactCheckVMaxSpin)
        jvl_contactCheckFormLayout.addRow("接触確認:", jvl_contactCheckRow)
        jvl_saveRunGroupBox.layout().addLayout(jvl_contactCheckFormLayout)
        jvl_saveRunGroupBox.layout().addWidget(self.jvl_contactCheckButton)
        jvl_saveRunGroupBox.layout().addWidget(self.jvl_contactCheckReadingLabel)

        # 表示パネル側のウィジェット(JVLは2ページ構成のプロットタブ)
        self.jvl_progressBar = QtWidgets.QProgressBar(objectName="jvl_progressBar")
        self.jvl_progressBar.setValue(0)

        self.jvl_plotTabWidget = QtWidgets.QTabWidget(objectName="jvl_plotTabWidget")

        self.jvl_ivPlotWidget = pg.PlotWidget()
        self.jvl_ivPlotWidget.setObjectName("jvl_ivPlotWidget")
        set_iv_axis_labels(self.jvl_ivPlotWidget)
        self.jvl_ivPlotWidget.showGrid(x=True, y=True, alpha=0.2)
        install_auto_range_menu(self.jvl_ivPlotWidget)
        self.jvl_plotTabWidget.addTab(self.jvl_ivPlotWidget, "I-V")

        self.jvl_ivlPlotWidget = pg.PlotWidget()
        self.jvl_ivlPlotWidget.setObjectName("jvl_ivlPlotWidget")
        set_iv_axis_labels(self.jvl_ivlPlotWidget)
        self.jvl_ivlPlotWidget.showGrid(x=True, y=True, alpha=0.2)
        setup_luminance_axis(self.jvl_ivlPlotWidget)
        install_auto_range_menu(self.jvl_ivlPlotWidget)
        self.jvl_plotTabWidget.addTab(self.jvl_ivlPlotWidget, "I-V-L")

        self.jvl_logTextEdit = QtWidgets.QTextEdit(objectName="jvl_logTextEdit")
        self.jvl_logTextEdit.setReadOnly(True)

        tab_layout.build_settings_column(
            self, "jvl", settings_groups=[jvl_measurementGroupBox, jvl_saveRunGroupBox]
        )
        self._display_panel = tab_layout.build_display_panel(
            "jvl", self.jvl_plotTabWidget, self.jvl_progressBar
        )

    def display_panel(self) -> QtWidgets.QWidget:
        """MainWindow右カラム(displayStack)に積む表示パネル(進捗バー+グラフ)。"""
        return self._display_panel

    def log_widget(self) -> QtWidgets.QWidget:
        """MainWindow左カラムの「ログ」グループ(logStack)に積むログ表示。"""
        return self.jvl_logTextEdit

    def plot_widgets(self) -> list:
        """このタブが保有する全プロットウィジェット(グラフ表示設定の適用対象)。"""
        return [self.jvl_ivPlotWidget, self.jvl_ivlPlotWidget]

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
            hysteresis=self.jvl_hysteresisCheckBox.isChecked(),
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        if not ensure_save_dir(self, self.jvl_saveDirEdit):
            return
        config = self._build_config()
        planned_path = os.path.join(config.save_dir, jvl_csv_filename(config.sample_name))
        if not confirm_overwrite(self, [planned_path]):
            return
        total_points = len(config.build_voltage_list())
        self.jvl_progressBar.setMaximum(max(total_points, 1))
        self.jvl_progressBar.setValue(0)
        reverse_from_index = config.forward_point_count() if config.hysteresis else None
        # review.md指摘#6: JVLタブのみ凡例名を指定して凡例を表示する
        self._iv_plot_buffer = PlotBuffer(
            self.jvl_ivPlotWidget, curve_name="Current", reverse_from_index=reverse_from_index
        )
        self._ivl_plot_buffer = DualAxisPlotBuffer(
            self.jvl_ivlPlotWidget,
            current_name="Current",
            luminance_name="Luminance",
            reverse_from_index=reverse_from_index,
        )
        self.viewModel.start_measurement(config)

    def _on_stop_clicked(self) -> None:
        self.viewModel.stop_measurement()

    def _on_contact_check_clicked(self) -> None:
        if self._contact_check_running:
            self.viewModel.stop_contact_check()
        else:
            self.viewModel.start_contact_check(
                self._device_type,
                self._connection,
                self._channel,
                self._use_mock,
                self.jvl_complianceSpin.value(),
                self.jvl_nplcSpin.value(),
                self.jvl_contactCheckThresholdSpin.value(),
                self.jvl_contactCheckVMaxSpin.value(),
            )

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ
    # ------------------------------------------------------------------
    def _on_running_changed(self, running: bool) -> None:
        self.jvl_startButton.setEnabled(not running)
        self.jvl_stopButton.setEnabled(running)
        self.jvl_useLuminanceCheckBox.setEnabled(not running)
        self.jvl_hysteresisCheckBox.setEnabled(not running)
        if not self._contact_check_running:
            self.jvl_contactCheckButton.setEnabled(not running)

    def _on_contact_check_running_changed(self, running: bool) -> None:
        self._contact_check_running = running
        self.jvl_contactCheckButton.setText("接触確認を停止" if running else "接触確認")
        self.jvl_contactCheckButton.setEnabled(True)
        if not running:
            self.jvl_contactCheckReadingLabel.setText("電流: -")
        self.jvl_startButton.setEnabled(not running)

    def _on_contact_check_reading(self, voltage: float, current: float) -> None:
        self.jvl_contactCheckReadingLabel.setText(f"電流: {current:.6e} A (V={voltage:.3f})")

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

    def _on_finished_ok(self, points: list, csv_path: str, aborted: bool) -> None:
        self._last_result = (points, self.jvl_useLuminanceCheckBox.isChecked())
        play_completion_sound("aborted" if aborted else "success")

    # ------------------------------------------------------------------
    # 別名保存(ファイルメニュー「測定データを別名保存...」/Ctrl+S)
    # ------------------------------------------------------------------
    def save_last_result_as(self, parent=None) -> None:
        """最後に完了/中断した測定結果を任意のファイル名でCSV保存する。"""
        if not self._last_result:
            QtWidgets.QMessageBox.information(
                parent or self, "情報", "保存できる測定結果がありません。"
            )
            return
        points, include_luminance = self._last_result
        sample_name = self.jvl_sampleNameEdit.text().strip() or "sample"
        save_dir = self.jvl_saveDirEdit.text().strip() or "."
        default_path = os.path.join(save_dir, jvl_csv_filename(sample_name))
        path, _filter = QtWidgets.QFileDialog.getSaveFileName(
            parent or self, "測定データを別名保存", default_path, "CSV Files (*.csv)"
        )
        if not path:
            return
        save_points_csv(points, path, include_luminance)
        self._append_log(f"測定データを保存しました: {path}")

    # ------------------------------------------------------------------
    # 設定の永続化(MainWindowが起動時restore/終了時saveに使用)
    # ------------------------------------------------------------------
    def persistent_widgets(self) -> dict:
        """永続化対象の設定キーとウィジェットの対応表を返す。

        キー名は ``utils.persistence.MEASUREMENT_SETTINGS_DEFAULTS`` と一致させる。
        """
        return {
            "jvl_v_min": self.jvl_vMinSpin,
            "jvl_v_max": self.jvl_vMaxSpin,
            "jvl_v_step": self.jvl_vStepSpin,
            "jvl_iteration": self.jvl_iterationSpin,
            "jvl_nplc": self.jvl_nplcSpin,
            "jvl_delay": self.jvl_delaySpin,
            "jvl_compliance": self.jvl_complianceSpin,
            "jvl_use_luminance": self.jvl_useLuminanceCheckBox,
            "jvl_hysteresis": self.jvl_hysteresisCheckBox,
            "jvl_contact_check_threshold": self.jvl_contactCheckThresholdSpin,
            "jvl_contact_check_v_max": self.jvl_contactCheckVMaxSpin,
        }

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
