"""Windows固有ユーティリティ(スリープ抑制)。

EQEプロジェクト(``EQE/src/utils/system/win32_utils.py``)の
``prevent_sleep``を踏襲する。長時間の掃引測定中にWindowsが
スリープ・ディスプレイ消灯して測定が中断されるのを防ぐ。
win32以外のプラットフォームでは何もしない。

Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import sys

from utils.logger import get_logger

logger = get_logger("win32_utils")

# SetThreadExecutionState のフラグ定数
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def _set_thread_execution_state(flags: int):
    """Win32 API ``SetThreadExecutionState`` を呼び出す(テスト時にモック化する分離点)。"""
    import ctypes

    return ctypes.windll.kernel32.SetThreadExecutionState(flags)


def prevent_sleep(prevent: bool = True) -> None:
    """Windowsのスリープ・ディスプレイ消灯を一時的に防止または通常状態へ復帰する。

    Args:
        prevent: Trueでスリープ防止、Falseで通常状態に復帰。
    """
    if sys.platform != "win32":
        return
    try:
        if prevent:
            logger.info("Preventing system and display sleep during measurement.")
            _set_thread_execution_state(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
        else:
            logger.info("Restoring normal system sleep state.")
            _set_thread_execution_state(ES_CONTINUOUS)
    except Exception as e:  # noqa: BLE001 - スリープ制御失敗で測定は止めない
        logger.error("Failed to set thread execution state: %s", e)
