"""アプリケーションのベースディレクトリおよび設定・ログ出力先の解決ユーティリティ。

EQEプロジェクト(``EQE/src/utils/system/paths.py``)の配置基準を踏襲する:

* **設定ファイル (settings.json)**:
  - 通常実行: プロジェクトルートの ``settings.json``
  - EXE実行(PyInstaller): Roaming AppData (``%APPDATA%/OPVJVL/settings.json``)
* **ログファイル (log/)**:
  - 通常実行: プロジェクトルートの ``log/``
  - EXE実行: Local AppData (``%LOCALAPPDATA%/OPVJVL/log/``)

Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import os
import sys

_APP_NAME = "OPVJVL"


def get_base_dir() -> str:
    """アプリケーションのベースディレクトリの絶対パスを返す。

    PyInstaller製EXEの場合は ``sys.executable`` の親ディレクトリ、
    通常実行の場合はプロジェクトルート(``src/`` の親)を返す。
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # src/utils/paths.py から見たプロジェクトルートは2階層上
    utils_dir = os.path.dirname(os.path.abspath(__file__))  # src/utils
    src_dir = os.path.dirname(utils_dir)  # src
    return os.path.dirname(src_dir)


def get_settings_path() -> str:
    """設定ファイル (settings.json) の絶対パスを返す。

    環境変数 ``OPVJVL_SETTINGS_PATH`` が設定されている場合はそれを優先する
    (テストや特殊環境で設定ファイルを差し替えるための逃げ道)。
    """
    override = os.environ.get("OPVJVL_SETTINGS_PATH")
    if override:
        parent = os.path.dirname(override)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return override

    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        target_dir = os.path.join(appdata, _APP_NAME)
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, "settings.json")
    return os.path.join(get_base_dir(), "settings.json")


def get_log_dir() -> str:
    """ログ出力先ディレクトリの絶対パスを返す(無ければ作成する)。

    環境変数 ``OPVJVL_LOG_DIR`` が設定されている場合はそれを優先する
    (テストや特殊環境でログ出力先を差し替えるための逃げ道)。
    """
    override = os.environ.get("OPVJVL_LOG_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override

    if getattr(sys, "frozen", False):
        localappdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        target_dir = os.path.join(localappdata, _APP_NAME, "log")
    else:
        target_dir = os.path.join(get_base_dir(), "log")
    os.makedirs(target_dir, exist_ok=True)
    return target_dir
