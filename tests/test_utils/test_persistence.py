"""設定永続化(utils/persistence.py)とスリープ防止(utils/win32_utils.py)のテスト。"""
from __future__ import annotations

import json
import sys

from utils import device_settings, persistence, win32_utils


def _use_tmp_settings(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(path))
    return path


def test_save_and_load_roundtrip(monkeypatch, tmp_path):
    """保存→復元のラウンドトリップで値が維持されることを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings({"opv_v_min": -0.5, "jvl_use_luminance": False, "shared_sample_name": "dev01"})
    loaded = persistence.load_settings()

    assert loaded["opv_v_min"] == -0.5
    assert loaded["jvl_use_luminance"] is False
    assert loaded["shared_sample_name"] == "dev01"


def test_save_merges_and_preserves_other_keys(monkeypatch, tmp_path):
    """部分保存が既存の他キーを破壊しないことを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings({"opv_v_min": -0.3})
    persistence.save_settings({"jvl_v_max": 2.5})

    loaded = persistence.load_settings()
    assert loaded["opv_v_min"] == -0.3
    assert loaded["jvl_v_max"] == 2.5


def test_load_returns_defaults_when_file_missing(monkeypatch, tmp_path):
    """ファイルが存在しない場合、DEFAULT_SETTINGSの値が返ることを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    loaded = persistence.load_settings()
    assert loaded == persistence.DEFAULT_SETTINGS
    # 返り値はコピーであり、書き換えてもデフォルトは汚染されない
    loaded["opv_v_min"] = 999
    assert persistence.DEFAULT_SETTINGS["opv_v_min"] != 999


def test_load_falls_back_to_defaults_on_corrupted_json(monkeypatch, tmp_path):
    """破損したJSONでも例外にならずデフォルト値で続行することを検証。"""
    path = _use_tmp_settings(monkeypatch, tmp_path)
    path.write_text("{ this is not valid json", encoding="utf-8")

    loaded = persistence.load_settings()
    assert loaded == persistence.DEFAULT_SETTINGS


def test_load_fills_missing_keys_with_defaults(monkeypatch, tmp_path):
    """一部キーのみのファイルでも欠落キーがデフォルト値で補完されることを検証。"""
    path = _use_tmp_settings(monkeypatch, tmp_path)
    path.write_text(json.dumps({"opv_v_max": 2.0}), encoding="utf-8")

    loaded = persistence.load_settings()
    assert loaded["opv_v_max"] == 2.0
    assert loaded["opv_v_min"] == persistence.DEFAULT_SETTINGS["opv_v_min"]
    assert loaded["jvl_bm9_port"] == persistence.DEFAULT_SETTINGS["jvl_bm9_port"]


def test_ensure_settings_exist_creates_file(monkeypatch, tmp_path):
    path = _use_tmp_settings(monkeypatch, tmp_path)

    assert persistence.ensure_settings_exist() is True
    assert path.exists()
    # 2回目は既存のため何もしない
    assert persistence.ensure_settings_exist() is False

    content = json.loads(path.read_text(encoding="utf-8"))
    assert content == persistence.DEFAULT_SETTINGS


def test_device_settings_wrapper_delegates_to_persistence(monkeypatch, tmp_path):
    """device_settings APIがpersistence(単一settings.json)に統合されていることを検証。"""
    path = _use_tmp_settings(monkeypatch, tmp_path)

    device_settings.save_device_settings({"opv_connection": "COM9"})
    # 同じファイルに書かれ、機器設定以外のキーも共存できる
    persistence.save_settings({"opv_v_min": -0.7})

    loaded_device = device_settings.load_device_settings()
    assert loaded_device["opv_connection"] == "COM9"
    # 機器設定キーのみが返る
    assert set(loaded_device.keys()) == set(device_settings.DEFAULT_DEVICE_SETTINGS.keys())

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["opv_connection"] == "COM9"
    assert raw["opv_v_min"] == -0.7


def test_prevent_sleep_calls_win32_api(monkeypatch):
    """prevent_sleepがSetThreadExecutionStateを正しいフラグで呼ぶことを検証(APIはモック化)。"""
    calls = []
    monkeypatch.setattr(win32_utils, "_set_thread_execution_state", calls.append)
    monkeypatch.setattr(sys, "platform", "win32")

    win32_utils.prevent_sleep(True)
    win32_utils.prevent_sleep(False)

    assert calls == [
        win32_utils.ES_CONTINUOUS
        | win32_utils.ES_SYSTEM_REQUIRED
        | win32_utils.ES_DISPLAY_REQUIRED,
        win32_utils.ES_CONTINUOUS,
    ]


def test_prevent_sleep_noop_on_non_windows(monkeypatch):
    """win32以外のプラットフォームでは何もしない安全なフォールバックを検証。"""
    calls = []
    monkeypatch.setattr(win32_utils, "_set_thread_execution_state", calls.append)
    monkeypatch.setattr(sys, "platform", "linux")

    win32_utils.prevent_sleep(True)
    win32_utils.prevent_sleep(False)

    assert calls == []
