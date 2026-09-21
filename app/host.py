"""Различия Windows и POSIX без ослабления проверок безопасности."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_windows() -> bool:
    return os.name == "nt" or sys.platform == "win32"


def user_data_home() -> Path:
    """Каталог профиля для журналов. Не зависит от cwd и не пишет в сборку."""
    if is_windows():
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if not local:
            local = str(Path.home() / "AppData" / "Local")
        return Path(local)
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "share"


def volume_id(path: Path) -> str:
    """Идентификатор тома для таблицы и фильтра: ``C:`` или ``/home``."""
    drive = str(path.drive or "").replace("/", "\\").rstrip("\\")
    if drive:
        return drive
    parts = path.parts
    if not parts:
        return "/"
    if parts[0] == "/" and len(parts) == 1:
        return "/"
    if len(parts) >= 2 and parts[1] in {"media", "mnt"}:
        return str(Path(*parts[: min(4, len(parts))]))
    if len(parts) >= 3 and parts[1] == "run" and parts[2] == "media":
        return str(Path(*parts[: min(5, len(parts))]))
    if len(parts) >= 2:
        return "/" + str(parts[1])
    return "/"


def drive_key(drive: str) -> str:
    text = str(drive).strip()
    if not text:
        return ""
    if is_windows() or (len(text) >= 2 and text[1] == ":"):
        return text.upper().rstrip("\\")
    stripped = text.rstrip("/")
    return stripped if stripped else "/"


def folder_filter_key(path: Path | str) -> str:
    text = str(path).replace("\\", "/")
    if is_windows():
        return text.replace("/", "\\").rstrip("\\").casefold()
    return text.rstrip("/")


def folder_filter_match(haystack: str, needle: str) -> bool:
    if not needle:
        return True
    if is_windows():
        sep = "\\"
        left = haystack.replace("/", "\\").rstrip("\\")
        return left == needle or left.startswith(needle + sep)
    left = haystack.replace("\\", "/").rstrip("/")
    return left == needle or left.startswith(needle + "/")
