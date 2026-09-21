"""Модель таблицы найденных медиафайлов.

Флажки выбора управляются через Qt.CheckStateRole.
Ни одна строка не создаётся выбранной. В ячейки не помещаются QWidget.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from models.media_file import MediaFile

COL_SELECTED = 0
COL_NAME = 1
COL_CATEGORY = 2
COL_EXTENSION = 3
COL_SIZE = 4
COL_MODIFIED = 5
COL_PATH = 6
COL_DRIVE = 7
COL_STATUS = 8
COL_ACTION = 9
COLUMN_COUNT = 10

HEADERS = (
    "",
    "Имя",
    "Категория",
    "Расширение",
    "Размер",
    "Изменён",
    "Путь",
    "Диск",
    "Статус",
    "Действие",
)

CATEGORY_LABELS = {
    "image": "Изображение",
    "video": "Видео",
    "audio": "Аудио",
}

UNITS = ("Б", "КБ", "МБ", "ГБ", "ТБ")
CHECK_STATE_ROLE_ID = 10


def _role_is_check(role: object) -> bool:
    if role == Qt.ItemDataRole.CheckStateRole or role == Qt.CheckStateRole:
        return True
    return role == CHECK_STATE_ROLE_ID


def _value_is_checked(value: object) -> bool:
    if value == Qt.CheckState.Checked:
        return True
    if value == 2:
        return True
    return False


def format_size_bytes(size_bytes: int) -> str:
    value = float(max(0, int(size_bytes)))
    unit_index = 0
    while value >= 1024.0 and unit_index < len(UNITS) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {UNITS[unit_index]}"
    return f"{value:.2f} {UNITS[unit_index]}"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


class MediaTableModel(QAbstractTableModel):
    """Табличная модель. Сканер не должен вызывать mark_selected."""

    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[MediaFile] = []
        self._count = 0
        self._total = 0
        self._image_size = 0
        self._video_size = 0
        self._audio_size = 0
        self._selected_count = 0
        self._selected_size = 0

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return COLUMN_COUNT

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(HEADERS):
            return HEADERS[section]
        if orientation == Qt.Vertical:
            return str(section + 1)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.NoItemFlags
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == COL_SELECTED:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        item = self._rows[index.row()]
        column = index.column()
        if _role_is_check(role) and column == COL_SELECTED:
            return Qt.CheckState.Checked if item.is_selected else Qt.CheckState.Unchecked
        if role == Qt.UserRole and column == COL_SIZE:
            return int(item.size_bytes)
        if role == Qt.TextAlignmentRole and column == COL_SIZE:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        if column == COL_SELECTED:
            return ""
        if column == COL_NAME:
            return item.name
        if column == COL_CATEGORY:
            return CATEGORY_LABELS.get(item.category, item.category)
        if column == COL_EXTENSION:
            return item.extension
        if column == COL_SIZE:
            return format_size_bytes(item.size_bytes)
        if column == COL_MODIFIED:
            return format_datetime(item.modified_at)
        if column == COL_PATH:
            return str(item.normalized_path)
        if column == COL_DRIVE:
            return item.drive
        if column == COL_STATUS:
            return item.safety_status
        if column == COL_ACTION:
            return "Открыть папку"
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole) -> bool:
        if not index.isValid() or index.column() != COL_SELECTED:
            return False
        if not _role_is_check(role):
            return False
        item = self._rows[index.row()]
        selected = _value_is_checked(value)
        if item.is_selected == selected:
            return False
        self._adjust_selection(item, selected)
        item.mark_selected(selected)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
        self.selection_changed.emit()
        return True

    def toggle_row(self, row: int) -> bool:
        item = self.file_at(row)
        if item is None:
            return False
        index = self.index(row, COL_SELECTED)
        return self.setData(
            index,
            Qt.CheckState.Unchecked if item.is_selected else Qt.CheckState.Checked,
            Qt.ItemDataRole.CheckStateRole,
        )

    def file_at(self, row: int) -> MediaFile | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def files(self) -> list[MediaFile]:
        return list(self._rows)

    def iter_files(self) -> list[MediaFile]:
        return self._rows

    def append_files(self, items: list[MediaFile]) -> None:
        if not items:
            return
        for item in items:
            item.mark_selected(False)
        start = len(self._rows)
        end = start + len(items) - 1
        self.beginInsertRows(QModelIndex(), start, end)
        self._rows.extend(items)
        for item in items:
            self._add_to_totals(item)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self._reset_totals()
        self.endResetModel()
        self.selection_changed.emit()

    def clear_selection(self) -> None:
        if not self._rows or self._selected_count == 0:
            return
        for item in self._rows:
            if item.is_selected:
                item.mark_selected(False)
        self._selected_count = 0
        self._selected_size = 0
        top = self.index(0, COL_SELECTED)
        bottom = self.index(len(self._rows) - 1, COL_SELECTED)
        self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.CheckStateRole])
        self.selection_changed.emit()

    def selected_files(self) -> list[MediaFile]:
        return [item for item in self._rows if item.is_selected]

    def remove_by_paths(self, paths: list[Path]) -> int:
        if not paths:
            return 0
        keys = {str(path).replace("/", "\\").casefold() for path in paths}
        kept: list[MediaFile] = []
        removed = 0
        for item in self._rows:
            key = str(item.normalized_path).replace("/", "\\").casefold()
            if key in keys:
                self._remove_from_totals(item)
                removed += 1
                continue
            kept.append(item)
        if removed == 0:
            return 0
        self.beginResetModel()
        self._rows = kept
        self.endResetModel()
        self.selection_changed.emit()
        return removed

    def selected_count(self) -> int:
        return self._selected_count

    def selected_size_bytes(self) -> int:
        return self._selected_size

    def totals(self) -> tuple[int, int, int, int, int, int]:
        return (
            self._count,
            self._total,
            self._image_size,
            self._video_size,
            self._audio_size,
            self._selected_size,
        )

    def _reset_totals(self) -> None:
        self._count = 0
        self._total = 0
        self._image_size = 0
        self._video_size = 0
        self._audio_size = 0
        self._selected_count = 0
        self._selected_size = 0

    def _add_to_totals(self, item: MediaFile) -> None:
        self._count += 1
        self._total += item.size_bytes
        if item.category == "image":
            self._image_size += item.size_bytes
        elif item.category == "video":
            self._video_size += item.size_bytes
        elif item.category == "audio":
            self._audio_size += item.size_bytes

    def _remove_from_totals(self, item: MediaFile) -> None:
        self._count = max(0, self._count - 1)
        self._total = max(0, self._total - item.size_bytes)
        if item.category == "image":
            self._image_size = max(0, self._image_size - item.size_bytes)
        elif item.category == "video":
            self._video_size = max(0, self._video_size - item.size_bytes)
        elif item.category == "audio":
            self._audio_size = max(0, self._audio_size - item.size_bytes)
        if item.is_selected:
            self._selected_count = max(0, self._selected_count - 1)
            self._selected_size = max(0, self._selected_size - item.size_bytes)

    def _adjust_selection(self, item: MediaFile, selected: bool) -> None:
        if selected:
            self._selected_count += 1
            self._selected_size += item.size_bytes
        else:
            self._selected_count = max(0, self._selected_count - 1)
            self._selected_size = max(0, self._selected_size - item.size_bytes)
