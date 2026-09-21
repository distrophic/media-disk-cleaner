"""Агрегированные результаты сканирования (без удаления файлов)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .media_file import MediaFile


@dataclass(slots=True)
class ScanSummary:
    """Сводка без списка файлов — для карточек UI и журнала."""

    files_found: int = 0
    total_size_bytes: int = 0
    image_count: int = 0
    image_size_bytes: int = 0
    video_count: int = 0
    video_size_bytes: int = 0
    audio_count: int = 0
    audio_size_bytes: int = 0
    files_checked: int = 0
    directories_visited: int = 0
    skipped_directories: int = 0
    skipped_files: int = 0
    access_errors: int = 0
    cancelled: bool = False
    elapsed_seconds: float = 0.0


@dataclass(slots=True)
class ScanResult:
    """Полный итог одного запуска сканера.

    Сканер не удаляет файлы. Список ``files`` содержит только кандидатов
    с ``is_selected=False``.
    """

    roots: list[Path]
    files: list[MediaFile] = field(default_factory=list)
    summary: ScanSummary = field(default_factory=ScanSummary)
    skipped_path_reasons: list[tuple[str, str]] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    mode: str = "quick"

    def selected_volume_bytes(self) -> int:
        return sum(item.size_bytes for item in self.files if item.is_selected)

    def selected_count(self) -> int:
        return sum(1 for item in self.files if item.is_selected)
