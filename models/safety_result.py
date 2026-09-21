"""Результаты централизованной проверки безопасности."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ExpectedMetadata:
    """Снимок метаданных, сохранённый во время сканирования.

    Используется перед перемещением в корзину, чтобы обнаружить замену
    или изменение файла. Не содержит содержимого файла.
    """

    size_bytes: int
    modified_timestamp: float | None = None
    mtime_ns: int | None = None
    extension: str | None = None


@dataclass(frozen=True, slots=True)
class SafetyResult:
    """Итог ``is_safe_media_file``.

    ``safe`` означает, что объект прошёл все проверки для запрошенной цели
    (индексация или перемещение в корзину). Для корзины требуется явный выбор.
    """

    safe: bool
    reason: str
    normalized_path: Path
    category: str | None
    allows_index: bool = False
    allows_recycle: bool = False
    size_bytes: int | None = None
    mtime_ns: int | None = None
    modified_timestamp: float | None = None
    is_symlink: bool = False
    is_reparse_point: bool = False
    extension: str | None = None

    def as_expected_metadata(self) -> ExpectedMetadata | None:
        if self.size_bytes is None:
            return None
        return ExpectedMetadata(
            size_bytes=self.size_bytes,
            modified_timestamp=self.modified_timestamp,
            mtime_ns=self.mtime_ns,
            extension=self.extension,
        )


@dataclass(frozen=True, slots=True)
class VerifiedMediaTarget:
    """Контракт для RecycleService.

    UI и сканер не должны передавать в сервис корзины произвольный ``Path``.
    Объект создаётся только после централизованной проверки.
    RecycleService обязан вызвать повторную проверку перед send2trash.
    """

    normalized_path: Path
    category: str
    size_bytes: int
    modified_timestamp: float | None
    mtime_ns: int | None
    scan_root: Path
    extension: str
    explicitly_selected: bool = True
