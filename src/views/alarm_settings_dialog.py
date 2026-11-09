"""全測定モード共通の完了アラーム設定。"""
from __future__ import annotations

import os

from qtcompat import QtWidgets, enum_value
from utils import persistence
from views import notify_sound
from views.widgets.no_scroll_combobox import NoScrollComboBox


class AlarmSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("アラームの設定")
        self.setObjectName("alarmSettingsDialog")
        self.setMinimumWidth(520)
        self._preview_dialog = None
        settings = persistence.load_settings()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("全測定モードの測定完了アラームに適用します。"))
        self.mode_combo = NoScrollComboBox(objectName="alarmModeCombo")
        for label, value in (("標準音", "standard"), ("音源ファイル", "file"),
                             ("アラームなし（音・ポップアップなし）", "none")):
            self.mode_combo.addItem(label, value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(settings["alarm_mode"])))
        layout.addWidget(self.mode_combo)
        file_row = QtWidgets.QHBoxLayout()
        self.file_edit = QtWidgets.QLineEdit(settings["alarm_file"], objectName="alarmFileEdit")
        self.file_edit.setPlaceholderText("WAV / MP3 / FLAC / OGG / M4A")
        self.browse_button = QtWidgets.QPushButton("参照...", objectName="alarmBrowseButton")
        self.browse_button.clicked.connect(self._browse)
        file_row.addWidget(self.file_edit)
        file_row.addWidget(self.browse_button)
        layout.addLayout(file_row)
        note = QtWidgets.QLabel("再生は最大20秒です。音源が短い場合は最後まで再生して停止します。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.preview_button = QtWidgets.QPushButton("試聴", objectName="alarmPreviewButton")
        self.preview_button.clicked.connect(self._preview)
        layout.addWidget(self.preview_button)
        buttons = QtWidgets.QDialogButtonBox(
            enum_value(QtWidgets.QDialogButtonBox, "Ok") | enum_value(QtWidgets.QDialogButtonBox, "Cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode_combo.currentIndexChanged.connect(self._update_controls)
        self.finished.connect(self._stop_preview)
        self._update_controls()

    def _update_controls(self, *_args):
        mode = self.mode_combo.currentData()
        self.file_edit.setEnabled(mode == "file")
        self.browse_button.setEnabled(mode == "file")
        self.preview_button.setEnabled(mode != "none")
        self._stop_preview()

    def _browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "アラーム音源を選択", self.file_edit.text(),
            "音声ファイル (*.wav *.mp3 *.flac *.ogg *.m4a);;すべてのファイル (*)",
        )
        if path:
            self.file_edit.setText(path)

    def get_settings(self):
        path = self.file_edit.text().strip()
        if path:
            path = os.path.abspath(os.path.expanduser(path))
        return {"alarm_mode": self.mode_combo.currentData(), "alarm_file": path}

    def _validate(self):
        settings = self.get_settings()
        if settings["alarm_mode"] == "file":
            try:
                with open(settings["alarm_file"], "rb") as stream:
                    if not stream.read(1):
                        raise ValueError("音源ファイルが空です。")
            except (OSError, ValueError) as exc:
                QtWidgets.QMessageBox.warning(self, "音源を確認してください", str(exc))
                return False
        return True

    def _preview(self):
        if not self._validate():
            return
        self._preview_dialog = notify_sound.play_completion_sound(
            "success", self, settings=self.get_settings(), preview=True,
        )
        if self._preview_dialog is None:
            QtWidgets.QMessageBox.warning(self, "試聴できません", "音源ファイルやオーディオ出力を確認してください。")

    def _stop_preview(self, *_args):
        if self._preview_dialog is not None:
            try:
                self._preview_dialog.close()
            except RuntimeError:
                pass
            self._preview_dialog = None

    def accept(self):
        if not self._validate():
            return
        settings = self.get_settings()
        persistence.save_settings(settings)
        saved = persistence.load_settings()
        if any(saved[key] != value for key, value in settings.items()):
            QtWidgets.QMessageBox.warning(self, "設定を保存できません", "設定ファイルの保存先を確認してください。")
            return
        notify_sound.dismiss_completion_alarm()
        super().accept()
