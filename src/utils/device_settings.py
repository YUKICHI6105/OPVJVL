"""機器設定(接続先ポート・機器種別等)のロード・保存を担当するモジュール。

EQEの構成(単一settings.jsonに全設定を集約)に合わせ、実体は
``utils.persistence`` に統合した。本モジュールは機器設定キーのみを
抜き出す薄いラッパーとして既存API(``load_device_settings`` /
``save_device_settings`` / ``DEFAULT_DEVICE_SETTINGS``)を維持する。

Qt/PyQt5/PyQt6に一切依存しない純粋なPythonモジュール。
"""
from __future__ import annotations

from utils import persistence

#: 機器設定のデフォルト値(唯一の正は persistence.DEVICE_SETTINGS_DEFAULTS)
DEFAULT_DEVICE_SETTINGS: dict = persistence.DEVICE_SETTINGS_DEFAULTS


def load_device_settings() -> dict:
    """``settings.json`` から機器設定(機器設定ダイアログが扱うキーのみ)を読み込む。

    ファイルが存在しない・壊れている場合や既存キーが一部欠けている場合は
    デフォルト値で補完される(persistence.load_settings に委譲)。
    """
    settings = persistence.load_settings()
    return {key: settings.get(key, default) for key, default in DEFAULT_DEVICE_SETTINGS.items()}


def save_device_settings(settings: dict) -> None:
    """機器設定を ``settings.json`` へ永続化する(既存の他キーは破壊しない)。"""
    persistence.save_settings(settings)
