"""測定完了時の音とプログレスバー表示のテスト。"""
from __future__ import annotations

import io
import sys
import wave

import pytest

from qtcompat import QtWidgets
from views import notify_sound
from views.dual_channel_tab import DualChannelTab
from views.jvl_tab import JVLTab
from views.opv_tab import OPVTab
from views.progress_bar import set_measurement_completed


class _FakeWinSound:
    SND_MEMORY = 0x0004
    SND_FILENAME = 0x0002
    SND_ASYNC = 0x0001
    MB_ICONEXCLAMATION = 0x0030
    MB_ICONHAND = 0x0010

    def __init__(self) -> None:
        self.play_calls = []
        self.beep_calls = []

    def PlaySound(self, sound, flags) -> None:
        self.play_calls.append((sound, flags))

    def MessageBeep(self, sound_type) -> None:
        self.beep_calls.append(sound_type)


def test_success_sound_is_20_second_async_alarm(monkeypatch) -> None:
    fake = _FakeWinSound()
    monkeypatch.setattr(notify_sound, "winsound", fake)
    monkeypatch.setattr(
        notify_sound, "_get_success_alarm_path", lambda: "completion-alarm.wav"
    )

    notify_sound.play_completion_sound("success")

    assert fake.play_calls[0] == (None, 0)
    assert len(fake.play_calls) == 2
    sound, flags = fake.play_calls[1]
    assert sound == "completion-alarm.wav"
    assert flags == fake.SND_FILENAME | fake.SND_ASYNC
    assert fake.beep_calls == []

    with wave.open(io.BytesIO(notify_sound._SUCCESS_ALARM_WAV), "rb") as wav_file:
        duration = wav_file.getnframes() / wav_file.getframerate()
        samples = wav_file.readframes(wav_file.getnframes())

    assert duration == pytest.approx(20.0, abs=0.01)
    assert min(samples) < 16
    assert max(samples) > 240


def _start_alarm_popup(qtbot, monkeypatch):
    fake = _FakeWinSound()
    monkeypatch.setattr(notify_sound, "winsound", fake)
    monkeypatch.setattr(
        notify_sound, "_get_success_alarm_path", lambda: "completion-alarm.wav"
    )
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = notify_sound.play_completion_sound("success", parent)
    assert dialog is not None
    return fake, parent, dialog


def test_alarm_popup_stop_button_stops_sound_and_closes(qtbot, monkeypatch) -> None:
    fake, _parent, dialog = _start_alarm_popup(qtbot, monkeypatch)

    assert isinstance(dialog, QtWidgets.QDialog)
    assert not isinstance(dialog, QtWidgets.QMessageBox)
    assert dialog.windowTitle() == "測定完了"
    assert dialog.stop_button.text() == "アラームを停止"
    assert dialog._close_timer.isSingleShot()
    assert dialog._close_timer.interval() == 20_000

    dialog.stop_button.click()

    assert not dialog.isVisible()
    assert notify_sound._active_alarm_dialog is None
    assert fake.play_calls[-1] == (None, 0)


def test_alarm_popup_closes_automatically_when_sound_ends(qtbot, monkeypatch) -> None:
    fake, _parent, dialog = _start_alarm_popup(qtbot, monkeypatch)

    dialog._close_timer.timeout.emit()

    assert not dialog.isVisible()
    assert notify_sound._active_alarm_dialog is None
    assert fake.play_calls[-1] == (None, 0)


def test_closed_alarm_popups_are_deleted_instead_of_accumulating(qtbot, monkeypatch) -> None:
    fake = _FakeWinSound()
    monkeypatch.setattr(notify_sound, "winsound", fake)
    monkeypatch.setattr(
        notify_sound, "_get_success_alarm_path", lambda: "completion-alarm.wav"
    )
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)

    for _ in range(3):
        dialog = notify_sound.play_completion_sound("success", parent)
        assert dialog is not None
        dialog.accept()
        qtbot.wait(1)

    assert parent.findChildren(notify_sound.CompletionAlarmDialog) == []
    assert notify_sound._active_alarm_dialog is None


def test_destroying_an_old_popup_does_not_stop_the_current_alarm(qtbot, monkeypatch) -> None:
    stop_calls = []
    monkeypatch.setattr(notify_sound, "stop_completion_sound", lambda: stop_calls.append(True))
    old_dialog = notify_sound.CompletionAlarmDialog()
    current_dialog = notify_sound.CompletionAlarmDialog()
    qtbot.addWidget(old_dialog)
    qtbot.addWidget(current_dialog)
    notify_sound._active_alarm_dialog = current_dialog

    notify_sound._on_alarm_dialog_destroyed(old_dialog)

    assert notify_sound._active_alarm_dialog is current_dialog
    assert stop_calls == []
    notify_sound._active_alarm_dialog = None


def test_failed_success_alarm_does_not_show_a_stale_stop_popup(qtbot, monkeypatch) -> None:
    class _FailingWinSound(_FakeWinSound):
        def PlaySound(self, sound, flags) -> None:
            raise OSError("audio device unavailable")

    monkeypatch.setattr(notify_sound, "winsound", _FailingWinSound())
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)

    dialog = notify_sound.play_completion_sound("success", parent)

    assert dialog is None
    assert parent.findChildren(notify_sound.CompletionAlarmDialog) == []


def test_aborted_measurement_does_not_play_a_system_sound(monkeypatch) -> None:
    fake = _FakeWinSound()
    monkeypatch.setattr(notify_sound, "winsound", fake)

    notify_sound.play_completion_sound("aborted")

    assert fake.play_calls == [(None, 0)]
    assert fake.beep_calls == []


def test_progress_bar_completion_state_can_be_set_and_reset(qtbot) -> None:
    progress_bar = QtWidgets.QProgressBar()
    qtbot.addWidget(progress_bar)
    progress_bar.setMaximum(12)
    progress_bar.setValue(5)

    set_measurement_completed(progress_bar, True)

    assert progress_bar.value() == 12
    assert progress_bar.property("measurementCompleted") is True

    set_measurement_completed(progress_bar, False)

    assert progress_bar.property("measurementCompleted") is False


@pytest.mark.parametrize(
    ("tab_class", "running_flag", "stop_handler", "contact_stop", "measurement_stop"),
    [
        (
            OPVTab,
            "_contact_check_running",
            "_on_stop_clicked",
            "stop_contact_check",
            "stop_measurement",
        ),
        (
            JVLTab,
            "_contact_check_running",
            "_on_stop_clicked",
            "stop_contact_check",
            "stop_measurement",
        ),
        (
            DualChannelTab,
            "_contact_check_running_a",
            "_on_mode_a_stop_clicked",
            "stop_contact_check_a",
            "stop_mode_a",
        ),
        (
            DualChannelTab,
            "_contact_check_running_b",
            "_on_mode_b_stop_clicked",
            "stop_contact_check_b",
            "stop_mode_b",
        ),
    ],
)
def test_red_stop_button_stops_contact_check_when_it_is_running(
    qtbot,
    monkeypatch,
    tab_class,
    running_flag,
    stop_handler,
    contact_stop,
    measurement_stop,
) -> None:
    calls = []
    tab = tab_class()
    qtbot.addWidget(tab)
    monkeypatch.setattr(tab.viewModel, contact_stop, lambda: calls.append("contact"))
    monkeypatch.setattr(tab.viewModel, measurement_stop, lambda: calls.append("measurement"))
    setattr(tab, running_flag, True)

    getattr(tab, stop_handler)()

    assert calls == ["contact"]


@pytest.mark.parametrize(
    ("tab_class", "progress_bar_name", "handler_name", "handler_args"),
    [
        (OPVTab, "opv_progressBar", "_on_finished_ok", ([], "", False)),
        (JVLTab, "jvl_progressBar", "_on_finished_ok", ([], "", False)),
        (DualChannelTab, "dual_a_progressBar", "_on_finished_ok_a", ([], "", False)),
        (
            DualChannelTab,
            "dual_b_progressBar",
            "_on_finished_ok_b",
            ([], "", "", False),
        ),
    ],
)
def test_all_measurement_modes_turn_progress_green_on_success(
    qtbot, monkeypatch, tab_class, progress_bar_name, handler_name, handler_args
) -> None:
    outcomes = []
    tab_module = sys.modules[tab_class.__module__]
    monkeypatch.setattr(
        tab_module,
        "play_completion_sound",
        lambda outcome, parent: outcomes.append((outcome, parent)),
    )
    tab = tab_class()
    qtbot.addWidget(tab)
    progress_bar = getattr(tab, progress_bar_name)
    progress_bar.setMaximum(10)
    progress_bar.setValue(6)

    getattr(tab, handler_name)(*handler_args)

    assert progress_bar.value() == 10
    assert progress_bar.property("measurementCompleted") is True
    assert outcomes == [("success", tab)]
