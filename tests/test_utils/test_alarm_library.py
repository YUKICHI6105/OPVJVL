"""音源のコピー保持・重複登録・同名衝突・コピー失敗時の保護。"""
from pathlib import Path

import pytest

from utils import alarm_library


def test_registered_audio_survives_removal_of_original(tmp_path, monkeypatch):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    original = tmp_path / "日本語 音源.MP3"
    original.write_bytes(b"audio data")
    stored = Path(alarm_library.import_sound(str(original)))
    original.unlink()
    assert stored.parent == tmp_path / "alarm_sounds"
    assert stored.read_bytes() == b"audio data"
    assert alarm_library.list_sounds() == [stored]


def test_duplicate_reused_and_different_audio_with_same_name_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    originals = []
    for folder, data in (("one", b"first audio"), ("two", b"second audio")):
        directory = tmp_path / folder
        directory.mkdir()
        original = directory / "alarm.wav"
        original.write_bytes(data)
        originals.append(original)
    first, second = [Path(alarm_library.import_sound(str(path))) for path in originals]
    assert first != second
    assert first.read_bytes() == b"first audio"
    assert second.read_bytes() == b"second audio"
    assert [alarm_library.import_sound(str(path)) for path in originals] == [str(first), str(second)]
    assert len(alarm_library.list_sounds()) == 2


def test_copy_failure_does_not_publish_partial_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("OPVJVL_SETTINGS_PATH", str(tmp_path / "settings.json"))
    original = tmp_path / "alarm.wav"
    original.write_bytes(b"complete audio")
    def fail(incoming, output):
        output.write(b"partial")
        raise OSError("disk full")
    monkeypatch.setattr(alarm_library.shutil, "copyfileobj", fail)
    with pytest.raises(OSError, match="disk full"):
        alarm_library.import_sound(str(original))
    assert list(alarm_library.library_directory().iterdir()) == []
    assert original.read_bytes() == b"complete audio"
