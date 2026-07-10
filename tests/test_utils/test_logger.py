"""ロガー基盤(utils/logger.py)とクラッシュハンドラのテスト。"""
from __future__ import annotations

import logging
import os
import uuid

from utils import logger as logger_mod


def _flush_root_handlers() -> None:
    for handler in logging.root.handlers:
        handler.flush()


def test_get_logger_writes_to_log_file():
    """get_logger()で取得したロガーの出力がログファイルへ書き込まれることを検証。"""
    marker = f"logger-test-{uuid.uuid4()}"
    log = logger_mod.get_logger("test_logger")
    log.info(marker)
    _flush_root_handlers()

    assert os.path.exists(logger_mod.LOG_FILE)
    with open(logger_mod.LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    assert marker in content
    # フォーマット: レベル名とロガー名が含まれる
    assert "[INFO] test_logger" in content


def test_custom_debug_levels_available():
    """EQE踏襲のカスタムデバッグレベル(debug1/2/3)が利用できることを検証。"""
    log = logger_mod.get_logger("test_logger_levels")
    assert hasattr(log, "debug1")
    assert hasattr(log, "debug2")
    assert hasattr(log, "debug3")
    assert logging.getLevelName(logger_mod.DEBUG2) == "DEBUG2"
    assert logging.getLevelName(logger_mod.DEBUG3) == "DEBUG3"

    marker = f"debug3-test-{uuid.uuid4()}"
    log.debug3(marker)
    _flush_root_handlers()
    with open(logger_mod.LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    # デフォルトのファイルレベルはDEBUG3なのでファイルには記録される
    assert marker in content


def test_parse_level():
    assert logger_mod.parse_level("INFO", 0) == logging.INFO
    assert logger_mod.parse_level("DEBUG2", 0) == 9
    assert logger_mod.parse_level("unknown", 42) == 42
    assert logger_mod.parse_level(15, 0) == 15


def test_uncaught_exception_hook_logs_critical(qtbot, monkeypatch):
    """app.log_uncaught_exceptionが未捕捉例外をCRITICALでログに記録することを検証。"""
    import app as app_mod

    # モーダルダイアログ(exec)がテストをブロックしないよう無効化する
    monkeypatch.setattr(app_mod, "qt_exec", lambda obj: None)

    marker = f"crash-test-{uuid.uuid4()}"
    try:
        raise RuntimeError(marker)
    except RuntimeError:
        import sys

        exctype, value, tb = sys.exc_info()

    app_mod.log_uncaught_exception(exctype, value, tb)
    _flush_root_handlers()

    with open(logger_mod.LOG_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Unhandled Exception (Application Crash)" in content
    assert marker in content
