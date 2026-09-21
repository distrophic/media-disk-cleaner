"""Панель фильтров над таблицей результатов."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.media_filter_proxy import MediaFilterProxyModel

_SIZE_UNITS = (("Б", 1), ("КБ", 1024), ("МБ", 1024**2), ("ГБ", 1024**3))


class FilterBarWidget(QWidget):
    filters_changed = Signal()

    def __init__(self, proxy: MediaFilterProxyModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proxy = proxy
        self._folder: Path | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        self.category = QComboBox()
        self.category.addItem("Все категории", None)
        self.category.addItem("Изображения", "image")
        self.category.addItem("Видео", "video")
        self.category.addItem("Аудио", "audio")
        self.extension = QComboBox()
        self.extension.setMinimumWidth(110)
        self._reset_extensions()
        self.drive = QComboBox()
        self.drive.addItem("Все диски", None)
        self.drive.addItem("C:", "C:")
        self.drive.addItem("D:", "D:")
        self.min_size = QLineEdit()
        self.min_size.setPlaceholderText("Мин. размер")
        self.min_size.setMaximumWidth(90)
        self.max_size = QLineEdit()
        self.max_size.setPlaceholderText("Макс. размер")
        self.max_size.setMaximumWidth(90)
        self.size_unit = QComboBox()
        for label, _factor in _SIZE_UNITS:
            self.size_unit.addItem(label)
        self.size_unit.setCurrentText("МБ")
        row1.addWidget(QLabel("Категория"))
        row1.addWidget(self.category)
        row1.addWidget(QLabel("Тип"))
        row1.addWidget(self.extension)
        row1.addWidget(QLabel("Диск"))
        row1.addWidget(self.drive)
        row1.addWidget(self.min_size)
        row1.addWidget(QLabel("—"))
        row1.addWidget(self.max_size)
        row1.addWidget(self.size_unit)
        row1.addStretch(1)

        row2 = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        today = QDate.currentDate()
        self.date_from.setDate(today.addYears(-10))
        self.date_to.setDate(today)
        self.use_dates = QCheckBox("Дата изменения")
        self.large_only = QCheckBox("Только крупные (≥ 100 МБ)")
        self.old_only = QCheckBox("Только старые (≥ 1 года)")
        self.selected_only = QCheckBox("Только выбранные")
        self.folder_button = QPushButton("Папка фильтра")
        self.folder_button.setObjectName("secondaryButton")
        self.folder_label = QLabel("папка не задана")
        self.reset_button = QPushButton("Сбросить фильтры")
        self.reset_button.setObjectName("secondaryButton")
        for box in (self.use_dates, self.large_only, self.old_only, self.selected_only):
            box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        row2.addWidget(self.use_dates)
        row2.addWidget(self.date_from)
        row2.addWidget(self.date_to)
        row2.addStretch(1)

        row3 = QHBoxLayout()
        row3.addWidget(self.large_only)
        row3.addWidget(self.old_only)
        row3.addWidget(self.selected_only)
        row3.addWidget(self.folder_button)
        row3.addWidget(self.folder_label, 1)
        row3.addWidget(self.reset_button)

        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)

        for widget in (
            self.category,
            self.extension,
            self.drive,
            self.size_unit,
        ):
            widget.currentIndexChanged.connect(self._apply)
        self.min_size.editingFinished.connect(self._apply)
        self.max_size.editingFinished.connect(self._apply)
        self.use_dates.toggled.connect(self._apply)
        self.date_from.dateChanged.connect(self._apply)
        self.date_to.dateChanged.connect(self._apply)
        self.large_only.toggled.connect(self._apply)
        self.old_only.toggled.connect(self._apply)
        self.selected_only.toggled.connect(self._apply)
        self.folder_button.clicked.connect(self._choose_folder)
        self.reset_button.clicked.connect(self.reset)

    def set_extensions(self, extensions: list[str]) -> None:
        current = self.extension.currentData()
        self.extension.blockSignals(True)
        self._reset_extensions()
        for ext in sorted(set(extensions)):
            if ext:
                self.extension.addItem(ext, ext)
        index = self.extension.findData(current)
        if index >= 0:
            self.extension.setCurrentIndex(index)
        self.extension.blockSignals(False)

    def sync_from_proxy_preset(self, category: str | None, large_only: bool) -> None:
        self.category.blockSignals(True)
        self.large_only.blockSignals(True)
        index = self.category.findData(category)
        self.category.setCurrentIndex(index if index >= 0 else 0)
        self.large_only.setChecked(large_only)
        self.category.blockSignals(False)
        self.large_only.blockSignals(False)

    def reset(self) -> None:
        self.category.setCurrentIndex(0)
        self.extension.setCurrentIndex(0)
        self.drive.setCurrentIndex(0)
        self.min_size.clear()
        self.max_size.clear()
        self.use_dates.setChecked(False)
        self.large_only.setChecked(False)
        self.old_only.setChecked(False)
        self.selected_only.setChecked(False)
        self._folder = None
        self.folder_label.setText("папка не задана")
        self._proxy.reset_filters()
        self.filters_changed.emit()

    def _reset_extensions(self) -> None:
        self.extension.clear()
        self.extension.addItem("Все типы", None)

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Фильтровать по папке")
        if not selected:
            return
        self._folder = Path(selected)
        self.folder_label.setText(str(self._folder))
        self._apply()

    def _apply(self) -> None:
        self._proxy.begin_update()
        try:
            self._proxy.set_category(self.category.currentData())
            self._proxy.set_extension(self.extension.currentData())
            self._proxy.set_drive(self.drive.currentData())
            self._proxy.set_size_range(self._parse_size(self.min_size), self._parse_size(self.max_size))
            if self.use_dates.isChecked():
                start_q = self.date_from.date()
                end_q = self.date_to.date()
                start = datetime(start_q.year(), start_q.month(), start_q.day())
                end = datetime(end_q.year(), end_q.month(), end_q.day(), 23, 59, 59)
                self._proxy.set_date_range(start, end)
            else:
                self._proxy.set_date_range(None, None)
            self._proxy.set_large_only(self.large_only.isChecked())
            self._proxy.set_old_only(self.old_only.isChecked())
            self._proxy.set_selected_only(self.selected_only.isChecked())
            self._proxy.set_folder(self._folder)
        finally:
            self._proxy.end_update()
        self.filters_changed.emit()

    def _parse_size(self, field: QLineEdit) -> int | None:
        text = field.text().strip().replace(",", ".")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        if value < 0:
            return None
        factor = _SIZE_UNITS[self.size_unit.currentIndex()][1]
        return int(value * factor)
