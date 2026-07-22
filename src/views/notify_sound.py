"""測定完了時の音通知。

正常完了時は、Windowsの通常のオーディオ出力から約20秒間のアラームを
非同期再生する。波形自体はクリップしない範囲で大きく生成し、実際の音量は
Windowsのシステム音量に従う。ユーザーによる中断とエラーは、長いアラームに
せず従来どおりOS標準の短い通知音で鳴らし分ける。

正常完了以外では音を鳴らさない。これにより、Windows標準の効果音が
完了アラームとして鳴ることを防ぐ。
"""
from __future__ import annotations

import atexit
import io
import math
import os
import tempfile
import wave

from qtcompat import QTimer, QtWidgets
from utils.logger import get_logger

try:
    import winsound
except ImportError:  # win32以外の環境
    winsound = None


logger = get_logger(__name__)

_ALARM_DURATION_SECONDS = 20.0
_ALARM_DURATION_MILLISECONDS = int(_ALARM_DURATION_SECONDS * 1_000)


def _build_success_alarm() -> bytes:
    """大きく聞こえる2音交互のアラームをPCM WAVとして生成する。"""
    sample_rate = 16_000
    cycle_seconds = 0.8
    active_seconds = 0.64
    switch_seconds = 0.16
    amplitude = 120  # 8-bit PCMの最大振幅127に近い値(クリップ防止)
    frame_count = int(sample_rate * _ALARM_DURATION_SECONDS)
    frames = bytearray(frame_count)

    for index in range(frame_count):
        elapsed = index / sample_rate
        position = elapsed % cycle_seconds
        if position >= active_seconds:
            frames[index] = 128
            continue

        frequency = 1_000 if int(position / switch_seconds) % 2 == 0 else 1_500
        # 各発音区間の端を短くフェードし、クリックノイズを抑える。
        edge = position % switch_seconds
        envelope = min(1.0, edge / 0.005, (switch_seconds - edge) / 0.005)
        sample = 128 + int(amplitude * envelope * math.sin(2.0 * math.pi * frequency * elapsed))
        frames[index] = max(0, min(255, sample))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(1)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
    return buffer.getvalue()


# 一時WAVファイルの作成元として、生成済み波形をモジュール全体で保持する。
_SUCCESS_ALARM_WAV = _build_success_alarm()
_success_alarm_path: str | None = None


def _get_success_alarm_path() -> str:
    """非同期再生用WAVを一時ファイルへ保存し、そのパスを返す。"""
    global _success_alarm_path
    if _success_alarm_path is not None and os.path.exists(_success_alarm_path):
        return _success_alarm_path

    file_descriptor, path = tempfile.mkstemp(
        prefix="opvjvl_completion_alarm_", suffix=".wav"
    )
    try:
        with os.fdopen(file_descriptor, "wb") as alarm_file:
            alarm_file.write(_SUCCESS_ALARM_WAV)
    except Exception:
        try:
            os.close(file_descriptor)
        except OSError:
            pass
        try:
            os.remove(path)
        except OSError:
            pass
        raise

    _success_alarm_path = path
    return path


def stop_completion_sound() -> None:
    """現在再生中のアラームを直ちに停止する。"""
    if winsound is None:
        return
    try:
        winsound.PlaySound(None, 0)
    except (OSError, RuntimeError):
        pass


def _cleanup_success_alarm_file() -> None:
    """プロセス終了時に再生を止め、一時WAVを削除する。"""
    global _success_alarm_path
    stop_completion_sound()
    path = _success_alarm_path
    _success_alarm_path = None
    if path is not None:
        try:
            os.remove(path)
        except OSError:
            pass


atexit.register(_cleanup_success_alarm_file)


class CompletionAlarmDialog(QtWidgets.QDialog):
    """OS標準音を鳴らさない、停止ボタン付きの非モーダル通知。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("completionAlarmDialog")
        self.setWindowTitle("測定完了")
        self.setModal(False)

        layout = QtWidgets.QVBoxLayout(self)
        title_label = QtWidgets.QLabel("測定が完了しました。", self)
        title_label.setObjectName("completionAlarmTitleLabel")
        title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(title_label)

        message_label = QtWidgets.QLabel(
            "アラームは約20秒後に自動停止し、この画面も閉じます。", self
        )
        message_label.setObjectName("completionAlarmMessageLabel")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        self.stop_button = QtWidgets.QPushButton("アラームを停止", self)
        self.stop_button.setObjectName("completionAlarmStopButton")
        self.stop_button.clicked.connect(self.accept)
        layout.addWidget(self.stop_button)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.setInterval(_ALARM_DURATION_MILLISECONDS)
        self._close_timer.timeout.connect(self.accept)
        self.finished.connect(self._on_finished)

        self.setMinimumWidth(360)

    def showEvent(self, event) -> None:  # noqa: N802 - Qtの命名規則
        super().showEvent(event)
        self._close_timer.start()

    def _on_finished(self, _result: int) -> None:
        self._close_timer.stop()
        if _release_alarm_dialog(self):
            stop_completion_sound()
        self.deleteLater()


_active_alarm_dialog: CompletionAlarmDialog | None = None


def _release_alarm_dialog(dialog: CompletionAlarmDialog) -> bool:
    """現役ダイアログなら参照を解放し、解放できたかを返す。"""
    global _active_alarm_dialog
    if _active_alarm_dialog is dialog:
        _active_alarm_dialog = None
        return True
    return False


def _on_alarm_dialog_destroyed(dialog: CompletionAlarmDialog) -> None:
    """親画面の破棄に伴って通知が破棄された場合も消音する。"""
    if _release_alarm_dialog(dialog):
        stop_completion_sound()


def _close_active_alarm_dialog() -> None:
    """前回のアラーム通知が残っていれば閉じる。"""
    global _active_alarm_dialog
    dialog = _active_alarm_dialog
    _active_alarm_dialog = None
    stop_completion_sound()
    if dialog is not None:
        try:
            dialog.close()
        except RuntimeError:
            # 親タブと一緒にC++オブジェクトだけ先に破棄される場合がある。
            pass


def dismiss_completion_alarm() -> None:
    """表示中の完了通知とアラームを閉じる。"""
    _close_active_alarm_dialog()


def play_completion_sound(
    outcome: str = "success", parent=None
) -> CompletionAlarmDialog | None:
    """計測の結果種別に応じた音を鳴らす。

    Args:
        outcome: ``"success"``(正常完了) / ``"aborted"``(ユーザーによる中断) /
            ``"error"``(エラー)のいずれか。正常完了時だけ音を鳴らす。
        parent: 正常完了時の停止ボタン付きポップアップの親ウィジェット。

    Returns:
        正常完了かつ``parent``が指定された場合は表示したポップアップ。それ以外は
        ``None``。
    """
    global _active_alarm_dialog
    _close_active_alarm_dialog()

    if outcome != "success":
        return None

    if winsound is None:
        logger.warning("測定完了アラームを再生できません: winsoundが利用できません")
        return None

    try:
        # Python 3.13ではSND_MEMORYとSND_ASYNCの併用が禁止されているため、
        # 一時WAVファイルを非同期再生する。これならGUIをブロックせず、
        # PlaySound(None, 0)による即時停止も可能。
        alarm_path = _get_success_alarm_path()
        winsound.PlaySound(alarm_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except (OSError, RuntimeError) as error:
        logger.warning("測定完了アラームを再生できませんでした: %s", error)
        return None

    if parent is None:
        return None

    dialog = CompletionAlarmDialog(parent)
    _active_alarm_dialog = dialog
    dialog.destroyed.connect(
        lambda _object=None, expected=dialog: _on_alarm_dialog_destroyed(expected)
    )
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog
