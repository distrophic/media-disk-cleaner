"""Фоновая загрузка превью без блокировки GUI."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from core.metadata_service import MediaPreview, MetadataService
from models.media_file import MediaFile


class PreviewSignals(QObject):
    ready = Signal(object)


class PreviewWorker(QRunnable):
    """Читает метаданные в пуле потоков. Не удаляет файлы."""

    def __init__(
        self,
        media: MediaFile | None,
        request_id: int,
        service: MetadataService,
        signals: PreviewSignals,
    ) -> None:
        super().__init__()
        self.setAutoDelete(True)
        self._media = media
        self._request_id = request_id
        self._service = service
        self._signals = signals

    def run(self) -> None:
        try:
            payload = self._service.preview_for(self._media, request_id=self._request_id)
        except Exception as exc:
            payload = MediaPreview(
                request_id=self._request_id,
                name=self._media.name if self._media is not None else "",
                path_text=str(self._media.normalized_path) if self._media is not None else "",
                category=self._media.category if self._media is not None else "",
                extension=self._media.extension if self._media is not None else "",
                size_bytes=self._media.size_bytes if self._media is not None else 0,
                created_at=self._media.created_at if self._media is not None else None,
                modified_at=self._media.modified_at if self._media is not None else None,
                placeholder_kind="blocked",
                message=f"Ошибка превью: {exc.__class__.__name__}",
            )
        self._signals.ready.emit(payload)
