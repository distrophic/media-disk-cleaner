"""Панель предварительного просмотра выбранного файла."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.metadata_service import MediaPreview
from models.media_table_model import CATEGORY_LABELS, format_datetime, format_size_bytes


class PreviewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewPane")
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self._source_pixmap = QPixmap()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("Предпросмотр")
        title.setObjectName("previewTitle")
        layout.addWidget(title)
        self._message = QLabel()
        self._message.setObjectName("previewMessage")
        self._message.setWordWrap(True)
        self._message.setMinimumHeight(48)
        self._message.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        layout.addWidget(self._message)
        self._image = QLabel()
        self._image.setObjectName("previewImage")
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setMinimumHeight(120)
        self._image.setFixedHeight(160)
        self._frame = QFrame()
        self._frame.setObjectName("previewFrame")
        self._frame.setMinimumHeight(140)
        self._frame.setMaximumHeight(180)
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.addWidget(self._image)
        layout.addWidget(self._frame)
        scroll = QScrollArea()
        scroll.setObjectName("previewScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAutoFillBackground(True)
        fields = QWidget()
        fields.setObjectName("previewFields")
        fields.setAutoFillBackground(True)
        fields.setAttribute(Qt.WA_StyledBackground, True)
        fields_layout = QVBoxLayout(fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(4)
        self._name = self._add_value(fields_layout, "Имя")
        self._path = self._add_value(fields_layout, "Путь")
        self._path.setWordWrap(True)
        self._size = self._add_value(fields_layout, "Размер")
        self._created = self._add_value(fields_layout, "Создан")
        self._modified = self._add_value(fields_layout, "Изменён")
        self._resolution = self._add_value(fields_layout, "Разрешение")
        self._category = self._add_value(fields_layout, "Категория")
        fields_layout.addStretch(1)
        scroll.setWidget(fields)
        scroll.viewport().setObjectName("previewScrollViewport")
        scroll.viewport().setAutoFillBackground(True)
        scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        layout.addWidget(scroll, 1)
        self.clear()

    def _add_value(self, layout: QVBoxLayout, caption: str) -> QLabel:
        caption_label = QLabel(caption)
        caption_label.setObjectName("previewCaption")
        value = QLabel("—")
        value.setObjectName("previewValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(caption_label)
        layout.addWidget(value)
        return value

    def clear(self) -> None:
        empty = MediaPreview(
            request_id=0,
            name="",
            path_text="",
            category="",
            extension="",
            size_bytes=0,
            created_at=None,
            modified_at=None,
            placeholder_kind="empty",
            message="Выберите файл в таблице, чтобы увидеть сведения и превью.",
        )
        self.show_preview(empty)

    def show_preview(self, preview: MediaPreview) -> None:
        self._source_pixmap = self._pixmap_for(preview)
        self._name.setText(preview.name or "—")
        self._path.setText(preview.path_text or "—")
        self._size.setText(format_size_bytes(preview.size_bytes) if preview.name else "—")
        self._created.setText(format_datetime(preview.created_at))
        self._modified.setText(format_datetime(preview.modified_at))
        if preview.width and preview.height:
            self._resolution.setText(f"{preview.width} × {preview.height}")
        else:
            self._resolution.setText("—")
        self._category.setText(CATEGORY_LABELS.get(preview.category, preview.category or "—"))
        self._message.setText(preview.message or "")
        self._message.setVisible(bool(preview.message))
        show_image = preview.placeholder_kind != "empty"
        self._frame.setVisible(show_image)
        if show_image:
            self._fit_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._frame.isVisible():
            self._fit_pixmap()

    def _fit_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        width = max(140, self._image.width() - 8)
        height = max(90, self._image.height() - 8)
        self._image.setPixmap(
            self._source_pixmap.scaled(
                width,
                height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def _pixmap_for(self, preview: MediaPreview) -> QPixmap:
        if preview.thumbnail_png:
            pixmap = QPixmap()
            if pixmap.loadFromData(preview.thumbnail_png, "PNG"):
                return pixmap
        kind = preview.placeholder_kind
        if kind == "video":
            return self._badge("Видео", QColor("#1d4ed8"))
        if kind == "audio":
            return self._badge("Аудио", QColor("#0f766e"))
        if kind == "image":
            return self._badge("Изображение", QColor("#7c3aed"))
        if kind == "blocked":
            return self._badge("Нет превью", QColor("#9a3412"))
        return QPixmap()

    def _badge(self, text: str, color: QColor) -> QPixmap:
        pixmap = QPixmap(240, 140)
        pixmap.fill(color)
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()
        return pixmap
