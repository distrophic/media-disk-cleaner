"""Таблица результатов без виджетов в ячейках."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QVBoxLayout, QWidget

from models.media_file import MediaFile
from models.media_filter_proxy import MediaFilterProxyModel
from models.media_table_model import COL_ACTION, COL_NAME, COL_PATH, COL_SELECTED, MediaTableModel
from ui.filter_bar_widget import FilterBarWidget


class ResultsWidget(QWidget):
    open_folder_requested = Signal(object)
    filters_changed = Signal()
    current_file_changed = Signal(object)

    def __init__(self, model: MediaTableModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source = model
        self.proxy = MediaFilterProxyModel(self)
        self.proxy.setSourceModel(model)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.filters = FilterBarWidget(self.proxy)
        self.filters.filters_changed.connect(self.filters_changed.emit)
        layout.addWidget(self.filters)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(COL_NAME, QHeaderView.Interactive)
        self.table.setColumnWidth(COL_SELECTED, 36)
        self.table.setColumnWidth(COL_NAME, 240)
        self.table.setColumnWidth(COL_PATH, 360)
        self.table.clicked.connect(self._on_clicked)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.selectionModel().currentChanged.connect(self._on_current_changed)
        layout.addWidget(self.table)
        model.selection_changed.connect(self._on_source_selection)
        model.modelReset.connect(self._emit_current)

    def set_scanning(self, scanning: bool) -> None:
        # Не сортируем десятки тысяч строк автоматически: это грузит CPU.
        # Сортировка — только по клику на заголовок колонки.
        self.table.setSortingEnabled(not scanning)

    def _on_source_selection(self) -> None:
        if self.proxy.selected_only():
            self.proxy.invalidateFilter()

    def _on_clicked(self, index) -> None:
        if not index.isValid():
            return
        if index.column() == COL_ACTION:
            item = self.proxy.file_from_proxy(index)
            if item is not None:
                self.open_folder_requested.emit(item)
            return
        if index.column() == COL_SELECTED:
            return
        source = self.proxy.mapToSource(index)
        self._source.toggle_row(source.row())

    def _on_double_clicked(self, index) -> None:
        item = self.proxy.file_from_proxy(index)
        if item is not None:
            self.open_folder_requested.emit(item)

    def current_file(self) -> MediaFile | None:
        return self.proxy.file_from_proxy(self.table.currentIndex())

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.current_file_changed.emit(self.proxy.file_from_proxy(current))

    def _emit_current(self) -> None:
        self.current_file_changed.emit(self.current_file())

    def refresh_extensions(self) -> None:
        extensions = [item.extension for item in self._source.files()]
        self.filters.set_extensions(extensions)

    def apply_nav_preset(self, category: str | None, large_only: bool) -> None:
        self.table.setUpdatesEnabled(False)
        self.filters.sync_from_proxy_preset(category, large_only)
        self.proxy.apply_preset(category=category, large_only=large_only)
        self.table.setUpdatesEnabled(True)
        self.filters_changed.emit()
        self.current_file_changed.emit(self.current_file())
