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
    assert loaded["opvjvl_bm9_port"] == persistence.DEFAULT_SETTINGS["opvjvl_bm9_port"]


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

    device_settings.save_device_settings({"opvjvl_connection": "COM9"})
    # 同じファイルに書かれ、機器設定以外のキーも共存できる
    persistence.save_settings({"opv_v_min": -0.7})

    loaded_device = device_settings.load_device_settings()
    assert loaded_device["opvjvl_connection"] == "COM9"
    # 機器設定キーのみが返る
    assert set(loaded_device.keys()) == set(device_settings.DEFAULT_DEVICE_SETTINGS.keys())

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["opvjvl_connection"] == "COM9"
    assert raw["opv_v_min"] == -0.7


def test_load_raw_settings_returns_file_contents_without_default_merge(monkeypatch, tmp_path):
    """load_raw_settingsがデフォルト補完なしでファイルの生の内容を返すことを検証。"""
    path = _use_tmp_settings(monkeypatch, tmp_path)

    assert persistence.load_raw_settings() == {}

    path.write_text(json.dumps({"opv_connection": "COM7"}), encoding="utf-8")
    raw = persistence.load_raw_settings()
    assert raw == {"opv_connection": "COM7"}
    assert "opvjvl_connection" not in raw


def test_load_raw_settings_returns_empty_dict_on_corrupted_json(monkeypatch, tmp_path):
    """破損したJSONではload_raw_settingsが例外にならず空辞書を返すことを検証。"""
    path = _use_tmp_settings(monkeypatch, tmp_path)
    path.write_text("{ this is not valid json", encoding="utf-8")

    assert persistence.load_raw_settings() == {}


def test_device_settings_migrates_from_old_opv_jvl_keys(monkeypatch, tmp_path):
    """旧settings.json(opv_*/jvl_*)からopvjvl_*キーへ移行されることを検証(opv優先、無ければjvl)。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings(
        {
            "opv_device_type_index": 1,
            "opv_connection": "COM11",
            "opv_channel": "smub",
            "opv_use_mock": True,
            "jvl_device_type_index": 0,
            "jvl_connection": "COM12",
            "jvl_channel": "smua",
            "jvl_bm9_port": "COM13",
            "jvl_use_mock": False,
        }
    )

    loaded = device_settings.load_device_settings()
    # opv_* が優先される
    assert loaded["opvjvl_device_type_index"] == 1
    assert loaded["opvjvl_connection"] == "COM11"
    assert loaded["opvjvl_channel"] == "smub"
    assert loaded["opvjvl_use_mock"] is True
    # bm9ポートはOPVに存在しないためJVL側から移行される
    assert loaded["opvjvl_bm9_port"] == "COM13"


def test_device_settings_migrates_bm9_port_from_dual_a_when_jvl_missing(monkeypatch, tmp_path):
    """jvl_bm9_portが無い場合はdual_a_bm9_portから移行されることを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings({"dual_a_bm9_port": "COM21"})

    loaded = device_settings.load_device_settings()
    assert loaded["opvjvl_bm9_port"] == "COM21"


def test_device_settings_migrates_from_old_dual_a_b_keys(monkeypatch, tmp_path):
    """旧settings.json(dual_a_*/dual_b_*)からdual_*キーへ移行されることを検証(A優先、無ければB)。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings(
        {
            "dual_a_connection": "USB0::A",
            "dual_a_bm9_port": "COM31",
            "dual_a_use_mock": True,
            "dual_b_connection": "USB0::B",
            "dual_b_bm9_port": "COM32",
            "dual_b_use_mock": False,
        }
    )

    loaded = device_settings.load_device_settings()
    assert loaded["dual_connection"] == "USB0::A"
    assert loaded["dual_bm9_port"] == "COM31"
    assert loaded["dual_use_mock"] is True


def test_device_settings_migrates_dual_from_b_when_a_missing(monkeypatch, tmp_path):
    """dual_a_*が無い場合はdual_b_*から移行されることを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings({"dual_b_connection": "USB0::B", "dual_b_bm9_port": "COM32"})

    loaded = device_settings.load_device_settings()
    assert loaded["dual_connection"] == "USB0::B"
    assert loaded["dual_bm9_port"] == "COM32"


def test_device_settings_prefers_new_keys_over_old_when_both_present(monkeypatch, tmp_path):
    """新キーが既に書かれている場合は旧キーより新キーが優先されることを検証。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    persistence.save_settings(
        {
            "opvjvl_connection": "COM99",
            "opv_connection": "COM11",
            "jvl_connection": "COM12",
        }
    )

    loaded = device_settings.load_device_settings()
    assert loaded["opvjvl_connection"] == "COM99"


def test_device_settings_uses_defaults_when_no_keys_at_all(monkeypatch, tmp_path):
    """新旧いずれのキーも無い場合はデフォルト値になることを検証(初回起動相当)。"""
    _use_tmp_settings(monkeypatch, tmp_path)

    loaded = device_settings.load_device_settings()
    assert loaded == device_settings.DEFAULT_DEVICE_SETTINGS


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
