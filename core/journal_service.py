"""Понятная пользователю история операций.

Не хранит содержимое файлов, пароли и токены. Только факты: скан, корзина, ошибки.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.paths import ensure_user_dirs, operations_journal_path

logger = logging.getLogger("media_disk_cleaner.journal")

_FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "passwd",
        "token",
        "secret",
        "api_key",
        "content",
        "bytes",
        "body",
    }
)


@dataclass(slots=True)
class JournalEntry:
    timestamp: str
    kind: str
    message: str
    details: dict[str, Any]


class JournalService:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else operations_journal_path()
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, kind: str, message: str, details: dict[str, Any] | None = None) -> None:
        ensure_user_dirs()
        entry = JournalEntry(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            kind=str(kind),
            message=str(message),
            details=_sanitize(details or {}),
        )
        line = json.dumps(
            {
                "timestamp": entry.timestamp,
                "kind": entry.kind,
                "message": entry.message,
                "details": entry.details,
            },
            ensure_ascii=False,
        )
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        logger.info("%s: %s", kind, message)

    def read_recent(self, limit: int = 400) -> list[JournalEntry]:
        if not self._path.is_file():
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logger.warning("Cannot read journal: %s", exc)
            return []
        entries: list[JournalEntry] = []
        for raw in lines[-max(1, limit) :]:
            text = raw.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            details = payload.get("details")
            entries.append(
                JournalEntry(
                    timestamp=str(payload.get("timestamp", "")),
                    kind=str(payload.get("kind", "")),
                    message=str(payload.get("message", "")),
                    details=details if isinstance(details, dict) else {},
                )
            )
        return entries

    def clear(self) -> None:
        with self._lock:
            self._path.write_text("", encoding="utf-8")
        logger.info("User operations journal cleared")


def _sanitize(details: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in details.items():
        name = str(key).casefold()
        if name in _FORBIDDEN_KEYS:
            continue
        if isinstance(value, Path):
            clean[key] = str(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            clean[key] = value
        elif isinstance(value, list):
            clean[key] = [_json_safe(item) for item in value[:50]]
        elif isinstance(value, dict):
            clean[key] = _sanitize(value)
        else:
            clean[key] = str(value)
    return clean


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
