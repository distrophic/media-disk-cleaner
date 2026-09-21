"""Безопасное перемещение выбранных медиафайлов в корзину.

Не принимает произвольный Path. Не использует os.remove, Path.unlink,
shutil.rmtree и оболочку. Ошибка одного файла не останавливает остальные.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from send2trash import send2trash

from app.constants import PURPOSE_RECYCLE, REASON_NOT_SELECTED, REASON_OK
from core.safety_validator import SafetyValidator
from models.media_file import MediaFile
from models.safety_result import VerifiedMediaTarget

logger = logging.getLogger("media_disk_cleaner.recycle")

TrashFn = Callable[[str], None]


@dataclass(slots=True)
class RecycleItemResult:
    path: Path
    name: str
    moved: bool
    skipped: bool
    error: bool
    reason: str
    size_bytes: int = 0


@dataclass(slots=True)
class RecycleReport:
    moved: int = 0
    skipped: int = 0
    errors: int = 0
    freed_bytes: int = 0
    items: list[RecycleItemResult] = field(default_factory=list)

    @property
    def moved_paths(self) -> list[Path]:
        return [item.path for item in self.items if item.moved]


class RecycleService:
    """Корзина только для VerifiedMediaTarget после повторной проверки."""

    def __init__(
        self,
        validator: SafetyValidator | None = None,
        trash_fn: TrashFn | None = None,
    ) -> None:
        self._validator = validator if validator is not None else SafetyValidator()
        self._trash = trash_fn if trash_fn is not None else send2trash

    def recycle_selected(self, files: Sequence[MediaFile]) -> RecycleReport:
        report = RecycleReport()
        for media in files:
            item = self._recycle_one(media)
            report.items.append(item)
            if item.moved:
                report.moved += 1
                report.freed_bytes += item.size_bytes
            elif item.error:
                report.errors += 1
            else:
                report.skipped += 1
        return report

    def recycle_verified(self, target: VerifiedMediaTarget) -> RecycleItemResult:
        """Повторная проверка непосредственно перед send2trash."""
        if not isinstance(target, VerifiedMediaTarget):
            return RecycleItemResult(
                path=Path(),
                name="",
                moved=False,
                skipped=True,
                error=False,
                reason="invalid_target_type",
            )
        if not target.explicitly_selected:
            return RecycleItemResult(
                path=target.normalized_path,
                name=target.normalized_path.name,
                moved=False,
                skipped=True,
                error=False,
                reason=REASON_NOT_SELECTED,
                size_bytes=target.size_bytes,
            )
        safety = self._validator.is_safe_media_file(
            target.normalized_path,
            scan_roots=[target.scan_root],
            explicitly_selected=True,
            expected_metadata=_metadata_from_target(target),
            expected_category=target.category,
            expected_path=target.normalized_path,
            purpose=PURPOSE_RECYCLE,
        )
        if not safety.safe or not safety.allows_recycle or safety.category is None:
            logger.info("recycle skipped %s (%s)", target.normalized_path, safety.reason)
            return RecycleItemResult(
                path=target.normalized_path,
                name=target.normalized_path.name,
                moved=False,
                skipped=True,
                error=False,
                reason=safety.reason,
                size_bytes=target.size_bytes,
            )
        try:
            self._trash(str(safety.normalized_path))
        except OSError as exc:
            logger.warning("send2trash failed %s: %s", safety.normalized_path, exc)
            return RecycleItemResult(
                path=safety.normalized_path,
                name=safety.normalized_path.name,
                moved=False,
                skipped=False,
                error=True,
                reason=f"send2trash:{exc.__class__.__name__}",
                size_bytes=target.size_bytes,
            )
        except Exception as exc:
            logger.warning("send2trash unexpected %s: %s", safety.normalized_path, exc)
            return RecycleItemResult(
                path=safety.normalized_path,
                name=safety.normalized_path.name,
                moved=False,
                skipped=False,
                error=True,
                reason=f"send2trash:{exc.__class__.__name__}",
                size_bytes=target.size_bytes,
            )
        logger.info("moved to recycle bin: %s", safety.normalized_path)
        return RecycleItemResult(
            path=safety.normalized_path,
            name=safety.normalized_path.name,
            moved=True,
            skipped=False,
            error=False,
            reason=REASON_OK,
            size_bytes=int(safety.size_bytes or target.size_bytes),
        )

    def _recycle_one(self, media: MediaFile) -> RecycleItemResult:
        if not media.is_selected:
            return RecycleItemResult(
                path=media.normalized_path,
                name=media.name,
                moved=False,
                skipped=True,
                error=False,
                reason=REASON_NOT_SELECTED,
                size_bytes=media.size_bytes,
            )
        safety = self._validator.is_safe_media_file(
            media.normalized_path,
            scan_roots=[media.scan_root],
            explicitly_selected=True,
            expected_metadata=media.expected_metadata(),
            expected_category=media.category,
            expected_path=media.normalized_path,
            purpose=PURPOSE_RECYCLE,
        )
        if not safety.safe or not safety.allows_recycle or safety.category is None:
            logger.info("prepare skipped %s (%s)", media.normalized_path, safety.reason)
            return RecycleItemResult(
                path=media.normalized_path,
                name=media.name,
                moved=False,
                skipped=True,
                error=False,
                reason=safety.reason,
                size_bytes=media.size_bytes,
            )
        target = VerifiedMediaTarget(
            normalized_path=safety.normalized_path,
            category=safety.category,
            size_bytes=int(safety.size_bytes or media.size_bytes),
            modified_timestamp=safety.modified_timestamp,
            mtime_ns=safety.mtime_ns,
            scan_root=media.scan_root,
            extension=safety.extension or media.extension,
            explicitly_selected=True,
        )
        return self.recycle_verified(target)


def _metadata_from_target(target: VerifiedMediaTarget):
    from models.safety_result import ExpectedMetadata

    return ExpectedMetadata(
        size_bytes=target.size_bytes,
        modified_timestamp=target.modified_timestamp,
        mtime_ns=target.mtime_ns,
        extension=target.extension,
    )
