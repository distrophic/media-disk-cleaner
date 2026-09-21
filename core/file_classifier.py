"""Классификатор пользовательских медиафайлов по расширению.

Расширение не является доказательством безопасности файла. Перед удалением
обязательна полная проверка ``SafetyValidator``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.constants import (
    CATEGORY_AUDIO,
    CATEGORY_IMAGE,
    CATEGORY_VIDEO,
    DANGEROUS_EXTENSIONS,
    MEDIA_CATEGORIES,
)

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tif",
        ".tiff",
        ".heic",
        ".heif",
        ".avif",
        ".ico",
        ".raw",
        ".cr2",
        ".cr3",
        ".nef",
        ".arw",
        ".dng",
    }
)

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".webm",
        ".mpeg",
        ".mpg",
        ".m4v",
        ".3gp",
        ".ts",
        ".mts",
        ".m2ts",
        ".flv",
    }
)

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".mp3",
        ".wav",
        ".flac",
        ".aac",
        ".ogg",
        ".opus",
        ".m4a",
        ".wma",
        ".aiff",
        ".ape",
        ".alac",
        ".mid",
        ".midi",
    }
)


def normalize_extension(value: str | Path) -> str:
    """Вернуть расширение с точкой в нижнем регистре."""
    if isinstance(value, Path):
        suffix = value.suffix
    else:
        text = value.strip()
        if not text:
            return ""
        if "/" in text or "\\" in text:
            suffix = Path(text).suffix
        elif text.startswith("."):
            suffix = text
        elif "." in text:
            suffix = "." + text.rsplit(".", 1)[-1]
        else:
            suffix = "." + text
    return suffix.casefold()


def is_dangerous_extension(extension: str) -> bool:
    return normalize_extension(extension) in DANGEROUS_EXTENSIONS


def default_extension_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for ext in IMAGE_EXTENSIONS:
        mapping[ext] = CATEGORY_IMAGE
    for ext in VIDEO_EXTENSIONS:
        mapping[ext] = CATEGORY_VIDEO
    for ext in AUDIO_EXTENSIONS:
        mapping[ext] = CATEGORY_AUDIO
    return mapping


class FileClassifier:
    """Сопоставление расширения и категории медиафайла.

    Пользовательские расширения из настроек можно передать в ``extra_extensions``,
    но опасные и системные расширения никогда не будут добавлены.
    """

    def __init__(self, extra_extensions: Mapping[str, str] | None = None) -> None:
        self._map: dict[str, str] = default_extension_map()
        if extra_extensions:
            self.apply_extra_extensions(extra_extensions)

    def apply_extra_extensions(self, extra_extensions: Mapping[str, str]) -> None:
        for raw_ext, raw_category in extra_extensions.items():
            ext = normalize_extension(raw_ext)
            category = str(raw_category).strip().casefold()
            if not ext or ext == ".":
                continue
            if is_dangerous_extension(ext):
                continue
            if category not in MEDIA_CATEGORIES:
                continue
            if ext in DANGEROUS_EXTENSIONS:
                continue
            self._map[ext] = category

    def classify(self, path: Path | str) -> str | None:
        extension = normalize_extension(Path(path) if not isinstance(path, Path) else path)
        if not extension:
            return None
        if is_dangerous_extension(extension):
            return None
        return self._map.get(extension)

    def classify_extension(self, extension: str) -> str | None:
        ext = normalize_extension(extension)
        if not ext or is_dangerous_extension(ext):
            return None
        return self._map.get(ext)

    def is_allowed_media_extension(self, extension: str) -> bool:
        return self.classify_extension(extension) is not None

    def allowed_extensions(self) -> frozenset[str]:
        return frozenset(self._map.keys())

    def category_for_path(self, path: Path) -> str | None:
        return self.classify(path)


DEFAULT_CLASSIFIER = FileClassifier()
