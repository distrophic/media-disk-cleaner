"""Безопасный обход пользовательских каталогов.

Сканер только читает метаданные. Он не удаляет файлы, не меняет ACL,
не следует по symlink/junction и не запрашивает права администратора.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.constants import (
    CATEGORY_AUDIO,
    CATEGORY_IMAGE,
    CATEGORY_VIDEO,
    PURPOSE_INDEX,
    QUICK_SCAN_FOLDER_NAMES,
    SAFETY_STATUS_SAFE,
    SCAN_BATCH_SIZE,
    SCAN_MAX_DEPTH,
    SCAN_MAX_SKIPPED_REASONS,
    SCAN_MODE_EXTENDED,
    SCAN_MODE_QUICK,
    SCAN_MODE_SELECTIVE,
)
from core.file_classifier import FileClassifier
from core.safety_validator import (
    SafetyValidator,
    is_component_prefix,
    is_directory_no_follow,
    is_excluded_system_path,
    is_hidden_entry,
    is_symlink_or_reparse,
    normalize_windows_path,
    path_components,
    path_exists_no_follow,
)
from models.media_file import MediaFile
from models.scan_result import ScanResult, ScanSummary

logger = logging.getLogger("media_disk_cleaner.scanner")

ProgressCallback = Callable[["ScanProgress"], None]
BatchCallback = Callable[[list[MediaFile]], None]


@dataclass(slots=True)
class ScanOptions:
    """Параметры одного запуска сканера."""

    mode: str = SCAN_MODE_SELECTIVE
    include_hidden: bool = False
    min_size_bytes: int = 0
    batch_size: int = SCAN_BATCH_SIZE
    max_depth: int = SCAN_MAX_DEPTH
    extra_extensions: dict[str, str] | None = None


@dataclass(slots=True)
class ScanProgress:
    current_folder: str
    files_checked: int
    media_found: int
    total_size_bytes: int
    elapsed_seconds: float
    roots_total: int
    roots_done: int
    cancelled: bool = False


@dataclass(slots=True)
class _DirJob:
    path: Path
    scan_root: Path
    depth: int
    is_scan_root: bool


def get_current_user_home(home: Path | None = None) -> Path:
    if home is not None:
        resolved = normalize_windows_path(home)
        return resolved if resolved is not None else Path(home)
    return Path.home()


def get_quick_scan_roots(home: Path | None = None) -> list[Path]:
    """Стандартные пользовательские папки текущей учётной записи.

    Не включает корень C:\\ и профили других пользователей.
    Существование проверяется без обхода содержимого.
    """
    base = get_current_user_home(home)
    roots: list[Path] = []
    for name in QUICK_SCAN_FOLDER_NAMES:
        candidate = base / name
        normalized = normalize_windows_path(candidate)
        if normalized is None:
            continue
        if is_drive_root(normalized):
            continue
        if is_excluded_system_path(normalized):
            continue
        if not _directory_exists_for_root(normalized):
            continue
        roots.append(normalized)
    return roots


def is_drive_root(path: Path) -> bool:
    components = path_components(path)
    return components is not None and len(components) == 1


def _directory_exists_for_root(path: Path) -> bool:
    if not path_exists_no_follow(path):
        return False
    if is_directory_no_follow(path):
        return True
    return is_symlink_or_reparse(path)


def _is_cancelled(cancel_event: threading.Event | None) -> bool:
    return cancel_event is not None and cancel_event.is_set()


class Scanner:
    """Итеративный обход каталогов с защитой от циклов и отменой."""

    def __init__(
        self,
        validator: SafetyValidator | None = None,
        classifier: FileClassifier | None = None,
    ) -> None:
        self._classifier = classifier if classifier is not None else FileClassifier()
        self._validator = (
            validator if validator is not None else SafetyValidator(self._classifier)
        )

    def _classifier_for_options(self, options: ScanOptions) -> FileClassifier:
        extras: dict[str, str] = {}
        for ext in self._classifier.allowed_extensions():
            category = self._classifier.classify_extension(ext)
            if category:
                extras[ext] = category
        if options.extra_extensions:
            extras.update(options.extra_extensions)
        return FileClassifier(extras)

    def scan(
        self,
        roots: Sequence[Path],
        *,
        options: ScanOptions | None = None,
        cancel_event: threading.Event | None = None,
        on_batch: BatchCallback | None = None,
        on_progress: ProgressCallback | None = None,
        user_home: Path | None = None,
    ) -> ScanResult:
        opts = options if options is not None else ScanOptions()
        original_classifier = self._classifier
        original_validator = self._validator
        self._classifier = self._classifier_for_options(opts)
        self._validator = SafetyValidator(self._classifier)
        started = datetime.now()
        started_mono = time.monotonic()
        summary = ScanSummary()
        result = ScanResult(
            roots=[],
            files=[],
            summary=summary,
            started_at=started,
            mode=opts.mode,
        )

        try:
            prepared = self._prepare_roots(roots, opts.mode, user_home)
            result.roots = list(prepared)
            if not prepared:
                result.finished_at = datetime.now()
                summary.elapsed_seconds = time.monotonic() - started_mono
                self._emit_progress(
                    on_progress,
                    folder="",
                    summary=summary,
                    started_mono=started_mono,
                    roots_total=0,
                    roots_done=0,
                    cancelled=False,
                )
                return result

            visited_dirs: set[tuple[str, ...]] = set()
            seen_files: set[tuple[str, ...]] = set()
            batch: list[MediaFile] = []
            batch_size = max(1, int(opts.batch_size))
            current_user = get_current_user_home(user_home).name.casefold()
            roots_done = 0

            def flush_batch(force: bool = False) -> None:
                if not batch:
                    return
                if not force and len(batch) < batch_size:
                    return
                chunk = list(batch)
                batch.clear()
                result.files.extend(chunk)
                if on_batch is not None:
                    on_batch(chunk)

            def skip(path: Path, reason: str) -> None:
                logger.info("skip %s (%s)", path, reason)
                if len(result.skipped_path_reasons) < SCAN_MAX_SKIPPED_REASONS:
                    result.skipped_path_reasons.append((str(path), reason))

            for root in prepared:
                if _is_cancelled(cancel_event):
                    summary.cancelled = True
                    break
                self._walk_root(
                    root=root,
                    all_roots=prepared,
                    options=opts,
                    cancel_event=cancel_event,
                    visited_dirs=visited_dirs,
                    seen_files=seen_files,
                    batch=batch,
                    summary=summary,
                    skip=skip,
                    flush_batch=flush_batch,
                    on_progress=on_progress,
                    started_mono=started_mono,
                    roots_total=len(prepared),
                    roots_done=roots_done,
                    current_user=current_user,
                )
                roots_done += 1
                self._emit_progress(
                    on_progress,
                    folder=str(root),
                    summary=summary,
                    started_mono=started_mono,
                    roots_total=len(prepared),
                    roots_done=roots_done,
                    cancelled=summary.cancelled,
                )
                if summary.cancelled:
                    break

            flush_batch(force=True)
            result.finished_at = datetime.now()
            summary.elapsed_seconds = time.monotonic() - started_mono
            return result
        finally:
            self._classifier = original_classifier
            self._validator = original_validator

    def _prepare_roots(
        self,
        roots: Sequence[Path],
        mode: str,
        user_home: Path | None,
    ) -> list[Path]:
        if mode == SCAN_MODE_QUICK:
            candidates = get_quick_scan_roots(user_home)
        else:
            candidates = [Path(item) for item in roots]

        prepared: list[Path] = []
        seen: set[tuple[str, ...]] = set()
        for raw in candidates:
            normalized = normalize_windows_path(raw)
            if normalized is None:
                continue
            if mode == SCAN_MODE_QUICK and is_drive_root(normalized):
                continue
            if is_excluded_system_path(normalized):
                logger.info("scan root excluded as system path: %s", normalized)
                continue
            if not _directory_exists_for_root(normalized):
                logger.info("scan root missing or inaccessible: %s", normalized)
                continue
            key = path_components(normalized)
            if key is None or key in seen:
                continue
            seen.add(key)
            prepared.append(normalized)
        return prepared

    def _walk_root(
        self,
        *,
        root: Path,
        all_roots: Sequence[Path],
        options: ScanOptions,
        cancel_event: threading.Event | None,
        visited_dirs: set[tuple[str, ...]],
        seen_files: set[tuple[str, ...]],
        batch: list[MediaFile],
        summary: ScanSummary,
        skip: Callable[[Path, str], None],
        flush_batch: Callable[..., None],
        on_progress: ProgressCallback | None,
        started_mono: float,
        roots_total: int,
        roots_done: int,
        current_user: str,
    ) -> None:
        stack: list[_DirJob] = [
            _DirJob(path=root, scan_root=root, depth=0, is_scan_root=True)
        ]
        while stack:
            if _is_cancelled(cancel_event):
                summary.cancelled = True
                return
            job = stack.pop()
            if job.depth > options.max_depth:
                skip(job.path, "max_depth_exceeded")
                summary.skipped_directories += 1
                continue
            if not self._register_directory(job.path, visited_dirs, allow_reparse=job.is_scan_root):
                skip(job.path, "duplicate_or_unreadable_directory")
                summary.skipped_directories += 1
                continue
            if not job.is_scan_root:
                if is_excluded_system_path(job.path):
                    skip(job.path, "system_excluded_path")
                    summary.skipped_directories += 1
                    continue
                if is_symlink_or_reparse(job.path):
                    skip(job.path, "reparse_point")
                    summary.skipped_directories += 1
                    continue
                if self._is_foreign_user_profile(job.path, all_roots, current_user):
                    skip(job.path, "foreign_user_profile")
                    summary.skipped_directories += 1
                    continue
                if not options.include_hidden and is_hidden_entry(job.path):
                    skip(job.path, "hidden_directory")
                    summary.skipped_directories += 1
                    continue
            summary.directories_visited += 1
            self._emit_progress(
                on_progress,
                folder=str(job.path),
                summary=summary,
                started_mono=started_mono,
                roots_total=roots_total,
                roots_done=roots_done,
                cancelled=False,
            )
            children = self._list_dir(job.path, summary, skip)
            if children is None:
                continue
            for entry in children:
                if _is_cancelled(cancel_event):
                    summary.cancelled = True
                    return
                try:
                    entry_path = Path(entry.path)
                except (OSError, ValueError, TypeError):
                    summary.access_errors += 1
                    continue
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                    is_link = entry.is_symlink()
                except OSError as exc:
                    summary.access_errors += 1
                    skip(entry_path, f"entry_stat_error:{exc.__class__.__name__}")
                    continue
                if is_link or is_symlink_or_reparse(entry_path):
                    skip(entry_path, "symlink_or_reparse")
                    if is_dir:
                        summary.skipped_directories += 1
                    else:
                        summary.skipped_files += 1
                    continue
                if is_dir:
                    stack.append(
                        _DirJob(
                            path=entry_path,
                            scan_root=job.scan_root,
                            depth=job.depth + 1,
                            is_scan_root=False,
                        )
                    )
                    continue
                if is_file:
                    self._handle_file(
                        entry_path,
                        scan_root=job.scan_root,
                        options=options,
                        seen_files=seen_files,
                        batch=batch,
                        summary=summary,
                        skip=skip,
                        flush_batch=flush_batch,
                    )

    def _handle_file(
        self,
        path: Path,
        *,
        scan_root: Path,
        options: ScanOptions,
        seen_files: set[tuple[str, ...]],
        batch: list[MediaFile],
        summary: ScanSummary,
        skip: Callable[[Path, str], None],
        flush_batch: Callable[..., None],
    ) -> None:
        summary.files_checked += 1
        key = path_components(path)
        if key is None:
            skip(path, "invalid_path")
            summary.skipped_files += 1
            return
        if key in seen_files:
            skip(path, "duplicate_file")
            summary.skipped_files += 1
            return
        seen_files.add(key)
        if not options.include_hidden and is_hidden_entry(path):
            skip(path, "hidden_file")
            summary.skipped_files += 1
            return
        if self._classifier.classify(path) is None:
            return
        try:
            safety = self._validator.is_safe_media_file(
                path,
                scan_roots=[scan_root],
                explicitly_selected=False,
                purpose=PURPOSE_INDEX,
            )
        except OSError as exc:
            summary.access_errors += 1
            skip(path, f"validator_os_error:{exc.__class__.__name__}")
            summary.skipped_files += 1
            return
        if not safety.safe or not safety.allows_index or safety.category is None:
            skip(path, safety.reason)
            summary.skipped_files += 1
            return
        size = int(safety.size_bytes or 0)
        if options.min_size_bytes > 0 and size < options.min_size_bytes:
            skip(path, "below_min_size")
            summary.skipped_files += 1
            return
        media = self._to_media_file(path, scan_root, safety)
        if media is None:
            skip(path, "media_record_failed")
            summary.skipped_files += 1
            return
        media.is_selected = False
        batch.append(media)
        summary.files_found += 1
        summary.total_size_bytes += media.size_bytes
        self._add_category_totals(summary, media)
        flush_batch(force=False)

    def _to_media_file(
        self,
        path: Path,
        scan_root: Path,
        safety,
    ) -> MediaFile | None:
        try:
            stats = path.lstat()
        except OSError:
            return None
        created_ts: float | None
        try:
            created_ts = float(stats.st_ctime)
            created_at = datetime.fromtimestamp(created_ts)
        except (OSError, OverflowError, ValueError):
            created_ts = None
            created_at = None
        modified_at = None
        if safety.modified_timestamp is not None:
            try:
                modified_at = datetime.fromtimestamp(float(safety.modified_timestamp))
            except (OverflowError, ValueError, OSError):
                modified_at = None
        normalized = safety.normalized_path
        attrs = int(getattr(stats, "st_file_attributes", 0) or 0)
        return MediaFile(
            path=normalized,
            name=normalized.name,
            extension=safety.extension or path.suffix,
            category=safety.category or "",
            size_bytes=int(safety.size_bytes or 0),
            created_at=created_at,
            modified_at=modified_at,
            drive=str(normalized.drive),
            parent_folder=normalized.parent,
            is_selected=False,
            scan_root=scan_root,
            safety_status=SAFETY_STATUS_SAFE,
            safety_reason=safety.reason,
            scanned_size_bytes=int(safety.size_bytes or 0),
            scanned_modified_timestamp=safety.modified_timestamp,
            normalized_path=normalized,
            file_identity=(int(safety.size_bytes or 0), safety.mtime_ns, attrs),
            mtime_ns=safety.mtime_ns,
            created_timestamp=created_ts,
        )

    def _add_category_totals(self, summary: ScanSummary, media: MediaFile) -> None:
        if media.category == CATEGORY_IMAGE:
            summary.image_count += 1
            summary.image_size_bytes += media.size_bytes
        elif media.category == CATEGORY_VIDEO:
            summary.video_count += 1
            summary.video_size_bytes += media.size_bytes
        elif media.category == CATEGORY_AUDIO:
            summary.audio_count += 1
            summary.audio_size_bytes += media.size_bytes

    def _register_directory(
        self,
        path: Path,
        visited_dirs: set[tuple[str, ...]],
        *,
        allow_reparse: bool,
    ) -> bool:
        key = path_components(path)
        if key is None:
            return False
        if key in visited_dirs:
            return False
        resolved_key: tuple[str, ...] | None = None
        if not is_symlink_or_reparse(path) or allow_reparse:
            try:
                resolved = path.resolve(strict=False)
                resolved_key = path_components(resolved)
            except (OSError, RuntimeError, ValueError):
                resolved_key = None
            if resolved_key is not None and resolved_key in visited_dirs:
                return False
        visited_dirs.add(key)
        if resolved_key is not None:
            visited_dirs.add(resolved_key)
        return True

    def _is_foreign_user_profile(
        self,
        path: Path,
        scan_roots: Sequence[Path],
        current_user: str,
    ) -> bool:
        components = path_components(path)
        if components is None or len(components) < 3:
            return False
        if components[1] != "users":
            return False
        profile_name = components[2]
        if profile_name in {current_user, "public", "default", "all users"}:
            return False
        profile = components[:3]
        for root in scan_roots:
            root_components = path_components(root)
            if root_components is None:
                continue
            if is_component_prefix(profile, root_components):
                return False
        return True

    def _list_dir(
        self,
        path: Path,
        summary: ScanSummary,
        skip: Callable[[Path, str], None],
    ) -> list[os.DirEntry[str]] | None:
        try:
            with os.scandir(path) as iterator:
                return list(iterator)
        except PermissionError:
            summary.access_errors += 1
            summary.skipped_directories += 1
            skip(path, "permission_denied")
            return None
        except FileNotFoundError:
            summary.skipped_directories += 1
            skip(path, "missing_directory")
            return None
        except OSError as exc:
            summary.access_errors += 1
            summary.skipped_directories += 1
            skip(path, f"os_error:{exc.__class__.__name__}")
            return None

    def _emit_progress(
        self,
        on_progress: ProgressCallback | None,
        *,
        folder: str,
        summary: ScanSummary,
        started_mono: float,
        roots_total: int,
        roots_done: int,
        cancelled: bool,
    ) -> None:
        if on_progress is None:
            return
        on_progress(
            ScanProgress(
                current_folder=folder,
                files_checked=summary.files_checked,
                media_found=summary.files_found,
                total_size_bytes=summary.total_size_bytes,
                elapsed_seconds=time.monotonic() - started_mono,
                roots_total=roots_total,
                roots_done=roots_done,
                cancelled=cancelled,
            )
        )


# Имена режимов реэкспортируются для UI следующих этапов.
SCAN_MODES = (SCAN_MODE_QUICK, SCAN_MODE_SELECTIVE, SCAN_MODE_EXTENDED)
