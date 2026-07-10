"""OPVJVL計測ソフトウェアのカスタムロギングシステム。

EQEプロジェクト(``EQE/src/utils/system/logger.py``)の設計を踏襲し、
標準ログレベルに加えOpenSSHスタイルの3段階カスタムデバッグレベル
(DEBUG1/DEBUG2/DEBUG3)をサポートする。

ログ基本設定:
    * **保存先**: ``utils.paths.get_log_dir()`` 配下の ``opvjvl_software.log``
      (通常実行: プロジェクトルート ``log/``、EXE実行: ``%LOCALAPPDATA%/OPVJVL/log/``)
    * **ローテーション**: 毎日深夜0時。過去30日分を保持
    * **フォーマット**: ``YYYY-MM-DD HH:MM:SS,mmm [ログレベル] ロガー名: メッセージ``

ログレベル設計:
    * **CRITICAL (50)**: 未処理例外によるクラッシュ(sys.excepthookで自己検知)
    * **ERROR (40)**: 続行不可能なエラー(機器接続エラー、バリデーションエラー等)
    * **WARNING (30)**: 処理は続行されるが警戒が必要なログ
    * **INFO (20)**: 起動、測定の開始・終了・中断、データ保存などの主要イベント
    * **DEBUG1 (10)**: 各モジュールの主要関数の実行情報
    * **DEBUG2 (9)**: ハードウェア接続プロセス等の環境制御ログ
    * **DEBUG3 (8)**: 生コマンド通信・測定ループ等の低レベルログ

設定ファイル (settings.json) の ``console_log_level`` / ``file_log_level``
キーで出力制限レベルを制御できる(EQEと同一キー名)。

Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import json
import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler

from utils.paths import get_log_dir, get_settings_path

# OpenSSHスタイルの3段階のDebugレベルを定義
DEBUG1 = 10  # 標準のlogging.DEBUGと同じレベル
DEBUG2 = 9   # より詳細なハードウェアコマンド、データ保存先
DEBUG3 = 8   # 最も詳細な生の値、内部処理ループ

logging.addLevelName(DEBUG1, "DEBUG1")
logging.addLevelName(DEBUG2, "DEBUG2")
logging.addLevelName(DEBUG3, "DEBUG3")


def _log_debug1(self, message, *args, **kws):
    """カスタムログレベル DEBUG1 (10) でメッセージを記録する。"""
    if self.isEnabledFor(DEBUG1):
        self._log(DEBUG1, message, args, **kws)


def _log_debug2(self, message, *args, **kws):
    """カスタムログレベル DEBUG2 (9) でメッセージを記録する。"""
    if self.isEnabledFor(DEBUG2):
        self._log(DEBUG2, message, args, **kws)


def _log_debug3(self, message, *args, **kws):
    """カスタムログレベル DEBUG3 (8) でメッセージを記録する。"""
    if self.isEnabledFor(DEBUG3):
        self._log(DEBUG3, message, args, **kws)


logging.Logger.debug1 = _log_debug1
logging.Logger.debug2 = _log_debug2
logging.Logger.debug3 = _log_debug3
# 簡単なエイリアスとして標準のdebugもDEBUG1へマッピング(EQE踏襲)
logging.Logger.debug = _log_debug1


LEVEL_MAP = {
    "DEBUG1": 10,
    "DEBUG2": 9,
    "DEBUG3": 8,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def parse_level(level_val, default):
    """文字列または整数値から対応するロギングレベル数値を解析して返す。"""
    if isinstance(level_val, int):
        return level_val
    if isinstance(level_val, str):
        level_val = level_val.upper().strip()
        if level_val in LEVEL_MAP:
            return LEVEL_MAP[level_val]
        try:
            return int(level_val)
        except ValueError:
            pass
    return default


# デフォルトの出力制限レベル
console_level = logging.INFO
file_level = DEBUG3

# settings.jsonからログレベル設定を読み込む(EQEと同一キー名)
_settings_path = get_settings_path()
if os.path.exists(_settings_path):
    try:
        with open(_settings_path, "r", encoding="utf-8") as f:
            _cfg = json.load(f)
        if "console_log_level" in _cfg:
            console_level = parse_level(_cfg["console_log_level"], console_level)
        if "file_log_level" in _cfg:
            file_level = parse_level(_cfg["file_log_level"], file_level)
    except Exception:  # noqa: BLE001 - 設定破損時はデフォルトレベルで続行
        pass

# ロギングの初期化設定
LOG_DIR = get_log_dir()
LOG_FILE = os.path.join(LOG_DIR, "opvjvl_software.log")

# 既存のルートハンドラーをクリア(多重初期化防止)
for _handler in logging.root.handlers[:]:
    logging.root.removeHandler(_handler)

logging.root.setLevel(min(console_level, file_level))

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _log_namer(default_name):
    """ローテーション後のファイル名を「ベース名_YYYY-MM-DD.log」に変更する。"""
    pattern = r"^(.*)\.log\.(\d{4}-\d{2}-\d{2})$"
    match = re.match(pattern, default_name)
    if match:
        return f"{match.group(1)}_{match.group(2)}.log"
    return default_name


# ファイルハンドラー (毎日深夜0時にローテーション、過去30日分を保持)
_file_handler = TimedRotatingFileHandler(
    LOG_FILE, when="midnight", interval=1, backupCount=30, encoding="utf-8"
)
_file_handler.namer = _log_namer
_file_handler.setLevel(file_level)
_file_handler.setFormatter(_formatter)

# コンソールハンドラー
_console_handler = logging.StreamHandler()
_console_handler.setLevel(console_level)
_console_handler.setFormatter(_formatter)

logging.root.addHandler(_file_handler)
logging.root.addHandler(_console_handler)


def get_logger(name):
    """指定された名前を持つ Logger インスタンスを取得する。

    debug1(10)/debug2(9)/debug3(8) のカスタムメソッドが利用できる。
    """
    return logging.getLogger(name)


def update_log_levels(console_level_name, file_level_name):
    """実行時にログ出力の制御レベルを動的に更新する。"""
    global console_level, file_level
    console_level = parse_level(console_level_name, logging.INFO)
    file_level = parse_level(file_level_name, DEBUG3)

    logging.root.setLevel(min(console_level, file_level))
    for handler in logging.root.handlers:
        if isinstance(handler, TimedRotatingFileHandler):
            handler.setLevel(file_level)
        else:
            handler.setLevel(console_level)
