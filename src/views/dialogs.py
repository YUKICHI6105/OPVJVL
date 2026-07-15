"""機器設定ダイアログ(View層)。

OPV/JVL/2ch活用モードA/2ch活用モードBの各タブに個別に存在していた
「機器選択」「接続先(COM/VISA)」「輝度計(BM9)ポート」の入力欄を、
メニューバーから呼び出す1つの設定ダイアログに統合する。

EQEプロジェクト(``EQE/src/views/dialogs.py`` の ``MeasurementSettingsDialog``)の
構成(QVBoxLayout + 複数QGroupBox + 「設定を初期化」ボタン付きQDialogButtonBox)を
踏襲するが、OPVJVLはPyQt5/PyQt6両対応が必須のため、Qt型は全て ``qtcompat`` 経由で
取得する(直接 ``PyQt5``/``PyQt6`` をimportしない)。
"""
from __future__ import annotations

from qtcompat import QtWidgets, enum_value
from utils.device_settings import DEFAULT_DEVICE_SETTINGS
from viewmodels.device_discovery import list_serial_ports, list_visa_resources
from views import theme

_DEVICE_TYPE_ITEMS = ["Keithley2400", "Keithley2612B(単チャンネル運用)"]
_CHANNEL_ITEMS = ["smua", "smub"]


def _make_editable_combo(object_name: str, current_text: str) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox(objectName=object_name)
    combo.setEditable(True)
    if current_text:
        combo.addItem(current_text)
    combo.setCurrentText(current_text)
    return combo


class DisplaySettingsDialog(QtWidgets.QDialog):
    """グラフ描画スタイル(目盛フォント・線幅・シンボルサイズ・グリッド・凡例)の設定ダイアログ。

    EQEプロジェクト(``EQE/src/views/dialogs.py`` の ``DisplaySettingsDialog``)から移植。
    グリッド表示の切替に加え、review.md指摘#6でJVLタブに凡例を追加したため、
    凡例の表示/非表示・フォントサイズも設定できる。
    デフォルト値の唯一の正は ``views.theme.GRAPH_STYLE_DEFAULTS``。
    """

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setObjectName("DisplaySettingsDialog")
        self.setWindowTitle("グラフ表示の設定")
        self.settings = current_settings or {}
        self._init_ui()
        self.resize(360, self.sizeHint().height())

    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()

        defaults = theme.GRAPH_STYLE_DEFAULTS

        self.fontSizeSpin = QtWidgets.QSpinBox(objectName="graph_fontSizeSpin")
        self.fontSizeSpin.setRange(6, 24)
        self.fontSizeSpin.setValue(
            int(self.settings.get("graph_font_size", defaults["graph_font_size"]))
        )
        form_layout.addRow("軸・目盛フォントサイズ (pt):", self.fontSizeSpin)

        self.lineWidthSpin = QtWidgets.QDoubleSpinBox(objectName="graph_lineWidthSpin")
        self.lineWidthSpin.setRange(0.5, 10.0)
        self.lineWidthSpin.setSingleStep(0.5)
        self.lineWidthSpin.setDecimals(1)
        self.lineWidthSpin.setValue(
            float(self.settings.get("graph_line_width", defaults["graph_line_width"]))
        )
        form_layout.addRow("プロット線幅 (px):", self.lineWidthSpin)

        self.symbolSizeSpin = QtWidgets.QSpinBox(objectName="graph_symbolSizeSpin")
        self.symbolSizeSpin.setRange(0, 20)
        self.symbolSizeSpin.setValue(
            int(self.settings.get("graph_symbol_size", defaults["graph_symbol_size"]))
        )
        form_layout.addRow("プロットシンボルサイズ (px):", self.symbolSizeSpin)

        self.showGridCheckBox = QtWidgets.QCheckBox(
            "グリッド線を表示する", objectName="graph_showGridCheckBox"
        )
        self.showGridCheckBox.setChecked(
            bool(self.settings.get("graph_show_grid", defaults["graph_show_grid"]))
        )
        form_layout.addRow("グリッド表示:", self.showGridCheckBox)

        self.showLegendCheckBox = QtWidgets.QCheckBox(
            "凡例を表示する", objectName="graph_showLegendCheckBox"
        )
        self.showLegendCheckBox.setChecked(
            bool(self.settings.get("graph_show_legend", defaults["graph_show_legend"]))
        )
        form_layout.addRow("凡例表示:", self.showLegendCheckBox)

        self.legendFontSizeSpin = QtWidgets.QSpinBox(objectName="graph_legendFontSizeSpin")
        self.legendFontSizeSpin.setRange(6, 24)
        self.legendFontSizeSpin.setValue(
            int(self.settings.get("graph_legend_font_size", defaults["graph_legend_font_size"]))
        )
        form_layout.addRow("凡例フォントサイズ (pt):", self.legendFontSizeSpin)

        layout.addLayout(form_layout)

        button_layout = QtWidgets.QHBoxLayout()
        self.resetButton = QtWidgets.QPushButton("設定を初期化", objectName="graph_resetButton")
        self.resetButton.clicked.connect(self.reset_to_defaults)

        ok_flag = enum_value(QtWidgets.QDialogButtonBox, "Ok")
        cancel_flag = enum_value(QtWidgets.QDialogButtonBox, "Cancel")
        self.buttonBox = QtWidgets.QDialogButtonBox(ok_flag | cancel_flag)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        button_layout.addWidget(self.resetButton)
        button_layout.addStretch()
        button_layout.addWidget(self.buttonBox)
        layout.addLayout(button_layout)

    def reset_to_defaults(self) -> None:
        defaults = theme.GRAPH_STYLE_DEFAULTS
        self.fontSizeSpin.setValue(int(defaults["graph_font_size"]))
        self.lineWidthSpin.setValue(float(defaults["graph_line_width"]))
        self.symbolSizeSpin.setValue(int(defaults["graph_symbol_size"]))
        self.showGridCheckBox.setChecked(bool(defaults["graph_show_grid"]))
        self.showLegendCheckBox.setChecked(bool(defaults["graph_show_legend"]))
        self.legendFontSizeSpin.setValue(int(defaults["graph_legend_font_size"]))

    def get_settings(self) -> dict:
        return {
            "graph_font_size": self.fontSizeSpin.value(),
            "graph_line_width": self.lineWidthSpin.value(),
            "graph_symbol_size": self.symbolSizeSpin.value(),
            "graph_show_grid": self.showGridCheckBox.isChecked(),
            "graph_show_legend": self.showLegendCheckBox.isChecked(),
            "graph_legend_font_size": self.legendFontSizeSpin.value(),
        }


class DeviceSettingsDialog(QtWidgets.QDialog):
    """OPV/JVLモード・2ch活用モードの機器接続設定をまとめて編集するダイアログ。

    実験室ではOPVモードとJVLモードは同一のソースメータを、2ch活用モードA/Bは
    同一のKeithley2612Bを共用するため、設定は「OPV/JVLモード共通」
    「2ch活用モード共通」の2グループに統合されている
    (旧: OPV/JVL/2ch活用モードA/Bの4グループ)。
    """

    def __init__(
        self,
        parent=None,
        current_settings: dict | None = None,
        developer_mode: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("DeviceSettingsDialog")
        self.setWindowTitle("機器設定")
        self.settings = current_settings or {}
        self.developer_mode = developer_mode
        self._init_ui()
        self.resize(480, self.sizeHint().height())

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(self._build_opvjvl_group())
        layout.addWidget(self._build_dual_group())

        button_layout = QtWidgets.QHBoxLayout()
        self.resetButton = QtWidgets.QPushButton("設定を初期化", objectName="resetButton")
        self.resetButton.clicked.connect(self.reset_to_defaults)

        ok_flag = enum_value(QtWidgets.QDialogButtonBox, "Ok")
        cancel_flag = enum_value(QtWidgets.QDialogButtonBox, "Cancel")
        self.buttonBox = QtWidgets.QDialogButtonBox(ok_flag | cancel_flag)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        button_layout.addWidget(self.resetButton)
        button_layout.addStretch()
        button_layout.addWidget(self.buttonBox)
        layout.addLayout(button_layout)

    def _build_opvjvl_group(self) -> QtWidgets.QGroupBox:
        """「OPV/JVLモード共通」グループを構築する。

        実験室ではOPVモードとJVLモードは同一のソースメータを使うため、
        機器選択・接続先・チャンネル・モック使用有無は1系統(opvjvl_*)に統合する。
        輝度計(BM9)ポートはJVLモードの輝度測定でのみ使用するが、
        グループ自体はOPV/JVL共通のためここに配置する。
        """
        groupBox = QtWidgets.QGroupBox("OPV/JVLモード共通", objectName="opvjvlGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.opvjvl_deviceTypeCombo = QtWidgets.QComboBox(objectName="opvjvl_deviceTypeCombo")
        self.opvjvl_deviceTypeCombo.addItems(_DEVICE_TYPE_ITEMS)
        self.opvjvl_deviceTypeCombo.setCurrentIndex(
            self.settings.get(
                "opvjvl_device_type_index", DEFAULT_DEVICE_SETTINGS["opvjvl_device_type_index"]
            )
        )
        formLayout.addRow("機器選択:", self.opvjvl_deviceTypeCombo)

        self.opvjvl_connectionEdit = _make_editable_combo(
            "opvjvl_connectionEdit",
            self.settings.get("opvjvl_connection", DEFAULT_DEVICE_SETTINGS["opvjvl_connection"]),
        )
        self.opvjvl_refreshButton = QtWidgets.QPushButton("再検索", objectName="opvjvl_refreshButton")
        self.opvjvl_refreshButton.clicked.connect(
            lambda: self._refresh_connection_combo(
                self.opvjvl_connectionEdit, self.opvjvl_deviceTypeCombo
            )
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.opvjvl_connectionEdit)
        connectionRow.addWidget(self.opvjvl_refreshButton)
        formLayout.addRow("接続先(COM/VISA):", connectionRow)

        self.opvjvl_channelCombo = QtWidgets.QComboBox(objectName="opvjvl_channelCombo")
        self.opvjvl_channelCombo.addItems(_CHANNEL_ITEMS)
        self.opvjvl_channelCombo.setCurrentText(
            self.settings.get("opvjvl_channel", DEFAULT_DEVICE_SETTINGS["opvjvl_channel"])
        )
        self.opvjvl_channelLabel = QtWidgets.QLabel("チャンネル(2612B時のみ):")
        formLayout.addRow(self.opvjvl_channelLabel, self.opvjvl_channelCombo)

        self.opvjvl_deviceTypeCombo.currentIndexChanged.connect(
            self._update_opvjvl_channel_visibility
        )
        self._update_opvjvl_channel_visibility()

        self.opvjvl_bm9PortEdit = _make_editable_combo(
            "opvjvl_bm9PortEdit",
            self.settings.get("opvjvl_bm9_port", DEFAULT_DEVICE_SETTINGS["opvjvl_bm9_port"]),
        )
        self.opvjvl_bm9RefreshButton = QtWidgets.QPushButton(
            "再検索", objectName="opvjvl_bm9RefreshButton"
        )
        self.opvjvl_bm9RefreshButton.clicked.connect(
            lambda: self._refresh_serial_combo(self.opvjvl_bm9PortEdit)
        )
        bm9Row = QtWidgets.QHBoxLayout()
        bm9Row.addWidget(self.opvjvl_bm9PortEdit)
        bm9Row.addWidget(self.opvjvl_bm9RefreshButton)
        formLayout.addRow("輝度計(BM9)ポート(JVL輝度測定用):", bm9Row)

        if self.developer_mode:
            self.opvjvl_useMockCheckBox = QtWidgets.QCheckBox(objectName="opvjvl_useMockCheckBox")
            self.opvjvl_useMockCheckBox.setChecked(self.settings.get("opvjvl_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.opvjvl_useMockCheckBox)

        return groupBox

    def _update_opvjvl_channel_visibility(self) -> None:
        is_2612b = self.opvjvl_deviceTypeCombo.currentIndex() == 1
        self.opvjvl_channelLabel.setVisible(is_2612b)
        self.opvjvl_channelCombo.setVisible(is_2612b)

    def _build_dual_group(self) -> QtWidgets.QGroupBox:
        """「2ch活用モード共通」グループを構築する。

        2ch活用モードA・Bは同一のKeithley2612B(2チャンネル)を使うため、
        接続先・輝度計ポート・モック使用有無は1系統(dual_*)に統合する。
        機器はKeithley2612B固定のため機器選択コンボは持たない。
        """
        groupBox = QtWidgets.QGroupBox("2ch活用モード共通", objectName="dualGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.dual_connectionEdit = _make_editable_combo(
            "dual_connectionEdit",
            self.settings.get("dual_connection", DEFAULT_DEVICE_SETTINGS["dual_connection"]),
        )
        self.dual_refreshButton = QtWidgets.QPushButton("再検索", objectName="dual_refreshButton")
        self.dual_refreshButton.clicked.connect(
            lambda: self._refresh_visa_combo(self.dual_connectionEdit)
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.dual_connectionEdit)
        connectionRow.addWidget(self.dual_refreshButton)
        formLayout.addRow("接続先(VISA、Keithley2612B固定):", connectionRow)

        self.dual_bm9PortEdit = _make_editable_combo(
            "dual_bm9PortEdit",
            self.settings.get("dual_bm9_port", DEFAULT_DEVICE_SETTINGS["dual_bm9_port"]),
        )
        self.dual_bm9RefreshButton = QtWidgets.QPushButton(
            "再検索", objectName="dual_bm9RefreshButton"
        )
        self.dual_bm9RefreshButton.clicked.connect(
            lambda: self._refresh_serial_combo(self.dual_bm9PortEdit)
        )
        bm9Row = QtWidgets.QHBoxLayout()
        bm9Row.addWidget(self.dual_bm9PortEdit)
        bm9Row.addWidget(self.dual_bm9RefreshButton)
        formLayout.addRow("輝度計(BM9)ポート:", bm9Row)

        if self.developer_mode:
            self.dual_useMockCheckBox = QtWidgets.QCheckBox(objectName="dual_useMockCheckBox")
            self.dual_useMockCheckBox.setChecked(self.settings.get("dual_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.dual_useMockCheckBox)

        return groupBox

    # ------------------------------------------------------------------
    # 再検索処理
    # ------------------------------------------------------------------
    @staticmethod
    def _refresh_connection_combo(
        combo: QtWidgets.QComboBox, device_type_combo: QtWidgets.QComboBox
    ) -> None:
        """機器選択に応じてVISA/シリアルポートを再検索し、コンボへ反映する。

        既存の各タブ ``_on_refresh_devices_clicked`` と同じ判定ロジック:
        Keithley2612Bを選択している場合のみVISA、それ以外はシリアルとして検索する。
        """
        is_2612b = device_type_combo.currentIndex() == 1
        candidates = list_visa_resources() if is_2612b else list_serial_ports()
        current_text = combo.currentText()
        combo.clear()
        for candidate in candidates:
            combo.addItem(candidate)
        combo.setCurrentText(current_text)

    @staticmethod
    def _refresh_serial_combo(combo: QtWidgets.QComboBox) -> None:
        candidates = list_serial_ports()
        current_text = combo.currentText()
        combo.clear()
        for candidate in candidates:
            combo.addItem(candidate)
        combo.setCurrentText(current_text)

    @staticmethod
    def _refresh_visa_combo(combo: QtWidgets.QComboBox) -> None:
        candidates = list_visa_resources()
        current_text = combo.currentText()
        combo.clear()
        for candidate in candidates:
            combo.addItem(candidate)
        combo.setCurrentText(current_text)

    # ------------------------------------------------------------------
    # 初期化 / 値取得
    # ------------------------------------------------------------------
    def reset_to_defaults(self) -> None:
        self.opvjvl_deviceTypeCombo.setCurrentIndex(
            DEFAULT_DEVICE_SETTINGS["opvjvl_device_type_index"]
        )
        self.opvjvl_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["opvjvl_connection"])
        self.opvjvl_channelCombo.setCurrentText(DEFAULT_DEVICE_SETTINGS["opvjvl_channel"])
        self.opvjvl_bm9PortEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["opvjvl_bm9_port"])
        if hasattr(self, "opvjvl_useMockCheckBox"):
            self.opvjvl_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["opvjvl_use_mock"])

        self.dual_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_connection"])
        self.dual_bm9PortEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_bm9_port"])
        if hasattr(self, "dual_useMockCheckBox"):
            self.dual_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["dual_use_mock"])

    def get_settings(self) -> dict:
        return {
            "opvjvl_device_type_index": self.opvjvl_deviceTypeCombo.currentIndex(),
            "opvjvl_connection": self.opvjvl_connectionEdit.currentText().strip(),
            "opvjvl_channel": self.opvjvl_channelCombo.currentText(),
            "opvjvl_bm9_port": self.opvjvl_bm9PortEdit.currentText().strip(),
            "opvjvl_use_mock": (
                self.opvjvl_useMockCheckBox.isChecked()
                if hasattr(self, "opvjvl_useMockCheckBox")
                else self.settings.get("opvjvl_use_mock", False)
            ),
            "dual_connection": self.dual_connectionEdit.currentText().strip(),
            "dual_bm9_port": self.dual_bm9PortEdit.currentText().strip(),
            "dual_use_mock": (
                self.dual_useMockCheckBox.isChecked()
                if hasattr(self, "dual_useMockCheckBox")
                else self.settings.get("dual_use_mock", False)
            ),
        }
