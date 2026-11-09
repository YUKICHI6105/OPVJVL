"""アラーム選択・永続化と無音設定、音源プレイヤーの寿命を検証する。"""
from types import SimpleNamespace

import pytest

from qtcompat import QObject, QtWidgets, pyqtSignal
from utils import persistence
from views import notify_sound
from views.alarm_settings_dialog import AlarmSettingsDialog
from views.main_window import MainWindow


def test_alarm_settings_save_reload_preserves_measurement_directories(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    paths = {"shared_save_dir": "shared-original", "dual_b_save_dir": "dual-original"}
    persistence.save_settings(paths)
    window = MainWindow()
    qtbot.addWidget(window)
    audio = tmp_path / "日本語 音源.wav"
    audio.write_bytes(notify_sound._SUCCESS_ALARM_WAV)
    dialog = AlarmSettingsDialog(window)
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("file"))
    dialog.file_edit.setText(str(audio))
    dialog.accept()
    assert dialog.result() == 1
    window.close()
    reopened = AlarmSettingsDialog()
    qtbot.addWidget(reopened)
    assert reopened.get_settings() == {"alarm_mode": "file", "alarm_file": str(audio)}
    assert {key: persistence.load_settings()[key] for key in paths} == paths
    reopened.mode_combo.setCurrentIndex(reopened.mode_combo.findData("none"))
    assert not reopened.file_edit.isEnabled()
    assert not reopened.preview_button.isEnabled()
    reopened.accept()
    assert persistence.load_settings()["alarm_mode"] == "none"


def test_cancel_does_not_change_alarm(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    dialog = AlarmSettingsDialog()
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("none"))
    dialog.reject()
    assert persistence.load_settings()["alarm_mode"] == "standard"


def test_preview_uses_unsaved_selection_and_stops_on_cancel(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    path = tmp_path / "music.mp3"
    path.write_bytes(b"audio")
    calls = []
    preview = QtWidgets.QDialog()
    qtbot.addWidget(preview)
    preview.show()
    def play(outcome, parent, **kwargs):
        calls.append(kwargs)
        return preview
    monkeypatch.setattr(notify_sound, "play_completion_sound", play)
    dialog = AlarmSettingsDialog()
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("file"))
    dialog.file_edit.setText(str(path))
    dialog.preview_button.click()
    assert calls == [{"settings": {"alarm_mode": "file", "alarm_file": str(path)}, "preview": True}]
    assert persistence.load_settings()["alarm_mode"] == "standard"
    dialog.reject()
    assert not preview.isVisible()


def test_missing_audio_cannot_be_saved(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    warnings = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", lambda *args: warnings.append(args))
    dialog = AlarmSettingsDialog()
    qtbot.addWidget(dialog)
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("file"))
    dialog.file_edit.setText(str(tmp_path / "missing.mp3"))
    dialog.accept()
    assert warnings
    assert dialog.result() == 0
    assert persistence.load_settings()["alarm_mode"] == "standard"


def test_saving_no_alarm_stops_existing_notification(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    existing = notify_sound.CompletionAlarmDialog()
    qtbot.addWidget(existing)
    existing.show()
    notify_sound._active_alarm_dialog = existing
    stopped = []
    monkeypatch.setattr(notify_sound, "stop_completion_sound", lambda: stopped.append(True))
    settings = AlarmSettingsDialog()
    qtbot.addWidget(settings)
    settings.mode_combo.setCurrentIndex(settings.mode_combo.findData("none"))
    settings.accept()
    assert stopped
    assert notify_sound._active_alarm_dialog is None
    assert not existing.isVisible()


def test_alarm_menu_opens_settings(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    opened = []
    monkeypatch.setattr("views.main_window.qt_exec", lambda dialog: opened.append(dialog) or 0)
    window = MainWindow()
    qtbot.addWidget(window)
    window.actionAlarmSettings.trigger()
    assert isinstance(opened[0], AlarmSettingsDialog)
    window.close()


@pytest.mark.parametrize("mode", ["opv", "jvl", "dual_a", "dual_b"])
def test_no_alarm_suppresses_sound_and_popup_for_every_mode(qtbot, monkeypatch, tmp_path, mode):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    persistence.save_settings({"alarm_mode": "none"})
    def unexpected(*args):
        pytest.fail("アラームなしの場合は音源を準備しない")
    monkeypatch.setattr(notify_sound, "_get_success_alarm_path", unexpected)
    monkeypatch.setattr(notify_sound, "_create_custom_player", unexpected)
    window = MainWindow()
    qtbot.addWidget(window)
    if mode == "opv":
        window.opv_tab._on_finished_ok([], "", False)
    elif mode == "jvl":
        window.jvl_tab._on_finished_ok([], "", False)
    elif mode == "dual_a":
        window.dual_channel_tab._on_finished_ok_a([], "", False)
    else:
        window.dual_channel_tab._on_finished_ok_b([], "", "", False)
    assert notify_sound._active_alarm_dialog is None
    assert not window.findChildren(notify_sound.CompletionAlarmDialog)
    window.close()


class FakePlayer(QObject):
    mediaStatusChanged = pyqtSignal(int)
    errorOccurred = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.played = 0
        self.stopped = 0

    def play(self):
        self.played += 1

    def stop(self):
        self.stopped += 1

    def errorString(self):
        return "Unsupported audio"


@pytest.mark.parametrize("finish", ["end", "button", "timer", "parent"])
def test_custom_player_stops_on_each_completion_path(qtbot, monkeypatch, finish):
    player = FakePlayer()
    selected = []
    def create(path):
        selected.append(path)
        notify_sound._custom_player = player
        return player
    monkeypatch.setattr(notify_sound, "_create_custom_player", create)
    monkeypatch.setattr(notify_sound, "load_qt_multimedia", lambda: SimpleNamespace(
        QMediaPlayer=SimpleNamespace(EndOfMedia=7)))
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = notify_sound.play_completion_sound("success", parent,
        settings={"alarm_mode": "file", "alarm_file": "music.mp3"})
    assert selected == ["music.mp3"]
    assert player.played == 1
    if finish == "end":
        player.mediaStatusChanged.emit(7)
    elif finish == "button":
        dialog.stop_button.click()
    elif finish == "timer":
        dialog._close_timer.timeout.emit()
    else:
        parent.deleteLater()
        qtbot.waitUntil(lambda: notify_sound._active_alarm_dialog is None)
    assert notify_sound._custom_player is None
    assert player.stopped == 1
