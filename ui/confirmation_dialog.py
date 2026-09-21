"""Подтверждение перемещения выбранных файлов в корзину."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

from models.media_file import MediaFile
from models.media_table_model import format_size_bytes

_PREVIEW_LIMIT = 8


class RecycleConfirmationDialog(QDialog):
    def __init__(self, files: list[MediaFile], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Переместить в корзину")
        self.setModal(True)
        self.resize(560, 420)
        count = len(files)
        total = sum(item.size_bytes for item in files)
        layout = QVBoxLayout(self)
        summary = QLabel(
            f"Вы собираетесь переместить в корзину {count} файлов "
            f"общим размером {format_size_bytes(total)}. Продолжить?"
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)
        warning = QLabel(
            "Проверьте выбор. Файлы не удаляются окончательно — они попадут "
            "в корзину. Каталоги не удаляются. Системные файлы программа "
            "не трогает. Игровые звуки и картинки из Steam тоже являются медиафайлами: "
            "если они отмечены, они будут перемещены."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addWidget(QLabel("Первые файлы из выбора:"))
        preview = QListWidget()
        for item in files[:_PREVIEW_LIMIT]:
            preview.addItem(f"{item.name}  ({format_size_bytes(item.size_bytes)})  {item.normalized_path}")
        if count > _PREVIEW_LIMIT:
            preview.addItem(f"… и ещё {count - _PREVIEW_LIMIT}")
        layout.addWidget(preview)
        buttons = QDialogButtonBox()
        self._cancel = buttons.addButton("Отмена", QDialogButtonBox.RejectRole)
        self._ok = buttons.addButton("Переместить в корзину", QDialogButtonBox.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._cancel.setDefault(True)
        self._ok.setAutoDefault(False)
