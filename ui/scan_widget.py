"""Панель режима сканирования и прогресса."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.constants import SCAN_MODE_EXTENDED, SCAN_MODE_QUICK, SCAN_MODE_SELECTIVE
from core.scanner import ScanProgress
from models.media_table_model import format_size_bytes


class ScanWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Быстрое сканирование", SCAN_MODE_QUICK)
        self.mode_combo.addItem("Выборочное сканирование", SCAN_MODE_SELECTIVE)
        self.mode_combo.addItem("Расширенное сканирование диска", SCAN_MODE_EXTENDED)
        self.mode_combo.setCurrentIndex(1)
        self._folder = QLabel("Текущая папка: —")
        self._checked = QLabel("Проверено файлов: 0")
        self._found = QLabel("Найдено медиафайлов: 0")
        self._size = QLabel("Суммарный размер: 0 Б")
        self._elapsed = QLabel("Время: 0 с")
        self._roots = QLabel("Корни: 0 / 0")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        form = QFormLayout()
        form.addRow("Режим", self.mode_combo)
        layout.addLayout(form)
        layout.addWidget(self._folder)
        layout.addWidget(self._checked)
        layout.addWidget(self._found)
        layout.addWidget(self._size)
        layout.addWidget(self._elapsed)
        layout.addWidget(self._roots)
        layout.addWidget(self.progress)

    def current_mode(self) -> str:
        return str(self.mode_combo.currentData())

    def set_busy(self, busy: bool) -> None:
        self.mode_combo.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(1)

    def show_progress(self, progress: ScanProgress) -> None:
        self._folder.setText(f"Текущая папка: {progress.current_folder or '—'}")
        self._checked.setText(f"Проверено файлов: {progress.files_checked}")
        self._found.setText(f"Найдено медиафайлов: {progress.media_found}")
        self._size.setText(f"Суммарный размер: {format_size_bytes(progress.total_size_bytes)}")
        self._elapsed.setText(f"Время: {progress.elapsed_seconds:.1f} с")
        self._roots.setText(f"Корни: {progress.roots_done} / {progress.roots_total}")
        if progress.roots_total > 0:
            self.progress.setRange(0, progress.roots_total)
            self.progress.setValue(min(progress.roots_done, progress.roots_total))

    def reset_progress(self) -> None:
        self._folder.setText("Текущая папка: —")
        self._checked.setText("Проверено файлов: 0")
        self._found.setText("Найдено медиафайлов: 0")
        self._size.setText("Суммарный размер: 0 Б")
        self._elapsed.setText("Время: 0 с")
        self._roots.setText("Корни: 0 / 0")
        self.progress.setRange(0, 0)
