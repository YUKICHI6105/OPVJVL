"""review.md項目3のテスト: Ctrl+C(SIGINT)での正常終了。

``app.main()`` はQApplicationのイベントループ(``qt_exec``)を実際に回してしまうため
テストでは実行できない。そのため、シグナル登録とQTimerの生成部分を
``app.install_sigint_handler(window)``として関数化してあり、MainWindow相当の
軽量スタブを渡して単体検証する。
"""
from __future__ import annotations

import signal

import app as app_module


class _WindowStub:
    """``close()``だけを持つMainWindowの代替スタブ。"""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_install_sigint_handler_registers_signal_and_returns_timer(qtbot):
    """SIGINTハンドラが登録され、定期実行用のQTimerが返されること。"""
    original_handler = signal.getsignal(signal.SIGINT)
    try:
        window = _WindowStub()
        timer = app_module.install_sigint_handler(window, interval_ms=50)

        # signal.SIGINTのハンドラが本関数のものに差し替わっていること
        assert signal.getsignal(signal.SIGINT) is not original_handler

        # 定期実行用タイマーが起動していること
        assert timer.isActive()
        assert timer.interval() == 50

        timer.stop()
    finally:
        signal.signal(signal.SIGINT, original_handler)


def test_sigint_handler_closes_window():
    """登録したハンドラを直接呼び出すと、window.close()が呼ばれること(正常終了経路)。"""
    original_handler = signal.getsignal(signal.SIGINT)
    try:
        window = _WindowStub()
        app_module.install_sigint_handler(window, interval_ms=1000)

        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)

        assert window.closed is True
    finally:
        signal.signal(signal.SIGINT, original_handler)
