"""Информационные карточки статистики."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from models.media_table_model import format_size_bytes


class _Card(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        self._title = QLabel(title)
        self._title.setObjectName("cardTitle")
        self._value = QLabel("0")
        self._value.setObjectName("cardValue")
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)


class DashboardWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._files = _Card("Найдено файлов")
        self._total = _Card("Общий размер")
        self._images = _Card("Размер изображений")
        self._videos = _Card("Размер видео")
        self._audio = _Card("Размер аудио")
        self._selected = _Card("Выбрано для очистки")
        for card in (
            self._files,
            self._total,
            self._images,
            self._videos,
            self._audio,
            self._selected,
        ):
            layout.addWidget(card)

    def update_from_totals(
        self,
        files_found: int,
        total_size: int,
        image_size: int,
        video_size: int,
        audio_size: int,
        selected_size: int,
    ) -> None:
        self._files.set_value(str(files_found))
        self._total.set_value(format_size_bytes(total_size))
        self._images.set_value(format_size_bytes(image_size))
        self._videos.set_value(format_size_bytes(video_size))
        self._audio.set_value(format_size_bytes(audio_size))
        self._selected.set_value(format_size_bytes(selected_size))
