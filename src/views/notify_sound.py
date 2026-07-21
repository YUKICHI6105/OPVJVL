"""測定完了時の音通知。

``QApplication.beep()``はPC内蔵スピーカー由来の非常に小さい音になる環境が多く、
測定完了に気づけないという報告があった。Windowsでは``winsound.MessageBeep``で
OS標準の通知音(サウンドカード出力・システム音量に連動)を鳴らすことで、
より確実に聞こえるようにする。winsoundが使えない環境(非Windows)では
``QApplication.beep()``にフォールバックする。

正常完了・ユーザーによる中断・エラーの3種類で異なる音を鳴らし分ける。
"""
from __future__ import annotations

from qtcompat import QApplication

try:
    import winsound
except ImportError:  # win32以外の環境
    winsound = None

#: 結果種別ごとのwinsound定数名(Windowsの「サウンド」設定に対応する識別子)
_SOUND_CONSTANT_NAMES = {
    "success": "MB_ICONASTERISK",  # 正常完了: 通知音
    "aborted": "MB_ICONEXCLAMATION",  # ユーザーによる中断: 警告音
    "error": "MB_ICONHAND",  # エラー: 最も目立つ音
}


def play_completion_sound(outcome: str = "success") -> None:
    """計測の結果種別に応じた音を鳴らす。

    Args:
        outcome: ``"success"``(正常完了) / ``"aborted"``(ユーザーによる中断) /
            ``"error"``(エラー)のいずれか。未知の値は``"success"``として扱う。
    """
    if winsound is not None:
        try:
            constant_name = _SOUND_CONSTANT_NAMES.get(outcome, _SOUND_CONSTANT_NAMES["success"])
            winsound.MessageBeep(getattr(winsound, constant_name))
            return
        except OSError:
            pass
    QApplication.beep()
