"""OPVモード(太陽電池 JV/IV特性測定)タブのView。

B-6-2節「OPVタブ（opv_tab.ui）階層」のウィジェットツリー・objectName命名規則に
厳密に従い、Pythonコードでウィジェットツリーを構築する。
"""
from __future__ import annotations

import os

import pyqtgraph as pg

from qtcompat import QtWidgets
from models.measurement.config import OPVConfig
from models.measurement.csv_writer import opv_csv_filename, save_points_csv
from viewmodels.opv_viewmodel import OPVViewModel
from views import tab_layout
from views.notify_sound import play_completion_sound
from views.plot_buffer import PlotBuffer, install_auto_range_menu, set_iv_axis_labels
from views.save_confirm import confirm_overwrite, ensure_save_dir


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
        self._last_result = None  # (points, include_luminance) 最後に完了/中断した測定結果
        self._contact_check_running = False
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

        # 接触確認(OPV式)
        self.opv_contactCheckButton.clicked.connect(self._on_contact_check_clicked)
        self.viewModel.contact_check_running_changed.connect(self._on_contact_check_running_changed)
        self.viewModel.contact_check_reading.connect(self._on_contact_check_reading)

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """共通レイアウトビルダー(views/tab_layout.py)でタブを構築する。

        JVLタブと同一のコードパスを通すことで、レイアウト差の発生を
        構造的に防ぐ(review.md指摘#3)。左右分割はメインウィンドウ直下の
        QSplitterが担うため(review.md指摘#1)、このタブ自身は設定カラムの
        中身だけを持ち、表示パネル/ログはMainWindowへ``display_panel()``/
        ``log_widget()``経由で渡す。
        """
        # 測定設定グループ(OPV固有の初期値のみ指定。行構成はJVLと共通)
        opv_measurementGroupBox, measurement_widgets = tab_layout.build_measurement_group(
            "opv", v_min_default=-0.1, v_max_default=1.1, v_step_default=0.02,
            sweep_single_step=0.01,
        )
        self.opv_vMinSpin = measurement_widgets["v_min"]
        self.opv_vMaxSpin = measurement_widgets["v_max"]
        self.opv_vStepSpin = measurement_widgets["v_step"]
        self.opv_iterationSpin = measurement_widgets["iteration"]
        self.opv_nplcSpin = measurement_widgets["nplc"]
        self.opv_delaySpin = measurement_widgets["delay"]
        self.opv_complianceSpin = measurement_widgets["compliance"]
        self.opv_hysteresisCheckBox = measurement_widgets["hysteresis"]

        # 保存・実行グループ
        opv_saveRunGroupBox, save_run_widgets = tab_layout.build_save_run_group(
            "opv",
            self._external_sample_name_edit,
            self._external_save_dir_edit,
            self._on_browse_save_dir,
        )
        self.opv_sampleNameEdit = save_run_widgets["sample_name"]
        self.opv_saveDirEdit = save_run_widgets["save_dir"]
        self.opv_startButton = save_run_widgets["start"]
        self.opv_stopButton = save_run_widgets["stop"]
        if save_run_widgets["browse"] is not None:
            self.opv_browseSaveDirButton = save_run_widgets["browse"]

        # 接触確認(OPV式: 0V印加を継続し電流を表示するトグル動作)
        self.opv_contactCheckButton = QtWidgets.QPushButton(
            "接触確認", objectName="opv_contactCheckButton"
        )
        self.opv_contactCheckReadingLabel = QtWidgets.QLabel(
            "電流: -", objectName="opv_contactCheckReadingLabel"
        )
        opv_saveRunGroupBox.layout().addWidget(self.opv_contactCheckButton)
        opv_saveRunGroupBox.layout().addWidget(self.opv_contactCheckReadingLabel)

        # 表示パネル側のウィジェット
        self.opv_progressBar = QtWidgets.QProgressBar(objectName="opv_progressBar")
        self.opv_progressBar.setValue(0)
        self.opv_plotWidget = pg.PlotWidget()
        self.opv_plotWidget.setObjectName("opv_plotWidget")
        set_iv_axis_labels(self.opv_plotWidget)
        install_auto_range_menu(self.opv_plotWidget)
        self.opv_logTextEdit = QtWidgets.QTextEdit(objectName="opv_logTextEdit")
        self.opv_logTextEdit.setReadOnly(True)

        tab_layout.build_settings_column(
            self, "opv", settings_groups=[opv_measurementGroupBox, opv_saveRunGroupBox]
        )
        self._display_panel = tab_layout.build_display_panel(
            "opv", self.opv_plotWidget, self.opv_progressBar
        )

    def display_panel(self) -> QtWidgets.QWidget:
        """MainWindow右カラム(displayStack)に積む表示パネル(進捗バー+グラフ)。"""
        return self._display_panel

    def log_widget(self) -> QtWidgets.QWidget:
        """MainWindow左カラムの「ログ」グループ(logStack)に積むログ表示。"""
        return self.opv_logTextEdit

    def plot_widgets(self) -> list:
        """このタブが保有する全プロットウィジェット(グラフ表示設定の適用対象)。"""
        return [self.opv_plotWidget]

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
            hysteresis=self.opv_hysteresisCheckBox.isChecked(),
        )

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------
    def _on_start_clicked(self) -> None:
        if not ensure_save_dir(self, self.opv_saveDirEdit):
            return
        config = self._build_config()
        planned_path = os.path.join(config.save_dir, opv_csv_filename(config.sample_name))
        if not confirm_overwrite(self, [planned_path]):
            return
        total_points = len(config.build_voltage_list())
        self.opv_progressBar.setMaximum(max(total_points, 1))
        self.opv_progressBar.setValue(0)
        reverse_from_index = config.forward_point_count() if config.hysteresis else None
        self._plot_buffer = PlotBuffer(self.opv_plotWidget, reverse_from_index=reverse_from_index)
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
                self.opv_complianceSpin.value(),
                self.opv_nplcSpin.value(),
            )

    # ------------------------------------------------------------------
    # ViewModelからのシグナル受信ハンドラ
    # ------------------------------------------------------------------
    def _on_running_changed(self, running: bool) -> None:
        # running_changedは本測定と接触確認の両方から発火される共有シグナル
        # (MainWindow側のクロスタブ排他ロックが流用するため)。本測定用の
        # start/stopボタン制御は、接触確認自身によるrunning=Trueでも意味を
        # 持つため素直に反映してよいが、接触確認ボタン自体は自身の状態
        # (_contact_check_running)でのみ制御し、ここでは触れない。
        self.opv_startButton.setEnabled(not running)
        self.opv_stopButton.setEnabled(running)
        self.opv_hysteresisCheckBox.setEnabled(not running)
        if not self._contact_check_running:
            self.opv_contactCheckButton.setEnabled(not running)

    def _on_contact_check_running_changed(self, running: bool) -> None:
        self._contact_check_running = running
        self.opv_contactCheckButton.setText("接触確認を停止" if running else "接触確認")
        self.opv_contactCheckButton.setEnabled(True)
        if not running:
            self.opv_contactCheckReadingLabel.setText("電流: -")
        self.opv_startButton.setEnabled(not running)

    def _on_contact_check_reading(self, voltage: float, current: float) -> None:
        self.opv_contactCheckReadingLabel.setText(f"電流: {current:.6e} A (V={voltage:.3f})")

    def _on_point_measured(self, point) -> None:
        if self._plot_buffer is not None:
            self._plot_buffer.add_point(point.voltage, point.current)

    def _append_log(self, message: str) -> None:
        self.opv_logTextEdit.append(message)

    def _append_error_log(self, message: str) -> None:
        self.opv_logTextEdit.append(f'<span style="color:#ff5555;">エラー: {message}</span>')

    def _show_warning(self, message: str) -> None:
        QtWidgets.QMessageBox.warning(self, "入力エラー", message)

    def _on_finished_ok(self, points: list, csv_path: str, aborted: bool) -> None:
        self._last_result = (points, False)
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
        sample_name = self.opv_sampleNameEdit.text().strip() or "sample"
        save_dir = self.opv_saveDirEdit.text().strip() or "."
        default_path = os.path.join(save_dir, opv_csv_filename(sample_name))
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
            "opv_v_min": self.opv_vMinSpin,
            "opv_v_max": self.opv_vMaxSpin,
            "opv_v_step": self.opv_vStepSpin,
            "opv_iteration": self.opv_iterationSpin,
            "opv_nplc": self.opv_nplcSpin,
            "opv_delay": self.opv_delaySpin,
            "opv_compliance": self.opv_complianceSpin,
            "opv_hysteresis": self.opv_hysteresisCheckBox,
        }

    def _on_browse_save_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択")
        if directory:
            self.opv_saveDirEdit.setText(directory)
