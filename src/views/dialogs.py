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

_DEVICE_TYPE_ITEMS = ["Keithley2400", "Keithley2612B(単チャンネル運用)"]
_CHANNEL_ITEMS = ["smua", "smub"]


def _make_editable_combo(object_name: str, current_text: str) -> QtWidgets.QComboBox:
    combo = QtWidgets.QComboBox(objectName=object_name)
    combo.setEditable(True)
    if current_text:
        combo.addItem(current_text)
    combo.setCurrentText(current_text)
    return combo


class DeviceSettingsDialog(QtWidgets.QDialog):
    """OPV/JVL/2ch活用モードA・Bの機器接続設定をまとめて編集するダイアログ。"""

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

        layout.addWidget(self._build_opv_group())
        layout.addWidget(self._build_jvl_group())
        layout.addWidget(self._build_dual_a_group())
        layout.addWidget(self._build_dual_b_group())

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

    def _build_opv_group(self) -> QtWidgets.QGroupBox:
        groupBox = QtWidgets.QGroupBox("OPVモード", objectName="opvGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.opv_deviceTypeCombo = QtWidgets.QComboBox(objectName="opv_deviceTypeCombo")
        self.opv_deviceTypeCombo.addItems(_DEVICE_TYPE_ITEMS)
        self.opv_deviceTypeCombo.setCurrentIndex(
            self.settings.get("opv_device_type_index", DEFAULT_DEVICE_SETTINGS["opv_device_type_index"])
        )
        formLayout.addRow("機器選択:", self.opv_deviceTypeCombo)

        self.opv_connectionEdit = _make_editable_combo(
            "opv_connectionEdit",
            self.settings.get("opv_connection", DEFAULT_DEVICE_SETTINGS["opv_connection"]),
        )
        self.opv_refreshButton = QtWidgets.QPushButton("再検索", objectName="opv_refreshButton")
        self.opv_refreshButton.clicked.connect(
            lambda: self._refresh_connection_combo(self.opv_connectionEdit, self.opv_deviceTypeCombo)
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.opv_connectionEdit)
        connectionRow.addWidget(self.opv_refreshButton)
        formLayout.addRow("接続先(COM/VISA):", connectionRow)

        self.opv_channelCombo = QtWidgets.QComboBox(objectName="opv_channelCombo")
        self.opv_channelCombo.addItems(_CHANNEL_ITEMS)
        self.opv_channelCombo.setCurrentText(
            self.settings.get("opv_channel", DEFAULT_DEVICE_SETTINGS["opv_channel"])
        )
        self.opv_channelLabel = QtWidgets.QLabel("チャンネル(2612B時のみ):")
        formLayout.addRow(self.opv_channelLabel, self.opv_channelCombo)

        self.opv_deviceTypeCombo.currentIndexChanged.connect(self._update_opv_channel_visibility)
        self._update_opv_channel_visibility()

        if self.developer_mode:
            self.opv_useMockCheckBox = QtWidgets.QCheckBox(objectName="opv_useMockCheckBox")
            self.opv_useMockCheckBox.setChecked(self.settings.get("opv_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.opv_useMockCheckBox)

        return groupBox

    def _update_opv_channel_visibility(self) -> None:
        is_2612b = self.opv_deviceTypeCombo.currentIndex() == 1
        self.opv_channelLabel.setVisible(is_2612b)
        self.opv_channelCombo.setVisible(is_2612b)

    def _build_jvl_group(self) -> QtWidgets.QGroupBox:
        groupBox = QtWidgets.QGroupBox("JVLモード", objectName="jvlGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.jvl_deviceTypeCombo = QtWidgets.QComboBox(objectName="jvl_deviceTypeCombo")
        self.jvl_deviceTypeCombo.addItems(_DEVICE_TYPE_ITEMS)
        self.jvl_deviceTypeCombo.setCurrentIndex(
            self.settings.get("jvl_device_type_index", DEFAULT_DEVICE_SETTINGS["jvl_device_type_index"])
        )
        formLayout.addRow("機器選択:", self.jvl_deviceTypeCombo)

        self.jvl_connectionEdit = _make_editable_combo(
            "jvl_connectionEdit",
            self.settings.get("jvl_connection", DEFAULT_DEVICE_SETTINGS["jvl_connection"]),
        )
        self.jvl_refreshButton = QtWidgets.QPushButton("再検索", objectName="jvl_refreshButton")
        self.jvl_refreshButton.clicked.connect(
            lambda: self._refresh_connection_combo(self.jvl_connectionEdit, self.jvl_deviceTypeCombo)
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.jvl_connectionEdit)
        connectionRow.addWidget(self.jvl_refreshButton)
        formLayout.addRow("接続先(COM/VISA):", connectionRow)

        self.jvl_bm9PortEdit = _make_editable_combo(
            "jvl_bm9PortEdit",
            self.settings.get("jvl_bm9_port", DEFAULT_DEVICE_SETTINGS["jvl_bm9_port"]),
        )
        self.jvl_bm9RefreshButton = QtWidgets.QPushButton("再検索", objectName="jvl_bm9RefreshButton")
        self.jvl_bm9RefreshButton.clicked.connect(
            lambda: self._refresh_serial_combo(self.jvl_bm9PortEdit)
        )
        bm9Row = QtWidgets.QHBoxLayout()
        bm9Row.addWidget(self.jvl_bm9PortEdit)
        bm9Row.addWidget(self.jvl_bm9RefreshButton)
        formLayout.addRow("輝度計(BM9)ポート:", bm9Row)

        self.jvl_channelCombo = QtWidgets.QComboBox(objectName="jvl_channelCombo")
        self.jvl_channelCombo.addItems(_CHANNEL_ITEMS)
        self.jvl_channelCombo.setCurrentText(
            self.settings.get("jvl_channel", DEFAULT_DEVICE_SETTINGS["jvl_channel"])
        )
        self.jvl_channelLabel = QtWidgets.QLabel("チャンネル(2612B時のみ):")
        formLayout.addRow(self.jvl_channelLabel, self.jvl_channelCombo)

        self.jvl_deviceTypeCombo.currentIndexChanged.connect(self._update_jvl_channel_visibility)
        self._update_jvl_channel_visibility()

        if self.developer_mode:
            self.jvl_useMockCheckBox = QtWidgets.QCheckBox(objectName="jvl_useMockCheckBox")
            self.jvl_useMockCheckBox.setChecked(self.settings.get("jvl_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.jvl_useMockCheckBox)

        return groupBox

    def _update_jvl_channel_visibility(self) -> None:
        is_2612b = self.jvl_deviceTypeCombo.currentIndex() == 1
        self.jvl_channelLabel.setVisible(is_2612b)
        self.jvl_channelCombo.setVisible(is_2612b)

    def _build_dual_a_group(self) -> QtWidgets.QGroupBox:
        groupBox = QtWidgets.QGroupBox("2ch活用モードA", objectName="dualAGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.dual_a_connectionEdit = _make_editable_combo(
            "dual_a_connectionEdit",
            self.settings.get("dual_a_connection", DEFAULT_DEVICE_SETTINGS["dual_a_connection"]),
        )
        self.dual_a_refreshButton = QtWidgets.QPushButton("再検索", objectName="dual_a_refreshButton")
        self.dual_a_refreshButton.clicked.connect(
            lambda: self._refresh_visa_combo(self.dual_a_connectionEdit)
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.dual_a_connectionEdit)
        connectionRow.addWidget(self.dual_a_refreshButton)
        formLayout.addRow("接続先(VISA、Keithley2612B固定):", connectionRow)

        self.dual_a_bm9PortEdit = _make_editable_combo(
            "dual_a_bm9PortEdit",
            self.settings.get("dual_a_bm9_port", DEFAULT_DEVICE_SETTINGS["dual_a_bm9_port"]),
        )
        self.dual_a_bm9RefreshButton = QtWidgets.QPushButton("再検索", objectName="dual_a_bm9RefreshButton")
        self.dual_a_bm9RefreshButton.clicked.connect(
            lambda: self._refresh_serial_combo(self.dual_a_bm9PortEdit)
        )
        bm9Row = QtWidgets.QHBoxLayout()
        bm9Row.addWidget(self.dual_a_bm9PortEdit)
        bm9Row.addWidget(self.dual_a_bm9RefreshButton)
        formLayout.addRow("輝度計(BM9)ポート:", bm9Row)

        if self.developer_mode:
            self.dual_a_useMockCheckBox = QtWidgets.QCheckBox(objectName="dual_a_useMockCheckBox")
            self.dual_a_useMockCheckBox.setChecked(self.settings.get("dual_a_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.dual_a_useMockCheckBox)

        return groupBox

    def _build_dual_b_group(self) -> QtWidgets.QGroupBox:
        groupBox = QtWidgets.QGroupBox("2ch活用モードB", objectName="dualBGroupBox")
        formLayout = QtWidgets.QFormLayout(groupBox)

        self.dual_b_connectionEdit = _make_editable_combo(
            "dual_b_connectionEdit",
            self.settings.get("dual_b_connection", DEFAULT_DEVICE_SETTINGS["dual_b_connection"]),
        )
        self.dual_b_refreshButton = QtWidgets.QPushButton("再検索", objectName="dual_b_refreshButton")
        self.dual_b_refreshButton.clicked.connect(
            lambda: self._refresh_visa_combo(self.dual_b_connectionEdit)
        )
        connectionRow = QtWidgets.QHBoxLayout()
        connectionRow.addWidget(self.dual_b_connectionEdit)
        connectionRow.addWidget(self.dual_b_refreshButton)
        formLayout.addRow("接続先(VISA、チャンネルA/B共通):", connectionRow)

        self.dual_b_bm9PortEdit = _make_editable_combo(
            "dual_b_bm9PortEdit",
            self.settings.get("dual_b_bm9_port", DEFAULT_DEVICE_SETTINGS["dual_b_bm9_port"]),
        )
        self.dual_b_bm9RefreshButton = QtWidgets.QPushButton("再検索", objectName="dual_b_bm9RefreshButton")
        self.dual_b_bm9RefreshButton.clicked.connect(
            lambda: self._refresh_serial_combo(self.dual_b_bm9PortEdit)
        )
        bm9Row = QtWidgets.QHBoxLayout()
        bm9Row.addWidget(self.dual_b_bm9PortEdit)
        bm9Row.addWidget(self.dual_b_bm9RefreshButton)
        formLayout.addRow("輝度計(BM9)ポート:", bm9Row)

        if self.developer_mode:
            self.dual_b_useMockCheckBox = QtWidgets.QCheckBox(objectName="dual_b_useMockCheckBox")
            self.dual_b_useMockCheckBox.setChecked(self.settings.get("dual_b_use_mock", False))
            formLayout.addRow("モックを使用する(開発者モード):", self.dual_b_useMockCheckBox)

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
        self.opv_deviceTypeCombo.setCurrentIndex(DEFAULT_DEVICE_SETTINGS["opv_device_type_index"])
        self.opv_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["opv_connection"])
        self.opv_channelCombo.setCurrentText(DEFAULT_DEVICE_SETTINGS["opv_channel"])
        if hasattr(self, "opv_useMockCheckBox"):
            self.opv_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["opv_use_mock"])

        self.jvl_deviceTypeCombo.setCurrentIndex(DEFAULT_DEVICE_SETTINGS["jvl_device_type_index"])
        self.jvl_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["jvl_connection"])
        self.jvl_bm9PortEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["jvl_bm9_port"])
        self.jvl_channelCombo.setCurrentText(DEFAULT_DEVICE_SETTINGS["jvl_channel"])
        if hasattr(self, "jvl_useMockCheckBox"):
            self.jvl_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["jvl_use_mock"])

        self.dual_a_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_a_connection"])
        self.dual_a_bm9PortEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_a_bm9_port"])
        if hasattr(self, "dual_a_useMockCheckBox"):
            self.dual_a_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["dual_a_use_mock"])

        self.dual_b_connectionEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_b_connection"])
        self.dual_b_bm9PortEdit.setCurrentText(DEFAULT_DEVICE_SETTINGS["dual_b_bm9_port"])
        if hasattr(self, "dual_b_useMockCheckBox"):
            self.dual_b_useMockCheckBox.setChecked(DEFAULT_DEVICE_SETTINGS["dual_b_use_mock"])

    def get_settings(self) -> dict:
        return {
            "opv_device_type_index": self.opv_deviceTypeCombo.currentIndex(),
            "opv_connection": self.opv_connectionEdit.currentText().strip(),
            "opv_channel": self.opv_channelCombo.currentText(),
            "opv_use_mock": (
                self.opv_useMockCheckBox.isChecked()
                if hasattr(self, "opv_useMockCheckBox")
                else self.settings.get("opv_use_mock", False)
            ),
            "jvl_device_type_index": self.jvl_deviceTypeCombo.currentIndex(),
            "jvl_connection": self.jvl_connectionEdit.currentText().strip(),
            "jvl_bm9_port": self.jvl_bm9PortEdit.currentText().strip(),
            "jvl_channel": self.jvl_channelCombo.currentText(),
            "jvl_use_mock": (
                self.jvl_useMockCheckBox.isChecked()
                if hasattr(self, "jvl_useMockCheckBox")
                else self.settings.get("jvl_use_mock", False)
            ),
            "dual_a_connection": self.dual_a_connectionEdit.currentText().strip(),
            "dual_a_bm9_port": self.dual_a_bm9PortEdit.currentText().strip(),
            "dual_a_use_mock": (
                self.dual_a_useMockCheckBox.isChecked()
                if hasattr(self, "dual_a_useMockCheckBox")
                else self.settings.get("dual_a_use_mock", False)
            ),
            "dual_b_connection": self.dual_b_connectionEdit.currentText().strip(),
            "dual_b_bm9_port": self.dual_b_bm9PortEdit.currentText().strip(),
            "dual_b_use_mock": (
                self.dual_b_useMockCheckBox.isChecked()
                if hasattr(self, "dual_b_useMockCheckBox")
                else self.settings.get("dual_b_use_mock", False)
            ),
        }
