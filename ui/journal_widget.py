"""Страница журнала операций и экспорта отчёта."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.journal_service import JournalEntry, JournalService


class JournalWidget(QWidget):
    open_journal_requested = Signal()
    clear_journal_requested = Signal()
    export_report_requested = Signal()

    def __init__(self, journal: JournalService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._journal = journal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel(
            "Корзина — кнопка внизу главного окна. Здесь история сканирования "
            "и перемещений. Содержимое файлов, пароли и токены не записываются."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QHBoxLayout()
        self._open_button = QPushButton("Открыть журнал")
        self._open_button.setObjectName("secondaryButton")
        self._clear_button = QPushButton("Очистить журнал")
        self._clear_button.setObjectName("secondaryButton")
        self._export_button = QPushButton("Экспортировать отчёт")
        self._open_button.clicked.connect(self.open_journal_requested.emit)
        self._clear_button.clicked.connect(self.clear_journal_requested.emit)
        self._export_button.clicked.connect(self.export_report_requested.emit)
        buttons.addWidget(self._open_button)
        buttons.addWidget(self._clear_button)
        buttons.addWidget(self._export_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        layout.addWidget(self._view, 1)
        self.reload()

    def reload(self) -> None:
        entries = self._journal.read_recent(400)
        if not entries:
            self._view.setPlainText("Пока нет записей. Выполните сканирование или перемещение в корзину.")
            return
        lines = [_format_entry(entry) for entry in reversed(entries)]
        self._view.setPlainText("\n".join(lines))


def _format_entry(entry: JournalEntry) -> str:
    extra = ""
    if entry.details:
        parts = [f"{key}={value}" for key, value in entry.details.items()]
        extra = " · " + "; ".join(parts)
    return f"{entry.timestamp}  {entry.message}{extra}"
