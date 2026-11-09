"""登録したアラーム音源を設定ファイルの隣にコピーして保持する。"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from utils.paths import get_settings_path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def library_directory() -> Path:
    return Path(get_settings_path()).resolve().parent / "alarm_sounds"


def list_sounds() -> list[Path]:
    directory = library_directory()
    if not directory.is_dir():
        return []
    return sorted((path for path in directory.iterdir()
                   if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
                   and path.stat().st_size > 0), key=lambda path: path.name.casefold())


def _digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def import_sound(source: str) -> str:
    """同名・同内容は再利用し、同名で内容が違う場合は連番で追加する。"""
    original = Path(source).expanduser().resolve()
    if original.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValueError("WAV、MP3、FLAC、OGG、M4Aの音源を指定してください。")
    if original.stat().st_size == 0:
        raise ValueError("音源ファイルが空です。")
    source_digest = _digest(original)
    directory = library_directory()
    directory.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        name = original.name if number == 1 else f"{original.stem} ({number}){original.suffix}"
        target = directory / name
        if target.exists():
            if _digest(target) == source_digest:
                return str(target)
            number += 1
            continue
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        os.close(descriptor)
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
            with os.fdopen(descriptor, "wb") as output, original.open("rb") as incoming:
                shutil.copyfileobj(incoming, output)
            os.replace(temporary, target)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        return str(target)
