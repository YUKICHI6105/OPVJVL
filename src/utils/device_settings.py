"""機器設定(接続先ポート・機器種別等)のロード・保存を担当するモジュール。

EQEの構成(単一settings.jsonに全設定を集約)に合わせ、実体は
``utils.persistence`` に統合した。本モジュールは機器設定キーのみを
抜き出す薄いラッパーとして既存API(``load_device_settings`` /
``save_device_settings`` / ``DEFAULT_DEVICE_SETTINGS``)を維持する。

旧バージョン(OPV/JVL/2ch活用モードA/Bをそれぞれ個別に設定していた頃)の
settings.jsonからの移行(旧キー opv_*/jvl_*/dual_a_*/dual_b_* → 新キー
opvjvl_*/dual_*)も本モジュールが担う。

Qt/PyQt5/PyQt6に一切依存しない純粋なPythonモジュール。
"""
from __future__ import annotations

from utils import persistence

#: 機器設定のデフォルト値(唯一の正は persistence.DEVICE_SETTINGS_DEFAULTS)
DEFAULT_DEVICE_SETTINGS: dict = persistence.DEVICE_SETTINGS_DEFAULTS

#: 新キー → 旧キーの移行元候補(優先順)。
#: OPV/JVL共通キーはOPV側の値を優先し(無ければJVL側)、
#: 2ch活用共通キーはモードA側の値を優先する(無ければモードB側)。
#: 輝度計(BM9)ポートはOPVモードに存在しなかったため、JVL→2ch活用モードAの順とする。
_OLD_KEY_FALLBACKS: dict = {
    "opvjvl_device_type_index": ("opv_device_type_index", "jvl_device_type_index"),
    "opvjvl_connection": ("opv_connection", "jvl_connection"),
    "opvjvl_channel": ("opv_channel", "jvl_channel"),
    "opvjvl_bm9_port": ("jvl_bm9_port", "dual_a_bm9_port"),
    "opvjvl_use_mock": ("opv_use_mock", "jvl_use_mock"),
    "dual_connection": ("dual_a_connection", "dual_b_connection"),
    "dual_bm9_port": ("dual_a_bm9_port", "dual_b_bm9_port"),
    "dual_use_mock": ("dual_a_use_mock", "dual_b_use_mock"),
}


def load_device_settings() -> dict:
    """``settings.json`` から機器設定(機器設定ダイアログが扱うキーのみ)を読み込む。

    ファイルが存在しない・壊れている場合や既存キーが一部欠けている場合は
    デフォルト値で補完される(persistence.load_settings に委譲)。

    さらに、settings.json に新キー(opvjvl_*/dual_*)が存在せず、
    旧キー(opv_*/jvl_*/dual_a_*/dual_b_*)が存在する場合は、
    ``_OLD_KEY_FALLBACKS`` の優先順で旧値を引き継ぐ(1回限りの移行読み替え。
    ファイル自体は本関数呼び出しだけでは書き換わらず、次回保存時に新キーで
    永続化される)。移行判定には「ファイルに実際に書かれているキーか否か」が
    必要なため、デフォルトとマージ済みの ``load_settings`` ではなく、
    生の内容を返す ``load_raw_settings`` を参照する。
    """
    settings = persistence.load_settings()
    raw = persistence.load_raw_settings()

    result = {}
    for key, default in DEFAULT_DEVICE_SETTINGS.items():
        if key in raw:
            result[key] = settings.get(key, default)
            continue
        migrated_value = default
        for old_key in _OLD_KEY_FALLBACKS.get(key, ()):
            if old_key in raw:
                migrated_value = raw[old_key]
                break
        result[key] = migrated_value
    return result


def save_device_settings(settings: dict) -> None:
    """機器設定を ``settings.json`` へ永続化する(既存の他キーは破壊しない)。"""
    persistence.save_settings(settings)
