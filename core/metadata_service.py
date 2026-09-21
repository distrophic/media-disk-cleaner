"""Чтение метаданных и миниатюр изображений.

Сервис только читает. Он не удаляет файлы, не меняет ACL и не открывает
путь, пока SafetyValidator не подтвердил, что это обычный медиафайл.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.constants import (
    CATEGORY_AUDIO,
    CATEGORY_IMAGE,
    CATEGORY_VIDEO,
    PREVIEW_MAX_IMAGE_BYTES,
    PREVIEW_MAX_PIXELS,
    PREVIEW_THUMB_MAX_PX,
    PURPOSE_PREVIEW,
)
from core.safety_validator import SafetyValidator
from models.media_file import MediaFile

logger = logging.getLogger("media_disk_cleaner.metadata")

Image.MAX_IMAGE_PIXELS = PREVIEW_MAX_PIXELS

# Форматы, где Pillow обычно не даёт быструю миниатюру без плагинов.
_SKIP_THUMBNAIL_EXTENSIONS = frozenset(
    {".raw", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".heic", ".heif", ".avif"}
)


@dataclass(slots=True)
class MediaPreview:
    """Снимок для панели превью. Без объектов Qt."""

    request_id: int
    name: str
    path_text: str
    category: str
    extension: str
    size_bytes: int
    created_at: datetime | None
    modified_at: datetime | None
    width: int | None = None
    height: int | None = None
    thumbnail_png: bytes | None = None
    placeholder_kind: str = "empty"
    message: str = ""
    safe: bool = False


class MetadataService:
    """Метаданные и миниатюры. Не принимает непроверенный Path из UI."""

    def __init__(self, validator: SafetyValidator | None = None) -> None:
        self._validator = validator if validator is not None else SafetyValidator()

    def preview_for(self, media: MediaFile | None, *, request_id: int) -> MediaPreview:
        if media is None:
            return MediaPreview(
                request_id=request_id,
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
        base = self._from_scan_snapshot(media, request_id)
        roots: Collection[Path] = (media.scan_root,)
        result = self._validator.is_safe_media_file(
            media.path,
            scan_roots=roots,
            explicitly_selected=False,
            expected_metadata=media.expected_metadata(),
            expected_category=media.category,
            expected_path=media.normalized_path,
            purpose=PURPOSE_PREVIEW,
        )
        if not result.safe:
            base.safe = False
            base.message = (
                "Превью не открыто: файл не прошёл повторную проверку. "
                f"Причина: {result.reason}."
            )
            base.placeholder_kind = "blocked"
            return base
        base.safe = True
        if media.category == CATEGORY_IMAGE:
            self._fill_image(base, result.normalized_path, media.extension, media.size_bytes)
        elif media.category == CATEGORY_VIDEO:
            base.placeholder_kind = "video"
            base.message = "Миниатюра кадра для видео не извлекается. Показаны сведения файла."
        elif media.category == CATEGORY_AUDIO:
            base.placeholder_kind = "audio"
            base.message = "Для аудио показаны сведения файла."
        else:
            base.placeholder_kind = "blocked"
            base.message = "Неизвестная категория."
        return base

    def _from_scan_snapshot(self, media: MediaFile, request_id: int) -> MediaPreview:
        return MediaPreview(
            request_id=request_id,
            name=media.name,
            path_text=str(media.normalized_path),
            category=media.category,
            extension=media.extension,
            size_bytes=media.size_bytes,
            created_at=media.created_at,
            modified_at=media.modified_at,
            placeholder_kind=media.category if media.category else "empty",
        )

    def _fill_image(
        self,
        preview: MediaPreview,
        path: Path,
        extension: str,
        size_bytes: int,
    ) -> None:
        preview.placeholder_kind = "image"
        if size_bytes > PREVIEW_MAX_IMAGE_BYTES:
            preview.message = (
                "Файл слишком большой для миниатюры. Показаны имя, путь и даты."
            )
            return
        if extension.casefold() in _SKIP_THUMBNAIL_EXTENSIONS:
            preview.message = (
                "Для этого формата миниатюра не строится. Показаны сведения файла."
            )
            return
        try:
            with Image.open(path) as image:
                width, height = image.size
                preview.width = int(width)
                preview.height = int(height)
                pixels = int(width) * int(height)
                if pixels > PREVIEW_MAX_PIXELS:
                    preview.message = "Изображение слишком большое для миниатюры."
                    return
                try:
                    image = ImageOps.exif_transpose(image)
                except (OSError, ValueError, SyntaxError):
                    pass
                image.thumbnail(
                    (PREVIEW_THUMB_MAX_PX, PREVIEW_THUMB_MAX_PX),
                    Image.Resampling.LANCZOS,
                )
                if image.mode not in {"RGB", "RGBA"}:
                    image = image.convert("RGBA" if "A" in image.mode else "RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG", optimize=False)
                preview.thumbnail_png = buffer.getvalue()
                preview.message = ""
        except Image.DecompressionBombError:
            preview.message = "Изображение отклонено как потенциально опасное по числу пикселей."
            preview.placeholder_kind = "blocked"
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
            logger.info("Preview decode skipped for %s: %s", path, exc)
            preview.message = "Не удалось прочитать изображение. Показаны сведения файла."
            preview.placeholder_kind = "image"
