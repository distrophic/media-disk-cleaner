"""Пути ресурсов и пользовательских данных.

Изменяемые журналы, отчёты и настройки никогда не пишутся в каталог
сборки PyInstaller (``sys._MEIPASS``) и не зависят от текущей рабочей папки.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.constants import APP_ID
from app.host import user_data_home


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """Неизменяемые ресурсы: рядом с исходниками или внутри сборки."""
    if is_frozen():
        return Path(str(sys._MEIPASS))
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    return user_data_home() / APP_ID


def logs_dir() -> Path:
    return user_data_root() / "logs"


def reports_dir() -> Path:
    return user_data_root() / "reports"


def settings_dir() -> Path:
    return user_data_root() / "settings"


def technical_log_path() -> Path:
    return logs_dir() / "app.log"


def operations_journal_path() -> Path:
    return logs_dir() / "operations.jsonl"


def ensure_user_dirs() -> None:
    """Создать каталоги, доступные обычной учётной записи."""
    for folder in (logs_dir(), reports_dir(), settings_dir()):
        folder.mkdir(parents=True, exist_ok=True)
