"""機器設定(接続先ポート・機器種別等)のデフォルト値・JSON永続化を担当するモジュール。

Qt/PyQt5/PyQt6に一切依存しない純粋なPythonモジュールとし、View層(ダイアログ)からも
テストからも同じロジックを共有できるようにする。

各タブに個別に存在していた機器選択・接続先(COM/VISA)・輝度計(BM9)ポートの入力欄を
1つの設定ダイアログ(``views.dialogs.DeviceSettingsDialog``)に統合するにあたり、
設定値を ``settings.json`` (プロジェクトルート直下)へ永続化し、次回起動時に復元する
ために使用する。
"""
from __future__ import annotations

import json
import os

_SETTINGS_FILENAME = "settings.json"

DEFAULT_DEVICE_SETTINGS: dict = {
    "opv_device_type_index": 0,  # 0=Keithley2400, 1=Keithley2612B
    "opv_connection": "COM5",
    "opv_channel": "smua",
    "jvl_device_type_index": 0,
    "jvl_connection": "COM5",
    "jvl_channel": "smua",
    "jvl_bm9_port": "COM4",
    "dual_a_connection": "",
    "dual_a_bm9_port": "COM4",
    "dual_b_connection": "",
    "dual_b_bm9_port": "COM4",
    "opv_use_mock": False,
    "jvl_use_mock": False,
    "dual_a_use_mock": False,
    "dual_b_use_mock": False,
}


def _settings_path() -> str:
    """``settings.json`` のプロジェクトルート絶対パスを返す。

    このファイル(``src/utils/device_settings.py``)から見て2階層上が
    プロジェクトルートに相当する。
    """
    utils_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(utils_dir)
    project_root = os.path.dirname(src_dir)
    return os.path.join(project_root, _SETTINGS_FILENAME)


def load_device_settings() -> dict:
    """``settings.json`` から機器設定を読み込む。

    ファイルが存在しない、または壊れている(JSONとして読めない)場合は
    ``DEFAULT_DEVICE_SETTINGS`` をそのまま返す。既存キーが一部欠けている
    場合はデフォルト値で補完する。
    """
    path = _settings_path()
    merged = dict(DEFAULT_DEVICE_SETTINGS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for key in DEFAULT_DEVICE_SETTINGS:
                if key in loaded:
                    merged[key] = loaded[key]
        except (OSError, ValueError):
            pass
    return merged


def save_device_settings(settings: dict) -> None:
    """機器設定を ``settings.json`` へ永続化する。

    既存ファイルがあれば読み込んでマージしてから書き込むため、
    (将来追加されうる)機器設定以外の他の設定キーを破壊しない。
    """
    path = _settings_path()
    existing: dict = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, ValueError):
            existing = {}
    existing.update(settings)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
    except OSError:
        pass
