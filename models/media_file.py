"""Доменная модель найденного медиафайла."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .safety_result import ExpectedMetadata


@dataclass(slots=True)
class MediaFile:
    """Описание пользовательского медиафайла, найденного сканером.

    Сканер обязан создавать объекты с ``is_selected=False``.
    Пользовательский выбор выполняется позже через ``mark_selected``.
    """

    path: Path
    name: str
    extension: str
    category: str
    size_bytes: int
    created_at: datetime | None
    modified_at: datetime | None
    drive: str
    parent_folder: Path
    is_selected: bool
    scan_root: Path
    safety_status: str
    safety_reason: str | None
    scanned_size_bytes: int
    scanned_modified_timestamp: float | None
    normalized_path: Path
    file_identity: tuple[int, int | None, int | None] | None = None
    mtime_ns: int | None = None
    created_timestamp: float | None = None
    drive_key: str = ""
    search_blob: str = ""

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.parent_folder = Path(self.parent_folder)
        self.scan_root = Path(self.scan_root)
        self.normalized_path = Path(self.normalized_path)
        self.name = str(self.name)
        self.category = str(self.category)
        self.safety_status = str(self.safety_status)
        self.drive = str(self.drive)
        self.extension = _normalize_extension_field(self.extension)
        if self.size_bytes < 0:
            self.size_bytes = 0
        if self.scanned_size_bytes < 0:
            self.scanned_size_bytes = 0
        self.drive_key = self.drive.upper().rstrip("\\")
        self.search_blob = f"{self.name}\0{self.normalized_path}".casefold()

    def expected_metadata(self) -> ExpectedMetadata:
        return ExpectedMetadata(
            size_bytes=self.scanned_size_bytes,
            modified_timestamp=self.scanned_modified_timestamp,
            mtime_ns=self.mtime_ns,
            extension=self.extension,
        )

    def mark_selected(self, selected: bool) -> None:
        """Явный выбор пользователя. Не вызывается сканером."""
        self.is_selected = bool(selected)

    def identity_tuple(self) -> tuple[int, int | None, int | None]:
        if self.file_identity is not None:
            return self.file_identity
        return (self.scanned_size_bytes, self.mtime_ns, None)


def _normalize_extension_field(extension: str) -> str:
    text = str(extension).strip().casefold()
    if not text:
        return ""
    if not text.startswith("."):
        text = f".{text}"
    return text
