"""アプリケーション設定(settings.json)の永続化。

EQEプロジェクト(``EQE/src/utils/system/persistence.py``)のパターンを踏襲し、
機器接続設定と各タブの測定パラメータを単一の ``settings.json`` に保存・復元する。
保存先は ``utils.paths.get_settings_path()`` が解決する
(通常実行: プロジェクトルート、EXE実行: ``%APPDATA%/OPVJVL/settings.json``)。

``DEFAULT_SETTINGS`` は初回起動時・キー欠落時のフォールバック値の
「唯一の正(Single Source of Truth)」であり、各Viewのウィジェット初期値と
一致させること(値を二重管理しない)。

Qt非依存の純Pythonモジュール。
"""
from __future__ import annotations

import json
import os

from utils.logger import get_logger
from utils.paths import get_settings_path

logger = get_logger("persistence")

# -----------------------------------------------------------------------
# デフォルト設定値(唯一の正: Single Source of Truth)
# -----------------------------------------------------------------------

#: 機器接続設定のデフォルト(機器設定ダイアログ ``DeviceSettingsDialog`` が扱うキー)
#:
#: OPVモードとJVLモードは実験室では同一のソースメータを、2ch活用モードAとBは
#: 同一のKeithley2612Bを使うため、設定は「OPV/JVL共通」「2ch活用共通」の2系統に
#: 統合されている(旧: opv_*/jvl_*/dual_a_*/dual_b_* の4系統)。
#: 旧settings.jsonからの移行は ``utils.device_settings.load_device_settings`` が行う。
DEVICE_SETTINGS_DEFAULTS: dict = {
    "opvjvl_device_type_index": 0,  # 0=Keithley2400, 1=Keithley2612B
    "opvjvl_connection": "COM5",
    "opvjvl_channel": "smua",
    "opvjvl_bm9_port": "COM4",
    "opvjvl_use_mock": False,
    "dual_connection": "",
    "dual_bm9_port": "COM4",
    "dual_use_mock": False,
}

#: 測定パラメータ・共通保存設定のデフォルト(各タブのウィジェット初期値と一致させる)
MEASUREMENT_SETTINGS_DEFAULTS: dict = {
    # --- 共通保存設定パネル ---
    "shared_sample_name": "",
    "shared_save_dir": "",
    # --- OPVモード ---
    "opv_v_min": -0.1,
    "opv_v_max": 1.1,
    "opv_v_step": 0.02,
    "opv_iteration": 3,
    "opv_nplc": 1.0,
    "opv_delay": 1.0,
    "opv_compliance": 0.02,
    "opv_hysteresis": False,
    # --- JVLモード ---
    "jvl_v_min": -1.0,
    "jvl_v_max": 1.9,
    "jvl_v_step": 0.1,
    "jvl_iteration": 3,
    "jvl_nplc": 1.0,
    "jvl_delay": 1.0,
    "jvl_compliance": 0.02,
    "jvl_use_luminance": True,
    "jvl_hysteresis": False,
    # --- 2ch活用モードA ---
    "dual_a_device_mode": "太陽電池",
    "dual_a_v_min": -0.1,
    "dual_a_v_max": 1.1,
    "dual_a_v_step": 0.02,
    "dual_a_iteration": 3,
    "dual_a_nplc": 1.0,
    "dual_a_delay": 1.0,
    "dual_a_compliance": 0.02,
    "dual_a_hysteresis": False,
    # --- 2ch活用モードB(共通) ---
    "dual_b_save_dir": "",
    # --- 2ch活用モードB チャンネルA ---
    "dual_chA_enabled": False,
    "dual_chA_device_mode": "太陽電池",
    "dual_chA_v_min": -0.1,
    "dual_chA_v_max": 1.1,
    "dual_chA_v_step": 0.02,
    "dual_chA_iteration": 3,
    "dual_chA_nplc": 1.0,
    "dual_chA_delay": 1.0,
    "dual_chA_use_bm9": False,
    "dual_chA_sample_name": "",
    "dual_chA_hysteresis": False,
    # --- 2ch活用モードB チャンネルB ---
    "dual_chB_enabled": False,
    "dual_chB_device_mode": "太陽電池",
    "dual_chB_v_min": -0.1,
    "dual_chB_v_max": 1.1,
    "dual_chB_v_step": 0.02,
    "dual_chB_iteration": 3,
    "dual_chB_nplc": 1.0,
    "dual_chB_delay": 1.0,
    "dual_chB_use_bm9": False,
    "dual_chB_sample_name": "",
    "dual_chB_hysteresis": False,
}

#: settings.json 全体のデフォルト
DEFAULT_SETTINGS: dict = {}
DEFAULT_SETTINGS.update(DEVICE_SETTINGS_DEFAULTS)
DEFAULT_SETTINGS.update(MEASUREMENT_SETTINGS_DEFAULTS)


def ensure_settings_exist() -> bool:
    """``settings.json`` が存在しない場合、デフォルト値で新規作成する。

    Returns:
        bool: 新規作成した場合はTrue、既に存在した場合はFalse。
    """
    settings_file = get_settings_path()
    if os.path.exists(settings_file):
        return False

    logger.info("settings.json が見つかりません。デフォルト値で新規作成します: %s", settings_file)
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        return True
    except OSError as e:
        logger.error("settings.json の自動生成に失敗しました: %s", e)
        return False


def load_settings() -> dict:
    """settings.json を読み込み、デフォルト値とマージした辞書を返す。

    ファイルが存在しない・壊れている(JSONとして読めない)場合は
    ``DEFAULT_SETTINGS`` のコピーを返す。既存キーが一部欠けている場合は
    デフォルト値で補完する。
    """
    merged = dict(DEFAULT_SETTINGS)
    settings_file = get_settings_path()
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                merged.update(loaded)
        except (OSError, ValueError) as e:
            logger.error("settings.json の読み込みに失敗しました(デフォルト値で続行): %s", e)
    return merged


def load_raw_settings() -> dict:
    """settings.json の生の内容を、デフォルト値とのマージなしで返す。

    ``load_settings`` はデフォルトとマージ済みの辞書を返すため、
    「ファイルに実際に書かれているキーか否か」を判別できない。
    旧キー→新キーの移行判定(``utils.device_settings.load_device_settings``)など、
    生の内容を参照したい用途向けの小さなヘルパー。
    ファイルが存在しない・壊れている場合は空辞書を返す。
    """
    settings_file = get_settings_path()
    if not os.path.exists(settings_file):
        return {}
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            return loaded
    except (OSError, ValueError) as e:
        logger.error("settings.json の読み込みに失敗しました(デフォルト値で続行): %s", e)
    return {}


def save_settings(settings_dict: dict) -> None:
    """設定辞書を settings.json へ永続化する(既存内容とマージして部分更新)。"""
    settings_file = get_settings_path()
    try:
        existing: dict = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    existing = loaded
            except (OSError, ValueError):
                pass

        existing.update(settings_dict)

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
    except OSError as e:
        logger.error("settings.json への保存に失敗しました (%s): %s", settings_file, e)
