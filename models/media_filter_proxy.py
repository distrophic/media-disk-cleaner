"""Прокси фильтрации и сортировки таблицы медиафайлов.

Сортировка по размеру использует байты, а не отформатированную строку.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from app.constants import LARGE_FILE_THRESHOLD_BYTES, OLD_FILE_AGE_DAYS
from app.host import drive_key, folder_filter_key, folder_filter_match
from models.media_file import MediaFile
from models.media_table_model import (
    COL_CATEGORY,
    COL_DRIVE,
    COL_EXTENSION,
    COL_MODIFIED,
    COL_NAME,
    COL_PATH,
    COL_SELECTED,
    COL_SIZE,
    MediaTableModel,
)


class MediaFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDynamicSortFilter(False)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self._text = ""
        self._category: str | None = None
        self._extension: str | None = None
        self._min_size: int | None = None
        self._max_size: int | None = None
        self._date_from: datetime | None = None
        self._date_to: datetime | None = None
        self._drive: str | None = None
        self._folder: Path | None = None
        self._folder_needle = ""
        self._large_only = False
        self._old_only = False
        self._selected_only = False
        self._old_threshold: datetime | None = None
        self._batch = 0

    def begin_update(self) -> None:
        self._batch += 1

    def end_update(self) -> None:
        self._batch = max(0, self._batch - 1)
        if self._batch == 0:
            super().invalidateFilter()

    def _touch(self) -> None:
        if self._batch == 0:
            super().invalidateFilter()

    def source_model(self) -> MediaTableModel | None:
        model = self.sourceModel()
        return model if isinstance(model, MediaTableModel) else None

    def file_from_proxy(self, proxy_index: QModelIndex) -> MediaFile | None:
        if not proxy_index.isValid():
            return None
        source = self.source_model()
        if source is None:
            return None
        mapped = self.mapToSource(proxy_index)
        return source.file_at(mapped.row())

    def selected_only(self) -> bool:
        return self._selected_only

    def set_text(self, value: str) -> None:
        text = value.strip().casefold()
        if text == self._text:
            return
        self._text = text
        self._touch()

    def set_category(self, value: str | None) -> None:
        if value == self._category:
            return
        self._category = value
        self._touch()

    def set_extension(self, value: str | None) -> None:
        if value:
            ext = value.strip().casefold()
            if ext and not ext.startswith("."):
                ext = f".{ext}"
            self._extension = ext or None
        else:
            self._extension = None
        self._touch()

    def set_size_range(self, minimum: int | None, maximum: int | None) -> None:
        self._min_size = minimum
        self._max_size = maximum
        self._touch()

    def set_date_range(self, start: datetime | None, end: datetime | None) -> None:
        self._date_from = start
        self._date_to = end
        self._touch()

    def set_drive(self, value: str | None) -> None:
        self._drive = drive_key(value) if value else None
        self._touch()

    def set_folder(self, value: Path | None) -> None:
        self._folder = value
        if value is None:
            self._folder_needle = ""
        else:
            self._folder_needle = folder_filter_key(value)
        self._touch()

    def set_large_only(self, enabled: bool) -> None:
        self._large_only = bool(enabled)
        self._touch()

    def set_old_only(self, enabled: bool) -> None:
        self._old_only = bool(enabled)
        self._old_threshold = (
            datetime.now() - timedelta(days=OLD_FILE_AGE_DAYS) if self._old_only else None
        )
        self._touch()

    def set_selected_only(self, enabled: bool) -> None:
        self._selected_only = bool(enabled)
        self._touch()

    def reset_filters(self) -> None:
        self._text = ""
        self._category = None
        self._extension = None
        self._min_size = None
        self._max_size = None
        self._date_from = None
        self._date_to = None
        self._drive = None
        self._folder = None
        self._folder_needle = ""
        self._large_only = False
        self._old_only = False
        self._selected_only = False
        self._old_threshold = None
        self._touch()

    def apply_preset(self, *, category: str | None = None, large_only: bool = False) -> None:
        if self._category == category and self._large_only == large_only:
            return
        self._category = category
        self._large_only = large_only
        self._touch()

    def visible_totals(self) -> tuple[int, int, int, int, int, int]:
        count = 0
        total = 0
        image_size = 0
        video_size = 0
        audio_size = 0
        selected_size = 0
        source = self.source_model()
        if source is None:
            return (0, 0, 0, 0, 0, 0)
        if not self._has_active_filter():
            return source.totals()
        for item in source.iter_files():
            if not self._matches(item):
                continue
            count += 1
            total += item.size_bytes
            if item.category == "image":
                image_size += item.size_bytes
            elif item.category == "video":
                video_size += item.size_bytes
            elif item.category == "audio":
                audio_size += item.size_bytes
            if item.is_selected:
                selected_size += item.size_bytes
        return count, total, image_size, video_size, audio_size, selected_size

    def _has_active_filter(self) -> bool:
        return bool(
            self._text
            or self._category
            or self._extension
            or self._min_size is not None
            or self._max_size is not None
            or self._date_from is not None
            or self._date_to is not None
            or self._drive
            or self._folder is not None
            or self._large_only
            or self._old_only
            or self._selected_only
        )

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source = self.source_model()
        if source is None:
            return False
        item = source.file_at(source_row)
        if item is None:
            return False
        return self._matches(item)

    def _matches(self, item: MediaFile) -> bool:
        if self._category and item.category != self._category:
            return False
        if self._extension and item.extension != self._extension:
            return False
        if self._min_size is not None and item.size_bytes < self._min_size:
            return False
        if self._max_size is not None and item.size_bytes > self._max_size:
            return False
        if self._large_only and item.size_bytes < LARGE_FILE_THRESHOLD_BYTES:
            return False
        if self._old_only:
            if item.modified_at is None or self._old_threshold is None:
                return False
            if item.modified_at > self._old_threshold:
                return False
        if self._selected_only and not item.is_selected:
            return False
        if self._drive and item.drive_key != self._drive:
            return False
        if self._folder_needle:
            haystack = folder_filter_key(item.normalized_path)
            if not folder_filter_match(haystack, self._folder_needle):
                return False
        if self._date_from is not None or self._date_to is not None:
            if item.modified_at is None:
                return False
            stamp = item.modified_at
            if self._date_from is not None and stamp < self._date_from:
                return False
            if self._date_to is not None and stamp > self._date_to:
                return False
        if self._text and self._text not in item.search_blob:
            return False
        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        source = self.source_model()
        if source is None:
            return super().lessThan(left, right)
        left_item = source.file_at(left.row())
        right_item = source.file_at(right.row())
        if left_item is None or right_item is None:
            return super().lessThan(left, right)
        column = left.column()
        if column == COL_SIZE:
            return left_item.size_bytes < right_item.size_bytes
        if column == COL_MODIFIED:
            left_ts = left_item.modified_at or datetime.min
            right_ts = right_item.modified_at or datetime.min
            return left_ts < right_ts
        if column == COL_SELECTED:
            return int(left_item.is_selected) < int(right_item.is_selected)
        if column == COL_NAME:
            return left_item.name.casefold() < right_item.name.casefold()
        if column == COL_EXTENSION:
            return left_item.extension < right_item.extension
        if column == COL_CATEGORY:
            return left_item.category < right_item.category
        if column == COL_PATH:
            return str(left_item.normalized_path).casefold() < str(
                right_item.normalized_path
            ).casefold()
        if column == COL_DRIVE:
            return left_item.drive_key < right_item.drive_key
        return super().lessThan(left, right)
